from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Category, IncomeProfile, Transaction


def get_income_profile_by_id(
    session: Session,
    profile_id: int,
) -> IncomeProfile | None:
    return session.get(IncomeProfile, profile_id)


def get_income_profiles_for_table(session: Session):
    statement = (
        select(
            IncomeProfile,
            Account.name.label("account_name"),
            Category.name.label("category_name"),
        )
        .join(Account, IncomeProfile.account_id == Account.id)
        .join(Category, IncomeProfile.income_category_id == Category.id)
        .order_by(IncomeProfile.name)
    )

    return list(session.execute(statement).all())


def create_income_profile(
    session: Session,
    **fields,
) -> IncomeProfile:
    profile = IncomeProfile(**fields)

    session.add(profile)
    session.flush()

    return profile


def update_income_profile(
    session: Session,
    profile: IncomeProfile,
    **fields,
) -> IncomeProfile:
    for field_name, field_value in fields.items():
        setattr(profile, field_name, field_value)

    session.flush()

    return profile


def delete_income_profile(
    session: Session,
    profile_id: int,
) -> None:
    profile = session.get(IncomeProfile, profile_id)

    if profile is None:
        return

    session.delete(profile)
    session.flush()


def is_profile_used(
    session: Session,
    profile_id: int,
) -> bool:
    statement = (
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.income_profile_id == profile_id)
    )

    result = session.scalar(statement)

    return (result or 0) > 0