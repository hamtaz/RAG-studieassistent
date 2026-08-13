from openai import AzureOpenAI, OpenAI
import os
from dotenv import load_dotenv
from src.chunking import Chunk
from azure.cosmos import ContainerProxy
from dataclasses import asdict

load_dotenv()

AZURE_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
API_KEY = os.getenv("AZURE_AI_KEY")
DEPLOYMENT_NAME = os.getenv("AZURE_AI_DEPLOYMENT_NAME")
API_VERSION = "2024-10-21"

text = "The quick brown fox jumped over the lazy dog."

client = AzureOpenAI(
    api_version = API_VERSION,
    azure_endpoint = AZURE_ENDPOINT,
    api_key = API_KEY
)

def get_embedding(text: str, model: str):
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

def embed_and_store(chunks: list[Chunk], container: ContainerProxy):
    failed_chunks = []

    for i, chunk in enumerate(chunks):
        unique_id = f"{chunk.document_hash}_{chunk.page_number}_{chunk.id}"

        try:
            embedding = get_embedding(chunk.chunk_text, DEPLOYMENT_NAME)

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
    result = get_embedding(text, DEPLOYMENT_NAME)
    print(f"Embedding dimensions: {len(result)}")