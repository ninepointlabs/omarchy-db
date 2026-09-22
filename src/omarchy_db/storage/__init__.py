"""Pick a backend and open a database.

Three engines, locked for v1:

- `sqlite`   — one file on your computer. The default; nothing to install.
- `postgres` — a PostgreSQL server you already have.
- `mysql`    — a MySQL or MariaDB server you already have.

The GUI, the CLI and the MCP server all come through here, so they behave
the same way whichever engine a database uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import BackendNotAvailable, OmarchyDBError
from .base import DatabaseInfo, Storage, TableInfo
from .sqlite import SQLiteStorage

SQLITE = "sqlite"
POSTGRES = "postgres"
MYSQL = "mysql"

#: Names people may type that mean the same engine.
ALIASES = {
    "sqlite3": SQLITE,
    "file": SQLITE,
    "postgresql": POSTGRES,
    "pg": POSTGRES,
    "mariadb": MYSQL,
    "mysql/mariadb": MYSQL,
}


@dataclass(frozen=True)
class BackendChoice:
    """What the "New database" screen shows for one engine."""

    key: str
    title: str
    blurb: str
    needs_server: bool
    driver_package: str = ""

    def driver_installed(self) -> bool:
        if self.key == SQLITE:
            return True
        module = {POSTGRES: "psycopg", MYSQL: "pymysql"}[self.key]
        try:
            __import__(module)
        except ImportError:
            return False
        return True


BACKENDS: tuple[BackendChoice, ...] = (
    BackendChoice(
        key=SQLITE,
        title="Just a file on this computer",
        blurb="The simple one. Your database is a single file you can copy, back up or email.",
        needs_server=False,
    ),
    BackendChoice(
        key=POSTGRES,
        title="A PostgreSQL server",
        blurb="Use a PostgreSQL server you already have. You will need its address and login.",
        needs_server=True,
        driver_package="psycopg",
    ),
    BackendChoice(
        key=MYSQL,
        title="A MySQL or MariaDB server",
        blurb="Use a MySQL or MariaDB server you already have. You will need its address and login.",
        needs_server=True,
        driver_package="PyMySQL",
    ),
)

BACKEND_KEYS = tuple(choice.key for choice in BACKENDS)


def normalise_backend(backend: str | None) -> str:
    key = (backend or SQLITE).strip().lower()
    key = ALIASES.get(key, key)
    if key not in BACKEND_KEYS:
        known = ", ".join(BACKEND_KEYS)
        raise OmarchyDBError(f"Unknown backend {backend!r}. Pick one of: {known}.")
    return key


def backend_choice(backend: str) -> BackendChoice:
    key = normalise_backend(backend)
    return next(choice for choice in BACKENDS if choice.key == key)


def create_database(
    *,
    title: str = "",
    backend: str = SQLITE,
    path: str | None = None,
    overwrite: bool = False,
    connection: dict[str, Any] | None = None,
) -> Storage:
    """Make a new database and hand back an open connection to it."""
    key = normalise_backend(backend)
    connection = dict(connection or {})

    if key == SQLITE:
        if not path:
            raise OmarchyDBError("Choose where to save the database file.")
        return SQLiteStorage.create(path, title=title, overwrite=overwrite)

    if key == POSTGRES:
        from .postgres import PostgresStorage, connection_string

        return PostgresStorage.create(
            connection_string(**_postgres_args(connection)), title=title, overwrite=overwrite
        )

    from .mysql import MySQLStorage

    return MySQLStorage.create(title=title, overwrite=overwrite, **_mysql_args(connection))


def open_database(
    *,
    backend: str = SQLITE,
    path: str | None = None,
    connection: dict[str, Any] | None = None,
) -> Storage:
    """Open a database that already exists."""
    key = normalise_backend(backend)
    connection = dict(connection or {})

    if key == SQLITE:
        if not path:
            raise OmarchyDBError("Which database file should be opened?")
        return SQLiteStorage.open(path)

    if key == POSTGRES:
        from .postgres import PostgresStorage, connection_string

        return PostgresStorage.open(connection_string(**_postgres_args(connection)))

    from .mysql import MySQLStorage

    return MySQLStorage.open(**_mysql_args(connection))


def _postgres_args(connection: dict[str, Any]) -> dict[str, Any]:
    allowed = {"host", "port", "database", "user", "password", "url"}
    extra = set(connection) - allowed
    if extra:
        raise OmarchyDBError(f"PostgreSQL does not take {sorted(extra)[0]!r}.")
    args = {k: v for k, v in connection.items() if v not in (None, "")}
    if not args.get("url") and not args.get("database"):
        raise OmarchyDBError("Tell Omarchy-DB which PostgreSQL database to use.")
    args.setdefault("host", "localhost")
    args.setdefault("port", 5432)
    return args


def _mysql_args(connection: dict[str, Any]) -> dict[str, Any]:
    allowed = {"host", "port", "database", "user", "password"}
    extra = set(connection) - allowed
    if extra:
        raise OmarchyDBError(f"MySQL / MariaDB does not take {sorted(extra)[0]!r}.")
    args = {k: v for k, v in connection.items() if v not in (None, "")}
    if not args.get("database"):
        raise OmarchyDBError("Tell Omarchy-DB which MySQL/MariaDB database to use.")
    args.setdefault("host", "localhost")
    args.setdefault("port", 3306)
    return args


__all__ = [
    "BACKENDS",
    "BACKEND_KEYS",
    "MYSQL",
    "POSTGRES",
    "SQLITE",
    "BackendChoice",
    "BackendNotAvailable",
    "DatabaseInfo",
    "Storage",
    "TableInfo",
    "backend_choice",
    "create_database",
    "normalise_backend",
    "open_database",
]
