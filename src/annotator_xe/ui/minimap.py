"""Minimap navigation widget for image annotation."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QSizeF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QMouseEvent, QResizeEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy

logger = logging.getLogger(__name__)


class MiniatureView(QLabel):
    """
    Minimap widget for navigating large images.

    Displays a scaled-down view of the full image with a draggable
    viewport rectangle showing the currently visible area.
    """

    # Signal emitted when the viewport is dragged
    view_rect_changed = pyqtSignal(QRectF)

    def __init__(self, parent: Optional[QLabel] = None) -> None:
        """Initialize the miniature view."""
        super().__init__(parent)

        self.setMinimumSize(100, 100)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # State
        self.view_rect = QRectF()
        self.dragging = False
        self.start_pos = QRectF()
        self.original_pixmap: Optional[QPixmap] = None
        self.image_size = QSizeF()
        self.aspect_ratio = 1.0

    def setPixmap(self, pixmap: QPixmap) -> None:
        """
        Set the image pixmap for the minimap.

        Args:
            pixmap: The image to display
        """
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            self.image_size = pixmap.size()
            self.aspect_ratio = self.image_size.width() / self.image_size.height()
            self._update_scaled_pixmap()
        else:
            logger.debug("Setting empty pixmap in MiniatureView")
            self.original_pixmap = None
            self.image_size = QSizeF()
            self.aspect_ratio = 1.0
            super().setPixmap(QPixmap())

    def _update_scaled_pixmap(self) -> None:
        """Update the displayed pixmap to fit the widget size."""
        if not self.original_pixmap or self.original_pixmap.isNull():
            super().setPixmap(QPixmap())
            return

        available_width = self.width()
        available_height = self.height()

        # Calculate size that maintains aspect ratio
        scaled_width = available_width
        scaled_height = scaled_width / self.aspect_ratio

        if scaled_height > available_height:
            scaled_height = available_height
            scaled_width = scaled_height * self.aspect_ratio

        scaled_pixmap = self.original_pixmap.scaled(
            int(scaled_width),
            int(scaled_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle widget resize."""
        super().resizeEvent(event)
        self._update_scaled_pixmap()
        # Maintain square-ish proportions
        self.setMinimumHeight(self.width())

    def paintEvent(self, event) -> None:
        """Paint the minimap with viewport rectangle."""
        super().paintEvent(event)

        if self.pixmap() and not self.pixmap().isNull():
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.drawRect(self.view_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for viewport dragging."""
        if self.view_rect.contains(event.position()):
            self.dragging = True
            self.start_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for viewport dragging."""
        if not self.dragging:
            return

        delta = event.position() - self.start_pos
        new_rect = self.view_rect.translated(delta)

        # Keep viewport within bounds
        if new_rect.left() < 0:
            new_rect.moveLeft(0)
        if new_rect.top() < 0:
            new_rect.moveTop(0)
        if new_rect.right() > self.width():
            new_rect.moveRight(self.width())
        if new_rect.bottom() > self.height():
            new_rect.moveBottom(self.height())

        self.view_rect = new_rect
        self.start_pos = event.position()
        self.update()
        self.view_rect_changed.emit(self.view_rect)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        self.dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_view_rect(self, rect: QRectF) -> None:
        """
        Set the viewport rectangle position.

        Args:
            rect: The new viewport rectangle
        """
        self.view_rect = rect
        self.update()

    def clear(self) -> None:
        """Clear the minimap display."""
        self.original_pixmap = None
        self.image_size = QSizeF()
        self.view_rect = QRectF()
        super().setPixmap(QPixmap())
        self.update()
