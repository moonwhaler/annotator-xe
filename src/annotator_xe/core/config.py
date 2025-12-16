"""Configuration management for Annotator XE."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default configuration file path
DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass
class AppConfig:
    """
    Application configuration settings.

    Stores user preferences and application state.
    """

    default_directory: str = ""
    yolo_model_path: str = ""
    line_thickness: int = 2
    font_size: int = 10
    autosave: bool = False
    focus_on_select: bool = True
    zoom_on_select: bool = False
    zoom_on_select_level: str = "fit"  # fit, close, closer, detail
    auto_select_on_point_click: bool = True
    finish_drawing_key: str = "Escape"  # Key/combination to finish polygon drawing (empty to disable)
    delete_shape_key: str = "Delete"  # Key/combination to delete selected shape (empty to disable)
    thumbnail_size: int = 80  # Thumbnail size in pixels (48-160)
    thumbnail_cache_enabled: bool = True  # Enable disk cache for thumbnails
    thumbnail_cache_max_mb: int = 500  # Maximum thumbnail cache size in MB
    default_annotation_format: str = "yolo"  # Default format for new directories
    auto_detect_format: bool = True  # Auto-detect format when opening directory
    gpu_acceleration: bool = False  # Use GPU for hardware-accelerated image rendering
    theme: str = "system"  # Theme mode: "light", "dark", or "system"
    max_recent_paths: int = 10  # Number of recent paths to remember (0-20, 0 = disabled)
    recent_paths: list[str] = field(default_factory=list)  # List of recently opened paths
    max_history_entries: int = 100  # Maximum undo/redo history entries (10-1000)
    warn_box_rotation: bool = True  # Show warning when box is converted for rotation

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "defaultDirectory": self.default_directory,
            "yoloModelPath": self.yolo_model_path,
            "lineThickness": self.line_thickness,
            "fontSize": self.font_size,
            "autosave": self.autosave,
            "focusOnSelect": self.focus_on_select,
            "zoomOnSelect": self.zoom_on_select,
            "zoomOnSelectLevel": self.zoom_on_select_level,
            "autoSelectOnPointClick": self.auto_select_on_point_click,
            "finishDrawingKey": self.finish_drawing_key,
            "deleteShapeKey": self.delete_shape_key,
            "thumbnailSize": self.thumbnail_size,
            "thumbnailCacheEnabled": self.thumbnail_cache_enabled,
            "thumbnailCacheMaxMb": self.thumbnail_cache_max_mb,
            "defaultAnnotationFormat": self.default_annotation_format,
            "autoDetectFormat": self.auto_detect_format,
            "gpuAcceleration": self.gpu_acceleration,
            "theme": self.theme,
            "maxRecentPaths": self.max_recent_paths,
            "recentPaths": self.recent_paths,
            "maxHistoryEntries": self.max_history_entries,
            "warnBoxRotation": self.warn_box_rotation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        """Create config from dictionary."""
        return cls(
            default_directory=data.get("defaultDirectory", ""),
            yolo_model_path=data.get("yoloModelPath", ""),
            line_thickness=data.get("lineThickness", 2),
            font_size=data.get("fontSize", 10),
            autosave=data.get("autosave", False),
            focus_on_select=data.get("focusOnSelect", True),
            zoom_on_select=data.get("zoomOnSelect", False),
            zoom_on_select_level=data.get("zoomOnSelectLevel", "fit"),
            auto_select_on_point_click=data.get("autoSelectOnPointClick", True),
            finish_drawing_key=data.get("finishDrawingKey", "Escape"),
            delete_shape_key=data.get("deleteShapeKey", "Delete"),
            thumbnail_size=data.get("thumbnailSize", 80),
            thumbnail_cache_enabled=data.get("thumbnailCacheEnabled", True),
            thumbnail_cache_max_mb=data.get("thumbnailCacheMaxMb", 500),
            default_annotation_format=data.get("defaultAnnotationFormat", "yolo"),
            auto_detect_format=data.get("autoDetectFormat", True),
            gpu_acceleration=data.get("gpuAcceleration", False),
            theme=data.get("theme", "system"),
            max_recent_paths=data.get("maxRecentPaths", 10),
            recent_paths=data.get("recentPaths", []),
            max_history_entries=data.get("maxHistoryEntries", 100),
            warn_box_rotation=data.get("warnBoxRotation", True),
        )


@dataclass
class YOLODataConfig:
    """
    YOLO dataset configuration (data.yaml).

    Stores paths and class information for YOLO training.
    """

    train_path: str = "/path/to/train/images"
    val_path: str = "/path/to/valid/images"
    test_path: str = "/path/to/test/images"
    num_classes: int = 0
    class_names: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "train": self.train_path,
            "val": self.val_path,
            "test": self.test_path,
            "nc": self.num_classes,
            "names": self.class_names,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> YOLODataConfig:
        """Create config from dictionary."""
        names = data.get("names", [])
        if isinstance(names, str):
            names = [n.strip() for n in names.split(",")]

        return cls(
            train_path=data.get("train", "/path/to/train/images"),
            val_path=data.get("val", "/path/to/valid/images"),
            test_path=data.get("test", "/path/to/test/images"),
            num_classes=data.get("nc", 0),
            class_names=names,
        )


class ConfigManager:
    """
    Manager for loading and saving application configuration.

    Handles YAML serialization and provides a clean interface
    for configuration access.
    """

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self._config: Optional[AppConfig] = None

    @property
    def config(self) -> AppConfig:
        """Get the current configuration, loading if necessary."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> AppConfig:
        """
        Load configuration from file.

        Returns:
            AppConfig instance with loaded or default values
        """
        if not self.config_path.exists():
            logger.info(f"Config file not found at {self.config_path}, using defaults")
            return AppConfig()

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_path}")
            return AppConfig.from_dict(data)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config file: {e}")
            return AppConfig()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return AppConfig()

    def save(self, config: Optional[AppConfig] = None) -> bool:
        """
        Save configuration to file.

        Args:
            config: Configuration to save, or use current config

        Returns:
            True if save was successful
        """
        if config is not None:
            self._config = config

        if self._config is None:
            logger.warning("No configuration to save")
            return False

        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self._config.to_dict(), f, default_flow_style=False)
            logger.info(f"Saved configuration to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def update(self, **kwargs: Any) -> None:
        """
        Update configuration with new values.

        Args:
            **kwargs: Key-value pairs to update
        """
        config = self.config
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown config key: {key}")
        self.save()


class YOLODataConfigManager:
    """Manager for YOLO data.yaml configuration files."""

    def __init__(self, directory: Path) -> None:
        """
        Initialize with a directory path.

        Args:
            directory: Directory containing data.yaml
        """
        self.directory = Path(directory)
        self.config_path = self.directory / "data.yaml"
        self._config: Optional[YOLODataConfig] = None

    @property
    def config(self) -> YOLODataConfig:
        """Get the current configuration, loading if necessary."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> YOLODataConfig:
        """Load YOLO data configuration from file."""
        if not self.config_path.exists():
            logger.info(f"data.yaml not found at {self.config_path}, using defaults")
            return YOLODataConfig()

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f) or {}
            return YOLODataConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading data.yaml: {e}")
            return YOLODataConfig()

    def save(self, config: Optional[YOLODataConfig] = None) -> bool:
        """Save YOLO data configuration to file."""
        if config is not None:
            self._config = config

        if self._config is None:
            return False

        try:
            content = "# This config is for running YOLOv8 training locally.\n"
            with open(self.config_path, "w") as f:
                f.write(content)
                data = self._config.to_dict()
                for key, value in data.items():
                    if key == "names":
                        f.write(f"names: {value}\n")
                    else:
                        yaml.dump({key: value}, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Error saving data.yaml: {e}")
            return False

    def get_classes(self) -> Dict[str, int]:
        """
        Get class name to ID mapping.

        Returns:
            Dictionary mapping class names to their indices
        """
        return {name: i for i, name in enumerate(self.config.class_names)}

    def update_classes(self, classes: Dict[str, int]) -> None:
        """
        Update class names from a class dictionary.

        Args:
            classes: Dictionary mapping class names to IDs
        """
        # Sort by ID to maintain order
        sorted_classes = sorted(classes.items(), key=lambda x: x[1])
        self._config = YOLODataConfig(
            train_path=self.config.train_path,
            val_path=self.config.val_path,
            test_path=self.config.test_path,
            num_classes=len(classes),
            class_names=[name for name, _ in sorted_classes],
        )
        self.save()
