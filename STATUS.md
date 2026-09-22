# Omarchy-DB — status

**Phase A (skeleton). Last updated 2026-09-21.**

Phase A is complete except for one check that needs a running PostgreSQL and
MySQL server — see [Not yet verified](#not-yet-verified). Nothing from Phase B
or C was started.

## What works today

### Core library (`src/omarchy_db/`)

- **Storage interface** (`storage/base.py`) that the window, the command line
  and the MCP server all share. One API, three engines.
- **SQLite backend** — complete. Makes a `.omadb` file (mode 0600), creates
  tables, adds/reads/updates/deletes rows, paging and sorting.
- **PostgreSQL backend** (`psycopg`) and **MySQL/MariaDB backend** (`PyMySQL`) —
  real drivers, no stubs and no fakes. Create/open, create table, list tables,
  describe, and full row CRUD are implemented through the same interface.
- **CSV import** with type guessing across the five field types
  (words / whole number / number with decimals / date / yes-no). Blank cells
  never decide a type; a cell that does not fit is kept as words and reported
  rather than dropped.
- **CSV export**, including yes/no written as words.
- **Recent databases list** at `~/.local/state/omarchy-db/databases.json`
  (mode 0600). It records how to find a server, never how to log into one.
- **Path safety** — every path is resolved and must land under an approved root
  (`$HOME` by default, or `OMARCHY_DB_ROOTS`). `../` traversal and symlinks
  pointing outside are refused.

### Command line (`omarchy-db`)

`backends`, `new`, `import`, `plan`, `tables`, `rows`, `export`, `recent`.
Verified by hand end to end on `data/examples/pets.csv`.

### MCP server (`omarchy-db-mcp`)

Stdio JSON-RPC, protocol `2024-11-05`. Tools: `list_backends`,
`create_database`, `list_databases`, `open_database`, `plan_import`,
`import_spreadsheet`, `list_tables`, `describe_table`, `list_rows`, `add_row`,
`export_table`. `--tools` prints the schemas.

### Window (`omarchy-db-gui`)

GTK4 + Libadwaita. Opens a database (or the most recent one on start), lists its
tables, shows the rows, makes a new SQLite database through a backend chooser,
and imports a spreadsheet — asking first if that would replace a table.
Launched on this machine under Hyprland/Wayland and confirmed showing tables and
rows; follows the system light/dark preference.

`packaging/omarchy-db.desktop` exists but is **not installed** anywhere
(installing it is Phase C).

## Verified

- `python -m pytest` — **88 passed**, covering type guessing, path safety and
  traversal, the SQLite backend, import/export, the backend chooser and SQL
  shapes for all three engines, and the MCP server (including starting it as a
  real process and speaking JSON-RPC to it over a pipe).
- CLI end to end: made a database, imported `pets.csv` (5 fields correctly
  typed, 4 rows), listed tables and rows, exported CSV, and confirmed a write
  to `/etc/` is refused.
- GTK window launched and screenshotted showing the imported table.

## Not yet verified

**Live PostgreSQL and MySQL/MariaDB connect.** The drivers are installed and
the code paths are unit-tested offline (column type maps, identifier quoting,
parameter markers, password redaction, connection-string building), but no
server has actually been connected to on this machine. Docker is installed but
its socket needs root, and this session's process carries stale group
membership, so the containers could not be started from here.

To finish the check, start two throwaway servers and run the smoke script:

```sh
docker run -d --rm --name omadb-pg -e POSTGRES_PASSWORD=smoke \
    -e POSTGRES_DB=omadb_smoke -p 5432:5432 postgres:16
docker run -d --rm --name omadb-my -e MARIADB_ROOT_PASSWORD=smoke \
    -e MARIADB_DATABASE=omadb_smoke -p 3306:3306 mariadb:11

OMARCHY_DB_PASSWORD=smoke .venv/bin/python scripts/smoke_remote.py postgres \
    --host 127.0.0.1 --database omadb_smoke --user postgres
OMARCHY_DB_PASSWORD=smoke .venv/bin/python scripts/smoke_remote.py mysql \
    --host 127.0.0.1 --database omadb_smoke --user root

docker stop omadb-pg omadb-my
```

The script connects, creates an empty table, lists tables, describes it, adds
and reads back a row, updates and deletes it, drops the table and reopens.

## Phase A success criteria

| Criterion | State |
|---|---|
| `~/Projects/omarchy-db` with README + tests | done |
| Import a sample CSV into a new `.omadb` and list rows via library/MCP | done |
| Creation offers SQLite (default), PostgreSQL, MySQL/MariaDB | done |
| SQLite full path works | done |
| Postgres/MySQL connect + empty table + list tables in a smoke test | **code + script ready, not run against a live server** |
| MCP server starts and tools work in a smoke test | done |
| GTK window opens and shows tables/rows | done |
| `STATUS.md` lists done / next | done |
| No secrets committed; path traversal tests pass | done |

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
  it can see there.
- **CSV import on server backends** is written and shares the SQLite path, but
  has only been exercised against SQLite. Confirm it with the smoke script
  above before relying on it.
- **New database in the window** currently only makes SQLite databases. The
  chooser shows all three and explains the other two; a server database is made
  from the command line or an agent for now.

## Decisions worth knowing

- **Python, not Rust.** Faster to a readable v1, and PyGObject is already on
  Omarchy (`python-gobject`).
- **The MCP server has no SDK dependency.** MCP over stdio is plain JSON-RPC,
  so it is written against the stdlib. The core library and the MCP server
  install with zero third-party packages; only the window (PyGObject) and the
  two server backends need anything.
- **Type guessing prefers yes/no over numbers for a 0/1 column.** A column of
  nothing but 0 and 1 is a yes/no far more often than a count. It is shown in
  the plan before import and can be changed.
- **Names are refused, not escaped.** Table and field names must be plain
  identifiers. Spreadsheet headings are slugified into safe names and the
  original heading is kept as the label people see.

## Next — Phase B (not started, waiting on Tim)

- Form view: one record at a time, next/previous, save.
- xlsx import and export (`openpyxl`).
- Reports: choose fields, preview, fit-to-width, system print and PDF.
- Import wizard in the window: editable column mapping and type guesses.
- Make a server database from the window, not just the command line.
- Empty-state polish ("Drop a spreadsheet here").

## Phase C (not started)

Desktop entry install script and an optional PKGBUILD draft for `omarchy-pkgs`.
Nothing to be published without Tim.
