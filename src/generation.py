"""Generation: turn retrieved chunks into a grounded answer.

This is the "G" in RAG - retrieval (src/retrieval.py) finds the chunks,
this module builds a prompt around them and calls the chat deployment.
"""

import logging

from azure.core.exceptions import AzureError
from azure.cosmos import ContainerProxy
from openai import OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from src.config import get_settings
from src.embeddings import get_client
from src.retrieval import vector_search

logger = logging.getLogger(__name__)

# Grounding is the whole point: an ungrounded RAG answer is worse than no
# answer, because it looks sourced when it isn't. Two rules matter most -
# answer only from context, and say so when the context doesn't cover it -
# so an interview-worthy failure mode (confident hallucination) doesn't slip
# through a vaguer prompt.
SYSTEM_PROMPT = (
    "You are a study assistant. Answer the user's question using ONLY the "
    "numbered context excerpts below. Every claim in your answer must be "
    "traceable to one of them - cite the source and page(s) inline, e.g. "
    '"(cs-concepts.pdf, p. 4)". If the context does not contain the answer, '
    'say "I don\'t know based on the provided material" instead of guessing.'
)


def build_prompt(question: str, chunks: list[dict]) -> list[ChatCompletionMessageParam]:
    """Build the chat `messages` list: system instructions + numbered context + question.

    Pure function - no Azure calls - so prompt formatting is unit-testable
    without live credentials.
    """
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        start = chunk.get("page_number")
        end = chunk.get("page_end")
        pages = f"p. {start}" if end in (None, start) else f"p. {start}-{end}"
        context_blocks.append(f"[{i}] ({chunk.get('source_name')}, {pages})\n{chunk.get('chunk_text')}")

    user_content = (
        "Context:\n\n" + "\n\n".join(context_blocks) + f"\n\nQuestion: {question}"
        if context_blocks
        else f"Context: (none found)\n\nQuestion: {question}"
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def answer_question(question: str, container: ContainerProxy, top_k: int = 5) -> dict:
    """Retrieve context for `question` and generate a grounded answer.

    Returns {"answer": str, "sources": list[dict]}. Raises on API failure
    rather than swallowing it - unlike embed_and_store's per-chunk batch
    handling, a single failed answer has nothing partial worth returning.
    """
    settings = get_settings()
    chunks = vector_search(question, container, top_k=top_k)
    messages = build_prompt(question, chunks)

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=settings.azure_ai_chat_deployment_name,
            messages=messages,
        )
    except (OpenAIError, AzureError) as e:
        logger.warning("Chat completion failed for question %r: %s", question, e)
        raise

    answer = response.choices[0].message.content or ""
    return {"answer": answer, "sources": chunks}
