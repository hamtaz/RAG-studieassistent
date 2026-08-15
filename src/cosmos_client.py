from functools import lru_cache

from azure.cosmos import ContainerProxy, CosmosClient
from azure.identity import DefaultAzureCredential

from src.config import get_settings


def _build_credential(cosmos_key: str | None) -> str | DefaultAzureCredential:
    """Key auth if a key is configured, RBAC via DefaultAzureCredential otherwise.

    DefaultAzureCredential tries az CLI login locally and falls back to
    Managed Identity once deployed - no secret stored either way.
    """
    if cosmos_key:
        return cosmos_key
    return DefaultAzureCredential()


@lru_cache
def _get_client() -> CosmosClient:
    """Build (and cache) the CosmosClient once.

    CosmosClient owns a connection pool and is meant to be long-lived and
    shared, not constructed per call.
    """
    settings = get_settings()
    credential = _build_credential(settings.cosmos_key)
    return CosmosClient(settings.cosmos_uri, credential=credential)


def get_container() -> ContainerProxy:
    settings = get_settings()
    client = _get_client()
    database = client.get_database_client(settings.cosmos_database_name)
    return database.get_container_client(settings.cosmos_container_name)
