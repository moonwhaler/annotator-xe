"""Settings dialog for Annotator XE."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QWidget,
    QLineEdit, QPushButton, QSpinBox, QCheckBox, QDialogButtonBox,
    QFileDialog, QComboBox, QKeySequenceEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QLabel, QFrame, QSizePolicy, QGroupBox, QScrollArea
)
from PyQt6.QtGui import QKeySequence, QFont

from ...core.config import AppConfig, ConfigManager
from ...core.format_registry import FormatRegistry
from ..drawing_area import is_opengl_available

logger = logging.getLogger(__name__)

# Modern stylesheet for the settings dialog
SETTINGS_STYLESHEET = """
QDialog {
    background-color: #1e1e1e;
}

QListWidget {
    background-color: #252526;
    border: none;
    border-radius: 8px;
    padding: 8px 4px;
    outline: none;
}

QListWidget::item {
    color: #cccccc;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}

QListWidget::item:selected {
    background-color: #0e639c;
    color: #ffffff;
}

QListWidget::item:hover:!selected {
    background-color: #2a2d2e;
}

QStackedWidget {
    background-color: transparent;
}

QGroupBox {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    padding-top: 32px;
    font-weight: bold;
    color: #cccccc;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    color: #cccccc;
}

QLabel {
    color: #cccccc;
}

QLabel[class="description"] {
    color: #808080;
    font-size: 11px;
}

QLabel[class="section-title"] {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
}

QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 12px;
    color: #cccccc;
    selection-background-color: #0e639c;
}

QLineEdit:focus {
    border-color: #0e639c;
}

QLineEdit:disabled {
    background-color: #2d2d2d;
    color: #808080;
}

QSpinBox {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 12px;
    color: #cccccc;
    min-width: 80px;
}

QSpinBox:focus {
    border-color: #0e639c;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #4a4a4a;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #5a5a5a;
}

QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 12px;
    color: #cccccc;
    min-width: 150px;
}

QComboBox:focus {
    border-color: #0e639c;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #cccccc;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    selection-background-color: #0e639c;
    color: #cccccc;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 6px 8px;
    min-height: 24px;
}

QPushButton {
    background-color: #0e639c;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: #ffffff;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #0d5a8c;
}

QPushButton[class="secondary"] {
    background-color: #3c3c3c;
    color: #cccccc;
}

QPushButton[class="secondary"]:hover {
    background-color: #4a4a4a;
}

QCheckBox {
    color: #cccccc;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #555555;
    background-color: #3c3c3c;
}

QCheckBox::indicator:checked {
    background-color: #0e639c;
    border-color: #0e639c;
}

QCheckBox::indicator:hover {
    border-color: #0e639c;
}

QKeySequenceEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 12px;
    color: #cccccc;
    min-width: 150px;
}

QKeySequenceEdit:focus {
    border-color: #0e639c;
}

