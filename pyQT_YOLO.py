import sys
import os
import yaml
import torch
from ultralytics import YOLO
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QListWidget, QHBoxLayout, QWidget, QLabel,
                             QVBoxLayout, QToolBar, QStatusBar, QListView, QPushButton, QSplitter, QMessageBox,
                             QMenu, QInputDialog, QDialog, QScrollArea, QListWidgetItem, QAbstractItemView, QSlider,
                             QTabWidget, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox, QComboBox)
from PyQt6.QtGui import (QPixmap, QIcon, QPainter, QColor, QPen, QFont, QPainterPath, QPolygonF, QAction, QPalette,
                         QActionGroup, QCursor, QImageReader, QStandardItemModel, QStandardItem, QFontMetrics)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, pyqtSignal, QPoint, QRect, QFileInfo
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

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

    @staticmethod
    def generate_random_color():
        return QColor.fromHsv(torch.randint(0, 360, (1,)).item(), 255, 255, 128)

class DrawingArea(QLabel):
    view_changed = pyqtSignal(QRect)
    zoom_changed = pyqtSignal(float)
    classification_changed = pyqtSignal(str)
    shapes_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
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

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self.set_scale_factor(self.scale_factor * 1.1)

    def zoom_out(self):
        self.set_scale_factor(self.scale_factor / 1.1)

    def set_scroll_area(self, scroll_area):
        self.scroll_area = scroll_area

    def set_scale_factor(self, factor):
        self.scale_factor = factor
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

    def mousePressEvent(self, event):
        self.setFocus()
        pos = self.transform_pos(event.position())

        if event.button() == Qt.MouseButton.RightButton:
            self.finish_drawing()
            return

        if self.panning:
            self.pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.current_tool == 'polygon':
            if not self.drawing:
                if self.hover_edge:
                    self.insert_point_to_polygon(pos)
                else:
                    self.drawing = True
                    self.current_shape = Shape('polygon', [pos])
            else:
                self.current_shape.points.append(pos)
        elif self.current_tool == 'select':
            self.handle_select_tool(pos)
        elif self.current_tool == 'move':
            self.handle_move_tool(pos)
        elif self.current_tool == 'box':
            self.drawing = True
            self.start_point = pos
            self.current_shape = Shape('box', [self.start_point, self.start_point])
        self.update()

    def mouseMoveEvent(self, event):
        pos = self.transform_pos(event.position())
        if self.panning:
            delta = event.position().toPoint() - self.pan_start
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y())
            self.pan_start = event.position().toPoint()
            self.update_minimap()
            return

        if self.drawing:
            if self.current_tool == 'box':
                self.current_shape.points[1] = pos
            elif self.current_tool == 'polygon':
                if len(self.current_shape.points) > 0:
                    self.current_shape.points[-1] = pos
        elif self.current_tool == 'select':
            if self.resize_handle:
                self.resize_box(pos)
            elif self.moving_point:
                self.move_polygon_point(pos)
            elif self.moving_shape:
                self.move_shape(pos)
        self.update_hover(pos)
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
            elif self.current_tool == 'polygon':
                if len(self.current_shape.points) > 2 and (pos - self.current_shape.points[0]).manhattanLength() < 20 / self.scale_factor:
                    self.current_shape.points.pop()
                    self.shapes.append(self.current_shape)
                    self.current_shape = None
                    self.drawing = False
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

        # Draw hover effects
        if self.hover_point:
            shape, index = self.hover_point
            point = shape.points[index]
            painter.setBrush(QColor(255, 0, 0, 128))
            painter.drawEllipse(point, 5 / self.scale_factor, 5 / self.scale_factor)
        elif self.hover_edge:
            shape, index = self.hover_edge
            p1 = shape.points[index]
            p2 = shape.points[(index + 1) % len(shape.points)]
            painter.setPen(QPen(QColor(255, 0, 0, 128), 2 / self.scale_factor))
            painter.drawLine(p1, p2)

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

    def handle_select_tool(self, pos):
        self.resize_handle = None
        self.moving_point = None
        self.moving_shape = False

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
                point = self.get_nearest_point(shape, pos)
                if (point - pos).manhattanLength() < 10 / self.scale_factor:
                    self.moving_point = point
                    shape.selected = True
                    self.selected_shape = shape
                    return

            if self.shape_contains_point(shape, pos):
                self.moving_shape = True
                shape.selected = True
                self.selected_shape = shape
                self.move_start_point = pos
                return

        self.selected_shape = None
        self.update()

    def handle_move_tool(self, pos):
        for shape in self.shapes:
            if self.shape_contains_point(shape, pos):
                self.selected_shape = shape
                self.moving_shape = True
                self.move_start_point = pos
                break

    def move_shape(self, pos):
        if self.selected_shape and self.move_start_point != QPointF():
            delta = pos - self.move_start_point
            for point in self.selected_shape.points:
                point += delta
            self.move_start_point = pos

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
            self.selected_shape.points[index] = pos
            self.moving_point = pos
            self.update()

    def get_nearest_point(self, shape, point):
        return min(shape.points, key=lambda p: (p - point).manhattanLength())

    def shape_contains_point(self, shape, point):
        if shape.type == 'box':
            return QRectF(shape.points[0], shape.points[1]).normalized().contains(point)
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
        elif event.key() == Qt.Key.Key_Delete:
            if self.selected_shape:
                self.shapes.remove(self.selected_shape)
                self.selected_shape = None
                self.update()
                self.shapes_changed.emit()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def finish_drawing(self):
        if self.current_shape and self.current_shape.type == 'polygon' and len(self.current_shape.points) > 2:
            self.shapes.append(self.current_shape)
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

