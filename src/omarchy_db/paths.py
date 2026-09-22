"""Where files may live, and how we refuse the ones that may not.

Omarchy-DB (and especially the MCP server, which agents drive) only ever
touches files under roots the user approved. By default that is the user's
home directory. `OMARCHY_DB_ROOTS` can widen or narrow it (a `:`-separated
list, same shape as `PATH`).
"""

from __future__ import annotations

import os
from pathlib import Path

from .errors import PathNotAllowed

STATE_DIR_NAME = "omarchy-db"
DB_SUFFIX = ".omadb"


def home() -> Path:
    return Path(os.path.expanduser("~")).resolve()


def state_dir() -> Path:
    """`~/.local/state/omarchy-db/`, created on demand, owner-only."""
    base = os.environ.get("XDG_STATE_HOME") or str(home() / ".local" / "state")
    path = Path(base).expanduser() / STATE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def default_documents_dir() -> Path:
    """Where new databases go when the user does not pick a folder."""
    configured = os.environ.get("OMARCHY_DB_DEFAULT_DIR")
    if configured:
        return Path(configured).expanduser()
    documents = home() / "Documents"
    return documents if documents.is_dir() else home()


def allowed_roots() -> list[Path]:
    """The folders Omarchy-DB will read and write."""
    configured = os.environ.get("OMARCHY_DB_ROOTS")
    if configured:
        roots = []
        for chunk in configured.split(os.pathsep):
            chunk = chunk.strip()
            if chunk:
                roots.append(Path(chunk).expanduser().resolve())
        if roots:
            return roots
    return [home()]


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_under_roots(raw: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    """Resolve a path and prove it stays inside an approved root.

    Symlinks are followed before the check, so a link that points out of the
    approved area is refused too. Raises `PathNotAllowed` when it escapes.
    """
    if raw is None or str(raw).strip() == "":
        raise PathNotAllowed("No path was given.")

    text = str(raw)
    if "\x00" in text:
        raise PathNotAllowed("That path is not a real file path.")

    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    # Resolve the deepest part that exists, then re-attach the rest. This
    # catches "../.." traversal and symlinked parents even for new files.
    resolved = _resolve_strictish(candidate)

    roots = allowed_roots()
    if not any(_is_within(resolved, root) or resolved == root for root in roots):
        pretty = ", ".join(str(root) for root in roots)
        raise PathNotAllowed(
            f"That file is outside the folders Omarchy-DB may use ({pretty}): {resolved}"
        )

    if must_exist and not resolved.exists():
        raise PathNotAllowed(f"There is no file at {resolved}")
    return resolved


def _resolve_strictish(candidate: Path) -> Path:
    existing = candidate
    tail: list[str] = []
    while not existing.exists():
        if existing.parent == existing:
            break
        tail.append(existing.name)
        existing = existing.parent
    resolved = existing.resolve()
    for name in reversed(tail):
        if name in ("..", "."):
            # Cannot happen after expanduser+resolve of the existing part, but
            # refuse loudly rather than silently walking upward.
            raise PathNotAllowed("That path tries to step outside its folder.")
        resolved = resolved / name
    return resolved


def database_path(raw: str | os.PathLike[str]) -> Path:
    """Approve a path for a SQLite database file, adding `.omadb` if missing."""
    path = resolve_under_roots(raw)
    if path.suffix.lower() not in (DB_SUFFIX, ".sqlite", ".sqlite3", ".db"):
        path = path.with_name(path.name + DB_SUFFIX)
    return path
