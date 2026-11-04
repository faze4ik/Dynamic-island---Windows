"""Shared Qt stylesheets."""

ACCENT = "#6f86f5"
ACCENT_HOVER = "#8195ff"

APP_QSS = """
QDialog, QWidget#SettingsRoot {
    background: #0b0d12;
    color: #e8edf8;
}
QWidget {
    color: #e8edf8;
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
    font-size: 12px;
}
QLabel { background: transparent; }
QLabel#Title {
    font-family: "Segoe UI Variable Display", "Segoe UI", sans-serif;
    font-size: 20px;
    font-weight: 600;
    color: #f4f7ff;
}
QLabel#Subtitle { color: #8b95aa; font-size: 11px; }
QLabel#Section {
    color: #a9b3c8;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    padding-top: 2px;
}
QLabel#Hint { color: #7f89a0; font-size: 10.5px; }
QLabel#Value { color: #9aa6c0; font-size: 11px; }
QFrame#Card {
    background: #10131b;
    border: 1px solid #1e2433;
    border-radius: 12px;
}
QFrame#Divider { background: #1d2331; max-height: 1px; border: 0; }
QFrame#ThemePreview {
    background: #10131b;
    border: 1px solid #1e2433;
    border-radius: 12px;
}
QLabel#PreviewTitle { background: transparent; }
QLabel#PreviewSub { background: transparent; }
QLabel#SystemValue { color: #dfe6f5; font-size: 11.5px; }
QProgressBar#Meter {
    background: #141924;
    border: 1px solid #242b3c;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar#Meter::chunk {
    background: #5b74e8;
    border-radius: 2px;
}
QTabWidget::pane {
    border: 1px solid #1d2333;
    border-radius: 12px;
    background: #0e1118;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #8b95aa;
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 12px;
}
QTabBar::tab:selected { background: #1a2131; color: #f2f5ff; }
QTabBar::tab:hover:!selected { color: #c9d3e6; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background: #141924;
    border: 1px solid #242b3c;
    border-radius: 8px;
    padding: 6px 9px;
    color: #e8edf8;
    selection-background-color: #3b4ea1;
    selection-color: #ffffff;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QPlainTextEdit:hover {
    border-color: #333d56;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #5168d8;
}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QPlainTextEdit:disabled {
    color: #616b80;
    background: #10141d;
}
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView {
    background: #151a26;
    border: 1px solid #283044;
    border-radius: 8px;
    selection-background-color: #26325c;
    color: #e8edf8;
    outline: 0;
    padding: 4px;
}
QPushButton {
    background: #1a2030;
    border: 1px solid #2a3247;
    border-radius: 9px;
    padding: 7px 14px;
    color: #dfe6f5;
}
QPushButton:hover { background: #222a3d; border-color: #3a4666; }
QPushButton:pressed { background: #151b29; }
QPushButton#Primary {
    background: #5b74e8;
    border: 1px solid #7088ff;
    color: #ffffff;
    font-weight: 600;
    padding: 8px 22px;
}
QPushButton#Primary:hover { background: #6a82f2; }
QPushButton#Primary:pressed { background: #4c63d4; }
QPushButton#Ghost {
    background: transparent;
    border: 1px solid transparent;
    color: #8d97ad;
}
QPushButton#Ghost:hover { color: #dfe6f5; background: #171c29; }
QCheckBox, QRadioButton { spacing: 8px; color: #dfe6f5; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid #2c3448;
    background: #141924;
}
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #5b74e8;
    border-color: #7088ff;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #46557a; }
QSlider::groove:horizontal { height: 4px; background: #202635; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #5b74e8; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: #eef2ff;
    border: 2px solid #5b74e8;
}
QSlider::handle:horizontal:hover { border-color: #8195ff; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2a3246; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3a4562; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QWidget#TabInner { background: transparent; }
QToolTip {
    background: #151a26;
    color: #e8edf8;
    border: 1px solid #2a3246;
    padding: 5px 8px;
}
"""

MENU_QSS = """
QMenu {
    background: #12151f;
    border: 1px solid #262d40;
    border-radius: 10px;
    padding: 6px;
    color: #e6ebf7;
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
    font-size: 12px;
}
QMenu::item {
    padding: 7px 30px 7px 12px;
    border-radius: 6px;
    background: transparent;
}
QMenu::item:selected { background: #223055; color: #ffffff; }
QMenu::item:disabled { color: #5f6980; }
QMenu::separator { height: 1px; background: #242b3c; margin: 5px 8px; }
QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 6px;
    border-radius: 4px;
}
QMenu::indicator:checked {
    background: #5b74e8;
    border: 1px solid #8195ff;
}
QMenu::right-arrow { width: 10px; height: 10px; }
"""
