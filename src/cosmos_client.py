from functools import lru_cache

from azure.cosmos import CosmosClient, ContainerProxy

from src.config import get_settings


@lru_cache
def _get_client() -> CosmosClient:
    """Build (and cache) the CosmosClient once.

    CosmosClient owns a connection pool and is meant to be long-lived and
    shared, not constructed per call.
    """
    settings = get_settings()
    return CosmosClient(settings.cosmos_uri, credential=settings.cosmos_key)


def get_container() -> ContainerProxy:
    settings = get_settings()
    client = _get_client()
    database = client.get_database_client(settings.cosmos_database_name)
    return database.get_container_client(settings.cosmos_container_name)
