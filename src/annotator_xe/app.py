"""Application bootstrap for Annotator XE."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def create_application() -> QApplication:
    """
    Create and configure the Qt application.

    Returns:
        Configured QApplication instance
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Annotator XE")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Annotator XE")
    return app


def create_main_window() -> MainWindow:
    """
    Create the main application window.

    Returns:
        MainWindow instance
    """
    return MainWindow()


def run() -> int:
    """
    Run the Annotator XE application.

    Returns:
        Exit code
    """
    logger.info("Starting Annotator XE")

    try:
        app = create_application()
        logger.info("QApplication created")

        window = create_main_window()
        logger.info("MainWindow created")

        window.show()
        logger.info("MainWindow shown")

        return app.exec()

    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        return 1


def main() -> None:
    """Main entry point for the application."""
    sys.exit(run())


if __name__ == "__main__":
    main()
