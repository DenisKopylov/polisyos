---
title: PolicyOS Debt Register
created: 2026-08-21
revised: 2026-08-21 (Rev 2 - the fifteen AMBIGUOUS debts re-measured against their own executable witnesses; 14 of 15 resolved, GY-DEF9 stays ambiguous on a witness that cannot reach its own discriminator; four broken/blocked witnesses registered as new rows)
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

**Three terms Rev 2 needed and could not find — proposed, not adopted.** Each was forced into an
existing token plus prose; the vocabulary gained `ambiguous`, `folded` and `foreign` this week
precisely because forcing fits loses information.

| proposed | meaning | what forced it |
| --- | --- | --- |
| `closed_by_successor` | the closure signal is met, but by a **named later debt row**, not by this row's own work. `closed_by` would name a debt id rather than a commit | `GY-DEFC-1`'s cold axis (met by `GY-DEFC-6`), `GY-DEFC-8`'s (by `GY-DEFC-9`), `GY-DEFC-7`'s writer axis (by `GY-DEF15`). Recording these as plain `closed` credits the wrong row and hides that the objective travelled; recording them `open` is false |
| `closed_per_axis` | the row is two-axis and its axes differ, with each axis carrying its own status and evidence | The `GY-DEFC` family header declares the split and `GY-DEF6` is the precedent, yet `status` is a single token. Rev 2 had to widen the table to two columns instead. Any single token here re-commits the original error — collapsing two axes so a table stays tidy is how `executed` came to read as `closed` |
| `closed_unreproducible` | the closure signal was met and receipted at a named head, and is **not re-derivable at the current base** because a prerequisite environment or witness is broken — distinct from `ambiguous`, which never had a verdict | `GY-DEFC-9`'s cold axis: `status=pass, issue_count=0` at `69f3fa39a` with receipt `d53184b8…`, while a base `--check` reports drift and `canonical-venv-editable-target-deleted` blocks the canonical re-run. Rev 2 used `closed` plus a new section-A row, which the register's own rule permits — but that rule assumes a *regression*, and an unrunnable verifier is not a regression |

## Census provenance

Three independent sources were reconciled; a verdict was recorded only where at least two agree,
and every disagreement or silence became `ambiguous`:

- **A** — last recorded standing in the owning plan's text.
- **B** — targeted per-identifier closing-commit scan of `main` (exact-ID match, not a verb scan).
- **C** — merges the architect performed and verified in session, 2026-08-01 … 2026-08-21.

**Rev 2 — 2026-08-21, re-measurement of the fifteen `ambiguous` items.** Base `main`
`c270b46c5`, bound as the merge base of a fresh attached worktree on `codex/debt-register-census`;
`main`'s tip was never used. Read-only until the register was written; no GY-plan standing was
edited, no defect was repaired, and line 7 of both plans was not touched. Prose was **not** an
admissible source. The two sources reconciled per item were:

- **B′ — cited-evidence verification.** Every commit, branch and path a block cites was resolved
  against git. **29 unique commits are cited across these blocks and their immediate neighbours;
  all 29 resolve and 28 are ancestors of `c270b46c5`.** The one exception is `ba5946ebc`, which the
  plan itself declares *not* an ancestor — so the blocks' cited evidence checks out, including
  where it claims a negative. Structural claims reproduce
  exactly where they are checkable: `70a3f3d15` = 61 commits / 29 paths; `GY-DI4`'s lane = 15 files
  / 0 under `src/`; `GY-DEFC-4`'s delta = 0 paths under `src/polisyos/data_forge/`; and
  `88210076e` is `21ae2ba65^1`, the docs-only parent the `GY-DEFC-8` block says it is.
- **W — the block's own executable witness, run at `c270b46c5`.** Receipts: `test_gy_waist_contracts.py`
  **54/54** exit `0` (`real 12.29`); `test_value_gate.py` **86/86** exit `0`; the seven `test_n11_*`
  projection identities **11/11** (`real 498.35`); the `GY-DI4` predicate set **12/12** (`real 10.76`);
  the `GY-DEF16` `P29` pair **2/2**; and a full base `check_layer3_gy_confidence_ledger --check`
  that reached `owner_bundle_loaded` and `frozen_contract_derived` before terminating
  `confidence_ledger_contract_drift` (`real 3160.47`, exit `1`).

**Environment appointed, not modified.** The fresh worktree carried neither `production_data` nor a
`.venv`, and 29 of 29 `test_second_domain_pack.py` failures were a single `OwnerDataUnavailableError`.
Both were appointed by **git-ignored symlinks** to the main tree — the `GY-N12` appointment
precedent named in `producer-availability-denominator`. `git status` stayed clean throughout; no
tracked byte moved for measurement. The canonical interpreter is `policy-engine/.venv`; results
taken on the homebrew interpreter were discarded and re-run, since it holds no `polisyos`
distribution at all.

**Non-receipts, recorded as such.** A killed or capped run measures the cap, not the lane
(`GY-DI4`): a 10-minute wrapper kill on the first batch; `test_layer3_gy_confidence_ledger_contract.py`
killed after 77 minutes with no terminal; and `test_real_plugin_postures_verify_n8_n10a_and_depth_n`
`TimeoutExpired` at load ~7 **and** at load ~1.9. Only the last is a finding — a cap that fails
serialized is undersized, not contended. Every bundled gate was judged by its own predicate, never
by a composite exit code.

