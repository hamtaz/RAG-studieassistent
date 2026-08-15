# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG-based study assistant ("studieassistent"): PDF → text → chunks → embeddings → Azure Cosmos DB (NoSQL API) vector search. `plan.md` holds the author's 7-step roadmap (in Norwegian); steps 1–2 (extraction/chunking, embeddings + Cosmos storage) are implemented. Steps 3–7 (Azure AI Foundry LLM calls, content safety, FastAPI, MCP server, deploy) are not built yet.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1        # activate the venv (Python 3.13)
pip install -e ".[dev]"              # runtime deps + pytest, from pyproject.toml

python main.py                       # full ingestion pipeline: PDF → chunks → embed → upsert to Cosmos

pytest                               # unit tests (offline: no Azure credentials needed)
pytest tests/test_chunking.py -k overlap    # single file / single test

ruff check .                         # lint
ruff format .                        # format (ruff format --check . in CI)
mypy src main.py                     # type check — scoped, see below

python -m scripts.verify_cosmos_connection  # verify Cosmos creds + vector policy/index + doc count
python -m scripts.verify_vector_search      # end-to-end vector search against stored chunks
python -m src.embeddings                    # smoke-test the embedding deployment, prints dimensions

python -m scripts.evaluate_retrieval                          # score retrieval: recall@k + MRR against data/eval_questions.json
python -m scripts.evaluate_retrieval --questions other.json   # score a different document's eval set
```

`tests/` holds real pytest tests and is the only thing pytest collects (`testpaths` under `[tool.pytest.ini_options]` in `pyproject.toml`). They cover the pure functions only — `cleaning`, `chunking`, and `get_file_hash` — so they need no network and no Azure credentials. That same section sets `pythonpath = ["."]` so `import src.*` resolves without an install step.

The `scripts/` files are *not* tests: they are manual verification scripts that hit live Azure. They are named `verify_*` precisely so pytest does not collect them. Run them from the repo root with `python -m`, never `python scripts/foo.py`.

`mypy` is scoped to `src/` and `main.py` only (the `mypy src main.py` invocation, not a `[tool.mypy]` file-discovery setting) — `scripts/` are one-off manual checks and `tests/` are pytest tests, where full annotation coverage is unidiomatic. Within that scope it's `disallow_untyped_defs` + a couple of related checks, deliberately short of blanket `strict = True`; that's a considered middle ground, not an oversight. `[tool.mypy]` in `pyproject.toml` enables `plugins = ["pydantic.mypy"]`, without which mypy can't see that `BaseSettings` subclasses (`src/config.py`) synthesize required-but-env-sourced fields and flags `Settings()` as missing every argument.

GitHub Actions (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, `mypy`, and `pytest` on every push/PR to `main`. No secrets required — that's a direct consequence of `src/config.py` reading env lazily and the test suite needing zero Azure credentials.

Retry: neither `src/embeddings.py` nor `src/cosmos_client.py` hand-rolls backoff — both SDKs already retry transient errors internally. `AzureOpenAI` gets `max_retries=settings.azure_ai_max_retries` (default 5, up from the SDK's own default of 2); Cosmos retries throttled (429) requests automatically without any code here configuring it. Logging: `src/embeddings.py` and `main.py` use `logging.getLogger(__name__)` and never call `basicConfig` themselves — only the `if __name__ == "__main__":` block in `main.py` does, and deliberately sets **root** to `WARNING` while raising just `"src"` and `"__main__"` to `INFO`. Root at `INFO` was tried first and immediately proved why this split matters: `azure.cosmos` logs full HTTP request/response traces (headers included) at `INFO`, and inherits whatever level root is set to. `scripts/verify_*.py` still use plain `print` — they're human-facing diagnostic tools run directly by a person, not library code.

## Environment

All Azure config comes from a gitignored `.env` at the repo root; copy `.env.example` and fill in real values. `src/config.py` is the **single** place that reads the environment — `Settings(BaseSettings)` validates every required field at once (one clear error listing everything missing, not a `ValueError` per call site), and `get_settings()` is an `lru_cache`-wrapped factory around it. Nothing else in the codebase calls `os.getenv()` or `load_dotenv()` directly.

- `COSMOS_URI` — required; `Settings` raises without it
- `COSMOS_KEY` — **optional**. Set it for primary-key auth. Leave it unset to authenticate via `DefaultAzureCredential` instead (Managed Identity / RBAC) — see below.
- `COSMOS_DATABASE_NAME` (default `studieassistent`), `COSMOS_CONTAINER_NAME` (default `chunk`)
- `AZURE_AI_ENDPOINT`, `AZURE_AI_KEY`, `AZURE_AI_DEPLOYMENT_NAME` — the embedding deployment
- `AZURE_AI_API_VERSION` (default `2024-10-21`) — not in `.env.example`, override only if you need to pin a different API version

**Cosmos auth: key or RBAC, decided by whether `COSMOS_KEY` is set.** `src/cosmos_client.py`'s `_build_credential(cosmos_key)` returns the key string unchanged if present, else a `DefaultAzureCredential()` — a credential chain that tries `az` CLI login locally and Managed Identity once deployed (roadmap step 7), with no secret stored either way. A stored primary key grants full read/write/delete over the whole account forever until manually rotated; RBAC scopes access to a specific data-plane role instead. Key auth is kept as a fallback rather than removed — this is a migration, not a breaking change, so existing setups (and CI, if it ever needs live Cosmos access) don't need RBAC configured before anything works. `scripts/verify_cosmos_connection.py` calls `get_container()` (like `verify_vector_search.py` already did) instead of hand-building a `CosmosClient`, so it always exercises whichever auth mode `.env` currently selects.

Cosmos DB's data-plane RBAC is **not** the Azure Portal's regular IAM/Contributor role — it needs a Cosmos-specific SQL role assignment, run once per account against your own subscription:

```powershell
az cosmosdb sql role assignment create `
  --account-name <your-cosmos-account> `
  --resource-group <your-resource-group> `
  --scope "/" `
  --principal-id <your-az-login-or-managed-identity-object-id> `
  --role-definition-id 00000000-0000-0000-0000-000000000002
```

