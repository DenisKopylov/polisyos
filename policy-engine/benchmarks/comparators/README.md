# Research Acceptance Comparator Stack

This directory defines the external benchmark toolchain required for a
publication-grade `research_acceptance` run.

Required comparators
- `econml`: DML, Causal Forest, X-Learner family.
- `stochtree`: BCF/BART-style nonlinear baseline for HTE and LBIDD.
- `zepid`: TMLE baseline and cross-fit reference semantics.
- `dowhy`: reference estimation pipelines and graph-aware diagnostics.
- `y0`: symbolic identification parity for PolicyOS vs external ID stack.
- `lightgbm`: acceptance-grade nuisance backend for the shared benchmark stack.

Policy
- `local_evidence` runs may proceed with lightweight local PolicyOS estimators and
  missing comparators recorded under `preflight.comparator_status`.
- `research_acceptance` runs must fail fast if the comparator stack is incomplete.
- Comparator wrappers should serialize results into the same benchmark JSON schema
  as native PolicyOS suites, including `benchmark_tier`, `method_groups`, and
  `aggregate_metrics`.

Recommended usage
1. Create a dedicated benchmark environment from
   [research_acceptance_environment.yml](/Users/deniskopylov/polisyos/policy-engine/benchmarks/comparators/research_acceptance_environment.yml).
2. Export the same data env vars used by local runners: `ACIC_DATA_DIR`,
   `LBIDD_DATA_DIR`, `REALCAUSE_DATA_DIR`.
3. Run `bash /Users/deniskopylov/polisyos/policy-engine/benchmarks/run_all_benchmarks.sh --mode acceptance --tier research_acceptance`.
