"""YOLO object detection wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

import torch

from .models import Shape, ShapeType
from PyQt6.QtCore import QPointF

logger = logging.getLogger(__name__)


class YOLODetector:
    """
    Wrapper for Ultralytics YOLO object detection.

    Provides a clean interface for running inference and
    converting results to Shape objects.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        """
        Initialize the YOLO detector.

        Args:
            model_path: Path to the YOLO model file (.pt)
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: Optional[Any] = None
        self.model_path: Optional[str] = None
        self._class_names: dict[int, str] = {}

        if model_path:
            self.load_model(model_path)

    @property
    def is_loaded(self) -> bool:
        """Check if a model is loaded."""
        return self.model is not None

    @property
    def class_names(self) -> dict[int, str]:
        """Get the class names from the loaded model."""
        return self._class_names

    def load_model(self, model_path: str) -> bool:
        """
        Load a YOLO model from file.

        Args:
            model_path: Path to the model file

        Returns:
            True if model loaded successfully
        """
        try:
            from ultralytics import YOLO

            self.model = YOLO(model_path)
            self.model.to(self.device)
            self.model_path = model_path

            # Cache class names
            if hasattr(self.model, "names"):
                self._class_names = dict(self.model.names)

            logger.info(f"Loaded YOLO model from {model_path} on {self.device}")
            return True

        except ImportError:
            logger.error("ultralytics package not installed")
            return False
        except Exception as e:
            logger.error(f"Error loading YOLO model: {e}")
            self.model = None
            self.model_path = None
            return False

    def detect(
        self,
        image_path: str,
        confidence: float = 0.25,
        iou_threshold: float = 0.45
    ) -> List[Shape]:
        """
        Run object detection on an image.

        Args:
            image_path: Path to the image file
            confidence: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS

        Returns:
            List of detected Shape objects
        """
        if not self.is_loaded:
            raise ValueError("No model loaded. Call load_model() first.")

        try:
            results = self.model(
                image_path,
                conf=confidence,
                iou=iou_threshold,
                verbose=False
            )

            if not results:
                return []

            return self._convert_results(results[0])

        except Exception as e:
            logger.error(f"Detection failed: {e}")
            raise

    def _convert_results(self, result: Any) -> List[Shape]:
        """
        Convert YOLO results to Shape objects.

        Args:
            result: Single YOLO result object

        Returns:
            List of Shape objects
        """
        shapes: List[Shape] = []

        # Process bounding boxes
        if hasattr(result, "boxes") and result.boxes is not None:
            for box in result.boxes:
                try:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    class_id = int(box.cls)
                    label = result.names.get(class_id, str(class_id))

                    shape = Shape(
                        type=ShapeType.BOX,
                        points=[QPointF(x1, y1), QPointF(x2, y2)],
                        label=label
                    )
                    shapes.append(shape)

                except Exception as e:
                    logger.warning(f"Error processing box detection: {e}")

        # Process segmentation masks
        if hasattr(result, "masks") and result.masks is not None:
            for i, mask in enumerate(result.masks):
                try:
                    if not hasattr(mask, "xy") or not mask.xy or len(mask.xy) == 0:
                        logger.warning("Invalid mask shape detected")
                        continue

                    polygon = mask.xy[0].tolist()
                    if len(polygon) < 3:
                        continue

                    points = [QPointF(x, y) for x, y in polygon]

                    # Get class ID from boxes if available
                    class_id = 0
                    if hasattr(result, "boxes") and i < len(result.boxes):
                        class_id = int(result.boxes[i].cls)

                    label = result.names.get(class_id, str(class_id))

                    shape = Shape(
                        type=ShapeType.POLYGON,
                        points=points,
                        label=label
                    )
                    shapes.append(shape)

                except Exception as e:
                    logger.warning(f"Error processing mask detection: {e}")

        logger.info(f"Detected {len(shapes)} objects")
        return shapes

    def get_device_info(self) -> str:
        """Get information about the compute device."""
        if self.device == "cuda":
            try:
                device_name = torch.cuda.get_device_name(0)
                return f"CUDA: {device_name}"
            except Exception:
                return "CUDA (unknown device)"
        return "CPU"
