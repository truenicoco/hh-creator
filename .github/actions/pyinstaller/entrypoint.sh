#!/bin/bash

# This is mostly ~stolen~ taken from https://github.com/JackMcKew/pyinstaller-action-windows/

# Fail on errors.
set -e

# Make sure .bashrc is sourced
. /root/.bashrc

WORKDIR=$1
SPEC_FILE=${2:-*.spec}
REQ_FILE=$3

python -m pip install --upgrade pip wheel setuptools

cd $WORKDIR

if [ -f $REQ_FILE ]; then
    pip install -r $REQ_FILE
    # pyinstaller does not want to build if pathlib is installed
    pip uninstall pathlib -y || true
fi

pyinstaller --clean -y --dist ./dist/windows --workpath /tmp $SPEC_FILE
chown -R --reference=. ./dist/windows
