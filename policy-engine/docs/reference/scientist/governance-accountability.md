# Scientist Governance Accountability

Related reference: [Calibration Governance](calibration-governance.md), [Governance Passes](governance-passes.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/governance/{accountability.py,calibration_validation.py}`, `src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py`, and `tests/unit/scientist/governance/{test_accountability.py,test_calibration_validation.py}`
Evidence pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; source and test paths below were inspected, not run for this documentation update.

`polisyos.scientist.governance.accountability` builds a persisted C5b
accountability artifact from governance verdicts, threshold evaluations, calibration,
fairness, and risk evidence. The artifact carries a local `risk_weighted_verdict`, a
promotion-safety facet, and an escalation recommendation; persisting or displaying those
fields does not itself grant publication authority or impose a universal workflow stop.
Authority effects depend on the consumer that reads the artifact (`P01`, `P02`, `P05`).

## What The Artifact Contains

| Section              | Meaning                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `threshold_registry` | Canonical threshold values, rationale, severity, observed metric, and pass/fail state                                 |
| `calibration`        | Brier score, log score, ECE, ENCE, and reliability-diagram bins                                                       |
| `fairness`           | Equalized-odds gap, demographic parity gap, calibration-by-group, intersectional gap, counterfactual fairness summary |
| `adaptive_threshold` | Deterministic threshold search with fairness-accuracy frontier and selected operating point                           |
| `risk`               | Stress summary, tail exceedance delta, and CVaR / expected-shortfall drift                                            |
| `model_card`         | Compact model-card section for intended use, primary metrics, and limitations                                         |
| `datasheet`          | Dataset name/version, protected axes, data sources, and known coverage limits                                         |
| `escalation_policy`  | Explicit human-review policy, triggers, rationale, and documented rules                                               |

## Default Decision Path

For the promotion-purpose C5b path, `CalibrationValidationRunner` creates the artifact after
backtest, stress, and leaderboard work, persists it to CAS, and attaches its reference and compact
summary to `CalibrationValidationBundle`. The governance-short-circuit path also attaches an
artifact. The separate `candidate_diagnostic` path is explicitly non-promotable and rejects an
attached accountability artifact in its bundle contract.

The bundle then exposes the reference and summary through:

- the persisted `scientist.governance_accountability_artifact` CAS object;
- `CalibrationValidationBundle.readout_summary()` and the decision packet's
  `payload["calibration_validation"]` section;
- `ChampionPolicyDossier.accountability_summary` and the policy artifact bundle.

These are reporting and audit surfaces. The inspected source and tests do not establish a Ukraine
D4 `governance_accountability.json` materializer at this pin (`not_established`); do not infer that
export from the existence of the CAS artifact.

## Threshold Registry

This artifact records the defaults and overrides used in its own calculation. It does not establish
that every governance pass routes every threshold through this registry. Each entry records:

- `threshold_id`
- `metric_id`
- comparator and threshold value
- severity (`info`, `warning`, `blocker`, or `human_gate`)
- source (`default` or `override`)
- rationale explaining why the threshold exists

The entry contract allows severity `info`, `warning`, `blocker`, or `human_gate`.
`_resolve_risk_weighted_verdict` applies a local composition rule: a failed `human_gate`
threshold yields `human_gate`; a failed `blocker` threshold yields `reject`; another failed
threshold yields `needs_revision`; otherwise the governance verdict and promotion eligibility
determine the result. This is the accountability artifact's own verdict calculation, not the
cross-system status lattice (`P04`). The generic governance-pass issue severities are a different
contract and do not map to these threshold severities by name.

Builtin passes such as `confidence` and `equity` may emit their own pass issues; the cited source
does not establish that every pass consumes this accountability artifact or its verdict.

## Escalation Policy

The artifact stores a review recommendation and its local triggers:

- `requires_human_review`
- `escalation_triggers`
- `recommended_action`
- `rationale`
- `documented_rules`

The implementation adds triggers for:

- an input governance verdict of `human_gate`;
- a failed threshold whose severity is `human_gate`;
- failed adversarial results;
- `missing_group_labels` or `missing_probabilistic_outputs` if those gaps are already present when
  the escalation policy is built.

There is an ordering gap in the last rule: `build_governance_accountability_artifact` constructs
the escalation policy before it appends the final `missing_group_labels` and
`missing_probabilistic_outputs` gaps. Consequently those two missing-only conditions do not reach
the trigger checks through this path; the artifact can record the gap without setting
`requires_human_review` from that gap alone. The current test source exercises a failed
human-gate fairness threshold and checks the resulting review recommendation, but contains no
missing-only counterexample (`semantic_test_missing`, `P09`, `P38`).

## Missing Evidence Behavior

The builder does not invent calibration inputs. It records gaps such as:

- `missing_probabilistic_outputs`
- `missing_group_labels`
- `missing_tail_risk_summary`
- `missing_counterfactual_fairness_report`

Those gap fields make missing evidence visible in the artifact. They are not, by themselves, proof
that a promotion consumer stopped or required review; the missing-only review composition above is
not established.

## Verdict Versus Consumer Enforcement

The C5b runner can persist a bundle with status `completed` while the accountability summary says
`human_gate`; its readout exposes both fields. The decision-packet test likewise verifies that a
completed calibration section can display a `human_gate` accountability summary. The output-bundle
test verifies that a dossier surfaces `risk_weighted_verdict: needs_revision` while the node
returns `ok`. Those tests establish artifact creation and projection, not enforcement of the
accountability verdict by those consumers. For that authority effect, a consumer-side gate is
`consumer_missing` and the end-to-end semantic test is `semantic_test_missing` in the inspected
paths (`P01`, `P02`, `P05`).

This does not erase other controls. For example, the separate `GovernanceReport` verdict has
consumers that act on `reject` or `human_gate`; the accountability summary is an additional local
calculation. Do not treat `NodeOutcome(status="ok")`, the bundle's `completed` status, or a
serialized review recommendation as approval.

## Normative Target And Boundary

The ratified target keeps authority fail-closed for protected actions, published claims, and
custody facts while allowing candidate analysis to proceed under a declared unknown (`S0-K03`,
`S0-K04`, `S0-K05`, `S0-K06`, `S0-K07`). External institutions retain their own acts and signatures;
PolicyOS consumes them as typed evidence. Corrections append to history and time roles remain
distinct (`S0-K08`, `S0-K09`, `S0-K12`).

Status composition and warning handling remain local until a consumer explicitly connects them.
The normative completion target is a composed status lattice plus an owned warning lifecycle with
owners, aging, accepted-deficit rules, escalation, and closeout/publication impact. Do not infer
those system-wide properties from this artifact's threshold registry or `escalation_policy`
(`P04`, `P09`). A capability claim still requires its typed artifact, producer, persisted event,
bridge, consumer, verification, declared surface, and a negative or end-to-end semantic test
(`P01`, `P02`, `P03`, `P29`, `P32`).

## Regression Evidence

The following tests were inspected as source evidence; they were not run for this documentation
update:

- `tests/unit/scientist/governance/test_accountability.py`
- `tests/unit/scientist/governance/test_calibration_validation.py`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py`
- `tests/unit/scientist/nodes/test_build_policy_output_bundle.py`

They cover artifact build/persist/readback, runner attachment and readout, and selected packet or
policy-bundle projections. They do not establish the missing-evidence escalation case or
consumer-side enforcement of the accountability verdict.
