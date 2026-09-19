from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, RecurringRule


def get_recurring_rule_by_id(
    session: Session,
    rule_id: int,
) -> RecurringRule | None:
    return session.get(RecurringRule, rule_id)


def get_recurring_rules_for_table(session: Session):
    statement = (
        select(
            RecurringRule,
            Account.name.label("account_name"),
            Category.name.label("category_name"),
        )
        .join(Account, RecurringRule.account_id == Account.id)
        .join(Category, RecurringRule.category_id == Category.id)
        .order_by(RecurringRule.name)
    )

    return list(session.execute(statement).all())


def create_recurring_rule(
    session: Session,
    **fields,
) -> RecurringRule:
    rule = RecurringRule(**fields)

    session.add(rule)
    session.flush()

    return rule


def update_recurring_rule(
    session: Session,
    rule: RecurringRule,
    **fields,
) -> RecurringRule:
    for field_name, field_value in fields.items():
        setattr(rule, field_name, field_value)

    session.flush()

    return rule


def delete_recurring_rule(
    session: Session,
    rule_id: int,
) -> None:
    rule = session.get(RecurringRule, rule_id)

    if rule is None:
        return

    session.delete(rule)
    session.flush()


def get_due_rules(session: Session, today: date):
    statement = (
        select(RecurringRule)
        .where(RecurringRule.is_active == True)
        .where(RecurringRule.next_due_date.is_not(None))
        .where(RecurringRule.next_due_date <= today)
    )

    return list(session.scalars(statement).all())