import calendar
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction


def money_amount():
    return func.coalesce(Transaction.base_amount_minor, Transaction.amount_minor)

def add_months(source_date: date, months: int) -> date:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1

    return date(year, month, 1)


def get_month_start(source_date: date) -> date:
    return date(source_date.year, source_date.month, 1)


def get_month_end(source_date: date) -> date:
    last_day = calendar.monthrange(source_date.year, source_date.month)[1]

    return date(source_date.year, source_date.month, last_day)


def get_current_month_bounds() -> tuple[date, date]:
    today = date.today()

    return get_month_start(today), get_month_end(today)


def get_total_balance(session: Session) -> int:
    initial_balance = session.scalar(
        select(func.coalesce(func.sum(Account.initial_balance_minor), 0))
    )

    income_total = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "income"
        )
    )

    expense_total = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "expense"
        )
    )

    initial_balance = initial_balance or 0
    income_total = income_total or 0
    expense_total = expense_total or 0

    return initial_balance + income_total - expense_total


def get_period_summary(
    session: Session,
    start_date: date,
    end_date: date,
) -> dict:
    income_total = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "income",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
    )

    expense_total = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "expense",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
    )

    income_total = income_total or 0
    expense_total = expense_total or 0

    return {
        "income": income_total,
        "expense": expense_total,
        "net": income_total - expense_total,
    }


def get_current_month_summary(session: Session) -> dict:
    start_date, end_date = get_current_month_bounds()

    return get_period_summary(
        session=session,
        start_date=start_date,
        end_date=end_date,
    )


def get_monthly_income_expense(session: Session, months: int = 6) -> list[dict]:
    today = date.today()
    current_month_start = get_month_start(today)
    first_month_start = add_months(current_month_start, -(months - 1))

    month_label = func.strftime("%Y-%m", Transaction.occurred_at).label("month")

    statement = (
        select(
            month_label,
            Transaction.type,
            func.sum(money_amount()),
        )
        .where(Transaction.occurred_at >= first_month_start)
        .group_by(month_label, Transaction.type)
    )

    data: dict[str, dict[str, int]] = {}

    for row in session.execute(statement):
        month = row[0]
        transaction_type = row[1]
        amount = row[2]

        if month not in data:
            data[month] = {
                "income": 0,
                "expense": 0,
            }

        data[month][transaction_type] = amount

    result: list[dict] = []

    for index in range(months):
        month_start = add_months(current_month_start, index - (months - 1))
        month_key = month_start.strftime("%Y-%m")

        month_data = data.get(month_key, {})

        result.append(
            {
                "start": month_start,
                "income": month_data.get("income", 0),
                "expense": month_data.get("expense", 0),
            }
        )

    return result


