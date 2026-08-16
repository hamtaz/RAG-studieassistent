# Studieassistent — RAG Study Assistant

[![CI](https://github.com/hamtaz/RAG-studieassistent/actions/workflows/ci.yml/badge.svg)](https://github.com/hamtaz/RAG-studieassistent/actions/workflows/ci.yml)

A retrieval-augmented generation pipeline that turns a PDF into a searchable
knowledge base: extract text, chunk it, embed it with Azure OpenAI, and store
it in Azure Cosmos DB for vector search. Built as a learning project to
practice RAG fundamentals end to end, with an emphasis on getting the data
pipeline correct before adding an LLM on top of it.

**Status:** steps 1–6 of the 7-step roadmap in [`plan.md`](plan.md) are done —
extraction/chunking, embeddings/vector storage, grounded LLM answers via
Azure AI Foundry, content moderation + prompt-injection defense, a FastAPI
endpoint, and an MCP server. Step 7 (deployment) is not built yet.

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

Generation (`src/generation.py`, called from `scripts/ask.py`) takes retrieved
chunks, builds a prompt that grounds the answer in them, and calls a separate
chat deployment (`AZURE_AI_CHAT_DEPLOYMENT_NAME`) on the same Azure AI
resource — the same `AzureOpenAI` client (`src/embeddings.py`'s `get_client()`)
is reused for both embedding and chat calls, just with a different `model=`.

Before `generation.py` calls the LLM (and again on its output), `src/safety.py`
moderates the text via Azure AI Content Safety, if configured.

`src/api.py` exposes this over HTTP: a single `POST /ask` endpoint (FastAPI)
that validates the request body, calls `answer_question()`, and returns
`{"answer": ..., "sources": [...]}`. A failed upstream call (`OpenAIError` /
`AzureError`) becomes a `502`; anything unexpected falls through to FastAPI's
default `500` handler rather than a bespoke error path for a one-endpoint app.

`src/mcp_server.py` exposes the same capability as an MCP tool
(`ask_study_assistant`) for MCP clients like Claude Desktop, using the MCP
Python SDK's `FastMCP`. It calls `answer_question()` directly rather than
going through the HTTP API - same logic, no extra network hop.

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

**Cosmos auth defaults to Managed Identity / RBAC, not a stored key.**
`COSMOS_KEY` is optional — set it for primary-key auth, or leave it blank to
authenticate via `DefaultAzureCredential` instead (`az login` locally,
Managed Identity once deployed), with no secret in `.env` at all. A stored
primary key grants full read/write/delete over the whole account forever
until manually rotated; RBAC scopes access to a specific data-plane role and
needs no secret to leak. RBAC needs a one-time role assignment on the Cosmos
account — see `CLAUDE.md`'s Environment section for the exact `az` command.

**The generation prompt only allows answers traceable to the retrieved
context, and requires an explicit "I don't know" otherwise.** An ungrounded
RAG answer is worse than no answer — it looks sourced when it isn't. The
system prompt (`src/generation.py`) requires inline page citations for every
claim, which also makes a wrong or unsupported answer easy to catch by eye.

**Content moderation is a pass-through when unconfigured, prompt-injection
defense is not optional.** `src/safety.py` calls Azure AI Content Safety's
`analyze_text` on the question before generation and on the answer after it,
rejecting either side above a deliberately strict severity threshold — but if
`CONTENT_SAFETY_ENDPOINT`/`CONTENT_SAFETY_KEY` aren't set, it logs a warning
and lets the text through rather than breaking `main.py`/`scripts/ask.py` for
setups that haven't provisioned that resource yet. Prompt injection is
handled differently: Content Safety's Prompt Shields detector isn't exposed
by any published version of `azure-ai-contentsafety` (verified against
1.0.0 and 1.0.0b1 — REST-only today), so instead `generation.py`'s system
prompt explicitly instructs the model to treat any instruction embedded in
the question or in retrieved context as untrusted text, never as a command.
`scripts/check_prompt_injection.py` is a behavioral check against that
defense, not an automated detector.

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
# fill in COSMOS_URI, AZURE_AI_ENDPOINT, AZURE_AI_KEY, AZURE_AI_DEPLOYMENT_NAME,
# AZURE_AI_CHAT_DEPLOYMENT_NAME
# COSMOS_KEY is optional - leave blank to use DefaultAzureCredential (RBAC)
# instead, see CLAUDE.md's Environment section for the required role assignment
# CONTENT_SAFETY_ENDPOINT/CONTENT_SAFETY_KEY are optional - leave blank to
# skip moderation

python -m scripts.verify_cosmos_connection   # confirm Cosmos + vector setup
python main.py                                # ingest data/cs-concepts.pdf
python -m scripts.verify_vector_search        # sanity-check retrieval
python -m scripts.ask "What is an algorithm?" # ask a grounded question end to end
python -m scripts.check_prompt_injection      # eyeball behavior on adversarial questions

uvicorn src.api:app --reload                  # run the API locally at http://127.0.0.1:8000
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"What is an algorithm?\"}"

python -m src.mcp_server                      # run the MCP server (stdio transport)
```

To use the MCP server from Claude Desktop, add it to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "studieassistent": {
      "command": "C:\\path\\to\\repo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:\\path\\to\\repo"
    }
  }
}
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

## Retrieval evaluation

`data/eval_questions.json` is a hand-written ground-truth set — 26 questions
against `data/cs-concepts.pdf`, each naming the page(s) its answer lives on.
`src/evaluation.py` scores `vector_search()` results against it: **recall@k**
(fraction of questions with a relevant chunk in the top k) and **MRR** (mean
reciprocal rank of the first relevant chunk). A result only counts as
relevant if it's from the same source document *and* its page range overlaps
the expected pages — the container can hold chunks from more than one
ingested PDF, so page number alone isn't enough to prove a match.

```powershell
python -m scripts.evaluate_retrieval                          # scores data/eval_questions.json
python -m scripts.evaluate_retrieval --questions other.json   # scores a different document's eval set
```

Measured against the current chunking settings (`min_word=200, max_word=350,
overlap_sentences=2`):

```
recall@1: 0.92
recall@3: 0.96
recall@5: 1.00
MRR: 0.952
(26 questions)
```

This is what makes chunking parameters a measured decision instead of a
guess — retuning `min_word`/`max_word` can now be checked against a number,
not just a chunk count.

## Repository layout

| Path | Purpose |
|---|---|
| `src/` | Pipeline modules: `extraction`, `cleaning`, `chunking`, `embeddings`, `cosmos_client`, `retrieval`, `generation`, `safety`, `evaluation`, `api`, `mcp_server` |
| `scripts/` | Manual scripts that hit live Azure (`verify_*`, `evaluate_retrieval`, `ask`, `check_prompt_injection`) — not pytest tests |
| `tests/` | Unit tests for the pure pipeline stages |
| `data/` | Source PDF(s) for ingestion, plus `eval_questions.json` ground truth |
| `main.py` | Ingestion entry point: PDF → chunks → embed → upsert |
| `plan.md`, `notes.md` | Working notes (Norwegian) from building this project step by step |
| `CODE_REVIEW.md` | A self-review of the codebase against professional engineering practice |

## Known limitations

A fuller list with file/line references lives in [`CODE_REVIEW.md`](CODE_REVIEW.md).
The headline items not yet addressed:

- `main.py` is hardwired to `data/cs-concepts.pdf` — no CLI to point it at a
  different file.
- Azure OpenAI still authenticates with a stored key (`AZURE_AI_KEY`) — Cosmos
  moved to optional Managed Identity / RBAC, the OpenAI key hasn't; Key Vault
  is the documented path for it at deploy time (roadmap step 7).
- Cleaning doesn't remove repeating headers/footers or page numbers.
- No hybrid (keyword + vector) search or re-ranking.
- No automated grounding/quality eval for generated answers yet (retrieval has
  one — see above; generation doesn't).
- Prompt Shields (Azure AI Content Safety's jailbreak/injection detector) isn't
  used — not available in the Python SDK yet (see `src/safety.py`). Injection
  defense today is prompt-level plus a manual behavioral check.

## Roadmap

See [`plan.md`](plan.md) for the full 7-step plan (Norwegian). Remaining
step: deployment to Azure App Service.
