"""Background image loading worker thread."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class ImageLoader(QThread):
    """
    Background thread for loading image thumbnails.

    Emits signals as images are loaded to update the UI progressively
    without blocking the main thread.
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
        thumbnail_size: int = 80
    ) -> None:
        """
        Initialize the image loader.

        Args:
            directory: Directory containing images
            file_list: List of filenames to load
            thumbnail_size: Size for thumbnail icons
        """
        super().__init__()
        self.directory = Path(directory)
        self.file_list = file_list
        self.thumbnail_size = thumbnail_size
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

            # Allow GUI to remain responsive
            QApplication.processEvents()

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
