"""Main application window for Annotator XE."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QSize, QRectF, QTimer
from PyQt6.QtGui import (
    QAction, QActionGroup, QPixmap, QPainter, QFont, QPalette,
    QColor, QIcon, QImageReader, QStandardItemModel, QStandardItem
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QStatusBar, QLabel, QDockWidget, QToolBar, QListWidget, QListView,
    QPushButton, QSlider, QComboBox, QCheckBox, QMenu, QMessageBox,
    QInputDialog, QFileDialog, QAbstractItemView, QListWidgetItem,
    QApplication, QSizePolicy
)

from ..core.annotation_format import AnnotationFormat
from ..core.config import ConfigManager, AppConfig, YOLODataConfigManager
from ..core.detector import YOLODetector
from ..core.format_registry import FormatRegistry
from ..core.models import Shape, ShapeType
from ..core.yolo_format import YOLOAnnotationReader, YOLOAnnotationWriter
from ..workers.image_loader import ImageLoader, ImageScanner, ThumbnailLoader, get_image_files
from ..core.thumbnail_cache import get_thumbnail_cache, ThumbnailCache
from ..utils.workspace import WorkspaceManager
from .dialogs.settings import SettingsDialog
from .dialogs.model_selector import ModelSelector
from .dialogs.format_choice import FormatChoiceDialog
from .dialogs.import_export import ImportAnnotationsDialog, ExportAnnotationsDialog
from .drawing_area import DrawingArea
from .minimap import MiniatureView
from .image_browser import (
    ImageListItem, SortableImageList, ImageBrowserWidget,
    add_annotation_marker, create_placeholder_icon
)
from .theme import get_theme_manager, ThemeMode

logger = logging.getLogger(__name__)


def increase_image_allocation_limit() -> None:
    """Remove image allocation limit for large images."""
    QImageReader.setAllocationLimit(0)


class MainWindow(QMainWindow):
    """
    Main application window for Annotator XE.

    Provides the complete UI for image annotation including:
    - Image display and navigation
    - Drawing tools for boxes and polygons
    - Classification management
    - YOLO format import/export
    - AI-powered auto-detection
    """

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()

        # Remove image allocation limit
        increase_image_allocation_limit()

        # Initialize managers
        self.config_manager = ConfigManager()
        self.workspace_manager = WorkspaceManager()
        self.yolo_reader = YOLOAnnotationReader()
        self.yolo_writer = YOLOAnnotationWriter()
        self.yolo_data_manager: Optional[YOLODataConfigManager] = None

        # Annotation format handling
        self.annotation_handler: Optional[AnnotationFormat] = None
        self.current_format: str = "yolo"
        self.annotations_cache: Dict[str, List[Shape]] = {}  # For dataset formats
        self.image_sizes_cache: Dict[str, tuple] = {}  # For dataset formats

        # State
        self.current_directory = ""
        self.current_image = ""
        self.classes: Dict[str, int] = {}
        self.yolo_detector: Optional[YOLODetector] = None
        self.image_loader: Optional[ImageLoader] = None
        self.image_scanner: Optional[ImageScanner] = None
        self.thumbnail_loader: Optional[ThumbnailLoader] = None
        self.thumbnail_cache: ThumbnailCache = get_thumbnail_cache(
            max_size_mb=self.config_manager.config.thumbnail_cache_max_mb,
            enabled=self.config_manager.config.thumbnail_cache_enabled
        )

        # UI elements (initialized in _init_ui)
        self.dock_widgets: Dict[str, QDockWidget] = {}
        self.view_actions: Dict[str, QAction] = {}
        self.image_label: Optional[DrawingArea] = None
        self.image_scroll_area: Optional[QScrollArea] = None
        self.miniature_view: Optional[MiniatureView] = None
        self.image_list: Optional[SortableImageList] = None
        self.class_list: Optional[QListView] = None
        self.class_model: Optional[QStandardItemModel] = None
        self.shape_list: Optional[QListWidget] = None
        self.zoom_slider: Optional[QSlider] = None
        self.hide_tagged_checkbox: Optional[QCheckBox] = None

        # Status bar elements
        self.status_bar: Optional[QStatusBar] = None
        self.dir_label: Optional[QLabel] = None
        self.file_label: Optional[QLabel] = None
        self.image_count_label: Optional[QLabel] = None
        self.tagged_count_label: Optional[QLabel] = None
        self.format_label: Optional[QLabel] = None

        # Load settings and initialize UI
        self._load_settings()
        self._init_ui()
        self._setup_connections()

        logger.info("MainWindow initialization complete")

    @property
    def config(self) -> AppConfig:
        """Get the current configuration."""
        return self.config_manager.config

    def _load_settings(self) -> None:
        """Load application settings."""
        config = self.config

        # Initialize theme from config
        theme_mode = ThemeMode(config.theme)
        get_theme_manager().set_mode(theme_mode)

        self.current_directory = config.default_directory
        if self.current_directory and Path(self.current_directory).is_dir():
            # Will load images after UI is initialized
            pass

        if config.yolo_model_path:
            self._load_yolo_model(config.yolo_model_path)

    def _load_yolo_model(self, model_path: str) -> bool:
        """Load a YOLO model for auto-detection."""
        try:
            self.yolo_detector = YOLODetector(model_path)
            if not self.yolo_detector.is_loaded:
                raise ValueError("Failed to initialize YOLO model")
            logger.info(f"YOLO model loaded: {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.yolo_detector = None
            return False

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle("Annotator XE")
        self.setGeometry(100, 100, 1200, 800)

        # Apply theme
        self._apply_theme()
        get_theme_manager().register_callback(self._on_theme_changed)

        # Central widget with drawing area
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.image_scroll_area = QScrollArea()
        self.image_label = DrawingArea()
        self.image_label.set_scroll_area(self.image_scroll_area)
        self.image_label.line_thickness = self.config.line_thickness
        self.image_label.font_size = self.config.font_size
        self.image_label.auto_select_on_point_click = self.config.auto_select_on_point_click
        self.image_label.finish_drawing_key = self.config.finish_drawing_key
        self.image_label.delete_shape_key = self.config.delete_shape_key

        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)

        # Apply themed background to scroll area
        colors = get_theme_manager().colors
        self.image_scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {colors.background_secondary}; border: none; }}"
        )
        self.image_scroll_area.viewport().setStyleSheet(
            f"background-color: {colors.background_secondary};"
        )

        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.image_scroll_area)

        # Status bar
        self._create_status_bar()

        # Dock widgets
        self._create_dock_widgets()

        # Toolbar
        self._create_toolbar()

        # Menu bar
        self._create_menus()

        # Restore last session window state (position, size, dock layout)
        self._restore_last_session()

        # Load images if directory was set
        if self.current_directory:
            self._load_images(self.current_directory)
            self._load_yaml_classes()

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.dir_label = QLabel()
        self.status_bar.addPermanentWidget(self.dir_label)

        self.file_label = QLabel()
        self.status_bar.addPermanentWidget(self.file_label)

        self.format_label = QLabel()
        colors = get_theme_manager().colors
        self.format_label.setStyleSheet(f"QLabel {{ color: {colors.text_muted}; }}")
        self.status_bar.addPermanentWidget(self.format_label)

        self.image_count_label = QLabel()
        self.status_bar.addPermanentWidget(self.image_count_label)

        # Keep reference but don't add to UI - counts are combined in image_count_label
        self.tagged_count_label = QLabel()

    def _create_dock_widgets(self) -> None:
        """Create all dock widgets."""
        # Image Browser Dock
        self.dock_widgets["Image Browser"] = QDockWidget("Image Browser", self)
        self.dock_widgets["Image Browser"].setObjectName("ImageBrowserDock")
        self.dock_widgets["Image Browser"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Image Browser"].setWidget(self._create_image_browser_widget())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_widgets["Image Browser"])

        # Miniature View Dock
        self.dock_widgets["Miniature View"] = QDockWidget("Miniature View", self)
        self.dock_widgets["Miniature View"].setObjectName("MiniatureViewDock")
        self.dock_widgets["Miniature View"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Miniature View"].setWidget(self._create_minimap_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Miniature View"])

        # Classifications Dock
        self.dock_widgets["Classifications"] = QDockWidget("Classifications", self)
        self.dock_widgets["Classifications"].setObjectName("ClassificationsDock")
        self.dock_widgets["Classifications"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Classifications"].setWidget(self._create_classifications_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Classifications"])

        # Shapes Dock
        self.dock_widgets["Shapes"] = QDockWidget("Shapes", self)
        self.dock_widgets["Shapes"].setObjectName("ShapesDock")
        self.dock_widgets["Shapes"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Shapes"].setWidget(self._create_shapes_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Shapes"])

    def _create_image_browser_widget(self) -> QWidget:
        """Create the image browser widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Sorting controls
        sort_layout = QHBoxLayout()
        sort_layout.setContentsMargins(8, 8, 8, 0)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Date Modified", "Date Created"])
        self.sort_combo.currentTextChanged.connect(self._change_sort_role)

        self.order_combo = QComboBox()
        self.order_combo.addItems(["Ascending", "Descending"])
        self.order_combo.currentTextChanged.connect(self._change_sort_order)

        sort_layout.addWidget(QLabel("Sort:"))
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addWidget(self.order_combo)
        sort_layout.addStretch()
        layout.addLayout(sort_layout)

        # Modern image browser widget
        self.image_browser = ImageBrowserWidget(thumbnail_size=self.config.thumbnail_size)
        self.image_browser.image_list.itemClicked.connect(self._display_image)
        self.image_browser.thumbnail_size_changed.connect(self._on_thumbnail_size_changed)
        layout.addWidget(self.image_browser, 1)

        # Convenience reference to the image list
        self.image_list = self.image_browser.image_list

        # Hide tagged checkbox
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(8, 0, 8, 8)
        self.hide_tagged_checkbox = QCheckBox("Gray out annotated")
        self.hide_tagged_checkbox.stateChanged.connect(self._toggle_tagged_images)
        options_layout.addWidget(self.hide_tagged_checkbox)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        return widget

    def _on_thumbnail_size_changed(self, size: int) -> None:
        """Handle thumbnail size changes from the browser widget."""
        self.config_manager.update(thumbnail_size=size)

    def _create_minimap_widget(self) -> QWidget:
        """Create the minimap widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.miniature_view = MiniatureView(self)
        self.miniature_view.view_rect_changed.connect(self._update_main_view)
        layout.addWidget(self.miniature_view, 1)

        # Zoom controls
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(4, 4, 4, 4)
        zoom_layout.setSpacing(4)

        # Fit to view button
        fit_btn = QPushButton("Fit")
        fit_btn.setToolTip("Fit image to view")
        fit_btn.clicked.connect(self._fit_to_view)
        fit_btn.setFixedWidth(32)

        # Zoom out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.clicked.connect(self._zoom_out_step)
        zoom_out_btn.setFixedWidth(24)

        # Zoom slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._zoom_image)

        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.clicked.connect(self._zoom_in_step)
        zoom_in_btn.setFixedWidth(24)

        # Zoom percentage label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(42)
        self.zoom_label.setToolTip("Current zoom level")

        zoom_layout.addWidget(fit_btn)
        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addWidget(self.zoom_slider, 1)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addWidget(self.zoom_label)
        layout.addWidget(zoom_widget)

        return widget

    def _create_classifications_widget(self) -> QWidget:
        """Create the classifications widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.class_list = QListView()
        self.class_model = QStandardItemModel()
        self.class_list.setModel(self.class_model)
        self.class_list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.class_list.doubleClicked.connect(self._edit_classification)
        layout.addWidget(self.class_list)

        # Class toolbar
        class_toolbar = QToolBar()
        class_toolbar.setIconSize(QSize(24, 24))

        add_action = QAction(self._create_icon("plus", 24), "Add Classification", self)
        add_action.triggered.connect(self._add_classification)
        class_toolbar.addAction(add_action)

        edit_action = QAction(self._create_icon("edit", 24), "Edit Classification", self)
        edit_action.triggered.connect(self._edit_selected_classification)
        class_toolbar.addAction(edit_action)

        delete_action = QAction(self._create_icon("delete", 24), "Delete Classification", self)
        delete_action.triggered.connect(self._delete_classification)
        class_toolbar.addAction(delete_action)

        layout.addWidget(class_toolbar)

        apply_button = QPushButton("Apply Classification")
        apply_button.clicked.connect(self._apply_classification)
        layout.addWidget(apply_button)

        return widget

    def _create_shapes_widget(self) -> QWidget:
        """Create the shapes list widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.shape_list = QListWidget()
        self.shape_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.shape_list.itemSelectionChanged.connect(self._select_shape_from_list)
        self.shape_list.itemClicked.connect(self._on_shape_list_item_clicked)
        layout.addWidget(self.shape_list)

        delete_button = QPushButton("Delete selected shape")
        delete_button.clicked.connect(self._delete_selected_shape_from_list)
        layout.addWidget(delete_button)

        return widget

    def _create_toolbar(self) -> None:
        """Create the main toolbar."""
        self.toolbar = QToolBar()
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(self.toolbar)

        # Open directory
        open_action = QAction(self._create_icon("folder"), "Open Directory", self)
        open_action.triggered.connect(self._open_directory)
        self.toolbar.addAction(open_action)

        self.toolbar.addSeparator()

        # Undo/Redo
        self.undo_action = QAction(self._create_icon("undo"), "Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        self.toolbar.addAction(self.undo_action)

        self.redo_action = QAction(self._create_icon("redo"), "Redo", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        self.toolbar.addAction(self.redo_action)

        self.toolbar.addSeparator()

        # Drawing tools
        drawing_tools = QActionGroup(self)

        select_action = QAction(self._create_icon("select"), "Select", self)
        select_action.setCheckable(True)
        select_action.triggered.connect(lambda: self._set_drawing_tool("select"))
        drawing_tools.addAction(select_action)

        box_action = QAction(self._create_icon("box"), "Draw Box", self)
        box_action.setCheckable(True)
        box_action.triggered.connect(lambda: self._set_drawing_tool("box"))
        drawing_tools.addAction(box_action)

        polygon_action = QAction(self._create_icon("polygon"), "Draw Polygon", self)
        polygon_action.setCheckable(True)
        polygon_action.triggered.connect(lambda: self._set_drawing_tool("polygon"))
        drawing_tools.addAction(polygon_action)

        # Save
        self.toolbar_save_action = QAction(self._create_icon("save"), "Save", self)
        self.toolbar_save_action.triggered.connect(self._save_annotations)
        self.toolbar.addAction(self.toolbar_save_action)

        # Model selection
        select_model_action = QAction(self._create_icon("model"), "Select Model", self)
        select_model_action.triggered.connect(self._select_model)
        self.toolbar.addAction(select_model_action)

        # Auto detect
        detect_action = QAction(self._create_icon("detect"), "Auto Detect", self)
        detect_action.triggered.connect(self._auto_detect)
        self.toolbar.addAction(detect_action)

        # Settings
        settings_action = QAction(self._create_icon("settings"), "Settings", self)
        settings_action.triggered.connect(self._open_settings)
        self.toolbar.addAction(settings_action)

        self.toolbar.addActions(drawing_tools.actions())

        # Default to select tool
        select_action.setChecked(True)
        self._set_drawing_tool("select")

    def _create_menus(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open Directory...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_directory)
        file_menu.addAction(open_action)

        # Recent Paths submenu
        self.recent_paths_menu = file_menu.addMenu("Recent Paths")
        self._update_recent_paths_menu()

        file_menu.addSeparator()

        self.menu_save_action = QAction("Save", self)
        self.menu_save_action.setShortcut("Ctrl+S")
        self.menu_save_action.triggered.connect(self._save_annotations)
        file_menu.addAction(self.menu_save_action)

        file_menu.addSeparator()

        import_action = QAction("Import Annotations...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._import_annotations)
        file_menu.addAction(import_action)

        export_action = QAction("Export Annotations...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_annotations)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        undo_menu_action = QAction("Undo", self)
        undo_menu_action.setShortcut("Ctrl+Z")
        undo_menu_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_menu_action)

        redo_menu_action = QAction("Redo", self)
        redo_menu_action.setShortcut("Ctrl+Shift+Z")
        redo_menu_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_menu_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")

        settings_action = QAction("Open Settings", self)
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_action)

        # View menu
        view_menu = menubar.addMenu("View")
        for name, dock in self.dock_widgets.items():
            action = QAction(name, self, checkable=True)
            action.setChecked(dock.isVisible())
            action.triggered.connect(lambda checked, d=dock: d.setVisible(checked))
            dock.visibilityChanged.connect(lambda visible, a=action: a.setChecked(visible))
            view_menu.addAction(action)
            self.view_actions[name] = action

        # Workspaces menu
        self.workspaces_menu = menubar.addMenu("Workspaces")
        self._update_workspaces_menu()

        # Info menu
        info_menu = menubar.addMenu("Info")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        info_menu.addAction(about_action)

    def _setup_connections(self) -> None:
        """Set up signal/slot connections."""
        # Drawing area signals
        self.image_label.view_changed.connect(self._update_minimap_view_rect)
        self.image_label.zoom_changed.connect(self._update_zoom_slider)
        self.image_label.classification_changed.connect(self._handle_classification_change)
        self.image_label.shapes_changed.connect(self._update_shapes)
        self.image_label.shape_created.connect(self._on_shape_created)
        self.image_label.points_deleted.connect(self._on_points_deleted)
        self.image_label.select_mode_requested.connect(self._switch_to_select_mode)
        self.image_label.shape_selected.connect(self._on_shape_selected_in_viewport)

        # Undo/Redo state changes
        self.image_label.undo_manager.state_changed.connect(self._update_undo_redo_state)

        # Scroll area signals for minimap
        self.image_scroll_area.horizontalScrollBar().valueChanged.connect(
            self._update_minimap_view_rect
        )
        self.image_scroll_area.verticalScrollBar().valueChanged.connect(
            self._update_minimap_view_rect
        )

        # Install event filter to catch viewport resize events
        self.image_scroll_area.viewport().installEventFilter(self)

    @staticmethod
    def _create_icon(name: str, size: int = 32) -> QIcon:
        """Create an icon from Unicode emoji/symbol.

        Args:
            name: Icon identifier
            size: Icon size in pixels
        """
        # Map icon names to Unicode symbols
        icons = {
            "folder": "📂",
            "undo": "↩",
            "redo": "↪",
            "select": "↖",
            "box": "▢",
            "polygon": "⬡",
            "save": "💾",
            "model": "🤖",
            "detect": "🔍",
            "settings": "⚙",
            "plus": "➕",
            "edit": "✏",
            "delete": "🗑",
        }

        symbol = icons.get(name, name)

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use system font for better emoji rendering
        font_size = int(size * 0.65)
        font = QFont()
        font.setPointSize(font_size)
        painter.setFont(font)

        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
        painter.end()

        return QIcon(pixmap)

    # === File Operations ===

    def _open_directory(self) -> None:
        """Open a directory for annotation."""
        new_directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if new_directory:
            self._open_directory_path(new_directory)

    def _open_directory_path(self, directory_path: str) -> None:
        """Open a specific directory for annotation."""
        if not Path(directory_path).is_dir():
            QMessageBox.warning(
                self,
                "Directory Not Found",
                f"The directory does not exist:\n{directory_path}"
            )
            return

        self._reset_ui()
        self.current_directory = directory_path
        self._detect_and_set_format(Path(directory_path))
        self._load_images(self.current_directory)
        self._load_classes_for_format()
        self.dir_label.setText(f"{self.current_directory}")
        self._add_recent_path(directory_path)

    def _add_recent_path(self, path: str) -> None:
        """Add a path to the recent paths list."""
        config = self.config_manager.config
        max_recent = config.max_recent_paths

        # Don't track if disabled
        if max_recent == 0:
            return

        recent_paths = list(config.recent_paths)

        # Remove if already exists (to move to top)
        if path in recent_paths:
            recent_paths.remove(path)

        # Insert at beginning
        recent_paths.insert(0, path)

        # Trim to max
        recent_paths = recent_paths[:max_recent]

        # Save config
        self.config_manager.update(recent_paths=recent_paths)

        # Update menu
        self._update_recent_paths_menu()

    def _update_recent_paths_menu(self) -> None:
        """Update the recent paths submenu."""
        self.recent_paths_menu.clear()

        config = self.config_manager.config
        recent_paths = config.recent_paths
        max_recent = config.max_recent_paths

        # Show disabled state if feature is disabled
        if max_recent == 0:
            disabled_action = self.recent_paths_menu.addAction("(Disabled in settings)")
            disabled_action.setEnabled(False)
            return

        # Show placeholder if no recent paths
        if not recent_paths:
            no_recent_action = self.recent_paths_menu.addAction("No recent paths")
            no_recent_action.setEnabled(False)
            return

        # Add recent paths
        for path in recent_paths:
            action = self.recent_paths_menu.addAction(path)
            action.triggered.connect(lambda checked, p=path: self._open_recent_path(p))

        # Add separator and clear action
        self.recent_paths_menu.addSeparator()
        clear_action = self.recent_paths_menu.addAction("Clear Recent Paths")
        clear_action.triggered.connect(self._clear_recent_paths)

    def _open_recent_path(self, path: str) -> None:
        """Open a path from the recent paths list."""
        self._open_directory_path(path)

    def _clear_recent_paths(self) -> None:
        """Clear all recent paths."""
        self.config_manager.update(recent_paths=[])
        self._update_recent_paths_menu()

    def _detect_and_set_format(self, directory: Path) -> bool:
        """
        Detect annotation format and initialize handler.

        Returns:
            True if format was set successfully, False if user cancelled
        """
        if self.config.auto_detect_format:
            detected_formats = FormatRegistry.detect_all_formats(directory)

            if len(detected_formats) > 1:
                # Multiple formats detected - let user choose
                dialog = FormatChoiceDialog(
                    detected_formats,
                    directory.name,
                    parent=self
                )
                if dialog.exec() == FormatChoiceDialog.DialogCode.Accepted:
                    self.current_format = dialog.get_selected_format()
                else:
                    # User cancelled - use default
                    self.current_format = self.config.default_annotation_format
                    return False
            elif len(detected_formats) == 1:
                self.current_format = detected_formats[0]
            else:
                # No format detected - use default
                self.current_format = self.config.default_annotation_format
        else:
            self.current_format = self.config.default_annotation_format

        # Initialize the format handler
        self.annotation_handler = FormatRegistry.get_handler(self.current_format)

        # Update format label in status bar
        display_name = FormatRegistry.get_display_name(self.current_format)
        self.format_label.setText(f"[{display_name}]")

        # Update Save action text to show current format
        self._update_save_action_text()

        # For dataset formats, load all annotations
        if not self.annotation_handler.is_per_image:
            self.annotations_cache = self.annotation_handler.load_directory(directory)
            # Update classes from the loaded annotations
            loaded_classes = self.annotation_handler.get_classes_from_directory(directory)
            if loaded_classes:
                self.classes = loaded_classes
                self.annotation_handler.set_classes(self.classes)
        else:
            self.annotations_cache.clear()

        logger.info(f"Using {display_name} format for {directory}")
        return True

    def _load_classes_for_format(self) -> None:
        """Load class definitions based on current format."""
        if not self.current_directory:
            return

        directory = Path(self.current_directory)

        if self.current_format == "yolo":
            # Use existing YOLO data.yaml loading
            self._load_yaml_classes()
        else:
            # Load classes from the format handler
            if self.annotation_handler:
                self.classes = self.annotation_handler.get_classes_from_directory(directory)
                self.annotation_handler.set_classes(self.classes)

        # Also update legacy YOLO reader/writer for backward compatibility
        self.yolo_reader.set_classes(self.classes)
        self.yolo_writer.set_classes(self.classes)
        self._update_classification_list()

    def _reset_ui(self) -> None:
        """Reset UI state for new directory."""
        self.current_image = ""
        self.classes = {}
        self.annotations_cache.clear()
        self.image_sizes_cache.clear()
        self.image_label.clear()
        self.image_label.shapes = []
        self.image_label.current_shape = None
        self.image_list.clear()
        self.class_model.clear()
        self.file_label.setText("")
        self.format_label.setText("")
        self.miniature_view.clear()
        self._reset_zoom()
        self.hide_tagged_checkbox.setChecked(False)

    def _load_images(self, dir_path: str) -> None:
        """Load images from directory using lazy loading.

        Phase 1: Quick scan to list all image files with placeholders
        Phase 2: On-demand thumbnail loading based on scroll position
        """
        # Stop any existing loaders
        self._stop_image_loading()

        self.image_list.clear()
        self._show_status_message("Scanning images...")

        thumbnail_size = self.config.thumbnail_size

        # Phase 1: Start quick scan
        self.image_scanner = ImageScanner(dir_path)
        self.image_scanner.image_found.connect(self._add_image_placeholder)
        self.image_scanner.finished.connect(self._image_scan_finished)
        self.image_scanner.start()

        # Phase 2: Start thumbnail loader (will load on demand)
        self.thumbnail_loader = ThumbnailLoader(
            dir_path,
            thumbnail_size,
            cache=self.thumbnail_cache
        )
        self.thumbnail_loader.thumbnail_loaded.connect(self._update_thumbnail)
        self.thumbnail_loader.queue_empty.connect(self._on_thumbnails_loaded)
        self.thumbnail_loader.start()

        # Connect visibility tracking
        self.image_list.visible_items_changed.connect(self._on_visible_items_changed)

    def _stop_image_loading(self) -> None:
        """Stop any active image loading threads."""
        if self.image_scanner:
            self.image_scanner.stop()
            self.image_scanner.wait()
            self.image_scanner = None

        if self.thumbnail_loader:
            self.thumbnail_loader.stop()
            self.thumbnail_loader.wait()
            self.thumbnail_loader = None

        if self.image_loader:
            self.image_loader.stop()
            self.image_loader.wait()
            self.image_loader = None

        # Disconnect visibility tracking if connected
        try:
            self.image_list.visible_items_changed.disconnect(self._on_visible_items_changed)
        except (TypeError, RuntimeError):
            pass  # Not connected

    def _add_image_placeholder(self, filename: str) -> None:
        """Add a placeholder for an image during the scan phase."""
        file_path = os.path.join(self.current_directory, filename)
        size = self.config.thumbnail_size
        placeholder = create_placeholder_icon(size)
        item = ImageListItem(placeholder, file_path, size, thumbnail_loaded=False)

        # Check annotation status using the format handler
        if self.annotation_handler:
            if self.annotation_handler.is_per_image:
                item.has_annotation = self.annotation_handler.has_annotation(Path(file_path))
            else:
                # For dataset formats, check the cache
                item.has_annotation = filename in self.annotations_cache and bool(self.annotations_cache[filename])

        if self.hide_tagged_checkbox.isChecked() and item.has_annotation:
            item.setHidden(True)

        self.image_list.addItem(item)

    def _image_scan_finished(self, total_count: int) -> None:
        """Handle completion of image scanning (Phase 1)."""
        self._show_status_message(f"Found {total_count} images, loading thumbnails...")
        self.image_list.sortItems()
        self.image_scanner = None

        # Update counts
        total = self.image_list.count()
        tagged = sum(
            1 for i in range(total)
            if isinstance(self.image_list.item(i), ImageListItem)
            and self.image_list.item(i).has_annotation
        )

        self.image_count_label.setText(f"{tagged}/{total} tagged")
        self.image_browser.update_stats()

        # Trigger initial thumbnail loading for visible items
        QTimer.singleShot(100, self._load_initial_thumbnails)

    def _load_initial_thumbnails(self) -> None:
        """Load thumbnails for initially visible items."""
        if self.thumbnail_loader:
            items = self.image_list.get_items_needing_thumbnails()
            if items:
                self.thumbnail_loader.request_thumbnails(items, priority=0)

    def _on_visible_items_changed(self, filenames: List[str]) -> None:
        """Handle scroll-triggered visibility changes."""
        if self.thumbnail_loader and filenames:
            self.thumbnail_loader.request_thumbnails(filenames, priority=10)

    def _update_thumbnail(self, filename: str, icon: QIcon) -> None:
        """Update an item with its loaded thumbnail."""
        item = self.image_list.find_item_by_name(filename)
        if item:
            size = self.config.thumbnail_size
            if item.has_annotation:
                item.setIcon(add_annotation_marker(icon, size))
            else:
                item.setIcon(icon)
            item.thumbnail_loaded = True

    def _add_image_to_list(self, filename: str, icon: QIcon) -> None:
        """Add a loaded image to the list (legacy method for fallback)."""
        file_path = os.path.join(self.current_directory, filename)
        size = self.config.thumbnail_size
        item = ImageListItem(icon, file_path, size, thumbnail_loaded=True)

        # Check annotation status using the format handler
        if self.annotation_handler:
            if self.annotation_handler.is_per_image:
                item.has_annotation = self.annotation_handler.has_annotation(Path(file_path))
            else:
                # For dataset formats, check the cache
                item.has_annotation = filename in self.annotations_cache and bool(self.annotations_cache[filename])

        if item.has_annotation:
            item.setIcon(add_annotation_marker(icon, size))

        if self.hide_tagged_checkbox.isChecked() and item.has_annotation:
            item.setHidden(True)

        self.image_list.addItem(item)

    def _image_loading_finished(self) -> None:
        """Handle completion of image loading (legacy method)."""
        self._show_status_message("Image loading complete")
        self.image_list.sortItems()
        self.image_loader = None

        total = self.image_list.count()
        tagged = sum(
            1 for i in range(total)
            if isinstance(self.image_list.item(i), ImageListItem)
            and self.image_list.item(i).has_annotation
        )

        self.image_count_label.setText(f"{tagged}/{total} tagged")

        # Update the image browser stats
        self.image_browser.update_stats()

    def _display_image(self, item: ImageListItem) -> None:
        """Display an image from the list."""
        if not self.current_directory:
            return

        # Always save current annotations before switching images
        if self.current_image:
            self._save_yolo()

        self.current_image = os.path.basename(item.file_path)
        image_path = item.file_path

        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", f"Failed to load image: {self.current_image}")
                return

            self.image_label.setPixmap(pixmap)
            self.image_label.shapes = []
            self.image_label.current_shape = None
            self.image_label.scale_factor = 1.0
            self.image_label.clear_undo_history()  # Clear undo history for new image

            self._load_yolo_annotations()
            self.file_label.setText(f"{self.current_image}")
            self._update_classification_list()
            self._update_shape_list()
            self._update_minimap()
            self._update_minimap_view_rect()
            self._reset_zoom()
            self.image_label.update()

            QTimer.singleShot(100, self._update_minimap_view_rect)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading image: {e}")
            logger.error(f"Error displaying image: {e}")

    # === YOLO Operations ===

    def _load_yaml_classes(self) -> None:
        """Load class definitions from data.yaml."""
        if not self.current_directory:
            return

        self.yolo_data_manager = YOLODataConfigManager(Path(self.current_directory))
        self.classes = self.yolo_data_manager.get_classes()
        self.yolo_reader.set_classes(self.classes)
        self.yolo_writer.set_classes(self.classes)
        self._update_classification_list()

    def _load_annotations(self) -> None:
        """Load annotations for current image using the active format handler."""
        if not self.current_image or not self.image_label.pixmap():
            return

        image_path = Path(self.current_directory) / self.current_image
        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        # Store image size for dataset formats
        self.image_sizes_cache[self.current_image] = (img_width, img_height)

        if self.annotation_handler:
            # Ensure handler has current class mapping
            self.annotation_handler.set_classes(self.classes)

            if self.annotation_handler.is_per_image:
                # Per-image format: read directly from file
                shapes = self.annotation_handler.read_image(image_path, img_width, img_height)
            else:
                # Dataset format: get from cache
                shapes = self.annotations_cache.get(self.current_image, []).copy()
        else:
            # Fallback to legacy YOLO reader
            txt_path = image_path.with_suffix(".txt")
            self.yolo_reader.set_classes(self.classes)
            shapes = self.yolo_reader.read(txt_path, img_width, img_height)

        self.image_label.shapes = shapes
        self.image_label.update()
        self._update_shape_list()

    def _load_yolo_annotations(self) -> None:
        """Legacy method - redirects to _load_annotations."""
        self._load_annotations()

    def _save_annotations(self) -> None:
        """Save annotations using the active format handler."""
        if not self.current_image:
            return

        image_path = Path(self.current_directory) / self.current_image
        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        # Store image size
        self.image_sizes_cache[self.current_image] = (img_width, img_height)

        has_shapes = bool(self.image_label.shapes)

        if self.annotation_handler:
            self.annotation_handler.set_classes(self.classes)

            if self.annotation_handler.is_per_image:
                # Per-image format: write directly to file
                self.annotation_handler.write_image(
                    image_path,
                    self.image_label.shapes,
                    img_width,
                    img_height
                )
            else:
                # Dataset format: update cache and save
                self.annotations_cache[self.current_image] = self.image_label.shapes.copy()
                self.annotation_handler.save_directory(
                    Path(self.current_directory),
                    self.annotations_cache,
                    self.image_sizes_cache
                )
        else:
            # Fallback to legacy YOLO writer
            txt_path = image_path.with_suffix(".txt")

            if not self.image_label.shapes:
                if txt_path.exists():
                    txt_path.unlink()
            else:
                self.yolo_writer.set_classes(self.classes)
                self.yolo_writer.write(
                    txt_path,
                    self.image_label.shapes,
                    img_width,
                    img_height
                )

        # Save class definitions (format-specific)
        self._save_classes_for_format()
        self._update_image_list_item(self.current_image, has_shapes)

    def _save_yolo(self) -> None:
        """Legacy method - redirects to _save_annotations."""
        self._save_annotations()

    def _save_classes_for_format(self) -> None:
        """Save class definitions based on current format."""
        if self.current_format == "yolo":
            self._save_yaml_classes()
        # Other formats store classes within the annotation file itself

    def _save_yaml_classes(self) -> None:
        """Save class definitions to data.yaml."""
        if self.yolo_data_manager:
            self.yolo_data_manager.update_classes(self.classes)

    def _update_save_action_text(self) -> None:
        """Update the Save action text to show current format."""
        display_name = FormatRegistry.get_display_name(self.current_format)
        save_text = f"Save ({display_name})"

        if hasattr(self, 'menu_save_action'):
            self.menu_save_action.setText(save_text)
        if hasattr(self, 'toolbar_save_action'):
            self.toolbar_save_action.setText(save_text)
            self.toolbar_save_action.setToolTip(f"Save annotations in {display_name} format")

    def _import_annotations(self) -> None:
        """Open import annotations dialog."""
        dialog = ImportAnnotationsDialog(
            current_directory=self.current_directory,
            parent=self
        )

        if dialog.exec() != ImportAnnotationsDialog.DialogCode.Accepted:
            return

        source_path, format_name, import_mode, preview_data = dialog.get_import_settings()

        if not source_path or not format_name:
            return

        try:
            # Load annotations from source
            handler = FormatRegistry.get_handler(format_name)

            if source_path.is_dir():
                imported_data = handler.load_directory(source_path)
            else:
                imported_data = preview_data  # Use already-loaded preview data

            if not imported_data:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "No annotations found in the selected source."
                )
                return

            # Apply imported annotations
            imported_count = 0
            for image_name, shapes in imported_data.items():
                # Check if image exists in current directory
                if self.current_directory:
                    image_path = Path(self.current_directory) / image_name
                    if not image_path.exists():
                        # Try to find by stem (different extension)
                        found = False
                        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
                            alt_path = image_path.with_suffix(ext)
                            if alt_path.exists():
                                image_name = alt_path.name
                                found = True
                                break
                        if not found:
                            continue

                if import_mode == "replace":
                    self.annotations_cache[image_name] = shapes.copy()
                else:  # merge
                    existing = self.annotations_cache.get(image_name, [])
                    self.annotations_cache[image_name] = existing + shapes.copy()

                imported_count += 1

                # Update classes from imported shapes
                for shape in shapes:
                    if shape.label and shape.label not in self.classes:
                        new_id = len(self.classes)
                        self.classes[shape.label] = new_id

            # Reload current image to show imported annotations
            if self.current_image and self.current_image in self.annotations_cache:
                self.image_label.shapes = self.annotations_cache[self.current_image].copy()
                self.image_label.update()
                self._update_shapes_list()

            # Save all imported annotations in current format
            if self.annotation_handler:
                self.annotation_handler.set_classes(self.classes)
                if not self.annotation_handler.is_per_image:
                    # Dataset format - save all at once
                    self.annotation_handler.save_directory(
                        Path(self.current_directory),
                        self.annotations_cache,
                        self.image_sizes_cache
                    )
                else:
                    # Per-image format - save each modified image
                    for image_name, shapes in imported_data.items():
                        if image_name in self.annotations_cache:
                            image_path = Path(self.current_directory) / image_name
                            if image_path.exists():
                                # We need image dimensions - estimate from cache or load
                                if image_name in self.image_sizes_cache:
                                    w, h = self.image_sizes_cache[image_name]
                                else:
                                    # Load to get dimensions
                                    pixmap = QPixmap(str(image_path))
                                    w, h = pixmap.width(), pixmap.height()
                                    self.image_sizes_cache[image_name] = (w, h)

                                self.annotation_handler.write_image(
                                    image_path,
                                    self.annotations_cache[image_name],
                                    w, h
                                )

            # Update class list UI
            self._update_class_list()
            self._save_classes_for_format()

            # Update image browser to show annotation markers
            self._refresh_image_list()

            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported annotations for {imported_count} images."
            )

            logger.info(f"Imported {imported_count} images from {source_path}")

        except Exception as e:
            logger.exception("Error importing annotations")
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import annotations: {e}"
            )

    def _export_annotations(self) -> None:
        """Open export annotations dialog."""
        # Check if we have polygons
        has_polygons = False
        for shapes in self.annotations_cache.values():
            for shape in shapes:
                if shape.type == ShapeType.POLYGON:
                    has_polygons = True
                    break
            if has_polygons:
                break

        # Also check current image shapes
        if not has_polygons and self.image_label:
            for shape in self.image_label.shapes:
                if shape.type == ShapeType.POLYGON:
                    has_polygons = True
                    break

        dialog = ExportAnnotationsDialog(
            current_directory=self.current_directory,
            current_format=self.current_format,
            current_image=self.current_image,
            total_images=self.image_list.count() if self.image_list else 0,
            has_polygons=has_polygons,
            parent=self
        )

        if dialog.exec() != ExportAnnotationsDialog.DialogCode.Accepted:
            return

        target_format, scope, target_dir = dialog.get_export_settings()

        if not target_format:
            return

        try:
            # Create export handler
            export_handler = FormatRegistry.get_handler(target_format, self.classes.copy())

            if scope == "current" and self.current_image:
                # Export current image only
                self._export_single_image(export_handler, target_dir)
            else:
                # Export all images
                self._export_all_images(export_handler, target_dir)

            display_name = FormatRegistry.get_display_name(target_format)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported annotations to {display_name} format in:\n{target_dir}"
            )

            logger.info(f"Exported to {target_format} format in {target_dir}")

        except Exception as e:
            logger.exception("Error exporting annotations")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export annotations: {e}"
            )

    def _export_single_image(self, handler, target_dir: Path) -> None:
        """Export annotations for the current image only."""
        if not self.current_image or not self.current_directory:
            return

        image_path = Path(self.current_directory) / self.current_image
        shapes = self.image_label.shapes if self.image_label else []

        if not shapes:
            return

        # Get image dimensions
        if self.image_label and self.image_label.pixmap():
            w = self.image_label.pixmap().width()
            h = self.image_label.pixmap().height()
        else:
            pixmap = QPixmap(str(image_path))
            w, h = pixmap.width(), pixmap.height()

        # For per-image formats, write directly
        if handler.is_per_image:
            # Write to target directory
            target_image_path = target_dir / self.current_image
            handler.write_image(target_image_path, shapes, w, h)
        else:
            # For dataset formats, create a single-image dataset
            annotations = {self.current_image: shapes}
            sizes = {self.current_image: (w, h)}
            handler.save_directory(target_dir, annotations, sizes)

    def _export_all_images(self, handler, target_dir: Path) -> None:
        """Export annotations for all images."""
        if not self.current_directory:
            return

        source_dir = Path(self.current_directory)

        # Ensure current image is saved to cache first
        if self.current_image and self.image_label:
            self.annotations_cache[self.current_image] = self.image_label.shapes.copy()
            if self.image_label.pixmap():
                self.image_sizes_cache[self.current_image] = (
                    self.image_label.pixmap().width(),
                    self.image_label.pixmap().height()
                )

        # Load ALL annotations from source directory
        all_annotations: Dict[str, List[Shape]] = {}
        all_sizes: Dict[str, Tuple[int, int]] = {}

        if self.annotation_handler:
            # For per-image formats, load_directory returns empty dict
            # We need to find all images with annotations and load them individually
            if self.annotation_handler.is_per_image:
                all_annotations, all_sizes = self._load_all_per_image_annotations(source_dir)
            else:
                # Dataset formats can load all at once
                all_annotations = self.annotation_handler.load_directory(source_dir)
                # Load image sizes for all annotated images
                for image_name in all_annotations:
                    if image_name in self.image_sizes_cache:
                        all_sizes[image_name] = self.image_sizes_cache[image_name]
                    else:
                        image_path = source_dir / image_name
                        if image_path.exists():
                            pixmap = QPixmap(str(image_path))
                            w, h = pixmap.width(), pixmap.height()
                            all_sizes[image_name] = (w, h)
                            self.image_sizes_cache[image_name] = (w, h)

            # Merge with any unsaved changes in cache (current image edits)
            for image_name, shapes in self.annotations_cache.items():
                if shapes:  # Only override if there are shapes
                    all_annotations[image_name] = shapes.copy()

        # Now export using the target handler
        if handler.is_per_image:
            for image_name, shapes in all_annotations.items():
                if not shapes:
                    continue

                if image_name not in all_sizes:
                    continue

                w, h = all_sizes[image_name]
                target_image_path = target_dir / image_name
                handler.write_image(target_image_path, shapes, w, h)
        else:
            # For dataset formats, save all at once
            handler.save_directory(target_dir, all_annotations, all_sizes)

    def _load_all_per_image_annotations(
        self,
        directory: Path
    ) -> Tuple[Dict[str, List[Shape]], Dict[str, Tuple[int, int]]]:
        """
        Load all annotations for per-image formats (YOLO, Pascal VOC).

        This finds all images with annotations and loads them with their dimensions.

        Returns:
            Tuple of (annotations dict, sizes dict)
        """
        all_annotations: Dict[str, List[Shape]] = {}
        all_sizes: Dict[str, Tuple[int, int]] = {}

        if not self.annotation_handler:
            return all_annotations, all_sizes

        # Get all image files in directory
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}

        for image_path in directory.iterdir():
            if image_path.suffix.lower() not in image_extensions:
                continue

            # Check if this image has an annotation
            if not self.annotation_handler.has_annotation(image_path):
                continue

            image_name = image_path.name

            # Get image dimensions
            if image_name in self.image_sizes_cache:
                w, h = self.image_sizes_cache[image_name]
            else:
                pixmap = QPixmap(str(image_path))
                if pixmap.isNull():
                    continue
                w, h = pixmap.width(), pixmap.height()
                self.image_sizes_cache[image_name] = (w, h)

            all_sizes[image_name] = (w, h)

            # Load annotations for this image
            shapes = self.annotation_handler.read_image(image_path, w, h)
            if shapes:
                all_annotations[image_name] = shapes

        return all_annotations, all_sizes

    def _refresh_image_list(self) -> None:
        """Refresh the image list to update annotation markers."""
        if not self.current_directory:
            return

        # Update each item's annotation status
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if isinstance(item, ImageListItem):
                has_ann = item.image_name in self.annotations_cache and bool(
                    self.annotations_cache[item.image_name]
                )
                if item.has_annotation != has_ann:
                    self._update_image_list_item(item.image_name, has_ann)

    def _update_image_list_item(self, image_name: str, has_annotation: bool) -> None:
        """Update image list item annotation status."""
        item = self.image_list.find_item_by_name(image_name)
        if item and item.has_annotation != has_annotation:
            item.has_annotation = has_annotation

            size = self.config.thumbnail_size
            original_icon = QIcon(
                QPixmap(item.file_path).scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

            if has_annotation:
                item.setIcon(add_annotation_marker(original_icon, size))
            else:
                item.setIcon(original_icon)

            if self.hide_tagged_checkbox.isChecked():
                item.setHidden(has_annotation)
            else:
                item.setHidden(False)

        # Update counts
        total = self.image_list.count()
        tagged = sum(
            1 for i in range(total)
            if isinstance(self.image_list.item(i), ImageListItem)
            and self.image_list.item(i).has_annotation
        )
        self.image_count_label.setText(f"{tagged}/{total} tagged")
        self.image_browser.update_stats()

    # === Classification Operations ===

    def _add_classification(self) -> None:
        """Add a new classification."""
        new_class, ok = QInputDialog.getText(self, "Add Classification", "Enter new classification:")
        if ok and new_class and new_class not in self.classes:
            self.classes[new_class] = len(self.classes)
            self._update_classification_list()

    def _edit_classification(self, index) -> None:
        """Edit a classification."""
        item = self.class_model.itemFromIndex(index)
        old_class = item.text()
        new_class, ok = QInputDialog.getText(
            self, "Edit Classification", "Enter new classification:", text=old_class
        )
        if ok and new_class and new_class != old_class:
            del self.classes[old_class]
            self.classes[new_class] = len(self.classes)
            self._update_classification_list()
            self._update_shape_labels(old_class, new_class)
            self._update_shape_list()

    def _edit_selected_classification(self) -> None:
        """Edit the selected classification."""
        selected = self.class_list.selectedIndexes()
        if selected:
            self._edit_classification(selected[0])

    def _delete_classification(self) -> None:
        """Delete a classification."""
        selected = self.class_list.selectedIndexes()
        if selected:
            class_to_delete = self.class_model.itemFromIndex(selected[0]).text()
            confirm = QMessageBox.question(
                self, "Confirm Deletion",
                f"Delete classification '{class_to_delete}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                del self.classes[class_to_delete]
                self._update_classification_list()
                self._remove_shape_labels(class_to_delete)

    def _apply_classification(self) -> None:
        """Apply selected classification to selected shape."""
        selected = self.class_list.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a classification to apply.")
            return

        selected_class = self.class_model.itemFromIndex(selected[0]).text()

        if self.image_label.selected_shape:
            self.image_label.selected_shape.label = selected_class
            self.image_label.update()
            self._update_shapes()
            if self.config.autosave:
                self._save_yolo()
        else:
            QMessageBox.warning(self, "Warning", "Please select a shape first.")

    def _update_classification_list(self) -> None:
        """Update the classification list display."""
        self.class_model.clear()
        for class_name in sorted(self.classes.keys()):
            item = QStandardItem(class_name)
            self.class_model.appendRow(item)

    def _update_shape_labels(self, old_label: str, new_label: str) -> None:
        """Update shape labels when classification is renamed."""
        for shape in self.image_label.shapes:
            if shape.label == old_label:
                shape.label = new_label
        self.image_label.update()

    def _remove_shape_labels(self, label: str) -> None:
        """Remove label from shapes when classification is deleted."""
        for shape in self.image_label.shapes:
            if shape.label == label:
                shape.label = ""
        self.image_label.update()

    def _handle_classification_change(self, new_label: str) -> None:
        """Handle classification change from drawing area."""
        if new_label not in self.classes:
            self.classes[new_label] = len(self.classes)
        self._update_classification_list()

    # === Shape Operations ===

    def _update_shape_list(self) -> None:
        """Update the shape list display."""
        self.shape_list.clear()
        for i, shape in enumerate(self.image_label.shapes):
            shape_type = "Box" if shape.type == ShapeType.BOX else "Polygon"
            label = shape.label if shape.label and shape.label != "-1" else "Unlabeled"
            item = QListWidgetItem(f"{shape_type} {i + 1}: {label}")
            item.setData(Qt.ItemDataRole.UserRole, i)

            if label == "Unlabeled":
                item.setForeground(QColor(128, 128, 128))

            self.shape_list.addItem(item)

    def _select_shape_from_list(self) -> None:
        """Select a shape when selection changes in the list."""
        selected = self.shape_list.selectedItems()
        if selected:
            index = selected[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= index < len(self.image_label.shapes):
                shape = self.image_label.shapes[index]
                self.image_label.selected_shape = shape
                self.image_label.update()
                self.setFocus()

    def _on_shape_list_item_clicked(self, item) -> None:
        """Handle click on shape list item - triggers focus/zoom on every click."""
        index = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= index < len(self.image_label.shapes):
            shape = self.image_label.shapes[index]
            # Ensure the shape is selected
            self.image_label.selected_shape = shape
            self.image_label.update()

            # Apply focus/zoom on every click
            if self.config.zoom_on_select:
                self._zoom_to_shape(shape)
            elif self.config.focus_on_select:
                self._focus_on_shape(shape)

    def _on_shape_selected_in_viewport(self, shape: object) -> None:
        """Update list selection when a shape is selected in the viewport.

        This is a one-way sync: viewport -> list only.
        Does not trigger zoom/focus behavior.
        """
        # Block signals to prevent _select_shape_from_list from being called
        self.shape_list.blockSignals(True)
        try:
            if shape is None:
                self.shape_list.clearSelection()
            else:
                # Find the shape's index in the shapes list
                try:
                    index = self.image_label.shapes.index(shape)
                    # Select the corresponding item in the list
                    for i in range(self.shape_list.count()):
                        item = self.shape_list.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == index:
                            self.shape_list.setCurrentItem(item)
                            break
                except ValueError:
                    # Shape not found in list
                    self.shape_list.clearSelection()
        finally:
            self.shape_list.blockSignals(False)

    def _delete_selected_shape_from_list(self) -> None:
        """Delete the selected shape from the list."""
        selected = self.shape_list.selectedItems()
        if selected:
            index = selected[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= index < len(self.image_label.shapes):
                del self.image_label.shapes[index]
                self.image_label.selected_shape = None
                self.image_label.update()
                self._update_shapes()
                if self.config.autosave:
                    self._save_yolo()

    def _update_shapes(self) -> None:
        """Update shapes display."""
        self._update_shape_list()
        self.image_label.update()

    def _on_shape_created(self) -> None:
        """Handle new shape creation."""
        self._update_shape_list()
        if self.config.autosave:
            self._save_yolo()

    def _on_points_deleted(self) -> None:
        """Handle points deletion."""
        self._update_shapes()
        if self.config.autosave:
            self._save_yolo()

    def _is_shape_visible(self, shape: Shape) -> bool:
        """Check if shape is currently visible in viewport."""
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            return True

        x, y, w, h = shape.get_bounding_rect()
        scale = self.image_label.scale_factor
        shape_screen_rect = QRectF(x * scale, y * scale, w * scale, h * scale)

        viewport = self.image_scroll_area.viewport().rect()
        scroll_x = self.image_scroll_area.horizontalScrollBar().value()
        scroll_y = self.image_scroll_area.verticalScrollBar().value()
        visible_rect = QRectF(scroll_x, scroll_y, viewport.width(), viewport.height())

        return visible_rect.intersects(shape_screen_rect)

    def _focus_on_shape(self, shape: Shape) -> None:
        """Scroll viewport to center on the shape."""
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            return

        x, y, w, h = shape.get_bounding_rect()
        center_x = x + w / 2
        center_y = y + h / 2

        scale = self.image_label.scale_factor
        screen_center_x = center_x * scale
        screen_center_y = center_y * scale

        viewport = self.image_scroll_area.viewport()
        new_scroll_x = screen_center_x - viewport.width() / 2
        new_scroll_y = screen_center_y - viewport.height() / 2

        new_scroll_x = max(0, new_scroll_x)
        new_scroll_y = max(0, new_scroll_y)

        self.image_scroll_area.horizontalScrollBar().setValue(int(new_scroll_x))
        self.image_scroll_area.verticalScrollBar().setValue(int(new_scroll_y))

    def _zoom_to_shape(self, shape: Shape) -> None:
        """Zoom viewport to fit the shape based on configured zoom level."""
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            return

        x, y, w, h = shape.get_bounding_rect()
        if w <= 0 or h <= 0:
            return

        viewport = self.image_scroll_area.viewport()
        viewport_w = viewport.width()
        viewport_h = viewport.height()

        padding = 0.1
        padded_w = w * (1 + padding)
        padded_h = h * (1 + padding)

        scale_x = viewport_w / padded_w
        scale_y = viewport_h / padded_h
        fit_scale = min(scale_x, scale_y)

        zoom_multipliers = {
            "fit": 1.0,
            "close": 1.5,
            "closer": 2.0,
            "detail": 3.0,
        }
        zoom_level = self.config.zoom_on_select_level
        multiplier = zoom_multipliers.get(zoom_level, 1.0)

        target_scale = fit_scale * multiplier
        target_scale = max(0.2, min(5.0, target_scale))

        self.image_label.set_scale_factor(target_scale)
        self.zoom_slider.setValue(int(target_scale * 100))

        self._focus_on_shape(shape)

    # === Drawing Tool Operations ===

    def _set_drawing_tool(self, tool: str) -> None:
        """Set the current drawing tool."""
        self.image_label.current_tool = tool
        self.image_label.clear_interaction_state()
        if tool != "polygon":
            self.image_label.finish_drawing()
        self._show_status_message(f"Current tool: {tool.capitalize()}")

    def _switch_to_select_mode(self) -> None:
        """Switch to select mode (triggered by point click in draw mode)."""
        self._set_drawing_tool("select")
        # Update toolbar to reflect the change
        for action in self.toolbar.actions():
            if action.text() == "Select":
                action.setChecked(True)
                break

    # === Zoom Operations ===

    def _zoom_image(self, value: int) -> None:
        """Handle zoom slider change, preserving viewport center."""
        old_scale = self.image_label.scale_factor
        new_scale = value / 100.0

        if old_scale == new_scale:
            return

        # Get current viewport center in image coordinates
        viewport = self.image_scroll_area.viewport()
        h_bar = self.image_scroll_area.horizontalScrollBar()
        v_bar = self.image_scroll_area.verticalScrollBar()

        # Center of viewport in widget coordinates
        viewport_center_x = h_bar.value() + viewport.width() / 2
        viewport_center_y = v_bar.value() + viewport.height() / 2

        # Convert to image coordinates (before scale change)
        image_center_x = viewport_center_x / old_scale if old_scale > 0 else 0
        image_center_y = viewport_center_y / old_scale if old_scale > 0 else 0

        # Apply the new scale
        self.image_label.set_scale_factor(new_scale)
        self.zoom_label.setText(f"{value}%")

        # Calculate new scroll position to keep the same image point centered
        new_viewport_center_x = image_center_x * new_scale
        new_viewport_center_y = image_center_y * new_scale

        h_bar.setValue(int(new_viewport_center_x - viewport.width() / 2))
        v_bar.setValue(int(new_viewport_center_y - viewport.height() / 2))

        self._update_minimap_view_rect()

    def _update_zoom_slider(self, scale_factor: float) -> None:
        """Update zoom slider from drawing area (wheel/gesture zoom)."""
        value = int(scale_factor * 100)
        # Block signals to prevent _zoom_image from re-adjusting scroll
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(value)
        self.zoom_slider.blockSignals(False)
        self.zoom_label.setText(f"{value}%")
        self._update_minimap()

    def _zoom_in_step(self) -> None:
        """Zoom in by a step."""
        current = self.zoom_slider.value()
        # Use predefined zoom levels for smoother stepping
        zoom_levels = [20, 25, 33, 50, 67, 75, 100, 125, 150, 200, 250, 300, 400, 500]
        for level in zoom_levels:
            if level > current:
                self.zoom_slider.setValue(level)
                return
        self.zoom_slider.setValue(500)

    def _zoom_out_step(self) -> None:
        """Zoom out by a step."""
        current = self.zoom_slider.value()
        # Use predefined zoom levels for smoother stepping
        zoom_levels = [20, 25, 33, 50, 67, 75, 100, 125, 150, 200, 250, 300, 400, 500]
        for level in reversed(zoom_levels):
            if level < current:
                self.zoom_slider.setValue(level)
                return
        self.zoom_slider.setValue(20)

    def _fit_to_view(self) -> None:
        """Fit the image to the view and center it."""
        if not self.image_label.pixmap():
            return
        viewport_size = self.image_scroll_area.viewport().size()
        pixmap_size = self.image_label.pixmap().size()

        # Calculate scale to fit in viewport with some margin
        scale_x = (viewport_size.width() - 20) / pixmap_size.width()
        scale_y = (viewport_size.height() - 20) / pixmap_size.height()
        scale = min(scale_x, scale_y)

        # Clamp to slider range
        scale_percent = max(20, min(500, int(scale * 100)))

        # Block signals and set scale directly to avoid center-preservation logic
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(scale_percent)
        self.zoom_slider.blockSignals(False)

        self.image_label.set_scale_factor(scale_percent / 100.0)
        self.zoom_label.setText(f"{scale_percent}%")

        # Center the image in the viewport
        h_bar = self.image_scroll_area.horizontalScrollBar()
        v_bar = self.image_scroll_area.verticalScrollBar()
        h_bar.setValue((h_bar.maximum()) // 2)
        v_bar.setValue((v_bar.maximum()) // 2)

        self._update_minimap_view_rect()

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.zoom_slider.setValue(100)

    # === Undo/Redo Operations ===

    def _undo(self) -> None:
        """Undo the last action."""
        if self.image_label.undo():
            self._update_shape_list()
            if self.config.autosave:
                self._save_yolo()

    def _redo(self) -> None:
        """Redo the last undone action."""
        if self.image_label.redo():
            self._update_shape_list()
            if self.config.autosave:
                self._save_yolo()

    def _update_undo_redo_state(self) -> None:
        """Update undo/redo action enabled states."""
        self.undo_action.setEnabled(self.image_label.can_undo())
        self.redo_action.setEnabled(self.image_label.can_redo())

        # Update tooltips with descriptions
        if self.image_label.can_undo():
            desc = self.image_label.undo_manager.undo_description()
            self.undo_action.setToolTip(f"Undo: {desc}")
        else:
            self.undo_action.setToolTip("Undo")

        if self.image_label.can_redo():
            desc = self.image_label.undo_manager.redo_description()
            self.redo_action.setToolTip(f"Redo: {desc}")
        else:
            self.redo_action.setToolTip("Redo")

    # === Minimap Operations ===

    def _update_minimap(self) -> None:
        """Update the minimap display."""
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            self.miniature_view.setPixmap(self.image_label.pixmap())
            self._update_minimap_view_rect()
        else:
            self.miniature_view.clear()

    def _update_minimap_view_rect(self) -> None:
        """Update the minimap viewport rectangle."""
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            self.miniature_view.set_view_rect_normalized(QRectF(0, 0, 1, 1))
            return

        image_size = self.image_label.pixmap().size()
        img_width = image_size.width()
        img_height = image_size.height()

        if img_width <= 0 or img_height <= 0:
            return

        viewport_size = self.image_scroll_area.viewport().size()
        scale = self.image_label.scale_factor

        # Calculate visible area in original image coordinates
        scroll_x = self.image_scroll_area.horizontalScrollBar().value()
        scroll_y = self.image_scroll_area.verticalScrollBar().value()

        # Visible area in original image pixels
        visible_x = scroll_x / scale
        visible_y = scroll_y / scale
        visible_width = viewport_size.width() / scale
        visible_height = viewport_size.height() / scale

        # Clamp to image bounds
        visible_x = max(0, min(visible_x, img_width))
        visible_y = max(0, min(visible_y, img_height))
        visible_width = min(visible_width, img_width - visible_x)
        visible_height = min(visible_height, img_height - visible_y)

        # Also cap to image size (when zoomed out, viewport might be larger than image)
        visible_width = min(visible_width, img_width)
        visible_height = min(visible_height, img_height)

        # Convert to normalized coordinates (0-1)
        norm_rect = QRectF(
            visible_x / img_width,
            visible_y / img_height,
            visible_width / img_width,
            visible_height / img_height
        )

        self.miniature_view.set_view_rect_normalized(norm_rect)

    def _update_main_view(self, rect: QRectF) -> None:
        """Update main view scroll position from minimap (rect is in normalized 0-1 coords)."""
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            return

        image_size = self.image_label.pixmap().size()
        img_width = image_size.width()
        img_height = image_size.height()

        if img_width <= 0 or img_height <= 0:
            return

        # Convert normalized coordinates to original image coordinates
        image_x = rect.x() * img_width
        image_y = rect.y() * img_height

        # Apply the drawing area's zoom scale to get scroll position
        scroll_x = image_x * self.image_label.scale_factor
        scroll_y = image_y * self.image_label.scale_factor

        self.image_scroll_area.horizontalScrollBar().setValue(int(scroll_x))
        self.image_scroll_area.verticalScrollBar().setValue(int(scroll_y))

    # === Auto Detection ===

    def _select_model(self) -> None:
        """Open model selection dialog."""
        dialog = ModelSelector(self)
        if dialog.exec():
            model_path = dialog.get_model_path()
            if model_path and self._load_yolo_model(model_path):
                self.config_manager.update(yolo_model_path=model_path)

    def _auto_detect(self) -> None:
        """Run auto-detection on current image."""
        if not self.yolo_detector or not self.yolo_detector.is_loaded:
            QMessageBox.warning(self, "Warning", "Please select a valid YOLO model first.")
            return

        if not self.current_image:
            QMessageBox.warning(self, "Warning", "No image selected.")
            return

        image_path = os.path.join(self.current_directory, self.current_image)

        try:
            self._show_status_message("Detecting objects...")
            shapes = self.yolo_detector.detect(image_path)
            self._show_status_message("Detection complete")

            self.image_label.shapes = shapes
            self.image_label.update()

            # Add detected class names
            for shape in shapes:
                if shape.label and shape.label not in self.classes:
                    self.classes[shape.label] = len(self.classes)

            self._update_classification_list()
            self._update_shape_list()

            if not shapes:
                QMessageBox.information(self, "Info", "No detections found.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Detection failed: {e}")
            logger.error(f"Auto-detection error: {e}")

    # === Sorting Operations ===

    def _change_sort_role(self, role: str) -> None:
        """Change the image list sort role."""
        role_map = {
            "Name": "name",
            "Date Modified": "date_modified",
            "Date Created": "date_created"
        }
        self.image_list.setSortRole(role_map[role])
        self.image_list.sortItems()

    def _change_sort_order(self, order: str) -> None:
        """Change the image list sort order."""
        order_map = {
            "Ascending": Qt.SortOrder.AscendingOrder,
            "Descending": Qt.SortOrder.DescendingOrder
        }
        self.image_list.setSortOrder(order_map[order])
        self.image_list.sortItems()

    def _toggle_tagged_images(self) -> None:
        """Toggle visibility of tagged images."""
        hide = self.hide_tagged_checkbox.isChecked()
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if isinstance(item, ImageListItem):
                item.setHidden(hide and item.has_annotation)

    # === Settings Operations ===

    def _open_settings(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self, self.config_manager)
        dialog.load_settings()
        if dialog.exec():
            self._apply_settings()

    def _apply_settings(self) -> None:
        """Apply updated settings."""
        config = self.config_manager.config
        self.image_label.line_thickness = config.line_thickness
        self.image_label.font_size = config.font_size
        self.image_label.auto_select_on_point_click = config.auto_select_on_point_click
        self.image_label.finish_drawing_key = config.finish_drawing_key
        self.image_label.delete_shape_key = config.delete_shape_key

        # Apply GPU acceleration setting (takes effect immediately)
        self.image_label.set_gpu_acceleration(config.gpu_acceleration)

        self.image_label.update()

    def _apply_theme(self) -> None:
        """Apply the current theme stylesheet to the main window."""
        self.setStyleSheet(get_theme_manager().get_main_window_stylesheet())
        # Apply background to scroll area viewport (canvas area)
        colors = get_theme_manager().colors
        if self.image_scroll_area:
            self.image_scroll_area.setStyleSheet(
                f"QScrollArea {{ background-color: {colors.background_secondary}; border: none; }}"
            )
            self.image_scroll_area.viewport().setStyleSheet(
                f"background-color: {colors.background_secondary};"
            )

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        """Handle theme change."""
        self._apply_theme()
        # Update format label color based on theme
        colors = get_theme_manager().colors
        self.format_label.setStyleSheet(f"QLabel {{ color: {colors.text_muted}; }}")

    # === Workspace Operations ===

    def _update_workspaces_menu(self) -> None:
        """Update the workspaces menu."""
        self.workspaces_menu.clear()

        save_action = self.workspaces_menu.addAction("Save current workspace")
        save_action.triggered.connect(self._save_current_workspace)
        self.workspaces_menu.addSeparator()

        for name in self.workspace_manager.workspace_names:
            action = self.workspaces_menu.addAction(name)
            action.triggered.connect(lambda checked, n=name: self._load_workspace(n))

    def _save_current_workspace(self) -> None:
        """Save the current workspace layout."""
        name, ok = QInputDialog.getText(self, "Save Workspace", "Enter workspace name:")
        if ok and name:
            if self.workspace_manager.has_workspace(name):
                confirm = QMessageBox.question(
                    self, "Confirm Overwrite",
                    f"Workspace '{name}' exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm == QMessageBox.StandardButton.No:
                    return

            layout = self._get_current_layout()
            self.workspace_manager.add_workspace(name, layout)
            self._update_workspaces_menu()

    def _get_current_layout(self) -> Dict[str, Any]:
        """Get the current dock layout including full window state."""
        layout = {}
        for name, dock in self.dock_widgets.items():
            area = self.dockWidgetArea(dock)
            # Convert geometry tuple to list for YAML serialization
            geom = dock.geometry().getRect() if dock.isFloating() else None
            layout[name] = {
                "area": area,
                "floating": dock.isFloating(),
                "geometry": list(geom) if geom else None,
                "visible": dock.isVisible(),
                "size": {"width": dock.width(), "height": dock.height()}
            }

        # Save main window state including position, size, and window state
        layout["main_window"] = {
            "geometry": {
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height()
            },
            "state": self._get_window_state_string(),
            "qt_state": base64.b64encode(self.saveState().data()).decode('utf-8')
        }

        return layout

    def _get_window_state_string(self) -> str:
        """Get the current window state as a string."""
        if self.isMaximized():
            return "maximized"
        elif self.isMinimized():
            return "minimized"
        return "normal"

    def _save_session_state(self) -> None:
        """Save the current window state for automatic restoration on next launch."""
        layout = self._get_current_layout()
        self.workspace_manager.add_workspace("_last_session", layout)
        logger.info("Session state saved")

    def _restore_last_session(self) -> None:
        """Restore the last session state if available."""
        layout = self.workspace_manager.get_workspace("_last_session")
        if layout:
            logger.info("Restoring last session state")
            self._apply_layout(layout, show_window=False)
        else:
            logger.info("No previous session state found")

    def _load_workspace(self, name: str) -> None:
        """Load a workspace layout."""
        layout = self.workspace_manager.get_workspace(name)
        if not layout:
            QMessageBox.warning(self, "Warning", f"Workspace '{name}' not found.")
            return

        self._apply_layout(layout)

    def _apply_layout(self, layout: Dict[str, Any], show_window: bool = True) -> None:
        """Apply a workspace layout to the window.

        Args:
            layout: Layout dictionary with dock and main window settings
            show_window: Whether to show/activate the window after applying (set to False during init)
        """
        main_window_settings = layout.get("main_window", {})

        # Handle main window geometry (supports both old and new format)
        if "geometry" in main_window_settings:
            geom = main_window_settings["geometry"]
            self.setGeometry(geom["x"], geom["y"], geom["width"], geom["height"])
        elif "size" in main_window_settings:
            # Backwards compatibility with old format
            size = main_window_settings["size"]
            self.resize(size["width"], size["height"])

        # Restore Qt state (handles dock tabification and complex layouts)
        qt_state = main_window_settings.get("qt_state")
        if qt_state:
            try:
                state_bytes = base64.b64decode(qt_state.encode('utf-8'))
                self.restoreState(state_bytes)
            except Exception as e:
                logger.warning(f"Failed to restore Qt state: {e}")
                # Fall back to manual dock restoration
                self._apply_dock_layout_manually(layout)
        else:
            # No Qt state saved, use manual restoration
            self._apply_dock_layout_manually(layout)

        # Apply window state (maximized/normal) after geometry is set
        window_state = main_window_settings.get("state", "normal")
        if show_window:
            if window_state == "maximized":
                self.showMaximized()
            elif window_state == "minimized":
                self.showMinimized()
            else:
                self.showNormal()

    def _apply_dock_layout_manually(self, layout: Dict[str, Any]) -> None:
        """Apply dock layout manually (fallback when Qt state is not available)."""
        for dock_name, settings in layout.items():
            if dock_name == "main_window":
                continue

            if dock_name in self.dock_widgets:
                dock = self.dock_widgets[dock_name]
                area = settings.get("area", Qt.DockWidgetArea.NoDockWidgetArea)
                self.addDockWidget(area, dock)
                dock.setFloating(settings.get("floating", False))

                if settings.get("floating") and settings.get("geometry"):
                    dock.setGeometry(*settings["geometry"])
                elif "size" in settings:
                    dock.resize(settings["size"]["width"], settings["size"]["height"])

                dock.setVisible(settings.get("visible", True))

    # === Utility Methods ===

    def _show_status_message(self, message: str) -> None:
        """Show a status bar message."""
        self.status_bar.showMessage(message)

    def _on_thumbnails_loaded(self) -> None:
        """Update status message when thumbnail loading completes."""
        total = self.image_list.count()
        self.status_bar.showMessage(f"Found {total} images")

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Annotator XE",
            "Annotator XE\nVersion 1.0.0\n\n"
            "A powerful tool for image annotation and YOLO format generation."
        )

    # === Event Handlers ===

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Delete:
            if self.image_label.selected_points:
                self.image_label.delete_selected_points()
            elif self.image_label.selected_shape:
                self._delete_selected_shape()
        super().keyPressEvent(event)

    def _delete_selected_shape(self) -> None:
        """Delete the selected shape."""
        if self.image_label.selected_shape:
            self.image_label.shapes.remove(self.image_label.selected_shape)
            self.image_label.selected_shape = None
            self.image_label.update()
            self.image_label.shapes_changed.emit()

            if self.config.autosave:
                self._save_yolo()

    def resizeEvent(self, event) -> None:
        """Handle window resize."""
        super().resizeEvent(event)
        self._update_minimap_view_rect()

    def eventFilter(self, obj, event) -> bool:
        """Filter events for the scroll area viewport to catch resize."""
        from PyQt6.QtCore import QEvent

        if obj == self.image_scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            # Viewport was resized, update minimap
            self._update_minimap_view_rect()

        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Save current window state for next launch
        self._save_session_state()

        # Stop all image loading threads
        self._stop_image_loading()

        # Cleanup thumbnail cache
        if self.thumbnail_cache:
            self.thumbnail_cache.cleanup()

        super().closeEvent(event)
