# Getting Started

## Debian

    # apt-get install python3.5 python3.5-dev python3-pip python3-setuptools libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk socat

## virtualenv

    $ pip3 install --user --upgrade virtualenv
    $ virtualenv -p python3.5 env
    $ source env/bin/activate
    $ pip3 install -r REQUIREMENTS.txt

### Check if virtualenv is active

    $ printenv | grep VIRTUAL_ENV

### Deactivate virtualenv

    $ deactivate
