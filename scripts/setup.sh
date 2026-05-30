#!/usr/bin/env bash
#
# Setup script for Annotator XE (macOS / Linux)
#
# Creates an isolated Python virtual environment and installs the project.
#
# Usage:
#   ./scripts/setup.sh [options]
#
# Options:
#   --dev         Also install development tools (pytest, ruff, black, mypy, ...)
#   --yolo        Also install auto-detection deps (torch, ultralytics) [heavy ~2GB+]
#   --gpu         Also install GPU/OpenGL rendering deps (PyOpenGL)
#   --all         Install everything (equivalent to --dev --yolo --gpu)
#   --recreate    Delete and rebuild the virtual environment from scratch
#   --python PATH Use a specific Python interpreter
#   --no-color    Disable colored output
#   -h, --help    Show this help and exit
#

set -euo pipefail

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------
WANT_DEV=0
WANT_YOLO=0
WANT_GPU=0
RECREATE=0
PYTHON_OVERRIDE=""
USE_COLOR=1

print_help() {
    # Print the leading comment block (skipping the shebang), stripping '# '.
    awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "${BASH_SOURCE[0]}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dev)       WANT_DEV=1 ;;
        --yolo)      WANT_YOLO=1 ;;
        --gpu)       WANT_GPU=1 ;;
        --all)       WANT_DEV=1; WANT_YOLO=1; WANT_GPU=1 ;;
        --recreate)  RECREATE=1 ;;
        --python)    shift; PYTHON_OVERRIDE="${1:-}" ;;
        --no-color)  USE_COLOR=0 ;;
        -h|--help)   print_help; exit 0 ;;
        *) echo "Unknown option: $1 (use --help)"; exit 2 ;;
    esac
    shift
done

# --------------------------------------------------------------------------
# Colors
# --------------------------------------------------------------------------
if [ "$USE_COLOR" -eq 1 ] && [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
    C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi

info()  { echo "${C_BLUE}==>${C_RESET} $*"; }
ok()    { echo "${C_GREEN}✓${C_RESET} $*"; }
warn()  { echo "${C_YELLOW}!${C_RESET} $*" >&2; }
err()   { echo "${C_RED}✗ $*${C_RESET}" >&2; }
header(){ echo; echo "${C_BOLD}========================================${C_RESET}"; echo "${C_BOLD}  $*${C_RESET}"; echo "${C_BOLD}========================================${C_RESET}"; echo; }

# Error trap so failures are obvious instead of a bare non-zero exit.
trap 'err "Setup failed at line $LINENO. See output above."' ERR

# --------------------------------------------------------------------------
# Platform
# --------------------------------------------------------------------------
OS="$(uname -s)"
case "$OS" in
    Darwin) PLATFORM="macOS" ;;
    Linux)  PLATFORM="Linux" ;;
    *)      PLATFORM="$OS" ;;
esac

header "Annotator XE - Setup ($PLATFORM)"

# --------------------------------------------------------------------------
# Locate a suitable Python (>= 3.10)
# --------------------------------------------------------------------------
MIN_MAJOR=3
MIN_MINOR=10

version_ok() {
    # $1 = python command; returns 0 if >= MIN_MAJOR.MIN_MINOR
    "$1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= ($MIN_MAJOR, $MIN_MINOR) else 1)" 2>/dev/null
}

PYTHON_CMD=""
if [ -n "$PYTHON_OVERRIDE" ]; then
    if command -v "$PYTHON_OVERRIDE" >/dev/null 2>&1 && version_ok "$PYTHON_OVERRIDE"; then
        PYTHON_CMD="$PYTHON_OVERRIDE"
    else
        err "Provided interpreter '$PYTHON_OVERRIDE' missing or older than $MIN_MAJOR.$MIN_MINOR."
        exit 1
    fi
