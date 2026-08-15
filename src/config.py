from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment configuration, validated in one place.

    Field names map to env vars case-insensitively (cosmos_uri -> COSMOS_URI),
    so this mirrors .env.example without any extra aliasing.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cosmos_uri: str
    # Optional: set for primary-key auth, leave unset for DefaultAzureCredential
    # (az login locally, Managed Identity once deployed). See cosmos_client.py.
    cosmos_key: str | None = None
    cosmos_database_name: str = "studieassistent"
    cosmos_container_name: str = "chunk"

    azure_ai_endpoint: str
    azure_ai_key: str
    azure_ai_deployment_name: str
    # The chat/completions deployment, e.g. gpt-4o-mini. Separate from
    # azure_ai_deployment_name (the embedding deployment) - same Azure AI
    # resource, different model deployment.
    azure_ai_chat_deployment_name: str
    azure_ai_api_version: str = "2024-10-21"
    # Bumped over the openai SDK's own default of 2. The SDK already retries
    # transient errors (429, 5xx, connection failures) with exponential
    # backoff internally - this only tunes how many attempts it gets.
    azure_ai_max_retries: int = 5


@lru_cache
def get_settings() -> Settings:
    """Build (and cache) Settings on first use.

    Deliberately not a module-level instance: that would just move the
    import-time-requires-Azure-credentials problem here from embeddings.py
    instead of fixing it. Nothing reads the environment until something
    actually calls get_settings().
    """
    return Settings()
