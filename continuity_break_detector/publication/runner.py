from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.publication.paper import DEFAULT_OUTPUT_DIR, draft_paper
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft a research paper from study outputs.")
    parser.add_argument("--study-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        result = draft_paper(study_path=args.study_path, output_dir=args.output_dir)
    except Exception as exc:
        LOGGER.error("Paper drafting failed before GPT step: %s", exc)
        return 1

    LOGGER.info("study_path,%s", args.study_path)
    LOGGER.info("output_dir,%s", result.output_dir)
    LOGGER.info("source_snapshot,%s", result.snapshot_path)
    if result.gpt_succeeded:
        LOGGER.info("draft,%s", result.draft_path)
        LOGGER.info("metadata,%s", result.metadata_path)
        return 0
    LOGGER.error("GPT-5.5 drafting failed: %s", result.error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
