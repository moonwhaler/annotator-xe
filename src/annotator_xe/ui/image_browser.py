"""Image browser list widgets for Annotator XE."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Set

from PyQt6.QtCore import Qt, QFileInfo, QSize, pyqtSignal, QTimer, QRect
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont, QPen, QBrush
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QLineEdit, QFrame, QAbstractItemView
)

from ..core.yolo_format import has_annotation
from .theme import get_theme_manager, ThemeColors

logger = logging.getLogger(__name__)

# Cache for placeholder icons by size and theme
_placeholder_icons: dict = {}
_placeholder_theme_key: str = ""


def create_placeholder_icon(size: int, colors: Optional[ThemeColors] = None) -> QIcon:
    """
    Create a placeholder icon for images not yet loaded.

    Args:
        size: Size of the placeholder icon
        colors: Theme colors to use (defaults to current theme)

    Returns:
        QIcon with a placeholder design matching current theme
    """
    global _placeholder_theme_key, _placeholder_icons

    if colors is None:
        colors = get_theme_manager().colors

    # Cache key includes theme to invalidate on theme change
    theme_key = colors.background_tertiary
    if theme_key != _placeholder_theme_key:
        _placeholder_icons.clear()
        _placeholder_theme_key = theme_key

    if size in _placeholder_icons:
        return _placeholder_icons[size]

    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(colors.background_tertiary))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw a subtle image icon in the center
    icon_size = size // 3
    center_x = size // 2
    center_y = size // 2

    # Draw mountain/image icon outline
    painter.setPen(QPen(QColor(colors.border), max(1, size // 40)))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Outer rectangle
    margin = size // 6
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 4, 4)

    # Simple mountain shapes
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(colors.surface))

    # Small mountain
    points_small = [
        (center_x - icon_size // 2, center_y + icon_size // 3),
        (center_x - icon_size // 6, center_y - icon_size // 6),
        (center_x + icon_size // 6, center_y + icon_size // 3),
    ]
    from PyQt6.QtGui import QPolygon
    from PyQt6.QtCore import QPoint
    painter.drawPolygon(QPolygon([QPoint(x, y) for x, y in points_small]))

    # Large mountain
    points_large = [
        (center_x - icon_size // 6, center_y + icon_size // 3),
        (center_x + icon_size // 3, center_y - icon_size // 3),
        (center_x + icon_size // 2 + icon_size // 6, center_y + icon_size // 3),
    ]
    painter.drawPolygon(QPolygon([QPoint(x, y) for x, y in points_large]))

    # Sun circle
    sun_radius = icon_size // 6
    painter.setBrush(QColor(colors.surface))
    painter.drawEllipse(
        center_x - icon_size // 3 - sun_radius,
        center_y - icon_size // 3,
        sun_radius * 2,
        sun_radius * 2
    )

    painter.end()

    icon = QIcon(pixmap)
    _placeholder_icons[size] = icon
    return icon


class ImageListItem(QListWidgetItem):
    """
    Custom list item for images with annotation status.

    Displays a thumbnail with metadata about annotation state
    and provides sorting by various attributes.
    """

    def __init__(
        self,
        icon: QIcon,
        file_path: str,
        thumbnail_size: int = 80,
        thumbnail_loaded: bool = True
    ) -> None:
        """
        Initialize the image list item.

        Args:
            icon: Thumbnail icon for the image (or placeholder)
            file_path: Full path to the image file
            thumbnail_size: Size of the thumbnail
            thumbnail_loaded: Whether the actual thumbnail has been loaded
        """
        super().__init__(icon, "")
        self.file_path = file_path
        self.file_info = QFileInfo(file_path)
        self._thumbnail_size = thumbnail_size
        self._thumbnail_loaded = thumbnail_loaded
        self._update_size_hint()

        self._hidden = False
        self.has_annotation = self._check_annotation_exists()

    def _update_size_hint(self) -> None:
        """Update the size hint based on thumbnail size."""
        # Add space for padding and filename text
        self.setSizeHint(QSize(self._thumbnail_size + 16, self._thumbnail_size + 24))

    def set_thumbnail_size(self, size: int) -> None:
        """Update the thumbnail size."""
        self._thumbnail_size = size
        self._update_size_hint()

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

    @property
    def thumbnail_loaded(self) -> bool:
        """Check if the actual thumbnail has been loaded."""
        return self._thumbnail_loaded

    @thumbnail_loaded.setter
    def thumbnail_loaded(self, value: bool) -> None:
        """Set the thumbnail loaded state."""
        self._thumbnail_loaded = value

    def update_thumbnail(self, icon: QIcon) -> None:
        """
        Update the item with a loaded thumbnail.

        Args:
            icon: The loaded thumbnail icon
        """
        self.setIcon(icon)
        self._thumbnail_loaded = True


class SortableImageList(QListWidget):
    """
    Image list widget with sorting capabilities and lazy loading support.

    Displays images in an icon grid view with support for
    sorting by name, date modified, or date created.
    Emits signals when visible items change to support lazy thumbnail loading.
    """

    # Signal emitted when visible items change (list of filenames needing thumbnails)
    visible_items_changed = pyqtSignal(list)

    def __init__(self, parent=None, thumbnail_size: int = 80) -> None:
        """Initialize the sortable image list."""
        super().__init__(parent)

        self.sort_role = "name"
        self.sort_order = Qt.SortOrder.AscendingOrder
        self._thumbnail_size = thumbnail_size
        self._filter_text = ""
        self._last_visible_items: Set[str] = set()

        # Configure view mode
        self.setObjectName("imageList")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setSpacing(8)
        self.setIconSize(QSize(thumbnail_size, thumbnail_size))
        self.setUniformItemSizes(True)  # Enable for better performance
        self.setWordWrap(True)

        # Debounce timer for visibility changes
        self._visibility_timer = QTimer()
        self._visibility_timer.setSingleShot(True)
        self._visibility_timer.setInterval(50)  # 50ms debounce
        self._visibility_timer.timeout.connect(self._emit_visible_items)

        # Connect scroll events
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self) -> None:
        """Handle scroll events with debouncing."""
        self._visibility_timer.start()

    def _emit_visible_items(self) -> None:
        """Calculate and emit visible items that need thumbnails."""
        items_needing_thumbnails = self.get_items_needing_thumbnails()
        if items_needing_thumbnails:
            self.visible_items_changed.emit(items_needing_thumbnails)

    def get_visible_items_in_viewport(self) -> List[ImageListItem]:
        """
        Get list items currently visible in the viewport.

        Returns:
            List of ImageListItem objects in the visible area
        """
        visible = []
        viewport_rect = self.viewport().rect()

        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem):
                item_rect = self.visualItemRect(item)
                if viewport_rect.intersects(item_rect):
                    visible.append(item)

        return visible

    def get_items_needing_thumbnails(self, buffer_count: int = 50) -> List[str]:
        """
        Get filenames of items that need thumbnails loaded.

        Includes visible items plus a buffer above and below.

        Args:
            buffer_count: Number of items to include above/below visible area

        Returns:
            List of filenames that need thumbnails
        """
        # Find visible items
        visible_items = self.get_visible_items_in_viewport()
        if not visible_items:
            return []

        # Get indices of visible items
        visible_indices = set()
        for item in visible_items:
            row = self.row(item)
            if row >= 0:
                visible_indices.add(row)

        if not visible_indices:
            return []

        # Calculate range with buffer
        min_idx = max(0, min(visible_indices) - buffer_count)
        max_idx = min(self.count() - 1, max(visible_indices) + buffer_count)

        # Collect items needing thumbnails
        needs_loading = []
        for i in range(min_idx, max_idx + 1):
            item = self.item(i)
            if isinstance(item, ImageListItem):
                if not item.thumbnail_loaded and not item.isHidden():
                    needs_loading.append(item.filename)

        return needs_loading

    def set_thumbnail_size(self, size: int) -> None:
        """
        Set the thumbnail size for all items.

        Args:
            size: New thumbnail size in pixels
        """
        self._thumbnail_size = size
        self.setIconSize(QSize(size, size))

        # Update all items
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem):
                item.set_thumbnail_size(size)

        # Force layout update
        self.scheduleDelayedItemsLayout()

    def set_filter(self, text: str) -> None:
        """
        Filter items by filename.

        Args:
            text: Filter text (case-insensitive)
        """
        self._filter_text = text.lower()
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem):
                matches = self._filter_text in item.filename.lower()
                item.setHidden(not matches if self._filter_text else False)

    def get_visible_count(self) -> int:
        """Get count of visible (non-hidden) items."""
        count = 0
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem) and not item.isHidden():
                count += 1
        return count

    def get_annotated_count(self) -> int:
        """Get count of annotated items."""
        count = 0
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ImageListItem) and item.has_annotation:
                count += 1
        return count

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


class ImageBrowserWidget(QWidget):
    """
    Modern image browser widget with search, filtering, and size controls.
    """

    # Signal emitted when thumbnail size changes
    thumbnail_size_changed = pyqtSignal(int)

    def __init__(self, parent=None, thumbnail_size: int = 80) -> None:
        """Initialize the image browser widget."""
        super().__init__(parent)
        self._thumbnail_size = thumbnail_size
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        self.setObjectName("imageBrowserContainer")
        self._apply_theme()

        # Register for theme changes
        get_theme_manager().register_callback(self._on_theme_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("Search images...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_box)

        # Stats label
        self.stats_label = QLabel("0 images")
        self.stats_label.setObjectName("statsLabel")
        layout.addWidget(self.stats_label)

        # Image list
        self.image_list = SortableImageList(thumbnail_size=self._thumbnail_size)
        layout.addWidget(self.image_list, 1)

        # Bottom controls
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        # Size slider
        size_label = QLabel("Size:")
        size_label.setObjectName("sizeLabel")
        bottom_layout.addWidget(size_label)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(48, 160)
        self.size_slider.setValue(self._thumbnail_size)
        self.size_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        bottom_layout.addWidget(self.size_slider, 1)

        self.size_value_label = QLabel(f"{self._thumbnail_size}px")
        self.size_value_label.setObjectName("sizeLabel")
        self.size_value_label.setMinimumWidth(45)
        bottom_layout.addWidget(self.size_value_label)

        layout.addLayout(bottom_layout)

    def _on_search_changed(self, text: str) -> None:
        """Handle search text changes."""
        self.image_list.set_filter(text)
        self._update_stats()

    def _on_size_changed(self, size: int) -> None:
        """Handle thumbnail size changes."""
        self._thumbnail_size = size
        self.size_value_label.setText(f"{size}px")
        self.image_list.set_thumbnail_size(size)
        self.thumbnail_size_changed.emit(size)

    def set_thumbnail_size(self, size: int) -> None:
        """Set the thumbnail size programmatically."""
        self._thumbnail_size = size
        self.size_slider.setValue(size)
        self.image_list.set_thumbnail_size(size)

    def _update_stats(self) -> None:
        """Update the statistics label."""
        total = self.image_list.count()
        visible = self.image_list.get_visible_count()
        annotated = self.image_list.get_annotated_count()

        if self.search_box.text():
            self.stats_label.setText(f"{visible} of {total} images ({annotated} annotated)")
        else:
            self.stats_label.setText(f"{total} images ({annotated} annotated)")

    def update_stats(self) -> None:
        """Public method to update stats."""
        self._update_stats()

    def _apply_theme(self) -> None:
        """Apply the current theme stylesheet."""
        self.setStyleSheet(get_theme_manager().get_image_browser_stylesheet())

    def _on_theme_changed(self, mode) -> None:
        """Handle theme change."""
        self._apply_theme()


def add_annotation_marker(icon: QIcon, size: int = 80) -> QIcon:
    """
    Add a visual marker to indicate annotation exists.

    Args:
        icon: The original icon
        size: Size of the icon

    Returns:
        Modified icon with annotation marker
    """
    pixmap = icon.pixmap(size, size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw a more visible checkmark badge at bottom right
    badge_size = max(16, size // 5)
    badge_x = pixmap.width() - badge_size - 2
    badge_y = pixmap.height() - badge_size - 2

    # Badge background (green circle)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(34, 197, 94))  # Modern green
    painter.drawEllipse(badge_x, badge_y, badge_size, badge_size)

    # Checkmark
    painter.setPen(QPen(QColor(255, 255, 255), max(1.5, badge_size / 8)))
    check_margin = badge_size // 4
    painter.drawLine(
        badge_x + check_margin,
        badge_y + badge_size // 2,
        badge_x + badge_size // 2 - 1,
        badge_y + badge_size - check_margin
    )
    painter.drawLine(
        badge_x + badge_size // 2 - 1,
        badge_y + badge_size - check_margin,
        badge_x + badge_size - check_margin,
        badge_y + check_margin
    )

    painter.end()
    return QIcon(pixmap)


def create_thumbnail(image_path: str, size: int = 80, show_filename: bool = True) -> Optional[QIcon]:
    """
    Create a thumbnail icon for an image.

    Args:
        image_path: Path to the image file
        size: Size of the thumbnail
        show_filename: Whether to draw filename on the thumbnail

    Returns:
        QIcon with thumbnail or None on error
    """
    try:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return None

        # Scale the image
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Create a new pixmap with space for filename
        if show_filename:
            filename = os.path.basename(image_path)
            # Truncate long filenames
            if len(filename) > 15:
                filename = filename[:12] + "..."

            final_pixmap = QPixmap(size, size + 16)
            final_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Center the scaled image
            x_offset = (size - scaled.width()) // 2
            y_offset = (size - scaled.height()) // 2
            painter.drawPixmap(x_offset, y_offset, scaled)

            # Draw filename at bottom
            painter.setPen(QColor(200, 200, 200))
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(
                0, size, size, 16,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                filename
            )

            painter.end()
            return QIcon(final_pixmap)
        else:
            return QIcon(scaled)

    except Exception as e:
        logger.error(f"Error creating thumbnail for {image_path}: {e}")
        return None
