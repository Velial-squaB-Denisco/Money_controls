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
from app.repositories import income_profile_repository
from app.ui.widgets.income_profile_dialog import IncomeProfileDialog
from app.ui.widgets.transaction_dialog import TransactionDialog
from app.ui.helpers.form_style import style_table, style_toolbar


class IncomeProfilesPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Профили доходов")
        title_label.setObjectName("pageTitle")

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить профиль")
        add_button.clicked.connect(self.add_profile)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_profile)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_profile)

        create_income_button = QPushButton("Создать доход из профиля")
        create_income_button.clicked.connect(self.create_income_from_selected_profile)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addWidget(create_income_button)
        toolbar_layout.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Название",
                "Тип",
                "Счет",
                "Категория",
                "Налог",
                "Оклад / база",
                "Аванс",
                "Годовая премия",
                "Активен",
            ]
        )

        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self.edit_selected_profile)

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)

        self.load_profiles()
        
    def create_income_from_selected_profile(self) -> None:
        profile_id = self.get_selected_profile_id()

        if profile_id is None:
            QMessageBox.information(
                self,
                "Профиль не выбран",
                "Выбери профиль дохода, чтобы создать доход",
            )
            return

        dialog = TransactionDialog(self, income_profile_id=profile_id)

        dialog.exec()

    def add_profile(self) -> None:
        dialog = IncomeProfileDialog(self)

        if dialog.exec():
            self.load_profiles()

    def edit_selected_profile(self) -> None:
        profile_id = self.get_selected_profile_id()

        if profile_id is None:
            QMessageBox.information(
                self,
                "Профиль не выбран",
                "Выбери профиль дохода, чтобы изменить его",
            )
            return

        dialog = IncomeProfileDialog(self, profile_id=profile_id)

        if dialog.exec():
            self.load_profiles()

    def delete_selected_profile(self) -> None:
        profile_id = self.get_selected_profile_id()

        if profile_id is None:
            QMessageBox.information(
                self,
                "Профиль не выбран",
                "Выбери профиль дохода, чтобы удалить его",
            )
            return

        session = SessionLocal()

        try:
            if income_profile_repository.is_profile_used(
                session=session,
                profile_id=profile_id,
            ):
                QMessageBox.warning(
                    self,
                    "Профиль используется",
                    "Этот профиль дохода уже используется операциями.\n"
                    "Сначала измени эти операции или удали их",
                )
                return

            result = QMessageBox.question(
                self,
                "Удаление профиля",
                "Удалить выбранный профиль дохода?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if result != QMessageBox.StandardButton.Yes:
                return

            income_profile_repository.delete_income_profile(
                session=session,
                profile_id=profile_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_profiles()

    def get_selected_profile_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def format_money(self, amount_minor: int | None) -> str:
        if amount_minor is None:
            return "-"

        return f"{amount_minor / 100:.2f}"

    def format_percent(self, rate_bp: int | None) -> str:
        if rate_bp is None:
            return "-"

        return f"{rate_bp / 100:.2f}%"

    def load_profiles(self) -> None:
        with SessionLocal() as session:
            rows = income_profile_repository.get_income_profiles_for_table(session)

        self.table.setRowCount(len(rows))

        kind_labels = {
            "salary": "Зарплата",
            "freelance": "Фриланс",
            "business": "Бизнес",
            "investment": "Инвестиции",
            "other": "Другое",
        }

        for row_index, row in enumerate(rows):
            profile = row[0]
            account_name = row.account_name
            category_name = row.category_name

            if profile.tax_mode == "none":
                tax_label = "Без налога"
            elif profile.tax_mode == "fixed":
                tax_label = self.format_percent(profile.fixed_tax_rate_bp)
            else:
                tax_label = "-"

            if profile.advance_percent_bp is not None:
                advance_label = self.format_percent(profile.advance_percent_bp)
            elif profile.advance_fixed_minor is not None:
                advance_label = self.format_money(profile.advance_fixed_minor)
            else:
                advance_label = "-"

            values = [
                profile.name,
                kind_labels.get(profile.kind, profile.kind),
                account_name,
                category_name,
                tax_label,
                self.format_money(profile.base_gross_minor),
                advance_label,
                self.format_money(profile.annual_bonus_gross_minor),
                "Да" if profile.is_active else "Нет",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setData(Qt.UserRole, profile.id)

                self.table.setItem(row_index, column_index, item)

        self.table.resizeColumnsToContents()

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        
    def refresh(self) -> None:
        self.load_profiles()