# E02 work plan: visible development, composition and branch retirement

**Status:** execution resumed by the user on 30 October 2026. Product composition, regression checks and safe retirement of reviewed branches are authorized. Work remains local; no cloud tasks. The user additionally authorized moving disposable materials to Trash while preserving code, documentation and unique production data; never permanently delete files or empty Trash.

**Goal:** integrate useful existing work into tested product behavior in `origin/main`, remove obsolete branches, and replace hidden development and repetitive paperwork with one visible work cycle.

**Baseline:** published `0741080cfc026077483f551333f853203b33d52d`, tree `6c8f6c87e77ac7ed4299105ede9fb42ac99eceee`. Its product source is unchanged from `87cd7f41303d0df4e962ef510badd733fdab4f9b`. The 233-parent `ours` merge preserved history, not alternative implementations. Do not repeat archival-only merges as product composition or use `git branch --merged` as evidence of incorporation.

## 1. Chosen working model

Use the existing `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos` checkout on `codex/e02-unified-local-20261009`; publish ready product changes to `origin/main`. The older local `main` is occupied by `8dda`. Reattach the app/review view to the canonical workspace first. Fast-forward an idle clean local-main worktree later, after checking untracked collisions; do not move its occupied ref behind its back. Do not develop in the primary or G checkout.

This is the **only current execution plan/status document**. Original [TASKS](policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json) and [criterion coverage](policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json) remain the requirements. Historical plans stay as references. Edit current status here in place; Git supplies history. No dated progress copies, plan per helper or replacement C/R-number backlog.

| Area | Rule |
| --- | --- |
| Source | Owners edit real `src`, mirrored `tests`, tools and required companions. New useful code must never exist only in RAW, copied postimages, archives or chat. Preserve/recover existing material before retiring its storage. |
| Git | The coordinator alone owns the canonical index, commits, merges and publication. It stages only the released owner's explicit paths, inspects the staged diff and hook changes, and never stages another owner's unfinished work. |
| Parallelism | Start four persistent domain authors, a branch curator and an independent reviewer when work is ready. Expand for genuinely disjoint work; do not manufacture work to fill the 100-agent ceiling. |
| Shared source | One writer per mechanism and overlapping companions. Hold the affected dependency/readset stable through verification and binding to the committed candidate. Other disjoint owners continue. Use visible worktree isolation when this cannot be guaranteed. |
| Isolation | Reuse the existing checkout/environment by default. A few ordinary visible worktrees are an exception for real isolation, not a full source/dependency/data copy per assistant. |
| Preservation | Commit useful coherent work before stopping. Unfinished selected work belongs in an owned visible Git branch, not a stash or hidden proposal queue. |
| Main | Integrate a coherent checked/reviewed change promptly, with normal hooks and required CI; use a PR if protection requires it. No force update of main or rewriting published history. |

Authors own results through the real consumer check; the coordinator resolves overlaps instead of reconstructing every change from RAW copies. New agents read AGENTS, this plan, relevant contributor/source guidance and the original criterion; historical material is opened only for a concrete question.

## 2. Operating instructions now corrected

The user authorized these instruction changes. AGENTS and HANDOFF now carry the working rules; the dated PLAN/README/EXECUTION/COMPOSITION packet is explicitly historical. Original criteria, accepted decisions and historical evidence are preserved.

| Existing source | Current rule |
| --- | --- |
| [AGENTS](AGENTS.md) and [HANDOFF](policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md) | Disjoint real-source authorship; coordinator owns the shared index/refs and actual overlaps. No RAW-only proposal queue. |
| COMPOSITION / Git procedure | Reviewed ordinary cherry-picks and selected semantic patches are allowed without rewriting originals; resolve companions and requalify affected consumers. |
| HANDOFF / evidence | One compact change record; deciding output retained once with actual receiver access. No routine per-slice JSON or separate receipt commit. |
| Old operational packet | Historical headers retire dated quotas, planning-only/publication bans and append-only status rules. This file is the current plan/status. |
| AGENTS / checks | Affected behavior/importers/consumers and applicable guards; real semantic/authority controls stay. Reuse unchanged qualified evidence and pinned complete censuses. |
| AGENTS / source attribution | Use a finding ID when available, otherwise the actual primary section. Git history is append-only; working documents can be updated. |
| AGENTS / skills | Apply the appropriate method within user scope. No automatic skill chain, new approval, serial-author requirement, forced isolation or blanket broad suite. |

