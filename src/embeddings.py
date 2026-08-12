from openai import AzureOpenAI, OpenAI
import os
from dotenv import load_dotenv
from src.chunking import Chunk
from azure.cosmos import ContainerProxy

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
    for chunk in chunks:
        unique_id = f"{chunk.source_name}_{chunk.page_number}_{chunk.id}"
        embedding = get_embedding(chunk.chunk_text, DEPLOYMENT_NAME)
        
    print()

if __name__ == "__main__":
    result = get_embedding(text, DEPLOYMENT_NAME)
    print(f"Embedding dimensions: {len(result)}")