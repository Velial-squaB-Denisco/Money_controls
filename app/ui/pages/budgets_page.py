from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.repositories import budget_repository
from app.services import analytics_service
from app.ui.widgets.budget_dialog import BudgetDialog
from app.ui.helpers.form_style import style_table, style_toolbar


class BudgetsPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Бюджеты")
        title_label.setObjectName("pageTitle")
        
        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить бюджет")
        add_button.clicked.connect(self.add_budget)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_budget)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_budget)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Категория",
                "Лимит",
                "Потрачено",
                "Осталось",
                "Прогресс",
                "Статус",
                "Комментарий",
            ]
        )

        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self.edit_selected_budget)

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        self.empty_label = QLabel(
            "🎯  Пока нет бюджетов\n\nСоздай бюджет, чтобы контролировать траты по категориям"
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addWidget(self.table)
        layout.addWidget(self.empty_label)

        self.load_budgets()

    def refresh(self) -> None:
        self.load_budgets()

    def add_budget(self) -> None:
        dialog = BudgetDialog(self)

        if dialog.exec():
            self.load_budgets()

    def edit_selected_budget(self) -> None:
        budget_id = self.get_selected_budget_id()

        if budget_id is None:
            QMessageBox.information(
                self,
                "Бюджет не выбран",
                "Выбери бюджет, чтобы изменить его",
            )
            return

        dialog = BudgetDialog(self, budget_id=budget_id)

        if dialog.exec():
            self.load_budgets()

    def delete_selected_budget(self) -> None:
        budget_id = self.get_selected_budget_id()

        if budget_id is None:
            QMessageBox.information(
                self,
                "Бюджет не выбран",
                "Выбери бюджет, чтобы удалить его",
            )
            return

        result = QMessageBox.question(
            self,
            "Удаление бюджета",
            "Удалить выбранный бюджет?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        session = SessionLocal()

        try:
            budget_repository.delete_budget(
                session=session,
                budget_id=budget_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_budgets()

    def get_selected_budget_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def format_money(self, amount_minor: int) -> str:
        amount = amount_minor / 100

        return f"{amount:,.2f}".replace(",", " ")

    def load_budgets(self) -> None:
        with SessionLocal() as session:
            rows = budget_repository.get_budgets_for_table(session)

            budget_category_ids = [row[0].category_id for row in rows]

            month_start, month_end = analytics_service.get_current_month_bounds()

            spent_map = analytics_service.get_budget_spent_map(
                session=session,
                start_date=month_start,
                end_date=month_end,
                budget_category_ids=budget_category_ids,
            )

        self.table.setRowCount(len(rows))
        has_rows = len(rows) > 0

        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

        for row_index, row in enumerate(rows):
            budget = row[0]
            category_name = row.category_name

            limit_minor = budget.amount_minor
            spent_minor = spent_map.get(budget.category_id, 0)
            remaining_minor = limit_minor - spent_minor

            if limit_minor > 0:
                percent = int(round(spent_minor * 100 / limit_minor))
            else:
                percent = 0

            if spent_minor > limit_minor:
                status_label = "Превышен"
            elif percent >= 80:
                status_label = "Почти лимит"
            else:
                status_label = "Ок"

            category_item = QTableWidgetItem(category_name)
            category_item.setData(Qt.UserRole, budget.id)

            limit_item = QTableWidgetItem(self.format_money(limit_minor))
            spent_item = QTableWidgetItem(self.format_money(spent_minor))
            remaining_item = QTableWidgetItem(self.format_money(remaining_minor))
            status_item = QTableWidgetItem(status_label)
            note_item = QTableWidgetItem(budget.note or "")

            self.table.setItem(row_index, 0, category_item)
            self.table.setItem(row_index, 1, limit_item)
            self.table.setItem(row_index, 2, spent_item)
            self.table.setItem(row_index, 3, remaining_item)

            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(min(percent, 100))
            progress_bar.setTextVisible(True)

            if spent_minor > limit_minor:
                progress_bar.setStyleSheet(
                    """
                    QProgressBar::chunk {
                        background-color: #d9534f;
                    }
                    """
                )
            elif percent >= 80:
                progress_bar.setStyleSheet(
                    """
                    QProgressBar::chunk {
                        background-color: #f0ad4e;
                    }
                    """
                )
            else:
                progress_bar.setStyleSheet(
                    """
                    QProgressBar::chunk {
                        background-color: #5cb85c;
                    }
                    """
                )

            self.table.setCellWidget(row_index, 4, progress_bar)
            self.table.setItem(row_index, 5, status_item)
            self.table.setItem(row_index, 6, note_item)

        self.table.resizeColumnsToContents()

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)