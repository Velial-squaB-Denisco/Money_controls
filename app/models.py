from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    
    # cash / card / deposit / savings / loan / credit_card
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="card")
    
    # Годовая ставка в базисных пунктах: 12% = 1200
    annual_rate_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Ежемесячное пополнение (вклад) или платеж (кредит)
    monthly_payment_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # День месяца для пополнения/платежа
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Счет, с которого идет пополнение или платеж
    payment_from_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=True,
    )

    # День месяца, когда начисляются проценты
    interest_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Не создавать автооперации раньше этой даты
    auto_start_date: Mapped[date | None] = mapped_column(nullable=True)

    # Следующая запланированная дата списания/пополнения
    next_due_date: Mapped[date | None] = mapped_column(nullable=True)

    # RUB / USD
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")

    # Начальный баланс в копейках/центах.
    initial_balance_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # income / expense
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"),
        nullable=True,
    )

    # Если True, это раздел, например "ЖКХ и дом".
    is_section: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DirectoryItem(Base):
    __tablename__ = "directory_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Название объекта, например:
    # Пятерочка, Кофе, Молоко, Спортзал, Интернет
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Нормализованное название для поиска дублей.
    # Например: "пятерочка"
    normalized_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
    )

    # Тип объекта:
    # product / merchant / service / subscription / other
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="other")

    # Категория по умолчанию, чтобы при выборе объекта
    # можно было автоматически подставлять категорию.
    default_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DirectoryItemAlias(Base):
    __tablename__ = "directory_item_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)

    directory_item_id: Mapped[int] = mapped_column(
        ForeignKey("directory_items.id"),
        nullable=False,
    )

    # Алиас объекта.
    # Например:
    # Основной объект: Пятерочка
    # Алиас: Пятёрочка
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    normalized_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TaxRule(Base):
    __tablename__ = "tax_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Например:
    # fixed / progressive
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")

    # Фиксированная ставка в базисных пунктах.
    # 13% = 1300
    fixed_rate_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TaxBracket(Base):
    __tablename__ = "tax_brackets"

    id: Mapped[int] = mapped_column(primary_key=True)

    tax_rule_id: Mapped[int] = mapped_column(
        ForeignKey("tax_rules.id"),
        nullable=False,
    )

    # Нижняя граница годового дохода в копейках.
    min_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Верхняя граница.
    # Если NULL, значит "и выше".
    max_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Ставка в базисных пунктах.
    # 13% = 1300
    rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IncomeProfile(Base):
    __tablename__ = "income_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # salary / freelance / business / investment / other
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="salary")

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
    )

    income_category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")

    # none / fixed / rule
    tax_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")

    # Если tax_mode = fixed.
    fixed_tax_rate_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Если tax_mode = rule.
    tax_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_rules.id"),
        nullable=True,
    )

    # Базовый оклад до налога в копейках.
    base_gross_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Надбавки до налога.
    allowances_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Аванс в процентах от месячного дохода.
    # 50% = 5000
    advance_percent_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Или фиксированный аванс.
    advance_fixed_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Годовая премия до налога.
    annual_bonus_gross_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
    )

    # Ссылка на объект из справочника.
    # Например: Пятерочка, Кофе, Спортзал.
    counterparty_id: Mapped[int | None] = mapped_column(
        ForeignKey("directory_items.id"),
        nullable=True,
    )

    income_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("income_profiles.id"),
        nullable=True,
    )
    
    transfer_to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=True,
    )

    transfer_to_amount_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # income / expense
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Валюта операции, обычно совпадает с валютой счета.
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Для дохода: сумма, которая реально пришла на счет.
    # Для расхода: сумма списания.
    # Храним в копейках/центах.
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    # Для дохода: сумма до налога.
    gross_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Для дохода: удержанный налог.
    tax_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Ставка налога в базисных пунктах.
    # 13% = 1300
    tax_rate_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Тип дохода:
    # salary_advance / salary_final / salary_bonus / freelance / other
    income_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Дата фактического поступления или списания.
    occurred_at: Mapped[date] = mapped_column(nullable=False)

    # Период, за который доход начислен.
    # Например, зарплата за сентябрь пришла 5 октября.
    period_start: Mapped[date | None] = mapped_column(nullable=True)
    period_end: Mapped[date | None] = mapped_column(nullable=True)

    # Получатель/место покупки в свободной форме.
    # Если выбран объект из справочника, сюда можно подставлять его имя.
    payee: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Комментарий, например "на что именно потрачены деньги".
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # manual / recurring / imported
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # posted / draft / pending
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")

    # Для импорта банковских выписок.
    import_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Конвертация в основную валюту.
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )
    base_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class IncomeComponent(Base):
    __tablename__ = "income_components"

    id: Mapped[int] = mapped_column(primary_key=True)

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # base / allowance / bonus / tax / deduction / other
    kind: Mapped[str] = mapped_column(String(30), nullable=False)

    # Сумма в копейках/центах.
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    # Если True, компонент вычитается: налог, удержание.
    is_deduction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tax_rate_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Например, USD -> RUB.
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    rate_date: Mapped[date] = mapped_column(nullable=False)

    # Курс.
    # Например, 1 USD = 92.5 RUB.
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # cbr / manual / cached
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "from_currency",
            "to_currency",
            "rate_date",
            name="uq_exchange_rate_currency_date",
        ),
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
    )

    # monthly / weekly / yearly
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")

    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RecurringRule(Base):
    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # income / expense
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
    )
    
    transfer_to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=True,
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")

    # Для фиксированных платежей сумма обязательна.
    # Для переменных платежей, например ЖКХ, может быть примерной.
    amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Например:
    # FREQ=MONTHLY;BYMONTHDAY=5
    rrule: Mapped[str] = mapped_column(String(200), nullable=False)

    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    next_due_date: Mapped[date | None] = mapped_column(nullable=True)
    last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Если True, сумма фиксированная.
    # Если False, сумму желательно уточнять вручную.
    is_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Если True, создавать операцию как черновик для подтверждения.
    create_as_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        nullable=False,
    )

    directory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("directory_items.id"),
        nullable=True,
    )

    # Название товара на момент создания операции.
    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)

    # Позже сюда можно будет добавлять цену/сумму позиции.
    amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
class LLMInsight(Base):
    __tablename__ = "llm_insights"

    id: Mapped[int] = mapped_column(primary_key=True)

    # month_analysis / anomaly / budget_recommendations
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Например: 2026-09
    period: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Контекст, который отправляли в LLM.
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ответ ассистента.
    response_text: Mapped[str] = mapped_column(Text, nullable=False)

    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
class LLMChatSession(Base):
    __tablename__ = "llm_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Новый чат")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LLMChatMessage(Base):
    __tablename__ = "llm_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    chat_session_id: Mapped[int] = mapped_column(
        ForeignKey("llm_chat_sessions.id"),
        nullable=False,
    )

    # user / assistant
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )