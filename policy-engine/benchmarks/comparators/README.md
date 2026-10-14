# Research Acceptance Comparator Stack

This directory defines the external benchmark toolchain required for a
publication-grade `research_acceptance` run.

Required comparators

The required set is defined by [`stack.py`](stack.py).

- `econml`: DML, Causal Forest, X-Learner family.
- `stochtree`: BCF/BART-style nonlinear baseline for HTE and LBIDD.
- `zepid`: TMLE baseline and cross-fit reference semantics.
- `dowhy`: reference estimation pipelines and graph-aware diagnostics.
- `y0`: symbolic identification parity for PolicyOS vs external ID stack.
- `lightgbm`: acceptance-grade nuisance backend for the shared benchmark stack.

Policy
- The suite preflight records comparator availability in
  `preflight.comparator_status`. `local_evidence` runs may proceed with missing
  comparators; in the `research_acceptance` tier, preflight rejects an unavailable
  required module. See [`advanced/common.py`](../advanced/common.py),
  [`runtime.py`](../runtime.py), and [`reporting.py`](../reporting.py).
- Comparator wrappers should serialize results into the same benchmark JSON schema
  as native PolicyOS suites, including `benchmark_tier`, `method_groups`, and
  `aggregate_metrics`.

Recommended usage
1. Create a dedicated benchmark environment from
   [research_acceptance_environment.yml](research_acceptance_environment.yml).
2. Export the same data env vars used by local runners: `ACIC_DATA_DIR`,
   `LBIDD_DATA_DIR`, `REALCAUSE_DATA_DIR`.
3. From `policy-engine/`, use the
   [canonical benchmark entry point](../../tools/research/benchmarks/README.md):
   `uv run polisyos-tools benchmarks run-all --mode acceptance --tier research_acceptance`.

## Last Updated

2026-10-14
