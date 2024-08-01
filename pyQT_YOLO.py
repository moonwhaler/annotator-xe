import sys
import os
import yaml
import torch
from ultralytics import YOLO
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QListWidget, QHBoxLayout, QWidget, QLabel,
                             QVBoxLayout, QToolBar, QStatusBar, QListView, QPushButton, QSplitter, QMessageBox,
                             QMenu, QInputDialog, QDialog, QScrollArea, QListWidgetItem, QAbstractItemView, QSlider,
                             QTabWidget, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox, QComboBox,
                             QDockWidget, QSizePolicy)
from PyQt6.QtGui import (QPixmap, QIcon, QPainter, QColor, QPen, QFont, QPainterPath, QPolygonF, QAction, QPalette,
                         QActionGroup, QCursor, QImageReader, QStandardItemModel, QStandardItem, QFontMetrics)
from PyQt6.QtCore import (Qt, QPointF, QRectF, QSize, QSizeF, pyqtSignal, QPoint, QRect, QFileInfo,
                          QThread, QTimer, QDateTime)

def increase_image_allocation_limit():
    QImageReader.setAllocationLimit(0)  # 0 means no limit

class ImageLoader(QThread):
    image_loaded = pyqtSignal(str, QIcon)
    finished = pyqtSignal()

    def __init__(self, directory, file_list):
        super().__init__()
        self.directory = directory
        self.file_list = file_list
        self.is_running = True

    def run(self):
        for filename in self.file_list:
            if not self.is_running:
                break
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(self.directory, filename)
                try:
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        icon = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.image_loaded.emit(filename, QIcon(icon))
                except Exception as e:
                    print(f"Error loading image {file_path}: {str(e)}")
            QApplication.processEvents()  # Allow GUI to remain responsive
        self.finished.emit()

    def stop(self):
        self.is_running = False

class Shape:
    def __init__(self, shape_type, points, label=''):
        self.type = shape_type
        self.points = [QPointF(p) if isinstance(p, QPointF) else p for p in points]
        self.label = label
        self.selected = False
        self.color = self.generate_random_color()
        if self.type == 'polygon':
            self.close_polygon()

    @staticmethod
    def generate_random_color():
        return QColor.fromHsv(torch.randint(0, 360, (1,)).item(), 255, 255, 128)

    def close_polygon(self):
        if self.type == 'polygon' and len(self.points) > 2:
            if self.points[0] != self.points[-1]:
                self.points.append(QPointF(self.points[0]))

    def remove_point(self, index):
        if self.type == 'polygon' and len(self.points) > 3:
            del self.points[index]
            self.close_polygon()

    def move_by(self, delta):
        self.points = [point + delta for point in self.points]

    def move_point(self, index, new_pos):
        if 0 <= index < len(self.points):
            self.points[index] = new_pos
            if self.type == 'polygon':
                if index == 0 or index == len(self.points) - 1:
                    self.points[0] = self.points[-1] = new_pos

