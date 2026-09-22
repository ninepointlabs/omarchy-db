"""The import guesses a type for each column. These lock the rules down."""

from __future__ import annotations

import pytest

from omarchy_db.fields import BOOLEAN, DATE, INTEGER, REAL, TEXT, coerce, unique_names
from omarchy_db.infer import infer_column_type, infer_fields


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1", "2", "-3"], INTEGER),
        (["1", "2.5"], REAL),
        (["1,200", "3,400"], INTEGER),
        (["yes", "no", "TRUE"], BOOLEAN),
        (["2024-01-02", "2024/03/04"], DATE),
        (["03/04/2024", "05/06/2024"], DATE),
        (["Rex", "Milo"], TEXT),
        (["1", "Rex"], TEXT),
        (["1e400", "2"], TEXT),
        ([], TEXT),
        (["", "  "], TEXT),
        ([None, "7"], INTEGER),
    ],
)
def test_column_types(values, expected):
    assert infer_column_type(values) == expected


def test_blanks_never_decide_the_type():
    assert infer_column_type(["", "4", None, "  ", "5"]) == INTEGER


def test_zero_and_one_read_as_yes_no_before_number():
    # 0/1 is a yes/no column far more often than it is a count.
    assert infer_column_type(["0", "1", "1"]) == BOOLEAN


def test_infer_fields_uses_headings_for_labels():
    fields = infer_fields(["First Name", "Age"], [["Ada", "36"], ["Grace", "45"]])
    assert [f.name for f in fields] == ["first_name", "age"]
    assert [f.type for f in fields] == [TEXT, INTEGER]
    assert fields[0].label == "First Name"


def test_headings_are_made_safe_and_unique():
    assert unique_names(["First Name", "first name", "2024 ($)", ""]) == [
        "first_name",
        "first_name_2",
        "c_2024",
        "field_4",
    ]


def test_ragged_rows_do_not_crash_inference():
    fields = infer_fields(["a", "b", "c"], [["1"], ["2", "x"], ["3", "y", "2024-01-01"]])
    assert [f.type for f in fields] == [INTEGER, TEXT, DATE]


@pytest.mark.parametrize(
    ("raw", "kind", "expected"),
    [
        ("  7 ", INTEGER, 7),
        ("1,234", INTEGER, 1234),
        ("2.50", REAL, 2.5),
        ("Y", BOOLEAN, True),
        ("off", BOOLEAN, False),
        ("", TEXT, None),
        ("   ", INTEGER, None),
    ],
)
def test_coerce(raw, kind, expected):
    assert coerce(raw, kind) == expected


def test_coerce_refuses_nonsense():
    with pytest.raises(ValueError):
        coerce("maybe", BOOLEAN)
    with pytest.raises(ValueError):
        coerce("someday", DATE)
