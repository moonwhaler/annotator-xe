"""Background image loading worker threads."""

from __future__ import annotations

import logging
from pathlib import Path
from queue import PriorityQueue
from threading import Lock
from typing import List, Optional, Set

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap

from ..core.thumbnail_cache import get_thumbnail_cache, ThumbnailCache

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class ImageScanner(QThread):
    """
    Fast background thread for scanning image files in a directory.

    Only scans for filenames - does not load any image data.
    Emits signals for each found image file to build the UI quickly.
    """

    # Signal emitted for each image file found (filename)
    image_found = pyqtSignal(str)

    # Signal emitted when scan is complete (total count)
    finished = pyqtSignal(int)

    def __init__(self, directory: str) -> None:
        """
        Initialize the image scanner.

        Args:
            directory: Directory to scan for images
        """
        super().__init__()
        self.directory = Path(directory)
        self._is_running = True

    def run(self) -> None:
        """Scan directory for image files."""
        count = 0

        try:
            for entry in self.directory.iterdir():
                if not self._is_running:
                    logger.info("Image scanning cancelled")
                    break

                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                    self.image_found.emit(entry.name)
                    count += 1
        except Exception as e:
            logger.error(f"Error scanning directory {self.directory}: {e}")

        self.finished.emit(count)
        logger.info(f"Image scan complete: {count} images found")

    def stop(self) -> None:
        """Request the scanner to stop."""
        self._is_running = False


