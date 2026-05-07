# Scientist Wave 2 Runtime Contracts

Related references: [Scientist](index.md), [Best-in-class readiness](best-in-class-readiness.md), [Wave 1 acceptance](best-in-class-wave1-acceptance.md), [Wave 2 acceptance](best-in-class-wave2-acceptance.md), [Wave 2 migration notes](wave2-migration-notes.md), [Best-in-class maturity](best-in-class-maturity.md), [Claims](claims.md), [Claim Ledger](claim-ledger.md), [Research DAG](research-dag.md), [Research DAG replay](research-dag-replay.md), [VOI scheduler](voi-scheduler.md), [Reflexive memory](reflexive-memory.md), [Adversarial challenge factory](adversarial-challenge-factory.md), [Continuous governance](continuous-governance.md), [Decision-grade compiler](decision-grade-compiler.md), [Benchmark authority](benchmark-authority.md), [Human oversight](human-oversight.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `docs/adr/0129-scientist-claim-ledger.md`, `docs/adr/0130-scientist-research-dag.md`, `docs/adr/0131-scientist-readiness-ladder.md`, `docs/adr/0132-scientist-voi-compute-law.md`, `docs/reference/scientist/claim-ledger.md`, `docs/reference/scientist/research-dag-replay.md`, `docs/reference/scientist/voi-scheduler.md`, `docs/reference/scientist/reflexive-memory.md`, `docs/reference/scientist/adversarial-challenge-factory.md`, `docs/reference/scientist/continuous-governance.md`, `docs/reference/scientist/decision-grade-compiler.md`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md`, `tools/ci/check_scientist_best_in_class_phase2_0.py`, `tools/ci/check_scientist_best_in_class_phase2_1.py`, `tools/ci/check_scientist_best_in_class_phase2_2.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py`, `tools/ci/check_scientist_best_in_class_phase2_4.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py`, `tools/ci/check_scientist_best_in_class_phase2_6.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py`, `tools/ci/check_scientist_best_in_class_wave2.py`, `tests/unit/scientist/orchestrator_v2/test_compatibility_contracts.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_0.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_1.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_2.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_3.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_4.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_5.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_6.py`, `tests/repo_quality/tools/test_scientist_best_in_class_phase2_7.py`, and `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py`.

This page is the Phase 2.0 operating contract for Wave 2. It does not implement
new runtime primitives. It freezes package boundaries, artifact names,
deprecation posture, feature-flag defaults and compatibility rules so phases
2.1-2.8 can be implemented without renegotiating the Scientist OS vocabulary.

## Accepted ADRs

| ADR | Status | Runtime boundary |
| --- | --- | --- |
| [0129](../../adr/0129-scientist-claim-ledger.md) | accepted | Claim lifecycle, audit, diff and export live under `src/polisyos/scientist/evidence/claims/**`. |
| [0130](../../adr/0130-scientist-research-dag.md) | accepted | Research-path replay, diff and invalidation live under `src/polisyos/scientist/methods/research_dag/**`. |
| [0131](../../adr/0131-scientist-readiness-ladder.md) | accepted | `DecisionReadinessContract` remains the public readiness ladder. |
| [0132](../../adr/0132-scientist-voi-compute-law.md) | accepted | VOI is a subordinate budget/prioritization control under Scientist search/compute. |

## Package Boundaries

| Package | Owns | Does not own |
| --- | --- | --- |
| `scientist.claims` | claim ids, claim records, claim ledgers, lifecycle sidecars, claim diffs, claim exports, naked-claim validators | source fetching, benchmark hidden splits, reviewer signatures |
| `scientist.research_dag` | typed research nodes/edges, replay, diff, source invalidation projection, public redaction | raw transcripts, raw untrusted web text, checkpoint storage |
| `scientist.evidence` and `scholar.search.models` | safe fetch, source quality, snippet ledger, claim-to-source support links | claim lifecycle transitions, readiness promotion |
| `scientist.evals` | benchmark authority, split taxonomy, leakage/staleness policy, frozen-web eval infrastructure | runtime web search, claim text generation |
| `scientist.evals.challenge_factory` | generated challenge contracts, review-before-hidden admission, sentinel/red-team metadata and rotating challenge lineage | hidden eval self-admission, reusable memory, provider search |
| `scientist.governance.continuous` | decision validity monitor events, source invalidation bridge, reissue packets, incidents, withdrawal records and public/internal validity reports | production monitoring infrastructure, automatic public withdrawal, universal drift thresholds |
| `scientist.governance.human_review` | review packets, queue, review decisions, override/reject/reissue semantics, audit trail | automatic benchmark approval or VOI budget choices |
| `scientist.search` | readiness ladder, benchmark registry, VOI scheduler, advanced search policies | public packet schema removal |
| `scientist.memory` | scoped failure lessons, applicability, contamination guards, warning-only retrieval, consolidation/revocation and memory-to-DAG attribution | public claim evidence, hidden benchmark storage, high-risk default influence |
| `scientist.publisher` and `scientist.orchestrator.decision_card` | Phase 2.7 decision_grade_compiler, audience-specific `DecisionGradeExport`, omission validation, machine `frontend_trust_view` and compiler-backed decision-card trust hooks | frontend UI implementation, hidden benchmark publication, legacy packet field removal |
| `scientist.nodes.builtins.decide` | decision-packet projection and additive sidecar refs | owning claim/research/review lifecycle internals |

## Artifact Versioning Map

Wave 2 artifacts use additive sidecars and dual-read migration. Existing fields
remain readable until a later accepted ADR explicitly removes them.

| Surface | Current field/ref | Wave 2 additive fields | Legacy rendering |
| --- | --- | --- | --- |
| Claim projection | `claims_ref`, `claim_ledger_status` | `claim_ledger_v2_ref`, `claim_ledger_diff_ref`, `claim_export_ref`, `blocked_claim_summary_ref` | `claim_ledger_status = "legacy_missing"` |
| Research path | `research_dag_ref`, `research_dag_status` | `research_dag_replay_ref`, `research_dag_diff_ref`, `research_source_invalidation_ref` | `research_dag_status = "legacy_missing"` |
| Benchmark authority | `benchmark_authority_ref` where present | `benchmark_scope_ref`, `hidden_eval_redaction_ref`, `challenge_pack_rotation_ref` | `not_applicable` for old packets |
| Human review | `human_review_packet_ref`, `human_review_decision_ref`, `human_review` | `review_assignment_ref`, `two_person_review_ref`, `explanation_sufficiency_ref` | `pending` or `legacy_missing` only when required |
| VOI | none required in Wave 1 | `voi_report_ref`, `source_voi_ref`, `human_review_voi_ref`, `compute_budget_decision_ref` | `not_applicable` |
| Reflexive memory | none required in Wave 1 | `memory_retrieval_ref`, `memory_event_ref`, `memory_influence_dag_ref`, `lesson_revocation_ref` | `not_applicable` |
| Challenge factory | none required in Wave 1 | `challenge_factory_report_ref`, `challenge_pack_lineage_ref`, `rotating_challenge_freshness_ref` | `not_applicable` |
| Continuous governance / Reissue | none required in Wave 1 | `continuous_governance_report_ref`, `reissue_packet_ref`, `withdrawal_record_ref`, `incident_report_ref`, `monitor_event_ref` | `not_applicable` |
| Decision-grade compiler | legacy publisher/card payloads | `decision_grade_export_ref`, `public_summary_ref`, `reviewer_packet_ref`, `expert_appendix_ref`, `machine_export_ref`, `frontend_trust_view` | legacy cards load through `DecisionCard.from_packet(...)` |

Schema versions must be monotonic. A proposed artifact schema below its accepted
baseline fails Phase 2.0 compatibility checks.

| Artifact | Baseline schema |
| --- | --- |
| `ClaimLedger` | `1.0` |
| `ResearchDAGArtifact` | `1.0` |
| `AgentCapabilityPromotionReport` | `1.0` |
| `BenchmarkAuthorityVerdict` | `1.0` |
| `HumanReviewPacket` | `1.0` |
| `GovernanceMonitorEvent` | `1.0` |
| `ReissuePacket` | `1.0` |
| `DecisionValidityReport` | `1.0` |
| `DecisionGradeExport` | `1.0` |

## Feature Flag Defaults

No new Wave 2 feature may default to production-on in Phase 2.0.

| Flag | Default posture |
| --- | --- |
| `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2` | off |
| `scientist.best_in_class.wave2.phase2_2.research_dag_replay` | off |
| `scientist.best_in_class.wave2.phase2_3.voi_scheduler` | shadow |
| `scientist.best_in_class.wave2.phase2_4.reflexive_memory` | shadow |
| `scientist.best_in_class.wave2.phase2_5.challenge_factory` | shadow |
| `scientist.best_in_class.wave2.phase2_6.continuous_governance_reissue` | off |
| `scientist.best_in_class.wave2.phase2_7.decision_grade_compiler` | off |
| `scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card` | off |
| `scientist.best_in_class.wave2.phase2_8.wave2_acceptance_gate` | off |

## Compatibility Rules

- Wave 2 changes are additive/deprecated first. Do not remove old decision
  packet fields during Wave 2 implementation.
- Old decision packets without Wave 2 fields must still load through existing
  consumers such as `DecisionCard.from_packet(...)`.
- Old packets without `claims_ref` or `research_dag_ref` render
  `legacy_missing`, not failure, unless a later selected publication workflow
  explicitly opts into fail-closed behavior.
- `DecisionReadinessContract` remains the public readiness ladder.
- Feature flags may start as `off` or `shadow`; no Wave 2 flag may be
  production-on before its phase gate and the Wave 2 closeout gate pass.
- Hidden benchmark refs, private review notes and raw untrusted web text must
  not leak into public decision artifacts.

## API Migration Notes

- Public packet consumers must dual-read legacy fields and new sidecar refs for
  the full Wave 2 rollout period.
- New producers may write `claim_ledger_v2_ref`, `research_dag_replay_ref`,
  `voi_report_ref` and `reissue_packet_ref`, but must keep existing
  `claims_ref`, `claim_ledger_status`, `research_dag_ref`,
  `research_dag_status`, `human_review`, `governance`, `policy_ir`,
  `simulation_results` and `artifacts` fields readable.
- API clients should treat absent Wave 2 refs as `legacy_missing` or
  `not_applicable`; absence alone is not a parsing error for old packets.
- Any proposed ADR or schema migration that removes, renames or deletes a
  legacy public decision-packet field fails the Phase 2.0 compatibility check.
- Production cutover for any Wave 2 flag requires that feature's phase gate and
  the future Wave 2 closeout gate.

## Current Wave 2 Phase Index

| Phase | Status | Gate |
| --- | --- | --- |
| Phase 2.0 - Scientist OS foundation | closed | `tools/ci/check_scientist_best_in_class_phase2_0.py` |
| Phase 2.1 - Claim Ledger | closed | `tools/ci/check_scientist_best_in_class_phase2_1.py` |
| Phase 2.2 - Research DAG replay and comparison | closed | `tools/ci/check_scientist_best_in_class_phase2_2.py` |
| Phase 2.3 - VOI scheduler | closed | `tools/ci/check_scientist_best_in_class_phase2_3.py`; `voi_run_report_ref` sidecars stay additive and shadow-first |
| Phase 2.4 - Reflexive memory and failure intelligence | closed | `tools/ci/check_scientist_best_in_class_phase2_4.py`; memory remains warning-only/shadow with Research DAG attribution |
| Phase 2.5 - Adversarial challenge factory | closed | `tools/ci/check_scientist_best_in_class_phase2_5.py`; challenge generation remains shadow and hidden admission requires review-before-hidden |
| Phase 2.6 - Continuous governance and reissue loop | closed | `tools/ci/check_scientist_best_in_class_phase2_6.py`; continuous governance remains shadow/additive with explicit human-approved withdrawal |
| Phase 2.7 - Decision-grade research compiler | closed | `tools/ci/check_scientist_best_in_class_phase2_7.py`; compiler outputs stay additive/shadow and all tiers share `claims_ref` plus `research_dag_ref` |
| Phase 2.8 - System closeout | closed | `tools/ci/check_scientist_best_in_class_wave2.py`; [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md), [wave2-migration-notes.md](wave2-migration-notes.md) and [best-in-class-maturity.md](best-in-class-maturity.md) close Wave 2 with cross-phase invariants and measured shadow evidence |

## Validation

```bash
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_0.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_1.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_2.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_3.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_4.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_5.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_6.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_7.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_wave2.py --repo-root . --output-format json --require-passing
uv run pytest tests/unit/scientist/orchestrator_v2/test_compatibility_contracts.py tests/repo_quality/tools/test_scientist_best_in_class_phase2_0.py -q
```
