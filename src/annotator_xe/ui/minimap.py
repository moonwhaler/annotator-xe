"""Minimap navigation widget for image annotation."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QSizeF, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QMouseEvent, QResizeEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy

logger = logging.getLogger(__name__)


class MiniatureView(QLabel):
    """
    Minimap widget for navigating large images.

    Displays a scaled-down view of the full image with a draggable
    viewport rectangle showing the currently visible area.

    The viewport is stored in normalized coordinates (0-1) relative to the image,
    making it independent of minimap size.
    """

    # Signal emitted when the viewport is dragged (normalized coordinates)
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
        self._normalized_view_rect = QRectF(0, 0, 1, 1)  # Normalized 0-1 coordinates
        self.dragging = False
        self.drag_start_pos = QPointF()
        self.drag_start_rect = QRectF()
        self.original_pixmap: Optional[QPixmap] = None
        self.image_size = QSizeF()

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
            self._update_scaled_pixmap()
        else:
            self.original_pixmap = None
            self.image_size = QSizeF()
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

        img_width = self.image_size.width()
        img_height = self.image_size.height()

        if img_width <= 0 or img_height <= 0:
            return

        # Calculate size that maintains aspect ratio
        img_aspect = img_width / img_height
        widget_aspect = available_width / available_height

        if img_aspect > widget_aspect:
            # Image is wider - fit to width
            scaled_width = available_width
            scaled_height = available_width / img_aspect
        else:
            # Image is taller - fit to height
            scaled_height = available_height
            scaled_width = available_height * img_aspect

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
                not self._scaled_image_rect.isEmpty()):

            painter = QPainter(self)

            # Convert normalized rect to widget coordinates
            draw_rect = QRectF(
                self._scaled_image_rect.x() + self._normalized_view_rect.x() * self._scaled_image_rect.width(),
                self._scaled_image_rect.y() + self._normalized_view_rect.y() * self._scaled_image_rect.height(),
                self._normalized_view_rect.width() * self._scaled_image_rect.width(),
                self._normalized_view_rect.height() * self._scaled_image_rect.height()
            )

            # Clip to the image bounds
            draw_rect = draw_rect.intersected(self._scaled_image_rect)

            # Draw semi-transparent overlay outside the viewport
            painter.setBrush(QBrush(Qt.GlobalColor.black))
            painter.setOpacity(0.3)
            painter.setPen(Qt.PenStyle.NoPen)

            # Draw darkened areas around the viewport
            img_rect = self._scaled_image_rect
            # Top
            if draw_rect.top() > img_rect.top():
                painter.drawRect(QRectF(img_rect.left(), img_rect.top(),
                                       img_rect.width(), draw_rect.top() - img_rect.top()))
            # Bottom
            if draw_rect.bottom() < img_rect.bottom():
                painter.drawRect(QRectF(img_rect.left(), draw_rect.bottom(),
                                       img_rect.width(), img_rect.bottom() - draw_rect.bottom()))
            # Left
            if draw_rect.left() > img_rect.left():
                painter.drawRect(QRectF(img_rect.left(), draw_rect.top(),
                                       draw_rect.left() - img_rect.left(), draw_rect.height()))
            # Right
            if draw_rect.right() < img_rect.right():
                painter.drawRect(QRectF(draw_rect.right(), draw_rect.top(),
                                       img_rect.right() - draw_rect.right(), draw_rect.height()))

            # Draw the viewport rectangle border
            painter.setOpacity(1.0)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(draw_rect)

    def _widget_to_normalized(self, pos: QPointF) -> QPointF:
        """Convert widget coordinates to normalized image coordinates (0-1)."""
        if self._scaled_image_rect.isEmpty():
            return QPointF(0, 0)

        # Convert to position relative to scaled image
        rel_x = (pos.x() - self._scaled_image_rect.x()) / self._scaled_image_rect.width()
        rel_y = (pos.y() - self._scaled_image_rect.y()) / self._scaled_image_rect.height()

        return QPointF(max(0, min(1, rel_x)), max(0, min(1, rel_y)))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for viewport dragging."""
        if self._scaled_image_rect.isEmpty():
            return

        click_pos = event.position()

        # Check if click is within the image area
        if not self._scaled_image_rect.contains(click_pos):
            return

        norm_pos = self._widget_to_normalized(click_pos)

        # Check if within viewport rect
        if self._normalized_view_rect.contains(norm_pos):
            self.dragging = True
            self.drag_start_pos = norm_pos
            self.drag_start_rect = QRectF(self._normalized_view_rect)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            # Click outside viewport - center viewport on click
            self._center_viewport_on(norm_pos)

    def _center_viewport_on(self, norm_pos: QPointF) -> None:
        """Center the viewport on the given normalized position."""
        new_x = norm_pos.x() - self._normalized_view_rect.width() / 2
        new_y = norm_pos.y() - self._normalized_view_rect.height() / 2

        # Clamp to valid range
        max_x = 1.0 - self._normalized_view_rect.width()
        max_y = 1.0 - self._normalized_view_rect.height()

        new_x = max(0, min(new_x, max(0, max_x)))
        new_y = max(0, min(new_y, max(0, max_y)))

        self._normalized_view_rect.moveTopLeft(QPointF(new_x, new_y))
        self.update()
        self.view_rect_changed.emit(self._normalized_view_rect)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for viewport dragging."""
        if not self.dragging or self._scaled_image_rect.isEmpty():
            return

        norm_pos = self._widget_to_normalized(event.position())
        delta = norm_pos - self.drag_start_pos

        new_rect = QRectF(self.drag_start_rect)
        new_rect.translate(delta)

        # Keep viewport within bounds (0-1)
        if new_rect.left() < 0:
            new_rect.moveLeft(0)
        if new_rect.top() < 0:
            new_rect.moveTop(0)
        if new_rect.right() > 1:
            new_rect.moveRight(1)
        if new_rect.bottom() > 1:
            new_rect.moveBottom(1)

        self._normalized_view_rect = new_rect
        self.update()
        self.view_rect_changed.emit(self._normalized_view_rect)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        self.dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_view_rect_normalized(self, rect: QRectF) -> None:
        """
        Set the viewport rectangle in normalized coordinates (0-1).

        Args:
            rect: The viewport rectangle with x, y, width, height all in range 0-1
        """
        self._normalized_view_rect = rect
        self.update()

    def get_view_rect_normalized(self) -> QRectF:
        """Get the viewport rectangle in normalized coordinates."""
        return self._normalized_view_rect

    def clear(self) -> None:
        """Clear the minimap display."""
        self.original_pixmap = None
        self.image_size = QSizeF()
        self._normalized_view_rect = QRectF(0, 0, 1, 1)
        self._scaled_image_rect = QRectF()
        super().setPixmap(QPixmap())
        self.update()
