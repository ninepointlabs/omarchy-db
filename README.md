# Omarchy-DB

A simple database for your own computer, made for [Omarchy](https://omarchy.org/) Linux.

Think of the old Microsoft Access, without the hard parts. Make a database,
put a spreadsheet in it, look at your rows, print a tidy list. No SQL to learn,
no server to set up, no account to make.

**Status: early.** The desktop app, the command line, and the MCP server for
agents all work for the basics: make a database, import a CSV, see the tables
and rows, export CSV. Forms, Excel files, reports and printing come next. See
[STATUS.md](STATUS.md) for exactly what works today.

## What you can do

- **Make a database.** It is one file on your computer. Copy it, back it up, email it.
- **Import a spreadsheet.** Drop a CSV on the window and Omarchy-DB works out
  each column: words, whole numbers, numbers with decimals, dates, or yes/no.
- **Look at your rows.** A plain grid of everything in a table.
- **Send it back out.** Write any table to a CSV file (command line and agents today).
- **Let an agent do it.** The MCP server gives Claude Code (or any MCP client)
  the same jobs, so "turn this spreadsheet into a database" just works.

Coming in the next phase: typing into forms, Excel files, and printed reports
that fit the page.

## How it is built

Three pieces, one library underneath:

| Piece | What it is | Command |
|---|---|---|
| **The app** | A Qt Quick / QML desktop window. A small PySide6 host starts it and hands it a bridge to the library. Nothing about databases is written in QML. | `omarchy-db-app` |
| **The command line** | The same jobs from a terminal or a script. | `omarchy-db` |
| **The MCP server** | The same jobs for agents, over stdio. | `omarchy-db-mcp` |

The window follows your Omarchy theme. It reads the active theme's
`colors.toml`, so it is dark or light, and uses your accent colour, to match
the rest of the desktop. Change theme and the open window changes with it.

## Where your database lives

By default a new database is a single file in your Documents folder, ending in
`.omadb`. It is an ordinary SQLite file, so nothing is locked away.

If you already run a **PostgreSQL** or **MySQL / MariaDB** server, you can point
Omarchy-DB at that instead when you make the database. Same app, same features;
your data stays on your server.

| You pick | What it means | Needs |
|---|---|---|
| Just a file on this computer | The simple one. Nothing to install. | Nothing |
| A PostgreSQL server | A server you already run. | `psycopg` |
| A MySQL or MariaDB server | A server you already run. | `PyMySQL` |

Server passwords are never saved. The app remembers where the server is and
asks for the password again next time.

## Install

Omarchy-DB needs Python 3.11 or newer. The window needs Qt 6 and PySide6,
which Omarchy already has (`pyside6` and `qt6-declarative`).

```sh
# On Omarchy / Arch these are usually present already
sudo pacman -S --needed pyside6 qt6-declarative

git clone https://github.com/ninepointlabs/omarchy-db.git ~/Projects/omarchy-db
cd ~/Projects/omarchy-db
uv venv --system-site-packages .venv      # or: python -m venv --system-site-packages .venv
uv pip install -e .                       # or: .venv/bin/pip install -e .
```

Add a server backend only if you want one:

```sh
uv pip install -e '.[postgres]'   # PostgreSQL
uv pip install -e '.[mysql]'      # MySQL / MariaDB
```

To get it in your app launcher (links the commands into `~/.local/bin` and
installs the desktop entry and icon under `~/.local/share`):

```sh
./scripts/install-launcher.sh          # --remove undoes it
```

## Use it

### The app

```sh
omarchy-db-app                        # the home screen
omarchy-db-app ~/Documents/pets.omadb # open a database straight away
```

The home screen has three big buttons: **New database**, **Open a database**,
**Import a spreadsheet**, and the databases you opened lately. Drop a CSV
anywhere on the window and it becomes a database (or a table, if one is
already open). Nothing is replaced without asking first.

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
  explicit `overwrite` / `--replace` (the app asks you), and the result says
  what it replaced.
- **No passwords are kept.** The list of recent databases remembers how to
  find a server, never how to log into one. Server passwords are passed in at
  the time you connect and are stripped out of anything printed or logged.
- **Names are checked, not escaped.** Table and field names must be plain
  identifiers; anything else is refused rather than quoted around.

Your own settings live in `~/.local/state/omarchy-db/` (owner-only). Your
databases live wherever you put them.

## Developing

```sh
uv venv --system-site-packages .venv
uv pip install -e '.[dev,postgres,mysql]'
.venv/bin/python -m pytest
```

The tests cover type guessing, path safety, the SQLite backend end to end,
import and export, the MCP server (including a real process over a pipe), and
the app: the bridge, the rows model, the theme, and loading the QML window
offscreen with an imported table on screen.

A live PostgreSQL or MySQL server is not needed for the test suite. To check
one of those for real:

```sh
OMARCHY_DB_PASSWORD=secret .venv/bin/python scripts/smoke_remote.py postgres \
    --host localhost --database omadb_smoke --user postgres
```

### Layout

```
src/omarchy_db/       the core: backends, import, export, paths, CLI
src/omarchy_db_app/   the desktop app: PySide6 host, bridge, theme, and qml/
src/omarchy_db_mcp/   the MCP server agents attach to
archive/gtk-prototype/  the first (GTK) window, kept for reference only
data/examples/        a small sample spreadsheet
tests/                the test suite
packaging/            the desktop entry and icon
scripts/              launcher install and the server-backend smoke test
```

## Licence

MIT. See [LICENSE](LICENSE).
