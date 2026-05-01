from __future__ import annotations

from dataclasses import dataclass

import httpx


class LemonadeError(RuntimeError):
    pass


@dataclass(frozen=True)
class LemonadeClient:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 120.0

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LemonadeError(f"Lemonade request failed: {exc}") from exc

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LemonadeError("Lemonade response did not contain message content") from exc
        if not isinstance(content, str) or not content.strip():
            raise LemonadeError("Lemonade response content was empty")
        return content.strip()

