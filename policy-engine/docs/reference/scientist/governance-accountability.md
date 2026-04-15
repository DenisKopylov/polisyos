# Scientist Governance Accountability
Related reference: [Calibration Governance](calibration-governance.md), [Governance Passes](governance-passes.md).

`polisyos.scientist.governance.accountability` is the WS-3B audit surface that
turns calibration, fairness, threshold policy, and escalation logic into one
persisted artifact instead of leaving those claims scattered across pass notes
or notebook-only analysis.

## What The Artifact Contains

| Section | Meaning |
|------|---------|
| `threshold_registry` | Canonical threshold values, rationale, severity, observed metric, and pass/fail state |
| `calibration` | Brier score, log score, ECE, ENCE, and reliability-diagram bins |
| `fairness` | Equalized-odds gap, demographic parity gap, calibration-by-group, intersectional gap, counterfactual fairness summary |
| `adaptive_threshold` | Deterministic threshold search with fairness-accuracy frontier and selected operating point |
| `risk` | Stress summary, tail exceedance delta, and CVaR / expected-shortfall drift |
| `model_card` | Compact model-card section for intended use, primary metrics, and limitations |
| `datasheet` | Dataset name/version, protected axes, data sources, and known coverage limits |
| `escalation_policy` | Explicit human-review policy, triggers, rationale, and documented rules |

## Default Decision Path

The accountability artifact is created during calibration validation and then
surfaced in three operator-facing places:

- the persisted `scientist.governance_accountability_artifact` CAS object;
- `CalibrationValidationBundle.readout_summary()` and the decision packet's
  `payload["calibration_validation"]` section;
- `ChampionPolicyDossier.accountability_summary` and the policy artifact bundle.

On the Ukraine D4 path the artifact is also materialized as
`governance_accountability.json` so external auditors do not need to dereference
CAS manually.

## Threshold Registry

Thresholds are no longer hidden magic numbers inside individual passes. Each
entry records:

- `threshold_id`
- `metric_id`
- comparator and threshold value
- severity (`info`, `warning`, `blocker`, or `human_gate`)
- source (`default` or `override`)
- rationale explaining why the threshold exists

Builtin governance passes such as `confidence`, `equity`, and `escalation` now
resolve their defaults through this shared registry.

## Escalation Policy

Probabilistic verdicts are required to explain when they fall back to human
review. The artifact therefore stores:

- `requires_human_review`
- `escalation_triggers`
- `recommended_action`
- `rationale`
- `documented_rules`

Current default rules escalate when:

- governance already returns `human_gate`;
- fairness-sensitive human-gate thresholds fail;
- adversarial governance checks fail;
- the evidence surface is too incomplete for externally auditable probabilistic claims.

## Missing Evidence Behavior

WS-3B intentionally does not invent calibration inputs. If a runtime path has
dataset provenance and group metadata but does not yet expose calibrated
probability vectors, the artifact records explicit gaps such as:

- `missing_probabilistic_outputs`
- `missing_group_labels`
- `missing_tail_risk_summary`
- `missing_counterfactual_fairness_report`

That makes degraded accountability visible without silently publishing
statistically unsupported calibration claims.

## Regression Evidence

Primary regression coverage lives in:

- `tests/scientist/governance/test_accountability.py`
- `tests/scientist/governance/test_calibration_validation.py`
- `tests/scientist/test_decision_packet_node_v3.py`
- `tests/scientist/nodes/test_build_policy_output_bundle.py`
- `tests/ukraine_data/test_builders.py`
