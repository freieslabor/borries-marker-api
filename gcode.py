#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import subprocess as sp
import re

from marker import Marker
from test_marker import MarkerEmulator


class GCodeToBorries(object):
    def __init__(self):
        """Prepare PTYs, MarkerEmulator and Marker."""
        self.reset_state()
        # create two connected PTYs
        cmd = ['socat', '-d', '-d', 'pty,raw,echo=0', 'pty,raw,echo=0']
        try:
            self.socat = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
            with self.socat.stdout as stdout:
                marker_pty = stdout.readline().split()[-1]
                if not os.path.exists(marker_pty):
                    raise Exception('PTY creation failed.')

                self.client_pty = stdout.readline().split()[-1]
        except OSError:
            raise Exception('%s is not installed' % cmd[0])

        self.marker_emu = MarkerEmulator(str(marker_pty, encoding='UTF-8'))
        self.marker_emu.start()

        self.marker = Marker(str(self.client_pty, encoding='UTF-8'))
        self.marker.start()
        self.set_state_idle()

        self.variables = {}
        self.calc_groups = re.compile(r'\[(.*)\]')

    def reset_state(self):
        self.state = {
            'axesHomed': [0, 0, 1],
            'status': 'B',
            'position': [0, 0],
            'absolutePositions': True,
            'selectedFile': None,
            'message': ''
        }

    def set_state_idle(self):
        self.state['status'] = 'I'
        self.state['position'] = self.marker.position
        self.state['message'] = self.marker.error_msg
        self.state['axesHomed'] = self.marker.homed_axes

    def substitute_variables_calculate(self, params):
        for i in range(len(params)):
            # replace variables
            for var, value in self.variables.items():
                params[i] = params[i].replace('#{}'.format(var), value)

            # evaluate expressions in brackets
            match = self.calc_groups.search(params[i])
            if match:
                expr = match.groups()[0]
                expr_evaluated = str(eval(expr))
                params[i] = params[i].replace('[{}]'.format(expr),
                                              expr_evaluated)
                logging.info('Evaluated parameter {} to {}'
                             .format(expr, expr_evaluated))

        return params

    def M23(self, *params):
        self.state['selectedFile'] = params[0]

    def M24(self, *params, macro=None):
        """Execute each GCode command in selected file."""
        if macro:
            file = macro
        else:
            file = os.path.join('gcodes', self.state['selectedFile'])
        with open(file) as f:
            for line in f:
                if line.strip() == '':
                    continue

                if line[-1] == '\n':
                    line = line[:-1]

                logging.info('Processing: {}'.format(line))

                try:
                    cmd, *params = line.split()
                except ValueError:
                    cmd = line
                # add leading zero
                if cmd[0] != '#' and len(cmd) == 2:
                    cmd = '{}0{}'.format(cmd[0], cmd[1])
                params = self.substitute_variables_calculate(params)
                try:
                    getattr(self, cmd)(*params)
                except AttributeError:
                    # variable parsing
                    if cmd[0] == '#':
                        var = cmd[1:]
                        # remove empty elements from params
                        params = [param for param in params if param]
                        self.variables[var] = params[1]
                        comment = ' '.join(params[2:])
                        logging.info('Parsed variable #{} with value "{}" {}'
                                     .format(var, params[1], comment))
                    else:
                        logging.error('GCode {} is not implemented'.format(cmd))

    def M32(self, *params):
        self.M23(*params)
        self.M24()

    def M98(self, *params):
        """Execute GCodes in macro file."""
        # ignore P and leading slash
        macro_file = params[0][2:]
        self.M24(macro=macro_file)

    def M112(self, *params):
        self.state['status'] = 'D'
        self.marker.emergency_off('webinterface')
        self.state['status'] = 'S'

    def M999(self, *params):
        self.state['status'] = 'R'
        logging.info('Restarting marker')
        while not self.marker.emergency_off_done:
            pass
        self.marker = Marker(str(self.client_pty, encoding='UTF-8'))
        self.reset_state()
        self.marker.start()
        self.set_state_idle()
        logging.info('Restart done')

    def G00(self, *params):
        """Rapid linear move"""
        self.G01(*params)

    def G01(self, *params):
        """Linear move"""
        x = y = 0
        for param in params:
            # ignore E and F parameters
            if param[0] == 'X':
                x = float(param[1:])
            elif param[0] == 'Y':
                y = float(param[1:])

        # FIXME: do the actual marking
        if self.state['absolutePositions']:
            self.marker.move_abs(x, y)
        else:
            self.marker.move_rel(x, y)

    def G02(self, *params):
        """Clockwise arc move"""
        x = y = i = j = 0
        for param in params:
            # ignore E and F parameters
            if param[0] == 'X':
                x = float(param[1:])
            elif param[0] == 'Y':
                y = float(param[1:])
            elif param[0] == 'I':
                i = float(param[1:])
            elif param[0] == 'J':
                j = float(param[1:])

        # FIXME: calculate intermediate points on circle defined by current
        # position, final position (X,Y) and circle center (as offset)

    def G03(self, *params):
        """Counter-clockwise arc move"""

        # FIXME: do something similar as G2, but counter-clockwise

    def G20(self, *params):
        # FIXME: use unit
        self.state['unit'] = 'inch'

    def G21(self, *params):
        # FIXME: use unit
        self.state['unit'] = 'mm'

    def G28(self, *params):
        if len(params) > 0:
            if params[0] == 'X':
                logging.info('Homing X axis')
                # FIXME: is there a home_x() ?
                self.marker.home()
            elif params[0] == 'Y':
                logging.info('Homing Y axis')
                # FIXME: is there a home_y() ?
                self.marker.home()
        else:
            logging.info('Homing X and Y axes')
            self.marker.home()

    def G90(self, *params):
        logging.info('Switch to absolute positioning')
        self.state['absolutePositions'] = True

    def G91(self, *params):
        logging.info('Switch to relative positioning')
        self.state['absolutePositions'] = False
