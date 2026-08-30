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
| environment bind | pending | pending | pending |
| red fixtures | pending | pending | pending |
| targeted green | pending | pending | pending |
| debt ledger | pending | pending | pending |
| docs lifecycle | pending | pending | pending |

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
