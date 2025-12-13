"""Workspace layout management for Annotator XE."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

# Default workspace file path
DEFAULT_WORKSPACE_PATH = Path("workspaces.yaml")


class WorkspaceManager:
    """
    Manager for saving and loading dock widget layouts.

    Provides persistence for window arrangements so users
    can customize and restore their preferred layouts.
    """

    # Mapping between Qt dock areas and integers for serialization
    AREA_TO_INT = {
        Qt.DockWidgetArea.LeftDockWidgetArea: 1,
        Qt.DockWidgetArea.RightDockWidgetArea: 2,
        Qt.DockWidgetArea.TopDockWidgetArea: 4,
        Qt.DockWidgetArea.BottomDockWidgetArea: 8,
        Qt.DockWidgetArea.AllDockWidgetAreas: 15,
        Qt.DockWidgetArea.NoDockWidgetArea: 0,
    }

    INT_TO_AREA = {v: k for k, v in AREA_TO_INT.items()}

    def __init__(self, workspace_path: Path = DEFAULT_WORKSPACE_PATH) -> None:
        """
        Initialize the workspace manager.

        Args:
            workspace_path: Path to the workspace YAML file
        """
        self.workspace_path = workspace_path
        self._workspaces: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load workspaces from file."""
        if not self.workspace_path.exists():
            self._workspaces = {"Default": self.get_default_layout()}
            return

        try:
            with open(self.workspace_path, "r") as f:
                loaded = yaml.safe_load(f) or {}

            self._workspaces = {}
            for name, layout in loaded.items():
                processed = {}
                for key, value in layout.items():
                    if isinstance(value, dict) and "area" in value:
                        value = value.copy()
                        value["area"] = self.INT_TO_AREA.get(
                            value["area"],
                            Qt.DockWidgetArea.NoDockWidgetArea
                        )
                    processed[key] = value
                self._workspaces[name] = processed

            logger.info(f"Loaded {len(self._workspaces)} workspaces")

        except yaml.YAMLError as e:
            logger.error(f"Error parsing workspaces file: {e}")
            self._workspaces = {"Default": self.get_default_layout()}
        except Exception as e:
            logger.error(f"Error loading workspaces: {e}")
            self._workspaces = {"Default": self.get_default_layout()}

    def save(self) -> bool:
        """
        Save workspaces to file.

        Returns:
            True if save was successful
        """
        try:
            serializable = {}
            for name, layout in self._workspaces.items():
                ser_layout = {}
                for key, value in layout.items():
                    if isinstance(value, dict) and "area" in value:
                        value = value.copy()
                        area = value.get("area")
                        if isinstance(area, Qt.DockWidgetArea):
                            value["area"] = self.AREA_TO_INT.get(area, 0)
                    ser_layout[key] = value
                serializable[name] = ser_layout

            with open(self.workspace_path, "w") as f:
                yaml.dump(serializable, f, default_flow_style=False)

            logger.info(f"Saved {len(self._workspaces)} workspaces")
            return True

        except Exception as e:
            logger.error(f"Error saving workspaces: {e}")
            return False

    @property
    def workspaces(self) -> Dict[str, Dict[str, Any]]:
        """Get all workspace layouts."""
        return self._workspaces

    @property
    def workspace_names(self) -> list[str]:
        """Get list of user-visible workspace names (excludes internal workspaces)."""
        return [name for name in self._workspaces.keys() if not name.startswith("_")]

    def get_workspace(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a workspace layout by name.

        Args:
            name: Workspace name

        Returns:
            Layout dictionary or None
        """
        return self._workspaces.get(name)

    def add_workspace(self, name: str, layout: Dict[str, Any]) -> None:
        """
        Add or update a workspace.

        Args:
            name: Workspace name
            layout: Layout dictionary
        """
        self._workspaces[name] = layout
        self.save()

    def remove_workspace(self, name: str) -> bool:
        """
        Remove a workspace.

        Args:
            name: Workspace name to remove

        Returns:
            True if workspace was removed
        """
        # Don't allow deletion of Default or internal workspaces (prefixed with _)
        if name in self._workspaces and name != "Default" and not name.startswith("_"):
            del self._workspaces[name]
            self.save()
            return True
        return False

    def has_workspace(self, name: str) -> bool:
        """Check if a workspace exists."""
        return name in self._workspaces

    @staticmethod
    def get_default_layout() -> Dict[str, Any]:
        """
        Get the default workspace layout.

        Returns:
            Default layout dictionary
        """
        default_left_width = 250
        default_right_width = 300
        default_height = 300

        return {
            "Image Browser": {
                "area": Qt.DockWidgetArea.LeftDockWidgetArea,
                "floating": False,
                "geometry": None,
                "visible": True,
                "size": {"width": default_left_width, "height": default_height}
            },
            "Miniature View": {
                "area": Qt.DockWidgetArea.RightDockWidgetArea,
                "floating": False,
                "geometry": None,
                "visible": True,
                "size": {"width": default_right_width, "height": default_height}
            },
            "Classifications": {
                "area": Qt.DockWidgetArea.RightDockWidgetArea,
                "floating": False,
                "geometry": None,
                "visible": True,
                "size": {"width": default_right_width, "height": default_height}
            },
            "Shapes": {
                "area": Qt.DockWidgetArea.RightDockWidgetArea,
                "floating": False,
                "geometry": None,
                "visible": True,
                "size": {"width": default_right_width, "height": default_height}
            },
            "main_window": {
                "geometry": {"x": 100, "y": 100, "width": 1200, "height": 800},
                "state": "normal",  # normal, maximized, minimized
                "qt_state": None,  # Base64-encoded QMainWindow state for dock layout
            }
        }


def area_to_int(area: Qt.DockWidgetArea) -> int:
    """Convert Qt dock area to integer."""
    return WorkspaceManager.AREA_TO_INT.get(area, 0)


def int_to_area(value: int) -> Qt.DockWidgetArea:
    """Convert integer to Qt dock area."""
    return WorkspaceManager.INT_TO_AREA.get(value, Qt.DockWidgetArea.NoDockWidgetArea)
