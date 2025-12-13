"""Thumbnail caching for fast image browser loading."""

from __future__ import annotations

import hashlib
import logging
import os
import platform
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)


def get_cache_dir() -> Path:
    """Get the system cache directory for thumbnails."""
    system = platform.system()

    if system == "Darwin":  # macOS
        cache_base = Path.home() / "Library" / "Caches"
    elif system == "Windows":
        cache_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:  # Linux and others
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

    cache_dir = cache_base / "annotator-xe" / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class ThumbnailCache:
    """
    Persistent disk cache for image thumbnails with LRU eviction.

    Thumbnails are stored as PNG files with names based on a hash of
    the source file path, modification time, and thumbnail size.
    """

    def __init__(self, max_size_mb: int = 500, enabled: bool = True) -> None:
        """
        Initialize the thumbnail cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
            enabled: Whether caching is enabled
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.enabled = enabled
        self.cache_dir = get_cache_dir() if enabled else None

        if self.cache_dir:
            logger.info(f"Thumbnail cache initialized at {self.cache_dir}")

    def _get_cache_key(self, file_path: Path, size: int) -> str:
        """
        Generate a cache key for an image.

        The key is based on:
        - Full file path
        - File modification time
        - Thumbnail size

        Args:
            file_path: Path to the source image
            size: Thumbnail size in pixels

        Returns:
            SHA256 hash string for the cache key
        """
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = 0

        key_string = f"{file_path}:{mtime}:{size}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the full path for a cached thumbnail."""
        return self.cache_dir / f"{cache_key}.png"

    def get(self, file_path: Path, size: int) -> Optional[QPixmap]:
        """
        Retrieve a cached thumbnail if it exists.

        Args:
            file_path: Path to the source image
            size: Thumbnail size in pixels

        Returns:
            QPixmap if found in cache, None otherwise
        """
        if not self.enabled or not self.cache_dir:
            return None

        cache_key = self._get_cache_key(file_path, size)
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                # Update access time for LRU tracking
                cache_path.touch()
                return pixmap
            else:
                # Corrupted cache file, remove it
                try:
                    cache_path.unlink()
                except OSError:
                    pass

        return None

    def put(self, file_path: Path, size: int, pixmap: QPixmap) -> bool:
        """
        Store a thumbnail in the cache.

        Args:
            file_path: Path to the source image
            size: Thumbnail size in pixels
            pixmap: The thumbnail pixmap to cache

        Returns:
            True if successfully cached
        """
        if not self.enabled or not self.cache_dir or pixmap.isNull():
            return False

        cache_key = self._get_cache_key(file_path, size)
        cache_path = self._get_cache_path(cache_key)

        try:
            pixmap.save(str(cache_path), "PNG")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache thumbnail for {file_path}: {e}")
            return False

    def get_cache_size(self) -> int:
        """Get the current cache size in bytes."""
        if not self.cache_dir or not self.cache_dir.exists():
            return 0

        total = 0
        for f in self.cache_dir.iterdir():
            if f.suffix == ".png":
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
        return total

    def cleanup(self) -> int:
        """
        Remove oldest cache files if over size limit.

        Uses LRU eviction based on file access times.

        Returns:
            Number of files removed
        """
        if not self.cache_dir or not self.cache_dir.exists():
            return 0

        current_size = self.get_cache_size()
        if current_size <= self.max_size_bytes:
            return 0

        # Get all cache files with their access times
        cache_files = []
        for f in self.cache_dir.iterdir():
            if f.suffix == ".png":
                try:
                    stat = f.stat()
                    cache_files.append((f, stat.st_atime, stat.st_size))
                except OSError:
                    pass

        # Sort by access time (oldest first)
        cache_files.sort(key=lambda x: x[1])

        # Remove oldest files until under limit
        removed = 0
        target_size = int(self.max_size_bytes * 0.8)  # Clean to 80% to avoid frequent cleanups

        for file_path, _, file_size in cache_files:
            if current_size <= target_size:
                break

            try:
                file_path.unlink()
                current_size -= file_size
                removed += 1
            except OSError:
                pass

        if removed > 0:
            logger.info(f"Thumbnail cache cleanup: removed {removed} files")

        return removed

    def clear(self) -> int:
        """
        Clear all cached thumbnails.

        Returns:
            Number of files removed
        """
        if not self.cache_dir or not self.cache_dir.exists():
            return 0

        removed = 0
        for f in self.cache_dir.iterdir():
            if f.suffix == ".png":
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass

        logger.info(f"Thumbnail cache cleared: removed {removed} files")
        return removed


# Global cache instance
_cache: Optional[ThumbnailCache] = None


def get_thumbnail_cache(max_size_mb: int = 500, enabled: bool = True) -> ThumbnailCache:
    """
    Get the global thumbnail cache instance.

    Args:
        max_size_mb: Maximum cache size in megabytes
        enabled: Whether caching is enabled

    Returns:
        ThumbnailCache singleton instance
    """
    global _cache
    if _cache is None:
        _cache = ThumbnailCache(max_size_mb=max_size_mb, enabled=enabled)
    return _cache


def reset_thumbnail_cache() -> None:
    """Reset the global thumbnail cache instance."""
    global _cache
    _cache = None
