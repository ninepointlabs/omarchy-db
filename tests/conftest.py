"""Shared fixtures. Every test runs inside its own temporary approved root."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

EXAMPLE_CSV = Path(__file__).resolve().parents[1] / "data" / "examples" / "pets.csv"


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A folder that is the only place Omarchy-DB is allowed to touch."""
    monkeypatch.setenv("OMARCHY_DB_ROOTS", str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("OMARCHY_DB_DEFAULT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def database(sandbox: Path):
    """A fresh SQLite database inside the sandbox."""
    from omarchy_db.storage import create_database

    storage = create_database(title="Test", backend="sqlite", path=str(sandbox / "test.omadb"))
    yield storage
    storage.close()


@pytest.fixture
def pets_csv(sandbox: Path) -> Path:
    target = sandbox / "pets.csv"
    target.write_text(EXAMPLE_CSV.read_text("utf-8"), "utf-8")
    return target
