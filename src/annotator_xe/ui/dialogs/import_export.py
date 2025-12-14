"""Import and Export dialogs for annotation formats."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt

from annotator_xe.core.format_registry import FormatRegistry
from annotator_xe.core.models import Shape, ShapeType
from ..theme import get_theme_manager

logger = logging.getLogger(__name__)


class ImportAnnotationsDialog(QDialog):
    """
    Dialog for importing annotations from various formats.

    Allows users to:
    - Select a source file or directory
    - Auto-detect or manually select the format
    - Choose import mode (replace or merge)
    - Preview what will be imported
    """

    def __init__(
        self,
        current_directory: Optional[str] = None,
        parent=None
    ) -> None:
        """
        Initialize the import dialog.

        Args:
            current_directory: Current working directory (for relative paths)
            parent: Parent widget
        """
        super().__init__(parent)
        self.current_directory = current_directory
        self.source_path: Optional[Path] = None
        self.detected_format: Optional[str] = None
        self.selected_format: Optional[str] = None
        self.import_mode: str = "replace"
        self._preview_data: Dict[str, List[Shape]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Import Annotations")
        self.setMinimumWidth(550)
        self.setModal(True)

        # Apply theme
        self.setStyleSheet(get_theme_manager().get_dialog_stylesheet())

        layout = QVBoxLayout()
        layout.setSpacing(16)

        # === Source Selection ===
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout()

        # Path input with browse button
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select a file or directory...")
        self.path_input.textChanged.connect(self._on_path_changed)
        path_layout.addWidget(self.path_input)

        browse_file_btn = QPushButton("File...")
        browse_file_btn.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_file_btn)

        browse_dir_btn = QPushButton("Directory...")
        browse_dir_btn.clicked.connect(self._browse_directory)
        path_layout.addWidget(browse_dir_btn)

        source_layout.addLayout(path_layout)
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # === Format Selection ===
        format_group = QGroupBox("Format")
        format_layout = QHBoxLayout()

        format_layout.addWidget(QLabel("Detected:"))
        self.detected_label = QLabel("—")
        self.detected_label.setStyleSheet("font-weight: bold;")
        format_layout.addWidget(self.detected_label)

        format_layout.addSpacing(20)

        format_layout.addWidget(QLabel("Use:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("Auto-detect", None)
        for fmt in FormatRegistry.get_format_names():
            display_name = FormatRegistry.get_display_name(fmt)
            self.format_combo.addItem(display_name, fmt)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)

        format_layout.addStretch()
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # === Import Mode ===
        mode_group = QGroupBox("Import Mode")
        mode_layout = QVBoxLayout()

        self.mode_button_group = QButtonGroup(self)

        self.replace_radio = QRadioButton("Replace existing annotations")
        self.replace_radio.setChecked(True)
        self.replace_radio.setToolTip(
            "Remove existing annotations and import new ones"
        )
        self.mode_button_group.addButton(self.replace_radio)
        mode_layout.addWidget(self.replace_radio)

        self.merge_radio = QRadioButton("Merge with existing annotations")
        self.merge_radio.setToolTip(
            "Keep existing annotations and add imported ones"
        )
        self.mode_button_group.addButton(self.merge_radio)
        mode_layout.addWidget(self.merge_radio)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # === Preview ===
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("Select a source to see preview...")
        self.preview_label.setStyleSheet("color: gray;")
        preview_layout.addWidget(self.preview_label)

        # Format compatibility warning
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: orange;")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        preview_layout.addWidget(self.warning_label)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # === Buttons ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.import_btn = QPushButton("Import")
        self.import_btn.setEnabled(False)
        self.import_btn.setDefault(True)
        self.import_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.import_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _browse_file(self) -> None:
        """Open file browser for JSON files (COCO/CreateML)."""
        start_dir = self.current_directory or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Annotation File",
            start_dir,
            "JSON Files (*.json);;XML Files (*.xml);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def _browse_directory(self) -> None:
        """Open directory browser."""
        start_dir = self.current_directory or ""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Annotations Directory",
            start_dir
        )
        if dir_path:
            self.path_input.setText(dir_path)

    def _on_path_changed(self, path: str) -> None:
        """Handle path input change."""
        self.source_path = Path(path) if path else None
        self._detect_format()
        self._update_preview()

    def _on_format_changed(self, index: int) -> None:
        """Handle format selection change."""
        self.selected_format = self.format_combo.currentData()
        self._update_preview()

    def _detect_format(self) -> None:
        """Detect format from the selected source."""
        self.detected_format = None

        if not self.source_path or not self.source_path.exists():
            self.detected_label.setText("—")
            return

        if self.source_path.is_dir():
            # Use directory detection
            formats = FormatRegistry.detect_all_formats(self.source_path)
            if formats:
                self.detected_format = formats[0]
                if len(formats) > 1:
                    names = [FormatRegistry.get_display_name(f) for f in formats]
                    self.detected_label.setText(f"{names[0]} (+ {len(formats)-1} more)")
                else:
                    self.detected_label.setText(
                        FormatRegistry.get_display_name(self.detected_format)
                    )
            else:
                self.detected_label.setText("Unknown")
        else:
            # File-based detection
            self._detect_format_from_file()

    def _detect_format_from_file(self) -> None:
        """Detect format from a single file."""
        if not self.source_path:
            return

        suffix = self.source_path.suffix.lower()

        if suffix == ".json":
            # Could be COCO or CreateML - need to peek inside
            try:
                import json
                with open(self.source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    # CreateML format (array of image entries)
                    if len(data) > 0 and isinstance(data[0], dict) and "image" in data[0]:
                        self.detected_format = "createml"
                elif isinstance(data, dict):
                    # COCO format (object with images/annotations/categories)
                    if "images" in data or "annotations" in data or "categories" in data:
                        self.detected_format = "coco"
            except Exception:
                pass
        elif suffix == ".xml":
            self.detected_format = "pascal_voc"
        elif suffix == ".txt":
            self.detected_format = "yolo"

        if self.detected_format:
            self.detected_label.setText(
                FormatRegistry.get_display_name(self.detected_format)
            )
        else:
            self.detected_label.setText("Unknown")

    def _update_preview(self) -> None:
        """Update the preview section."""
        self._preview_data.clear()
        self.warning_label.hide()

        effective_format = self.selected_format or self.detected_format

        if not self.source_path or not self.source_path.exists():
            self.preview_label.setText("Select a source to see preview...")
            self.preview_label.setStyleSheet("color: gray;")
            self.import_btn.setEnabled(False)
            return

        if not effective_format:
            self.preview_label.setText("Unable to detect format. Please select manually.")
            self.preview_label.setStyleSheet("color: red;")
            self.import_btn.setEnabled(False)
            return

        try:
            handler = FormatRegistry.get_handler(effective_format)

            if self.source_path.is_dir():
                # Load from directory
                self._preview_data = handler.load_directory(self.source_path)
            else:
                # Load from single file - need special handling
                self._preview_data = self._load_from_file(effective_format)

            # Count stats
            image_count = len(self._preview_data)
            annotation_count = sum(len(shapes) for shapes in self._preview_data.values())

            # Count polygons vs boxes
            polygon_count = 0
            box_count = 0
            for shapes in self._preview_data.values():
                for shape in shapes:
                    if shape.type == ShapeType.POLYGON:
                        polygon_count += 1
                    else:
                        box_count += 1

            preview_text = (
                f"<b>{image_count}</b> images with "
                f"<b>{annotation_count}</b> annotations"
            )
            if polygon_count > 0 and box_count > 0:
                preview_text += f" ({box_count} boxes, {polygon_count} polygons)"
            elif polygon_count > 0:
                preview_text += f" ({polygon_count} polygons)"
            elif box_count > 0:
                preview_text += f" ({box_count} boxes)"

            self.preview_label.setText(preview_text)
            self.preview_label.setStyleSheet("color: green;")
            self.import_btn.setEnabled(image_count > 0)

        except Exception as e:
            self.preview_label.setText(f"Error reading source: {e}")
            self.preview_label.setStyleSheet("color: red;")
            self.import_btn.setEnabled(False)
            logger.exception("Error loading preview")

    def _load_from_file(self, format_name: str) -> Dict[str, List[Shape]]:
        """Load annotations from a single file."""
        handler = FormatRegistry.get_handler(format_name)

        if format_name in ("coco", "createml"):
            # These formats store all annotations in a single JSON file
            # We can load directly using the handler's internal method
            return handler.load_directory(self.source_path.parent, self.source_path.name)

        # For per-image formats, we'd need the directory
        return {}

    def get_import_settings(self) -> Tuple[Path, str, str, Dict[str, List[Shape]]]:
        """
        Get the import settings selected by the user.

        Returns:
            Tuple of (source_path, format_name, import_mode, preview_data)
        """
        effective_format = self.selected_format or self.detected_format
        mode = "merge" if self.merge_radio.isChecked() else "replace"
        return self.source_path, effective_format, mode, self._preview_data


class ExportAnnotationsDialog(QDialog):
    """
    Dialog for exporting annotations to various formats.

    Allows users to:
    - Select target format
    - Choose scope (current image or all images)
    - Select target location
    - See compatibility warnings
    """

    def __init__(
        self,
        current_directory: Optional[str] = None,
        current_format: str = "yolo",
        current_image: Optional[str] = None,
        total_images: int = 0,
        has_polygons: bool = False,
        parent=None
    ) -> None:
        """
        Initialize the export dialog.

        Args:
            current_directory: Current working directory
            current_format: Currently active format
            current_image: Currently selected image name
            total_images: Total number of images in directory
            has_polygons: Whether any annotations contain polygons
            parent: Parent widget
        """
        super().__init__(parent)
        self.current_directory = current_directory
        self.current_format = current_format
        self.current_image = current_image
        self.total_images = total_images
        self.has_polygons = has_polygons
        self.target_path: Optional[Path] = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Export Annotations")
        self.setMinimumWidth(500)
        self.setModal(True)

        # Apply theme
        self.setStyleSheet(get_theme_manager().get_dialog_stylesheet())

        layout = QVBoxLayout()
        layout.setSpacing(16)

        # === Format Selection ===
        format_group = QGroupBox("Target Format")
        format_layout = QVBoxLayout()

        self.format_combo = QComboBox()
        for fmt in FormatRegistry.get_format_names():
            display_name = FormatRegistry.get_display_name(fmt)
            description = FormatRegistry.get_description(fmt)
            self.format_combo.addItem(f"{display_name} - {description}", fmt)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)

        # Format info
        self.format_info_label = QLabel("")
        self.format_info_label.setStyleSheet("color: gray; font-size: 11px;")
        self.format_info_label.setWordWrap(True)
        format_layout.addWidget(self.format_info_label)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # === Scope Selection ===
        scope_group = QGroupBox("Scope")
        scope_layout = QVBoxLayout()

        self.scope_button_group = QButtonGroup(self)

        self.all_radio = QRadioButton(f"All images ({self.total_images} images)")
        self.all_radio.setChecked(True)
        self.scope_button_group.addButton(self.all_radio)
        scope_layout.addWidget(self.all_radio)

        current_label = f"Current image only ({self.current_image})" if self.current_image else "Current image only"
        self.current_radio = QRadioButton(current_label)
        self.current_radio.setEnabled(self.current_image is not None)
        self.scope_button_group.addButton(self.current_radio)
        scope_layout.addWidget(self.current_radio)

        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)

        # === Target Location ===
        target_group = QGroupBox("Target Location")
        target_layout = QVBoxLayout()

        # Same directory option
        self.same_dir_radio = QRadioButton("Same directory (alongside existing files)")
        self.same_dir_radio.setChecked(True)
        target_layout.addWidget(self.same_dir_radio)

        # Different directory option
        diff_dir_layout = QHBoxLayout()
        self.diff_dir_radio = QRadioButton("Different directory:")
        diff_dir_layout.addWidget(self.diff_dir_radio)

        self.target_input = QLineEdit()
        self.target_input.setEnabled(False)
        self.target_input.setPlaceholderText("Select target directory...")
        diff_dir_layout.addWidget(self.target_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_target)
        diff_dir_layout.addWidget(browse_btn)

        target_layout.addLayout(diff_dir_layout)

        self.same_dir_radio.toggled.connect(
            lambda checked: self.target_input.setEnabled(not checked)
        )

        target_group.setLayout(target_layout)
        layout.addWidget(target_group)

        # === Warnings ===
        self.warning_frame = QFrame()
        self.warning_frame.setStyleSheet(
            "QFrame { background-color: #fff3cd; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 8px; }"
        )
        warning_layout = QVBoxLayout()
        warning_layout.setContentsMargins(8, 8, 8, 8)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #856404;")
        self.warning_label.setWordWrap(True)
        warning_layout.addWidget(self.warning_label)

        self.warning_frame.setLayout(warning_layout)
        self.warning_frame.hide()
        layout.addWidget(self.warning_frame)

        # === Buttons ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton("Export")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.export_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Initial update
        self._on_format_changed(0)

    def _browse_target(self) -> None:
        """Open directory browser for target location."""
        start_dir = self.current_directory or ""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Target Directory",
            start_dir
        )
        if dir_path:
            self.target_input.setText(dir_path)
            self.diff_dir_radio.setChecked(True)

    def _on_format_changed(self, index: int) -> None:
        """Handle format selection change."""
        fmt = self.format_combo.currentData()
        if not fmt:
            return

        # Update format info
        supports_polygons = FormatRegistry.format_supports_polygons(fmt)
        is_per_image = FormatRegistry.is_per_image_format(fmt)

        info_parts = []
        if is_per_image:
            info_parts.append("Creates one file per image")
        else:
            info_parts.append("Creates a single file for all images")

        if supports_polygons:
            info_parts.append("Supports polygons")
        else:
            info_parts.append("Boxes only (polygons will be converted)")

        self.format_info_label.setText(" | ".join(info_parts))

        # Show warning if format doesn't support polygons but we have some
        if self.has_polygons and not supports_polygons:
            self.warning_label.setText(
                "Warning: Your annotations contain polygons, but the selected format "
                "only supports bounding boxes. Polygons will be converted to their "
                "bounding rectangles."
            )
            self.warning_frame.show()
        else:
            self.warning_frame.hide()

    def get_export_settings(self) -> Tuple[str, str, Path]:
        """
        Get the export settings selected by the user.

        Returns:
            Tuple of (format_name, scope, target_directory)
        """
        fmt = self.format_combo.currentData()
        scope = "current" if self.current_radio.isChecked() else "all"

        if self.same_dir_radio.isChecked():
            target = Path(self.current_directory) if self.current_directory else Path(".")
        else:
            target = Path(self.target_input.text()) if self.target_input.text() else Path(".")

        return fmt, scope, target
