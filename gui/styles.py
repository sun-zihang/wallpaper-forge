DARK_QSS = """
QWidget {
    background: #1e1e1e;
    color: #dddddd;
    font-size: 13px;
}
QMainWindow, QDialog { background: #1e1e1e; }
QListWidget, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #2a2a2a;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #3b82f6;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #3b82f6; color: white; }
QPushButton {
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover { background: #2563eb; }
QPushButton:disabled { background: #555555; color: #999999; }
QPushButton#secondary {
    background: #3a3a3a;
    border: 1px solid #555555;
    font-weight: normal;
}
QPushButton#secondary:hover { background: #4a4a4a; }
QProgressBar {
    background: #2a2a2a;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    text-align: center;
    height: 18px;
}
QProgressBar::chunk { background: #3b82f6; }
QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QTabWidget::pane { border: 1px solid #3c3c3c; }
QTabBar::tab {
    background: #2a2a2a;
    padding: 6px 14px;
    border: 1px solid #3c3c3c;
    border-bottom: none;
}
QTabBar::tab:selected { background: #3b82f6; color: white; }
QHeaderView::section {
    background: #2a2a2a;
    border: none;
    padding: 4px;
}
QTableWidget {
    background: #2a2a2a;
    gridline-color: #3c3c3c;
    border: 1px solid #3c3c3c;
}
QLabel#banner {
    background: #7c5e10;
    color: #ffe9a8;
    border-radius: 4px;
    padding: 8px;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #555;
    border-radius: 4px;
    min-height: 20px;
}
QStatusBar { background: #2a2a2a; }
"""
