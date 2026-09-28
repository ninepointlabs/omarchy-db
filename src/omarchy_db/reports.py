"""Reports and forms: the printable list of a table, and how a form is laid out.

A *report* is a tidy, fitted table of rows: pick the table, the columns, a
title, the page size and orientation. "Fitted" means the columns shrink and
the text wraps so the whole table fits the page width, nothing clipped.

This module holds the parts that need no toolkit: the spec, the row fetch,
the column-fitting arithmetic, and where forms and reports are remembered
(inside the database itself, in Omarchy-DB's own info table). Drawing the
pages needs Qt and lives in `printing.py`, which this module calls only when
a PDF is actually asked for.
"""

from __future__ import annotations

import json
from typing import Any

from .errors import BadName, OmarchyDBError
from .filters import filter_words, normalise_filter
from .paths import resolve_under_roots
from .storage.base import Storage

#: Page sizes in points (1/72 inch), portrait.
PAGE_SIZES = {
    "letter": (612.0, 792.0),
    "a4": (595.0, 842.0),
    "legal": (612.0, 1008.0),
}
ORIENTATIONS = ("portrait", "landscape")
MAX_REPORT_ROWS = 20000
CHUNK = 1000

FORM_KEY = "form:"
REPORT_KEY = "report:"


# -------------------------------------------------------------------------
# Report specs
# -------------------------------------------------------------------------

def normalise_spec(storage: Storage, spec: dict[str, Any]) -> dict[str, Any]:
    """Fill in the blanks of a report spec and check it against the table."""
    table = spec.get("table") or ""
    info = storage.describe_table(table)
    known = {f.name: f for f in info.fields}

    columns = list(spec.get("columns") or [f.name for f in info.fields])
    for name in columns:
        if name not in known:
            raise BadName(f"The table {table!r} has no field called {name!r}.")
    if not columns:
        raise OmarchyDBError("Pick at least one column for the report.")

    page_size = str(spec.get("page_size") or "letter").lower()
    if page_size not in PAGE_SIZES:
        raise OmarchyDBError(f"Unknown page size {page_size!r}. Use: {', '.join(PAGE_SIZES)}.")
    orientation = str(spec.get("orientation") or "portrait").lower()
    if orientation not in ORIENTATIONS:
        raise OmarchyDBError("Orientation must be portrait or landscape.")

    margins = float(spec.get("margins_mm", 15))
    margins = min(max(margins, 5.0), 40.0)
    font_pt = float(spec.get("font_pt", 10))
    font_pt = min(max(font_pt, 6.0), 16.0)

    row_filter = normalise_filter(info.fields, spec.get("filter") or None)

    return {
        "name": str(spec.get("name") or ""),
        "table": table,
        "title": str(spec.get("title") or info.name.replace("_", " ").title()),
        "columns": columns,
        "filter": row_filter,
        "filter_words": filter_words(info.fields, row_filter),
        "labels": [known[name].title for name in columns],
        "types": [known[name].type for name in columns],
        "page_size": page_size,
        "orientation": orientation,
        "margins_mm": margins,
        "fit_to_width": bool(spec.get("fit_to_width", True)),
        "font_pt": font_pt,
        "show_row_numbers": bool(spec.get("show_row_numbers", False)),
    }


def page_points(spec: dict[str, Any]) -> tuple[float, float]:
    width, height = PAGE_SIZES[spec["page_size"]]
    if spec["orientation"] == "landscape":
        width, height = height, width
    return width, height


def fetch_rows(storage: Storage, spec: dict[str, Any]) -> list[list[str]]:
    """Every row of the table as display text, in the report's column order."""
    columns = spec["columns"]
    types = dict(zip(columns, spec["types"]))
    out: list[list[str]] = []
    offset = 0
    while len(out) < MAX_REPORT_ROWS:
        page = storage.list_rows(spec["table"], limit=CHUNK, offset=offset, where=spec.get("filter"))
        if not page["rows"]:
            break
        positions = [page["columns"].index(name) for name in columns]
        for row in page["rows"]:
            out.append([cell_text(row[pos], types[name]) for pos, name in zip(positions, columns)])
        offset += CHUNK
    return out


def cell_text(value: Any, kind: str | None) -> str:
    """How a value reads on screen and on paper: a whole number without a trailing ".0"."""
    if value is None:
        return ""
    if kind == "boolean":
        return "Yes" if value else "No"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def fit_columns(
    natural: list[float], minimum: list[float], available: float, *, fit: bool = True
) -> list[float]:
    """Choose column widths that add up to at most `available`.

    Columns that need less than their fair share keep what they need; the
    rest share what is left in proportion to how wide they wanted to be, but
    never narrower than `minimum` (roughly their longest word). If even the
    minimums do not fit, everything is scaled down together and cells wrap.
    With `fit` off, natural widths are kept and the table may run off the page.
    """
    if not natural:
        return []
    if not fit or sum(natural) <= available:
        return list(natural)

    widths = list(natural)
    fixed = [False] * len(widths)
    for _ in range(len(widths)):
        free = available - sum(w for w, f in zip(widths, fixed) if f)
        flexible = [i for i, f in enumerate(fixed) if not f]
        if not flexible:
            break
        share = free / len(flexible)
        changed = False
        for i in flexible:
            if widths[i] <= share:
                fixed[i] = True
                changed = True
        if not changed:
            total = sum(widths[i] for i in flexible)
            for i in flexible:
                widths[i] = max(minimum[i], free * widths[i] / total)
            break

    if sum(widths) > available + 0.01:
        scale = available / sum(widths)
        widths = [w * scale for w in widths]
    return widths


