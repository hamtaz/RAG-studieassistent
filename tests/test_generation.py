from src.generation import SYSTEM_PROMPT, build_prompt

SAMPLE_CHUNKS = [
    {"source_name": "cs-concepts.pdf", "page_number": 4, "page_end": 4, "chunk_text": "An algorithm is..."},
    {"source_name": "cs-concepts.pdf", "page_number": 7, "page_end": 8, "chunk_text": "Big-O notation..."},
]


def test_build_prompt_includes_system_prompt():
    messages = build_prompt("What is an algorithm?", SAMPLE_CHUNKS)
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_build_prompt_includes_question():
    messages = build_prompt("What is an algorithm?", SAMPLE_CHUNKS)
    assert "What is an algorithm?" in messages[1]["content"]


def test_build_prompt_cites_single_page():
    messages = build_prompt("q", SAMPLE_CHUNKS)
    assert "cs-concepts.pdf, p. 4)" in messages[1]["content"]


def test_build_prompt_cites_page_range():
    messages = build_prompt("q", SAMPLE_CHUNKS)
    assert "cs-concepts.pdf, p. 7-8)" in messages[1]["content"]


def test_build_prompt_includes_chunk_text():
    messages = build_prompt("q", SAMPLE_CHUNKS)
    assert "An algorithm is..." in messages[1]["content"]
    assert "Big-O notation..." in messages[1]["content"]


def test_build_prompt_handles_no_context():
    messages = build_prompt("q", [])
    assert "none found" in messages[1]["content"]
