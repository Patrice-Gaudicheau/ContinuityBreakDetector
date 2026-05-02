from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.publication.paper import DEFAULT_OUTPUT_DIR, draft_paper


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft a research paper from study outputs.")
    parser.add_argument("--study-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        result = draft_paper(study_path=args.study_path, output_dir=args.output_dir)
    except Exception as exc:
        print(f"Paper drafting failed before GPT step: {exc}")
        return 1

    print(f"study_path,{args.study_path}")
    print(f"output_dir,{result.output_dir}")
    print(f"source_snapshot,{result.snapshot_path}")
    if result.gpt_succeeded:
        print(f"draft,{result.draft_path}")
        print(f"metadata,{result.metadata_path}")
        return 0
    print(f"GPT-5.5 drafting failed: {result.error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