class MiniatureView(QLabel):
    view_rect_changed = pyqtSignal(QRectF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setMaximumSize(200, 200)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.view_rect = QRectF()
        self.dragging = False
        self.start_pos = QPointF()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap():
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
    def __init__(self, text, icon, file_path):
        super().__init__(icon, text)
        self.file_path = file_path
        self.file_info = QFileInfo(file_path)
        self.setSizeHint(QSize(100, 100))

    def __lt__(self, other):
        if not isinstance(other, ImageListItem):
            return super().__lt__(other)

        sort_role = self.listWidget().sort_role
        if sort_role == "name":
            return self.text().lower() < other.text().lower()
        elif sort_role == "date_modified":
            return self.file_info.lastModified() < other.file_info.lastModified()
        elif sort_role == "date_created":
            return self.file_info.birthTime() < other.file_info.birthTime()
        else:
            return super().__lt__(other)

class SortableImageList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sort_role = "name"
        self.sort_order = Qt.SortOrder.AscendingOrder

    def setSortRole(self, role):
        self.sort_role = role
        self.sortItems()

    def setSortOrder(self, order):
        self.sort_order = order
        self.sortItems()

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
        increase_image_allocation_limit()
        self.current_directory = ""
        self.current_image = ""
        self.classes = {}
        self.yaml_data = {}
        self.yolo_detector = None
        self.zoom_slider = None
        self.miniature_view = None
        self.settings = {}
        self.image_loader = None
        self.loadSettings()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Modern Image Annotator')
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        main_layout = QHBoxLayout()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_pane = self.create_left_pane()
        self.image_scroll_area = QScrollArea()
        self.image_label = DrawingArea()
        self.image_label.set_scroll_area(self.image_scroll_area)
        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)
        self.image_label.view_changed.connect(self.update_minimap_view_rect)
        self.image_label.zoom_changed.connect(self.update_zoom_slider)
        self.image_label.classification_changed.connect(self.handle_classification_change)
        self.image_label.shapes_changed.connect(self.update_shapes)
        right_pane = self.create_right_pane()

        splitter.addWidget(left_pane)
        splitter.addWidget(self.image_scroll_area)
        splitter.addWidget(right_pane)

        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.dir_label = QLabel()

        self.statusBar.addPermanentWidget(self.dir_label)
        self.file_label = QLabel()
        self.statusBar.addPermanentWidget(self.file_label)

        self.create_zoom_controls()

        # Create toolbar after image_label is initialized
        self.create_toolbar()

    def create_left_pane(self):
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)

        # Add "Images:" label
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

        left_pane.setMinimumWidth(200)
        left_pane.setMaximumWidth(300)
        return left_pane

    def create_right_pane(self):
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)

        self.miniature_view = MiniatureView(self)
        self.miniature_view.view_rect_changed.connect(self.update_main_view)
        right_layout.addWidget(self.miniature_view)

        self.class_list = QListView()
        self.class_model = QStandardItemModel()
        self.class_list.setModel(self.class_model)
        self.class_list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.class_list.doubleClicked.connect(self.edit_classification)

        right_layout.addWidget(QLabel("Classifications:"))
        right_layout.addWidget(self.class_list)

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

        right_layout.addWidget(class_toolbar)

        apply_button = QPushButton("Apply Classification")
        apply_button.clicked.connect(self.apply_classification)
        right_layout.addWidget(apply_button)

        right_layout.addWidget(QLabel("Shapes:"))
        self.shape_list = QListWidget()
        self.shape_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.shape_list.itemSelectionChanged.connect(self.select_shape_from_list)
        right_layout.addWidget(self.shape_list)

        right_pane.setMinimumWidth(200)
        right_pane.setMaximumWidth(300)

        return right_pane

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

        move_action = QAction(self.create_icon('✋'), 'Move', self)
        move_action.setCheckable(True)
        move_action.triggered.connect(lambda: self.set_drawing_tool('move'))
        drawing_tools.addAction(move_action)

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
        self.set_drawing_tool('select')

    def handle_classification_change(self, new_label):
        if new_label not in self.classes:
            self.classes[new_label] = len(self.classes)
        self.update_classification_list()

    def create_zoom_controls(self):
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(zoom_widget)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 500)  # 10% to 500% zoom
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.zoom_image)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.clicked.connect(self.image_label.zoom_in)

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.clicked.connect(self.image_label.zoom_out)

        reset_zoom_btn = QPushButton("Reset")
        reset_zoom_btn.clicked.connect(self.reset_zoom)

        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addWidget(reset_zoom_btn)

        self.statusBar.addPermanentWidget(zoom_widget)

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
            painter.setPen(Qt.GlobalColor.white)  # Use white color for dark mode
        else:
            painter.setPen(Qt.GlobalColor.black)  # Use black color for light mode

        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        return QIcon(pixmap)

    def set_drawing_tool(self, tool):
        self.image_label.current_tool = tool
        if tool != 'polygon':
            self.image_label.finish_drawing()
        self.statusBar.showMessage(f"Current tool: {tool.capitalize()}")

    def open_directory(self):
        new_directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if new_directory:
            self.reset_ui()
            self.current_directory = new_directory
            self.load_images(self.current_directory)
            self.load_yaml_classes()
            self.dir_label.setText(f"Directory: {self.current_directory}")

    def reset_ui(self):
        self.current_image = ""
        self.classes = {}
        self.image_label.clear()
        self.image_label.shapes = []
        self.image_label.current_shape = None
        self.image_list.clear()
        self.class_model.clear()
        self.file_label.setText("")
        self.miniature_view.clear()  # Clear the miniature view
        self.miniature_view.set_view_rect(QRectF())  # Reset the view rectangle
        self.reset_zoom()

    def load_images(self, dir_path):
        self.image_list.clear()
        self.statusBar.showMessage("Loading images...")

        # Get the list of files in the directory
        file_list = os.listdir(dir_path)

        # Create and start the image loader thread
        self.image_loader = ImageLoader(dir_path, file_list)
        self.image_loader.image_loaded.connect(self.add_image_to_list)
        self.image_loader.finished.connect(self.image_loading_finished)
        self.image_loader.start()

    def add_image_to_list(self, filename, icon):
        file_path = os.path.join(self.current_directory, filename)
        item = ImageListItem(filename, icon, file_path)
        self.image_list.addItem(item)

    def image_loading_finished(self):
        self.statusBar.showMessage("Image loading complete")
        self.image_list.sortItems()
        self.image_loader = None

    def closeEvent(self, event):
        if self.image_loader:
            self.image_loader.stop()
            self.image_loader.wait()
        super().closeEvent(event)

    def display_image(self, item):
        if not self.current_directory:
            return

        # Check if autosave is enabled and if there's a current image
        if self.settings.get('autosave', False) and self.current_image:
            self.save_yolo()  # Save the current image annotations before loading the new one

        self.current_image = item.text()
        image_path = os.path.join(self.current_directory, self.current_image)
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", f"Failed to load image: {self.current_image}")
                return
            self.image_label.setPixmap(pixmap)
            self.image_label.shapes = []
            self.image_label.current_shape = None
            self.load_yolo_annotations()
            self.file_label.setText(f"File: {self.current_image}")
            self.update_classification_list()
            self.update_shape_list()  # Update the shape list
            self.update_minimap()
            self.reset_zoom()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading image {self.current_image}: {str(e)}")

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
            self.update_shapes()  # Update shapes after applying classification
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
        self.shape_list.clear()
        for i, shape in enumerate(self.image_label.shapes):
            shape_type = "Box" if shape.type == 'box' else "Polygon"
            label = shape.label if shape.label else "Unlabeled"
            item = QListWidgetItem(f"{shape_type} {i+1}: {label}")
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store the index of the shape
            self.shape_list.addItem(item)

    def select_shape_from_list(self):
        selected_items = self.shape_list.selectedItems()
        if selected_items:
            shape_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if 0 <= shape_index < len(self.image_label.shapes):
                self.image_label.selected_shape = self.image_label.shapes[shape_index]
                self.image_label.update()
                self.setFocus()  # Set focus to the ImageBrowser to receive key events

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

    def update_zoom_slider(self, scale_factor):
        self.zoom_slider.setValue(int(scale_factor * 100))
        self.update_minimap()

    def reset_zoom(self):
        self.zoom_slider.setValue(100)
        self.image_label.set_scale_factor(1.0)

    def update_minimap(self):
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            scaled_pixmap = self.image_label.pixmap().scaled(
                self.miniature_view.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.miniature_view.setPixmap(scaled_pixmap)
            self.update_minimap_view_rect()
        else:
            self.miniature_view.clear()
            self.miniature_view.set_view_rect(QRectF())

    def update_minimap_view_rect(self):
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            viewport_rect = self.image_scroll_area.viewport().rect()
            viewport_rect.translate(
                self.image_scroll_area.horizontalScrollBar().value(),
                self.image_scroll_area.verticalScrollBar().value()
            )
            if self.image_label.width() > 0 and self.image_label.height() > 0:
                scaled_rect = QRectF(
                    viewport_rect.x() * self.miniature_view.width() / self.image_label.width(),
                    viewport_rect.y() * self.miniature_view.height() / self.image_label.height(),
                    viewport_rect.width() * self.miniature_view.width() / self.image_label.width(),
                    viewport_rect.height() * self.miniature_view.height() / self.image_label.height()
                )
                self.miniature_view.set_view_rect(scaled_rect)
        else:
            self.miniature_view.set_view_rect(QRectF())

    def update_main_view(self, rect):
        if self.image_label.pixmap():
            x = rect.x() * self.image_label.width() / self.miniature_view.width()
            y = rect.y() * self.image_label.height() / self.miniature_view.height()
            self.image_scroll_area.horizontalScrollBar().setValue(int(x))
            self.image_scroll_area.verticalScrollBar().setValue(int(y))

    def save_yolo(self):
        if not self.current_image:
            return  # Silently return if there's no current image

        image_path = os.path.join(self.current_directory, self.current_image)
        txt_path = os.path.splitext(image_path)[0] + '.txt'

        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        with open(txt_path, 'w') as f:
            for shape in self.image_label.shapes:
                if shape.label and shape.label in self.classes:
                    class_id = self.classes[shape.label]
                else:
                    # Use -1 as class_id for unclassified shapes
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

    def select_model(self):
        model_selector = ModelSelector(self)
        if model_selector.exec():
            model_path = model_selector.get_model_path()
            if model_path:
                self.loadYOLOModel(model_path)
                # Update settings
                self.settings['yoloModelPath'] = model_path
                with open('config.yaml', 'w') as f:
                    yaml.dump(self.settings, f)

    def auto_detect(self):
        if not self.yolo_detector or self.yolo_detector.model is None:
            QMessageBox.warning(self, "Warning", "Please select a valid YOLO model first.")
            return
        if not self.current_image:
            QMessageBox.warning(self, "Warning", "No image selected.")
            return

        image_path = os.path.join(self.current_directory, self.current_image)
        try:
            results = self.yolo_detector.detect(image_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Detection failed: {str(e)}")
            return

        # Clear existing shapes before adding new ones
        self.image_label.shapes = []

        # Process only the first result (assuming single image input)
        if results and len(results) > 0:
            result = results[0]

            # Handle bounding boxes
            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    class_id = int(box.cls)
                    label = result.names[class_id]
                    shape = Shape('box', [QPointF(x1, y1), QPointF(x2, y2)])
                    shape.label = label
                    self.image_label.shapes.append(shape)

            # Handle segmentation masks
            if hasattr(result, 'masks') and result.masks is not None:
                for mask in result.masks:
                    # Check if the mask has a valid shape
                    if mask.xy and len(mask.xy) > 0:
                        polygon = mask.xy[0].tolist()
                        if len(polygon) > 2:  # Ensure we have at least 3 points for a valid polygon
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
                    # Handle both list and individual item formats
                    names = data['names'] if isinstance(data['names'], list) else data['names'].split(',')
                    self.classes = {name.strip(): i for i, name in enumerate(names)}
                    self.update_classification_list()
                # Store directory information
                self.yaml_data = data
        else:
            # Create default data if no YAML file exists
            self.yaml_data = {
                'train': '/path/to/train/images',
                'val': '/path/to/valid/images',
                'test': '/path/to/test/images',
                'nc': 0,
                'names': []
            }

    def save_yaml_classes(self):
        yaml_path = os.path.join(self.current_directory, 'data.yaml')

        # Update class information
        self.yaml_data['names'] = list(self.classes.keys())
        self.yaml_data['nc'] = len(self.classes)

        # Add a comment at the top of the file
        yaml_content = "# This config is for running Yolov8 training locally.\n"

        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
            # Custom dumping to ensure 'names' is on a single line
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

        if not os.path.exists(txt_path):
            return

        img_width = self.image_label.pixmap().width()
        img_height = self.image_label.pixmap().height()

        with open(txt_path, 'r') as f:
            lines = f.readlines()

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
            except Exception as e:
                print(f"Error processing line in annotation file: {line}")
                print(f"Error details: {str(e)}")

        self.image_label.update()
        self.update_classification_list()
        self.update_shape_list()

    def update_shapes(self):
        self.update_shape_list()
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

    def change_sort_order(self, order):
        order_map = {
            "Ascending": Qt.SortOrder.AscendingOrder,
            "Descending": Qt.SortOrder.DescendingOrder
        }
        self.image_list.setSortOrder(order_map[order])

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
            self.update_shapes()
            if self.settings.get('autosave', False):
                self.save_yolo()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ImageBrowser()
    ex.show()
    sys.exit(app.exec())
