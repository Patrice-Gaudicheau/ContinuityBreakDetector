# Architecture

This document explains the main design choices in ContinuityBreakDetector. It is
intended for reviewers and contributors who want to understand why the project is
structured as a deterministic core with optional external ML workers.

## Project Purpose

ContinuityBreakDetector identifies continuity-break candidates in long-run public
time series. It ingests heterogeneous public data, normalizes it into comparable
yearly series, computes deterministic statistical features, runs rolling
backtests, ranks candidate break years, and audits likely data artifacts.

Deterministic statistical analysis remains the core because the project needs
inspectable evidence. A break candidate should be traceable to source data,
intermediate artifacts, scoring rules, and audit outputs. ML forecasts can add a
secondary signal, but they do not replace the statistical detector.

## Layered Architecture

The project is organized into layers with explicit boundaries:

- Core statistical detector: normalization, feature generation, break scoring,
  rolling backtests, ranking, and artifact checks.
- Data and artifact layer: local raw responses, normalized Parquet files,
  study outputs, provenance metadata, and publication inputs.
- Optional ML forecasting layer: TimesFM and Chronos workers isolated from the
  core environment.
- CLI orchestration: commands compose existing modules and write structured JSON
  or file artifacts.
- Docker worker isolation: model-specific Python environments are built and run
  separately from the lightweight core container.

The core package remains usable without Docker, Torch, TimesFM, or Chronos.

## Why Parquet?

Parquet is used for internal tabular artifacts because it provides typed
columnar storage and efficient reads/writes for time-series style data. This is
useful when later stages need only selected columns or subsets of a study.

Parquet also improves reproducibility and auditability. Schema information is
stored with the file, numeric columns remain typed, and intermediate artifacts
are less dependent on ad hoc CSV parsing rules.

CSV is still useful for interchange, debugging, and publication tables. It is
not the main internal artifact format because CSV loses type information,
requires repeated parsing decisions, and is easier to accidentally alter in ways
that affect downstream results.

## Why Subprocess and Docker Workers Instead of Threads?

ML dependencies such as Torch, TimesFM, and Chronos are heavy, version-sensitive,
and not required by the statistical detector. Running them behind subprocess or
Docker boundaries keeps the core environment small and stable.

Process isolation also gives clearer failure boundaries. Worker failures can be
captured through stdout, stderr, and exit codes without taking down the whole
core pipeline. Docker further separates Python versions and native libraries,
which matters because the core can use Python 3.12 while ML workers can use
Python 3.11.

Threads are not the right boundary for this layer. CPU-heavy and native-library
workloads interact poorly with Python threading assumptions, and thread failures
do not isolate dependency conflicts or native crashes. A process boundary is
simpler to reason about and easier to clean up.

## Why JSON Over stdin/stdout?

JSON over stdin/stdout is the current worker protocol because it is simple local
IPC:

- no port allocation
- no HTTP server lifecycle
- easy CLI and batch composition
- direct capture of stdout, stderr, and exit codes
- one clear machine-readable output stream

The contract is strict: stdout contains JSON only, while logs, warnings, cache
messages, and model download progress go to stderr. One-shot workers read one
JSON object and exit. Warm daemon workers use newline-delimited JSON, one request
and one response per line.

## Why Shared Prediction Schema?

The module `continuity_break_detector.prediction_schema` is the source of truth
for prediction request and response validation. It is shared by the core client,
worker scripts, CLI paths, and tests.

This prevents contract drift. Without a shared schema, the core, TimesFM worker,
Chronos worker, daemon client, and tests could each accept slightly different
payloads or produce different error shapes. Centralized validation makes future
backends, such as daemon or remote workers, safer to add.

## Why Normalization and Scoring Schema?

The input signals come from heterogeneous sources with different units, scales,
coverage, and revision patterns. Normalization makes those signals comparable
enough for cross-domain ranking and review.

Break scores and heuristic weights are deterministic and documented so they can
be inspected. They are evidence, not proof. A high score identifies a candidate
that deserves review; it does not establish cause. This distinction is important
because real shocks, source revisions, sparse historical coverage, and data
artifacts can all produce discontinuities.

## Why Optional ML?

ML forecasting is a secondary signal. TimesFM and Chronos can help ask whether a
series continued in an unexpected way, but their outputs are not the core
detector and should not override deterministic statistical evidence.

The project must remain usable without Docker or ML dependencies. This keeps the
demo, tests, deterministic pipeline, and documentation accessible on a standard
Python environment. Optional ML workers can be built when a contributor wants to
run model-backed prediction or compare model expectations.

## Current Trade-offs and Limitations

- One-shot workers are simple and robust, but each prediction pays container,
  Python, and model-load overhead.
- Daemon mode improves repeated predictions by keeping a model process warm, but
  it is still experimental.
- Docker adds operational complexity and requires users to understand image
  builds, volumes, and runtime caches.
- Model outputs are not deterministic in the same sense as statistical scoring.
  They depend on model versions, library behavior, and runtime details.
- Batch and backtest scaling still need resource controls, concurrency limits,
  timeout policies, and better lifecycle handling.

## Future Direction

Near-term architecture work should focus on:

- batch daemon mode for repeated forecast calls
- resource limits and concurrency controls for ML workers
- stronger integration tests around worker failure modes
- an optional hosted coverage badge if a service such as Codecov or Coveralls is
  configured
- further unification of worker backends only where it reduces duplication

The guiding constraint is that the deterministic core remains lightweight,
auditable, and usable without optional ML infrastructure.
