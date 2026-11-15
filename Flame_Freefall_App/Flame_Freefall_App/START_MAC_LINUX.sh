#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3.11 -m venv .venv; fi
if [ ! -f .venv/flame-installed-1.0 ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/flame-installed-1.0
fi
exec .venv/bin/python launch.py
