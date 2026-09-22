"""The Omarchy-DB MCP server.

Agents (Claude Code, and anything else that speaks MCP) attach to this over
stdio and get the same jobs the app does: make a database, import a
spreadsheet, list tables, read rows, write a CSV.

It speaks MCP's JSON-RPC 2.0 framing directly over stdin/stdout, with no
third-party SDK, so the only thing needed to run it is Python.

Safety rules, enforced here and in `omarchy_db.paths`:

- Every file path is resolved and must land inside an approved root
  (the user's home by default, or `OMARCHY_DB_ROOTS`). Traversal is refused.
- Spreadsheet cells are read as data. A formula is stored as its own text
  and never worked out or run.
- Anything that would replace a file or a table says so in its result, and
  will not do it unless asked with `overwrite` / `if_exists`.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from omarchy_db import __version__, catalog
from omarchy_db.errors import OmarchyDBError
from omarchy_db.exporter import export_table
from omarchy_db.fields import FIELD_TYPES
from omarchy_db.importer import import_spreadsheet, plan_import
from omarchy_db.storage import BACKENDS, Storage, create_database, open_database

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "omarchy-db"

_BACKEND_ENUM = [choice.key for choice in BACKENDS]

_CONNECTION_SCHEMA = {
    "type": "object",
    "description": "Server details. Only for the postgres and mysql backends.",
    "properties": {
        "host": {"type": "string"},
        "port": {"type": "integer"},
        "database": {"type": "string"},
        "user": {"type": "string"},
        "password": {"type": "string"},
        "url": {"type": "string", "description": "PostgreSQL only: a full connection URL."},
    },
    "additionalProperties": False,
}

_TARGET_PROPERTIES = {
    "backend": {"type": "string", "enum": _BACKEND_ENUM, "default": "sqlite"},
    "path": {"type": "string", "description": "The database file, for the sqlite backend."},
    "connection": _CONNECTION_SCHEMA,
}


def _open(arguments: dict[str, Any]) -> Storage:
    return open_database(
        backend=arguments.get("backend", "sqlite"),
        path=arguments.get("path"),
        connection=arguments.get("connection"),
    )


def _remember(storage: Storage) -> None:
    info = storage.describe()
    catalog.remember(
        title=info.title,
        backend=info.backend,
        path=info.location if info.backend == "sqlite" else "",
        where="" if info.backend == "sqlite" else info.location,
    )


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def tool_create_database(arguments: dict[str, Any]) -> dict[str, Any]:
    with create_database(
        title=arguments.get("title", ""),
        backend=arguments.get("backend", "sqlite"),
        path=arguments.get("path"),
        overwrite=bool(arguments.get("overwrite", False)),
        connection=arguments.get("connection"),
    ) as storage:
        _remember(storage)
        info = storage.describe()
    return {
        "made": True,
        "title": info.title,
        "backend": info.backend,
        "location": info.location,
        "replaced_existing": bool(arguments.get("overwrite", False)),
        "note": "A brand new database. It has no tables yet.",
    }


def tool_list_databases(arguments: dict[str, Any]) -> dict[str, Any]:
    entries = catalog.recent(int(arguments.get("limit", 20)))
    return {"databases": entries, "count": len(entries)}


def tool_open_database(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        info = storage.describe()
        _remember(storage)
    return {
        "opened": True,
        "title": info.title,
        "backend": info.backend,
        "location": info.location,
        "tables": info.tables,
    }


def tool_plan_import(arguments: dict[str, Any]) -> dict[str, Any]:
    return plan_import(arguments["file"])


def tool_import_spreadsheet(arguments: dict[str, Any]) -> dict[str, Any]:
    if_exists = arguments.get("if_exists", "error")
    if if_exists not in ("error", "skip", "replace"):
        raise OmarchyDBError("if_exists must be 'error', 'skip' or 'replace'.")
    with _open(arguments) as storage:
        result = import_spreadsheet(
            storage,
            arguments["file"],
            table=arguments.get("table"),
            if_exists=if_exists,
        )
        _remember(storage)
    if if_exists == "replace":
        result["note"] = "Any table of that name was dropped first."
    return result


def tool_list_tables(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        names = storage.list_tables()
        tables = []
        for name in names:
            info = storage.describe_table(name)
            tables.append({"name": name, "fields": len(info.fields), "rows": info.row_count})
    return {"tables": tables, "count": len(tables)}


def tool_describe_table(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        info = storage.describe_table(arguments["table"])
    return {
        "table": info.name,
        "rows": info.row_count,
        "fields": [{"name": f.name, "type": f.type, "label": f.title} for f in info.fields],
        "field_types": list(FIELD_TYPES),
    }


def tool_list_rows(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        return storage.list_rows(
            arguments["table"],
            limit=int(arguments.get("limit", 100)),
            offset=int(arguments.get("offset", 0)),
            order_by=arguments.get("order_by"),
            descending=bool(arguments.get("descending", False)),
        )


def tool_add_row(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        row_id = storage.add_row(arguments["table"], dict(arguments.get("values") or {}))
    return {"added": True, "table": arguments["table"], "id": row_id}


def tool_export_table(arguments: dict[str, Any]) -> dict[str, Any]:
    with _open(arguments) as storage:
        result = export_table(
            storage,
            arguments["table"],
            arguments["file"],
            file_format=arguments.get("format", "csv"),
            overwrite=bool(arguments.get("overwrite", False)),
            include_id=bool(arguments.get("include_id", False)),
        )
    if result["replaced_existing_file"]:
        result["note"] = "A file was already there and has been replaced."
    return result


def tool_list_backends(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "backends": [
            {
                "key": choice.key,
                "title": choice.title,
                "what_it_is": choice.blurb,
                "needs_server": choice.needs_server,
                "driver_installed": choice.driver_installed(),
                "driver_package": choice.driver_package,
            }
            for choice in BACKENDS
        ],
        "default": "sqlite",
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_backends",
        "description": "Show the kinds of database Omarchy-DB can make, and whether each driver is installed.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": tool_list_backends,
    },
    {
        "name": "create_database",
        "description": (
            "Make a new, empty database. Default backend is sqlite, which is one file on disk; "
            "give `path`. For postgres or mysql give `connection` instead — the server and its "
            "database must already exist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What to call it, in plain words."},
                **_TARGET_PROPERTIES,
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": "Replace a database that is already there. Destroys its data.",
                },
            },
            "additionalProperties": False,
        },
        "handler": tool_create_database,
    },
    {
        "name": "list_databases",
        "description": "List the databases this user has made or opened recently. Never includes passwords.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
            "additionalProperties": False,
        },
        "handler": tool_list_databases,
    },
    {
        "name": "open_database",
        "description": "Open a database and report its title and tables.",
        "inputSchema": {
            "type": "object",
            "properties": dict(_TARGET_PROPERTIES),
            "additionalProperties": False,
        },
        "handler": tool_open_database,
    },
    {
        "name": "plan_import",
        "description": (
            "Look at a CSV file and report the table, fields and guessed types it would create, "
            "without changing anything."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
            "additionalProperties": False,
        },
        "handler": tool_plan_import,
    },
    {
        "name": "import_spreadsheet",
        "description": (
            "Read a CSV file into a new table, guessing each field's type "
            "(text, integer, real, date, boolean). Excel .xlsx is not read yet."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_TARGET_PROPERTIES,
                "file": {"type": "string", "description": "The CSV file to read."},
                "table": {"type": "string", "description": "Table name. Defaults to the file name."},
                "if_exists": {
                    "type": "string",
                    "enum": ["error", "skip", "replace"],
                    "default": "error",
                    "description": "'replace' drops a table of that name first, losing its rows.",
                },
            },
            "required": ["file"],
            "additionalProperties": False,
        },
        "handler": tool_import_spreadsheet,
    },
    {
        "name": "list_tables",
        "description": "List the tables in a database, with how many fields and rows each has.",
        "inputSchema": {
            "type": "object",
            "properties": dict(_TARGET_PROPERTIES),
            "additionalProperties": False,
        },
        "handler": tool_list_tables,
    },
    {
        "name": "describe_table",
        "description": "Show one table's fields, their types and labels, and its row count.",
        "inputSchema": {
            "type": "object",
            "properties": {**_TARGET_PROPERTIES, "table": {"type": "string"}},
            "required": ["table"],
            "additionalProperties": False,
        },
        "handler": tool_describe_table,
    },
    {
        "name": "list_rows",
        "description": "Read rows from a table, a page at a time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_TARGET_PROPERTIES,
                "table": {"type": "string"},
                "limit": {"type": "integer", "default": 100, "maximum": 5000},
                "offset": {"type": "integer", "default": 0},
                "order_by": {"type": "string", "description": "A field name, or 'id'."},
                "descending": {"type": "boolean", "default": False},
            },
            "required": ["table"],
            "additionalProperties": False,
        },
        "handler": tool_list_rows,
    },
    {
        "name": "add_row",
        "description": "Add one row to a table. Values are checked against each field's type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_TARGET_PROPERTIES,
                "table": {"type": "string"},
                "values": {"type": "object", "description": "Field name to value."},
            },
            "required": ["table", "values"],
            "additionalProperties": False,
        },
        "handler": tool_add_row,
    },
    {
        "name": "export_table",
        "description": (
            "Write a whole table out to a CSV file. Says in its result whether a file was "
            "replaced. xlsx and pdf are not written yet."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_TARGET_PROPERTIES,
                "table": {"type": "string"},
                "file": {"type": "string", "description": "Where to write it."},
                "format": {"type": "string", "enum": ["csv"], "default": "csv"},
                "overwrite": {"type": "boolean", "default": False},
                "include_id": {"type": "boolean", "default": False},
            },
            "required": ["table", "file"],
            "additionalProperties": False,
        },
        "handler": tool_export_table,
    },
]

HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    tool["name"]: tool["handler"] for tool in TOOLS
}

TOOL_SCHEMAS = [
    {k: v for k, v in tool.items() if k != "handler"} for tool in TOOLS
]


# --------------------------------------------------------------------------
# JSON-RPC plumbing
# --------------------------------------------------------------------------

def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one tool and wrap it the way MCP wants. Errors come back as text."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _content({"error": f"There is no tool called {name!r}."}, is_error=True)
    try:
        result = handler(arguments or {})
    except OmarchyDBError as error:
        return _content({"error": str(error)}, is_error=True)
    except KeyError as error:
        return _content({"error": f"Missing argument: {error.args[0]!r}"}, is_error=True)
    except Exception as error:  # noqa: BLE001 - never kill the server on one bad call
        return _content({"error": f"{type(error).__name__}: {error}"}, is_error=True)
    return _content(result)


def _content(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    text = json.dumps(payload, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """Turn one JSON-RPC request into its response (or None for a notice)."""
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "instructions": (
                "Omarchy-DB makes simple desktop databases. Start with create_database "
                "(backend 'sqlite' is one file and needs nothing installed), then "
                "import_spreadsheet, then list_tables and list_rows. File paths must be "
                "inside the user's approved folders."
            ),
        }
        return _ok(message_id, result)

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return _ok(message_id, {})

    if method == "tools/list":
        return _ok(message_id, {"tools": TOOL_SCHEMAS})

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        return _ok(message_id, call_tool(name, arguments))

    if method == "resources/list":
        return _ok(message_id, {"resources": []})

    if method == "prompts/list":
        return _ok(message_id, {"prompts": []})

    if message_id is None:
        return None
    return _error(message_id, -32601, f"Unknown method: {method}")


def _ok(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: Any, code: int, text: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": text}}


def serve(stdin=None, stdout=None) -> int:
    """Read newline-delimited JSON-RPC from stdin until it closes."""
    source = stdin or sys.stdin
    sink = stdout or sys.stdout
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            _write(sink, _error(None, -32700, "That was not JSON."))
            continue
        if isinstance(message, list):
            for item in message:
                response = handle(item)
                if response is not None:
                    _write(sink, response)
            continue
        response = handle(message)
        if response is not None:
            _write(sink, response)
    return 0


def _write(sink, payload: dict[str, Any]) -> None:
    sink.write(json.dumps(payload) + "\n")
    sink.flush()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--tools", "-t"):
        print(json.dumps(TOOL_SCHEMAS, indent=2))
        return 0
    if argv and argv[0] in ("--version", "-V"):
        print(f"{SERVER_NAME} {__version__}")
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
