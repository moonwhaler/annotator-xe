#!/usr/bin/env bash
#
# Run script for Annotator XE (macOS / Linux)
# Kept as a backwards-compatible alias for start.sh.
#
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/start.sh" "$@"
