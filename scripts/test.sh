#!/usr/bin/env bash
#
# Test script for Annotator XE (macOS/Linux)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Running setup first..."
    "$SCRIPT_DIR/setup.sh" --dev
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Ensure dev dependencies are installed
pip install -e ".[dev]" --quiet

cd "$PROJECT_DIR"

echo "========================================"
echo "  Running Tests"
echo "========================================"
echo ""

if [ "$1" == "--coverage" ]; then
    pytest --cov=annotator_xe --cov-report=html --cov-report=term
    echo ""
    echo "Coverage report generated in htmlcov/"
elif [ "$1" == "--verbose" ]; then
    pytest -v --tb=long
else
    pytest
fi
