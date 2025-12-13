"""Image browser list widgets for Annotator XE."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QFileInfo, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from ..core.yolo_format import has_annotation

logger = logging.getLogger(__name__)


class ImageListItem(QListWidgetItem):
    """
    Custom list item for images with annotation status.

    Displays a thumbnail with metadata about annotation state
    and provides sorting by various attributes.
    """

    def __init__(self, icon: QIcon, file_path: str) -> None:
        """
        Initialize the image list item.

        Args:
            icon: Thumbnail icon for the image
            file_path: Full path to the image file
        """
        super().__init__(icon, "")  # No text, icon only
        self.file_path = file_path
        self.file_info = QFileInfo(file_path)
        self.setSizeHint(QSize(100, 100))

        self._hidden = False
        self.has_annotation = self._check_annotation_exists()

    def __lt__(self, other: ImageListItem) -> bool:
        """Compare items for sorting."""
        if not isinstance(other, ImageListItem):
            return super().__lt__(other)

        list_widget = self.listWidget()
        if not isinstance(list_widget, SortableImageList):
            return super().__lt__(other)

        sort_role = list_widget.sort_role

        if sort_role == "name":
            return self.file_info.fileName().lower() < other.file_info.fileName().lower()
        elif sort_role == "date_modified":
            return self.file_info.lastModified() < other.file_info.lastModified()
        elif sort_role == "date_created":
            return self.file_info.birthTime() < other.file_info.birthTime()
        else:
            return super().__lt__(other)

    def _check_annotation_exists(self) -> bool:
        """Check if an annotation file exists for this image."""
        return has_annotation(Path(self.file_path))

    def refresh_annotation_status(self) -> None:
        """Refresh the annotation status from disk."""
        self.has_annotation = self._check_annotation_exists()

    def setHidden(self, hidden: bool) -> None:
        """
        Set whether the item should be grayed out.

        Args:
            hidden: True to gray out the item
        """
        self._hidden = hidden
        if hidden:
            self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        else:
            self.setFlags(self.flags() | Qt.ItemFlag.ItemIsEnabled)

    def isHidden(self) -> bool:
        """Check if the item is hidden/grayed out."""
        return self._hidden

    @property
    def filename(self) -> str:
        """Get just the filename without path."""
        return os.path.basename(self.file_path)


class SortableImageList(QListWidget):
    """
    Image list widget with sorting capabilities.

    Displays images in an icon grid view with support for
    sorting by name, date modified, or date created.
    """

    def __init__(self, parent=None) -> None:
        """Initialize the sortable image list."""
        super().__init__(parent)

        self.sort_role = "name"
        self.sort_order = Qt.SortOrder.AscendingOrder

        # Configure view mode
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setSpacing(10)
        self.setIconSize(QSize(80, 80))

    def setSortRole(self, role: str) -> None:
        """
        Set the sort role.

        Args:
            role: One of "name", "date_modified", "date_created"
        """
        self.sort_role = role
        self.sortItems()

    def setSortOrder(self, order: Qt.SortOrder) -> None:
        """
        Set the sort order.

        Args:
            order: Qt.SortOrder.AscendingOrder or DescendingOrder
        """
        self.sort_order = order
        self.sortItems()

    def sortItems(self, order: Optional[Qt.SortOrder] = None) -> None:
        """Sort items according to current settings."""
        if order is None:
            order = self.sort_order
        super().sortItems(order)

    def get_image_items(self) -> list[ImageListItem]:
        """Get all ImageListItem objects in the list."""
        return [
            self.item(i) for i in range(self.count())
            if isinstance(self.item(i), ImageListItem)
        ]

    def find_item_by_path(self, file_path: str) -> Optional[ImageListItem]:
        """
        Find an item by its file path.

        Args:
            file_path: Full path to the image file

        Returns:
            The matching item or None
        """
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem) and item.file_path == file_path:
                return item
        return None

    def find_item_by_name(self, filename: str) -> Optional[ImageListItem]:
        """
        Find an item by its filename.

        Args:
            filename: Just the filename (not full path)

        Returns:
            The matching item or None
        """
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem) and item.filename == filename:
                return item
        return None


def add_annotation_marker(icon: QIcon, size: int = 80) -> QIcon:
    """
    Add a green marker to an icon to indicate annotation exists.

    Args:
        icon: The original icon
        size: Size of the icon

    Returns:
        Modified icon with green marker
    """
    pixmap = icon.pixmap(size, size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw green circle at bottom right
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 255, 0, 200))
    painter.drawEllipse(pixmap.width() - 15, pixmap.height() - 15, 10, 10)

    painter.end()
    return QIcon(pixmap)


def create_thumbnail(image_path: str, size: int = 80) -> Optional[QIcon]:
    """
    Create a thumbnail icon for an image.

    Args:
        image_path: Path to the image file
        size: Size of the thumbnail

    Returns:
        QIcon with thumbnail or None on error
    """
    try:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return None

        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        return QIcon(scaled)

    except Exception as e:
        logger.error(f"Error creating thumbnail for {image_path}: {e}")
        return None
