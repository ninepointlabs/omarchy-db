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


def test_excel_says_it_is_not_ready_yet(database, sandbox: Path):
    sheet = sandbox / "book.xlsx"
    sheet.write_bytes(b"PK\x03\x04not really a workbook")
    with pytest.raises(ImportProblem, match="Excel"):
        import_spreadsheet(database, str(sheet))


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


def test_xlsx_and_pdf_export_say_they_are_coming(database, pets_csv: Path, sandbox: Path):
    import_spreadsheet(database, str(pets_csv))
    for kind in ("xlsx", "pdf"):
        with pytest.raises(OmarchyDBError, match="not built yet"):
            export_table(database, "pets", str(sandbox / f"out.{kind}"), file_format=kind)