**One measurement is `not_established` and says so.** `canonical-venv-editable-target-deleted`
means the canonical validators cannot be imported the canonical way, so the `--check` above ran
under a `PYTHONPATH` proxy. Because deployment identity is computed over the **authority import
closure**, that proxy can change the very quantity being compared — the `P38` shape exactly. The
drift it reports is therefore registered as a row to re-measure, never as a verdict.

---

## A. Open and executable now

| id | subject | owner | status | closure signal |
| --- | --- | --- | --- | --- |
| `deep-import-baseline-stale` | six unregistered deep-import creep edges; the required release gate at `core-runtime-release-gate.yml:242` **exits nonzero on `main`** | runtime/GY; approval `team-architecture` | `open` | owner adjudicates each of the six edges — stable facade, intentional baseline acceptance with a recorded reason, or a registered temporary exception — and the plain gate exits zero with generated freshness still clean. **Closing is a governance act, not a `sync`**: `guardrails sync` would silently accept six new creeps |
| `control-plane-fixture-drift` | `DecisionMonitoringContract` rejects fixture fields. **Identities:** `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report` (`400`, expected `200`) and `::test_reissue_endpoint_fails_closed_without_durable_control_plane` (`400`, expected `422 durable_worker_required`). Measured: `test_runs_api.py` 42/44, `test_control_api.py` **60/60 green** | runtime/GY | `open` | both named identities green with no fixture re-baselining |
| `case-record-not-run-bound` | `persist_s2_design_search_run` exists and is exported but has **zero production callers** — 6 call sites, all in one test file; the artifact carries no run/case/tenant binding | runtime/GY (`team-runtime`) | `open` | a production run closure persists a content-bound `DesignRecord` with verifiable run/case/tenant identity, resolvable from a run id without a builder or global index; **DS8-B** is the consumer |
| `adjacent-print-export` | run-detail A4 print regression; the `724×2113` expectation is a bulk-publish placeholder never derived against this surface. **Four states, three measured:** `13,269` neither change · `12,966` DS6 suppression · `12,949` DS7 strangle · **`12,646` both, measured by DS8** | DS8 (repair) / DS6 (verification) | `open` | DS8 adjudicates the mixed panel's paper projection; the composed A4 gate replaces the `P38` full-tree raster; expectation **first-derived, not re-baselined**; two consecutive stable no-update captures  **REPAIR LANDED 2026-08-22 at `69aca1e25`; CLOSURE IS DS6'S.** The composed A4 gate went **red-to-green before any expectation moved** — an initial no-writer run found four printable controls plus a synthetic skip link, both then bound to the existing `[data-print-hidden="true"]` boundary. The legacy `724×2113` PNG stayed **byte-identical until that gate passed**, was retired, and exactly **one** bounded writer derivation produced `run-report-identity-a4-print-chromium-darwin.png` at **746×84**, 19,197 bytes, `26cca8a75e61cfcf…` — a **first derivation under a new name**, not a re-baseline. Two consecutive no-writer captures passed with the snapshot SHA identical before, between and after; PDFs at 5 and 30 pages; maximum box deltas 0.31564 pt wide / 0.03018 pt high, inside 0.5 pt. **The round-2 widening went into the cause, not the gate**: a 2,352 px intrinsic width was fixed by making the shared paper fact shrinkable and breakable rather than by adjusting the crop or a tolerance. **DS6 owns the independent verification and closes this row.** |
| ~~`run-lifecycle-terminal-fact`~~ | `GY-GAP4` supplies producer-owned terminality, but `run_terminality` has **zero production consumers** — it occurs only inside generated `src/api/types.ts`. DS7 rendered a *different* fact on a different surface | **re-owned 2026-08-21**; needs a named consumer surface | `open` | `RunSummary.run_terminality` rendered without status/timestamp derivation, unbound lifecycle fact absent rather than false, C22 negatives and DS5 ownership lint green  **CLOSED 2026-08-22, merged `69aca1e25`** (DS8-A C05). `RunSummary.run_terminality` is rendered at `RunsListPage.tsx:186` by **direct member access** — `exportValue: run.run_terminality` and `render: <Badge kind="neutral">{run.run_terminality}</Badge>` — with no status or timestamp derivation. Architect-verified on the merged tree. The row carried **zero** production consumers from DS7's closure until now; **re-owning it instead of assuming DS7's completion is what made it closeable at all**. |
| `ds4-waist-decision-grade` | of the three DS4 canonical-waist vocabularies, only `DecisionGrade` is executable (real `Literal` at `pdc/_impl/layer2_readiness.py:39`); `CgfDisposition` is `producer_missing`; `CacheAge` retired as superseded | Group A executor | `open` | `DecisionGrade` swapped to the generated client vocabulary on the next regeneration |
| ~~`atlas-health-metric-replay-pins-uncommitted-paths`~~ | `atlasHealthMetrics.test.ts` pinned a transient working-tree state as a governed expectation (`P38`) | DS6 | `closed` | **CLOSED by `da1ff0398`, recomputed 2026-08-22 on clean `0440f0a8d`:** the persisted snapshot asserts the exact ordered six-path `HEALTH_IMPLEMENTATION_PATHS` set directly; replay remains covered by missing-path degradation, clean-versus-absent byte comparison, and inconsistent status/path-set rejection. Fresh focused receipt: 1/1 file, 22/22 tests green. This closes test debt only; the health capability stays `implemented_but_not_orchestrated`, `consumer_missing`, and `surface_missing`. |
| ~~`producer-availability-denominator`~~ | DS3 measured 5 available / 7 `invalid_source` / 1 `artifact_missing` from a worktree **without** `production_data` | **needs re-owning — DS7 is closed** | `open` | re-measure on `main` with an appointed data root; see the `GY-N12` appointment precedent  **RE-TYPED 2026-08-22 — the denominator question is answered and the row is superseded by its own result.** Measured with a control: appointed read-only root gives **10 available / 2 `invalid_source` / 1 `artifact_missing`**; the same `main` without the appointment gives **8 / 4 / 1**. The appointment's contribution is exactly two producers — `n13a-acquisition-census` and `n13a-live-probe-journal` — which were **unmeasurable, not absent**. DS3's `5 / 7 / 1` therefore split into intervening work (5→8) and the appointment (8→10). Superseded by `three-unavailable-governed-producers` below, which carries what actually remains. |
| `three-unavailable-governed-producers` | three of the thirteen governed projections are unavailable **regardless of data appointment**: `generation-cycle-disposition` and `capability-reality` return `invalid_source`, `surface-readiness` returns `artifact_missing`. Architect-verified 2026-08-22 against a control. **None of the three is registered anywhere** — `git grep` returns **zero** mentions of any of them in the GY plan, so they are not covered by `GY-GAP5`, `GY-GAP6` or any existing row | **unassigned — needs an owner determination**; each is a governed-projection source, so the owner follows from which lane owns that source | `open` | each of the three either produces a valid source or is re-typed with a reason; the availability census then reads 13/13 or names its remainder |
| ~~`canonical-venv-editable-target-deleted`~~ | the shared environment `policy-engine/.venv` resolves `policy-engine 0.1.0` through an editable `.pth` pointing at `/Users/deniskopylov/polisyos/.worktrees/gy-gap1-obligation-instance-identity/policy-engine` — a worktree that **no longer exists**. `import polisyos` raises `ModuleNotFoundError` in the canonical interpreter; only `pytest` recovers, via rootdir insertion. Measured 2026-08-21 at `c270b46c5` | runtime/GY (env owner) | `open` | `<venv>/bin/python -c "import polisyos, tools"` exits zero from a checkout that is not the install target, **and** the editable target names a live path. Re-pointing a shared venv is a governance act: it changes which source every other lane's validators import  **CLOSED 2026-08-21 by the architect, same day it was registered.** Cause confirmed: the root checkout's `.venv` carried editable `.pth` files pointing at `.worktrees/gy-gap1-obligation-instance-identity/policy-engine`, a worktree **I moved to Trash while freeing disk space** on 2026-08-20. `import polisyos` raised `ModuleNotFoundError`; only pytest recovered, via rootdir insertion, which is why four lanes measured green against a broken interpreter. Repaired by re-syncing the root venv; the editable target now reads `/Users/deniskopylov/polisyos/policy-engine` and `import polisyos` resolves to `…/policy-engine/src/polisyos/__init__.py`. Tracked tree untouched. **The lesson is not the repair.** Trashing a merged worktree is safe for git and unsafe for every editable install that bound its address — the same subject as `GY-DEF13` one level up. Any future worktree retirement must re-sync the root environment in the same action. |
| `def9-witness-cannot-reach-its-discriminator` | `tests/repo_quality/tools/test_governed_owner_history_independence.py::test_real_governed_owner_bytes_ignore_incompatible_durable_history` — all **5/5** parameterized cases terminate `ConfidenceLedgerError: canonical_loaded_runtime_mismatch` inside `_run_owner`, **before** the fresh-versus-incompatible history byte comparison the witness exists to make. A falsifier that cannot fire | runtime/quality | `open` | the five cases reach their own assertions (`from_repo_calls == []`, fresh/incompatible governed bytes equal) and report pass or fail on **that** predicate, not on a deployment-identity prerequisite. Blocks the re-measurement of `GY-DEF9` |
| ~~`plugin-posture-witness-binds-cap-and-checkout`~~ | `tests/unit/runtime/quality/test_second_domain_pack.py::test_real_plugin_postures_verify_n8_n10a_and_depth_n` hardcodes `REPO_ROOT/.venv/bin/python` and a bare `timeout=240` on its posture subprocess. It cannot run at all in a worktree without its own `.venv`, and it raised `subprocess.TimeoutExpired` on **both** a contended run (load ~7) and a serialized one (load ~1.9) at `c270b46c5` — so the cap is undersized for this host, not merely contended. This is `GY-DI4`'s own rule (a killed run measures the cap, not the lane) violated inside a witness | runtime/quality | `open` | the cap is **declared and measured** per `GY-DI2`/`GY-DI4` rather than literal, the interpreter is resolved rather than path-bound, and the witness returns a completed terminal on this host  **CLOSED 2026-08-22, merged `efb708fd3`** (mechanism `1c9829fb8`). Interpreter resolved via `sys.executable` rather than a hardcoded `.venv` path — `integration` and `gy-def22` proved the old binding unrunnable, and where it runs the two are byte-identical. Cap declared from measurement: two samples, **611.9 s** and **513.0 s**, both exit 0, against a **1,224 s** cap at twice the maximum observed. The literal `240 s` was **2.5× undersized**. Two residuals carried, not hidden: the `timing_budgets.json` lane binding, and an undeclared precondition — the witness asserts an installed `polisyos-foundry-method-example` that is neither a `uv.lock` entry nor a workspace member, so no canonical `uv sync` provides it. |
| ~~`confidence-ledger-check-red-at-base`~~ | `check_layer3_gy_confidence_ledger --check` at `c270b46c5` completed the full milestone sequence through `frozen_contract_derived` / `stage_complete` and then terminated **`confidence_ledger_contract_drift`**, exit `1`, `real 3160.47` s. Frozen `deployment_identity` is `policy-engine-deployment:sha256:53618d6b…db03` (reissued at `f4e4522e4`, after `GY-DEFC-9`'s `f05a816f…5983955f`). Cites `GY-DEFC-9`, whose cold closure was `status=pass, issue_count=0` at `69f3fa39a` — this is a **new row for a later base**, not a reopening | runtime/quality | `open` | **The measurement is `not_established` canonically** and must be repeated first: it ran under a `PYTHONPATH` proxy because `canonical-venv-editable-target-deleted` blocks the real import path, and the authority import closure is exactly what the identity is computed over. Re-run through a live editable install; only then does the drift verdict bind  **RE-TYPED 2026-08-22 — the red is real, not an environment artefact.** Re-run on the repaired canonical environment under a **4,200 s** ceiling declared before launch: **completed in 1,972.41 s, exit 1** — a receipt, not a kill. Reached `frozen_contract_derived → stage_complete → two_pass_worker_complete` and terminated `confidence_ledger_contract_drift`. The canonical environment is also **faster** than the proxy (1,972 s vs 3,160 s), so the `PYTHONPATH` proxy was distorting duration as well as identity. Status moves from `not_established` to a measured red owned by runtime/quality. `--check` does not emit the frozen `deployment_identity`, so the original row's value is **not** re-verified here and must not be cited as though it were. |

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
| `GY-DEFC-3` | `GY-DEFC-4`, which carried its unmet objective and both unspent allowances | 2026-08-21 |

## F. AMBIGUOUS — status not determinable; re-measurement required

**Rev 2, 2026-08-21 — re-measured. 14 of the 15 resolved; one remains.** Each resolved item is
below in section **G** (or **E** for `GY-DEFC-3`) with both of its agreeing sources named. The
method was not re-reading the prose: every block's cited commits and branches were checked against
git, and each block's own executable witness was located and run at `c270b46c5`.

| id | status | why it could not be settled |
| --- | --- | --- |
| `GY-DEF9` | `ambiguous` | Its two sources **disagree**. Source 1 agrees with the standing: the witness commit `3af775d8e` ("test: witness governed owner history independence") is an ancestor of `c270b46c5` and adds the parameterized witness. Source 2 refuses: run at `c270b46c5` on the canonical interpreter, **all 5/5 cases terminate `ConfidenceLedgerError: canonical_loaded_runtime_mismatch`** inside `_run_owner`, *before* the fresh-versus-incompatible governed-byte comparison that is DEF9's actual predicate. A completed failure would be a receipt; this is a failure of a **prerequisite**, so the DEF9 predicate was never evaluated and neither `open` nor `closed` is supportable. Blocking rows: `def9-witness-cannot-reach-its-discriminator` and `canonical-venv-editable-target-deleted` (section A). **Do not read this as a regression** — the standing's own repair (`_for_verification` injection) was not exercised either way |

**What the Rev-1 census's two proxies actually missed**, measured while resolving these — both are
`P38` at their own boundary and both are cheap to fix:

- **Source A (last recorded standing) keys on one marker spelling.** `GY-DEF10`'s standing opens
  **CLOSED at `431bcd798`**, and `GY-DEF13`'s opens **Execution standing (`f015e6631`,
  2026-08-10): `defect_standing = closed`**. Neither begins **STANDING RECORDED**, so both read as
  "no standing marker at all". Five of the fifteen were ambiguous for this reason alone — the
  standings were present and correct.
