from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.db import SessionLocal
from app.models import Account
from app.repositories import account_repository
from app.services import deposit_loan_analytics as analytics
from app.ui import theme
from app.ui.helpers import finance_html


TYPE_LABELS = {
    "deposit": "Вклад",
    "savings": "Накопления",
    "loan": "Кредит",
    "credit_card": "Кредитная карта",
}


def fmt(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


class FinancePage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Счет:"))

        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(220)
        self.account_combo.currentIndexChanged.connect(self.render)
        toolbar.addWidget(self.account_combo)

        toolbar.addWidget(QLabel("Прогноз:"))

        self.horizon_combo = QComboBox()
        for months in (6, 12, 24, 36, 60, 120):
            self.horizon_combo.addItem(f"{months} мес", months)
        self.horizon_combo.currentIndexChanged.connect(self.render)
        toolbar.addWidget(self.horizon_combo)

        toolbar.addWidget(QLabel("Доп. платеж / взнос:"))

        self.extra_spin = QDoubleSpinBox()
        self.extra_spin.setRange(0, 999_999_999)
        self.extra_spin.setDecimals(2)
        self.extra_spin.setSingleStep(1000)
        self.extra_spin.valueChanged.connect(self.render)
        toolbar.addWidget(self.extra_spin)

        toolbar.addStretch()

        self.web_view = QWebEngineView()

        layout.addLayout(toolbar)
        layout.addWidget(self.web_view)

        self.load_accounts()

    def refresh(self) -> None:
        self.render()

    # =========================
    # Счета
    # =========================

    def load_accounts(self) -> None:
        current = self.account_combo.currentData()

        self.account_combo.blockSignals(True)
        self.account_combo.clear()

        with SessionLocal() as session:
            accounts = account_repository.get_all_accounts(session)

        for account in accounts:
            account_type = account.type or "card"

            if account_type in analytics.DEPOSIT_TYPES + analytics.LOAN_TYPES:
                self.account_combo.addItem(
                    f"{account.name} ({TYPE_LABELS.get(account_type, account_type)})",
                    account.id,
                )

        if current is not None:
            index = self.account_combo.findData(current)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

        self.account_combo.blockSignals(False)

        self.render()

    def render(self) -> None:
        account_id = self.account_combo.currentData()

        if account_id is None:
            self.web_view.setHtml(finance_html.build_empty_html(theme.get_theme()))
            return

        with SessionLocal() as session:
            account = session.get(Account, account_id)

            if account is None:
                self.web_view.setHtml(
                    finance_html.build_empty_html(theme.get_theme())
                )
                return

            account_type = account.type or "card"

            if account_type in analytics.DEPOSIT_TYPES:
                payload = self.build_deposit_payload(session, account)
            else:
                payload = self.build_loan_payload(session, account)

        self.web_view.setHtml(
            finance_html.build_finance_html(payload, theme.get_theme())
        )

    # =========================
    # Вклады и накопления
    # =========================

    def build_deposit_payload(self, session, account) -> dict:
        data = analytics.get_deposit_analytics(session, account.id)

        horizon = self.horizon_combo.currentData() or 12

        extra_minor = int(round(self.extra_spin.value() * 100))

        recurring_contribution = analytics.get_recurring_monthly_amount(
            session, account.id
        )

        base_contribution = (
            recurring_contribution
            if recurring_contribution > 0
            else (account.monthly_payment_minor or 0)
        )

        forecast = analytics.forecast_deposit(
            session,
            account.id,
            horizon,
            contribution_minor=base_contribution + extra_minor,
        )

        forecast_no_contrib = analytics.forecast_deposit(
            session,
            account.id,
            horizon,
            contribution_minor=0,
        )

        cards = [
            {
                "title": "Текущий баланс",
                "value": fmt(data["current_balance"] / 100),
            },
            {
                "title": "Внесено самим",
                "value": fmt(data["totals"]["contributions"] / 100),
            },
            {
                "title": "Начислено банком",
                "value": fmt(data["totals"]["interest"] / 100),
                "value_class": "income",
            },
            {
                "title": "Снято",
                "value": fmt(data["totals"]["withdrawals"] / 100),
                "value_class": "expense",
            },
            {
                "title": "Эффективная ставка",
                "value": f"{data['effective_rate_percent']}%",
            },
        ]

        forecast_points = forecast[1:]

        charts = [
            {
                "id": "flowChart",
                "title": "Пополнения / проценты / снятия по месяцам",
                "type": "bar",
                "labels": [month["label"] for month in data["months"]],
                "datasets": [
                    {
                        "label": "Пополнения",
                        "data": [
                            month["contributions"] / 100 for month in data["months"]
                        ],
                        "color": "@income",
                    },
                    {
                        "label": "Проценты",
                        "data": [month["interest"] / 100 for month in data["months"]],
                        "color": "@accent",
                    },
                    {
                        "label": "Снятия",
                        "data": [
                            month["withdrawals"] / 100 for month in data["months"]
                        ],
                        "color": "@expense",
                    },
                ],
            },
            {
                "id": "balanceChart",
                "title": "Рост баланса",
                "type": "line",
                "labels": [month["label"] for month in data["months"]],
                "datasets": [
                    {
                        "label": "Баланс",
                        "data": [month["balance"] / 100 for month in data["months"]],
                        "color": "@accent",
                        "line": True,
                        "fill": True,
                    }
                ],
            },
            {
                "id": "interestMonthlyChart",
                "title": "Прогноз: сколько процентов придет в каждом месяце",
                "type": "bar",
                "labels": [str(point["month"]) for point in forecast_points],
                "datasets": [
                    {
                        "label": "Проценты за месяц",
                        "data": [point["interest"] / 100 for point in forecast_points],
                        "color": "@income",
                    }
                ],
            },
            {
                "id": "interestProfitChart",
                "title": f"Прибыль от процентов нарастающим итогом за {horizon} мес",
                "type": "line",
                "labels": [str(point["month"]) for point in forecast_points],
                "datasets": [
                    {
                        "label": "Накопленные проценты",
                        "data": [
                            point["interest_cum"] / 100 for point in forecast_points
                        ],
                        "color": "@income",
                        "line": True,
                        "fill": True,
                    }
                ],
            },
            {
                "id": "forecastChart",
                "title": f"Прогноз с капитализацией на {horizon} мес",
                "type": "line",
                "labels": [str(point["month"]) for point in forecast],
                "datasets": [
                    {
                        "label": "С пополнениями и доп. взносом",
                        "data": [point["balance"] / 100 for point in forecast],
                        "color": "@income",
                        "line": True,
                        "fill": True,
                    },
                    {
                        "label": "Только проценты (без пополнений)",
                        "data": [
                            point["balance"] / 100 for point in forecast_no_contrib
                        ],
                        "color": "@accent",
                        "line": True,
                        "fill": False,
                    },
                ],
            },
        ]

        return {
            "title": f"{account.name} · {TYPE_LABELS.get(account.type, '')}",
            "cards": cards,
            "charts": charts,
        }

    # =========================
    # Кредиты и кредитки
    # =========================

    def build_loan_payload(self, session, account) -> dict:
        extra_minor = int(round(self.extra_spin.value() * 100))

        recurring_payment = analytics.get_recurring_monthly_amount(
            session, account.id
        )

        base_payment = (
            recurring_payment
            if recurring_payment > 0
            else (account.monthly_payment_minor or 0)
        )

        account_for_analytics = account

        if recurring_payment > 0 and account.monthly_payment_minor != recurring_payment:
            account_for_analytics = account

        data = analytics.get_loan_analytics(
            session,
            account.id,
            extra_minor,
            base_payment_minor=base_payment,
        )

        base = data["base"]
        with_extra = data["with_extra"]

        payoff_base = analytics.payoff_date_from_months(base["months"])
        payoff_extra = analytics.payoff_date_from_months(with_extra["months"])

        cards = [
            {
                "title": "Текущий долг",
                "value": fmt(data["current_debt"] / 100),
                "value_class": "expense",
            },
            {
                "title": "Платеж в месяц",
                "value": fmt((data["payment_minor"] + extra_minor) / 100),
            },
            {
                "title": "Ставка",
                "value": f"{(account.annual_rate_bp or 0) / 100:.2f}%",
            },
            {
                "title": "Закрытие при текущем платеже",
                "value": payoff_base.strftime("%m.%Y") if payoff_base else "—",
            },
            {
                "title": "Переплата процентов (осталось)",
                "value": fmt((base["total_interest"] or 0) / 100),
                "value_class": "expense",
            },
        ]

        if extra_minor > 0 and base["months"] and with_extra["months"] is not None:
            saved_interest = (base["total_interest"] or 0) - (
                with_extra["total_interest"] or 0
            )
            saved_months = base["months"] - with_extra["months"]

            cards.append(
                {
                    "title": "Экономия на процентах",
                    "value": fmt(saved_interest / 100),
                    "value_class": "income",
                }
            )
            cards.append(
                {
                    "title": "Закроется быстрее на",
                    "value": f"{saved_months} мес",
                    "value_class": "income",
                }
            )

            if payoff_extra is not None:
                cards.append(
                    {
                        "title": "Новая дата закрытия",
                        "value": payoff_extra.strftime("%m.%Y"),
                    }
                )

        charts = [
            {
                "id": "payChart",
                "title": "Погашение по месяцам: тело и проценты",
                "type": "bar",
                "labels": [month["label"] for month in data["months"]],
                "datasets": [
                    {
                        "label": "Тело",
                        "data": [month["principal"] / 100 for month in data["months"]],
                        "color": "@accent",
                    },
                    {
                        "label": "Проценты",
                        "data": [month["interest"] / 100 for month in data["months"]],
                        "color": "@expense",
                    },
                ],
            },
            {
                "id": "debtChart",
                "title": "Динамика долга",
                "type": "line",
                "labels": [month["label"] for month in data["months"]],
                "datasets": [
                    {
                        "label": "Баланс кредита",
                        "data": [-month["debt"] / 100 for month in data["months"]],
                        "color": "@expense",
                        "line": True,
                        "fill": True,
                    }
                ],
            },
        ]

        base_forecast = analytics.forecast_loan(
            session,
            account.id,
            payment_minor=data["payment_minor"],
        )

        forecast_datasets = [
            {
                "label": "Текущий платеж",
                "data": [point["balance"] / 100 for point in base_forecast],
                "color": "@expense",
                "line": True,
                "fill": True,
            }
        ]

        if extra_minor > 0:
            extra_forecast = analytics.forecast_loan(
                session,
                account.id,
                payment_minor=data["payment_minor"] + extra_minor,
            )

            forecast_datasets.append(
                {
                    "label": "С доп. платежом",
                    "data": [point["balance"] / 100 for point in extra_forecast],
                    "color": "@income",
                    "line": True,
                    "fill": False,
                }
            )

        charts.append(
            {
                "id": "loanForecastChart",
                "title": "Прогноз долга до полного закрытия",
                "type": "line",
                "labels": [str(point["month"]) for point in base_forecast],
                "datasets": forecast_datasets,
            }
        )

        return {
            "title": f"{account.name} · {TYPE_LABELS.get(account.type, '')}",
            "cards": cards,
            "charts": charts,
        }