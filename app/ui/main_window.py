from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.ui.pages.assistant_page import AssistantPage
from app.ui.pages.budgets_page import BudgetsPage
from app.ui.pages.categories_page import CategoriesPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.directory_page import DirectoryPage
from app.ui.pages.income_profiles_page import IncomeProfilesPage
from app.ui.pages.recurring_page import RecurringPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.transactions_page import TransactionsPage
from app.ui.pages.accounts_page import AccountsPage
from app.ui.pages.finance_page import FinancePage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Финансы")
        self.resize(1440, 900)

        central_widget = QWidget()
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.menu_list = QListWidget()
        self.menu_list.setObjectName("sidebarMenu")
        self.menu_list.setFixedWidth(240)

        self.pages = QStackedWidget()

        pages = [
            ("📊  Дашборд", DashboardPage()),
            ("💳  Операции", TransactionsPage()),
            ("💰  Счета", AccountsPage()),
            ("💼  Профили доходов", IncomeProfilesPage()),
            ("🎯  Бюджеты", BudgetsPage()),
            ("📈  Вклады и кредиты", FinancePage()),
            ("🤖  Ассистент", AssistantPage()),
            ("🏷️  Категории", CategoriesPage()),
            ("🧾  Объекты", DirectoryPage()),
            ("🔁  Автоплатежи", RecurringPage()),
            ("⚙️  Настройки", SettingsPage()),
        ]

        for title, page in pages:
            menu_item = QListWidgetItem(title)
            self.menu_list.addItem(menu_item)
            self.pages.addWidget(page)

        self._page_animation = None

        self.menu_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.pages.currentChanged.connect(self.refresh_current_page)
        self.pages.currentChanged.connect(self.animate_page_change)

        self.menu_list.setCurrentRow(0)

        root_layout.addWidget(self.menu_list)
        root_layout.addWidget(self.pages, 1)

        self.setCentralWidget(central_widget)

    def refresh_current_page(self, index: int) -> None:
        page = self.pages.widget(index)

        if page is None:
            return

        if hasattr(page, "refresh"):
            page.refresh()
            
    def animate_page_change(self, index: int) -> None:
        widget = self.pages.widget(index)

        if widget is None:
            return

        try:
            if widget.findChild(QWebEngineView) is not None:
                return
        except Exception:
            return

        try:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

            animation = QPropertyAnimation(effect, b"opacity")
            animation.setDuration(180)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)

            animation.finished.connect(
                lambda: widget.setGraphicsEffect(None)
            )

            self._page_animation = animation
            animation.start()
        except Exception:
            widget.setGraphicsEffect(None)