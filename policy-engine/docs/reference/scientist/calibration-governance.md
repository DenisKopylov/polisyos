# Calibration Governance

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/governance/{accountability,backtest_matrix,calibration,calibration_leaderboard,calibration_validation,stress_scenarios}.py` and `tests/unit/scientist/governance/**`

Calibration governance extends the base validation pipeline with observation-family policy mapping, adversarial challenge suites, backtest matrices, stress scenarios, and leaderboard rollups.

## Module Map

| Module                    | Responsibility                                                                                        |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `accountability`          | Unified calibration/fairness/risk artifact with threshold registry and escalation policy              |
| `backtest_matrix`         | Execute standardized backtest suites across multiple runtime surfaces                                 |
| `calibration`             | Main calibration governance runner, family-level pass mapping, adversarial suites, lesson publication |
| `calibration_leaderboard` | Rank calibrated candidates with shared metrics                                                        |
| `calibration_validation`  | Persist and reload validation bundles around calibration runs                                         |
| `stress_scenarios`        | Compare candidate robustness under macro and procurement shocks                                       |

## WS-3B Accountability Surface

Calibration validation now emits a first-class governance accountability
artifact alongside the replay bundle. That artifact keeps the following claims
audit-visible on the default path:

- Brier score, log score, reliability bins, and ENCE
- calibration-by-group and fairness-aware calibration gaps
- equalized odds, intersectional slices, and counterfactual fairness summary
- adaptive threshold selection with fairness-accuracy frontier
- CVaR / tail-risk drift and human-escalation triggers

Reference: [governance-accountability.md](governance-accountability.md)

## Persisted bundle compatibility

`CalibrationValidationBundle` is persisted as `scientist.calibration_validation_bundle`
with `application/json` media type and schema name
`polisyos.scientist.governance.CalibrationValidationBundle`. Historical bundles
without selected JSON profile provenance remain schema `1.0` and load with that
provenance absent (`not_established`); they are not rewritten. Producers that
persist the typed `source_json_snapshot_reads` field emit schema `1.1`. The
fresh reader accepts only schema `1.0` or `1.1` when the manifest schema name
and version match the payload, and a nonempty source profile field is invalid
under payload schema `1.0`.

The S1 `source_json_snapshot_binding_status` is a recomputed lineage-edge
binding result. `available` means each expected source role has exactly one
edge whose artifact ID and selected manifest profile match its typed reader
provenance, and whose selected CAS manifest and bytes still match the recorded
kind, media type, schema, digest, and size. Profile status remains separately visible; `available` does not
establish source authority, producer attestation, currentness, custody, unit,
population coverage, or signoff. Old strict readers may reject `1.1`; they must
not reinterpret it as a `1.0` bundle. No historical artifact migration is
required.

## Backtest Kinds

| Kind              | Semantics                                               |
| ----------------- | ------------------------------------------------------- |
| `MACRO`           | Aggregate macro backtests over system-wide indicators   |
| `CELL`            | Cell-level spatial or sectoral outcome replay           |
| `STRATEGIC_AGENT` | Agent behavior under strategic-response assumptions     |
| `HOUSEHOLD`       | Household distribution and welfare replay               |
| `DISTRESS`        | Distress and failure-signal replay for downside control |

## Stress Scenario Kinds

| Kind                   | Semantics                                                         |
| ---------------------- | ----------------------------------------------------------------- |
| `BUDGET_CONTRACTION`   | Tests resilience when public budget room shrinks                  |
| `PROCUREMENT_SHOCK`    | Tests procurement graph disruptions and supplier stress           |
| `WAGE_SUBSIDY`         | Tests labor-support intervention sensitivity                      |
| `FX`                   | Tests exchange-rate movement against imported-cost channels       |
| `TRADE_DISRUPTION`     | Tests supply and demand dislocation from trade breaks             |
| `REIMBURSEMENT_TARIFF` | Tests tariff / reimbursement rule changes against fiscal exposure |

## D1 Governance Evidence Map

Phase 3 governance claims require an artifact, a decision-surface projection,
and regression evidence. Missing evidence is represented as explicit gaps,
never as inferred calibration quality.

| Claim                                                                    | Artifact surface                                                                                | Regression evidence                                                                                    |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Calibration quality is measured with scoring rules and reliability bins. | `CalibrationValidationBundle.readout_summary()`, `GovernanceAccountabilityArtifact.calibration` | `tests/unit/scientist/governance/test_calibration_validation.py`                                            |
| Fairness and group calibration are auditable.                            | `GovernanceAccountabilityArtifact.fairness`, threshold registry entries, missing-evidence gaps  | `tests/unit/scientist/governance/test_accountability.py`                                                    |
| Risk-weighted verdicts and escalation policy are explainable.            | `risk_weighted_verdict`, `requires_human_review`, `escalation_policy`                           | `tests/unit/scientist/governance/test_accountability.py`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py` |
| Policy output bundles carry calibration governance evidence forward.     | `calibration_validation_summary`, `governance_accountability_artifact_ref`                      | `tests/unit/scientist/nodes/test_build_policy_output_bundle.py`                                             |

## Validation Commands

```bash
uv run pytest tests/unit/scientist/governance/test_accountability.py tests/unit/scientist/governance/test_calibration_validation.py -q
uv run pytest tests/unit/scientist/nodes/test_decision_packet_node_v3.py tests/unit/scientist/nodes/test_build_policy_output_bundle.py -q
```

## API Reference

::: polisyos.scientist.governance.backtest_matrix

::: polisyos.scientist.governance.accountability

::: polisyos.scientist.governance.calibration

::: polisyos.scientist.governance.calibration_leaderboard

::: polisyos.scientist.governance.calibration_validation

::: polisyos.scientist.governance.stress_scenarios

For candidate diagnostics, the C5b and selected Backtest manifests are the
runtime source of truth for the complete source-edge set. Every source edge is
compared as a multiset of role, artifact ID, and selected manifest profile; this
preserves repeated roles and edges named `backtest_report`. The C5b producer adds
one structural `backtest_report` self-edge for the typed nested report reference,
and the fresh reader removes exactly one matching occurrence before comparing
all remaining C5b inputs with every nested Backtest input. The candidate edge
must also equal the C5b payload's `candidate_ref`. Each nonempty selected profile
is resolved through CAS for its paired artifact ID, so matching but nonexistent
digests cannot pass as selected views. The known household roles remain
required, while additional source roles come from the actual manifests. The nested report
reference and its C5b structural edge preserve the same selected report profile. The
Decision Packet carries that selected view when loading the direct report and
compares its complete artifact identity with the nested C5b reference. A same-ID
edge that selects another manifest profile leaves the report readable but makes
source binding unavailable and withholds candidate diagnostics; a historical
edge with no selected profile remains `not_established` and also withholds those
values from direct and nested packet projections. These checks establish lineage
selection only.
