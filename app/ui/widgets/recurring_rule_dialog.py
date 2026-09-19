from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.helpers.form_style import polish_dialog
from app.core import schedule
from app.db import SessionLocal
from app.models import Account
from app.repositories import (
    account_repository,
    category_repository,
    recurring_repository,
)


class RecurringRuleDialog(QDialog):
    def __init__(self, parent=None, rule_id: int | None = None):
        super().__init__(parent)

        self.rule_id = rule_id
        self._initial_category_id: int | None = None

        if self.rule_id is None:
            self.setWindowTitle("Добавить автооперацию")
        else:
            self.setWindowTitle("Изменить автооперацию")

        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Интернет, Аванс, Пополнение вклада")

        self.type_combo = QComboBox()
        self.type_combo.addItem("Расход", "expense")
        self.type_combo.addItem("Доход", "income")
        self.type_combo.addItem("Перевод", "transfer")

        self.account_combo = QComboBox()
        self.transfer_to_combo = QComboBox()
        self.category_combo = QComboBox()

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999_999_999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(100)

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem("Ежемесячно", "monthly")
        self.frequency_combo.addItem("Еженедельно", "weekly")
        self.frequency_combo.addItem("Ежегодно", "yearly")

        self.period_stack = QStackedWidget()

        monthly_widget = QWidget()
        monthly_form = QFormLayout(monthly_widget)
        self.monthly_day_spin = QDoubleSpinBox()
        self.monthly_day_spin.setRange(1, 31)
        self.monthly_day_spin.setDecimals(0)
        self.monthly_day_spin.setValue(1)
        monthly_form.addRow("День месяца", self.monthly_day_spin)

        weekly_widget = QWidget()
        weekly_form = QFormLayout(weekly_widget)
        self.weekly_day_combo = QComboBox()

        for code, label in schedule.WEEKDAY_LABELS.items():
            self.weekly_day_combo.addItem(label, code)

        weekly_form.addRow("День недели", self.weekly_day_combo)

        yearly_widget = QWidget()
        yearly_form = QFormLayout(yearly_widget)

        self.yearly_month_combo = QComboBox()

        for month_number, month_label in schedule.MONTH_LABELS.items():
            self.yearly_month_combo.addItem(month_label, month_number)

        self.yearly_day_spin = QDoubleSpinBox()
        self.yearly_day_spin.setRange(1, 31)
        self.yearly_day_spin.setDecimals(0)
        self.yearly_day_spin.setValue(1)

        yearly_form.addRow("Месяц", self.yearly_month_combo)
        yearly_form.addRow("День", self.yearly_day_spin)

        self.period_stack.addWidget(monthly_widget)
        self.period_stack.addWidget(weekly_widget)
        self.period_stack.addWidget(yearly_widget)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")

        self.active_checkbox = QCheckBox("Активно")
        self.active_checkbox.setChecked(True)

        self.create_draft_checkbox = QCheckBox("Создавать как черновик")
        self.create_draft_checkbox.setChecked(False)
        self.create_draft_checkbox.setToolTip(
            "Полезно для ЖКХ и других платежей с плавающей суммой"
        )

        form_layout.addRow("Название", self.name_edit)
        form_layout.addRow("Тип операции", self.type_combo)
        form_layout.addRow("Счет", self.account_combo)
        form_layout.addRow("Счет получения", self.transfer_to_combo)
        form_layout.addRow("Категория", self.category_combo)
        form_layout.addRow("Сумма", self.amount_spin)
        form_layout.addRow("Повторение", self.frequency_combo)
        form_layout.addRow("Настройки повторения", self.period_stack)
        form_layout.addRow("Дата начала", self.start_date_edit)
        form_layout.addRow("", self.active_checkbox)
        form_layout.addRow("", self.create_draft_checkbox)

        self._category_label = form_layout.labelForField(self.category_combo)
        self._transfer_to_label = form_layout.labelForField(self.transfer_to_combo)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.load_accounts()

        if self.rule_id is not None:
            self.load_rule()

        self.load_categories()

        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.frequency_combo.currentIndexChanged.connect(self.update_period_stack)

        self.update_period_stack()
        self.update_type_visibility()

    # =========================
    # Видимость
    # =========================

    def on_type_changed(self) -> None:
        self._initial_category_id = None
        self.load_categories()
        self.update_type_visibility()

    def update_type_visibility(self) -> None:
        is_transfer = self.type_combo.currentData() == "transfer"

        self.category_combo.setVisible(not is_transfer)

        if self._category_label is not None:
            self._category_label.setVisible(not is_transfer)

        self.transfer_to_combo.setVisible(is_transfer)

        if self._transfer_to_label is not None:
            self._transfer_to_label.setVisible(is_transfer)

    def update_period_stack(self) -> None:
        self.period_stack.setCurrentIndex(self.frequency_combo.currentIndex())

    # =========================
    # Загрузка справочников
    # =========================

    def load_accounts(self) -> None:
        self.account_combo.clear()
        self.transfer_to_combo.clear()

        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

        for account in accounts:
            label = f"{account.name} ({account.currency})"
            self.account_combo.addItem(label, account.id)
            self.transfer_to_combo.addItem(label, account.id)

    def load_categories(self) -> None:
        rule_type = self.type_combo.currentData()

        self.category_combo.clear()

        with SessionLocal() as session:
            categories = category_repository.get_categories_by_type(
                session=session,
                type=rule_type,
            )

        categories_by_id = {category.id: category for category in categories}

        for category in categories:
            label = category.name

            if category.parent_id is not None:
                parent = categories_by_id.get(category.parent_id)

                if parent:
                    label = f"{parent.name} / {category.name}"

            self.category_combo.addItem(label, category.id)

        if self._initial_category_id is not None:
            for index in range(self.category_combo.count()):
                if self.category_combo.itemData(index) == self._initial_category_id:
                    self.category_combo.setCurrentIndex(index)
                    break

            self._initial_category_id = None

    # =========================
    # Редактирование
    # =========================

    def load_rule(self) -> None:
        with SessionLocal() as session:
            rule = recurring_repository.get_recurring_rule_by_id(
                session=session,
                rule_id=self.rule_id,
            )

        if rule is None:
            self.rule_id = None
            return

        self.name_edit.setText(rule.name)

        type_index = self.type_combo.findData(rule.type)

        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        for index in range(self.account_combo.count()):
            if self.account_combo.itemData(index) == rule.account_id:
                self.account_combo.setCurrentIndex(index)
                break

        if rule.transfer_to_account_id is not None:
            for index in range(self.transfer_to_combo.count()):
                if (
                    self.transfer_to_combo.itemData(index)
                    == rule.transfer_to_account_id
                ):
                    self.transfer_to_combo.setCurrentIndex(index)
                    break

        self.amount_spin.setValue((rule.amount_minor or 0) / 100)

        parsed = schedule.parse_rrule(rule.rrule)

        frequency_index = self.frequency_combo.findData(
            parsed["frequency"] or "monthly"
        )

        if frequency_index >= 0:
            self.frequency_combo.setCurrentIndex(frequency_index)

        self.monthly_day_spin.setValue(parsed["monthly_day"] or 1)

        weekly_day_index = self.weekly_day_combo.findData(parsed["weekly_day"] or "MO")

        if weekly_day_index >= 0:
            self.weekly_day_combo.setCurrentIndex(weekly_day_index)

        yearly_month_index = self.yearly_month_combo.findData(
            parsed["yearly_month"] or 1
        )

        if yearly_month_index >= 0:
            self.yearly_month_combo.setCurrentIndex(yearly_month_index)

        self.yearly_day_spin.setValue(parsed["yearly_day"] or 1)

        self.start_date_edit.setDate(
            QDate(
                rule.start_date.year,
                rule.start_date.month,
                rule.start_date.day,
            )
        )

        self.active_checkbox.setChecked(rule.is_active)
        self.create_draft_checkbox.setChecked(rule.create_as_draft)

        self._initial_category_id = rule.category_id

    # =========================
    # Сохранение
    # =========================

    def accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Ошибка", "Введи название автооперации")
            return

        rule_type = self.type_combo.currentData()

        account_id = self.account_combo.currentData()

        if account_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите счет")
            return

        transfer_to_account_id = None
        category_id = None

        if rule_type == "transfer":
            transfer_to_account_id = self.transfer_to_combo.currentData()

            if transfer_to_account_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите счет получения")
                return

            if transfer_to_account_id == account_id:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Счет и счет получения совпадают",
                )
                return
        else:
            category_id = self.category_combo.currentData()

            if category_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите категорию")
                return

        amount = self.amount_spin.value()

        if amount <= 0:
            QMessageBox.warning(self, "Ошибка", "Сумма должна быть больше нуля")
            return

        frequency = self.frequency_combo.currentData()

        rrule_text = schedule.build_rrule(
            frequency=frequency,
            monthly_day=int(self.monthly_day_spin.value()),
            weekly_day=self.weekly_day_combo.currentData(),
            yearly_month=self.yearly_month_combo.currentData(),
            yearly_day=int(self.yearly_day_spin.value()),
        )

        start_date = self.start_date_edit.date().toPython()
        reference_date = max(start_date, date.today())

        next_due_date = schedule.get_next_due_date(
            rrule_text=rrule_text,
            start_date=start_date,
            reference_date=reference_date,
        )

        amount_minor = int(round(amount * 100))
        is_active = self.active_checkbox.isChecked()
        create_as_draft = self.create_draft_checkbox.isChecked()

        session = SessionLocal()

        try:
            account = session.get(Account, account_id)

            if account is None:
                raise ValueError("Счет не найден")
            
            if rule_type == "transfer":
                category_id = category_repository.get_or_create_transfer_category(
                    session
                ).id

            fields = {
                "name": name,
                "type": rule_type,
                "account_id": account_id,
                "transfer_to_account_id": transfer_to_account_id,
                "category_id": category_id,
                "currency": account.currency,
                "amount_minor": amount_minor,
                "rrule": rrule_text,
                "start_date": start_date,
                "end_date": None,
                "next_due_date": next_due_date,
                "is_active": is_active,
                "is_fixed": True,
                "create_as_draft": create_as_draft,
                "note": None,
            }

            if self.rule_id is None:
                recurring_repository.create_recurring_rule(
                    session=session,
                    **fields,
                )
            else:
                rule = recurring_repository.get_recurring_rule_by_id(
                    session=session,
                    rule_id=self.rule_id,
                )

                if rule is None:
                    raise ValueError("Автооперация не найдена")

                recurring_repository.update_recurring_rule(
                    session=session,
                    rule=rule,
                    **fields,
                )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        super().accept()