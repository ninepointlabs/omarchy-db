"""Renaming and deleting fields, tables and database files; importing every sheet."""

from __future__ import annotations

from pathlib import Path

import pytest

from omarchy_db import catalog, schema
from omarchy_db.errors import BadName, OmarchyDBError
from omarchy_db.importer import import_spreadsheet, import_workbook
from omarchy_db.reports import form_for, list_reports, load_report, save_form, save_report
from omarchy_db.storage import create_database, open_database


@pytest.fixture
def pets(database, pets_csv):
    import_spreadsheet(database, str(pets_csv))
    return database


def test_rename_field_changes_the_column_and_keeps_the_rows(pets):
    result = schema.rename_field(pets, "pets", "weight_kg", "weight", label="Weight (kg)")
    names = [f["name"] for f in result["fields"]]
    assert names == ["name", "age", "adopted_on", "is_good", "weight"]
    assert result["fields"][-1]["label"] == "Weight (kg)"
    page = pets.list_rows("pets")
    assert page["columns"][-1] == "weight"
    assert page["rows"][0][-1] == 12.5
    assert pets.describe_table("pets").fields[-1].label == "Weight (kg)"


def test_relabel_only_keeps_the_name(pets):
    result = schema.relabel_field(pets, "pets", "is_good", "Good pet?")
    assert result["fields"][3] == {"name": "is_good", "type": "boolean", "label": "Good pet?"}


def test_rename_field_refuses_bad_and_clashing_names(pets):
    with pytest.raises(BadName):
        schema.rename_field(pets, "pets", "age", "name")
    with pytest.raises(BadName):
        schema.rename_field(pets, "pets", "age", "id")
    with pytest.raises(BadName):
        schema.rename_field(pets, "pets", "age", "how old?")
    with pytest.raises(BadName):
        schema.rename_field(pets, "pets", "colour", "hue")


def test_drop_field_removes_the_column_and_its_data(pets):
    result = schema.drop_field(pets, "pets", "adopted_on")
    assert [f["name"] for f in result["fields"]] == ["name", "age", "is_good", "weight_kg"]
    page = pets.list_rows("pets")
    assert "adopted_on" not in page["columns"]
    assert page["total"] == 4
    assert page["rows"][0][1:] == ["Rex", 4, True, 12.5]
    with pytest.raises(BadName):
        schema.drop_field(pets, "pets", "adopted_on")
    with pytest.raises(BadName):
        schema.drop_field(pets, "pets", "id")


def test_the_last_field_cannot_be_dropped(database):
    from omarchy_db.fields import Field

    database.create_table("one", [Field("only", "text")])
    with pytest.raises(BadName, match="at least one field"):
        schema.drop_field(database, "one", "only")


def test_forms_and_reports_follow_a_rename_and_a_drop(pets):
    save_form(pets, "pets", {"fields": ["name", "weight_kg", "age"], "labels": {"weight_kg": "Kilos"}})
    save_report(pets, {"name": "Weights", "table": "pets", "columns": ["name", "weight_kg"]})
    save_report(pets, {"name": "Ages", "table": "pets", "columns": ["age"]})

    schema.rename_field(pets, "pets", "weight_kg", "weight", label="Weight")
    form = form_for(pets, "pets")
    assert form["fields"][:3] == ["name", "weight", "age"]
    assert form["labels"]["weight"] == "Kilos"
    report = load_report(pets, "Weights")
    assert report["columns"] == ["name", "weight"]
    assert report["labels"] == ["name", "Weight"]

    schema.drop_field(pets, "pets", "weight")
    assert "weight" not in form_for(pets, "pets")["fields"]
    assert load_report(pets, "Weights")["columns"] == ["name"]
    schema.drop_field(pets, "pets", "age")
    # A report with no columns left is forgotten rather than left broken.
    assert [r["name"] for r in list_reports(pets)] == ["Weights"]


def test_drop_table_forgets_its_form_and_reports(pets):
    save_form(pets, "pets", {"fields": ["name"]})
    save_report(pets, {"name": "All", "table": "pets"})
    result = schema.drop_table(pets, "pets")
    assert result == {"table": "pets", "rows_deleted": 4, "reports_forgotten": ["All"]}
    assert pets.list_tables() == []
    assert list_reports(pets) == []
    assert pets.get_info("form:pets", "") == ""


def test_delete_database_file_removes_it_and_forgets_it(sandbox: Path):
    path = sandbox / "gone.omadb"
    storage = create_database(title="Gone", path=str(path))
    catalog.remember(title="Gone", backend="sqlite", path=str(path))
    result = schema.delete_database_file(storage, str(path))
    assert result["deleted"] is True
    assert not path.exists()
    assert not Path(str(path) + "-wal").exists()
    assert catalog.recent() == []
    with pytest.raises(OmarchyDBError, match="no database"):
        schema.delete_database_file(None, str(path))
    with pytest.raises(OmarchyDBError, match="outside"):
        schema.delete_database_file(None, "/etc/passwd.omadb")
    (sandbox / "notes.txt").write_text("hi")
    with pytest.raises(OmarchyDBError, match="not a database file"):
        schema.delete_database_file(None, str(sandbox / "notes.txt"))
    assert (sandbox / "notes.txt").exists()


def test_import_workbook_makes_a_table_per_sheet(database, sandbox: Path):
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    first = book.active
    first.title = "People"
    first.append(["Name", "Age"])
    first.append(["Ann", 31])
    second = book.create_sheet("Places")
    second.append(["City", "Country"])
    second.append(["Tyler", "USA"])
    second.append(["Oslo", "Norway"])
    book.create_sheet("Empty")
    book.save(sandbox / "three.xlsx")

    result = import_workbook(database, str(sandbox / "three.xlsx"))
    assert [(t["table"], t["rows_added"]) for t in result["tables"]] == [("people", 1), ("places", 2)]
    assert [e["sheet"] for e in result["errors"]] == ["Empty"]
    assert "empty" in result["errors"][0]["error"].lower()
    assert database.list_tables() == ["people", "places"]

    again = import_workbook(database, str(sandbox / "three.xlsx"))
    assert again["tables"] == []
    assert len(again["errors"]) == 3
    replaced = import_workbook(database, str(sandbox / "three.xlsx"), if_exists="replace")
    assert [t["replaced_existing"] for t in replaced["tables"]] == [True, True]
    assert database.count_rows("places") == 2


def test_import_workbook_treats_a_csv_as_one_sheet(database, pets_csv):
    result = import_workbook(database, str(pets_csv))
    assert [t["table"] for t in result["tables"]] == ["pets"]
    assert result["errors"] == []
