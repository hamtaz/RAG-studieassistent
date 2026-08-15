"""
Testscript for å verifisere tilkobling til Azure Cosmos DB.
Kun for testing/debugging - ikke del av hovedpipelinen.
"""

from azure.cosmos import exceptions

from src.config import get_settings
from src.cosmos_client import get_container


def test_connection():
    try:
        settings = get_settings()

        auth_mode = "key-basert" if settings.cosmos_key else "DefaultAzureCredential (RBAC)"
        print(f"Kobler til med autentisering: {auth_mode}")

        container = get_container()
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

        # Ingen emoji her: Windows-konsollen bruker cp1252 og kaster
        # UnicodeEncodeError, som blir fanget nedenfor og feilaktig
        # rapportert som at tilkoblingen feilet.
        print("\nOK: Tilkobling fungerer - alt ser riktig konfigurert ut.")

    except exceptions.CosmosResourceNotFoundError as e:
        print(f"FEIL: Fant ikke ressurs - sjekk at database-/container-navn stemmer. {e}")
    except exceptions.CosmosHttpResponseError as e:
        print(f"FEIL: Cosmos DB returnerte en feil (sjekk URI/key). {e}")
    except Exception as e:
        print(f"UVENTET FEIL: {e}")


if __name__ == "__main__":
    test_connection()
