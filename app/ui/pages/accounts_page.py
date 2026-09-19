from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from app.db import SessionLocal
from app.repositories import account_repository
from app.services import interest_service
from app.ui.widgets.account_dialog import AccountDialog
from app.ui.helpers.form_style import style_table, style_toolbar

TYPE_LABELS = {
    "cash": "Наличные",
    "card": "Карта",
    "deposit": "Вклад",
    "savings": "Накопления",
    "loan": "Кредит",
    "credit_card": "Кредитная карта",
}


class AccountsPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Счета")
        title_label.setObjectName("pageTitle")

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить счет")
        add_button.clicked.connect(self.add_account)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_account)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_account)

        accrue_button = QPushButton("Начислить проценты")
        accrue_button.setObjectName("secondaryButton")
        accrue_button.clicked.connect(self.accrue_now)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addWidget(accrue_button)
        toolbar_layout.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Название",
                "Тип",
                "Валюта",
                "Начальный баланс",
                "Текущий баланс",
                "Ставка",
                "Следующий платеж",
                "Активен",
                "По умолчанию",
            ]
        )

        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self.edit_selected_account)

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)

        self.load_accounts()

    def refresh(self) -> None:
        self.load_accounts()

    # =========================
    # Действия
    # =========================

    def add_account(self) -> None:
        dialog = AccountDialog(self)

        if dialog.exec():
            self.load_accounts()

    def edit_selected_account(self) -> None:
        account_id = self.get_selected_account_id()

        if account_id is None:
            QMessageBox.information(
                self,
                "Счет не выбран",
                "Выбери счет, чтобы изменить его",
            )
            return

        dialog = AccountDialog(self, account_id=account_id)

        if dialog.exec():
            self.load_accounts()

    def delete_selected_account(self) -> None:
        account_id = self.get_selected_account_id()

        if account_id is None:
            QMessageBox.information(
                self,
                "Счет не выбран",
                "Выбери счет, чтобы удалить его",
            )
            return

        session = SessionLocal()

        try:
            if account_repository.is_account_used(
                session=session,
                account_id=account_id,
            ):
                QMessageBox.warning(
                    self,
                    "Счет используется",
                    "По этому счету есть операции. Сначала удали или перенеси их",
                )
                return

            result = QMessageBox.question(
                self,
                "Удаление счета",
                "Удалить выбранный счет?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if result != QMessageBox.StandardButton.Yes:
                return

            account_repository.delete_account(
                session=session,
                account_id=account_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_accounts()

    def accrue_now(self) -> None:
        session = SessionLocal()

        try:
            created_count = interest_service.process_all(session)
            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        QMessageBox.information(
            self,
            "Начисление завершено",
            f"Создано операций процентов: {created_count}",
        )

        self.load_accounts()

    # =========================
    # Таблица
    # =========================

    def get_selected_account_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def load_accounts(self) -> None:
        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

            balances = {}
            next_dates = {}

            for account in accounts:
                balances[account.id] = interest_service.get_native_balance(
                    session, account.id
                )
                next_dates[account.id] = account.next_due_date

        self.table.setRowCount(len(accounts))

        for row_index, account in enumerate(accounts):
            name_item = QTableWidgetItem(account.name)
            name_item.setData(Qt.UserRole, account.id)

            type_item = QTableWidgetItem(
                TYPE_LABELS.get(account.type or "card", account.type or "card")
            )

            currency_item = QTableWidgetItem(account.currency)

            initial_item = QTableWidgetItem(
                f"{account.initial_balance_minor / 100:.2f}"
            )

            current_balance = balances.get(account.id, 0)
            balance_item = QTableWidgetItem(f"{current_balance / 100:.2f}")

            if account.annual_rate_bp:
                rate_item = QTableWidgetItem(f"{account.annual_rate_bp / 100:.2f}%")
            else:
                rate_item = QTableWidgetItem("-")

            next_date = next_dates.get(account.id)

            if next_date is not None:
                next_item = QTableWidgetItem(next_date.strftime("%d.%m.%Y"))
            else:
                next_item = QTableWidgetItem("-")

            active_item = QTableWidgetItem("Да" if account.is_active else "Нет")
            default_item = QTableWidgetItem("Да" if account.is_default else "Нет")

            self.table.setItem(row_index, 0, name_item)
            self.table.setItem(row_index, 1, type_item)
            self.table.setItem(row_index, 2, currency_item)
            self.table.setItem(row_index, 3, initial_item)
            self.table.setItem(row_index, 4, balance_item)
            self.table.setItem(row_index, 5, rate_item)
            self.table.setItem(row_index, 6, next_item)
            self.table.setItem(row_index, 7, active_item)
            self.table.setItem(row_index, 8, default_item)

        self.table.resizeColumnsToContents()

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)