# Annotator XE - Project Description & Architecture

## Overview

**Annotator XE** is a modern desktop image annotation application built with PyQt6 for creating labeled datasets for computer vision and machine learning projects. It specializes in YOLO format annotations and supports both bounding box and polygon annotations with AI-assisted auto-detection capabilities.

---

## What the Application Does

### Core Purpose
Annotator XE enables users to:
1. **Load and browse images** from a directory with thumbnail previews
2. **Draw annotations** using bounding boxes or polygons
3. **Classify annotations** with custom labels
4. **Export in YOLO format** (normalized coordinates in `.txt` files)
5. **Auto-detect objects** using pre-trained YOLOv8 models
6. **Undo/Redo** all annotation operations

### Key Features

| Feature | Description |
|---------|-------------|
| **Bounding Boxes** | Click-and-drag rectangle drawing for object detection |
| **Polygons** | Click-to-place vertices for segmentation masks |
| **Vertex Editing** | Add, move, or delete individual polygon points |
| **YOLO Export** | Native support for YOLO annotation format |
| **AI Auto-Detection** | Integrate YOLOv8 models for automatic annotation |
| **Undo/Redo** | Full undo/redo support for all annotation operations (Ctrl+Z / Ctrl+Shift+Z) |
| **Zoom & Pan** | 20%-500% zoom with Ctrl+scroll, Space+drag panning |
| **Minimap** | Navigation overview with draggable viewport |
| **Workspace Layouts** | Save/restore custom UI arrangements |
| **Autosave** | Optional automatic annotation persistence |
| **Dark Mode** | System-wide dark mode support |

### YOLO Format Support

**Bounding Box Format:**
```
class_id x_center y_center width height
```

**Polygon Format:**
```
class_id x1 y1 x2 y2 x3 y3 ... xn yn
```

All coordinates are normalized (0-1) relative to image dimensions.

---

## Project Structure

### Modular Architecture

The application follows a clean modular architecture with separation of concerns:

```
annotator-xe/
├── src/annotator_xe/           # Main application package
│   ├── __init__.py
│   ├── __main__.py             # Entry point (python -m annotator_xe)
│   ├── app.py                  # Application bootstrap
│   │
│   ├── core/                   # Business logic (UI-independent)
│   │   ├── __init__.py
│   │   ├── models.py           # Shape, Annotation dataclasses
│   │   ├── config.py           # Configuration management
│   │   ├── yolo_format.py      # YOLO read/write operations
│   │   ├── detector.py         # YOLODetector wrapper
│   │   └── undo_redo.py        # Undo/Redo command pattern
│   │
│   ├── ui/                     # PyQt6 UI components
│   │   ├── __init__.py
│   │   ├── main_window.py      # Main application window
│   │   ├── drawing_area.py     # Canvas for drawing annotations
│   │   ├── minimap.py          # Navigation minimap
│   │   ├── image_browser.py    # Image list widgets
│   │   └── dialogs/
│   │       ├── __init__.py
│   │       ├── settings.py     # Settings dialog
│   │       └── model_selector.py # YOLO model selector
│   │
│   ├── workers/                # Background threads
│   │   ├── __init__.py
│   │   └── image_loader.py     # Async image loading
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       └── workspace.py        # Layout management
│
├── tests/                      # Test suite (49 tests)
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_models.py          # Shape/Annotation tests
│   ├── test_config.py          # Configuration tests
│   └── test_yolo_format.py     # YOLO I/O tests
│
├── scripts/                    # Cross-platform automation
│   ├── setup.sh / setup.bat    # Environment setup
│   ├── run.sh / run.bat        # Run application
│   ├── test.sh / test.bat      # Run tests
│   ├── lint.sh / lint.bat      # Code quality checks
│   ├── build.sh / build.bat    # Build packages
│   └── clean.sh / clean.bat    # Clean artifacts
│
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Core dependencies
├── requirements-dev.txt        # Development dependencies
├── pyQT_YOLO.py               # Legacy entry point (preserved)
├── README.md
└── LICENSE
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `core/models.py` | Shape and Annotation dataclasses with YOLO conversion methods |
| `core/config.py` | AppConfig, YOLODataConfig management with YAML persistence |
| `core/yolo_format.py` | YOLOAnnotationReader/Writer for file I/O |
| `core/detector.py` | YOLODetector wrapper for ultralytics inference |
| `core/undo_redo.py` | Command pattern implementation for undo/redo |
| `ui/main_window.py` | MainWindow orchestrating all UI components |
| `ui/drawing_area.py` | DrawingArea canvas with shape editing |
| `ui/minimap.py` | MiniatureView for navigation |
| `ui/image_browser.py` | ImageListItem, SortableImageList for image browsing |
| `ui/dialogs/settings.py` | SettingsDialog for user preferences |
| `ui/dialogs/model_selector.py` | ModelSelector for YOLO model selection |
| `workers/image_loader.py` | ImageLoader QThread for async loading |
| `utils/workspace.py` | WorkspaceManager for layout persistence |

---

## Architecture Highlights

### Design Patterns

1. **Command Pattern** (Undo/Redo)
   - All annotation operations are encapsulated as Command objects
   - Supports: Add/Delete shapes, Move shapes/points, Change labels
   - Clear separation between action execution and UI updates

2. **MVC Separation**
   - **Model:** `core/` - Business logic independent of UI
   - **View:** `ui/` - PyQt6 widgets
   - **Controller:** Signal/slot connections coordinate model and view

3. **Repository Pattern**
   - `YOLOAnnotationReader` / `YOLOAnnotationWriter` handle file I/O
   - `ConfigManager` / `YOLODataConfigManager` manage configuration

4. **Observer Pattern**
   - PyQt signals notify UI of state changes
   - `shapes_changed`, `view_changed`, `zoom_changed` signals

### Code Quality Features

- **Type Hints** - Full type annotations throughout
- **Dataclasses** - Immutable data structures for models
- **Logging** - Structured logging with Python's logging module
- **Error Handling** - Consistent exception handling with user feedback

---

## Dependencies

### Core Framework
- PyQt6 >= 6.5.0

### Machine Learning
- torch >= 2.0.0
- ultralytics >= 8.0.0

### Utilities
- PyYAML >= 6.0
- Pillow >= 10.0.0

### Development
- pytest >= 7.0.0
- pytest-qt >= 4.0.0
- pytest-cov >= 4.0.0
- mypy >= 1.0.0
- ruff >= 0.1.0
- black >= 23.0.0

---

## Installation & Usage

### Quick Start

```bash
# Clone and setup
git clone https://github.com/moonwhaler/annotator-xe.git
cd annotator-xe
./scripts/setup.sh          # macOS/Linux
scripts\setup.bat           # Windows

# Run the application
./scripts/run.sh            # macOS/Linux
scripts\run.bat             # Windows
```

### Alternative Methods

```bash
# Using pip entry point (after setup)
annotator-xe

# As Python module
python -m annotator_xe

# Direct execution (legacy)
python pyQT_YOLO.py
```

### Development

```bash
# Setup with dev dependencies
./scripts/setup.sh --dev

# Run tests
./scripts/test.sh
./scripts/test.sh --coverage

# Code quality
./scripts/lint.sh
./scripts/lint.sh --fix
```

---

## Testing

The project includes a comprehensive test suite with 49 tests covering:

| Test Module | Coverage |
|-------------|----------|
| `test_models.py` | Shape creation, manipulation, YOLO conversion |
| `test_config.py` | Configuration loading, saving, updates |
| `test_yolo_format.py` | YOLO file reading, writing, validation |

Run tests with:
```bash
./scripts/test.sh
./scripts/test.sh --coverage    # With coverage report
./scripts/test.sh --verbose     # Verbose output
```

---

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `config.yaml` | User settings (default directory, model path, UI preferences) | Working directory |
| `workspaces.yaml` | Saved dock widget layouts | Working directory |
| `data.yaml` | Per-directory YOLO class definitions | Image directory |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + Z` | Undo |
| `Ctrl + Shift + Z` | Redo |
| `Ctrl + Scroll` | Zoom in/out |
| `Space + Drag` | Pan the image |
| `Delete` | Delete selected shape or points |
| `Escape` | Cancel current drawing |
| `Right-click` | Finish polygon / Context menu |
| `Double-click` | Finish polygon |

---

## Modernization Completed

This codebase was refactored from a single 2,199-line monolithic file to a modern modular architecture:

### Improvements Made

| Area | Before | After |
|------|--------|-------|
| **Structure** | Single file (2,199 lines) | 21 modules across packages |
| **Type Safety** | No type hints | Full type annotations |
| **Data Models** | Plain classes | Dataclasses with validation |
| **Testing** | None | 49 unit tests |
| **Packaging** | Manual | pyproject.toml with entry points |
| **Logging** | print statements | Structured logging |
| **Undo/Redo** | Not available | Full undo/redo support |
| **Scripts** | None | Cross-platform automation |
| **Error Handling** | Inconsistent | Structured with user feedback |

### Architecture Benefits

- **Maintainability** - Easy to navigate and modify
- **Testability** - Core logic can be tested without UI
- **Extensibility** - New features can be added in isolation
- **Reliability** - Type hints catch errors early
- **Developer Experience** - IDE support, autocomplete, documentation

---

*Document updated: December 2024*
