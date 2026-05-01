# Scientist Wave 2 Migration Notes

Related references: [Wave 2 acceptance](best-in-class-wave2-acceptance.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Best-in-class maturity](best-in-class-maturity.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `docs/reference/scientist/wave2-runtime-contracts.md`, `tools/ci/check_scientist_best_in_class_wave2.py`, and the Phase 2.0-2.7 reference pages.

Wave 2 migration is additive. Existing decision packets, decision cards and
workflow APIs remain readable. New primitives write sidecars and exports that
can be disabled or ignored by legacy consumers.

## Public Fields And Sidecar Refs

| Primitive | New public/ref fields | Legacy posture | Rollback |
| --- | --- | --- | --- |
| Claim Ledger | `claim_ledger_v2_ref`, `claim_ledger_diff_ref`, `claim_export_ref`, `blocked_claim_summary_ref` | Old `claims_ref` and `claim_ledger_status` remain readable. | Disable `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2`; keep Phase 1.1 `ClaimLedger` reads. |
| Research DAG replay | `research_dag_replay_ref`, `research_dag_diff_ref`, `research_source_invalidation_ref` | Old `research_dag_ref` renders `legacy_minimal` or `legacy_missing`. | Disable `scientist.best_in_class.wave2.phase2_2.replay_plan` and `scientist.best_in_class.wave2.phase2_2.source_invalidation`. |
| VOI | `voi_report_ref`, `source_voi_ref`, `human_review_voi_ref`, `compute_budget_decision_ref` | Absence is `not_applicable`; static scheduling continues. | Disable `scientist.best_in_class.wave2.phase2_3.voi_reports`, `scientist.best_in_class.wave2.phase2_3.voi_scheduler_shadow`, or `scientist.best_in_class.wave2.phase2_3.voi_scheduler_default`. |
| Reflexive memory | `memory_retrieval_ref`, `memory_event_ref`, `memory_influence_dag_ref`, `lesson_revocation_ref` | Memory influence is warning-only and optional. | Disable `scientist.best_in_class.wave2.phase2_4.reflexive_memory`, `scientist.best_in_class.wave2.phase2_4.memory_influence_shadow`, or `scientist.best_in_class.wave2.phase2_4.memory_influence_default`. |
| Challenge factory | `challenge_factory_report_ref`, `challenge_pack_lineage_ref`, `rotating_challenge_freshness_ref` | Generated cases are not benchmark evidence until reviewed and registered. | Disable `scientist.best_in_class.wave2.phase2_5.challenge_factory` or `scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge`. |
| Continuous governance | `continuous_governance_report_ref`, `reissue_packet_ref`, `withdrawal_record_ref`, `incident_report_ref`, `monitor_event_ref` | Shadow validity reports do not mutate public artifacts automatically. | Disable `scientist.best_in_class.wave2.phase2_6.continuous_governance`, `scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow`, or `scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status`. |
| Decision-grade compiler | `decision_grade_export_ref`, `public_summary_ref`, `reviewer_packet_ref`, `expert_appendix_ref`, `machine_export_ref`, `frontend_trust_view` | Legacy packet/card consumers keep loading old fields. | Disable `scientist.best_in_class.wave2.phase2_7.decision_grade_compiler` or `scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card`. |
| Wave 2 closeout | `best_in_class_wave2_status`, `wave2_acceptance_ref` where a workflow elects to publish closeout status | Not required for old runs. | Disable `scientist.best_in_class.wave2.phase2_8.wave2_acceptance_gate`; individual phase gates remain available. |

## Flag Defaults

| Flag | Default after closeout |
| --- | --- |
| `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2` | off |
| `scientist.best_in_class.wave2.phase2_1.require_lifecycle_events` | off |
| `scientist.best_in_class.wave2.phase2_2.replay_plan` | off |
| `scientist.best_in_class.wave2.phase2_2.source_invalidation` | off |
| `scientist.best_in_class.wave2.phase2_3.voi_reports` | shadow |
| `scientist.best_in_class.wave2.phase2_3.voi_scheduler_shadow` | shadow |
| `scientist.best_in_class.wave2.phase2_3.voi_scheduler_default` | off |
| `scientist.best_in_class.wave2.phase2_4.reflexive_memory` | shadow |
| `scientist.best_in_class.wave2.phase2_4.memory_influence_shadow` | shadow |
| `scientist.best_in_class.wave2.phase2_4.memory_influence_default` | off |
| `scientist.best_in_class.wave2.phase2_5.challenge_factory` | shadow |
| `scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge` | off except near-frontier authority checks that opt in. |
| `scientist.best_in_class.wave2.phase2_6.continuous_governance` | shadow |
| `scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow` | off |
| `scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status` | off |
| `scientist.best_in_class.wave2.phase2_7.decision_grade_compiler` | off |
| `scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card` | off |
| `scientist.best_in_class.wave2.phase2_8.wave2_acceptance_gate` | off |

## Consumer Migration Rules

- Dual-read legacy packet fields and new sidecar refs for the full Wave 2
  rollout period.
- Treat missing Wave 2 refs as `legacy_missing` or `not_applicable`, not as a
  parse failure for old artifacts.
- Do not infer production readiness from the presence of a sidecar ref.
- Public exports must not include hidden benchmark, hidden eval, private eval,
  internal monitor, raw transcript, system prompt or developer prompt refs.
- Reviewer and machine exports must preserve blocked/superseded claims with
  omission reasons where an audience cannot see details.
- Rollback removes default use of the primitive, not the ability to read
  already-persisted sidecars.

## Validation

Run:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave2.py --repo-root . --output-format json --require-passing
```

The gate verifies that this page lists every Wave 2 public field/ref and flag,
contains Rollback instructions, and has no open migration markers.
