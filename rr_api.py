#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from aiohttp.web import Response
import json
import os


class RRApi(object):
    ALLOWED_DIRECTORIES = ['gcodes', 'sys', 'macros']
    async def rr_connect(self, request):
        # FIXME: implement auth
        response = {
            'err': 0,
            'sessionTimeout': 500,
            'boardType': 'Borries Marker'
        }
        return Response(text=json.dumps(response),
                        content_type='application/json')

    async def rr_disconnect(self, request):
        return Response(status=200)

    async def rr_status(self, request):
        # FIXME: remove static values
        response = {
          'status': 'I',
          'coords': {
            'axesHomed': [0, 0, 1],
            'extr': [0.0, 0.0, 0.0],
            'xyz': [0.0, 0.0, 0.0],
          },
          'output': {
            # 'message': '...',
          },
          'params': {
            'atxPower': 1,
            'fanPercent': 0,
            'speedFactor': 1.0,
            'extrFactors': []
          },
          'seq': 0,
          'sensors': {
            'probeValue': 0,
            'fanRPM': 0,
          },
          'temps': {
            'heads': {
              'current': [],
              'active': [],
              'standby': [],
              'state': [],
            }
          },
          'time': 0,
          'name': 'Borries Marker 320-DP',
          'currentLayer': 0,
          'currentLayerTime': 0.0,
          'extrRaw': [],
          'fractionPrinted': 0.0,
          'firstLayerDuration': 0.0,
          'firstLayerHeight': 0.0,
          'printDuration': 0.0,
          'warmUpDuration': 0.0,
          'timesLeft': {
            'file': 0.0,
            'filament': 0.0,
            'layer': 0.0,
          }
        }
        return Response(text=json.dumps(response),
                        content_type='application/json')

    def get_path(self, request, get_param):
        if get_param in request.GET:
            # make sure the directory is allowed
            path_components = request.GET[get_param].split(os.sep)
            if path_components[1] in self.ALLOWED_DIRECTORIES:
                current_abs_path = os.path.abspath(os.path.dirname(__file__))
                # ignore first character of parameter, because path is not
                # really absolute
                result = os.path.join(current_abs_path,
                                      request.GET[get_param][1:])
                return result
            else:
                raise NotADirectoryError
        else:
            # FIXME: default to file being printed
            return os.path.join(os.path.dirname(__file__), '/gcodes/foo.gcode')

    async def rr_filelist(self, request):
        file_path = self.get_path(request, 'dir')
        relative_path = file_path.replace(os.path.dirname(__file__), '')

        response = {
            'dir': relative_path,
            'files': []
        }

        for entry in os.scandir(file_path):
            info = {
                'name': entry.name,
                'size': entry.stat().st_size,
                'type': 'd' if entry.is_dir() else 'f'
            }
            response['files'].append(info)

        return Response(text=json.dumps(response),
                        content_type='application/json')

    async def rr_fileinfo(self, request):
        # file_path = self.get_path(request, 'name')
        # relative_path = file_path.replace(os.path.dirname(__file__))

        # FIXME: retrieve values from file_path
        response = {
            'err': 0,
            'height': 0,
            'layerHeight': 0,
            'filament': 0,
            'generatedBy': 'slic3r or sth'
        }

        return Response(text=json.dumps(response),
                        content_type='application/json')

    async def rr_download(self, request):
        file_path = self.get_path(request, 'name')
        with open(file_path, 'rb') as file:
            return Response(body=file.read())

    async def rr_delete(self, request):
        try:
            file_path = self.get_path(request, 'name')
            if os.path.isfile(file_path):
                os.remove(file_path)
                result = {'err': 0}
            elif os.path.isdir(file_path):
                # remove only empty directories
                if len(os.listdir(file_path)) == 0:
                    os.rmdir(file_path)
                    result = {'err': 0}
                else:
                    result = {'err': 1}
                    logging.info('Directory {} is not empty; Will not delete'
                                 .format(file_path))
            else:
                # neither file nor directory
                result = {'err': 1}
        except Exception as e:
            result = {'err': 1}
            logging.info('Could not delete {}: {}'.format(file_path, e))

        return Response(text=json.dumps(result),
                        content_type='application/json')

    async def rr_mkdir(self, request):
        try:
            file_path = self.get_path(request, 'dir')
            os.mkdir(file_path)
            result = {'err': 0}
        except:
            result = {'err': 1}

        return Response(text=json.dumps(result),
                        content_type='application/json')

    async def rr_upload(self, request):
        file_path = self.get_path(request, 'name')
        reader = await request.multipart()
        data = await reader.next()

        try:
            size = 0
            with open(file_path, 'wb') as f:
                while True:
                    chunk = await data.read_chunk()  # 8192 bytes by default.
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)

            result = {'err': 0 if size > 0 else 1}
        except Exception as e:
            logging.info('File upload failed: {}'.format(e))
            result = {'err': 1}

        return Response(text=json.dumps(result),
                        content_type='application/json')

    async def rr_reply(self, request):
        # FIXME: what should this do?
        return Response(text='', content_type='application/json')

    async def rr_gcode(self, request):
        # FIXME: handle gcode
        logging.info('Got gcode: {}'.format(request.GET['gcode']))

        return Response(text=json.dumps({}),
                        content_type='application/json')
