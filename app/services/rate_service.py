from datetime import date
from decimal import Decimal

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExchangeRate


SUPPORTED_CURRENCIES = ["USD", "EUR"]


def parse_cbr_rates(xml_text: str) -> dict:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)

    rates: dict[str, Decimal] = {}

    for valute in root.findall("Valute"):
        code = valute.findtext("CharCode")

        if code not in SUPPORTED_CURRENCIES:
            continue

        nominal_text = valute.findtext("Nominal") or "1"
        value_text = valute.findtext("Value") or "0"

        nominal = int(nominal_text)
        value = Decimal(value_text.replace(",", "."))

        if nominal > 0:
            rates[code] = value / nominal

    return rates


def fetch_cbr_rates(on_date: date | None = None) -> dict:
    url = "https://www.cbr.ru/scripts/XML_daily.asp"

    params = {}

    if on_date is not None:
        params["date_req"] = on_date.strftime("%d/%m/%Y")

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return parse_cbr_rates(response.text)


def refresh_rates(session: Session, on_date: date | None = None) -> int:
    target_date = on_date or date.today()

    rates = fetch_cbr_rates(target_date)

    created_count = 0

    for code, rate in rates.items():
        existing = session.scalar(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency == code)
            .where(ExchangeRate.to_currency == "RUB")
            .where(ExchangeRate.rate_date == target_date)
        )

        if existing is not None:
            existing.rate = rate
            existing.source = "cbr"
        else:
            session.add(
                ExchangeRate(
                    from_currency=code,
                    to_currency="RUB",
                    rate_date=target_date,
                    rate=rate,
                    source="cbr",
                )
            )

            created_count += 1

    session.flush()

    return created_count


def get_stored_rate(
    session: Session,
    from_currency: str,
    to_currency: str,
    on_date: date,
) -> Decimal | None:
    if from_currency == to_currency:
        return Decimal("1")

    direct = session.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == from_currency)
        .where(ExchangeRate.to_currency == to_currency)
        .where(ExchangeRate.rate_date <= on_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )

    if direct is not None:
        return direct.rate

    inverse = session.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == to_currency)
        .where(ExchangeRate.to_currency == from_currency)
        .where(ExchangeRate.rate_date <= on_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )

    if inverse is not None and inverse.rate:
        return Decimal("1") / inverse.rate

    return None


def get_rate(
    session: Session,
    from_currency: str,
    to_currency: str,
    on_date: date | None = None,
) -> Decimal | None:
    if on_date is None:
        on_date = date.today()

    rate = get_stored_rate(session, from_currency, to_currency, on_date)

    if rate is not None:
        return rate

    if from_currency == "RUB" or to_currency == "RUB":
        try:
            refresh_rates(session, on_date)

            rate = get_stored_rate(session, from_currency, to_currency, on_date)

            if rate is not None:
                return rate
        except Exception:
            pass

        rate = get_stored_rate(session, from_currency, to_currency, date.today())

        if rate is not None:
            return rate

    return None


def get_latest_rate_info(
    session: Session,
    from_currency: str = "USD",
    to_currency: str = "RUB",
):
    return session.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == from_currency)
        .where(ExchangeRate.to_currency == to_currency)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )