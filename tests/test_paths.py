"""Path safety: nothing outside the approved roots, ever."""

from __future__ import annotations

from pathlib import Path

import pytest

from omarchy_db.errors import PathNotAllowed
from omarchy_db.paths import database_path, resolve_under_roots, state_dir


def test_a_plain_path_inside_the_root_is_fine(sandbox: Path):
    assert resolve_under_roots(str(sandbox / "notes.csv")) == sandbox / "notes.csv"


def test_nested_new_file_is_fine(sandbox: Path):
    target = sandbox / "deep" / "deeper" / "new.csv"
    assert resolve_under_roots(str(target)) == target


@pytest.mark.parametrize(
    "attempt",
    [
        "../escape.csv",
        "../../etc/passwd",
        "sub/../../escape.csv",
        "/etc/passwd",
        "/etc/./passwd",
        "~root/.bashrc",
    ],
)
def test_traversal_is_refused(sandbox: Path, attempt: str):
    candidate = attempt if attempt.startswith(("/", "~")) else str(sandbox / attempt)
    with pytest.raises(PathNotAllowed):
        resolve_under_roots(candidate)


def test_a_symlink_pointing_out_is_refused(sandbox: Path):
    link = sandbox / "shortcut"
    link.symlink_to("/etc")
    with pytest.raises(PathNotAllowed):
        resolve_under_roots(str(link / "passwd"))


def test_a_symlinked_parent_of_a_new_file_is_refused(sandbox: Path):
    link = sandbox / "outside"
    link.symlink_to("/tmp")
    with pytest.raises(PathNotAllowed):
        resolve_under_roots(str(link / "brand-new.csv"))


def test_empty_and_null_paths_are_refused(sandbox: Path):
    with pytest.raises(PathNotAllowed):
        resolve_under_roots("")
    with pytest.raises(PathNotAllowed):
        resolve_under_roots("file\x00.csv")


def test_must_exist_is_enforced(sandbox: Path):
    with pytest.raises(PathNotAllowed):
        resolve_under_roots(str(sandbox / "missing.csv"), must_exist=True)


def test_database_path_adds_the_suffix(sandbox: Path):
    assert database_path(str(sandbox / "pets")).name == "pets.omadb"
    assert database_path(str(sandbox / "pets.sqlite")).name == "pets.sqlite"


def test_state_dir_is_owner_only(sandbox: Path):
    directory = state_dir()
    assert directory.is_dir()
    assert oct(directory.stat().st_mode)[-3:] == "700"
