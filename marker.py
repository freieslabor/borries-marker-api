#!/usr/bin/env python3.5
# -*- coding: utf-8 -*-

import threading
import logging
import time
import serial
from datetime import datetime, timedelta


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
        """Number of successfull commands."""
        return self.__done * self.multiplier

    @property
    def ready(self):
        """True if all commands were executed successfull, False otherwise."""
        return self.done == self.tbd

    @property
    def perc_done(self):
        """Percentage, e.g. 14.22."""
        return (self.done / float(self.tbd)) * 100

    def increment_done(self):
        """Increment done counter."""
        self.__done += 1

    def __str__(self):
        return '%d/%d' % (self.done, self.tbd)


class Marker(threading.Thread):
    """Borries marker representation."""
    MAX_X = 122.5
    MAX_Y = 102.5

    def __init__(self, device, slow_motion=False, log_level=logging.DEBUG):

        """Initializes marker and moves to home position."""
        threading.Thread.__init__(self)
        self.lock = threading.RLock()
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            datefmt='%H:%M:%S')

        self.__x = 0
        self.__y = 0

        # command buffers
        self.read_buf = r''
        self.write_buf = r''

        self.daemon = True
        self.running = True
        self.start_time = None
        self.error_message = None
        self.homed = [0, 0]

        self.__serial = serial.Serial(device, timeout=0)
        self.emergency_off_done = False
        # count<prefix of answer, SerialAnswer object>
        self.count = {
            'ST': SerialAnswer(.5),  # movement
        }

        # slow motion mode
        if slow_motion:
            self.write_buf += INIT % (650, 650, 220)
        else:
            self.write_buf += INIT % (6500, 6500, 2200)

        # init sends 12 answers when done
        self.count['ST'].tbd += 12

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

                if count.done > 0 and not self.start_time:
                    self.start_time = datetime.now()

                # start estimation when enough data is available
                if self.start_time and count.done > 2:
                    runtime = (datetime.now() - self.start_time).seconds
                    eta_seconds = (runtime * (1 - (count.perc_done/100.0))) / \
                        (count.perc_done/100.0)
                    eta = timedelta(seconds=eta_seconds)

                    days, seconds = eta.days, eta.seconds
                    hrs = days * 24 + seconds // 3600
                    min = (seconds % 3600) // 60
                    sec = seconds % 60

                    logging.info('%s %s executed; %.2f%%; ETA: '
                                 '%02d:%02d:%02d.' % (count, prefix,
                                                      count.perc_done,
                                                      hrs, min, sec))

    def position(self):
        """Returns x and y position as tuple."""
        return self.__x, self.__y

    def error_msg(self):
        """Returns error message or None in case of no error."""
        return self.error_message

    def homed_axes(self):
        """Returns list of axes, 1 for homed otherwise 0."""
        return self.homed

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

        self.homed = [1, 1]

    def emergency_off(self, cause='client'):
        """Sends emergency off sequence."""
        # make sure write buffer won't get send anymore
        self.running = False
        # do not use write buffer, send directly
        self.__serial.write(EMERGENCY_OFF.encode())
        self.__serial.flush()
        err = 'Emergency off triggered by %s' % cause
        logging.error(err)
        self.emergency_off_done = True

    def move_rel(self, x, y, batch=False):
        """Moves to given relative position."""
        if not self.homed == [1, 1]:
            self.error_message = 'Home all axes before moving around.'
            if batch:
                self.emergency_off('Not all axes homed.')
            else:
                return

        if not (0 <= x + self.__x <= self.MAX_X and
                0 <= y + self.__y <= self.MAX_Y):

            self.error_message = '(%02.2f,%02.2f) out of bounds.' \
                % (self.__x + x, self.__y + y)
            if batch:
                self.emergency_off('(%02.2f,%02.2f) out of bounds.'
                                   % (self.__x + x, self.__y + y))
            else:
                return

        x = round(x, 2)
        y = round(y, 2)
        self.write_buf += r';*PR%02.2f,%02.2f;;*SH;*OA;*SE;' % (x, y)

        self.__x = self.__x + x
        self.__y = self.__y + y
        self.count['ST'].tbd += 1

    def move_abs(self, x, y, batch=False):
        """Moves to given absolute position."""
        rel_x = x - self.__x
        rel_y = y - self.__y
        self.move_rel(rel_x, rel_y, batch=batch)

    def needle_down(self):
        """Moves the needle marking unit down."""
        self.write_buf += NEEDLE
        self.count['ST'].tbd += 1

    def run(self):
        """Thread loop."""
        while self.running:
            if ';;' not in self.write_buf:
                # send heartbeat when there's nothing else to do
                with self.lock:
                    self.write_buf += ';*SH;;*SH;'

            # write/read commands to/from buffer
            while ';;' in self.write_buf and self.running:
                with self.lock:
                    datagram, self.write_buf = self.write_buf.split(';;', 1)
                    self.__serial.write((';%s;' % datagram).encode())
                    logging.debug('write: ;%s;' % datagram)
                    self.read()
                    self.__serial.flush()

            time.sleep(.1)


if __name__ == '__main__':
    m = Marker('/dev/ttyUSB1')
    m.start()

    # move to home position for next session
    m.home()

    # wait for thread to be finished
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            m.emergency_off('^C')
