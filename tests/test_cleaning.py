import pytest

from src.cleaning import (
    clean_page_text,
    collapse_whitespace,
    join_hyphenated_linebreaks,
    remove_invisible_characters,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("nor​mal", "normal"),
        ("zero‌width‍joiner", "zerowidthjoiner"),
        ("﻿leading BOM", "leading BOM"),
        ("nothing to strip", "nothing to strip"),
    ],
)
def test_remove_invisible_characters(raw, expected):
    assert remove_invisible_characters(raw) == expected


def test_remove_invisible_characters_does_not_insert_spaces():
    """A zero-width space is a line-break hint, not a word separator."""
    assert remove_invisible_characters("algo​rithm") == "algorithm"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("algo-\nrithm", "algorithm"),
        ("algo- \n rithm", "algorithm"),
        ("well-known term", "well-known term"),  # hyphen without a line break
        ("dash -\nnot a word break", "dash -\nnot a word break"),
    ],
)
def test_join_hyphenated_linebreaks(raw, expected):
    assert join_hyphenated_linebreaks(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("a\nb", "a b"),
        ("a  \t b", "a b"),
        ("  padded  ", "padded"),
        ("multi\n\n\nline", "multi line"),
    ],
)
def test_collapse_whitespace(raw, expected):
    assert collapse_whitespace(raw) == expected


def test_clean_page_text_removes_newlines():
    """Regression: the previous implementation left every newline in place."""
    assert "\n" not in clean_page_text("first line\nsecond line")


def test_clean_page_text_runs_steps_in_order():
    """De-hyphenation must see the newline, so it has to run before collapsing."""
    raw = "An algo-\nrithm is a proce​dure.\nIt terminates."
    assert clean_page_text(raw) == "An algorithm is a procedure. It terminates."


@pytest.mark.parametrize("empty", ["", None])
def test_clean_page_text_handles_empty_input(empty):
    assert clean_page_text(empty) == ""


def test_clean_page_text_is_idempotent():
    once = clean_page_text("An algo-\nrithm is a proce​dure.")
    assert clean_page_text(once) == once
