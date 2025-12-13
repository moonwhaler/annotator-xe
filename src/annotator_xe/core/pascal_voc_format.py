"""Pascal VOC annotation format reading and writing."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.dom import minidom

from PyQt6.QtCore import QPointF

from .annotation_format import AnnotationFormat
from .models import Shape, ShapeType

logger = logging.getLogger(__name__)


class PascalVOCAnnotationFormat(AnnotationFormat):
    """
    Pascal VOC annotation format handler.

    Pascal VOC format stores annotations in XML files with one file per image.
    It only supports bounding boxes (not polygons).

    XML structure:
    <annotation>
        <folder>images</folder>
        <filename>image.jpg</filename>
        <size>
            <width>1920</width>
            <height>1080</height>
            <depth>3</depth>
        </size>
        <object>
            <name>cat</name>
            <pose>Unspecified</pose>
            <truncated>0</truncated>
            <difficult>0</difficult>
            <bndbox>
                <xmin>100</xmin>
                <ymin>100</ymin>
                <xmax>200</xmax>
                <ymax>200</ymax>
            </bndbox>
        </object>
    </annotation>
    """

    def __init__(self, classes: Optional[Dict[str, int]] = None) -> None:
        """Initialize the Pascal VOC format handler."""
        super().__init__(classes)

    @property
    def format_name(self) -> str:
        """Return the format name."""
        return "pascal_voc"

    @property
    def is_per_image(self) -> bool:
        """Pascal VOC uses one .xml file per image."""
        return True

    @property
    def file_extension(self) -> str:
        """Pascal VOC uses .xml files."""
        return ".xml"

    @property
    def supports_polygons(self) -> bool:
        """Pascal VOC only supports bounding boxes."""
        return False

    def read_image(
        self,
        image_path: Path,
        img_width: int,
        img_height: int
    ) -> List[Shape]:
        """
        Read annotations for a single image from XML file.

        Args:
            image_path: Path to the image file
            img_width: Image width in pixels (used for validation)
            img_height: Image height in pixels (used for validation)

        Returns:
            List of Shape objects (bounding boxes only)
        """
        xml_path = self.get_annotation_path(image_path)
        if not xml_path.exists():
            logger.debug(f"Pascal VOC annotation file not found: {xml_path}")
            return []

        shapes: List[Shape] = []

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for obj in root.findall("object"):
                name_elem = obj.find("name")
                if name_elem is None:
                    continue

                label = name_elem.text or ""

                bndbox = obj.find("bndbox")
                if bndbox is None:
                    continue

                try:
                    xmin = float(bndbox.find("xmin").text)
                    ymin = float(bndbox.find("ymin").text)
                    xmax = float(bndbox.find("xmax").text)
                    ymax = float(bndbox.find("ymax").text)

                    # Ensure coordinates are within bounds
                    xmin = max(0, min(xmin, img_width))
                    ymin = max(0, min(ymin, img_height))
                    xmax = max(0, min(xmax, img_width))
                    ymax = max(0, min(ymax, img_height))

                    shape = Shape(
                        type=ShapeType.BOX,
                        points=[QPointF(xmin, ymin), QPointF(xmax, ymax)],
                        label=label
                    )
                    shapes.append(shape)

                except (AttributeError, ValueError, TypeError) as e:
                    logger.warning(f"Error parsing bndbox in {xml_path}: {e}")
                    continue

            logger.info(f"Loaded {len(shapes)} annotations from {xml_path}")

        except ET.ParseError as e:
            logger.error(f"Error parsing Pascal VOC XML {xml_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading Pascal VOC file {xml_path}: {e}")

        return shapes

    def write_image(
        self,
        image_path: Path,
        shapes: List[Shape],
        img_width: int,
        img_height: int
    ) -> bool:
        """
        Write annotations for a single image to XML file.

        Note: Polygon shapes will be converted to bounding boxes.

        Args:
            image_path: Path to the image file
            shapes: List of shapes to write
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            True if write was successful
        """
        xml_path = self.get_annotation_path(image_path)

        # Delete file if no shapes
        if not shapes:
            if xml_path.exists():
                try:
                    xml_path.unlink()
                    logger.info(f"Deleted empty Pascal VOC file: {xml_path}")
                except Exception as e:
                    logger.error(f"Error deleting Pascal VOC file: {e}")
                    return False
            return True

        try:
            # Create XML structure
            annotation = ET.Element("annotation")

            # Folder
            folder_elem = ET.SubElement(annotation, "folder")
            folder_elem.text = image_path.parent.name

            # Filename
            filename_elem = ET.SubElement(annotation, "filename")
            filename_elem.text = image_path.name

            # Path
            path_elem = ET.SubElement(annotation, "path")
            path_elem.text = str(image_path.absolute())

            # Source
            source_elem = ET.SubElement(annotation, "source")
            database_elem = ET.SubElement(source_elem, "database")
            database_elem.text = "Unknown"

            # Size
            size_elem = ET.SubElement(annotation, "size")
            width_elem = ET.SubElement(size_elem, "width")
            width_elem.text = str(img_width)
            height_elem = ET.SubElement(size_elem, "height")
            height_elem.text = str(img_height)
            depth_elem = ET.SubElement(size_elem, "depth")
            depth_elem.text = "3"  # Assume RGB

            # Segmented
            segmented_elem = ET.SubElement(annotation, "segmented")
            segmented_elem.text = "0"

            # Objects
            polygon_converted = False
            for shape in shapes:
                obj_elem = ET.SubElement(annotation, "object")

                name_elem = ET.SubElement(obj_elem, "name")
                name_elem.text = shape.label if shape.label else "unknown"

                pose_elem = ET.SubElement(obj_elem, "pose")
                pose_elem.text = "Unspecified"

                truncated_elem = ET.SubElement(obj_elem, "truncated")
                truncated_elem.text = "0"

                difficult_elem = ET.SubElement(obj_elem, "difficult")
                difficult_elem.text = "0"

                # Get bounding box coordinates
                if shape.type == ShapeType.BOX and len(shape.points) >= 2:
                    xmin = min(shape.points[0].x(), shape.points[1].x())
                    ymin = min(shape.points[0].y(), shape.points[1].y())
                    xmax = max(shape.points[0].x(), shape.points[1].x())
                    ymax = max(shape.points[0].y(), shape.points[1].y())
                elif shape.type == ShapeType.POLYGON and shape.points:
                    # Convert polygon to bounding box
                    polygon_converted = True
                    xs = [p.x() for p in shape.points]
                    ys = [p.y() for p in shape.points]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                else:
                    continue

                bndbox_elem = ET.SubElement(obj_elem, "bndbox")
                xmin_elem = ET.SubElement(bndbox_elem, "xmin")
                xmin_elem.text = str(int(round(xmin)))
                ymin_elem = ET.SubElement(bndbox_elem, "ymin")
                ymin_elem.text = str(int(round(ymin)))
                xmax_elem = ET.SubElement(bndbox_elem, "xmax")
                xmax_elem.text = str(int(round(xmax)))
                ymax_elem = ET.SubElement(bndbox_elem, "ymax")
                ymax_elem.text = str(int(round(ymax)))

            if polygon_converted:
                logger.warning(
                    f"Polygons converted to bounding boxes in {xml_path} "
                    "(Pascal VOC doesn't support polygons)"
                )

            # Write XML with pretty printing
            xml_str = ET.tostring(annotation, encoding="unicode")
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent="    ")

            # Remove extra blank lines from minidom output
            lines = [line for line in pretty_xml.split("\n") if line.strip()]
            pretty_xml = "\n".join(lines[1:])  # Skip XML declaration line

            with open(xml_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(pretty_xml)

            logger.info(f"Saved {len(shapes)} annotations to {xml_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing Pascal VOC file {xml_path}: {e}")
            return False

    def load_directory(
        self,
        directory: Path
    ) -> Dict[str, List[Shape]]:
        """
        Load all Pascal VOC annotations from a directory.

        Note: This method doesn't load shapes directly because it needs
        image dimensions. Use read_image() for individual images.

        Returns:
            Empty dict - use read_image() with dimensions for actual loading
        """
        # For per-image formats, we don't pre-load everything
        return {}

    def save_directory(
        self,
        directory: Path,
        annotations: Dict[str, List[Shape]],
        image_sizes: Dict[str, Tuple[int, int]]
    ) -> bool:
        """Save all annotations to individual Pascal VOC XML files."""
        success = True
        for filename, shapes in annotations.items():
            image_path = directory / filename
            if filename in image_sizes:
                width, height = image_sizes[filename]
                if not self.write_image(image_path, shapes, width, height):
                    success = False
        return success

    def get_annotation_path(self, image_path: Path) -> Path:
        """Get the .xml annotation file path for an image."""
        return image_path.with_suffix(".xml")

    def has_annotation(self, image_path: Path) -> bool:
        """Check if an image has Pascal VOC annotations."""
        xml_path = self.get_annotation_path(image_path)
        if not xml_path.exists():
            return False

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            # Check if there's at least one object
            return len(root.findall("object")) > 0
        except Exception:
            return False

    def get_classes_from_directory(self, directory: Path) -> Dict[str, int]:
        """
        Extract class names from all XML files in directory.

        Returns:
            Dictionary mapping class names to IDs
        """
        classes: Dict[str, int] = {}
        class_counter = 0

        for xml_path in directory.glob("*.xml"):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()

                for obj in root.findall("object"):
                    name_elem = obj.find("name")
                    if name_elem is not None and name_elem.text:
                        class_name = name_elem.text
                        if class_name not in classes:
                            classes[class_name] = class_counter
                            class_counter += 1
            except Exception:
                continue

        return classes if classes else self.classes.copy()