The coordinator chose RAW-only source processing and excessive status/approval repetition; root AGENTS did not mandate that. COMPOSITION's single-writer rule and EXECUTION's append-only ledger were real procedures; their active workflow has now been replaced. P13, P29 and P40 already require proportional effort and stopping verification/repair ladders; they were underused.

Keep product safeguards: canonical ownership, candidate/authority separation, status/provenance/time semantics, actual producer → artifact → bridge → consumer → surface, semantic negative tests, independent review, hooks/CI and G's separate acceptance. Missing authority facts restrict the affected claim, not independent engineering. Shorten duplicated operational text in AGENTS without rewriting product doctrine.

### Reviewed skill templates and their use in PolicyOS

Reviewed all 15 installed `superpowers` 7.0.1 `SKILL.md` entrypoints, compared with `codex-engineering-guardrails` 1.1.1 and the system `skill-creator`. These are content findings, not a measured speed benchmark. Project routing is implemented in AGENTS; installed plugin caches, global settings and host skill discovery are unchanged. Explicit skill requests and higher-priority platform/user instructions still apply.

| Template(s) | Project handling |
| --- | --- |
| `using-superpowers` | No blanket invocation/chain merely because any response is being written. Choose the relevant method. |
| `brainstorming`, `writing-plans` | Use for open design/requested planning; do not add separate design/plan approvals to scoped authorized execution. Brainstorming already has quick-task/opt-out exceptions. |
| `executing-plans`, `subagent-driven-development` | Do not import serial implementation, fresh implementer per small task, a task-review gate before unrelated work or another full suite for every fix. The task review has one reviewer/two verdicts, not two mandatory reviewer agents. |
| `dispatching-parallel-agents` | Retain independent assignments; use affected integrated checks rather than a blanket full suite after every combination. |
| `test-driven-development` | Retain meaningful regression evidence. Never delete useful pre-existing work to recreate a test-first sequence, or require permission to preserve it. |
| `systematic-debugging`, `receiving-code-review` | Keep reproduction and causal diagnosis; clarify dependent items without stopping unrelated work. A numeric attempt count alone does not require a new architecture/approval cycle; use the actual failure class and P40. |
| `requesting-code-review` | One independent coherent-change review and material-delta follow-up; do not create a new multi-stage process per micro-edit. |
| `verification-before-completion` | Require truthful source-bound results; rerun for material input changes/required gates. It does not itself require a full suite after every message. Do not relabel old results as a new execution. |
| `using-git-worktrees`, `finishing-a-development-branch` | Reuse admitted source/environment; isolate for a concrete conflict. Follow the user's integration decision instead of another setup/baseline/menu or automatic workspace cleanup. The worktree template already permits reuse/working in place. |
| `writing-skills`, `diagnosing-superpowers` | For actual skill maintenance prefer proportional `skill-creator`; for a targeted instruction review inspect the files directly. Do not automatically build a pressure-test harness or seven-analyst transcript investigation. Use those larger workflows only when requested/needed and authorized. |

No replacement meta-skill or new wrapper framework is introduced. If the user later wants global skill availability changed, use supported plugin/skill controls for that explicit scope rather than patching a versioned cache that updates can overwrite.

## 3. Extract useful code and retire old branches

**Active curation assignment:** compare committed product `fa32c74dd8e0b1d6f42b53a652f57e6edaae71cd` via Git objects, not the shared working files. The checkout is **expected to be dirty** from concurrent authorized authors; cleanliness is not a precondition for this read-only review. Maximal slots use sorted `tips` by `tip` in `source-delivery-20261030-r1/branches/portable/manifest.json`, slice `[slot::36]`. Remaining slots reconstruct the union of SHAs in `branches/local-refs-at-start.txt` (column 2) and `remote-heads-at-start.txt` (column 1), subtract maximal tips, sort and slice `[slot::24]`. All paths are under the existing source-delivery directory linked below. Return concise decisions to the coordinator; no new report files, source/refs edits, tests or delegation. Judge every meaningful mechanism/companion before recommending retirement; uncertain content stays held.

Reuse the existing [ref inventory](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source-delivery-20261030-r1/branches/initial-ref-inventory.json) and [portable-patch manifest](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source-delivery-20261030-r1/branches/portable/manifest.json). They are inputs, not a new task queue. Portable patches omit some companions; selected mechanisms require their full pinned Git trees. Ancestry alone cannot discard intermediate branch tips whose useful code was later replaced/reverted.

