#!/usr/bin/env python3.5
# -*- coding: utf-8 -*-

import re
import unittest
from marker import Marker
import time
import os
from datetime import datetime
import signal
import subprocess as sp
import serial
import threading
import random
try:
    import Image
except ImportError:
    from PIL import Image


# send commands
HEARTBEAT_OUT = 'RSIX800O00'
ACK = 'ST 00 XX 00 60 00 00 00 00 00 00 00 00 00'

# receive commands
INIT = r'\*SQ;;\*SQ;;\*SQ;\*CB;\*INITstn;\*INITzn;\*DB;\*CPa;\*SE;' \
        r'\*CPz;\*CPd;\*CPa;\*SE;\*INITp301;\*OI;;\*CPa;\*RTEOF;\*SE;' \
        r'\*INITwn;\*INITgn;\*INITppn,pj;\*INITzpj;\*INITzn;\*INITd16,0,5,' \
        r'500,20000;\*INITdx15,0,30;\*WD10;\*WU10;\*SE;\*INITs100.00,100.00;' \
        r'\*INITo-100,-100;;\*INITno0,0;\*INITrd\+,\+;\*INITrr\+,\+;' \
        r'\*INITrs\+,\+;LO1;\*LBn;\*INITesn,n;\*INITze-,-;\*VM6500,6500;' \
        r'\*VN\d+,\d+;\*VS400,400;\*SE;\*VB\d+;\*VH600,600;\*VP600,600;' \
        r'\*VC600,600;\*SE;;\*AC90000,90000;\*LBd0.00;\*LBm1.4,1.16;;' \
        r'\*INITn1;;\*INITxqrap;;\*INITxp5;\*INITzs0;;\*INITaen,asn,adj;' \
        r'\*MO18E1,9600;\*CPa;\*SE;;\*INITbeL,0,beL,1,beL,2,beH,3,beL,4,beH,' \
        r'5,beH,6,beL,7,beL,8,beL,9,beL,10,beL,11,beL,12,beL,13,beL,14,beL,' \
        r'15,beL,16,beL,17,beL,18,beL,19,beL,20,beL,21,beL,22,beL,23,beL,24;' \
        r'\*INITbaD,22,baD,21,baD,20,baD,19,baD,18,baD,17,baD,16,baD,15,baD,' \
        r'14,baD,13,baD,12,baD,11,baD,10,baD,9,baD,8,baD,7,baD,6,baD,5,baD,' \
        r'4,baD,3,baD,2,baD,1,ba0,0;\*SE;;;;\*VP1200,1200;;\*CPa;\*RTEOF;' \
        r'\*SE;CS6;\*INITbe0,5;;\*CPa;\*RTEOF;\*SE;;\*XRH;;\*EB;\*SE;;' \
        r'\*SH;;\*SH;;\*SH;;\*SH;;PU;;\*INITrr\+,\+;'
HOME = r';\*INITrd\+,\+;\*RX;\*RY;\*RTHOME;\*SH;;\*SE;;\*OA;;\*SH;;\*SE;'
MOVE = r';\*PR\d+\.\d\d,\d+\.\d\d;;\*SH;\*OA;\*SE;'
EMERGENCY_OFF = r';;\*HE;;;'
NEEDLE = r'SP1;;PD;\*WT250;PU;\*SE;'
HEARTBEAT_IN = r';\*SH;'


class MarkerEmulator(threading.Thread):
    """Emulates a Borries marker machine."""
    read_buf = ''
    initialized = False
    daemon = True
    running = True

    def __init__(self, dev):
        """Initializes emulator."""
        threading.Thread.__init__(self)
        self.serial = serial.Serial(dev, timeout=0)

    def answer(self):
        """Answer commands."""
        if re.search(INIT, self.read_buf):
            self.__command_seen(INIT)
            self.initialized = True
            self.write(ACK, 24)

        if self.initialized:
            if re.search(HOME, self.read_buf):
                self.__command_seen(HOME)
                self.write(ACK, 4)

            if re.search(MOVE, self.read_buf):
                self.__command_seen(MOVE)
                self.write(ACK, 2)

            if re.search(NEEDLE, self.read_buf):
                self.__command_seen(NEEDLE)
                self.write(ACK, 2)

            if re.search(EMERGENCY_OFF, self.read_buf):
                self.__command_seen(EMERGENCY_OFF)
                self.initialized = False

            if re.search(HEARTBEAT_IN, self.read_buf):
                self.write(HEARTBEAT_OUT)

    def read(self, size=128):
        """Reads given amount of bytes in buffer."""
        self.read_buf += str(self.serial.read(size), encoding='UTF-8')

    def write(self, cmd, count=1):
        """Writes given command count times to serial device."""
        for i in range(count):
            self.serial.write(('%s\r' % cmd).encode())

    def __command_seen(self, cmd):
        """Remove command from read buffer."""
        self.read_buf = re.sub(cmd, '', self.read_buf, count=1)

    def run(self):
        while self.running:
            self.read()
            self.answer()
            time.sleep(.1)


