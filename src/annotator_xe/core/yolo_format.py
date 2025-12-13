"""YOLO annotation format reading and writing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF

from .annotation_format import AnnotationFormat
from .models import Shape, ShapeType

logger = logging.getLogger(__name__)


class YOLOAnnotationReader:
    """
    Reader for YOLO format annotation files.

    Supports both bounding box format (5 values) and polygon format (2n+1 values).
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """
        Initialize the reader.

        Args:
            classes: Dictionary mapping class names to IDs
        """
        self.classes = classes or {}
        self._id_to_name: Dict[int, str] = {v: k for k, v in self.classes.items()}

    def set_classes(self, classes: Dict[str, int]) -> None:
        """Update the class mapping."""
        self.classes = classes
        self._id_to_name = {v: k for k, v in self.classes.items()}

    def get_class_name(self, class_id: int) -> str:
        """
        Get class name from ID.

        Args:
            class_id: Numeric class ID

        Returns:
            Class name or string representation of ID
        """
        return self._id_to_name.get(class_id, str(class_id))

    def read(
        self,
        txt_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """
        Read annotations from a YOLO format text file.

        Args:
            txt_path: Path to the annotation file
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            List of Shape objects
        """
        txt_path = Path(txt_path)
        if not txt_path.exists():
            logger.debug(f"Annotation file not found: {txt_path}")
            return []

        shapes: List[Shape] = []

        try:
            with open(txt_path, "r") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    shape = self._parse_line(line, img_width, img_height)
                    if shape:
                        shapes.append(shape)
                except Exception as e:
                    logger.warning(f"Error parsing line {line_num} in {txt_path}: {e}")

            logger.info(f"Loaded {len(shapes)} annotations from {txt_path}")

        except Exception as e:
            logger.error(f"Error reading annotation file {txt_path}: {e}")

        return shapes

    def _parse_line(
        self,
        line: str,
        img_width: int,
        img_height: int
    ) -> Optional[Shape]:
        """
        Parse a single annotation line.

        Args:
            line: Line from annotation file
            img_width: Image width
            img_height: Image height

        Returns:
            Shape object or None if parsing fails
        """
        data = line.split()
        if not data:
            return None

        class_id = int(data[0])
        label = self.get_class_name(class_id)

        if len(data) == 5:
            # Bounding box format: class_id x_center y_center width height
            x_center, y_center, width, height = map(float, data[1:])

            x1 = int((x_center - width / 2) * img_width)
            y1 = int((y_center - height / 2) * img_height)
            x2 = int((x_center + width / 2) * img_width)
            y2 = int((y_center + height / 2) * img_height)

            return Shape(
                type=ShapeType.BOX,
                points=[QPointF(x1, y1), QPointF(x2, y2)],
                label=label
            )

        elif len(data) > 5:
            # Polygon format: class_id x1 y1 x2 y2 ... xn yn
            coords = list(map(float, data[1:]))
            points = [
                QPointF(coords[i] * img_width, coords[i + 1] * img_height)
                for i in range(0, len(coords), 2)
            ]

            return Shape(
                type=ShapeType.POLYGON,
                points=points,
                label=label
            )

        else:
            logger.warning(f"Invalid annotation format: {line}")
            return None


class YOLOAnnotationWriter:
    """
    Writer for YOLO format annotation files.

    Writes shapes to YOLO format with normalized coordinates.
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """
        Initialize the writer.

        Args:
            classes: Dictionary mapping class names to IDs
        """
        self.classes = classes or {}

    def set_classes(self, classes: Dict[str, int]) -> None:
        """Update the class mapping."""
        self.classes = classes

    def get_class_id(self, label: str) -> int:
        """
        Get class ID from label.

        Args:
            label: Class label string

        Returns:
            Class ID or -1 if not found
        """
        return self.classes.get(label, -1)

    def write(
        self,
        txt_path: Path,
        shapes: List[Shape],
        img_width: int,
        img_height: int
    ) -> bool:
        """
        Write annotations to a YOLO format text file.

        Args:
            txt_path: Path to write the annotation file
            shapes: List of shapes to write
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            True if write was successful
        """
        txt_path = Path(txt_path)

        # If no shapes and file exists, delete it
        if not shapes:
            if txt_path.exists():
                try:
                    txt_path.unlink()
                    logger.info(f"Deleted empty annotation file: {txt_path}")
                except Exception as e:
                    logger.error(f"Error deleting annotation file: {e}")
                    return False
            return True

        try:
            with open(txt_path, "w") as f:
                for shape in shapes:
                    line = self._format_shape(shape, img_width, img_height)
                    if line:
                        f.write(line + "\n")

            logger.info(f"Saved {len(shapes)} annotations to {txt_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing annotation file {txt_path}: {e}")
            return False

    def _format_shape(
        self,
        shape: Shape,
        img_width: int,
        img_height: int
    ) -> Optional[str]:
        """
        Format a single shape as a YOLO annotation line.

        Args:
            shape: Shape to format
            img_width: Image width
            img_height: Image height

        Returns:
            Formatted annotation string or None
        """
        class_id = self.get_class_id(shape.label) if shape.label else -1

        if shape.type == ShapeType.BOX:
            if len(shape.points) < 2:
                return None

            x1, y1 = shape.points[0].x(), shape.points[0].y()
            x2, y2 = shape.points[1].x(), shape.points[1].y()

            x_center = (x1 + x2) / (2 * img_width)
            y_center = (y1 + y2) / (2 * img_height)
            width = abs(x2 - x1) / img_width
            height = abs(y2 - y1) / img_height

            return f"{class_id} {x_center} {y_center} {width} {height}"

        elif shape.type == ShapeType.POLYGON:
            if len(shape.points) < 3:
                return None

            coords = [
                f"{p.x() / img_width} {p.y() / img_height}"
                for p in shape.points
            ]

            return f"{class_id} {' '.join(coords)}"

        return None


def get_annotation_path(image_path: Path) -> Path:
    """
    Get the annotation file path for an image.

    Args:
        image_path: Path to the image file

    Returns:
        Path to the corresponding annotation file
    """
    return image_path.with_suffix(".txt")


def has_annotation(image_path: Path) -> bool:
    """
    Check if an image has a valid annotation file.

    Args:
        image_path: Path to the image file

    Returns:
        True if annotation file exists and contains valid YOLO data
    """
    txt_path = get_annotation_path(image_path)
    if not txt_path.exists():
        return False

    try:
        with open(txt_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Check if line starts with a valid class ID (integer)
                parts = line.split()
                if len(parts) >= 5:  # Minimum: class_id + 4 coords (bbox)
                    try:
                        int(parts[0])  # class_id must be integer
                        float(parts[1])  # coordinates must be floats
                        return True  # Found at least one valid annotation
                    except ValueError:
                        continue
        return False  # No valid annotations found
    except Exception:
        return False


class YOLOAnnotationFormat(AnnotationFormat):
    """
    YOLO annotation format handler implementing the AnnotationFormat interface.

    YOLO format stores annotations in .txt files with one file per image.
    Each line contains: class_id x_center y_center width height (for boxes)
    or class_id x1 y1 x2 y2 ... xn yn (for polygons).
    All coordinates are normalized to [0, 1].
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """Initialize the YOLO format handler."""
        super().__init__(classes)
        self._reader = YOLOAnnotationReader(classes)
        self._writer = YOLOAnnotationWriter(classes)

    def set_classes(self, classes: Dict[str, int]) -> None:
        """Update the class mapping."""
        super().set_classes(classes)
        self._reader.set_classes(classes)
        self._writer.set_classes(classes)

    @property
    def format_name(self) -> str:
        """Return the format name."""
        return "yolo"

    @property
    def is_per_image(self) -> bool:
        """YOLO uses one .txt file per image."""
        return True

    @property
    def file_extension(self) -> str:
        """YOLO uses .txt files."""
        return ".txt"

    @property
    def supports_polygons(self) -> bool:
        """YOLO supports both bounding boxes and polygons."""
        return True

    def read_image(
        self,
        image_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """Read annotations for a single image."""
        txt_path = get_annotation_path(image_path)
        return self._reader.read(txt_path, img_width, img_height)

    def write_image(
        self,
        image_path: Path,
        shapes: List[Shape],
        img_width: int,
        img_height: int
    ) -> bool:
        """Write annotations for a single image."""
        txt_path = get_annotation_path(image_path)
        return self._writer.write(txt_path, shapes, img_width, img_height)

    def load_directory(
        self,
        directory: Path
    ) -> Dict[str, List[Shape]]:
        """
        Load all YOLO annotations from a directory.

        Note: This method doesn't load shapes directly because it needs
        image dimensions. Use read_image() for individual images.

        Returns:
            Empty dict - use read_image() with dimensions for actual loading
        """
        # For per-image formats, we don't pre-load everything
        # The main window will call read_image() for each image as needed
        return {}

    def save_directory(
        self,
        directory: Path,
        annotations: Dict[str, List[Shape]],
        image_sizes: Dict[str, Tuple[int, int]]
    ) -> bool:
        """Save all annotations to individual YOLO files."""
        success = True
        for filename, shapes in annotations.items():
            image_path = directory / filename
            if filename in image_sizes:
                width, height = image_sizes[filename]
                if not self.write_image(image_path, shapes, width, height):
                    success = False
        return success

    def get_annotation_path(self, image_path: Path) -> Path:
        """Get the .txt annotation file path for an image."""
        return get_annotation_path(image_path)

    def has_annotation(self, image_path: Path) -> bool:
        """Check if an image has YOLO annotations."""
        return has_annotation(image_path)

    def get_classes_from_directory(self, directory: Path) -> Dict[str, int]:
        """
        Load classes from data.yaml in the directory.

        Returns:
            Dictionary mapping class names to IDs
        """
        data_yaml = directory / "data.yaml"
        if not data_yaml.exists():
            return self.classes.copy()

        try:
            import yaml
            with open(data_yaml, "r") as f:
                data = yaml.safe_load(f) or {}

            names = data.get("names", [])
            if isinstance(names, list):
                return {name: i for i, name in enumerate(names)}
            elif isinstance(names, dict):
                # Some YOLO data.yaml use dict format {0: 'cat', 1: 'dog'}
                return {v: int(k) for k, v in names.items()}
        except Exception as e:
            logger.error(f"Error loading classes from data.yaml: {e}")

        return self.classes.copy()
