"""`omarchy-db` on the command line — the same jobs the app does.

    omarchy-db new "My Pets" ~/Documents/pets.omadb
    omarchy-db import ~/Documents/pets.omadb data/examples/pets.csv
    omarchy-db tables ~/Documents/pets.omadb
    omarchy-db rows ~/Documents/pets.omadb pets
    omarchy-db export ~/Documents/pets.omadb pets ~/Documents/pets-out.csv
    omarchy-db backends
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import catalog
from .errors import OmarchyDBError
from .exporter import export_table
from .importer import import_spreadsheet, plan_import
from .storage import BACKENDS, create_database, open_database


def _remember(storage: Any) -> None:
    info = storage.describe()
    catalog.remember(
        title=info.title,
        backend=info.backend,
        path=info.location if info.backend == "sqlite" else "",
        where="" if info.backend == "sqlite" else info.location,
    )


def cmd_backends(args: argparse.Namespace) -> int:
    for choice in BACKENDS:
        ready = "ready" if choice.driver_installed() else f"needs {choice.driver_package}"
        print(f"{choice.key:9} {choice.title}  [{ready}]")
        print(f"          {choice.blurb}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    with create_database(
        title=args.title, backend="sqlite", path=args.path, overwrite=args.overwrite
    ) as storage:
        _remember(storage)
        print(f"Made the database {storage.title!r} at {storage.location()}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    with open_database(backend="sqlite", path=args.path) as storage:
        result = import_spreadsheet(
            storage,
            args.file,
            table=args.table,
            if_exists="replace" if args.replace else "error",
        )
        _remember(storage)
    print(f"Added {result['rows_added']} rows to the table {result['table']!r}.")
    for field in result["created_fields"]:
        print(f"  {field['label']}  ->  {field['name']} ({field['type']})")
    if result["note_count"]:
        print(f"{result['note_count']} cells did not match their column's type:")
        for note in result["notes"]:
            print(f"  {note}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    print(json.dumps(plan_import(args.file), indent=2))
    return 0


def cmd_tables(args: argparse.Namespace) -> int:
    with open_database(backend="sqlite", path=args.path) as storage:
        names = storage.list_tables()
        if not names:
            print("This database has no tables yet. Import a spreadsheet to make one.")
        for name in names:
            info = storage.describe_table(name)
            print(f"{name}  ({len(info.fields)} fields, {info.row_count} rows)")
    return 0


def cmd_rows(args: argparse.Namespace) -> int:
    with open_database(backend="sqlite", path=args.path) as storage:
        page = storage.list_rows(args.table, limit=args.limit, offset=args.offset)
    if args.json:
        print(json.dumps(page, indent=2, default=str))
        return 0
    print(" | ".join(page["columns"]))
    for row in page["rows"]:
        print(" | ".join("" if value is None else str(value) for value in row))
    print(f"-- {len(page['rows'])} of {page['total']} rows")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with open_database(backend="sqlite", path=args.path) as storage:
        result = export_table(
            storage, args.table, args.out, file_format=args.format, overwrite=args.overwrite
        )
    print(f"Wrote {result['rows_written']} rows to {result['file']}")
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    entries = catalog.recent()
    if not entries:
        print("No databases yet.")
    for entry in entries:
        where = entry.get("path") or entry.get("where")
        print(f"{entry.get('title', '?'):24} {entry.get('backend', '?'):9} {where}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omarchy-db", description="A simple desktop database.")
    subs = parser.add_subparsers(dest="command", required=True)

    sub = subs.add_parser("backends", help="Show the kinds of database you can make")
    sub.set_defaults(func=cmd_backends)

    sub = subs.add_parser("new", help="Make a new database file")
    sub.add_argument("title")
    sub.add_argument("path")
    sub.add_argument("--overwrite", action="store_true")
    sub.set_defaults(func=cmd_new)

    sub = subs.add_parser("import", help="Put a spreadsheet into a database")
    sub.add_argument("path")
    sub.add_argument("file")
    sub.add_argument("--table")
    sub.add_argument("--replace", action="store_true", help="Replace a table of the same name")
    sub.set_defaults(func=cmd_import)

    sub = subs.add_parser("plan", help="Show what a spreadsheet would become")
    sub.add_argument("file")
    sub.set_defaults(func=cmd_plan)

    sub = subs.add_parser("tables", help="List the tables in a database")
    sub.add_argument("path")
    sub.set_defaults(func=cmd_tables)

    sub = subs.add_parser("rows", help="Show rows from a table")
    sub.add_argument("path")
    sub.add_argument("table")
    sub.add_argument("--limit", type=int, default=20)
    sub.add_argument("--offset", type=int, default=0)
    sub.add_argument("--json", action="store_true")
    sub.set_defaults(func=cmd_rows)

    sub = subs.add_parser("export", help="Write a table out as a CSV file")
    sub.add_argument("path")
    sub.add_argument("table")
    sub.add_argument("out")
    sub.add_argument("--format", default="csv")
    sub.add_argument("--overwrite", action="store_true")
    sub.set_defaults(func=cmd_export)

    sub = subs.add_parser("recent", help="Databases you opened lately")
    sub.set_defaults(func=cmd_recent)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except OmarchyDBError as error:
        print(f"Sorry — {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
