from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LLMChatMessage, LLMChatSession


def create_session(
    session: Session,
    title: str = "Новый чат",
) -> LLMChatSession:
    chat_session = LLMChatSession(title=title)

    session.add(chat_session)
    session.flush()

    return chat_session


def get_sessions(session: Session):
    statement = (
        select(LLMChatSession)
        .order_by(LLMChatSession.updated_at.desc(), LLMChatSession.id.desc())
    )

    return list(session.scalars(statement).all())


def get_session_by_id(
    session: Session,
    session_id: int,
) -> LLMChatSession | None:
    return session.get(LLMChatSession, session_id)


def delete_session(
    session: Session,
    session_id: int,
) -> None:
    messages_statement = (
        select(LLMChatMessage)
        .where(LLMChatMessage.chat_session_id == session_id)
    )

    for message in session.scalars(messages_statement):
        session.delete(message)

    chat_session = session.get(LLMChatSession, session_id)

    if chat_session is not None:
        session.delete(chat_session)

    session.flush()


def add_message(
    session: Session,
    chat_session_id: int,
    role: str,
    content: str,
) -> LLMChatMessage:
    message = LLMChatMessage(
        chat_session_id=chat_session_id,
        role=role,
        content=content,
    )

    session.add(message)
    session.flush()

    chat_session = session.get(LLMChatSession, chat_session_id)

    if chat_session is not None:
        chat_session.updated_at = datetime.now()
        session.flush()

    return message


def get_messages(
    session: Session,
    chat_session_id: int,
):
    statement = (
        select(LLMChatMessage)
        .where(LLMChatMessage.chat_session_id == chat_session_id)
        .order_by(LLMChatMessage.id.asc())
    )

    return list(session.scalars(statement).all())