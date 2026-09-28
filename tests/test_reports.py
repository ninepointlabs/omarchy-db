"""Reports: fitting columns, laying out pages, writing PDF; and remembered forms."""

from __future__ import annotations

from pathlib import Path

import pytest

from omarchy_db.errors import BadName, OmarchyDBError
from omarchy_db.fields import Field
from omarchy_db.importer import import_spreadsheet
from omarchy_db.reports import (
    delete_report,
    export_report,
    fetch_rows,
    fit_columns,
    form_for,
    list_reports,
    load_report,
    normalise_spec,
    save_form,
    save_report,
)


def test_fit_columns_keeps_what_fits_and_shares_the_rest():
    assert fit_columns([100, 100], [20, 20], 400) == [100, 100]
    widths = fit_columns([100, 300, 50], [30, 60, 30], 300)
    assert widths == [100, 150.0, 50]
    assert sum(widths) <= 300


def test_fit_columns_scales_everything_when_even_minimums_do_not_fit():
    widths = fit_columns([200, 200], [150, 150], 200)
    assert sum(widths) == pytest.approx(200)
    assert widths[0] == pytest.approx(widths[1])


def test_fit_columns_can_be_turned_off():
    assert fit_columns([300, 300], [10, 10], 100, fit=False) == [300, 300]
    assert fit_columns([], [], 100) == []


def test_normalise_spec_fills_defaults_and_checks_columns(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    spec = normalise_spec(database, {"table": "pets"})
    assert spec["title"] == "Pets"
    assert spec["columns"] == ["name", "age", "adopted_on", "is_good", "weight_kg"]
    assert spec["page_size"] == "letter"
    assert spec["orientation"] == "portrait"
    assert spec["fit_to_width"] is True
    with pytest.raises(BadName):
        normalise_spec(database, {"table": "pets", "columns": ["name", "colour"]})
    with pytest.raises(OmarchyDBError, match="page size"):
        normalise_spec(database, {"table": "pets", "page_size": "tabloid"})


def test_fetch_rows_gives_display_text_in_column_order(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    spec = normalise_spec(database, {"table": "pets", "columns": ["is_good", "name"]})
    rows = fetch_rows(database, spec)
    assert rows[0] == ["Yes", "Rex"]
    assert rows[2] == ["No", "Shadow"]


def test_export_report_writes_a_pdf_and_paginates(database, pets_csv: Path, sandbox: Path):
    pytest.importorskip("PySide6")
    import_spreadsheet(database, str(pets_csv))
    result = export_report(database, {"table": "pets", "title": "My pets"}, str(sandbox / "pets"))
    assert result["file"].endswith("pets.pdf")
    assert result["pages"] == 1
    assert result["rows_written"] == 4
    data = Path(result["file"]).read_bytes()
    assert data.startswith(b"%PDF")

    with pytest.raises(OmarchyDBError, match="already a file"):
        export_report(database, {"table": "pets"}, str(sandbox / "pets.pdf"))
    again = export_report(database, {"table": "pets"}, str(sandbox / "pets.pdf"), overwrite=True)
    assert again["replaced_existing_file"] is True

    database.create_table("many", [Field("n", "integer", "N"), Field("words", "text", "Words")])
    for i in range(120):
        database.add_row("many", {"n": i, "words": "long text that has to wrap onto more lines " * 4})
    landscape = export_report(
        database, {"table": "many", "orientation": "landscape", "page_size": "a4"}, str(sandbox / "many.pdf")
    )
    assert landscape["pages"] > 1
    assert landscape["orientation"] == "landscape"


def test_export_report_refuses_paths_outside_roots(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    with pytest.raises(OmarchyDBError, match="outside"):
        export_report(database, {"table": "pets"}, "/etc/pets.pdf")


def test_forms_are_remembered_in_the_database(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    plain = form_for(database, "pets")
    assert plain["saved"] is False
    assert plain["fields"] == ["name", "age", "adopted_on", "is_good", "weight_kg"]

    saved = save_form(database, "pets", {"title": "A pet", "fields": ["name", "is_good"], "labels": {"is_good": "Good pet?"}})
    assert saved["labels"]["is_good"] == "Good pet?"
    form = form_for(database, "pets")
    assert form["saved"] is True
    assert form["title"] == "A pet"
    # Fields left out of the saved order still show, after the chosen ones.
    assert form["fields"] == ["name", "is_good", "age", "adopted_on", "weight_kg"]
    assert form["labels"]["is_good"] == "Good pet?"
    with pytest.raises(BadName):
        save_form(database, "pets", {"fields": ["nope"]})


def test_reports_are_remembered_and_listed(database, pets_csv: Path):
    import_spreadsheet(database, str(pets_csv))
    assert list_reports(database) == []
    save_report(database, {"name": "Good pets", "table": "pets", "columns": ["name", "is_good"]})
    save_report(database, {"table": "pets", "title": "Everything"})
    names = [r["name"] for r in list_reports(database)]
    assert names == ["Everything", "Good pets"]
    assert load_report(database, "Good pets")["columns"] == ["name", "is_good"]
    assert delete_report(database, "Good pets") is True
    assert delete_report(database, "Good pets") is False
    assert [r["name"] for r in list_reports(database)] == ["Everything"]


def test_the_printer_path_paints_the_same_pages(database, pets_csv: Path, sandbox: Path):
    """`print_to` is what the system print dialog hands a QPrinter to."""
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtPrintSupport import QPrinter

    from omarchy_db.printing import ReportDocument, ensure_gui_app
    from omarchy_db.reports import fetch_rows, normalise_spec

    ensure_gui_app()
    import_spreadsheet(database, str(pets_csv))
    spec = normalise_spec(database, {"table": "pets", "orientation": "landscape"})
    document = ReportDocument(spec, fetch_rows(database, spec))
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(sandbox / "printed.pdf"))
    assert document.print_to(printer) == 1
    assert (sandbox / "printed.pdf").read_bytes().startswith(b"%PDF")
    preview = document.preview_image(0, 300)
    assert preview.width() == 300
    assert preview.width() > preview.height()  # landscape


def test_cell_text_drops_the_trailing_point_zero_on_whole_numbers():
    from omarchy_db.reports import cell_text

    assert cell_text(3350.0, "real") == "3350"
    assert cell_text(42.5, "real") == "42.5"
    assert cell_text(7, "integer") == "7"
    assert cell_text(True, "boolean") == "Yes"
    assert cell_text(None, "real") == ""
