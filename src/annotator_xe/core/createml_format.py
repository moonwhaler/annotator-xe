"""CreateML annotation format reading and writing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF

from .annotation_format import AnnotationFormat
from .models import Shape, ShapeType

logger = logging.getLogger(__name__)

# Common CreateML annotation file names
CREATEML_FILE_NAMES = [
    "_annotations.createml.json",
    "annotations.createml.json",
    "createml.json",
]


class CreateMLAnnotationFormat(AnnotationFormat):
    """
    CreateML annotation format handler.

    CreateML format stores all annotations in a single JSON file for the entire dataset.
    It only supports bounding boxes (not polygons).

    JSON structure (array of image entries):
    [
        {
            "image": "image.jpg",
            "annotations": [
                {
                    "label": "cat",
                    "coordinates": {
                        "x": 150,  // center x
                        "y": 150,  // center y
                        "width": 100,
                        "height": 100
                    }
                }
            ]
        }
    ]

    Note: CreateML uses center coordinates, not top-left corner.
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """Initialize the CreateML format handler."""
        super().__init__(classes)
        # Cache for loaded annotations (filename -> shapes)
        self._annotations_cache: Dict[str, List[Shape]] = {}
        # Cache for image info (filename -> (width, height))
        self._image_info_cache: Dict[str, Tuple[int, int]] = {}
        # Track the loaded directory
        self._loaded_directory: Optional[Path] = None
        # Track the CreateML file path
        self._createml_file_path: Optional[Path] = None

    @property
    def format_name(self) -> str:
        """Return the format name."""
        return "createml"

    @property
    def is_per_image(self) -> bool:
        """CreateML uses a single JSON file for all images."""
        return False

    @property
    def file_extension(self) -> str:
        """CreateML uses .json files."""
        return ".json"

    @property
    def supports_polygons(self) -> bool:
        """CreateML only supports bounding boxes."""
        return False

    def _find_createml_file(self, directory: Path) -> Optional[Path]:
        """Find the CreateML annotation file in a directory."""
        for filename in CREATEML_FILE_NAMES:
            createml_path = directory / filename
            if createml_path.exists():
                # Verify it's a CreateML file (array format)
                try:
                    with open(createml_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # CreateML is an array with 'image' and 'annotations' keys
                    if isinstance(data, list):
                        if len(data) == 0:
                            return createml_path
                        if isinstance(data[0], dict) and "image" in data[0]:
                            return createml_path
                except Exception:
                    continue
        return None

    def _get_default_createml_path(self, directory: Path) -> Path:
        """Get the default CreateML file path for a directory."""
        return directory / "_annotations.createml.json"

    def read_image(
        self,
        image_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """
        Read annotations for a single image from cache.

        For CreateML format, annotations are loaded from the dataset file
        when load_directory() is called. This method returns cached data.

        Args:
            image_path: Path to the image file
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            List of Shape objects for the image
        """
        # Check if we need to load the directory
        directory = image_path.parent
        if self._loaded_directory != directory:
            self.load_directory(directory)

        filename = image_path.name
        return self._annotations_cache.get(filename, []).copy()

    def write_image(
        self,
        image_path: Path,
        shapes: List[Shape],
        img_width: int,
        img_height: int
    ) -> bool:
        """
        Update annotations for a single image in cache.

        For CreateML format, this updates the in-memory cache.
        Call save_directory() to persist changes to disk.

        Note: Polygon shapes will be converted to bounding boxes.

        Args:
            image_path: Path to the image file
            shapes: List of shapes to write
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            True if update was successful
        """
        filename = image_path.name
        directory = image_path.parent

        # Ensure directory is loaded
        if self._loaded_directory != directory:
            self.load_directory(directory)

        # Update cache
        self._annotations_cache[filename] = shapes.copy()
        self._image_info_cache[filename] = (img_width, img_height)

        # Auto-save to disk
        return self.save_directory(
            directory,
            self._annotations_cache,
            self._image_info_cache
        )

    def load_directory(
        self,
        directory: Path
    ) -> Dict[str, List[Shape]]:
        """
        Load all CreateML annotations from a directory.

        Args:
            directory: Path to the directory containing the CreateML JSON file

        Returns:
            Dictionary mapping image filenames to their shapes
        """
        self._annotations_cache.clear()
        self._image_info_cache.clear()
        self._loaded_directory = directory

        createml_path = self._find_createml_file(directory)
        if not createml_path:
            logger.debug(f"No CreateML annotation file found in {directory}")
            self._createml_file_path = self._get_default_createml_path(directory)
            return {}

        self._createml_file_path = createml_path

        try:
            with open(createml_path, "r", encoding="utf-8") as f:
                createml_data = json.load(f)

            if not isinstance(createml_data, list):
                logger.error(f"Invalid CreateML format in {createml_path}")
                return {}

            # Extract classes from annotations
            class_set: set = set()

            for entry in createml_data:
                if not isinstance(entry, dict):
                    continue

                filename = entry.get("image", "")
                if not filename:
                    continue

                self._annotations_cache[filename] = []

                annotations = entry.get("annotations", [])
                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue

                    label = ann.get("label", "")
                    coords = ann.get("coordinates", {})

                    if not coords:
                        continue

                    # CreateML uses center coordinates
                    cx = coords.get("x", 0)
                    cy = coords.get("y", 0)
                    w = coords.get("width", 0)
                    h = coords.get("height", 0)

                    # Convert to corner coordinates
                    x1 = cx - w / 2
                    y1 = cy - h / 2
                    x2 = cx + w / 2
                    y2 = cy + h / 2

                    shape = Shape(
                        type=ShapeType.BOX,
                        points=[QPointF(x1, y1), QPointF(x2, y2)],
                        label=label
                    )
                    self._annotations_cache[filename].append(shape)

                    if label:
                        class_set.add(label)

            # Update classes
            for i, class_name in enumerate(sorted(class_set)):
                if class_name not in self.classes:
                    self.classes[class_name] = i
            self._id_to_name = {v: k for k, v in self.classes.items()}

            total_shapes = sum(len(shapes) for shapes in self._annotations_cache.values())
            logger.info(f"Loaded {total_shapes} annotations from {createml_path}")

            return self._annotations_cache.copy()

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing CreateML JSON {createml_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading CreateML file {createml_path}: {e}")

        return {}

    def save_directory(
        self,
        directory: Path,
        annotations: Dict[str, List[Shape]],
        image_sizes: Dict[str, Tuple[int, int]]
    ) -> bool:
        """
        Save all annotations to CreateML JSON file.

        Note: Polygon shapes will be converted to bounding boxes.

        Args:
            directory: Path to the directory
            annotations: Dictionary mapping image filenames to shapes
            image_sizes: Dictionary mapping image filenames to (width, height)

        Returns:
            True if save was successful
        """
        createml_path = self._createml_file_path or self._get_default_createml_path(directory)

        try:
            createml_data: List[Dict[str, Any]] = []
            polygon_converted = False

            for filename, shapes in annotations.items():
                if not shapes:
                    continue

                entry: Dict[str, Any] = {
                    "image": filename,
                    "annotations": []
                }

                for shape in shapes:
                    # Get bounding box coordinates
                    if shape.type == ShapeType.BOX and len(shape.points) >= 2:
                        x1 = min(shape.points[0].x(), shape.points[1].x())
                        y1 = min(shape.points[0].y(), shape.points[1].y())
                        x2 = max(shape.points[0].x(), shape.points[1].x())
                        y2 = max(shape.points[0].y(), shape.points[1].y())
                    elif shape.type == ShapeType.POLYGON and shape.points:
                        # Convert polygon to bounding box
                        polygon_converted = True
                        xs = [p.x() for p in shape.points]
                        ys = [p.y() for p in shape.points]
                        x1, x2 = min(xs), max(xs)
                        y1, y2 = min(ys), max(ys)
                    else:
                        continue

                    # Calculate center coordinates (CreateML format)
                    w = x2 - x1
                    h = y2 - y1
                    cx = x1 + w / 2
                    cy = y1 + h / 2

                    ann_entry = {
                        "label": shape.label if shape.label else "unknown",
                        "coordinates": {
                            "x": round(cx, 2),
                            "y": round(cy, 2),
                            "width": round(w, 2),
                            "height": round(h, 2)
                        }
                    }
                    entry["annotations"].append(ann_entry)

                if entry["annotations"]:
                    createml_data.append(entry)

            if polygon_converted:
                logger.warning(
                    f"Polygons converted to bounding boxes in {createml_path} "
                    "(CreateML doesn't support polygons)"
                )

            # Write JSON file
            with open(createml_path, "w", encoding="utf-8") as f:
                json.dump(createml_data, f, indent=2)

            total_annotations = sum(len(e["annotations"]) for e in createml_data)
            logger.info(f"Saved {total_annotations} annotations to {createml_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing CreateML file {createml_path}: {e}")
            return False

    def get_annotation_path(self, image_path: Path) -> Path:
        """Get the CreateML JSON file path for the directory."""
        directory = image_path.parent
        createml_path = self._find_createml_file(directory)
        return createml_path or self._get_default_createml_path(directory)

    def has_annotation(self, image_path: Path) -> bool:
        """Check if an image has CreateML annotations."""
        directory = image_path.parent

        # Ensure directory is loaded
        if self._loaded_directory != directory:
            self.load_directory(directory)

        filename = image_path.name
        shapes = self._annotations_cache.get(filename, [])
        return len(shapes) > 0

    def get_classes_from_directory(self, directory: Path) -> Dict[str, int]:
        """
        Extract class names from CreateML JSON file.

        Returns:
            Dictionary mapping class names to IDs
        """
        createml_path = self._find_createml_file(directory)
        if not createml_path:
            return self.classes.copy()

        try:
            with open(createml_path, "r", encoding="utf-8") as f:
                createml_data = json.load(f)

            if not isinstance(createml_data, list):
                return self.classes.copy()

            class_set: set = set()
            for entry in createml_data:
                if not isinstance(entry, dict):
                    continue
                for ann in entry.get("annotations", []):
                    label = ann.get("label", "")
                    if label:
                        class_set.add(label)

            classes: Dict[str, int] = {
                name: i for i, name in enumerate(sorted(class_set))
            }
            return classes if classes else self.classes.copy()

        except Exception as e:
            logger.error(f"Error loading CreateML classes: {e}")
            return self.classes.copy()

    def clear_cache(self) -> None:
        """Clear the annotations cache."""
        self._annotations_cache.clear()
        self._image_info_cache.clear()
        self._loaded_directory = None
