"""Tests for Pascal VOC format reading and writing."""

import pytest
from pathlib import Path
import tempfile

from PyQt6.QtCore import QPointF

from annotator_xe.core.pascal_voc_format import PascalVOCAnnotationFormat
from annotator_xe.core.models import Shape, ShapeType


class TestPascalVOCAnnotationFormat:
    """Tests for PascalVOCAnnotationFormat."""

    def test_format_properties(self):
        """Test format properties."""
        handler = PascalVOCAnnotationFormat()
        assert handler.format_name == "pascal_voc"
        assert handler.is_per_image is True
        assert handler.file_extension == ".xml"
        assert handler.supports_polygons is False

    def test_read_empty_directory(self):
        """Test reading from directory with no XML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = PascalVOCAnnotationFormat()
            image_path = Path(tmpdir) / "test.jpg"
            shapes = handler.read_image(image_path, 1000, 1000)
            assert shapes == []

    def test_write_and_read_box(self):
        """Test writing and reading a bounding box."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(300, 300)],
                label="cat"
            )

            handler = PascalVOCAnnotationFormat({"cat": 0})

            # Write
            result = handler.write_image(image_path, [shape], 1000, 1000)
            assert result is True

            xml_path = image_path.with_suffix(".xml")
            assert xml_path.exists()

            # Read back
            shapes = handler.read_image(image_path, 1000, 1000)
            assert len(shapes) == 1
            assert shapes[0].type == ShapeType.BOX
            assert shapes[0].label == "cat"

            # Check coordinates (Pascal VOC uses integer coordinates)
            assert int(shapes[0].points[0].x()) == 100
            assert int(shapes[0].points[0].y()) == 100
            assert int(shapes[0].points[1].x()) == 300
            assert int(shapes[0].points[1].y()) == 300

    def test_write_multiple_boxes(self):
        """Test writing multiple bounding boxes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            shapes = [
                Shape(
                    type=ShapeType.BOX,
                    points=[QPointF(100, 100), QPointF(200, 200)],
                    label="cat"
                ),
                Shape(
                    type=ShapeType.BOX,
                    points=[QPointF(300, 300), QPointF(400, 400)],
                    label="dog"
                ),
            ]

            handler = PascalVOCAnnotationFormat({"cat": 0, "dog": 1})
            handler.write_image(image_path, shapes, 1000, 1000)

            read_shapes = handler.read_image(image_path, 1000, 1000)
            assert len(read_shapes) == 2

    def test_polygon_converted_to_box(self):
        """Test that polygons are converted to bounding boxes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            # Create a triangle polygon
            shape = Shape(
                type=ShapeType.POLYGON,
                points=[QPointF(100, 100), QPointF(200, 100), QPointF(150, 200)],
                label="triangle"
            )

            handler = PascalVOCAnnotationFormat()
            handler.write_image(image_path, [shape], 1000, 1000)

            # Read back - should be a box
            shapes = handler.read_image(image_path, 1000, 1000)
            assert len(shapes) == 1
            assert shapes[0].type == ShapeType.BOX
            assert shapes[0].label == "triangle"

            # Bounding box should encompass the polygon
            xmin = int(shapes[0].points[0].x())
            ymin = int(shapes[0].points[0].y())
            xmax = int(shapes[0].points[1].x())
            ymax = int(shapes[0].points[1].y())

            assert xmin == 100
            assert ymin == 100
            assert xmax == 200
            assert ymax == 200

    def test_empty_shapes_deletes_file(self):
        """Test that writing empty shapes deletes existing XML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"
            xml_path = image_path.with_suffix(".xml")

            # Create initial annotation
            handler = PascalVOCAnnotationFormat()
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(200, 200)],
                label="cat"
            )
            handler.write_image(image_path, [shape], 1000, 1000)
            assert xml_path.exists()

            # Write empty shapes
            handler.write_image(image_path, [], 1000, 1000)
            assert not xml_path.exists()

    def test_has_annotation(self):
        """Test checking if annotation exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            handler = PascalVOCAnnotationFormat()

            # No annotation yet
            assert handler.has_annotation(image_path) is False

            # Create annotation
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(200, 200)],
                label="cat"
            )
            handler.write_image(image_path, [shape], 1000, 1000)

            assert handler.has_annotation(image_path) is True

    def test_get_annotation_path(self):
        """Test getting annotation path."""
        handler = PascalVOCAnnotationFormat()
        image_path = Path("/path/to/image.jpg")
        xml_path = handler.get_annotation_path(image_path)
        assert xml_path == Path("/path/to/image.xml")

    def test_get_classes_from_directory(self):
        """Test extracting classes from XML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            handler = PascalVOCAnnotationFormat()
            shapes = [
                Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(100, 100)], label="cat"),
                Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(100, 100)], label="dog"),
            ]
            handler.write_image(image_path, shapes, 1000, 1000)

            classes = handler.get_classes_from_directory(Path(tmpdir))
            assert "cat" in classes
            assert "dog" in classes
