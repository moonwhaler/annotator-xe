#!/usr/bin/env bash
#
# Run script for Annotator XE (macOS/Linux)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Running setup first..."
    "$SCRIPT_DIR/setup.sh"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Run the application
echo "Starting Annotator XE..."
cd "$PROJECT_DIR"

if [ "$1" == "--legacy" ]; then
    python pyQT_YOLO.py
else
    python -m annotator_xe
fi
