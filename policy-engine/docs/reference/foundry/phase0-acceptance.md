# Foundry Phase 0 Acceptance

Foundry Phase 0 is considered complete only when the typed uncertainty surfaces,
runtime substrate, and benchmark evidence are all machine-checkable in the
repository. This acceptance surface is separate from
`tools/ci/check_scientist_phase0_gate.py`; that scientist gate remains a
different remediation artifact and is not the source of truth for Foundry
Phase 0 closure.

## Source Of Truth

- Manifest: `tools/quality/validation/foundry_phase0_manifest.json`
- Validator: `tools/quality/validation/validate_foundry_phase0_closure.py`
- Wrapper: `tools/quality/validation/run_foundry_phase0_validation.sh`
- Required benchmark: `benchmarks/synthetic_world/phase0_seed_benchmark.py --mode smoke`

## Exit Criteria

The validator must report `overall_status = "complete"` and every manifest
deliverable must be `complete`.

The benchmark report used by the validator must prove all of the following:

- `aggregate_metrics.target_coverage_rate == 1.0`
- `aggregate_metrics.deterministic_replay_rate == 1.0`
- At least one benchmark case carries `metadata.calibrated_world = true`

## Evidence Matrix

| Deliverable                                         | Machine check                                                                                                            |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `PosteriorResult.truthfulness_tier`                 | Validator checks the field is first-class on the posterior contract                                                      |
| `ForecastingUncertaintyBundle` surface              | Validator checks `prediction_interval`, `fan_chart`, `posterior_predictive_ref`, `coverage_diagnostic`, `horizon_policy` |
| `UncertaintyEnvelope.composition_provenance`        | Validator checks the field exists on the shared envelope                                                                 |
| `MethodAdvisorResult.calibrated_regret_certificate` | Validator checks the advisor result dataclass surface                                                                    |
| HMC/NUTS truthfulness closure                       | Validator checks real catalog entries plus advisor pre-run output                                                        |
| Statistical tolerance budgets                       | Validator checks same-fingerprint, compatible, and composed replay budgets without placeholders                          |
| Default cross-backend equivalence emission          | Validator checks the default dispatcher path with the process-global resolver                                            |
| Validated numerics reachability                     | Validator checks a critical-path method emits a `ValidatedBound` certificate                                             |
| Synthetic world registry                            | Validator checks at least one calibrated world is registered and bound into the benchmark suite                          |
| Synthetic world smoke benchmark                     | Validator checks benchmark JSON coverage, replay, and calibrated-world evidence                                          |

## Reproducible Command

From the `policy-engine` repository root:

```bash
tools/quality/validation/run_foundry_phase0_validation.sh
```

This wrapper runs the curated regression pack, generates the synthetic-world
smoke benchmark JSON, and then evaluates the Foundry Phase 0 closure validator
against that benchmark evidence.
