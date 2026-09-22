"""Omarchy-DB — a simple desktop database for Omarchy Linux.

The core library. The GTK app (`omarchy_db_gui`) and the MCP server
(`omarchy_db_mcp`) are both thin layers over what is here.
"""

from __future__ import annotations

from .catalog import recent, remember
from .errors import (
    BackendNotAvailable,
    BadName,
    DatabaseExists,
    DatabaseMissing,
    ImportProblem,
    OmarchyDBError,
    PathNotAllowed,
    TableMissing,
)
from .exporter import export_table
from .fields import FIELD_TYPE_LABELS, FIELD_TYPES, Field
from .importer import import_spreadsheet, plan_import
from .storage import (
    BACKENDS,
    MYSQL,
    POSTGRES,
    SQLITE,
    BackendChoice,
    Storage,
    backend_choice,
    create_database,
    open_database,
)

__version__ = "0.1.0"

__all__ = [
    "BACKENDS",
    "FIELD_TYPES",
    "FIELD_TYPE_LABELS",
    "MYSQL",
    "POSTGRES",
    "SQLITE",
    "BackendChoice",
    "BackendNotAvailable",
    "BadName",
    "DatabaseExists",
    "DatabaseMissing",
    "Field",
    "ImportProblem",
    "OmarchyDBError",
    "PathNotAllowed",
    "Storage",
    "TableMissing",
    "__version__",
    "backend_choice",
    "create_database",
    "export_table",
    "import_spreadsheet",
    "open_database",
    "plan_import",
    "recent",
    "remember",
]
