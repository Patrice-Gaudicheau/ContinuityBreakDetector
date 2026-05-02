from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


class LemonadeError(RuntimeError):
    pass


@dataclass(frozen=True)
class LemonadeClient:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 300.0

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        data = self._chat_json(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            include_chat_template_kwargs=True,
        )
        content = extract_visible_content(data)
        if content:
            return content
        if has_reasoning_content(data):
            retry_prompt = (
                f"{user_prompt}\n\n"
                "Return a visible final answer only. Do not place the report in hidden "
                "reasoning content. Start the visible answer with 'Final report:'."
            )
            data = self._chat_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
                include_chat_template_kwargs=True,
            )
            content = extract_visible_content(data)
            if content:
                return content
        raise LemonadeError("Lemonade response did not contain usable visible content")

    def completion_metadata(self, *, model: str, prompt: str) -> dict[str, Any]:
        data, status_code = self._chat_json_with_status(
            model=model,
            system_prompt="Return a short visible answer. Do not use hidden reasoning.",
            user_prompt=prompt,
            include_chat_template_kwargs=True,
        )
        return safe_response_metadata(data, status_code=status_code)

    def models(self) -> list[str]:
        headers = self._headers()
        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = httpx.get(url, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise LemonadeError(f"Lemonade models request failed: {exc}") from exc
        except ValueError as exc:
            raise LemonadeError("Lemonade models response was not JSON") from exc
        models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return []
        ids: list[str] = []
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("id"), str):
                ids.append(model["id"])
        return ids

    def _chat_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        include_chat_template_kwargs: bool,
    ) -> dict[str, Any]:
        data, _status_code = self._chat_json_with_status(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            include_chat_template_kwargs=include_chat_template_kwargs,
        )
        return data

    def _chat_json_with_status(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        include_chat_template_kwargs: bool,
    ) -> tuple[dict[str, Any], int]:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": 1200,
        }
        if include_chat_template_kwargs:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            response = httpx.post(
                url,
                headers=self._headers(headers),
                json=payload,
                timeout=self.timeout_seconds,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if include_chat_template_kwargs and _looks_like_unsupported_template_kwargs(
                    response
                ):
                    return self._chat_json_with_status(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        include_chat_template_kwargs=False,
                    )
                raise exc
        except httpx.HTTPError as exc:
            raise LemonadeError(f"Lemonade request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LemonadeError("Lemonade response was not JSON") from exc
        if not isinstance(data, dict):
            raise LemonadeError("Lemonade response JSON was not an object")
        if os.getenv("CBD_LEMONADE_DEBUG") == "1":
            print_debug_metadata(response.status_code, data)
        if "error" in data and not data.get("choices"):
            raise LemonadeError("Lemonade response contained an error object and no choices")
        return data, response.status_code

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def extract_visible_content(data: dict[str, Any]) -> str | None:
    first_choice = first_choice_or_none(data)
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    text = first_choice.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def has_reasoning_content(data: dict[str, Any]) -> bool:
    first_choice = first_choice_or_none(data)
    if not isinstance(first_choice, dict):
        return False
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return False
    reasoning = message.get("reasoning_content")
    return isinstance(reasoning, str) and bool(reasoning.strip())


def first_choice_or_none(data: dict[str, Any]) -> Any:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    return choices[0]


def safe_response_metadata(
    data: dict[str, Any], *, status_code: int | None = None
) -> dict[str, Any]:
    choices = data.get("choices")
    first_choice = first_choice_or_none(data)
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    return {
        "http_status_code": status_code,
        "top_level_json_keys": sorted(str(key) for key in data.keys()),
        "choices_length": len(choices) if isinstance(choices, list) else 0,
        "first_choice_keys": (
            sorted(str(key) for key in first_choice.keys())
            if isinstance(first_choice, dict)
            else []
        ),
        "message_keys": sorted(str(key) for key in message.keys())
        if isinstance(message, dict)
        else [],
        "content_exists": bool(extract_visible_content(data)),
        "reasoning_content_exists": has_reasoning_content(data),
        "finish_reason": (
            first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
        ),
    }


def print_debug_metadata(status_code: int, data: dict[str, Any]) -> None:
    metadata = safe_response_metadata(data, status_code=status_code)
    print(f"lemonade_debug_metadata,{metadata}")


def _looks_like_unsupported_template_kwargs(response: httpx.Response) -> bool:
    if response.status_code not in {400, 404, 422}:
        return False
    try:
        text = response.text.lower()
    except RuntimeError:
        return True
    return "chat_template_kwargs" in text or "enable_thinking" in text or "extra" in text
