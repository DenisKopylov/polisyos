# Deep-import baseline stale — candidate adjudication

Date: 2026-08-23
Branch: `codex/deep-import-baseline-stale`
Base: `3c89f008f83f50461d1eb364b502925e2d1b4a13`
Owner lane: runtime/GY
Required approval owner: `team-architecture`

## Authority status

**Authority status: candidate adjudication.**
**Approval receipt: `not_established`.**

This journal records owner evidence and candidate dispositions. It does not constitute
`team-architecture` approval, ratification, or closure of the debt row. The execution
authorization for this branch is not an independent architecture-approval receipt. The
authoritative debt and ledger rows remain unchanged and open.

All paths below are repository-root coordinates. Commands were run from `policy-engine/`;
`git rev-parse --show-prefix` returned `policy-engine/`.

## Adjudication census

| # | Base import and package edge | Why the call site needs it | Supported route and cost | Provenance | Candidate disposition |
|---|---|---|---|---|---|
| 1 | `src/polisyos/runtime/http/services/channel_contracts.py:9`, `ArtifactRef`; `runtime -> core` via `polisyos.core.artifacts.manifest` | Types `RunDetailSnapshot.decision_superseded_by_ref`, preserving the superseding artifact as a strict owner DTO rather than an untyped ID. | `polisyos.core` is supported and lazily exposes `artifacts`; caller-only module-qualified annotation. Pydantic/SSE/generated-schema verification required. | `952a52a4421ed820ad7fc787a55715a48a89c1b6`, 2026-07-17, `fix(runtime): bind projections to owner validation`. | **Stable facade:** `from polisyos.core import artifacts as core_artifacts`. |
| 2 | Same file, base lines 10–12, `DecisionValidityStatus`; `runtime -> core` via `polisyos.core.contracts.decision_validity` | Preserves the owner validity lattice in list/detail SSE contracts. | `polisyos.core` exposes `contracts`; caller-only module-qualified annotation with the same runtime class. | Same deliberate `952a52a4421e...` owner-validation task. | **Stable facade:** `from polisyos.core import contracts as core_contracts`. |
| 3 | `src/polisyos/runtime/http/services/control/lex_pipeline.py:286`, `LegalKnowledgeStore`; `runtime -> lex` via `polisyos.lex.knowledge.store` | Performs read-only fact search, preserves owner-result order and fields, requests no trust-tier filter, excludes candidates, and closes the DuckDB-owning object. | Supported `polisyos.lex.LegalKnowledgeGraph.text_search` delegates to the same store operation; `close()` delegates to its store. Caller change is non-mechanical and must preserve every explicit argument and lifecycle/error behavior. | `a92fcce6eee9f8668c3a58780d1ae26b29818d7d`, 2026-07-17, `feat(runtime): preserve Lex truth through HTTP projection`. | **Stable facade:** `polisyos.lex.LegalKnowledgeGraph`, with explicit `top_k`, `trust_tier=None`, and `include_candidates=False`; `graph.close()` remains in `finally`. |
| 4 | `src/polisyos/runtime/http/services/control/lex_search_projection.py:7`, `ApiMeta`; `runtime -> core` via `polisyos.core.contracts.runtime` | Required metadata type of the strict Lex HTTP response. | Supported Core root exposes `contracts`; caller-only module-qualified annotation. | Same deliberate `a92fcce6eee9...` Lex-truth task. | **Stable facade:** `polisyos.core.contracts` reached through the supported Core root. |
| 5 | Same file, base line 8, `LegalFactResult`; `runtime -> lex` via `polisyos.lex.knowledge.types` | The HTTP item subclasses the complete owner result so authority, grounding, quality, temporal, provenance, and citation fields are not truncated. | `polisyos.lex.knowledge` already exists, exports the same class, and documents it as public; the formal contract alone omitted it. Add only this exact `public_stable` supported entrypoint and regenerate its two projections. | Same deliberate `a92fcce6eee9...` Lex-truth task. | **Stable facade:** `from polisyos.lex.knowledge import LegalFactResult`, plus formal registration of that exact facade. |
| 6 | `src/polisyos/scientist/orchestration/engine/checkpoint.py:31–35`, three ambient scope getters; `scientist -> core` via `polisyos.core.security.tenant_context` | Supplies the single fail-closed checkpoint-scope intake used by hook construction, restore, sync/async production, and resume. | `architecture/policies/cross_cutting_concerns.toml` declares `polisyos.core.security` the canonical cross-component interface under `team-security`, while the public-surface contract does not support it. Narrowing to that real facade is local; promoting the security facade would affect another live edge and belongs to Core/security architecture ownership. | `b66bf3f829bbad1aed8cc5462abeb84388d3c45e`, 2026-08-19, `fix(scientist): close GY-DEF3 checkpoint scope`. | **Intentional baseline acceptance candidate:** `checkpoint -> polisyos.core.security`. This is recorded for `team-architecture`; it is not self-approved. |

