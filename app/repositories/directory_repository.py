from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.normalize import normalize_directory_name
from app.models import DirectoryItem, DirectoryItemAlias, TransactionItem


def get_directory_item_by_normalized_name(
    session: Session,
    normalized_name: str,
) -> DirectoryItem | None:
    statement = (
        select(DirectoryItem)
        .where(DirectoryItem.normalized_name == normalized_name)
        .limit(1)
    )

    item = session.scalar(statement)

    if item:
        return item

    statement = (
        select(DirectoryItem)
        .join(
            DirectoryItemAlias,
            DirectoryItem.id == DirectoryItemAlias.directory_item_id,
        )
        .where(DirectoryItemAlias.normalized_name == normalized_name)
        .limit(1)
    )

    return session.scalar(statement)


def create_directory_item(
    session: Session,
    name: str,
    kind: str = "other",
    default_category_id: int | None = None,
    note: str | None = None,
) -> DirectoryItem:
    normalized_name = normalize_directory_name(name)

    if not normalized_name:
        raise ValueError("Directory item name cannot be empty")

    item = DirectoryItem(
        name=name.strip(),
        normalized_name=normalized_name,
        kind=kind,
        default_category_id=default_category_id,
        note=note,
        is_archived=False,
    )

    session.add(item)
    session.flush()

    return item


def get_or_create_directory_item(
    session: Session,
    name: str,
    kind: str = "other",
    default_category_id: int | None = None,
    note: str | None = None,
) -> DirectoryItem:
    normalized_name = normalize_directory_name(name)

    if not normalized_name:
        raise ValueError("Directory item name cannot be empty")

    item = get_directory_item_by_normalized_name(
        session=session,
        normalized_name=normalized_name,
    )

    if item:
        return item

    return create_directory_item(
        session=session,
        name=name,
        kind=kind,
        default_category_id=default_category_id,
        note=note,
    )

def get_all_directory_items(session: Session) -> list[DirectoryItem]:
    statement = (
        select(DirectoryItem)
        .order_by(DirectoryItem.name)
    )

    return list(session.scalars(statement).all())


def update_directory_item(
    session: Session,
    item: DirectoryItem,
    **fields,
) -> DirectoryItem:
    for field_name, field_value in fields.items():
        setattr(item, field_name, field_value)

    session.flush()

    return item


def delete_directory_item(
    session: Session,
    item_id: int,
) -> None:
    item = session.get(DirectoryItem, item_id)

    if item is None:
        return

    session.delete(item)
    session.flush()


def is_directory_item_used(
    session: Session,
    item_id: int,
) -> bool:
    from sqlalchemy import func as sa_func

    from app.models import Transaction, TransactionItem

    transactions_count = session.scalar(
        select(sa_func.count())
        .select_from(Transaction)
        .where(Transaction.counterparty_id == item_id)
    )

    if transactions_count:
        return True

    items_count = session.scalar(
        select(sa_func.count())
        .select_from(TransactionItem)
        .where(TransactionItem.directory_item_id == item_id)
    )

    return (items_count or 0) > 0


def get_last_price_minor(
    session: Session,
    name: str,
) -> int | None:
    normalized_name = normalize_directory_name(name)

    item = get_directory_item_by_normalized_name(
        session=session,
        normalized_name=normalized_name,
    )

    if item is None:
        return None

    statement = (
        select(TransactionItem.unit_price_minor)
        .where(TransactionItem.directory_item_id == item.id)
        .where(TransactionItem.unit_price_minor.is_not(None))
        .order_by(TransactionItem.id.desc())
        .limit(1)
    )

    return session.scalar(statement)