"""Format registry for annotation format auto-detection and management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

from .annotation_format import AnnotationFormat
from .coco_format import COCOAnnotationFormat, COCO_FILE_NAMES
from .createml_format import CreateMLAnnotationFormat, CREATEML_FILE_NAMES
from .pascal_voc_format import PascalVOCAnnotationFormat
from .yolo_format import YOLOAnnotationFormat

logger = logging.getLogger(__name__)


# Format display names
FORMAT_DISPLAY_NAMES = {
    "yolo": "YOLO",
    "coco": "COCO",
    "pascal_voc": "Pascal VOC",
    "createml": "CreateML",
}

# Format descriptions
FORMAT_DESCRIPTIONS = {
    "yolo": "One .txt file per image with normalized coordinates",
    "coco": "Single JSON file for entire dataset (Microsoft COCO format)",
    "pascal_voc": "One .xml file per image (ImageNet/VOC format)",
    "createml": "Single JSON file for entire dataset (Apple CreateML format)",
}


class FormatRegistry:
    """
    Registry for annotation format handlers.

    Provides format auto-detection and handler instantiation.
    """

    # Map format names to handler classes
    _formats: Dict[str, Type[AnnotationFormat]] = {
        "yolo": YOLOAnnotationFormat,
        "coco": COCOAnnotationFormat,
        "pascal_voc": PascalVOCAnnotationFormat,
        "createml": CreateMLAnnotationFormat,
    }

    @classmethod
    def get_format_names(cls) -> List[str]:
        """Get list of available format names."""
        return list(cls._formats.keys())

    @classmethod
    def get_display_name(cls, format_name: str) -> str:
        """Get the display name for a format."""
        return FORMAT_DISPLAY_NAMES.get(format_name, format_name)

    @classmethod
    def get_description(cls, format_name: str) -> str:
        """Get the description for a format."""
        return FORMAT_DESCRIPTIONS.get(format_name, "")

    @classmethod
    def get_handler(
        cls,
        format_name: str,
        classes: Optional[Dict[str, int]] = None
    ) -> AnnotationFormat:
        """
        Get an instance of a format handler.

        Args:
            format_name: Name of the format (yolo, coco, pascal_voc, createml)
            classes: Optional class mapping to initialize the handler with

        Returns:
            AnnotationFormat instance

        Raises:
            ValueError: If format name is unknown
        """
        if format_name not in cls._formats:
            raise ValueError(f"Unknown format: {format_name}")

        handler_class = cls._formats[format_name]
        return handler_class(classes)

    @classmethod
    def detect_format(cls, directory: Path) -> str:
        """
        Auto-detect the annotation format used in a directory.

        Detection order (first match wins):
        1. COCO: annotations.json, _annotations.coco.json with COCO structure
        2. CreateML: createml.json, _annotations.createml.json with CreateML structure
        3. Pascal VOC: .xml files alongside images
        4. YOLO: .txt files alongside images, or data.yaml present
        5. Default: YOLO

        Args:
            directory: Path to the directory to analyze

        Returns:
            Format name string
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning(f"Directory not found: {directory}, defaulting to YOLO")
            return "yolo"

        # Check for COCO format
        if cls._detect_coco(directory):
            logger.info(f"Detected COCO format in {directory}")
            return "coco"

        # Check for CreateML format
        if cls._detect_createml(directory):
            logger.info(f"Detected CreateML format in {directory}")
            return "createml"

        # Check for Pascal VOC format
        if cls._detect_pascal_voc(directory):
            logger.info(f"Detected Pascal VOC format in {directory}")
            return "pascal_voc"

        # Check for YOLO format (or default)
        if cls._detect_yolo(directory):
            logger.info(f"Detected YOLO format in {directory}")
            return "yolo"

        # Default to YOLO for new/empty directories
        logger.info(f"No format detected in {directory}, defaulting to YOLO")
        return "yolo"

    @classmethod
    def _detect_coco(cls, directory: Path) -> bool:
        """Check if directory contains COCO format annotations."""
        for filename in COCO_FILE_NAMES:
            json_path = directory / filename
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # COCO format has specific structure
                    if isinstance(data, dict):
                        # Must have at least 'images' or 'annotations' key
                        if "images" in data or "annotations" in data or "categories" in data:
                            return True
                except Exception:
                    continue
        return False

    @classmethod
    def _detect_createml(cls, directory: Path) -> bool:
        """Check if directory contains CreateML format annotations."""
        for filename in CREATEML_FILE_NAMES:
            json_path = directory / filename
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # CreateML format is an array with 'image' and 'annotations' keys
                    if isinstance(data, list):
                        if len(data) == 0:
                            # Empty CreateML file
                            return True
                        if isinstance(data[0], dict) and "image" in data[0]:
                            return True
                except Exception:
                    continue

        # Also check for annotations.json that might be CreateML format
        annotations_json = directory / "annotations.json"
        if annotations_json.exists():
            try:
                with open(annotations_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], dict) and "image" in data[0]:
                        return True
            except Exception:
                pass

        return False

    @classmethod
    def _detect_pascal_voc(cls, directory: Path) -> bool:
        """Check if directory contains Pascal VOC format annotations."""
        # Look for .xml files alongside images
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

        for xml_path in directory.glob("*.xml"):
            # Check if there's a corresponding image file
            stem = xml_path.stem
            for ext in image_extensions:
                if (directory / f"{stem}{ext}").exists():
                    # Verify it's a Pascal VOC XML
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        # Pascal VOC has 'annotation' root with 'object' children
                        if root.tag == "annotation":
                            return True
                    except Exception:
                        continue
        return False

    @classmethod
    def _detect_yolo(cls, directory: Path) -> bool:
        """Check if directory contains YOLO format annotations."""
        # Check for data.yaml (YOLO dataset config)
        if (directory / "data.yaml").exists():
            return True

        # Look for .txt files alongside images
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

        for txt_path in directory.glob("*.txt"):
            stem = txt_path.stem
            for ext in image_extensions:
                if (directory / f"{stem}{ext}").exists():
                    # Verify it looks like YOLO format
                    try:
                        with open(txt_path, "r") as f:
                            line = f.readline().strip()
                            if line:
                                parts = line.split()
                                # YOLO: class_id + at least 4 coords
                                if len(parts) >= 5:
                                    int(parts[0])  # class_id is integer
                                    float(parts[1])  # coords are floats
                                    return True
                    except Exception:
                        continue
        return False

    @classmethod
    def is_per_image_format(cls, format_name: str) -> bool:
        """Check if a format uses per-image files."""
        handler = cls.get_handler(format_name)
        return handler.is_per_image

    @classmethod
    def format_supports_polygons(cls, format_name: str) -> bool:
        """Check if a format supports polygon annotations."""
        handler = cls.get_handler(format_name)
        return handler.supports_polygons
