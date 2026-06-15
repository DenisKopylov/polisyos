# Layer 3 GY Task 0 P0 Coverage Findings

Scope: close the four P0 audit gaps identified after the first Task 0 pass:
production job -> worker -> DAG, the 406 excluded candidate-positive statuses,
blocked DAG state reads, and depth-2 generalization beyond the UA MSME case.

## Result

P0 is now explicitly audited, but it is **not green** for downstream planning.
The audit artifact passes because the evidence is complete enough to block bad
claims, not because the production route is healthy.

Primary artifact:

- `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_p0_coverage_audit.json`
- validator: `tools/quality/validation/check_layer3_gy_p0_coverage_audit.py`
- tests: `tests/repo_quality/tools/test_layer3_gy_p0_coverage_audit.py`

## Findings

### P0-1: production worker path reaches the DAG, but job status launders workflow failure

Executed proof:

- Existing dispatch proof passed:
  `uv run pytest tests/unit/runtime/http/test_runtime_api_observability.py::test_control_job_execution_metrics_preserve_trace_context -q`
- Real path probe:
  `launch_workflow_run -> _enqueue_job -> ControlWorker.dispatch_once -> _process_control_job -> _execute_workflow -> run_experiment`

Observed:

- control job state: `completed`
- persisted `scientist_policy_design` workflow report: `fail`
- workflow report counts: `12 ok / 1 fail / 24 skip`
- failing node: `bind_foundry_inputs` on invalid runtime fixture `DataSnapshot`

This proves the critical mismatch: `run_lifecycle.py:1408` calls
`run_experiment(...)` and discards the returned final state/report status.
The NL path at `nl_pipeline.py:6596` captures `final_state` and consumes
`reports_index.workflow_report`; therefore GY-2 should not be scoped only to the
discarded call site.

### P0-2: all 406 candidate-positive statuses are enumerated and firewall-excluded

Counts:

- `candidate_positive_status_count = 406`
- `positive_status_count = 0`
- `excluded_candidate_count = 406`
- firewall reasons:
  - `397` generic diagnostic `status=pass` without producer/reducer provenance
  - `8` search-health pass fields without producer/reducer provenance
  - `1` external demand-pull input-only pass with explicit `may_not_use_for`

No false exclusions were found by the current rule. The remaining risk is not
that GX counted a production positive incorrectly; it is that public/generated
surfaces can still display diagnostic `pass` fields without an authority
boundary.

### P0-3: blocked DAG inputs now map to concrete state reads

Input-blocked nodes:

- `build_literature_prior`: missing `params.causal_variables`
- `reconcile_causal_graph`: missing `params.data_causal_graph`; also lacks
  `artifacts_index.literature_prior_ref` because the prior node skipped
- `run_causal_evaluation`: missing top-level `observational_data_ref` even when
  `inputs.data_snapshot_ref` / `inputs.input_bindings_ref` exist elsewhere

Classification:

- causal variables: `route_omitted`
- data causal graph: `producer_missing`
- observational data bridge: `available_elsewhere_not_wired`

The 19 downstream skipped nodes are not independent input gaps; they are
`blocked_upstream` by `run_hierarchical_policy_search`.

### P0-4: depth-2 generalization fails before any universal claim

Second case: `pl-household-energy-affordability-2024`.

Catalog:

- country-filtered PL/PK probes returned `0` results despite 80 text candidates
- unfiltered probes returned plausible global/unscoped hits, including Eurostat
  `NRG_PC_204` and World Bank poverty/social-protection datasets

DAG:

- with a minimal valid non-authority `fabric.data_snapshot`, the second case ran
  the real `scientist_policy_design` DAG
- result: `fail`, `14 ok / 1 fail / 22 skip`
- failing node: `run_hierarchical_policy_search`
- failure: `verified_policy_option_rate: lower >= upper`

Reducers:

- GX reducer CLI has no arbitrary case input
- implementation loads the pinned `layer3_gx_data_home` request
- depth-2 reducer generalization is therefore `route_omitted_case_not_parameterized`

## Plan Impact

GY-2 should be reframed around the workflow-report/final-state authority
boundary and its surfaces, not just the discarded `run_lifecycle.py` call. GY-1
must also cover jurisdiction/source-contract admissibility, because catalog
search can produce plausible topical hits while country-filtered admission
returns zero.
