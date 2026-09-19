from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.repositories import settings_repository
from app.services import rate_service, transaction_service
from app.ui import theme


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel("Настройки")
        title_label.setObjectName("pageTitle")

        common_group = QGroupBox("Общие")
        common_form = QFormLayout(common_group)

        self.base_currency_combo = QComboBox()
        self.base_currency_combo.addItem("Рубли (RUB)", "RUB")
        self.base_currency_combo.addItem("Доллары (USD)", "USD")

        save_base_currency_button = QPushButton("Сохранить основную валюту")
        save_base_currency_button.clicked.connect(self.save_base_currency)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Темная", "dark")

        apply_theme_button = QPushButton("Применить тему")
        apply_theme_button.clicked.connect(self.apply_theme)

        common_form.addRow("Основная валюта", self.base_currency_combo)
        common_form.addRow("", save_base_currency_button)
        common_form.addRow("Тема приложения", self.theme_combo)
        common_form.addRow("", apply_theme_button)

        rates_group = QGroupBox("Курсы валют")
        rates_form = QFormLayout(rates_group)

        self.usd_rate_label = QLabel("-")

        refresh_rates_button = QPushButton("Обновить курсы ЦБ")
        refresh_rates_button.setObjectName("secondaryButton")
        refresh_rates_button.clicked.connect(self.refresh_rates)

        self.manual_usd_rate_spin = QDoubleSpinBox()
        self.manual_usd_rate_spin.setRange(0, 10000)
        self.manual_usd_rate_spin.setDecimals(4)
        self.manual_usd_rate_spin.setSingleStep(0.5)

        save_manual_rate_button = QPushButton("Сохранить ручной курс USD")
        save_manual_rate_button.setObjectName("secondaryButton")
        save_manual_rate_button.clicked.connect(self.save_manual_rate)

        rates_form.addRow("Курс USD → RUB", self.usd_rate_label)
        rates_form.addRow("", refresh_rates_button)
        rates_form.addRow("Ручной курс USD", self.manual_usd_rate_spin)
        rates_form.addRow("", save_manual_rate_button)

        layout.addWidget(title_label)
        layout.addWidget(common_group)
        layout.addWidget(rates_group)
        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        with SessionLocal() as session:
            base_currency = settings_repository.get_setting(
                session=session,
                key="base_currency",
                default="RUB",
            )

            latest_rate = rate_service.get_latest_rate_info(session)

        index = self.base_currency_combo.findData(base_currency or "RUB")

        if index >= 0:
            self.base_currency_combo.setCurrentIndex(index)

        if latest_rate is not None:
            self.usd_rate_label.setText(
                f"{latest_rate.rate:.4f} на {latest_rate.rate_date.strftime('%d.%m.%Y')}"
            )
        else:
            self.usd_rate_label.setText("Курс не загружен")

        current_theme = theme.get_theme()

        theme_index = self.theme_combo.findData(current_theme)

        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)

    def save_base_currency(self) -> None:
        base_currency = self.base_currency_combo.currentData() or "RUB"

        session = SessionLocal()

        try:
            settings_repository.set_setting(
                session=session,
                key="base_currency",
                value=base_currency,
            )

            updated_count = transaction_service.recalculate_all_base_amounts(
                session
            )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        QMessageBox.information(
            self,
            "Валюта сохранена",
            f"Основная валюта: {base_currency}\nПересчитано операций: {updated_count}",
        )

        self.refresh()

    def refresh_rates(self) -> None:
        session = SessionLocal()

        try:
            created_count = rate_service.refresh_rates(session)
            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(
                self,
                "Ошибка загрузки курсов",
                str(exception),
            )
            return
        finally:
            session.close()

        QMessageBox.information(
            self,
            "Курсы обновлены",
            f"Загружено курсов: {created_count}",
        )

        self.refresh()

    def save_manual_rate(self) -> None:
        from datetime import date
        from decimal import Decimal

        from app.models import ExchangeRate

        rate_value = self.manual_usd_rate_spin.value()

        if rate_value <= 0:
            QMessageBox.warning(self, "Ошибка", "Курс должен быть больше нуля")
            return

        session = SessionLocal()

        try:
            today = date.today()

            existing = session.scalar(
                __import__("sqlalchemy").select(ExchangeRate)
                .where(ExchangeRate.from_currency == "USD")
                .where(ExchangeRate.to_currency == "RUB")
                .where(ExchangeRate.rate_date == today)
            )

            if existing is not None:
                existing.rate = Decimal(str(rate_value))
                existing.source = "manual"
            else:
                session.add(
                    ExchangeRate(
                        from_currency="USD",
                        to_currency="RUB",
                        rate_date=today,
                        rate=Decimal(str(rate_value)),
                        source="manual",
                    )
                )

            session.commit()
        except Exception as exception:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", str(exception))
            return
        finally:
            session.close()

        QMessageBox.information(
            self,
            "Курс сохранен",
            "Ручной курс USD сохранен",
        )

        self.refresh()

    def apply_theme(self) -> None:
        theme_name = self.theme_combo.currentData()

        if theme_name is None:
            theme_name = "light"

        theme.set_theme(theme_name)

        main_window = self.window()

        if hasattr(main_window, "refresh_current_page") and hasattr(
            main_window, "pages"
        ):
            main_window.refresh_current_page(
                main_window.pages.currentIndex()
            )

        QMessageBox.information(
            self,
            "Тема применена",
            "Тема применена",
        )