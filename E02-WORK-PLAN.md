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
| Q0 | Reconcile the individual original occurrences and useful legacy mechanisms; no aggregate source-inventory closure. |
| Q1 | Complete CAN.3 affected readers, state/Foundry/cache and installed migration; preserve accepted CAN.2. |
| Q2 | TC child-ID fixture integrated: normal module 17 PASS, 13.21 s, including fresh child read and missing-Fabric-row refusal (outputs `_cache/e02/tc`). Continue selected-member/API/client/generated/installed consumers. |
| R1 | Finish required real-child contours and basis invalidation beyond the verified single contour. |
| R2 | Preserve accepted B87/B89; keep provenance correction separate and recheck genuinely affected changes only. |
| R3 | Observe the current original producer/cache pilot, then resolve and run the affected original 14-case routes. |
| R4 | Preserve accepted configured B56 folds; prove the distinct long-compute control/lease/fencing property. |
| I1 | Complete LA-041 persisted recovery, malformed/legacy/interrupted retry and original selectors. |
| I2 | Obtain the real root-census/installed CLI result through supported execution; stop building replacement profilers. |
| I3 | Complete source-owned keys/version/progress and durable replay through actual consumers. |
| I4 | Complete Legal encoder/flat-legacy changed-text and each distinct Legal criterion, beyond Catalog acceptance. |
| S1 | Connect actual source/request and parent/child scientific computation through owned outputs and effects. |
| S2 | Complete actual relation owner and separate B190/B194/B197/B200/LA-036/B157 obligations. |
| S3 | Join S1 source/request to exact paired subject/unit and fresh positive/negative consumer. |
| T1 | Bind real source/issuer/currentness to each claim; implement software admission without fabricating institutional facts. |
| T2 | Complete actual permission/issuer/source/commit-time checks and their same-context negatives. |
| V1 | Demonstrate ordinary POST → owned context → N5 → CAS → fresh GET with the required controlled/authentic roots. |
| V2 | Complete actual N4 children, N6 frontier/history and fresh reader with sibling/budget controls. |
| V3 | Composed the three-failure repair in generation_cycle and its mirrored tests: N6-owned JSON array round-trip, refusal preservation and unbound-route suppression; scheduled tax-receipt positive plus unscheduled firm_survival negative. Independent review GO; 9 focused + 8 guard/history + 1 served COV PASS, normal pytest/JAX CPU profile, synthetic fixture data, full outputs once at `policy-engine/_cache/e02/v3/`. Wrong-family matcher red remains open with attribution not established; next run the source-semantic-enabled fresh-route consumer and repair live/historical matching at its canonical owner. No overall V3/G closure. |
| V4 | Complete real N7/planner selected-source and normal served consumer, including loaded execution. |
| V5 | Preserve actual typed units/uncertainty through report/history; finish distinct GP/native and B157 paths. |
| V6 | Establish valid exact-profile A/A then intended A/B and B13 basis/sibling behavior. |
| V7 | Derive measured coverage from actual observations and preserve its meaning through the fresh served result. |
| DX0 | Freeze actual package assets/origins and complete required native/installed/source-wheel/sdist/archive proofs. |


Pattern pass: P01/P02 actual consumer integration; P13 proportional effort; P14 no inflated proof counts; P27/P31 canonical mechanisms; P29 actual property checks and a stopping point; P35 finite complete ref/criterion coverage; P38 ancestry is not behavior; P40 no repair ladder; P41 correct failure attribution. Organizational cleanup is not E02 completion.
