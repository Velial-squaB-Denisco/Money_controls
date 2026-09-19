from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction
from app.services.interest_service import get_native_balance


DEPOSIT_TYPES = ["deposit", "savings"]
LOAN_TYPES = ["loan", "credit_card"]

def get_recurring_monthly_amount(
    session: Session,
    target_account_id: int,
) -> int:
    from app.models import RecurringRule
    from app.core import schedule

    statement = (
        select(RecurringRule)
        .where(RecurringRule.is_active == True)
        .where(RecurringRule.type == "transfer")
        .where(RecurringRule.transfer_to_account_id == target_account_id)
    )

    rules = session.scalars(statement).all()

    total = 0

    for rule in rules:
        if rule.amount_minor is None:
            continue

        parsed = schedule.parse_rrule(rule.rrule)
        frequency = parsed["frequency"]

        if frequency == "monthly":
            monthly = rule.amount_minor
        elif frequency == "weekly":
            monthly = int(rule.amount_minor * 52 / 12)
        elif frequency == "yearly":
            monthly = int(rule.amount_minor / 12)
        else:
            monthly = rule.amount_minor

        total += monthly

    return total


def zero_flow() -> dict:
    return {
        "contributions": 0,
        "withdrawals": 0,
        "interest_in": 0,
        "interest_out": 0,
    }


def month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def parse_key(key: str) -> tuple[int, int]:
    year, month = key.split("-")
    return int(year), int(month)


def list_keys(start_key: str, end_key: str) -> list[str]:
    keys = []
    year, month = parse_key(start_key)
    end_year, end_month = parse_key(end_key)

    while (year, month) <= (end_year, end_month):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    return keys


def label_of(key: str) -> str:
    year, month = parse_key(key)
    return f"{month:02d}.{str(year)[2:]}"


def get_flows_by_month(session: Session, account_id: int) -> dict:
    category_names = {
        category.id: category.name
        for category in session.scalars(select(Category)).all()
    }

    statement = select(
        Transaction.type,
        Transaction.category_id,
        Transaction.transfer_to_account_id,
        Transaction.amount_minor,
        Transaction.occurred_at,
    ).where(
        (Transaction.account_id == account_id)
        | (Transaction.transfer_to_account_id == account_id)
    )

    flows: dict[str, dict] = {}

    for row in session.execute(statement):
        key = month_key(row.occurred_at)
        bucket = flows.setdefault(key, zero_flow())
        amount = row.amount_minor or 0

        if row.type == "transfer":
            if row.transfer_to_account_id == account_id:
                bucket["contributions"] += amount
            else:
                bucket["withdrawals"] += amount
        elif row.type == "income":
            if category_names.get(row.category_id) == "Проценты по вкладам":
                bucket["interest_in"] += amount
        elif row.type == "expense":
            if category_names.get(row.category_id) == "Проценты по кредитам":
                bucket["interest_out"] += amount

    return flows


def get_deposit_analytics(session: Session, account_id: int) -> dict:
    account = session.get(Account, account_id)
    flows = get_flows_by_month(session, account_id)

    today = date.today()
    end_key = month_key(today)
    start_key = min(min(flows.keys()), end_key) if flows else end_key

    keys = list_keys(start_key, end_key)

    balance = account.initial_balance_minor
    months = []
    totals = {"contributions": 0, "interest": 0, "withdrawals": 0}
    balance_sum = 0

    for key in keys:
        flow = flows.get(key) or zero_flow()

        balance += flow["contributions"] + flow["interest_in"] - flow["withdrawals"]

        months.append(
            {
                "key": key,
                "label": label_of(key),
                "contributions": flow["contributions"],
                "interest": flow["interest_in"],
                "withdrawals": flow["withdrawals"],
                "balance": balance,
            }
        )

        totals["contributions"] += flow["contributions"]
        totals["interest"] += flow["interest_in"]
        totals["withdrawals"] += flow["withdrawals"]
        balance_sum += balance

    avg_balance = balance_sum / len(keys) if keys else 0

    effective = 0.0
    if avg_balance > 0 and keys:
        effective = (totals["interest"] / avg_balance) * (12 / len(keys)) * 100

    return {
        "months": months,
        "totals": totals,
        "current_balance": balance,
        "effective_rate_percent": round(effective, 2),
    }