1. **Preserve once.** Create/read back one annotated archival tag on the delivery commit, not hundreds of archive refs. Verify each retirement tip is reachable from that or another protected published root. The tag protects Git history, not untracked/ignored work or new tips outside its ancestry.
2. **Use a finite snapshot.** Refresh local/remote refs, actual worktrees and the protected set. Map every original ref to its unique tip and content groups. Do not research every historical commit. For changed/new refs, inspect their new endpoint; use delta-only review only when a previously checked ancestor and its affected dependencies are established.
3. **Compare content correctly.** For diverged tips, use the original common ancestor with the pre-preservation product baseline. For tips ancestral to that baseline, compare their relevant endpoint content directly with current main: their merge-base is the tip and would otherwise produce an empty diff. Group/deduplicate by actual mechanism, not branch name/date.
4. **Decide every mechanism and companion:** already implemented with a current code/test pointer; adapt into the canonical owner; reject with a concrete duplicate/supersession/defect reason; or deliberately defer with source SHA and obstacle. A ref is resolved only when all its relevant content is covered. Keep grouped decisions here, referring to existing inventories instead of producing per-branch handoff files.
5. **Transfer selected work visibly.** Integrate ready behavior with tests and companions. Put uniquely useful unfinished E02 work in a committed, published, named active branch with owner/next action before retiring its old ref, or retain the ref. Name a protected exact representative for duplicates. Deliberately out-of-scope/decision-deferred code may stay at the archival root with an explicit decision; it is not completed work.
6. **Retire resolved groups continuously.** Do not wait for all E02/external facts to finish. For both local and remote deletion, require atomic compare-and-delete at the reviewed SHA; otherwise retain the ref. Use a short exclusive branch/worktree-management window and re-read the tip, default/protected/G/deployment refs and all registered worktrees, including locks, after establishing that window. A changed tip or uncertain protection keeps the ref for reassessment. Never force past an occupied-worktree safeguard. Read back refs after each batch.

**Target:** no obsolete E02 topic/checkpoint/retired branches; main, one current author/integration branch and only actually owned feature branches needed for isolation. G and gh-pages have explicit protected roles, not an automatic cleanup exemption for every old topic. Archive reachability is checked per tip, including tips that moved beyond the original tag. Branch deletion is not a claim of meaningful disk savings.

Decision table format in this same file: `mechanism | refs/tips via inventory | keep/adapt/reject/defer | resulting commit/test or obstacle | retired refs`. Later remove duplicated delivery archives from the current tree only after content decisions, useful-code transfer and verified historical access, via an ordinary reviewed commit. Do not rewrite history or delete historical RAW/filesystems now.

### Composition and retirement results (30 October)

- TC fixture correction: `fa32c74dd8e0b1d6f42b53a652f57e6edaae71cd`, normal pytest module 17 PASS; published and read back in both main and the author branch.
- V3 refusal/round-trip repair: `70f7b636f`, independently reviewed two-path behavior, 9 focused + 8 guard/history + 1 served + 1 source-semantic fresh-reader PASS. Reviewed source/test hashes match committed bytes. The separate live-versus-historical family-matcher fix continues.
- One annotated published archival tag `archive/e02-before-composition-20261030` peels to `0741080cfc026077483f551333f853203b33d52d`. It protects the initial branch history, without claiming semantic incorporation.
- First retirement batch: **127 local refs + 15 remote refs / 137 unique reviewed tips**, atomically compared against their reviewed SHA and reread absent. Current/main/G/deployment and every registered worktree ref were excluded, including prunable registrations. Complete inventories after this batch: **351 local heads / 207 remote heads**. Ref deletion is not meaningful disk reclamation.

Content disposition for this batch: current canonical mechanisms and mirrored tests account for the behavior, or stronger guards supersede the endpoint; lexical/research-only material is historical. Reject unproven REST cursor forwarding, permissive DoWhy/PAG/CAN alternatives and weaker backtest admission; retain history through the tag. Canonical owners include DFI facade/selection, CAS transfer/profile/read owner, Catalog/legal projection, Search lifecycle/stopping, generation context/frontier/history, calibration/uncertainty, forecast/backtest, migration and schema contracts. Original unfinished criteria remain in section 8. Unique useful untransferred E02 source/tests remain on old refs or an exact named active representative.

