# Studieassistent — RAG Study Assistant

A retrieval-augmented generation pipeline that turns a PDF into a searchable
knowledge base: extract text, chunk it, embed it with Azure OpenAI, and store
it in Azure Cosmos DB for vector search. Built as a learning project to
practice RAG fundamentals end to end, with an emphasis on getting the data
pipeline correct before adding an LLM on top of it.

**Status:** steps 1–2 of the 7-step roadmap in [`plan.md`](plan.md) are done —
extraction/chunking and embeddings/vector storage. Steps 3–7 (LLM calls via
Azure AI Foundry, content-safety filtering, a FastAPI wrapper, an MCP server,
and deployment) are not built yet.

## Architecture

```
data/*.pdf
    │
    ▼
┌─────────────────┐   pdfplumber, one page of text per page
│  extraction.py   │   + a SHA-256 hash of the source file
└────────┬─────────┘
         │ SourceDocument (per page)
         ▼
┌─────────────────┐   strip zero-width chars, rejoin words split
│   cleaning.py    │   across a line break, collapse whitespace
└────────┬─────────┘
         │ cleaned page text
         ▼
┌─────────────────┐   pages joined into one document, split into
│   chunking.py    │   sentences, grouped into ~200–350 word chunks
└────────┬─────────┘   with 2-sentence overlap between chunks
         │ Chunk[] (with page_number / page_end)
         ▼
┌─────────────────┐   Azure OpenAI embedding call per chunk,
│  embeddings.py   │   id = {document_hash}_{page}_{chunk.id}
└────────┬─────────┘
         │ Chunk + embedding vector
         ▼
┌─────────────────┐   upsert into Cosmos DB (NoSQL API),
│ cosmos_client.py │   vector-indexed on /embedding
└──────────────────┘
```

Retrieval (`src/retrieval.py`, called from `scripts/verify_vector_search.py`)
runs the query through the same embedding deployment and orders stored chunks
by `VectorDistance` in Cosmos — query and stored vectors have to come from the
same model, so retrieval correctness is tied to `AZURE_AI_DEPLOYMENT_NAME`
never silently changing.

## Design choices

**Cosmos DB (NoSQL API) for vector search, not a dedicated vector database.**
The project already needed a document store for chunk metadata (source, page,
word count); Cosmos's native vector indexing means chunks and their
embeddings live in one place with one query surface, at the cost of the
tuning knobs a dedicated vector DB (e.g. Pinecone, Qdrant) would offer.

**Chunking runs over the whole document, not page by page.** Pages are
concatenated before sentence-splitting, so a sentence that a PDF happens to
break across a page boundary is healed rather than cut in two. It also means
the document has exactly one "tail" chunk (the leftover text once nothing more
fits the word budget) instead of one per page — see the next point.

**`min_word` merges undersized tails instead of dropping or padding them.**
A chunk under the word budget after everything else is packed gets folded into
its predecessor rather than stored as a stray fragment. A short chunk embeds
poorly and tends to rank above genuinely relevant content in vector search, so
merging is preferred over emitting noise — even though it means a small
minority of chunks end up over `max_word`. That trade-off is intentional and
covered by a test (`test_tail_merge_may_exceed_max_word`).

**Sentence splitting is a regex plus an abbreviation list, not a full NLP
segmenter.** It keeps the dependency footprint small and is accurate enough
for the reference material used here, at the cost of missing abbreviations
not yet in the list. `ABBREVIATIONS` in `src/chunking.py` is the place to
extend it; a real segmenter (spaCy, `pysbd`) is the documented upgrade path
if source material gets more varied.

**The Cosmos document id is `{document_hash}_{page_number}_{chunk.id}`.**
Composing it from a content hash rather than a random UUID makes ingestion
idempotent — re-running `main.py` on an unchanged PDF upserts over the same
documents instead of duplicating them, and a changed PDF gets a new hash and
therefore new ids.

**All environment config is read in exactly one place.** `src/config.py`
validates every required variable at startup with `pydantic-settings` — one
clear error listing everything missing, instead of a `ValueError` the first
time each variable happens to get used. Reading is lazy (`get_settings()` is
cached, not a module-level instance), so importing the pipeline modules still
requires no Azure credentials at all; only calling into them does. The Azure
clients (`CosmosClient`, `AzureOpenAI`) follow the same lazy-and-cached
pattern, so each is built once and reused rather than reconnected per call.

## Getting started

Requires Python 3.13, an Azure Cosmos DB account (NoSQL API) with a container
that already has a `vectorEmbeddingPolicy` and matching `vectorIndexes` on
`/embedding` (nothing here provisions that container — it's a manual Azure
Portal step), and an Azure OpenAI embedding deployment.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

copy .env.example .env
# fill in COSMOS_URI, COSMOS_KEY, AZURE_AI_ENDPOINT, AZURE_AI_KEY,
# AZURE_AI_DEPLOYMENT_NAME

python -m scripts.verify_cosmos_connection   # confirm Cosmos + vector setup
python main.py                                # ingest data/cs-concepts.pdf
python -m scripts.verify_vector_search        # sanity-check retrieval
```

Run the test suite (offline, no Azure credentials needed — it only covers
`extraction`, `cleaning`, and `chunking`, the pure parts of the pipeline):

```powershell
pytest
```

### Example run

Ingesting the bundled 28-page reference PDF at the current `min_word=200,
max_word=350` settings:

```
Document count (pages): 28
Chunks count: 43
```

43 chunks from 28 pages, mean chunk size ~333 words, only 1 chunk outside the
word budget (the documented tail-merge trade-off above). Chunking the same
pages independently instead of over the whole document, at the same
`min_word`/`max_word`, produces 37 chunks with 19 outside the budget — one
undersized tail per page instead of one for the whole document.

## Repository layout

| Path | Purpose |
|---|---|
| `src/` | Pipeline modules: `extraction`, `cleaning`, `chunking`, `embeddings`, `cosmos_client` |
| `scripts/` | Manual scripts that hit live Azure (`verify_*`) — not pytest tests |
| `tests/` | Unit tests for the pure pipeline stages |
| `data/` | Source PDF(s) for ingestion |
| `main.py` | Ingestion entry point: PDF → chunks → embed → upsert |
| `plan.md`, `notes.md` | Working notes (Norwegian) from building this project step by step |
| `CODE_REVIEW.md` | A self-review of the codebase against professional engineering practice |

## Known limitations

A fuller list with file/line references lives in [`CODE_REVIEW.md`](CODE_REVIEW.md).
The headline items not yet addressed:

- No retry/backoff on embedding calls, so a rate limit silently drops chunks
  instead of retrying.
- One embedding API call per chunk rather than batched requests.
- Authentication uses a Cosmos primary key in `.env`, not Managed Identity /
  RBAC.
- No CI, linter, or type checker yet.
- Cleaning doesn't remove repeating headers/footers or page numbers.

## Roadmap

See [`plan.md`](plan.md) for the full 7-step plan (Norwegian). Remaining steps:
LLM calls via Azure AI Foundry, content-safety filtering, a FastAPI endpoint,
an MCP server wrapping that endpoint, and deployment to Azure App Service.
