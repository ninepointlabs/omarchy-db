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
    QThread,
    QUrl,
    Signal,
    Slot,
)

from omarchy_db import catalog, schema
from omarchy_db.errors import OmarchyDBError
from omarchy_db.exporter import export_table
from omarchy_db.fields import FIELD_TYPE_LABELS, FIELD_TYPES, Field
from omarchy_db.importer import import_spreadsheet, import_workbook, plan_import, workbook_plan
from omarchy_db.paths import default_documents_dir, home
from omarchy_db.reports import form_for
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
        self._names: list[str] = []
        self._rows: list[list[str]] = []
        self._raw: list[list[Any]] = []
        #: Called with (row_id, field_name, new_text) when a cell is edited in the grid.
        self.editor: Any = None

    def load(self, page: dict[str, Any]) -> None:
        self.beginResetModel()
        self._headings = ["#"] + [field["label"] for field in page["fields"]]
        self._kinds = [None] + [field["type"] for field in page["fields"]]
        self._names = ["id"] + [field["name"] for field in page["fields"]]
        self._raw = [list(row) for row in page["rows"]]
        self._rows = [
            [_cell_text(value, self._kinds[i] if i < len(self._kinds) else None)
             for i, value in enumerate(row)]
            for row in self._raw
        ]
        self.endResetModel()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.isValid() and index.column() > 0:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        """An edit made in the grid. The bridge writes it and reloads the table."""
        if not index.isValid() or index.column() == 0 or self.editor is None:
            return False
        if role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.DisplayRole):
            return False
        row = index.row()
        if row >= len(self._raw) or index.column() >= len(self._names):
            return False
        return bool(self.editor(self._raw[row][0], self._names[index.column()], value))

    @Slot(int, result=int)
    def rowId(self, row: int) -> int:  # noqa: N802
        if 0 <= row < len(self._raw):
            return int(self._raw[row][0])
        return 0

    @Slot(int, result=int)
    def rowIndexOf(self, row_id: int) -> int:  # noqa: N802
        for index, row in enumerate(self._raw):
            if int(row[0]) == int(row_id):
                return index
        return -1

    @Slot(int, result="QVariantMap")
    def record(self, row: int) -> dict[str, Any]:
        """One row for the form: field name -> value (yes/no as true/false, blanks as "")."""
        if not (0 <= row < len(self._raw)):
            return {"id": 0, "values": {}}
        values: dict[str, Any] = {}
        for column, name in enumerate(self._names):
            if column == 0:
                continue
            raw = self._raw[row][column]
            if self._kinds[column] == "boolean":
                values[name] = bool(raw) if raw is not None else False
            else:
                values[name] = "" if raw is None else str(raw)
        return {"id": int(self._raw[row][0]), "values": values}

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