def get_top_expense_categories(
    session: Session,
    start_date: date,
    end_date: date,
    limit: int = 5,
) -> list[tuple[str, int]]:
    statement = (
        select(
            Category.name,
            func.sum(money_amount()).label("total"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.type == "expense",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
        .group_by(Category.name)
        .order_by(func.sum(money_amount()).desc())
        .limit(limit)
    )

    result: list[tuple[str, int]] = []

    for row in session.execute(statement):
        result.append((row[0], row[1]))

    return result

def get_budget_spent_map(
    session: Session,
    start_date: date,
    end_date: date,
    budget_category_ids: list[int],
) -> dict[int, int]:
    if not budget_category_ids:
        return {}

    categories = session.execute(
        select(Category.id, Category.parent_id).where(Category.type == "expense")
    ).all()

    children_by_parent: dict[int, list[int]] = {}

    for category_id, parent_id in categories:
        if parent_id is None:
            continue

        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []

        children_by_parent[parent_id].append(category_id)

    statement = (
        select(
            Transaction.category_id,
            func.sum(money_amount()),
        )
        .where(
            Transaction.type == "expense",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
        .group_by(Transaction.category_id)
    )

    spent_by_category: dict[int, int] = {}

    for row in session.execute(statement):
        category_id = row[0]
        amount = row[1]

        spent_by_category[category_id] = amount or 0

    result: dict[int, int] = {}

    for budget_category_id in budget_category_ids:
        total = spent_by_category.get(budget_category_id, 0)

        child_ids = children_by_parent.get(budget_category_id, [])

        for child_id in child_ids:
            total += spent_by_category.get(child_id, 0)

        result[budget_category_id] = total

    return result

def get_balance_history_monthly(session: Session, months: int = 12) -> dict:
    today = date.today()
    current_month_start = get_month_start(today)

    keys = [
        add_months(current_month_start, index - (months - 1)).strftime("%Y-%m")
        for index in range(months)
    ]

    accounts = session.scalars(select(Account)).all()

    statement = select(
        Transaction.account_id,
        Transaction.transfer_to_account_id,
        Transaction.type,
        Transaction.amount_minor,
        Transaction.transfer_to_amount_minor,
        Transaction.occurred_at,
    )

    deltas: dict[tuple[int, str], int] = {}

    for row in session.execute(statement):
        key = row.occurred_at.strftime("%Y-%m")
        amount = row.amount_minor or 0
        to_amount = row.transfer_to_amount_minor or amount

        if row.type == "income":
            deltas[(row.account_id, key)] = (
                deltas.get((row.account_id, key), 0) + amount
            )
        elif row.type == "expense":
            deltas[(row.account_id, key)] = (
                deltas.get((row.account_id, key), 0) - amount
            )
        elif row.type == "transfer":
            deltas[(row.account_id, key)] = (
                deltas.get((row.account_id, key), 0) - amount
            )
            deltas[(row.transfer_to_account_id, key)] = (
                deltas.get((row.transfer_to_account_id, key), 0) + to_amount
            )

    running: dict[int, int] = {
        account.id: account.initial_balance_minor for account in accounts
    }

    for (account_id, key), delta in deltas.items():
        if key < keys[0]:
            running[account_id] = running.get(account_id, 0) + delta

    net_series: list[int] = []
    cash_series: list[int] = []

    for key in keys:
        for account in accounts:
            running[account.id] = running.get(account.id, 0) + deltas.get(
                (account.id, key), 0
            )

        net_series.append(sum(running.values()))

        cash_series.append(
            sum(
                running[account.id]
                for account in accounts
                if (account.type or "card") in ["cash", "card"]
            )
        )

    return {
        "labels": [f"{key[5:7]}.{key[2:4]}" for key in keys],
        "net": net_series,
        "cash": cash_series,
    }


def get_recurring_monthly_totals(session: Session) -> dict:
    from app.core import schedule
    from app.models import RecurringRule

    rules = session.scalars(
        select(RecurringRule).where(RecurringRule.is_active == True)
    ).all()

    income_total = 0
    expense_total = 0

    for rule in rules:
        if rule.amount_minor is None:
            continue

        parsed = schedule.parse_rrule(rule.rrule)
        frequency = parsed["frequency"]

        if frequency == "monthly":
            monthly_amount = rule.amount_minor
        elif frequency == "weekly":
            monthly_amount = int(rule.amount_minor * 52 / 12)
        elif frequency == "yearly":
            monthly_amount = int(rule.amount_minor / 12)
        else:
            monthly_amount = rule.amount_minor

        if rule.type == "income":
            income_total += monthly_amount
        else:
            expense_total += monthly_amount

    return {
        "income": income_total,
        "expense": expense_total,
    }


def get_manual_daily_averages(
    session: Session,
    income_days: int = 90,
    expense_days: int = 60,
) -> dict:
    from datetime import timedelta

    today = date.today()

    income_start = today - timedelta(days=income_days)
    expense_start = today - timedelta(days=expense_days)

    income_sum = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "income",
            Transaction.source != "recurring",
            Transaction.occurred_at > income_start,
        )
    ) or 0

    expense_sum = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0)).where(
            Transaction.type == "expense",
            Transaction.source != "recurring",
            Transaction.occurred_at > expense_start,
        )
    ) or 0

    return {
        "income_per_day": income_sum / income_days,
        "expense_per_day": expense_sum / expense_days,
    }


def get_forecast_series(
    session: Session,
    days: int,
    step: int = 7,
) -> dict:
    current_balance = get_total_balance(session)
    recurring = get_recurring_monthly_totals(session)
    manual = get_manual_daily_averages(session)

    income_per_day = recurring["income"] / 30 + manual["income_per_day"]
    expense_per_day = recurring["expense"] / 30 + manual["expense_per_day"]

    net_per_day = income_per_day - expense_per_day

    series: list[dict] = []

    day = 0

    while day < days:
        series.append(
            {
                "day": day,
                "balance": int(current_balance + net_per_day * day),
            }
        )

        day += step

    series.append(
        {
            "day": days,
            "balance": int(current_balance + net_per_day * days),
        }
    )

    return {
        "series": series,
        "end": int(current_balance + net_per_day * days),
        "net_per_day": net_per_day,
    }


