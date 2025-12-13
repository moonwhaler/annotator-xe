"""YOLO model selector dialog for Annotator XE."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog
)

logger = logging.getLogger(__name__)


class ModelSelector(QDialog):
    """
    Dialog for selecting a YOLO model file.

    Provides a simple interface for browsing and selecting
    a .pt model file for object detection.
    """

    def __init__(self, parent=None) -> None:
        """Initialize the model selector dialog."""
        super().__init__(parent)
        self.model_path: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Select YOLO Model")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        self.path_label = QLabel("No model selected")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        select_button = QPushButton("Select Model")
        select_button.clicked.connect(self._select_model)
        layout.addWidget(select_button)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

        self.setLayout(layout)

    def _select_model(self) -> None:
        """Open file dialog to select a model file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Model",
            "",
            "PT files (*.pt)"
        )
        if file_path:
            self.model_path = file_path
            self.path_label.setText(f"Selected: {file_path}")
            logger.info(f"Model selected: {file_path}")

    def get_model_path(self) -> Optional[str]:
        """
        Get the selected model path.

        Returns:
            Path to the selected model file or None
        """
        return self.model_path

    def set_model_path(self, path: str) -> None:
        """
        Pre-set the model path.

        Args:
            path: Path to display as selected
        """
        self.model_path = path
        self.path_label.setText(f"Selected: {path}")
