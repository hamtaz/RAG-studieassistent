# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG-based study assistant ("studieassistent"): PDF → text → chunks → embeddings → Azure Cosmos DB (NoSQL API) vector search. `plan.md` holds the author's 7-step roadmap (in Norwegian); steps 1–2 (extraction/chunking, embeddings + Cosmos storage) are implemented. Steps 3–7 (Azure AI Foundry LLM calls, content safety, FastAPI, MCP server, deploy) are not built yet.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1        # activate the venv (Python 3.13)
pip install -r requirements.txt

python main.py                       # full ingestion pipeline: PDF → chunks → embed → upsert to Cosmos

pytest                               # unit tests (offline: no Azure credentials needed)
pytest tests/test_chunking.py -k overlap    # single file / single test

python -m scripts.verify_cosmos_connection  # verify Cosmos creds + vector policy/index + doc count
python -m scripts.verify_vector_search      # end-to-end vector search against stored chunks
python -m src.embeddings                    # smoke-test the embedding deployment, prints dimensions
```

`tests/` holds real pytest tests and is the only thing pytest collects (`testpaths` in `pytest.ini`). They cover the pure functions only — `cleaning`, `chunking`, and `get_file_hash` — so they need no network and no Azure credentials. `pytest.ini` sets `pythonpath = .` so `import src.*` resolves without an install step.

The `scripts/` files are *not* tests: they are manual verification scripts that hit live Azure. They are named `verify_*` precisely so pytest does not collect them. Run them from the repo root with `python -m`, never `python scripts/foo.py`.

There is no linter, type checker, or build step yet.

## Environment

All Azure config comes from a gitignored `.env` at the repo root:

- `COSMOS_URI`, `COSMOS_KEY` — required; `get_container()` raises without them
- `COSMOS_DATABASE_NAME` (default `studieassistent`), `COSMOS_CONTAINER_NAME` (default `chunk`)
- `AZURE_AI_ENDPOINT`, `AZURE_AI_KEY`, `AZURE_AI_DEPLOYMENT_NAME` — the embedding deployment

Gotcha: `src/embeddings.py` constructs the `AzureOpenAI` client at module import time, so *importing* it (directly or transitively via `main.py`) fails if the Azure vars are missing — not just calling `get_embedding`. This is why the test suite covers `cleaning`/`chunking`/`extraction` but not `embeddings`. The Cosmos container must be created ahead of time with a `vectorEmbeddingPolicy` and matching `vectorIndexes` on `/embedding`; nothing in the code provisions it. `scripts/verify_cosmos_connection.py` is the tool for confirming that setup.

## Pipeline architecture

`main.py` wires the `src/` modules in sequence; each has a single responsibility and passes plain dataclasses forward:

1. **`extraction.py`** — `load_pdf_document()` opens the PDF with pdfplumber and emits one `SourceDocument` **per page**, each carrying a `document_hash` (first 12 hex chars of the file's SHA-256). Page text passes through `cleaning.clean_page_text()`.
2. **`cleaning.py`** — an ordered pipeline of named, individually-tested steps (`CLEANING_STEPS`): strip zero-width characters, rejoin words hyphenated across a line break, then collapse all whitespace. Order is load-bearing — de-hyphenation needs the newlines that the collapse step removes. This is the **only** place text is normalized, so what Cosmos stores is exactly what was embedded.
3. **`chunking.py`** — `chunk_document()` is the entry point and takes the **whole document** as `(page_number, text)` pairs. It concatenates the pages first, then splits, so a sentence spanning a page break stays whole and the document has exactly **one** tail instead of one per page. `_split_sentence_spans()` splits on `(?<=[.!?])\s+(?=[A-Z])`, keeping terminal punctuation (the delimiter is inside a lookbehind, so only whitespace is consumed), rejoins fragments cut after an abbreviation or an initial, and tracks each sentence's character offset — that offset is how a chunk resolves back to a page. Chunks close *before* adding a sentence that would exceed `max_word`, carry `overlap_sentences` forward, and apply `min_word` **only to the tail** (an undersized final chunk merges back into its predecessor, minus the already-stored overlap, rather than being emitted as a fragment). Each `Chunk` records `page_number` (page it starts on) and `page_end` (page it ends on); `id` is a counter **global to the document**. `chunk_text()` remains as a single-page wrapper — convenience and tests only, not the ingestion path.
4. **`embeddings.py`** — `embed_and_store()` embeds each chunk, then builds the Cosmos document id as `{document_hash}_{page_number}_{chunk.id}`. That composition is what makes ids globally unique despite the per-page counter, and it makes writes idempotent: re-running `main.py` on the same PDF upserts over the same documents instead of duplicating them. Failures are collected per chunk and reported at the end rather than aborting the run. `get_embedding()` deliberately does **not** normalize its input — `cleaning.py` owns that, and normalizing twice would embed a different string than the one stored.
5. **`cosmos_client.py`** — key-based `ContainerProxy` factory, injected into `embed_and_store()` so storage stays decoupled from embedding.

Retrieval (`scripts/verify_vector_search.py`) embeds the query with the *same* deployment and orders by `VectorDistance(c.embedding, @query_embedding)` — query and stored embeddings must always come from one model, so changing `AZURE_AI_DEPLOYMENT_NAME` invalidates everything already in the container.

## Conventions and known rough edges

- `main.py` passes `min_word=200, max_word=350, overlap_sentences=2`. On `data/cs-concepts.pdf` (28 pages) that yields 43 chunks, mean 333 words, with 1 chunk over budget. `notes.md` predates document-level chunking and describes the old per-page behavior it was written to work around.
- Chunks can still exceed `max_word` in two documented cases: a single sentence longer than the budget, and the one undersized tail being merged back. Both are tested (`test_tail_merge_may_exceed_max_word`) — treat them as intended, not as bugs to fix.
- Sentence splitting is a hand-rolled regex plus an abbreviation list, not a real segmenter. It is a deliberate trade-off against a spaCy/`pysbd` dependency; extend `ABBREVIATIONS` in `chunking.py` when a new false split shows up, and add a case to `tests/test_chunking.py` alongside it.
- Comments and console output mix Norwegian and English; match the surrounding file rather than normalizing.
- `container/config.py` is an empty placeholder for Cosmos container provisioning config.
- This is a learning project — the author is a third-year engineering student who has asked (in `plan.md`) for concepts to be explained alongside code, not just code handed over.
