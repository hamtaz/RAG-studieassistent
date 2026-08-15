import logging
from dataclasses import asdict
from functools import lru_cache

from azure.core.exceptions import AzureError
from azure.cosmos import ContainerProxy
from openai import AzureOpenAI, OpenAIError

from src.chunking import Chunk
from src.config import get_settings

logger = logging.getLogger(__name__)

# At ~200-350 words (~270-475 tokens) per chunk, this is a conservative
# ceiling well under typical per-request token limits for the embeddings
# endpoint, not a measured maximum.
DEFAULT_BATCH_SIZE = 100


@lru_cache
def get_client() -> AzureOpenAI:
    """Build (and cache) the AzureOpenAI client once, on first real use.

    Not built at module scope: that would make importing this module fail
    without live Azure credentials, which is what broke unit-testing it
    before. Shared with src/generation.py - one AzureOpenAI client, used for
    both embeddings and chat completions (different `model=` deployment per
    call), same as one Azure AI resource with two deployments.
    """
    settings = get_settings()
    return AzureOpenAI(
        api_version=settings.azure_ai_api_version,
        azure_endpoint=settings.azure_ai_endpoint,
        api_key=settings.azure_ai_key,
        max_retries=settings.azure_ai_max_retries,
    )


def get_embedding(text: str, model: str) -> list[float]:
    """Embed a single string - used for one-off queries (src/retrieval.py).

    For ingesting many chunks, prefer get_embeddings() (batched).
    """
    # No normalization here on purpose. cleaning.clean_page_text() already
    # flattened whitespace before chunking, so normalizing again would embed a
    # different string than the one stored alongside the vector.
    client = get_client()
    return client.embeddings.create(input=[text], model=model).data[0].embedding


def get_embeddings(texts: list[str], model: str) -> list[list[float]]:
    """Embed many strings in one API call instead of one call per string."""
    client = get_client()
    response = client.embeddings.create(input=texts, model=model)
    # Sort by the API's own index rather than trusting response order to
    # match input order - cheap insurance against silently pairing the wrong
    # embedding with the wrong chunk.
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


def embed_and_store(
    chunks: list[Chunk], container: ContainerProxy, batch_size: int = DEFAULT_BATCH_SIZE
) -> list[str]:
    """Embed and upsert every chunk. Returns the ids of chunks that failed.

    An empty return means every chunk was saved. Embedding calls are batched;
    Cosmos writes stay one upsert_item() per chunk (batching those needs a
    shared partition key per batch, which the container's partition-key
    strategy doesn't yet settle - see CODE_REVIEW.md).
    """
    deployment_name = get_settings().azure_ai_deployment_name
    failed_chunks: list[str] = []

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]

        try:
            embeddings = get_embeddings([chunk.chunk_text for chunk in batch], deployment_name)
        except (OpenAIError, AzureError) as e:
            logger.warning("Batch embedding call failed for %d chunks: %s", len(batch), e)
            failed_chunks.extend(f"{chunk.document_hash}_{chunk.page_number}_{chunk.id}" for chunk in batch)
            continue

        batch_failed: list[str] = []
        for chunk, embedding in zip(batch, embeddings, strict=True):
            unique_id = f"{chunk.document_hash}_{chunk.page_number}_{chunk.id}"

            try:
                chunk_dict = asdict(chunk)
                chunk_dict["embedding"] = embedding
                chunk_dict["id"] = unique_id

                container.upsert_item(chunk_dict)
                logger.debug("Saved chunk %s", unique_id)

            except (OpenAIError, AzureError) as e:
                logger.warning("Failed to save chunk %s: %s", unique_id, e)
                batch_failed.append(unique_id)

        failed_chunks.extend(batch_failed)
        logger.info(
            "Batch %d-%d: %d/%d chunks saved",
            batch_start + 1,
            batch_start + len(batch),
            len(batch) - len(batch_failed),
            len(batch),
        )

    if failed_chunks:
        logger.warning("%d of %d chunks failed:", len(failed_chunks), len(chunks))
        for fid in failed_chunks:
            logger.warning("  - %s", fid)
    else:
        logger.info("All %d chunks were saved.", len(chunks))

    return failed_chunks


if __name__ == "__main__":
    result = get_embedding(
        "The quick brown fox jumped over the lazy dog.",
        get_settings().azure_ai_deployment_name,
    )
    print(f"Embedding dimensions: {len(result)}")
