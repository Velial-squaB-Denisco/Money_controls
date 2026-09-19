from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.ui.helpers.form_style import polish_dialog
from app.db import SessionLocal
from app.models import Account
from app.repositories import (
    account_repository,
    category_repository,
    income_profile_repository,
)


class IncomeProfileDialog(QDialog):
    def __init__(self, parent=None, profile_id: int | None = None):
        super().__init__(parent)

        self.profile_id = profile_id

        if self.profile_id is None:
            self.setWindowTitle("Добавить профиль дохода")
        else:
            self.setWindowTitle("Изменить профиль дохода")

        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Основная работа, Фриланс клиент 1")

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Зарплата", "salary")
        self.kind_combo.addItem("Фриланс", "freelance")
        self.kind_combo.addItem("Бизнес", "business")
        self.kind_combo.addItem("Инвестиции", "investment")
        self.kind_combo.addItem("Другое", "other")

        self.account_combo = QComboBox()
        self.category_combo = QComboBox()

        self.tax_mode_combo = QComboBox()
        self.tax_mode_combo.addItem("Фиксированная ставка", "fixed")
        self.tax_mode_combo.addItem("Без налога", "none")

        self.tax_rate_spin = QDoubleSpinBox()
        self.tax_rate_spin.setRange(0, 100)
        self.tax_rate_spin.setDecimals(2)
        self.tax_rate_spin.setSingleStep(0.5)
        self.tax_rate_spin.setSuffix(" %")

        self.base_gross_spin = QDoubleSpinBox()
        self.base_gross_spin.setRange(0, 999_999_999)
        self.base_gross_spin.setDecimals(2)
        self.base_gross_spin.setSingleStep(1000)
        self.base_gross_spin.setToolTip("Базовый доход до налога, например оклад")

        self.allowances_spin = QDoubleSpinBox()
        self.allowances_spin.setRange(0, 999_999_999)
        self.allowances_spin.setDecimals(2)
        self.allowances_spin.setSingleStep(1000)
        self.allowances_spin.setToolTip("Надбавки и доплаты до налога")

        self.advance_percent_spin = QDoubleSpinBox()
        self.advance_percent_spin.setRange(0, 100)
        self.advance_percent_spin.setDecimals(2)
        self.advance_percent_spin.setSingleStep(1)
        self.advance_percent_spin.setSuffix(" %")
        self.advance_percent_spin.setToolTip("Размер аванса в процентах от месячного дохода")

        self.advance_fixed_spin = QDoubleSpinBox()
        self.advance_fixed_spin.setRange(0, 999_999_999)
        self.advance_fixed_spin.setDecimals(2)
        self.advance_fixed_spin.setSingleStep(1000)
        self.advance_fixed_spin.setToolTip("Фиксированный аванс, если не хочешь использовать проценты")

        self.annual_bonus_spin = QDoubleSpinBox()
        self.annual_bonus_spin.setRange(0, 999_999_999)
        self.annual_bonus_spin.setDecimals(2)
        self.annual_bonus_spin.setSingleStep(1000)
        self.annual_bonus_spin.setToolTip("Годовая премия до налога")

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Комментарий к профилю дохода")

        self.is_active_checkbox = QCheckBox("Активен")
        self.is_active_checkbox.setChecked(True)

        form_layout.addRow("Название", self.name_edit)
        form_layout.addRow("Тип дохода", self.kind_combo)
        form_layout.addRow("Счет", self.account_combo)
        form_layout.addRow("Категория дохода", self.category_combo)
        form_layout.addRow("Налог", self.tax_mode_combo)
        form_layout.addRow("Ставка налога", self.tax_rate_spin)
        form_layout.addRow("Оклад / база до налога", self.base_gross_spin)
        form_layout.addRow("Надбавки", self.allowances_spin)
        form_layout.addRow("Аванс, %", self.advance_percent_spin)
        form_layout.addRow("Аванс, фикс. сумма", self.advance_fixed_spin)
        form_layout.addRow("Годовая премия", self.annual_bonus_spin)
        form_layout.addRow("Комментарий", self.note_edit)
        form_layout.addRow("", self.is_active_checkbox)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.tax_mode_combo.currentIndexChanged.connect(self.update_tax_mode_state)

        self.load_accounts()
        self.load_categories()

        if self.profile_id is not None:
            self.load_profile()

        self.update_tax_mode_state()

    def update_tax_mode_state(self) -> None:
        tax_mode = self.tax_mode_combo.currentData()

        self.tax_rate_spin.setEnabled(tax_mode == "fixed")

    def load_accounts(self) -> None:
        self.account_combo.clear()

        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

        for account in accounts:
            self.account_combo.addItem(
                f"{account.name} ({account.currency})",
                account.id,
            )

    def load_categories(self) -> None:
        self.category_combo.clear()

        with SessionLocal() as session:
            categories = category_repository.get_categories_by_type(
                session=session,
                type="income",
            )

        categories_by_id = {category.id: category for category in categories}

        for category in categories:
            label = category.name

            if category.parent_id is not None:
                parent = categories_by_id.get(category.parent_id)

                if parent:
                    label = f"{parent.name} / {category.name}"

            self.category_combo.addItem(label, category.id)

    def load_profile(self) -> None:
        with SessionLocal() as session:
            profile = income_profile_repository.get_income_profile_by_id(
                session=session,
                profile_id=self.profile_id,
            )

        if profile is None:
            self.profile_id = None
            return

        self.name_edit.setText(profile.name)

        kind_index = self.kind_combo.findData(profile.kind)

        if kind_index >= 0:
            self.kind_combo.setCurrentIndex(kind_index)

        for index in range(self.account_combo.count()):
            if self.account_combo.itemData(index) == profile.account_id:
                self.account_combo.setCurrentIndex(index)
                break

        for index in range(self.category_combo.count()):
            if self.category_combo.itemData(index) == profile.income_category_id:
                self.category_combo.setCurrentIndex(index)
                break

        tax_mode_index = self.tax_mode_combo.findData(profile.tax_mode)

        if tax_mode_index >= 0:
            self.tax_mode_combo.setCurrentIndex(tax_mode_index)

        self.tax_rate_spin.setValue((profile.fixed_tax_rate_bp or 0) / 100)
        self.base_gross_spin.setValue((profile.base_gross_minor or 0) / 100)
        self.allowances_spin.setValue((profile.allowances_minor or 0) / 100)
        self.advance_percent_spin.setValue((profile.advance_percent_bp or 0) / 100)
        self.advance_fixed_spin.setValue((profile.advance_fixed_minor or 0) / 100)
        self.annual_bonus_spin.setValue((profile.annual_bonus_gross_minor or 0) / 100)
        self.note_edit.setText(profile.note or "")
        self.is_active_checkbox.setChecked(profile.is_active)

    def amount_to_minor(self, value: float) -> int | None:
        if value <= 0:
            return None

        return int(round(value * 100))

    def percent_to_bp(self, value: float) -> int | None:
        if value <= 0:
            return None

        return int(round(value * 100))

    def accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Ошибка", "Введи название профиля дохода")
            return

        account_id = self.account_combo.currentData()
        category_id = self.category_combo.currentData()

        if account_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите счет")
            return

        if category_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите категорию дохода")
            return

        kind = self.kind_combo.currentData()
        tax_mode = self.tax_mode_combo.currentData()

        fixed_tax_rate_bp = None

        if tax_mode == "fixed":
            fixed_tax_rate_bp = int(round(self.tax_rate_spin.value() * 100))

        base_gross_minor = self.amount_to_minor(self.base_gross_spin.value())
        allowances_minor = self.amount_to_minor(self.allowances_spin.value())
        advance_percent_bp = self.percent_to_bp(self.advance_percent_spin.value())
        advance_fixed_minor = self.amount_to_minor(self.advance_fixed_spin.value())
        annual_bonus_gross_minor = self.amount_to_minor(self.annual_bonus_spin.value())

        note = self.note_edit.text().strip() or None
        is_active = self.is_active_checkbox.isChecked()

        session = SessionLocal()

        try:
            account = session.get(Account, account_id)

            if account is None:
                raise ValueError("Счет не найден")

            fields = {
                "name": name,
                "kind": kind,
                "account_id": account_id,
                "income_category_id": category_id,
                "currency": account.currency,
                "tax_mode": tax_mode,
                "fixed_tax_rate_bp": fixed_tax_rate_bp,
                "tax_rule_id": None,
                "base_gross_minor": base_gross_minor,
                "allowances_minor": allowances_minor,
                "advance_percent_bp": advance_percent_bp,
                "advance_fixed_minor": advance_fixed_minor,
                "annual_bonus_gross_minor": annual_bonus_gross_minor,
                "note": note,
                "is_active": is_active,
            }

            if self.profile_id is None:
                income_profile_repository.create_income_profile(
                    session=session,
                    **fields,
                )
            else:
                profile = income_profile_repository.get_income_profile_by_id(
                    session=session,
                    profile_id=self.profile_id,
                )

                if profile is None:
                    raise ValueError("Профиль дохода не найден")

                income_profile_repository.update_income_profile(
                    session=session,
                    profile=profile,
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