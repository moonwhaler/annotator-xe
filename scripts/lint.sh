#!/usr/bin/env bash
#
# Lint script for Annotator XE (macOS/Linux)
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
echo "  Code Quality Checks"
echo "========================================"

if [ "$1" == "--fix" ]; then
    echo ""
    echo "Running Ruff (with auto-fix)..."
    ruff check src/annotator_xe --fix || true

    echo ""
    echo "Running Black (formatting)..."
    black src/annotator_xe
else
    echo ""
    echo "Running Ruff..."
    ruff check src/annotator_xe || true

    echo ""
    echo "Running Black (check only)..."
    black --check src/annotator_xe || true
fi

echo ""
echo "Running MyPy..."
mypy src/annotator_xe || true

echo ""
echo "========================================"
echo "  Done!"
echo "========================================"