- **Source B (exact-ID closing-commit scan) misses the repo's own commit idiom.** `GY-DI4`'s four
  closing commits are subjects like `fix(gy-di4): admit a timing sample on completion, not on
  exit_code == 0` — lowercase kebab, not `GY-DI4`. All four are ancestors of `c270b46c5`. The scan
  reported "no matching commit" for an item with four of them.

## H. Closure programme — grouped 2026-08-21

Grouping is by **shared subject**, not by owner convenience. A group exists only where closing the
items together is cheaper or more truthful than closing them apart; everything else stays a
singleton.

### β1 — the measurement layer (new task, first)

`def9-witness-cannot-reach-its-discriminator` · `plugin-posture-witness-binds-cap-and-checkout` ·
`confidence-ledger-check-red-at-base` · (~~`canonical-venv-editable-target-deleted`~~, closed)

One subject: **a gate that cannot fire, or fires on a proxy.** `GY-DEF9`'s witness terminates
before reaching its own discriminator; the plugin-posture witness times out serialized at load 1.9,
undersized rather than contended, breaking `GY-DI4`'s own rule inside a witness four days after
`GY-DI4` closed; the confidence-ledger red measured itself under a `PYTHONPATH` proxy while
identity is computed over the import closure. All four surfaced from one task in one day.

