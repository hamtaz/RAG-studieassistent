"""
Manual script: ask the study assistant a question end to end (retrieve +
generate). Hits live Azure OpenAI + Cosmos, like the other verify_* /
evaluate_* scripts.

Usage:
    python -m scripts.ask "What is an algorithm?"
"""

import argparse

from src.cosmos_client import get_container
from src.generation import answer_question


def run(question: str) -> None:
    container = get_container()
    result = answer_question(question, container)

    print(f"Question: {question}\n")
    print(f"Answer:\n{result['answer']}\n")

    print("Sources:")
    for chunk in result["sources"]:
        start = chunk.get("page_number")
        end = chunk.get("page_end")
        pages = f"p. {start}" if end in (None, start) else f"p. {start}-{end}"
        print(f"  - {chunk.get('source_name')}, {pages}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Question to ask the study assistant")
    args = parser.parse_args()
    run(args.question)
