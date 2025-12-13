#!/usr/bin/env bash
#
# Build script for Annotator XE (macOS/Linux)
# Creates distributable package
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

cd "$PROJECT_DIR"

echo "========================================"
echo "  Building Annotator XE"
echo "========================================"

# Install build tools
echo ""
echo "Installing build tools..."
pip install --upgrade build twine

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info src/*.egg-info

# Build package
echo ""
echo "Building package..."
python -m build

echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo "Distribution files created in dist/"
ls -la dist/
echo ""
echo "To install locally:"
echo "  pip install dist/annotator_xe-*.whl"
echo ""
echo "To upload to PyPI (requires credentials):"
echo "  twine upload dist/*"
echo ""
