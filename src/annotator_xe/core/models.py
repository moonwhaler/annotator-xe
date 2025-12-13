"""Data models for Annotator XE annotations."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)


class ShapeType(str, Enum):
    """Type of annotation shape."""

    BOX = "box"
    POLYGON = "polygon"


@dataclass
class Shape:
    """
    Data model for a single annotation shape.

    Supports both bounding boxes and polygons with labels,
    selection state, and random color assignment.
    """

    type: ShapeType
    points: List[QPointF]
    label: str = ""
    selected: bool = False
    color: QColor = field(default_factory=lambda: Shape._generate_random_color())

    def __post_init__(self) -> None:
        """Ensure points are QPointF and close polygons."""
        # Convert any non-QPointF points
        self.points = [
            QPointF(p) if isinstance(p, QPointF) else QPointF(p.x(), p.y())
            for p in self.points
        ]

        # Close polygon if needed
        if self.type == ShapeType.POLYGON:
            self.close_polygon()

    @staticmethod
    def _generate_random_color() -> QColor:
        """Generate a random color with full saturation and value."""
        hue = random.randint(0, 359)
        return QColor.fromHsv(hue, 255, 255, 128)

    def close_polygon(self) -> None:
        """Ensure the polygon is closed (first point equals last point)."""
        if self.type == ShapeType.POLYGON and len(self.points) > 2:
            if self.points[0] != self.points[-1]:
                self.points.append(QPointF(self.points[0]))

    def remove_point(self, index: int) -> bool:
        """
        Remove a point from a polygon shape.

        Args:
            index: Index of the point to remove

        Returns:
            True if point was removed, False otherwise
        """
        if self.type != ShapeType.POLYGON:
            logger.warning("Cannot remove points from non-polygon shapes")
            return False

        if len(self.points) <= 3:
            logger.warning("Cannot remove point: polygon needs at least 3 points")
            return False

        if 0 <= index < len(self.points):
            del self.points[index]
            self.close_polygon()
            return True
        return False

    def move_by(self, delta: QPointF) -> None:
        """
        Move all points by a delta offset.

        Args:
            delta: The offset to move by
        """
        self.points = [point + delta for point in self.points]

    def move_point(self, index: int, new_pos: QPointF) -> bool:
        """
        Move a specific point to a new position.

        For polygons, handles closing point synchronization.

        Args:
            index: Index of point to move
            new_pos: New position for the point

        Returns:
            True if point was moved, False otherwise
        """
        if not (0 <= index < len(self.points)):
            return False

        # Check if polygon is closed (first and last points are at the same position)
        is_closed = (
            self.type == ShapeType.POLYGON and
            len(self.points) > 2 and
            self.points[0] == self.points[-1]
        )

        self.points[index] = new_pos

        # Keep polygon closed if it was already closed
        if is_closed and (index == 0 or index == len(self.points) - 1):
            self.points[0] = self.points[-1] = new_pos

        return True

    def get_bounding_rect(self) -> tuple[float, float, float, float]:
        """
        Get the bounding rectangle of the shape.

        Returns:
            Tuple of (x, y, width, height)
        """
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)

        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        return (min_x, min_y, max_x - min_x, max_y - min_y)

    def to_yolo_box(self, img_width: int, img_height: int) -> tuple[float, float, float, float]:
        """
        Convert bounding box to YOLO format (normalized center coordinates).

        Args:
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            Tuple of (x_center, y_center, width, height) normalized to [0, 1]
        """
        if self.type != ShapeType.BOX or len(self.points) < 2:
            raise ValueError("Shape must be a box with 2 points")

        x1, y1 = self.points[0].x(), self.points[0].y()
        x2, y2 = self.points[1].x(), self.points[1].y()

        x_center = (x1 + x2) / (2 * img_width)
        y_center = (y1 + y2) / (2 * img_height)
        width = abs(x2 - x1) / img_width
        height = abs(y2 - y1) / img_height

        return (x_center, y_center, width, height)

    def to_yolo_polygon(self, img_width: int, img_height: int) -> List[tuple[float, float]]:
        """
        Convert polygon to YOLO format (normalized coordinates).

        Args:
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            List of (x, y) tuples normalized to [0, 1]
        """
        if self.type != ShapeType.POLYGON:
            raise ValueError("Shape must be a polygon")

        return [(p.x() / img_width, p.y() / img_height) for p in self.points]

    @classmethod
    def from_yolo_box(
        cls,
        class_id: int,
        x_center: float,
        y_center: float,
        width: float,
        height: float,
        img_width: int,
        img_height: int,
        label: str = ""
    ) -> Shape:
        """
        Create a box shape from YOLO normalized coordinates.

        Args:
            class_id: Class ID (unused, label is used instead)
            x_center: Normalized x center coordinate
            y_center: Normalized y center coordinate
            width: Normalized width
            height: Normalized height
            img_width: Image width in pixels
            img_height: Image height in pixels
            label: Label string for the shape

        Returns:
            New Shape instance
        """
        x1 = int((x_center - width / 2) * img_width)
        y1 = int((y_center - height / 2) * img_height)
        x2 = int((x_center + width / 2) * img_width)
        y2 = int((y_center + height / 2) * img_height)

        return cls(
            type=ShapeType.BOX,
            points=[QPointF(x1, y1), QPointF(x2, y2)],
            label=label
        )

    @classmethod
    def from_yolo_polygon(
        cls,
        class_id: int,
        coordinates: List[float],
        img_width: int,
        img_height: int,
        label: str = ""
    ) -> Shape:
        """
        Create a polygon shape from YOLO normalized coordinates.

        Args:
            class_id: Class ID (unused, label is used instead)
            coordinates: Flat list of normalized x, y coordinates
            img_width: Image width in pixels
            img_height: Image height in pixels
            label: Label string for the shape

        Returns:
            New Shape instance
        """
        points = [
            QPointF(coordinates[i] * img_width, coordinates[i + 1] * img_height)
            for i in range(0, len(coordinates), 2)
        ]

        return cls(
            type=ShapeType.POLYGON,
            points=points,
            label=label
        )


@dataclass
class Annotation:
    """
    Collection of shapes for a single image.

    Represents all annotations for one image file.
    """

    image_path: str
    shapes: List[Shape] = field(default_factory=list)

    def add_shape(self, shape: Shape) -> None:
        """Add a shape to the annotation."""
        self.shapes.append(shape)

    def remove_shape(self, index: int) -> Optional[Shape]:
        """Remove and return a shape by index."""
        if 0 <= index < len(self.shapes):
            return self.shapes.pop(index)
        return None

    def clear(self) -> None:
        """Remove all shapes."""
        self.shapes.clear()

    @property
    def box_count(self) -> int:
        """Count of bounding box annotations."""
        return sum(1 for s in self.shapes if s.type == ShapeType.BOX)

    @property
    def polygon_count(self) -> int:
        """Count of polygon annotations."""
        return sum(1 for s in self.shapes if s.type == ShapeType.POLYGON)
