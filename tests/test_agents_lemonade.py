from __future__ import annotations

import httpx
import pytest

from continuity_break_detector.agents.lemonade import LemonadeClient, LemonadeError


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

    with pytest.raises(LemonadeError, match="empty"):
        client.chat(model="model", system_prompt="system", user_prompt="user")
