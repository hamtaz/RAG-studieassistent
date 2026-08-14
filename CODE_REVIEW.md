# Code Review & Improvement Recommendations — RAG Study Assistant

*Review date: 2026-08-13 · Covers roadmap steps 1–2 as implemented*

## Context

Steps 1–2 of the `plan.md` roadmap are implemented: PDF extraction → cleaning → chunking → Azure OpenAI embeddings → Cosmos DB vector storage, plus two manual verification scripts. Steps 3–7 (LLM calls, content safety, FastAPI, MCP, deploy) are not started.

This project is intended as a portfolio piece shown to employers. That changes what "done" means: reviewers judge it on engineering judgment, not feature count. A small project with tests, CI, typed config, and a README that explains *why* reads far stronger than a large one without them. The recommendations below are ordered so that correctness comes first (bugs here silently degrade every answer the finished assistant gives), then the engineering practices that make the work legible to a reviewer.

**No code changes have been made** — this is a review document.

---

## 1. Correctness bugs — fix these first

These are real defects, verified against the code. They degrade retrieval quality invisibly, which is the worst failure mode in RAG: nothing crashes, answers just get quietly worse.

### 1.1 The sentence splitter destroys terminal punctuation — `src/chunking.py:17`

`re.split(r'[\?!.] (?=[A-Z])', text)` puts the delimiter *outside* the lookahead, so the `.`/`!`/`?` and the following space are consumed and discarded. Verified:

```
"The cat sat on the mat. Then it left! Was it happy? Dr. Smith saw it."
→ ['The cat sat on the mat', 'Then it left', 'Was it happy', 'Dr', 'Smith saw it.']
```

Every stored chunk is therefore a run-on with no sentence boundaries. This hurts twice: the embedding model sees degraded text, and any text you later feed an LLM as context is harder to read and cite. Note the same example also splits `Dr. Smith` — abbreviations, decimals, and initials all break it.