<details><summary>First batch reviewed tip set (exact refs follow the existing inventory and occupied-ref exclusions)</summary>

`0197fe58 051dbdf2 0a00a1f4 0af60cb5 0b38bd05 0ca14b75 0e65b08e 0e987eaf 126885e9 135288c6 13c4af3f 15a04c44 167674c7 16d54e8b 172e791c 19405cd2 1dca66fd 1ed15b0e 20692bbe 233ad9ba 26c014f8 285f0b67 2ac640c9 2b548c44 2eebc0b2 3181beff 31838cda 32b539f7 34ee268f 36e864a8 375b090b 38ae8518 397a449e 3c937944 3cc7d2cb 3dde887e 3fc84a34 44e35ecd 44e8f492 45fe660b 4b4656b8 4e9b3f2e 527f8551 537124e0 5610eba4 57405dc0 5ac91950 5c10f120 5e0c8018 62cb804f 63e21470 6486e6a6 6602fbd0 66136425 668e091f 689acc0c 6a391aec 6bb8b7f7 6ccd51e6 713d2edf 72c38fff 72ca933a 754357d1 77166daa 77739ce1 7798c5fc 79c2d82a 7a48a2a3 7d5b4f15 834c9fbc 8520e63c 88b34d1b 8a6f82e6 8b5067c7 8d652c86 8e588cbb 8f3d9753 90409a5b 94571bd8 9a952415 9b91395b a239f6f4 a502741e a5bf3d53 a7204961 ae4befed b4e72621 b69685b7 b72c7c8d b7c72683 b815e46f ba56fb46 ba5946eb bb78b2b6 bc3911f0 bcbe3ab8 bd949d39 be5383e7 bf1eca0d c1e3dd51 c6ada1e5 c886f63b c8c2319d cb9be630 cd73f360 d40d5713 d47ee070 d4fb677a d8d68550 da58bd54 dd17d149 dd2e9476 ded00804 dfaadaac e0d8a926 e182bd19 e18c23f3 e25b3c8d e4fab345 e7dc1655 e81077ce e8adb07e e9ab35ab ec412aff ef3f208d ef9eafef f0fae836 f293396e f73360bc f7af77f3 f7f9484b f857fa5a fba62c46 fc0f012a fcf164eb fd00ddba fe510123`

</details>

`_cache/e02` stores current run output, never hidden source. An additional Trash pass moved four inactive caches (9,852 KiB); no environments, production originals or code/docs were moved.

### Full finite curation and second retirement batch

The original inventory contains **478 local heads + 318 local remote-tracking refs** (796 refs / 700 unique SHAs), and **222 remote heads / 221 unique SHAs**. Their SHA intersection is 220: **701 unique SHAs in the union**, not 701 branch tips. The existing manifest selects 232 maximal tips; the sorted remaining set contains 469 SHAs. Thirty-six direct slices and 24 leaf slices reviewed these respective sets; root corrected three mistaken direct-slot assignments before using them.

All 469 remaining positions were accounted for: **438 content-eligible / 31 retained**. Positions are zero-based in `sorted((local_inventory_SHA union remote_inventory_SHA) minus manifest_tip_SHA)`, using the pinned existing inventory files. Eligible inclusive ranges: `0-7, 9-12, 14-63, 65-73, 75-76, 78-101, 103-107, 109-114, 116-117, 119-156, 158-208, 210-212, 214-218, 220-234, 236-257, 259-265, 267-268, 270-277, 279-290, 292-310, 312-315, 317-337, 339-340, 342-347, 349-356, 358-361, 363-410, 412-413, 415-428, 430-431, 433-434, 436-468`. This exact set is replayable without another inventory/report. The retained positions below are the complement.

Second conditional batch deleted **268 local + 108 remote branches**; all read back absent. It also verified 119 corresponding/stale origin tracking refs absent (108 removed by normal push, 11 removed with explicit SHA comparison). The archive's peeled target, live tips, GitHub protected/default refs and every registered worktree were reread before mutation. Protected/occupied refs remain. Cumulative branch deletions: **395 local + 123 remote**. Complete post-batch inventories: **83 local heads / 99 remote heads**. Additional maximal tips still need composition; these counts are neither capability counts nor E02 closure.

