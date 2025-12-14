"""Format choice dialog for when multiple annotation formats are detected."""

from __future__ import annotations

import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt

from annotator_xe.core.format_registry import FormatRegistry
from ..theme import get_theme_manager

logger = logging.getLogger(__name__)


class FormatChoiceDialog(QDialog):
    """
    Dialog for selecting an annotation format when multiple are detected.

    Presents the user with radio button options for each detected format
    and allows them to choose which one to use.
    """

    def __init__(
        self,
        formats: List[str],
        directory_name: str,
        parent=None
    ) -> None:
        """
        Initialize the format choice dialog.

        Args:
            formats: List of detected format names
            directory_name: Name of the directory being opened (for display)
            parent: Parent widget
        """
        super().__init__(parent)
        self.formats = formats
        self.directory_name = directory_name
        self.selected_format: Optional[str] = formats[0] if formats else None
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Multiple Formats Detected")
        self.setMinimumWidth(450)
        self.setModal(True)

        # Apply theme
        self.setStyleSheet(get_theme_manager().get_dialog_stylesheet())

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Header message
        header = QLabel(
            f"Multiple annotation formats were detected in:\n"
            f"<b>{self.directory_name}</b>\n\n"
            f"Please select which format to use:"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setWordWrap(True)
        layout.addWidget(header)

        # Radio buttons for each format
        self.button_group = QButtonGroup(self)

        for i, format_name in enumerate(self.formats):
            display_name = FormatRegistry.get_display_name(format_name)
            description = FormatRegistry.get_description(format_name)

            radio = QRadioButton(f"{display_name}")
            radio.setToolTip(description)

            if i == 0:
                radio.setChecked(True)

            self.button_group.addButton(radio, i)

            # Create a layout with radio and description
            format_layout = QVBoxLayout()
            format_layout.setContentsMargins(0, 0, 0, 8)
            format_layout.addWidget(radio)

            desc_label = QLabel(f"    <i>{description}</i>")
            desc_label.setTextFormat(Qt.TextFormat.RichText)
            desc_label.setProperty("class", "description")
            format_layout.addWidget(desc_label)

            layout.addLayout(format_layout)

        self.button_group.buttonClicked.connect(self._on_format_selected)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _on_format_selected(self, button: QRadioButton) -> None:
        """Handle format selection."""
        index = self.button_group.id(button)
        if 0 <= index < len(self.formats):
            self.selected_format = self.formats[index]
            logger.debug(f"Format selected: {self.selected_format}")

    def get_selected_format(self) -> Optional[str]:
        """
        Get the selected format.

        Returns:
            The selected format name, or None if cancelled
        """
        return self.selected_format