(`00000000-0000-0000-0000-000000000002` is the built-in "Cosmos DB Built-in Data Contributor" role.) This is a manual step against your own account — nothing in this codebase runs it for you.

Gotcha: `get_settings()` is deliberately **not** a module-level `Settings()` instance — that would just relocate the old import-time-requires-Azure-credentials problem from `embeddings.py` to `config.py`. Nothing reads the environment until something calls `get_settings()`, so `cleaning`/`chunking`/`extraction` (and the test suite) stay import-safe with zero Azure credentials. `src/cosmos_client.py` and `src/embeddings.py` follow the same pattern for their Azure clients: a private `lru_cache`-wrapped `_get_client()`, built lazily on first real use and reused after — this also means `get_container()` no longer opens a new `CosmosClient` connection pool on every call. The Cosmos container must be created ahead of time with a `vectorEmbeddingPolicy` and matching `vectorIndexes` on `/embedding`; nothing in the code provisions it. `scripts/verify_cosmos_connection.py` is the tool for confirming that setup.

## Pipeline architecture

`main.py` wires the `src/` modules in sequence; each has a single responsibility and passes plain dataclasses forward:

1. **`extraction.py`** — `load_pdf_document()` opens the PDF with pdfplumber and emits one `SourceDocument` **per page**, each carrying a `document_hash` (first 12 hex chars of the file's SHA-256). Page text passes through `cleaning.clean_page_text()`.
2. **`cleaning.py`** — an ordered pipeline of named, individually-tested steps (`CLEANING_STEPS`): strip zero-width characters, rejoin words hyphenated across a line break, then collapse all whitespace. Order is load-bearing — de-hyphenation needs the newlines that the collapse step removes. This is the **only** place text is normalized, so what Cosmos stores is exactly what was embedded.
3. **`chunking.py`** — `chunk_document()` is the entry point and takes the **whole document** as `(page_number, text)` pairs. It concatenates the pages first, then splits, so a sentence spanning a page break stays whole and the document has exactly **one** tail instead of one per page. `_split_sentence_spans()` splits on `(?<=[.!?])\s+(?=[A-Z])`, keeping terminal punctuation (the delimiter is inside a lookbehind, so only whitespace is consumed), rejoins fragments cut after an abbreviation or an initial, and tracks each sentence's character offset — that offset is how a chunk resolves back to a page. Chunks close *before* adding a sentence that would exceed `max_word`, carry `overlap_sentences` forward, and apply `min_word` **only to the tail** (an undersized final chunk merges back into its predecessor, minus the already-stored overlap, rather than being emitted as a fragment). Each `Chunk` records `page_number` (page it starts on) and `page_end` (page it ends on); `id` is a counter **global to the document**. `chunk_text()` remains as a single-page wrapper — convenience and tests only, not the ingestion path.
4. **`embeddings.py`** — `embed_and_store()` embeds chunks in batches (`get_embeddings()`, `DEFAULT_BATCH_SIZE = 100` chunks/call, not one API call per chunk) then upserts each individually, building the Cosmos document id as `{document_hash}_{page_number}_{chunk.id}`. That composition is what makes ids globally unique despite the per-page counter, and it makes writes idempotent: re-running `main.py` on the same PDF upserts over the same documents instead of duplicating them. Returns the list of failed chunk ids (empty = clean run) instead of `None`, so `main()` can `sys.exit(1)` on partial failure. Its `except` is narrowed to `(openai.OpenAIError, azure.core.exceptions.AzureError)` — real, verified exception roots for both SDKs — so a bug in this codebase (e.g. a bad attribute access) crashes loudly instead of being logged as just another failed chunk. `get_embedding()` (singular, used by `retrieval.py` for one-off queries) deliberately does **not** normalize its input — `cleaning.py` owns that, and normalizing twice would embed a different string than the one stored.
5. **`cosmos_client.py`** — `ContainerProxy` factory, authenticated by key or `DefaultAzureCredential` depending on whether `COSMOS_KEY` is set (see Environment above), injected into `embed_and_store()` so storage stays decoupled from embedding.
6. **`retrieval.py`** — `vector_search()`, the query-side counterpart to `embeddings.py`. Not exercised by `main.py` (that's ingestion-only); called from `scripts/verify_vector_search.py` today and is what roadmap step 3 (LLM calls) will import for RAG context retrieval.
7. **`evaluation.py`** — pure scoring functions (`is_relevant`, `reciprocal_rank`, `hit_at_k`, `evaluate`) for measuring `vector_search()` quality against a hand-written ground-truth set, no Azure calls itself. `scripts/evaluate_retrieval.py` is the live-hitting counterpart, same split as `retrieval.py`/`verify_vector_search.py`.

Retrieval embeds the query with the *same* deployment and orders by `VectorDistance(c.embedding, @query_embedding)` — query and stored embeddings must always come from one model, so changing `AZURE_AI_DEPLOYMENT_NAME` invalidates everything already in the container.

## Retrieval evaluation

`data/eval_questions.json` is `{"source_pdf": ..., "questions": [{"question", "expected_pages"}, ...]}` — ground truth is a **page range in one named source document**, not a chunk id, because chunk boundaries shift whenever `min_word`/`max_word`/`overlap_sentences` change (already happened once: 300/500 → 200/350) and a chunk-id-pinned eval set would need rewriting every time. `is_relevant()` (`src/evaluation.py`) checks `source_name` first and page-range overlap second — `vector_search()` queries the whole Cosmos container with no document filter, so once more than one PDF is ever ingested, a page-only check could wrongly count a same-numbered page from the *wrong* document as a hit. `scripts/evaluate_retrieval.py` takes `--questions` (default `data/eval_questions.json`, targeting the bundled `data/cs-concepts.pdf`) precisely so the eval format doesn't bake in "the PDF in `data/`" as a permanent assumption — a different ingested document gets its own eval file naming its own `source_pdf`. `recall@k`/`MRR` are defined for single-answer retrieval (hit-rate and mean reciprocal rank), documented in `src/evaluation.py`'s module docstring since "recall@k" normally implies a multi-relevant-document set this project doesn't have. Current measured numbers (26 questions, `cs-concepts.pdf`, current chunking settings) live in the README's "Retrieval evaluation" section, not duplicated here — that's the number that goes stale first when chunking gets retuned.

## Conventions and known rough edges

- `main.py` passes `min_word=200, max_word=350, overlap_sentences=2`. On `data/cs-concepts.pdf` (28 pages) that yields 43 chunks, mean 333 words, with 1 chunk over budget. `notes.md` predates document-level chunking and describes the old per-page behavior it was written to work around.
- Chunks can still exceed `max_word` in two documented cases: a single sentence longer than the budget, and the one undersized tail being merged back. Both are tested (`test_tail_merge_may_exceed_max_word`) — treat them as intended, not as bugs to fix.
- Sentence splitting is a hand-rolled regex plus an abbreviation list, not a real segmenter. It is a deliberate trade-off against a spaCy/`pysbd` dependency; extend `ABBREVIATIONS` in `chunking.py` when a new false split shows up, and add a case to `tests/test_chunking.py` alongside it.
- Comments and console output mix Norwegian and English; match the surrounding file rather than normalizing.
- `container/config.py` is an empty placeholder for Cosmos container provisioning config.
- This is a learning project — the author is a third-year engineering student who has asked (in `plan.md`) for concepts to be explained alongside code, not just code handed over.