Deliberate history-only deferrals include obsolete review/receipt/research packets whose original requirements remain in TASKS/coverage, and out-of-scope R9/GY/Atlas planning. Do not implement those future stages. Unique useful unfinished E02 source/tests are held; an open requirement in prose alone never justifies discarding its implementation ref. The identical native-replay portion of c40b2f57 is represented by retained 56417347; its distinct Bayesian bridge is already adapted.

| Remaining-set index / tip | Why retained / next owner action |
| --- | --- |
| 8 / `052e7632` | Conditioned GP checkpoint equivalence and fake-restore control |
| 13 / `082c28ef` | Policy-worker durable BudgetMiddleware admission |
| 64 / `273616d3` | Neural CAS resume and nested RL state |
| 74 / `2acc4c81` | Welfare GE-bound withholding and typed uniform carriers |
| 77 / `2c773afb` | Next-owner requirement packet needs explicit reconciliation |
| 102 / `3d18f37a` | Compiler/prompt-cache invalidation and settlement controls |
| 108 / `3e762fba` | Lesson read/access-write throttling without full-index CAS snapshots |
| 115 / `415621e8` | Broad D source/test endpoint not fully reconciled |
| 118 / `42987be6` | C05 embedded source patch and facade companions |
| 157 / `56417347` | Native predictive replay and admission; also represents identical c40b2f57 replay files |
| 209 / `6e9bb8a2` | Final-artifact verifier and semantic controls |
| 213 / `6f1e5e7a` | Fresh GET N8 replay and cross-process integration |
| 219 / `70d05813` | Spawned worker removed-journal negative |
| 235 / `789e9e90` | Streaming capacity-removal oracle |
| 258 / `86584ad1` | Nested RNG restoration and persisted Sobol test |
| 266 / `89f0520e` | Exact paid-ledger cache-custody reconciliation and conflict negatives |
| 269 / `8ae1d552` | Unowned empty-subdirectory refusal control |
| 278 / `8f58d734` | Persisted DOE receipt and fresh CAS sensitivity consumer |
| 291 / `93d62af8` | Recursive simulation/N8/N5 CAS and hard-admission controls |
| 311 / `a2276d5a` | Sampling admission and UQP/UQS controls |
| 316 / `a30eb1a8` | IID/Bernstein, persisted DOE and native replay |
| 338 / `b2dcf0ee` | Federation/backtest/calibration proposals need owner composition |
| 341 / `b36168bc` | Bootstrap/pnpm/release-glob regression controls |
| 348 / `b6b0d415` | Native replay implementation and tests |
| 357 / `bc532b30` | Nested RL checkpoint, decay and plateau controls |
| 362 / `c07f1be6` | Persisted welfare-draw lineage and reconciliation |
| 411 / `e0c004fb` | Broad historical source/test endpoint lacks semantic crosswalk |
| 414 / `e3f0103c` | Checkpoint sidecar cleanup/fsync/concurrent-reader tests |
| 429 / `ed065a94` | Persisted code-graph identity and durable worker budget |
| 432 / `ee6f2fb6` | Calibration, sampling, DOE, backtest, DDM and FRC source/tests |
| 435 / `f07058a3` | Numerical oracles committed; failure-path joint-law/axis recipe disclosure and combined dual-precision ledger control remain distinct |

## 4. First product composition front

Select behavior against current owners, not the newest SHA or largest diff. Quick verification repairs and critical integrations run together; an unrelated lane's final acceptance is not a prerequisite.

| Lane / original area | First action and useful result |
| --- | --- |
| TC / Q2 | Correct the child ID in `test_nl_temporal_context_world_read.py`; exercise the real fresh child reader and missing-Fabric-row refusal. This repairs verification of existing transport. |
| Compute / child execution | Check spawned worker origin and use an established importable helper. Connect the existing identified ledger to actual priced work; prove one reservation/charge and child-failure handling. The test-only import patch is not that bridge. |
| V3 / generation | Reuse the existing three-failure diagnostic, without another qualifier. Separate record round-trip, absent cost basis and reason overwrite; complete scheduled cost, unscheduled candidate and persisted refusal behavior. One writer owns overlapping V3/V4/V7/R3 generation changes. |
| Dynamic / source preflight | Compose coherent R18 semantics/companions; test real eager/deferred and dict-order behavior plus source-wide compatibility and practical false positives. |
| Child computation / S1 consumers | Exercise the real SQLite/CAS seam promptly; concurrently wire the scoped Foundry adapter, actual Stage-B planner and typed selected output closure through the existing executor. Include accounting/parent effects that this route needs. Kernel-only toy execution does not finish it. |
| N7 / V4/V7 | Complete real early-host/Protocol startup and loader/provider mutation/restoration before authority activation. The archived predicate literally returning `False` is unfinished, not the final solution. |
| Legacy scientific candidates / Q0/V5/V7 | Assess finite-family CPDAG queries, predictive verification and interval-basis reconciliation against current owners/criteria. Adapt missing behavior without promoting candidates to authority or restoring old broad subsystems. |

