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
from app.repositories import transaction_repository
from app.ui.widgets.transaction_dialog import TransactionDialog
from app.ui.helpers.form_style import style_table, style_toolbar


class TransactionsPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Операции")
        title_label.setObjectName("pageTitle")

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить операцию")
        add_button.clicked.connect(self.add_transaction)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_transaction)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_transaction)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Дата",
                "Тип",
                "Категория",
                "Объект",
                "Счет",
                "Сумма",
                "Товары",
                "Комментарий",
            ]
        )

        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self.edit_selected_transaction)

        self.empty_label = QLabel(
            "💳  Пока нет операций\n\nДобавь первую операцию, чтобы увидеть доходы, расходы и аналитику"
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_label)

        self.load_transactions()

    def refresh(self) -> None:
        self.load_transactions()

    def add_transaction(self) -> None:
        dialog = TransactionDialog(self)

        if dialog.exec():
            self.load_transactions()

    def edit_selected_transaction(self) -> None:
        transaction_id = self.get_selected_transaction_id()

        if transaction_id is None:
            QMessageBox.information(
                self,
                "Операция не выбрана",
                "Выбери операцию в таблице, чтобы изменить ее",
            )
            return

        dialog = TransactionDialog(self, transaction_id=transaction_id)

        if dialog.exec():
            self.load_transactions()

    def delete_selected_transaction(self) -> None:
        transaction_id = self.get_selected_transaction_id()

        if transaction_id is None:
            QMessageBox.information(
                self,
                "Операция не выбрана",
                "Выбери операцию в таблице, чтобы удалить ее",
            )
            return

        result = QMessageBox.question(
            self,
            "Удаление операции",
            "Удалить выбранную операцию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        session = SessionLocal()

        try:
            transaction_repository.delete_transaction(
                session=session,
                transaction_id=transaction_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_transactions()

    def get_selected_transaction_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def load_transactions(self) -> None:
        with SessionLocal() as session:
            rows = transaction_repository.get_transactions_for_table(session)

            transaction_ids = [row[0].id for row in rows]

            items_map = transaction_repository.get_transaction_items_map(
                session=session,
                transaction_ids=transaction_ids,
            )

        has_rows = len(rows) > 0

        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            transaction = row[0]
            category_name = row.category_name
            account_name = row.account_name
            directory_item_name = row.directory_item_name

            object_name = directory_item_name or transaction.payee or ""

            if transaction.type == "income":
                type_label = "Доход"
            elif transaction.type == "transfer":
                type_label = "Перевод"
            else:
                type_label = "Расход"

            if transaction.type == "transfer":
                account_label = f"{account_name} → {row.to_account_name or '?'}"
                category_label = "Перевод"
            else:
                account_label = account_name
                category_label = category_name

            amount = transaction.amount_minor / 100

            if transaction.type == "income":
                amount_label = f"+{amount:.2f} {transaction.currency}"
            elif transaction.type == "transfer":
                amount_label = f"{amount:.2f} {transaction.currency}"
            else:
                amount_label = f"-{amount:.2f} {transaction.currency}"

            date_label = transaction.occurred_at.strftime("%d.%m.%Y")

            item_names = items_map.get(transaction.id, [])
            items_label = ", ".join(item_names)

            values = [
                date_label,
                type_label,
                category_label,
                object_name,
                account_label,
                amount_label,
                items_label,
                transaction.note or "",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setData(Qt.UserRole, transaction.id)

                if column_index == 5:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                self.table.setItem(row_index, column_index, item)

        self.table.resizeColumnsToContents()

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)