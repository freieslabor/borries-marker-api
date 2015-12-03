#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import logging
import time
import serial
import re
from datetime import datetime, timedelta
try:
    import Image
    import ImageDraw
except ImportError:
    from PIL import Image
    from PIL import ImageDraw


INIT = '*SQ;;*SQ;;*SQ;*CB;*INITstn;*INITzn;*DB;*CPa;*SE;*CPz;*CPd;' \
        '*CPa;*SE;*INITp301;*OI;;*CPa;*RTEOF;*SE;*INITwn;*INITgn;*INITppn,' \
        'pj;*INITzpj;*INITzn;*INITd16,0,5,500,20000;*INITdx15,0,30;*WD10;' \
        '*WU10;*SE;*INITs100.00,100.00;*INITo-100,-100;;*INITno0,0;*INITrd+,' \
        '+;*INITrr+,+;*INITrs+,+;LO1;*LBn;*INITesn,n;*INITze-,-;*VM6500,' \
        '6500;*VN%d,%d;*VS400,400;*SE;*VB%d;*VH600,600;*VP600,600;*VC600,' \
        '600;*SE;;*AC90000,90000;*LBd0.00;*LBm1.4,1.16;;*INITn1;;*INITxqrap;' \
        ';*INITxp5;*INITzs0;;*INITaen,asn,adj;*MO18E1,9600;*CPa;*SE;;' \
        '*INITbeL,0,beL,1,beL,2,beH,3,beL,4,beH,5,beH,6,beL,7,beL,8,beL,9,' \
        'beL,10,beL,11,beL,12,beL,13,beL,14,beL,15,beL,16,beL,17,beL,18,beL,' \
        '19,beL,20,beL,21,beL,22,beL,23,beL,24;*INITbaD,22,baD,21,baD,20,' \
        'baD,19,baD,18,baD,17,baD,16,baD,15,baD,14,baD,13,baD,12,baD,11,baD,' \
        '10,baD,9,baD,8,baD,7,baD,6,baD,5,baD,4,baD,3,baD,2,baD,1,ba0,0;*SE;' \
        ';;;*VP1200,1200;;*CPa;*RTEOF;*SE;CS6;*INITbe0,5;;*CPa;*RTEOF;' \
        '*SE;;*XRH;;*EB;*SE;;*SH;;*SH;;*SH;;*SH;;PU;;*INITrr+,+;'
HOME = ';*INITrd+,+;*RX;*RY;*RTHOME;*SH;;*SE;;*OA;;*SH;;*SE;'
MOVE = ';*PR%02.2f,%02.2f;;*SH;*OA;*SE;'
EMERGENCY_OFF = ';;*HE;;;'
NEEDLE = 'SP1;;PD;*WT250;PU;*SE;'


class SerialAnswer(object):
    """Answer type (movement, heartbeat..)."""
    # to be done
    tbd = 0
    # internal count of completed operations (multiplied by percentage)
    __done = 0
    # percentage multiplier
    multiplier = 1

    def __init__(self, multiplier):
        """Initialization with multiplier defining the fractional amount of
        messages needed for one complete answer."""
        self.multiplier = multiplier

    @property
    def done(self):
        return self.__done * self.multiplier

    @property
    def ready(self):
        return self.done == self.tbd

    @property
    def perc_done(self):
        return (self.done / float(self.tbd)) * 100

    def increment_done(self):
        self.__done += 1

    def __str__(self):
        return '%d/%d' % (self.done, self.tbd)


