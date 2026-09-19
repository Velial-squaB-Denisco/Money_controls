from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.db import SessionLocal
from app.repositories import category_repository
from app.ui.helpers.form_style import polish_dialog


class CategoryDialog(QDialog):
    def __init__(self, parent=None, category_id: int | None = None):
        super().__init__(parent)

        self.category_id = category_id

        if self.category_id is None:
            self.setWindowTitle("Добавить категорию")
        else:
            self.setWindowTitle("Изменить категорию")

        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()

        self.type_combo = QComboBox()
        self.type_combo.addItem("Доход", "income")
        self.type_combo.addItem("Расход", "expense")

        self.parent_combo = QComboBox()

        self.is_section_checkbox = QCheckBox("Это раздел верхнего уровня")
        self.is_archived_checkbox = QCheckBox("В архиве")

        form_layout.addRow("Название", self.name_edit)
        form_layout.addRow("Тип", self.type_combo)
        form_layout.addRow("Родитель", self.parent_combo)
        form_layout.addRow("", self.is_section_checkbox)
        form_layout.addRow("", self.is_archived_checkbox)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.type_combo.currentIndexChanged.connect(self.load_parents)

        self.load_parents()

        if self.category_id is not None:
            self.load_category()

    def load_parents(self) -> None:
        current_parent_id = self.parent_combo.currentData()

        self.parent_combo.clear()
        self.parent_combo.addItem("Без родителя", None)

        category_type = self.type_combo.currentData()

        with SessionLocal() as session:
            categories = category_repository.get_categories_by_type(
                session=session,
                type=category_type,
            )

        for category in categories:
            if category.id == self.category_id:
                continue

            self.parent_combo.addItem(category.name, category.id)

        if current_parent_id is not None:
            index = self.parent_combo.findData(current_parent_id)

            if index >= 0:
                self.parent_combo.setCurrentIndex(index)

    def load_category(self) -> None:
        with SessionLocal() as session:
            category = session.get(
                __import__("app.models", fromlist=["Category"]).Category,
                self.category_id,
            )

        if category is None:
            self.category_id = None
            return

        self.name_edit.setText(category.name)

        type_index = self.type_combo.findData(category.type)

        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        self.load_parents()

        if category.parent_id is not None:
            parent_index = self.parent_combo.findData(category.parent_id)

            if parent_index >= 0:
                self.parent_combo.setCurrentIndex(parent_index)

        self.is_section_checkbox.setChecked(category.is_section)
        self.is_archived_checkbox.setChecked(category.is_archived)

    def accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Ошибка", "Введи название категории")
            return

        category_type = self.type_combo.currentData()
        parent_id = self.parent_combo.currentData()
        is_section = self.is_section_checkbox.isChecked()
        is_archived = self.is_archived_checkbox.isChecked()

        if parent_id == self.category_id:
            parent_id = None

        session = SessionLocal()

        try:
            fields = {
                "name": name,
                "type": category_type,
                "parent_id": parent_id,
                "is_section": is_section or parent_id is None,
                "is_archived": is_archived,
            }

            if self.category_id is None:
                category_repository.create_category(session=session, **fields)
            else:
                category = category_repository.get_category_by_name(
                    session=session,
                    name=name,
                    type=category_type,
                    parent_id=parent_id,
                )

                from app.models import Category

                category = session.get(Category, self.category_id)

                if category is None:
                    raise ValueError("Категория не найдена")

                category_repository.update_category(
                    session=session,
                    category=category,
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