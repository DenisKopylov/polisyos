# Scientist Decision-Grade Compiler

Related references: [Scientist](index.md), [Claim Ledger](claim-ledger.md), [Research DAG replay](research-dag-replay.md), [Continuous governance](continuous-governance.md), [Human oversight](human-oversight.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `src/polisyos/scientist/publisher.py`, `src/polisyos/scientist/orchestrator/decision_card.py`, `src/polisyos/scientist/claims/export.py`, `tests/scientist/test_decision_grade_compiler.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py`, and `tests/tools/test_scientist_best_in_class_phase2_7.py`.

The Phase 2.7 decision-grade compiler turns governed research artifacts into
audience-specific outputs without losing provenance. Public summary, reviewer
packet, expert appendix and machine export all derive from the same Claim
Ledger and Research DAG refs.

## Runtime Contracts

| Contract | Module | Role |
| --- | --- | --- |
| `OutputAudience` | `publisher.py` | Four output tiers: `public`, `reviewer`, `expert`, `machine`. |
| `OutputOmissionRecord` | `publisher.py` | Required record when a field, blocker or internal detail is intentionally hidden from one audience. |
| `DecisionGradeExport` | `publisher.py` | Versioned export with `claims_ref`, `research_dag_ref`, payload and omissions. |
| `ClaimExportAudience.EXPERT` | `claims/export.py` | Expert claim export mode; blockers and superseded claims remain visible. |
| `TrustProvenanceSummary` | `orchestrator/decision_card.py` | Frontend decision-card hook for claim count, blocked count, Research DAG status and governance status. |

`DecisionGradeExport` validates that every tier carries `trust_provenance`
whose `claims_ref` and `research_dag_ref` match the export-level refs.
Compiler inputs must also agree on `run_id`; if a Research DAG already carries
`claim_ledger_ref`, it must match the compiler `claims_ref`. Legacy/minimal DAGs
with no claim-ledger ref remain loadable.

`persist_decision_grade_export(...)` stores a compiled tier as
`scientist.decision_grade_export` with manifest inputs for `claims` and
`research_dag`; `load_decision_grade_export(...)` reads it back as the typed
`DecisionGradeExport`.

## Output Tiers

| Tier | Audience | Required contents |
| --- | --- | --- |
| public summary | citizen/operator | Approved claims, plain summary, limits, redacted research-path counts and intentional omissions. |
| reviewer packet | human reviewer | Full claim export, blocked claims, evidence and counterevidence counts, reviewer controls and replay summary. |
| expert appendix | analyst/legal/scientist | Claim export, methods, Research DAG replay, assumptions, uncertainty and benchmark authority scope when attached. |
| machine export | UI/API/audit | Claim Ledger export, blocked claim summary, Research DAG replay, sidecar refs and `frontend_trust_view`. |

All tiers are produced by `compile_decision_grade_export(...)` or
`compile_decision_grade_exports(...)`. `assert_decision_grade_exports_consistent(...)`
fails if a set of exports mixes different `claims_ref` or `research_dag_ref`
values.

## Omission Rules

No tier may silently omit blockers. Public summary may hide blocked claim
details, but only with `OutputOmissionRecord` entries such as
`blocked_claim_summary.blocked_claims`. Reviewer, expert and machine tiers must
include blocked claims visibly in the claim export or blocked claim summary.

Public exports reject hidden benchmark, hidden eval, hidden holdout, private
eval, benchmark answer, internal monitor, raw transcript, system prompt and
developer prompt tokens. Public omissions record the reason but never expose a
hidden ref.

## Frontend Trust Fields

Machine export includes `frontend_trust_view` so UI/API/audit consumers can
render a Trust View without parsing legacy report prose:

- `claims_ref`;
- `research_dag_ref`;
- `claim_count`;
- `blocked_claim_count`;
- `approved_claim_ids`;
- `blocked_claim_ids`;
- `research_step_count`;
- `research_replay_status`;
- `continuous_governance_status`.

`DecisionCard.from_decision_grade_export(...)` converts the same machine export
into a compact `DecisionCard` with `TrustProvenanceSummary`. Legacy
`DecisionCard.from_packet(...)` remains loadable and only uses the compiler
when an explicit `decision_grade_export` field is present.

## Additive Migration

The compiler is additive. It does not remove old decision packet fields,
rewrite legacy reports, or require frontend consumers to switch immediately.
During rollout, producers may emit compiler exports alongside existing decision
packets and cards.

## Feature Flags

```text
scientist.best_in_class.wave2.phase2_7.decision_grade_compiler
scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card
```

Default rollout is off/shadow. Compiler-backed cards can be enabled only after
the machine export has parity and public redaction tests remain green.

## Validation

```bash
uv run pytest tests/scientist/test_decision_grade_compiler.py -q
uv run pytest tests/tools/test_scientist_best_in_class_phase2_7.py -q
uv run python tools/ci/check_scientist_best_in_class_phase2_7.py --repo-root . --output-format json --require-passing
```
