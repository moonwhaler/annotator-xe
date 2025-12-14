"""Drawing area canvas widget for image annotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from PyQt6.QtCore import Qt, QPointF, QRectF, QRect, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QPolygonF,
    QPixmap, QFontMetrics, QMouseEvent, QKeyEvent, QWheelEvent,
    QNativeGestureEvent, QKeySequence, QImage
)
from PyQt6.QtWidgets import (
    QLabel, QMenu, QInputDialog, QScrollArea, QGestureEvent,
    QApplication, QWidget, QStackedLayout
)

from ..core.models import Shape, ShapeType
from ..core.undo_redo import (
    UndoRedoManager, AddShapeCommand, DeleteShapeCommand,
    MoveShapeCommand, MovePointCommand, ChangeLabelCommand, DeletePointsCommand
)

logger = logging.getLogger(__name__)

# Check if OpenGL is available
_OPENGL_AVAILABLE = False
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
    import OpenGL.GL as gl
    _OPENGL_AVAILABLE = True
except ImportError:
    logger.info("OpenGL not available - GPU acceleration disabled")


def is_opengl_available() -> bool:
    """Check if OpenGL is available for GPU acceleration."""
    return _OPENGL_AVAILABLE


@dataclass
class RenderState:
    """
    Shared rendering state between CPU and GPU backends.

    Contains all data needed to render the annotation canvas.
    """
    # Image
    pixmap: Optional[QPixmap] = None
    scaled_pixmap: Optional[QPixmap] = None

    # Shapes
    shapes: List[Shape] = field(default_factory=list)
    current_shape: Optional[Shape] = None
    selected_shape: Optional[Shape] = None
    selected_points: List[Tuple] = field(default_factory=list)

    # Hover state
    hover_point: Optional[Tuple] = None
    hover_edge: Optional[Tuple] = None
    hover_shape: Optional[Shape] = None
    moving_point: Optional[QPointF] = None
    _last_mouse_pos: Optional[QPointF] = None

    # Selection rectangle
    selection_rect_start: Optional[QPointF] = None
    selection_rect_end: Optional[QPointF] = None
    drawing_selection_rect: bool = False

    # View state
    scale_factor: float = 1.0
    current_tool: Optional[str] = None
    drawing: bool = False

    # Visual settings
    line_thickness: int = 2
    font_size: int = 10
    box_color: QColor = field(default_factory=lambda: QColor("#FF0000"))
    polygon_color: QColor = field(default_factory=lambda: QColor("#00FF00"))


class RenderBackendMixin:
    """
    Mixin providing common rendering methods for both CPU and GPU backends.

    Contains the shape drawing and label rendering logic that's shared
    between QPainter-based rendering approaches.
    """

    def _draw_shape(self, painter: QPainter, shape: Shape, state: RenderState) -> None:
        """Draw a single shape with its label and points."""
        color = shape.color if hasattr(shape, "color") else (
            state.box_color if shape.type == ShapeType.BOX else state.polygon_color
        )

        if shape == state.selected_shape:
            color = QColor(255, 255, 0, 128)

        painter.setPen(QPen(color, state.line_thickness / state.scale_factor))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 64))

        if shape.type == ShapeType.BOX:
            painter.drawRect(QRectF(shape.points[0], shape.points[1]).normalized())
        elif shape.type == ShapeType.POLYGON:
            painter.drawPolygon(QPolygonF(shape.points))

        if shape.label:
            self._draw_label(painter, shape.label, shape.points[0], color, state)

        # Draw points
        for i, point in enumerate(shape.points):
            if state.hover_point and shape == state.hover_point[0] and i == state.hover_point[1]:
                painter.setBrush(QColor(255, 0, 0, 128))
                painter.drawEllipse(point, 5 / state.scale_factor, 5 / state.scale_factor)
            elif point == state.moving_point:
                painter.setBrush(QColor(255, 0, 0))
                painter.drawEllipse(point, 5 / state.scale_factor, 5 / state.scale_factor)
            else:
                painter.setBrush(QColor(0, 255, 0))
                painter.drawEllipse(point, 3 / state.scale_factor, 3 / state.scale_factor)

    def _draw_label(
        self,
        painter: QPainter,
        label: str,
        point: QPointF,
        color: QColor,
        state: RenderState
    ) -> None:
        """Draw a label with background at the given position."""
        adjusted_font_size = state.font_size / state.scale_factor
        font = QFont("Arial", int(adjusted_font_size))
        font.setPointSizeF(adjusted_font_size)
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(label)
        text_height = font_metrics.height()

        padding = 4 / state.scale_factor
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

    def _draw_overlays(self, painter: QPainter, state: RenderState) -> None:
        """Draw selection rectangles, hover highlights, and other overlays."""
        # Draw selected points
        for shape, point_index in state.selected_points:
            point = shape.points[point_index]
            painter.setBrush(QColor(255, 255, 0, 200))
            painter.drawEllipse(point, 6 / state.scale_factor, 6 / state.scale_factor)

        # Draw selection rectangle
        if state.drawing_selection_rect and state.selection_rect_start and state.selection_rect_end:
            rect = QRectF(state.selection_rect_start, state.selection_rect_end).normalized()
            painter.setPen(QPen(QColor(0, 120, 215), 1 / state.scale_factor, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(0, 120, 215, 30))
            painter.drawRect(rect)

        # Draw edge hover highlight and preview point
        if state.hover_edge and state.current_tool == "polygon" and not state.drawing:
            shape, edge_index = state.hover_edge
            p1 = shape.points[edge_index]
            p2 = shape.points[(edge_index + 1) % len(shape.points)]

            highlight_color = QColor(0, 200, 255)
            painter.setPen(QPen(highlight_color, (state.line_thickness + 2) / state.scale_factor))
            painter.drawLine(p1, p2)

            if state._last_mouse_pos:
                preview_point = self._closest_point_on_line(state._last_mouse_pos, p1, p2)
                painter.setPen(QPen(highlight_color, 2 / state.scale_factor))
                painter.setBrush(QColor(255, 255, 255, 200))
                painter.drawEllipse(preview_point, 6 / state.scale_factor, 6 / state.scale_factor)
                painter.setBrush(highlight_color)
                painter.drawEllipse(preview_point, 3 / state.scale_factor, 3 / state.scale_factor)

    def _closest_point_on_line(self, p: QPointF, a: QPointF, b: QPointF) -> QPointF:
        """Find the closest point on line segment a-b to point p."""
        if a == b:
            return QPointF(a)

        ab = b - a
        ap = p - a
        ab_squared = ab.x() ** 2 + ab.y() ** 2
        t = (ap.x() * ab.x() + ap.y() * ab.y()) / ab_squared
        t = max(0.0, min(1.0, t))

        return QPointF(a.x() + t * ab.x(), a.y() + t * ab.y())


class CPURenderBackend(QLabel, RenderBackendMixin):
    """
    CPU-based rendering backend using QPainter.

    This is the default renderer that uses Qt's software rendering
    for image display and annotation drawing.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state: Optional[RenderState] = None
        self._scaled_pixmap: Optional[QPixmap] = None
        # Enable mouse tracking for hover detection without button press
        self.setMouseTracking(True)

    def set_render_state(self, state: RenderState) -> None:
        """Set the render state for drawing."""
        self._state = state

    def update_scaled_pixmap(self) -> None:
        """Update the scaled pixmap based on current scale factor."""
        if self._state and self._state.pixmap and not self._state.pixmap.isNull():
            self._scaled_pixmap = self._state.pixmap.scaled(
                self._state.pixmap.size() * self._state.scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setFixedSize(self._scaled_pixmap.size())
            self._state.scaled_pixmap = self._scaled_pixmap

    def paintEvent(self, event) -> None:
        """Paint the canvas with image and shapes."""
        super().paintEvent(event)

        if not self._state:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw image
        if self._scaled_pixmap and not self._scaled_pixmap.isNull():
            painter.drawPixmap(self.rect(), self._scaled_pixmap)

        # Apply scale for annotations
        painter.scale(self._state.scale_factor, self._state.scale_factor)

        # Draw shapes
        for shape in self._state.shapes:
            self._draw_shape(painter, shape, self._state)

        # Draw current shape being drawn
        if self._state.current_shape:
            self._draw_shape(painter, self._state.current_shape, self._state)

        # Draw overlays (selection, hover states)
        self._draw_overlays(painter, self._state)


class GPURenderBackend(RenderBackendMixin):
    """
    GPU-accelerated rendering backend using OpenGL.

    Uses QOpenGLWidget for hardware-accelerated image display
    while falling back to QPainter for annotation rendering.
    This hybrid approach provides GPU acceleration for the most
    expensive operation (image scaling) while maintaining
    compatibility with existing annotation rendering code.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if not _OPENGL_AVAILABLE:
            raise RuntimeError("OpenGL is not available")

        # Import here to avoid issues if OpenGL not available
        from PyQt6.QtOpenGLWidgets import QOpenGLWidget

        # Create the actual widget
        self._widget = _GPURenderWidget(parent)
        self._widget._backend = self
        self._state: Optional[RenderState] = None
        self._texture_id: int = 0
        self._texture_needs_update = True

    @property
    def widget(self) -> QWidget:
        """Return the underlying Qt widget."""
        return self._widget

    def set_render_state(self, state: RenderState) -> None:
        """Set the render state for drawing."""
        self._state = state
        self._widget._state = state

    def update_scaled_pixmap(self) -> None:
        """Mark texture for update (GPU handles scaling)."""
        self._texture_needs_update = True
        if self._state and self._state.pixmap and not self._state.pixmap.isNull():
            # Set widget size based on scaled dimensions
            orig_size = self._state.pixmap.size()
            scaled_width = int(orig_size.width() * self._state.scale_factor)
            scaled_height = int(orig_size.height() * self._state.scale_factor)
            self._widget.setFixedSize(scaled_width, scaled_height)

    def setFixedSize(self, *args):
        """Forward setFixedSize to the widget."""
        self._widget.setFixedSize(*args)

    def update(self):
        """Trigger a repaint."""
        self._widget.update()

    def size(self):
        """Return widget size."""
        return self._widget.size()


if _OPENGL_AVAILABLE:
    class _GPURenderWidget(QOpenGLWidget, RenderBackendMixin):
        """Internal OpenGL widget for GPU rendering."""

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._state: Optional[RenderState] = None
            self._backend: Optional[GPURenderBackend] = None
            self._texture_id: int = 0
            self._gl_initialized = False
            # Enable mouse tracking for hover detection without button press
            self.setMouseTracking(True)

        def initializeGL(self) -> None:
            """Initialize OpenGL context."""
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            self._gl_initialized = True

        def resizeGL(self, width: int, height: int) -> None:
            """Handle resize."""
            gl.glViewport(0, 0, width, height)
            gl.glMatrixMode(gl.GL_PROJECTION)
            gl.glLoadIdentity()
            gl.glOrtho(0, width, height, 0, -1, 1)
            gl.glMatrixMode(gl.GL_MODELVIEW)
            gl.glLoadIdentity()

        def paintGL(self) -> None:
            """Render the image using OpenGL."""
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            if not self._state or not self._state.pixmap:
                return

            # Upload texture if needed
            if self._backend and self._backend._texture_needs_update:
                self._upload_texture()
                self._backend._texture_needs_update = False

            # Draw image as textured quad
            if self._texture_id:
                self._draw_image()

        def _upload_texture(self) -> None:
            """Upload QPixmap to OpenGL texture."""
            if not self._state or not self._state.pixmap or self._state.pixmap.isNull():
                return

            image = self._state.pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            image = image.mirrored(False, True)  # OpenGL has inverted Y

            if self._texture_id == 0:
                self._texture_id = gl.glGenTextures(1)

            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

            ptr = image.bits()
            ptr.setsize(image.sizeInBytes())

            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                image.width(), image.height(), 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                bytes(ptr)
            )

        def _draw_image(self) -> None:
            """Draw image as textured quad."""
            if not self._state:
                return

            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
            gl.glColor4f(1.0, 1.0, 1.0, 1.0)

            w = self.width()
            h = self.height()

            gl.glBegin(gl.GL_QUADS)
            gl.glTexCoord2f(0, 1); gl.glVertex2f(0, 0)
            gl.glTexCoord2f(1, 1); gl.glVertex2f(w, 0)
            gl.glTexCoord2f(1, 0); gl.glVertex2f(w, h)
            gl.glTexCoord2f(0, 0); gl.glVertex2f(0, h)
            gl.glEnd()

        def paintEvent(self, event) -> None:
            """Paint with OpenGL for image, QPainter for annotations."""
            # First do OpenGL rendering
            super().paintEvent(event)

            if not self._state:
                return

            # Then overlay with QPainter for shapes (hybrid approach)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Apply scale for annotations
            painter.scale(self._state.scale_factor, self._state.scale_factor)

            # Draw shapes
            for shape in self._state.shapes:
                self._draw_shape(painter, shape, self._state)

            # Draw current shape being drawn
            if self._state.current_shape:
                self._draw_shape(painter, self._state.current_shape, self._state)

            # Draw overlays
            self._draw_overlays(painter, self._state)

            painter.end()


class DrawingArea(QWidget):
    """
    Main canvas widget for drawing and editing annotations.

    Supports drawing bounding boxes and polygons, with zoom/pan functionality
    and interactive editing of shapes and points.

    Uses pluggable render backends (CPU or GPU) for image display with
    dynamic switching capability.
    """

    # Signals
    view_changed = pyqtSignal(QRect)
    zoom_changed = pyqtSignal(float)
    classification_changed = pyqtSignal(str)
    shapes_changed = pyqtSignal()
    points_deleted = pyqtSignal()
    shape_created = pyqtSignal()
    select_mode_requested = pyqtSignal()
    shape_selected = pyqtSignal(object)  # Emits Shape or None when selection changes in viewport

    # Constants
    MIN_ZOOM = 0.2
    MAX_ZOOM = 5.0
    ZOOM_FACTOR = 1.1
    POINT_DETECTION_RADIUS = 10
    EDGE_DETECTION_RADIUS = 5

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the drawing area."""
        super().__init__(parent)

        # Visual settings
        self.scale_factor = 1.0
        self.box_color = QColor("#FF0000")
        self.polygon_color = QColor("#00FF00")
        self.line_thickness = 2
        self.font_size = 10
        self.auto_select_on_point_click = True
        self.finish_drawing_key = "Escape"  # Key/combination to finish drawing
        self.delete_shape_key = "Delete"  # Key/combination to delete selected shape

        # Undo/Redo manager
        self.undo_manager = UndoRedoManager()

        # Render state and backends
        self._render_state = RenderState()
        self._cpu_backend = CPURenderBackend(self)
        self._gpu_backend: Optional[GPURenderBackend] = None
        self._current_backend = self._cpu_backend
        self._gpu_enabled = False

        # Layout for render backends
        self._layout = QStackedLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._layout.addWidget(self._cpu_backend)

        # Set up backend
        self._cpu_backend.set_render_state(self._render_state)

        # Install event filter to forward mouse events from CPU backend
        self._cpu_backend.installEventFilter(self)

        # Image storage (for pixmap() compatibility)
        self._pixmap: Optional[QPixmap] = None

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
        self._last_mouse_pos: Optional[QPointF] = None  # For edge preview point

        self.panning = False
        self.pan_start = QPoint()
        self.scroll_area: Optional[QScrollArea] = None
        self.selected_points: List[Tuple[Shape, int]] = []

        # Undo tracking state
        self._move_start_points: Optional[List[QPointF]] = None
        self._point_move_start: Optional[QPointF] = None
        self._point_move_index: Optional[int] = None
        self._multi_point_move_starts: Optional[List[Tuple[Shape, int, QPointF]]] = None
        self._multi_point_drag_origin: Optional[QPointF] = None

        # Selection rectangle state
        self._selection_rect_start: Optional[QPointF] = None
        self._selection_rect_end: Optional[QPointF] = None
        self._drawing_selection_rect = False

        # Point insertion state
        self._inserting_point = False

        # Widget setup
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Enable native gesture events (for touchpad pinch-to-zoom)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)

    # === Pixmap Methods (for compatibility with QLabel API) ===

    def pixmap(self) -> Optional[QPixmap]:
        """Return the current pixmap."""
        return self._pixmap

    def setPixmap(self, pixmap: QPixmap) -> None:
        """Set the image pixmap."""
        self._pixmap = pixmap
        self._render_state.pixmap = pixmap
        self._sync_render_state()
        self._update_scaled_pixmap()
        self.update()

    def clear(self) -> None:
        """Clear the pixmap and reset state (QLabel API compatibility)."""
        self._pixmap = None
        self._render_state.pixmap = None
        self._render_state.scaled_pixmap = None
        self.scaled_pixmap = None

        # Clear backend state
        self._cpu_backend._scaled_pixmap = None
        self._cpu_backend.clear()  # QLabel.clear()

        if self._gpu_backend:
            self._gpu_backend._texture_needs_update = True

        self.update()

    # === GPU Acceleration ===

    def set_gpu_acceleration(self, enabled: bool) -> None:
        """
        Enable or disable GPU-accelerated rendering.

        Args:
            enabled: True to use GPU rendering, False for CPU rendering
        """
        if enabled == self._gpu_enabled:
            return

        if enabled and not is_opengl_available():
            logger.warning("GPU acceleration requested but OpenGL is not available")
            return

        self._gpu_enabled = enabled

        if enabled:
            # Create GPU backend if needed
            if self._gpu_backend is None:
                try:
                    self._gpu_backend = GPURenderBackend(self)
                    self._layout.addWidget(self._gpu_backend.widget)
                    self._gpu_backend.set_render_state(self._render_state)

                    # Install event filter to forward mouse events
                    self._gpu_backend.widget.installEventFilter(self)
                except Exception as e:
                    logger.error(f"Failed to create GPU backend: {e}")
                    self._gpu_enabled = False
                    return

            # Switch to GPU backend
            self._current_backend = self._gpu_backend
            self._layout.setCurrentWidget(self._gpu_backend.widget)
            self._gpu_backend.update_scaled_pixmap()
            logger.info("Switched to GPU rendering")
        else:
            # Switch to CPU backend
            self._current_backend = self._cpu_backend
            self._layout.setCurrentWidget(self._cpu_backend)
            self._cpu_backend.update_scaled_pixmap()
            logger.info("Switched to CPU rendering")

        self._sync_render_state()
        self.update()

    def is_gpu_enabled(self) -> bool:
        """Check if GPU acceleration is currently enabled."""
        return self._gpu_enabled

    # === Render State Synchronization ===

    def _sync_render_state(self) -> None:
        """Synchronize local state with render state object."""
        self._render_state.shapes = self.shapes
        self._render_state.current_shape = self.current_shape
        self._render_state.selected_shape = self.selected_shape
        self._render_state.selected_points = self.selected_points
        self._render_state.hover_point = self.hover_point
        self._render_state.hover_edge = self.hover_edge
        self._render_state.hover_shape = self.hover_shape
        self._render_state.moving_point = self.moving_point
        self._render_state._last_mouse_pos = self._last_mouse_pos
        self._render_state.selection_rect_start = self._selection_rect_start
        self._render_state.selection_rect_end = self._selection_rect_end
        self._render_state.drawing_selection_rect = self._drawing_selection_rect
        self._render_state.scale_factor = self.scale_factor
        self._render_state.current_tool = self.current_tool
        self._render_state.drawing = self.drawing
        self._render_state.line_thickness = self.line_thickness
        self._render_state.font_size = self.font_size
        self._render_state.box_color = self.box_color
        self._render_state.polygon_color = self.polygon_color

    def set_scroll_area(self, scroll_area: QScrollArea) -> None:
        """Set the parent scroll area for pan support."""
        self.scroll_area = scroll_area

    def clear_interaction_state(self) -> None:
        """Clear interaction state when switching tools."""
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None
        self._selection_rect_start = None
        self._selection_rect_end = None
        self._drawing_selection_rect = False

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
        self._sync_render_state()

        if self._gpu_enabled and self._gpu_backend:
            self._gpu_backend.update_scaled_pixmap()
            # Update container size to match backend
            if self._pixmap and not self._pixmap.isNull():
                orig_size = self._pixmap.size()
                scaled_width = int(orig_size.width() * self.scale_factor)
                scaled_height = int(orig_size.height() * self.scale_factor)
                self.setFixedSize(scaled_width, scaled_height)
        else:
            self._cpu_backend.update_scaled_pixmap()
            # Update container size to match backend
            if self._cpu_backend._scaled_pixmap:
                self.setFixedSize(self._cpu_backend._scaled_pixmap.size())
                self.scaled_pixmap = self._cpu_backend._scaled_pixmap

    # === Event Handlers ===

    def event(self, event: QEvent) -> bool:
        """Handle events including gestures."""
        if event.type() == QEvent.Type.NativeGesture:
            return self._handle_native_gesture(event)
        elif event.type() == QEvent.Type.Gesture:
            return self._handle_gesture(event)
        return super().event(event)

    def _handle_native_gesture(self, event: QNativeGestureEvent) -> bool:
        """Handle native gesture events (macOS trackpad pinch-to-zoom)."""
        from PyQt6.QtCore import Qt as QtCore

        gesture_type = event.gestureType()

        if gesture_type == Qt.NativeGestureType.ZoomNativeGesture:
            # Pinch-to-zoom gesture
            zoom_delta = event.value()

            # Get cursor position for zoom center
            cursor_pos = event.position()

            # Calculate new scale factor
            # zoom_delta is typically small (e.g., 0.01 per tick)
            new_scale = self.scale_factor * (1.0 + zoom_delta)
            new_scale = max(min(new_scale, self.MAX_ZOOM), self.MIN_ZOOM)

            if new_scale != self.scale_factor:
                # Calculate relative position for zoom centering
                relative_pos = QPointF(
                    cursor_pos.x() / self.width() if self.width() > 0 else 0.5,
                    cursor_pos.y() / self.height() if self.height() > 0 else 0.5
                )

                old_scale = self.scale_factor
                self.set_scale_factor(new_scale)

                # Adjust scroll position to keep cursor point stable
                if self.scroll_area:
                    scale_ratio = new_scale / old_scale
                    viewport_size = self.scroll_area.viewport().size()

                    new_scroll_x = int(cursor_pos.x() * scale_ratio - viewport_size.width() * relative_pos.x())
                    new_scroll_y = int(cursor_pos.y() * scale_ratio - viewport_size.height() * relative_pos.y())

                    self.scroll_area.horizontalScrollBar().setValue(new_scroll_x)
                    self.scroll_area.verticalScrollBar().setValue(new_scroll_y)

            event.accept()
            return True

        return False

    def _handle_gesture(self, event: QGestureEvent) -> bool:
        """Handle gesture events (pinch-to-zoom via QGesture)."""
        from PyQt6.QtWidgets import QPinchGesture

        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if pinch and isinstance(pinch, QPinchGesture):
            change_flags = pinch.changeFlags()

            if change_flags & QPinchGesture.ChangeFlag.ScaleFactorChanged:
                scale_factor = pinch.scaleFactor()
                center = pinch.centerPoint()

                # Apply zoom
                new_scale = self.scale_factor * scale_factor
                new_scale = max(min(new_scale, self.MAX_ZOOM), self.MIN_ZOOM)

                if new_scale != self.scale_factor:
                    self.set_scale_factor(new_scale)

                    # Adjust scroll to center on pinch point
                    if self.scroll_area:
                        local_center = self.mapFromGlobal(center.toPoint())
                        self.scroll_area.ensureVisible(
                            int(local_center.x()),
                            int(local_center.y()),
                            50, 50
                        )

            event.accept()
            return True

        return False

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
        self._last_mouse_pos = transformed_pos

        if self.panning:
            self._handle_pan(pos)
            return

        if self.drawing:
            self._handle_drawing_move(transformed_pos)
        elif self.current_tool == "select":
            self._handle_select_move(transformed_pos)
        elif self.current_tool == "polygon" and self.moving_point:
            # Handle dragging a newly inserted point
            self._move_polygon_point(transformed_pos)

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

        # Handle multi-point move undo
        if self._multi_point_move_starts:
            commands_added = False
            for shape, idx, start_pos in self._multi_point_move_starts:
                new_pos = shape.points[idx]
                if start_pos != new_pos:
                    cmd = MovePointCommand(
                        shape,
                        idx,
                        start_pos,
                        QPointF(new_pos),
                        self._on_undo_redo_change
                    )
                    self.undo_manager._undo_stack.append(cmd)
                    commands_added = True
            if commands_added:
                self.undo_manager._redo_stack.clear()
                self.undo_manager.state_changed.emit()

        # Handle selection rectangle completion
        if self._drawing_selection_rect and self._selection_rect_start and self._selection_rect_end:
            self._select_points_in_rect()

        # Handle point insertion completion (polygon tool)
        if self._inserting_point and self.selected_shape:
            # Emit shapes_changed to trigger autosave and update UI
            self.shapes_changed.emit()

        self.selecting = False
        self.moving_shape = False
        self.resize_handle = None
        self.moving_point = None
        self.move_start_point = QPointF()
        self._move_start_points = None
        self._point_move_start = None
        self._point_move_index = None
        self._multi_point_move_starts = None
        self._multi_point_drag_origin = None
        self._selection_rect_start = None
        self._selection_rect_end = None
        self._inserting_point = False
        self._drawing_selection_rect = False
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
        elif self.finish_drawing_key and self._matches_key_sequence(event, self.finish_drawing_key):
            self.finish_drawing()
        elif self.delete_shape_key and self._matches_key_sequence(event, self.delete_shape_key):
            self._delete_selected()
        super().keyPressEvent(event)

    def _delete_selected(self) -> None:
        """Delete selected points or shape.

        If points are selected, delete those points.
        If no points selected but a shape is selected, delete the shape.
        """
        if self.selected_points:
            self.delete_selected_points()
        elif self.selected_shape and self.selected_shape in self.shapes:
            index = self.shapes.index(self.selected_shape)
            self.delete_shape(index)
            self.update()
            self.shapes_changed.emit()

    def _matches_key_sequence(self, event: QKeyEvent, key_sequence_str: str) -> bool:
        """Check if a key event matches a configured key sequence string."""
        if not key_sequence_str:
            return False

        # Build the key combination from the event
        key = event.key()
        modifiers = event.modifiers()

        # Ignore pure modifier key presses
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return False

        # Build combined key with modifiers
        combined = key
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            combined |= Qt.KeyboardModifier.ControlModifier.value
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            combined |= Qt.KeyboardModifier.ShiftModifier.value
        if modifiers & Qt.KeyboardModifier.AltModifier:
            combined |= Qt.KeyboardModifier.AltModifier.value
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            combined |= Qt.KeyboardModifier.MetaModifier.value

        # Create key sequence from the event and compare
        event_sequence = QKeySequence(combined)
        config_sequence = QKeySequence(key_sequence_str)

        return event_sequence == config_sequence

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle key release events."""
        if event.key() == Qt.Key.Key_Space:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """Paint event - rendering is delegated to the active backend."""
        # The backend widgets (CPURenderBackend or GPURenderBackend) handle
        # all actual rendering. This container widget doesn't draw anything.
        super().paintEvent(event)

    def update(self) -> None:
        """Update the widget - syncs state and triggers backend repaint."""
        self._sync_render_state()
        if self._gpu_enabled and self._gpu_backend:
            self._gpu_backend.update()
        else:
            self._cpu_backend.update()
        super().update()

    def eventFilter(self, watched, event) -> bool:
        """
        Filter events from child widgets (CPU and GPU backends).

        Forwards mouse and keyboard events from backend widgets to the
        DrawingArea's event handlers for consistent behavior.
        """
        # Check if event is from one of our backend widgets
        is_backend_widget = (
            watched == self._cpu_backend or
            (self._gpu_backend and watched == self._gpu_backend.widget)
        )

        if is_backend_widget:
            event_type = event.type()

            # Forward mouse events
            if event_type in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonDblClick,
            ):
                # Create a copy of the event and handle it
                if event_type == QEvent.Type.MouseButtonPress:
                    self.mousePressEvent(event)
                elif event_type == QEvent.Type.MouseButtonRelease:
                    self.mouseReleaseEvent(event)
                elif event_type == QEvent.Type.MouseMove:
                    self.mouseMoveEvent(event)
                elif event_type == QEvent.Type.MouseButtonDblClick:
                    self.mouseDoubleClickEvent(event)
                return True  # Event handled

            # Forward wheel events
            if event_type == QEvent.Type.Wheel:
                self.wheelEvent(event)
                return True

            # Forward key events
            if event_type == QEvent.Type.KeyPress:
                self.keyPressEvent(event)
                return True
            if event_type == QEvent.Type.KeyRelease:
                self.keyReleaseEvent(event)
                return True

        return super().eventFilter(watched, event)

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
        """Draw a label with background at the given position.

        The label size is adjusted inversely to the zoom level so it
        maintains a consistent visual size on screen.
        """
        # Adjust font size inversely to scale factor for consistent visual size
        adjusted_font_size = self.font_size / self.scale_factor
        font = QFont("Arial", int(adjusted_font_size))
        font.setPointSizeF(adjusted_font_size)  # Use float for smoother scaling
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(label)
        text_height = font_metrics.height()

        # Adjust padding inversely to scale factor
        padding = 4 / self.scale_factor
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

    def _get_point_at_position(self, pos: QPointF) -> Optional[Tuple[Shape, int]]:
        """Check if there's a shape point at the given position."""
        for shape in self.shapes:
            for i, point in enumerate(shape.points):
                if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                    return (shape, i)
        return None

    def _handle_polygon_click(self, pos: QPointF) -> None:
        """Handle click in polygon drawing mode."""
        if self.auto_select_on_point_click and not self.drawing:
            point_info = self._get_point_at_position(pos)
            if point_info:
                self._switch_to_select_and_grab_point(point_info, pos)
                return

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
        if self.auto_select_on_point_click:
            point_info = self._get_point_at_position(pos)
            if point_info:
                self._switch_to_select_and_grab_point(point_info, pos)
                return

        self.drawing = True
        self.start_point = pos
        self.current_shape = Shape(ShapeType.BOX, [self.start_point, self.start_point])

    def _switch_to_select_and_grab_point(self, point_info: Tuple[Shape, int], pos: QPointF) -> None:
        """Switch to select mode and immediately grab the point for dragging."""
        shape, point_index = point_info

        # Clear any previous selection state
        for s in self.shapes:
            s.selected = False

        # Set up the point for dragging
        shape.selected = True
        self.selected_shape = shape
        self.selected_points = [(shape, point_index)]
        self.shape_selected.emit(shape)

        if shape.type == ShapeType.BOX:
            # For boxes, set up resize handle
            rect = QRectF(shape.points[0], shape.points[1]).normalized()
            handle_map = {
                0: "topleft",
                1: "bottomright"
            }
            # Determine which corner based on point index
            if point_index == 0:
                # Check if this is top-left or bottom-right after normalization
                if shape.points[0] == rect.topLeft():
                    handle = "topleft"
                else:
                    handle = "bottomright"
            else:
                if shape.points[1] == rect.bottomRight():
                    handle = "bottomright"
                else:
                    handle = "topleft"
            self.resize_handle = (shape, handle)
            self._move_start_points = [QPointF(p) for p in shape.points]
        else:
            # For polygons, set up point dragging
            self.moving_point = shape.points[point_index]
            self._point_move_start = QPointF(shape.points[point_index])
            self._point_move_index = point_index

        # Emit signal to update toolbar
        self.select_mode_requested.emit()
        self.update()

    def _handle_select_click(self, pos: QPointF, event: QMouseEvent) -> None:
        """Handle click in select mode."""
        self.resize_handle = None
        self.moving_point = None
        self.moving_shape = False
        self._move_start_points = None
        self._point_move_start = None
        self._point_move_index = None
        self._multi_point_move_starts = None
        self._multi_point_drag_origin = None

        # Check if clicking on an already-selected point to start multi-point drag
        if len(self.selected_points) > 1:
            for shape, i in self.selected_points:
                point = shape.points[i]
                if (point - pos).manhattanLength() < self.POINT_DETECTION_RADIUS / self.scale_factor:
                    # Start multi-point drag
                    self._multi_point_move_starts = [
                        (s, idx, QPointF(s.points[idx])) for s, idx in self.selected_points
                    ]
                    self._multi_point_drag_origin = pos
                    self.moving_point = point  # Use this to indicate dragging is active
                    self.update()
                    return

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
                    self.shape_selected.emit(shape)
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
                        self.shape_selected.emit(shape)
                        self.update()
                        return

            if self._shape_contains_point(shape, pos):
                self.moving_shape = True
                shape.selected = True
                self.selected_shape = shape
                self.shape_selected.emit(shape)
                self.move_start_point = self._inverse_transform_pos(pos)
                # Capture starting points for undo
                self._move_start_points = [QPointF(p) for p in shape.points]
                return

        # No shape or point clicked - start selection rectangle
        self._selection_rect_start = pos
        self._selection_rect_end = pos
        self._drawing_selection_rect = True
        self.selected_shape = None
        self.shape_selected.emit(None)
        self.update()

    def _handle_move_click(self, pos: QPointF) -> None:
        """Handle click in move mode."""
        for shape in self.shapes:
            if self._shape_contains_point(shape, pos):
                self.selected_shape = shape
                self.shape_selected.emit(shape)
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
        if self._drawing_selection_rect:
            self._selection_rect_end = pos
            self.update()
        elif self.resize_handle:
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
        """Move polygon point(s) - supports both single and multi-point movement."""
        # Multi-point movement
        if self._multi_point_move_starts and self._multi_point_drag_origin:
            delta = pos - self._multi_point_drag_origin
            for shape, idx, start_pos in self._multi_point_move_starts:
                new_pos = start_pos + delta
                shape.points[idx] = new_pos
            self.update()
            return

        # Single point movement
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
        """Insert a point into a polygon edge and set up for immediate dragging."""
        if self.hover_edge:
            shape, edge_index = self.hover_edge
            new_point_index = edge_index + 1

            # Insert the new point
            shape.points.insert(new_point_index, pos)

            # Set up full dragging state (like _switch_to_select_and_grab_point)
            shape.selected = True
            self.selected_shape = shape
            self.selected_points = [(shape, new_point_index)]
            self.moving_point = shape.points[new_point_index]
            self._point_move_start = QPointF(pos)  # Start position for undo
            self._point_move_index = new_point_index
            self._inserting_point = True  # Flag to indicate we're inserting, not just moving

            self.shape_selected.emit(shape)
            self.update()

    def _select_points_in_rect(self) -> None:
        """Select all shape points inside the selection rectangle."""
        if not self._selection_rect_start or not self._selection_rect_end:
            return

        rect = QRectF(self._selection_rect_start, self._selection_rect_end).normalized()

        # Only select if rectangle has meaningful size
        if rect.width() < 5 / self.scale_factor and rect.height() < 5 / self.scale_factor:
            return

        for shape in self.shapes:
            for i, point in enumerate(shape.points):
                if rect.contains(point):
                    if (shape, i) not in self.selected_points:
                        self.selected_points.append((shape, i))

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

    def _closest_point_on_line(
        self,
        p: QPointF,
        a: QPointF,
        b: QPointF
    ) -> QPointF:
        """Find the closest point on line segment a-b to point p."""
        if a == b:
            return QPointF(a)

        # Vector from a to b
        ab = b - a
        # Vector from a to p
        ap = p - a

        # Project ap onto ab, getting the parameter t
        ab_squared = ab.x() ** 2 + ab.y() ** 2
        t = (ap.x() * ab.x() + ap.y() * ab.y()) / ab_squared

        # Clamp t to [0, 1] to stay on the segment
        t = max(0.0, min(1.0, t))

        # Calculate the closest point
        return QPointF(a.x() + t * ab.x(), a.y() + t * ab.y())

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
        """Delete all selected points from polygons.

        Ensures polygons remain closed after deletion if they were closed before.
        Won't delete points if it would leave fewer than 3 points.
        """
        if not self.selected_points:
            return

        # Group points by shape and track closure state
        # Use id(shape) as key since Shape is not hashable
        shape_info = {}  # id(shape) -> {'shape': shape, 'points': [...], 'was_closed': bool}
        for shape, point_index in self.selected_points:
            if shape.type != ShapeType.POLYGON:
                continue

            shape_id = id(shape)
            if shape_id not in shape_info:
                # Check if polygon is closed (first == last point)
                is_closed = (
                    len(shape.points) > 2 and
                    shape.points[0] == shape.points[-1]
                )
                shape_info[shape_id] = {
                    'shape': shape,
                    'points': [],
                    'was_closed': is_closed,
                    'effective_count': len(shape.points) - 1 if is_closed else len(shape.points)
                }

            shape_info[shape_id]['points'].append((point_index, QPointF(shape.points[point_index])))

        # Process each shape
        for shape_id, info in shape_info.items():
            shape = info['shape']
            points_to_delete = info['points']
            was_closed = info['was_closed']
            effective_count = info['effective_count']

            # For closed polygons, handle first/last point specially
            if was_closed:
                # Get indices being deleted
                indices = {idx for idx, _ in points_to_delete}
                last_idx = len(shape.points) - 1

                # If deleting first point (index 0), also mark last point for deletion
                # If deleting last point, also mark first point
                # But avoid double-counting
                if 0 in indices and last_idx not in indices:
                    points_to_delete.append((last_idx, QPointF(shape.points[last_idx])))
                elif last_idx in indices and 0 not in indices:
                    points_to_delete.append((0, QPointF(shape.points[0])))

                # Recalculate unique points being deleted (excluding the closing duplicate)
                unique_indices = set()
                for idx, _ in points_to_delete:
                    if idx == last_idx:
                        unique_indices.add(0)  # Treat last as first for closed polygons
                    else:
                        unique_indices.add(idx)

                # Check if we'd have at least 3 points remaining
                remaining = effective_count - len(unique_indices)
                if remaining < 3:
                    continue  # Skip this shape - can't delete
            else:
                # Open polygon - just check we have enough points
                if len(shape.points) - len(points_to_delete) < 3:
                    continue

            # Create undo command and execute
            cmd = DeletePointsCommand(shape, points_to_delete, self._on_undo_redo_change)
            self.undo_manager.execute(cmd)

            # Re-close the polygon if it was closed
            if was_closed and len(shape.points) >= 3:
                # Ensure first and last points are the same
                if shape.points[0] != shape.points[-1]:
                    shape.points.append(QPointF(shape.points[0]))

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
