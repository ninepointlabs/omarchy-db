"""Saved views: a named "Show rows where…" that lives in the database file.

A view is one table, one name, one filter (see `filters.py`). It is kept in
Jubako's own info table under `view:<table>:<name>`, so it travels with
the `.jubadb`. One view per table may be the default: the one the table
opens with.
"""

from __future__ import annotations

import json
from typing import Any

from .errors import JubakoError
from .filters import filter_words, normalise_filter
from .storage.base import Storage

VIEW_KEY = "view:"


def _key(table: str, name: str) -> str:
    return f"{VIEW_KEY}{table}:{name}"


def save_view(
    storage: Storage,
    table: str,
    name: str,
    filter_spec: dict[str, Any] | None,
    *,
    replace: bool = False,
    default: bool | None = None,
) -> dict[str, Any]:
    """Keep a filter under a name. Refuses a blank name, and a taken one unless `replace`."""
    name = (name or "").strip()
    if not name:
        raise JubakoError("Give the view a name, like “Still here”.")
    if ":" in name or len(name) > 60:
        raise JubakoError("A view's name cannot contain a colon, and must be 60 letters or fewer.")
    info = storage.describe_table(table)
    spec = normalise_filter(info.fields, filter_spec)
    if spec is None:
        raise JubakoError("Apply a filter first, then save it as a view.")
    existing = get_view(storage, table, name)
    if existing and not replace:
        raise JubakoError(f"There is already a view called “{name}” for {table}. Pick another name, or replace it.")
    if default is None:
        default = bool(existing and existing.get("default"))
    if default:
        for other in list_views(storage, table):
            if other["name"] != name and other.get("default"):
                _write(storage, {**other, "default": False})
    view = {"name": name, "table": table, "filter": spec, "default": bool(default),
            "words": filter_words(info.fields, spec)}
    _write(storage, view)
    view["replaced"] = bool(existing)
    return view


def get_view(storage: Storage, table: str, name: str) -> dict[str, Any] | None:
    raw = storage.get_info(_key(table, (name or "").strip()), "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def list_views(storage: Storage, table: str | None = None) -> list[dict[str, Any]]:
    rows = storage.query(
        f"SELECT {storage.quote('key')}, {storage.quote('value')} FROM {storage.quote('jubako_info')}"
    )
    out = []
    for key, value in rows:
        key = str(key)
        if not key.startswith(VIEW_KEY):
            continue
        try:
            view = json.loads(value)
        except ValueError:
            continue
        if table and view.get("table") != table:
            continue
        out.append(view)
    return sorted(out, key=lambda v: (v.get("table", ""), v.get("name", "").lower()))


def default_view(storage: Storage, table: str) -> dict[str, Any] | None:
    for view in list_views(storage, table):
        if view.get("default"):
            return view
    return None


def delete_view(storage: Storage, table: str, name: str) -> bool:
    if get_view(storage, table, name) is None:
        return False
    _forget(storage, _key(table, (name or "").strip()))
    return True


def rename_view(storage: Storage, table: str, old: str, new: str) -> dict[str, Any]:
    view = get_view(storage, table, old)
    if view is None:
        raise JubakoError(f"There is no view called “{old}” for {table}.")
    new = (new or "").strip()
    if not new:
        raise JubakoError("Give the view a name.")
    if new != old and get_view(storage, table, new):
        raise JubakoError(f"There is already a view called “{new}” for {table}.")
    _forget(storage, _key(table, old))
    view["name"] = new
    _write(storage, view)
    return view


def retarget_views(storage: Storage, table: str, old: str, new: str | None) -> list[str]:
    """A field was renamed (`new`) or dropped (`new` None): fix or forget the views on it."""
    touched = []
    for view in list_views(storage, table):
        spec = view.get("filter") or {}
        if spec.get("field") != old:
            continue
        if new:
            view["filter"] = {**spec, "field": new}
            try:
                fields = storage.describe_table(table).fields
                view["words"] = filter_words(fields, normalise_filter(fields, view["filter"]))
            except JubakoError:
                pass
            _write(storage, view)
        else:
            _forget(storage, _key(table, view["name"]))
        touched.append(view["name"])
    return touched


def forget_views(storage: Storage, table: str) -> list[str]:
    names = []
    for view in list_views(storage, table):
        _forget(storage, _key(table, view["name"]))
        names.append(view["name"])
    return names


def _write(storage: Storage, view: dict[str, Any]) -> None:
    storage.set_info(_key(view["table"], view["name"]), json.dumps(view))


def _forget(storage: Storage, key: str) -> None:
    storage.execute(
        f"DELETE FROM {storage.quote('jubako_info')} WHERE {storage.quote('key')} = {storage.placeholder(0)}",
        (key,),
    )
    storage.commit()
