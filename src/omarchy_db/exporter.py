"""Send a table back out as a file. v1 does CSV; xlsx and PDF are Phase B."""

from __future__ import annotations

import csv
from typing import Any

from .errors import OmarchyDBError
from .paths import resolve_under_roots
from .fields import BOOLEAN
from .storage.base import Storage, to_jsonable

CHUNK = 1000
FORMATS = ("csv",)
LATER_FORMATS = ("xlsx", "pdf")


def export_table(
    storage: Storage,
    table: str,
    file_path: str,
    *,
    file_format: str = "csv",
    overwrite: bool = False,
    include_id: bool = False,
) -> dict[str, Any]:
    """Write every row of a table to a file the user picked."""
    kind = (file_format or "csv").strip().lower().lstrip(".")
    if kind in LATER_FORMATS:
        raise OmarchyDBError(
            f"{kind.upper()} export is not built yet — it comes in the next step. Use CSV for now."
        )
    if kind not in FORMATS:
        raise OmarchyDBError(f"Omarchy-DB cannot write {kind!r} files. Use: {', '.join(FORMATS)}.")

    info = storage.describe_table(table)
    target = resolve_under_roots(file_path)
    if target.suffix.lower() != ".csv":
        target = target.with_name(target.name + ".csv")

    existed = target.exists()
    if existed and not overwrite:
        raise OmarchyDBError(
            f"There is already a file at {target}. Pass overwrite to replace it."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        heading = (["id"] if include_id else []) + [f.title for f in info.fields]
        writer.writerow(heading)
        offset = 0
        while True:
            page = storage.list_rows(table, limit=CHUNK, offset=offset)
            if not page["rows"]:
                break
            for row in page["rows"]:
                values = row if include_id else row[1:]
                kinds = ([None] if include_id else []) + [f.type for f in info.fields]
                writer.writerow([_cell(value, kind) for value, kind in zip(values, kinds)])
                written += 1
            offset += CHUNK

    return {
        "table": table,
        "file": str(target),
        "format": "csv",
        "rows_written": written,
        "replaced_existing_file": existed,
    }


def _cell(value: Any, kind: str | None) -> str:
    """One cell of CSV. Yes/no fields are written as words, not 1 and 0."""
    if value is None:
        return ""
    if kind == BOOLEAN:
        return "yes" if value else "no"
    return str(to_jsonable(value))
