"""The QML desktop app: the bridge, the rows model, the theme, and the window itself.

These run without a display (`QT_QPA_PLATFORM=offscreen`). They are skipped
when PySide6 is not installed, because the core library and the MCP server do
not need it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QUrl  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QML_DIR = Path(__file__).resolve().parents[1] / "src" / "omarchy_db_app" / "qml"


@pytest.fixture(scope="session")
def app():
    from PySide6.QtGui import QGuiApplication

    from omarchy_db_app.main import make_app

    return QGuiApplication.instance() or make_app(["omarchy-db-app"])


@pytest.fixture
def bridge(app, sandbox):
    from omarchy_db_app.bridge import Bridge

    bridge = Bridge()
    yield bridge
    bridge.closeDatabase()


# -- the bridge ------------------------------------------------------------

def test_backends_lists_the_three_engines_sqlite_first(bridge):
    keys = [b["key"] for b in bridge.backends()]
    assert keys == ["sqlite", "postgres", "mysql"]
    assert bridge.backends()[0]["ready"] is True
    assert bridge.backends()[0]["needsServer"] is False


def test_new_database_then_import_then_rows(bridge, sandbox, pets_csv):
    assert bridge.isOpen is False
    made = bridge.newDatabase("sqlite", str(sandbox / "pets.omadb"), "My Pets", {})
    assert made == {"ok": True}
    assert bridge.isOpen is True
    assert bridge.title == "My Pets"
    assert bridge.tables == []

    done = bridge.importSpreadsheet(str(pets_csv), False)
    assert done["ok"] is True
    assert done["table"] == "pets"
    assert done["rowsAdded"] == 4
    assert [t["name"] for t in bridge.tables] == ["pets"]
    assert bridge.currentTable == "pets"
    assert bridge.totalRows == 4
    assert bridge.rows.rowCount() == 4
    assert bridge.rows.columnCount() == 6  # id + five fields


def test_import_asks_before_replacing_a_table(bridge, sandbox, pets_csv):
    bridge.newDatabase("sqlite", str(sandbox / "pets.omadb"), "", {})
    bridge.importSpreadsheet(str(pets_csv), False)
    again = bridge.importSpreadsheet(str(pets_csv), False)
    assert again["ok"] is False
    assert again["needsConfirm"] is True
    assert again["table"] == "pets"
    assert bridge.totalRows == 4
    replaced = bridge.importSpreadsheet(str(pets_csv), True)
    assert replaced["ok"] is True
    assert bridge.totalRows == 4


def test_file_urls_are_accepted(bridge, sandbox, pets_csv):
    url = QUrl.fromLocalFile(str(sandbox / "from-url.omadb")).toString()
    assert bridge.newDatabase("sqlite", url, "", {})["ok"] is True
    assert bridge.location == str(sandbox / "from-url.omadb")
    csv_url = QUrl.fromLocalFile(str(pets_csv)).toString()
    assert bridge.importSpreadsheet(csv_url, False)["ok"] is True
    assert bridge.suggestedDatabaseName(csv_url) == "pets.omadb"


def test_import_into_new_makes_the_database_and_names_it(bridge, sandbox, pets_csv):
    result = bridge.importIntoNew(str(pets_csv), str(sandbox / "new.omadb"))
    assert result["ok"] is True
    assert bridge.title == "Pets"
    assert bridge.totalRows == 4


def test_paths_outside_the_approved_roots_are_refused(bridge, sandbox):
    result = bridge.newDatabase("sqlite", "/etc/evil.omadb", "", {})
    assert result["ok"] is False
    assert "outside" in result["error"]
    assert bridge.isOpen is False


def test_recent_and_open_recent(bridge, sandbox):
    bridge.newDatabase("sqlite", str(sandbox / "a.omadb"), "A", {})
    bridge.newDatabase("sqlite", str(sandbox / "b.omadb"), "B", {})
    bridge.closeDatabase()
    recent = bridge.recent()
    assert [r["title"] for r in recent] == ["B", "A"]
    assert recent[0]["backendWord"] == "File"
    assert bridge.openRecent(1) == {"ok": True}
    assert bridge.title == "A"


def test_open_recent_forgets_a_database_that_is_gone(bridge, sandbox):
    bridge.newDatabase("sqlite", str(sandbox / "gone.omadb"), "Gone", {})
    bridge.closeDatabase()
    (sandbox / "gone.omadb").unlink()
    assert bridge.openRecent(0)["ok"] is False
    assert bridge.recent() == []


def test_a_remembered_server_asks_for_its_password(bridge, sandbox):
    from omarchy_db import catalog

    catalog.remember(
        title="Shop", backend="postgres",
        where="host=db.local port=5433 dbname=shop user=tim password=***",
    )
    result = bridge.openRecent(0)
    assert result["ok"] is False
    assert result["needsConnection"] is True
    assert result["backend"] == "postgres"
    assert result["connection"] == {"host": "db.local", "port": "5433", "database": "shop", "user": "tim"}

    catalog.remember(title="Shop2", backend="mysql", where="root@127.0.0.1:3306/shop")
    result = bridge.openRecent(0)
    assert result["connection"] == {"host": "127.0.0.1", "port": "3306", "database": "shop", "user": "root"}


def test_server_backend_errors_come_back_as_words(bridge):
    result = bridge.newDatabase("postgres", "", "X", {"host": "", "port": ""})
    assert result["ok"] is False
    assert result["error"]  # either "needs psycopg" or "which database to use"
    assert bridge.isOpen is False


# -- the rows model -----------------------------------------------------------

def test_rows_model_shows_yes_no_and_blanks(app):
    from PySide6.QtCore import Qt

    from omarchy_db_app.bridge import RowsModel

    model = RowsModel()
    model.load(
        {
            "fields": [
                {"name": "name", "type": "text", "label": "Name"},
                {"name": "good", "type": "boolean", "label": "Good?"},
            ],
            "rows": [[1, "Rex", True], [2, None, False]],
        }
    )
    assert model.columnCount() == 3
    assert model.headerData(1, Qt.Orientation.Horizontal) == "Name"
    assert model.data(model.index(0, 2)) == "Yes"
    assert model.data(model.index(1, 2)) == "No"
    assert model.data(model.index(1, 1)) == ""
    assert model.columnWidth(1) >= 60
    assert model.kindAt(2) == "boolean"


# -- the theme ----------------------------------------------------------------

def test_theme_reads_omarchy_colors_and_falls_back(tmp_path):
    from PySide6.QtGui import QPalette

    from omarchy_db_app.theme import build_palette, load_colors

    missing = load_colors(tmp_path / "nope.toml")
    assert missing["accent"]  # the fallback
    file = tmp_path / "colors.toml"
    file.write_text('mode = "light"\naccent = "#123456"\nbackground = "#ffffff"\n')
    colors = load_colors(file)
    assert colors["accent"] == "#123456"
    assert colors["mode"] == "light"
    palette = build_palette(colors)
    assert palette.color(QPalette.ColorRole.Highlight).name() == "#123456"
    assert palette.color(QPalette.ColorRole.Base).name() == "#ffffff"


# -- the window ----------------------------------------------------------------

def test_the_window_loads_and_shows_an_imported_table(app, bridge, sandbox, pets_csv):
    from PySide6.QtQml import QQmlApplicationEngine

    from omarchy_db_app.theme import Theme

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("Bridge", bridge)
    engine.rootContext().setContextProperty("Theme", Theme(app))
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    assert len(engine.rootObjects()) == 1, "Main.qml did not load"
    window = engine.rootObjects()[0]
    assert window.title() == "Omarchy-DB"

    assert bridge.importIntoNew(str(pets_csv), str(sandbox / "pets.omadb"))["ok"] is True
    app.processEvents()
    assert window.title() == "Pets — Omarchy-DB"
    grids = [
        child for child in window.findChildren(QObject)
        if child.metaObject().className() == "QQuickTableView"
    ]
    assert grids, "the rows grid is not on screen"
    assert grids[0].property("rows") == 4
    assert grids[0].property("columns") == 6

    bridge.closeDatabase()
    app.processEvents()
    assert window.title() == "Omarchy-DB"
    engine.deleteLater()


def test_theme_follows_omarchy_theme_set_swapping_the_directory(app, tmp_path, monkeypatch):
    """`omarchy theme set` does rm -rf current/theme; mv theme.next current/theme."""
    import shutil

    from PySide6.QtTest import QTest

    from omarchy_db_app.theme import Theme

    monkeypatch.delenv("OMARCHY_DB_THEME_FILE", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    current = tmp_path / "omarchy" / "current"
    (current / "theme").mkdir(parents=True)
    (current / "theme" / "colors.toml").write_text('mode = "dark"\naccent = "#111111"\n')
    (current / "theme.name").write_text("one\n")

    theme = Theme()
    assert theme.accent == "#111111"
    seen = []
    theme.changed.connect(lambda: seen.append(theme.accent))

    staging = current / "theme.next"
    staging.mkdir()
    (staging / "colors.toml").write_text('mode = "light"\naccent = "#222222"\n')
    shutil.rmtree(current / "theme")
    staging.rename(current / "theme")
    (current / "theme.name").write_text("two\n")

    QTest.qWait(700)
    assert seen == ["#222222"]
    assert theme.isDark is False

    # And again, to prove the watches were re-armed after the first swap.
    staging.mkdir()
    (staging / "colors.toml").write_text('mode = "dark"\naccent = "#333333"\n')
    shutil.rmtree(current / "theme")
    staging.rename(current / "theme")
    QTest.qWait(700)
    assert seen == ["#222222", "#333333"]
    assert str(current / "theme" / "colors.toml") in theme.watched()


# -- editing rows -------------------------------------------------------------

@pytest.fixture
def pets(bridge, sandbox, pets_csv):
    assert bridge.importIntoNew(str(pets_csv), str(sandbox / "pets.omadb"))["ok"] is True
    return bridge


def test_save_row_adds_and_updates(pets):
    assert [f["name"] for f in pets.fields] == ["name", "age", "adopted_on", "is_good", "weight_kg"]
    added = pets.saveRow(0, {"name": "Nova", "age": "3", "adopted_on": "2025-02-01", "is_good": True, "weight_kg": ""})
    assert added["ok"] is True
    assert added["rowId"] > 0
    assert pets.totalRows == 5
    assert added["rowIndex"] == 4
    record = pets.rows.record(added["rowIndex"])
    assert record["id"] == added["rowId"]
    assert record["values"] == {"name": "Nova", "age": "3", "adopted_on": "2025-02-01", "is_good": True, "weight_kg": ""}

    changed = pets.saveRow(added["rowId"], {"age": 4, "is_good": False})
    assert changed["ok"] is True
    assert pets.rows.record(4)["values"]["age"] == "4"
    assert pets.rows.record(4)["values"]["is_good"] is False
    assert pets.totalRows == 5


def test_save_row_explains_a_value_that_does_not_fit(pets):
    result = pets.saveRow(0, {"name": "Bad", "age": "three"})
    assert result["ok"] is False
    assert result["error"] == "age needs a whole number. “three” does not fit."
    assert pets.totalRows == 4
    result = pets.saveRow(pets.rows.rowId(0), {"adopted_on": "someday"})
    assert result["ok"] is False
    assert "needs a date" in result["error"]


def test_delete_row(pets):
    first = pets.rows.rowId(0)
    assert pets.deleteRow(first)["ok"] is True
    assert pets.totalRows == 3
    assert pets.rows.rowIndexOf(first) == -1
    again = pets.deleteRow(first)
    assert again["ok"] is False
    assert pets.totalRows == 3


def test_grid_edit_goes_through_set_data(pets):
    from PySide6.QtCore import Qt

    model = pets.rows
    assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable == Qt.ItemFlag(0)
    assert model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(model.index(0, 1), "Rexy") is True
    assert model.data(model.index(0, 1)) == "Rexy"
    assert model.setData(model.index(0, 4), "no") is True
    assert model.data(model.index(0, 4)) == "No"
    heard = []
    pets.message.connect(heard.append)
    assert model.setData(model.index(0, 2), "lots") is False
    assert heard and "whole number" in heard[0]
    assert model.setData(model.index(0, 0), "7") is False
