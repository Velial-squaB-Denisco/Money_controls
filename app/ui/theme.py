from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.db import SessionLocal
from app.repositories import settings_repository


LIGHT_COLORS = {
    "bg": "#f5f7fb",
    "panel": "#eef2f7",
    "card": "#ffffff",
    "text": "#111827",
    "muted": "#6b7280",
    "border": "#d9e0ea",
    "accent": "#0f766e",
    "accent_hover": "#0d5f59",
    "income": "#15803d",
    "expense": "#b91c1c",
    "selection": "#99f6e4",
    "button_text": "#ffffff",
}

DARK_COLORS = {
    "bg": "#0b1220",
    "panel": "#111827",
    "card": "#171f2e",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "border": "#2b3648",
    "accent": "#2dd4bf",
    "accent_hover": "#5eead4",
    "income": "#4ade80",
    "expense": "#f87171",
    "selection": "#134e4a",
    "button_text": "#000000",
}


def get_colors(theme_name: str | None = None) -> dict:
    if theme_name == "dark":
        return DARK_COLORS

    return LIGHT_COLORS


def get_theme() -> str:
    try:
        with SessionLocal() as session:
            theme_name = settings_repository.get_setting(
                session=session,
                key="ui_theme",
                default="light",
            )

        return theme_name or "light"
    except Exception:
        return "light"


def set_theme(theme_name: str) -> None:
    with SessionLocal() as session:
        settings_repository.set_setting(
            session=session,
            key="ui_theme",
            value=theme_name,
        )

        session.commit()

    apply_theme(theme_name)


