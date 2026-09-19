from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, Setting, Transaction
from app.repositories import directory_repository, transaction_repository
from app.services import rate_service


def resolve_counterparty(
    session: Session,
    object_name: str | None,
) -> tuple[int | None, str | None]:
    if not object_name:
        return None, None

    item = directory_repository.get_or_create_directory_item(
        session=session,
        name=object_name,
        kind="other",
    )

    return item.id, item.name


def resolve_base_currency(
    session: Session,
    account: Account,
    amount_minor: int,
    occurred_at: date,
) -> tuple[str | None, Decimal | None, int | None]:
    base_currency_setting = session.get(Setting, "base_currency")

    base_currency = (
        base_currency_setting.value
        if base_currency_setting and base_currency_setting.value
        else account.currency
    )

    if base_currency == account.currency:
        return base_currency, Decimal("1"), amount_minor

    rate = rate_service.get_rate(
        session=session,
        from_currency=account.currency,
        to_currency=base_currency,
        on_date=occurred_at,
    )

    if rate is None:
        return base_currency, None, None

    base_amount_minor = int(round(amount_minor * rate))

    return base_currency, rate, base_amount_minor


def resolve_transfer_amount(
    session: Session,
    account: Account,
    transfer_to_account_id: int | None,
    amount_minor: int,
    occurred_at: date,
    transfer_to_amount_minor: int | None,
) -> int | None:
    if transfer_to_account_id is None:
        return None

    if transfer_to_amount_minor is not None:
        return transfer_to_amount_minor

    to_account = session.get(Account, transfer_to_account_id)

    if to_account is None:
        return None

    if to_account.currency == account.currency:
        return amount_minor

    transfer_rate = rate_service.get_rate(
        session=session,
        from_currency=account.currency,
        to_currency=to_account.currency,
        on_date=occurred_at,
    )

    if transfer_rate is None:
        return None

    return int(round(amount_minor * transfer_rate))


def sync_transaction_items(
    session: Session,
    transaction_id: int,
    items: list[dict] | None,
) -> None:
    transaction_repository.delete_transaction_items_by_transaction_id(
        session=session,
        transaction_id=transaction_id,
    )

    if not items:
        return

    for item in items:
        name = (item.get("name") or "").strip()

        if not name:
            continue

        directory_item = directory_repository.get_or_create_directory_item(
            session=session,
            name=name,
            kind="product",
        )

        quantity = item.get("quantity") or 1
        unit_price_minor = item.get("unit_price_minor")
        amount_minor = item.get("amount_minor")

        if amount_minor is None:
            amount_minor = (unit_price_minor or 0) * quantity

        transaction_repository.create_transaction_item(
            session=session,
            transaction_id=transaction_id,
            directory_item_id=directory_item.id,
            name_snapshot=directory_item.name,
            quantity=quantity,
            unit_price_minor=unit_price_minor,
            amount_minor=amount_minor,
        )


def create_transaction(
    session: Session,
    *,
    type: str,
    account_id: int,
    category_id: int,
    occurred_at: date,
    amount_minor: int,
    income_profile_id: int | None = None,
    object_name: str | None = None,
    items: list[dict] | None = None,
    note: str | None = None,
    gross_amount_minor: int | None = None,
    tax_amount_minor: int | None = None,
    tax_rate_bp: int | None = None,
    income_kind: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    transfer_to_account_id: int | None = None,
    transfer_to_amount_minor: int | None = None,
    source: str = "manual",
) -> Transaction:
    if amount_minor <= 0:
        raise ValueError("Сумма операции должна быть больше нуля")

    account = session.get(Account, account_id)

    if account is None:
        raise ValueError("Счет не найден")

    if type == "transfer":
        if category_id is None:
            from app.repositories import category_repository

            category_id = category_repository.get_or_create_transfer_category(
                session
            ).id

        transfer_to_amount_minor = resolve_transfer_amount(
            session=session,
            account=account,
            transfer_to_account_id=transfer_to_account_id,
            amount_minor=amount_minor,
            occurred_at=occurred_at,
            transfer_to_amount_minor=transfer_to_amount_minor,
        )

    if type != "income":
        income_profile_id = None
        gross_amount_minor = None
        tax_amount_minor = None
        tax_rate_bp = None
        income_kind = None
        period_start = None
        period_end = None

    counterparty_id, payee = resolve_counterparty(
        session=session,
        object_name=object_name,
    )

    base_currency, exchange_rate, base_amount_minor = resolve_base_currency(
        session=session,
        account=account,
        amount_minor=amount_minor,
        occurred_at=occurred_at,
    )

    transaction = transaction_repository.create_transaction(
        session=session,
        account_id=account_id,
        category_id=category_id,
        income_profile_id=income_profile_id,
        type=type,
        currency=account.currency,
        amount_minor=amount_minor,
        occurred_at=occurred_at,
        counterparty_id=counterparty_id,
        payee=payee,
        note=note,
        gross_amount_minor=gross_amount_minor,
        tax_amount_minor=tax_amount_minor,
        tax_rate_bp=tax_rate_bp,
        income_kind=income_kind,
        period_start=period_start,
        period_end=period_end,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        base_amount_minor=base_amount_minor,
        transfer_to_account_id=transfer_to_account_id,
        transfer_to_amount_minor=transfer_to_amount_minor,
        source=source,
    )

    if type == "expense":
        sync_transaction_items(
            session=session,
            transaction_id=transaction.id,
            items=items,
        )

    return transaction


