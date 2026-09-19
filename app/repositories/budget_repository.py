from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, Category


def get_budget_by_id(
    session: Session,
    budget_id: int,
) -> Budget | None:
    return session.get(Budget, budget_id)


def get_budgets_for_table(session: Session):
    statement = (
        select(
            Budget,
            Category.name.label("category_name"),
        )
        .join(Category, Budget.category_id == Category.id)
        .order_by(Category.name)
    )

    return list(session.execute(statement).all())


def get_budget_by_category(
    session: Session,
    category_id: int,
    period_type: str = "monthly",
    exclude_budget_id: int | None = None,
) -> Budget | None:
    statement = (
        select(Budget)
        .where(Budget.category_id == category_id)
        .where(Budget.period_type == period_type)
    )

    if exclude_budget_id is not None:
        statement = statement.where(Budget.id != exclude_budget_id)

    statement = statement.limit(1)

    return session.scalar(statement)


def create_budget(
    session: Session,
    **fields,
) -> Budget:
    budget = Budget(**fields)

    session.add(budget)
    session.flush()

    return budget


def update_budget(
    session: Session,
    budget: Budget,
    **fields,
) -> Budget:
    for field_name, field_value in fields.items():
        setattr(budget, field_name, field_value)

    session.flush()

    return budget


def delete_budget(
    session: Session,
    budget_id: int,
) -> None:
    budget = session.get(Budget, budget_id)

    if budget is None:
        return

    session.delete(budget)
    session.flush()