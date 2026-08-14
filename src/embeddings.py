from dataclasses import asdict
from functools import lru_cache

from azure.cosmos import ContainerProxy
from openai import AzureOpenAI

from src.chunking import Chunk
from src.config import get_settings


@lru_cache
def _get_client() -> AzureOpenAI:
    """Build (and cache) the AzureOpenAI client once, on first real use.

    Not built at module scope: that would make importing this module fail
    without live Azure credentials, which is what broke unit-testing it
    before.
    """
    settings = get_settings()
    return AzureOpenAI(
        api_version=settings.azure_ai_api_version,
        azure_endpoint=settings.azure_ai_endpoint,
        api_key=settings.azure_ai_key,
    )


def get_embedding(text: str, model: str):
    # No normalization here on purpose. cleaning.clean_page_text() already
    # flattened whitespace before chunking, so normalizing again would embed a
    # different string than the one stored alongside the vector.
    client = _get_client()
    return client.embeddings.create(input=[text], model=model).data[0].embedding


def embed_and_store(chunks: list[Chunk], container: ContainerProxy):
    deployment_name = get_settings().azure_ai_deployment_name
    failed_chunks = []

    for i, chunk in enumerate(chunks):
        unique_id = f"{chunk.document_hash}_{chunk.page_number}_{chunk.id}"

        try:
            embedding = get_embedding(chunk.chunk_text, deployment_name)

            chunk_dict = asdict(chunk)
            chunk_dict["embedding"] = embedding
            chunk_dict["id"] = unique_id

            container.upsert_item(chunk_dict)
            print(f"[{i + 1}/{len(chunks)}] Saved chunk {unique_id}")

        except Exception as e:
            print(f"[{i + 1}/{len(chunks)}] FAIL on chunk {unique_id}: {e}")
            failed_chunks.append(unique_id)
            continue

    if failed_chunks:
        print(f"\n{len(failed_chunks)} av {len(chunks)} chunks failed:")
        for fid in failed_chunks:
            print(f"  - {fid}")
    else:
        print(f"\nAll {len(chunks)} chunks were saved.")


if __name__ == "__main__":
    result = get_embedding(
        "The quick brown fox jumped over the lazy dog.",
        get_settings().azure_ai_deployment_name,
    )
    print(f"Embedding dimensions: {len(result)}")
