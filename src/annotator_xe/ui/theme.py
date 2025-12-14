"""Theme management for Annotator XE."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPalette, QColor


class ThemeMode(Enum):
    """Available theme modes."""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class ThemeColors:
    """Color palette for a theme."""
    # Backgrounds
    background: str
    background_secondary: str
    background_tertiary: str
    surface: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str

    # Accents
    accent: str
    accent_hover: str
    accent_pressed: str

    # Borders
    border: str
    border_light: str

    # Interactive states
    hover: str
    selected: str

    # Status colors
    success: str
    warning: str
    error: str


# Dark theme palette (VS Code inspired)
DARK_THEME = ThemeColors(
    background="#1e1e1e",
    background_secondary="#252526",
    background_tertiary="#2d2d2d",
    surface="#3c3c3c",

    text_primary="#cccccc",
    text_secondary="#9d9d9d",
    text_muted="#808080",

    accent="#0e639c",
    accent_hover="#1177bb",
    accent_pressed="#0d5a8c",

    border="#555555",
    border_light="#3c3c3c",

    hover="#363636",
    selected="#094771",

    success="#22c55e",
    warning="#f59e0b",
    error="#ef4444",
)

# Light theme palette
LIGHT_THEME = ThemeColors(
    background="#ffffff",
    background_secondary="#f5f5f5",
    background_tertiary="#ebebeb",
    surface="#e0e0e0",

    text_primary="#1a1a1a",
    text_secondary="#4a4a4a",
    text_muted="#808080",

    accent="#0066cc",
    accent_hover="#0055aa",
    accent_pressed="#004488",

    border="#cccccc",
    border_light="#e0e0e0",

    hover="#f0f0f0",
    selected="#cce4f7",

    success="#16a34a",
    warning="#d97706",
    error="#dc2626",
)


def get_theme_colors(mode: ThemeMode) -> ThemeColors:
    """Get the color palette for the specified theme mode."""
    if mode == ThemeMode.DARK:
        return DARK_THEME
    elif mode == ThemeMode.LIGHT:
        return LIGHT_THEME
    else:  # SYSTEM
        # Detect system preference
        if _is_system_dark_mode():
            return DARK_THEME
        return LIGHT_THEME


def _is_system_dark_mode() -> bool:
    """Check if the system is in dark mode."""
    app = QApplication.instance()
    if app:
        palette = app.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        # If background luminance is low, it's dark mode
        luminance = (0.299 * bg_color.red() +
                     0.587 * bg_color.green() +
                     0.114 * bg_color.blue()) / 255
        return luminance < 0.5
    return False


def generate_image_browser_stylesheet(colors: ThemeColors) -> str:
    """Generate stylesheet for the image browser widget."""
    return f"""
QWidget#imageBrowserContainer {{
    background-color: {colors.background};
}}

QLineEdit#searchBox {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 6px 10px;
    color: {colors.text_primary};
    font-size: 12px;
}}

QLineEdit#searchBox:focus {{
    border-color: {colors.accent};
}}

QLineEdit#searchBox::placeholder {{
    color: {colors.text_muted};
}}

QLabel#statsLabel {{
    color: {colors.text_muted};
    font-size: 11px;
    padding: 4px 0;
}}

QLabel#sizeLabel {{
    color: {colors.text_muted};
    font-size: 11px;
    min-width: 40px;
}}

QSlider::groove:horizontal {{
    background-color: {colors.surface};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {colors.accent};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {colors.accent_hover};
}}

QListWidget#imageList {{
    background-color: {colors.background_secondary};
    border: none;
    border-radius: 6px;
    padding: 8px;
    outline: none;
}}

QListWidget#imageList::item {{
    background-color: {colors.background_tertiary};
    border: 1px solid {colors.border_light};
    border-radius: 4px;
    padding: 4px;
}}

QListWidget#imageList::item:selected {{
    background-color: {colors.selected};
    border-color: {colors.accent};
}}

QListWidget#imageList::item:hover:!selected {{
    background-color: {colors.hover};
    border-color: {colors.border};
}}

