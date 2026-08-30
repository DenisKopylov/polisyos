# Epoch and Decision-Validity Debt Closure Journal

Date: 2026-08-30

Branch: `codex/debt-b-epoch-decision-validity`

Slice base: `784d020148c56e9bfb3a3631909ba11232210a9f`

Plan: `docs/superpowers/plans/2026-08-30-debt-b-epoch-decision-validity.md`

## Entry state

- `git symbolic-ref -q HEAD` -> `refs/heads/codex/debt-b-epoch-decision-validity` (exit `0`).
- `git status -sb` -> attached branch, no tracked or untracked changes before task-created plan/journal (exit `0`).
- `git rev-parse HEAD` -> `784d020148c56e9bfb3a3631909ba11232210a9f` (exit `0`).
- `uv sync --frozen` completed at exit `0`; test extras are invoked explicitly with `uv run --frozen --extra test`.
- Read completely before planning: `CONTRIBUTING.md`, `docs/reference/policy-design-case-failure-patterns.md`, the eight full debt-register rows and five institutional siblings, identity §9 item 5, `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-design.md`, `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-closure-basis.md`, and all `10,727` lines of `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`.

## Baseline receipts

### GY-GAP8 live red

Command:

```bash
uv run --frozen --extra test -m pytest -q tests/repo_quality/test_claim_ledger_export_callers.py::test_all_execution_context_constructors_require_same_claim_owner_port
```

Result: exit `1`; the exact assertion is `118 == 117`.

Measured Git candidate denominator:

```text
5,710 paths = 5,705 .py + 5 .pyi
```

Independent scan composition:

```text
AST ExecutionContext constructions:   118 tests + 0 src + 0 other
token ExecutionContext constructions: 118 tests + 0 src + 0 other
AST minus token:                       0 call sites
token minus AST:                       0 call sites
```

Mapping from Task-4.5 boundary `552213d90599f392ec6c68871e5c5af12a74ed49` by stable `(path, enclosing function)`:

- added: `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only`;
- removed: none;
- current call: line `201`, column `14`;
- introduction: `f715bfdc46c59cfa70e959b99248c9543379192e` (`feat(gy-o0): gate Scientist evaluation attempts`, 2026-08-28);
- purpose: exercise base `ExecutionContext` positional compatibility and keyword-only evaluation-safety fields; it is not a production or claim-producing constructor.

P38 divergence:

- property: every non-test execution-context construction uses the claim-capable owner path;
- proxy: a scalar total of test-only base constructions;
- valid divergence: adding this test preserves the property and breaks `117`;
- unsafe divergence: a base construction in `tools/` or another non-`src/`, non-`tests/` executable partition passes the old `not src` assertion;
- repair: assert the complete base-constructor set equals its `tests/` partition, while retaining exact positive claim-capable constructor paths.

### Implemented/unorchestrated and empty-slot census

- `EpochValidityTransitionProducer` exists and has zero production constructor sites and zero production `.produce_and_persist` calls.
- The one constructor/call pair is a negative-path unit test.
- Production injects `NoEpochTransitionSigningAuthority()` at `src/polisyos/runtime/http/dependencies.py:140` on the slice base.
- `DecisionValidityService` defaults to `NoEpochTransitionVerifier`; positive verifier objects are test fixtures.
- Strict intake, durable pending freeze, completion evidence, Claim bridge, canonical N9 consumer, and offline gate-evidence re-read already exist.
- Therefore the producer row is `implemented_but_not_orchestrated`, while the positive verifier is `producer_missing`; neither is truthfully closed by a fixture.

### Lineage and recompute entry state

- Pre-N9 subject derivation fixes `current_decision_packet_ref=None` and `packet_epoch_refs=()`.
- The N9 resolver rejects the shaped `current` arm as `epoch_validity_prior_binding_unresolved`.
- Decision Validity persists raw lineage head state but exposes no content-bound lookup keyed by the derived pre-N9 lineage digest.
- Epoch staleness projection constructs `EpochDerivedRecomputeView(status="not_established")` for every dependency and always reports the engineering absence.
- `derived_observations` has exact certified derivation production/replay but no epoch-inheritance receipt/resolver.
- `TemporalService.build_epoch_staleness_projection` is refusal-only on the slice base.

### Lex ambiguity

- The tracked repository supports the historical `156,196` owner denominator statement.
- It does not contain a production Lex database or a source/test/tool/architecture artifact from which `152,636` missing `effective_from` rows can be re-derived.
- No plausible reconstruction will be used as a closure signal.

## Command receipts

Append each command once, with exact argv, semantic predicate, exit code, and relevant counts. Do not bundle one exit code across predicates.

## Commit receipts

Before every commit record `git symbolic-ref -q HEAD`, expected old `HEAD`, staged paths, commit ID, tree ID, and post-commit readback.

## Register closure dossier

This section is intentionally completed only after source freeze, targeted verification, independent review, and branch readback. It will contain exactly eight blocks in the register's row order and use append-only supersession prose.