class Job(QThread):
    """Run one function off the GUI thread and hand its result back as a dict."""

    done = Signal("QVariantMap")

    def __init__(self, work, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._work = work

    def run(self) -> None:
        try:
            result = dict(self._work())
            result.setdefault("ok", True)
        except OmarchyDBError as error:
            result = {"ok": False, "error": str(error)}
        except Exception as error:  # noqa: BLE001 - the window must hear about it, not crash
            result = {"ok": False, "error": f"Something went wrong: {error}"}
        self.done.emit(result)


class Bridge(QObject):
    """Open one database at a time and answer the window's questions about it."""

    databaseChanged = Signal()
    tablesChanged = Signal()
    tableChanged = Signal()
    busyChanged = Signal()
    importFinished = Signal("QVariantMap")
    message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage: Storage | None = None
        self._tables: list[dict[str, Any]] = []
        self._current_table = ""
        self._shown = 0
        self._total = 0
        self._rows = RowsModel(self)
        self._rows.editor = self._edit_cell
        self._fields: list[dict[str, Any]] = []
        self._form_fields: list[dict[str, Any]] = []
        self._job: Job | None = None
        self._busy_text = ""

    def storage(self) -> Storage | None:
        return self._storage

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._job is not None

    @Property(str, notify=busyChanged)
    def busyText(self) -> str:  # noqa: N802
        return self._busy_text

    def _start(self, text: str, work, on_done) -> dict:
        if self._job is not None:
            return {"ok": False, "error": "Still working on the last thing. One moment."}
        self._busy_text = text
        self._job = Job(work, self)

        def finished(result: dict) -> None:
            job = self._job
            self._job = None
            self._busy_text = ""
            self.busyChanged.emit()
            if job is not None:
                job.deleteLater()
            on_done(dict(result))

        self._job.done.connect(finished)
        self._job.start()
        self.busyChanged.emit()
        return {"ok": True, "pending": True}

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

    @Property(bool, notify=databaseChanged)
    def isLocalFile(self) -> bool:  # noqa: N802
        """True for a .omadb on this computer: the only kind the app will delete."""
        return bool(self._storage) and self._storage.backend == SQLITE

    @Property("QVariantList", notify=tablesChanged)
    def tables(self) -> list[dict[str, Any]]:
        return list(self._tables)

    @Property(str, notify=tableChanged)
    def currentTable(self) -> str:  # noqa: N802
        return self._current_table

    @Property("QVariantList", notify=tableChanged)
    def fields(self) -> list[dict[str, Any]]:
        """The current table's fields: name, label, type. What the form is built from."""
        return list(self._fields)

    @Property("QVariantList", notify=tableChanged)
    def formFields(self) -> list[dict[str, Any]]:  # noqa: N802
        """The fields in the order and with the labels the table's form asks for."""
        return list(self._form_fields)

    @Slot(result="QVariantList")
    def fieldTypes(self) -> list[dict[str, str]]:  # noqa: N802
        return [{"key": key, "label": FIELD_TYPE_LABELS[key]} for key in FIELD_TYPES]

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

    @Slot(int, result="QVariantMap")
    def removeRecent(self, index: int) -> dict:  # noqa: N802
        """Forget a database in the recent list. The database itself is untouched."""
        entries = catalog.recent()
        if index < 0 or index >= len(entries):
            return {"ok": False, "error": "That database is not in the list any more."}
        entry = entries[index]
        catalog.forget(backend=entry.get("backend", SQLITE), path=entry.get("path", ""), where=entry.get("where", ""))
        return {"ok": True}

    @Slot(int, result="QVariantMap")
    def deleteRecentFile(self, index: int) -> dict:  # noqa: N802
        """Delete a database file from the recent list, for good."""
        entries = catalog.recent()
        if index < 0 or index >= len(entries):
            return {"ok": False, "error": "That database is not in the list any more."}
        entry = entries[index]
        if entry.get("backend", SQLITE) != SQLITE or not entry.get("path"):
            return {"ok": False, "error": "Only a database file on this computer can be deleted here."}
        path = entry["path"]
        if self._storage is not None and self._storage.backend == SQLITE and self._storage.location() == path:
            return self.deleteDatabase()
        try:
            schema.delete_database_file(None, path)
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self.message.emit(f"Deleted {Path(path).name}.")
        return {"ok": True}

    @Slot(result="QVariantMap")
    def deleteDatabase(self) -> dict:  # noqa: N802
        """Delete the open database file and go back to Home. Server databases are never dropped."""
        if self._storage is None:
            return {"ok": False, "error": "No database is open."}
        if self._storage.backend != SQLITE:
            return {"ok": False, "error": "Only a database file on this computer can be deleted here. "
                    "A server database is left alone."}
        path = self._storage.location()
        storage, self._storage = self._storage, None
        try:
            schema.delete_database_file(storage, path)
        except OmarchyDBError as error:
            self._storage = storage
            return {"ok": False, "error": str(error)}
        self._tables = []
        self._current_table = ""
        self._shown = self._total = 0
        self._rows.clear()
        self.tablesChanged.emit()
        self.tableChanged.emit()
        self.databaseChanged.emit()
        self.message.emit(f"Deleted {Path(path).name}.")
        return {"ok": True, "file": path}

    @Slot(str, str, result="QVariantMap")
    def importIntoNew(self, spreadsheet: str, database_path: str) -> dict:  # noqa: N802
        """The first-run path: a spreadsheet becomes a brand new database."""
        title = Path(self.localPath(spreadsheet)).stem.replace("_", " ").replace("-", " ").title()
        made = self.newDatabase(SQLITE, database_path, title, {})
        if not made["ok"]:
            return made
        return self.importSpreadsheet(spreadsheet, True)

    @Slot(str, str, result="QVariantMap")
    def planImport(self, spreadsheet: str, sheet: str) -> dict:  # noqa: N802
        """What a spreadsheet would become: the wizard shows this and lets people change it."""
        try:
            plan = plan_import(self.localPath(spreadsheet), sheet=sheet or None)
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        plan["ok"] = True
        plan["exists"] = bool(self._storage and self._storage.has_table(plan["table"]))
        return plan

    @Slot(str, str, str, "QVariantList", bool, result="QVariantMap")
    def importPlanned(self, spreadsheet: str, sheet: str, table: str, fields: list, replace: bool) -> dict:  # noqa: N802
        """Import with the wizard's choices: table name and each column's type.

        For a file database the work runs on a worker thread with its own
        connection, so a big spreadsheet does not freeze the window; the result
        arrives through `importFinished`. A server database imports in place.
        """
        if self._storage is None:
            return {"ok": False, "error": "Open a database first."}
        path = self.localPath(spreadsheet)
        try:
            chosen = [Field(name=f["name"], type=f["type"], label=f.get("label") or None) for f in fields] or None
            table = (table or "").strip() or None
            if not replace:
                plan = plan_import(path, sheet=sheet or None)
                if self._storage.has_table(table or plan["table"]):
                    return {"ok": False, "needsConfirm": True, "table": table or plan["table"]}
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}

        if_exists = "replace" if replace else "error"

        if self._storage.backend != SQLITE:
            try:
                report = import_spreadsheet(
                    self._storage, path, table=table, fields=chosen, sheet=sheet or None, if_exists=if_exists
                )
            except (ValueError, OmarchyDBError) as error:
                return {"ok": False, "error": str(error)}
            return self._imported(report)

        location = self._storage.location()

        def work() -> dict:
            with open_database(backend=SQLITE, path=location) as own:
                return import_spreadsheet(
                    own, path, table=table, fields=chosen, sheet=sheet or None, if_exists=if_exists
                )

        def done(result: dict) -> None:
            if result.get("ok", True) and "table" in result:
                result = self._imported(result)
            self.importFinished.emit(result)

        return self._start("Importing…", work, done)

    def _imported(self, report: dict) -> dict:
        self._refresh_tables(select=report["table"])
        note = f" {report['note_count']} cells did not fit and were kept as words." if report["note_count"] else ""
        self.message.emit(f"Added {report['rows_added']} rows to {report['table']}.{note}")
        return {"ok": True, "table": report["table"], "rowsAdded": report["rows_added"],
                "noteCount": report["note_count"], "notes": list(report["notes"])}

    @Slot(str, result="QVariantList")
    def workbookPlan(self, spreadsheet: str) -> list:  # noqa: N802
        """Each sheet and the table it would become, and whether that table exists."""
        try:
            plan = workbook_plan(self.localPath(spreadsheet))
        except OmarchyDBError:
            return []
        for item in plan:
            item["exists"] = bool(self._storage and self._storage.has_table(item["table"]))
        return plan

    @Slot(str, bool, result="QVariantMap")
    def importAllSheets(self, spreadsheet: str, replace: bool) -> dict:  # noqa: N802
        """Every sheet becomes its own table, with guessed types. One confirm covers all clashes."""
        if self._storage is None:
            return {"ok": False, "error": "Open a database first."}
        path = self.localPath(spreadsheet)
        if not replace:
            clashes = [item["table"] for item in self.workbookPlan(spreadsheet) if item["exists"]]
            if clashes:
                return {"ok": False, "needsConfirm": True, "tables": clashes, "table": clashes[0]}
        if_exists = "replace" if replace else "error"

        if self._storage.backend != SQLITE:
            try:
                report = import_workbook(self._storage, path, if_exists=if_exists)
            except OmarchyDBError as error:
                return {"ok": False, "error": str(error)}
            return self._imported_all(report)

        location = self._storage.location()

        def work() -> dict:
            with open_database(backend=SQLITE, path=location) as own:
                return import_workbook(own, path, if_exists=if_exists)

        def done(result: dict) -> None:
            if result.get("ok", True) and "tables" in result:
                result = self._imported_all(result)
            self.importFinished.emit(result)

        return self._start("Importing every sheet\u2026", work, done)

    def _imported_all(self, report: dict) -> dict:
        tables = [item["table"] for item in report["tables"]]
        errors = [f"{item['sheet']}: {item['error']}" for item in report["errors"]]
        self._refresh_tables(select=tables[0] if tables else self._current_table)
        if tables:
            word = "table" if len(tables) == 1 else "tables"
            text = f"Made {len(tables)} {word}: {', '.join(tables)}."
            if errors:
                text += f" Skipped {len(errors)} sheet{'s' if len(errors) != 1 else ''}."
            self.message.emit(text)
        return {"ok": bool(tables), "tables": tables, "errors": errors,
                "error": "" if tables else ("Nothing was imported. " + " ".join(errors))}

    # -- fields and tables ------------------------------------------------------
    @Slot(str, str, str, result="QVariantMap")
    def renameField(self, old: str, new: str, label: str) -> dict:  # noqa: N802
        """Change a field's name and/or label. Blank name means keep it."""
        if self._storage is None or not self._current_table:
            return {"ok": False, "error": "Pick a table first."}
        new = (new or "").strip() or old
        try:
            result = schema.rename_field(
                self._storage, self._current_table, old, new, label=(label or "").strip() or None
            )
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables(select=self._current_table)
        self.message.emit(f"Renamed {old} to {new}." if new != old else f"Relabelled {new}.")
        return {"ok": True, "fields": result["fields"]}

    @Slot(str, result="QVariantMap")
    def deleteField(self, name: str) -> dict:  # noqa: N802
        if self._storage is None or not self._current_table:
            return {"ok": False, "error": "Pick a table first."}
        try:
            result = schema.drop_field(self._storage, self._current_table, name)
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables(select=self._current_table)
        self.message.emit(f"Deleted the field {name}.")
        return {"ok": True, "fields": result["fields"]}

    @Slot(str, result="QVariantMap")
    def deleteTable(self, table: str) -> dict:  # noqa: N802
        if self._storage is None:
            return {"ok": False, "error": "Open a database first."}
        try:
            result = schema.drop_table(self._storage, table)
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables()
        self.message.emit(f"Deleted the table {table} and its {result['rows_deleted']} rows.")
        return {"ok": True, "rowsDeleted": result["rows_deleted"]}

    @Slot(str, str, result="QVariantMap")
    def exportTable(self, url: str, file_format: str) -> dict:  # noqa: N802
        """Write the current table out. The save dialog already asked about replacing."""
        if self._storage is None or not self._current_table:
            return {"ok": False, "error": "Pick a table first."}
        try:
            result = export_table(
                self._storage, self._current_table, self.localPath(url),
                file_format=file_format, overwrite=True,
            )
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self.message.emit(f"Wrote {result['rows_written']} rows to {Path(result['file']).name}.")
        return {"ok": True, "file": result["file"], "rows": result["rows_written"]}

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
        self._fields = [dict(field) for field in page["fields"]]
        try:
            form = form_for(self._storage, table)
            kinds = {f["name"]: f["type"] for f in self._fields}
            self._form_fields = [
                {"name": name, "label": form["labels"].get(name, name), "type": kinds[name]}
                for name in form["fields"] if name in kinds
            ]
        except OmarchyDBError:
            self._form_fields = list(self._fields)
        self._shown = len(page["rows"])
        self._total = page["total"]
        self.tableChanged.emit()
        return {"ok": True, "shown": self._shown, "total": self._total}

    # -- rows: add, change, delete ------------------------------------------
    @Slot(int, "QVariantMap", result="QVariantMap")
    def saveRow(self, row_id: int, values: dict) -> dict:  # noqa: N802
        """Write one record from the form. `row_id` 0 means a new row."""
        if self._storage is None or not self._current_table:
            return {"ok": False, "error": "Pick a table first."}
        clean = {name: _from_qml(value) for name, value in dict(values).items()}
        try:
            if int(row_id) > 0:
                self._storage.update_row(self._current_table, int(row_id), clean)
                saved = int(row_id)
            else:
                saved = int(self._storage.add_row(self._current_table, clean) or 0)
        except (ValueError, TypeError) as error:
            return {"ok": False, "error": _value_words(error, self._fields, clean)}
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables(select=self._current_table)
        return {"ok": True, "rowId": saved, "rowIndex": self._rows.rowIndexOf(saved)}

    @Slot(int, result="QVariantMap")
    def deleteRow(self, row_id: int) -> dict:  # noqa: N802
        if self._storage is None or not self._current_table:
            return {"ok": False, "error": "Pick a table first."}
        try:
            gone = self._storage.delete_row(self._current_table, int(row_id))
        except OmarchyDBError as error:
            return {"ok": False, "error": str(error)}
        self._refresh_tables(select=self._current_table)
        if gone:
            self.message.emit("Row deleted.")
        return {"ok": bool(gone), "error": "" if gone else "That row was already gone."}

    def _edit_cell(self, row_id: int, field: str, value: Any) -> bool:
        """A cell typed into in the grid."""
        result = self.saveRow(int(row_id), {field: value})
        if not result["ok"]:
            self.message.emit(result["error"])
        return bool(result["ok"])

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


def _from_qml(value: Any) -> Any:
    """QML hands strings and booleans; blanks mean "no value"."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _value_words(error: Exception, fields: list[dict[str, Any]], values: dict[str, Any]) -> str:
    """Say which field did not fit, in words, instead of a Python error."""
    kinds = {"integer": "a whole number", "real": "a number", "date": "a date like 2024-01-31",
             "boolean": "yes or no"}
    for field in fields:
        if field["name"] in values and values[field["name"]] is not None:
            try:
                from omarchy_db.fields import coerce

                coerce(values[field["name"]], field["type"])
            except (ValueError, TypeError):
                want = kinds.get(field["type"], "words")
                return f"{field['label']} needs {want}. \u201c{values[field['name']]}\u201d does not fit."
    return str(error)


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