**This group goes first** because every other group's verification depends on witnesses that fire.

### β2 — the authority-intake cluster (new task, after β1)

`control-plane-fixture-drift` · `case-record-not-run-bound` · `GY-DEF23` · `GY-GAP8`

One subject: **an authority boundary that trusts what it is handed, or was never wired at all.**
`DecisionMonitoringContract` rejects fixture fields at the control-plane run paths; `DesignRecord`
has a persistence helper with zero production callers and no run/case/tenant binding; Decision
Validity accepts caller-supplied `status` and `dependency_keys` at its intake; the Claim Ledger
lifecycle bridge has one definition and zero source calls.

`GY-DEF23` and `GY-GAP8` are already sequenced by `GY-N12`'s plan as `C5-PREREQ-CLAIM-DV-LIFECYCLE`
and arrive on `main` with that branch — they are the natural spine of this group, not additions to
it. `case-record-not-run-bound` is the `GY-GAP4` shape one slice later: a producer route that
exists but was never told it owns the binding.

### γ — natural additions to open tasks; **do not schedule separately**

| debt | absorbed by |
| --- | --- |
| `adjacent-print-export` | DS8-A `C08` — its composed A4 gate **is** the repair |
| `run-lifecycle-terminal-fact` | DS8-A `C05` — **reported discharged**, strike on merge |
| `ds4-waist-decision-grade` | the next client regeneration: DS15 or DS17 |
| ~~`atlas-health-metric-replay-pins-uncommitted-paths`~~ | Closed by DS6 test repair `da1ff0398`; fresh clean-tree receipt 22/22 on 2026-08-22. |