Converge shared Core custody/RunContext, runtime bootstrap, Engine executor/retry, generation fixtures and generated families at their actual owners. Copying the old settlement executor whole would remove newer safeguards. Reuse G's selected existing executor/trusted local profile; do not invent another scheduler or universal sandbox.

Establish relevant current-main behavior, then repeat affected tests/consumers after composition and add material missing regression coverage. Call a failure inherited only after the exact pre-slice replay and disjoint-input proof (P41). Never remove assertions, narrow inputs, bypass a gate or relabel refusal to manufacture compatibility.

**Regression recovery:** stop dependent promotion on a new red; fix forward or safely `git revert` the introducing own coherent commit, preserving unrelated work. If later dependencies prevent isolated revert, make a checked forward correction. Repeat affected checks and read back the published result. No reset/rebase/force rollback and no unexecuted absolute no-regression promise.

## 5. Short development and verification cycle

Each assignment names the owner, actual files, original requirement, expected behavior/check and shared resources. Authors edit source/tests directly. Keep one writer per overlap, freeze the affected import/dependency set for checks and bind the result to the candidate; use visible isolation when uncertain. Commit released paths at coherent boundaries; do not stash or overwrite other work for a clean-tree validator.

Use existing fixtures/runner and smallest relevant tests during development. Semantic/authority/lifecycle changes need real consumer and meaningful adversarial/removal controls. A spelling/import/docs fix does not need a new proof framework. One independent review per coherent change, then material-delta review only. On the second same-class escape, fix the class or demonstrate the actual missing capability; a named residual cannot authorize an unsafe claim and leaves its criterion unresolved. After an expensive freeze, cosmetic findings become debt; blocking findings are batched.

**One change record**, here or in the ordinary commit/PR description: `original criterion → change → command/result → material input/profile → needed output link → next action`. Git supplies source identities and footprint. Per-file provenance is added only when the actual claim needs it. No routine receipt JSON, separate receipt commit, nested evidence index, source copies or new observation qualifier.

Keep complete deciding-gate/removal output once, concise at source and losslessly compressed when useful, in accessible CI or designated local output storage. Deliver what G actually needs and irreproducible witnesses as real bytes. Reproducible material gets source/command/available-input instructions; duplicate/debug output gets no second copy. Preserve access or specify the exact rerun before needed output expires. A missing file's hash proves no delivery. Recovery archives are not the daily work format.

Run affected tests/importers, Ruff and applicable architecture/generated/validator checks; changed validators retain real corrupt-input/removal checks. Use broad backend/CI-parity, installed/native and cross-consumer checks when the blast radius or required gate warrants them. Final sequence: review/fix source → freeze relevant inputs/backend → one agreed expensive wave. A new docs-only HEAD does not reprice unchanged numerical proof. G independently accepts the final product/findings.

## 6. Resources, agents and visibility

Reuse Python 3.14, Node/corepack, existing caches/runner and read-only data link. No environment, checkout, dataset or CAS copy per owner. Remain local until cloud is authorized again; any later cloud task needs published compact inputs and a proven Git/PR return path before costly execution, with no ignored coordinator-local prerequisite or assumed mid-run messages.

Measure disk/RAM/threads/DB/ports separately. Drafting free disk was about 5.7 GiB, not a permanent quota. Budget measured growth for remaining steps plus a stated margin; unknown costly profiles run alone. Previously measured two jobs/four-GiB total RSS is a numerical starting reference, not an authorship limit. Do not silently lower safety stops or block all authors because one test cannot fit. Preserve chat databases, working environments, code, documentation and unique production data. Authorized cleanup moves only disposable inactive material to Trash; no permanent deletion or emptying Trash. The first pass moved 546 reproducible test/cache directories (6.783 GiB) by same-volume rename; that footprint is not a claim of reclaimed free space.