class Marker(threading.Thread):
    """Borries marker representation."""
    MAX_X = 122.5
    MAX_Y = 102.5

    __x = 0
    __y = 0

    read_buf = r''
    write_buf = r''

    daemon = True
    running = True

    def __init__(self, device, slow_motion=False, initial_check=False,
                 log_level=logging.INFO):

        """Initializes marker and moves to home position."""
        threading.Thread.__init__(self)
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            datefmt='%H:%M:%S')
        self.__serial = serial.Serial(device, timeout=0)
        self.checked = not initial_check
        # count<prefix of answer, SerialAnswer object>
        self.count = {
            'ST': SerialAnswer(.5),  # movement
        }
        self.start_time = datetime.now()

        if slow_motion:
            self.write_buf += INIT % (650, 650, 220)
        else:
            self.write_buf += INIT % (6500, 6500, 2200)

        # init sends 12 answers when done
        self.count['ST'].tbd += 12
        self.home()

    def read(self, size=102400):
        """Reads given amount of bytes in buffer and logs them."""
        self.read_buf += str(self.__serial.read(size), encoding='UTF-8')
        while '\r' in self.read_buf:
            answer, self.read_buf = self.read_buf.split('\r', 1)
            logging.debug('read: %s' % answer)

            # safe answer count per type
            prefix = answer.split()[0]
            if prefix in self.count:
                count = self.count[prefix]
                self.count[prefix].increment_done()
                runtime = (self.start_time - datetime.now()).seconds
                eta = timedelta(seconds=(100 / count.perc_done) * runtime)

                days, seconds = eta.days, eta.seconds
                hrs = days * 24 + seconds // 3600
                min = (seconds % 3600) // 60
                sec = seconds % 60

                logging.info('%s %s executed; %.2f%%; ETA: %02d:%02d:%02d.' %
                             (count, prefix, count.perc_done, hrs, min, sec))

    def position(self):
        """Returns x and y position as tuple."""
        return self.__x, self.__y

    def home(self):
        """Moves to home position and resets position counter."""
        # improve speed to home position: move to (1,1)
        if self.position() != (0, 0):
            self.move_abs(1, 1)

        self.write_buf += HOME
        # home sends 2 move answers when done
        self.count['ST'].tbd += 2

        self.__x = 0
        self.__y = 0

    def emergency_off(self, cause='client'):
        """Sends emergency off sequence."""
        # make sure write buffer won't get send anymore
        self.running = False
        # do not use write buffer, send directly
        self.__serial.write(EMERGENCY_OFF.encode())
        self.__serial.flush()
        err = 'Emergency off triggered by %s' % cause
        logging.error(err)
        raise Exception(err)

    def move_rel(self, x, y):
        """Moves to given relative position."""
        if 0 <= x + self.__x <= self.MAX_X and 0 <= y + self.__y <= self.MAX_Y:
            x = round(x, 2)
            y = round(y, 2)
            self.write_buf += r';*PR%02.2f,%02.2f;;*SH;*OA;*SE;' % (x, y)

            self.__x = self.__x + x
            self.__y = self.__y + y
            self.count['ST'].tbd += 1

        else:
            self.emergency_off('(%02.2f,%02.2f) out of bounds.'
                               % (self.__x + x, self.__y + y))

    def move_abs(self, x, y):
        """Moves to given absolute position."""
        rel_x = x - self.__x
        rel_y = y - self.__y
        self.move_rel(rel_x, rel_y)

    def needle_down(self):
        """Moves the needle marking unit down."""
        self.write_buf += NEEDLE
        self.count['ST'].tbd += 1

    def mark_picture(self, image_file, bounding_box, granularity=5):
        """Takes an image and marks it in the given bounding box."""
        # open image to file and convert to black and white
        start_x, start_y, end_x, end_y = bounding_box
        width = end_x - start_x
        height = end_y - start_y
        img = Image.open(image_file)

        if img.size[0] < width*granularity or img.size[1] < height*granularity:
            self.user_confirmation('Image resolution might be too low for '
                                   'given bounding box and granularity. Mark '
                                   'anyway?')

        img = img.resize((width*granularity, height*granularity),
                         Image.ANTIALIAS)
        granularity = float(granularity)
        img_bw = img.convert('1')
        for x in range(0, img_bw.size[0]):
            for y in range(0, img_bw.size[1]):
                pixel_value = img_bw.getpixel((x, y))
                if pixel_value == 0:
                    self.move_abs(start_x+(x*(1/granularity)),
                                  start_y+(y*(1/granularity)))
                    self.needle_down()

    def check(self, rds=10, preview_file='preview.png', dont_ask=False):
        start = datetime.now()

        white = (255, 255, 255)
        black = (0, 0, 0)

        im = Image.new('RGB', (int(self.MAX_X*100), int(self.MAX_Y*100)),
                       white)
        draw = ImageDraw.Draw(im)

        move_re = re.escape(MOVE).replace('\\%02\\.2f', '(\-?\d+\.\d\d)')
        move_re_cmpld = re.compile(move_re)
        x, y = (0, 0)
        pos = 0

        for n in re.finditer(re.escape(NEEDLE), self.write_buf):
            for move in move_re_cmpld.findall(self.write_buf[pos:n.start()]):
                x_rel, y_rel = move
                x += float(x_rel)
                y += float(y_rel)

                x = round(x, 2)
                y = round(y, 2)

                assert 0 <= x <= self.MAX_X, 'x value %02.2f not in range.' % x
                assert 0 <= y <= self.MAX_Y, 'y value %02.2f not in range.' % y

            pos = n.start()
            draw.ellipse((x*100-rds, y*100-rds, x*100+rds, y*100+rds), black)

        im.save(preview_file)

        # preview check by user
        logging.info('Preview saved as %s (took %s). Please check it.'
                     % (preview_file, datetime.now() - start))

        # preview check by user
        if not dont_ask:
            if not self.user_confirmation('Start marking?'):
                quit()

        self.checked = True

    def user_confirmation(self, question):
        cont = ' '
        while cont.lower() not in ['y', 'n']:
            cont = raw_input('%s [y/n]' % question)

        if cont.lower() == 'y':
            return True

        return False

    def run(self):
        """Thread loop."""
        while not self.checked:
            pass

        while self.running:
            if ';;' not in self.write_buf:
                self.write_buf += ';*SH;;*SH;'

            while ';;' in self.write_buf and self.running:
                datagram, self.write_buf = self.write_buf.split(';;', 1)
                self.__serial.write((';%s;' % datagram).encode())
                logging.debug('write: ;%s;' % datagram)
                self.read()
                self.__serial.flush()

            time.sleep(.1)


if __name__ == '__main__':
    m = Marker('/dev/ttyUSB1', initial_check=True)
    m.start()

    m.mark_picture('Logo_quadratisch.png', (0, 0, 50, 50))

    # check
    m.check()

    # move to home position for next session
    m.home()

    # wait for thread to be finished
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            m.emergency_off('^C')
