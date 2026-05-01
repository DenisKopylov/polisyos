# Scientist Best-in-Class Maturity

Related references: [Wave 2 acceptance](best-in-class-wave2-acceptance.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Best-in-class readiness](best-in-class-readiness.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `tools/ci/check_scientist_best_in_class_wave2.py`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, and the source-of-truth pages for each primitive.

This page defines the best-in-class maturity model used after Wave 2 closeout.
It is not a leaderboard. It describes whether Scientist can produce,
explain, review, reissue and safely export decision-grade research artifacts.

## Maturity Levels

| Maturity level | Name | Required behavior |
| --- | --- | --- |
| 0 | Legacy artifact | Decision packets may load, but claim ledger, research DAG and human-review refs can be `legacy_missing`. |
| 1 | Governed sidecars | Claim/evidence/readiness spine, Research DAG, benchmark authority and human review exist as additive sidecars. |
| 2 | Wave 2 shadow | Claim Ledger lifecycle, Research DAG replay, VOI, reflexive memory, challenge factory, continuous governance and decision-grade compiler run read-only or shadow. |
| 3 | Decision-grade default candidate | Outputs derive from the same claim ledger and research DAG, benchmark authority blocks default-enable gaps, and human review is explicit for high-risk paths. |
| 4 | Best-in-class operating posture | Continuous governance can recommend review/reissue, public exports are redacted, reviewer packets preserve blockers, and rollback is feature-flagged per primitive. |

Wave 2 closeout accepts level 2 for the implemented primitives and establishes
the evidence needed to move selected workflows toward level 3. Production
promotion remains per-feature.

## Capability Axes

| Axis | Level 2 expectation | Level 3+ promotion requirement |
| --- | --- | --- |
| claim ledger | Append-only lifecycle, diff, audit and export helpers are available. | New high-risk publication paths require lifecycle events and visible blocked/superseded claims. |
| research DAG | Replay and comparison explain changed sources, changed claims and changed governance. | Replay plans are required for selected reissue workflows. |
| benchmark authority | Hidden, rotating, sentinel and adversarial evidence is mediated by `BenchmarkRegistry`. | Default-enable requests cite fresh, non-stale authority verdicts. |
| human review | Review packets and decisions are CAS-persisted and linked to governance. | High-risk/public-sector release cannot claim reviewed readiness without review refs. |
| VOI | VOI reports explain spend/defer decisions without waiving mandatory gates. | Learned/default VOI needs calibration and regret evidence. |
| reflexive memory | Lessons are warning-only, scoped, revocable and contamination-guarded. | Memory influence must improve held-out recovery while remaining visible in the DAG. |
| challenge factory | Generated challenges require reviewer promotion before benchmark admission. | Near-frontier promotion requires fresh rotating challenge evidence. |
| continuous governance | Validity reports and reissue packets are additive sidecars. | Reissue/withdrawal paths require human-approved governance actions. |
| decision-grade compiler | Public, reviewer, expert and machine tiers share refs and omission rules. | UI/API consumers migrate to machine export after parity and redaction checks. |

## Gate

The maturity model is accepted only when the Wave 2 gate is green:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave2.py --repo-root . --output-format json --require-passing
```
