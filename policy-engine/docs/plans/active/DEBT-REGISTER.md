---
title: PolicyOS Debt Register
created: 2026-08-21
revised: 2026-08-21 (Rev 1 - first unified census; 15 of 47 GY debts measured AMBIGUOUS)
owner: architect
status: authoritative
---

# PolicyOS Debt Register

**This file is the single authoritative status surface for every registered debt.**
Where it disagrees with prose in a slice plan, this file wins and the prose is stale.

## Why this file exists

The Atlas master plan's debt table is machine-enumerable: one script read all 22 rows and
classified every one with zero ambiguity. The GY plan's debt prose is not. A census on
2026-08-21 measured **15 of 47 GY debts as `ambiguous`** — not open, not closed, *undecidable*
from the plan text plus git history. Three measured causes:

1. **Document order is not chronological.** `GY-DI1`'s last in-document standing reads
   "registered, never entered"; it was merged and closed. A reader taking the last standing gets
   the wrong answer.
2. **Eleven blocks carry no standing marker at all** — `GY-DEF5`, `DEF10`, `DEF15`, `DEF17`,
   `DEFC-3` … `DEFC-6`, `DEFC-9`, `GAP4` among them.
3. **Both obvious proxies misclassify at their own boundary** (`P38`). A plan-text scan calls an
   item closed when a later entry reopened it; a git verb scan calls `GY-GAP5` closed on the
   strength of the merge that *registered* it.

Two further findings the census produced:

- **`GY-DEF23` and `GY-GAP8` exist only on the unmerged branch `codex/gy-n12-epoch-chronology`.**
  Zero occurrences on `main`. A registration that lives only on a lane branch is not registered.
- **`GY-GAP7` is neither open nor closed** — it was folded into `GY-PA1` as its first cluster.
  The old vocabulary had no word for that, so it read as open forever.

## The rules this register enforces

1. **One row per debt, in this file.** A slice plan may narrate a debt; it may not be the place
   its status is read from.
2. **`status` comes from a closed vocabulary** (below). Anything else is invalid.
3. **A debt whose subject is failing tests must name the test identities**, `path::test_name`,
   with observed vs expected. A count plus "adjacent to X.py" is a rumour: DS7 re-investigated
   two failures DS3 had already registered, and the named file was 60/60 green.
4. **The closure signal must be executable** — a command or predicate someone can run. Ownership
   assigns responsibility for *correctness*, never the *moment of execution*.
5. **`registered_on` names the branch.** `main` unless stated. A debt registered only on a lane
   branch carries `status: open_unmerged` until that branch lands.
6. **Supersessions append.** Never rewrite a recorded standing; add a dated line beneath it.
7. **An unreadable cell is `ambiguous`, never a guess and never a zero.**

## Status vocabulary

| status | meaning |
| --- | --- |
| `open` | registered, not closed, evidence current |
| `open_unmerged` | registered only on a lane branch; not yet on `main` |
| `blocked` | open and not executable; `blocked_by` names what must land first |
| `folded` | absorbed into another item; `folded_into` names the carrier |
| `closed` | closure signal met, with `closed_by` naming the commit |
| `ambiguous` | status not determinable from evidence; **requires re-measurement** |
| `foreign` | owned by a lane outside this programme's scheduling |

## Census provenance

Three independent sources were reconciled; a verdict was recorded only where at least two agree,
and every disagreement or silence became `ambiguous`:

- **A** — last recorded standing in the owning plan's text.
- **B** — targeted per-identifier closing-commit scan of `main` (exact-ID match, not a verb scan).
- **C** — merges the architect performed and verified in session, 2026-08-01 … 2026-08-21.

---

## A. Open and executable now

