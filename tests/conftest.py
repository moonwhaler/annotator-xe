"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for tests that need it."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_annotation_file(tmp_path):
    """Create a sample YOLO annotation file."""
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text(
        "0 0.5 0.5 0.2 0.1\n"
        "1 0.3 0.3 0.1 0.15\n"
    )
    return txt_path


@pytest.fixture
def sample_data_yaml(tmp_path):
    """Create a sample data.yaml file."""
    yaml_path = tmp_path / "data.yaml"
    yaml_path.write_text(
        "train: /path/to/train\n"
        "val: /path/to/val\n"
        "nc: 2\n"
        "names: ['cat', 'dog']\n"
    )
    return yaml_path
