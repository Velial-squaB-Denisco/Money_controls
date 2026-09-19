from datetime import date, datetime, time

from dateutil.rrule import rrulestr

WEEKDAY_LABELS = {
    "MO": "Понедельник",
    "TU": "Вторник",
    "WE": "Среда",
    "TH": "Четверг",
    "FR": "Пятница",
    "SA": "Суббота",
    "SU": "Воскресенье",
}

MONTH_LABELS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def build_rrule(
    frequency: str,
    monthly_day: int | None = None,
    weekly_day: str | None = None,
    yearly_month: int | None = None,
    yearly_day: int | None = None,
) -> str:
    if frequency == "monthly":
        return f"FREQ=MONTHLY;BYMONTHDAY={monthly_day or 1}"

    if frequency == "weekly":
        return f"FREQ=WEEKLY;BYDAY={weekly_day or 'MO'}"

    if frequency == "yearly":
        return f"FREQ=YEARLY;BYMONTH={yearly_month or 1};BYMONTHDAY={yearly_day or 1}"

    raise ValueError(f"Unknown frequency: {frequency}")


def parse_rrule(rrule_text: str | None) -> dict:
    result = {
        "frequency": None,
        "monthly_day": None,
        "weekly_day": None,
        "yearly_month": None,
        "yearly_day": None,
    }

    if not rrule_text:
        return result

    parts: dict[str, str] = {}

    for part in rrule_text.split(";"):
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        parts[key.strip().upper()] = value.strip()

    frequency = parts.get("FREQ")

    if frequency == "MONTHLY":
        result["frequency"] = "monthly"
        result["monthly_day"] = int(parts.get("BYMONTHDAY", "1"))

    elif frequency == "WEEKLY":
        result["frequency"] = "weekly"
        result["weekly_day"] = parts.get("BYDAY", "MO")

    elif frequency == "YEARLY":
        result["frequency"] = "yearly"
        result["yearly_month"] = int(parts.get("BYMONTH", "1"))
        result["yearly_day"] = int(parts.get("BYMONTHDAY", "1"))

    return result


def _get_rule(rrule_text: str, start_date: date):
    dtstart = datetime.combine(start_date, time.min)

    return rrulestr(rrule_text, dtstart=dtstart)


def get_next_due_date(
    rrule_text: str,
    start_date: date,
    reference_date: date,
) -> date | None:
    rule = _get_rule(rrule_text, start_date)

    reference_datetime = datetime.combine(reference_date, time.min)

    next_datetime = rule.after(reference_datetime, inc=True)

    if next_datetime is None:
        return None

    return next_datetime.date()


def get_next_occurrence_after(
    rrule_text: str,
    start_date: date,
    after_date: date,
) -> date | None:
    rule = _get_rule(rrule_text, start_date)

    after_datetime = datetime.combine(after_date, time.min)

    next_datetime = rule.after(after_datetime, inc=False)

    if next_datetime is None:
        return None

    return next_datetime.date()


def format_rrule(rrule_text: str | None) -> str:
    parsed = parse_rrule(rrule_text)

    frequency = parsed["frequency"]

    if frequency == "monthly":
        return f"Ежемесячно {parsed['monthly_day']} числа"

    if frequency == "weekly":
        weekday = parsed["weekly_day"]
        weekday_label = WEEKDAY_LABELS.get(weekday, weekday)

        return f"Еженедельно: {weekday_label}"

    if frequency == "yearly":
        month = parsed["yearly_month"]
        day = parsed["yearly_day"]
        month_label = MONTH_LABELS.get(month, month)

        return f"Ежегодно {day} {month_label}"

    return rrule_text or "-"