| id | subject | owner | status | closure signal |
| --- | --- | --- | --- | --- |
| `deep-import-baseline-stale` | six unregistered deep-import creep edges; the required release gate at `core-runtime-release-gate.yml:242` **exits nonzero on `main`** | runtime/GY; approval `team-architecture` | `open` | owner adjudicates each of the six edges — stable facade, intentional baseline acceptance with a recorded reason, or a registered temporary exception — and the plain gate exits zero with generated freshness still clean. **Closing is a governance act, not a `sync`**: `guardrails sync` would silently accept six new creeps |
| `control-plane-fixture-drift` | `DecisionMonitoringContract` rejects fixture fields. **Identities:** `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report` (`400`, expected `200`) and `::test_reissue_endpoint_fails_closed_without_durable_control_plane` (`400`, expected `422 durable_worker_required`). Measured: `test_runs_api.py` 42/44, `test_control_api.py` **60/60 green** | runtime/GY | `open` | both named identities green with no fixture re-baselining |
| `case-record-not-run-bound` | `persist_s2_design_search_run` exists and is exported but has **zero production callers** — 6 call sites, all in one test file; the artifact carries no run/case/tenant binding | runtime/GY (`team-runtime`) | `open` | a production run closure persists a content-bound `DesignRecord` with verifiable run/case/tenant identity, resolvable from a run id without a builder or global index; **DS8-B** is the consumer |
| `adjacent-print-export` | run-detail A4 print regression; the `724×2113` expectation is a bulk-publish placeholder never derived against this surface. **Four states, three measured:** `13,269` neither change · `12,966` DS6 suppression · `12,949` DS7 strangle · **`12,646` both, measured by DS8** | DS8 (repair) / DS6 (verification) | `open` | DS8 adjudicates the mixed panel's paper projection; the composed A4 gate replaces the `P38` full-tree raster; expectation **first-derived, not re-baselined**; two consecutive stable no-update captures |
| `run-lifecycle-terminal-fact` | `GY-GAP4` supplies producer-owned terminality, but `run_terminality` has **zero production consumers** — it occurs only inside generated `src/api/types.ts`. DS7 rendered a *different* fact on a different surface | **re-owned 2026-08-21**; needs a named consumer surface | `open` | `RunSummary.run_terminality` rendered without status/timestamp derivation, unbound lifecycle fact absent rather than false, C22 negatives and DS5 ownership lint green |
| `ds4-waist-decision-grade` | of the three DS4 canonical-waist vocabularies, only `DecisionGrade` is executable (real `Literal` at `pdc/_impl/layer2_readiness.py:39`); `CgfDisposition` is `producer_missing`; `CacheAge` retired as superseded | Group A executor | `open` | `DecisionGrade` swapped to the generated client vocabulary on the next regeneration |
| `atlas-health-metric-replay-pins-uncommitted-paths` | `atlasHealthMetrics.test.ts:649` pins a transient working-tree state as a governed expectation; permanently red on a clean checkout (`P38`) | DS6 | `open` | assert the implementation set directly rather than through revision status |
| `producer-availability-denominator` | DS3 measured 5 available / 7 `invalid_source` / 1 `artifact_missing` from a worktree **without** `production_data` | **needs re-owning — DS7 is closed** | `open` | re-measure on `main` with an appointed data root; see the `GY-N12` appointment precedent |

## B. Open, not executable

| id | subject | owner | status | blocked by |
| --- | --- | --- | --- | --- |
| `GY-PA1` | S8 authority-grade value-schedule production/persistence/resolution chain; `producer_missing`. Carries `GY-GAP7` as its first cluster | runtime/quality | `open` | executable — re-measure before scheduling |
| `GY-GAP2` | confidence ledger has no cross-scope composition; label `contract_missing` | runtime/quality | `blocked` | folded into `GY-N12` Task 12 as its fourth deferred candidate consumer |
| `GY-GAP3` | no controlled release-family transcript owner; `absent/unallocated`, explicitly **not** `contract_only` | GY-N12 lane (primitive) / GY-PA3 (consumer) | `blocked` | blocks `PV-K07` issuance — a ratified statement is not issuable |
| `GY-GAP5` | production recursive-cycle run enumeration `absent/unallocated` | GY lane | `blocked` | renders as typed `not_established` on the Cycle Board |
| `GY-GAP6` | per-row acquisition re-entry / deeper-terminal movement binding | GY lane | `blocked` | `GY-N13b` movement data |
| `GY-DEF22` | frozen N8 record cannot discriminate environment | Foundry (correctness) / GY-N12 (execution) | `open` | executed inside `GY-N12` Cluster 1; **Foundry adjudication receipt owed** before closure |
| `GY-DEF14` | the artifact has not verified in the canonical environment at any point since registration | runtime/quality | `open` | re-measure; standing predates the GY-N12 environment appointment |

