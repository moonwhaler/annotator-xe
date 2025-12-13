# Annotator XE - Project Description & Architecture

## Overview

**Annotator XE** is a modern desktop image annotation application built with PyQt6 for creating labeled datasets for computer vision and machine learning projects. It supports multiple annotation formats (YOLO, COCO, Pascal VOC, CreateML) and provides both bounding box and polygon annotations with AI-assisted auto-detection capabilities.

---

## What the Application Does

### Core Purpose
Annotator XE enables users to:
1. **Load and browse images** from a directory with async thumbnail generation
2. **Draw annotations** using bounding boxes or polygons
3. **Classify annotations** with custom labels and manage class lists
4. **Export annotations** in multiple formats (YOLO, COCO, Pascal VOC, CreateML)
5. **Auto-detect objects** using pre-trained YOLOv8 models
6. **Undo/Redo** all annotation operations
7. **Navigate large images** with zoom and pan, aided by a minimap

### Key Features

| Feature | Description |
|---------|-------------|
| **Bounding Boxes** | Click-and-drag rectangle drawing for object detection |
| **Polygons** | Click-to-place vertices for segmentation masks |
| **Vertex Editing** | Add, move, or delete individual polygon points |
| **Multi-Format Export** | YOLO (native), COCO, Pascal VOC, Apple CreateML |
| **Format Auto-Detection** | Automatically detects annotation format in directories |
| **AI Auto-Detection** | Integrate YOLOv8 models for automatic annotation |
| **Undo/Redo** | Full command pattern undo/redo for all operations |
| **Zoom & Pan** | 20%-500% zoom with Ctrl+scroll, Space+drag panning |
| **Minimap** | Navigation overview with draggable viewport rectangle |
| **GPU Acceleration** | Optional hardware-accelerated rendering via OpenGL |
| **Thumbnail Caching** | Disk-based cache system for fast thumbnail access |
| **Image Browser** | Async loading, thumbnails, search/filter, sorting, annotation markers |
| **Workspace Layouts** | Save/restore custom UI arrangements |
| **Autosave** | Optional automatic annotation persistence |
| **Dark Mode** | System-wide dark mode support |

### Annotation Format Support

| Format | Extension | Description |
|--------|-----------|-------------|
| **YOLO** | `.txt` | Normalized coordinates (default) |
| **COCO** | `.json` | Microsoft COCO format |
| **Pascal VOC** | `.xml` | XML-based format |
| **CreateML** | `.json` | Apple CreateML format |

**YOLO Bounding Box Format:**
```
class_id x_center y_center width height
```

**YOLO Polygon Format:**
```
class_id x1 y1 x2 y2 x3 y3 ... xn yn
```

All YOLO coordinates are normalized (0-1) relative to image dimensions.

---

## Project Structure

### Modular Architecture

The application follows a clean modular architecture with separation of concerns (~11,000 lines of Python):

