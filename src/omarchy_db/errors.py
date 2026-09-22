"""Errors that Omarchy-DB raises. Messages are meant to be shown to people."""


class OmarchyDBError(Exception):
    """Base class. Anything we raise on purpose is one of these."""


class PathNotAllowed(OmarchyDBError):
    """A file path pointed outside the folders the user approved."""


class BackendNotAvailable(OmarchyDBError):
    """The database engine was picked but its driver is not installed."""


class DatabaseExists(OmarchyDBError):
    """Asked to make a database that is already there."""


class DatabaseMissing(OmarchyDBError):
    """Asked to open a database that is not there."""


class TableMissing(OmarchyDBError):
    """Asked for a table this database does not have."""


class BadName(OmarchyDBError):
    """A table or field name we cannot use safely."""


class ImportProblem(OmarchyDBError):
    """The spreadsheet could not be turned into a table."""
