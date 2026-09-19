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
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.core import schedule
from app.db import SessionLocal
from app.models import Account, RecurringRule
from app.repositories import account_repository
from app.ui.helpers.form_style import polish_dialog


WEEKDAY_LABELS = {
    "MO": "понедельник",
    "TU": "вторник",
    "WE": "среда",
    "TH": "четверг",
    "FR": "пятница",
    "SA": "суббота",
    "SU": "воскресенье",
}


class AccountDialog(QDialog):
    def __init__(self, parent=None, account_id: int | None = None):
        super().__init__(parent)

        self.account_id = account_id

        if self.account_id is None:
            self.setWindowTitle("Добавить счет")
        else:
            self.setWindowTitle("Изменить счет")

        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            "Например: Карта, Наличные, Вклад, Кредитка"
        )

        self.type_combo = QComboBox()
        self.type_combo.addItem("Наличные", "cash")
        self.type_combo.addItem("Карта", "card")
        self.type_combo.addItem("Вклад", "deposit")
        self.type_combo.addItem("Накопления", "savings")
        self.type_combo.addItem("Кредит", "loan")
        self.type_combo.addItem("Кредитная карта", "credit_card")

        self.currency_combo = QComboBox()
        self.currency_combo.addItem("RUB", "RUB")
        self.currency_combo.addItem("USD", "USD")

        self.initial_balance_spin = QDoubleSpinBox()
        self.initial_balance_spin.setRange(-999_999_999, 999_999_999)
        self.initial_balance_spin.setDecimals(2)
        self.initial_balance_spin.setSingleStep(1000)

        self.is_default_checkbox = QCheckBox("Счет по умолчанию")

        form_layout.addRow("Название", self.name_edit)
        form_layout.addRow("Тип счета", self.type_combo)
        form_layout.addRow("Валюта", self.currency_combo)
        form_layout.addRow("Начальный баланс", self.initial_balance_spin)
        form_layout.addRow("", self.is_default_checkbox)

        # ---------- Условия вклада / кредита ----------
        self.terms_group = QGroupBox("Условия вклада / кредита")
        terms_form = QFormLayout(self.terms_group)

        self.annual_rate_spin = QDoubleSpinBox()
        self.annual_rate_spin.setRange(0, 100)
        self.annual_rate_spin.setDecimals(2)
        self.annual_rate_spin.setSuffix(" %")

        self.interest_day_spin = QDoubleSpinBox()
        self.interest_day_spin.setRange(1, 31)
        self.interest_day_spin.setDecimals(0)
        self.interest_day_spin.setValue(1)

        self.auto_start_date_edit = QDateEdit()
        self.auto_start_date_edit.setCalendarPopup(True)
        self.auto_start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.auto_start_date_edit.setDate(QDate.currentDate())

        self.next_due_date_edit = QDateEdit()
        self.next_due_date_edit.setCalendarPopup(True)
        self.next_due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.next_due_date_edit.setDate(QDate.currentDate())

        terms_form.addRow("Годовая ставка", self.annual_rate_spin)
        terms_form.addRow("День начисления процентов", self.interest_day_spin)
        terms_form.addRow("Начало автоначислений", self.auto_start_date_edit)
        terms_form.addRow("Следующая дата начисления", self.next_due_date_edit)

        # ---------- Информация об автоплатежах ----------
        self.autopay_group = QGroupBox("Автоплатежи (настраиваются в разделе Автоплатежи)")
        autopay_form = QFormLayout(self.autopay_group)

        self.autopay_info_label = QLabel("Не настроено")
        self.autopay_info_label.setWordWrap(True)

        autopay_form.addRow(self.autopay_info_label)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)
        layout.addWidget(self.terms_group)
        layout.addWidget(self.autopay_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.type_combo.currentIndexChanged.connect(self.on_type_changed)

        self.on_type_changed()

        if self.account_id is not None:
            self.load_account()
            self.load_autopay_info()

    # =========================
    # Видимость
    # =========================

    def on_type_changed(self) -> None:
        account_type = self.type_combo.currentData()

        show = account_type in ["deposit", "savings", "loan", "credit_card"]

        self.terms_group.setVisible(show)
        self.autopay_group.setVisible(show)

    # =========================
    # Загрузка
    # =========================

    def load_account(self) -> None:
        with SessionLocal() as session:
            account = session.get(Account, self.account_id)

        if account is None:
            self.account_id = None
            return

        self.name_edit.setText(account.name)

        type_index = self.type_combo.findData(account.type or "card")

        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        currency_index = self.currency_combo.findData(account.currency)

        if currency_index >= 0:
            self.currency_combo.setCurrentIndex(currency_index)

        self.initial_balance_spin.setValue(account.initial_balance_minor / 100)
        self.is_default_checkbox.setChecked(account.is_default)

        self.annual_rate_spin.setValue((account.annual_rate_bp or 0) / 100)
        self.interest_day_spin.setValue(account.interest_day or 1)

        if account.auto_start_date is not None:
            self.auto_start_date_edit.setDate(
                QDate(
                    account.auto_start_date.year,
                    account.auto_start_date.month,
                    account.auto_start_date.day,
                )
            )

        if account.next_due_date is not None:
            self.next_due_date_edit.setDate(
                QDate(
                    account.next_due_date.year,
                    account.next_due_date.month,
                    account.next_due_date.day,
                )
            )

    def load_autopay_info(self) -> None:
        with SessionLocal() as session:
            rules = (
                session.query(RecurringRule)
                .filter(RecurringRule.type == "transfer")
                .filter(RecurringRule.is_active == True)
                .filter(RecurringRule.transfer_to_account_id == self.account_id)
                .all()
            )

            accounts = account_repository.get_all_accounts(session)

        account_names = {account.id: account.name for account in accounts}

        if not rules:
            self.autopay_info_label.setText("Не настроено")
            return

        lines = []

        for rule in rules:
            from_name = account_names.get(rule.account_id, "?")

            parsed = schedule.parse_rrule(rule.rrule)
            frequency = parsed.get("frequency")

            if frequency == "monthly":
                day = parsed.get("monthly_day")
                freq_text = f"ежемесячно, {day} число" if day else "ежемесячно"
            elif frequency == "weekly":
                code = parsed.get("weekly_day")
                freq_text = f"еженедельно, {WEEKDAY_LABELS.get(code, code)}"
            elif frequency == "yearly":
                month_num = parsed.get("yearly_month")
                day = parsed.get("yearly_day")
                freq_text = f"ежегодно, {day} число, месяц {month_num}"
            else:
                freq_text = "по расписанию"

            amount_text = f"{(rule.amount_minor or 0) / 100:,.2f}".replace(",", " ")

            lines.append(
                f"{rule.name}: {amount_text} ₽ ({from_name} → сюда, {freq_text})"
            )

        self.autopay_info_label.setText("\n".join(lines))

    # =========================
    # Сохранение
    # =========================

    def accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Ошибка", "Введи название счета")
            return

        account_type = self.type_combo.currentData()
        currency = self.currency_combo.currentData()
        initial_balance_minor = int(round(self.initial_balance_spin.value() * 100))
        is_default = self.is_default_checkbox.isChecked()

        if account_type in ["deposit", "savings", "loan", "credit_card"]:
            annual_rate_bp = int(round(self.annual_rate_spin.value() * 100))
            interest_day = int(self.interest_day_spin.value())
            auto_start_date = self.auto_start_date_edit.date().toPython()
            next_due_date = self.next_due_date_edit.date().toPython()
        else:
            annual_rate_bp = None
            interest_day = None
            auto_start_date = None
            next_due_date = None

        session = SessionLocal()

        try:
            if self.account_id is None:
                account = account_repository.create_account(
                    session=session,
                    name=name,
                    currency=currency,
                    initial_balance_minor=initial_balance_minor,
                    is_default=is_default,
                )

                account_repository.update_account(
                    session=session,
                    account=account,
                    type=account_type,
                    annual_rate_bp=annual_rate_bp,
                    interest_day=interest_day,
                    auto_start_date=auto_start_date,
                    next_due_date=next_due_date,
                )
            else:
                account = session.get(Account, self.account_id)

                if account is None:
                    raise ValueError("Счет не найден")

                account_repository.update_account(
                    session=session,
                    account=account,
                    name=name,
                    type=account_type,
                    currency=currency,
                    initial_balance_minor=initial_balance_minor,
                    is_default=is_default,
                    annual_rate_bp=annual_rate_bp,
                    interest_day=interest_day,
                    auto_start_date=auto_start_date,
                    next_due_date=next_due_date,
                )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        super().accept()