Use persistent, correctly named domain owners; default Luna for suitable finite work, Terra/Sol for complex code/review, with permitted capacity fallbacks. Source ownership, review concurrency and numerical process budgets are different. Report actual usable behavior, changed critical path and obstruction, not polling or archive counts. Before pause/handoff, commit useful work and update the next action here. Ordinary authorized engineering does not need repeated permission.

## 7. Execution sequence after approval

- [x] **Correct the instructions:** apply section 2's repository-level workflow and skill-routing corrections. This is the authorized instruction-only change.
- [ ] **Workspace visibility:** attachment tool refused the canonical worktree because it is owned by another task. Continue with explicit canonical paths; no checkout recreation or ownership bypass. Open canonical files/reviews directly while app attachment is unresolved.
- [ ] **Start integration and curation together:** begin section 4's ready lanes and the finite mechanism/ref review. The first checkpoint is integrated TC/spawn checks plus a real V3 diagnosis while child/N7 work progresses—not another source-only packet.
- [ ] **Retire resolved branch groups:** transfer useful code, verify reachability/tips/protections, delete conditionally and read back. No waiting for unrelated E02 acceptance.
- [ ] **Finish original routes:** maintain the single checklist below and original occurrence mapping; close internal producer/bridge/consumer defects and identify exact genuinely external inputs after real attempts.
- [ ] **Freeze and hand to G:** one composed verification wave and one concise final handoff section here, with source and required output links. No new general planning round or hundreds of receipt files.

## 8. Current E02 checklist — update this table, not a second backlog

Baseline: original **26 rows / 127 bundles / 282 IDs / 291 criterion occurrences / 319 task–ID edges**; the separately counted 331 occurrence-to-row routes are navigation. Exact original predicates remain in the linked TASKS/coverage and existing bindings. Historical B198/B59 and selected G decisions stay preserved. R9/GY/Atlas implementation remains outside E02 until acceptance.

This table records integrated results and next outcomes. During execution add the responsible owner, latest integrated commit/check and exact remaining obstruction to the same row. BOOT0 and DEC0 remain coordination rows, not substitute product completion.

