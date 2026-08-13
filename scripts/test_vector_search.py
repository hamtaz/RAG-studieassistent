"""
Testscript for å verifisere at vektorsøk fungerer.
Tar et testspørsmål, genererer embedding, og kjører en vector search-query
mot Cosmos DB for å hente de N mest relevante chunkene.
"""

import os
from dotenv import load_dotenv

from src.embeddings import get_embedding
from src.cosmos_client import get_container

load_dotenv()

DEPLOYMENT_NAME = os.getenv("AZURE_AI_DEPLOYMENT_NAME")


def vector_search(query: str, container, top_k: int = 5):
    # Steg 1: generer embedding for spørsmålet, samme modell som ved lagring
    query_embedding = get_embedding(query, DEPLOYMENT_NAME)

    # Steg 2: bygg og kjør vector search-spørringen
    # VectorDistance(c.embedding, @query_embedding) beregner cosinus-avstand
    # mellom hvert lagret dokuments embedding og spørsmålets embedding.
    # ORDER BY ... sorterer fra mest til minst relevant, TOP N begrenser antallet.
    sql_query = f"""
    SELECT TOP {top_k}
        c.chunk_text,
        c.source_name,
        c.page_number,
        VectorDistance(c.embedding, @query_embedding) AS similarity_score
    FROM c
    ORDER BY VectorDistance(c.embedding, @query_embedding)
    """

    parameters = [{"name": "@query_embedding", "value": query_embedding}]

    results = list(
        container.query_items(
            query=sql_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
    )
    return results


def print_results(results):
    if not results:
        print("No results found.")
        return

    for i, item in enumerate(results):
        print(f"\n--- Found {i + 1} (score: {item['similarity_score']:.4f}) ---")
        print(f"Source: {item['source_name']}, side {item['page_number']}")
        print(f"Text: {item['chunk_text']}...")


if __name__ == "__main__":
    container = get_container()

    test_query = "What is an algorithm?"  # bytt ut med noe relevant for din PDF
    print(f"Searching after: '{test_query}'\n")

    results = vector_search(test_query, container, top_k=5)
    print_results(results)