# ADR-0059: scientist_causal_full parallel with scientist_default, single cutover

## Status
Proposed

## Date
2026-02-28

## Context
The existing `scientist_default` workflow covers the core policy-evaluation loop
but lacks advanced causal inference steps such as graph reconciliation, causal
ensemble, and transportability checks. Rather than modifying the stable default
workflow in-place and risking regressions, a new `scientist_causal_full` workflow
is being developed. Running both workflows in parallel allows incremental
validation of the causal-full pipeline against the same inputs before any
production switchover.

## Decision
1. Introduce `scientist_causal_full` as a standalone workflow registered
   alongside `scientist_default` in `workflows/__init__.py`.
2. Both workflows remain selectable at runtime via the workflow builder;
   `scientist_default` stays the implicit default until cutover.
3. Acceptance criteria for cutover: `scientist_causal_full` must produce
   equivalent or superior governance pass rates on the existing integration test
   suite.
4. After cutover, `scientist_default` is retained for one release cycle as a
   fallback, then deprecated.

## Consequences
### Positive
- Parallel execution allows side-by-side comparison of decision packets,
  catching regressions before users are affected.
- The default workflow remains untouched during development, preserving
  stability for existing consumers.
- A single controlled cutover avoids prolonged feature-flag complexity.

### Negative
- Maintaining two parallel workflow definitions temporarily doubles the testing
  and review surface.
- Integration tests must be structured to run against both workflows, increasing
  CI resource usage during the parallel period.
