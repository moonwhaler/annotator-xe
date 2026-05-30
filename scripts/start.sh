#!/usr/bin/env bash
#
# Start script for Annotator XE (macOS / Linux)
#
# Launches the application from the project's virtual environment.
# Runs setup automatically if the venv does not yet exist.
# Any extra arguments are passed straight through to the app.
#
# Usage:
#   ./scripts/start.sh [app arguments...]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"
VPY="$VENV_DIR/bin/python"

# Bootstrap the environment on first run.
if [ ! -x "$VPY" ]; then
    echo "Virtual environment not found — running setup first..."
    "$SCRIPT_DIR/setup.sh"
fi

if [ ! -x "$VPY" ]; then
    echo "Setup did not produce a usable environment. Aborting." >&2
    exit 1
fi

echo "Starting Annotator XE..."
cd "$PROJECT_DIR"
exec "$VPY" -m annotator_xe "$@"
