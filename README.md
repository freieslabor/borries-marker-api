Borries Marker API
==================

This repository is part of our Borries Marker Toolchain:

* Marker API
* [Marker Web Control](https://github.com/freieslabor/MarkerWebControl)
* [Inkscape Marker Plugin](https://github.com/freieslabor/inkscape_marker_plugin)

# Getting Started

## Debian

    # apt-get install python3.5 python3.5-dev python3-pip python3-setuptools libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk socat

## virtualenv

    $ pip3 install --user --upgrade virtualenv
    $ virtualenv -p python3.5 env
    $ source env/bin/activate # enter the env
    $ pip3 install -r REQUIREMENTS.txt

### Check if virtualenv is active

    $ printenv | grep VIRTUAL_ENV

### Deactivate virtualenv

If you're done leave the virtualenv:

    $ deactivate

Remember: you have to be inside the virtualenv while starting the server.

## Initialize/Update Submodule

MarkerWebControl is part of this repository as a git submodule.

    $ git submodule update --init

## Start Marker Webserver

To start the server execute

    $ ./server.py

The server binds to 127.0.0.1:8080 by default. To change this edit
``HOST``/``PORT`` in ``server.py``. Logs get collected in ``marker.log``.
