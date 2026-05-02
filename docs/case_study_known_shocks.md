# Case Study: Known Global Shocks

ContinuityBreakDetector is useful only if it can separate three categories:

- known real-world shocks
- likely data artifacts
- unresolved statistical candidates

The 2008 global financial crisis and the 2020 COVID-19 pandemic are useful
sanity checks because both were large, well-documented shocks that affected
multiple dimensions of human development.

## Why 2008 Is a Sanity Check

The global financial crisis affected economic output, income trajectories,
employment, trade, fiscal conditions, and downstream development indicators.
A cross-domain backtest should therefore be capable of detecting forecast
failure around this period without treating it as mysterious.

In the audited study outputs, 2008 is treated as a low-artifact-risk known shock:

- it appears in modern, better-covered data
- it is not primarily explained by early historical reconstruction
- it has a clear ordinary historical explanation
- it survives artifact filtering without becoming an unexplained candidate

## Why 2020 Is a Sanity Check

The COVID-19 pandemic created a sharp global disruption across health,
demographics, and economics. A system looking for cross-domain anomaly clusters
should be sensitive to this kind of event.

In the audited study outputs, 2020 is also treated as a low-artifact-risk known
shock:

- it affects multiple domains
- it occurs in recent high-coverage data
- it has a clear historical explanation
- it is not classified as an unexplained synchronized break

## Why This Does Not Imply Unexplained Breaks

Detecting 2008 and 2020 is a validation signal for the pipeline, not evidence of
hidden causes. These years demonstrate that known shocks leave measurable traces
in long-term indicators.

The key conclusion remains cautious:

> The system detects known global shocks and data artifacts, but does not
> identify any unexplained synchronized cross-domain continuity break.

Any future unexplained candidate would need to survive source-level review,
artifact filtering, model-sensitivity checks, and comparison against ordinary
historical explanations.

