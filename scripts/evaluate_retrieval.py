"""
Manual script: measure retrieval quality (recall@k, MRR) against a
hand-written question set. Hits live Azure OpenAI + Cosmos, like the other
verify_* scripts - not a pytest test, so it's not named verify_* (a
different purpose: measuring quality, not checking connectivity).

Usage:
    python -m scripts.evaluate_retrieval
    python -m scripts.evaluate_retrieval --questions path/to/other.json

--questions defaults to the bundled eval set for data/cs-concepts.pdf. A
different ingested PDF gets its own eval file naming its own "source_pdf" -
nothing here assumes cs-concepts.pdf is the only document ever ingested; see
src/evaluation.py's module docstring for the scoring rules.
"""

import argparse
import json
from pathlib import Path

from src.cosmos_client import get_container
from src.evaluation import EvalQuestion, evaluate, reciprocal_rank
from src.retrieval import vector_search

K_VALUES = [1, 3, 5]
TOP_K = max(K_VALUES)

DEFAULT_QUESTIONS_PATH = Path(__file__).parent.parent / "data" / "eval_questions.json"


def load_questions(path: Path) -> tuple[str, list[EvalQuestion]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_pdf = data["source_pdf"]
    questions = [
        EvalQuestion(question=q["question"], expected_pages=set(q["expected_pages"]))
        for q in data["questions"]
    ]
    return source_pdf, questions


def run(questions_path: Path) -> None:
    source_pdf, questions = load_questions(questions_path)
    if not questions:
        print(f"No questions found in {questions_path}.")
        return

    container = get_container()
    print(f"Evaluating {len(questions)} questions against source_pdf='{source_pdf}' (top_k={TOP_K})\n")

    per_question: list[tuple[EvalQuestion, list[dict]]] = []
    for q in questions:
        results = vector_search(q.question, container, top_k=TOP_K)
        per_question.append((q, results))

        rr = reciprocal_rank(results, source_pdf, q.expected_pages)
        status = f"hit (rank {round(1 / rr)})" if rr > 0 else "miss"
        print(f"[{status:>10}] {q.question}")

    summary = evaluate(source_pdf, per_question, k_values=K_VALUES)

    print("\n--- Summary ---")
    for k in K_VALUES:
        print(f"recall@{k}: {summary.recall_at_k[k]:.2f}")
    print(f"MRR: {summary.mrr:.3f}")
    print(f"({summary.num_questions} questions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS_PATH,
        help="Path to an eval-questions JSON file (default: data/eval_questions.json)",
    )
    args = parser.parse_args()
    run(args.questions)
