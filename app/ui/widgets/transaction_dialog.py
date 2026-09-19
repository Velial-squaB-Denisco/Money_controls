from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QVBoxLayout,
)

from app.db import SessionLocal
from app.repositories import (
    account_repository,
    category_repository,
    directory_repository,
    income_profile_repository,
    transaction_repository,
)
from app.services import transaction_service
from app.ui.helpers.form_style import polish_dialog


class TransactionDialog(QDialog):
    def __init__(
        self,
        parent=None,
        transaction_id: int | None = None,
        income_profile_id: int | None = None,
    ):
        super().__init__(parent)

        self.transaction_id = transaction_id
        self.income_profile_id = income_profile_id

        self._initial_data = None
        self._initial_items: list[dict] = []
        self._initial_category_id: int | None = None
        self._initial_object_text = ""
        self.product_names: list[str] = []
        self._last_products_total = 0.0

        if self.transaction_id is None:
            self.setWindowTitle("Добавить операцию")
        else:
            self.setWindowTitle("Изменить операцию")

        self.setMinimumWidth(700)

        self.category_label_by_income_kind = {
            "salary_advance": "Зарплата / Аванс",
            "salary_final": "Зарплата / Основная часть",
            "salary_bonus": "Зарплата / Премия",
            "salary_annual_bonus": "Зарплата / Годовая премия",
            "freelance": "Фриланс",
            "other": "Прочие доходы",
        }

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        type_layout = QHBoxLayout()

        self.income_radio = QRadioButton("Доход")
        self.expense_radio = QRadioButton("Расход")
        self.transfer_radio = QRadioButton("Перевод")
        self.expense_radio.setChecked(True)

        type_layout.addWidget(self.income_radio)
        type_layout.addWidget(self.expense_radio)
        type_layout.addWidget(self.transfer_radio)
        type_layout.addStretch()

        self.account_combo = QComboBox()
        self.transfer_to_combo = QComboBox()
        self.category_combo = QComboBox()

        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999_999_999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(10)
        self.amount_spin.setToolTip(
            "Для дохода это сумма, которая реально пришла на счет"
        )

        # ---------- Детали дохода ----------
        self.income_group = QGroupBox("Детали дохода")
        income_form = QFormLayout(self.income_group)

        self.income_kind_combo = QComboBox()
        self.income_kind_combo.addItem("Аванс (зарплата)", "salary_advance")
        self.income_kind_combo.addItem("Основная часть зарплаты", "salary_final")
        self.income_kind_combo.addItem("Премия", "salary_bonus")
        self.income_kind_combo.addItem("Годовая премия", "salary_annual_bonus")
        self.income_kind_combo.addItem("Фриланс", "freelance")
        self.income_kind_combo.addItem("Прочий доход", "other")

        self.income_period_edit = QDateEdit()
        self.income_period_edit.setDate(QDate.currentDate())
        self.income_period_edit.setCalendarPopup(True)
        self.income_period_edit.setDisplayFormat("MM.yyyy")
        self.income_period_edit.setToolTip("Месяц, за который начислен доход")

        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0, 999_999_999)
        self.gross_spin.setDecimals(2)
        self.gross_spin.setSingleStep(1000)
        self.gross_spin.setToolTip("Сумма до налога")

        self.tax_rate_spin = QDoubleSpinBox()
        self.tax_rate_spin.setRange(0, 100)
        self.tax_rate_spin.setDecimals(2)
        self.tax_rate_spin.setSingleStep(0.5)
        self.tax_rate_spin.setSuffix(" %")
        self.tax_rate_spin.setToolTip("Налог в процентах, например 13%")

        self.tax_amount_spin = QDoubleSpinBox()
        self.tax_amount_spin.setRange(0, 999_999_999)
        self.tax_amount_spin.setDecimals(2)
        self.tax_amount_spin.setSingleStep(100)
        self.tax_amount_spin.setToolTip("Сумма налога")

        self.calculate_income_button = QPushButton("Рассчитать сумму на руки")

        income_form.addRow("Вид дохода", self.income_kind_combo)
        income_form.addRow("Период начисления", self.income_period_edit)
        income_form.addRow("Сумма до налога", self.gross_spin)
        income_form.addRow("Налог, %", self.tax_rate_spin)
        income_form.addRow("Сумма налога", self.tax_amount_spin)
        income_form.addRow("", self.calculate_income_button)

        # ---------- Объект и комментарий ----------
        self.object_combo = QComboBox()
        self.object_combo.setEditable(True)
        self.object_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.object_combo.setPlaceholderText("Магазин, получатель, объект")

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Свободный комментарий")

        self.extra_group = QGroupBox("Дополнительно")
        extra_form = QFormLayout(self.extra_group)
        extra_form.addRow("Объект", self.object_combo)
        extra_form.addRow("Комментарий", self.note_edit)

        # ---------- Товары ----------
        self.products_group = QGroupBox("Товары")
        products_layout = QVBoxLayout(self.products_group)

        products_toolbar = QHBoxLayout()

        self.add_product_row_button = QPushButton("＋  Товар")
        self.add_product_row_button.setObjectName("secondaryButton")
        self.add_product_row_button.clicked.connect(
            lambda checked=False: self.add_product_row()
        )

        self.remove_product_row_button = QPushButton("Удалить товар")
        self.remove_product_row_button.setObjectName("secondaryButton")
        self.remove_product_row_button.clicked.connect(
            lambda checked=False: self.remove_product_row()
        )

        products_toolbar.addWidget(self.add_product_row_button)
        products_toolbar.addWidget(self.remove_product_row_button)
        products_toolbar.addStretch()

        self.products_table = QTableWidget(0, 4)
        self.products_table.setHorizontalHeaderLabels(
            ["Товар", "Кол-во", "Цена", "Сумма"]
        )
        self.products_table.setMaximumHeight(300)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.verticalHeader().setDefaultSectionSize(48)
        self.products_table.setColumnWidth(0, 280)
        self.products_table.setColumnWidth(1, 80)
        self.products_table.setColumnWidth(2, 110)
        self.products_table.setColumnWidth(3, 110)

        products_layout.addLayout(products_toolbar)
        products_layout.addWidget(self.products_table)

        form_layout.addRow("Тип операции", type_layout)
        form_layout.addRow("Счет", self.account_combo)
        form_layout.addRow("Счет получения", self.transfer_to_combo)
        form_layout.addRow("Категория", self.category_combo)
        form_layout.addRow("Дата поступления/списания", self.date_edit)
        form_layout.addRow("Сумма", self.amount_spin)
        form_layout.addRow(self.income_group)
        form_layout.addRow(self.products_group)
        form_layout.addRow(self.extra_group)

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
        self.load_transfer_accounts()

        if self.transaction_id is not None:
            self.load_initial_transaction()
            self.apply_initial_state_before_categories()
        elif self.income_profile_id is not None:
            self.apply_income_profile()

        self.income_radio.toggled.connect(self.on_transaction_type_changed)
        self.expense_radio.toggled.connect(self.on_transaction_type_changed)
        self.transfer_radio.toggled.connect(self.on_transaction_type_changed)
        self.calculate_income_button.clicked.connect(self.calculate_income)
        self.income_kind_combo.currentIndexChanged.connect(
            self.sync_category_with_income_kind
        )

        self.load_categories()
        self.load_directory_items()

        if self._initial_data is not None:
            self.apply_initial_state_after_directory()

        self.update_type_visibility()

    # =========================
    # Тип операции и видимость
    # =========================

    def current_transaction_type(self) -> str:
        if self.income_radio.isChecked():
            return "income"

        if self.transfer_radio.isChecked():
            return "transfer"

        return "expense"

    def on_transaction_type_changed(self) -> None:
        self._initial_category_id = None
        self.load_categories()
        self.update_type_visibility()

    def update_type_visibility(self) -> None:
        transaction_type = self.current_transaction_type()

        is_income = transaction_type == "income"
        is_transfer = transaction_type == "transfer"
        is_expense = transaction_type == "expense"

        self.income_group.setVisible(is_income)
        self.products_group.setVisible(is_expense)
        self.extra_group.setVisible(is_expense or is_transfer)

        show_category = not is_transfer

        self.category_combo.setVisible(show_category)

        if self._category_label is not None:
            self._category_label.setVisible(show_category)

        self.transfer_to_combo.setVisible(is_transfer)

        if self._transfer_to_label is not None:
            self._transfer_to_label.setVisible(is_transfer)

    # =========================
    # Загрузка справочников
    # =========================

    def load_accounts(self) -> None:
        self.account_combo.clear()

        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

        default_index = 0

        for index, account in enumerate(accounts):
            self.account_combo.addItem(
                f"{account.name} ({account.currency})",
                account.id,
            )

            if account.is_default:
                default_index = index

        if self.account_combo.count() > 0:
            self.account_combo.setCurrentIndex(default_index)

    def load_transfer_accounts(self) -> None:
        self.transfer_to_combo.clear()

        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

        for account in accounts:
            self.transfer_to_combo.addItem(
                f"{account.name} ({account.currency})",
                account.id,
            )

        from_id = self.account_combo.currentData()

        for index in range(self.transfer_to_combo.count()):
            if self.transfer_to_combo.itemData(index) != from_id:
                self.transfer_to_combo.setCurrentIndex(index)
                break

    def load_categories(self) -> None:
        transaction_type = self.current_transaction_type()

        self.category_combo.clear()

        with SessionLocal() as session:
            categories = category_repository.get_categories_by_type(
                session=session,
                type=transaction_type,
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
            found = False

            for index in range(self.category_combo.count()):
                if self.category_combo.itemData(index) == self._initial_category_id:
                    self.category_combo.setCurrentIndex(index)
                    found = True
                    break

            self._initial_category_id = None

            if found:
                return

        if transaction_type == "income":
            self.sync_category_with_income_kind()

    def sync_category_with_income_kind(self) -> None:
        income_kind = self.income_kind_combo.currentData()

        if not income_kind:
            return

        needed_label = self.category_label_by_income_kind.get(income_kind)

        if not needed_label:
            return

        for index in range(self.category_combo.count()):
            if self.category_combo.itemText(index) == needed_label:
                self.category_combo.setCurrentIndex(index)
                return

    def load_directory_items(self) -> None:
        self.object_combo.clear()

        with SessionLocal() as session:
            items = directory_repository.get_all_directory_items(session)

        self.product_names = []

        for item in items:
            self.object_combo.addItem(item.name, item.id)
            self.product_names.append(item.name)

        self.object_combo.setEditText("")

        object_completer = QCompleter(self)
        object_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        object_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        object_completer.setModel(self.object_combo.model())
        self.object_combo.setCompleter(object_completer)

    # =========================
    # Таблица товаров
    # =========================

    def add_product_row(
        self,
        name: str = "",
        quantity: int = 1,
        price_minor: int = 0,
    ) -> None:
        row = self.products_table.rowCount()
        self.products_table.insertRow(row)

        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.addItems(self.product_names)
        combo.setEditText(str(name))

        completer = QCompleter(combo.model(), combo)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        combo.setCompleter(completer)

        quantity_spin = QDoubleSpinBox()
        quantity_spin.setDecimals(0)
        quantity_spin.setRange(1, 9999)
        quantity_spin.setValue(quantity)

        price_spin = QDoubleSpinBox()
        price_spin.setDecimals(2)
        price_spin.setRange(0, 999_999_999)
        price_spin.setSingleStep(10)
        price_spin.setValue(price_minor / 100)

        sum_label = QLabel("0.00")
        sum_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        combo.setFixedHeight(36)
        quantity_spin.setFixedHeight(36)
        price_spin.setFixedHeight(36)

        self.products_table.setCellWidget(row, 0, combo)
        self.products_table.setCellWidget(row, 1, quantity_spin)
        self.products_table.setCellWidget(row, 2, price_spin)
        self.products_table.setCellWidget(row, 3, sum_label)

        self.products_table.setRowHeight(row, 48)

        combo.currentTextChanged.connect(self.on_product_text_changed)
        quantity_spin.valueChanged.connect(
            lambda value: self.recalc_all_products()
        )
        price_spin.valueChanged.connect(
            lambda value: self.recalc_all_products()
        )
        quantity_spin.editingFinished.connect(self.recalc_all_products)
        price_spin.editingFinished.connect(self.recalc_all_products)

        self.recalc_all_products()

    def on_product_text_changed(self, text: str) -> None:
        combo = self.sender()

        row = -1

        for index in range(self.products_table.rowCount()):
            if self.products_table.cellWidget(index, 0) is combo:
                row = index
                break

        if row < 0:
            return

        price_spin = self.products_table.cellWidget(row, 2)

        if price_spin is None:
            return

        if price_spin.value() > 0:
            return

        clean_text = text.strip()

        if not clean_text:
            return

        with SessionLocal() as session:
            last_price = directory_repository.get_last_price_minor(
                session=session,
                name=clean_text,
            )

        if last_price:
            price_spin.setValue(last_price / 100)

        self.recalc_all_products()

    def recalc_all_products(self) -> None:
        grand_total = 0.0

        for row in range(self.products_table.rowCount()):
            quantity_spin = self.products_table.cellWidget(row, 1)
            price_spin = self.products_table.cellWidget(row, 2)
            sum_label = self.products_table.cellWidget(row, 3)

            if quantity_spin is None or price_spin is None:
                continue

            total = quantity_spin.value() * price_spin.value()
            grand_total += total

            if sum_label is not None:
                sum_label.setText(f"{total:,.2f}".replace(",", " "))

        self.sync_amount_with_products(grand_total)

    def sync_amount_with_products(self, grand_total: float) -> None:
        if self.current_transaction_type() != "expense":
            self._last_products_total = grand_total
            return

        current = self.amount_spin.value()

        should_sync = (
            abs(current - self._last_products_total) < 0.005
            or current == 0
        )

        self._last_products_total = grand_total

        if should_sync and grand_total > 0:
            self.amount_spin.setValue(round(grand_total, 2))

    def remove_product_row(self) -> None:
        current_row = self.products_table.currentRow()

        if current_row < 0:
            current_row = self.products_table.rowCount() - 1

        if current_row < 0:
            return

        self.products_table.removeRow(current_row)

        self.recalc_all_products()

    def collect_products(self) -> list[dict]:
        items: list[dict] = []

        for row in range(self.products_table.rowCount()):
            combo = self.products_table.cellWidget(row, 0)
            quantity_spin = self.products_table.cellWidget(row, 1)
            price_spin = self.products_table.cellWidget(row, 2)

            if combo is None or quantity_spin is None or price_spin is None:
                continue

            name = combo.currentText().strip()

            if not name:
                continue

            quantity = int(quantity_spin.value())
            unit_price_minor = int(round(price_spin.value() * 100))

            items.append(
                {
                    "name": name,
                    "quantity": quantity,
                    "unit_price_minor": unit_price_minor,
                    "amount_minor": quantity * unit_price_minor,
                }
            )

        return items

    # =========================
    # Редактирование операции
    # =========================

    def load_initial_transaction(self) -> None:
        with SessionLocal() as session:
            transaction = transaction_repository.get_transaction_by_id(
                session=session,
                transaction_id=self.transaction_id,
            )

            if transaction is None:
                self.transaction_id = None
                return

            detail_items = transaction_repository.get_transaction_items_detail(
                session=session,
                transaction_id=transaction.id,
            )

        self._initial_items = []

        for item in detail_items:
            self._initial_items.append(
                {
                    "directory_item_id": item.directory_item_id,
                    "name_snapshot": item.name_snapshot,
                    "quantity": item.quantity or 1,
                    "unit_price_minor": item.unit_price_minor or 0,
                }
            )

        period_qdate = QDate.currentDate()

        if transaction.period_start is not None:
            period_qdate = QDate(
                transaction.period_start.year,
                transaction.period_start.month,
                1,
            )

        self._initial_data = {
            "type": transaction.type,
            "account_id": transaction.account_id,
            "category_id": transaction.category_id,
            "occurred_at": transaction.occurred_at,
            "amount_value": transaction.amount_minor / 100,
            "payee": transaction.payee or "",
            "note": transaction.note or "",
            "gross_value": (transaction.gross_amount_minor or 0) / 100,
            "tax_amount_value": (transaction.tax_amount_minor or 0) / 100,
            "tax_rate_value": (transaction.tax_rate_bp or 0) / 100,
            "income_kind": transaction.income_kind,
            "period_qdate": period_qdate,
            "transfer_to_account_id": transaction.transfer_to_account_id,
        }

    def apply_initial_state_before_categories(self) -> None:
        if self._initial_data is None:
            return

        data = self._initial_data

        if data["type"] == "income":
            self.income_radio.setChecked(True)
        elif data["type"] == "transfer":
            self.transfer_radio.setChecked(True)
        else:
            self.expense_radio.setChecked(True)

        for index in range(self.account_combo.count()):
            if self.account_combo.itemData(index) == data["account_id"]:
                self.account_combo.setCurrentIndex(index)
                break

        if data["type"] == "transfer":
            for index in range(self.transfer_to_combo.count()):
                if (
                    self.transfer_to_combo.itemData(index)
                    == data.get("transfer_to_account_id")
                ):
                    self.transfer_to_combo.setCurrentIndex(index)
                    break

        occurred_at = data["occurred_at"]

        self.date_edit.setDate(
            QDate(
                occurred_at.year,
                occurred_at.month,
                occurred_at.day,
            )
        )

        self.amount_spin.setValue(data["amount_value"])
        self.note_edit.setText(data["note"])

        if data["income_kind"]:
            income_kind_index = self.income_kind_combo.findData(data["income_kind"])

            if income_kind_index >= 0:
                self.income_kind_combo.setCurrentIndex(income_kind_index)

        self.income_period_edit.setDate(data["period_qdate"])
        self.gross_spin.setValue(data["gross_value"])
        self.tax_rate_spin.setValue(data["tax_rate_value"])
        self.tax_amount_spin.setValue(data["tax_amount_value"])

        self._initial_category_id = data["category_id"]
        self._initial_object_text = data["payee"]

    def apply_initial_state_after_directory(self) -> None:
        self.object_combo.setEditText(self._initial_object_text)

        self.products_table.setRowCount(0)

        names_by_id: dict[int, str] = {}

        with SessionLocal() as session:
            for item in directory_repository.get_all_directory_items(session):
                names_by_id[item.id] = item.name

        for item in self._initial_items:
            name = names_by_id.get(
                item.get("directory_item_id"),
                item.get("name_snapshot", ""),
            )

            self.add_product_row(
                name=name,
                quantity=item.get("quantity", 1),
                price_minor=item.get("unit_price_minor", 0),
            )

    # =========================
    # Профиль дохода
    # =========================

    def apply_income_profile(self) -> None:
        with SessionLocal() as session:
            profile = income_profile_repository.get_income_profile_by_id(
                session=session,
                profile_id=self.income_profile_id,
            )

        if profile is None:
            self.income_profile_id = None
            return

        self.income_radio.setChecked(True)

        for index in range(self.account_combo.count()):
            if self.account_combo.itemData(index) == profile.account_id:
                self.account_combo.setCurrentIndex(index)
                break

        self._initial_category_id = profile.income_category_id

        income_kind_by_profile_kind = {
            "salary": "salary_final",
            "freelance": "freelance",
            "business": "other",
            "investment": "other",
            "other": "other",
        }

        income_kind = income_kind_by_profile_kind.get(profile.kind, "other")

        income_kind_index = self.income_kind_combo.findData(income_kind)

        if income_kind_index >= 0:
            self.income_kind_combo.setCurrentIndex(income_kind_index)

        gross_minor = (profile.base_gross_minor or 0) + (
            profile.allowances_minor or 0
        )

        self.gross_spin.setValue(gross_minor / 100)

        if profile.tax_mode == "fixed" and profile.fixed_tax_rate_bp is not None:
            self.tax_rate_spin.setValue(profile.fixed_tax_rate_bp / 100)
        else:
            self.tax_rate_spin.setValue(0)

        self.prepare_income_fields()

    # =========================
    # Расчет дохода
    # =========================

    def calculate_income(self) -> None:
        gross = self.gross_spin.value()
        tax_rate = self.tax_rate_spin.value()
        tax_amount = self.tax_amount_spin.value()

        if gross <= 0:
            QMessageBox.warning(self, "Ошибка", "Заполни сумму до налога")
            return

        if tax_amount <= 0 and tax_rate > 0:
            tax_amount = round(gross * tax_rate / 100, 2)
            self.tax_amount_spin.setValue(tax_amount)

        net = gross - tax_amount

        if net < 0:
            net = 0

        self.amount_spin.setValue(round(net, 2))

    def prepare_income_fields(self) -> None:
        if not self.income_radio.isChecked():
            return

        gross = self.gross_spin.value()
        tax_rate = self.tax_rate_spin.value()
        tax_amount = self.tax_amount_spin.value()

        if gross > 0:
            if tax_amount <= 0 and tax_rate > 0:
                tax_amount = round(gross * tax_rate / 100, 2)
                self.tax_amount_spin.setValue(tax_amount)

            if self.amount_spin.value() <= 0:
                net = gross - tax_amount

                if net < 0:
                    net = 0

                self.amount_spin.setValue(round(net, 2))

    # =========================
    # Сохранение
    # =========================

    def accept(self) -> None:
        transaction_type = self.current_transaction_type()

        self.prepare_income_fields()

        amount = self.amount_spin.value()

        if amount <= 0:
            QMessageBox.warning(self, "Ошибка", "Сумма должна быть больше нуля")
            return

        account_id = self.account_combo.currentData()
        category_id = self.category_combo.currentData()

        if account_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите счет")
            return

        if category_id is None and transaction_type != "transfer":
            QMessageBox.warning(self, "Ошибка", "Выберите категорию")
            return

        transfer_to_account_id = None

        if transaction_type == "transfer":
            transfer_to_account_id = self.transfer_to_combo.currentData()

            if transfer_to_account_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите счет получения")
                return

            if transfer_to_account_id == account_id:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Счет отправителя и счет получения совпадают",
                )
                return

        occurred_at = self.date_edit.date().toPython()

        object_name = None
        note = None

        if transaction_type == "expense":
            object_name = self.object_combo.currentText().strip() or None
            note = self.note_edit.text().strip() or None
        elif transaction_type == "transfer":
            note = self.note_edit.text().strip() or None

        items: list[dict] | None = None

        if transaction_type == "expense":
            collected_items = self.collect_products()
            items = collected_items or None

        amount_minor = int(round(amount * 100))

        gross_amount_minor = None
        tax_amount_minor = None
        tax_rate_bp = None
        income_kind = None
        period_start = None
        period_end = None

        if transaction_type == "income":
            gross_value = self.gross_spin.value()
            tax_rate_value = self.tax_rate_spin.value()
            tax_amount_value = self.tax_amount_spin.value()

            if gross_value > 0 and tax_amount_value > gross_value:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Сумма налога не может быть больше суммы до налога",
                )
                return

            if gross_value > 0:
                gross_amount_minor = int(round(gross_value * 100))

            if tax_amount_value > 0:
                tax_amount_minor = int(round(tax_amount_value * 100))

            if tax_rate_value > 0:
                tax_rate_bp = int(round(tax_rate_value * 100))

            if gross_amount_minor and tax_amount_minor and tax_rate_bp is None:
                tax_rate_bp = int(
                    round(tax_amount_minor * 10000 / gross_amount_minor)
                )

            income_kind = self.income_kind_combo.currentData()

            period_date = self.income_period_edit.date().toPython()
            last_day = monthrange(period_date.year, period_date.month)[1]

            period_start = date(period_date.year, period_date.month, 1)
            period_end = date(period_date.year, period_date.month, last_day)

        session = SessionLocal()

        try:
            if self.transaction_id is None:
                transaction_service.create_transaction(
                    session=session,
                    type=transaction_type,
                    account_id=account_id,
                    category_id=category_id,
                    occurred_at=occurred_at,
                    amount_minor=amount_minor,
                    income_profile_id=self.income_profile_id,
                    object_name=object_name,
                    items=items,
                    note=note,
                    gross_amount_minor=gross_amount_minor,
                    tax_amount_minor=tax_amount_minor,
                    tax_rate_bp=tax_rate_bp,
                    income_kind=income_kind,
                    period_start=period_start,
                    period_end=period_end,
                    transfer_to_account_id=transfer_to_account_id,
                )
            else:
                transaction_service.update_transaction(
                    session=session,
                    transaction_id=self.transaction_id,
                    type=transaction_type,
                    account_id=account_id,
                    category_id=category_id,
                    occurred_at=occurred_at,
                    amount_minor=amount_minor,
                    object_name=object_name,
                    items=items,
                    note=note,
                    gross_amount_minor=gross_amount_minor,
                    tax_amount_minor=tax_amount_minor,
                    tax_rate_bp=tax_rate_bp,
                    income_kind=income_kind,
                    period_start=period_start,
                    period_end=period_end,
                    transfer_to_account_id=transfer_to_account_id,
                )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        super().accept()