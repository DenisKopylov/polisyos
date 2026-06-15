# Foundry Phase 2 Acceptance

Owner: `@foundry-owners`
Source of truth: `tools/quality/validation/foundry_phase2_manifest.json`, `tools/quality/validation/validate_foundry_phase2_closure.py`, `tools/quality/validation/run_foundry_phase2_validation.sh`, and `tools/quality/validation/generate_foundry_phase2_evidence.py`

Foundry Phase 2 is closed only when every `P2.01` through `P2.14` track has a
machine-checkable evidence path that is reproducible from the repository:
typed target surface, enrolled acceptance tests, enrolled benchmark entrypoint,
synthetic-world verification, and a passing six-judge verdict. Unlike the
legacy Scientist remediation gate, this document and the validator below are
the canonical source of truth for Foundry Phase 2 closure.

## Source Of Truth

- Manifest: `tools/quality/validation/foundry_phase2_manifest.json`
- Validator: `tools/quality/validation/validate_foundry_phase2_closure.py`
- Wrapper: `tools/quality/validation/run_foundry_phase2_validation.sh`
- Evidence generator: `tools/quality/validation/generate_foundry_phase2_evidence.py`
- Compatibility wrapper: `tools/ci/check_scientist_phase2_gate.py`

## Exit Criteria

The canonical validator must report `overall_status = "complete"` and every
track summary in the manifest must be `status = "pass"`.

For each manifest track, the validator checks all of the following:

- Every `typed_target` resolves to a real public surface.
- Every `required_acceptance_test` is present in the enrolled JUnit report and passes.
- Every `required_benchmark` is present in the enrolled benchmark report and passes.
- Every `required_synthetic_world_check` is present in the evidence report and passes.
- Every `required_judge_verdict` is present in the evidence report and carries a promote-grade verdict.

If any one of those checks is missing or red, the corresponding artifact family
must stay capped at `RESEARCH_ARTIFACT` / `PROOF_ONLY` for
`PROOF_ONLY -> ENGINEER_READY`.

## Track Matrix

| Track                             | Canonical typed target(s)                      | Acceptance surface                                                                                                                                                                                            | Benchmark                                            |
| --------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `P2.01` high-dimensional IV       | `EconometricResult.post_selection_ci`          | `tests/unit/foundry/methods/catalog/econometrics/test_iv.py::test_high_dimensional_post_selection_iv_assigns_orthogonal_tier`                                                                                      | `phase2_econometrics_frontier`                       |
| `P2.02` thresholds / kinks        | `EconometricResult.threshold_state_field`      | `tests/unit/foundry/methods/catalog/econometrics/test_thresholds.py::test_state_dependent_threshold_runs_with_known_surface`                                                                                       | `phase2_econometrics_frontier`                       |
| `P2.03` nonstationary GARCH       | `EconometricResult.nonstationary_volatility`   | `tests/unit/foundry/methods/test_foundry_v2_domains.py::test_foundry_v2_nonstationary_garch_dispatch`                                                                                                                      | `phase2_econometrics_frontier`                       |
| `P2.04` distributional bounds     | `DistributionalBoundsBundle`                   | `tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py::test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families`                                                                 | `phase2_distributional_frontier`                     |
| `P2.05` mobility attrition        | `MobilityReport`                               | `tests/unit/foundry/methods/catalog/distributional/test_mobility.py::TestTransitionMatrix::test_attrition_adjusted_ipcw_recovers_balanced_rows_and_persists_bounds`                                                | `phase2_mobility_frontier`                           |
| `P2.06` ordinal poverty           | `OrdinalPovertyReport`                         | `tests/unit/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py::test_ordinal_poverty_config_persists_report_and_summary`                                                                        | `phase2_distributional_frontier`                     |
| `P2.07` peer effects              | `NetworkResult.peer_effect_decomposition`      | `tests/unit/foundry/methods/catalog/network/test_peer_effect_decomposition.py::test_peer_effect_decomposition_identified_route`                                                                                    | `phase2_network_identification`                      |
| `P2.08` strategic formation       | `NetworkResult.formation_diagnostic`           | `tests/unit/foundry/methods/catalog/network/test_analysis.py::TestStrategicNetworkFormation::test_event_history_route_is_used_when_available`                                                                      | `phase2_network_identification`                      |
| `P2.09` ERGM / SBM stratification | `ERGMResult`, `SBMStratificationResult`        | `tests/unit/foundry/methods/catalog/network/test_ergm.py::test_ergm_null_model_returns_diagnostics`, `tests/unit/foundry/methods/catalog/network/test_sbm.py::test_sbm_stratification_bridges_into_network_causal_data` | `ergm_null_diffusion`, `sbm_stratified_interference` |
| `P2.10` partial observability     | `NetworkResult.missingness_assessment`         | `tests/unit/foundry/methods/catalog/network/test_missingness.py::test_network_estimator_threads_missingness_assessment_into_result`                                                                                | `phase2_network_identification`                      |
| `P2.11` embedding fidelity        | `NetworkResult.embedding_fidelity_certificate` | `tests/unit/foundry/methods/catalog/network/test_embedding_fidelity.py::test_embedding_fidelity_certificate_green_when_separator_is_recoverable`                                                                   | `phase2_network_identification`                      |
| `P2.12` MAUP invariance           | `SpatialResult.maup_invariance_certificate`    | `tests/unit/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_maup_certificate_with_candidate_partitions`                                                                             | `phase2_spatial_identification`                      |
| `P2.13` spatial interference      | spatial `InterferenceCertificate`              | `tests/unit/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_status_success`                                                                                                         | `phase2_spatial_identification`                      |
| `P2.14` causal SAE smoothing      | `SpatialResult.spatial_hodge_diagnostics`      | `tests/unit/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_hodge_diagnostics_attach_multiscale_profile`                                                                            | `survey_causal_frontier_sae`                         |

## Reproducible Command

From the `policy-engine` repository root:

```bash
tools/quality/validation/run_foundry_phase2_validation.sh
```

This wrapper runs the enrolled Phase 2 acceptance suites, the family-level
six-judge suite, the enrolled benchmark entrypoints, generates the synthetic
world / judge evidence bundle, and then evaluates the canonical Phase 2
closure validator. The wrapper also refreshes the runtime-readable latest
closure report at `benchmarks/_reports/foundry_phase2_latest/foundry_phase2_closure.json`.
