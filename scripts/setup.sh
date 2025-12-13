#!/usr/bin/env bash
#
# Setup script for Annotator XE (macOS/Linux)
# Creates virtual environment and installs dependencies
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

echo "========================================"
echo "  Annotator XE - Setup"
echo "========================================"
echo ""

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

# Check minimum version
MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "Error: Python 3.10 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "Virtual environment created at: $VENV_DIR"
else
    echo ""
    echo "Virtual environment already exists at: $VENV_DIR"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install package
echo ""
echo "Installing Annotator XE..."
cd "$PROJECT_DIR"

if [ "$1" == "--dev" ]; then
    echo "(Development mode with testing tools)"
    pip install -e ".[dev]"
else
    pip install -e .
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run Annotator XE:"
echo "  annotator-xe"
echo "  or: ./scripts/run.sh"
echo ""
