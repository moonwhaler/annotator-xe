#!/usr/bin/env bash
#
# Clean script for Annotator XE (macOS/Linux)
# Removes build artifacts and cache files
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "========================================"
echo "  Cleaning Annotator XE"
echo "========================================"

echo ""
echo "Removing build artifacts..."
rm -rf dist/ build/ *.egg-info src/*.egg-info

echo "Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

echo "Removing test artifacts..."
rm -rf .pytest_cache/ htmlcov/ .coverage .mypy_cache/

if [ "$1" == "--all" ]; then
    echo ""
    echo "Removing virtual environment..."
    rm -rf venv/
fi

echo ""
echo "========================================"
echo "  Clean Complete!"
echo "========================================"

if [ "$1" == "--all" ]; then
    echo ""
    echo "Virtual environment removed. Run setup.sh to reinstall."
fi
