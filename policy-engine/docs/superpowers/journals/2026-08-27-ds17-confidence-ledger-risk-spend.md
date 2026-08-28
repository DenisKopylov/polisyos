# DS17 confidence-ledger risk-spend — C00 execution journal

## Admission identity and scope

- Attached execution branch: `codex/ds17-confidence-ledger-risk-spend-execution`.
- Exact execution base: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` (`main`).
- Product coordinate: `git rev-parse --show-prefix` returned `policy-engine/`.
- Required ancestors were re-read before the C00 writes: DS7 `74f26ca2d` ->
  exit `0`; N11 `f41d49071` -> exit `0`; DS11 merge
  `4ff11db52` -> exit `0`.
- C00 mechanism paths: **0/0**. The carried plan, this journal, and the three
  backend red-test companions are the only P39 companions. No production,
  generated, dashboard, Atlas/debt/LEDGER, deep-import, release, or other-slice
  path was written.
- Pattern pass before C00: P01/P02/P03 keep the actual N11 chain distinct from
  its missing DS17 surface; P04/P05/P09/P10/P15 require tagged, fail-closed
  future reasons; P29/P31/P32/P33 make these marker-constant and
  witness/admission reds semantic rather than form checks; P35/P37/P38 require
  complete denominators and the real gate predicate; P39 excludes the mandated
  companions; P41 attributes all observed reds to absent DS17 behavior, not
  inherited failures. The DS17 capability remains `absent/unallocated` at C00:
  a plan and red tests do not create a producer, artifact, bridge, consumer, or
  surface.

## DS11 landed-state receipt

The DS11 merge `4ff11db52` is an ancestor of the exact execution base. Both
required contribution walks against that base agree at **65/65**:

```text
git diff --name-only 4ff11db52^1 4ff11db52 | wc -l                         65
git diff --name-only $(git merge-base 4ff11db52^1 4ff11db52^2) 4ff11db52 | wc -l 65
```

This no-writer command completed exit `0`, `real 0.28`, `user 0.02`, `sys
0.05`, at uptime `20:28` -> `20:28`. Its operational-only ceiling is `30s`
(`2 × (0.02 + 0.05) < 30`). There is no disagreement to normalize.

## N11 census and inventory re-derivations

The N11 output census is pinned to `f41d49071`; the registry and persisted
artifact are read from the exact execution-base tree. Both the execution branch
and the clean exact-base `main` worktree report the same counts.

| complete denominator | independent derivations | execution branch | exact-base `main` |
| --- | --- | ---: | ---: |
| N11 projection declarations / public producers | AST class-declaration walk / AST `project_*` function walk over `src/polisyos/runtime/quality/confidence_ledger.py` at `f41d49071` | 3 / 3 | 3 / 3 |
| sole registry TOML | `tomllib` structural parse / whole-file `awk` section-and-role scan | 2 profiles, 7 pools, 5 proof profiles, 13 instruments, 6 routes; roles `1/5/11/1/6` (acquisition/admission/promotion/promotion-conformance/refusal) | same |
| sole persisted N11 JSON | Python `json` structural parse / `jq` complete checks-and-N9 walk | 3 checks = 1 refusal + 2 acquisition; 0 promotion rows | same |

The projection names are
`ConfidenceLedgerSemanticReceiptProjection`,
`N9PromotionCertificateProjection`, and `N12EpochReferenceProjection`; their
producer functions are `project_confidence_ledger_semantic_receipt`,
`project_n9_promotion_certificate`, and `project_n12_epoch_reference`.

The AST projection census completed exit `0`, `real 0.16`, `user 0.10`, `sys
0.03`, uptime `20:34` -> `20:34`; its ceiling is `30s`. The successful `awk`
inventory walk completed exit `0`, `real 0.00`, `user 0.00`, `sys 0.00`, uptime
`20:35` -> `20:35`; the `jq` persisted-instance walk completed exit `0`, `real
0.02`, `user 0.01`, `sys 0.00`, at the same uptime pair. Their ceilings are
`30s`. An initial inventory scanner used `index` as an awk loop variable and
therefore emitted a syntax error; its trailing `jq` succeeded, so it is a
tooling non-receipt and is excluded from these receipts. The corrected scanner
above is the accepted independent walk.

## C00 red witnesses

Collection succeeds for exactly the nine named red tests on the execution
branch: 3 coverage, 5 ledger-surface, and 1 HTTP. The exact-base `main`
worktree has **0/9** named tests (all three C00 companion files are absent).
The collection command completed exit `0`, `real 46.94`, `user 43.89`, `sys
1.82`, uptime `20:37` -> `20:37`; its operational-only ceiling is `91.42s`.

```text
tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py: 1
tests/unit/runtime/quality/test_confidence_ledger_surface.py: 5
tests/unit/runtime/quality/test_obligation_coverage.py: 3
```

The combined red command was:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_obligation_coverage.py \
  tests/unit/runtime/quality/test_confidence_ledger_surface.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py -q
```

The final pre-commit run completed exit `1`, `9 failed`, `real 48.44`, `user
44.92`, `sys 2.20`, uptime `20:39` -> `20:40`; its operational-only no-writer
ceiling is `94.24s`. (The original equivalent RED run was also exit `1`, 9
failed, `user 45.05`, `sys 2.10`; no RED became green.)
All coverage and ledger-surface tests fail through their in-test dynamic module
checks, not during collection/import setup: C01 lacks
`polisyos.runtime.quality.obligation_coverage` and
`polisyos.runtime.quality.confidence_ledger_surface`. Their messages name the
specific missing semantic mutation each future implementation must catch.

The HTTP test reaches the real current router and fails its desired `200` typed
review-operation assertion with current **HTTP 422**, not a tooling error.
After self-review it additionally binds the required static-before-dynamic
ordering, `RUNS_REVIEW`, tenant-collection resource binding, analyst admission,
and viewer `403` denial. Its final one-test run remains an intended `422` RED:
exit `1`, `real 46.67`, `user 44.31`, `sys 2.25`, uptime `20:42` -> `20:43`,
with a `93.12s` operational-only ceiling.

A complete AST walk over all test Python files finds exactly the nine named
functions in the execution tree's 2,460-file denominator and none in the clean
exact-base main tree's 2,457-file denominator. The three-file denominator delta
is exactly the three C00 test companions. Ruff over those three files completed
exit `0` (`All checks passed!`), `real 1.00`, `user 0.05`, `sys 0.03`, uptime
`20:38` -> `20:38`; its operational-only ceiling is `30s`.

### Ruling — current-main 404 -> 422 route drift

The C00 brief described a missing-operation `404`; exact current main instead
has the generic dynamic route
`GET /api/v1/exports/governed-projections/{projection_id}`. It parses the DS17
slug as the existing `ProjectionId` enum and rejects it with `422` before a
static DS17 operation exists. C00 therefore preserves the semantic red: it
requires `200` from the desired static typed/review-protected operation and
truthfully records the observed dynamic-route `422`.

Cost if wrong: treating this as a manufactured `404` would hide the actual
static-before-dynamic shadowing requirement and could let a future operation
fall through to an unreviewed generic handler; treating the dynamic `422` as
the desired route would falsely declare a typed protected operation present.
No production route, enum, or test environment was altered.

## C00 continuation

The red-test implementation has no production behavior to turn green in this
cluster. C01 owns the two derived-negative domain modules; C02 owns the
protected static HTTP bridge. Reopen the failure/repair register before C06.
