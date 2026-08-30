# Debt A Promotion Gate — Execution Journal

## Standing

- Worktree: `.worktrees/debt-a-promotion-gate`
- Attached branch: `refs/heads/codex/debt-a-promotion-gate`
- Slice base and initial HEAD:
  `784d020148c56e9bfb3a3631909ba11232210a9f`
- Scope denominator: the five rows named in the task brief and implementation
  plan; protected register/ledger/task-plan files remain read-only.
- EFFECT ruling: `_effect_obligation` is excluded byte-for-byte.
- EvalSafety ruling: safety core/hash and attempted-evaluation authority are
  excluded.

## Initial read-through findings

The source walk corrected two premises without turning them into authority:

1. Attempted-evaluation safety is already implemented and orchestrated through
   the control service, generation/Scientist execution contexts, and evaluator
   chokepoints. Its certificate expressly forbids use for promotion. The N9
   positive predicate is therefore not a missing import; it is a distinct
   `producer_missing` authority chain.
2. N5 already emits real unsupported-coupling blockers, but N9 drops the typed
   `SimulationPortObservation` and checks different strings on
   `CandidateSummary.value_blockers`. This is `bridge_missing`, not absence of
   all producer behavior.

The remaining measured classifications before source edits are:

| Predicate | Classification |
| --- | --- |
| admissibility | real CG2 producer/consumer exists; production assembly bridge missing; caller Boolean is redundant |
| effective independence | N9-purpose producer missing |
| coupling | N5 producer exists; N5→N9 bridge missing |
| measurement | measurement-root producer exists; N8→N9 bridge missing |
| promotion-grade EvalSafety | producer missing; attempted-evaluation certificate is denied for promotion |

## Pattern and P40 bucket

Current side of the line: **narrow patch**. The scoped caller-assertion finding
and scoped absent-token finding teach different properties. No additional
spelling of either property has yet been found outside the named rows. If one
appears, stop enumerating and record the triggering source location before
generalising.

Relevant patterns: `P01`, `P02`, `P04`, `P05`, `P07`, `P10`, `P14`, `P17`,
`P29`, `P31`, `P32`, `P33`, `P37`, `P38`, `P40`, `P41`.

## Command ledger

| Stage | Command/predicate | Direct exit | Decisive output |
| --- | --- | ---: | --- |
| branch preflight | `git status -sb && git symbolic-ref -q HEAD && git rev-parse HEAD && git merge-base main HEAD` | 0 | clean attached `codex/debt-a-promotion-gate`; HEAD and merge-base both `784d02014…` |
| environment bind | `uv sync --frozen --extra test` and `uv run python -c 'import sys, pytest; ...'` | 0 / 0 | bound `.venv/bin/python3`; pytest `9.0.2` |
| red DTO predicates | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_current_input_rejects_legacy_caller_gate_predicates' -q --tb=short` | 1 | both `admissibility=True` and `effective_independence=True` failed with `DID NOT RAISE` |
| red context predicates | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_context_cannot_supply_legacy_gate_predicate' -q --tb=short` | 1 | both legacy context keys failed with `DID NOT RAISE` |
| red coupling | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_coupling_without_bound_n5_projection_is_scope_insufficient' -q --tb=short` | 1 | both no blocker and actual `unsupported_coupling_class:feedback` emitted `satisfied`, not `scope_insufficient` |
| red independence | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_effective_independence_missing_is_explicit_decisive_nonreceipt' -q --tb=short` | 1 | no `#effective_independence` decisive row was emitted (`len(rows) == 0`) |
| red receipt epoch/scope | `uv run python -m pytest '...::test_v4_v1_history_is_readable_but_cannot_be_current_authority' '...::test_v1_scope_rows_cannot_be_restamped_as_current_authority' -q --tb=short` | 1 | current receipt remained v4; a self-consistent v1 scope restamp returned no validation issue |
| real admissibility owner control | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_cg2_open_admissibility_obligation_keeps_promotion_red' -q --tb=short` | 0 | a content-bound CG2 certificate with open `admissibility_closed` produced `not_bind_decision`; IDENTIFICATION refused |
| targeted green | pending | pending | pending |
| debt ledger | pending | pending | pending |
| debt ledger preflight | `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` before installing the test extra | 0, non-receipt | checker reported pytest unavailable and degraded runtime findings; this result is not closure evidence |
| docs lifecycle baseline | `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` | 1 | exactly six known findings: two `LEDGER.md` front-matter findings and four stale `frontend/runtime-dashboard` references |

## Decision log

### 2026-08-30 — governed receipt epoch

`n9_obligation_scope.v2` advances current promotion authority to v5. V4/v1 is
retained as history rather than accepted through the current model. Removing
the two Boolean owner fields advances the owner projection to v3 and retains
the exact v2 owner shape for v4 history.

### 2026-08-30 — no marker widening

The coupling consumer will not add `unsupported_coupling_class:feedback` to an
ever-growing string list. Until a typed N5/S5 result is carried and verified,
absence is `scope_insufficient`. The real spelling is a falsifier for the old
proxy, not a fabricated bridge.

### 2026-08-30 — EvalSafety non-transfer

The existing EvalSafety certificate is deliberately non-authoritative for
promotion. Reusing it would violate its `may_not_use_for` envelope and the task
stop rule protecting the safety core. N9 must name a distinct positive producer
if that predicate is retained.

## Commit ledger

| Commit | Boundary | Receipt |
| --- | --- | --- |
| pending | plan/spec/journal | branch preflight above; no source changed |

## Register closure dossier

The final execution commit appends five complete blocks here. Each block will
contain verdict, exact command or predicate, direct exit, decisive output, and
the exact prose the architect can append beneath the protected row.

### `gy-promotion-obligations-scope-insufficient`

- Verdict: pending
- Deciding command/predicate: pending
- Direct exit and decisive output: pending
- Exact append-only register prose: pending

### `gy-n9-caller-asserted-gate-predicates`

- Verdict: pending
- Deciding command/predicate: pending
- Direct exit and decisive output: pending
- Exact append-only register prose: pending

### `gy-n9-coupling-obligation-cannot-fail`

- Verdict: pending
- Deciding command/predicate: pending
- Direct exit and decisive output: pending
- Exact append-only register prose: pending

### `gy-n9-unmet-check-absence-kind-conflated`

- Verdict: pending
- Deciding command/predicate: pending
- Direct exit and decisive output: pending
- Exact append-only register prose: pending

### `GY-O0-NC-01`

- Verdict: `open` (binding task instruction; final basis pending verification)
- Deciding command/predicate: pending
- Direct exit and decisive output: pending
- Exact append-only register prose: pending

### Arithmetic

Pending final verification: `5 = closed + open + blocked + ambiguous`.
