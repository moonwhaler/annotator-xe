# Annotator XE Scripts

Cross-platform scripts for building, running, and developing Annotator XE.

## Available Scripts

| Script | Purpose |
|--------|---------|
| `setup` | Create virtual environment and install dependencies |
| `run` | Start the Annotator XE application |
| `test` | Run the test suite |
| `lint` | Run code quality checks (ruff, black, mypy) |
| `build` | Create distributable packages |
| `clean` | Remove build artifacts and caches |

## Usage

### macOS / Linux

```bash
# First time setup
./scripts/setup.sh

# Setup with dev tools
./scripts/setup.sh --dev

# Run the application
./scripts/run.sh

# Run legacy version
./scripts/run.sh --legacy

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

```batch
REM First time setup
scripts\setup.bat

REM Setup with dev tools
scripts\setup.bat --dev

REM Run the application
scripts\run.bat

REM Run legacy version
scripts\run.bat --legacy

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

- Checks Python version (requires 3.10+)
- Creates virtual environment in `venv/`
- Upgrades pip
- Installs the package in editable mode
- Use `--dev` flag to include development dependencies

### run.sh / run.bat

- Automatically runs setup if venv doesn't exist
- Activates virtual environment
- Starts Annotator XE
- Use `--legacy` to run the original `pyQT_YOLO.py`

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