No temporary exception is proposed or registered.

## Red-first and semantic receipts

The implementation used one red/green TDD round plus one mutation probe:

1. **Red:** 11 focused tests failed on the untouched imports. The three Edge 3 tests failed
   because the caller constructed a trapped `LegalKnowledgeStore`; six parameterized collector
   cases found the six leaf edges; the Lex projection and checkpoint candidate predicates also
   failed. Receipt: exit 1, 17.13 s; uptime `22:09`, loads `1.99 2.66 2.50` before and
   `2.29 2.68 2.51` after.
2. **Green:** the same 11 tests passed after the minimal facade routes. Receipt: exit 0,
   16.64 s; uptime `22:10`, loads `2.15 2.61 2.49` before and `2.04 2.56 2.47` after.
3. **Remove-the-lifecycle mutation:** removing only Edge 3's inner `finally` left the sentinel
   error propagation intact but failed the test at `close_count == 0`, expected `1`. Restoring
   the `finally` made the same test pass.

Edge 3 success coverage captures the exact call as:

```python
graph.text_search(
    "worker leave",
    top_k=7,
    trust_tier=None,
    include_candidates=False,
)
```

It compares two complete `LegalFactResult` dumps in deliberately non-sorted order. Separate
tests prove the declared known-error degradation, unknown-error propagation, and closure on both
paths. The real DuckDB HTTP projection test remains in the focused verification wave.

## Baseline transaction

The baseline was edited surgically; no `guardrails sync` command was run.

- Starting baseline: 3,650.
- Removed stale rows:
  - `polisyos.runtime.http.execution_policy -> polisyos.core.security.identity`
  - `polisyos.runtime.http.routes.runs -> polisyos.core.artifacts.ids`
  - `polisyos.runtime.http.routes.runs -> polisyos.core.canon`
- Added candidate baseline row:
  - `polisyos.scientist.orchestration.engine.checkpoint -> polisyos.core.security`
- Result: `3,650 - 3 + 1 = 3,648`.

Independent reconciliation receipts:

1. Canonical guardrail AST collector plus canonical baseline loader:
   `current=3648`, `baseline=3648`, zero key difference, rendered bytes exact; 7.85 s.
2. Report-only parser (`lint_imports.parse_imports`) plus direct complete JSON parsing:
   `current=3648`, `baseline=3648`, zero key difference, source/file/target triples exact;
   8.02 s.

Uptime remained `22:13`, loads `2.26 2.45 2.44` before and `2.34 2.46 2.45` after both
checks.

## Public-surface projection

Only `polisyos.lex.knowledge` was added to the existing Lex row's supported entrypoints. The
canonical renderers were executed in memory; no sync writer was invoked. Their complete diffs
were exactly one JSON list item and one Markdown entrypoint token.

| Artifact | Bytes | SHA-256 | Canonical result |
|---|---:|---|---|
| `architecture/public_surface/inventory.json` | 45,674 | `cf771eabc8175094a2e6742d6c5d7c52e668debf557031501f80f4a7ddab926e` | exact |
| `docs/reference/public-surface.md` | 33,208 | `778b19e482434de2d4b97611184816751f9e8ab01c46bc35e6a343c1ae4f0845` | exact |
| `docs/reference/generated-artifacts.md` | 145,494 | `063b86c00d8bedb1055a8692ad6599be24443cbcdc66e9a7f41c4cf8683e36a9` | unchanged and exact |

The exact entrypoint has zero collateral deep-edge exemptions: `.knowledge.store` and
`.knowledge.types` remain internal because the collector matches exact entrypoints, not prefixes.

## Predicate and pattern pass

- `P06` / `P27`: the five leaf dependencies bypassed existing owner facades; they now route
  through those facades without duplicating owner types or persistence logic.
- `P31` / `P05`: Edge 6 preserves the single checkpoint scope intake and its existing negative
  tests; no sibling scope resolver was introduced.
