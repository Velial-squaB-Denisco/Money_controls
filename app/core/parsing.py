def parse_comma_separated_items(value: str | None) -> list[str]:
    if not value:
        return []

    value = value.replace("\n", ",")
    value = value.replace(";", ",")

    parts = value.split(",")

    result: list[str] = []
    seen: set[str] = set()

    for part in parts:
        item = " ".join(part.strip().split())

        if not item:
            continue

        key = item.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result