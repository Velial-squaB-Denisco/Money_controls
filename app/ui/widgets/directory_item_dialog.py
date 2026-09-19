from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.db import SessionLocal
from app.repositories import directory_repository
from app.ui.helpers.form_style import polish_dialog


class DirectoryItemDialog(QDialog):
    def __init__(self, parent=None, item_id: int | None = None):
        super().__init__(parent)

        self.item_id = item_id

        if self.item_id is None:
            self.setWindowTitle("Добавить объект")
        else:
            self.setWindowTitle("Изменить объект")

        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Товар", "product")
        self.kind_combo.addItem("Магазин", "merchant")
        self.kind_combo.addItem("Услуга", "service")
        self.kind_combo.addItem("Подписка", "subscription")
        self.kind_combo.addItem("Другое", "other")

        self.note_edit = QLineEdit()

        form_layout.addRow("Название", self.name_edit)
        form_layout.addRow("Тип", self.kind_combo)
        form_layout.addRow("Заметка", self.note_edit)

        polish_dialog(self, form_layout, layout)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        if self.item_id is not None:
            self.load_item()

    def load_item(self) -> None:
        with SessionLocal() as session:
            item = session.get(
                __import__("app.models", fromlist=["DirectoryItem"]).DirectoryItem,
                self.item_id,
            )

        if item is None:
            self.item_id = None
            return

        self.name_edit.setText(item.name)

        kind_index = self.kind_combo.findData(item.kind)

        if kind_index >= 0:
            self.kind_combo.setCurrentIndex(kind_index)

        self.note_edit.setText(item.note or "")

    def accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Ошибка", "Введи название объекта")
            return

        kind = self.kind_combo.currentData()
        note = self.note_edit.text().strip() or None

        session = SessionLocal()

        try:
            if self.item_id is None:
                directory_repository.get_or_create_directory_item(
                    session=session,
                    name=name,
                    kind=kind,
                    note=note,
                )
            else:
                from app.models import DirectoryItem

                item = session.get(DirectoryItem, self.item_id)

                if item is None:
                    raise ValueError("Объект не найден")

                directory_repository.update_directory_item(
                    session=session,
                    item=item,
                    name=name,
                    kind=kind,
                    note=note,
                )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        super().accept()