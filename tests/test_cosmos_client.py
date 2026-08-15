from azure.identity import DefaultAzureCredential

from src.cosmos_client import _build_credential


def test_build_credential_returns_key_when_present():
    assert _build_credential("fake-key") == "fake-key"


def test_build_credential_returns_default_azure_credential_when_absent():
    # DefaultAzureCredential() only builds a credential chain - no network
    # call happens until a token is actually requested, so this is safe to
    # construct offline.
    assert isinstance(_build_credential(None), DefaultAzureCredential)
