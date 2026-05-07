# Human Oversight

Related references: [Scientist](index.md), [Claims](claims.md), [Governance accountability](governance-accountability.md), [Benchmark authority](benchmark-authority.md).

Owner: `@scientist-owners`
Backup owner: `@governance-owners`
Source of truth: `src/polisyos/scientist/governance/human_review/**`, `src/polisyos/scientist/governance/report.py`, `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`, and `tests/unit/scientist/governance/human_review/**`

Phase 1.6 makes human oversight an operational control plane. Review packets,
assignments, decisions and release-status summaries are typed runtime objects
that can be persisted in CAS and referenced from governance and decision
artifacts.

## Artifacts

| Artifact | Kind | Purpose |
| --- | --- | --- |
| `HumanReviewPacket` | `scientist.governance.human_review_packet` | Reviewable release packet with decision summary, claim ledger summary, evidence, counterevidence, uncertainty, calibration, source freshness, legal/fairness/privacy issues, blocked claims, unresolved assumptions, controls, audit trail and signatures. |
| `HumanReviewDecision` | `scientist.governance.human_review_decision` | Reviewer decision: approve, reject, request re-run, override, mark explanation insufficient or interrupt release. |
| `HumanReviewQueueState` | `scientist.governance.human_review_queue` | Queue snapshot with packet refs, assignments, status and decision refs. |

## Release Semantics

Reviewer actions are explicit:

- `approve`;
- `reject`;
- `request_rerun`;
- `override`;
- `explanation_insufficient`;
- `interrupt_release`.

`human_review_status(...)` aggregates decisions fail-closed. Reject, interrupt,
re-run and explanation-insufficient decisions block release. Approval requires
the configured reviewer count and distinct reviewer ids for two-person
verification. Override is allowed only with an override reason and remains
auditable as `overridden`, not plain approval.

## Public-Sector And Rights Review

`FundamentalRightsChecklist` records whether a release is public-sector,
fundamental-rights impacting, automated decision support, or affects vulnerable
groups. It also records whether legal basis, privacy, fairness, override and
explanation posture have been considered.

High-risk public-sector paths can require:

- human review before publication;
- two-person verification;
- stop, override, reissue, re-run and explanation controls;
- explicit reviewer signatures.

## Governance And Decision Packets

`GovernanceReportLinks` now includes:

- `human_review_packet_ref`;
- `human_review_decision_ref`.

Decision packets include a `human_review` section with required status, risk
tier, required reviewer count, reasons and refs. Publication validation blocks a
packet that claims `human_reviewed` readiness without a review packet or review
decision ref.

Feature flag:

```text
scientist.best_in_class.wave1.phase1_6.require_human_review_for_publication
```

Compatible param:

```text
require_human_review_for_publication=true
```

## Validation

```bash
uv run pytest tests/unit/scientist/governance/human_review -q
uv run pytest tests/unit/scientist/nodes/test_decision_packet_node_v3.py tests/unit/scientist/nodes/test_run_governance_normative.py -q
```
