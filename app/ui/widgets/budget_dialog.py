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

from app.db import SessionLocal
from app.repositories import budget_repository, category_repository
from app.ui.helpers.form_style import polish_dialog


class BudgetDialog(QDialog):
    def __init__(self, parent=None, budget_id: int | None = None):
        super().__init__(parent)

        self.budget_id = budget_id

        if self.budget_id is None:
            self.setWindowTitle("Добавить бюджет")
        else:
            self.setWindowTitle("Изменить бюджет")

        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.category_combo = QComboBox()

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999_999_999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(500)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Комментарий к бюджету")

        self.active_checkbox = QCheckBox("Активен")
        self.active_checkbox.setChecked(True)

        form_layout.addRow("Категория", self.category_combo)
        form_layout.addRow("Лимит на месяц", self.amount_spin)
        form_layout.addRow("Комментарий", self.note_edit)
        form_layout.addRow("", self.active_checkbox)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.load_categories()

        if self.budget_id is not None:
            self.load_budget()

    def load_categories(self) -> None:
        self.category_combo.clear()

        with SessionLocal() as session:
            categories = category_repository.get_categories_by_type(
                session=session,
                type="expense",
            )

        categories_by_id = {category.id: category for category in categories}

        for category in categories:
            label = category.name

            if category.parent_id is not None:
                parent = categories_by_id.get(category.parent_id)

                if parent:
                    label = f"{parent.name} / {category.name}"

            self.category_combo.addItem(label, category.id)

    def load_budget(self) -> None:
        with SessionLocal() as session:
            budget = budget_repository.get_budget_by_id(
                session=session,
                budget_id=self.budget_id,
            )

        if budget is None:
            self.budget_id = None
            return

        for index in range(self.category_combo.count()):
            if self.category_combo.itemData(index) == budget.category_id:
                self.category_combo.setCurrentIndex(index)
                break

        self.amount_spin.setValue(budget.amount_minor / 100)
        self.note_edit.setText(budget.note or "")
        self.active_checkbox.setChecked(budget.is_active)

    def accept(self) -> None:
        category_id = self.category_combo.currentData()

        if category_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите категорию")
            return

        amount = self.amount_spin.value()

        if amount <= 0:
            QMessageBox.warning(self, "Ошибка", "Лимит должен быть больше нуля")
            return

        amount_minor = int(round(amount * 100))
        note = self.note_edit.text().strip() or None
        is_active = self.active_checkbox.isChecked()

        session = SessionLocal()

        try:
            existing_budget = budget_repository.get_budget_by_category(
                session=session,
                category_id=category_id,
                period_type="monthly",
                exclude_budget_id=self.budget_id,
            )

            if existing_budget is not None:
                QMessageBox.warning(
                    self,
                    "Бюджет уже существует",
                    "Для этой категории уже есть месячный бюджет",
                )
                return

            fields = {
                "category_id": category_id,
                "period_type": "monthly",
                "amount_minor": amount_minor,
                "currency": "RUB",
                "note": note,
                "is_active": is_active,
            }

            if self.budget_id is None:
                budget_repository.create_budget(
                    session=session,
                    **fields,
                )
            else:
                budget = budget_repository.get_budget_by_id(
                    session=session,
                    budget_id=self.budget_id,
                )

                if budget is None:
                    raise ValueError("Бюджет не найден")

                budget_repository.update_budget(
                    session=session,
                    budget=budget,
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