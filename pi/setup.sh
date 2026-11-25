#!/usr/bin/env bash
# Prepare the Raspberry Pi for the BIS translator. Safe to run more than once.
#
# From the PC:
#   ssh -t bisbridge "git clone https://github.com/ramsestein/gwi_ma.git ~/gwi_ma 2>/dev/null; bash ~/gwi_ma/pi/setup.sh"
set -euo pipefail

REPO_URL="https://github.com/ramsestein/gwi_ma.git"
REPO_DIR="$HOME/gwi_ma"

echo "== System packages"
sudo apt-get update -q
sudo apt-get install -y -q git python3-venv

echo "== Serial port access (group dialout)"
if id -nG "$USER" | grep -qw dialout; then
    echo "$USER is already in dialout"
else
    sudo usermod -aG dialout "$USER"
    echo "Added $USER to dialout: takes effect on the next SSH login"
fi

echo "== Repository"
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$REPO_DIR"
fi

echo "== Python environment (pyserial only)"
if [ ! -x "$REPO_DIR/venv/bin/python" ]; then
    python3 -m venv "$REPO_DIR/venv"
fi
"$REPO_DIR/venv/bin/pip" install -q --upgrade pyserial
mkdir -p "$REPO_DIR/dumps"

echo "== Check"
cd "$REPO_DIR"
venv/bin/python -c "import serial; print('pyserial', serial.VERSION)"
venv/bin/python -m src.utils.serial_ports || true
echo "Done. Tools run from $REPO_DIR with: venv/bin/python -m src.<layer>.<tool>"
