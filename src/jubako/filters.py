"""Show rows where <field> <is / is not / is empty / is not empty / contains> <value>.

One small, safe filter shared by the grid, the form, reports and the MCP
server. There is no free-form SQL: the field must be one of the table's, the
match is one of a short list, and the value is bound as a parameter after
being read the way the field's type wants (so a yes/no field accepts yes, no,
true, false, 1 or 0).
"""

from __future__ import annotations

from typing import Any

from .errors import BadName, JubakoError
from .fields import BOOLEAN, DATE, TEXT, Field, coerce

OPS = ("is", "is_not", "empty", "not_empty", "contains")

#: The words people see for each match.
OP_WORDS = {
    "is": "is",
    "is_not": "is not",
    "empty": "is empty",
    "not_empty": "is not empty",
    "contains": "contains",
}

NEEDS_VALUE = {"is", "is_not", "contains"}


def normalise_filter(fields: list[Field], raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Check a filter against a table's fields. Returns None for "no filter"."""
    if not raw:
        return None
    field_name = str(raw.get("field") or "").strip()
    op = str(raw.get("op") or "is").strip().lower().replace(" ", "_")
    if op == "is_not_empty":
        op = "not_empty"
    if op == "is_empty":
        op = "empty"
    known = {f.name: f for f in fields}
    if field_name not in known:
        raise BadName(f"This table has no field called {field_name!r}.")
    if op not in OPS:
        raise JubakoError(f"Unknown match {raw.get('op')!r}. Use: {', '.join(OPS)}.")
    field = known[field_name]
    value: Any = raw.get("value")
    if op in NEEDS_VALUE:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise JubakoError(f"Say what {field.title} should {OP_WORDS[op]}.")
        if op == "contains":
            if field.type != TEXT:
                raise JubakoError("“contains” only works on a words field. Use “is” instead.")
            value = str(value)
        else:
            try:
                value = coerce(value, field.type)
            except (ValueError, TypeError):
                raise JubakoError(
                    f"“{value}” is not a {_kind_word(field.type)}, which is what {field.title} holds."
                ) from None
    else:
        value = None
    return {"field": field_name, "op": op, "value": value}


def where_clause(storage: Any, filter_spec: dict[str, Any] | None, *, first_index: int = 0) -> tuple[str, list[Any]]:
    """The SQL after WHERE (empty for no filter) and its parameters."""
    if not filter_spec:
        return "", []
    column = storage.quote(filter_spec["field"])
    op = filter_spec["op"]
    value = filter_spec["value"]
    mark = storage.placeholder(first_index)
    if op == "is":
        return f"{column} = {mark}", [_param(value)]
    if op == "is_not":
        return f"({column} IS NULL OR {column} <> {mark})", [_param(value)]
    if op == "empty":
        return f"({column} IS NULL OR CAST({column} AS CHAR(1)) = '')", []
    if op == "not_empty":
        return f"({column} IS NOT NULL AND CAST({column} AS CHAR(1)) <> '')", []
    if op == "contains":
        escaped = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"LOWER({column}) LIKE LOWER({mark}) ESCAPE '\\'", [f"%{escaped}%"]
    raise JubakoError(f"Unknown match {op!r}.")


def filter_words(fields: list[Field], filter_spec: dict[str, Any] | None) -> str:
    """The rule in plain words: "Moved is not Yes"."""
    if not filter_spec:
        return ""
    known = {f.name: f for f in fields}
    field = known.get(filter_spec["field"])
    label = field.title if field else filter_spec["field"]
    op = filter_spec["op"]
    if op in NEEDS_VALUE:
        value = filter_spec["value"]
        if field is not None and field.type == BOOLEAN:
            value = "Yes" if value else "No"
        return f"{label} {OP_WORDS[op]} {value}"
    return f"{label} {OP_WORDS[op]}"


def _param(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)  # SQLite keeps 0/1; PostgreSQL and MySQL accept it for their booleans too
    return value


def _kind_word(kind: str) -> str:
    return {"integer": "whole number", "real": "number", DATE: "date like 2024-01-31",
            BOOLEAN: "yes or no"}.get(kind, "words")
