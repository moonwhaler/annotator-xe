"""Tests for COCO format reading and writing."""

import json
import pytest
from pathlib import Path
import tempfile

from PyQt6.QtCore import QPointF

from annotator_xe.core.coco_format import COCOAnnotationFormat
from annotator_xe.core.models import Shape, ShapeType


class TestCOCOAnnotationFormat:
    """Tests for COCOAnnotationFormat."""

    def test_format_properties(self):
        """Test format properties."""
        handler = COCOAnnotationFormat()
        assert handler.format_name == "coco"
        assert handler.is_per_image is False
        assert handler.file_extension == ".json"
        assert handler.supports_polygons is True

    def test_read_empty_directory(self):
        """Test reading from directory with no COCO JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = COCOAnnotationFormat()
            annotations = handler.load_directory(Path(tmpdir))
            assert annotations == {}

    def test_write_and_read_box(self):
        """Test writing and reading a bounding box."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(300, 300)],
                label="cat"
            )

            handler = COCOAnnotationFormat({"cat": 1})

            # Write
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            result = handler.save_directory(Path(tmpdir), annotations, image_sizes)
            assert result is True

            # Verify JSON file exists
            json_path = Path(tmpdir) / "_annotations.coco.json"
            assert json_path.exists()

            # Read back
            handler2 = COCOAnnotationFormat()
            loaded = handler2.load_directory(Path(tmpdir))
            assert "test.jpg" in loaded
            assert len(loaded["test.jpg"]) == 1
            assert loaded["test.jpg"][0].type == ShapeType.BOX
            assert loaded["test.jpg"][0].label == "cat"

    def test_write_and_read_polygon(self):
        """Test writing and reading a polygon."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a triangle polygon
            shape = Shape(
                type=ShapeType.POLYGON,
                points=[QPointF(100, 100), QPointF(200, 100), QPointF(150, 200)],
                label="triangle"
            )

            handler = COCOAnnotationFormat({"triangle": 1})

            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read back
            handler2 = COCOAnnotationFormat()
            loaded = handler2.load_directory(Path(tmpdir))
            assert "test.jpg" in loaded
            assert len(loaded["test.jpg"]) == 1
            assert loaded["test.jpg"][0].type == ShapeType.POLYGON
            assert len(loaded["test.jpg"][0].points) >= 3

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

            handler = COCOAnnotationFormat({"cat": 1, "dog": 2})
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Verify JSON structure
            json_path = Path(tmpdir) / "_annotations.coco.json"
            with open(json_path) as f:
                coco_data = json.load(f)

            assert len(coco_data["images"]) == 2
            assert len(coco_data["annotations"]) == 2
            assert len(coco_data["categories"]) == 2

    def test_read_image_from_cache(self):
        """Test reading single image uses cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "test.jpg"

            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 100), QPointF(200, 200)],
                label="cat"
            )

            handler = COCOAnnotationFormat({"cat": 1})
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read using read_image (should load directory first)
            handler2 = COCOAnnotationFormat()
            shapes = handler2.read_image(image_path, 1000, 1000)
            assert len(shapes) == 1
            assert shapes[0].label == "cat"

    def test_has_annotation(self):
        """Test checking if image has annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = COCOAnnotationFormat({"cat": 1})

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
        """Test extracting categories from COCO JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a COCO JSON manually
            coco_data = {
                "images": [],
                "annotations": [],
                "categories": [
                    {"id": 1, "name": "cat"},
                    {"id": 2, "name": "dog"},
                    {"id": 3, "name": "bird"},
                ]
            }
            json_path = Path(tmpdir) / "_annotations.coco.json"
            with open(json_path, "w") as f:
                json.dump(coco_data, f)

            handler = COCOAnnotationFormat()
            classes = handler.get_classes_from_directory(Path(tmpdir))

            assert classes["cat"] == 1
            assert classes["dog"] == 2
            assert classes["bird"] == 3

    def test_coco_file_detection(self):
        """Test detection of various COCO file names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with annotations.json
            coco_data = {
                "images": [{"id": 1, "file_name": "test.jpg", "width": 100, "height": 100}],
                "annotations": [],
                "categories": []
            }

            for filename in ["_annotations.coco.json", "annotations.json", "instances.json"]:
                json_path = Path(tmpdir) / filename
                with open(json_path, "w") as f:
                    json.dump(coco_data, f)

                handler = COCOAnnotationFormat()
                loaded = handler.load_directory(Path(tmpdir))

                # Should load without error
                json_path.unlink()

    def test_bbox_format(self):
        """Test COCO bbox format is [x, y, width, height]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shape = Shape(
                type=ShapeType.BOX,
                points=[QPointF(100, 150), QPointF(300, 350)],  # x1,y1,x2,y2
                label="cat"
            )

            handler = COCOAnnotationFormat({"cat": 1})
            annotations = {"test.jpg": [shape]}
            image_sizes = {"test.jpg": (1000, 1000)}
            handler.save_directory(Path(tmpdir), annotations, image_sizes)

            # Read raw JSON
            json_path = Path(tmpdir) / "_annotations.coco.json"
            with open(json_path) as f:
                coco_data = json.load(f)

            ann = coco_data["annotations"][0]
            bbox = ann["bbox"]

            # COCO format: [x, y, width, height]
            assert bbox[0] == 100  # x
            assert bbox[1] == 150  # y
            assert bbox[2] == 200  # width
            assert bbox[3] == 200  # height

    def test_clear_cache(self):
        """Test clearing the annotations cache."""
        handler = COCOAnnotationFormat()
        handler._annotations_cache = {"test.jpg": []}
        handler._image_info_cache = {"test.jpg": (100, 100)}
        handler._loaded_directory = Path("/some/path")

        handler.clear_cache()

        assert handler._annotations_cache == {}
        assert handler._image_info_cache == {}
        assert handler._loaded_directory is None