def build_qss(theme_name: str) -> str:
    colors = get_colors(theme_name)

    qss = """
    QMainWindow {
        background-color: @bg;
    }

    QDialog {
        background-color: @bg;
    }

    QWidget {
        background-color: @bg;
        color: @text;
        font-size: 14px;
    }

    QListWidget#sidebarMenu {
        background-color: @panel;
        border: none;
    }

    QListWidget#sidebarMenu::item {
        padding: 10px 12px;
        border-radius: 10px;
        margin: 3px 8px;
        color: @muted;
        font-size: 14px;
    }

    QListWidget#sidebarMenu::item:selected {
        background-color: @accent;
        color: @button_text;
        font-weight: 600;
    }

    QListWidget#sidebarMenu::item:hover:!selected {
        background-color: @card;
        color: @text;
    }

    QListWidget {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 10px;
    }

    QListWidget::item {
        padding: 6px;
        border-radius: 8px;
    }

    QListWidget::item:selected {
        background-color: @selection;
        color: @text;
    }

    QPushButton {
        background-color: @accent;
        color: @button_text;
        border: none;
        border-radius: 10px;
        padding: 9px 16px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: @accent_hover;
        color: @button_text;
    }

    QPushButton:pressed {
        background-color: @accent;
        color: @button_text;
    }

    QPushButton:disabled {
        background-color: @border;
        color: @muted;
    }

    QPushButton#secondaryButton {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
    }

    QPushButton#secondaryButton:hover {
        background-color: @panel;
    }

    QPushButton#dangerButton {
        background-color: @expense;
        color: #ffffff;
    }

    QPushButton#dangerButton:hover {
        background-color: @expense;
        color: #ffffff;
    }

    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: @selection;
    }

    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
        border: 1px solid @accent;
    }

    QComboBox::drop-down {
        border: none;
        width: 26px;
    }

    QComboBox QAbstractItemView {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 10px;
        selection-background-color: @selection;
        selection-color: @text;
        padding: 4px;
    }

    QTableWidget {
        background-color: @card;
        alternate-background-color: @panel;
        color: @text;
        border: 1px solid @border;
        border-radius: 14px;
        gridline-color: transparent;
        selection-background-color: @selection;
        selection-color: @text;
    }

    QTableWidget::item {
        padding: 8px 12px;
        border: none;
        border-bottom: 1px solid @border;
    }

    QTableWidget::item:hover {
        background-color: @panel;
    }

    QTableWidget::item:selected {
        background-color: @selection;
        color: @text;
    }

    QHeaderView::section {
        background-color: @panel;
        color: @muted;
        font-size: 12px;
        font-weight: 700;
        padding: 10px 12px;
        border: none;
        border-bottom: 1px solid @border;
    }

    QHeaderView::section:first {
        border-top-left-radius: 14px;
    }

    QHeaderView::section:last {
        border-top-right-radius: 14px;
    }

    QTabWidget::pane {
        border: none;
    }

    QTabBar::tab {
        background: transparent;
        color: @muted;
        padding: 10px 16px;
        border-bottom: 2px solid transparent;
        margin-right: 6px;
    }

    QTabBar::tab:selected {
        color: @text;
        font-weight: 600;
        border-bottom: 2px solid @accent;
    }

    QGroupBox {
        background-color: @card;
        border: 1px solid @border;
        border-radius: 12px;
        margin-top: 14px;
        padding-top: 12px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: @muted;
        font-size: 12px;
        font-weight: 600;
    }

    QTextBrowser {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 12px;
    }

    QProgressBar {
        background-color: @panel;
        color: @text;
        border: 1px solid @border;
        border-radius: 8px;
        text-align: center;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 2px;
    }

    QScrollBar::handle:vertical {
        background: @border;
        border-radius: 4px;
        min-height: 30px;
    }

    QScrollBar::handle:vertical:hover {
        background: @muted;
    }

    QScrollBar:horizontal {
        background: transparent;
        height: 8px;
        margin: 2px;
    }

    QScrollBar::handle:horizontal {
        background: @border;
        border-radius: 4px;
        min-width: 30px;
    }

    QScrollBar::handle:horizontal:hover {
        background: @muted;
    }

    QScrollBar::add-line, QScrollBar::sub-line {
        height: 0;
        width: 0;
    }

    QMenu {
        background-color: @card;
        border: 1px solid @border;
        border-radius: 10px;
        padding: 6px;
    }

    QMenu::item {
        padding: 8px 14px;
        border-radius: 8px;
        color: @text;
    }

    QMenu::item:selected {
        background-color: @selection;
    }

    QToolTip {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 8px;
        padding: 6px;
    }

    QLabel {
        background: transparent;
    }

    QLabel#statCard {
        background-color: @card;
        color: @text;
        border: 1px solid @border;
        border-radius: 12px;
        padding: 14px;
        font-size: 14px;
    }
    
    QLabel#pageTitle {
        background: transparent;
        color: @text;
        font-size: 22px;
        font-weight: 700;
        padding: 4px 0 10px 0;
    }

    QLabel#emptyState {
        background: transparent;
        color: @muted;
        font-size: 15px;
        padding: 40px;
    }
    """

    for key, value in sorted(
        colors.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        qss = qss.replace(f"@{key}", value)

    return qss


def build_web_css(theme_name: str) -> str:
    colors = get_colors(theme_name)

    css = """
    body {
        background-color: @bg;
        color: @text;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 16px;
        line-height: 1.5;
    }

    h1, h2, h3, h4 {
        margin-top: 0;
        line-height: 1.3;
    }

    a {
        color: @accent;
    }

    table {
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
        background-color: @card;
        border-radius: 10px;
        overflow: hidden;
    }

    th, td {
        border: 1px solid @border;
        padding: 8px 10px;
        text-align: left;
        vertical-align: top;
    }

    th {
        background-color: @panel;
        color: @muted;
    }

    code {
        background-color: @panel;
        border-radius: 4px;
        padding: 2px 4px;
    }

    pre {
        background-color: @panel;
        border: 1px solid @border;
        border-radius: 8px;
        padding: 10px;
        overflow-x: auto;
    }

    blockquote {
        border-left: 3px solid @accent;
        margin-left: 0;
        padding-left: 12px;
        color: @muted;
    }

    .msg {
        background-color: @card;
        border: 1px solid @border;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .msg.user {
        border-left: 4px solid @accent;
    }

    .msg.assistant {
        border-left: 4px solid @income;
    }

    .role {
        font-weight: 700;
        margin-bottom: 6px;
        color: @muted;
    }

    .empty {
        color: @muted;
    }

    .income {
        color: @income;
    }

    .expense {
        color: @expense;
    }
    """

    for key, value in sorted(
        colors.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        css = css.replace(f"@{key}", value)

    return css


def apply_theme(theme_name: str | None = None) -> None:
    if theme_name is None:
        theme_name = get_theme()

    app = QApplication.instance()

    if app is None:
        return

    from PySide6.QtGui import QFontDatabase

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)

    app.setFont(font)
    app.setStyleSheet(build_qss(theme_name))