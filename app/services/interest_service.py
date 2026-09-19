import calendar
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction
from app.repositories import category_repository
from app.services import transaction_service


DEPOSIT_TYPES = ["deposit", "savings"]
LOAN_TYPES = ["loan", "credit_card"]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]

    return date(year, month, 1), date(year, month, last_day)


def get_native_balance(session: Session, account_id: int) -> int:
    account = session.get(Account, account_id)

    if account is None:
        return 0

    signed = session.scalar(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.type == "income", Transaction.amount_minor),
                        (Transaction.type == "expense", -Transaction.amount_minor),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(Transaction.account_id == account_id)
    ) or 0

    transfer_out = session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
            Transaction.type == "transfer",
            Transaction.account_id == account_id,
        )
    ) or 0

    transfer_in = session.scalar(
        select(
            func.coalesce(func.sum(Transaction.transfer_to_amount_minor), 0)
        ).where(
            Transaction.type == "transfer",
            Transaction.transfer_to_account_id == account_id,
        )
    ) or 0

    return account.initial_balance_minor + signed - transfer_out + transfer_in


def exists_month_income(
    session: Session,
    account_id: int,
    source: str,
    year: int,
    month: int,
) -> bool:
    start, end = month_bounds(year, month)

    count = session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.type == "income",
            Transaction.account_id == account_id,
            Transaction.source == source,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
    )

    return (count or 0) > 0


def exists_month_expense(
    session: Session,
    account_id: int,
    source: str,
    year: int,
    month: int,
) -> bool:
    start, end = month_bounds(year, month)

    count = session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.type == "expense",
            Transaction.account_id == account_id,
            Transaction.source == source,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
    )

    return (count or 0) > 0


def get_category(session: Session, name: str, type: str) -> Category:
    category = category_repository.get_category_by_name(
        session=session,
        name=name,
        type=type,
    )

    if category is not None:
        return category

    return category_repository.create_category(
        session=session,
        name=name,
        type=type,
        is_section=True,
    )


def interest_day_of(account: Account) -> int:
    return account.interest_day or account.payment_day or 1


def advance_month(from_date: date, day: int) -> date:
    year = from_date.year
    month = from_date.month + 1

    if month > 12:
        month = 1
        year += 1

    day = min(day, calendar.monthrange(year, month)[1])

    return date(year, month, day)


def ensure_next_due(account: Account, today: date) -> None:
    if account.next_due_date is not None:
        return

    base = today

    if account.auto_start_date and account.auto_start_date > base:
        base = account.auto_start_date

    day = min(interest_day_of(account), calendar.monthrange(base.year, base.month)[1])
    candidate = date(base.year, base.month, day)

    if candidate < base:
        candidate = advance_month(candidate, interest_day_of(account))

    account.next_due_date = candidate


def process_deposit_interest(
    session: Session,
    account: Account,
    scheduled: date,
) -> int:
    if not account.annual_rate_bp:
        return 0

    if exists_month_income(
        session, account.id, "auto_interest", scheduled.year, scheduled.month
    ):
        return 0

    balance = get_native_balance(session, account.id)

    if balance <= 0:
        return 0

    interest = int(round(balance * account.annual_rate_bp / 10000 / 12))

    if interest <= 0:
        return 0

    category = get_category(session, "Проценты по вкладам", "income")

    transaction_service.create_transaction(
        session=session,
        type="income",
        account_id=account.id,
        category_id=category.id,
        occurred_at=scheduled,
        amount_minor=interest,
        note=f"Проценты по вкладу {account.name} за {scheduled.month:02d}.{scheduled.year}",
        source="auto_interest",
    )

    return 1


def process_loan_interest(
    session: Session,
    account: Account,
    scheduled: date,
) -> int:
    if not account.annual_rate_bp:
        return 0

    if exists_month_expense(
        session, account.id, "auto_loan_payment", scheduled.year, scheduled.month
    ):
        return 0

    debt = -get_native_balance(session, account.id)

    if debt <= 0:
        return 0

    interest = int(round(debt * account.annual_rate_bp / 10000 / 12))

    if interest <= 0:
        return 0

    category = get_category(session, "Проценты по кредитам", "expense")

    transaction_service.create_transaction(
        session=session,
        type="expense",
        account_id=account.id,
        category_id=category.id,
        occurred_at=scheduled,
        amount_minor=interest,
        note=f"Проценты по кредиту {account.name} за {scheduled.month:02d}.{scheduled.year}",
        source="auto_loan_payment",
    )

    return 1


def process_all(session: Session) -> int:
    today = date.today()

    accounts = session.scalars(
        select(Account).where(Account.is_active == True)
    ).all()

    created = 0

    for account in accounts:
        account_type = account.type or "card"

        if account_type not in DEPOSIT_TYPES and account_type not in LOAN_TYPES:
            continue

        if not account.annual_rate_bp:
            continue

        ensure_next_due(account, today)

        safety = 0

        while (
            account.next_due_date is not None
            and account.next_due_date <= today
            and safety < 60
        ):
            scheduled = account.next_due_date

            if account.auto_start_date and scheduled < account.auto_start_date:
                account.next_due_date = advance_month(
                    scheduled, interest_day_of(account)
                )
                safety += 1
                continue

            if account_type in DEPOSIT_TYPES:
                created += process_deposit_interest(session, account, scheduled)
            else:
                created += process_loan_interest(session, account, scheduled)

            account.next_due_date = advance_month(
                scheduled, interest_day_of(account)
            )
            safety += 1

    session.flush()

    return created