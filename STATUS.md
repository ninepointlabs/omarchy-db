# Omarchy-DB — status

**Phase B (forms, Excel, reports, printing). Last updated 2026-09-22.**

## Fix 2026-09-22 — Excel import of a titled sheet collapsed to one column

Tim imported `Tyler_Community_Consolidated_List_1.1.xlsx` and got a single
field. The reader took the first non-blank row as the headers; on a normal
titled sheet that row is the title alone in A1, so every later row was cut
to one column. Now `read_xlsx`:

1. **Prefers the sheet's Excel Table** when it has one (the largest, if
   several): headers and data come from the Table's range, and cells outside
   it (footers, totals) are ignored. This needs the workbook opened
   normally rather than read-only, because read-only sheets do not expose
   their Tables.
2. **Otherwise finds the header row by looking**: among the first 30 rows,
   the first row at least half as wide as the widest and with two or more
   filled cells. A lone title never qualifies; a header row with a blank
   cell still does. The table is as wide as the last column with a heading
   or with data below it, and a column with data but no heading is called
   "Column 3" rather than dropped. A genuinely one-column sheet still works.

Verified on Tim's file: all three sheets — "Consolidated List" (Excel Table
`ConsolidatedMembers` A5:O30, 15 fields, 25 rows), "Clean_List_For_Print"
(Table, 9 fields, 32 rows) and "No Longer in the Area" (no Table; title,
subtitle, two blank rows, headers on row 5; 15 fields, 8 rows) — plan and
import with the real headers (IDN, First Name, Middle / Nickname, Last Name,
Mail Status, Address Line 1, City, State, ZIP, Home Phone, Work Phone, Cell
Phone, Email, Record Type, Notes), through the CLI and through the app's
wizard path (bridge `planImport` / `importPlanned` on the worker thread).
Four new tests build workbooks of these shapes; 127 tests pass.

Worth knowing: on the sheet without dashes in its ZIP codes the type guesser
calls ZIP a whole number, which the wizard lets you change to words before
importing. That is the guesser's normal behaviour, not part of this bug.

