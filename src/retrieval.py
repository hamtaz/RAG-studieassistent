"""Retrieval: embed a query and find the most relevant stored chunks.

This is the "R" in RAG, not a verification script - roadmap step 3 (LLM
calls) imports vector_search() from here.
"""

from azure.cosmos import ContainerProxy

from src.config import get_settings
from src.embeddings import get_embedding


def vector_search(query: str, container: ContainerProxy, top_k: int = 5) -> list[dict]:
    # Steg 1: generer embedding for spørsmålet, samme modell som ved lagring
    deployment_name = get_settings().azure_ai_deployment_name
    query_embedding = get_embedding(query, deployment_name)

    # Steg 2: bygg og kjør vector search-spørringen
    # VectorDistance(c.embedding, @query_embedding) beregner cosinus-avstand
    # mellom hvert lagret dokuments embedding og spørsmålets embedding.
    # ORDER BY ... sorterer fra mest til minst relevant, TOP N begrenser antallet.
    #
    sql_query = f"""
    SELECT TOP {top_k}
        c.chunk_text,
        c.source_name,
        c.page_number,
        c.page_end,
        VectorDistance(c.embedding, @query_embedding) AS similarity_score
    FROM c
    ORDER BY VectorDistance(c.embedding, @query_embedding)
    """

    parameters: list[dict[str, object]] = [{"name": "@query_embedding", "value": query_embedding}]

    results = list(
        container.query_items(
            query=sql_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
    )
    return results
