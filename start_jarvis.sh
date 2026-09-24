#!/usr/bin/env bash
# Start Jarvis. Add --text to type instead of talking.
cd "$(dirname "$0")"
exec .venv/bin/python -m jarvis "$@"
