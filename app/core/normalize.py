def normalize_directory_name(value: str) -> str:
    if not value:
        return ""

    value = value.strip().casefold()
    value = value.replace("ё", "е")

    return " ".join(value.split())