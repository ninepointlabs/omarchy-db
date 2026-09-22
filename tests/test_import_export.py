"""Spreadsheet in, table out, CSV back again."""

from __future__ import annotations

from pathlib import Path

import pytest

from omarchy_db.errors import ImportProblem, OmarchyDBError, PathNotAllowed
from omarchy_db.exporter import export_table
from omarchy_db.fields import BOOLEAN, DATE, INTEGER, REAL, TEXT
from omarchy_db.importer import import_spreadsheet, plan_import


def test_plan_reports_what_would_happen(pets_csv: Path):
    plan = plan_import(str(pets_csv))
    assert plan["table"] == "pets"
    assert [field["type"] for field in plan["fields"]] == [TEXT, INTEGER, DATE, BOOLEAN, REAL]
    assert plan["fields"][2]["label"] == "adopted_on"


def test_import_creates_the_table_and_rows(database, pets_csv: Path):
    report = import_spreadsheet(database, str(pets_csv))
    assert report["table"] == "pets"
    assert report["rows_added"] == 4
    assert report["note_count"] == 0

    page = database.list_rows("pets")
    assert page["total"] == 4
    assert page["rows"][0][1] == "Rex"
    assert page["rows"][0][2] == 4
    assert page["rows"][0][3] == "2021-03-14"
    assert page["rows"][0][4] is True  # "yes" comes back as a real yes
    assert page["rows"][3][2] is None  # the blank age stays blank, not zero