| Original row | Next product outcome or preserved boundary |
| --- | --- |
| BOOT0 | Correct visible workspace/ref; keep source and publication identities current. |
| DEC0 | Execute already selected decisions; ask G only genuine unresolved semantic choices. |
| Q0 | FED-02/B142 typed empty UNION now projects declared output types after current lineage-preserving profile restoration; 4 DuckDB cases PASS including persisted/reopened DESCRIBE, nonempty source typing and no-sources refusal. Independent source review GO; root read complete pytest output. PLG-02/LA-023 CLI now returns 1 for bridge_pending and 0 for real trained; 4 cases PASS including actual tiny native training and unsupported composite, independently reviewed by root. Outputs once `_cache/e02/sql-union` and `_cache/e02/training-cli`. Other original occurrences and legacy candidates remain. |
| Q1 | Complete CAN.3 affected readers, state/Foundry/cache and installed migration; preserve accepted CAN.2. |
| Q2 | TC child-ID fixture integrated: normal module 17 PASS, 13.21 s, including fresh child read and missing-Fabric-row refusal (outputs `_cache/e02/tc`). Continue selected-member/API/client/generated/installed consumers. |
| R1 | Finish required real-child contours and basis invalidation beyond the verified single contour. |
| R2 | Preserve accepted B87/B89; keep provenance correction separate and recheck genuinely affected changes only. |
| R3 | Observe the current original producer/cache pilot, then resolve and run the affected original 14-case routes. |
| R4 | Preserve accepted configured B56 folds; prove the distinct long-compute control/lease/fencing property. |
| I1 | Complete LA-041 persisted recovery, malformed/legacy/interrupted retry and original selectors. |
| I2 | Obtain the real root-census/installed CLI result through supported execution; stop building replacement profilers. |
| I3 | OBS-02/B147 now captures and verifies one bounded temporary Parquet member, and streams/retries the same bytes. Real pre-fix ABA/mutation controls reproduced; 30 final cases PASS (10.32 s, peak RSS ~781 MiB), including persisted D2 output and Scientist consumers; independent GO. Outputs `_cache/e02/obs-snapshot/importers.log`. Pre-copy local digest establishes byte continuity; producer authenticity/currentness, atomic capture and production-size resource behavior remain unestablished. Continue other source-owned keys/version/progress and durable replay obligations. |
| I4 | Complete Legal encoder/flat-legacy changed-text and each distinct Legal criterion, beyond Catalog acceptance. |
| S1 | Connect actual source/request and parent/child scientific computation through owned outputs and effects. |
| S2 | Complete actual relation owner and separate B190/B194/B197/B200/LA-036/B157 obligations. |
| S3 | Join S1 source/request to exact paired subject/unit and fresh positive/negative consumer. |
| T1 | Bind real source/issuer/currentness to each claim; implement software admission without fabricating institutional facts. |
| T2 | Complete actual permission/issuer/source/commit-time checks and their same-context negatives. |
| V1 | Demonstrate ordinary POST → owned context → N5 → CAS → fresh GET with the required controlled/authentic roots. |
| V2 | Complete actual N4 children, N6 frontier/history and fresh reader with sibling/budget controls. |
| V3 | Composed the three-failure repair in generation_cycle and its mirrored tests: N6-owned JSON array round-trip, refusal preservation and unbound-route suppression; scheduled tax-receipt positive plus unscheduled firm_survival negative. Independent review GO; 9 focused + 8 guard/history + 1 served COV PASS, normal pytest/JAX CPU profile, synthetic fixture data, full outputs once at `policy-engine/_cache/e02/v3/`. Source-semantic-enabled fresh-route consumer also PASS (1 case, 11.59 s, `_cache/e02/v3/semantic.*`). Wrong-family routing repaired: strict current family/explicit supplied route, legacy agreement for new unmarked records and recorded legacy replay law. Independent GO, final 4 negatives/compatibility + 2 marked/unmarked dispatch positives PASS; original broader wave 8 PASS/1 red. Full same-cycle N5/N8 reentry still stops at n7_reentry_current_world_context_unavailable with a registry-only fixture; attribution is not established and its expected second simulation remains unproved. Next wire a genuine ACQ-01 owner route and exercise full reentry. No overall V3/G closure. |
| V4 | N7 early launcher/recorder prerequisite integrated under six explicit paths: selected-role bindings, loader/remove-reimport controls, honest candidate fallback for test/diagnose when Git selection is unavailable. Independent GO; 25 source-level cases PASS (22 recorder + 3 bootstrap), outputs once `_cache/e02/n7/recorder-4.*`. This issues no authority. A committed-HEAD launcher smoke on 4e5b9bf35 exits 0 for tools --help (dispatch only). The 2-path recorded-finder delta has independent GO and 27 combined source-level PASS; real-product discovery remains red (2 PASS/1 FAIL) and is under diagnosis. Next actual host/provider/stdlib/native and through-use qualification. Ordinary product alias-finder insertion currently refuses capture; reconcile its actual owner, do not weaken mutation detection. |
| V5 | Independent Gaussian oracles integrated in the canonical Monte Carlo tests: exact axis/draw covariance, singular support, invalid-before-callback and joint non-authority. Full module 34 PASS (7.83 s, peak RSS ~537 MiB, CPU/one-thread profile), independent GO, output once `_cache/e02/gaussian/pytest.log`. No source owner changed. Explicit historical recipe fields, production joint provenance/units, persisted consumers and distinct GP/native/B157 routes remain. |
| V6 | Establish valid exact-profile A/A then intended A/B and B13 basis/sibling behavior. |
| V7 | Derive measured coverage from actual observations and preserve its meaning through the fresh served result. |
| DX0 | R18 scanner delta withdrawn after a conditional helper counterexample exposed a false-green target. Collector bytes remain unchanged; retained exact-vs-unknown subscript test/documentation correction has 3 native PASS and independent GO. Dict-order/global branch joins, hashing and deferred effects remain unresolved. Whole-source collector input changed during run, so no stable whole-gate PASS. Continue original native/installed/source-wheel/sdist/archive proofs. |


Pattern pass: P01/P02 actual consumer integration; P13 proportional effort; P14 no inflated proof counts; P27/P31 canonical mechanisms; P29 actual property checks and a stopping point; P35 finite complete ref/criterion coverage; P38 ancestry is not behavior; P40 no repair ladder; P41 correct failure attribution. Organizational cleanup is not E02 completion.
