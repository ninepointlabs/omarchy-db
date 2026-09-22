# Omarchy-DB — status

**Phase A2 (QML desktop app). Last updated 2026-09-21.**

Phase A2 is complete: the window is now a Qt Quick / QML desktop application
over the unchanged Python core, CLI and MCP server. The one open item carried
from Phase A remains: a live PostgreSQL and MySQL connect has still not been
run on this machine (see [Not yet verified](#not-yet-verified)). Nothing from
Phase B has **not** been started (waiting on Tim).

## What changed in A2

- **The app is QML.** `src/omarchy_db_app/` holds a PySide6 host (`main.py`,
  about 60 lines), a bridge (`bridge.py`), the theme loader (`theme.py`) and the
  QML files under `qml/`. It is a normal `ApplicationWindow`, not a Quickshell
  panel, plugin or bar chip. Command: `omarchy-db-app`.
- **The GTK window is archived** under `archive/gtk-prototype/`. It is not
  installed, not tested and no longer in `pyproject.toml`.
- **Python core untouched.** No `--json` CLI bridge was needed: the PySide6
  host imports the library in-process and the bridge calls the same functions
  the CLI and MCP server use. The bridge returns plain dicts (`ok`, `error`,
  ...) to the QML. Nothing about databases is written in QML.
- **Desktop entry** `packaging/omarchy-db.desktop` now launches
  `omarchy-db-app`; the app sets its Wayland app id to `omarchy-db` to match.
  `scripts/install-launcher.sh` links the commands into `~/.local/bin` and
  installs the entry plus `packaging/omarchy-db.svg` under `~/.local/share`.
  (This is the Phase C install script, pulled forward because "the .desktop
  file launches the app" cannot be checked without it.)
- **Omarchy theming.** The app reads the active theme's `colors.toml` from
  `~/.local/state/omarchy/current/theme/`, builds a Qt palette from it (dark or
  light by the theme's `mode`), and watches the file so `omarchy theme set`
  re-colours the open window. Controls use the Fusion style because it paints
  from the palette. The UI font is the system sans (Qt default); the Omarchy
  mono font is used only for the row-number column.

## What works today

### The app (`omarchy-db-app`)

- **Home**: New database, Open a database, Import a spreadsheet, and the
  recent list. Drop a CSV or `.omadb` anywhere on the window.
- **New database** chooser: SQLite (default) / PostgreSQL / MySQL-MariaDB with
  a one-line blurb each; a backend whose driver is missing is greyed out and
  says what to install. SQLite goes on to a save dialog. The server backends
  show host, port, database, user, password fields and connect in place, with
  the error shown inside the dialog.
- **Open**: a file dialog for SQLite; a recent server entry re-opens the same
  dialog pre-filled (host, port, database, user) and asks for the password,
  which is never saved.
- **Import spreadsheet**: into the open database, or, with none open, a CSV
  becomes a brand new `.omadb` (title from the file name). Asks before
  replacing a table of the same name.
- **Database page**: tables with row counts down the left, a read-only grid
  of the selected table (first 500 rows) with a header row and yes/no shown as
  words; empty states that say what to do next.
- Opens a database given on the command line (`omarchy-db-app file.omadb`),
  which is what `%f` in the desktop entry passes.

### Core library, CLI and MCP server

Unchanged from Phase A: storage interface with SQLite, PostgreSQL (psycopg)
and MySQL/MariaDB (PyMySQL) backends; CSV import with type guessing; CSV
export; recent list; path safety; `omarchy-db` CLI; `omarchy-db-mcp` with
`list_backends`, `create_database`, `list_databases`, `open_database`,
`plan_import`, `import_spreadsheet`, `list_tables`, `describe_table`,
`list_rows`, `add_row`, `export_table`.

## Verified

- `python -m pytest` — **101 passed** (88 from Phase A plus 13 new in
  `tests/test_app.py`: bridge flows, replace-asks-first, file URLs, path
  refusal, recent list and server re-connect prompt, rows model, theme
  palette, and loading `Main.qml` offscreen and finding a 4×6 grid after an
  import). MCP tests pass unchanged.
- Launched under Hyprland/Wayland from the terminal with a database argument:
  `hyprctl clients` shows class `omarchy-db`, title `Pets — Omarchy-DB`;
  screenshot shows the table list and rows in the Gruvbox palette.
- Ran `scripts/install-launcher.sh`, then `gio launch
  ~/.local/share/applications/omarchy-db.desktop`: the home screen opened
  (class `omarchy-db`), screenshot shows the three buttons and the recent list.
- Rendered the New database dialog offscreen with PostgreSQL selected: all
  connection fields and the greyed-out/blurb logic show correctly.
- `omarchy-db-mcp --tools` lists the same eleven tools as before.

## Not yet verified

**Live PostgreSQL and MySQL/MariaDB connect.** Same as Phase A: drivers
installed, code paths unit-tested offline, but no server has been connected to
from this machine (no local server binaries; Docker socket needs root). The
app's server dialog has been exercised only as far as the bridge returning an
error in words. To finish the check, start two throwaway servers and run
`scripts/smoke_remote.py` as described in its docstring, then try the same
details in the app's New database dialog.

## Phase A2 success criteria

| Criterion | State |
|---|---|
| QML desktop app opens a normal window on Omarchy (Hyprland/Wayland) | done |
| New SQLite DB, Open recent, Import CSV, list tables, show rows — via the Python helper | done |
| Backend chooser on New (SQLite default; Postgres/MySQL connection fields) | done; server connect **not run against a live server** |
| `.desktop` file launches the QML app | done (via `scripts/install-launcher.sh` + `gio launch`) |
| GTK GUI archived; README rewritten | done |
| MCP still works unchanged | done |
| `STATUS.md` updated | done |
| No rewrite of the Python core | done — zero changes under `src/omarchy_db/` except one docstring |

## Engine-specific limits

- **SQLite** keeps dates as ISO text and yes/no as 0/1. The library turns them
  back into real dates and yes/no on the way out, so all three engines look the
  same to the app. PostgreSQL and MySQL use their own `DATE` and boolean types.
- **Row identity.** Every table Omarchy-DB makes gets an automatic `id`
  (SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`, PostgreSQL `BIGSERIAL`, MySQL
  `BIGINT AUTO_INCREMENT`). A table made outside Omarchy-DB without an `id`
  column can be listed and read, but not updated or deleted row by row.
- **Where a database lives.** SQLite is a file the user picks. For PostgreSQL
  and MySQL, the *server* and the *database* must already exist — Omarchy-DB
  adds its tables to the one it is pointed at, and `overwrite` drops the tables
  it can see there. The app never passes `overwrite` for a server.
- **CSV import on server backends** shares the SQLite path but has only been
  exercised against SQLite.
- **Re-opening a recent server database** needs the password typed again
  (by design). A PostgreSQL entry remembered as a URL is re-opened through the
  URL with its password stripped, so it needs the password too.

## Decisions worth knowing

- **PySide6 host, not C++.** Tim said QML and "smallest host". PySide6 6.11 is
  already on Omarchy (`pyside6`), it runs QML in a normal window on Wayland,
  and it lets the bridge call the Python library directly, so no JSON CLI
  bridge and no second process. The host is ~60 lines; the bridge ~300.
- **Fusion style + palette.** The Basic style ignores the palette; Material
  and Universal bring their own look. Fusion paints from the palette, so one
  palette built from `colors.toml` themes every control.
- **Work runs on the GUI thread.** Import and open are synchronous. For the
  sample sizes in v1 that is instant; a big CSV will freeze the window while it
  loads. Moving that to a worker is a Phase B polish item.
- **Python, not Rust; MCP with no SDK; yes/no beats numbers for 0/1 columns;
  names refused not escaped** — unchanged from Phase A.

## Next — Phase B (not started, waiting on Tim)

- Form view: one record at a time, next/previous, save. Add / edit / delete
  rows from the grid.
- xlsx import and export (`openpyxl`).
- Reports: choose fields, preview, fit-to-width, system print (Qt print) and PDF.
- Import wizard in the window: editable column mapping and type guesses.
- Export CSV from the window (the library and MCP already do it).
- Run import/open off the GUI thread; drag-and-drop feedback while hovering.
- Live smoke test of PostgreSQL and MySQL, then confirm the app dialog against them.

## Phase C (mostly not started)

`scripts/install-launcher.sh` exists (pulled forward). Still to do: an optional
PKGBUILD draft for `omarchy-pkgs`. Nothing to be published without Tim.
