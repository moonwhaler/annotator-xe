"""Tests for format detection and registry."""

import json
import pytest
from pathlib import Path
import tempfile

from annotator_xe.core.format_registry import FormatRegistry
from annotator_xe.core.coco_format import COCOAnnotationFormat
from annotator_xe.core.createml_format import CreateMLAnnotationFormat
from annotator_xe.core.pascal_voc_format import PascalVOCAnnotationFormat
from annotator_xe.core.yolo_format import YOLOAnnotationFormat


class TestFormatRegistry:
    """Tests for FormatRegistry."""

    def test_get_format_names(self):
        """Test getting available format names."""
        names = FormatRegistry.get_format_names()
        assert "yolo" in names
        assert "coco" in names
        assert "pascal_voc" in names
        assert "createml" in names

    def test_get_display_name(self):
        """Test getting display names."""
        assert FormatRegistry.get_display_name("yolo") == "YOLO"
        assert FormatRegistry.get_display_name("coco") == "COCO"
        assert FormatRegistry.get_display_name("pascal_voc") == "Pascal VOC"
        assert FormatRegistry.get_display_name("createml") == "CreateML"

    def test_get_handler(self):
        """Test getting format handlers."""
        yolo_handler = FormatRegistry.get_handler("yolo")
        assert isinstance(yolo_handler, YOLOAnnotationFormat)

        coco_handler = FormatRegistry.get_handler("coco")
        assert isinstance(coco_handler, COCOAnnotationFormat)

        voc_handler = FormatRegistry.get_handler("pascal_voc")
        assert isinstance(voc_handler, PascalVOCAnnotationFormat)

        createml_handler = FormatRegistry.get_handler("createml")
        assert isinstance(createml_handler, CreateMLAnnotationFormat)

    def test_get_handler_with_classes(self):
        """Test getting handler with initial classes."""
        classes = {"cat": 0, "dog": 1}
        handler = FormatRegistry.get_handler("yolo", classes)

        assert handler.classes == classes
        assert handler.get_class_name(0) == "cat"
        assert handler.get_class_name(1) == "dog"

    def test_get_handler_unknown_format(self):
        """Test getting handler for unknown format raises error."""
        with pytest.raises(ValueError):
            FormatRegistry.get_handler("unknown_format")

    def test_is_per_image_format(self):
        """Test checking if format is per-image."""
        assert FormatRegistry.is_per_image_format("yolo") is True
        assert FormatRegistry.is_per_image_format("pascal_voc") is True
        assert FormatRegistry.is_per_image_format("coco") is False
        assert FormatRegistry.is_per_image_format("createml") is False

    def test_format_supports_polygons(self):
        """Test checking polygon support."""
        assert FormatRegistry.format_supports_polygons("yolo") is True
        assert FormatRegistry.format_supports_polygons("coco") is True
        assert FormatRegistry.format_supports_polygons("pascal_voc") is False
        assert FormatRegistry.format_supports_polygons("createml") is False


class TestFormatDetection:
    """Tests for format auto-detection."""

    def test_detect_yolo_by_txt_files(self):
        """Test detecting YOLO format by .txt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create image and YOLO annotation
            (Path(tmpdir) / "test.jpg").touch()
            (Path(tmpdir) / "test.txt").write_text("0 0.5 0.5 0.2 0.1")

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "yolo"

    def test_detect_yolo_by_data_yaml(self):
        """Test detecting YOLO format by data.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "data.yaml").write_text("names: [cat, dog]")

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "yolo"

    def test_detect_coco(self):
        """Test detecting COCO format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            coco_data = {
                "images": [{"id": 1, "file_name": "test.jpg"}],
                "annotations": [],
                "categories": []
            }
            (Path(tmpdir) / "_annotations.coco.json").write_text(json.dumps(coco_data))

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "coco"

    def test_detect_coco_annotations_json(self):
        """Test detecting COCO format with annotations.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            coco_data = {
                "images": [{"id": 1, "file_name": "test.jpg"}],
                "annotations": [],
                "categories": []
            }
            (Path(tmpdir) / "annotations.json").write_text(json.dumps(coco_data))

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "coco"

    def test_detect_createml(self):
        """Test detecting CreateML format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            createml_data = [
                {
                    "image": "test.jpg",
                    "annotations": []
                }
            ]
            (Path(tmpdir) / "_annotations.createml.json").write_text(json.dumps(createml_data))

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "createml"

    def test_detect_pascal_voc(self):
        """Test detecting Pascal VOC format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create image and VOC XML
            (Path(tmpdir) / "test.jpg").touch()
            voc_xml = """<?xml version="1.0"?>
<annotation>
    <filename>test.jpg</filename>
    <object>
        <name>cat</name>
        <bndbox>
            <xmin>100</xmin>
            <ymin>100</ymin>
            <xmax>200</xmax>
            <ymax>200</ymax>
        </bndbox>
    </object>
</annotation>"""
            (Path(tmpdir) / "test.xml").write_text(voc_xml)

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "pascal_voc"

    def test_detect_empty_directory_defaults_to_yolo(self):
        """Test that empty directory defaults to YOLO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "yolo"

    def test_detect_nonexistent_directory_defaults_to_yolo(self):
        """Test that nonexistent directory defaults to YOLO."""
        detected = FormatRegistry.detect_format(Path("/nonexistent/path"))
        assert detected == "yolo"

    def test_coco_takes_priority_over_yolo(self):
        """Test that COCO detection takes priority when both exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both YOLO and COCO files
            (Path(tmpdir) / "test.jpg").touch()
            (Path(tmpdir) / "test.txt").write_text("0 0.5 0.5 0.2 0.1")

            coco_data = {
                "images": [{"id": 1, "file_name": "test.jpg"}],
                "annotations": [],
                "categories": []
            }
            (Path(tmpdir) / "_annotations.coco.json").write_text(json.dumps(coco_data))

            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "coco"

    def test_createml_detected_by_structure(self):
        """Test CreateML is detected by its array structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # CreateML uses array format with 'image' key
            createml_data = [
                {"image": "test.jpg", "annotations": []}
            ]
            (Path(tmpdir) / "annotations.json").write_text(json.dumps(createml_data))

            detected = FormatRegistry.detect_format(Path(tmpdir))
            # Should detect as CreateML not COCO since it's array with 'image' key
            assert detected == "createml"

    def test_invalid_json_ignored(self):
        """Test that invalid JSON files are ignored during detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "_annotations.coco.json").write_text("not valid json {{{")

            # Should fall back to yolo
            detected = FormatRegistry.detect_format(Path(tmpdir))
            assert detected == "yolo"