QScrollBar:vertical {{
    background-color: {colors.background_secondary};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.border};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def generate_settings_stylesheet(colors: ThemeColors) -> str:
    """Generate stylesheet for the settings dialog."""
    return f"""
QDialog {{
    background-color: {colors.background};
}}

QListWidget {{
    background-color: {colors.background_secondary};
    border: none;
    border-radius: 8px;
    padding: 8px 4px;
    outline: none;
}}

QListWidget::item {{
    color: {colors.text_primary};
    padding: 12px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}}

QListWidget::item:selected {{
    background-color: {colors.accent};
    color: #ffffff;
}}

QListWidget::item:hover:!selected {{
    background-color: {colors.hover};
}}

QStackedWidget {{
    background-color: transparent;
}}

QGroupBox {{
    background-color: {colors.background_secondary};
    border: 1px solid {colors.border_light};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    padding-top: 32px;
    font-weight: bold;
    color: {colors.text_primary};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    color: {colors.text_primary};
}}

QLabel {{
    color: {colors.text_primary};
}}

QLabel[class="description"] {{
    color: {colors.text_muted};
    font-size: 11px;
}}

QLabel[class="section-title"] {{
    color: {colors.text_primary};
    font-size: 18px;
    font-weight: bold;
}}

QLineEdit {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
    selection-background-color: {colors.accent};
}}

QLineEdit:focus {{
    border-color: {colors.accent};
}}

QLineEdit:disabled {{
    background-color: {colors.background_tertiary};
    color: {colors.text_muted};
}}

QSpinBox {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
    min-width: 80px;
}}

QSpinBox:focus {{
    border-color: {colors.accent};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {colors.border};
    border: none;
    width: 20px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {colors.text_muted};
}}

QComboBox {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
    min-width: 150px;
}}

QComboBox:focus {{
    border-color: {colors.accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {colors.text_primary};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    selection-background-color: {colors.accent};
    color: {colors.text_primary};
    padding: 4px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 8px;
    min-height: 24px;
}}

QPushButton {{
    background-color: {colors.accent};
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: #ffffff;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {colors.accent_hover};
}}

QPushButton:pressed {{
    background-color: {colors.accent_pressed};
}}

QPushButton[class="secondary"] {{
    background-color: {colors.surface};
    color: {colors.text_primary};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {colors.border};
}}

QCheckBox {{
    color: {colors.text_primary};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {colors.border};
    background-color: {colors.surface};
}}

QCheckBox::indicator:checked {{
    background-color: {colors.accent};
    border-color: {colors.accent};
}}

QCheckBox::indicator:hover {{
    border-color: {colors.accent};
}}

QKeySequenceEdit {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
    min-width: 150px;
}}

QKeySequenceEdit:focus {{
    border-color: {colors.accent};
}}

QDialogButtonBox {{
    padding: 16px 0 0 0;
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {colors.background};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.border};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def generate_main_window_stylesheet(colors: ThemeColors) -> str:
    """Generate stylesheet for the main window."""
    return f"""
QMainWindow {{
    background-color: {colors.background};
}}

QDockWidget {{
    color: {colors.text_primary};
    titlebar-close-icon: url(close.png);
    titlebar-normal-icon: url(undock.png);
}}

QDockWidget::title {{
    background-color: {colors.background_secondary};
    padding: 6px;
    text-align: left;
}}

QDockWidget::close-button, QDockWidget::float-button {{
    border: none;
    background: transparent;
    padding: 2px;
}}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: {colors.hover};
}}

QMenuBar {{
    background-color: {colors.background_secondary};
    color: {colors.text_primary};
    padding: 2px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
}}

QMenuBar::item:selected {{
    background-color: {colors.hover};
}}

QMenu {{
    background-color: {colors.background_secondary};
    color: {colors.text_primary};
    border: 1px solid {colors.border};
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {colors.accent};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: {colors.border};
    margin: 4px 8px;
}}

QToolBar {{
    background-color: {colors.background_secondary};
    border: none;
    spacing: 4px;
    padding: 4px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {colors.border};
    margin: 4px 2px;
}}

QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
    color: {colors.text_primary};
}}

QToolButton:hover {{
    background-color: {colors.hover};
}}

QToolButton:checked {{
    background-color: {colors.accent};
}}

QStatusBar {{
    background-color: {colors.background_secondary};
    color: {colors.text_secondary};
}}

QStatusBar::item {{
    border: none;
}}

QScrollArea {{
    background-color: {colors.background};
    border: none;
}}

QListWidget {{
    background-color: {colors.background_secondary};
    border: 1px solid {colors.border_light};
    border-radius: 4px;
    color: {colors.text_primary};
    outline: none;
}}

QListWidget::item {{
    padding: 4px 8px;
}}

QListWidget::item:selected {{
    background-color: {colors.accent};
    color: #ffffff;
}}

QListWidget::item:hover:!selected {{
    background-color: {colors.hover};
}}

QListView {{
    background-color: {colors.background_secondary};
    border: 1px solid {colors.border_light};
    border-radius: 4px;
    color: {colors.text_primary};
    outline: none;
}}

QListView::item {{
    padding: 4px 8px;
}}

QListView::item:selected {{
    background-color: {colors.accent};
    color: #ffffff;
}}

QListView::item:hover:!selected {{
    background-color: {colors.hover};
}}

QComboBox {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 4px 8px;
    color: {colors.text_primary};
}}

QComboBox:focus {{
    border-color: {colors.accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {colors.text_primary};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    selection-background-color: {colors.accent};
    color: {colors.text_primary};
}}

QPushButton {{
    background-color: {colors.accent};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    color: #ffffff;
}}

QPushButton:hover {{
    background-color: {colors.accent_hover};
}}

QPushButton:pressed {{
    background-color: {colors.accent_pressed};
}}

QCheckBox {{
    color: {colors.text_primary};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid {colors.border};
    background-color: {colors.surface};
}}

QCheckBox::indicator:checked {{
    background-color: {colors.accent};
    border-color: {colors.accent};
}}

QLabel {{
    color: {colors.text_primary};
}}

QSlider::groove:horizontal {{
    background-color: {colors.surface};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {colors.accent};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {colors.accent_hover};
}}

QScrollBar:vertical {{
    background-color: {colors.background_secondary};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.border};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {colors.background_secondary};
    height: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background-color: {colors.border};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {colors.text_muted};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""


def generate_dialog_stylesheet(colors: ThemeColors) -> str:
    """Generate stylesheet for generic dialogs."""
    return f"""
QDialog {{
    background-color: {colors.background};
}}

QLabel {{
    color: {colors.text_primary};
}}

QLabel[class="description"] {{
    color: {colors.text_muted};
    font-size: 11px;
}}

QLabel[class="title"] {{
    color: {colors.text_primary};
    font-size: 14px;
    font-weight: bold;
}}

QLineEdit {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
    selection-background-color: {colors.accent};
}}

QLineEdit:focus {{
    border-color: {colors.accent};
}}

QComboBox {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    padding: 8px 12px;
    color: {colors.text_primary};
}}

QComboBox:focus {{
    border-color: {colors.accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {colors.text_primary};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {colors.surface};
    border: 1px solid {colors.border};
    selection-background-color: {colors.accent};
    color: {colors.text_primary};
}}

QPushButton {{
    background-color: {colors.accent};
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: #ffffff;
}}

QPushButton:hover {{
    background-color: {colors.accent_hover};
}}

QPushButton:pressed {{
    background-color: {colors.accent_pressed};
}}

QPushButton[class="secondary"] {{
    background-color: {colors.surface};
    color: {colors.text_primary};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {colors.border};
}}

QCheckBox {{
    color: {colors.text_primary};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {colors.border};
    background-color: {colors.surface};
}}

QCheckBox::indicator:checked {{
    background-color: {colors.accent};
    border-color: {colors.accent};
}}

QRadioButton {{
    color: {colors.text_primary};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid {colors.border};
    background-color: {colors.surface};
}}

QRadioButton::indicator:checked {{
    background-color: {colors.accent};
    border-color: {colors.accent};
}}

QGroupBox {{
    background-color: {colors.background_secondary};
    border: 1px solid {colors.border_light};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    padding-top: 32px;
    font-weight: bold;
    color: {colors.text_primary};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    color: {colors.text_primary};
}}

QListWidget {{
    background-color: {colors.background_secondary};
    border: 1px solid {colors.border_light};
    border-radius: 4px;
    color: {colors.text_primary};
    outline: none;
}}

QListWidget::item {{
    padding: 8px;
    border-radius: 4px;
}}

QListWidget::item:selected {{
    background-color: {colors.accent};
    color: #ffffff;
}}

QListWidget::item:hover:!selected {{
    background-color: {colors.hover};
}}

QDialogButtonBox {{
    padding: 16px 0 0 0;
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

QScrollBar:vertical {{
    background-color: {colors.background};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.border};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


class ThemeManager:
    """Singleton manager for application theme."""

    _instance: Optional[ThemeManager] = None

    def __new__(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._current_mode = ThemeMode.SYSTEM
        self._callbacks: List[Callable[[ThemeMode], None]] = []

    @property
    def current_mode(self) -> ThemeMode:
        """Get the current theme mode."""
        return self._current_mode

    @property
    def colors(self) -> ThemeColors:
        """Get the current theme colors."""
        return get_theme_colors(self._current_mode)

    def set_mode(self, mode: ThemeMode) -> None:
        """Set the theme mode and notify callbacks."""
        if mode != self._current_mode:
            self._current_mode = mode
            for callback in self._callbacks:
                callback(mode)

    def register_callback(self, callback: Callable[[ThemeMode], None]) -> None:
        """Register a callback to be called when theme changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[ThemeMode], None]) -> None:
        """Unregister a theme change callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def apply_to_widget(self, widget: QWidget, stylesheet_generator: Callable[[ThemeColors], str]) -> None:
        """Apply themed stylesheet to a widget."""
        stylesheet = stylesheet_generator(self.colors)
        widget.setStyleSheet(stylesheet)

    def get_image_browser_stylesheet(self) -> str:
        """Get stylesheet for image browser widget."""
        return generate_image_browser_stylesheet(self.colors)

    def get_settings_stylesheet(self) -> str:
        """Get stylesheet for settings dialog."""
        return generate_settings_stylesheet(self.colors)

    def get_main_window_stylesheet(self) -> str:
        """Get stylesheet for main window."""
        return generate_main_window_stylesheet(self.colors)

    def get_dialog_stylesheet(self) -> str:
        """Get stylesheet for generic dialogs."""
        return generate_dialog_stylesheet(self.colors)


def get_theme_manager() -> ThemeManager:
    """Get the theme manager singleton instance."""
    return ThemeManager()
