from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Account


def get_default_account(session: Session) -> Account | None:
    statement = (
        select(Account)
        .where(Account.is_default == True)
        .limit(1)
    )

    return session.scalar(statement)


def get_account_by_name(session: Session, name: str) -> Account | None:
    statement = (
        select(Account)
        .where(Account.name == name)
        .limit(1)
    )

    return session.scalar(statement)


def create_account(
    session: Session,
    name: str,
    currency: str = "RUB",
    initial_balance_minor: int = 0,
    is_default: bool = False,
) -> Account:
    if is_default:
        session.execute(
            update(Account).values(is_default=False)
        )

    account = Account(
        name=name,
        currency=currency,
        initial_balance_minor=initial_balance_minor,
        is_default=is_default,
        is_active=True,
    )

    session.add(account)
    session.flush()

    return account


def get_or_create_account(
    session: Session,
    name: str,
    currency: str = "RUB",
    initial_balance_minor: int = 0,
    is_default: bool = False,
) -> Account:
    account = get_account_by_name(session=session, name=name)

    if account:
        return account

    return create_account(
        session=session,
        name=name,
        currency=currency,
        initial_balance_minor=initial_balance_minor,
        is_default=is_default,
    )
    
def get_all_accounts(session: Session) -> list[Account]:
    statement = (
        select(Account)
        .where(Account.is_active == True)
        .order_by(Account.name)
    )

    return list(session.scalars(statement).all())

def update_account(
    session: Session,
    account: Account,
    **fields,
) -> Account:
    for field_name, field_value in fields.items():
        setattr(account, field_name, field_value)

    session.flush()

    return account


def delete_account(
    session: Session,
    account_id: int,
) -> None:
    account = session.get(Account, account_id)

    if account is None:
        return

    session.delete(account)
    session.flush()


def is_account_used(
    session: Session,
    account_id: int,
) -> bool:
    from sqlalchemy import func as sa_func

    from app.models import Transaction

    statement = (
        select(sa_func.count())
        .select_from(Transaction)
        .where(Transaction.account_id == account_id)
    )

    result = session.scalar(statement)

    return (result or 0) > 0