class DrawingArea(QLabel):
    view_changed = pyqtSignal(QRect)
    zoom_changed = pyqtSignal(float)
    classification_changed = pyqtSignal(str)
    shapes_changed = pyqtSignal()
    points_deleted = pyqtSignal()
    shape_created = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale_factor = 1.0
        self.box_color = QColor('#FF0000')
        self.polygon_color = QColor('#00FF00')
        self.line_thickness = 2
        self.font_size = 10
        self.init_drawing_area()

    def init_drawing_area(self):
        self.drawing = False
        self.selecting = False
        self.moving = False
        self.resizing = False
        self.start_point = QPointF()
        self.current_tool = None
        self.shapes = []
        self.current_shape = None
        self.selected_shape = None
        self.selected_point = None
        self.resize_handle = None
        self.hovered_point = None
        self.moving_point = None
        self.moving_shape = False
        self.move_start_point = QPointF()
        self.scale_factor = 1.0
        self.scaled_pixmap = None
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None
        self.panning = False
        self.pan_start = QPoint()
        self.scroll_area = None
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.selected_points = []  # Store selected points

    def set_scroll_area(self, scroll_area):
        self.scroll_area = scroll_area

    def set_scale_factor(self, factor):
        # Restrict zoom level between -500% and +500%
        self.scale_factor = max(min(factor, 5.0), 0.2)  # 0.2 is -500%, 5.0 is +500%
        self.update_scaled_pixmap()
        self.update()
        self.zoom_changed.emit(self.scale_factor)
        self.view_changed.emit(self.rect())

    def update_scaled_pixmap(self):
        if self.pixmap():
            self.scaled_pixmap = self.pixmap().scaled(
                self.pixmap().size() * self.scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setFixedSize(self.scaled_pixmap.size())

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            zoom_factor = 1.1 if delta > 0 else 1 / 1.1

            # Calculate the position of the cursor relative to the widget
            cursor_pos = event.position()
            relative_pos = QPointF(cursor_pos.x() / self.width(), cursor_pos.y() / self.height())

            # Apply zoom
            new_scale = self.scale_factor * zoom_factor
            self.set_scale_factor(new_scale)

            # Adjust scroll position to keep the point under the cursor fixed
            scroll_area = self.parent().parent()  # Assuming the structure: ScrollArea -> Viewport -> DrawingArea
            viewport_size = scroll_area.viewport().size()
            new_scroll_x = int(cursor_pos.x() * zoom_factor - viewport_size.width() * relative_pos.x())
            new_scroll_y = int(cursor_pos.y() * zoom_factor - viewport_size.height() * relative_pos.y())

            scroll_area.horizontalScrollBar().setValue(new_scroll_x)
            scroll_area.verticalScrollBar().setValue(new_scroll_y)

            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        pos = event.position()
        transformed_pos = self.transform_pos(pos)

        if event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
            return

        if self.panning:
            self.pan_start = pos.toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.current_tool == 'polygon':
            if not self.drawing:
                if self.hover_edge:
                    self.insert_point_to_polygon(transformed_pos)
                else:
                    self.drawing = True
                    self.current_shape = Shape('polygon', [transformed_pos])
            else:
                self.current_shape.points.append(transformed_pos)
        elif self.current_tool == 'select':
            self.handle_select_tool(transformed_pos, event)
        elif self.current_tool == 'move':
            self.handle_move_tool(transformed_pos)
        elif self.current_tool == 'box':
            self.drawing = True
            self.start_point = transformed_pos
            self.current_shape = Shape('box', [self.start_point, self.start_point])
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        transformed_pos = self.transform_pos(pos)
        if self.panning:
            delta = pos.toPoint() - self.pan_start
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y())
            self.pan_start = pos.toPoint()
            self.update_minimap()
            return

        if self.drawing:
            if self.current_tool == 'box':
                self.current_shape.points[1] = transformed_pos
            elif self.current_tool == 'polygon':
                if len(self.current_shape.points) > 0:
                    self.current_shape.points[-1] = transformed_pos
        elif self.current_tool == 'select':
            if self.resize_handle:
                self.resize_box(transformed_pos)
            elif self.moving_point:
                self.move_polygon_point(transformed_pos)
            elif self.moving_shape:
                self.move_shape(transformed_pos)
        self.update_hover(transformed_pos)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.panning:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return

        pos = self.transform_pos(event.position())
        if self.drawing:
            if self.current_tool == 'box':
                self.current_shape.points[1] = pos
                self.shapes.append(self.current_shape)
                self.current_shape = None
                self.drawing = False
                self.shape_created.emit()
            elif self.current_tool == 'polygon':
                if len(self.current_shape.points) > 2 and (pos - self.current_shape.points[0]).manhattanLength() < 20 / self.scale_factor:
                    self.current_shape.points.pop()
                    self.current_shape.points.append(self.current_shape.points[0])  # Close the polygon
                    self.shapes.append(self.current_shape)
                    self.current_shape = None
                    self.drawing = False
                    self.shape_created.emit()
        self.selecting = False
        self.moving_shape = False
        self.resize_handle = None
        self.moving_point = None
        self.move_start_point = QPointF()
        self.update()
        self.shapes_changed.emit()

    def mouseDoubleClickEvent(self, event):
        if self.current_tool == 'polygon' and self.drawing:
            if len(self.current_shape.points) > 2:
                self.shapes.append(self.current_shape)
                self.shape_created.emit()
            self.current_shape = None
            self.drawing = False
            self.update()
            self.shapes_changed.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.scaled_pixmap and not self.scaled_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.scaled_pixmap)

        painter.scale(self.scale_factor, self.scale_factor)

        for shape in self.shapes:
            self.draw_shape(painter, shape)

        if self.current_shape:
            self.draw_shape(painter, self.current_shape)

        # Draw selected points
        for shape, point_index in self.selected_points:
            point = shape.points[point_index]
            painter.setBrush(QColor(255, 255, 0, 200))
            painter.drawEllipse(point, 6 / self.scale_factor, 6 / self.scale_factor)

    def draw_shape(self, painter, shape):
        color = shape.color if hasattr(shape, 'color') else (self.box_color if shape.type == 'box' else self.polygon_color)
        if shape == self.selected_shape:
            color = QColor(255, 255, 0, 128)
        painter.setPen(QPen(color, self.line_thickness / self.scale_factor))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 64))

        if shape.type == 'box':
            painter.drawRect(QRectF(shape.points[0], shape.points[1]).normalized())
        elif shape.type == 'polygon':
            painter.drawPolygon(QPolygonF(shape.points))

        if shape.label:
            self.draw_label(painter, shape.label, shape.points[0], color)

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

    def draw_label(self, painter, label, point, color):
        font = QFont('Arial', self.font_size)
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(label)
        text_height = font_metrics.height()

        # Add padding
        padding = 4
        rect_width = text_width + 2 * padding
        rect_height = text_height + 2 * padding

        # Create rectangle for background
        background_rect = QRectF(point.x(), point.y() - rect_height, rect_width, rect_height)

        # Set background color (same as shape color but with reduced opacity)
        background_color = QColor(color)
        background_color.setAlpha(180)  # Adjust opacity as needed

        # Determine text color based on background brightness
        brightness = (background_color.red() * 299 + background_color.green() * 587 + background_color.blue() * 114) / 1000
        text_color = Qt.GlobalColor.black if brightness > 128 else Qt.GlobalColor.white

        # Draw background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_color)
        painter.drawRect(background_rect)

        # Draw text
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(background_rect, Qt.AlignmentFlag.AlignCenter, label)

    def transform_pos(self, pos):
        return QPointF(pos.x() / self.scale_factor, pos.y() / self.scale_factor)

    def inverse_transform_pos(self, pos):
        return QPointF(pos.x() * self.scale_factor, pos.y() * self.scale_factor)

    def update_hover(self, pos):
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None

        for shape in self.shapes:
            if shape.type == 'polygon':
                # Check for hovering over points
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < 10 / self.scale_factor:
                        self.hover_point = (shape, i)
                        self.hover_shape = shape
                        return

                # Check for hovering over edges
                for i in range(len(shape.points)):
                    p1 = shape.points[i]
                    p2 = shape.points[(i + 1) % len(shape.points)]
                    if self.point_to_line_distance(pos, p1, p2) < 5 / self.scale_factor:
                        self.hover_edge = (shape, i)
                        self.hover_shape = shape
                        return

            elif shape.type == 'box':
                # Check for hovering over box corners
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < 10 / self.scale_factor:
                        self.hover_point = (shape, i)
                        self.hover_shape = shape
                        return

                # Check if hovering over the box
                if self.shape_contains_point(shape, pos):
                    self.hover_shape = shape
                    return

    def insert_point_to_polygon(self, pos):
        if self.hover_edge:
            shape, index = self.hover_edge
            shape.points.insert(index + 1, pos)
            self.selected_shape = shape
            self.moving_point = pos
            self.update()

    def point_to_line_distance(self, p, a, b):
        if a == b:
            return (p - a).manhattanLength()
        else:
            n = b - a
            pa = a - p
            c = n.x() * pa.x() + n.y() * pa.y()
            if c > 0:
                return (p - a).manhattanLength()
            elif c < -n.x()**2 - n.y()**2:
                return (p - b).manhattanLength()
            else:
                return abs(n.x() * pa.y() - n.y() * pa.x()) / ((n.x()**2 + n.y()**2)**0.5)

    def handle_select_tool(self, pos, event):
        self.resize_handle = None
        self.moving_point = None
        self.moving_shape = False

        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.selected_points = []  # Clear previously selected points if Ctrl is not pressed

        for shape in self.shapes:
            shape.selected = False  # Deselect all shapes first

        for shape in self.shapes:
            if shape.type == 'box':
                handle = self.get_resize_handle(shape, pos)
                if handle:
                    self.resize_handle = (shape, handle)
                    shape.selected = True
                    self.selected_shape = shape
                    return
            elif shape.type == 'polygon':
                for i, point in enumerate(shape.points):
                    if (point - pos).manhattanLength() < 10 / self.scale_factor:
                        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                            # If Ctrl is pressed, toggle selection
                            if (shape, i) in self.selected_points:
                                self.selected_points.remove((shape, i))
                            else:
                                self.selected_points.append((shape, i))
                        else:
                            # If Ctrl is not pressed, select only this point
                            self.selected_points = [(shape, i)]
                        self.moving_point = point
                        shape.selected = True
                        self.selected_shape = shape
                        self.update()
                        return

            if self.shape_contains_point(shape, pos):
                self.moving_shape = True
                shape.selected = True
                self.selected_shape = shape
                self.move_start_point = self.inverse_transform_pos(pos)
                return

        self.selected_shape = None
        self.update()

    def handle_move_tool(self, pos):
        for shape in self.shapes:
            if self.shape_contains_point(shape, pos):
                self.selected_shape = shape
                self.moving_shape = True
                self.move_start_point = self.inverse_transform_pos(pos)
                break

    def move_shape(self, pos):
        if self.selected_shape and self.move_start_point != QPointF():
            delta = pos - self.transform_pos(self.move_start_point)
            self.selected_shape.move_by(delta)
            self.move_start_point = self.inverse_transform_pos(pos)
            self.update()

    def get_resize_handle(self, shape, pos):
        rect = QRectF(shape.points[0], shape.points[1]).normalized()
        handles = [
            ('topleft', rect.topLeft()), ('topright', rect.topRight()),
            ('bottomleft', rect.bottomLeft()), ('bottomright', rect.bottomRight())
        ]
        for name, point in handles:
            if (point - pos).manhattanLength() < 10 / self.scale_factor:
                return name
        return None

    def resize_box(self, pos):
        shape, handle = self.resize_handle
        rect = QRectF(shape.points[0], shape.points[1]).normalized()
        if handle == 'topleft':
            rect.setTopLeft(pos)
        elif handle == 'topright':
            rect.setTopRight(pos)
        elif handle == 'bottomleft':
            rect.setBottomLeft(pos)
        elif handle == 'bottomright':
            rect.setBottomRight(pos)
        shape.points = [rect.topLeft(), rect.bottomRight()]
        self.update()

    def move_polygon_point(self, pos):
        if self.moving_point and self.selected_shape:
            index = self.selected_shape.points.index(self.moving_point)
            self.selected_shape.move_point(index, pos)
            self.moving_point = pos

            # Update selected_points if the moved point is in the selection
            self.selected_points = [(shape, i) if shape != self.selected_shape or i != index
                                    else (shape, index) for shape, i in self.selected_points]
            self.update()

    def get_nearest_point(self, shape, point):
        return min(shape.points, key=lambda p: (p - point).manhattanLength())

    def shape_contains_point(self, shape, point):
        if shape.type == 'box':
            rect = QRectF(shape.points[0], shape.points[1]).normalized()
            return rect.contains(point)
        elif shape.type == 'polygon':
            path = QPainterPath()
            path.addPolygon(QPolygonF(shape.points))
            return path.contains(point)
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if not self.panning:
                self.panning = True
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_Escape:
            self.finish_drawing()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def finish_drawing(self):
        if self.current_shape and self.current_shape.type == 'polygon' and len(self.current_shape.points) > 2:
            self.shapes.append(self.current_shape)
            self.shape_created.emit()
        self.current_shape = None
        self.drawing = False
        self.update()
        self.shapes_changed.emit()

    def update_minimap(self):
        if self.scroll_area:
            viewport_rect = self.scroll_area.viewport().rect()
            viewport_rect.translate(
                self.scroll_area.horizontalScrollBar().value(),
                self.scroll_area.verticalScrollBar().value()
            )
            self.view_changed.emit(viewport_rect)

    def show_context_menu(self, position):
        for i, shape in enumerate(self.shapes):
            if self.shape_contains_point(shape, self.transform_pos(position)):
                self.create_shape_menu(position, i)
                return

    def create_shape_menu(self, position, shape_index):
        menu = QMenu()
        edit_action = menu.addAction("Edit Classification")
        delete_action = menu.addAction("Delete Shape")

        action = menu.exec(self.mapToGlobal(position))

        if action == edit_action:
            self.edit_classification(shape_index)
        elif action == delete_action:
            self.delete_shape(shape_index)

    def edit_classification(self, shape_index):
        shape = self.shapes[shape_index]
        new_label, ok = QInputDialog.getText(self, "Edit Classification", "Enter new classification:", text=shape.label)
        if ok and new_label:
            shape.label = new_label
            self.update()
            self.classification_changed.emit(new_label)

    def delete_shape(self, shape_index):
        del self.shapes[shape_index]
        self.update()
        self.shapes_changed.emit()

    def delete_selected_points(self):
        shapes_to_update = set()
        points_to_remove = []

        for shape, point_index in self.selected_points:
            if shape.type == 'polygon' and len(shape.points) > 3:
                shapes_to_update.add(shape)
                points_to_remove.append((shape, point_index))

        # Sort points_to_remove in reverse order to avoid index issues
        points_to_remove.sort(key=lambda x: x[1], reverse=True)

        for shape, point_index in points_to_remove:
            shape.remove_point(point_index)

        # Clear all selection and movement states
        self.selected_points = []
        self.moving_point = None
        self.selected_shape = None
        self.hover_point = None
        self.hover_edge = None
        self.hover_shape = None

        # Remove shapes with less than 3 points
        self.shapes = [shape for shape in self.shapes if len(shape.points) >= 3]

        self.update()
        self.shapes_changed.emit()
        self.points_deleted.emit()