**Recommendation:** keep the delimiter (use a capturing split or a lookbehind), and treat naive regex sentence splitting as a known limitation. A proper sentence segmenter (spaCy, `pysbd`, or NLTK's Punkt) handles abbreviations and is a one-line swap. If you keep the regex for dependency-weight reasons, say so explicitly in a comment — a reviewer respects a documented trade-off far more than an unexamined one.

### 1.2 The `min_word` parameter is dead code — `src/chunking.py:28`

```python
if current_word_count + len(...) >= max_word and current_word_count + len(...) >= min_word:
```

Both operands are the identical expression. Since `max_word > min_word` always, the second condition is implied by the first and can never independently fail. `min_word` has no effect on output.

Where `min_word` *should* apply is the final flush (`chunking.py:39–41`), which is unconditional: a page ending in a 6-word fragment emits a 6-word chunk. Short chunks are retrieval noise — they embed poorly and can outrank genuinely relevant content.

**Recommendation:** enforce `min_word` on the tail — merge an undersized final chunk into the previous one, or drop it.

### 1.3 Empty pages produce empty chunks that are then sent to the embedding API

`re.split` on an empty string returns `['']`, and the unconditional final flush turns that into a `Chunk` with `chunk_text=""` and `wordcount=0`. That chunk reaches `embed_and_store` and costs an API call that will either error or store a meaningless vector.

**Recommendation:** guard against empty/whitespace-only text at the chunker's entry and exit. `extraction.py` already filters falsy page text (`if text:`), so the guard belongs in `chunk_text` for symmetry.

### 1.4 Stored text and embedded text diverge — `src/embeddings.py:24`

`get_embedding` does `text.replace("\n", " ")` on its local copy, but `embed_and_store` stores `asdict(chunk)` with the *original* newline-bearing text. The vector and the text it supposedly represents are derived from different strings.

It's minor today, but it's exactly the class of drift that becomes untraceable later.

**Recommendation:** normalize once, in the cleaning stage, so that what you store is what you embedded.

### 1.5 The cleaner barely cleans — `src/cleaning.py:5`

`re.sub("​|\n​", " ", text)` has a redundant second alternative (the first branch already matches the `​` inside `\n​`, leaving the `\n` behind), so **newlines are never actually removed**. It's also a literal replacement dressed up as a regex — `str.replace` would be clearer.

More substantively, PDF text extraction needs: de-hyphenation across line breaks (`algo-\nrithm` → `algorithm`), whitespace collapsing, and removal of repeating headers/footers and page numbers. Right now those artifacts flow into chunks and into embeddings. Your `output.txt` (1382 lines of extracted text) is the evidence to work from.

**Recommendation:** treat cleaning as a real pipeline stage with a handful of named, individually-tested transformations. This is also the easiest place in the whole project to demonstrate test-driven work — pure functions, no I/O.

---

## 2. Reliability and cost — the parts an ops reviewer looks for

### 2.1 No retry or backoff on embedding calls — `src/embeddings.py:33–46`

Azure OpenAI embedding deployments rate-limit aggressively (HTTP 429). The current `except Exception` catches the 429, prints, and moves on — so a rate limit is silently converted into permanently missing data. A long ingestion run can lose a large fraction of its chunks and still report as having finished.

**Recommendation:** add exponential backoff with jitter on transient failures (429, 5xx, timeouts) and let genuinely permanent errors fail loudly. Distinguish transient from permanent rather than catching bare `Exception`.

### 2.2 One API call per chunk

`client.embeddings.create(input=[text])` sends a single string per request. The API accepts batches. For a few hundred chunks this is the difference between one slow, rate-limit-prone run and a fast one.

**Recommendation:** batch inputs (respecting the model's per-request token cap), and consider `upsert_item` batching on the Cosmos side too.

### 2.3 The pipeline reports success even when it fails

`embed_and_store` collects `failed_chunks`, prints them, and returns `None`. `main()` has no idea anything went wrong and exits 0. In any automated context — CI, a scheduled ingestion job, a container — that's an invisible failure.

**Recommendation:** return a result object (counts of succeeded/failed) and have `main` exit non-zero when failures occurred. Add a mechanism to re-drive only the failed chunks.

### 2.4 Re-ingestion re-embeds everything

The `{document_hash}_{page}_{id}` key (`embeddings.py:31`) makes writes idempotent — a re-run upserts rather than duplicates. Good design, and worth calling out in your README. But you still pay for every embedding again.

**Recommendation:** query Cosmos for the document hash before ingesting and skip unchanged documents. You already compute the hash in `extraction.py:10` — the mechanism exists, it's just not used as a guard.

### 2.5 `print` everywhere instead of logging

Every module prints. There's no way to control verbosity, no timestamps, no levels, and nothing that will work when this becomes a FastAPI service (step 5).

**Recommendation:** standard `logging` with a configured root logger. Structured (JSON) logs if you want to demo Azure Application Insights integration later — that would tie in well with step 7.

### 2.6 A new `CosmosClient` per `get_container()` call — `src/cosmos_client.py:17`

`CosmosClient` holds a connection pool and is designed to be long-lived and shared. Constructing one per call is a documented anti-pattern that will bite under FastAPI request load.

**Recommendation:** create it once and reuse (module-level singleton now; FastAPI lifespan-managed dependency at step 5).

---

## 3. Architecture and structure

### 3.1 Retrieval logic lives in a throwaway script

`vector_search()` in `scripts/test_vector_search.py:18` is **core domain logic** — it's the "R" in RAG — sitting in a file labelled as a test script. Step 3 (LLM calls) and step 5 (FastAPI) both need it and will end up importing from `scripts/` or copy-pasting it.

**Recommendation:** promote it to `src/retrieval.py` now. The script then becomes a thin caller, which is what it should have been.

### 3.2 Configuration is scattered across four modules

`load_dotenv()` is called in `cosmos_client.py`, `embeddings.py`, and both scripts; `os.getenv` calls are spread across them with defaults duplicated (`"studieassistent"`, `"chunk"` appear twice). `API_VERSION` is hardcoded at `embeddings.py:13`. Chunking parameters are hardcoded in `main.py:23–25`.

**Recommendation:** one settings module using `pydantic-settings` — typed, validated at startup, single source of defaults, fails fast with a clear message when a variable is missing. This is a small change that reads as noticeably more professional, and it directly fixes 3.3.

### 3.3 Import-time side effects — `src/embeddings.py:15–21`

The `AzureOpenAI` client is constructed at module scope, and there's a stray module-level `text = "The quick brown fox..."` global. Consequence: **importing** `src.embeddings` fails without Azure credentials — so you cannot unit-test the chunking pipeline, or even import the module, without live secrets. `OpenAI` is imported and never used.

**Recommendation:** build the client lazily inside a function or inject it as a parameter (the same dependency-injection pattern you already use correctly for `ContainerProxy` in `embed_and_store` — apply it consistently).

### 3.4 The chunk ID is assembled in the wrong layer

`Chunk.id` (`chunking.py:8`) is a per-page counter; the globally-unique key is composed in `embeddings.py:31`. So `Chunk.id` means one thing in memory and another in the database, and a storage concern lives in the embedding module.

**Recommendation:** have the chunker emit the stable, fully-qualified ID. Also consider adding character offsets to `Chunk` — you'll want them for precise source citations at step 3.

### 3.5 Ingestion is hardwired to one file — `main.py:10`

A hardcoded path to `data/cs-concepts.pdf`, and `print(all_chunks[0])` at line 34 will raise `IndexError` on an empty document.

**Recommendation:** a small CLI (`argparse` or `typer`) accepting a file or directory. Also decide and document the Cosmos **partition key** strategy — with one document it doesn't matter; with a corpus it determines whether queries stay single-partition.

### 3.6 `container/config.py` is an empty tracked file

**Recommendation:** either implement it as an idempotent bootstrap that provisions the database/container with the `vectorEmbeddingPolicy` and `vectorIndexes` (currently a manual portal step, invisible to anyone cloning the repo), or delete it. Infrastructure-as-code here — even a single script, or Bicep for step 7 — is a strong signal.

---

## 4. Security and secrets

Step 4 of your roadmap is security, and you've said it's something you want to show off. Two structural items are worth deciding *now*, because retrofitting them later is more work:

- **Move off primary keys.** `cosmos_client.py` uses `COSMOS_KEY`, which is a full-access credential in a `.env` file. Azure Managed Identity via `DefaultAzureCredential` plus Cosmos **RBAC data-plane roles** gives least privilege and no stored secret. `DefaultAzureCredential` falls back to your local Azure CLI login in development, so it works in both places. This is the single most credible security improvement available in the current codebase.
- **Azure Key Vault** for any secret that genuinely must exist (the Azure AI key), referenced from App Service configuration at step 7.

Also: `enable_cross_partition_query=True` (`test_vector_search.py:42`, `test_cosmos_connection.py:64`) is a legacy no-op in `azure-cosmos` 4.x — accepted and ignored. Minor, but removing dead parameters is the kind of detail reviewers notice.

On the SQL in `test_vector_search.py:26`: `TOP {top_k}` is f-string interpolated while the vector is properly parameterized. It's not exploitable as written (`top_k` is an internal int), and Cosmos doesn't support parameterizing `TOP` — so the right fix is to validate it as a bounded integer and add a one-line comment saying why it can't be a parameter. Demonstrating that you noticed is worth more than the fix itself.

---

## 5. Testing and quality gates — the biggest portfolio gap

There is currently **no test framework** (pytest isn't even in `requirements.txt`), no linter, no formatter, no type checking, and no CI. For a project meant to demonstrate professional practice, this is the most valuable area to invest in — and it's cheap, because your best-testable code is already pure.

- **`scripts/test_*.py` are not tests.** They're named as though pytest should collect them, and if you add pytest it *will* try to — then hit the network and fail. Rename to `verify_*.py` / `check_*.py`, or move them under a `scripts/manual/` directory.
- **Unit-test the pure functions.** `split_sentence`, `chunk_text`, `clean_page_text`, and `get_file_hash` need no network, no Azure, no mocks. Table-driven tests here would catch every bug in section 1 and directly demonstrate that your chunking behaves as documented — overlap is preserved, size bounds are respected, empty input is handled.
- **A small fixture PDF** in `tests/fixtures/` makes extraction testable too.
- **Ruff** (lint + format, one tool) and **mypy** — your type hints are partial and in one place wrong: `pdf_to_txt(file_path: str)` at `extraction.py:24` is annotated `str` but receives a `Path` and calls `.name` on it. `load_pdf_document` has the same mismatch. mypy catches exactly this.
- **GitHub Actions** running lint + type check + tests on push. A green CI badge on the README is the single highest signal-to-effort item in this entire review.
- **pre-commit** hooks so the above run locally before they run in CI.

---

## 6. Repository hygiene and presentation

This section matters disproportionately, because it's what a reviewer sees in the first sixty seconds.

### 6.1 `requirements.txt` is a `pip freeze` dump — and isn't committed

It's untracked, so **a fresh clone cannot install the project at all**. When you do commit it, note what's in it:

- Unused heavyweight dependencies: `pandas`, `numpy`, `datasets`, `huggingface_hub`, `pyarrow`, `aiohttp` — none are imported anywhere in the codebase (verified against all imports).
- `er==0.2` — an accidental install; not a real dependency of anything here.
- `dotenv==0.9.9` — a deprecated stub package. The real one, `python-dotenv`, is *also* listed. Having both is a red flag to anyone who knows the ecosystem.

**Recommendation:** declare **direct** dependencies only, in a `pyproject.toml`, with a lock file for reproducibility (`uv` is fast and increasingly the default; Poetry is fine too). Separate dev dependencies (pytest, ruff, mypy) from runtime ones. Getting this right signals supply-chain awareness.

### 6.2 No README — the most important missing file

For a portfolio project, the README *is* the deliverable. `plan.md` and `notes.md` currently occupy that space, but they're personal scratch written in Norwegian, and `plan.md` reads as a series of prompts to an AI assistant — which is not what you want a hiring manager to open first.

**Recommendation:** a proper README in English covering: what it does and why; an architecture diagram (the ingestion pipeline is genuinely nice to draw); technology choices **with rationale** (why Cosmos DB vector search over a dedicated vector DB, why per-page chunking, why the composite ID scheme gives idempotency); setup and run instructions; and results/screenshots. Move `plan.md` and `notes.md` into `docs/` or drop them. Consider a lightweight ADR log — a few short "decision, alternatives, rationale" records — which is a strong senior-level signal.

### 6.3 Other hygiene items

- **`output.txt` is committed** — a 1382-line extracted-text artifact. Gitignore it.
- **No `.env.example`.** Nobody can tell which five variables they need without reading source. Add one with placeholder values. (`.env` itself is correctly gitignored — good.)
- **No LICENSE.** For a public showcase repo, add one.
- **Mixed Norwegian and English.** Docstrings and console output in `scripts/`, plus `"{n} av {n} chunks failed"` at `embeddings.py:49`, are Norwegian; the rest is English. For a repo aimed at employers — especially international ones — standardize code, comments, and docs on English.
- **Commit messages.** Terse, and one has a typo (`Seperated logic`). Conventional Commits (`feat:`, `fix:`, `refactor:`) costs nothing and looks deliberate. Also: the shipped chunk sizes (`main.py`: 300/500) contradict `notes.md`, which says you reduced them to 200–350. Reconcile these — a reviewer reading both will notice.
- **Missing docstrings** on most `src/` functions.

---

## 7. RAG-specific quality — what will actually differentiate this project

Every RAG portfolio project does ingest → embed → retrieve → generate. Very few evaluate. This is where you separate yourself:

- **Build a small evaluation set.** 20–30 questions against your source PDF with known-correct source pages, then measure **recall@k** and **MRR**. This turns "I built a RAG pipeline" into "I measured my retrieval at recall@5 = 0.87 and improved it from 0.72 by fixing sentence segmentation." That sentence is worth more in an interview than any feature.
- **It also justifies your tuning.** Right now the 300/500-word choice and the `notes.md` reduction to 200–350 are guesses. With an eval set they become measured decisions — and you can show the chunking bugs in section 1 actually mattered.
- **Hybrid search.** Pure vector search misses exact keyword matches (acronyms, function names, proper nouns). Cosmos DB supports full-text and hybrid search with RRF — combining the two is a well-known quality win and shows you understand vector search's limits.
- **Consider a re-ranker** as a second stage over the top-k.
- **Store richer chunk metadata** — section headings, character offsets — so step 3 can produce precise citations rather than just page numbers.
- **Track cost and token usage** per ingestion run. Cost-awareness is a mature engineering trait and rarely demonstrated in portfolio work.

---

## Suggested sequencing

| Priority | Work | Why now |
|---|---|---|
| **1** | Section 1 bugs (splitter, `min_word`, empty chunks, cleaning) | Everything downstream inherits this data. Fix before generating more embeddings. |
| **2** | pytest + unit tests on the pure functions | Locks in the fixes; the cheapest credibility per hour in the whole list. |
| **3** | `pyproject.toml` with real dependencies; commit it; `.env.example` | The repo currently cannot be installed from a clean clone. |
| **4** | README with architecture and rationale | The thing reviewers actually read. |
| **5** | Settings module; lazy client; promote `vector_search` to `src/retrieval.py` | Structural prerequisites for steps 3 and 5 — cheaper now than later. |
| **6** | Ruff + mypy + GitHub Actions CI | Visible quality signal; badge on the README. |
| **7** | Retry/backoff, batching, logging, exit codes | Production-readiness story. |
| **8** | Evaluation set with recall@k | The genuine differentiator — do this before adding more features. |
| **9** | Managed Identity + RBAC over primary keys | Folds naturally into roadmap step 4. |

Items 1–4 are roughly a weekend and take the project from "student exercise" to "credible engineering work." Item 8 is what makes it memorable.