class MarkerTest(object):
    """Implements methods necessary for unit tests."""
    def __init__(self, *args, **kwargs):
        """Initializes test with or without initial preview check."""
        if 'initial_check' in kwargs:
            self.initial_check = kwargs['initial_check']
            del kwargs['initial_check']
        else:
            self.initial_check = False

        super(MarkerTest, self).__init__(*args, **kwargs)

    def setUp(self):
        """Prepare PTYs, MarkerEmulator and Marker."""
        # create two connected PTYs
        cmd = ['socat', '-d', '-d', 'pty,raw,echo=0', 'pty,raw,echo=0']
        try:
            self.socat = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
            with self.socat.stdout as stdout:
                marker_pty = stdout.readline().split()[-1]
                if not os.path.exists(marker_pty):
                    raise Exception('PTY creation failed.')

                client_pty = stdout.readline().split()[-1]
        except OSError:
            raise Exception('%s is not installed' % cmd[0])

        self.marker_emu = MarkerEmulator(str(marker_pty, encoding='UTF-8'))
        self.marker_emu.start()

        self.marker_client = Marker(str(client_pty, encoding='UTF-8'),
                                    initial_check=self.initial_check)
        self.marker_client.start()

        # wait for marker being ready only when checks are turned off
        if not self.initial_check:
            while not self.marker_client.count['ST'].ready:
                time.sleep(.1)

    def tearDown(self):
        """Clean up and shut down."""
        self.marker_client.running = False
        del self.marker_client
        self.marker_emu.running = False
        del self.marker_emu
        os.kill(self.socat.pid, signal.SIGINT)

    def check_commands_executed(self):
        """Checks if all commands that got sent were executed."""
        self.assertEqual(self.marker_client.count['ST'].done,
                         self.marker_client.count['ST'].tbd)

    def move(self, move_method, *args, **kwargs):
        """Move test wrapper."""
        done_before = self.marker_client.count['ST'].done
        move_method(*args, **kwargs)
        time.sleep(1)
        # independent movement check
        self.assertEqual(self.marker_client.count['ST'].done, done_before + 1)

    def random_x_position(self, min=0.01, max=None):
        """Returns a random, but valid x position."""
        if max is None:
            max = self.marker_client.MAX_X
        return random.randint(min*100, max*100) / 100.0

    def random_y_position(self, min=0.01, max=None):
        """Returns a random, but valid y position."""
        if max is None:
            max = self.marker_client.MAX_Y
        return random.randint(min*100, max*100) / 100.0


class MarkerBasicTest(MarkerTest, unittest.TestCase):
    """Performs basic marker tests."""
    def test_absolute_move(self):
        """Tests absolute movements."""
        new_pos = (self.random_x_position(), self.random_y_position())
        self.move(self.marker_client.move_abs, new_pos[0], new_pos[1])
        x, y = self.marker_client.position()
        # check if marker reached correct position
        self.assertEqual(x, new_pos[0])
        self.assertEqual(y, new_pos[1])

    def test_relative_move(self):
        """Tests relative movements."""
        x_old, y_old = self.marker_client.position()
        rel_x = self.marker_client.MAX_X - x_old
        rel_y = self.marker_client.MAX_Y - y_old
        steps = (self.random_x_position(-x_old, rel_x),
                 self.random_x_position(-y_old, rel_y))
        self.move(self.marker_client.move_rel, steps[0], steps[1])
        x, y = self.marker_client.position()
        # check if marker reached correct position
        self.assertEqual(x_old + steps[0], x)
        self.assertEqual(y_old + steps[1], y)

    def test_needle_down(self):
        """Tests needle down functionality."""
        done_before = self.marker_client.count['ST'].done
        self.marker_client.needle_down()
        time.sleep(1)
        self.check_commands_executed()
        self.assertEqual(self.marker_client.count['ST'].done, done_before + 1)

    def test_home(self):
        """Tests movement to home position."""
        self.marker_client.home()
        x, y = self.marker_client.position()
        time.sleep(1)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)
        self.check_commands_executed()

    def test_max_limit(self):
        """Tests marker limit."""
        with self.assertRaises(Exception):
            self.marker_client.move_abs(1000, 1000)
            time.sleep(1)

    def test_emergency_exit(self):
        """Tests emergency exit function."""
        self.marker_client.move_abs(100, 100)
        with self.assertRaises(Exception):
            time.sleep(1)
            self.marker_client.emergency_off()


class MarkerImageTest(MarkerTest, unittest.TestCase):
    """Performs image tests."""
    def __init__(self, *args, **kwargs):
        """Initializes marker test with initial preview check."""
        super(MarkerImageTest, self).__init__(*args, initial_check=True,
                                              **kwargs)

    def test_image(self):
        """Tests image marking."""
        self.marker_client.mark_picture('Logo_quadratisch.png', (0, 0, 30, 30),
                                        granularity=5)

        preview_file = 'preview_unittest.png'
        self.marker_client.check(preview_file=preview_file,
                                 dont_ask=True)

        mod_timestamp = os.path.getmtime(preview_file)
        mod_datetime = datetime.fromtimestamp(mod_timestamp)

        # basic file checks:
        # check that the file has just been written
        self.assertGreater(datetime.now(), mod_datetime)

        # check that the file is not empty
        with open(preview_file, 'rb') as img_file:
            with Image.open(img_file) as img:
                extrema_diff = [col[0] != col[1] for col in img.getextrema()]
                self.assertTrue(any(extrema_diff))


if __name__ == '__main__':
    unittest.main()