def get_top_budget_overruns(session: Session, limit: int = 5) -> list[dict]:
    from app.repositories import budget_repository

    month_start, month_end = get_current_month_bounds()

    rows = budget_repository.get_budgets_for_table(session)

    budget_category_ids = [row[0].category_id for row in rows]

    spent_map = get_budget_spent_map(
        session=session,
        start_date=month_start,
        end_date=month_end,
        budget_category_ids=budget_category_ids,
    )

    items: list[dict] = []

    for row in rows:
        budget = row[0]
        category_name = row.category_name

        spent = spent_map.get(budget.category_id, 0)

        if budget.amount_minor > 0:
            percent = round(spent * 100 / budget.amount_minor, 1)
        else:
            percent = 0

        if spent > budget.amount_minor or percent >= 80:
            items.append(
                {
                    "category": category_name,
                    "limit": budget.amount_minor,
                    "spent": spent,
                    "percent": percent,
                }
            )

    items.sort(key=lambda item: item["spent"] - item["limit"], reverse=True)

    return items[:limit]


def get_account_balances(session: Session) -> list[dict]:
    from decimal import Decimal

    from sqlalchemy import case

    from app.models import Setting
    from app.services import rate_service

    base_setting = session.get(Setting, "base_currency")
    base_currency = (
        base_setting.value
        if base_setting and base_setting.value
        else "RUB"
    )

    accounts = session.scalars(select(Account)).all()

    result: list[dict] = []

    for account in accounts:
        signed = session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "income", money_amount()),
                            (Transaction.type == "expense", -money_amount()),
                            else_=0,
                        )
                    ),
                    0,
                )
            ).where(Transaction.account_id == account.id)
        ) or 0

        transfer_out = session.scalar(
            select(
                func.coalesce(func.sum(money_amount()), 0)
            ).where(
                Transaction.type == "transfer",
                Transaction.account_id == account.id,
            )
        ) or 0

        transfer_in = session.scalar(
            select(
                func.coalesce(
                    func.sum(Transaction.transfer_to_amount_minor), 0
                )
            ).where(
                Transaction.type == "transfer",
                Transaction.transfer_to_account_id == account.id,
            )
        ) or 0

        signed = signed - transfer_out + transfer_in

        if account.currency == base_currency:
            rate = Decimal("1")
        else:
            rate = rate_service.get_rate(
                session=session,
                from_currency=account.currency,
                to_currency=base_currency,
            ) or Decimal("1")

        initial_base = int(round(account.initial_balance_minor * rate))

        result.append(
            {
                "id": account.id,
                "name": account.name,
                "type": account.type or "card",
                "currency": account.currency,
                "balance": initial_base + signed,
                "annual_rate_bp": account.annual_rate_bp,
                "monthly_payment_minor": account.monthly_payment_minor,
            }
        )

    return result


ASSET_ACCOUNT_TYPES = ["cash", "card", "deposit", "savings"]
LIABILITY_ACCOUNT_TYPES = ["loan", "credit_card"]


def get_cash_balance(session: Session) -> int:
    balances = get_account_balances(session)

    return sum(
        item["balance"]
        for item in balances
        if item["type"] in ["cash", "card"]
    )


def get_net_worth(session: Session) -> int:
    balances = get_account_balances(session)

    return sum(item["balance"] for item in balances)


def get_total_debts(session: Session) -> int:
    balances = get_account_balances(session)

    total = 0

    for item in balances:
        if item["type"] in LIABILITY_ACCOUNT_TYPES and item["balance"] < 0:
            total += -item["balance"]

    return total


def get_interest_summary(
    session: Session,
    start_date: date,
    end_date: date,
) -> dict:
    deposit_interest = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0))
        .select_from(Transaction)
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.type == "income",
            Category.name == "Проценты по вкладам",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
    ) or 0

    loan_interest = session.scalar(
        select(func.coalesce(func.sum(money_amount()), 0))
        .select_from(Transaction)
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.type == "expense",
            Category.name == "Проценты по кредитам",
            Transaction.occurred_at >= start_date,
            Transaction.occurred_at <= end_date,
        )
    ) or 0

    return {
        "deposit_interest": deposit_interest,
        "loan_interest": loan_interest,
    }