else
    # Prefer newest known-good interpreter.
    for cand in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && version_ok "$cand"; then
            PYTHON_CMD="$cand"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    err "No Python >= $MIN_MAJOR.$MIN_MINOR found."
    if [ "$PLATFORM" = "macOS" ]; then
        warn "Install with: brew install python@3.12   (or from python.org)"
    else
        warn "Install with your package manager, e.g.:"
        warn "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip"
        warn "  Fedora:        sudo dnf install python3 python3-pip"
        warn "  Arch:          sudo pacman -S python python-pip"
    fi
    exit 1
fi

PYVER="$("$PYTHON_CMD" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
ok "Using Python $PYVER ($PYTHON_CMD)"

# Ensure the venv module is present (Debian ships it separately).
if ! "$PYTHON_CMD" -c "import venv" >/dev/null 2>&1; then
    err "The 'venv' module is not available for $PYTHON_CMD."
    warn "Debian/Ubuntu: sudo apt install python3-venv"
    exit 1
fi

# --------------------------------------------------------------------------
# Virtual environment
# --------------------------------------------------------------------------
if [ "$RECREATE" -eq 1 ] && [ -d "$VENV_DIR" ]; then
    info "Removing existing virtual environment (--recreate)..."
    rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment at $VENV_DIR ..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Virtual environment created."
else
    ok "Reusing existing virtual environment at $VENV_DIR"
fi

# Use the venv's interpreter directly (no need to 'activate' in a script).
VPY="$VENV_DIR/bin/python"
if [ ! -x "$VPY" ]; then
    err "venv interpreter not found at $VPY. Try: ./scripts/setup.sh --recreate"
    exit 1
fi

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------
info "Upgrading pip / setuptools / wheel ..."
"$VPY" -m pip install --upgrade pip setuptools wheel >/dev/null

# Build the editable-install spec with the requested extras.
EXTRAS=""
add_extra() { if [ -z "$EXTRAS" ]; then EXTRAS="$1"; else EXTRAS="$EXTRAS,$1"; fi; }
[ "$WANT_DEV" -eq 1 ]  && add_extra "dev"
[ "$WANT_YOLO" -eq 1 ] && add_extra "yolo"

SPEC="."
[ -n "$EXTRAS" ] && SPEC=".[$EXTRAS]"

info "Installing Annotator XE (editable) -> $SPEC"
[ -n "$EXTRAS" ] && info "  extras: $EXTRAS"
( cd "$PROJECT_DIR" && "$VPY" -m pip install -e "$SPEC" )

if [ "$WANT_GPU" -eq 1 ]; then
    info "Installing GPU/OpenGL rendering deps (PyOpenGL) ..."
    "$VPY" -m pip install "PyOpenGL>=3.1.6"
fi

# --------------------------------------------------------------------------
# Sanity check: can PyQt6 actually load? (catches missing Qt system libs)
# --------------------------------------------------------------------------
info "Verifying PyQt6 import ..."
if "$VPY" -c "import PyQt6.QtWidgets" >/dev/null 2>&1; then
    ok "PyQt6 imports cleanly."
else
    warn "PyQt6 installed but failed to import — likely missing system libraries."
    if [ "$PLATFORM" = "Linux" ]; then
        warn "On Debian/Ubuntu try:"
        warn "  sudo apt install libgl1 libegl1 libxkbcommon0 libxcb-cursor0 \\"
        warn "       libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libdbus-1-3"
        warn "Fedora: sudo dnf install mesa-libGL libxkbcommon xcb-util-cursor dbus-libs"
    fi
    warn "The app may still fail to launch until these are installed."
fi

# --------------------------------------------------------------------------
# Done
# --------------------------------------------------------------------------
header "Setup Complete!"
echo "Start the app:"
echo "  ${C_BOLD}./scripts/start.sh${C_RESET}"
echo
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  annotator-xe"
echo
[ "$WANT_YOLO" -eq 0 ] && echo "Auto-detection (YOLO) not installed. Add it later: ./scripts/setup.sh --yolo"
[ "$WANT_GPU" -eq 0 ]  && echo "GPU/OpenGL rendering not installed. Add it later:  ./scripts/setup.sh --gpu"
echo
