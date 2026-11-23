#!/usr/bin/env bash
# Builds "dist/QR Studio.app" and a .dmg installer. Run on a Mac.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-build.txt
.venv/bin/python packaging/build.py