### δ — needs an owner before it needs a schedule

`producer-availability-denominator` — DS3 measured it, DS7 was to re-measure, **both are closed**.
It now has a precedent it lacked: the `GY-N12` production-data appointment shows how to measure
producer availability against an appointed read-only root instead of an absent one.

### Singletons — closed alone, on their own evidence

`deep-import-baseline-stale` is **not** an authority-intake defect; it is a governance decision
about six named import edges, and grouping it would blur that. `GY-PA1`, `GY-GAP2`, `GY-GAP3`,
`GY-GAP5`, `GY-GAP6`, `GY-DEF22`, `GY-DEF14` remain blocked or research-bound and are not
scheduled.

## I. Execution record — 2026-08-22, architect

### β1.1 — `def9-witness-cannot-reach-its-discriminator`: **hypothesis disproved, row stays open**

Re-run at `bcd5ae0e9` on a worktree with a correct editable install. **All 5/5 cases still
terminate `canonical_loaded_runtime_mismatch`** inside `_run_owner`. The venv danglement was *not*
the cause. That is a result, not a failure, and it is recorded because a disproved hypothesis is
worth as much as a confirmed one.

Two further mechanism hypotheses of mine were also disproved before I could record them:

- *the editable extension distributions split the import root* — false: this environment carries
  only `_editable_impl_policy_engine.pth`, no extension packages;
- *`PYTHONPATH` loses to the editable install* — false: the traceback shows `confidence_ledger.py`
  loading from the witness's temp checkout, so `PYTHONPATH` wins.

What is established: the witness clones the product tree to a temp checkout, sets `PYTHONPATH` to
it, and launches the worker with `sys.executable`. The mismatch is between `repo_root` (the temp
checkout) and the import-time manifest. **Naming which of those two is wrong is the owner's
repair, not this re-measurement**, and the row is left open with the narrowing recorded.

### β1.2 — `confidence-ledger-check-red-at-base`: **re-typed — the red is real**

Ceiling declared at **4,200 s** from the prior 3,160.47 s measurement before launching, with an
`uptime` pair, on the repaired canonical environment rather than a `PYTHONPATH` proxy.

**Completed in 1,972.41 s, exit 1** — well inside the ceiling, so this is a **receipt**, not a
kill. The run reached `frozen_consumer_projection → frozen_contract_derived → stage_complete →
two_pass_worker_complete` and terminated `confidence_ledger_contract_drift`.

**The drift reproduces canonically.** The row moves from `not_established` to a real, measured red
owned by runtime/quality. Note also that the canonical environment is *faster*: 1,972 s against
the proxy run's 3,160 s, so the proxy was distorting duration as well as identity.

One honest limit: `--check` does not emit the frozen `deployment_identity` in its output, so the
value carried in the original row is **not** re-verified by this run and must not be cited as
though it were.

### β1.3 — `plugin-posture-witness-binds-cap-and-checkout`: **repaired**

Landed at `1c9829fb8`. Red-first: `integration` and `gy-def22` have no `.venv/bin/python`, so the
hardcoded path made the witness unrunnable there; where it runs, `sys.executable` is
byte-identical, so the substitution only widens where it works. **Measured 611.9 s, exit 0** at
load ~6.0 — the literal `240 s` was **2.5× undersized**, which is why it timed out *serialized*
rather than under contention.