def forecast_deposit(
    session: Session,
    account_id: int,
    months_count: int,
    contribution_minor: int | None = None,
) -> list[dict]:
    account = session.get(Account, account_id)
    balance = get_native_balance(session, account_id)

    monthly_rate = (account.annual_rate_bp or 0) / 10000 / 12

    if contribution_minor is None:
        recurring = get_recurring_monthly_amount(session, account_id)

        if recurring > 0:
            contribution_minor = recurring
        else:
            contribution_minor = account.monthly_payment_minor or 0

    interest_cum = 0

    series = [
        {
            "month": 0,
            "balance": balance,
            "interest": 0,
            "interest_cum": 0,
        }
    ]

    for month in range(1, months_count + 1):
        interest = int(round(balance * monthly_rate))
        interest_cum += interest
        balance = balance + contribution_minor + interest

        series.append(
            {
                "month": month,
                "balance": balance,
                "interest": interest,
                "interest_cum": interest_cum,
            }
        )

    return series


def simulate_payoff(
    debt_minor: int,
    annual_rate_bp: int,
    payment_minor: int,
    max_months: int = 1200,
) -> dict:
    if debt_minor <= 0:
        return {"months": 0, "total_interest": 0}

    if payment_minor <= 0:
        return {"months": None, "total_interest": None}

    monthly_rate = annual_rate_bp / 10000 / 12
    months = 0
    total_interest = 0

    while debt_minor > 0 and months < max_months:
        interest = int(round(debt_minor * monthly_rate))
        principal = payment_minor - interest

        if principal <= 0:
            return {"months": None, "total_interest": None}

        debt_minor -= principal
        total_interest += interest
        months += 1

    return {"months": months, "total_interest": total_interest}


def payoff_date_from_months(months: int | None) -> date | None:
    if months is None:
        return None

    today = date.today()
    total = today.month - 1 + months
    year = today.year + total // 12
    month = total % 12 + 1

    return date(year, month, 1)


def get_loan_analytics(
    session: Session,
    account_id: int,
    extra_payment_minor: int = 0,
    base_payment_minor: int | None = None,
) -> dict:
    account = session.get(Account, account_id)
    flows = get_flows_by_month(session, account_id)

    today = date.today()
    end_key = month_key(today)
    start_key = min(flows.keys()) if flows else end_key

    keys = list_keys(start_key, end_key)

    balance = account.initial_balance_minor
    months = []
    totals = {"principal": 0, "interest": 0}

    for key in keys:
        flow = flows.get(key) or zero_flow()

        balance += flow["contributions"] - flow["interest_out"]

        months.append(
            {
                "key": key,
                "label": label_of(key),
                "principal": flow["contributions"],
                "interest": flow["interest_out"],
                "debt": -balance,
            }
        )

        totals["principal"] += flow["contributions"]
        totals["interest"] += flow["interest_out"]

    current_debt = -balance
    if current_debt < 0:
        current_debt = 0

    if base_payment_minor is None:
        payment = account.monthly_payment_minor or 0
    else:
        payment = base_payment_minor

    base = simulate_payoff(current_debt, account.annual_rate_bp or 0, payment)
    with_extra = simulate_payoff(
        current_debt,
        account.annual_rate_bp or 0,
        payment + extra_payment_minor,
    )

    return {
        "months": months,
        "totals": totals,
        "current_debt": current_debt,
        "payment_minor": payment,
        "base": base,
        "with_extra": with_extra,
        "extra_payment_minor": extra_payment_minor,
    }
    
def forecast_loan(
    session: Session,
    account_id: int,
    payment_minor: int | None = None,
    max_months: int = 600,
) -> list[dict]:
    account = session.get(Account, account_id)

    debt = -get_native_balance(session, account_id)

    if debt < 0:
        debt = 0

    monthly_rate = (account.annual_rate_bp or 0) / 10000 / 12

    if payment_minor is None or payment_minor <= 0:
        recurring = get_recurring_monthly_amount(session, account_id)

        if recurring > 0:
            payment_minor = recurring
        else:
            payment_minor = account.monthly_payment_minor or 0

    series = [{"month": 0, "balance": -debt}]

    month = 0

    while debt > 0 and month < max_months:
        interest = int(round(debt * monthly_rate))
        principal = payment_minor - interest

        if principal <= 0:
            break

        if principal >= debt:
            debt = 0
        else:
            debt -= principal

        month += 1
        series.append({"month": month, "balance": -debt})

        if debt == 0:
            break

    return series