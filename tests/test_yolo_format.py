"""Tests for YOLO format reading and writing."""

import pytest
from pathlib import Path
import tempfile

from PyQt6.QtCore import QPointF

from annotator_xe.core.yolo_format import (
    YOLOAnnotationReader,
    YOLOAnnotationWriter,
    get_annotation_path,
    has_annotation
)
from annotator_xe.core.models import Shape, ShapeType


class TestYOLOAnnotationReader:
    """Tests for YOLOAnnotationReader."""

    def test_read_empty_file(self):
        """Test reading an empty annotation file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            txt_path.write_text("")

            reader = YOLOAnnotationReader()
            shapes = reader.read(txt_path, 1000, 1000)

            assert shapes == []

    def test_read_box_annotation(self):
        """Test reading bounding box annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            # class_id x_center y_center width height
            txt_path.write_text("0 0.5 0.5 0.2 0.1\n")

            reader = YOLOAnnotationReader({"cat": 0})
            shapes = reader.read(txt_path, 1000, 1000)

            assert len(shapes) == 1
            assert shapes[0].type == ShapeType.BOX
            assert shapes[0].label == "cat"

    def test_read_polygon_annotation(self):
        """Test reading polygon annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            # class_id x1 y1 x2 y2 x3 y3
            txt_path.write_text("1 0.1 0.1 0.2 0.1 0.15 0.2\n")

            reader = YOLOAnnotationReader({"dog": 1})
            shapes = reader.read(txt_path, 1000, 1000)

            assert len(shapes) == 1
            assert shapes[0].type == ShapeType.POLYGON
            assert shapes[0].label == "dog"

    def test_read_multiple_annotations(self):
        """Test reading multiple annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            txt_path.write_text(
                "0 0.5 0.5 0.2 0.1\n"
                "1 0.3 0.3 0.1 0.1\n"
            )

            reader = YOLOAnnotationReader()
            shapes = reader.read(txt_path, 1000, 1000)

            assert len(shapes) == 2

    def test_read_nonexistent_file(self):
        """Test reading from a file that doesn't exist."""
        reader = YOLOAnnotationReader()
        shapes = reader.read(Path("/nonexistent/path.txt"), 1000, 1000)

        assert shapes == []

    def test_set_classes(self):
        """Test setting class mapping."""
        reader = YOLOAnnotationReader()
        reader.set_classes({"cat": 0, "dog": 1})

        assert reader.get_class_name(0) == "cat"
        assert reader.get_class_name(1) == "dog"
        assert reader.get_class_name(99) == "99"  # Unknown class


class TestYOLOAnnotationWriter:
    """Tests for YOLOAnnotationWriter."""

    def test_write_empty_shapes(self):
        """Test writing with no shapes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"

            writer = YOLOAnnotationWriter()
            result = writer.write(txt_path, [], 1000, 1000)

            assert result is True
            assert not txt_path.exists()

    def test_write_box(self):
        """Test writing bounding box annotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(400, 450), QPointF(600, 550)],
                label="cat"
            )

            writer = YOLOAnnotationWriter({"cat": 0})
            result = writer.write(txt_path, [shape], 1000, 1000)

            assert result is True
            assert txt_path.exists()

            content = txt_path.read_text()
            assert content.startswith("0 ")  # class_id 0
            assert "0.5" in content  # x_center

    def test_write_polygon(self):
        """Test writing polygon annotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            shape = Shape(
                type=ShapeType.POLYGON,
                points=[QPointF(100, 100), QPointF(200, 100), QPointF(150, 200)],
                label="dog"
            )

            writer = YOLOAnnotationWriter({"dog": 1})
            result = writer.write(txt_path, [shape], 1000, 1000)

            assert result is True
            content = txt_path.read_text()
            assert content.startswith("1 ")  # class_id 1

    def test_write_unlabeled_shape(self):
        """Test writing shape without label."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(0, 0), QPointF(100, 100)],
                label=""
            )

            writer = YOLOAnnotationWriter()
            result = writer.write(txt_path, [shape], 1000, 1000)

            assert result is True
            content = txt_path.read_text()
            assert content.startswith("-1 ")  # Unknown class

    def test_delete_existing_file_when_empty(self):
        """Test that existing file is deleted when shapes list is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            txt_path.write_text("0 0.5 0.5 0.2 0.1")

            writer = YOLOAnnotationWriter()
            writer.write(txt_path, [], 1000, 1000)

            assert not txt_path.exists()


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_annotation_path(self):
        """Test getting annotation path from image path."""
        image_path = Path("/path/to/image.jpg")
        txt_path = get_annotation_path(image_path)

        assert txt_path == Path("/path/to/image.txt")

    def test_has_annotation(self):
        """Test checking if annotation exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "image.jpg"
            txt_path = Path(tmpdir) / "image.txt"

            # No annotation yet
            assert has_annotation(image_path) is False

            # Create annotation
            txt_path.write_text("0 0.5 0.5 0.1 0.1")
            assert has_annotation(image_path) is True