**Re-verified under the final cap: exit 0 in 512.99 s.** Two independent samples — 611.9 s and
513.0 s — both passing, maximum observed 611.9 s against a 1,224 s cap. Merged to `main` at
`efb708fd3`.

Two residuals recorded rather than hidden:

- binding the lane into `tools/quality/timing_budgets.json` is the fuller form; that catalog
  enforces `recommended_timeout_ms == 2 × measured_p95_ms` and carries its own validator, which is
  wider than this repair;
- the witness asserts exactly one installed `polisyos-foundry-method-example`, and that
  distribution is **neither a `uv.lock` entry nor a workspace member** — no canonical `uv sync`
  provides it. The witness binds an environment fact instead of establishing it, the same class as
  the interpreter binding.

### β2 — `control-plane-fixture-drift`: **diagnosed, not repaired**

The discriminating input is exact: `IndexedRunRecord.decision_packet_ref` is `None`.

- `services/feedback.py:165` raises `decision_packet_missing` on `run.decision_packet_ref is None`;
- `core/contracts/runtime.py:1912` declares it a plain `ArtifactRef | None = None` — **no
  derivation from run outputs**;
- `tests/_helpers/runtime_http.py:1140` attaches the packet with `run.add_output(...)` and never
  populates the field.

So the fixture supplies the artifact and the contract reads a field nobody sets. **Which side is
wrong is the owner's ruling** — populate the field in the fixture, or derive it from outputs by
kind. Zero production bytes changed; `git diff` shows no path under `src/`.

`case-record-not-run-bound`, `GY-DEF23` and `GY-GAP8` are untouched and sequenced behind
`GY-N12`'s merge.

### γ — all four absorptions **verified**, not asserted

| debt | verification |
| --- | --- |
| `adjacent-print-export` | DS8-A resumed and advanced. On its branch `run-detail-a4-print-chromium-darwin.png` is **retired** and `run-report-identity-a4-print-chromium-darwin.png` added — a first derivation under a **new name**, not a re-baseline of the old one. Absorbed. |
| `run-lifecycle-terminal-fact` | **Verified discharged**: 10 occurrences across four production files, including `RunsListPage.tsx` (3), `validators.ts` (4), `RunReportPage.tsx` (2), `useRunPaper.ts` (1). Strike on DS8-A's merge. |
| `ds4-waist-decision-grade` | **Still open, and an opportunity was missed**: `DecisionGrade` is a real `Literal` at `pdc/_impl/layer2_readiness.py:39` with **zero** occurrences in the generated client, and a regeneration (`40bbafa18`) has since passed without taking the swap. |
| ~~`atlas-health-metric-replay-pins-uncommitted-paths`~~ | The earlier “assertion still live” observation was superseded by `da1ff0398`. Clean-tree readback finds the exact implementation-set assertion, and the focused suite is 22/22 green. |

**A method note worth keeping.** γ.2's first measurement returned *zero* production consumers —
the same result that correctly caught DS7. It was wrong, twice, from my own git path prefixing:
once searching `policy-engine/apps/...` where the tree wanted `apps/...`, then `git show <branch>:<path>`
where the path wanted the `policy-engine/` prefix back. **A zero from a path-shaped query is a
claim about the query until the query is proven**, and `git rev-parse --show-prefix` settles it.

### δ — `producer-availability-denominator`: **measured with a control**

Denominator confirmed as the 13 governed-projection definitions, matching DS3's `5 + 7 + 1`.

| tree | available | `invalid_source` | `artifact_missing` |
| --- | ---: | ---: | ---: |
| DS3, no `production_data` | 5 | 7 | 1 |
| current `main`, **no** appointment (control) | 8 | 4 | 1 |
| current `main`, **appointed** read-only root | **10** | **2** | **1** |

The control isolates the appointment's contribution to **exactly two** producers —
`n13a-acquisition-census` and `n13a-live-probe-journal` — which were **unmeasurable, not absent**.
The rise from 5 to 8 is intervening work; 8 to 10 is the appointment alone.

**Three are genuinely unavailable regardless of data**: `generation-cycle-disposition` and
`capability-reality` (`invalid_source`), and `surface-readiness` (`artifact_missing`). That is the
split the row asked for, and the residual is those three with their real owners — not a
denominator question any more.

## G. Closed

### G.1 Two-axis closures — re-measured 2026-08-21 (Rev 2)

The `GY-DEFC` family header declares the split: *"a source repair may exist on the isolated
successor branch while its governed artifact and cold closeout remain unproved."* `GY-DEF6` is the
precedent — *"closed on the source-defect axis at `e708e8f77`, and closed on that axis only."*
**An item closed on one axis and open on the other is not closed**, so both are reported.
Where an axis was closed by a *successor*, the successor is named rather than the row taking credit.

