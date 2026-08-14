"""
Testscript for å verifisere at vektorsøk fungerer.
Tar et testspørsmål, genererer embedding, og kjører en vector search-query
mot Cosmos DB for å hente de N mest relevante chunkene.
"""

from src.cosmos_client import get_container
from src.retrieval import vector_search


def print_results(results):
    if not results:
        print("No results found.")
        return

    for i, item in enumerate(results):
        # Chunks er delt opp over hele dokumentet, så én chunk kan spenne
        # over flere sider. Viser sideintervall når start og slutt er ulike.
        start = item.get("page_number")
        end = item.get("page_end")
        pages = f"side {start}" if end in (None, start) else f"side {start}-{end}"

        print(f"\n--- Found {i + 1} (score: {item['similarity_score']:.4f}) ---")
        print(f"Source: {item['source_name']}, {pages}")
        print(f"Text: {item['chunk_text']}...")


if __name__ == "__main__":
    container = get_container()

    test_query = "What is an algorithm?"  # bytt ut med noe relevant for din PDF
    print(f"Searching after: '{test_query}'\n")

    results = vector_search(test_query, container, top_k=5)
    print_results(results)
