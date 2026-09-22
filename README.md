# Omarchy-DB

A simple database for your own computer, made for [Omarchy](https://omarchy.org/) Linux.

Think of the old Microsoft Access, without the hard parts. Make a database,
put a spreadsheet in it, look at your rows, print a tidy list. No SQL to learn,
no server to set up, no account to make.

**Status: early. This is the Phase A scaffold** — the core library, a command
line, an MCP server for agents, and a first window. Forms, Excel files, reports
and printing come next. See [STATUS.md](STATUS.md) for exactly what works today.

## What you can do

- **Make a database.** It is one file on your computer. Copy it, back it up, email it.
- **Import a spreadsheet.** Drop in a CSV and Omarchy-DB works out each column:
  words, whole numbers, numbers with decimals, dates, or yes/no.
- **Look at your rows.** A plain list of everything in a table.
- **Send it back out.** Write any table to a CSV file.
- **Let an agent do it.** The MCP server gives Claude Code (or any MCP client)
  the same jobs, so "turn this spreadsheet into a database" just works.

Coming in the next phase: typing into forms, Excel files, and printed reports
that fit the page.

## Where your database lives

By default a new database is a single file in your Documents folder, ending in
`.omadb`. It is an ordinary SQLite file, so nothing is locked away.

If you already run a **PostgreSQL** or **MySQL / MariaDB** server, you can point
Omarchy-DB at that instead when you make the database. Same app, same features;
your data stays on your server.

| You pick | What it means | Needs |
|---|---|---|
| A file on this computer | The simple one. Nothing to install. | Nothing |
| A PostgreSQL server | A server you already run. | `psycopg` |
| A MySQL or MariaDB server | A server you already run. | `PyMySQL` |

## Install

Omarchy-DB needs Python 3.11 or newer. The window also needs GTK 4 and
Libadwaita, which Omarchy already has.

```sh
# On Omarchy / Arch, the window's bindings come from the system package
sudo pacman -S --needed python-gobject gtk4 libadwaita

git clone https://github.com/ninepointlabs/omarchy-db.git ~/Projects/omarchy-db
cd ~/Projects/omarchy-db
python -m venv --system-site-packages .venv
.venv/bin/pip install -e .
```

Add a server backend only if you want one:

```sh
.venv/bin/pip install -e '.[postgres]'   # PostgreSQL
.venv/bin/pip install -e '.[mysql]'      # MySQL / MariaDB
```

To get it in your app launcher:

```sh
install -Dm644 packaging/omarchy-db.desktop ~/.local/share/applications/omarchy-db.desktop
```

## Use it

### The window

```sh
omarchy-db-gui                      # or open a database straight away:
omarchy-db-gui ~/Documents/pets.omadb
```

### The command line

```sh
omarchy-db backends                                   # what kinds of database you can make
omarchy-db new "My Pets" ~/Documents/pets.omadb       # make one
omarchy-db import ~/Documents/pets.omadb pets.csv     # put a spreadsheet in it
omarchy-db tables ~/Documents/pets.omadb              # what's in there
omarchy-db rows ~/Documents/pets.omadb pets           # look at the rows
omarchy-db export ~/Documents/pets.omadb pets out.csv # send it back out
```

There is a tiny example to try: `data/examples/pets.csv`.

### From an agent (MCP)

Add this to your MCP client. For Claude Code:

```sh
claude mcp add omarchy-db -- /home/you/Projects/omarchy-db/.venv/bin/omarchy-db-mcp
```

Then ask it to do the work:

> Take `~/Downloads/members.csv` and make me a database in Documents.

The tools are `list_backends`, `create_database`, `list_databases`,
`open_database`, `plan_import`, `import_spreadsheet`, `list_tables`,
`describe_table`, `list_rows`, `add_row` and `export_table`. Run
`omarchy-db-mcp --tools` to print their schemas.

## How your columns get their types

When a spreadsheet comes in, each column gets the narrowest type that *every*
filled-in cell fits. Blank cells never decide anything, and anything unclear
stays as words, because words never lose data.

| The column holds | It becomes |
|---|---|
| `yes`, `no`, `true`, `1`, `0` | Yes / No |
| `4`, `-3`, `1,200` | Whole number |
| `12.5`, `6` | Number with decimals |
| `2021-03-14`, `14/03/2021` | Date |
| anything else, or a mix | Words |

The guesses are shown to you before anything is written, and you can change them.

## Safety

- **Files stay where you said.** Every path Omarchy-DB opens or writes is
  checked against a list of approved folders — your home directory by default,
  or whatever `OMARCHY_DB_ROOTS` says. A path that climbs out with `../`, or a
  symlink that points outside, is refused. This matters most for the MCP
  server, where an agent supplies the paths.
- **Spreadsheet formulas are text.** A cell holding `=1+1` is stored as the
  characters `=1+1`. Nothing from a spreadsheet is ever worked out or run.
- **Nothing is replaced quietly.** Writing over a file or a table takes an
  explicit `overwrite` / `--replace`, and the result says what it replaced.
- **No passwords are kept.** The list of recent databases remembers how to
  find a server, never how to log into one. Server passwords are passed in at
  the time you connect and are stripped out of anything printed or logged.
- **Names are checked, not escaped.** Table and field names must be plain
  identifiers; anything else is refused rather than quoted around.

Your own settings live in `~/.local/state/omarchy-db/` (owner-only). Your
databases live wherever you put them.

## Developing

```sh
python -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev,postgres,mysql]'
.venv/bin/python -m pytest
```

The tests cover type guessing, path safety, the SQLite backend end to end,
import and export, and the MCP server (including a real process over a pipe).

A live PostgreSQL or MySQL server is not needed for the test suite. To check
one of those for real:

```sh
OMARCHY_DB_PASSWORD=secret .venv/bin/python scripts/smoke_remote.py postgres \
    --host localhost --database omadb_smoke --user postgres
```

### Layout

```
src/omarchy_db/       the core: backends, import, export, paths, CLI
src/omarchy_db_gui/   the GTK4 + Libadwaita window
src/omarchy_db_mcp/   the MCP server agents attach to
data/examples/        a small sample spreadsheet
tests/                the test suite
packaging/            the desktop entry
scripts/              the server-backend smoke test
```

## Licence

MIT. See [LICENSE](LICENSE).
