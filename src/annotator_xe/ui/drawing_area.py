"""Drawing area canvas widget for image annotation."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QPolygonF,
    QPixmap, QFontMetrics, QMouseEvent, QKeyEvent, QWheelEvent
)
from PyQt6.QtWidgets import QLabel, QMenu, QInputDialog, QScrollArea

from ..core.models import Shape, ShapeType
from ..core.undo_redo import (
    UndoRedoManager, AddShapeCommand, DeleteShapeCommand,
    MoveShapeCommand, MovePointCommand, ChangeLabelCommand, DeletePointsCommand
)

logger = logging.getLogger(__name__)


class DrawingArea(QLabel):
    """
    Main canvas widget for drawing and editing annotations.

    Supports drawing bounding boxes and polygons, with zoom/pan functionality
    and interactive editing of shapes and points.
    """

    # Signals
    view_changed = pyqtSignal(QRect)
    zoom_changed = pyqtSignal(float)
    classification_changed = pyqtSignal(str)
    shapes_changed = pyqtSignal()
    points_deleted = pyqtSignal()
    shape_created = pyqtSignal()

    # Constants
    MIN_ZOOM = 0.2
    MAX_ZOOM = 5.0
    ZOOM_FACTOR = 1.1
    POINT_DETECTION_RADIUS = 10
    EDGE_DETECTION_RADIUS = 5

    def __init__(self, parent: Optional[QLabel] = None) -> None:
        """Initialize the drawing area."""
        super().__init__(parent)

        # Visual settings
        self.scale_factor = 1.0
        self.box_color = QColor("#FF0000")
        self.polygon_color = QColor("#00FF00")
        self.line_thickness = 2
        self.font_size = 10

        # Undo/Redo manager
        self.undo_manager = UndoRedoManager()

        # Initialize state
        self._init_state()

    def _init_state(self) -> None:
        """Initialize/reset drawing state."""
        self.drawing = False
        self.selecting = False
        self.moving = False
        self.resizing = False
        self.start_point = QPointF()

        self.current_tool: Optional[str] = None
        self.shapes: List[Shape] = []
        self.current_shape: Optional[Shape] = None
        self.selected_shape: Optional[Shape] = None
        self.selected_point: Optional[QPointF] = None
        self.resize_handle: Optional[Tuple[Shape, str]] = None

        self.hovered_point: Optional[Tuple[Shape, int]] = None
        self.moving_point: Optional[QPointF] = None
        self.moving_shape = False
        self.move_start_point = QPointF()

        self.scaled_pixmap: Optional[QPixmap] = None
        self.hover_point: Optional[Tuple[Shape, int]] = None
        self.hover_edge: Optional[Tuple[Shape, int]] = None
        self.hover_shape: Optional[Shape] = None

        self.panning = False
        self.pan_start = QPoint()
        self.scroll_area: Optional[QScrollArea] = None
        self.selected_points: List[Tuple[Shape, int]] = []

        # Undo tracking state
        self._move_start_points: Optional[List[QPointF]] = None
        self._point_move_start: Optional[QPointF] = None
        self._point_move_index: Optional[int] = None

        # Widget setup
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_scroll_area(self, scroll_area: QScrollArea) -> None:
        """Set the parent scroll area for pan support."""
        self.scroll_area = scroll_area

    def set_scale_factor(self, factor: float) -> None:
        """
        Set the zoom scale factor.

        Args:
            factor: Scale factor (0.2 to 5.0)
        """
        self.scale_factor = max(min(factor, self.MAX_ZOOM), self.MIN_ZOOM)
        self._update_scaled_pixmap()
        self.update()
        self.zoom_changed.emit(self.scale_factor)
        self.view_changed.emit(self.rect())

    def _update_scaled_pixmap(self) -> None:
        """Update the scaled pixmap based on current scale factor."""
        if self.pixmap() and not self.pixmap().isNull():
            self.scaled_pixmap = self.pixmap().scaled(
                self.pixmap().size() * self.scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setFixedSize(self.scaled_pixmap.size())

    # === Event Handlers ===

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            zoom_factor = self.ZOOM_FACTOR if delta > 0 else 1 / self.ZOOM_FACTOR

            cursor_pos = event.position()
            relative_pos = QPointF(
                cursor_pos.x() / self.width(),
                cursor_pos.y() / self.height()
            )

            new_scale = self.scale_factor * zoom_factor
            self.set_scale_factor(new_scale)

            if self.scroll_area:
                viewport_size = self.scroll_area.viewport().size()
                new_scroll_x = int(cursor_pos.x() * zoom_factor - viewport_size.width() * relative_pos.x())
                new_scroll_y = int(cursor_pos.y() * zoom_factor - viewport_size.height() * relative_pos.y())

                self.scroll_area.horizontalScrollBar().setValue(new_scroll_x)
                self.scroll_area.verticalScrollBar().setValue(new_scroll_y)

            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events."""
        self.setFocus()
        pos = event.position()
        transformed_pos = self._transform_pos(pos)

        if event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
            return

        if self.panning:
            self.pan_start = pos.toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.current_tool == "polygon":
            self._handle_polygon_click(transformed_pos)
        elif self.current_tool == "select":
            self._handle_select_click(transformed_pos, event)
        elif self.current_tool == "move":
            self._handle_move_click(transformed_pos)
        elif self.current_tool == "box":
            self._handle_box_click(transformed_pos)

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events."""
        pos = event.position()
        transformed_pos = self._transform_pos(pos)

        if self.panning:
            self._handle_pan(pos)
            return

        if self.drawing:
            self._handle_drawing_move(transformed_pos)
        elif self.current_tool == "select":
            self._handle_select_move(transformed_pos)

        self._update_hover(transformed_pos)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events."""
        if self.panning:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return

        pos = self._transform_pos(event.position())

        if self.drawing:
            if self.current_tool == "box":
                self._finish_box(pos)
            elif self.current_tool == "polygon":
                self._check_polygon_close(pos)

        # Create undo commands for completed move operations
        if self.selected_shape and self._move_start_points:
            new_points = [QPointF(p) for p in self.selected_shape.points]
            if self._move_start_points != new_points:
                # Shape was moved or resized - create command (already executed)
                cmd = MoveShapeCommand(
                    self.selected_shape,
                    self._move_start_points,
                    new_points,
                    self._on_undo_redo_change
                )
                # Add to undo stack without re-executing
                self.undo_manager._undo_stack.append(cmd)
                self.undo_manager._redo_stack.clear()
                self.undo_manager.state_changed.emit()

        if self.selected_shape and self._point_move_start is not None and self._point_move_index is not None:
            new_pos = self.selected_shape.points[self._point_move_index]
            if self._point_move_start != new_pos:
                # Point was moved - create command (already executed)
                cmd = MovePointCommand(
                    self.selected_shape,
                    self._point_move_index,
                    self._point_move_start,
                    QPointF(new_pos),
                    self._on_undo_redo_change
                )
                self.undo_manager._undo_stack.append(cmd)
                self.undo_manager._redo_stack.clear()
                self.undo_manager.state_changed.emit()

        self.selecting = False
        self.moving_shape = False
        self.resize_handle = None
        self.moving_point = None
        self.move_start_point = QPointF()
        self._move_start_points = None
        self._point_move_start = None
        self._point_move_index = None
        self.update()
        self.shapes_changed.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click to finish polygon."""
        if self.current_tool == "polygon" and self.drawing:
            if self.current_shape and len(self.current_shape.points) > 2:
                # Use command for undo support
                cmd = AddShapeCommand(self.shapes, self.current_shape, self._on_undo_redo_change)
                self.undo_manager.execute(cmd)
                self.shape_created.emit()
            self.current_shape = None
            self.drawing = False
            self.update()
            self.shapes_changed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Space:
            if not self.panning:
                self.panning = True
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_Escape:
            self.finish_drawing()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle key release events."""
        if event.key() == Qt.Key.Key_Space:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """Paint the canvas with image and shapes."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.scaled_pixmap and not self.scaled_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.scaled_pixmap)

        painter.scale(self.scale_factor, self.scale_factor)

        for shape in self.shapes:
            self._draw_shape(painter, shape)

        if self.current_shape:
            self._draw_shape(painter, self.current_shape)

        # Draw selected points
        for shape, point_index in self.selected_points:
            point = shape.points[point_index]
            painter.setBrush(QColor(255, 255, 0, 200))
            painter.drawEllipse(point, 6 / self.scale_factor, 6 / self.scale_factor)

    # === Drawing Helper Methods ===

    def _draw_shape(self, painter: QPainter, shape: Shape) -> None:
        """Draw a single shape with its label and points."""
        color = shape.color if hasattr(shape, "color") else (
            self.box_color if shape.type == ShapeType.BOX else self.polygon_color
        )

        if shape == self.selected_shape:
            color = QColor(255, 255, 0, 128)

        painter.setPen(QPen(color, self.line_thickness / self.scale_factor))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 64))

        if shape.type == ShapeType.BOX:
            painter.drawRect(QRectF(shape.points[0], shape.points[1]).normalized())
        elif shape.type == ShapeType.POLYGON:
            painter.drawPolygon(QPolygonF(shape.points))

        if shape.label:
            self._draw_label(painter, shape.label, shape.points[0], color)

        # Draw points
        for i, point in enumerate(shape.points):
            if self.hover_point and shape == self.hover_point[0] and i == self.hover_point[1]:
                painter.setBrush(QColor(255, 0, 0, 128))
                painter.drawEllipse(point, 5 / self.scale_factor, 5 / self.scale_factor)
            elif point == self.moving_point:
                painter.setBrush(QColor(255, 0, 0))
                painter.drawEllipse(point, 5 / self.scale_factor, 5 / self.scale_factor)
            else:
                painter.setBrush(QColor(0, 255, 0))
                painter.drawEllipse(point, 3 / self.scale_factor, 3 / self.scale_factor)

    def _draw_label(
        self,
        painter: QPainter,
        label: str,
        point: QPointF,
        color: QColor
    ) -> None:
        """Draw a label with background at the given position."""
        font = QFont("Arial", self.font_size)
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(label)
        text_height = font_metrics.height()

        padding = 4
        rect_width = text_width + 2 * padding
        rect_height = text_height + 2 * padding

        background_rect = QRectF(
            point.x(),
            point.y() - rect_height,
            rect_width,
            rect_height
        )

        background_color = QColor(color)
        background_color.setAlpha(180)

        # Determine text color based on background brightness
        brightness = (
            background_color.red() * 299 +
            background_color.green() * 587 +
            background_color.blue() * 114
        ) / 1000
        text_color = Qt.GlobalColor.black if brightness > 128 else Qt.GlobalColor.white

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_color)
        painter.drawRect(background_rect)

        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(background_rect, Qt.AlignmentFlag.AlignCenter, label)

    # === Coordinate Transform Methods ===

    def _transform_pos(self, pos: QPointF) -> QPointF:
        """Transform screen position to image coordinates."""
        return QPointF(pos.x() / self.scale_factor, pos.y() / self.scale_factor)

    def _inverse_transform_pos(self, pos: QPointF) -> QPointF:
        """Transform image coordinates to screen position."""
        return QPointF(pos.x() * self.scale_factor, pos.y() * self.scale_factor)

    # === Tool Handling Methods ===

    def _handle_polygon_click(self, pos: QPointF) -> None:
        """Handle click in polygon drawing mode."""
        if not self.drawing:
            if self.hover_edge:
                self._insert_point_to_polygon(pos)
            else:
                self.drawing = True
                self.current_shape = Shape(ShapeType.POLYGON, [pos])
        else:
            self.current_shape.points.append(pos)

    def _handle_box_click(self, pos: QPointF) -> None:
        """Handle click in box drawing mode."""
        self.drawing = True
        self.start_point = pos
        self.current_shape = Shape(ShapeType.BOX, [self.start_point, self.start_point])

    def _handle_select_click(self, pos: QPointF, event: QMouseEvent) -> None:
        """Handle click in select mode."""
        self.resize_handle = None
        self.moving_point = None
        self.moving_shape = False
        self._move_start_points = None
        self._point_move_start = None
        self._point_move_index = None

        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.selected_points = []

        for shape in self.shapes:
            shape.selected = False

        for shape in self.shapes:
            if shape.type == ShapeType.BOX:
                handle = self._get_resize_handle(shape, pos)
                if handle:
                    self.resize_handle = (shape, handle)
                    # Capture starting points for undo
                    self._move_start_points = [QPointF(p) for p in shape.points]
                    shape.selected = True
                    self.selected_shape = shape
                    return
            elif shape.type == ShapeType.POLYGON:
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                            if (shape, i) in self.selected_points:
                                self.selected_points.remove((shape, i))
                            else:
                                self.selected_points.append((shape, i))
                        else:
                            self.selected_points = [(shape, i)]

                        self.moving_point = point
                        # Capture starting position for undo
                        self._point_move_start = QPointF(point)
                        self._point_move_index = i
                        shape.selected = True
                        self.selected_shape = shape
                        self.update()
                        return

            if self._shape_contains_point(shape, pos):
                self.moving_shape = True
                shape.selected = True
                self.selected_shape = shape
                self.move_start_point = self._inverse_transform_pos(pos)
                # Capture starting points for undo
                self._move_start_points = [QPointF(p) for p in shape.points]
                return

        self.selected_shape = None
        self.update()

    def _handle_move_click(self, pos: QPointF) -> None:
        """Handle click in move mode."""
        for shape in self.shapes:
            if self._shape_contains_point(shape, pos):
                self.selected_shape = shape
                self.moving_shape = True
                self.move_start_point = self._inverse_transform_pos(pos)
                break

    def _handle_drawing_move(self, pos: QPointF) -> None:
        """Handle mouse move while drawing."""
        if self.current_tool == "box":
            self.current_shape.points[1] = pos
        elif self.current_tool == "polygon":
            if len(self.current_shape.points) > 0:
                self.current_shape.points[-1] = pos

    def _handle_select_move(self, pos: QPointF) -> None:
        """Handle mouse move in select mode."""
        if self.resize_handle:
            self._resize_box(pos)
        elif self.moving_point:
            self._move_polygon_point(pos)
        elif self.moving_shape:
            self._move_shape(pos)

    def _handle_pan(self, pos: QPointF) -> None:
        """Handle panning movement."""
        delta = pos.toPoint() - self.pan_start
        self.scroll_area.horizontalScrollBar().setValue(
            self.scroll_area.horizontalScrollBar().value() - delta.x()
        )
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().value() - delta.y()
        )
        self.pan_start = pos.toPoint()
        self._update_minimap()

    def _finish_box(self, pos: QPointF) -> None:
        """Finish drawing a box."""
        self.current_shape.points[1] = pos
        # Use command for undo support
        cmd = AddShapeCommand(self.shapes, self.current_shape, self._on_undo_redo_change)
        self.undo_manager.execute(cmd)
        self.current_shape = None
        self.drawing = False
        self.shape_created.emit()

    def _on_undo_redo_change(self) -> None:
        """Callback for undo/redo operations to refresh display."""
        self.update()
        self.shapes_changed.emit()

    def _check_polygon_close(self, pos: QPointF) -> None:
        """Check if polygon should be closed."""
        if (len(self.current_shape.points) > 2 and
            (pos - self.current_shape.points[0]).manhattanLength() < 20 / self.scale_factor):
            self.current_shape.points.pop()
            self.current_shape.points.append(self.current_shape.points[0])
            # Use command for undo support
            cmd = AddShapeCommand(self.shapes, self.current_shape, self._on_undo_redo_change)
            self.undo_manager.execute(cmd)
            self.current_shape = None
            self.drawing = False
            self.shape_created.emit()

    # === Shape Manipulation Methods ===

    def _get_resize_handle(self, shape: Shape, pos: QPointF) -> Optional[str]:
        """Get the resize handle name at position."""
        rect = QRectF(shape.points[0], shape.points[1]).normalized()
        handles = [
            ("topleft", rect.topLeft()),
            ("topright", rect.topRight()),
            ("bottomleft", rect.bottomLeft()),
            ("bottomright", rect.bottomRight())
        ]
        for name, point in handles:
            if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                return name
        return None

    def _resize_box(self, pos: QPointF) -> None:
        """Resize a box by moving a handle."""
        shape, handle = self.resize_handle
        rect = QRectF(shape.points[0], shape.points[1]).normalized()

        if handle == "topleft":
            rect.setTopLeft(pos)
        elif handle == "topright":
            rect.setTopRight(pos)
        elif handle == "bottomleft":
            rect.setBottomLeft(pos)
        elif handle == "bottomright":
            rect.setBottomRight(pos)

        shape.points = [rect.topLeft(), rect.bottomRight()]
        self.update()

    def _move_polygon_point(self, pos: QPointF) -> None:
        """Move a polygon point."""
        if self.moving_point and self.selected_shape:
            index = self.selected_shape.points.index(self.moving_point)
            self.selected_shape.move_point(index, pos)
            self.moving_point = pos

            self.selected_points = [
                (shape, i) if shape != self.selected_shape or i != index
                else (shape, index)
                for shape, i in self.selected_points
            ]
            self.update()

    def _move_shape(self, pos: QPointF) -> None:
        """Move the entire selected shape."""
        if self.selected_shape and self.move_start_point != QPointF():
            delta = pos - self._transform_pos(self.move_start_point)
            self.selected_shape.move_by(delta)
            self.move_start_point = self._inverse_transform_pos(pos)
            self.update()

    def _insert_point_to_polygon(self, pos: QPointF) -> None:
        """Insert a point into a polygon edge."""
        if self.hover_edge:
            shape, index = self.hover_edge
            shape.points.insert(index + 1, pos)
            self.selected_shape = shape
            self.moving_point = pos
            self.update()

    def _shape_contains_point(self, shape: Shape, point: QPointF) -> bool:
        """Check if a point is inside a shape."""
        if shape.type == ShapeType.BOX:
            rect = QRectF(shape.points[0], shape.points[1]).normalized()
            return rect.contains(point)
        elif shape.type == ShapeType.POLYGON:
            path = QPainterPath()
            path.addPolygon(QPolygonF(shape.points))
            return path.contains(point)
        return False

    def _update_hover(self, pos: QPointF) -> None:
        """Update hover state for shapes and points."""
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None

        for shape in self.shapes:
            if shape.type == ShapeType.POLYGON:
                # Check points
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                        self.hover_point = (shape, i)
                        self.hover_shape = shape
                        return

                # Check edges
                for i in range(len(shape.points)):
                    p1 = shape.points[i]
                    p2 = shape.points[(i + 1) % len(shape.points)]
                    if self._point_to_line_distance(pos, p1, p2) < self.EDGE_DETECTION_RADIUS / self.scale_factor:
                        self.hover_edge = (shape, i)
                        self.hover_shape = shape
                        return

            elif shape.type == ShapeType.BOX:
                # Check corners
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                        self.hover_point = (shape, i)
                        self.hover_shape = shape
                        return

                if self._shape_contains_point(shape, pos):
                    self.hover_shape = shape
                    return

    def _point_to_line_distance(
        self,
        p: QPointF,
        a: QPointF,
        b: QPointF
    ) -> float:
        """Calculate distance from point p to line segment a-b."""
        if a == b:
            return (p - a).manhattanLength()

        n = b - a
        pa = a - p
        c = n.x() * pa.x() + n.y() * pa.y()

        if c > 0:
            return (p - a).manhattanLength()
        elif c < -n.x() ** 2 - n.y() ** 2:
            return (p - b).manhattanLength()
        else:
            return abs(n.x() * pa.y() - n.y() * pa.x()) / ((n.x() ** 2 + n.y() ** 2) ** 0.5)

    # === Public Methods ===

    def finish_drawing(self) -> None:
        """Finish the current drawing operation."""
        if (self.current_shape and
            self.current_shape.type == ShapeType.POLYGON and
            len(self.current_shape.points) > 2):
            # Use command for undo support
            cmd = AddShapeCommand(self.shapes, self.current_shape, self._on_undo_redo_change)
            self.undo_manager.execute(cmd)
            self.shape_created.emit()

        self.current_shape = None
        self.drawing = False
        self.update()
        self.shapes_changed.emit()

    def delete_selected_points(self) -> None:
        """Delete all selected points from polygons."""
        if not self.selected_points:
            return

        # Group points by shape for undo
        shape_points = {}
        for shape, point_index in self.selected_points:
            if shape.type == ShapeType.POLYGON and len(shape.points) > 3:
                if shape not in shape_points:
                    shape_points[shape] = []
                shape_points[shape].append((point_index, QPointF(shape.points[point_index])))

        # Create undo commands for each shape
        for shape, points_data in shape_points.items():
            cmd = DeletePointsCommand(shape, points_data, self._on_undo_redo_change)
            self.undo_manager.execute(cmd)

        # Clear selection state
        self.selected_points = []
        self.moving_point = None
        self.selected_shape = None
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None

        # Remove shapes with less than 3 points
        self.shapes = [s for s in self.shapes if len(s.points) >= 3]

        self.update()
        self.shapes_changed.emit()
        self.points_deleted.emit()

    def delete_shape(self, shape_index: int) -> None:
        """Delete a shape by index."""
        if 0 <= shape_index < len(self.shapes):
            shape = self.shapes[shape_index]
            cmd = DeleteShapeCommand(self.shapes, shape, shape_index, self._on_undo_redo_change)
            self.undo_manager.execute(cmd)
            self.selected_shape = None

    def edit_classification(self, shape_index: int) -> None:
        """Edit the classification of a shape."""
        if 0 <= shape_index < len(self.shapes):
            shape = self.shapes[shape_index]
            old_label = shape.label
            new_label, ok = QInputDialog.getText(
                self,
                "Edit Classification",
                "Enter new classification:",
                text=shape.label
            )
            if ok and new_label and new_label != old_label:
                cmd = ChangeLabelCommand(shape, old_label, new_label, self._on_undo_redo_change)
                self.undo_manager.execute(cmd)
                self.classification_changed.emit(new_label)

    def undo(self) -> bool:
        """Undo the last action."""
        return self.undo_manager.undo()

    def redo(self) -> bool:
        """Redo the last undone action."""
        return self.undo_manager.redo()

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.undo_manager.can_undo()

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.undo_manager.can_redo()

    def clear_undo_history(self) -> None:
        """Clear the undo/redo history (e.g., when switching images)."""
        self.undo_manager.clear()

    def _update_minimap(self) -> None:
        """Emit view changed signal for minimap update."""
        if self.scroll_area:
            viewport_rect = self.scroll_area.viewport().rect()
            viewport_rect.translate(
                self.scroll_area.horizontalScrollBar().value(),
                self.scroll_area.verticalScrollBar().value()
            )
            self.view_changed.emit(viewport_rect)

    def _show_context_menu(self, position: QPoint) -> None:
        """Show context menu for shapes."""
        for i, shape in enumerate(self.shapes):
            if self._shape_contains_point(shape, self._transform_pos(QPointF(position))):
                menu = QMenu()
                edit_action = menu.addAction("Edit Classification")
                delete_action = menu.addAction("Delete Shape")

                action = menu.exec(self.mapToGlobal(position))

                if action == edit_action:
                    self.edit_classification(i)
                elif action == delete_action:
                    self.delete_shape(i)
                return
