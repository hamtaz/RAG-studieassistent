import pytest

from src.chunking import Chunk, chunk_document, chunk_text, split_sentence

SOURCE = "test.pdf"
HASH = "abc123def456"
PAGE = 1


def make_document(pages, min_word=10, max_word=20, overlap_sentences=1):
    return chunk_document(
        pages,
        source_name=SOURCE,
        document_hash=HASH,
        min_word=min_word,
        max_word=max_word,
        overlap_sentences=overlap_sentences,
    )


def make_chunks(text, min_word=10, max_word=20, overlap_sentences=1):
    return chunk_text(
        text,
        source_name=SOURCE,
        page_number=PAGE,
        document_hash=HASH,
        min_word=min_word,
        max_word=max_word,
        overlap_sentences=overlap_sentences,
    )


def sentence_of(word_count, word="word"):
    """A sentence of exactly `word_count` words, ending in a period."""
    return " ".join([word.capitalize()] + [word] * (word_count - 1)) + "."


# --- split_sentence -------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("One. Two.", ["One.", "Two."]),
        ("Bang! Boom?", ["Bang!", "Boom?"]),
        ("Single sentence.", ["Single sentence."]),
        ("No terminator", ["No terminator"]),
    ],
)
def test_split_sentence_keeps_terminal_punctuation(text, expected):
    """Regression: the old pattern consumed the delimiter and dropped it."""
    assert split_sentence(text) == expected


def test_split_sentence_does_not_lose_characters():
    text = "The cat sat on the mat. Then it left! Was it happy?"
    assert "".join(split_sentence(text)).replace(" ", "") == text.replace(" ", "")


@pytest.mark.parametrize(
    "text",
    [
        "Dr. Smith saw it.",
        "Use spaCy, e.g. for segmentation.",
        "See Fig. 4 for details.",
        "Written by J. R. Tolkien in 1937.",
    ],
)
def test_split_sentence_does_not_split_abbreviations(text):
    assert split_sentence(text) == [text]


def test_split_sentence_does_not_split_decimals():
    assert split_sentence("The value is 3.5 meters. Next.") == [
        "The value is 3.5 meters.",
        "Next.",
    ]


def test_split_sentence_splits_after_abbreviation_when_sentence_really_ends():
    assert split_sentence("Ask Dr. Smith. Then leave.") == [
        "Ask Dr. Smith.",
        "Then leave.",
    ]


@pytest.mark.parametrize("empty", ["", "   ", "\n"])
def test_split_sentence_on_empty_input(empty):
    assert split_sentence(empty) == []


# --- chunk_text: empty and degenerate input -------------------------------


@pytest.mark.parametrize("empty", ["", "   ", "\n\n"])
def test_chunk_text_on_empty_input_produces_nothing(empty):
    """Regression: empty pages used to yield an empty chunk sent to the API."""
    assert make_chunks(empty) == []


def test_chunk_text_never_emits_empty_text():
    chunks = make_chunks(" ".join(sentence_of(5) for _ in range(20)))
    assert all(chunk.chunk_text.strip() for chunk in chunks)
    assert all(chunk.wordcount > 0 for chunk in chunks)


def test_chunk_text_keeps_short_page_that_has_no_predecessor():
    """A whole page under min_word is still worth storing."""
    chunks = make_chunks("Short page.", min_word=100, max_word=200)
    assert len(chunks) == 1
    assert chunks[0].chunk_text == "Short page."


# --- chunk_text: size bounds ----------------------------------------------


def test_chunks_respect_max_word():
    text = " ".join(sentence_of(5) for _ in range(30))
    for chunk in make_chunks(text, min_word=10, max_word=20):
        assert chunk.wordcount <= 20


def test_tail_merge_may_exceed_max_word():
    """Documented trade-off: an oversized chunk beats a stray fragment.

    Five 9-word sentences pack two per chunk, leaving a 9-word tail. With
    min_word=20 that tail is folded back into the previous 18-word chunk,
    pushing it to 27 words - past max_word.
    """
    text = " ".join(sentence_of(9) for _ in range(5))
    chunks = make_chunks(text, min_word=20, max_word=20, overlap_sentences=0)

    assert len(chunks) >= 2
    assert chunks[-1].wordcount > 20


def test_oversized_single_sentence_is_not_split():
    """Splitting mid-sentence would defeat the point of sentence chunking."""
    chunks = make_chunks(sentence_of(50), min_word=10, max_word=20)
    assert len(chunks) == 1
    assert chunks[0].wordcount == 50


def test_undersized_tail_is_merged_into_previous_chunk():
    """Regression: min_word was dead code, so tails came out as fragments."""
    text = " ".join(sentence_of(9) for _ in range(5))
    chunks = make_chunks(text, min_word=15, max_word=20, overlap_sentences=0)

    assert len(chunks) >= 2
    assert chunks[-1].wordcount >= 15


