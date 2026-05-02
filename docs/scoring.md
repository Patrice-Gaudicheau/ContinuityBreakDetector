# Scoring Transparency

ContinuityBreakDetector uses deterministic heuristic scores to reduce noisy
backtest outputs into smaller sets of candidates. These scores are intended for
triage and review, not as proof of causality.

The scoring rules below are heuristic and subject to tuning as more datasets,
normalization rules, and validation cases are added.

## Ranking Score

Ranked break candidates are aggregated by target year. The rank score combines
four normalized components:

- `0.35 * normalized(mean_z_score)`
- `0.25 * normalized(affected_domain_count)`
- `0.20 * normalized(log1p(anomaly_count))`
- `0.20 * persistence_score`

Normalization is min-max normalization over all candidate years in a study. If a
component has the same value for every candidate, that component contributes
`0.0`.

`persistence_score` is the fraction of years in the five-year window
`target_year - 2` through `target_year + 2` that contain anomalies.

Nearby high-ranking candidates within a three-year window are reduced to a local
representative year, but all candidate years remain available in the parquet
output.

## Candidate Audit Score

The candidate audit estimates statistical robustness:

- `0.30 * model_agreement_score`
- `0.30 * domain_agreement_score`
- `0.20 * normalized(log1p(anomaly_count))`
- `0.20 * persistence_score`

The score is then reduced by deterministic risk penalties:

- `0.20` for high sparsity risk, or `0.10` for medium sparsity risk
- `0.15` for high historical-data risk, or `0.08` for medium historical-data risk
- `0.10` when an exact-year known ordinary explanation hint exists

The final robustness score is clamped to `[0.0, 1.0]`.

## Artifact Score

The data artifact audit estimates whether a candidate may be caused by data
quality or methodology issues rather than a real-world discontinuity:

- `0.25 * single_source_dominance`
- `0.25 * extreme_z_score_risk`
- `0.20 * historical_coverage_risk`
- `0.15 * has_revision_artifact_hint`
- `0.15 * model_echo_risk`

If the candidate has a known real-world event hint, `0.15` is subtracted. The
final artifact score is clamped to `[0.0, 1.0]`.

Artifact verdicts:

- `likely_data_artifact` for scores `>= 0.60`
- `possible_data_artifact` for scores `>= 0.35`
- `low_artifact_risk` otherwise

These labels indicate review priority. They do not prove that a candidate is or
is not a genuine historical discontinuity.
