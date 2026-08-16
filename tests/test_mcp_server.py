from unittest.mock import MagicMock

import src.mcp_server as mcp_server


def test_ask_study_assistant_returns_answer_question_result(monkeypatch):
    monkeypatch.setattr(mcp_server, "get_container", lambda: MagicMock())
    monkeypatch.setattr(
        mcp_server,
        "answer_question",
        lambda question, container: {"answer": "42", "sources": [{"source_name": "x.pdf"}]},
    )

    result = mcp_server.ask_study_assistant("What is the answer?")

    assert result == {"answer": "42", "sources": [{"source_name": "x.pdf"}]}
