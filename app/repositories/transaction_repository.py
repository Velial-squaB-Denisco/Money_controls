from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    Category,
    DirectoryItem,
    Transaction,
    TransactionItem,
)


def create_transaction(
    session: Session,
    *,
    account_id: int,
    category_id: int,
    income_profile_id: int | None = None,
    type: str,
    currency: str,
    amount_minor: int,
    occurred_at: date,
    counterparty_id: int | None = None,
    payee: str | None = None,
    note: str | None = None,
    gross_amount_minor: int | None = None,
    tax_amount_minor: int | None = None,
    tax_rate_bp: int | None = None,
    income_kind: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    base_currency: str | None = None,
    exchange_rate: Decimal | None = None,
    base_amount_minor: int | None = None,
    source: str = "manual",
    status: str = "posted",
    transfer_to_account_id: int | None = None,
    transfer_to_amount_minor: int | None = None,
    
) -> Transaction:
    transaction = Transaction(
        account_id=account_id,
        category_id=category_id,
        income_profile_id=income_profile_id,
        type=type,
        currency=currency,
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
        source=source,
        status=status,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        base_amount_minor=base_amount_minor,
        transfer_to_account_id=transfer_to_account_id,
        transfer_to_amount_minor=transfer_to_amount_minor,
    )

    session.add(transaction)
    session.flush()

    return transaction


def create_transaction_item(
    session: Session,
    *,
    transaction_id: int,
    directory_item_id: int | None = None,
    name_snapshot: str,
    amount_minor: int | None = None,
    quantity: int = 1,
    unit_price_minor: int | None = None,
    note: str | None = None,
) -> TransactionItem:
    transaction_item = TransactionItem(
        transaction_id=transaction_id,
        directory_item_id=directory_item_id,
        name_snapshot=name_snapshot,
        amount_minor=amount_minor,
        quantity=quantity,
        unit_price_minor=unit_price_minor,
        note=note,
    )

    session.add(transaction_item)
    session.flush()

    return transaction_item


def get_transactions_for_table(session: Session):
    from sqlalchemy.orm import aliased

    AccountTo = aliased(Account)

    statement = (
        select(
            Transaction,
            Category.name.label("category_name"),
            Account.name.label("account_name"),
            AccountTo.name.label("to_account_name"),
            DirectoryItem.name.label("directory_item_name"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(
            AccountTo,
            Transaction.transfer_to_account_id == AccountTo.id,
        )
        .outerjoin(
            DirectoryItem,
            Transaction.counterparty_id == DirectoryItem.id,
        )
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
    )

    return list(session.execute(statement).all())


def get_transaction_items_map(
    session: Session,
    transaction_ids: list[int],
) -> dict[int, list[str]]:
    if not transaction_ids:
        return {}

    statement = (
        select(
            TransactionItem.transaction_id,
            DirectoryItem.name.label("directory_item_name"),
            TransactionItem.name_snapshot,
            TransactionItem.quantity,
        )
        .outerjoin(
            DirectoryItem,
            TransactionItem.directory_item_id == DirectoryItem.id,
        )
        .where(TransactionItem.transaction_id.in_(transaction_ids))
        .order_by(TransactionItem.id)
    )

    result: dict[int, list[str]] = {}

    for row in session.execute(statement):
        names = result.setdefault(row.transaction_id, [])

        name = row.directory_item_name or row.name_snapshot
        quantity = row.quantity or 1

        if quantity and quantity > 1:
            label = f"{quantity} × {name}"
        else:
            label = name

        names.append(label)

    return result


def get_transaction_by_id(
    session: Session,
    transaction_id: int,
) -> Transaction | None:
    return session.get(Transaction, transaction_id)


def update_transaction(
    session: Session,
    transaction: Transaction,
    **fields,
) -> Transaction:
    for field_name, field_value in fields.items():
        setattr(transaction, field_name, field_value)

    session.flush()

    return transaction


def delete_transaction_items_by_transaction_id(
    session: Session,
    transaction_id: int,
) -> None:
    statement = (
        select(TransactionItem)
        .where(TransactionItem.transaction_id == transaction_id)
    )

    for transaction_item in session.scalars(statement):
        session.delete(transaction_item)

    session.flush()


def delete_transaction(
    session: Session,
    transaction_id: int,
) -> None:
    transaction = session.get(Transaction, transaction_id)

    if transaction is None:
        return

    delete_transaction_items_by_transaction_id(
        session=session,
        transaction_id=transaction_id,
    )

    session.delete(transaction)
    session.flush()

    
def get_transaction_items_detail(
    session: Session,
    transaction_id: int,
):
    statement = (
        select(TransactionItem)
        .where(TransactionItem.transaction_id == transaction_id)
        .order_by(TransactionItem.id)
    )

    return list(session.scalars(statement).all())