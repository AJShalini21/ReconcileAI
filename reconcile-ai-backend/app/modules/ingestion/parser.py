import csv
import io
from typing import Any


def normalize_header_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or "")).strip("_")


async def read_csv_rows(file_obj) -> list[dict[str, str]]:
    await file_obj.seek(0)
    text = await file_obj.read()
    if not text:
        return []

    stream = io.StringIO(text.decode("utf-8-sig") if isinstance(text, bytes) else text)
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        return []

    normalized_headers = [normalize_header_name(name) for name in reader.fieldnames]
    reader.fieldnames = normalized_headers

    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {}
        for key, value in row.items():
            cleaned[key] = (value or "").strip() if isinstance(value, str) else ""
        rows.append(cleaned)

    return rows


def required_columns_present(headers: list[str], required: set[str]) -> bool:
    return required.issubset(set(headers))


def get_csv_row_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if row.get(key) not in (None, ""):
            return str(row.get(key)).strip()
    return ""