QDialogButtonBox {
    padding: 16px 0 0 0;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #666666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class SettingsDialog(QDialog):
    """
    Modern settings dialog for configuring application preferences.

    Uses a sidebar navigation with grouped settings sections.
    """

    def __init__(self, parent=None, config_manager: Optional[ConfigManager] = None) -> None:
        """
        Initialize the settings dialog.

        Args:
            parent: Parent widget
            config_manager: Configuration manager instance
        """
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Settings")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        self.setStyleSheet(SETTINGS_STYLESHEET)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Sidebar navigation
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setSpacing(2)

        nav_items = [
            ("General", "general"),
            ("Appearance", "appearance"),
            ("Behavior", "behavior"),
            ("Shortcuts", "shortcuts"),
        ]

        for label, data in nav_items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        main_layout.addWidget(self.nav_list)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_general_page())
        self.stack.addWidget(self._create_appearance_page())
        self.stack.addWidget(self._create_behavior_page())
        self.stack.addWidget(self._create_shortcuts_page())
        content_layout.addWidget(self.stack, 1)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_settings)
        button_box.rejected.connect(self.reject)
        content_layout.addWidget(button_box)

        main_layout.addLayout(content_layout, 1)

    def _on_nav_changed(self, index: int) -> None:
        """Handle navigation item change."""
        self.stack.setCurrentIndex(index)

    def _create_scrollable_page(self, content_widget: QWidget) -> QScrollArea:
        """Wrap a content widget in a scroll area for proper scrolling."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content_widget)
        return scroll

    def _create_section_header(self, title: str, description: str = "") -> QWidget:
        """Create a section header with title and optional description."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setProperty("class", "section-title")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setProperty("class", "description")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        return widget

    def _create_setting_row(self, label: str, widget: QWidget, description: str = "") -> QWidget:
        """Create a setting row with label, widget, and optional description."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(4)

        # Top row: label and widget
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)

        label_widget = QLabel(label)
        label_widget.setFixedWidth(160)
        label_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        row_layout.addWidget(label_widget)

        # Give widgets proper sizing
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_layout.addWidget(widget, 1)
        layout.addLayout(row_layout)

        # Description below
        if description:
            desc_label = QLabel(description)
            desc_label.setProperty("class", "description")
            desc_label.setWordWrap(True)
            desc_label.setContentsMargins(176, 0, 0, 0)  # Align with widget (160 + 16 spacing)
            layout.addWidget(desc_label)

        return container

    def _create_path_input(self, line_edit: QLineEdit, browse_callback) -> QWidget:
        """Create a path input with inline browse button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        line_edit.setReadOnly(True)
        layout.addWidget(line_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setProperty("class", "secondary")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(browse_callback)
        layout.addWidget(browse_btn)

        return container

    def _create_general_page(self) -> QScrollArea:
        """Create the General settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 16, 0)
        layout.setSpacing(8)

        # Header
        layout.addWidget(self._create_section_header(
            "General",
            "Configure default paths and file handling options."
        ))

        # Paths group
        paths_group = QGroupBox("Paths")
        paths_layout = QVBoxLayout(paths_group)
        paths_layout.setSpacing(2)

        self.default_dir_edit = QLineEdit()
        self.default_dir_edit.setPlaceholderText("No directory selected")
        paths_layout.addWidget(self._create_setting_row(
            "Default Directory",
            self._create_path_input(self.default_dir_edit, self._browse_default_dir),
            "Starting directory when opening images"
        ))

        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText("No model selected")
        paths_layout.addWidget(self._create_setting_row(
            "YOLO Model",
            self._create_path_input(self.model_path_edit, self._browse_model_path),
            "Default YOLO model for auto-detection (.pt file)"
        ))

        layout.addWidget(paths_group)

        # File handling group
        files_group = QGroupBox("File Handling")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(2)

        self.autosave_checkbox = QCheckBox("Enable autosave")
        files_layout.addWidget(self._create_setting_row(
            "Autosave",
            self.autosave_checkbox,
            "Automatically save annotation files when switching images"
        ))

        layout.addWidget(files_group)

        # Annotation format group
        format_group = QGroupBox("Annotation Format")
        format_layout = QVBoxLayout(format_group)
        format_layout.setSpacing(2)

        self.default_format_combo = QComboBox()
        self.default_format_combo.setMinimumWidth(200)
        for format_name in FormatRegistry.get_format_names():
            display_name = FormatRegistry.get_display_name(format_name)
            description = FormatRegistry.get_description(format_name)
            self.default_format_combo.addItem(f"{display_name}", format_name)
            self.default_format_combo.setItemData(
                self.default_format_combo.count() - 1,
                description,
                Qt.ItemDataRole.ToolTipRole
            )
        format_layout.addWidget(self._create_setting_row(
            "Default Format",
            self.default_format_combo,
            "Default annotation format for new directories"
        ))

        self.auto_detect_format_checkbox = QCheckBox("Enable auto-detection")
        format_layout.addWidget(self._create_setting_row(
            "Auto-detect Format",
            self.auto_detect_format_checkbox,
            "Automatically detect annotation format when opening a directory"
        ))

        layout.addWidget(format_group)

        layout.addStretch()
        return self._create_scrollable_page(page)

    def _create_appearance_page(self) -> QScrollArea:
        """Create the Appearance settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 16, 0)
        layout.setSpacing(8)

        # Header
        layout.addWidget(self._create_section_header(
            "Appearance",
            "Customize how annotations and images are displayed."
        ))

        # Annotations group
        annotations_group = QGroupBox("Annotations")
        annotations_layout = QVBoxLayout(annotations_group)
        annotations_layout.setSpacing(2)

        self.line_thickness_spinbox = QSpinBox()
        self.line_thickness_spinbox.setRange(1, 10)
        self.line_thickness_spinbox.setSuffix(" px")
        self.line_thickness_spinbox.setMinimumWidth(100)
        annotations_layout.addWidget(self._create_setting_row(
            "Line Thickness",
            self.line_thickness_spinbox,
            "Thickness of annotation outlines (1-10 pixels)"
        ))

        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(6, 24)
        self.font_size_spinbox.setSuffix(" pt")
        self.font_size_spinbox.setMinimumWidth(100)
        annotations_layout.addWidget(self._create_setting_row(
            "Label Size",
            self.font_size_spinbox,
            "Font size for annotation labels (6-24 points)"
        ))

        layout.addWidget(annotations_group)

        # Image Browser group
        browser_group = QGroupBox("Image Browser")
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.setSpacing(2)

        self.thumbnail_size_spinbox = QSpinBox()
        self.thumbnail_size_spinbox.setRange(48, 160)
        self.thumbnail_size_spinbox.setSuffix(" px")
        self.thumbnail_size_spinbox.setSingleStep(8)
        self.thumbnail_size_spinbox.setMinimumWidth(100)
        browser_layout.addWidget(self._create_setting_row(
            "Thumbnail Size",
            self.thumbnail_size_spinbox,
            "Default size of image thumbnails (48-160 pixels)"
        ))

        layout.addWidget(browser_group)

        # Rendering group
        rendering_group = QGroupBox("Rendering")
        rendering_layout = QVBoxLayout(rendering_group)
        rendering_layout.setSpacing(2)

        self.gpu_acceleration_checkbox = QCheckBox("Enable GPU acceleration")

        # Disable if OpenGL is not available
        if not is_opengl_available():
            self.gpu_acceleration_checkbox.setEnabled(False)
            self.gpu_acceleration_checkbox.setToolTip("OpenGL not available on this system")
            description = "OpenGL not available - GPU acceleration is disabled"
        else:
            description = "Use GPU for hardware-accelerated image display (may improve performance with large images)"

        rendering_layout.addWidget(self._create_setting_row(
            "GPU Rendering",
            self.gpu_acceleration_checkbox,
            description
        ))

        layout.addWidget(rendering_group)

        layout.addStretch()
        return self._create_scrollable_page(page)

    def _create_behavior_page(self) -> QScrollArea:
        """Create the Behavior settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 16, 0)
        layout.setSpacing(8)

        # Header
        layout.addWidget(self._create_section_header(
            "Behavior",
            "Configure how the application responds to your actions."
        ))

        # Selection group
        selection_group = QGroupBox("Selection")
        selection_layout = QVBoxLayout(selection_group)
        selection_layout.setSpacing(2)

        self.focus_on_select_checkbox = QCheckBox("Enable focus on selection")
        selection_layout.addWidget(self._create_setting_row(
            "Focus Viewport",
            self.focus_on_select_checkbox,
            "Center the viewport on a shape when it's selected"
        ))

        self.zoom_on_select_checkbox = QCheckBox("Enable zoom on selection")
        selection_layout.addWidget(self._create_setting_row(
            "Zoom on Select",
            self.zoom_on_select_checkbox,
            "Automatically zoom to a shape when it's selected"
        ))

        self.zoom_level_combo = QComboBox()
        self.zoom_level_combo.setMinimumWidth(180)
        self.zoom_level_combo.addItem("Fit to viewport", "fit")
        self.zoom_level_combo.addItem("Close (1.5x)", "close")
        self.zoom_level_combo.addItem("Closer (2x)", "closer")
        self.zoom_level_combo.addItem("Detail (3x)", "detail")
        selection_layout.addWidget(self._create_setting_row(
            "Zoom Level",
            self.zoom_level_combo,
            "How much to zoom when selecting a shape"
        ))

        layout.addWidget(selection_group)

        # Drawing group
        drawing_group = QGroupBox("Drawing")
        drawing_layout = QVBoxLayout(drawing_group)
        drawing_layout.setSpacing(2)

        self.auto_select_checkbox = QCheckBox("Enable auto-switch")
        drawing_layout.addWidget(self._create_setting_row(
            "Auto Select Mode",
            self.auto_select_checkbox,
            "Automatically switch to select mode when clicking on a point"
        ))

        layout.addWidget(drawing_group)

        layout.addStretch()
        return self._create_scrollable_page(page)

    def _create_shortcuts_page(self) -> QScrollArea:
        """Create the Shortcuts settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 16, 0)
        layout.setSpacing(8)

        # Header
        layout.addWidget(self._create_section_header(
            "Keyboard Shortcuts",
            "Customize keyboard shortcuts for common actions."
        ))

        # Shortcuts group
        shortcuts_group = QGroupBox("Drawing Shortcuts")
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        shortcuts_layout.setSpacing(2)

        self.finish_drawing_key_edit = QKeySequenceEdit()
        self.finish_drawing_key_edit.setToolTip("Press a key combination or clear to disable")
        self.finish_drawing_key_edit.setMinimumWidth(180)
        shortcuts_layout.addWidget(self._create_setting_row(
            "Finish Drawing",
            self.finish_drawing_key_edit,
            "Key to finish drawing the current polygon"
        ))

        self.delete_shape_key_edit = QKeySequenceEdit()
        self.delete_shape_key_edit.setToolTip("Press a key combination or clear to disable")
        self.delete_shape_key_edit.setMinimumWidth(180)
        shortcuts_layout.addWidget(self._create_setting_row(
            "Delete Shape",
            self.delete_shape_key_edit,
            "Key to delete the currently selected shape"
        ))

        layout.addWidget(shortcuts_group)

        # Info label
        info_label = QLabel("Click on a shortcut field and press the desired key combination. "
                           "Clear the field to disable the shortcut.")
        info_label.setProperty("class", "description")
        info_label.setWordWrap(True)
        info_label.setContentsMargins(0, 16, 0, 0)
        layout.addWidget(info_label)

        layout.addStretch()
        return self._create_scrollable_page(page)

    def _browse_default_dir(self) -> None:
        """Open directory browser for default directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Directory",
            self.default_dir_edit.text() or ""
        )
        if directory:
            self.default_dir_edit.setText(directory)

    def _browse_model_path(self) -> None:
        """Open file browser for YOLO model."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Model",
            self.model_path_edit.text() or "",
            "YOLO Model (*.pt)"
        )
        if file_path:
            self.model_path_edit.setText(file_path)

    def load_settings(self) -> None:
        """Load current settings into the dialog."""
        config = self.config_manager.config

        self.default_dir_edit.setText(config.default_directory)
        self.model_path_edit.setText(config.yolo_model_path)
        self.line_thickness_spinbox.setValue(config.line_thickness)
        self.font_size_spinbox.setValue(config.font_size)
        self.thumbnail_size_spinbox.setValue(config.thumbnail_size)
        self.autosave_checkbox.setChecked(config.autosave)
        self.focus_on_select_checkbox.setChecked(config.focus_on_select)
        self.zoom_on_select_checkbox.setChecked(config.zoom_on_select)
        index = self.zoom_level_combo.findData(config.zoom_on_select_level)
        if index >= 0:
            self.zoom_level_combo.setCurrentIndex(index)
        self.auto_select_checkbox.setChecked(config.auto_select_on_point_click)
        if config.finish_drawing_key:
            self.finish_drawing_key_edit.setKeySequence(QKeySequence(config.finish_drawing_key))
        else:
            self.finish_drawing_key_edit.clear()
        if config.delete_shape_key:
            self.delete_shape_key_edit.setKeySequence(QKeySequence(config.delete_shape_key))
        else:
            self.delete_shape_key_edit.clear()

        # Format settings
        format_index = self.default_format_combo.findData(config.default_annotation_format)
        if format_index >= 0:
            self.default_format_combo.setCurrentIndex(format_index)
        self.auto_detect_format_checkbox.setChecked(config.auto_detect_format)

        # Rendering settings
        self.gpu_acceleration_checkbox.setChecked(config.gpu_acceleration)

    def _save_settings(self) -> None:
        """Save settings from dialog to configuration."""
        config = AppConfig(
            default_directory=self.default_dir_edit.text(),
            yolo_model_path=self.model_path_edit.text(),
            line_thickness=self.line_thickness_spinbox.value(),
            font_size=self.font_size_spinbox.value(),
            thumbnail_size=self.thumbnail_size_spinbox.value(),
            autosave=self.autosave_checkbox.isChecked(),
            focus_on_select=self.focus_on_select_checkbox.isChecked(),
            zoom_on_select=self.zoom_on_select_checkbox.isChecked(),
            zoom_on_select_level=self.zoom_level_combo.currentData(),
            auto_select_on_point_click=self.auto_select_checkbox.isChecked(),
            finish_drawing_key=self.finish_drawing_key_edit.keySequence().toString(),
            delete_shape_key=self.delete_shape_key_edit.keySequence().toString(),
            default_annotation_format=self.default_format_combo.currentData(),
            auto_detect_format=self.auto_detect_format_checkbox.isChecked(),
            gpu_acceleration=self.gpu_acceleration_checkbox.isChecked(),
        )

        self.config_manager.save(config)
        logger.info("Settings saved")
        self.accept()

    def get_config(self) -> AppConfig:
        """
        Get the current configuration from the dialog.

        Returns:
            AppConfig with current dialog values
        """
        return AppConfig(
            default_directory=self.default_dir_edit.text(),
            yolo_model_path=self.model_path_edit.text(),
            line_thickness=self.line_thickness_spinbox.value(),
            font_size=self.font_size_spinbox.value(),
            thumbnail_size=self.thumbnail_size_spinbox.value(),
            autosave=self.autosave_checkbox.isChecked(),
            focus_on_select=self.focus_on_select_checkbox.isChecked(),
            zoom_on_select=self.zoom_on_select_checkbox.isChecked(),
            zoom_on_select_level=self.zoom_level_combo.currentData(),
            auto_select_on_point_click=self.auto_select_checkbox.isChecked(),
            finish_drawing_key=self.finish_drawing_key_edit.keySequence().toString(),
            delete_shape_key=self.delete_shape_key_edit.keySequence().toString(),
            default_annotation_format=self.default_format_combo.currentData(),
            auto_detect_format=self.auto_detect_format_checkbox.isChecked(),
            gpu_acceleration=self.gpu_acceleration_checkbox.isChecked(),
        )
