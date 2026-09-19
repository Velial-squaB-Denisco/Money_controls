from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import schedule
from app.db import SessionLocal
from app.repositories import account_repository, recurring_repository
from app.services import recurring_service
from app.ui.helpers.form_style import style_table, style_toolbar
from app.ui.widgets.recurring_rule_dialog import RecurringRuleDialog


class RecurringPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Автоплатежи и автодоходы")
        title_label.setObjectName("pageTitle")

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить автооперацию")
        add_button.clicked.connect(self.add_rule)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_rule)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_rule)

        generate_button = QPushButton("Сгенерировать сейчас")
        generate_button.setObjectName("secondaryButton")
        generate_button.clicked.connect(self.generate_now)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addWidget(generate_button)
        toolbar_layout.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Название",
                "Тип",
                "Счет",
                "Категория",
                "Сумма",
                "Повторение",
                "Следующая дата",
                "Активно",
            ]
        )

        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self.edit_selected_rule)

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)

        self.load_rules()

    def refresh(self) -> None:
        self.load_rules()

    def add_rule(self) -> None:
        dialog = RecurringRuleDialog(self)

        if dialog.exec():
            self.load_rules()

    def edit_selected_rule(self) -> None:
        rule_id = self.get_selected_rule_id()

        if rule_id is None:
            QMessageBox.information(
                self,
                "Автооперация не выбрана",
                "Выбери автооперацию, чтобы изменить ее",
            )
            return

        dialog = RecurringRuleDialog(self, rule_id=rule_id)

        if dialog.exec():
            self.load_rules()

    def delete_selected_rule(self) -> None:
        rule_id = self.get_selected_rule_id()

        if rule_id is None:
            QMessageBox.information(
                self,
                "Автооперация не выбрана",
                "Выбери автооперацию, чтобы удалить ее",
            )
            return

        result = QMessageBox.question(
            self,
            "Удаление автооперации",
            "Удалить выбранную автооперацию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        session = SessionLocal()

        try:
            recurring_repository.delete_recurring_rule(
                session=session,
                rule_id=rule_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_rules()

    def generate_now(self) -> None:
        session = SessionLocal()

        try:
            created_count = recurring_service.generate_due_transactions(session)

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        QMessageBox.information(
            self,
            "Генерация автоопераций",
            f"Создано операций: {created_count}",
        )

        self.load_rules()

    def get_selected_rule_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def load_rules(self) -> None:
        with SessionLocal() as session:
            rows = recurring_repository.get_recurring_rules_for_table(session)
            accounts = account_repository.get_all_accounts(session)

        account_names = {account.id: account.name for account in accounts}

        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            rule = row[0]
            account_name = row.account_name
            category_name = row.category_name

            if rule.type == "income":
                type_label = "Доход"
            elif rule.type == "transfer":
                type_label = "Перевод"
            else:
                type_label = "Расход"

            if rule.type == "transfer":
                to_name = account_names.get(rule.transfer_to_account_id, "?")
                account_label = f"{account_name} → {to_name}"
                category_label = "Перевод"
            else:
                account_label = account_name
                category_label = category_name

            if rule.amount_minor is None:
                amount_label = "-"
            else:
                amount_label = f"{rule.amount_minor / 100:.2f} {rule.currency}"

            frequency_label = schedule.format_rrule(rule.rrule)

            if rule.next_due_date is None:
                next_due_label = "-"
            else:
                next_due_label = rule.next_due_date.strftime("%d.%m.%Y")

            values = [
                rule.name,
                type_label,
                account_label,
                category_label,
                amount_label,
                frequency_label,
                next_due_label,
                "Да" if rule.is_active else "Нет",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setData(Qt.UserRole, rule.id)

                self.table.setItem(row_index, column_index, item)

        self.table.resizeColumnsToContents()

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)