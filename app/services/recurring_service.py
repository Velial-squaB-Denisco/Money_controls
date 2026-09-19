from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import schedule
from app.models import Account, Setting
from app.repositories import (
    category_repository,
    recurring_repository,
    transaction_repository,
)
from app.services import rate_service


def resolve_transfer_amount(
    session: Session,
    from_account: Account,
    to_account: Account,
    amount_minor: int,
    on_date: date,
) -> int | None:
    if to_account.currency == from_account.currency:
        return amount_minor

    rate = rate_service.get_rate(
        session=session,
        from_currency=from_account.currency,
        to_currency=to_account.currency,
        on_date=on_date,
    )

    if rate is None:
        return None

    return int(round(amount_minor * rate))


def generate_due_transactions(
    session: Session,
    today: date | None = None,
) -> int:
    if today is None:
        today = date.today()

    rules = recurring_repository.get_due_rules(session=session, today=today)

    created_count = 0

    for rule in rules:
        safety_counter = 0

        while rule.next_due_date is not None and rule.next_due_date <= today:
            if safety_counter >= 100:
                break

            if rule.end_date is not None and rule.next_due_date > rule.end_date:
                rule.next_due_date = None
                break

            if rule.amount_minor is None or rule.amount_minor <= 0:
                next_due_date = schedule.get_next_occurrence_after(
                    rrule_text=rule.rrule,
                    start_date=rule.start_date,
                    after_date=rule.next_due_date,
                )

                rule.next_due_date = next_due_date
                safety_counter += 1
                continue

            account = session.get(Account, rule.account_id)

            if account is None:
                break

            base_currency_setting = session.get(Setting, "base_currency")

            base_currency = (
                base_currency_setting.value
                if base_currency_setting and base_currency_setting.value
                else account.currency
            )

            if base_currency == account.currency:
                exchange_rate = Decimal("1")
                base_amount_minor = rule.amount_minor
            else:
                exchange_rate = None
                base_amount_minor = None

            status = "draft" if rule.create_as_draft else "posted"

            if rule.type == "transfer":
                to_account = session.get(Account, rule.transfer_to_account_id)

                if to_account is None:
                    break

                category_id = rule.category_id

                if category_id is None:
                    category_id = category_repository.get_or_create_transfer_category(
                        session
                    ).id

                transfer_to_amount_minor = resolve_transfer_amount(
                    session=session,
                    from_account=account,
                    to_account=to_account,
                    amount_minor=rule.amount_minor,
                    on_date=rule.next_due_date,
                )

                transaction_repository.create_transaction(
                    session=session,
                    account_id=rule.account_id,
                    category_id=category_id,
                    type="transfer",
                    currency=account.currency,
                    amount_minor=rule.amount_minor,
                    occurred_at=rule.next_due_date,
                    note=rule.name,
                    source="recurring",
                    status=status,
                    base_currency=base_currency,
                    exchange_rate=exchange_rate,
                    base_amount_minor=base_amount_minor,
                    transfer_to_account_id=rule.transfer_to_account_id,
                    transfer_to_amount_minor=transfer_to_amount_minor,
                )
            else:
                transaction_repository.create_transaction(
                    session=session,
                    account_id=rule.account_id,
                    category_id=rule.category_id,
                    type=rule.type,
                    currency=account.currency,
                    amount_minor=rule.amount_minor,
                    occurred_at=rule.next_due_date,
                    note=rule.name,
                    source="recurring",
                    status=status,
                    base_currency=base_currency,
                    exchange_rate=exchange_rate,
                    base_amount_minor=base_amount_minor,
                )

            created_count += 1

            next_due_date = schedule.get_next_occurrence_after(
                rrule_text=rule.rrule,
                start_date=rule.start_date,
                after_date=rule.next_due_date,
            )

            if rule.end_date is not None and next_due_date is not None:
                if next_due_date > rule.end_date:
                    next_due_date = None

            rule.next_due_date = next_due_date
            safety_counter += 1

        rule.last_generated_at = datetime.now()

    return created_count