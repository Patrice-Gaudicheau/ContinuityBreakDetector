from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

DEFAULT_TIMESFM_LOCAL_PATH = Path("~/projects/timesfm").expanduser()
DEFAULT_CHRONOS_LOCAL_PATH = Path("~/projects/chronos-forecasting").expanduser()


@dataclass(frozen=True)
class ImportAttempt:
    module: ModuleType | None
    available: bool
    reason: str
    source_path: str | None = None


@contextmanager
def temporary_sys_path(path: Path) -> Iterator[None]:
    path_text = str(path)
    inserted = False
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(path_text)
            except ValueError:
                pass


def import_with_local_fallback(
    module_name: str,
    *,
    env_var: str,
    default_root: Path,
    candidate_relative_paths: list[str],
) -> ImportAttempt:
    try:
        module = importlib.import_module(module_name)
        return ImportAttempt(module, True, "installed import succeeded", None)
    except Exception as installed_error:
        installed_reason = f"installed import failed: {installed_error}"

    roots = _candidate_roots(env_var, default_root)
    checked_paths: list[str] = []
    errors: list[str] = [installed_reason]
    for root in roots:
        if not root.exists():
            errors.append(f"local root does not exist: {root}")
            continue
        for candidate in _candidate_paths(root, candidate_relative_paths):
            checked_paths.append(str(candidate))
            if not candidate.exists():
                continue
            try:
                with temporary_sys_path(candidate):
                    module = importlib.import_module(module_name)
                return ImportAttempt(
                    module,
                    True,
                    f"local import succeeded from {candidate}",
                    str(candidate),
                )
            except Exception as local_error:
                errors.append(f"local import failed from {candidate}: {local_error}")

    if checked_paths:
        errors.append(f"checked local paths: {', '.join(checked_paths)}")
    return ImportAttempt(None, False, "; ".join(errors), None)


def timesfm_candidate_paths(root: Path) -> list[Path]:
    return _candidate_paths(root, ["src", "timesfm-forecasting", "."])


def chronos_candidate_paths(root: Path) -> list[Path]:
    return _candidate_paths(root, ["src", "."])


def _candidate_roots(env_var: str, default_root: Path) -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get(env_var)
    if configured:
        roots.append(Path(configured).expanduser())
    if default_root not in roots:
        roots.append(default_root)
    return roots


def _candidate_paths(root: Path, relative_paths: list[str]) -> list[Path]:
    paths: list[Path] = []
    for relative in relative_paths:
        candidate = root if relative == "." else root / relative
        if candidate not in paths:
            paths.append(candidate)
    return paths