- `P35`: all counts come from complete AST/import and JSON denominators, not sampled search
  output.
- `P37`: the canonical-security declaration and formal-entrypoint omission are recomputed from
  controlled repository contracts; the required `team-architecture` approval is
  `not_established`, so the disposition remains a candidate.
- `P38`: verification asserts the collector's actual edge set and exact baseline bytes, not the
  composite command exit code.
- `P41`: the Phase 3A public-surface snapshot test fails identically at the pinned base. This task
  initially shifted 16 recorded line numbers by two; preserving the original import-line count
  removed that incremental drift. The complete normalized current snapshot is byte-identical to
  the base: 3,575,648 bytes, SHA-256
  `738b8a2bb24614d7fe3fb35cee778768fac1dd2ceeac3adde21ee8d0355086e1`.

## Separate findings kept out of scope

### Import-policy linter

Two independent derivations agree on 90 live policy violations: 84 match expired exceptions and
6 are unregistered. Those six are a different set from this baseline's six edges.
`lint_imports.py` runs from workspace verification, not the release guardrail. No violation or
exception was changed here.

### Expired exception register

Complete denominator: 26 TOML declarations and 26 matching Markdown IDs. All 26 are expired;
oldest 2026-07-01, newest 2026-07-30. Twenty-three declarations match 84 live violations; three
match none. `exceptions.md` still labels all 26 active. Recommended ownership: `team-architecture`
coordinates a bounded registry audit; each recorded package owner decides renewal or retirement.

### Cycle and god-file observations

The registered 16-package runtime import cycle remains observed and untouched:
`calibration`, `core`, `data_forge`, `data_requirement`, `fabric`, `fabric.io`, `foundry`, `ir`,
`lex`, `obligation_rules`, `pdc`, `policy_grammar`, `runtime`, `scholar`, `scientist`, and
`scientist.agent`. The god-file list still starts with
`src/polisyos/runtime/quality/__init__.py` at 79 unique internal target modules.

### GY-N12 coordination

Before this candidate transaction, GY-N12 inherited six new deep-import edges. After it, the
shared state contains one candidate baseline edge. Coordination delta: **six -> one**. N12 must
retain this receipt when replaying its P41 precondition; this branch does not absorb or rewrite
its task evidence.

## Capability-state statement

This task changes import governance rather than claiming a new product capability. Edge 6's
formal Core security public surface remains `surface_missing` pending the owning Core/security
architecture decision; the durable baseline acceptance is a candidate bounded coupling, not a
claim that the surface has been ratified.

## Final verification and review receipts

The full release guardrail was judged by its own architecture predicates, not only by its
process exit code. The declared ceiling was 180 seconds, derived from the 48.30-second first
completed measurement.

- **Before:** exit 1 in 48.30 s. Uptime/load pair: `21:05`, up `3 days, 23:37`, loads
  `4.80 3.46 2.78`; then `21:06`, loads `9.29 4.73 3.28`. Both generated families were fresh;
  the deep-import predicate was red with one current addition and three stale baseline rows.
- **After:** exit 0 in 89.85 s. Uptime/load pair: `22:36`, up `4 days, 1:08`, loads
  `6.37 4.62 4.14`; then `22:38`, up `4 days, 1:09`, loads `5.34 4.82 4.27`. The gate reported
  `runtime-api-client` fresh with five generator-observed outputs,
  `runtime-dashboard-api-types` fresh with one, and `Architecture guardrail check passed`.
  Independent predicate receipts immediately before it established public JSON/Markdown and
  generated-artifact Markdown canonical bytes, plus `3648 = 3648`, additions `0`, stale `0`.

The frozen blast-radius wave passed 38 tests in 49.69 s (uptime/load pair `22:33`, up
`4 days, 1:05`, loads `3.57 4.70 4.09`; then `22:33`, loads `4.48 4.77 4.16`). Targeted Ruff
passes for every owned changed line. The only checkpoint-file Ruff finding, a local-import
`I001` at line 1793, reproduces byte-for-byte on the pinned base and was left untouched.

Rounds consumed: one red/green TDD round, one remove-the-lifecycle mutation probe, and one
parallel read-only review round. Two reviewers completed with no critical findings and converged
on the same Ruff and authority-language cleanup; both were resolved. A third requested review
was a tooling non-receipt because the subagent workspace exhausted its credits, so it is not
counted as a review receipt or an approval. No `team-architecture` approval receipt exists.
