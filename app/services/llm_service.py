import requests

from app.repositories import settings_repository


def get_llm_settings(session) -> dict:
    return {
        "base_url": settings_repository.get_setting(
            session=session,
            key="llm_base_url",
            default="http://localhost:11434/v1",
        ),
        "api_key": settings_repository.get_setting(
            session=session,
            key="llm_api_key",
            default="",
        ),
        "model": settings_repository.get_setting(
            session=session,
            key="llm_model",
            default="",
        ),
    }


def save_llm_settings(
    session,
    base_url: str,
    api_key: str,
    model: str,
) -> None:
    settings_repository.set_setting(session, "llm_base_url", base_url)
    settings_repository.set_setting(session, "llm_api_key", api_key)
    settings_repository.set_setting(session, "llm_model", model)


def complete(settings: dict, messages: list[dict]) -> str:
    base_url = (settings.get("base_url") or "").strip()
    api_key = (settings.get("api_key") or "").strip()
    model = (settings.get("model") or "").strip()

    if not base_url:
        raise ValueError("Не указан Base URL для LLM")

    if not model:
        raise ValueError("Не указана модель LLM")

    # Мок-режим для проверки интерфейса без реального LLM.
    if base_url.lower() == "mock" or model.lower() == "mock":
        return (
            "Это мок-ответ ассистента.\n\n"
            "Чтобы подключить реальный LLM, укажи:\n"
            "- Base URL\n"
            "- API key, если требуется\n"
            "- модель\n\n"
            "Например, для Ollama:\n"
            "Base URL: http://localhost:11434/v1\n"
            "API key: пусто\n"
            "Model: llama3.1 или другая установленная модель"
        )

    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }

    response = requests.post(url, json=payload, timeout=1200)

    if response.status_code != 200:
        raise ValueError(
            f"LLM API вернул ошибку {response.status_code}:\n"
            f"{response.text[:1000]}"
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise ValueError("Не удалось разобрать ответ от LLM")