def test_merged_tail_does_not_duplicate_overlap():
    text = " ".join(sentence_of(9) for _ in range(5))
    chunks = make_chunks(text, min_word=15, max_word=20, overlap_sentences=1)

    last = chunks[-1]
    assert last.wordcount == len(last.chunk_text.split())
    # No sentence appears twice inside a single chunk.
    sentences = [s for s in last.chunk_text.split(". ") if s]
    assert len(sentences) == len(set(sentences))


def test_wordcount_matches_text():
    text = " ".join(sentence_of(7) for _ in range(15))
    for chunk in make_chunks(text):
        assert chunk.wordcount == len(chunk.chunk_text.split())


# --- chunk_text: overlap and metadata -------------------------------------


def test_overlap_repeats_trailing_sentences_in_next_chunk():
    text = " ".join(f"Sentence number {i} here is padding words." for i in range(12))
    chunks = make_chunks(text, min_word=1, max_word=20, overlap_sentences=1)

    assert len(chunks) >= 2
    previous_last = chunks[0].chunk_text.split(". ")[-1]
    assert chunks[1].chunk_text.startswith(previous_last.rstrip("."))


def test_zero_overlap_produces_no_repeats():
    text = " ".join(sentence_of(5) for _ in range(20))
    chunks = make_chunks(text, min_word=1, max_word=20, overlap_sentences=0)

    combined = sum(chunk.wordcount for chunk in chunks)
    assert combined == 20 * 5


def test_ids_are_sequential_within_a_page():
    text = " ".join(sentence_of(5) for _ in range(30))
    chunks = make_chunks(text)
    assert [chunk.id for chunk in chunks] == list(range(len(chunks)))


def test_metadata_is_carried_onto_every_chunk():
    chunks = make_chunks(" ".join(sentence_of(5) for _ in range(20)))
    assert chunks
    for chunk in chunks:
        assert isinstance(chunk, Chunk)
        assert chunk.source_name == SOURCE
        assert chunk.document_hash == HASH
        assert chunk.page_number == PAGE


# --- chunk_text: argument validation --------------------------------------


def test_min_word_above_max_word_is_rejected():
    with pytest.raises(ValueError, match="min_word"):
        make_chunks("Some text.", min_word=500, max_word=300)


def test_negative_overlap_is_rejected():
    with pytest.raises(ValueError, match="overlap_sentences"):
        make_chunks("Some text.", overlap_sentences=-1)


# --- chunk_document: page handling ----------------------------------------


def test_sentence_spanning_a_page_break_is_healed():
    """The reason document-level chunking exists.

    Page 1 ends mid-sentence and page 2 continues it. Chunked per page that is
    two fragments; chunked per document it is one sentence.
    """
    pages = [(1, "An algorithm is a finite sequence of"), (2, "well-defined instructions.")]
    chunks = make_document(pages, min_word=1, max_word=100)

    assert len(chunks) == 1
    assert chunks[0].chunk_text == ("An algorithm is a finite sequence of well-defined instructions.")


def test_document_has_only_one_tail():
    """Per page, every page contributes a tail; per document there is one."""
    pages = [(number, " ".join(sentence_of(9) for _ in range(3))) for number in range(1, 6)]

    per_page = [
        chunk
        for number, text in pages
        for chunk in make_chunks(text, min_word=20, max_word=25, overlap_sentences=0)
    ]
    per_document = make_document(pages, min_word=20, max_word=25, overlap_sentences=0)

    oversized_per_page = sum(1 for chunk in per_page if chunk.wordcount > 25)
    oversized_per_document = sum(1 for chunk in per_document if chunk.wordcount > 25)
    assert oversized_per_document < oversized_per_page


def test_chunks_report_the_page_they_start_on():
    pages = [(number, " ".join(sentence_of(10) for _ in range(2))) for number in (1, 2, 3)]
    chunks = make_document(pages, min_word=1, max_word=20, overlap_sentences=0)

    assert [chunk.page_number for chunk in chunks] == [1, 2, 3]


def test_chunk_spanning_pages_records_start_and_end():
    pages = [(1, sentence_of(10)), (2, sentence_of(10))]
    chunks = make_document(pages, min_word=1, max_word=100)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].page_end == 2


def test_single_page_chunk_starts_and_ends_on_that_page():
    chunks = make_document([(7, sentence_of(10))], min_word=1, max_word=100)
    assert chunks[0].page_number == 7
    assert chunks[0].page_end == 7


def test_blank_pages_are_skipped_without_shifting_page_numbers():
    pages = [(1, ""), (2, "   "), (3, sentence_of(10))]
    chunks = make_document(pages, min_word=1, max_word=100)

    assert len(chunks) == 1
    assert chunks[0].page_number == 3


def test_document_with_no_text_produces_nothing():
    assert make_document([(1, ""), (2, "   ")]) == []
    assert make_document([]) == []


def test_ids_are_sequential_across_the_whole_document():
    pages = [(number, " ".join(sentence_of(10) for _ in range(3))) for number in (1, 2, 3)]
    chunks = make_document(pages, min_word=1, max_word=20, overlap_sentences=0)

    assert [chunk.id for chunk in chunks] == list(range(len(chunks)))
    assert len({chunk.id for chunk in chunks}) == len(chunks)
