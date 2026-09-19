from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category


def get_category_by_name(
    session: Session,
    name: str,
    type: str,
    parent_id: int | None = None,
) -> Category | None:
    statement = (
        select(Category)
        .where(Category.name == name)
        .where(Category.type == type)
    )

    if parent_id is None:
        statement = statement.where(Category.parent_id.is_(None))
    else:
        statement = statement.where(Category.parent_id == parent_id)

    statement = statement.limit(1)

    return session.scalar(statement)


def create_category(
    session: Session,
    name: str,
    type: str,
    parent_id: int | None = None,
    is_section: bool = False,
    color: str | None = None,
    icon: str | None = None,
    sort_order: int = 0,
) -> Category:
    category = Category(
        name=name,
        type=type,
        parent_id=parent_id,
        is_section=is_section,
        color=color,
        icon=icon,
        sort_order=sort_order,
        is_archived=False,
    )

    session.add(category)
    session.flush()

    return category


def get_or_create_category(
    session: Session,
    name: str,
    type: str,
    parent_id: int | None = None,
    is_section: bool = False,
    color: str | None = None,
    icon: str | None = None,
    sort_order: int = 0,
) -> Category:
    category = get_category_by_name(
        session=session,
        name=name,
        type=type,
        parent_id=parent_id,
    )

    if category:
        return category

    return create_category(
        session=session,
        name=name,
        type=type,
        parent_id=parent_id,
        is_section=is_section,
        color=color,
        icon=icon,
        sort_order=sort_order,
    )

def get_all_categories(session: Session) -> list[Category]:
    statement = (
        select(Category)
        .order_by(Category.type, Category.sort_order, Category.name)
    )

    return list(session.scalars(statement).all())

def get_categories_by_type(session: Session, type: str) -> list[Category]:
    statement = (
        select(Category)
        .where(Category.type == type)
        .order_by(Category.sort_order, Category.name)
    )

    return list(session.scalars(statement).all())


def update_category(
    session: Session,
    category: Category,
    **fields,
) -> Category:
    for field_name, field_value in fields.items():
        setattr(category, field_name, field_value)

    session.flush()

    return category


def delete_category(
    session: Session,
    category_id: int,
) -> None:
    category = session.get(Category, category_id)

    if category is None:
        return

    session.delete(category)
    session.flush()


def is_category_used(
    session: Session,
    category_id: int,
) -> bool:
    from sqlalchemy import func as sa_func

    from app.models import Budget, IncomeProfile, RecurringRule, Transaction

    checks = [
        (Transaction, Transaction.category_id),
        (Budget, Budget.category_id),
        (RecurringRule, RecurringRule.category_id),
        (IncomeProfile, IncomeProfile.income_category_id),
    ]

    for model, column in checks:
        count = session.scalar(
            select(sa_func.count()).select_from(model).where(column == category_id)
        )

        if count:
            return True

    return False

def get_or_create_transfer_category(session: Session) -> Category:
    statement = select(Category).where(Category.type == "transfer").limit(1)

    category = session.scalar(statement)

    if category is not None:
        return category

    category = Category(
        name="Переводы между счетами",
        type="transfer",
        is_section=True,
    )

    session.add(category)
    session.flush()

    return category