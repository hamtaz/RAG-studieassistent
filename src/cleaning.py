import re

# Zero-width and BOM characters that PDF extraction leaves behind.
INVISIBLE_CHARACTERS = re.compile(r"[​‌‍⁠﻿]")

# A word broken across a line break: "algo-\nrithm" -> "algorithm".
HYPHENATED_LINEBREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")

WHITESPACE = re.compile(r"\s+")


def remove_invisible_characters(text: str) -> str:
    """Delete zero-width characters outright.

    They are line-break hints, not word separators, so replacing them with a
    space would split words that belong together.
    """
    return INVISIBLE_CHARACTERS.sub("", text)


def join_hyphenated_linebreaks(text: str) -> str:
    """Reassemble words the PDF layout split across two lines."""
    return HYPHENATED_LINEBREAK.sub(r"\1\2", text)


def collapse_whitespace(text: str) -> str:
    """Flatten newlines, tabs and runs of spaces into single spaces."""
    return WHITESPACE.sub(" ", text).strip()


# Order matters: invisible characters go first so they cannot hide inside a
# hyphen break, and whitespace collapses last so the newlines the earlier
# steps depend on are still present when those steps run.
CLEANING_STEPS = (
    remove_invisible_characters,
    join_hyphenated_linebreaks,
    collapse_whitespace,
)


def clean_page_text(text: str) -> str:
    """Normalize one page of extracted PDF text.

    This is the single place where text is normalized, so what gets stored in
    Cosmos is exactly what gets embedded.

    Not handled yet: repeating headers/footers and page numbers, which need
    cross-page comparison rather than a per-page rule.
    """
    if not text:
        return ""

    for step in CLEANING_STEPS:
        text = step(text)
    return text
