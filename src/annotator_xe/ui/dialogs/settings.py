"""Settings dialog for Annotator XE."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLineEdit, QPushButton, QSpinBox, QCheckBox, QDialogButtonBox,
    QFileDialog, QComboBox
)

from ...core.config import AppConfig, ConfigManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Settings dialog for configuring application preferences.

    Provides tabs for General, YOLO, and UI settings.
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
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout(self)

        # Tab widget
        tab_widget = QTabWidget()
        tab_widget.addTab(self._create_general_tab(), "General")
        tab_widget.addTab(self._create_yolo_tab(), "YOLO")
        tab_widget.addTab(self._create_ui_tab(), "UI")
        layout.addWidget(tab_widget)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QFormLayout()

        self.default_dir_edit = QLineEdit()
        layout.addRow("Default Directory:", self.default_dir_edit)

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_default_dir)
        layout.addRow("", browse_button)

        self.autosave_checkbox = QCheckBox("Autosave YOLO files")
        layout.addRow("", self.autosave_checkbox)

        widget.setLayout(layout)
        return widget

    def _create_yolo_tab(self) -> QWidget:
        """Create the YOLO settings tab."""
        widget = QWidget()
        layout = QFormLayout()

        self.model_path_edit = QLineEdit()
        layout.addRow("Default YOLO Model:", self.model_path_edit)

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_model_path)
        layout.addRow("", browse_button)

        widget.setLayout(layout)
        return widget

    def _create_ui_tab(self) -> QWidget:
        """Create the UI settings tab."""
        widget = QWidget()
        layout = QFormLayout()

        self.line_thickness_spinbox = QSpinBox()
        self.line_thickness_spinbox.setRange(1, 10)
        layout.addRow("Line Thickness:", self.line_thickness_spinbox)

        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(6, 24)
        layout.addRow("Font Size:", self.font_size_spinbox)

        self.focus_on_select_checkbox = QCheckBox("Focus viewport on selected shape")
        layout.addRow("", self.focus_on_select_checkbox)

        self.zoom_on_select_checkbox = QCheckBox("Zoom to shape on select")
        layout.addRow("", self.zoom_on_select_checkbox)

        self.zoom_level_combo = QComboBox()
        self.zoom_level_combo.addItem("Fit to viewport", "fit")
        self.zoom_level_combo.addItem("Close (1.5x)", "close")
        self.zoom_level_combo.addItem("Closer (2x)", "closer")
        self.zoom_level_combo.addItem("Detail (3x)", "detail")
        layout.addRow("Zoom level:", self.zoom_level_combo)

        self.auto_select_checkbox = QCheckBox("Auto-switch to select mode on point click")
        layout.addRow("", self.auto_select_checkbox)

        widget.setLayout(layout)
        return widget

    def _browse_default_dir(self) -> None:
        """Open directory browser for default directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Directory"
        )
        if directory:
            self.default_dir_edit.setText(directory)

    def _browse_model_path(self) -> None:
        """Open file browser for YOLO model."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Model",
            "",
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
        self.autosave_checkbox.setChecked(config.autosave)
        self.focus_on_select_checkbox.setChecked(config.focus_on_select)
        self.zoom_on_select_checkbox.setChecked(config.zoom_on_select)
        index = self.zoom_level_combo.findData(config.zoom_on_select_level)
        if index >= 0:
            self.zoom_level_combo.setCurrentIndex(index)
        self.auto_select_checkbox.setChecked(config.auto_select_on_point_click)

    def _save_settings(self) -> None:
        """Save settings from dialog to configuration."""
        config = AppConfig(
            default_directory=self.default_dir_edit.text(),
            yolo_model_path=self.model_path_edit.text(),
            line_thickness=self.line_thickness_spinbox.value(),
            font_size=self.font_size_spinbox.value(),
            autosave=self.autosave_checkbox.isChecked(),
            focus_on_select=self.focus_on_select_checkbox.isChecked(),
            zoom_on_select=self.zoom_on_select_checkbox.isChecked(),
            zoom_on_select_level=self.zoom_level_combo.currentData(),
            auto_select_on_point_click=self.auto_select_checkbox.isChecked()
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
            autosave=self.autosave_checkbox.isChecked(),
            focus_on_select=self.focus_on_select_checkbox.isChecked(),
            zoom_on_select=self.zoom_on_select_checkbox.isChecked(),
            zoom_on_select_level=self.zoom_level_combo.currentData(),
            auto_select_on_point_click=self.auto_select_checkbox.isChecked()
        )
