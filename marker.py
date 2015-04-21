#!/usr/bin/env python
# -*- coding: utf-8 -*-

import serial, logging, time, threading, math


INIT = "*SQ;;*SQ;;*SQ;*CB;*INITstn;*INITzn;*DB;*CPa;*SE;*CPz;*CPd;*CPa;*SE;*INITp301;*OI;;*CPa;*RTEOF;*SE;*INITwn;*INITgn;*INITppn,pj;*INITzpj;*INITzn;*INITd16,0,5,500,20000;*INITdx15,0,30;*WD10;*WU10;*SE;*INITs100.00,100.00;*INITo-100,-100;;*INITno0,0;*INITrd+,+;*INITrr+,+;*INITrs+,+;LO1;*LBn;*INITesn,n;*INITze-,-;*VM6500,6500;*VN6500,6500;*VS400,400;*SE;*VB2200;*VH600,600;*VP600,600;*VC600,600;*SE;;*AC90000,90000;*LBd0.00;*LBm1.4,1.16;;*INITn1;;*INITxqrap;;*INITxp5;*INITzs0;;*INITaen,asn,adj;*MO18E1,9600;*CPa;*SE;;*INITbeL,0,beL,1,beL,2,beH,3,beL,4,beH,5,beH,6,beL,7,beL,8,beL,9,beL,10,beL,11,beL,12,beL,13,beL,14,beL,15,beL,16,beL,17,beL,18,beL,19,beL,20,beL,21,beL,22,beL,23,beL,24;*INITbaD,22,baD,21,baD,20,baD,19,baD,18,baD,17,baD,16,baD,15,baD,14,baD,13,baD,12,baD,11,baD,10,baD,9,baD,8,baD,7,baD,6,baD,5,baD,4,baD,3,baD,2,baD,1,ba0,0;*SE;;;;*VP1200,1200;;*CPa;*RTEOF;*SE;CS6;*INITbe0,5;;*CPa;*RTEOF;*SE;;*XRH;;*EB;*SE;;*SH;;*SH;;*SH;;*SH;;PU;;*INITrr+,+;"

HOME = r";*INITrd+,+;*RX;*RY;*RTHOME;*SH;;*SE;;*OA;;*SH;;*SE;"

NOT_AUS = r';;*HE;;;'

class Marker(threading.Thread):
    MAX_X = 122.5
    MAX_Y = 102.5

    __x = 0
    __y = 0
    read_buf = r''
    write_buf = r''
    commands = []
    answers = []

    def __init__(self, dev, timeout=0):
        threading.Thread.__init__(self)
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s ' +
            '%(levelname)-8s %(message)s', datefmt='%H:%M:%S.%f')
        self.__serial = serial.Serial(dev, timeout=0)
        self.write_buf += INIT
        self.home()

    def read(self, size=102400):
        self.read_buf += self.__serial.read(size)
        while '\r' in self.read_buf:
            buf_split = self.read_buf.split('\r', 1)
            self.read_buf = buf_split[1]
            #if buf_split[0].startswith('ST '):
            #    self.answers.append(True)
            #    print '%s executed' % self.commands[len(self.answers)-1]
            logging.debug('read: %s' % buf_split[0])

    def position(self):
        return self.__x, self.__y

    def home(self):
        self.write_buf += HOME

        self.__x = 0
        self.__y = 0

    def not_aus(self):
        # do not use write_buf, send directly
        self.__serial.write(NOT_AUS)
        self.__serial.flush()

    def move(self, x, y):
        if 0 <= x + self.__x <= self.MAX_X and 0 <= y + self.__y <= self.MAX_Y:
            self.write_buf += r';*PR%02.2f,%02.2f;;*SH;*OA;*SE;' % (x, y)

            self.__x = self.__x + x
            self.__y = self.__y + y

        else:
            raise AttributeError

    def run(self):
        while True:
            if ';;' not in self.write_buf:
                self.write_buf += ';*SH;;*SH;'

            while ';;' in self.write_buf:
                datagram, self.write_buf = self.write_buf.split(';;', 1)
                self.__serial.write(';%s;' % datagram)
                logging.debug('write: ;%s;' % datagram)
                self.commands.append(datagram)
                self.read()
                self.__serial.flush()

            time.sleep(.1)


if __name__ == '__main__':
    m = Marker('/dev/ttyUSB0')
    points = [
            (100, 100),
            (-50, -50),
            (-50, -50),
            (100, 100),
            (-50, -50),
            (-50, -50)
    ]
    cycle_points = []

    old_x, old_y = 0, 0
    for i in xrange(250):
        angle = i*2*math.pi/50.0
        x = 50 + round(45 * math.cos(angle))
        y = 50 + round(45 * math.sin(angle))
        cycle_points.append((x-old_x, y-old_y))
        print (x-old_x, y-old_y)
        old_x, old_y = x, y

    m.start()
    for coord in cycle_points:
        m.move(coord[0], coord[1])
    m.home()