## C. Registered only on an unmerged branch

| id | subject | owner | status | note |
| --- | --- | --- | --- | --- |
| `GY-DEF23` | Decision Validity trusts caller-supplied `status` and `dependency_keys` at its authority intake; a shaped event crosses the gate it should not control. `producer_missing` | Scientist Decision Validity | `open_unmerged` | **zero occurrences on `main`**; lives on `codex/gy-n12-epoch-chronology` |
| `GY-GAP8` | Claim Ledger lifecycle bridge implemented in isolation — one definition, **zero source calls** across a 2,561-file AST walk. `implemented_but_not_orchestrated`, explicitly **not** `bridge_missing` | Scientist governance | `open_unmerged` | same branch; closure signal `C5-PREREQ-CLAIM-DV-LIFECYCLE` sequences it after `GY-DEF23` |

## D. Foreign lanes — recorded, not scheduled here

| id | owner | status |
| --- | --- | --- |
| `DS20-B B3 promotion CAS` | GY / fabric lane | `foreign` |
| `DS20-B B5 PostgreSQL linearizability proofs` | cloud verification | `foreign` |
| `DS20-B scorecard producer provenance` | DS9 / ops config | `foreign` |
| `DS20-B Helm policy mirror` | ops / deploy lane | `foreign` |
| `aiohttp Fabric connector cleanup` | GY / fabric lane | `foreign` |
| `worktree-tooling-gap` | ops note | `foreign` |

## E. Folded

| id | folded into | date |
| --- | --- | --- |
| `GY-GAP7` | `GY-PA1`, as its first cluster | 2026-08-20 |

## F. AMBIGUOUS — status not determinable; re-measurement required

These fifteen are the census result, not a backlog. **None may be reported open or closed until
re-measured against its own executable witness.**

`GY-DEF9` · `GY-DEF10` · `GY-DEF13` · `GY-DEF15` · `GY-DEF16` · `GY-DEFC-1` · `GY-DEFC-2` ·
`GY-DEFC-3` · `GY-DEFC-4` · `GY-DEFC-5` · `GY-DEFC-6` · `GY-DEFC-7` · `GY-DEFC-8` · `GY-DEFC-9` ·
`GY-DI4`

Per-item cause: `DEF13` two-axis standing with only one axis recorded; `DEF16` plan claims closure
by `GY-DEFC-9` with no matching closing commit; `DEFC-3` … `DEFC-6` carry no standing marker at
all; `DEFC-9` and `DEF9`/`DEF10`/`DEF15`/`DEFC-1` have a closing commit the plan text does not
confirm; `DI4` is declared closed in prose with no matching commit.

## G. Closed — 22 GY + 8 Atlas

GY: `DEF1` `DEF2` `DEF3` `DEF4` `DEF5` `DEF6` `DEF7` `DEF8` `DEF11` `DEF12` `DEF17` `DEF18`
`DEF19` `DEF20` `DEF21` `DI1` `DI2` `DI3` `GAP1` `GAP4` `PA2` `PA3`

Atlas: quantity-lint · inherited-Vitest · i18n-plural-rule · dashboard-architecture-layer ·
readiness/scientific-depth producer binding · four axe-`incomplete` clusters · plus `GY-DEF20`
and `GY-DEF21` as carried above.

Closed rows are never reopened by a later reading; a regression is a **new** row citing the old one.
