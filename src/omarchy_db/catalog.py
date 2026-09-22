"""The list of databases the user has made or opened.

Kept in `~/.local/state/omarchy-db/databases.json`, owner-readable only.
Passwords are never written here: for a server database we remember how to
find it, not how to log in.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Any

from .paths import state_dir

CATALOG_NAME = "databases.json"
MAX_ENTRIES = 50


def catalog_path():
    return state_dir() / CATALOG_NAME


def load() -> list[dict[str, Any]]:
    path = catalog_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return [entry for entry in data.get("databases", []) if isinstance(entry, dict)]


def save(entries: list[dict[str, Any]]) -> None:
    path = catalog_path()
    payload = {"version": 1, "databases": entries[:MAX_ENTRIES]}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _key(entry: dict[str, Any]) -> tuple:
    return (entry.get("backend", ""), entry.get("path", ""), entry.get("where", ""))


def remember(
    *,
    title: str,
    backend: str,
    path: str = "",
    where: str = "",
) -> dict[str, Any]:
    """Put a database at the top of the recent list."""
    entry = {
        "title": title,
        "backend": backend,
        "path": path,
        "where": where,
        "last_opened": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    entries = [item for item in load() if _key(item) != _key(entry)]
    entries.insert(0, entry)
    save(entries)
    return entry


def forget(*, backend: str, path: str = "", where: str = "") -> None:
    target = {"backend": backend, "path": path, "where": where}
    save([item for item in load() if _key(item) != _key(target)])


def recent(limit: int = 20) -> list[dict[str, Any]]:
    return load()[: max(1, limit)]
