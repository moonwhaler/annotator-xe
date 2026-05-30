# Annotator XE Scripts

Cross-platform scripts for building, running, and developing Annotator XE.

## Available Scripts

| Script | Purpose |
|--------|---------|
| `setup` | Create virtual environment and install dependencies |
| `start` | Launch the app (auto-runs setup on first use) |
| `run` | Alias of `start` (legacy name) |
| `test` | Run the test suite |
| `lint` | Run code quality checks (ruff, black, mypy) |
| `build` | Create distributable packages |
| `clean` | Remove build artifacts and caches |

Each script comes in three flavors:

- `*.sh` — macOS / Linux (bash)
- `*.bat` — Windows cmd.exe
- `*.ps1` — Windows PowerShell (recommended on Windows)

### Feature extras

The app runs on three core packages (PyQt6, PyYAML, Pillow). Heavier, optional
capabilities are installed on demand via flags so you don't pull ~2GB of Torch
unless you need it:

| Flag | Installs | Enables |
|------|----------|---------|
| `--dev`  / `-Dev`  | pytest, ruff, black, mypy, ... | running tests & linters |
| `--yolo` / `-Yolo` | torch, ultralytics | YOLO auto-detection |
| `--gpu`  / `-Gpu`  | PyOpenGL | OpenGL/GPU-accelerated rendering |
| `--all`  / `-All`  | all of the above | everything |

Extras are additive — re-run setup later with another flag to add them.

## Usage

### macOS / Linux

```bash
# First time setup (core only)
./scripts/setup.sh

# Setup with extras
./scripts/setup.sh --dev          # dev tools
./scripts/setup.sh --yolo         # auto-detection (torch/ultralytics)
./scripts/setup.sh --gpu          # OpenGL rendering
./scripts/setup.sh --all          # everything
./scripts/setup.sh --recreate     # rebuild venv from scratch
./scripts/setup.sh --python /usr/bin/python3.12

# Start the application (runs setup automatically if needed)
./scripts/start.sh

# Run tests
./scripts/test.sh
./scripts/test.sh --coverage
./scripts/test.sh --verbose

# Code quality
./scripts/lint.sh
./scripts/lint.sh --fix

# Build package
./scripts/build.sh

# Clean up
./scripts/clean.sh
./scripts/clean.sh --all  # Also removes venv
```

### Windows

PowerShell (recommended):

```powershell
# First time setup
.\scripts\setup.ps1            # core only
.\scripts\setup.ps1 -All       # everything
.\scripts\setup.ps1 -Dev -Recreate

# Start the application
.\scripts\start.ps1
```

cmd.exe:

```batch
REM First time setup
scripts\setup.bat

REM Setup with extras
scripts\setup.bat --dev
scripts\setup.bat --yolo
scripts\setup.bat --all
scripts\setup.bat --recreate

REM Start the application (runs setup automatically if needed)
scripts\start.bat

REM Run tests
scripts\test.bat
scripts\test.bat --coverage
scripts\test.bat --verbose

REM Code quality
scripts\lint.bat
scripts\lint.bat --fix

REM Build package
scripts\build.bat

REM Clean up
scripts\clean.bat
scripts\clean.bat --all
```

## Script Details

### setup.sh / setup.bat

- Detects the newest available Python (3.10+), or use `--python PATH`
- Creates an isolated virtual environment in `venv/`
- Upgrades pip / setuptools / wheel
- Installs the package in editable mode, plus any requested extras
- Verifies PyQt6 can actually import, and on Linux prints the system
  libraries to install if it can't
- `--recreate` rebuilds the venv from scratch

### start.sh / start.bat / start.ps1

- Automatically runs setup if the venv doesn't exist
- Launches Annotator XE from the venv interpreter (no activation needed)
- Forwards any extra arguments straight to the application

### test.sh / test.bat

- Runs pytest test suite
- Options:
  - `--coverage`: Generate coverage report
  - `--verbose`: Verbose output with full tracebacks

### lint.sh / lint.bat

- Runs code quality tools:
  - **Ruff**: Fast Python linter
  - **Black**: Code formatter
  - **MyPy**: Static type checker
- Use `--fix` to auto-fix issues

### build.sh / build.bat

- Cleans previous builds
- Creates wheel and source distributions
- Output in `dist/` directory

### clean.sh / clean.bat

- Removes `dist/`, `build/`, `*.egg-info`
- Removes `__pycache__` directories
- Removes `.pytest_cache`, `.mypy_cache`, `htmlcov`
- Use `--all` to also remove virtual environment
