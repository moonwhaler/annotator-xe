"""Tests for CreateML format reading and writing."""

import json
import pytest
from pathlib import Path
import tempfile

from PyQt6.QtCore import QPointF

from annotator_xe.core.createml_format import CreateMLAnnotationFormat
from annotator_xe.core.models import Shape, ShapeType


class TestCreateMLAnnotationFormat:
    """Tests for CreateMLAnnotationFormat."""

    def test_format_properties(self):
        """Test format properties."""
        handler = CreateMLAnnotationFormat()
        assert handler.format_name == "createml"
        assert handler.is_per_image is False
        assert handler.file_extension == ".json"
        assert handler.supports_polygons is False

    def test_read_empty_directory(self):
        """Test reading from directory with no CreateML JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = CreateMLAnnotationFormat()
            annotations = handler.load_directory(Path(tmpdir))
            assert annotations == {}

    def test_write_and_read_box(self):
        """Test writing and reading a bounding box."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(300, 300)],
                label="cat"
            )

            handler = CreateMLAnnotationFormat({"cat": 0})

            # Write
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            result = handler.save_directory(Path(tmpdir), annotations, image_sizes)
            assert result is True

            # Verify JSON file exists
            json_path = Path(tmpdir) / "_annotations.createml.json"
            assert json_path.exists()

            # Read back
            handler2 = CreateMLAnnotationFormat()
            loaded = handler2.load_directory(Path(tmpdir))
            assert "test.jpg" in loaded
            assert len(loaded["test.jpg"]) == 1
            assert loaded["test.jpg"][0].type == ShapeType.BOX
            assert loaded["test.jpg"][0].label == "cat"

    def test_center_coordinates(self):
        """Test CreateML uses center coordinates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Box from (100, 100) to (300, 300)
            # Center should be (200, 200), size 200x200
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(300, 300)],
                label="cat"
            )

            handler = CreateMLAnnotationFormat()
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read raw JSON
            json_path = Path(tmpdir) / "_annotations.createml.json"
            with open(json_path) as f:
                data = json.load(f)

            coords = data[0]["annotations"][0]["coordinates"]
            assert coords["x"] == 200  # center x
            assert coords["y"] == 200  # center y
            assert coords["width"] == 200
            assert coords["height"] == 200

    def test_polygon_converted_to_box(self):
        """Test that polygons are converted to bounding boxes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a triangle polygon
            shape = Shape(
                type=ShapeType.POLYGON,
                points=[QPointF(100, 100), QPointF(200, 100), QPointF(150, 200)],
                label="triangle"
            )

            handler = CreateMLAnnotationFormat()
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read back - should be a box (only boxes in CreateML)
            handler2 = CreateMLAnnotationFormat()
            loaded = handler2.load_directory(Path(tmpdir))
            assert "test.jpg" in loaded
            assert len(loaded["test.jpg"]) == 1
            assert loaded["test.jpg"][0].type == ShapeType.BOX

    def test_write_multiple_images(self):
        """Test writing annotations for multiple images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            annotations = {
                "image1.jpg": [
                    Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(100, 100)], label="cat")
                ],
                "image2.jpg": [
                    Shape(type=ShapeType.BOX, points=[QPointF(50, 50), QPointF(150, 150)], label="dog")
                ],
            }
            image_sizes = {
                "image1.jpg": (1000, 1000),
                "image2.jpg": (800, 600),
            }

            handler = CreateMLAnnotationFormat()
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Verify JSON structure
            json_path = Path(tmpdir) / "_annotations.createml.json"
            with open(json_path) as f:
                data = json.load(f)

            assert len(data) == 2
            image_names = [entry["image"] for entry in data]
            assert "image1.jpg" in image_names
            assert "image2.jpg" in image_names

    def test_read_image_from_cache(self):
        """Test reading single image uses cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(200, 200)],
                label="cat"
            )

            handler = CreateMLAnnotationFormat()
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read using read_image (should load directory first)
            handler2 = CreateMLAnnotationFormat()
            shapes = handler2.read_image(image_path, 1000, 1000)
            assert len(shapes) == 1
            assert shapes[0].label == "cat"

    def test_has_annotation(self):
        """Test checking if image has annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = CreateMLAnnotationFormat()

            annotations = {"test.jpg": [
                Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(100, 100)], label="cat")
            ]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            image_with_ann = Path(tmpdir) / "test.jpg"
            image_without_ann = Path(tmpdir) / "other.jpg"

            assert handler.has_annotation(image_with_ann) is True
            assert handler.has_annotation(image_without_ann) is False

    def test_get_classes_from_directory(self):
        """Test extracting classes from CreateML JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a CreateML JSON manually
            createml_data = [
                {
                    "image": "test1.jpg",
                    "annotations": [
                        {"label": "cat", "coordinates": {"x": 50, "y": 50, "width": 100, "height": 100}},
                        {"label": "dog", "coordinates": {"x": 150, "y": 150, "width": 100, "height": 100}},
                    ]
                },
                {
                    "image": "test2.jpg",
                    "annotations": [
                        {"label": "bird", "coordinates": {"x": 50, "y": 50, "width": 50, "height": 50}},
                    ]
                }
            ]
            json_path = Path(tmpdir) / "_annotations.createml.json"
            with open(json_path, "w") as f:
                json.dump(createml_data, f)

            handler = CreateMLAnnotationFormat()
            classes = handler.get_classes_from_directory(Path(tmpdir))

            assert "cat" in classes
            assert "dog" in classes
            assert "bird" in classes

    def test_round_trip_coordinates(self):
        """Test that coordinates are preserved through write/read cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(123.5, 456.7), QPointF(789.1, 234.5)],
                label="test"
            )

            handler = CreateMLAnnotationFormat()
            annotations = {"test.jpg": [original_shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read back
            handler2 = CreateMLAnnotationFormat()
            loaded = handler2.load_directory(Path(tmpdir))
            read_shape = loaded["test.jpg"][0]

            # Check that bounding box is approximately preserved
            # (some rounding may occur due to center coordinate conversion)
            orig_xmin = min(original_shape.points[0].x(), original_shape.points[1].x())
            orig_ymin = min(original_shape.points[0].y(), original_shape.points[1].y())
            orig_xmax = max(original_shape.points[0].x(), original_shape.points[1].x())
            orig_ymax = max(original_shape.points[0].y(), original_shape.points[1].y())

            read_xmin = min(read_shape.points[0].x(), read_shape.points[1].x())
            read_ymin = min(read_shape.points[0].y(), read_shape.points[1].y())
            read_xmax = max(read_shape.points[0].x(), read_shape.points[1].x())
            read_ymax = max(read_shape.points[0].y(), read_shape.points[1].y())

            assert abs(orig_xmin - read_xmin) < 1
            assert abs(orig_ymin - read_ymin) < 1
            assert abs(orig_xmax - read_xmax) < 1
            assert abs(orig_ymax - read_ymax) < 1

    def test_clear_cache(self):
        """Test clearing the annotations cache."""
        handler = CreateMLAnnotationFormat()
        handler._annotations_cache = {"test.jpg": []}
        handler._image_info_cache = {"test.jpg": (100, 100)}
        handler._loaded_directory = Path("/some/path")

        handler.clear_cache()

        assert handler._annotations_cache == {}
        assert handler._image_info_cache == {}
        assert handler._loaded_directory is None

    def test_empty_images_not_written(self):
        """Test that images with no annotations are not included in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            annotations = {
                "with_ann.jpg": [
                    Shape(type=ShapeType.BOX, points=[QPointF(0, 0), QPointF(100, 100)], label="cat")
                ],
                "without_ann.jpg": [],  # No annotations
            }
            image_sizes = {
                "with_ann.jpg": (1000, 1000),
                "without_ann.jpg": (1000, 1000),
            }

            handler = CreateMLAnnotationFormat()
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Verify JSON
            json_path = Path(tmpdir) / "_annotations.createml.json"
            with open(json_path) as f:
                data = json.load(f)

            # Only the image with annotations should be present
            assert len(data) == 1
            assert data[0]["image"] == "with_ann.jpg"
