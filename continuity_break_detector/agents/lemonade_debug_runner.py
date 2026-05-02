from __future__ import annotations

from continuity_break_detector.agents.config import load_agent_config
from continuity_break_detector.agents.lemonade import LemonadeClient, LemonadeError


def main() -> int:
    config = load_agent_config()
    client = LemonadeClient(
        base_url=config.lemonade_base_url,
        api_key=config.lemonade_api_key,
        timeout_seconds=60.0,
    )
    try:
        model_ids = client.models()
        print("available_models")
        for model_id in model_ids:
            print(model_id)
        for label, model in [
            ("router", config.router_model),
            ("executor", config.executor_model),
        ]:
            metadata = client.completion_metadata(
                model=model,
                prompt="Reply with exactly this visible text: ok",
            )
            print(f"{label}_model,{model}")
            print(f"{label}_metadata,{metadata}")
            print(f"{label}_visible_content,{metadata['content_exists']}")
    except LemonadeError as exc:
        print(f"Lemonade debug failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
