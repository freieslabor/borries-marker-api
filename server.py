#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
from aiohttp.web import Application, Response
import os

from rr_api import RRApi

HOST = '127.0.0.1'
PORT = 8080

WEBCTRL_CORE = os.path.join(os.path.dirname(__file__), 'MarkerWebControl/core')
STATIC_JS = os.path.join(WEBCTRL_CORE, 'js/')
STATIC_CSS = os.path.join(WEBCTRL_CORE, 'css/')
STATIC_FONTS = os.path.join(WEBCTRL_CORE, 'fonts/')

async def index(request):
    path = os.path.join(WEBCTRL_CORE, 'reprap.htm')
    return Response(body=open(path, 'rb').read(), content_type='text/html')

async def index404(request):
    path = os.path.join(WEBCTRL_CORE, 'html404.htm')
    return Response(body=open(path, 'rb').read(), content_type='text/html')

async def language_xml(request):
    path = os.path.join(WEBCTRL_CORE, 'language.xml')
    return Response(body=open(path, 'rb').read(), content_type='text/html')


def run():
    logging.basicConfig(level=logging.INFO, filename='marker.log')
    logging.info('Preparing server')

    loop = asyncio.get_event_loop()
    app = Application(loop=loop)

    # add static urls
    app.router.add_static('/js', STATIC_JS)
    app.router.add_static('/css', STATIC_CSS)
    app.router.add_static('/fonts', STATIC_FONTS)

    app.router.add_route('*', '/', index)
    app.router.add_route('*', '/index404.htm', index404)
    app.router.add_route('*', '/language.xml', language_xml)

    # add API urls
    api = RRApi()
    app.router.add_route('*', '/rr_connect', api.rr_connect)
    app.router.add_route('*', '/rr_disconnect', api.rr_disconnect)

    app.router.add_route('*', '/rr_status', api.rr_status)
    app.router.add_route('*', '/rr_config', api.rr_config)

    app.router.add_route('*', '/rr_filelist', api.rr_filelist)
    app.router.add_route('*', '/rr_fileinfo', api.rr_fileinfo)
    app.router.add_route('*', '/rr_delete', api.rr_delete)
    app.router.add_route('*', '/rr_mkdir', api.rr_mkdir)
    app.router.add_route('*', '/rr_move', api.rr_move)
    app.router.add_route('*', '/rr_download', api.rr_download)
    app.router.add_route('POST', '/rr_upload', api.rr_upload)

    app.router.add_route('*', '/rr_reply', api.rr_reply)

    app.router.add_route('*', '/rr_gcode', api.rr_gcode)

    handler = app.make_handler(logger=logging, access_log=logging)

    server = loop.run_until_complete(
        loop.create_server(handler, HOST, PORT)
    )

    # add tasks
    tasks = [
    ]

    # serve
    try:
        logging.info('Starting server on {}:{}'.format(HOST, PORT))
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info('\rStopping server')

    finally:
        loop.run_until_complete(handler.finish_connections(1.0))
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.run_until_complete(app.finish())

        for task in tasks:
            task.cancel()

        loop.run_until_complete(asyncio.wait(tasks))

    loop.close()

if __name__ == '__main__':
    run()
