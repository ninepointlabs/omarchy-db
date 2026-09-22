"""Turn a spreadsheet into a table.

v1 reads CSV (and tab-separated files). Excel `.xlsx` arrives in Phase B.
Cells are only ever read as data: a formula is stored as the text it is,
never worked out or run.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .errors import ImportProblem
from .fields import Field, coerce, slugify_name
from .infer import infer_fields
from .paths import resolve_under_roots
from .storage.base import Storage

SAMPLE_ROWS = 500
CSV_SUFFIXES = {".csv", ".tsv", ".txt"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


def read_csv(path: Path, *, max_rows: int | None = None) -> tuple[list[str], list[list[str]]]:
    """Read a CSV file into headings plus rows of plain text."""
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as handle:
        sample = handle.read(64 * 1024)
        handle.seek(0)
        try:
            dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        try:
            headers = next(reader)
        except StopIteration:
            raise ImportProblem("That file is empty.") from None
        rows: list[list[str]] = []
        for row in reader:
            if not any(str(cell).strip() for cell in row):
                continue
            rows.append([str(cell) for cell in row])
            if max_rows is not None and len(rows) >= max_rows:
                break
    headers = [str(header) for header in headers]
    if not any(header.strip() for header in headers):
        raise ImportProblem("The first line of that file has no column names.")
    return headers, rows


def table_name_for(path: Path) -> str:
    return slugify_name(path.stem, fallback="table")


def plan_import(file_path: str) -> dict[str, Any]:
    """Look at a spreadsheet and say what would be made, without making it.

    This is what the import wizard shows before the user presses the button.
    """
    path = resolve_under_roots(file_path, must_exist=True)
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        raise ImportProblem(
            "Excel files are not read yet — that comes in the next step of the project. "
            "Save the sheet as CSV and import that."
        )
    if suffix not in CSV_SUFFIXES:
        raise ImportProblem(f"Omarchy-DB does not know how to read {suffix or 'that file'} yet.")

    headers, rows = read_csv(path, max_rows=SAMPLE_ROWS)
    fields = infer_fields(headers, rows)
    return {
        "file": str(path),
        "table": table_name_for(path),
        "headers": headers,
        "fields": [{"name": f.name, "type": f.type, "label": f.title} for f in fields],
        "sample_rows": rows[:5],
        "rows_sampled": len(rows),
    }


def import_spreadsheet(
    storage: Storage,
    file_path: str,
    *,
    table: str | None = None,
    fields: Sequence[Field] | None = None,
    if_exists: str = "error",
) -> dict[str, Any]:
    """Read a spreadsheet and put it in the database as a table."""
    path = resolve_under_roots(file_path, must_exist=True)
    plan = plan_import(str(path))
    table_name = table or plan["table"]

    if fields is None:
        fields = [Field(name=f["name"], type=f["type"], label=f["label"]) for f in plan["fields"]]
    fields = list(fields)

    headers, rows = read_csv(path)
    existed = storage.has_table(table_name)
    storage.create_table(table_name, fields, if_exists=if_exists)

    typed_rows: list[list[Any]] = []
    problems: list[str] = []
    for line_number, row in enumerate(rows, start=2):
        values: list[Any] = []
        for index, field in enumerate(fields):
            raw = row[index] if index < len(row) else None
            try:
                values.append(coerce(raw, field.type))
            except (ValueError, TypeError):
                # Never lose a cell: keep the text and note it.
                values.append(None if raw in (None, "") else str(raw))
                problems.append(f"Line {line_number}, {field.title}: kept {raw!r} as words.")
        typed_rows.append(values)

    added = storage.add_rows(table_name, fields, typed_rows)
    return {
        "file": str(path),
        "table": table_name,
        "created_fields": [{"name": f.name, "type": f.type, "label": f.title} for f in fields],
        "rows_added": added,
        "notes": problems[:20],
        "note_count": len(problems),
        "replaced_existing": existed and if_exists == "replace",
    }
