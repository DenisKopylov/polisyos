# Honest Diagnostics Coverage

- Generated at: `2026-05-15T00:00:00Z`
- Invariant registry: `architecture/production_quality/invariant_registry.toml`
- Invariants: 21
- Status: `pass`

## Metrics

| Metric | Value | Numerator | Denominator | Denominator Changed | Wave 0 | Wave 1 | Wave 3 | Wave 4 | Final |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |
| `invariant_registry_complete_pct` | 100 | 21 | 21 | false | >= 10 | 100 | 100 |  | 100 |
| `runtime_emitted_invariant_pct` | 100 | 21 | 21 | false | baseline only | baseline only | >= 85 |  | 100 |
| `negative_control_coverage_pct` | 100 | 21 | 21 | false | >= 25 | >= 60 | 100 |  | 100 |
| `authority_envelope_complete_pct` | 100 | 21 | 21 | false | fixture baseline | 100 for contract tests | >= 90 runtime bundles |  | 100 |
| `payload_identity_verified_gate_pct` | 100 | 21 | 21 | false | baseline only | baseline only | 100 |  | 100 |
| `fallback_ledger_coverage_pct` | 100 | 21 | 21 | false | baseline only | >= 60 known paths | >= 90 known paths |  | 100 |
| `authority_bearing_provenance_pct` | 100 | 21 | 21 | false | baseline only | 100 for fixtures | 100 |  | 100 |
| `source_truth_conflict_gate_pct` | 100 | 21 | 21 | false | baseline only | >= 80 field families | 100 |  | 100 |
| `semantic_binding_gate_pct` | 100 | 21 | 21 | false | baseline only | baseline only | >= 60 |  | 100 |
| `legacy_quarantine_classified_pct` | 100 | 21 | 21 | false | baseline only | >= 90 known bundles | 100 |  | 100 |
| `diagnostic_slo_metric_coverage_pct` | 0 | 0 | 16 | false | baseline only | baseline only | baseline only | 100 | 100 |
| `attestation_observed_material_coverage_pct` | 0 | 0 | 1 | false | baseline only | baseline only | baseline only | 100 | 100 |
| `public_redaction_projection_coverage_pct` | 100 | 21 | 21 | false | baseline only | baseline only | baseline only | 100 | 100 |
| `false_pass_rate_negative_controls` | null | 0 | 0 | false | 0 | 0 | 0 |  | 0 |
| `replay_drift_gate_pct` | null | 0 | 0 | false | baseline only | baseline only | baseline only |  | 100 |
| `operator_ttrc_p50_minutes` | null | 0 | 0 | false | measured | measured | <= 10 |  | <= 5 |
| `operator_ttrc_p90_minutes` | null | 0 | 0 | false | measured | measured | <= 20 |  | <= 10 |
