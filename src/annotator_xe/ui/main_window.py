"""Main application window for Annotator XE."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

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

from ..core.config import ConfigManager, AppConfig, YOLODataConfigManager
from ..core.detector import YOLODetector
from ..core.models import Shape, ShapeType
from ..core.yolo_format import YOLOAnnotationReader, YOLOAnnotationWriter
from ..workers.image_loader import ImageLoader, get_image_files
from ..utils.workspace import WorkspaceManager
from .dialogs.settings import SettingsDialog
from .dialogs.model_selector import ModelSelector
from .drawing_area import DrawingArea
from .minimap import MiniatureView
from .image_browser import ImageListItem, SortableImageList, add_annotation_marker

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

        # State
        self.current_directory = ""
        self.current_image = ""
        self.classes: Dict[str, int] = {}
        self.yolo_detector: Optional[YOLODetector] = None
        self.image_loader: Optional[ImageLoader] = None

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

        # Central widget with drawing area
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.image_scroll_area = QScrollArea()
        self.image_label = DrawingArea()
        self.image_label.set_scroll_area(self.image_scroll_area)
        self.image_label.line_thickness = self.config.line_thickness
        self.image_label.font_size = self.config.font_size

        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)

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

        self.image_count_label = QLabel()
        self.status_bar.addPermanentWidget(self.image_count_label)

        self.tagged_count_label = QLabel()
        self.status_bar.addPermanentWidget(self.tagged_count_label)

    def _create_dock_widgets(self) -> None:
        """Create all dock widgets."""
        # Image Browser Dock
        self.dock_widgets["Image Browser"] = QDockWidget("Image Browser", self)
        self.dock_widgets["Image Browser"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Image Browser"].setWidget(self._create_image_browser_widget())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_widgets["Image Browser"])

        # Miniature View Dock
        self.dock_widgets["Miniature View"] = QDockWidget("Miniature View", self)
        self.dock_widgets["Miniature View"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Miniature View"].setWidget(self._create_minimap_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Miniature View"])

        # Classifications Dock
        self.dock_widgets["Classifications"] = QDockWidget("Classifications", self)
        self.dock_widgets["Classifications"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Classifications"].setWidget(self._create_classifications_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Classifications"])

        # Shapes Dock
        self.dock_widgets["Shapes"] = QDockWidget("Shapes", self)
        self.dock_widgets["Shapes"].setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_widgets["Shapes"].setWidget(self._create_shapes_widget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Shapes"])

    def _create_image_browser_widget(self) -> QWidget:
        """Create the image browser widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Images:"))

        # Sorting controls
        sort_layout = QHBoxLayout()

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Date Modified", "Date Created"])
        self.sort_combo.currentTextChanged.connect(self._change_sort_role)

        self.order_combo = QComboBox()
        self.order_combo.addItems(["Ascending", "Descending"])
        self.order_combo.currentTextChanged.connect(self._change_sort_order)

        sort_layout.addWidget(QLabel("Sort by:"))
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addWidget(self.order_combo)
        layout.addLayout(sort_layout)

        # Image list
        self.image_list = SortableImageList()
        self.image_list.itemClicked.connect(self._display_image)
        layout.addWidget(self.image_list)

        # Hide tagged checkbox
        self.hide_tagged_checkbox = QCheckBox("Gray out tagged images")
        self.hide_tagged_checkbox.stateChanged.connect(self._toggle_tagged_images)
        layout.addWidget(self.hide_tagged_checkbox)

        return widget

    def _create_minimap_widget(self) -> QWidget:
        """Create the minimap widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.miniature_view = MiniatureView(self)
        self.miniature_view.view_rect_changed.connect(self._update_main_view)
        layout.addWidget(self.miniature_view, 1)

        # Zoom controls
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 0, 0)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.valueChanged.connect(self._zoom_image)

        reset_zoom_btn = QPushButton("↺")
        reset_zoom_btn.setToolTip("Reset Zoom")
        reset_zoom_btn.clicked.connect(self._reset_zoom)
        reset_zoom_btn.setMaximumWidth(30)
        reset_zoom_btn.setStyleSheet("font-size: 16px;")

        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(reset_zoom_btn)
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

        add_action = QAction(self._create_icon("➕"), "Add Classification", self)
        add_action.triggered.connect(self._add_classification)
        class_toolbar.addAction(add_action)

        edit_action = QAction(self._create_icon("✏️"), "Edit Classification", self)
        edit_action.triggered.connect(self._edit_selected_classification)
        class_toolbar.addAction(edit_action)

        delete_action = QAction(self._create_icon("🗑️"), "Delete Classification", self)
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
        layout.addWidget(self.shape_list)

        delete_button = QPushButton("Delete selected shape")
        delete_button.clicked.connect(self._delete_selected_shape_from_list)
        layout.addWidget(delete_button)

        return widget

    def _create_toolbar(self) -> None:
        """Create the main toolbar."""
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(self.toolbar)

        # Open directory
        open_action = QAction(self._create_icon("📂"), "Open Directory", self)
        open_action.triggered.connect(self._open_directory)
        self.toolbar.addAction(open_action)

        self.toolbar.addSeparator()

        # Undo/Redo
        self.undo_action = QAction(self._create_icon("↩"), "Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        self.toolbar.addAction(self.undo_action)

        self.redo_action = QAction(self._create_icon("↪"), "Redo", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        self.toolbar.addAction(self.redo_action)

        self.toolbar.addSeparator()

        # Drawing tools
        drawing_tools = QActionGroup(self)

        select_action = QAction(self._create_icon("👆"), "Select", self)
        select_action.setCheckable(True)
        select_action.triggered.connect(lambda: self._set_drawing_tool("select"))
        drawing_tools.addAction(select_action)

        box_action = QAction(self._create_icon("◻️"), "Draw Box", self)
        box_action.setCheckable(True)
        box_action.triggered.connect(lambda: self._set_drawing_tool("box"))
        drawing_tools.addAction(box_action)

        polygon_action = QAction(self._create_icon("🔺"), "Draw Polygon", self)
        polygon_action.setCheckable(True)
        polygon_action.triggered.connect(lambda: self._set_drawing_tool("polygon"))
        drawing_tools.addAction(polygon_action)

        # Save
        save_action = QAction(self._create_icon("💾"), "Save YOLO", self)
        save_action.triggered.connect(self._save_yolo)
        self.toolbar.addAction(save_action)

        # Model selection
        select_model_action = QAction(self._create_icon("🤖"), "Select Model", self)
        select_model_action.triggered.connect(self._select_model)
        self.toolbar.addAction(select_model_action)

        # Auto detect
        detect_action = QAction(self._create_icon("🔍"), "Auto Detect", self)
        detect_action.triggered.connect(self._auto_detect)
        self.toolbar.addAction(detect_action)

        # Settings
        settings_action = QAction(self._create_icon("⚙️"), "Settings", self)
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

        open_action = QAction("Open Directory", self)
        open_action.triggered.connect(self._open_directory)
        file_menu.addAction(open_action)

        save_action = QAction("Save YOLO", self)
        save_action.triggered.connect(self._save_yolo)
        file_menu.addAction(save_action)

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

        # Undo/Redo state changes
        self.image_label.undo_manager.state_changed.connect(self._update_undo_redo_state)

        # Scroll area signals for minimap
        self.image_scroll_area.horizontalScrollBar().valueChanged.connect(
            self._update_minimap_view_rect
        )
        self.image_scroll_area.verticalScrollBar().valueChanged.connect(
            self._update_minimap_view_rect
        )

    @staticmethod
    def _create_icon(text: str) -> QIcon:
        """Create an icon from emoji text."""
        app = QApplication.instance()
        palette = app.palette()
        is_dark = palette.color(QPalette.ColorRole.Window).lightness() < 128

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.setPen(Qt.GlobalColor.white if is_dark else Qt.GlobalColor.black)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        return QIcon(pixmap)

    # === File Operations ===

    def _open_directory(self) -> None:
        """Open a directory for annotation."""
        new_directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if new_directory:
            self._reset_ui()
            self.current_directory = new_directory
            self._load_images(self.current_directory)
            self._load_yaml_classes()
            self.dir_label.setText(f"Directory: {self.current_directory}")

    def _reset_ui(self) -> None:
        """Reset UI state for new directory."""
        self.current_image = ""
        self.classes = {}
        self.image_label.clear()
        self.image_label.shapes = []
        self.image_label.current_shape = None
        self.image_list.clear()
        self.class_model.clear()
        self.file_label.setText("")
        self.miniature_view.clear()
        self._reset_zoom()
        self.hide_tagged_checkbox.setChecked(False)

    def _load_images(self, dir_path: str) -> None:
        """Load images from directory in background."""
        self.image_list.clear()
        self._show_status_message("Loading images...")

        file_list = os.listdir(dir_path)
        self.image_loader = ImageLoader(dir_path, file_list)
        self.image_loader.image_loaded.connect(self._add_image_to_list)
        self.image_loader.finished.connect(self._image_loading_finished)
        self.image_loader.start()

    def _add_image_to_list(self, filename: str, icon: QIcon) -> None:
        """Add a loaded image to the list."""
        file_path = os.path.join(self.current_directory, filename)
        item = ImageListItem(icon, file_path)

        if item.has_annotation:
            item.setIcon(add_annotation_marker(icon))

        if self.hide_tagged_checkbox.isChecked() and item.has_annotation:
            item.setHidden(True)

        self.image_list.addItem(item)

    def _image_loading_finished(self) -> None:
        """Handle completion of image loading."""
        self._show_status_message("Image loading complete")
        self.image_list.sortItems()
        self.image_loader = None

        total = self.image_list.count()
        tagged = sum(
            1 for i in range(total)
            if isinstance(self.image_list.item(i), ImageListItem)
            and self.image_list.item(i).has_annotation
        )

        self.image_count_label.setText(f"Total Images: {total}")
        self.tagged_count_label.setText(f"Tagged Images: {tagged}")

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
            self.file_label.setText(f"File: {self.current_image}")
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

    def _load_yolo_annotations(self) -> None:
        """Load annotations for current image."""
        if not self.current_image or not self.image_label.pixmap():
            return

        image_path = Path(self.current_directory) / self.current_image
        txt_path = image_path.with_suffix(".txt")

        # Ensure reader has current class mapping before reading
        self.yolo_reader.set_classes(self.classes)

        shapes = self.yolo_reader.read(
            txt_path,
            self.image_label.pixmap().width(),
            self.image_label.pixmap().height()
        )

        self.image_label.shapes = shapes
        self.image_label.update()
        self._update_shape_list()

    def _save_yolo(self) -> None:
        """Save annotations in YOLO format."""
        if not self.current_image:
            return

        image_path = Path(self.current_directory) / self.current_image
        txt_path = image_path.with_suffix(".txt")
        had_annotation = txt_path.exists()

        if not self.image_label.shapes:
            if had_annotation:
                txt_path.unlink()
            self._update_image_list_item(self.current_image, False)
            return

        self.yolo_writer.set_classes(self.classes)
        self.yolo_writer.write(
            txt_path,
            self.image_label.shapes,
            self.image_label.pixmap().width(),
            self.image_label.pixmap().height()
        )

        self._save_yaml_classes()
        self._update_image_list_item(self.current_image, True)

    def _save_yaml_classes(self) -> None:
        """Save class definitions to data.yaml."""
        if self.yolo_data_manager:
            self.yolo_data_manager.update_classes(self.classes)

    def _update_image_list_item(self, image_name: str, has_annotation: bool) -> None:
        """Update image list item annotation status."""
        item = self.image_list.find_item_by_name(image_name)
        if item and item.has_annotation != has_annotation:
            item.has_annotation = has_annotation

            original_icon = QIcon(
                QPixmap(item.file_path).scaled(
                    80, 80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

            if has_annotation:
                item.setIcon(add_annotation_marker(original_icon))
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
        self.tagged_count_label.setText(f"Tagged Images: {tagged}")

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
        """Select a shape when clicked in the list."""
        selected = self.shape_list.selectedItems()
        if selected:
            index = selected[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= index < len(self.image_label.shapes):
                self.image_label.selected_shape = self.image_label.shapes[index]
                self.image_label.update()
                self.setFocus()

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

    # === Drawing Tool Operations ===

    def _set_drawing_tool(self, tool: str) -> None:
        """Set the current drawing tool."""
        self.image_label.current_tool = tool
        if tool != "polygon":
            self.image_label.finish_drawing()
        self._show_status_message(f"Current tool: {tool.capitalize()}")

    # === Zoom Operations ===

    def _zoom_image(self, value: int) -> None:
        """Handle zoom slider change."""
        self.image_label.set_scale_factor(value / 100.0)
        self._update_minimap_view_rect()

    def _update_zoom_slider(self, scale_factor: float) -> None:
        """Update zoom slider from drawing area."""
        self.zoom_slider.setValue(int(scale_factor * 100))
        self._update_minimap()

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.zoom_slider.setValue(100)
        self.image_label.set_scale_factor(1.0)

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
            self.miniature_view.set_view_rect(QRectF())
            return

        image_size = self.image_label.pixmap().size()
        viewport_size = self.image_scroll_area.viewport().size()

        visible_rect = QRectF(
            self.image_scroll_area.horizontalScrollBar().value() / self.image_label.scale_factor,
            self.image_scroll_area.verticalScrollBar().value() / self.image_label.scale_factor,
            viewport_size.width() / self.image_label.scale_factor,
            viewport_size.height() / self.image_label.scale_factor
        )

        visible_rect = visible_rect.intersected(
            QRectF(0, 0, image_size.width(), image_size.height())
        )

        miniature_scale_x = self.miniature_view.width() / image_size.width()
        miniature_scale_y = self.miniature_view.height() / image_size.height()

        miniature_rect = QRectF(
            visible_rect.x() * miniature_scale_x,
            visible_rect.y() * miniature_scale_y,
            visible_rect.width() * miniature_scale_x,
            visible_rect.height() * miniature_scale_y
        )

        self.miniature_view.set_view_rect(miniature_rect)

    def _update_main_view(self, rect: QRectF) -> None:
        """Update main view scroll position from minimap."""
        if self.image_label.pixmap():
            image_size = self.image_label.pixmap().size()
            x_ratio = rect.x() / self.miniature_view.width()
            y_ratio = rect.y() / self.miniature_view.height()

            x = x_ratio * image_size.width() * self.image_label.scale_factor
            y = y_ratio * image_size.height() * self.image_label.scale_factor

            self.image_scroll_area.horizontalScrollBar().setValue(int(x))
            self.image_scroll_area.verticalScrollBar().setValue(int(y))

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
        self.image_label.update()

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
        """Get the current dock layout."""
        layout = {}
        for name, dock in self.dock_widgets.items():
            area = self.dockWidgetArea(dock)
            layout[name] = {
                "area": area,
                "floating": dock.isFloating(),
                "geometry": dock.geometry().getRect() if dock.isFloating() else None,
                "visible": dock.isVisible(),
                "size": {"width": dock.width(), "height": dock.height()}
            }

        layout["main_window"] = {
            "size": {"width": self.width(), "height": self.height()}
        }

        return layout

    def _load_workspace(self, name: str) -> None:
        """Load a workspace layout."""
        layout = self.workspace_manager.get_workspace(name)
        if not layout:
            QMessageBox.warning(self, "Warning", f"Workspace '{name}' not found.")
            return

        if "main_window" in layout and "size" in layout["main_window"]:
            size = layout["main_window"]["size"]
            self.resize(size["width"], size["height"])

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

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self.workspace_manager.save()

        if self.image_loader:
            self.image_loader.stop()
            self.image_loader.wait()

        super().closeEvent(event)
