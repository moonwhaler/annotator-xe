"""Minimap navigation widget for image annotation."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QSizeF, QPointF, pyqtSignal
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
        # Center the pixmap in the widget
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # State
        self.view_rect = QRectF()  # In minimap coordinates (relative to scaled image)
        self.dragging = False
        self.start_pos = QPointF()
        self.original_pixmap: Optional[QPixmap] = None
        self.image_size = QSizeF()
        self.aspect_ratio = 1.0

        # Track the actual scaled image bounds within the widget
        self._scaled_image_rect = QRectF()

    def setPixmap(self, pixmap: QPixmap) -> None:
        """
        Set the image pixmap for the minimap.

        Args:
            pixmap: The image to display
        """
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            self.image_size = QSizeF(pixmap.size())
            self.aspect_ratio = self.image_size.width() / self.image_size.height()
            self._update_scaled_pixmap()
        else:
            logger.debug("Setting empty pixmap in MiniatureView")
            self.original_pixmap = None
            self.image_size = QSizeF()
            self.aspect_ratio = 1.0
            self._scaled_image_rect = QRectF()
            super().setPixmap(QPixmap())

    def _update_scaled_pixmap(self) -> None:
        """Update the displayed pixmap to fit the widget size."""
        if not self.original_pixmap or self.original_pixmap.isNull():
            super().setPixmap(QPixmap())
            self._scaled_image_rect = QRectF()
            return

        available_width = self.width()
        available_height = self.height()

        if available_width <= 0 or available_height <= 0:
            return

        # Calculate size that maintains aspect ratio
        scaled_width = available_width
        scaled_height = scaled_width / self.aspect_ratio

        if scaled_height > available_height:
            scaled_height = available_height
            scaled_width = scaled_height * self.aspect_ratio

        # Calculate the offset for centering
        offset_x = (available_width - scaled_width) / 2
        offset_y = (available_height - scaled_height) / 2

        # Store the actual image bounds within the widget
        self._scaled_image_rect = QRectF(offset_x, offset_y, scaled_width, scaled_height)

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

    def paintEvent(self, event) -> None:
        """Paint the minimap with viewport rectangle."""
        super().paintEvent(event)

        if (self.pixmap() and not self.pixmap().isNull() and
                not self.view_rect.isEmpty() and not self._scaled_image_rect.isEmpty()):
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))

            # The view_rect is in scaled image coordinates, translate to widget coordinates
            draw_rect = QRectF(
                self._scaled_image_rect.x() + self.view_rect.x(),
                self._scaled_image_rect.y() + self.view_rect.y(),
                self.view_rect.width(),
                self.view_rect.height()
            )

            # Clip to the image bounds
            draw_rect = draw_rect.intersected(self._scaled_image_rect)

            painter.drawRect(draw_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for viewport dragging."""
        # Convert click position to image-relative coordinates
        click_pos = event.position()

        # Check if click is within the image area
        if self._scaled_image_rect.contains(click_pos):
            # Translate to image-relative coordinates
            image_pos = QPointF(
                click_pos.x() - self._scaled_image_rect.x(),
                click_pos.y() - self._scaled_image_rect.y()
            )

            # Check if within viewport rect
            if self.view_rect.contains(image_pos):
                self.dragging = True
                self.start_pos = image_pos
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                # Click outside viewport but inside image - center viewport on click
                self._center_viewport_on(image_pos)

    def _center_viewport_on(self, pos: QPointF) -> None:
        """Center the viewport on the given position (in image coordinates)."""
        if self._scaled_image_rect.isEmpty():
            return

        new_x = pos.x() - self.view_rect.width() / 2
        new_y = pos.y() - self.view_rect.height() / 2

        # Clamp to image bounds
        max_x = self._scaled_image_rect.width() - self.view_rect.width()
        max_y = self._scaled_image_rect.height() - self.view_rect.height()

        new_x = max(0, min(new_x, max_x))
        new_y = max(0, min(new_y, max_y))

        self.view_rect.moveTopLeft(QPointF(new_x, new_y))
        self.update()
        self.view_rect_changed.emit(self.view_rect)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for viewport dragging."""
        if not self.dragging or self._scaled_image_rect.isEmpty():
            return

        # Convert to image-relative coordinates
        image_pos = QPointF(
            event.position().x() - self._scaled_image_rect.x(),
            event.position().y() - self._scaled_image_rect.y()
        )

        delta = image_pos - self.start_pos
        new_rect = self.view_rect.translated(delta)

        # Keep viewport within image bounds
        if new_rect.left() < 0:
            new_rect.moveLeft(0)
        if new_rect.top() < 0:
            new_rect.moveTop(0)
        if new_rect.right() > self._scaled_image_rect.width():
            new_rect.moveRight(self._scaled_image_rect.width())
        if new_rect.bottom() > self._scaled_image_rect.height():
            new_rect.moveBottom(self._scaled_image_rect.height())

        self.view_rect = new_rect
        self.start_pos = image_pos
        self.update()
        self.view_rect_changed.emit(self.view_rect)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        self.dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_view_rect(self, rect: QRectF) -> None:
        """
        Set the viewport rectangle position (in scaled image coordinates).

        Args:
            rect: The new viewport rectangle
        """
        self.view_rect = rect
        self.update()

    def get_scaled_image_rect(self) -> QRectF:
        """Get the bounds of the scaled image within the widget."""
        return self._scaled_image_rect

    def get_scale_factors(self) -> tuple[float, float]:
        """
        Get the scale factors from original image to minimap image.

        Returns:
            Tuple of (scale_x, scale_y)
        """
        if self.image_size.isEmpty() or self._scaled_image_rect.isEmpty():
            return (1.0, 1.0)

        scale_x = self._scaled_image_rect.width() / self.image_size.width()
        scale_y = self._scaled_image_rect.height() / self.image_size.height()
        return (scale_x, scale_y)

    def clear(self) -> None:
        """Clear the minimap display."""
        self.original_pixmap = None
        self.image_size = QSizeF()
        self.view_rect = QRectF()
        self._scaled_image_rect = QRectF()
        super().setPixmap(QPixmap())
        self.update()