def update_transaction(
    session: Session,
    *,
    transaction_id: int,
    type: str,
    account_id: int,
    category_id: int,
    occurred_at: date,
    amount_minor: int,
    object_name: str | None = None,
    items: list[dict] | None = None,
    note: str | None = None,
    gross_amount_minor: int | None = None,
    tax_amount_minor: int | None = None,
    tax_rate_bp: int | None = None,
    income_kind: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    transfer_to_account_id: int | None = None,
    transfer_to_amount_minor: int | None = None,
) -> Transaction:
    transaction = transaction_repository.get_transaction_by_id(
        session=session,
        transaction_id=transaction_id,
    )

    if transaction is None:
        raise ValueError("Операция не найдена")

    if amount_minor <= 0:
        raise ValueError("Сумма операции должна быть больше нуля")

    account = session.get(Account, account_id)

    if account is None:
        raise ValueError("Счет не найден")

    if type == "transfer":
        if category_id is None:
            from app.repositories import category_repository

            category_id = category_repository.get_or_create_transfer_category(
                session
            ).id

        transfer_to_amount_minor = resolve_transfer_amount(
            session=session,
            account=account,
            transfer_to_account_id=transfer_to_account_id,
            amount_minor=amount_minor,
            occurred_at=occurred_at,
            transfer_to_amount_minor=transfer_to_amount_minor,
        )

    if type != "income":
        gross_amount_minor = None
        tax_amount_minor = None
        tax_rate_bp = None
        income_kind = None
        period_start = None
        period_end = None

    counterparty_id, payee = resolve_counterparty(
        session=session,
        object_name=object_name,
    )

    base_currency, exchange_rate, base_amount_minor = resolve_base_currency(
        session=session,
        account=account,
        amount_minor=amount_minor,
        occurred_at=occurred_at,
    )

    transaction = transaction_repository.update_transaction(
        session,
        transaction,
        account_id=account_id,
        category_id=category_id,
        type=type,
        currency=account.currency,
        amount_minor=amount_minor,
        occurred_at=occurred_at,
        counterparty_id=counterparty_id,
        payee=payee,
        note=note,
        gross_amount_minor=gross_amount_minor,
        tax_amount_minor=tax_amount_minor,
        tax_rate_bp=tax_rate_bp,
        income_kind=income_kind,
        period_start=period_start,
        period_end=period_end,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        base_amount_minor=base_amount_minor,
        transfer_to_account_id=transfer_to_account_id,
        transfer_to_amount_minor=transfer_to_amount_minor,
    )

    if type == "expense":
        sync_transaction_items(
            session=session,
            transaction_id=transaction.id,
            items=items,
        )
    else:
        sync_transaction_items(
            session=session,
            transaction_id=transaction.id,
            items=None,
        )

    return transaction


def recalculate_all_base_amounts(session: Session) -> int:
    from sqlalchemy import select as sa_select

    base_currency_setting = session.get(Setting, "base_currency")

    base_currency = (
        base_currency_setting.value
        if base_currency_setting and base_currency_setting.value
        else "RUB"
    )

    transactions = session.scalars(sa_select(Transaction)).all()

    updated_count = 0

    for transaction in transactions:
        if transaction.currency == base_currency:
            transaction.base_currency = base_currency
            transaction.exchange_rate = Decimal("1")
            transaction.base_amount_minor = transaction.amount_minor
        else:
            rate = rate_service.get_rate(
                session=session,
                from_currency=transaction.currency,
                to_currency=base_currency,
                on_date=transaction.occurred_at,
            )

            transaction.base_currency = base_currency
            transaction.exchange_rate = rate

            if rate is not None:
                transaction.base_amount_minor = int(
                    round(transaction.amount_minor * rate)
                )
            else:
                transaction.base_amount_minor = None

        updated_count += 1

    session.flush()

    return updated_count