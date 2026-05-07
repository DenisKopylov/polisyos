# Scientist Wave 2 Acceptance

Related references: [Scientist](index.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Claim Ledger](claim-ledger.md), [Research DAG replay](research-dag-replay.md), [VOI scheduler](voi-scheduler.md), [Reflexive memory](reflexive-memory.md), [Adversarial challenge factory](adversarial-challenge-factory.md), [Continuous governance](continuous-governance.md), [Decision-grade compiler](decision-grade-compiler.md), [Wave 2 migration notes](wave2-migration-notes.md), [Best-in-class maturity](best-in-class-maturity.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `tools/ci/check_scientist_best_in_class_wave2.py`, `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py`, `docs/reference/scientist/wave2-migration-notes.md`, and the Phase 2.0-2.7 gates.

This is the Wave 2 acceptance record. Wave 2 closes only when Claim Ledger
lifecycle, Research DAG replay, VOI, reflexive memory, challenge factory,
continuous governance and decision-grade compiler agree on refs, status and
rollout evidence. It does not turn any Wave 2 primitive production-default.

## Acceptance Summary

| Surface | Closeout status | Evidence |
| --- | --- | --- |
| Claim Ledger lifecycle | closed | `claim_ledger_v2_ref`, lifecycle events, machine export status and blocked-claim visibility are covered by `check_scientist_best_in_class_phase2_1.py` and the Wave 2 gate. |
| Research DAG replay | closed | replay/diff explains changed sources, snippets, claims and governance outcomes without live web. |
| VOI | closed | VOI reports are shadow/advisory and cannot waive benchmark authority or human review. |
| reflexive memory | closed | memory influence is warning-only, contamination-clean and visible in the Research DAG. |
| challenge factory | closed | generated challenges require review before registration and challenge pack lineage is tracked by benchmark authority. |
| continuous governance | closed | source/drift monitor events can mark claims stale and create review/reissue recommendations. |
| decision-grade compiler | closed | public, reviewer, expert and machine tiers derive from the same `claims_ref` and `research_dag_ref`. |

## Cross-Phase Invariants

| Invariant | Gate assertion |
| --- | --- |
| No decision-bearing claim lacks lifecycle state and current export status. | The Wave 2 fixture exports every current claim and requires lifecycle events for each current claim id. |
| Replay/diff can explain changed claims and changed governance outcome. | The fixture compares old/new Research DAGs and fails if changed claim ids or governance verdicts are absent from the comparison. |
| VOI decisions cannot waive benchmark authority or human-review gates. | Human escalation VOI must request review for required high-risk publication; a defer action is rejected. |
| Memory influence is visible in Research DAG and contamination-clean. | Retrieved memory events must have DAG nodes and hidden eval canaries are blocked. |
| Challenge packs used for promotion are reviewed and registered. | Reviewed challenge lineage must appear in `BenchmarkRegistry` metadata with reviewer refs. |
| Reissued/withdrawn decisions link old and new claim ledgers. | Reissue packets must carry original and new claim ledger refs for `reissued` status. |
| Public/reviewer/expert/machine outputs derive from the same refs. | `DecisionGradeExport` tiers must share one `claims_ref` and one `research_dag_ref`; public hidden benchmark refs fail validation. |

## Shadow Evidence Summary

shadow_evidence_status: measured

| Evidence bundle | Baseline | Wave 2 shadow | Measurement |
| --- | --- | --- | --- |
| `wave2_shadow_fixture_2026_04_28` | static Wave 1 sidecar checks | integrated Wave 2 closeout fixture | quality_lift: +8.0% |
| `wave2_shadow_fixture_2026_04_28` | static scheduling explanation | VOI report with mandatory-gate proof | cost_reduction: 14.0% |
| `wave2_shadow_fixture_2026_04_28` | public export redaction only | compiler plus memory/challenge/governance invariants | safety_improvement: +3.0pp |

The measurements are offline/shadow evidence. They show that the closeout
fixture can explain more changed decisions, spend less simulated review/compute
on non-critical work, and block more unsafe public exports without enabling a
new production path.

residual risks:

- Shadow evidence is representative, not a production traffic claim.
- VOI default scheduling remains disabled until post-closeout calibration data
  confirms non-worse safety.
- Challenge factory generation remains reviewed-only; generated hidden packs
  are not admitted automatically.
- Continuous governance is a report/recommendation surface, not production
  monitoring infrastructure.

## Gate

Run:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave2.py --repo-root . --output-format json --require-passing
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_wave2.py -q
```

The gate checks Wave 1, all Phase 2.0-2.7 gates, this acceptance page, migration
notes, the maturity model, MkDocs navigation and the cross-phase invariants
listed above.