class MiniatureView(QLabel):
    view_rect_changed = pyqtSignal(QRectF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.view_rect = QRectF()
        self.dragging = False
        self.start_pos = QPointF()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.original_pixmap = None
        self.image_size = QSizeF()
        self.aspect_ratio = 1.0

    def setPixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            self.image_size = pixmap.size()
            self.aspect_ratio = self.image_size.width() / self.image_size.height()
            self.update_scaled_pixmap()
        else:
            print("Warning: Attempted to set a null pixmap in MiniatureView")
            self.original_pixmap = None
            self.image_size = QSizeF()
            self.aspect_ratio = 1.0
            super().setPixmap(QPixmap())  # Set an empty pixmap

    def update_scaled_pixmap(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            available_width = self.width()
            available_height = self.height()

            # Calculate the size that maintains aspect ratio and fits within the available space
            scaled_width = available_width
            scaled_height = scaled_width / self.aspect_ratio

            if scaled_height > available_height:
                scaled_height = available_height
                scaled_width = scaled_height * self.aspect_ratio

            scaled_pixmap = self.original_pixmap.scaled(
                int(scaled_width), int(scaled_height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled_pixmap)
        else:
            super().setPixmap(QPixmap())  # Set an empty pixmap

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scaled_pixmap()
        # Set minimum height to current width
        self.setMinimumHeight(self.width())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap() and not self.pixmap().isNull():
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.drawRect(self.view_rect)

    def mousePressEvent(self, event):
        if self.view_rect.contains(event.position()):
            self.dragging = True
            self.start_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position() - self.start_pos
            new_rect = self.view_rect.translated(delta)

            # Adjust the new_rect to keep it within the bounds of the miniature view
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

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_view_rect(self, rect):
        self.view_rect = rect
        self.update()

class ImageListItem(QListWidgetItem):
    def __init__(self, icon, file_path):
        super().__init__(icon, "")  # Remove the text (filename) from the item
        self.file_path = file_path
        self.file_info = QFileInfo(file_path)
        self.setSizeHint(QSize(100, 100))  # Set a fixed size for the item
        self.has_annotation = self.check_annotation_exists()
        self.hidden = False

    def __lt__(self, other):
        if not isinstance(other, ImageListItem):
            return super().__lt__(other)

        sort_role = self.listWidget().sort_role
        if sort_role == "name":
            return self.file_info.fileName().lower() < other.file_info.fileName().lower()
        elif sort_role == "date_modified":
            return self.file_info.lastModified() < other.file_info.lastModified()
        elif sort_role == "date_created":
            return self.file_info.birthTime() < other.file_info.birthTime()
        else:
            return super().__lt__(other)

    def check_annotation_exists(self):
        txt_path = os.path.splitext(self.file_path)[0] + '.txt'
        return os.path.exists(txt_path)

    def setHidden(self, hidden):
        self.hidden = hidden
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEnabled if hidden else self.flags() | Qt.ItemFlag.ItemIsEnabled)

    def isHidden(self):
        return self.hidden

class SortableImageList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sort_role = "name"
        self.sort_order = Qt.SortOrder.AscendingOrder
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setSpacing(10)  # Add spacing between items

    def setSortRole(self, role):
        self.sort_role = role
        self.sortItems()

    def setSortOrder(self, order):
        self.sort_order = order
        self.sortItems()

    def sortItems(self, order=None):
        if order is None:
            order = self.sort_order
        super().sortItems(order)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = {}
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Settings')
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout(self)

        tab_widget = QTabWidget()
        tab_widget.addTab(self.createGeneralTab(), "General")
        tab_widget.addTab(self.createYOLOTab(), "YOLO")
        tab_widget.addTab(self.createUITab(), "UI")
        layout.addWidget(tab_widget)

        buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttonBox.accepted.connect(self.saveSettings)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self.setLayout(layout)

    def createGeneralTab(self):
        widget = QWidget()
        layout = QFormLayout()

        self.defaultDirEdit = QLineEdit()
        layout.addRow("Default Directory:", self.defaultDirEdit)

        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseDefaultDir)
        layout.addRow("", browseButton)

        self.autosaveCheckBox = QCheckBox("Autosave YOLO files")
        layout.addRow("", self.autosaveCheckBox)

        widget.setLayout(layout)
        return widget

    def createYOLOTab(self):
        widget = QWidget()
        layout = QFormLayout()

        self.modelPathEdit = QLineEdit()
        layout.addRow("Default YOLO Model:", self.modelPathEdit)

        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(self.browseModelPath)
        layout.addRow("", browseButton)

        widget.setLayout(layout)
        return widget

    def createUITab(self):
        widget = QWidget()
        layout = QFormLayout()

        self.lineThicknessSpinBox = QSpinBox()
        self.lineThicknessSpinBox.setRange(1, 10)
        layout.addRow("Line Thickness:", self.lineThicknessSpinBox)

        self.fontSizeSpinBox = QSpinBox()
        self.fontSizeSpinBox.setRange(6, 24)
        layout.addRow("Font Size:", self.fontSizeSpinBox)

        widget.setLayout(layout)
        return widget

    def browseDefaultDir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Default Directory")
        if directory:
            self.defaultDirEdit.setText(directory)

    def browseModelPath(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "Select YOLO Model", "", "YOLO Model (*.pt)")
        if filePath:
            self.modelPathEdit.setText(filePath)

    def loadSettings(self):
        try:
            with open('config.yaml', 'r') as f:
                self.settings = yaml.safe_load(f)
        except FileNotFoundError:
            self.settings = {}

        self.defaultDirEdit.setText(self.settings.get('defaultDirectory', ''))
        self.modelPathEdit.setText(self.settings.get('yoloModelPath', ''))
        self.lineThicknessSpinBox.setValue(self.settings.get('lineThickness', 2))
        self.fontSizeSpinBox.setValue(self.settings.get('fontSize', 10))
        self.autosaveCheckBox.setChecked(self.settings.get('autosave', False))

    def saveSettings(self):
        self.settings['defaultDirectory'] = self.defaultDirEdit.text()
        self.settings['yoloModelPath'] = self.modelPathEdit.text()
        self.settings['lineThickness'] = self.lineThicknessSpinBox.value()
        self.settings['fontSize'] = self.fontSizeSpinBox.value()
        self.settings['autosave'] = self.autosaveCheckBox.isChecked()

        with open('config.yaml', 'w') as f:
            yaml.dump(self.settings, f)

        self.accept()

class ModelSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.model_path = None

    def initUI(self):
        self.setWindowTitle('Select YOLO Model')
        layout = QVBoxLayout()

        self.path_label = QLabel('No model selected')
        layout.addWidget(self.path_label)

        select_button = QPushButton('Select Model')
        select_button.clicked.connect(self.select_model)
        layout.addWidget(select_button)

        ok_button = QPushButton('OK')
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def select_model(self):
        file_dialog = QFileDialog()
        self.model_path, _ = file_dialog.getOpenFileName(self, 'Select YOLO Model', '', 'PT files (*.pt)')
        if self.model_path:
            self.path_label.setText(f'Selected: {self.model_path}')

    def get_model_path(self):
        return self.model_path

class YOLODetector:
    def __init__(self, model_path):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        try:
            self.model = YOLO(model_path)
            self.model.to(self.device)
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            self.model = None

    def detect(self, image_path):
        if self.model is None:
            raise ValueError("YOLO model not properly initialized")
        results = self.model(image_path)
        return results

class ImageBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dock_widgets = {}
        self.view_actions = {}
        increase_image_allocation_limit()
        self.current_directory = ""
        self.current_image = ""
        self.classes = {}
        self.yaml_data = {}
        self.yolo_detector = None
        self.settings = {}
        self.image_loader = None

        # Initialize UI elements
        self.zoom_slider = None
        self.miniature_view = None
        self.image_list = None
        self.class_list = None
        self.class_model = None
        self.shape_list = None
        self.image_label = DrawingArea(self)
        self.image_scroll_area = None
        self.status_bar = None
        self.dir_label = None
        self.file_label = None

        # Workspace layout feature
        self.area_to_int = {
            Qt.DockWidgetArea.LeftDockWidgetArea: 1,
            Qt.DockWidgetArea.RightDockWidgetArea: 2,
            Qt.DockWidgetArea.TopDockWidgetArea: 4,
            Qt.DockWidgetArea.BottomDockWidgetArea: 8,
            Qt.DockWidgetArea.AllDockWidgetAreas: 15,
            Qt.DockWidgetArea.NoDockWidgetArea: 0
        }
        self.int_to_area = {v: k for k, v in self.area_to_int.items()}
        self.workspaces = {"Default": self.get_default_layout()}
        self.load_workspaces()

        self.loadSettings()
        self.initUI()
        self.setupConnections()

        print("ImageBrowser initialization complete")
        print(f"self.shape_list exists: {hasattr(self, 'shape_list')}")

    def initUI(self):
        self.setWindowTitle('Annotator XE')
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create and set up the image label
        self.image_scroll_area = QScrollArea()
        self.image_label = DrawingArea()
        self.image_label.set_scroll_area(self.image_scroll_area)
        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)

        # Set the image scroll area as the central widget
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.image_scroll_area)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.dir_label = QLabel()
        self.status_bar.addPermanentWidget(self.dir_label)
        self.file_label = QLabel()
        self.status_bar.addPermanentWidget(self.file_label)
        self.image_count_label = QLabel()
        self.status_bar.addPermanentWidget(self.image_count_label)
        self.tagged_count_label = QLabel()
        self.status_bar.addPermanentWidget(self.tagged_count_label)

        # Create dock widgets
        self.create_dock_widgets()

        # Create toolbar
        self.create_toolbar()

        # Create menu bar
        menubar = self.menuBar()

        # Add File menu
        file_menu = menubar.addMenu('File')
        self.create_file_menu(file_menu)

        # Add Settings menu
        settings_menu = menubar.addMenu('Settings')
        self.create_settings_menu(settings_menu)

        # Add View menu
        view_menu = menubar.addMenu('View')
        self.create_view_menu(view_menu)

        # Add workspace menu
        self.create_workspaces_menu()

        # Add Info menu
        info_menu = menubar.addMenu('Info')
        self.create_info_menu(info_menu)

    def create_file_menu(self, file_menu):
        open_action = QAction('Open Directory', self)
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)

        save_action = QAction('Save YOLO', self)
        save_action.triggered.connect(self.save_yolo)
        file_menu.addAction(save_action)

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def create_settings_menu(self, settings_menu):
        settings_action = QAction('Open Settings', self)
        settings_action.triggered.connect(self.openSettings)
        settings_menu.addAction(settings_action)

    def create_info_menu(self, info_menu):
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about_dialog)
        info_menu.addAction(about_action)

    def show_about_dialog(self):
        QMessageBox.about(self, "About Annotator XE",
                          "Annotator XE\nVersion 0.5\n\nA powerful tool for image annotation and YOLO format generation.")

    def on_resize(self, event):
        super().resizeEvent(event)
        self.update_minimap_view_rect()

    def on_miniature_dock_resize(self, event):
        # Update the minimum height of the miniature view to match the dock's width
        self.miniature_view.setMinimumHeight(self.dock_widgets["Miniature View"].width())
        # Call the original resizeEvent
        QDockWidget.resizeEvent(self.dock_widgets["Miniature View"], event)

    def create_view_menu(self, view_menu):
        for name, dock_widget in self.dock_widgets.items():
            action = self.create_dock_toggle_action(name, dock_widget)
            view_menu.addAction(action)
            self.view_actions[name] = action  # Store the action in the dictionary

    def create_dock_toggle_action(self, name, dock_widget):
        action = QAction(name, self, checkable=True)
        action.setChecked(dock_widget.isVisible())
        action.triggered.connect(lambda checked, dw=dock_widget: self.toggle_dock_visibility(dw, checked))

        # Connect the dock widget's visibilityChanged signal to update the action
        dock_widget.visibilityChanged.connect(lambda visible, act=action: act.setChecked(visible))

        return action

    def toggle_dock_visibility(self, dock_widget, visible):
        if visible:
            dock_widget.show()
        else:
            dock_widget.hide()

    def setupConnections(self):
        # Connect image label signals
        self.image_label.view_changed.connect(self.update_minimap_view_rect)
        self.image_label.zoom_changed.connect(self.update_zoom_slider)
        self.image_label.classification_changed.connect(self.handle_classification_change)
        self.image_label.shapes_changed.connect(self.update_shapes)
        self.image_label.shape_created.connect(self.on_shape_created)

        # Connect image list
        if self.image_list:
            self.image_list.itemClicked.connect(self.display_image)

        # Connect class list
        if self.class_list:
            self.class_list.doubleClicked.connect(self.edit_classification)

        # Connect shape list
        if self.shape_list:
            self.shape_list.itemSelectionChanged.connect(self.select_shape_from_list)

        # Connect miniature view
        self.miniature_view.view_rect_changed.connect(self.update_main_view)

        # Connect scroll bars to update minimap
        self.image_scroll_area.horizontalScrollBar().valueChanged.connect(self.update_minimap_view_rect)
        self.image_scroll_area.verticalScrollBar().valueChanged.connect(self.update_minimap_view_rect)

        # Connect zoom slider
        if self.zoom_slider:
            self.zoom_slider.valueChanged.connect(self.zoom_image)

        # Connect window resize event
        self.resizeEvent = self.on_resize

        # Connect miniature view resize event
        self.miniature_view.resizeEvent = self.on_miniature_dock_resize

        self.image_label.points_deleted.connect(self.on_points_deleted)
        self.hide_tagged_checkbox.stateChanged.connect(self.toggle_tagged_images)

    def on_shape_created(self):
        print("New shape created")  # Debug print
        self.update_shape_list()
        if self.settings.get('autosave', False):
            self.save_yolo()

    def create_dock_widgets(self):
        # Image Browser Dock
        self.dock_widgets["Image Browser"] = QDockWidget("Image Browser", self)
        self.dock_widgets["Image Browser"].setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_widgets["Image Browser"].setWidget(self.create_left_pane())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_widgets["Image Browser"])

        # Miniature View Dock
        self.dock_widgets["Miniature View"] = QDockWidget("Miniature View", self)
        self.dock_widgets["Miniature View"].setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        miniature_widget = QWidget()
        miniature_layout = QVBoxLayout(miniature_widget)
        miniature_layout.setContentsMargins(0, 0, 0, 0)
        miniature_layout.setSpacing(0)

        self.miniature_view = MiniatureView(self)
        self.miniature_view.view_rect_changed.connect(self.update_main_view)
        miniature_layout.addWidget(self.miniature_view, 1)  # Give it a stretch factor of 1

        zoom_controls = self.create_zoom_controls()
        miniature_layout.addWidget(zoom_controls)

        self.dock_widgets["Miniature View"].setWidget(miniature_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Miniature View"])

        # Connect the dock widget's resizeEvent to update the miniature view's minimum height
        self.dock_widgets["Miniature View"].resizeEvent = self.on_miniature_dock_resize

        # Classification List Dock
        self.dock_widgets["Classifications"] = QDockWidget("Classifications", self)
        self.dock_widgets["Classifications"].setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        classification_widget = QWidget()
        classification_layout = QVBoxLayout(classification_widget)
        self.class_list = QListView()
        self.class_model = QStandardItemModel()
        self.class_list.setModel(self.class_model)
        self.class_list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.class_list.doubleClicked.connect(self.edit_classification)
        classification_layout.addWidget(self.class_list)
        classification_layout.addWidget(self.create_class_toolbar())
        apply_button = QPushButton("Apply Classification")
        apply_button.clicked.connect(self.apply_classification)
        classification_layout.addWidget(apply_button)
        self.dock_widgets["Classifications"].setWidget(classification_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Classifications"])

        # Shape List Dock
        self.dock_widgets["Shapes"] = QDockWidget("Shapes", self)
        self.dock_widgets["Shapes"].setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        shapes_widget = QWidget()
        shapes_layout = QVBoxLayout(shapes_widget)
        self.shape_list = QListWidget()
        print("Shape list created")  # Debug print
        self.shape_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.shape_list.itemSelectionChanged.connect(self.select_shape_from_list)
        shapes_layout.addWidget(self.shape_list)

        # Add delete button
        delete_shape_button = QPushButton("Delete selected shape")
        delete_shape_button.clicked.connect(self.delete_selected_shape_from_list)
        shapes_layout.addWidget(delete_shape_button)

        self.dock_widgets["Shapes"].setWidget(shapes_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widgets["Shapes"])
        print("Shape list dock widget added")  # Debug print

    def delete_selected_shape_from_list(self):
        selected_items = self.shape_list.selectedItems()
        if selected_items:
            shape_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= shape_index < len(self.image_label.shapes):
                del self.image_label.shapes[shape_index]
                self.image_label.selected_shape = None
                self.image_label.update()
                self.update_shapes()
                if self.settings.get('autosave', False):
                    self.save_yolo()

    def create_left_pane(self):
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)

        left_layout.addWidget(QLabel("Images:"))

        # Add sorting controls
        sort_layout = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Date Modified", "Date Created"])
        self.sort_combo.currentTextChanged.connect(self.change_sort_role)

        self.order_combo = QComboBox()
        self.order_combo.addItems(["Ascending", "Descending"])
        self.order_combo.currentTextChanged.connect(self.change_sort_order)

        sort_layout.addWidget(QLabel("Sort by:"))
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addWidget(self.order_combo)

        left_layout.addLayout(sort_layout)

        # Create and add the image list
        self.image_list = SortableImageList()
        self.image_list.setIconSize(QSize(80, 80))
        self.image_list.itemClicked.connect(self.display_image)
        left_layout.addWidget(self.image_list)

        # Add "Hide tagged images" checkbox
        self.hide_tagged_checkbox = QCheckBox("Gray out tagged images")
        self.hide_tagged_checkbox.stateChanged.connect(self.toggle_tagged_images)
        left_layout.addWidget(self.hide_tagged_checkbox)

        return left_pane

    def create_class_toolbar(self):
        class_toolbar = QToolBar()
        class_toolbar.setIconSize(QSize(24, 24))

        add_class_action = QAction(self.create_icon('➕'), 'Add Classification', self)
        add_class_action.triggered.connect(self.add_classification)
        class_toolbar.addAction(add_class_action)

        edit_class_action = QAction(self.create_icon('✏️'), 'Edit Classification', self)
        edit_class_action.triggered.connect(self.edit_selected_classification)
        class_toolbar.addAction(edit_class_action)

        delete_class_action = QAction(self.create_icon('🗑️'), 'Delete Classification', self)
        delete_class_action.triggered.connect(self.delete_classification)
        class_toolbar.addAction(delete_class_action)

        return class_toolbar

    def create_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(self.toolbar)

        open_action = QAction(self.create_icon('📂'), 'Open Directory', self)
        open_action.triggered.connect(self.open_directory)
        self.toolbar.addAction(open_action)

        drawing_tools = QActionGroup(self)

        select_action = QAction(self.create_icon('👆'), 'Select', self)
        select_action.setCheckable(True)
        select_action.triggered.connect(lambda: self.set_drawing_tool('select'))
        drawing_tools.addAction(select_action)

        box_action = QAction(self.create_icon('◻️'), 'Draw Box', self)
        box_action.setCheckable(True)
        box_action.triggered.connect(lambda: self.set_drawing_tool('box'))
        drawing_tools.addAction(box_action)

        polygon_action = QAction(self.create_icon('🔺'), 'Draw Polygon', self)
        polygon_action.setCheckable(True)
        polygon_action.triggered.connect(lambda: self.set_drawing_tool('polygon'))
        drawing_tools.addAction(polygon_action)

        save_action = QAction(self.create_icon('💾'), 'Save YOLO', self)
        save_action.triggered.connect(self.save_yolo)
        self.toolbar.addAction(save_action)

        select_model_action = QAction(self.create_icon('🤖'), 'Select Model', self)
        select_model_action.triggered.connect(self.select_model)
        self.toolbar.addAction(select_model_action)

        detect_action = QAction(self.create_icon('🔍'), 'Auto Detect', self)
        detect_action.triggered.connect(self.auto_detect)
        self.toolbar.addAction(detect_action)

        settings_action = QAction(self.create_icon('⚙️'), 'Settings', self)
        settings_action.triggered.connect(self.openSettings)
        self.toolbar.addAction(settings_action)

        self.toolbar.addActions(drawing_tools.actions())

        # Set the "Select" tool as the default
        select_action.setChecked(True)
        if hasattr(self, 'status_bar'):
            self.set_drawing_tool('select')
        else:
            print("Warning: status_bar not initialized")

    def create_zoom_controls(self):
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 0, 0)  # Reduce margins for a more compact layout

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 500)  # 20% to 500% zoom
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.zoom_image)

        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(10)  # Minor ticks every 10%

        for value in [20, 50, 100, 200, 500]:
            self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            self.zoom_slider.setPageStep(value)

        reset_zoom_btn = QPushButton("↺")
        reset_zoom_btn.setToolTip("Reset Zoom")
        reset_zoom_btn.clicked.connect(self.reset_zoom)
        reset_zoom_btn.setMaximumWidth(30)
        reset_zoom_btn.setStyleSheet("font-size: 16px;")

        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(reset_zoom_btn)

        return zoom_widget

    @staticmethod
    def create_icon(text):
        app = QApplication.instance()
        palette = app.palette()

        is_dark_mode = palette.color(QPalette.ColorRole.Window).lightness() < 128

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setFont(QFont('Segoe UI Emoji', 20))

        if is_dark_mode:
            painter.setPen(Qt.GlobalColor.white)
        else:
            painter.setPen(Qt.GlobalColor.black)

        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        return QIcon(pixmap)

    def set_drawing_tool(self, tool):
        self.image_label.current_tool = tool
        if tool != 'polygon':
            self.image_label.finish_drawing()
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(f"Current tool: {tool.capitalize()}")
        else:
            print(f"Current tool: {tool.capitalize()}")

    def handle_classification_change(self, new_label):
        if new_label not in self.classes:
            self.classes[new_label] = len(self.classes)
        self.update_classification_list()

    def open_directory(self):
        new_directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if new_directory:
            self.reset_ui()
            self.current_directory = new_directory
            self.load_images(self.current_directory)
            self.load_yaml_classes()
            self.dir_label.setText(f"Directory: {self.current_directory}")

    def reset_ui(self):
        print("ImageBrowser.reset_ui called")
        self.current_image = ""
        self.classes = {}
        self.image_label.clear()
        self.image_label.shapes = []
        self.image_label.current_shape = None
        self.image_list.clear()
        self.class_model.clear()
        self.file_label.setText("")
        self.miniature_view.clear()
        self.miniature_view.set_view_rect(QRectF())
        self.reset_zoom()
        self.hide_tagged_checkbox.setChecked(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_minimap_view_rect()

    def load_images(self, dir_path):
        self.image_list.clear()
        self.show_status_message("Loading images...")

        file_list = os.listdir(dir_path)

        self.image_loader = ImageLoader(dir_path, file_list)
        self.image_loader.image_loaded.connect(self.add_image_to_list)
        self.image_loader.finished.connect(self.image_loading_finished)
        self.image_loader.start()

    def add_image_to_list(self, filename, icon):
        file_path = os.path.join(self.current_directory, filename)
        item = ImageListItem(icon, file_path)

        # Add green mark if annotation exists
        if item.has_annotation:
            marked_icon = self.add_green_mark(icon)
            item.setIcon(marked_icon)

        # Apply "Hide tagged images" filter
        if self.hide_tagged_checkbox.isChecked() and item.has_annotation:
            item.setHidden(True)

        self.image_list.addItem(item)

    def toggle_tagged_images(self):
        for index in range(self.image_list.count()):
            item = self.image_list.item(index)
            if isinstance(item, ImageListItem):
                if self.hide_tagged_checkbox.isChecked():
                    item.setHidden(item.has_annotation)
                else:
                    item.setHidden(False)

    def add_green_mark(self, icon):
        pixmap = icon.pixmap(80, 80)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw a small green circle at the bottom right corner
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 255, 0, 200))  # Semi-transparent green
        painter.drawEllipse(pixmap.width() - 15, pixmap.height() - 15, 10, 10)

        painter.end()
        return QIcon(pixmap)

    def image_loading_finished(self):
        self.show_status_message("Image loading complete")
        self.image_list.sortItems()
        self.image_loader = None

        # Count total images and tagged images
        total_images = self.image_list.count()
        tagged_images = sum(1 for index in range(total_images)
                            if isinstance(self.image_list.item(index), ImageListItem)
                            and self.image_list.item(index).has_annotation)

        # Update the image count labels
        if hasattr(self, 'image_count_label'):
            self.image_count_label.setText(f"Total Images: {total_images}")
        if hasattr(self, 'tagged_count_label'):
            self.tagged_count_label.setText(f"Tagged Images: {tagged_images}")

    def create_workspaces_menu(self):
        menubar = self.menuBar()
        self.workspaces_menu = menubar.addMenu('Workspaces')
        self.update_workspaces_menu()

    def update_workspaces_menu(self):
        self.workspaces_menu.clear()
        save_action = self.workspaces_menu.addAction('Save current workspace')
        save_action.triggered.connect(self.save_current_workspace)
        self.workspaces_menu.addSeparator()

        for workspace_name in self.workspaces.keys():
            action = self.workspaces_menu.addAction(workspace_name)
            action.triggered.connect(lambda checked, name=workspace_name: self.load_workspace(name))

    def save_current_workspace(self):
        name, ok = QInputDialog.getText(self, 'Save Workspace', 'Enter workspace name:')
        if ok and name:
            if name in self.workspaces:
                confirm = QMessageBox.question(self, 'Confirm Overwrite', f'Workspace "{name}" already exists. Overwrite?',
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.No:
                    return
            self.workspaces[name] = self.get_current_layout()
            self.save_workspaces()
            self.update_workspaces_menu()

    def load_workspace(self, name):
        if name in self.workspaces:
            self.apply_layout(self.workspaces[name])

            # Reset dock widths for the "Default" workspace
            if name == "Default":
                default_left_width = 250  # Default width for left pane
                default_right_width = 300  # Default width for right pane

                # Reset left dock width
                if "Image Browser" in self.dock_widgets:
                    self.resizeDocks([self.dock_widgets["Image Browser"]], [default_left_width], Qt.Orientation.Horizontal)

                # Reset right dock widths
                right_docks = ["Miniature View", "Classifications", "Shapes"]
                for dock_name in right_docks:
                    if dock_name in self.dock_widgets:
                        self.resizeDocks([self.dock_widgets[dock_name]], [default_right_width], Qt.Orientation.Horizontal)
        else:
            QMessageBox.warning(self, 'Warning', f'Workspace "{name}" not found.')

    def get_current_layout(self):
        layout = {}
        for name, dock in self.dock_widgets.items():
            area = self.dockWidgetArea(dock)
            layout[name] = {
                'area': self.area_to_int.get(area, 0),
                'floating': dock.isFloating(),
                'geometry': dock.geometry().getRect() if dock.isFloating() else None,
                'visible': dock.isVisible(),
                'size': {
                    'width': dock.width(),
                    'height': dock.height()
                }
            }

        # Save main window size
        layout['main_window'] = {
            'size': {
                'width': self.width(),
                'height': self.height()
            }
        }

        return layout

    def get_default_layout(self):
        default_left_width = 250  # Default width for left pane
        default_right_width = 300  # Default width for right pane
        default_height = 300  # Default height for all panes

        return {
            "Image Browser": {'area': self.area_to_int[Qt.DockWidgetArea.LeftDockWidgetArea], 'floating': False, 'geometry': None, 'visible': True, 'size': {'width': default_left_width, 'height': default_height}},
            "Miniature View": {'area': self.area_to_int[Qt.DockWidgetArea.RightDockWidgetArea], 'floating': False, 'geometry': None, 'visible': True, 'size': {'width': default_right_width, 'height': default_height}},
            "Classifications": {'area': self.area_to_int[Qt.DockWidgetArea.RightDockWidgetArea], 'floating': False, 'geometry': None, 'visible': True, 'size': {'width': default_right_width, 'height': default_height}},
            "Shapes": {'area': self.area_to_int[Qt.DockWidgetArea.RightDockWidgetArea], 'floating': False, 'geometry': None, 'visible': True, 'size': {'width': default_right_width, 'height': default_height}},
            "main_window": {'size': {'width': 1200, 'height': 800}}  # Default main window size
        }

    def apply_layout(self, layout):
        if 'main_window' in layout and 'size' in layout['main_window']:
            self.resize(layout['main_window']['size']['width'], layout['main_window']['size']['height'])

        for name, settings in layout.items():
            if name == 'main_window':
                continue
            if name in self.dock_widgets:
                dock = self.dock_widgets[name]
                area = self.int_to_area.get(settings.get('area', 0), Qt.DockWidgetArea.NoDockWidgetArea)
                self.addDockWidget(area, dock)
                dock.setFloating(settings.get('floating', False))
                if settings.get('floating') and settings.get('geometry'):
                    dock.setGeometry(*settings['geometry'])
                elif 'size' in settings:
                    dock.resize(settings['size']['width'], settings['size']['height'])
                dock.setVisible(settings.get('visible', True))

        # Adjust dock widget sizes after all docks are added
        for name, settings in layout.items():
            if name == 'main_window':
                continue
            if name in self.dock_widgets and 'size' in settings:
                dock = self.dock_widgets[name]
                area = self.int_to_area.get(settings.get('area', 0), Qt.DockWidgetArea.NoDockWidgetArea)
                if area in [Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea]:
                    self.resizeDocks([dock], [settings['size']['width']], Qt.Orientation.Horizontal)
                elif area in [Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea]:
                    self.resizeDocks([dock], [settings['size']['height']], Qt.Orientation.Vertical)

    def save_workspaces(self):
        serializable_workspaces = {}
        for name, layout in self.workspaces.items():
            serializable_layout = {}
            for key, value in layout.items():
                if isinstance(value, dict) and 'area' in value:
                    # Convert area to int for serialization using area_to_int dictionary
                    value = value.copy()  # Create a copy to avoid modifying the original
                    value['area'] = self.area_to_int.get(value['area'], 0)
                serializable_layout[key] = value
            serializable_workspaces[name] = serializable_layout

        with open('workspaces.yaml', 'w') as f:
            yaml.dump(serializable_workspaces, f)

    def load_workspaces(self):
        try:
            with open('workspaces.yaml', 'r') as f:
                loaded_workspaces = yaml.safe_load(f)

            self.workspaces = {}
            for name, layout in loaded_workspaces.items():
                processed_layout = {}
                for key, value in layout.items():
                    if isinstance(value, dict) and 'area' in value:
                        # Convert area back to Qt.DockWidgetArea
                        value['area'] = self.int_to_area.get(value['area'], Qt.DockWidgetArea.NoDockWidgetArea)
                    processed_layout[key] = value
                self.workspaces[name] = processed_layout

        except FileNotFoundError:
            self.workspaces = {"Default": self.get_default_layout()}
        except yaml.YAMLError as e:
            print(f"Error loading workspaces: {e}")
            self.workspaces = {"Default": self.get_default_layout()}

    def closeEvent(self, event):
        self.save_workspaces()
        if self.image_loader:
            self.image_loader.stop()
            self.image_loader.wait()
        super().closeEvent(event)

    def display_image(self, item):
        if not self.current_directory:
            return

        if self.settings.get('autosave', False) and self.current_image:
            self.save_yolo()

        self.current_image = os.path.basename(item.file_path)
        image_path = item.file_path
        print(f"Attempting to display image: {image_path}")
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", f"Failed to load image: {self.current_image}")
                return
            print(f"Image loaded successfully. Pixmap size: {pixmap.size()}")
            self.image_label.setPixmap(pixmap)
            self.image_label.shapes = []
            self.image_label.current_shape = None
            self.image_label.scale_factor = 1.0  # Reset scale factor
            self.load_yolo_annotations()
            self.file_label.setText(f"File: {self.current_image}")
            self.update_classification_list()
            self.update_shape_list()
            self.update_minimap()
            self.update_minimap_view_rect()
            self.reset_zoom()

            # Add this line to ensure the main view is updated
            self.image_label.update()

            # Force an update of the miniature view
            QTimer.singleShot(100, self.update_minimap_view_rect)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading image {self.current_image}: {str(e)}")
            print(f"Exception in display_image: {str(e)}")

    def add_classification(self):
        new_class, ok = QInputDialog.getText(self, "Add Classification", "Enter new classification:")
        if ok and new_class:
            if new_class not in self.classes:
                self.classes[new_class] = len(self.classes)
                self.update_classification_list()

    def edit_classification(self, index):
        item = self.class_model.itemFromIndex(index)
        old_class = item.text()
        new_class, ok = QInputDialog.getText(self, "Edit Classification", "Enter new classification:", text=old_class)
        if ok and new_class and new_class != old_class:
            del self.classes[old_class]
            self.classes[new_class] = len(self.classes)
            self.update_classification_list()
            self.update_shape_labels(old_class, new_class)
            self.update_shape_list()

    def edit_selected_classification(self):
        selected = self.class_list.selectedIndexes()
        if selected:
            self.edit_classification(selected[0])

    def delete_classification(self):
        selected = self.class_list.selectedIndexes()
        if selected:
            class_to_delete = self.class_model.itemFromIndex(selected[0]).text()
            confirm = QMessageBox.question(self, "Confirm Deletion", f"Are you sure you want to delete the classification '{class_to_delete}'?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                del self.classes[class_to_delete]
                self.update_classification_list()
                self.remove_shape_labels(class_to_delete)

    def apply_classification(self):
        selected_indexes = self.class_list.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select a classification to apply.")
            return

        selected_class = self.class_model.itemFromIndex(selected_indexes[0]).text()

        if self.image_label.selected_shape:
            self.image_label.selected_shape.label = selected_class
            self.image_label.update()
            self.update_shapes()
            if self.settings.get('autosave', False):
                self.save_yolo()
        else:
            QMessageBox.warning(self, "Warning", "Please select a shape on the image first.")

    def update_classification_list(self):
        self.class_model.clear()
        for class_name in sorted(self.classes.keys()):
            item = QStandardItem(class_name)
            self.class_model.appendRow(item)

    def update_shape_list(self):
        print("Entering update_shape_list() method")
        if hasattr(self, 'shape_list'):
            print(f"Shape list exists. Current item count: {self.shape_list.count()}")
            self.shape_list.clear()
            if hasattr(self.image_label, 'shapes'):
                print(f"Number of shapes in image_label: {len(self.image_label.shapes)}")
                for i, shape in enumerate(self.image_label.shapes):
                    shape_type = "Box" if shape.type == 'box' else "Polygon"
                    label = shape.label if shape.label and shape.label != '-1' else "Unlabeled"
                    item = QListWidgetItem(f"{shape_type} {i+1}: {label}")
                    item.setData(Qt.ItemDataRole.UserRole, i)

                    # Set the item color to grey if it's unlabeled
                    if label == "Unlabeled":
                        item.setForeground(QColor(128, 128, 128))  # Grey color

                    self.shape_list.addItem(item)
                    print(f"Added item to shape list: {shape_type} {i+1}: {label}")
            else:
                print("self.image_label.shapes does not exist")
            print(f"Updated shape list with {self.shape_list.count()} shapes")
        else:
            print("self.shape_list does not exist")

    def select_shape_from_list(self):
        selected_items = self.shape_list.selectedItems()
        if selected_items:
            shape_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= shape_index < len(self.image_label.shapes):
                self.image_label.selected_shape = self.image_label.shapes[shape_index]
                self.image_label.update()
                self.setFocus()

    def update_shape_labels(self, old_label, new_label):
        for shape in self.image_label.shapes:
            if shape.label == old_label:
                shape.label = new_label
        self.image_label.update()

    def remove_shape_labels(self, label):
        for shape in self.image_label.shapes:
            if shape.label == label:
                shape.label = ''
        self.image_label.update()

    def zoom_image(self, value):
        scale_factor = value / 100.0
        self.image_label.set_scale_factor(scale_factor)
        self.update_minimap_view_rect()

    def update_zoom_slider(self, scale_factor):
        self.zoom_slider.setValue(int(scale_factor * 100))
        self.update_minimap()

    def reset_zoom(self):
        self.zoom_slider.setValue(100)
        self.image_label.set_scale_factor(1.0)

    def update_minimap(self):
        print("ImageBrowser.update_minimap called")
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            print(f"Updating minimap with pixmap. Size: {self.image_label.pixmap().size()}")
            self.miniature_view.setPixmap(self.image_label.pixmap())
            self.update_minimap_view_rect()
        else:
            print("Clearing minimap due to null pixmap")
            self.miniature_view.setPixmap(QPixmap())  # Set an empty pixmap
            self.miniature_view.set_view_rect(QRectF())

    def update_minimap_view_rect(self):
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            self.miniature_view.set_view_rect(QRectF())
            return

        # Get the size of the entire image
        image_size = self.image_label.pixmap().size()

        # Get the size of the viewport (visible area)
        viewport_size = self.image_scroll_area.viewport().size()

        # Calculate the visible rectangle in the image's coordinate system
        visible_rect = QRectF(
            self.image_scroll_area.horizontalScrollBar().value() / self.image_label.scale_factor,
            self.image_scroll_area.verticalScrollBar().value() / self.image_label.scale_factor,
            viewport_size.width() / self.image_label.scale_factor,
            viewport_size.height() / self.image_label.scale_factor
        )

        # Ensure the visible rect is within the image bounds
        visible_rect = visible_rect.intersected(QRectF(0, 0, image_size.width(), image_size.height()))

        # Calculate the scale factor between the miniature view and the full image
        miniature_scale_x = self.miniature_view.width() / image_size.width()
        miniature_scale_y = self.miniature_view.height() / image_size.height()

        # Scale the visible rect to the miniature view size
        miniature_rect = QRectF(
            visible_rect.x() * miniature_scale_x,
            visible_rect.y() * miniature_scale_y,
            visible_rect.width() * miniature_scale_x,
            visible_rect.height() * miniature_scale_y
        )

        self.miniature_view.set_view_rect(miniature_rect)

    def update_main_view(self, rect):
        if self.image_label.pixmap():
            image_size = self.image_label.pixmap().size()
            x_ratio = rect.x() / self.miniature_view.width()
            y_ratio = rect.y() / self.miniature_view.height()

            x = x_ratio * image_size.width() * self.image_label.scale_factor
            y = y_ratio * image_size.height() * self.image_label.scale_factor

            self.image_scroll_area.horizontalScrollBar().setValue(int(x))
            self.image_scroll_area.verticalScrollBar().setValue(int(y))

    def save_yolo(self):
        if not self.current_image:
            return

        image_path = os.path.join(self.current_directory, self.current_image)
        txt_path = os.path.splitext(image_path)[0] + '.txt'

        had_annotation = os.path.exists(txt_path)

        if not self.image_label.shapes:
            # If there are no shapes and the file exists, delete it
            if had_annotation:
                os.remove(txt_path)
            self.update_image_list_item(self.current_image, False)
            return  # Exit the method early as there's nothing to save

        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        with open(txt_path, 'w') as f:
            for shape in self.image_label.shapes:
                if shape.label and shape.label in self.classes:
                    class_id = self.classes[shape.label]
                else:
                    class_id = -1

                if shape.type == 'box':
                    x1, y1 = shape.points[0].x(), shape.points[0].y()
                    x2, y2 = shape.points[1].x(), shape.points[1].y()
                    x_center = (x1 + x2) / (2 * img_width)
                    y_center = (y1 + y2) / (2 * img_height)
                    width = abs(x2 - x1) / img_width
                    height = abs(y2 - y1) / img_height
                    f.write(f"{class_id} {x_center} {y_center} {width} {height}\n")
                elif shape.type == 'polygon':
                    points = [f"{p.x()/img_width} {p.y()/img_height}" for p in shape.points]
                    f.write(f"{class_id} {' '.join(points)}\n")

        self.save_yaml_classes()
        self.update_image_list_item(self.current_image, True)

    def update_image_list_item(self, image_name, has_annotation):
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if isinstance(item, ImageListItem) and os.path.basename(item.file_path) == image_name:
                if item.has_annotation != has_annotation:
                    item.has_annotation = has_annotation

                    # Get the original icon without any marks
                    original_icon = QIcon(QPixmap(item.file_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

                    # Update the icon
                    if has_annotation:
                        marked_icon = self.add_green_mark(original_icon)
                        item.setIcon(marked_icon)
                    else:
                        item.setIcon(original_icon)

                    # Update visibility based on the "Hide tagged images" checkbox
                    if self.hide_tagged_checkbox.isChecked():
                        item.setHidden(has_annotation)
                    else:
                        item.setHidden(False)

                break

        # Update the tagged image count
        tagged_images = sum(1 for index in range(self.image_list.count())
                            if isinstance(self.image_list.item(index), ImageListItem)
                            and self.image_list.item(index).has_annotation)
        self.tagged_count_label.setText(f"Tagged Images: {tagged_images}")

    def select_model(self):
        model_selector = ModelSelector(self)
        if model_selector.exec():
            model_path = model_selector.get_model_path()
            if model_path:
                self.loadYOLOModel(model_path)
                self.settings['yoloModelPath'] = model_path
                with open('config.yaml', 'w') as f:
                    yaml.dump(self.settings, f)

    def show_status_message(self, message):
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(message)
        else:
            print(message)

    def auto_detect(self):
        if not self.yolo_detector or self.yolo_detector.model is None:
            QMessageBox.warning(self, "Warning", "Please select a valid YOLO model first.")
            return
        if not self.current_image:
            QMessageBox.warning(self, "Warning", "No image selected.")
            return

        image_path = os.path.join(self.current_directory, self.current_image)
        try:
            self.show_status_message("Detecting objects...")
            results = self.yolo_detector.detect(image_path)
            self.show_status_message("Detection complete")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Detection failed: {str(e)}")
            return

        self.image_label.shapes = []

        if results and len(results) > 0:
            result = results[0]

            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    class_id = int(box.cls)
                    label = result.names[class_id]
                    shape = Shape('box', [QPointF(x1, y1), QPointF(x2, y2)])
                    shape.label = label
                    self.image_label.shapes.append(shape)

            if hasattr(result, 'masks') and result.masks is not None:
                for mask in result.masks:
                    if mask.xy and len(mask.xy) > 0:
                        polygon = mask.xy[0].tolist()
                        if len(polygon) > 2:
                            points = [QPointF(x, y) for x, y in polygon]
                            class_id = int(mask.cls) if hasattr(mask, 'cls') else 0
                            label = result.names[class_id]
                            shape = Shape('polygon', points)
                            shape.label = label
                            self.image_label.shapes.append(shape)
                    else:
                        print("Warning: Invalid mask shape detected")

            self.image_label.update()
            self.update_classes(result.names)
            self.update_shapes()
            self.update_shape_list()
        else:
            QMessageBox.information(self, "Info", "No detections found.")

    def update_classes(self, names):
        for class_id, name in names.items():
            if name not in self.classes:
                self.classes[name] = class_id
        self.update_classification_list()

    def load_yaml_classes(self):
        yaml_path = os.path.join(self.current_directory, 'data.yaml')
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                if 'names' in data:
                    names = data['names'] if isinstance(data['names'], list) else data['names'].split(',')
                    self.classes = {name.strip(): i for i, name in enumerate(names)}
                    self.update_classification_list()
                self.yaml_data = data
        else:
            self.yaml_data = {
                'train': '/path/to/train/images',
                'val': '/path/to/valid/images',
                'test': '/path/to/test/images',
                'nc': 0,
                'names': []
            }

    def save_yaml_classes(self):
        yaml_path = os.path.join(self.current_directory, 'data.yaml')

        self.yaml_data['names'] = list(self.classes.keys())
        self.yaml_data['nc'] = len(self.classes)

        yaml_content = "# This config is for running Yolov8 training locally.\n"

        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
            for key, value in self.yaml_data.items():
                if key == 'names':
                    f.write(f"names: {value}\n")
                else:
                    yaml.dump({key: value}, f, default_flow_style=False)

    def load_yolo_annotations(self):
        if not self.current_image:
            return

        image_path = os.path.join(self.current_directory, self.current_image)
        txt_path = os.path.splitext(image_path)[0] + '.txt'

        print(f"Attempting to load YOLO annotations from: {txt_path}")  # Debug print

        if not os.path.exists(txt_path):
            print(f"No annotation file found at {txt_path}")  # Debug print
            return

        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        with open(txt_path, 'r') as f:
            lines = f.readlines()

        print(f"Found {len(lines)} annotations in the file")  # Debug print

        self.image_label.shapes = []
        for line in lines:
            try:
                data = line.strip().split()
                if not data:  # Skip empty lines
                    continue

                class_id = int(data[0])
                if len(data) == 5:  # box
                    x_center, y_center, width, height = map(float, data[1:])
                    x1 = int((x_center - width/2) * img_width)
                    y1 = int((y_center - height/2) * img_height)
                    x2 = int((x_center + width/2) * img_width)
                    y2 = int((y_center + height/2) * img_height)
                    shape = Shape('box', [QPointF(x1, y1), QPointF(x2, y2)])
                elif len(data) > 5:  # polygon
                    points = [QPointF(float(data[i])*img_width, float(data[i+1])*img_height)
                            for i in range(1, len(data), 2)]
                    shape = Shape('polygon', points)
                else:
                    print(f"Warning: Skipping invalid line in annotation file: {line}")
                    continue

                class_name = next((name for name, id in self.classes.items() if id == class_id), str(class_id))
                shape.label = class_name
                self.image_label.shapes.append(shape)
                print(f"Added shape: {shape.type} with label: {shape.label}")  # Debug print
            except Exception as e:
                print(f"Error processing line in annotation file: {line}")
                print(f"Error details: {str(e)}")

        print(f"Loaded {len(self.image_label.shapes)} shapes from annotations")  # Debug print

        self.image_label.update()
        self.update_classification_list()
        print("Calling update_shape_list() from load_yolo_annotations")  # Debug print
        self.update_shape_list()

    def update_shapes(self):
        if self.shape_list:
            self.update_shape_list()
        if self.image_label:
            self.image_label.update()

    def loadSettings(self):
        try:
            with open('config.yaml', 'r') as f:
                self.settings = yaml.safe_load(f)
        except FileNotFoundError:
            self.settings = {}

        # Apply settings
        self.current_directory = self.settings.get('defaultDirectory', '')
        if self.current_directory:
            self.load_images(self.current_directory)

        yolo_model_path = self.settings.get('yoloModelPath', '')
        if yolo_model_path:
            self.loadYOLOModel(yolo_model_path)

    def loadYOLOModel(self, model_path):
        try:
            self.yolo_detector = YOLODetector(model_path)
            if self.yolo_detector.model is None:
                raise ValueError("Failed to initialize YOLO model")
            print(f"YOLO model loaded: {model_path}")
        except Exception as e:
            print(f"Failed to load YOLO model: {str(e)}")
            self.yolo_detector = None

    def openSettings(self):
        dialog = SettingsDialog(self)
        dialog.loadSettings()
        if dialog.exec():
            self.loadSettings()  # Reload settings after dialog is accepted
            self.applySettings()

    def applySettings(self):
        # Apply UI settings
        line_thickness = self.settings.get('lineThickness', 2)
        font_size = self.settings.get('fontSize', 10)

        # Update DrawingArea with new settings
        self.image_label.line_thickness = line_thickness
        self.image_label.font_size = font_size
        self.image_label.update()

    def change_sort_role(self, role):
        role_map = {
            "Name": "name",
            "Date Modified": "date_modified",
            "Date Created": "date_created"
        }
        self.image_list.setSortRole(role_map[role])
        self.image_list.sortItems()

    def change_sort_order(self, order):
        order_map = {
            "Ascending": Qt.SortOrder.AscendingOrder,
            "Descending": Qt.SortOrder.DescendingOrder
        }
        self.image_list.setSortOrder(order_map[order])
        self.image_list.sortItems()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_shape()
        else:
            super().keyPressEvent(event)

    def delete_selected_shape(self):
        if self.image_label.selected_shape:
            self.image_label.shapes.remove(self.image_label.selected_shape)
            self.image_label.selected_shape = None
            self.image_label.update()
            self.image_label.shapes_changed.emit()

            if self.settings.get('autosave', False):
                self.save_yolo()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            if self.image_label.selected_points:
                self.image_label.delete_selected_points()
            elif self.image_label.selected_shape:
                self.delete_selected_shape()
        super().keyPressEvent(event)

    def on_points_deleted(self):
        self.update_shapes()
        if self.settings.get('autosave', False):
            self.save_yolo()

if __name__ == '__main__':
    print("Starting application")
    app = QApplication(sys.argv)
    print("QApplication created")
    ex = ImageBrowser()
    print("ImageBrowser instance created")
    ex.show()
    print("ImageBrowser shown")
    sys.exit(app.exec())
