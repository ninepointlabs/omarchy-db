"""The bridge: the only way the QML window talks to the Omarchy-DB library.

Every slot returns a plain dict the QML can read (`ok`, `error`, and whatever
the call produced). Nothing here knows SQL; it calls the same functions the
command line and the MCP server use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)

from omarchy_db import catalog
from omarchy_db.errors import OmarchyDBError
from omarchy_db.importer import import_spreadsheet, plan_import
from omarchy_db.paths import default_documents_dir, home
from omarchy_db.storage import BACKENDS, SQLITE, Storage, create_database, open_database

PAGE_SIZE = 500

BACKEND_WORDS = {"sqlite": "File", "postgres": "PostgreSQL", "mysql": "MySQL / MariaDB"}


def _cell_text(value: Any, kind: str | None) -> str:
    if value is None:
        return ""
    if kind == "boolean":
        return "Yes" if value else "No"
    return str(value)


class RowsModel(QAbstractTableModel):
    """One table's rows, the way `TableView` wants them: a grid of strings."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._headings: list[str] = []
        self._kinds: list[str | None] = []
        self._rows: list[list[str]] = []

    def load(self, page: dict[str, Any]) -> None:
        self.beginResetModel()
        self._headings = ["#"] + [field["label"] for field in page["fields"]]
        self._kinds = [None] + [field["type"] for field in page["fields"]]
        self._rows = [
            [_cell_text(value, self._kinds[i] if i < len(self._kinds) else None)
             for i, value in enumerate(row)]
            for row in page["rows"]
        ]
        self.endResetModel()

    def clear(self) -> None:
        self.load({"fields": [], "rows": []})
        self.beginResetModel()
        self._headings = []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._headings)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        column = index.column()
        return row[column] if column < len(row) else ""

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headings[section] if section < len(self._headings) else ""
        return section + 1

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {Qt.ItemDataRole.DisplayRole: b"display"}

    @Slot(int, result=int)
    def columnWidth(self, column: int) -> int:  # noqa: N802
        """A width that fits the longest cell in the column, within reason."""
        if column >= len(self._headings):
            return 120
        longest = len(self._headings[column])
        for row in self._rows[:200]:
            if column < len(row):
                longest = max(longest, len(row[column]))
        return int(min(max(60, longest * 9 + 28), 360))

    @Slot(int, result=str)
    def kindAt(self, column: int) -> str:  # noqa: N802
        kind = self._kinds[column] if column < len(self._kinds) else None
        return kind or "id"