```
annotator-xe/
├── src/annotator_xe/               # Main application package
│   ├── __init__.py
│   ├── __main__.py                 # Entry point (python -m annotator_xe)
│   ├── app.py                      # Application bootstrap
│   │
│   ├── core/                       # Business logic (UI-independent)
│   │   ├── __init__.py
│   │   ├── models.py               # Shape, Annotation dataclasses
│   │   ├── config.py               # Configuration management (YAML)
│   │   ├── annotation_format.py    # Abstract base for format handlers
│   │   ├── format_registry.py      # Format discovery & registration
│   │   ├── yolo_format.py          # YOLO annotation I/O
│   │   ├── coco_format.py          # COCO format support
│   │   ├── pascal_voc_format.py    # Pascal VOC format support
│   │   ├── createml_format.py      # Apple CreateML format support
│   │   ├── detector.py             # YOLODetector wrapper
│   │   ├── undo_redo.py            # Command pattern implementation
│   │   └── thumbnail_cache.py      # Disk-based thumbnail caching
│   │
│   ├── ui/                         # PyQt6 UI components
│   │   ├── __init__.py
│   │   ├── main_window.py          # Main application window
│   │   ├── drawing_area.py         # Canvas (CPU & GPU rendering)
│   │   ├── minimap.py              # Navigation minimap with zoom slider
│   │   ├── image_browser.py        # Image list with async thumbnails
│   │   ├── dialogs/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py         # Settings dialog
│   │   │   ├── model_selector.py   # YOLO model selector
│   │   │   ├── format_choice.py    # Format selection dialog
│   │   │   └── import_export.py    # Import/export dialogs
│   │   └── widgets/                # Custom widgets
│   │
│   ├── workers/                    # Background threads
│   │   ├── __init__.py
│   │   └── image_loader.py         # Async image/thumbnail loading
│   │
│   └── utils/                      # Utilities
│       ├── __init__.py
│       └── workspace.py            # Layout persistence
│
├── tests/                          # Comprehensive test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_models.py              # Shape/Annotation tests
│   ├── test_config.py              # Configuration tests
│   ├── test_yolo_format.py         # YOLO I/O tests
│   ├── test_coco_format.py         # COCO format tests
│   ├── test_pascal_voc_format.py   # Pascal VOC format tests
│   ├── test_createml_format.py     # CreateML format tests
│   └── test_format_detection.py    # Auto-detection tests
│
├── scripts/                        # Cross-platform automation
│   ├── setup.sh / setup.bat        # Environment setup
│   ├── run.sh / run.bat            # Run application
│   ├── test.sh / test.bat          # Run tests
│   ├── lint.sh / lint.bat          # Code quality checks
│   ├── build.sh / build.bat        # Build packages
│   ├── clean.sh / clean.bat        # Clean artifacts
│   └── README.md                   # Script documentation
│
├── pyproject.toml                  # Modern Python packaging
├── requirements.txt                # Core dependencies
├── requirements-dev.txt            # Development dependencies
├── config.yaml                     # Runtime configuration
├── workspaces.yaml                 # Saved UI layouts
├── pyQT_YOLO.py                   # Legacy entry point (preserved)
├── README.md
├── project-description.md
└── LICENSE
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| **Core Layer** | |
| `core/models.py` | Shape and Annotation dataclasses with format conversion methods |
| `core/config.py` | AppConfig, YOLODataConfig management with YAML persistence |
| `core/annotation_format.py` | Abstract base class defining format handler interface |
| `core/format_registry.py` | Factory pattern for format instantiation and discovery |
| `core/yolo_format.py` | YOLO annotation reader/writer |
| `core/coco_format.py` | COCO JSON format handler |
| `core/pascal_voc_format.py` | Pascal VOC XML format handler |
| `core/createml_format.py` | Apple CreateML JSON format handler |
| `core/detector.py` | YOLODetector wrapper for ultralytics inference |
| `core/undo_redo.py` | Command pattern for undo/redo operations |
| `core/thumbnail_cache.py` | Disk-based thumbnail caching system |
| **UI Layer** | |
| `ui/main_window.py` | MainWindow orchestrating all UI components |
| `ui/drawing_area.py` | DrawingArea canvas with CPU/GPU rendering backends |
| `ui/minimap.py` | MiniatureView with draggable viewport and zoom slider |
| `ui/image_browser.py` | ImageListItem, SortableImageList for browsing |
| `ui/dialogs/settings.py` | SettingsDialog for user preferences |
| `ui/dialogs/model_selector.py` | ModelSelector for YOLO model selection |
| `ui/dialogs/format_choice.py` | FormatChoiceDialog for format selection |
| `ui/dialogs/import_export.py` | Import/export dialogs |
| **Worker Layer** | |
| `workers/image_loader.py` | ImageScanner, ThumbnailLoader, ImageLoader threads |
| **Utility Layer** | |
| `utils/workspace.py` | WorkspaceManager for layout persistence |

---

## Architecture Highlights

### Design Patterns

1. **Command Pattern** (Undo/Redo)
   - Located in `core/undo_redo.py`
   - Command classes: `AddShapeCommand`, `DeleteShapeCommand`, `MoveShapeCommand`, `MovePointCommand`, `ChangeLabelCommand`, `DeletePointsCommand`
   - UndoRedoManager maintains command history stacks
   - Full separation between execution and UI updates

2. **MVC Separation**
   - **Model:** `core/` package - Business logic independent of UI
   - **View:** `ui/` package - PyQt6 widgets and dialogs
   - **Controller:** Signal/slot connections coordinate model-view interactions

3. **Abstract Factory** (Annotation Formats)
   - `AnnotationFormat` abstract base class defines interface
   - Concrete implementations: YOLO, COCO, Pascal VOC, CreateML
   - `FormatRegistry` manages registration and instantiation
   - Plugin-friendly architecture for adding new formats

4. **Repository Pattern**
   - Format handlers encapsulate file I/O operations
   - `ConfigManager` / `YOLODataConfigManager` manage persistence
   - Clean separation between data access and business logic

5. **Observer Pattern**
   - PyQt signals notify UI of state changes
   - Key signals: `shapes_changed`, `view_rect_changed`, `thumbnail_loaded`, `image_found`

6. **Strategy Pattern** (Rendering Backends)
   - `RenderBackendMixin` provides shared rendering logic
   - Supports both CPU rendering (QPainter) and GPU acceleration (OpenGL)
   - Graceful fallback when OpenGL unavailable

7. **Thread Worker Pattern**
   - `ImageScanner`, `ThumbnailLoader`, `ImageLoader` extend QThread
   - Background image and thumbnail loading without blocking UI
   - Priority queues for efficient thumbnail rendering

### Code Quality Features

- **Type Hints** - Full type annotations throughout (mypy compatible)
- **Dataclasses** - Immutable data models (Shape, ShapeType, AppConfig)
- **Logging** - Structured logging with Python's logging module
- **Error Handling** - Consistent exception handling with user feedback
- **Configuration** - YAML-based configuration with sensible defaults
- **Testability** - Core logic separated from UI for unit testing
- **Modular Design** - Clear separation of concerns across 25+ modules

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

### Graphics (Optional)
- PyOpenGL >= 3.1.6 (GPU acceleration)

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

The project includes a comprehensive test suite covering:

| Test Module | Coverage |
|-------------|----------|
| `test_models.py` | Shape creation, manipulation, format conversion |
| `test_config.py` | Configuration loading, saving, updates |
| `test_yolo_format.py` | YOLO file reading, writing, validation |
| `test_coco_format.py` | COCO JSON format handling |
| `test_pascal_voc_format.py` | Pascal VOC XML format handling |
| `test_createml_format.py` | Apple CreateML format handling |
| `test_format_detection.py` | Automatic format detection in directories |

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
| `config.yaml` | User settings (UI preferences, GPU settings, shortcuts) | Working directory |
| `workspaces.yaml` | Saved dock widget layouts | Working directory |
| `data.yaml` | Per-directory class definitions | Image directory |

### Configurable Settings

- Default directory and YOLO model path
- Line thickness, font size, thumbnail size
- Autosave, focus-on-select, zoom-on-select behaviors
- Thumbnail cache settings (size, max MB)
- Annotation format (YOLO/COCO/VOC/CreateML)
- Keyboard shortcuts (finish drawing, delete shape)
- GPU acceleration toggle

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

This codebase was refactored from a single 2,199-line monolithic file to a modern, extensible architecture:

### Improvements Made

| Area | Before | After |
|------|--------|-------|
| **Structure** | Single file (2,199 lines) | 25+ modules (~11,000 lines) |
| **Type Safety** | No type hints | Full type annotations (mypy) |
| **Data Models** | Plain classes | Typed dataclasses |
| **Testing** | None | Comprehensive test suite |
| **Packaging** | Manual | pyproject.toml with entry points |
| **Logging** | print statements | Structured logging |
| **Undo/Redo** | Not available | Full command pattern |
| **Scripts** | None | Cross-platform automation |
| **Error Handling** | Inconsistent | Structured with user feedback |
| **Formats** | YOLO only | YOLO, COCO, VOC, CreateML |
| **Rendering** | CPU only | CPU + GPU acceleration |
| **Thumbnails** | None | Disk-based caching |

### Architecture Benefits

- **Maintainability** - Easy to navigate and modify individual modules
- **Testability** - Core logic can be tested without UI dependencies
- **Extensibility** - Plugin-friendly format registry for new annotation formats
- **Reliability** - Type hints and tests catch errors early
- **Performance** - GPU acceleration and async loading for large datasets
- **Developer Experience** - IDE support, autocomplete, documentation

### Recent Development Focus

- GPU acceleration for image rendering (hardware acceleration)
- Minimap improvements and zoom slider
- Mouse event handling optimization
- Large-scale image browser support (handling huge image counts)
- Multi-format support expansion (COCO, Pascal VOC, CreateML)
- Enhanced image browser with search/filtering
- Point editing and polygon vertex manipulation
- Workspace save/restore improvements

---

*Document updated: December 2024*
