"""Score vector_search() results against a hand-written ground-truth set.

Ground truth is page-based and scoped to one source document (see
data/eval_questions.json): each question names the pages its answer lives on
in one specific PDF, not a chunk id. Chunk boundaries shift whenever chunking
parameters change (min_word/max_word/overlap_sentences), so pinning to pages
instead means an eval file survives a chunking retune without being rewritten.

recall@k and MRR here are defined for single-answer retrieval, not classic
multi-relevant-document recall (each question has one relevant page region in
one document, not an enumerable set of relevant documents):

- recall@k: the fraction of questions where at least one relevant chunk
  appears in the top-k results (a hit-rate, the standard substitute for
  recall@k when there's a single relevant answer rather than a graded set).
- MRR: the mean, over all questions, of 1/rank of the first relevant chunk
  (0 if no relevant chunk appears in the results returned at all).
"""

from dataclasses import dataclass


@dataclass
class EvalQuestion:
    question: str
    expected_pages: set[int]


@dataclass
class EvalSummary:
    num_questions: int
    recall_at_k: dict[int, float]
    mrr: float


def is_relevant(result: dict, source_pdf: str, expected_pages: set[int]) -> bool:
    """A result counts as relevant only if it's from the right document.

    vector_search() queries the whole Cosmos container with no document
    filter. If it ever holds chunks from more than one ingested PDF, a
    page-only check could count a same-numbered page from the *wrong*
    document as a hit - checking source_name first closes that before it's
    reachable, not after.
    """
    if result.get("source_name") != source_pdf:
        return False

    page_number = result.get("page_number")
    if page_number is None:
        return False
    page_number = int(page_number)

    page_end_raw = result.get("page_end")
    page_end = int(page_end_raw) if page_end_raw is not None else page_number

    return any(page_number <= page <= page_end for page in expected_pages)


def reciprocal_rank(results: list[dict], source_pdf: str, expected_pages: set[int]) -> float:
    """1/rank of the first relevant result (1-indexed), or 0.0 if none is."""
    for rank, result in enumerate(results, start=1):
        if is_relevant(result, source_pdf, expected_pages):
            return 1.0 / rank
    return 0.0


def hit_at_k(results: list[dict], source_pdf: str, expected_pages: set[int], k: int) -> bool:
    """True if at least one relevant result appears within the top k."""
    return any(is_relevant(result, source_pdf, expected_pages) for result in results[:k])


def evaluate(
    source_pdf: str,
    per_question: list[tuple[EvalQuestion, list[dict]]],
    k_values: list[int],
) -> EvalSummary:
    """Aggregate recall@k (for each k in k_values) and MRR over all questions."""
    num_questions = len(per_question)
    if num_questions == 0:
        return EvalSummary(num_questions=0, recall_at_k=dict.fromkeys(k_values, 0.0), mrr=0.0)

    recall_at_k = {
        k: sum(hit_at_k(results, source_pdf, q.expected_pages, k) for q, results in per_question)
        / num_questions
        for k in k_values
    }
    mrr = sum(reciprocal_rank(results, source_pdf, q.expected_pages) for q, results in per_question) / (
        num_questions
    )

    return EvalSummary(num_questions=num_questions, recall_at_k=recall_at_k, mrr=mrr)
