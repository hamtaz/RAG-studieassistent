"""
Testscript for å verifisere tilkobling til Azure Cosmos DB.
Kun for testing/debugging - ikke del av hovedpipelinen.
"""

import os
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv

# Laster inn miljøvariabler fra .env-filen
load_dotenv()

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "studieassistent")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME", "chunk" \
"")


def test_connection():
    if not COSMOS_URI or not COSMOS_KEY:
        print("FEIL: COSMOS_URI eller COSMOS_KEY er ikke satt i .env-filen.")
        return

    try:
        # Oppretter klient med key-basert autentisering
        client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
        print("Klient opprettet, kobler til database...")

        # Henter database
        database = client.get_database_client(DATABASE_NAME)
        print(f"Fant database: {database.id}")

        # Henter container
        container = database.get_container_client(CONTAINER_NAME)
        container_props = container.read()
        print(f"Fant container: {container_props['id']}")

        # Sjekker om vector policy er satt opp riktig
        vector_policy = container_props.get("vectorEmbeddingPolicy")
        if vector_policy:
            print("\nVector embedding policy funnet:")
            for embedding in vector_policy.get("vectorEmbeddings", []):
                print(f"  - path: {embedding.get('path')}")
                print(f"    dimensions: {embedding.get('dimensions')}")
                print(f"    distanceFunction: {embedding.get('distanceFunction')}")
        else:
            print("\nADVARSEL: Fant ingen vectorEmbeddingPolicy på containeren.")

        # Sjekker om vector index er satt opp riktig
        indexing_policy = container_props.get("indexingPolicy", {})
        vector_indexes = indexing_policy.get("vectorIndexes")
        if vector_indexes:
            print("\nVector index(er) funnet:")
            for idx in vector_indexes:
                print(f"  - path: {idx.get('path')}, type: {idx.get('type')}")
        else:
            print("\nADVARSEL: Fant ingen vectorIndexes i indexingPolicy.")

        # Teller eksisterende dokumenter (skal være 0 hvis containeren er ny)
        item_count = list(
            container.query_items(
                query="SELECT VALUE COUNT(1) FROM c",
                enable_cross_partition_query=True,
            )
        )[0]
        print(f"\nAntall dokumenter i containeren: {item_count}")

        print("\n✅ Tilkobling OK - alt ser riktig konfigurert ut.")

    except exceptions.CosmosResourceNotFoundError as e:
        print(f"FEIL: Fant ikke ressurs - sjekk at database-/container-navn stemmer. {e}")
    except exceptions.CosmosHttpResponseError as e:
        print(f"FEIL: Cosmos DB returnerte en feil (sjekk URI/key). {e}")
    except Exception as e:
        print(f"UVENTET FEIL: {e}")


if __name__ == "__main__":
    test_connection()