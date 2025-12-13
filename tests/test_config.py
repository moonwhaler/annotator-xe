"""Tests for configuration management."""

import pytest
from pathlib import Path
import tempfile

from annotator_xe.core.config import (
    AppConfig,
    ConfigManager,
    YOLODataConfig,
    YOLODataConfigManager
)


class TestAppConfig:
    """Tests for AppConfig."""

    def test_default_config(self):
        """Test creating config with defaults."""
        config = AppConfig()

        assert config.default_directory == ""
        assert config.yolo_model_path == ""
        assert config.line_thickness == 2
        assert config.font_size == 10
        assert config.autosave is False

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = AppConfig(
            default_directory="/path/to/dir",
            yolo_model_path="/path/to/model.pt",
            line_thickness=5,
            font_size=14,
            autosave=True
        )

        assert config.default_directory == "/path/to/dir"
        assert config.yolo_model_path == "/path/to/model.pt"
        assert config.line_thickness == 5
        assert config.font_size == 14
        assert config.autosave is True

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = AppConfig(
            default_directory="/path/to/dir",
            autosave=True
        )

        data = config.to_dict()

        assert data["defaultDirectory"] == "/path/to/dir"
        assert data["autosave"] is True
        assert "lineThickness" in data

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "defaultDirectory": "/test/path",
            "yoloModelPath": "/model/path.pt",
            "lineThickness": 3,
            "fontSize": 12,
            "autosave": True
        }

        config = AppConfig.from_dict(data)

        assert config.default_directory == "/test/path"
        assert config.yolo_model_path == "/model/path.pt"
        assert config.line_thickness == 3
        assert config.font_size == 12
        assert config.autosave is True

    def test_from_dict_with_defaults(self):
        """Test creating config from partial dictionary."""
        data = {"defaultDirectory": "/test/path"}

        config = AppConfig.from_dict(data)

        assert config.default_directory == "/test/path"
        assert config.line_thickness == 2  # default
        assert config.autosave is False  # default


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_load_nonexistent_file(self):
        """Test loading config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.yaml"
            manager = ConfigManager(config_path)

            config = manager.load()

            # Should return default config
            assert config.default_directory == ""
            assert config.line_thickness == 2

    def test_save_and_load(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            manager = ConfigManager(config_path)

            # Create and save config
            config = AppConfig(
                default_directory="/test/dir",
                autosave=True
            )
            manager.save(config)

            # Load it back
            loaded = manager.load()

            assert loaded.default_directory == "/test/dir"
            assert loaded.autosave is True

    def test_update(self):
        """Test updating config values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            manager = ConfigManager(config_path)

            manager.update(default_directory="/new/path", autosave=True)

            assert manager.config.default_directory == "/new/path"
            assert manager.config.autosave is True

    def test_config_property(self):
        """Test config property lazy loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            manager = ConfigManager(config_path)

            # First access loads config
            config1 = manager.config
            config2 = manager.config

            # Should return same instance
            assert config1 is config2


class TestYOLODataConfig:
    """Tests for YOLODataConfig."""

    def test_default_config(self):
        """Test creating config with defaults."""
        config = YOLODataConfig()

        assert config.num_classes == 0
        assert config.class_names == []

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = YOLODataConfig(
            train_path="/train",
            val_path="/val",
            num_classes=3,
            class_names=["cat", "dog", "bird"]
        )

        assert config.train_path == "/train"
        assert config.num_classes == 3
        assert config.class_names == ["cat", "dog", "bird"]

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = YOLODataConfig(
            num_classes=2,
            class_names=["a", "b"]
        )

        data = config.to_dict()

        assert data["nc"] == 2
        assert data["names"] == ["a", "b"]

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "train": "/train/path",
            "val": "/val/path",
            "nc": 2,
            "names": ["cat", "dog"]
        }

        config = YOLODataConfig.from_dict(data)

        assert config.train_path == "/train/path"
        assert config.num_classes == 2
        assert config.class_names == ["cat", "dog"]

    def test_from_dict_with_string_names(self):
        """Test parsing comma-separated names."""
        data = {
            "names": "cat, dog, bird"
        }

        config = YOLODataConfig.from_dict(data)

        assert config.class_names == ["cat", "dog", "bird"]


class TestYOLODataConfigManager:
    """Tests for YOLODataConfigManager."""

    def test_get_classes(self):
        """Test getting class dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = YOLODataConfigManager(Path(tmpdir))
            manager._config = YOLODataConfig(
                num_classes=2,
                class_names=["cat", "dog"]
            )

            classes = manager.get_classes()

            assert classes == {"cat": 0, "dog": 1}

    def test_update_classes(self):
        """Test updating classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = YOLODataConfigManager(Path(tmpdir))

            manager.update_classes({"bird": 0, "fish": 1, "cat": 2})

            assert manager.config.num_classes == 3
            assert "bird" in manager.config.class_names
