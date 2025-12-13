"""Tests for core models."""

import pytest
from PyQt6.QtCore import QPointF

from annotator_xe.core.models import Shape, ShapeType, Annotation


class TestShape:
    """Tests for the Shape class."""

    def test_create_box(self):
        """Test creating a bounding box shape."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 10), QPointF(100, 100)],
            label="test"
        )

        assert shape.type == ShapeType.BOX
        assert len(shape.points) == 2
        assert shape.label == "test"
        assert shape.selected is False
        assert shape.color is not None

    def test_create_polygon(self):
        """Test creating a polygon shape."""
        points = [QPointF(0, 0), QPointF(100, 0), QPointF(50, 100)]
        shape = Shape(
            type=ShapeType.POLYGON,
            points=points,
            label="polygon"
        )

        assert shape.type == ShapeType.POLYGON
        # Polygon should be closed automatically
        assert len(shape.points) == 4
        assert shape.points[0] == shape.points[-1]
        assert shape.label == "polygon"

    def test_polygon_auto_close(self):
        """Test that polygons are automatically closed."""
        points = [QPointF(0, 0), QPointF(100, 0), QPointF(50, 100)]
        shape = Shape(type=ShapeType.POLYGON, points=points)

        assert shape.points[0] == shape.points[-1]

    def test_move_by(self):
        """Test moving shape by delta."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 10), QPointF(100, 100)]
        )

        shape.move_by(QPointF(5, 5))

        assert shape.points[0].x() == 15
        assert shape.points[0].y() == 15
        assert shape.points[1].x() == 105
        assert shape.points[1].y() == 105

    def test_move_point(self):
        """Test moving a single point."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 10), QPointF(100, 100)]
        )

        result = shape.move_point(0, QPointF(20, 20))

        assert result is True
        assert shape.points[0].x() == 20
        assert shape.points[0].y() == 20

    def test_move_point_invalid_index(self):
        """Test moving point with invalid index."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 10), QPointF(100, 100)]
        )

        result = shape.move_point(10, QPointF(20, 20))

        assert result is False

    def test_remove_point_polygon(self):
        """Test removing a point from a polygon."""
        points = [
            QPointF(0, 0),
            QPointF(100, 0),
            QPointF(100, 100),
            QPointF(0, 100)
        ]
        shape = Shape(type=ShapeType.POLYGON, points=points)

        initial_count = len(shape.points)
        result = shape.remove_point(1)

        assert result is True
        assert len(shape.points) == initial_count - 1

    def test_remove_point_box_fails(self):
        """Test that removing points from box fails."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 10), QPointF(100, 100)]
        )

        result = shape.remove_point(0)

        assert result is False

    def test_get_bounding_rect(self):
        """Test getting bounding rectangle."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(10, 20), QPointF(110, 120)]
        )

        x, y, w, h = shape.get_bounding_rect()

        assert x == 10
        assert y == 20
        assert w == 100
        assert h == 100

    def test_to_yolo_box(self):
        """Test converting box to YOLO format."""
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(100, 100), QPointF(300, 200)]
        )

        x_center, y_center, width, height = shape.to_yolo_box(1000, 1000)

        assert x_center == 0.2  # (100 + 300) / 2 / 1000
        assert y_center == 0.15  # (100 + 200) / 2 / 1000
        assert width == 0.2  # 200 / 1000
        assert height == 0.1  # 100 / 1000

    def test_to_yolo_polygon(self):
        """Test converting polygon to YOLO format."""
        points = [QPointF(100, 100), QPointF(200, 100), QPointF(150, 200)]
        shape = Shape(type=ShapeType.POLYGON, points=points)

        coords = shape.to_yolo_polygon(1000, 1000)

        assert coords[0] == (0.1, 0.1)
        assert coords[1] == (0.2, 0.1)
        assert coords[2] == (0.15, 0.2)

    def test_from_yolo_box(self):
        """Test creating box from YOLO format."""
        shape = Shape.from_yolo_box(
            class_id=0,
            x_center=0.5,
            y_center=0.5,
            width=0.2,
            height=0.1,
            img_width=1000,
            img_height=1000,
            label="test"
        )

        assert shape.type == ShapeType.BOX
        assert shape.label == "test"
        assert len(shape.points) == 2

    def test_from_yolo_polygon(self):
        """Test creating polygon from YOLO format."""
        coords = [0.1, 0.1, 0.2, 0.1, 0.15, 0.2]
        shape = Shape.from_yolo_polygon(
            class_id=0,
            coordinates=coords,
            img_width=1000,
            img_height=1000,
            label="poly"
        )

        assert shape.type == ShapeType.POLYGON
        assert shape.label == "poly"

    def test_random_color_generation(self):
        """Test that colors are generated."""
        shape1 = Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)])
        shape2 = Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)])

        assert shape1.color is not None
        assert shape2.color is not None
        # Colors are random, so they may or may not be different


class TestAnnotation:
    """Tests for the Annotation class."""

    def test_create_annotation(self):
        """Test creating an annotation."""
        annotation = Annotation(image_path="/path/to/image.jpg")

        assert annotation.image_path == "/path/to/image.jpg"
        assert len(annotation.shapes) == 0

    def test_add_shape(self):
        """Test adding a shape to annotation."""
        annotation = Annotation(image_path="/path/to/image.jpg")
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(0, 0), QPointF(100, 100)]
        )

        annotation.add_shape(shape)

        assert len(annotation.shapes) == 1
        assert annotation.shapes[0] == shape

    def test_remove_shape(self):
        """Test removing a shape from annotation."""
        annotation = Annotation(image_path="/path/to/image.jpg")
        shape = Shape(
            type=ShapeType.BOX,
            points=[QPointF(0, 0), QPointF(100, 100)]
        )
        annotation.add_shape(shape)

        removed = annotation.remove_shape(0)

        assert removed == shape
        assert len(annotation.shapes) == 0

    def test_remove_shape_invalid_index(self):
        """Test removing shape with invalid index."""
        annotation = Annotation(image_path="/path/to/image.jpg")

        removed = annotation.remove_shape(10)

        assert removed is None

    def test_clear(self):
        """Test clearing all shapes."""
        annotation = Annotation(image_path="/path/to/image.jpg")
        annotation.add_shape(Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)]))
        annotation.add_shape(Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)]))

        annotation.clear()

        assert len(annotation.shapes) == 0

    def test_box_count(self):
        """Test counting box annotations."""
        annotation = Annotation(image_path="/path/to/image.jpg")
        annotation.add_shape(Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)]))
        annotation.add_shape(Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(1, 1)]))
        annotation.add_shape(
            Shape(type=ShapeType.POLYGON, points=[QPointF(0, 0), QPointF(1, 0), QPointF(0.5, 1)])
        )

        assert annotation.box_count == 2
        assert annotation.polygon_count == 1
