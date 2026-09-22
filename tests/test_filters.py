"""Show rows where ... : the one filter behind the grid, the form, reports and MCP."""

from __future__ import annotations

import pytest

from omarchy_db import schema
from omarchy_db.errors import BadName, OmarchyDBError
from omarchy_db.fields import Field
from omarchy_db.filters import filter_words, normalise_filter
from omarchy_db.importer import import_spreadsheet
from omarchy_db.reports import export_report, fetch_rows, normalise_spec


@pytest.fixture
def pets(database, pets_csv):
    import_spreadsheet(database, str(pets_csv))
    schema.add_field(database, "pets", label="Moved", field_type="boolean")
    ids = [row[0] for row in database.list_rows("pets")["rows"]]
    database.update_row("pets", ids[0], {"moved": "yes"})
    database.update_row("pets", ids[2], {"moved": True})
    return database


def names(page):
    return [row[1] for row in page["rows"]]


def test_add_field_appends_a_blank_column(database, pets_csv):
    import_spreadsheet(database, str(pets_csv))
    result = schema.add_field(database, "pets", label="Moved", field_type="boolean")
    assert result["fields"][-1] == {"name": "moved", "type": "boolean", "label": "Moved"}
    page = database.list_rows("pets")
    assert page["columns"][-1] == "moved"
    assert [row[-1] for row in page["rows"]] == [None, None, None, None]
    assert schema.add_field(database, "pets", label="Vet's phone")["fields"][-1]["name"] == "vet_s_phone"
    assert schema.add_field(database, "pets", label="Fee", name="fee_usd", field_type="real")["fields"][-1]["name"] == "fee_usd"
    with pytest.raises(BadName):
        schema.add_field(database, "pets", label="Moved")
    with pytest.raises(BadName):
        schema.add_field(database, "pets", label="Row", name="id")
    with pytest.raises(OmarchyDBError, match="Unknown field type"):
        schema.add_field(database, "pets", label="X", field_type="blob")
    with pytest.raises(OmarchyDBError, match="label"):
        schema.add_field(database, "pets", label="   ")


def test_is_and_is_not_on_a_yes_no_field(pets):
    hide_moved = {"field": "moved", "op": "is_not", "value": "yes"}
    page = pets.list_rows("pets", where=hide_moved)
    assert names(page) == ["Milo", "Pip"]        # blanks count as "not yes"
    assert page["total"] == 2
    assert page["total_all"] == 4
    assert page["filter"] == {"field": "moved", "op": "is_not", "value": True}
    for word in ("yes", "true", "1", "Y", True):
        assert names(pets.list_rows("pets", where={"field": "moved", "op": "is", "value": word})) == ["Rex", "Shadow"]
    assert pets.count_rows("pets", where=hide_moved) == 2
    assert pets.count_rows("pets") == 4


def test_empty_not_empty_and_contains(pets):
    assert names(pets.list_rows("pets", where={"field": "moved", "op": "empty"})) == ["Milo", "Pip"]
    assert names(pets.list_rows("pets", where={"field": "moved", "op": "not_empty"})) == ["Rex", "Shadow"]
    assert names(pets.list_rows("pets", where={"field": "name", "op": "contains", "value": "i"})) == ["Milo", "Pip"]
    assert names(pets.list_rows("pets", where={"field": "name", "op": "contains", "value": "%"})) == []
    assert names(pets.list_rows("pets", where={"field": "age", "op": "is", "value": "4"})) == ["Rex"]
    assert names(pets.list_rows("pets", where={"field": "adopted_on", "op": "is", "value": "2024-01-05"})) == ["Pip"]
    assert names(pets.list_rows("pets", where={"field": "age", "op": "is empty"})) == ["Pip"]


def test_filters_are_checked_in_words(pets):
    fields = pets.describe_table("pets").fields
    with pytest.raises(BadName):
        normalise_filter(fields, {"field": "colour", "op": "is", "value": "red"})
    with pytest.raises(OmarchyDBError, match="Unknown match"):
        normalise_filter(fields, {"field": "name", "op": "like", "value": "x"})
    with pytest.raises(OmarchyDBError, match="Say what"):
        normalise_filter(fields, {"field": "name", "op": "is", "value": ""})
    with pytest.raises(OmarchyDBError, match="not a whole number"):
        normalise_filter(fields, {"field": "age", "op": "is", "value": "old"})
    with pytest.raises(OmarchyDBError, match="only works on a words field"):
        normalise_filter(fields, {"field": "age", "op": "contains", "value": "4"})
    assert normalise_filter(fields, None) is None
    assert normalise_filter(fields, {}) is None
    # No SQL sneaks in: the field must be a real one, the value is bound.
    with pytest.raises(BadName):
        normalise_filter(fields, {"field": "name; DROP TABLE pets", "op": "is", "value": "x"})
    assert names(pets.list_rows("pets", where={"field": "name", "op": "is", "value": "Rex' OR 1=1 --"})) == []


def test_filter_words(pets):
    fields = pets.describe_table("pets").fields
    assert filter_words(fields, normalise_filter(fields, {"field": "moved", "op": "is_not", "value": "yes"})) == "Moved is not Yes"
    assert filter_words(fields, normalise_filter(fields, {"field": "name", "op": "empty"})) == "name is empty"
    assert filter_words(fields, normalise_filter(fields, {"field": "name", "op": "contains", "value": "Re"})) == "name contains Re"
    assert filter_words(fields, None) == ""


def test_reports_honour_the_filter(pets, sandbox):
    pytest.importorskip("PySide6")
    spec = normalise_spec(pets, {"table": "pets", "columns": ["name", "moved"],
                                 "filter": {"field": "moved", "op": "is_not", "value": "yes"}})
    assert spec["filter_words"] == "Moved is not Yes"
    assert fetch_rows(pets, spec) == [["Milo", ""], ["Pip", ""]]
    result = export_report(pets, spec, str(sandbox / "not-moved.pdf"))
    assert result["rows_written"] == 2
    plain = normalise_spec(pets, {"table": "pets"})
    assert plain["filter"] is None and plain["filter_words"] == ""
    with pytest.raises(BadName):
        normalise_spec(pets, {"table": "pets", "filter": {"field": "nope", "op": "is", "value": 1}})
