#!/bin/bash
# Setup script for the Claude Code cloud environment used by the iteration routine.
# Paste into the environment's "Setup script" field. Installs what `make test` needs (the APK is built by CI).
set -e
pip install --quiet playwright==1.56.0
python -m playwright install --with-deps chromium
