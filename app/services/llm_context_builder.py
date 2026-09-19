import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.repositories import budget_repository
from app.services import analytics_service


def minor_to_money(amount_minor: int | None) -> float:
    return round((amount_minor or 0) / 100, 2)


def build_month_context(session: Session) -> dict:
    month_start, month_end = analytics_service.get_current_month_bounds()

    previous_month_start = analytics_service.add_months(month_start, -1)
    previous_month_end = month_start - timedelta(days=1)

    current_summary = analytics_service.get_period_summary(
        session=session,
        start_date=month_start,
        end_date=month_end,
    )

    previous_summary = analytics_service.get_period_summary(
        session=session,
        start_date=previous_month_start,
        end_date=previous_month_end,
    )

    balance = analytics_service.get_total_balance(session)

    top_expense_categories = analytics_service.get_top_expense_categories(
        session=session,
        start_date=month_start,
        end_date=month_end,
        limit=7,
    )

    budget_rows = budget_repository.get_budgets_for_table(session)

    budget_category_ids = [row[0].category_id for row in budget_rows]

    spent_map = analytics_service.get_budget_spent_map(
        session=session,
        start_date=month_start,
        end_date=month_end,
        budget_category_ids=budget_category_ids,
    )

    budgets = []

    for row in budget_rows:
        budget = row[0]
        category_name = row.category_name

        spent_minor = spent_map.get(budget.category_id, 0)
        remaining_minor = budget.amount_minor - spent_minor

        if budget.amount_minor > 0:
            percent = round(spent_minor * 100 / budget.amount_minor, 1)
        else:
            percent = 0

        budgets.append(
            {
                "category": category_name,
                "limit": minor_to_money(budget.amount_minor),
                "spent": minor_to_money(spent_minor),
                "remaining": minor_to_money(remaining_minor),
                "percent": percent,
                "is_active": budget.is_active,
            }
        )

    context = {
        "period": month_start.strftime("%Y-%m"),
        "currency": "RUB",
        "balance": minor_to_money(balance),
        "current_month": {
            "income": minor_to_money(current_summary["income"]),
            "expense": minor_to_money(current_summary["expense"]),
            "net": minor_to_money(current_summary["net"]),
        },
        "previous_month": {
            "income": minor_to_money(previous_summary["income"]),
            "expense": minor_to_money(previous_summary["expense"]),
            "net": minor_to_money(previous_summary["net"]),
        },
        "top_expense_categories": [
            {
                "category": name,
                "amount": minor_to_money(amount),
            }
            for name, amount in top_expense_categories
        ],
        "budgets": budgets,
    }
    
    balances = analytics_service.get_account_balances(session)

    interest = analytics_service.get_interest_summary(
        session=session,
        start_date=month_start,
        end_date=month_end,
    )

    financial_accounts = [
        {
            "name": item["name"],
            "type": item["type"],
            "balance": minor_to_money(item["balance"]),
            "annual_rate_percent": round(
                (item.get("annual_rate_bp") or 0) / 100, 2
            ),
            "monthly_payment": minor_to_money(
                item.get("monthly_payment_minor") or 0
            ),
        }
        for item in balances
        if item["type"] in ["deposit", "savings", "loan", "credit_card"]
    ]

    context["cash"] = minor_to_money(
        analytics_service.get_cash_balance(session)
    )
    context["net_worth"] = minor_to_money(
        analytics_service.get_net_worth(session)
    )
    context["total_debts"] = minor_to_money(
        analytics_service.get_total_debts(session)
    )
    context["financial_accounts"] = financial_accounts
    context["interest"] = {
        "deposit_interest": minor_to_money(interest["deposit_interest"]),
        "loan_interest": minor_to_money(interest["loan_interest"]),
    }

    return context


def context_to_json(context: dict) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2)


def base_system_prompt() -> str:
    return (
        "Ты — финансовый ассистент пользователя. "
        "Ты получаешь не сырые транзакции, а заранее подготовленные агрегаты. "
        "Отвечай на русском языке, кратко и по делу. "
        "Не выдумывай данные, которых нет в контексте. "
        "Если данных мало, так и скажи. "
        "Используй суммы в рублях. "
        "Давай практичные рекомендации без воды."
    )


def build_month_analysis_messages(context: dict) -> list[dict]:
    context_json = context_to_json(context)

    user_prompt = (
        "Ниже приведены агрегированные финансовые данные за текущий месяц.\n"
        "Сравни текущий месяц с прошлым месяцем.\n"
        "Отметь важные изменения, риски и позитивные моменты.\n"
        "Дай 3-5 практических рекомендаций.\n\n"
        f"Данные:\n{context_json}"
    )

    return [
        {"role": "system", "content": base_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def build_anomaly_messages(context: dict) -> list[dict]:
    context_json = context_to_json(context)

    user_prompt = (
        "Ниже приведены агрегированные финансовые данные.\n"
        "Найди возможные аномалии или тревожные сигналы:\n"
        "- сильный рост расходов;\n"
        "- перерасход бюджетов;\n"
        "- снижение остатка;\n"
        "- необычно высокая доля одной категории.\n"
        "Если аномалий нет, спокойно скажи об этом.\n\n"
        f"Данные:\n{context_json}"
    )

    return [
        {"role": "system", "content": base_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def build_budget_recommendation_messages(context: dict) -> list[dict]:
    context_json = context_to_json(context)

    user_prompt = (
        "Ниже приведены агрегированные финансовые данные и бюджеты пользователя.\n"
        "Оцени, насколько реалистичны текущие бюджеты.\n"
        "Предложи корректировки лимитов, если это уместно.\n"
        "Укажи, где можно сократить расходы, а где лимит можно увеличить.\n"
        "Не придумывай категории или суммы, которых нет в данных.\n\n"
        f"Данные:\n{context_json}"
    )

    return [
        {"role": "system", "content": base_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def build_chat_system_prompt(context: dict) -> str:
    context_json = context_to_json(context)

    return (
        f"{base_system_prompt()}\n\n"
        "Ниже приведен финансовый контекст пользователя.\n"
        "Используй его, чтобы отвечать на вопросы пользователя.\n"
        "Если вопроса нет в данных, не выдумывай ответ, а скажи, что таких данных нет.\n"
        "Если пользователь спрашивает про расходы, доходы, бюджеты или баланс, "
        "опирайся только на переданный контекст.\n\n"
        f"Финансовый контекст:\n{context_json}"
    )
    

def build_debt_and_deposit_messages(context: dict) -> list[dict]:
    context_json = context_to_json(context)

    user_prompt = (
        "Ниже приведены финансовые данные пользователя, включая свободные деньги, "
        "чистые активы, долги, вклады, накопительные счета, кредиты, кредитные карты "
        "и проценты за месяц.\n"
        "Проанализируй долги и вклады:\n"
        "- оцени долговую нагрузку и стоимость обслуживания долгов;\n"
        "- оцени, сколько приносят вклады и накопления;\n"
        "- сравни уплаченные проценты по кредитам с полученными процентами по вкладам;\n"
        "- если данных достаточно, прикинь срок закрытия кредита при текущих платежах;\n"
        "- дай 3-5 практичных рекомендаций по вкладам, накоплениям и кредитам.\n"
        "Не выдумывай цифры, которых нет в контексте.\n\n"
        f"Данные:\n{context_json}"
    )

    return [
        {"role": "system", "content": base_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]