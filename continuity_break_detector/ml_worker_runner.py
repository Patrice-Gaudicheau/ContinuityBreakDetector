from __future__ import annotations

import argparse

from continuity_break_detector.ml_workers import (
    WorkerResult,
    run_chronos_worker_smoke,
    run_timesfm_worker_smoke,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run optional Docker ML worker smoke tests.")
    parser.add_argument(
        "--worker",
        choices=["all", "timesfm", "chronos"],
        default="all",
        help="Worker smoke test to run.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run opt-in model smoke tests that may download weights.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout per worker in seconds.",
    )
    args = parser.parse_args()

    results: list[WorkerResult] = []
    if args.worker in {"all", "timesfm"}:
        results.append(run_timesfm_worker_smoke(full=args.full, timeout=args.timeout))
    if args.worker in {"all", "chronos"}:
        results.append(run_chronos_worker_smoke(full=args.full, timeout=args.timeout))

    for result in results:
        status = "passed" if result.succeeded else "failed"
        print(f"{result.worker_name}: {status} (exit {result.returncode})")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())

    return 0 if all(result.succeeded for result in results) else 1
