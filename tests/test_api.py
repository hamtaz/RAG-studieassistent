from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from openai import OpenAIError

import src.api as api

client = TestClient(api.app)


def test_ask_returns_answer_and_sources(monkeypatch):
    monkeypatch.setattr(api, "get_container", lambda: MagicMock())
    monkeypatch.setattr(
        api,
        "answer_question",
        lambda question, container: {"answer": "42", "sources": [{"source_name": "x.pdf"}]},
    )

    response = client.post("/ask", json={"question": "What is the answer?"})

    assert response.status_code == 200
    assert response.json() == {"answer": "42", "sources": [{"source_name": "x.pdf"}]}


def test_ask_returns_502_on_upstream_failure(monkeypatch):
    monkeypatch.setattr(api, "get_container", lambda: MagicMock())

    def raise_openai_error(question, container):
        raise OpenAIError("boom")

    monkeypatch.setattr(api, "answer_question", raise_openai_error)

    response = client.post("/ask", json={"question": "What is the answer?"})

    assert response.status_code == 502