| id | source-defect axis @ `c270b46c5` | governed-artifact / cold-closeout axis | the two agreeing sources |
| --- | --- | --- | --- |
| `GY-DEF13` | `closed` | `closed` — its blocker is gone | (1) `f015e6631` is an ancestor; the frozen `layer3_gy_value_gate_contract.json` carries `direct_url_sha256: null` with `source_byte_closure: "not_established"` on **both** entry points — the exact smallest correct closure (record the fact, do not gate on the install path). (2) `test_value_gate.py` **86/86 passed**, exit `0`; and DEF13's three named failure codes (`catalog_ambient_discovery_manifest_mismatch`, `catalog_entry_point_distribution_manifest_mismatch`, `catalog_provenance_manifest_mismatch`) occur **zero** times in a full base run that reached `frozen_contract_derived` |
| `GY-DEFC-1` | `closed` — the two class owners landed | `closed` **by `GY-DEFC-6`**, not by this row | (1) `e18861d12` and `8d87624db` are ancestors; the frozen artifact carries `predicate_admission_policy` admitting only `recomputed`/`independently_reconciled` and rejecting `consumer_asserted`/`institutionally_supplied` with `reject_or_quarantine`, `governed_discovery.unbound_inputs: []`, and `runtime_backend_identity`. (2) `test_value_gate.py` 86/86. Its own standing says *"the two class owners landed; the objective did NOT"* — that objective is closed below |
| `GY-DEFC-2` | `closed` | **not applicable — genuinely single-axis** | (1) The instrumentation is in source and matches its "done when" exactly: `_GyOperationalDriftDiagnostic` (`gy_waist.py:526`) carries `admission_arm`, `changed_leaves` (`min_length=1`), `expected_frozen`/`live_replayed` operand identities and `recording_role`, and `safe_detail` is documented and built as an **identity-only** payload — role, leaf and both identities, no raw values. (2) `test_gy_waist_contracts.py` **54/54 passed**, exit `0`, `real 12.29`. It reissued no artifact and consumed no cold allowance, so there is no second axis to report; its required classification (`not_established`, next discriminator named) is delivered inside `GY-DEF13` |
| `GY-DEFC-4` | `closed` for the three members it landed | `closed` for those three artifacts; 4th member carried to `GY-DEFC-5` | (1) `7d02818a0`, `482c204d9`, `d15681e5d`, `ba18ad7d7` are all ancestors, and the delta's decisive negative claim reproduces exactly — **0 paths** under `src/polisyos/data_forge/`. (2) `test_value_gate.py` 86/86 over the predicate it repaired. **This row does not close `GY-DEF14`**, the class it was named for; `GY-DEF14` stays `open` in section B |
| `GY-DEFC-5` | `closed` for the three members it landed | `closed` for those three artifacts; Depth carried to `GY-DEFC-6` | (1) `7a259daa6` is an ancestor and sits on the linear chain `ba18ad7d7 → 7a259daa6 → ca9bc59b0 → 70a3f3d15 → 18f081933 → c270b46c5`. (2) The Depth stop is recorded as a **borrowed-cap non-receipt** (`GY-DI2`, third occurrence), and `GY-DI4` — the row that makes that classification executable — is closed with witnesses green (G.2) |
| `GY-DEFC-6` | `closed` | `closed` — **the objective, independently reproduced** | (1) `ca9bc59b0` is an ancestor; `owner_bundle_loaded` exists as a real milestone (`check_layer3_gy_confidence_ledger.py:219`, reported at `:1267`). (2) **Reproduced at `c270b46c5` by this census**: a base `--check` emitted `owner_bundle_loaded` and continued through `real_ledger_receipt_validated`, `frozen_contract_derived` and `stage_complete`. This is the strongest verdict in the set — the second source is a fresh run, not a document |
| `GY-DEFC-7` | `closed` — it delivered its classification | `closed` **by `GY-DEFC-8`/`GY-DEF15`**; the writer it probed was RED at the time | (1) Its `29`-path branch denominator reproduces exactly: `70a3f3d15^1...70a3f3d15^2` is **29 paths**. (2) Its result is behavioural and now carried by a green witness — the writer defect it left open is `GY-DEF15`, closed at `2789b49ea` with **11/11** witnesses green (G.2). Its truncated "executed, blocker…" standing is resolved: blocker moved, writer red, successor closed it |
| `GY-DEFC-8` | `closed` | `closed` **by `GY-DEFC-9`**, which spent the cold allowance it stopped before | (1) The cited merge shape reproduces **exactly** — `70a3f3d15` is `61` commits and `29` paths, as claimed, on `codex/gy-defc-3-retry` (branch still present); `3f9c817b2`, `2789b49ea` and `5b2c2173b` are all ancestors. (2) `test_gy_waist_contracts.py` 54/54 plus the seven `test_n11_*` witnesses **11/11**. Its own stop is correctly framed by the plan as a `main` condition, which became `GY-DEF16` — also closed below |
| `GY-DEFC-9` | `closed` | `closed` at head `69f3fa39a`, receipt `d53184b8…4eb86` | (1) `0f6c88add → 69f3fa39a → 18f081933 → c270b46c5` is a verified ancestor chain, and the deployment identity it records is confirmed **in the tree at its own merge**: `18f081933` carries `policy-engine-deployment:sha256:f05a816f…`. (2) The typed consumer it shipped is green — `test_n8_transport_gap_consumes_the_typed_governing_subset` and `test_n8_transport_gap_fails_closed_on_a_typed_governing_issue` both **passed**, and `test_value_gate.py` 86/86. **Caveat, and it is a new row not a reopening:** the artifact was reissued after this closure at `f4e4522e4` (identity now `53618d6b…`), and a base `--check` reports `confidence_ledger_contract_drift` — registered as `confidence-ledger-check-red-at-base`, whose own measurement is `not_established` until the canonical import path is restored |

