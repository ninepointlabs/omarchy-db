"""Databases and state made before the rename from Omarchy-DB to Jubako still work."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jubako.fields import TEXT, Field
from jubako.paths import database_path, state_dir
from jubako.storage import create_database, open_database


def _make_legacy_database(sandbox: Path) -> Path:
    """A `.omadb` file whose bookkeeping tables still use the `omadb_` prefix."""
    path = sandbox / "pets.omadb"
    with create_database(title="Old pets", backend="sqlite", path=str(sandbox / "new.jubadb")) as storage:
        storage.create_table("pets", [Field("name", TEXT, "Name")])
        storage.set_info("view:pets:Still here", '{"table": "pets"}')
    (sandbox / "new.jubadb").rename(path)
    connection = sqlite3.connect(path)
    connection.execute('ALTER TABLE "jubako_info" RENAME TO "omadb_info"')
    connection.execute('ALTER TABLE "jubako_tables" RENAME TO "omadb_tables"')
    connection.commit()
    connection.close()
    return path


def test_an_omadb_path_keeps_its_suffix(sandbox: Path):
    assert database_path(str(sandbox / "pets.omadb")) == sandbox / "pets.omadb"


def test_a_new_database_gets_the_jubadb_suffix(sandbox: Path):
    assert database_path(str(sandbox / "pets")) == sandbox / "pets.jubadb"


def test_opening_an_old_database_renames_its_bookkeeping_tables(sandbox: Path):
    path = _make_legacy_database(sandbox)
    with open_database(backend="sqlite", path=str(path)) as storage:
        assert storage.title == "Old pets"
        assert storage.list_tables() == ["pets"]
        assert storage.get_info("view:pets:Still here") == '{"table": "pets"}'
        assert [f.label for f in storage.describe_table("pets").fields] == ["Name"]
        real = set(storage.real_table_names())
    assert {"jubako_info", "jubako_tables"} <= real
    assert not {"omadb_info", "omadb_tables"} & real


def test_the_old_state_folder_moves_over(sandbox: Path):
    legacy = sandbox / "state" / "omarchy-db"
    legacy.mkdir(parents=True)
    (legacy / "databases.json").write_text("[]", "utf-8")
    moved = state_dir()
    assert moved == sandbox / "state" / "jubako"
    assert (moved / "databases.json").read_text("utf-8") == "[]"
    assert not legacy.exists()
