import re
from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Optional


@dataclass
class Chunk:
    id: int
    chunk_text: str
    source_name: str
    wordcount: int
    document_hash: str
    page_number: Optional[int] = None  # page the chunk starts on
    page_end: Optional[int] = None  # page the chunk ends on, if it spans several


# Sentence-ending punctuation, whitespace, then a capital (optionally behind an
# opening quote or bracket). The punctuation sits in a lookbehind and the
# capital in a lookahead, so only the whitespace between them is consumed -
# each sentence keeps its own terminator.
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z])")

# A period after one of these is a title or an abbreviation, not a sentence end.
ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st",
        "e.g", "i.e", "etc", "vs", "cf", "al", "approx",
        "fig", "no", "vol", "pp", "inc", "ltd", "co",
    }
)

LAST_TOKEN = re.compile(r"(\S+)\s*$")

# A sentence paired with its character offset in the document text.
PositionedSentence = tuple[str, int]


def _ends_with_abbreviation(sentence: str) -> bool:
    """True if this fragment was cut after an abbreviation or an initial.

    Decimals such as "3.5" need no handling here: the boundary pattern requires
    whitespace after the period, and there is none inside a number.
    """
    if not sentence.endswith("."):
        return False

    match = LAST_TOKEN.search(sentence)
    if not match:
        return False

    token = match.group(1).rstrip(".").lower()
    if len(token) == 1 and token.isalpha():
        return True  # a single initial, as in "J. R. Tolkien"
    return token in ABBREVIATIONS


def _split_sentence_spans(text: str) -> list[PositionedSentence]:
    """Split into sentences, keeping each one's offset in `text`.

    The offsets are what let a chunk report which page it came from once pages
    have been concatenated into a single document.
    """
    if not text or not text.strip():
        return []

    fragments: list[PositionedSentence] = []
    start = 0
    for match in SENTENCE_BOUNDARY.finditer(text):
        fragments.append((text[start : match.start()], start))
        start = match.end()
    fragments.append((text[start:], start))

    # Re-join anything the pattern cut at an abbreviation, keeping the offset
    # of the fragment the sentence actually started at.
    sentences: list[PositionedSentence] = []
    for sentence, offset in fragments:
        if sentences and _ends_with_abbreviation(sentences[-1][0]):
            previous, previous_offset = sentences[-1]
            sentences[-1] = (f"{previous} {sentence}", previous_offset)
        else:
            sentences.append((sentence, offset))

    return [(sentence, offset) for sentence, offset in sentences if sentence.strip()]


def split_sentence(text: str) -> list[str]:
    """Split text into sentences, keeping terminal punctuation intact."""
    return [sentence for sentence, _ in _split_sentence_spans(text)]


def _join_pages(pages: Sequence[tuple[int, str]]) -> tuple[str, list[tuple[int, int]]]:
    """Concatenate page texts, recording where each page starts.

    Joining before splitting is the whole point of document-level chunking: a
    sentence running across a page break is healed here, instead of being cut
    in half by chunking each page in isolation.
    """
    parts: list[str] = []
    page_starts: list[tuple[int, int]] = []
    cursor = 0

    for page_number, text in pages:
        text = text.strip() if text else ""
        if not text:
            continue

        if parts:
            parts.append(" ")
            cursor += 1

        page_starts.append((cursor, page_number))
        parts.append(text)
        cursor += len(text)

    return "".join(parts), page_starts


def _page_lookup(page_starts: Sequence[tuple[int, int]]) -> Callable[[int], Optional[int]]:
    """Build an offset -> page number resolver over sorted page start offsets."""
    offsets = [offset for offset, _ in page_starts]
    numbers = [number for _, number in page_starts]

    def page_at(offset: int) -> Optional[int]:
        if not offsets:
            return None
        index = max(bisect_right(offsets, offset) - 1, 0)
        return numbers[index]

    return page_at