def test_importing_twice_is_refused_unless_asked(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    with pytest.raises(OmarchyDBError):
        import_spreadsheet(database, str(pets_csv))
    report = import_spreadsheet(database, str(pets_csv), if_exists="replace")
    assert report["rows_added"] == 4
    assert database.count_rows("pets") == 4


def test_a_formula_is_kept_as_text_not_worked_out(database, sandbox: Path):
    sheet = sandbox / "sums.csv"
    sheet.write_text('label,amount\nrent,"=1+1"\n', "utf-8")
    import_spreadsheet(database, str(sheet))
    assert database.list_rows("sums")["rows"][0][2] == "=1+1"


def test_odd_headings_become_safe_fields(database, sandbox: Path):
    sheet = sandbox / "odd.csv"
    sheet.write_text("First Name,First Name,2024 Total ($)\nAda,Lovelace,10\n", "utf-8")
    report = import_spreadsheet(database, str(sheet))
    assert [f["name"] for f in report["created_fields"]] == [
        "first_name",
        "first_name_2",
        "c_2024_total",
    ]


def test_a_stray_cell_is_kept_as_words_and_reported(database, sandbox: Path):
    sheet = sandbox / "ages.csv"
    # The first 500 rows decide the type; a later odd value must not be lost.
    lines = ["age"] + [str(n) for n in range(600)] + ["unknown"]
    sheet.write_text("\n".join(lines) + "\n", "utf-8")
    report = import_spreadsheet(database, str(sheet))
    assert report["note_count"] == 1
    assert "unknown" in report["notes"][0]
    assert report["rows_added"] == 601


def test_semicolon_files_are_read(database, sandbox: Path):
    sheet = sandbox / "euro.csv"
    sheet.write_text("name;count\nAda;3\nGrace;4\n", "utf-8")
    report = import_spreadsheet(database, str(sheet))
    assert report["rows_added"] == 2
    assert [f["name"] for f in report["created_fields"]] == ["name", "count"]


def test_empty_file_is_reported_kindly(database, sandbox: Path):
    sheet = sandbox / "empty.csv"
    sheet.write_text("", "utf-8")
    with pytest.raises(ImportProblem):
        import_spreadsheet(database, str(sheet))


def test_a_broken_excel_file_is_refused_in_words(database, sandbox: Path):
    pytest.importorskip("openpyxl")
    sheet = sandbox / "book.xlsx"
    sheet.write_bytes(b"PK\x03\x04not really a workbook")
    with pytest.raises(ImportProblem, match="Excel"):
        import_spreadsheet(database, str(sheet))


def test_old_xls_is_refused_with_advice(database, sandbox: Path):
    sheet = sandbox / "book.xls"
    sheet.write_bytes(b"\xd0\xcf\x11\xe0 old excel")
    with pytest.raises(ImportProblem, match="save it as .xlsx"):
        import_spreadsheet(database, str(sheet))


def test_xlsx_round_trip_keeps_types(database, pets_csv: Path, sandbox: Path):
    pytest.importorskip("openpyxl")
    import_spreadsheet(database, str(pets_csv))
    out = export_table(database, "pets", str(sandbox / "pets.xlsx"), file_format="xlsx")
    assert out["format"] == "xlsx"
    assert out["rows_written"] == 4
    assert (sandbox / "pets.xlsx").exists()

    plan = plan_import(str(sandbox / "pets.xlsx"))
    assert plan["sheets"] == ["pets"]
    assert plan["sheet"] == "pets"
    assert [f["type"] for f in plan["fields"]] == ["text", "integer", "date", "boolean", "real"]

    back = import_spreadsheet(database, str(sandbox / "pets.xlsx"), table="pets_again")
    assert back["rows_added"] == 4
    rows = database.list_rows("pets_again")["rows"]
    assert rows[0][1:] == ["Rex", 4, "2021-03-14", True, 12.5]


def test_xlsx_import_picks_a_sheet_and_reads_saved_formula_values(database, sandbox: Path):
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    first = book.active
    first.title = "People"
    first.append(["Name", "Age"])
    first.append(["Ann", 31])
    second = book.create_sheet("Totals")
    second.append(["Item", "Price", "Doubled"])
    second.append(["Pen", 1.5, "=B2*2"])
    book.save(sandbox / "two.xlsx")

    plan = plan_import(str(sandbox / "two.xlsx"))
    assert plan["sheets"] == ["People", "Totals"]
    assert plan["table"] == "people"
    result = import_spreadsheet(database, str(sandbox / "two.xlsx"), sheet="Totals")
    assert result["table"] == "totals"
    # openpyxl wrote no cached value for the formula, so the cell is blank —
    # the formula itself is never worked out by Omarchy-DB.
    rows = database.list_rows("totals")["rows"]
    assert rows[0][1:3] == ["Pen", 1.5]
    assert rows[0][3] is None
    with pytest.raises(ImportProblem, match="no sheet called"):
        import_spreadsheet(database, str(sandbox / "two.xlsx"), sheet="Nope")


def test_import_refuses_a_file_outside_the_approved_roots(database):
    with pytest.raises(PathNotAllowed):
        import_spreadsheet(database, "/etc/passwd")


def test_export_writes_every_row(database, pets_csv: Path, sandbox: Path):
    import_spreadsheet(database, str(pets_csv))
    out = sandbox / "out.csv"
    report = export_table(database, "pets", str(out))
    assert report["rows_written"] == 4
    lines = out.read_text("utf-8").strip().splitlines()
    assert lines[0] == "name,age,adopted_on,is_good,weight_kg"
    assert lines[1] == "Rex,4,2021-03-14,yes,12.5"
    assert lines[3].split(",")[3] == "no"
    assert len(lines) == 5


def test_export_will_not_clobber_without_permission(database, pets_csv: Path, sandbox: Path):
    import_spreadsheet(database, str(pets_csv))
    out = sandbox / "out.csv"
    out.write_text("keep me", "utf-8")
    with pytest.raises(OmarchyDBError):
        export_table(database, "pets", str(out))
    report = export_table(database, "pets", str(out), overwrite=True)
    assert report["replaced_existing_file"] is True


def test_export_refuses_a_path_outside_the_roots(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    with pytest.raises(PathNotAllowed):
        export_table(database, "pets", "/etc/omarchy-db-escape.csv")


def test_unknown_export_format_is_refused(database, pets_csv: Path, sandbox: Path):
    import_spreadsheet(database, str(pets_csv))
    with pytest.raises(OmarchyDBError, match="cannot write"):
        export_table(database, "pets", str(sandbox / "out.doc"), file_format="doc")


def test_the_report_says_when_a_table_was_replaced(database, pets_csv: Path):
    first = import_spreadsheet(database, str(pets_csv))
    assert first["replaced_existing"] is False
    second = import_spreadsheet(database, str(pets_csv), if_exists="replace")
    assert second["replaced_existing"] is True
