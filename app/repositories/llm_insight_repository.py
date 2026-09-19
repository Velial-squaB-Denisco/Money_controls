from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LLMInsight


def create_insight(
    session: Session,
    *,
    request_type: str,
    period: str | None = None,
    context_json: str | None = None,
    response_text: str,
    model_name: str | None = None,
) -> LLMInsight:
    insight = LLMInsight(
        request_type=request_type,
        period=period,
        context_json=context_json,
        response_text=response_text,
        model_name=model_name,
        is_pinned=False,
    )

    session.add(insight)
    session.flush()

    return insight


def get_history(session: Session):
    statement = (
        select(LLMInsight)
        .order_by(LLMInsight.created_at.desc(), LLMInsight.id.desc())
    )

    return list(session.scalars(statement).all())


def get_insight_by_id(
    session: Session,
    insight_id: int,
) -> LLMInsight | None:
    return session.get(LLMInsight, insight_id)


def delete_insight(
    session: Session,
    insight_id: int,
) -> None:
    insight = session.get(LLMInsight, insight_id)

    if insight is None:
        return

    session.delete(insight)
    session.flush()