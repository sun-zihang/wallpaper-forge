from __future__ import annotations


BG = "#14171c"
PANEL = "#1a1e24"
PANEL_HI = "#20252d"
BORDER = "#2a303a"
TEXT = "#e8eaee"
DIM = "#9aa3b0"
FAINT = "#6b7482"
ACCENT = "#e0a458"
ACCENT_TEXT = "#17130c"
OK = "#86b06a"
FAIL = "#d97a72"
RUNNING = "#e0a458"
MONO_FONT = "Consolas"
DISABLED = "#737a84"
ACCENT_TEXT_ON_ACCENT = ACCENT_TEXT

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
}}
QMainWindow, QDialog {{
    background: {BG};
    color: {TEXT};
}}
QWidget#pageRoot {{
    background: {BG};
    color: {TEXT};
}}
QFrame {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel {{
    background: transparent;
    border: 0;
}}
QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QGroupBox {{
    margin-top: 10px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {DIM};
}}
QPushButton {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
    border: 1px solid {ACCENT};
    border-radius: 6px;
    padding: 6px 13px;
    font-weight: 600;
}}
QPushButton#primary {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
    border-color: {ACCENT};
}}
QPushButton#secondary {{
    background: {PANEL_HI};
    color: {TEXT};
    border-color: {BORDER};
    font-weight: 400;
}}
QPushButton:hover {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QPushButton#secondary:hover {{
    background: {PANEL_HI};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: {PANEL_HI};
    color: {ACCENT_TEXT};
}}
QPushButton#secondary:pressed {{
    background: {PANEL};
    color: {TEXT};
}}
QPushButton:disabled, QPushButton#secondary:disabled {{
    background: {PANEL_HI};
    color: {DISABLED};
    border-color: {BORDER};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 7px;
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {DISABLED};
}}
QListWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
}}
QListWidget::item {{
    border-radius: 6px;
    padding: 9px 8px;
    margin: 2px 0;
    color: {DIM};
}}
QListWidget::item:selected {{
    background: {PANEL_HI};
    color: {ACCENT};
}}
QTableWidget {{
    background: {PANEL};
    alternate-background-color: {BG};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    selection-background-color: rgba(224, 164, 88, 28);
    selection-color: {TEXT};
}}
QTableWidget::item:selected {{
    background: rgba(224, 164, 88, 28);
    color: {TEXT};
}}
QHeaderView::section {{
    background: {PANEL_HI};
    color: {DIM};
    border: 0;
    border-right: 1px solid {BORDER};
    padding: 5px;
}}
QProgressBar {{
    background: {BG};
    border: 0;
    border-radius: 8px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 8px;
}}
QSlider::groove:horizontal {{
    background: {BG};
    height: 4px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}
QSlider::handle:horizontal:hover {{
    background: {TEXT};
}}
QCheckBox, QRadioButton {{
    spacing: 6px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    background: {BG};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QStatusBar {{
    background: {PANEL};
    color: {TEXT};
    border-top: 1px solid {BORDER};
}}
QLabel#statusBar {{
    background: {PANEL};
    color: {TEXT};
    font-family: {MONO_FONT};
}}
QLabel#mutedText {{
    color: {DIM};
}}
QLabel#pathText {{
    color: {DIM};
    font-family: {MONO_FONT};
}}
QLabel#faintText {{
    color: {FAINT};
}}
QLabel#banner {{
    background: {PANEL_HI};
    color: {ACCENT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px;
}}
QMessageBox {{
    background: {PANEL};
    color: {TEXT};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {BG};
    border: 0;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {DIM};
    border-radius: 6px;
    min-height: 22px;
    min-width: 22px;
}}
QScrollBar::handle:hover:vertical, QScrollBar::handle:hover:horizontal {{
    background: {ACCENT};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
"""

DARK_QSS = STYLESHEET
