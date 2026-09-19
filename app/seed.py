from sqlalchemy.orm import Session

from app.core.normalize import normalize_directory_name
from app.db import SessionLocal
from app.models import Setting
from app.repositories import (
    account_repository,
    category_repository,
    directory_repository,
    tax_repository,
)


def get_or_create_setting(session: Session, key: str, value: str) -> Setting:
    setting = session.get(Setting, key)

    if setting:
        setting.value = value
        return setting

    setting = Setting(key=key, value=value)
    session.add(setting)
    session.flush()

    return setting


def seed_settings(session: Session) -> None:
    get_or_create_setting(session=session, key="base_currency", value="RUB")
    get_or_create_setting(session=session, key="app_initialized", value="true")


def seed_accounts(session: Session) -> None:
    account_repository.get_or_create_account(
        session=session,
        name="Основной",
        currency="RUB",
        initial_balance_minor=0,
        is_default=True,
    )


def seed_income_categories(session: Session) -> None:
    salary = category_repository.get_or_create_category(
        session=session,
        name="Зарплата",
        type="income",
        parent_id=None,
        is_section=True,
    )

    income_children = [
        "Аванс",
        "Основная часть",
        "Премия",
        "Годовая премия",
    ]

    for name in income_children:
        category_repository.get_or_create_category(
            session=session,
            name=name,
            type="income",
            parent_id=salary.id,
            is_section=False,
        )

    category_repository.get_or_create_category(
        session=session,
        name="Фриланс",
        type="income",
        parent_id=None,
        is_section=True,
    )

    category_repository.get_or_create_category(
        session=session,
        name="Прочие доходы",
        type="income",
        parent_id=None,
        is_section=True,
    )


def seed_expense_categories(session: Session) -> None:
    expense_sections: dict[str, list[str]] = {
        "ЖКХ и дом": [
            "Вода",
            "Электричество",
            "Газ",
            "Отопление",
            "Интернет",
            "Вывоз мусора",
            "Обслуживание дома",
        ],
        "Транспорт": [
            "Общественный транспорт",
            "Такси",
            "Бензин",
            "Парковка",
            "Обслуживание авто",
        ],
        "Продукты": [
            "Супермаркеты",
            "Рынок",
            "Доставка продуктов",
        ],
        "Здоровье": [
            "Аптека",
            "Врачи",
            "Спорт",
        ],
        "Развлечения": [
            "Кафе и рестораны",
            "Кино",
            "Игры",
        ],
        "Связь": [
            "Мобильная связь",
            "Прочая связь",
        ],
        "Подписки": [],
        "Одежда": [],
        "Прочие расходы": [],
    }

    for section_name, children in expense_sections.items():
        section = category_repository.get_or_create_category(
            session=session,
            name=section_name,
            type="expense",
            parent_id=None,
            is_section=True,
        )

        for child_name in children:
            category_repository.get_or_create_category(
                session=session,
                name=child_name,
                type="expense",
                parent_id=section.id,
                is_section=False,
            )


def seed_categories(session: Session) -> None:
    seed_income_categories(session=session)
    seed_expense_categories(session=session)


def seed_tax_rules(session: Session) -> None:
    tax_rules = [
        {
            "name": "Без налога",
            "fixed_rate_bp": 0,
            "description": "Доход без налога",
        },
        {
            "name": "НДФЛ 13%",
            "fixed_rate_bp": 1300,
            "description": "Фиксированная ставка НДФЛ 13%",
        },
        {
            "name": "НДФЛ 15%",
            "fixed_rate_bp": 1500,
            "description": "Фиксированная ставка НДФЛ 15%",
        },
        {
            "name": "Самозанятость 4%",
            "fixed_rate_bp": 400,
            "description": "Налог на профессиональный доход 4%",
        },
        {
            "name": "Самозанятость 6%",
            "fixed_rate_bp": 600,
            "description": "Налог на профессиональный доход 6%",
        },
    ]

    for rule in tax_rules:
        tax_repository.get_or_create_tax_rule(
            session=session,
            name=rule["name"],
            fixed_rate_bp=rule["fixed_rate_bp"],
            type="fixed",
            currency="RUB",
            description=rule["description"],
        )


def seed_directory_items(session: Session) -> None:
    items = [
        {
            "name": "Пятерочка",
            "kind": "merchant",
            "note": "Магазин продуктов",
        },
        {
            "name": "Магнит",
            "kind": "merchant",
            "note": "Магазин продуктов",
        },
        {
            "name": "Кофе",
            "kind": "product",
            "note": "Кофе или напитки",
        },
        {
            "name": "Обед",
            "kind": "product",
            "note": "Обед / готовая еда",
        },
    ]

    for item in items:
        directory_repository.get_or_create_directory_item(
            session=session,
            name=item["name"],
            kind=item["kind"],
            note=item["note"],
        )


def seed_initial_data() -> None:
    with SessionLocal() as session:
        seed_settings(session=session)
        seed_accounts(session=session)
        seed_categories(session=session)
        category_repository.get_or_create_transfer_category(session)
        category_repository.get_or_create_category(
            session=session,
            name="Проценты по вкладам",
            type="income",
            is_section=True,
        )

        category_repository.get_or_create_category(
            session=session,
            name="Проценты по кредитам",
            type="expense",
            is_section=True,
        )
        seed_tax_rules(session=session)
        seed_directory_items(session=session)

        session.commit()
