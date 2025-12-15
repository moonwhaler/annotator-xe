"""History panel for displaying and navigating undo/redo history."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame
)
from PyQt6.QtGui import QFont, QColor

from .theme import get_theme_manager

if TYPE_CHECKING:
    from ..core.undo_redo import UndoRedoManager

logger = logging.getLogger(__name__)


class HistoryPanel(QWidget):
    """
    Panel displaying the undo/redo history with click navigation.

    Shows past actions (undo stack) above the current position
    and future actions (redo stack) below. Clicking an item
    navigates to that point in history.
    """

    # Emitted when user clicks to navigate history
    history_navigated = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the history panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._undo_manager: Optional[UndoRedoManager] = None
        self._updating = False  # Flag to prevent recursive updates
        self._navigating = False  # Flag to prevent clicks during navigation
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # History list
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.history_list)

        # Empty state label (shown when no history)
        self.empty_label = QLabel("No history")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        colors = get_theme_manager().colors
        self.empty_label.setStyleSheet(f"color: {colors.text_muted}; padding: 20px;")
        layout.addWidget(self.empty_label)

        self._apply_theme()
        get_theme_manager().register_callback(self._on_theme_changed)

    def _apply_theme(self) -> None:
        """Apply the current theme styling."""
        colors = get_theme_manager().colors
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {colors.background_secondary};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: {colors.hover};
            }}
            QListWidget::item:selected {{
                background-color: {colors.selected};
            }}
        """)
        self.empty_label.setStyleSheet(f"color: {colors.text_muted}; padding: 20px;")

    def _on_theme_changed(self) -> None:
        """Handle theme change."""
        self._apply_theme()

    def set_undo_manager(self, undo_manager: UndoRedoManager) -> None:
        """
        Connect to an undo/redo manager.

        Args:
            undo_manager: The undo/redo manager to track
        """
        if self._undo_manager:
            try:
                self._undo_manager.state_changed.disconnect(self._update_history)
            except (TypeError, RuntimeError):
                pass

        self._undo_manager = undo_manager
        self._undo_manager.state_changed.connect(self._update_history)
        self._update_history()

    def _update_history(self) -> None:
        """Update the history list from the undo manager."""
        if self._updating or not self._undo_manager:
            return

        self._updating = True
        try:
            self.history_list.clear()

            history = self._undo_manager.get_history()

            if not history:
                self.history_list.hide()
                self.empty_label.show()
                return

            self.empty_label.hide()
            self.history_list.show()

            colors = get_theme_manager().colors
            undo_count = self._undo_manager.undo_count
            redo_count = self._undo_manager.redo_count

            # Always add "Initial State" entry at the top when there's any history
            initial_item = QListWidgetItem("(Initial State)")
            initial_item.setData(Qt.ItemDataRole.UserRole, ("initial", None))
            if undo_count > 0:
                initial_item.setForeground(QColor(colors.text_muted))
                initial_item.setToolTip(f"Click to undo all {undo_count} step(s)")
            else:
                # We're at the initial state
                initial_item.setForeground(QColor(colors.text_primary))
                initial_item.setToolTip("Current state (initial)")
            self.history_list.addItem(initial_item)

            # Add items to the list
            for idx, description, is_undo_stack in history:
                item = QListWidgetItem(description)
                item.setData(Qt.ItemDataRole.UserRole, (idx, is_undo_stack))

                if is_undo_stack:
                    # Past actions - normal text
                    item.setForeground(QColor(colors.text_primary))
                    # Calculate steps to undo to reach this point
                    # idx 0 is oldest, undo_count-1 is newest
                    # To reach idx, we need to undo (undo_count - idx - 1) times
                    # But clicking means "go back to state after this command"
                    # So we need to undo (undo_count - idx - 1) steps
                    steps_back = undo_count - idx - 1
                    if steps_back > 0:
                        item.setToolTip(f"Click to undo {steps_back} step(s)")
                    else:
                        item.setToolTip("Current state")
                else:
                    # Future actions (in redo stack) - muted text
                    item.setForeground(QColor(colors.text_muted))
                    # Calculate steps to redo to reach this point
                    # Items are displayed in redo order (first to redo is shown first)
                    # idx is reversed: first item shown has highest idx, last has idx=0
                    # To redo to item with idx, we need (redo_count - idx) steps
                    steps_forward = redo_count - idx
                    item.setToolTip(f"Click to redo {steps_forward} step(s)")

                self.history_list.addItem(item)

            # Select the current position
            # Account for the "Initial State" entry at index 0
            if undo_count > 0:
                # Current position is after all undo items
                self.history_list.setCurrentRow(undo_count)  # +1 for initial state, -1 for 0-index = undo_count
            else:
                # We're at initial state, select it
                self.history_list.setCurrentRow(0)

        finally:
            self._updating = False

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle click on a history item.

        Args:
            item: The clicked list item
        """
        if self._updating or self._navigating or not self._undo_manager:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return

        idx, is_undo_stack = data
        undo_count = self._undo_manager.undo_count

        # Set navigating flag to prevent re-entry
        self._navigating = True
        try:
            # Handle "Initial State" entry
            if idx == "initial":
                if undo_count > 0:
                    self._undo_manager.undo_to(undo_count)
                    self.history_navigated.emit()
                return

            if is_undo_stack:
                # Clicked on an undo item - need to undo back to that point
                # Current position is at undo_count (after all undo items)
                # Item at idx means we want to go back to state after command at idx
                # That means we need to undo (undo_count - idx - 1) commands
                steps = undo_count - idx - 1
                if steps > 0:
                    self._undo_manager.undo_to(steps)
                    self.history_navigated.emit()
            else:
                # Clicked on a redo item - need to redo forward to that point
                # idx is reversed: first redo item has highest idx, last has idx=0
                # To redo to item with idx, we need (redo_count - idx) steps
                redo_count = self._undo_manager.redo_count
                steps = redo_count - idx
                if steps > 0:
                    self._undo_manager.redo_to(steps)
                    self.history_navigated.emit()
        finally:
            self._navigating = False

    def clear(self) -> None:
        """Clear the history display."""
        self.history_list.clear()
        self.history_list.hide()
        self.empty_label.show()
