"""Guess what each spreadsheet column holds.

The rule is simple and predictable: a column gets the narrowest type that
every non-blank value fits. Blanks never decide anything. Anything we are
unsure about stays Words (text), because text never loses data.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .fields import (
    BOOLEAN,
    DATE,
    INTEGER,
    REAL,
    TEXT,
    Field,
    parse_boolean,
    parse_date,
    unique_names,
)

# Narrowest first. The first type that fits every value wins.
_ORDER = (BOOLEAN, INTEGER, REAL, DATE, TEXT)


def _fits_integer(value: str) -> bool:
    text = value.replace(",", "").strip()
    if text in ("", "-", "+"):
        return False
    try:
        int(text)
    except ValueError:
        return False
    return True


def _fits_real(value: str) -> bool:
    text = value.replace(",", "").strip()
    if text == "":
        return False
    try:
        number = float(text)
    except ValueError:
        return False
    return number == number and abs(number) != float("inf")


def _fits(value: str, field_type: str) -> bool:
    if field_type == TEXT:
        return True
    if field_type == BOOLEAN:
        return parse_boolean(value) is not None
    if field_type == INTEGER:
        return _fits_integer(value)
    if field_type == REAL:
        return _fits_real(value)
    if field_type == DATE:
        return parse_date(value) is not None
    return False


def infer_column_type(values: Iterable[object]) -> str:
    """Pick the type for one column of raw cells."""
    samples = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            samples.append(text)

    if not samples:
        return TEXT

    for field_type in _ORDER:
        if all(_fits(sample, field_type) for sample in samples):
            return field_type
    return TEXT


def infer_fields(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[Field]:
    """Turn headings plus sample rows into the fields for a new table."""
    names = unique_names(list(headers))
    fields: list[Field] = []
    for index, name in enumerate(names):
        column = [row[index] if index < len(row) else None for row in rows]
        label = str(headers[index]).strip() if index < len(headers) else name
        fields.append(Field(name=name, type=infer_column_type(column), label=label or name))
    return fields
