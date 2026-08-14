import pytest
from pydantic import ValidationError

from src.config import Settings, get_settings

REQUIRED = {
    "cosmos_uri": "https://example.documents.azure.com:443/",
    "cosmos_key": "fake-key",
    "azure_ai_endpoint": "https://example.openai.azure.com/",
    "azure_ai_key": "fake-key",
    "azure_ai_deployment_name": "fake-deployment",
}


def make_settings(**overrides):
    """Build Settings from explicit values only.

    _env_file=None stops pydantic-settings from reading the developer's real
    .env - these tests must never depend on, or be able to see, real
    credentials.
    """
    values = {**REQUIRED, **overrides}
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """get_settings() is lru_cache'd; without clearing, one test's cached
    instance would leak into the next."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_accepts_all_required_fields():
    settings = make_settings()
    assert settings.cosmos_uri == REQUIRED["cosmos_uri"]
    assert settings.azure_ai_deployment_name == REQUIRED["azure_ai_deployment_name"]


@pytest.mark.parametrize(
    "missing", ["cosmos_uri", "cosmos_key", "azure_ai_endpoint", "azure_ai_key", "azure_ai_deployment_name"]
)
def test_settings_raises_on_missing_required_field(missing):
    values = {key: value for key, value in REQUIRED.items() if key != missing}
    with pytest.raises(ValidationError, match=missing):
        Settings(_env_file=None, **values)


def test_settings_reports_every_missing_field_at_once():
    """One clear error listing everything missing, not one ValueError per
    call site the first time each var happens to be touched."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    missing_fields = {error["loc"][0] for error in excinfo.value.errors()}
    assert missing_fields == set(REQUIRED)


def test_settings_defaults():
    settings = make_settings()
    assert settings.cosmos_database_name == "studieassistent"
    assert settings.cosmos_container_name == "chunk"
    assert settings.azure_ai_api_version == "2024-10-21"


def test_settings_defaults_are_overridable():
    settings = make_settings(cosmos_database_name="other-db", cosmos_container_name="other-container")
    assert settings.cosmos_database_name == "other-db"
    assert settings.cosmos_container_name == "other-container"


def test_get_settings_is_cached(monkeypatch):
    """Same instance on repeated calls, so Azure clients built from it can
    also be cached without rebuilding per call."""
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key.upper(), value)

    first = get_settings()
    second = get_settings()
    assert first is second