def chunk_document(
    pages: Sequence[tuple[int, str]],
    source_name: str,
    document_hash: str,
    min_word: int,
    max_word: int,
    overlap_sentences: int,
) -> list[Chunk]:
    """Chunk a whole document given its pages as (page_number, text) pairs.

    Pages are concatenated first, then split into sentences, so sentences that
    run across a page break stay whole and the document has exactly one tail
    instead of one per page. Each chunk records the page it starts on
    (`page_number`) and the page it ends on (`page_end`).

    Consecutive chunks share their last `overlap_sentences` sentences so a fact
    split across a boundary still appears whole in one of them.

    `min_word` applies to the final chunk only. Mid-document chunks are bounded
    by `max_word` by construction, but the tail is whatever is left over, and a
    stray fragment embeds poorly and pollutes search results.

    Two cases deliberately exceed `max_word`, because the alternatives are
    worse: a single sentence longer than the budget (splitting it would break
    the sentence boundaries this module exists to preserve), and an undersized
    tail merged back into its predecessor (a short fragment retrieves worse
    than an oversized chunk). Chunking per document rather than per page keeps
    the second case rare - there is only one tail to merge.
    """
    if min_word > max_word:
        raise ValueError(f"min_word ({min_word}) must not exceed max_word ({max_word})")
    if overlap_sentences < 0:
        raise ValueError(f"overlap_sentences ({overlap_sentences}) must not be negative")

    text, page_starts = _join_pages(pages)
    sentences = _split_sentence_spans(text)
    if not sentences:
        return []

    page_at = _page_lookup(page_starts)

    chunks: list[Chunk] = []
    current: list[PositionedSentence] = []
    current_words = 0
    carried = 0  # leading sentences in `current` reused from the previous chunk

    def build(items: list[PositionedSentence], wordcount: int) -> Chunk:
        return Chunk(
            id=len(chunks),
            chunk_text=" ".join(sentence for sentence, _ in items),
            source_name=source_name,
            wordcount=wordcount,
            document_hash=document_hash,
            page_number=page_at(items[0][1]),
            page_end=page_at(items[-1][1]),
        )

    for sentence, offset in sentences:
        words = len(sentence.split())

        # Close the chunk before adding, so max_word is a real ceiling. A single
        # sentence longer than the budget still gets through - splitting it
        # would break the sentence boundaries this module preserves.
        if current and current_words + words > max_word:
            chunks.append(build(current, current_words))
            current = current[-overlap_sentences:] if overlap_sentences else []
            carried = len(current)
            current_words = sum(len(carried_.split()) for carried_, _ in current)

        current.append((sentence, offset))
        current_words += words

    fresh = current[carried:]
    if not fresh:
        # Everything left is overlap already stored in the previous chunk.
        return chunks

    if chunks and current_words < min_word:
        # Undersized tail: fold the new sentences into the previous chunk
        # rather than emitting a fragment. Only the sentences that are not
        # already there, otherwise the overlap would be duplicated.
        previous = chunks[-1]
        merged_text = f"{previous.chunk_text} {' '.join(sentence for sentence, _ in fresh)}"
        chunks[-1] = replace(
            previous,
            chunk_text=merged_text,
            wordcount=len(merged_text.split()),
            page_end=page_at(fresh[-1][1]),
        )
    else:
        chunks.append(build(current, current_words))

    return chunks


def chunk_text(
    text: str,
    source_name: str,
    page_number: int,
    document_hash: str,
    min_word: int,
    max_word: int,
    overlap_sentences: int,
) -> list[Chunk]:
    """Chunk a single page. Convenience wrapper around `chunk_document()`.

    Prefer `chunk_document()` for real ingestion: chunking page by page cuts
    sentences at page breaks and gives every page its own undersized tail.
    """
    return chunk_document(
        [(page_number, text)],
        source_name=source_name,
        document_hash=document_hash,
        min_word=min_word,
        max_word=max_word,
        overlap_sentences=overlap_sentences,
    )
