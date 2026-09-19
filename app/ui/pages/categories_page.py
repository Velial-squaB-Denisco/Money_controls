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
from app.repositories import category_repository
from app.ui.widgets.category_dialog import CategoryDialog
from app.ui.helpers.form_style import style_table, style_toolbar


class CategoriesPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QTreeWidget()
        title_label.setColumnCount(0)
        title_label.setHeaderHidden(True)
        title_label.setMaximumHeight(35)

        title_item = QTreeWidgetItem(["Категории"])
        title_label.addTopLevelItem(title_item)

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        add_button = QPushButton("＋  Добавить категорию")
        add_button.clicked.connect(self.add_category)

        edit_button = QPushButton("Изменить")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected_category)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_category)

        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(edit_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addStretch()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Категория", "Тип"])
        self.tree.setColumnWidth(0, 420)

        layout.addWidget(title_label)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.tree)

        self.load_categories()

    def refresh(self) -> None:
        self.load_categories()

    def add_category(self) -> None:
        dialog = CategoryDialog(self)

        if dialog.exec():
            self.load_categories()

    def edit_selected_category(self) -> None:
        category_id = self.get_selected_category_id()

        if category_id is None:
            QMessageBox.information(
                self,
                "Категория не выбрана",
                "Выбери категорию в списке",
            )
            return

        dialog = CategoryDialog(self, category_id=category_id)

        if dialog.exec():
            self.load_categories()

    def delete_selected_category(self) -> None:
        category_id = self.get_selected_category_id()

        if category_id is None:
            QMessageBox.information(
                self,
                "Категория не выбрана",
                "Выбери категорию в списке",
            )
            return

        session = SessionLocal()

        try:
            if category_repository.is_category_used(
                session=session,
                category_id=category_id,
            ):
                QMessageBox.warning(
                    self,
                    "Категория используется",
                    "Эту категорию используют операции, бюджеты или правила. Сначала измени их",
                )
                return

            result = QMessageBox.question(
                self,
                "Удаление категории",
                "Удалить выбранную категорию?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if result != QMessageBox.StandardButton.Yes:
                return

            category_repository.delete_category(
                session=session,
                category_id=category_id,
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        self.load_categories()

    def get_selected_category_id(self) -> int | None:
        selected_items = self.tree.selectedItems()

        if not selected_items:
            return None

        return selected_items[0].data(0, 255)

    def load_categories(self) -> None:
        with SessionLocal() as session:
            categories = category_repository.get_all_categories(session)

        self.tree.clear()

        income_root = QTreeWidgetItem(["Доходы", ""])
        expense_root = QTreeWidgetItem(["Расходы", ""])

        self.tree.addTopLevelItem(income_root)
        self.tree.addTopLevelItem(expense_root)

        items_by_id = {}

        for category in categories:
            type_label = "Доход" if category.type == "income" else "Расход"

            item = QTreeWidgetItem([category.name, type_label])
            item.setData(0, 255, category.id)

            items_by_id[category.id] = item

        for category in categories:
            item = items_by_id[category.id]

            if category.parent_id is None:
                if category.type == "income":
                    income_root.addChild(item)
                else:
                    expense_root.addChild(item)
            else:
                parent_item = items_by_id.get(category.parent_id)

                if parent_item:
                    parent_item.addChild(item)

        self.tree.expandAll()