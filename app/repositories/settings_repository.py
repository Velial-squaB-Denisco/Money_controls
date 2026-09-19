from sqlalchemy.orm import Session

from app.models import Setting


def get_setting(
    session: Session,
    key: str,
    default: str | None = None,
) -> str | None:
    setting = session.get(Setting, key)

    if setting is None or setting.value is None:
        return default

    return setting.value


def set_setting(
    session: Session,
    key: str,
    value: str | None,
) -> None:
    setting = session.get(Setting, key)

    if setting is None:
        setting = Setting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value

    session.flush()