### G.2 Single-axis closures — re-measured 2026-08-21 (Rev 2)

Each of these repairs a comparator, predicate or projection owner and reissues no governed
artifact of its own, so it genuinely has one axis. Stated, per the task's requirement, with why.

| id | status | the two agreeing sources |
| --- | --- | --- |
| `GY-DEF10` | `closed`, `closed_by: 431bcd798` | (1) `431bcd798` is an ancestor, and all four named owners exist in `src/polisyos/pdc/_impl/gy_waist.py` — `strip_gy_volatile_fields` (`:616`), `gy_content_hash` (`:630`), `gy_artifact_self_identity_projection` (`:779`), `reconcile_gy_operational_leaves` (`:816`). The plan's `:176/:190/:200/:219` line numbers have drifted; the identities have not. (2) `test_gy_waist_contracts.py` **54/54 passed**, exit `0`. One axis: it repairs *what equal means* in the shared waist owner and reissues nothing — the plan says so twice, at `GY-DEF15` ("`GY-DEF10` stays closed at `431bcd798`") and at `GY-DEFC-4` ("explicitly not in this batch — it is closed") |
| `GY-DEF15` | `closed`, `closed_by: 2789b49ea` | (1) `2789b49ea` is an ancestor and is contained in `70a3f3d15`. (2) Its **complete** closure signal ran green at base: the seven `test_n11_*` identities in `tests/repo_quality/tools/test_layer3_gy_confidence_ledger_contract.py` — `…null_survives_all_projection_boundaries`, `…construction_and_validation_share_identity_projection`, `…non_null_comparison_identity_remains_diagnosable`, `…explicit_null_comparison_identity_fails_both_intakes`, `…round_trip_preserves_complete_required_null_denominator`, `…absent_required_nullable_member_fails_closed`, `…unknown_or_malformed_representation_stays_governing` — **11/11 passed**, `real 498.35`. Its "cold verification still unspent" is now spent: `GY-DEFC-9` exercised this projection cold |
| `GY-DEF16` | `closed`, `closed_by: 18f081933` | (1) `18f081933` is an ancestor — the Rev-1 census's "no matching closing commit" is refuted — and the amplifier is gone in source: `_n8_transport_gap_closure` (`check_layer3_gy_second_domain_pack.py:6059`) now calls `n8.validate_payload_result(payload)` and branches on `validation.governing_issues`, not on the whole issue set, with no issue-code allowlist. (2) Its `P29` pair — one witness that must stay green, one that must go red — **both passed**: `test_n8_transport_gap_consumes_the_typed_governing_subset` and `test_n8_transport_gap_fails_closed_on_a_typed_governing_issue`. Its third witness is a non-receipt and is registered as `plugin-posture-witness-binds-cap-and-checkout`; the `P29` pair alone satisfies the recorded closure signal |
| `GY-DI4` | `closed`, `closed_by: ee44c5e8d` (lane `15b41f960` · `ee44c5e8d` · `ec1a8f055` · `7e745391f`) | (1) All four commits are ancestors, and the lane's shape reproduces **exactly**: `15b41f960^..7e745391f` is **15 files with 0 under `src/`**, as claimed, so no artifact replay was priced. The closure shape is real and complete — `TIMING_HEALTHY_TERMINAL_EXIT_CODES` is declared in exactly **seven** tool modules, matching "the seven declarations", and read by `tools/lib/timing.py`. (2) The lane's own predicates are green: **12/12 passed**, `real 10.76` — `test_salvaged_corrupt_lane_run_at_exit_one_is_admitted_as_a_sample`, `test_killed_run_stays_inadmissible_even_when_its_exit_code_is_declared_healthy`, `test_non_terminal_records_stay_inadmissible_under_a_maximally_wide_declaration`, `test_every_corrupt_drift_lane_is_classified_and_declares_its_own_healthy_terminal`, `test_lane_summary_counts_a_declared_nonzero_terminal_as_an_admitted_run`, `test_catalog_rejects_an_unknown_predicate_or_regime`. One axis: 0 files under `src/` means there is no governed artifact to verify |

### G.3 Carried closed set

Closed before Rev 2 and not re-measured by this census.

GY: `DEF1` `DEF2` `DEF3` `DEF4` `DEF5` `DEF6` `DEF7` `DEF8` `DEF11` `DEF12` `DEF17` `DEF18`
`DEF19` `DEF20` `DEF21` `DI1` `DI2` `DI3` `GAP1` `GAP4` `PA2` `PA3`

Added by Rev 2, each with two agreeing sources in G.1/G.2 above — GY: `DEF10` `DEF13` `DEF15`
`DEF16` `DEFC-1` `DEFC-2` `DEFC-4` `DEFC-5` `DEFC-6` `DEFC-7` `DEFC-8` `DEFC-9` `DI4`.
`GY-DEFC-3` is `folded` (section E), and `GY-DEF9` remains `ambiguous` (section F).
**GY closed count: 22 → 35**, with one ambiguous and one folded.

Atlas: quantity-lint · inherited-Vitest · i18n-plural-rule · dashboard-architecture-layer ·
readiness/scientific-depth producer binding · four axe-`incomplete` clusters · plus `GY-DEF20`
and `GY-DEF21` as carried above.

Closed rows are never reopened by a later reading; a regression is a **new** row citing the old one.
