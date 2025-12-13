# Annotator XE

Annotator XE is a powerful and user-friendly desktop application for annotating images with bounding boxes and polygons. It's designed to streamline the process of creating datasets for computer vision and machine learning projects, with native support for multiple annotation formats including YOLO, COCO, Pascal VOC, and CreateML.

![image](https://github.com/user-attachments/assets/22c4cf92-4d6e-4a88-92fd-2c3d5eef2cf7)

## Features

- **Intuitive Interface**: Easy-to-use GUI for efficient image annotation
- **Multiple Annotation Types**: Support for both bounding boxes and polygons with vertex editing
- **Multi-Format Support**: Native export to YOLO, COCO, Pascal VOC, and Apple CreateML formats
- **AI Auto-Detection**: Integrate YOLOv8 models for automatic object annotation
- **Full Undo/Redo**: Complete undo/redo support for all annotation operations
- **Class Management**: Easily add, edit, and delete classification labels
- **Image Navigation**: Convenient image browser with thumbnails, sorting, and search/filter
- **Zoom and Pan**: Smooth zooming (20%-500%) and panning for detailed annotations
- **Minimap**: Quick navigation overview with draggable viewport for large images
- **GPU Acceleration**: Optional hardware-accelerated rendering via OpenGL
- **Thumbnail Caching**: Fast disk-based thumbnail cache for responsive browsing
- **Workspace Layouts**: Save and restore custom UI arrangements
- **Auto-save**: Optional automatic saving of annotations
- **Dark Mode**: Supports system-wide dark mode for comfortable use in low-light environments

## Installation

### Quick Install with Scripts (Recommended)

```bash
# Clone the repository
git clone https://github.com/moonwhaler/annotator-xe.git
cd annotator-xe

# Run setup script
./scripts/setup.sh        # macOS/Linux
scripts\setup.bat         # Windows
```

### Manual Install

```bash
# Clone the repository
git clone https://github.com/moonwhaler/annotator-xe.git
cd annotator-xe

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### Development Install

For development with testing and linting tools:

```bash
./scripts/setup.sh --dev  # macOS/Linux
scripts\setup.bat --dev   # Windows

# Or manually:
pip install -e ".[dev]"
```

## Usage

### Running the Application

There are multiple ways to start Annotator XE:

```bash
# Using scripts (recommended)
./scripts/run.sh          # macOS/Linux
scripts\run.bat           # Windows

# Using the entry point (after pip install)
annotator-xe

# Or as a Python module
python -m annotator_xe
```

### Basic Workflow

1. **Open Directory**: Click the folder icon or use File → Open Directory to select a folder containing your images

2. **Select a Tool**:
   - **Select** (👆): Select and move shapes or points
   - **Box** (◻️): Draw bounding boxes by clicking and dragging
   - **Polygon** (🔺): Click to place vertices, right-click or double-click to finish

3. **Manage Classifications**: Use the Classifications panel to add, edit, or delete labels

4. **Apply Labels**: Select a shape, then select a classification and click "Apply Classification"

5. **Save Annotations**: Click the save icon or enable auto-save in Settings

### Keyboard Shortcuts

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

### Annotation Formats

Annotator XE supports multiple annotation formats with automatic detection:

| Format | Extension | Description |
|--------|-----------|-------------|
| **YOLO** | `.txt` | Normalized coordinates (default) |
| **COCO** | `.json` | Microsoft COCO format |
| **Pascal VOC** | `.xml` | XML-based format |
| **CreateML** | `.json` | Apple CreateML format |

**YOLO Format Example:**

Bounding Box:
```
class_id x_center y_center width height
```

Polygon:
```
class_id x1 y1 x2 y2 x3 y3 ... xn yn
```

All YOLO coordinates are normalized (0-1) relative to image dimensions.

## Project Structure

```
annotator-xe/
├── src/annotator_xe/
│   ├── core/                     # Business logic (UI-independent)
│   │   ├── models.py             # Shape, Annotation dataclasses
│   │   ├── config.py             # Configuration management (YAML)
│   │   ├── annotation_format.py  # Abstract base for format handlers
│   │   ├── format_registry.py    # Format discovery & registration
│   │   ├── yolo_format.py        # YOLO annotation I/O
│   │   ├── coco_format.py        # COCO format support
│   │   ├── pascal_voc_format.py  # Pascal VOC format support
│   │   ├── createml_format.py    # Apple CreateML format support
│   │   ├── detector.py           # YOLO detection wrapper
│   │   ├── undo_redo.py          # Command pattern implementation
│   │   └── thumbnail_cache.py    # Disk-based thumbnail caching
│   ├── ui/                       # PyQt6 UI components
│   │   ├── main_window.py        # Main application window
│   │   ├── drawing_area.py       # Canvas (CPU & GPU rendering)
│   │   ├── minimap.py            # Navigation minimap
│   │   ├── image_browser.py      # Image list with thumbnails
│   │   ├── dialogs/
│   │   │   ├── settings.py       # Settings dialog
│   │   │   ├── model_selector.py # YOLO model selector
│   │   │   ├── format_choice.py  # Format selection dialog
│   │   │   └── import_export.py  # Import/export dialogs
│   │   └── widgets/              # Custom widgets
│   ├── workers/                  # Background threads
│   │   └── image_loader.py       # Async image/thumbnail loading
│   └── utils/
│       └── workspace.py          # Layout persistence
├── tests/                        # Test suite
├── scripts/                      # Cross-platform automation
├── pyproject.toml                # Modern Python packaging
├── requirements.txt              # Core dependencies
└── requirements-dev.txt          # Development dependencies
```

## Scripts

Cross-platform scripts are provided in the `scripts/` directory for common tasks:

| Script | macOS/Linux | Windows | Description |
|--------|-------------|---------|-------------|
| Setup | `./scripts/setup.sh` | `scripts\setup.bat` | Create venv and install dependencies |
| Run | `./scripts/run.sh` | `scripts\run.bat` | Start the application |
| Test | `./scripts/test.sh` | `scripts\test.bat` | Run test suite |
| Lint | `./scripts/lint.sh` | `scripts\lint.bat` | Run code quality checks |
| Build | `./scripts/build.sh` | `scripts\build.bat` | Create distribution packages |
| Clean | `./scripts/clean.sh` | `scripts\clean.bat` | Remove build artifacts |

### Script Options

```bash
# Setup with dev dependencies
./scripts/setup.sh --dev

# Run legacy version
./scripts/run.sh --legacy

# Test with coverage report
./scripts/test.sh --coverage

# Auto-fix lint issues
./scripts/lint.sh --fix

# Clean everything including venv
./scripts/clean.sh --all
```

## Development

### Running Tests

```bash
# Using scripts
./scripts/test.sh                 # Basic
./scripts/test.sh --coverage      # With coverage
./scripts/test.sh --verbose       # Verbose output

# Or manually
pip install -e ".[dev]"
pytest
pytest --cov=annotator_xe
```

### Code Quality

```bash
# Using scripts
./scripts/lint.sh                 # Check only
./scripts/lint.sh --fix           # Auto-fix

# Or manually
mypy src/annotator_xe             # Type checking
ruff check src/annotator_xe       # Linting
black src/annotator_xe            # Formatting
```

## Configuration Files

Annotator XE creates the following configuration files:

| File | Purpose | Location |
|------|---------|----------|
| `config.yaml` | User settings (default directory, model path, UI preferences, GPU settings) | Working directory |
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

## Requirements

- Python 3.10+
- PyQt6 >= 6.5.0
- PyYAML >= 6.0
- torch >= 2.0.0
- ultralytics >= 8.0.0
- Pillow >= 10.0.0
- PyOpenGL >= 3.1.6 (optional, for GPU acceleration)

## Updating

```bash
git pull origin main
pip install -e . --upgrade
```

## Contributing

Contributions to Annotator XE are welcome! Please feel free to:

- Submit pull requests
- Create issues for bugs or feature requests
- Improve documentation
- Share the project

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Run the test suite: `pytest`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [YOLO](https://github.com/ultralytics/ultralytics) for object detection
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the graphical user interface
- [Ultralytics](https://ultralytics.com/) for the YOLOv8 implementation
