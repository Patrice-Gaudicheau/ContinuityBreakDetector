from __future__ import annotations

import httpx
import pytest

from continuity_break_detector.agents.lemonade import (
    LemonadeClient,
    LemonadeError,
    safe_response_metadata,
)


def test_missing_lemonade_response_is_treated_as_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_post(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", "http://localhost:8000/v1/chat/completions")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": ""}}]},
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    with pytest.raises(LemonadeError, match="visible content"):
        client.chat(model="model", system_prompt="system", user_prompt="user")


def test_message_content_extraction(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_post(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _json_response({"choices": [{"message": {"content": " visible "}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    assert client.chat(model="model", system_prompt="system", user_prompt="user") == "visible"


def test_choice_text_extraction(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_post(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _json_response({"choices": [{"text": " text answer "}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    assert client.chat(model="model", system_prompt="system", user_prompt="user") == "text answer"


def test_reasoning_content_only_triggers_retry(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = []

    def fake_post(*_args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["json"])
        if len(calls) == 1:
            return _json_response(
                {"choices": [{"message": {"reasoning_content": "hidden reasoning"}}]}
            )
        return _json_response({"choices": [{"message": {"content": "final answer"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    assert client.chat(model="model", system_prompt="system", user_prompt="user") == "final answer"
    assert len(calls) == 2
    assert "visible final answer only" in calls[1]["messages"][1]["content"]


def test_reasoning_content_only_fails_after_retry(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_post(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _json_response({"choices": [{"message": {"reasoning_content": "hidden reasoning"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    with pytest.raises(LemonadeError, match="visible content"):
        client.chat(model="model", system_prompt="system", user_prompt="user")


def test_unsupported_chat_template_kwargs_retries_without_it(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payloads = []

    def fake_post(*_args, **kwargs):  # type: ignore[no-untyped-def]
        payloads.append(kwargs["json"])
        if len(payloads) == 1:
            return _json_response({"error": "unknown field chat_template_kwargs"}, status_code=400)
        return _json_response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LemonadeClient(base_url="http://localhost:8000/v1")

    assert client.chat(model="model", system_prompt="system", user_prompt="user") == "ok"
    assert "chat_template_kwargs" in payloads[0]
    assert "chat_template_kwargs" not in payloads[1]


def test_debug_metadata_excludes_full_content_and_reasoning() -> None:
    metadata = safe_response_metadata(
        {
            "id": "abc",
            "choices": [
                {
                    "message": {
                        "content": "visible report",
                        "reasoning_content": "hidden reasoning",
                    },
                    "finish_reason": "stop",
                }
            ],
        },
        status_code=200,
    )

    serialized = str(metadata)
    assert metadata["content_exists"] is True
    assert metadata["reasoning_content_exists"] is True
    assert "visible report" not in serialized
    assert "hidden reasoning" not in serialized


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    request = httpx.Request("POST", "http://localhost:8000/v1/chat/completions")
    return httpx.Response(status_code, json=payload, request=request)
