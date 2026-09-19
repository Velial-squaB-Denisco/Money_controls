from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.services import analytics_service
from app.ui import theme
from app.ui.helpers import dashboard_html
from app.ui.helpers.form_style import style_table, style_toolbar


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar_layout = QHBoxLayout()
        style_toolbar(toolbar_layout)

        title_label = QLabel("Дашборд")
        title_label.setObjectName("pageTitle")

        horizon_label = QLabel("Прогноз:")

        self.horizon_combo = QComboBox()

        for days in [30, 60, 90, 180, 360]:
            self.horizon_combo.addItem(f"{days} дней", days)

        self.horizon_combo.setCurrentIndex(0)

        self.horizon_combo.currentIndexChanged.connect(self.render)

        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(horizon_label)
        toolbar_layout.addWidget(self.horizon_combo)

        self.web_view = QWebEngineView()

        layout.addLayout(toolbar_layout)
        layout.addWidget(self.web_view)

        self.render()

    def refresh(self) -> None:
        self.render()

    def format_money(self, amount_minor: int) -> str:
        amount = amount_minor / 100

        return f"{amount:,.0f}".replace(",", " ") + " ₽"

    def format_delta(self, delta_minor: int) -> str:
        if delta_minor > 0:
            return f"+{self.format_money(delta_minor)} к прошлому месяцу"

        if delta_minor < 0:
            return f"{self.format_money(delta_minor)} к прошлому месяцу"

        return "без изменений к прошлому месяцу"

    def render(self) -> None:
        horizon = self.horizon_combo.currentData() or 30

        with SessionLocal() as session:
            cash_balance = analytics_service.get_cash_balance(session)
            net_worth = analytics_service.get_net_worth(session)
            total_debts = analytics_service.get_total_debts(session)

            current_summary = analytics_service.get_current_month_summary(session)

            month_start, month_end = analytics_service.get_current_month_bounds()

            previous_start = analytics_service.add_months(month_start, -1)
            previous_end = month_start - timedelta(days=1)

            previous_summary = analytics_service.get_period_summary(
                session=session,
                start_date=previous_start,
                end_date=previous_end,
            )

            forecast = analytics_service.get_forecast_series(
                session=session,
                days=horizon,
            )

            balance_history = analytics_service.get_balance_history_monthly(
                session=session,
                months=12,
            )

            monthly = analytics_service.get_monthly_income_expense(
                session=session,
                months=6,
            )

            top_categories = analytics_service.get_top_expense_categories(
                session=session,
                start_date=month_start,
                end_date=month_end,
                limit=7,
            )

            donut_labels = [name for name, _ in top_categories]
            donut_values = [amount / 100 for _, amount in top_categories]

            top_sum = sum(amount for _, amount in top_categories)
            other_sum = current_summary["expense"] - top_sum

            if other_sum > 0:
                donut_labels.append("Прочее")
                donut_values.append(other_sum / 100)

            overruns = analytics_service.get_top_budget_overruns(
                session=session,
                limit=5,
            )

        if current_summary["income"] > 0:
            savings_rate = round(
                current_summary["net"] * 100 / current_summary["income"],
                1,
            )
        else:
            savings_rate = 0

        cards = [
            {
                "title": "Деньги",
                "value": self.format_money(cash_balance),
            },
            {
                "title": "Чистые активы",
                "value": self.format_money(net_worth),
            },
            {
                "title": "Долги",
                "value": self.format_money(total_debts),
                "value_class": "expense" if total_debts > 0 else "",
            },
            {
                "title": "Доходы за месяц",
                "value": self.format_money(current_summary["income"]),
                "value_class": "income",
                "delta": self.format_delta(
                    current_summary["income"] - previous_summary["income"]
                ),
            },
            {
                "title": "Расходы за месяц",
                "value": self.format_money(current_summary["expense"]),
                "value_class": "expense",
                "delta": self.format_delta(
                    current_summary["expense"] - previous_summary["expense"]
                ),
            },
            {
                "title": "Остаток за месяц",
                "value": self.format_money(current_summary["net"]),
                "value_class": "income" if current_summary["net"] >= 0 else "expense",
            },
            {
                "title": f"Прогноз на {horizon} дн.",
                "value": self.format_money(forecast["end"]),
            },
        ]

        data = {
            "cards": cards,
            "balance": {
                "labels": balance_history["labels"],
                "net": [value / 100 for value in balance_history["net"]],
                "cash": [value / 100 for value in balance_history["cash"]],
            },
            "flow": {
                "labels": [
                    item["start"].strftime("%m.%y")
                    for item in monthly
                ],
                "income": [item["income"] / 100 for item in monthly],
                "expense": [item["expense"] / 100 for item in monthly],
            },
            "donut": {
                "labels": donut_labels,
                "values": donut_values,
            },
            "top": {
                "labels": [name for name, _ in top_categories],
                "values": [amount / 100 for _, amount in top_categories],
            },
            "forecast": {
                "labels": [item["day"] for item in forecast["series"]],
                "values": [item["balance"] / 100 for item in forecast["series"]],
            },
            "overruns": overruns,
        }

        html = dashboard_html.build_dashboard_html(
            data=data,
            theme_name=theme.get_theme(),
        )

        self.web_view.setHtml(html)