class ThumbnailLoader(QThread):
    """
    Background thread for loading thumbnails on demand.

    Uses a priority queue to load visible items first.
    Integrates with thumbnail cache for fast loading.
    """

    # Signal emitted when a thumbnail is loaded (filename, icon)
    thumbnail_loaded = pyqtSignal(str, QIcon)

    # Signal emitted when queue is empty (temporary idle)
    queue_empty = pyqtSignal()

    def __init__(
        self,
        directory: str,
        thumbnail_size: int = 80,
        cache: Optional[ThumbnailCache] = None
    ) -> None:
        """
        Initialize the thumbnail loader.

        Args:
            directory: Directory containing images
            thumbnail_size: Size for thumbnail icons
            cache: Optional thumbnail cache instance
        """
        super().__init__()
        self.directory = Path(directory)
        self.thumbnail_size = thumbnail_size
        self.cache = cache or get_thumbnail_cache()

        self._queue: PriorityQueue = PriorityQueue()
        self._is_running = True
        self._loaded: Set[str] = set()
        self._lock = Lock()

    def request_thumbnail(self, filename: str, priority: int = 100) -> None:
        """
        Request a thumbnail to be loaded.

        Args:
            filename: Image filename to load
            priority: Lower number = higher priority (0 = highest)
        """
        with self._lock:
            if filename not in self._loaded:
                self._queue.put((priority, filename))

    def request_thumbnails(self, filenames: List[str], priority: int = 100) -> None:
        """
        Request multiple thumbnails to be loaded.

        Args:
            filenames: List of image filenames to load
            priority: Lower number = higher priority
        """
        with self._lock:
            for filename in filenames:
                if filename not in self._loaded:
                    self._queue.put((priority, filename))

    def clear_queue(self) -> None:
        """Clear all pending thumbnail requests."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Exception:
                    break

    def run(self) -> None:
        """Process thumbnail loading requests."""
        while self._is_running:
            try:
                # Wait for items with timeout to allow checking _is_running
                try:
                    priority, filename = self._queue.get(timeout=0.1)
                except Exception:
                    continue

                # Skip if already loaded
                with self._lock:
                    if filename in self._loaded:
                        continue

                # Load the thumbnail
                file_path = self.directory / filename
                icon = self._load_thumbnail(file_path)

                if icon:
                    with self._lock:
                        self._loaded.add(filename)
                    self.thumbnail_loaded.emit(filename, icon)

                # Check if queue is empty
                if self._queue.empty():
                    self.queue_empty.emit()

            except Exception as e:
                logger.error(f"Error in thumbnail loader: {e}")

        logger.info("Thumbnail loader stopped")

    def stop(self) -> None:
        """Request the loader to stop."""
        self._is_running = False
        self.clear_queue()

    def _load_thumbnail(self, file_path: Path) -> Optional[QIcon]:
        """
        Load and create a thumbnail icon for an image.

        Checks cache first, then loads from disk if needed.

        Args:
            file_path: Path to the image file

        Returns:
            QIcon with thumbnail or None on error
        """
        try:
            # Try to get from cache first
            if self.cache and self.cache.enabled:
                cached_pixmap = self.cache.get(file_path, self.thumbnail_size)
                if cached_pixmap:
                    return QIcon(cached_pixmap)

            # Load from disk
            pixmap = QPixmap(str(file_path))

            if pixmap.isNull():
                logger.warning(f"Failed to load image: {file_path}")
                return None

            # Scale to thumbnail size
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Store in cache
            if self.cache and self.cache.enabled:
                self.cache.put(file_path, self.thumbnail_size, scaled)

            return QIcon(scaled)

        except Exception as e:
            logger.error(f"Error loading image {file_path}: {e}")
            return None

    def is_loaded(self, filename: str) -> bool:
        """Check if a thumbnail has been loaded."""
        with self._lock:
            return filename in self._loaded

    def get_loaded_count(self) -> int:
        """Get the number of loaded thumbnails."""
        with self._lock:
            return len(self._loaded)


class ImageLoader(QThread):
    """
    Background thread for loading image thumbnails.

    Emits signals as images are loaded to update the UI progressively
    without blocking the main thread.

    Note: For large directories, prefer ImageScanner + ThumbnailLoader
    for better performance with lazy loading.
    """

    # Signal emitted when an image is loaded (filename, icon)
    image_loaded = pyqtSignal(str, QIcon)

    # Signal emitted when all images are loaded
    finished = pyqtSignal()

    # Signal for progress updates (current, total)
    progress = pyqtSignal(int, int)

    def __init__(
        self,
        directory: str,
        file_list: List[str],
        thumbnail_size: int = 80,
        cache: Optional[ThumbnailCache] = None
    ) -> None:
        """
        Initialize the image loader.

        Args:
            directory: Directory containing images
            file_list: List of filenames to load
            thumbnail_size: Size for thumbnail icons
            cache: Optional thumbnail cache instance
        """
        super().__init__()
        self.directory = Path(directory)
        self.file_list = file_list
        self.thumbnail_size = thumbnail_size
        self.cache = cache or get_thumbnail_cache()
        self._is_running = True

    def run(self) -> None:
        """Load images in the background thread."""
        total = len(self.file_list)
        loaded = 0

        for filename in self.file_list:
            if not self._is_running:
                logger.info("Image loading cancelled")
                break

            if self._is_image_file(filename):
                file_path = self.directory / filename
                icon = self._load_thumbnail(file_path)

                if icon:
                    self.image_loaded.emit(filename, icon)
                    loaded += 1
                    self.progress.emit(loaded, total)

        self.finished.emit()
        logger.info(f"Image loading complete: {loaded} images")

    def stop(self) -> None:
        """Request the loader to stop."""
        self._is_running = False

    def _is_image_file(self, filename: str) -> bool:
        """Check if a file is a supported image format."""
        return Path(filename).suffix.lower() in IMAGE_EXTENSIONS

    def _load_thumbnail(self, file_path: Path) -> Optional[QIcon]:
        """
        Load and create a thumbnail icon for an image.

        Args:
            file_path: Path to the image file

        Returns:
            QIcon with thumbnail or None on error
        """
        try:
            # Try to get from cache first
            if self.cache and self.cache.enabled:
                cached_pixmap = self.cache.get(file_path, self.thumbnail_size)
                if cached_pixmap:
                    return QIcon(cached_pixmap)

            # Load from disk
            pixmap = QPixmap(str(file_path))

            if pixmap.isNull():
                logger.warning(f"Failed to load image: {file_path}")
                return None

            # Scale to thumbnail size
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Store in cache
            if self.cache and self.cache.enabled:
                self.cache.put(file_path, self.thumbnail_size, scaled)

            return QIcon(scaled)

        except Exception as e:
            logger.error(f"Error loading image {file_path}: {e}")
            return None


def get_image_files(directory: Path) -> List[str]:
    """
    Get list of image files in a directory.

    Args:
        directory: Directory to scan

    Returns:
        List of image filenames (not full paths)
    """
    if not directory.is_dir():
        return []

    return [
        f.name for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
