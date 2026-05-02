from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    lemonade_base_url: str
    lemonade_api_key: str | None
    router_model: str
    executor_model: str


def load_agent_config() -> AgentConfig:
    return AgentConfig(
        lemonade_base_url=os.getenv("CBD_LEMONADE_BASE_URL", "http://localhost:8000/v1"),
        lemonade_api_key=os.getenv("CBD_LEMONADE_API_KEY"),
        router_model=os.getenv("CBD_ROUTER_MODEL", "Qwen3-0.6B-GGUF"),
        executor_model=os.getenv("CBD_EXECUTOR_MODEL", "Qwen3.5-35B-A3B-GGUF"),
    )
