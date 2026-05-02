from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)
DEFAULT_USER_AGENT = "ContinuityBreakDetector/0.1"


class HttpClient:
    """Small synchronous httpx wrapper with retries and optional pacing."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        backoff_factor: float = 1.0,
        user_agent: str = DEFAULT_USER_AGENT,
        mailto: str | None = None,
        min_interval_seconds: float = 0.0,
    ) -> None:
        if mailto:
            user_agent = f"{user_agent} (mailto:{mailto})"
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": user_agent,
                "Accept": "*/*",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        self._sleep_if_needed()
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._client.get(url, params=params, headers=headers)
                if response.status_code < 500 and response.status_code != 429:
                    return response
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                sleep_seconds = self.backoff_factor * (2**attempt)
                LOGGER.warning(
                    "GET retry %s/%s for %s after %s",
                    attempt + 1,
                    self.retries,
                    url,
                    exc,
                )
                time.sleep(sleep_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"GET failed without response: {url}")

    def _sleep_if_needed(self) -> None:
        if self.min_interval_seconds <= 0:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()
