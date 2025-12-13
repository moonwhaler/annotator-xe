"""Abstract base class for annotation format handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Shape


class AnnotationFormat(ABC):
    """
    Abstract base class for annotation format handlers.

    Provides a unified interface for reading and writing annotations
    in different formats (YOLO, COCO, Pascal VOC, CreateML).

    Formats are divided into two types:
    - Per-image formats (YOLO, Pascal VOC): One annotation file per image
    - Dataset formats (COCO, CreateML): One file for all images in directory
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """
        Initialize the format handler.

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
        """Get class name from ID."""
        return self._id_to_name.get(class_id, str(class_id))

    def get_class_id(self, label: str) -> int:
        """Get class ID from label."""
        return self.classes.get(label, -1)

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name (e.g., 'yolo', 'coco', 'pascal_voc', 'createml')."""
        pass

    @property
    @abstractmethod
    def is_per_image(self) -> bool:
        """
        Return True if format uses one file per image, False for dataset-wide files.

        Per-image formats: YOLO (.txt), Pascal VOC (.xml)
        Dataset formats: COCO (.json), CreateML (.json)
        """
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension for annotation files (e.g., '.txt', '.xml', '.json')."""
        pass

    @property
    def supports_polygons(self) -> bool:
        """Return True if format supports polygon annotations."""
        return True  # Override in formats that don't support polygons

    # === Per-image methods (primary for YOLO/VOC) ===

    @abstractmethod
    def read_image(
        self,
        image_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """
        Read annotations for a single image.

        Args:
            image_path: Path to the image file
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            List of Shape objects for the image
        """
        pass

    @abstractmethod
    def write_image(
        self,
        image_path: Path,
        shapes: List[Shape],
        img_width: int,
        img_height: int
    ) -> bool:
        """
        Write annotations for a single image.

        Args:
            image_path: Path to the image file
            shapes: List of shapes to write
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            True if write was successful
        """
        pass

    # === Dataset methods (primary for COCO/CreateML) ===

    @abstractmethod
    def load_directory(
        self,
        directory: Path
    ) -> Dict[str, List[Shape]]:
        """
        Load all annotations for a directory.

        For per-image formats, this reads all annotation files.
        For dataset formats, this parses the single JSON file.

        Args:
            directory: Path to the directory containing images/annotations

        Returns:
            Dictionary mapping image filenames to their shapes
        """
        pass

    @abstractmethod
    def save_directory(
        self,
        directory: Path,
        annotations: Dict[str, List[Shape]],
        image_sizes: Dict[str, Tuple[int, int]]
    ) -> bool:
        """
        Save all annotations for a directory.

        For per-image formats, this writes individual annotation files.
        For dataset formats, this writes a single JSON file.

        Args:
            directory: Path to the directory
            annotations: Dictionary mapping image filenames to shapes
            image_sizes: Dictionary mapping image filenames to (width, height)

        Returns:
            True if save was successful
        """
        pass

    @abstractmethod
    def get_annotation_path(self, image_path: Path) -> Path:
        """
        Get the annotation file path for an image.

        For per-image formats: Returns path to individual annotation file
        For dataset formats: Returns path to the dataset JSON file

        Args:
            image_path: Path to the image file

        Returns:
            Path to the annotation file
        """
        pass

    @abstractmethod
    def has_annotation(self, image_path: Path) -> bool:
        """
        Check if an image has annotations.

        Args:
            image_path: Path to the image file

        Returns:
            True if annotations exist for the image
        """
        pass

    def get_classes_from_directory(self, directory: Path) -> Dict[str, int]:
        """
        Extract class names from annotations in directory.

        Override in subclasses to implement format-specific class extraction.

        Args:
            directory: Path to the directory

        Returns:
            Dictionary mapping class names to IDs
        """
        return self.classes.copy()