class Bridge(QObject):
    """Open one database at a time and answer the window's questions about it."""

    databaseChanged = Signal()
    tablesChanged = Signal()
    tableChanged = Signal()
    message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage: Storage | None = None
        self._tables: list[dict[str, Any]] = []
        self._current_table = ""
        self._shown = 0
        self._total = 0
        self._rows = RowsModel(self)

    # -- what the window can read ---------------------------------------
    @Property(QObject, constant=True)
    def rows(self) -> RowsModel:
        return self._rows

    @Property(bool, notify=databaseChanged)
    def isOpen(self) -> bool:  # noqa: N802
        return self._storage is not None

    @Property(str, notify=databaseChanged)
    def title(self) -> str:
        return self._storage.title if self._storage else ""

    @Property(str, notify=databaseChanged)
    def location(self) -> str:
        return self._storage.location() if self._storage else ""

    @Property(str, notify=databaseChanged)
    def backendWord(self) -> str:  # noqa: N802
        return BACKEND_WORDS.get(self._storage.backend, "") if self._storage else ""

    @Property("QVariantList", notify=tablesChanged)
    def tables(self) -> list[dict[str, Any]]:
        return list(self._tables)

    @Property(str, notify=tableChanged)
    def currentTable(self) -> str:  # noqa: N802
        return self._current_table

    @Property(int, notify=tableChanged)
    def shownRows(self) -> int:  # noqa: N802
        return self._shown

    @Property(int, notify=tableChanged)
    def totalRows(self) -> int:  # noqa: N802
        return self._total

    # -- lists for the home screen and the chooser ------------------------
    @Slot(result="QVariantList")
    def backends(self) -> list[dict[str, Any]]:
        return [
            {
                "key": choice.key,
                "title": choice.title,
                "blurb": choice.blurb,
                "needsServer": choice.needs_server,
                "ready": choice.driver_installed(),
                "driver": choice.driver_package,
            }
            for choice in BACKENDS
        ]

    @Slot(result="QVariantList")
    def recent(self) -> list[dict[str, Any]]:
        out = []
        for entry in catalog.recent():
            backend = entry.get("backend", SQLITE)
            out.append(
                {
                    "title": entry.get("title") or "Database",
                    "backend": backend,
                    "backendWord": BACKEND_WORDS.get(backend, backend),
                    "path": entry.get("path", ""),
                    "where": entry.get("where", ""),
                    "lastOpened": entry.get("last_opened", ""),
                }
            )
        return out

    @Slot(result=str)
    def documentsFolder(self) -> str:  # noqa: N802
        return QUrl.fromLocalFile(str(default_documents_dir())).toString()

    @Slot(result=str)
    def homeFolder(self) -> str:  # noqa: N802
        return QUrl.fromLocalFile(str(home())).toString()

    @Slot(str, result=str)
    def localPath(self, url: str) -> str:  # noqa: N802
        """`file:///home/tim/x.omadb` -> `/home/tim/x.omadb`."""
        parsed = QUrl(url)
        return parsed.toLocalFile() if parsed.isLocalFile() else url

    @Slot(str, result=str)
    def suggestedDatabaseName(self, spreadsheet: str) -> str:  # noqa: N802
        stem = Path(self.localPath(spreadsheet)).stem or "my-database"
        return f"{stem}.omadb"

    # -- making and opening --------------------------------------------------
    @Slot(str, str, str, "QVariantMap", result="QVariantMap")
    def newDatabase(self, backend: str, path: str, title: str, connection: dict) -> dict:  # noqa: N802
        connection = {k: v for k, v in dict(connection).items() if v not in ("", None)}
        try:
            storage = create_database(
                title=title, backend=backend or SQLITE, path=self.localPath(path) or None,
                overwrite=backend in ("", SQLITE), connection=connection,
            )
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._adopt(storage)
        self.message.emit("New database made. Now import a spreadsheet.")
        return {"ok": True}

    @Slot(str, str, "QVariantMap", result="QVariantMap")
    def openDatabase(self, backend: str, path: str, connection: dict) -> dict:  # noqa: N802
        connection = {k: v for k, v in dict(connection).items() if v not in ("", None)}
        try:
            storage = open_database(
                backend=backend or SQLITE, path=self.localPath(path) or None, connection=connection
            )
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._adopt(storage)
        return {"ok": True}

    @Slot(int, result="QVariantMap")
    def openRecent(self, index: int) -> dict:  # noqa: N802
        entries = catalog.recent()
        if index < 0 or index >= len(entries):
            return {"ok": False, "error": "That database is not in the list any more."}
        entry = entries[index]
        backend = entry.get("backend", SQLITE)
        if backend == SQLITE:
            result = self.openDatabase(SQLITE, entry.get("path", ""), {})
            if not result["ok"]:
                catalog.forget(backend=SQLITE, path=entry.get("path", ""))
            return result
        # A server: we remember where it is, never the password, so ask.
        return {
            "ok": False,
            "needsConnection": True,
            "backend": backend,
            "title": entry.get("title", ""),
            "connection": _parse_where(backend, entry.get("where", "")),
        }

    @Slot(str, str, result="QVariantMap")
    def importIntoNew(self, spreadsheet: str, database_path: str) -> dict:  # noqa: N802
        """The first-run path: a spreadsheet becomes a brand new database."""
        title = Path(self.localPath(spreadsheet)).stem.replace("_", " ").replace("-", " ").title()
        made = self.newDatabase(SQLITE, database_path, title, {})
        if not made["ok"]:
            return made
        return self.importSpreadsheet(spreadsheet, True)

    @Slot(str, bool, result="QVariantMap")
    def importSpreadsheet(self, spreadsheet: str, replace: bool) -> dict:  # noqa: N802
        if self._storage is None:
            return {"ok": False, "error": "Open a database first."}
        path = self.localPath(spreadsheet)
        try:
            plan = plan_import(path)
            if not replace and self._storage.has_table(plan["table"]):
                return {"ok": False, "needsConfirm": True, "table": plan["table"]}
            report = import_spreadsheet(
                self._storage, path, if_exists="replace" if replace else "error"
            )
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables(select=report["table"])
        self.message.emit(f"Added {report['rows_added']} rows to {report['table']}.")
        return {"ok": True, "table": report["table"], "rowsAdded": report["rows_added"],
                "noteCount": report["note_count"]}

    @Slot(str, result="QVariantMap")
    def selectTable(self, table: str) -> dict:  # noqa: N802
        if self._storage is None:
            return {"ok": False, "error": "Open a database first."}
        try:
            page = self._storage.list_rows(table, limit=PAGE_SIZE)
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._rows.load(page)
        self._current_table = table
        self._shown = len(page["rows"])
        self._total = page["total"]
        self.tableChanged.emit()
        return {"ok": True, "shown": self._shown, "total": self._total}

    @Slot()
    def refresh(self) -> None:
        if self._storage is not None:
            self._refresh_tables(select=self._current_table)

    @Slot()
    def closeDatabase(self) -> None:  # noqa: N802
        if self._storage is not None:
            try:
                self._storage.close()
            except Exception:  # noqa: BLE001 - a stale handle must not stop us
                pass
        self._storage = None
        self._tables = []
        self._current_table = ""
        self._shown = self._total = 0
        self._rows.clear()
        self.tablesChanged.emit()
        self.tableChanged.emit()
        self.databaseChanged.emit()

    # -- inside --------------------------------------------------------------
    def _adopt(self, storage: Storage) -> None:
        if self._storage is not None:
            try:
                self._storage.close()
            except Exception:  # noqa: BLE001
                pass
        self._storage = storage
        info = storage.describe()
        catalog.remember(
            title=info.title,
            backend=info.backend,
            path=info.location if info.backend == SQLITE else "",
            where="" if info.backend == SQLITE else info.location,
        )
        self.databaseChanged.emit()
        self._refresh_tables()

    def _refresh_tables(self, *, select: str = "") -> None:
        assert self._storage is not None
        tables = []
        for name in self._storage.list_tables():
            try:
                info = self._storage.describe_table(name)
                tables.append({"name": name, "rows": info.row_count})
            except OmarchyDBError:
                tables.append({"name": name, "rows": 0})
        self._tables = tables
        self.tablesChanged.emit()
        names = [t["name"] for t in tables]
        if select and select in names:
            self.selectTable(select)
        elif names:
            self.selectTable(names[0])
        else:
            self._rows.clear()
            self._current_table = ""
            self._shown = self._total = 0
            self.tableChanged.emit()


def _parse_where(backend: str, where: str) -> dict[str, str]:
    """Turn the remembered location back into connection fields (no password)."""
    fields = {"host": "", "port": "", "database": "", "user": ""}
    if backend == "postgres":
        if "://" in where:
            fields["url"] = where.replace(":***@", "@")
            return fields
        for chunk in where.split():
            key, _, value = chunk.partition("=")
            if key == "dbname":
                fields["database"] = value
            elif key in fields:
                fields[key] = value
        return fields
    # mysql: user@host:port/database
    user, _, rest = where.rpartition("@")
    fields["user"] = user
    hostport, _, database = rest.partition("/")
    host, _, port = hostport.partition(":")
    fields.update(host=host, port=port, database=database)
    return fields
