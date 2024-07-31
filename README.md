# Modern Image Annotator

Modern Image Annotator is a powerful and user-friendly desktop application for annotating images with bounding boxes and polygons. It's designed to streamline the process of creating datasets for computer vision and machine learning projects, particularly those using the YOLO (You Only Look Once) format.

![image](https://github.com/user-attachments/assets/22c4cf92-4d6e-4a88-92fd-2c3d5eef2cf7)

## Features

- **Intuitive Interface**: Easy-to-use GUI for efficient image annotation.
- **Multiple Annotation Types**: Support for both bounding boxes and polygons.
- **YOLO Integration**: Built-in support for YOLO format, including auto-detection using pre-trained models.
- **Class Management**: Easily add, edit, and delete classification labels.
- **Image Navigation**: Convenient image browser with sorting options.
- **Zoom and Pan**: Smooth zooming and panning for detailed annotations.
- **Minimap**: Quick navigation overview of large images.
- **Auto-save**: Optional automatic saving of annotations.
- **Dark Mode**: Supports system-wide dark mode for comfortable use in low-light environments.

## Installation

Follow these steps to set up the Modern Image Annotator on your local machine:

1. Clone the repository:
   ```
   git clone https://github.com/moonwhaler/modern-image-annotator.git
   cd modern-image-annotator
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS and Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To start the Modern Image Annotator:

1. Ensure your virtual environment is activated.

2. Run the main script:
   ```
   python pyQT_YOLO.py
   ```

3. Use the "Open Directory" button to select a folder containing your images.

4. Start annotating by selecting a tool (Select, Box, or Polygon) and drawing on the image.

5. Manage classes using the "Classifications" panel.

6. Save your annotations using the "Save YOLO" button or enable auto-save in the settings.

## Updating

To update the Modern Image Annotator to the latest version:

1. Pull the latest changes from the repository:
   ```
   git pull origin main
   ```

2. Activate your virtual environment if it's not already activated.

3. Update the dependencies:
   ```
   pip install -r requirements.txt --upgrade
   ```

## Contributing

Contributions to the Modern Image Annotator are welcome! Please feel free to submit pull requests, create issues or spread the word.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- YOLO (You Only Look Once) for object detection
- PyQt6 for the graphical user interface
- Ultralytics for the YOLOv8 implementation
