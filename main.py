from __future__ import annotations

import sys

from continuity_break_detector.ingestion.runner import main as ingestion_main


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "ingest":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return ingestion_main()
    print("Usage: python main.py ingest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

