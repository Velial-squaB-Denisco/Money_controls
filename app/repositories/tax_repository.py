from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaxRule


def get_tax_rule_by_name(session: Session, name: str) -> TaxRule | None:
    statement = (
        select(TaxRule)
        .where(TaxRule.name == name)
        .limit(1)
    )

    return session.scalar(statement)


def create_tax_rule(
    session: Session,
    name: str,
    fixed_rate_bp: int,
    type: str = "fixed",
    currency: str = "RUB",
    description: str | None = None,
) -> TaxRule:
    tax_rule = TaxRule(
        name=name,
        type=type,
        fixed_rate_bp=fixed_rate_bp,
        currency=currency,
        description=description,
        is_active=True,
    )

    session.add(tax_rule)
    session.flush()

    return tax_rule


def get_or_create_tax_rule(
    session: Session,
    name: str,
    fixed_rate_bp: int,
    type: str = "fixed",
    currency: str = "RUB",
    description: str | None = None,
) -> TaxRule:
    tax_rule = get_tax_rule_by_name(session=session, name=name)

    if tax_rule:
        return tax_rule

    return create_tax_rule(
        session=session,
        name=name,
        fixed_rate_bp=fixed_rate_bp,
        type=type,
        currency=currency,
        description=description,
    )