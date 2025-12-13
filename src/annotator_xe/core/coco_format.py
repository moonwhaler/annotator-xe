"""COCO annotation format reading and writing."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF

from .annotation_format import AnnotationFormat
from .models import Shape, ShapeType

logger = logging.getLogger(__name__)

# Common COCO annotation file names
COCO_FILE_NAMES = [
    "_annotations.coco.json",
    "annotations.json",
    "instances.json",
    "coco.json",
]


class COCOAnnotationFormat(AnnotationFormat):
    """
    COCO annotation format handler.

    COCO format stores all annotations in a single JSON file for the entire dataset.
    It supports both bounding boxes and polygon segmentation.

    JSON structure:
    {
        "info": {...},
        "licenses": [...],
        "images": [
            {"id": 1, "file_name": "image.jpg", "width": 1920, "height": 1080}
        ],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [x, y, width, height],
                "segmentation": [[x1, y1, x2, y2, ...]],
                "area": 1000,
                "iscrowd": 0
            }
        ],
        "categories": [
            {"id": 1, "name": "cat", "supercategory": "animal"}
        ]
    }
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """Initialize the COCO format handler."""
        super().__init__(classes)
        # Cache for loaded annotations (filename -> shapes)
        self._annotations_cache: Dict[str, List[Shape]] = {}
        # Cache for image info (filename -> (width, height))
        self._image_info_cache: Dict[str, Tuple[int, int]] = {}
        # Track the loaded directory
        self._loaded_directory: Optional[Path] = None
        # Track the COCO file path
        self._coco_file_path: Optional[Path] = None

    @property
    def format_name(self) -> str:
        """Return the format name."""
        return "coco"

    @property
    def is_per_image(self) -> bool:
        """COCO uses a single JSON file for all images."""
        return False

    @property
    def file_extension(self) -> str:
        """COCO uses .json files."""
        return ".json"

    @property
    def supports_polygons(self) -> bool:
        """COCO supports both bounding boxes and polygon segmentation."""
        return True

    def _find_coco_file(self, directory: Path) -> Optional[Path]:
        """Find the COCO annotation file in a directory."""
        for filename in COCO_FILE_NAMES:
            coco_path = directory / filename
            if coco_path.exists():
                return coco_path
        return None

    def _get_default_coco_path(self, directory: Path) -> Path:
        """Get the default COCO file path for a directory."""
        return directory / "_annotations.coco.json"

    def read_image(
        self,
        image_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """
        Read annotations for a single image from cache.

        For COCO format, annotations are loaded from the dataset file
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

        For COCO format, this updates the in-memory cache.
        Call save_directory() to persist changes to disk.

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
        Load all COCO annotations from a directory.

        Args:
            directory: Path to the directory containing the COCO JSON file

        Returns:
            Dictionary mapping image filenames to their shapes
        """
        self._annotations_cache.clear()
        self._image_info_cache.clear()
        self._loaded_directory = directory

        coco_path = self._find_coco_file(directory)
        if not coco_path:
            logger.debug(f"No COCO annotation file found in {directory}")
            self._coco_file_path = self._get_default_coco_path(directory)
            return {}

        self._coco_file_path = coco_path

        try:
            with open(coco_path, "r", encoding="utf-8") as f:
                coco_data = json.load(f)

            # Parse categories
            categories: Dict[int, str] = {}
            for cat in coco_data.get("categories", []):
                cat_id = cat.get("id")
                cat_name = cat.get("name", "")
                if cat_id is not None:
                    categories[cat_id] = cat_name
                    if cat_name not in self.classes:
                        self.classes[cat_name] = cat_id
            self._id_to_name = {v: k for k, v in self.classes.items()}

            # Parse images
            image_id_to_filename: Dict[int, str] = {}
            for img in coco_data.get("images", []):
                img_id = img.get("id")
                filename = img.get("file_name", "")
                width = img.get("width", 0)
                height = img.get("height", 0)

                if img_id is not None and filename:
                    image_id_to_filename[img_id] = filename
                    self._image_info_cache[filename] = (width, height)
                    self._annotations_cache[filename] = []

            # Parse annotations
            for ann in coco_data.get("annotations", []):
                image_id = ann.get("image_id")
                category_id = ann.get("category_id")

                if image_id not in image_id_to_filename:
                    continue

                filename = image_id_to_filename[image_id]
                img_width, img_height = self._image_info_cache.get(filename, (0, 0))

                if img_width == 0 or img_height == 0:
                    continue

                label = categories.get(category_id, str(category_id))

                # Try to parse segmentation (polygon) first
                segmentation = ann.get("segmentation")
                if segmentation and isinstance(segmentation, list) and len(segmentation) > 0:
                    # COCO segmentation is a list of polygons
                    # Each polygon is [x1, y1, x2, y2, ...]
                    for seg in segmentation:
                        if isinstance(seg, list) and len(seg) >= 6:
                            # Convert flat list to points
                            points = []
                            for i in range(0, len(seg), 2):
                                if i + 1 < len(seg):
                                    points.append(QPointF(seg[i], seg[i + 1]))

                            if len(points) >= 3:
                                shape = Shape(
                                    type=ShapeType.POLYGON,
                                    points=points,
                                    label=label
                                )
                                self._annotations_cache[filename].append(shape)
                else:
                    # Fall back to bbox
                    bbox = ann.get("bbox")
                    if bbox and len(bbox) == 4:
                        x, y, w, h = bbox
                        shape = Shape(
                            type=ShapeType.BOX,
                            points=[QPointF(x, y), QPointF(x + w, y + h)],
                            label=label
                        )
                        self._annotations_cache[filename].append(shape)

            total_shapes = sum(len(shapes) for shapes in self._annotations_cache.values())
            logger.info(f"Loaded {total_shapes} annotations from {coco_path}")

            return self._annotations_cache.copy()

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing COCO JSON {coco_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading COCO file {coco_path}: {e}")

        return {}

    def save_directory(
        self,
        directory: Path,
        annotations: Dict[str, List[Shape]],
        image_sizes: Dict[str, Tuple[int, int]]
    ) -> bool:
        """
        Save all annotations to COCO JSON file.

        Args:
            directory: Path to the directory
            annotations: Dictionary mapping image filenames to shapes
            image_sizes: Dictionary mapping image filenames to (width, height)

        Returns:
            True if save was successful
        """
        coco_path = self._coco_file_path or self._get_default_coco_path(directory)

        try:
            # Build COCO structure
            coco_data: Dict[str, Any] = {
                "info": {
                    "description": "Exported from Annotator XE",
                    "url": "",
                    "version": "1.0",
                    "year": datetime.now().year,
                    "contributor": "Annotator XE",
                    "date_created": datetime.now().isoformat()
                },
                "licenses": [],
                "images": [],
                "annotations": [],
                "categories": []
            }

            # Build categories from classes
            for class_name, class_id in sorted(self.classes.items(), key=lambda x: x[1]):
                coco_data["categories"].append({
                    "id": class_id,
                    "name": class_name,
                    "supercategory": ""
                })

            # Build images and annotations
            annotation_id = 1

            for image_id, (filename, shapes) in enumerate(annotations.items(), start=1):
                if filename not in image_sizes:
                    continue

                width, height = image_sizes[filename]

                # Add image entry
                coco_data["images"].append({
                    "id": image_id,
                    "file_name": filename,
                    "width": width,
                    "height": height
                })

                # Add annotation entries
                for shape in shapes:
                    category_id = self.get_class_id(shape.label)
                    if category_id == -1:
                        # Add new category
                        category_id = len(self.classes)
                        self.classes[shape.label] = category_id
                        coco_data["categories"].append({
                            "id": category_id,
                            "name": shape.label,
                            "supercategory": ""
                        })

                    ann_entry: Dict[str, Any] = {
                        "id": annotation_id,
                        "image_id": image_id,
                        "category_id": category_id,
                        "iscrowd": 0
                    }

                    if shape.type == ShapeType.BOX and len(shape.points) >= 2:
                        x1 = min(shape.points[0].x(), shape.points[1].x())
                        y1 = min(shape.points[0].y(), shape.points[1].y())
                        x2 = max(shape.points[0].x(), shape.points[1].x())
                        y2 = max(shape.points[0].y(), shape.points[1].y())
                        w = x2 - x1
                        h = y2 - y1

                        ann_entry["bbox"] = [x1, y1, w, h]
                        ann_entry["area"] = w * h
                        ann_entry["segmentation"] = []

                    elif shape.type == ShapeType.POLYGON and len(shape.points) >= 3:
                        # Convert polygon to segmentation format
                        # Exclude closing point if it duplicates the first
                        points = shape.points
                        if len(points) > 1 and points[0] == points[-1]:
                            points = points[:-1]

                        seg = []
                        for p in points:
                            seg.extend([p.x(), p.y()])

                        ann_entry["segmentation"] = [seg]

                        # Calculate bbox from polygon
                        xs = [p.x() for p in points]
                        ys = [p.y() for p in points]
                        x1, x2 = min(xs), max(xs)
                        y1, y2 = min(ys), max(ys)
                        w = x2 - x1
                        h = y2 - y1

                        ann_entry["bbox"] = [x1, y1, w, h]

                        # Calculate area (using shoelace formula)
                        area = 0.0
                        n = len(points)
                        for i in range(n):
                            j = (i + 1) % n
                            area += points[i].x() * points[j].y()
                            area -= points[j].x() * points[i].y()
                        ann_entry["area"] = abs(area) / 2.0
                    else:
                        continue

                    coco_data["annotations"].append(ann_entry)
                    annotation_id += 1

            # Write JSON file
            with open(coco_path, "w", encoding="utf-8") as f:
                json.dump(coco_data, f, indent=2)

            total_annotations = len(coco_data["annotations"])
            logger.info(f"Saved {total_annotations} annotations to {coco_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing COCO file {coco_path}: {e}")
            return False

    def get_annotation_path(self, image_path: Path) -> Path:
        """Get the COCO JSON file path for the directory."""
        directory = image_path.parent
        coco_path = self._find_coco_file(directory)
        return coco_path or self._get_default_coco_path(directory)

    def has_annotation(self, image_path: Path) -> bool:
        """Check if an image has COCO annotations."""
        directory = image_path.parent

        # Ensure directory is loaded
        if self._loaded_directory != directory:
            self.load_directory(directory)

        filename = image_path.name
        shapes = self._annotations_cache.get(filename, [])
        return len(shapes) > 0

    def get_classes_from_directory(self, directory: Path) -> Dict[str, int]:
        """
        Load categories from COCO JSON file.

        Returns:
            Dictionary mapping class names to IDs
        """
        coco_path = self._find_coco_file(directory)
        if not coco_path:
            return self.classes.copy()

        try:
            with open(coco_path, "r", encoding="utf-8") as f:
                coco_data = json.load(f)

            classes: Dict[str, int] = {}
            for cat in coco_data.get("categories", []):
                cat_id = cat.get("id")
                cat_name = cat.get("name", "")
                if cat_id is not None and cat_name:
                    classes[cat_name] = cat_id

            return classes if classes else self.classes.copy()

        except Exception as e:
            logger.error(f"Error loading COCO categories: {e}")
            return self.classes.copy()

    def clear_cache(self) -> None:
        """Clear the annotations cache."""
        self._annotations_cache.clear()
        self._image_info_cache.clear()
        self._loaded_directory = None
