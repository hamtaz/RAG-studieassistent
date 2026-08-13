# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG-based study assistant ("studieassistent"): PDF → text → chunks → embeddings → Azure Cosmos DB (NoSQL API) vector search. `plan.md` holds the author's 7-step roadmap (in Norwegian); steps 1–2 (extraction/chunking, embeddings + Cosmos storage) are implemented. Steps 3–7 (Azure AI Foundry LLM calls, content safety, FastAPI, MCP server, deploy) are not built yet.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1        # activate the venv (Python 3.13)
pip install -r requirements.txt

python main.py                       # full ingestion pipeline: PDF → chunks → embed → upsert to Cosmos
python -m scripts.test_cosmos_connection   # verify Cosmos creds + vector policy/index + doc count
python -m scripts.test_vector_search       # end-to-end vector search against stored chunks
python -m src.embeddings                   # smoke-test the embedding deployment, prints dimensions
```

There is no test framework, linter, or build step. The `scripts/` files are manual verification scripts run as modules (they import `src.*`), not pytest tests — always run them from the repo root with `python -m`, never `python scripts/foo.py`.

## Environment

All Azure config comes from a gitignored `.env` at the repo root:

- `COSMOS_URI`, `COSMOS_KEY` — required; `get_container()` raises without them
- `COSMOS_DATABASE_NAME` (default `studieassistent`), `COSMOS_CONTAINER_NAME` (default `chunk`)
- `AZURE_AI_ENDPOINT`, `AZURE_AI_KEY`, `AZURE_AI_DEPLOYMENT_NAME` — the embedding deployment

Gotcha: `src/embeddings.py` constructs the `AzureOpenAI` client at module import time, so *importing* it (directly or transitively via `main.py`) fails if the Azure vars are missing — not just calling `get_embedding`. The Cosmos container must be created ahead of time with a `vectorEmbeddingPolicy` and matching `vectorIndexes` on `/embedding`; nothing in the code provisions it. `scripts/test_cosmos_connection.py` is the tool for confirming that setup.

## Pipeline architecture

`main.py` wires four `src/` modules in sequence; each has a single responsibility and passes plain dataclasses forward:

1. **`extraction.py`** — `load_pdf_document()` opens the PDF with pdfplumber and emits one `SourceDocument` **per page**, each carrying a `document_hash` (first 12 hex chars of the file's SHA-256). Page text passes through `cleaning.clean_page_text()` (currently just zero-width-space removal).
2. **`chunking.py`** — `chunk_text()` runs per page, splitting on sentence boundaries via regex and accumulating sentences until the word budget is hit, then carrying `overlap_sentences` forward into the next chunk. Emits `Chunk` dataclasses whose `id` is a counter **local to that page**.
3. **`embeddings.py`** — `embed_and_store()` embeds each chunk, then builds the Cosmos document id as `{document_hash}_{page_number}_{chunk.id}`. That composition is what makes ids globally unique despite the per-page counter, and it makes writes idempotent: re-running `main.py` on the same PDF upserts over the same documents instead of duplicating them. Failures are collected per chunk and reported at the end rather than aborting the run.
4. **`cosmos_client.py`** — key-based `ContainerProxy` factory, injected into `embed_and_store()` so storage stays decoupled from embedding.

Retrieval (`scripts/test_vector_search.py`) embeds the query with the *same* deployment and orders by `VectorDistance(c.embedding, @query_embedding)` — query and stored embeddings must always come from one model, so changing `AZURE_AI_DEPLOYMENT_NAME` invalidates everything already in the container.

## Conventions and known rough edges

- Chunking per page (rather than over the concatenated PDF) means chunks can end mid-sentence; `notes.md` documents shrinking the word budget to 200–350 to compensate, but `main.py` still passes `min_word=300, max_word=500`. Confirm the intended values with the user before changing either side.
- Comments and console output mix Norwegian and English; match the surrounding file rather than normalizing.
- `container/config.py` is an empty placeholder for Cosmos container provisioning config.
- This is a learning project — the author is a third-year engineering student who has asked (in `plan.md`) for concepts to be explained alongside code, not just code handed over.
