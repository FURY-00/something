#!/usr/bin/env bash
# Jarvis installer for macOS and Linux. Run from the project folder:
#   bash scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  echo "==> System packages (microphone, keyboard control, fallback voice)"
  if command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-dev python3-tk libportaudio2 portaudio19-dev \
      espeak-ng xclip scrot
  elif command -v dnf >/dev/null; then
    sudo dnf install -y python3-devel python3-tkinter portaudio portaudio-devel espeak-ng xclip scrot
  elif command -v pacman >/dev/null; then
    sudo pacman -S --needed python tk portaudio espeak-ng xclip scrot
  else
    echo "Please install: PortAudio, Tk for Python, espeak-ng, xclip, scrot"
  fi
fi

PY="${PYTHON:-python3}"
"$PY" -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or newer is required'"

echo "==> Creating virtual environment (.venv)"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps openwakeword

echo "==> Checking Ollama (runs the AI model locally)"
if ! command -v ollama >/dev/null; then
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null; then
      brew install ollama
    else
      echo "Install Ollama from https://ollama.com/download and run this script again."
      exit 1
    fi
  else
    curl -fsSL https://ollama.com/install.sh | sh
  fi
fi
if ! curl -s http://localhost:11434/api/tags >/dev/null; then
  echo "Starting the Ollama server..."
  (ollama serve >/dev/null 2>&1 &)
  sleep 5
fi

echo "==> Downloading models (one time, several GB)"
.venv/bin/python -m jarvis --setup && {
  echo
  echo "Done! Start Jarvis with:  ./start_jarvis.sh"
  [ "$OS" = "Darwin" ] && echo "macOS: allow Terminal under System Settings > Privacy & Security > Microphone and Accessibility."
  true
}