# -------------------------------------------------------------------------
# Exporting
# -------------------------------------------------------------------------

def export_report(
    storage: Storage, spec: dict[str, Any], file_path: str, *, overwrite: bool = False
) -> dict[str, Any]:
    """Lay the report out and write it as a PDF."""
    full = normalise_spec(storage, spec)
    target = resolve_under_roots(file_path)
    if target.suffix.lower() != ".pdf":
        target = target.with_name(target.name + ".pdf")
    existed = target.exists()
    if existed and not overwrite:
        raise OmarchyDBError(f"There is already a file at {target}. Pass overwrite to replace it.")
    target.parent.mkdir(parents=True, exist_ok=True)

    from .printing import ReportDocument  # noqa: PLC0415 - needs Qt, only for PDF

    document = ReportDocument(full, fetch_rows(storage, full))
    pages = document.write_pdf(str(target))
    return {
        "table": full["table"],
        "title": full["title"],
        "file": str(target),
        "format": "pdf",
        "rows_written": len(document.rows),
        "pages": pages,
        "page_size": full["page_size"],
        "orientation": full["orientation"],
        "replaced_existing_file": existed,
    }


# -------------------------------------------------------------------------
# Remembering forms and reports inside the database
# -------------------------------------------------------------------------

def save_form(storage: Storage, table: str, form: dict[str, Any]) -> dict[str, Any]:
    """Keep a simple form layout for a table: field order and labels."""
    info = storage.describe_table(table)
    known = {f.name: f for f in info.fields}
    order = list(form.get("fields") or [f.name for f in info.fields])
    for name in order:
        if name not in known:
            raise BadName(f"The table {table!r} has no field called {name!r}.")
    labels = dict(form.get("labels") or {})
    for name in labels:
        if name not in known:
            raise BadName(f"The table {table!r} has no field called {name!r}.")
    saved = {
        "table": table,
        "title": str(form.get("title") or info.name.replace("_", " ").title()),
        "fields": order,
        "labels": {name: str(labels.get(name) or known[name].title) for name in order},
    }
    storage.set_info(FORM_KEY + table, json.dumps(saved))
    return saved


def load_form(storage: Storage, table: str) -> dict[str, Any] | None:
    raw = storage.get_info(FORM_KEY + table, "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def form_for(storage: Storage, table: str) -> dict[str, Any]:
    """The saved form, or the plain default: every field, in table order."""
    saved = load_form(storage, table)
    info = storage.describe_table(table)
    known = {f.name: f for f in info.fields}
    if saved:
        # Fields added since the form was saved go on the end; removed ones drop out.
        order = [n for n in saved.get("fields", []) if n in known]
        order += [f.name for f in info.fields if f.name not in order]
        labels = {n: saved.get("labels", {}).get(n) or known[n].title for n in order}
        return {"table": table, "title": saved.get("title") or info.name, "fields": order,
                "labels": labels, "saved": True}
    return {
        "table": table,
        "title": info.name.replace("_", " ").title(),
        "fields": [f.name for f in info.fields],
        "labels": {f.name: f.title for f in info.fields},
        "saved": False,
    }


def save_report(storage: Storage, spec: dict[str, Any]) -> dict[str, Any]:
    full = normalise_spec(storage, spec)
    name = full["name"] or full["title"]
    if not name.strip():
        raise OmarchyDBError("Give the report a name.")
    full["name"] = name.strip()
    storage.set_info(REPORT_KEY + full["name"], json.dumps(full))
    return full


def load_report(storage: Storage, name: str) -> dict[str, Any] | None:
    raw = storage.get_info(REPORT_KEY + name, "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def list_reports(storage: Storage) -> list[dict[str, Any]]:
    rows = storage.query(
        f"SELECT {storage.quote('key')}, {storage.quote('value')} FROM {storage.quote('omadb_info')}"
    )
    out = []
    for key, value in rows:
        if str(key).startswith(REPORT_KEY):
            try:
                spec = json.loads(value)
            except ValueError:
                continue
            out.append({"name": spec.get("name") or str(key)[len(REPORT_KEY):],
                        "table": spec.get("table", ""), "title": spec.get("title", "")})
    return sorted(out, key=lambda item: item["name"].lower())


def delete_report(storage: Storage, name: str) -> bool:
    if load_report(storage, name) is None:
        return False
    storage.execute(
        f"DELETE FROM {storage.quote('omadb_info')} WHERE {storage.quote('key')} = {storage.placeholder(0)}",
        (REPORT_KEY + name,),
    )
    storage.commit()
    return True
