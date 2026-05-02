from __future__ import annotations

from continuity_break_detector.agents.config import load_agent_config
from continuity_break_detector.agents.lemonade import LemonadeClient, LemonadeError
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    config = load_agent_config()
    client = LemonadeClient(
        base_url=config.lemonade_base_url,
        api_key=config.lemonade_api_key,
        timeout_seconds=60.0,
    )
    try:
        model_ids = client.models()
        LOGGER.info("available_models")
        for model_id in model_ids:
            LOGGER.info("%s", model_id)
        for label, model in [
            ("router", config.router_model),
            ("executor", config.executor_model),
        ]:
            metadata = client.completion_metadata(
                model=model,
                prompt="Reply with exactly this visible text: ok",
            )
            LOGGER.info("%s_model,%s", label, model)
            LOGGER.info("%s_metadata,%s", label, metadata)
            LOGGER.info("%s_visible_content,%s", label, metadata["content_exists"])
    except LemonadeError as exc:
        LOGGER.error("Lemonade debug failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