Phase B is complete on this machine, in the order Tim asked for: B0 (live
theme follow) first, then the form view and grid editing, then Excel import
and export, fitted PDF reports with preview and system print, the import
wizard, and a worker thread for imports. The one open item carried from Phase
A remains: no live PostgreSQL or MySQL server has been connected to from
here (see [Not yet verified](#not-yet-verified)). Phase C (packaging) is
mostly not started.

## What changed in Phase B

### B0 — the window follows `omarchy theme set` (verified live)

`omarchy theme set` does `rm -rf current/theme` and then `mv theme.next
current/theme`, so a watch on `colors.toml` went stale the moment the theme
changed. The app now watches `~/.local/state/omarchy/current/` itself and
`theme.name` (which are rewritten in place), re-arms the inner watches after
every change, waits for the burst of events to settle, reads `colors.toml`
once the new directory is there, rebuilds the palette and emits
`Theme.changed`. The QML binds to `Theme.*` (`Theme.window`, `Theme.base`,
`Theme.alternateBase`, `Theme.accent`, …), never to `palette.*`.

Verified with the window open: switched from the guild theme to Gruvbox and
back; the window recoloured each time (screenshots taken at each step). A
unit test performs the same rm-rf-then-rename twice.

### B1 — form view and grid editing

- **Form**: one record at a time. Previous / Next, "Row 2 of 4", New row,
  Save (or "Add this row"), Undo changes, Delete this row. Yes/no fields are a
  checkbox; other fields are a box to type in with a hint of what fits.
- **Grid**: tap a row to pick it, double-tap a cell (or Enter / F2) to type in
  it. Add row and Delete row buttons above the grid. Delete asks first.
- Values that do not fit come back in words: "age needs a whole number.
  “three” does not fit."
- The form honours a form kept in the database (`create_form` in MCP): field
  order and labels.

### B2 — Excel, reports, printing, import wizard, worker thread

- **Excel (.xlsx) import and export** with `openpyxl` (optional extra
  `xlsx`). Import reads one sheet per call (the wizard and MCP let you pick),
  uses the values Excel last saved for formulas, and never runs anything.
  Export writes real Excel types (numbers, dates, booleans), bold headings,
  frozen header row. Old `.xls` is refused with advice.
- **Reports**: `omarchy_db/reports.py` holds the spec (table, columns, title,
  page size Letter/A4/Legal, orientation, margins, fit-to-width, text size,
  row numbers), the row fetch and the column-fitting arithmetic; forms and
  reports are kept inside the database in Omarchy-DB's own info table.
  `omarchy_db/printing.py` lays out and paints pages with Qt: one
  `ReportDocument` writes the PDF, prints to a `QPrinter`, and renders the
  preview image, so what you preview is what you print. Fit-to-width shrinks
  columns proportionally (never below their longest word) and wraps cells;
  rows never clip; pages number "Page n of N".
- **In the app**: "Print report" opens the designer: title, column
  checkboxes, page, orientation, fit, margins, text size, keep-by-name, list
  of kept reports; a live preview that relays out 250 ms after each change,
  with page arrows; "Print…" opens the system print dialog (`QPrintDialog`),
  "Save PDF…" a save dialog. "Export…" writes the current table as CSV or
  Excel.
- **Import wizard**: every import now goes through one screen showing the
  file, the sheet (when there is more than one), the table name, and each
  column's label, guessed type (editable) and a few sample values. Replacing
  a table still asks first.
- **Worker thread**: for a file database the import runs on a `QThread` with
  its own SQLite connection; the wizard shows a spinner and cannot be closed
  until it is done. Server databases import in place (their connection is
  not re-openable without the password).
- **MCP**: new tools `update_row`, `delete_row`, `create_form`, `get_form`,
  `create_report`, `list_reports`, `delete_report`, `export_report`;
  `import_spreadsheet` and `plan_import` take `sheet`; `export_table` takes
  `format` csv | xlsx | pdf. 19 tools in all.
- **CLI**: `omarchy-db report <db> <table> <out.pdf> [--title --columns --page
  --landscape --no-fit]`; `export --format csv|xlsx|pdf`; `import --sheet`.
- **Host**: `QApplication` instead of `QGuiApplication`, only because the
  system print dialog is a widget. The UI is still all QML.

## Verified

- `python -m pytest` — **127 passed** (123 after Phase B plus the four Excel
  header tests; the 123 were 101 after A2, plus theme swap, editing,
  import worker, export, report bridge, xlsx round trip, sheet choice, saved
  formula values, column fitting, pagination, PDF bytes, printer path,
  preview orientation, forms and reports kept in the database, and the new
  MCP tools end to end).
- Live theme follow under Hyprland: theme switched twice with the window
  open; the window recoloured both times.
- Launched live after every milestone; last launch under the Lumon theme
  shows Grid / Form, Add row / Delete row, Export…, Print report.
- Offscreen renders inspected: grid row selection, in-place cell editor, the
  form ("Row 2 of 4"), the report designer with its preview, the import
  wizard on a two-sheet workbook (imported the People sheet with the right
  types), a landscape one-page PDF and a seven-page wrapping report whose
  PDF pages (via `pdftoppm`) match the preview image.
- MCP: `omarchy-db-mcp --tools` lists 19 tools; the MCP test drives
  update/delete row, create/get form, create/list/export/delete report
  through the real handlers.
- CLI: `omarchy-db report … --landscape` wrote a one-page PDF.

## Not yet verified

- **Live PostgreSQL and MySQL/MariaDB connect.** Unchanged: drivers
  installed, code paths unit-tested offline, no server reachable from this
  machine (no local server binaries; Docker socket needs root). Optional per
  Tim; `scripts/smoke_remote.py` is ready.
- **Pressing Print in the system dialog.** The dialog cannot be driven from
  here. The path it feeds (`ReportDocument.print_to(QPrinter)`) is tested by
  printing to a PDF-format `QPrinter`, and the dialog constructs.
- **Forms and reports on server backends.** They are kept in Omarchy-DB's
  own info table through the shared storage interface, so they should work
  on all three engines, but have only run on SQLite.

## Phase B success criteria (from the brief)

| Criterion | State |
|---|---|
| B0: window tracks `omarchy theme set` while open | done, verified live |
| Form view: one record, next/prev, save | done |
| Grid add/edit/delete | done |
| xlsx import and export | done |
| Report preview + PDF + system print with fit-to-width | done (print dialog opens; printing to a PDF printer tested) |
| Import wizard: editable mapping and type guesses | done (types and table name editable; column renaming is not) |
| Polish empty states | done in A2; wizard and form add their own hints |
| Worker thread for imports | done for SQLite; in place for servers |
| MCP `update_row` / `delete_row` / `create_form` / `create_report` / `export_report` | done |
| STATUS.md updated | done |

## Engine-specific limits

- **SQLite** keeps dates as ISO text and yes/no as 0/1. The library turns them
  back into real dates and yes/no on the way out, so all three engines look the
  same to the app. PostgreSQL and MySQL use their own `DATE` and boolean types.
- **Row identity.** Every table Omarchy-DB makes gets an automatic `id`. A
  table made outside Omarchy-DB without an `id` column can be listed and
  read, but not updated or deleted row by row, so the form and grid editing
  will refuse it.
- **Where a database lives.** SQLite is a file the user picks. For PostgreSQL
  and MySQL, the *server* and the *database* must already exist. The app never
  passes `overwrite` for a server.
- **Imports on server backends** run on the GUI thread (see worker thread
  above) and have only been exercised against SQLite.
- **Re-opening a recent server database** needs the password typed again
  (by design).
- **Report size.** A report reads at most 20,000 rows; column widths are
  measured on the first 2,000. The grid shows the first 500 rows of a table.

## Decisions worth knowing

- **Pixel-size fonts in reports.** The painter is scaled so one unit is one
  point on every target (PDF at 300 dpi, printer, preview image). Point-size
  fonts already follow the device DPI and came out double-scaled; pixel-size
  fonts do not, so measuring and painting agree everywhere.
- **Reports live in the core, Qt is imported lazily.** The core still installs
  with no third-party packages; `printing.py` imports PySide6 only when a PDF
  is made, and starts an offscreen `QGuiApplication` if none exists (that is
  how the MCP server and CLI make PDFs).
- **Forms and reports are stored in the database file**, under `form:<table>`
  and `report:<name>` keys in `omadb_info`, so they travel with the `.omadb`.
- **The wizard is the only import path in the window.** Dropping a file,
  the Import button and the first-run path all open it, so the type guesses
  are always shown before anything is written.
- **PySide6 host; Fusion style + palette; work on the GUI thread except
  imports; Python not Rust; MCP with no SDK; names refused not escaped** —
  unchanged from earlier phases.

## Next — Phase C (mostly not started, waiting on Tim)

- `scripts/install-launcher.sh` exists (done early in A2). Still to do: an
  optional PKGBUILD draft for `omarchy-pkgs`. Nothing to be published without
  Tim.

## Loose ends worth a later pass

- Column renaming in the import wizard (labels are shown, not editable).
- Filter and sort in the grid (the brief's "filter/sort simple" for table view).
- Reports: choose sort order; group headings; a header/footer of your own.
- Open a database on the worker thread too (only imports are off-thread today).
- A drag-over highlight while a file is being dropped on the window.
- Live PostgreSQL / MySQL smoke, then confirm forms, reports and imports there.
