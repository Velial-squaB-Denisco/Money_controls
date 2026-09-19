from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.repositories import directory_repository
from app.ui.widgets.directory_item_dialog import DirectoryItemDialog
from app.ui.helpers.form_style import style_table, style_toolbar


class DirectoryPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить объект")
        add_button.clicked.connect(self.add_item)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_item)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_item)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addStretch()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Название", "Тип", "Заметка"])
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 180)

        layout.addLayout(toolbar_layout)
        layout.addWidget(self.tree)

        self.load_items()

    def refresh(self) -> None:
        self.load_items()

    def add_item(self) -> None:
        dialog = DirectoryItemDialog(self)

        if dialog.exec():
            self.load_items()

    def edit_selected_item(self) -> None:
        item_id = self.get_selected_item_id()

        if item_id is None:
            QMessageBox.information(
                self,
                "Объект не выбран",
                "Выбери объект в списке",
            )
            return

        dialog = DirectoryItemDialog(self, item_id=item_id)

        if dialog.exec():
            self.load_items()

    def delete_selected_item(self) -> None:
        item_id = self.get_selected_item_id()

        if item_id is None:
            QMessageBox.information(
                self,
                "Объект не выбран",
                "Выбери объект в списке",
            )
            return

        session = SessionLocal()

        try:
            if directory_repository.is_directory_item_used(
                session=session,
                item_id=item_id,
            ):
                QMessageBox.warning(
                    self,
                    "Объект используется",
                    "Этот объект привязан к операциям или товарам. Сначала измени их",
                )
                return

            result = QMessageBox.question(
                self,
                "Удаление объекта",
                "Удалить выбранный объект?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if result != QMessageBox.StandardButton.Yes:
                return

            directory_repository.delete_directory_item(
                session=session,
                item_id=item_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_items()

    def get_selected_item_id(self) -> int | None:
        selected_items = self.tree.selectedItems()

        if not selected_items:
            return None

        return selected_items[0].data(0, 255)

    def load_items(self) -> None:
        with SessionLocal() as session:
            items = directory_repository.get_all_directory_items(session)

        self.tree.clear()

        kind_labels = {
            "product": "Товар",
            "merchant": "Магазин",
            "service": "Услуга",
            "subscription": "Подписка",
            "other": "Другое",
        }

        for item in items:
            row = QTreeWidgetItem(
                [
                    item.name,
                    kind_labels.get(item.kind, item.kind),
                    item.note or "",
                ]
            )

            row.setData(0, 255, item.id)

            self.tree.addTopLevelItem(row)