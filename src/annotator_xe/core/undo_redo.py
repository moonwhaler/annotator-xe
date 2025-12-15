"""Undo/Redo system using the Command pattern."""

from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from ..core.models import Shape

logger = logging.getLogger(__name__)


class Command(ABC):
    """Abstract base class for undoable commands."""

    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the command."""
        pass


class AddShapeCommand(Command):
    """Command for adding a shape."""

    def __init__(
        self,
        shapes_list: List[Shape],
        shape: Shape,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shapes_list = shapes_list
        self._shape = shape
        self._on_change = on_change

    def execute(self) -> None:
        if self._shape not in self._shapes_list:
            self._shapes_list.append(self._shape)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        if self._shape in self._shapes_list:
            self._shapes_list.remove(self._shape)
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        shape_type = "Box" if self._shape.type.value == "box" else "Polygon"
        return f"Add {shape_type}"


class DeleteShapeCommand(Command):
    """Command for deleting a shape."""

    def __init__(
        self,
        shapes_list: List[Shape],
        shape: Shape,
        index: int,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shapes_list = shapes_list
        self._shape = shape
        self._index = index
        self._on_change = on_change

    def execute(self) -> None:
        if self._shape in self._shapes_list:
            self._shapes_list.remove(self._shape)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        if self._shape not in self._shapes_list:
            self._shapes_list.insert(self._index, self._shape)
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        shape_type = "Box" if self._shape.type.value == "box" else "Polygon"
        return f"Delete {shape_type}"


class MoveShapeCommand(Command):
    """Command for moving a shape."""

    def __init__(
        self,
        shape: Shape,
        old_points: list,
        new_points: list,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shape = shape
        self._old_points = old_points
        self._new_points = new_points
        self._on_change = on_change

    def execute(self) -> None:
        self._shape.points = [p.__class__(p) for p in self._new_points]
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        self._shape.points = [p.__class__(p) for p in self._old_points]
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        return "Move Shape"


class ResizeShapeCommand(Command):
    """Command for resizing a shape."""

    def __init__(
        self,
        shape: Shape,
        old_points: list,
        new_points: list,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shape = shape
        self._old_points = old_points
        self._new_points = new_points
        self._on_change = on_change

    def execute(self) -> None:
        self._shape.points = [p.__class__(p) for p in self._new_points]
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        self._shape.points = [p.__class__(p) for p in self._old_points]
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        return "Resize Shape"


class MovePointCommand(Command):
    """Command for moving a single point."""

    def __init__(
        self,
        shape: Shape,
        point_index: int,
        old_position: 'QPointF',
        new_position: 'QPointF',
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shape = shape
        self._point_index = point_index
        self._old_position = old_position
        self._new_position = new_position
        self._on_change = on_change

    def execute(self) -> None:
        if 0 <= self._point_index < len(self._shape.points):
            self._shape.points[self._point_index] = self._new_position.__class__(self._new_position)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        if 0 <= self._point_index < len(self._shape.points):
            self._shape.points[self._point_index] = self._old_position.__class__(self._old_position)
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        return "Move Point"


class ChangeLabelCommand(Command):
    """Command for changing a shape's label."""

    def __init__(
        self,
        shape: Shape,
        old_label: str,
        new_label: str,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shape = shape
        self._old_label = old_label
        self._new_label = new_label
        self._on_change = on_change

    def execute(self) -> None:
        self._shape.label = self._new_label
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        self._shape.label = self._old_label
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        return f"Change Label to '{self._new_label}'"


class DeletePointsCommand(Command):
    """Command for deleting points from a polygon."""

    def __init__(
        self,
        shape: Shape,
        deleted_points: List[tuple],  # List of (index, point) tuples
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        self._shape = shape
        self._deleted_points = sorted(deleted_points, key=lambda x: x[0], reverse=True)
        self._on_change = on_change

    def execute(self) -> None:
        # Delete in reverse order to maintain indices
        for index, _ in self._deleted_points:
            if 0 <= index < len(self._shape.points):
                del self._shape.points[index]
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        # Restore in forward order
        for index, point in reversed(self._deleted_points):
            self._shape.points.insert(index, point)
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        count = len(self._deleted_points)
        return f"Delete {count} Point{'s' if count > 1 else ''}"


class BatchChangeLabelCommand(Command):
    """Command for changing labels on multiple shapes at once."""

    def __init__(
        self,
        shapes: List[Shape],
        old_label: str,
        new_label: str,
        on_change: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Initialize the batch label change command.

        Args:
            shapes: List of shapes to modify (only those with old_label will be changed)
            old_label: The label to replace
            new_label: The new label to apply
            on_change: Callback to execute after changes
        """
        self._shapes = shapes
        self._old_label = old_label
        self._new_label = new_label
        self._on_change = on_change
        # Track which shapes were actually modified
        self._affected_shapes: List[Shape] = []

    def execute(self) -> None:
        self._affected_shapes = []
        for shape in self._shapes:
            if shape.label == self._old_label:
                shape.label = self._new_label
                self._affected_shapes.append(shape)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        for shape in self._affected_shapes:
            shape.label = self._old_label
        if self._on_change:
            self._on_change()

    @property
    def description(self) -> str:
        if self._new_label:
            return f"Rename '{self._old_label}' to '{self._new_label}'"
        else:
            return f"Clear label '{self._old_label}'"


class UndoRedoManager(QObject):
    """
    Manages undo/redo stacks for the application.

    Emits signals when the undo/redo state changes so UI can update.
    """

    state_changed = pyqtSignal()  # Emitted when undo/redo availability changes

    def __init__(self, max_history: int = 100) -> None:
        """
        Initialize the undo/redo manager.

        Args:
            max_history: Maximum number of commands to keep in history
        """
        super().__init__()
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_history = max_history

    def execute(self, command: Command) -> None:
        """
        Execute a command and add it to the undo stack.

        Args:
            command: The command to execute
        """
        command.execute()
        self._undo_stack.append(command)

        # Clear redo stack when new command is executed
        self._redo_stack.clear()

        # Limit history size
        while len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

        logger.debug(f"Executed: {command.description}")
        self.state_changed.emit()

    def undo(self) -> bool:
        """
        Undo the last command.

        Returns:
            True if a command was undone
        """
        if not self._undo_stack:
            return False

        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)

        logger.debug(f"Undone: {command.description}")
        self.state_changed.emit()
        return True

    def redo(self) -> bool:
        """
        Redo the last undone command.

        Returns:
            True if a command was redone
        """
        if not self._redo_stack:
            return False

        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)

        logger.debug(f"Redone: {command.description}")
        self.state_changed.emit()
        return True

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    def undo_description(self) -> str:
        """Get description of the command that would be undone."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return ""

    def redo_description(self) -> str:
        """Get description of the command that would be redone."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def clear(self) -> None:
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.state_changed.emit()

    @property
    def undo_count(self) -> int:
        """Get the number of commands that can be undone."""
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        """Get the number of commands that can be redone."""
        return len(self._redo_stack)

    def get_history(self) -> List[Tuple[int, str, bool]]:
        """
        Get the full history as a list of tuples.

        Returns:
            List of (index, description, is_undo_stack) tuples.
            - Undo stack items (past actions) have is_undo_stack=True
            - Redo stack items (undone actions) have is_undo_stack=False
            - Index is the position in respective stack (0 = oldest)
        """
        history = []

        # Add undo stack items (past actions, oldest first)
        for i, cmd in enumerate(self._undo_stack):
            history.append((i, cmd.description, True))

        # Add redo stack items (future actions, in reverse so newest redo is first)
        for i, cmd in enumerate(reversed(self._redo_stack)):
            history.append((len(self._redo_stack) - 1 - i, cmd.description, False))

        return history

    def undo_to(self, steps: int) -> bool:
        """
        Undo multiple steps at once.

        Args:
            steps: Number of steps to undo

        Returns:
            True if at least one command was undone
        """
        if steps <= 0:
            return False

        success = False
        for _ in range(steps):
            if not self._undo_stack:
                break

            command = self._undo_stack.pop()
            command.undo()
            self._redo_stack.append(command)
            logger.debug(f"Undone: {command.description}")
            success = True

        # Only emit once after all undos are complete
        if success:
            self.state_changed.emit()

        return success

    def redo_to(self, steps: int) -> bool:
        """
        Redo multiple steps at once.

        Args:
            steps: Number of steps to redo

        Returns:
            True if at least one command was redone
        """
        if steps <= 0:
            return False

        success = False
        for _ in range(steps):
            if not self._redo_stack:
                break

            command = self._redo_stack.pop()
            command.execute()
            self._undo_stack.append(command)
            logger.debug(f"Redone: {command.description}")
            success = True

        # Only emit once after all redos are complete
        if success:
            self.state_changed.emit()

        return success

    def set_max_history(self, max_history: int) -> None:
        """
        Update the maximum history size.

        Args:
            max_history: New maximum number of commands to keep
        """
        self._max_history = max(1, max_history)  # Ensure at least 1

        # Trim undo stack if necessary
        while len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

        self.state_changed.emit()
