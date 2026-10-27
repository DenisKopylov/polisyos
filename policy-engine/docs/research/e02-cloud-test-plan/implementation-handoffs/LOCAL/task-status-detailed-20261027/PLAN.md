# E02 completion plan: current 19-row detail set

Status: source-qualified completion plan, subject to independent review and root publication. Product source cut: a92c9774edf8049d590cd6ca6de35aa17063025a, tree 7f9908cd38ca5aa2148f7cc9458d3dbbd0cdb1d9. The pinned packet-generation HEAD is 65ac853e2735e827e27688a6175f1a385901e20e (tree 95a1820149020d566a229a718e67b79d690844c3). After BOOT0/T1 documentation commits 81bc3861 and 76691bd2, R2 added tests/unit/fabric/connectors/test_pool_admission_races.py; root reports two passing nodes. The committed product-src diff from a92 to that packet-generation HEAD is empty, so the current task source remains pinned to a92.

## Goal

Complete each original unified-local task exit with a source-bound producer/artifact/bridge/consumer witness and its required negative controls. Reconcile each of the 291 original criterion occurrences separately before any Q0/G proposal. Do not translate task-row progress into finding closures.

## Architecture and reuse

Apply the ratified decisions and reuse existing contracts, selected refs, adapters, owners, test fixtures, CAS, stores, and consumers. Extend only where the original criterion's property is not currently exercised. Do not introduce new authority, unsupported estimators, broad registries, producer rights, or output surfaces to satisfy a test-shaped proxy. Candidate evidence remains candidate evidence; missing owner facts stay typed as not_established. Keep source, producer, persisted artifact, orchestration bridge, consumer, verification, surface, and semantic test linked.

## Tech stack

Use the existing policy-engine Python environment and native pytest profile. Preserve pytest.ini, default plugin autoload and configured addopts. Use corepack pnpm for generated API/dashboard work. Reuse existing package inputs and worker environments. Provision missing supported backends through existing locked recipes/cache, offline where available, after resource admission; avoid environment/source copies. Preserve scientific and platform contracts. Exact per-task commands, expected predicates, dependency notes, and measured/unmeasured resource data are in tasks.json. Commands naming proposed tests become executable only after those companions are authored.

## Spec and denominator

The authoritative original task manifest is policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json@a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c. Its denominator is 26 task/decision rows, 127 bundles, 282 unique finding IDs, 291 criterion occurrences, and 319 task-to-finding edges.

This packet has 19 task reports. I1 is author_complete for its bounded task exit based on its 25-node current-source run, prior 20-node run, and independent full 18-source join review. The 25-node readset itself matches 16/18 paths; the remaining two were loaded and matched in the preceding run. It has no formal closure IDs. The other 18 rows have implementation or verification work. DEC0 is a separate decision row, and BOOT0/T1/R2/R4/I4/V6 are outside this detailed-19 packet.

Q0 is not a full semantic refresh. Its direct assignment is 206 IDs / 212 occurrences; 76 IDs / 79 occurrences are routed to specialist tasks. The earlier 3c13 matrix covers source spans/source cuts/navigation across 291 rows only. The prior Q0 audit counted 210/212 direct rows without a new occurrence-specific runtime receipt since dc626; treat that as a dated receipt count, not a current work count. The new family-A requalification covers seven current criterion rows with source/test analysis but zero qualifying current runtime receipts; B18/B23/B25 are not whole-criterion author-complete, and LA-045's installed proof remains pending. B199 and LA-004 have bounded older-source receipts and need exact-current rebind. Five IDs repeat across 11 distinct cards (six extra occurrence refs); preserve those rows independently. Property-family counts and exact refs are retained in the Q0 report referenced by tasks.json.

## Global constraints

- Root owns every canonical source write, generated output, commit, and task-status publication. This aggregate writes only to its assigned RAW prefix.
- Keep a single writer for a shared source/test/packaging lease. Root's first-wave plan is the execution anchor; leaves prepare reviewable raw proposals, and root reviews/applies.
- Root admits at most two native jobs whose combined measured memory budget is at most 4 GiB, with one numerical thread per job. Run the first unmeasured V1/V2 replay, native GP, and VM work alone. This limit applies to native jobs, not the independent read-only subagents. Keep the disk floor at 6 GiB; honor larger task-local reserves (R1 requires 8 GiB before its contour replay). Recheck disk and cache/inodes before any packaging wave. No environment copies.
- Preserve the exact source/test/input/readset base for each check. Do not infer inherited failure without exact slice-base reproduction and a zero intersection against the complete input denominator. No blind cap increases. This planning artifact launches no installs or workers; subsequent supported provisioning follows the locked recipes and resource admission above.
- Existing G decisions remain selected: CAN.3/TC/Closure, B09, HTE/CAN/B161 internal relative-width, N818, and PAG/transport. Do not invent new architecture decisions or blanket G blockers. Findings are closed only by G's explicit admission, not by a passing task suite.
- DEC0 remains a separate G decision item. No formal closure IDs are proposed.

## Pattern pass and review focus

Relevant register rules: P35 (full-set denominator), P37/P38 (recomputed gate predicates and property-vs-proxy divergence), P40 (same-class residual versus new class), and P41 (failure provenance from the exact slice base). Corrections below narrow inherited task prose where it exceeded the original criteria.

Review every packet for five things:
1. Actual source owner, authority, epoch/currentness, provenance, and selected input are independently bound.
2. Producer -> typed persisted artifact/event -> orchestration bridge -> real consumer -> required surface is exercised end to end.
3. Positive behavior is paired with counterfeit, foreign, stale, missing, sibling-consumer, or property-removal controls at the consumed seam.
4. The implementation meets the original finding ID/criterion occurrence without expanding its scope; truthful unsupported/limited status is acceptable when allowed by the original criterion.
5. Exact source/input/test denominator, current readset, bounded resources, and no unapproved write are recorded. Classify a repeated same-class escape under P40 before proposing another repair.

## Current row status and concrete next work

Detailed per-row paths, criterion IDs, work units, commands, expected outputs, dependencies, and resources are in tasks.json; each record carries its report path and SHA-256.

| Row | Current task status | Concrete remaining work |
| --- | --- | --- |
| Q0 | verification_remaining | Produce one current outcome per direct occurrence (206 IDs / 212 refs), preserving repeated cards; family A has 7 source/test requalifications but no current runtime receipt, so keep all seven verification_missing; rebind B199 and LA-004; reconcile 76 / 79 specialist refs without claiming the 291-row source map is semantic review. |
| Q1 | implementation_remaining | Bind the existing CAN .3 packet's 27 pre/post path hashes to a92; complete C-A Core/IR codec and profile laws, C06 pre-materialization controls, C-B/C state/Foundry/idempotency consumers, then C-D public/installed readers. |
| Q2 | implementation_remaining | TC and closure interface work proceeds on accepted CAN .2 in parallel with CAN .3; after the affected contract freeze, selected source contracts and semantic consumers, generated OpenAPI/client/dashboard companions with corruption detection, then exact frozen-source installed source-wheel/sdist/GCP archive consumers. |
| R1 | verification_remaining | Finish five serial current-source contours and B148 criterion-specific/removal controls. First 111-test group had 110 passes/one failure: child expected exit 73 but returned SIGTERM (-15). A guard-only single-node discriminator failed the same way, so the spawn-guard hypothesis is not the sole cause. Cause remains not_established; diagnose child startup/exit timing against its 30-second child timeout, do not count it as inherited or a proven product defect. Four contours remain pending; root schedules them after I2. |
| R3 | implementation_remaining | Fix exact tenant_context test fixture signature; add actual B10 second-candidate/fallback witness; wire existing app-scoped CacheReuseAuthorizer with owner-resolved snapshot metadata, admitted identity and current epoch through the ordinary NL route. A temporary self-owned CAS/configured local owner is a valid software positive; production source rights remain not_established and are not a prerequisite. |
| S1 | implementation_remaining | Add B161 source-array/content-bound unit/scope join through the real served assessment/fresh snapshot; coordinate one B31 paired ID/interval unit witness with S3; replay remaining assigned criteria and the separate finite G528 route. |
| S2 | implementation_remaining | For B200, reuse selected InputRef/CAS/composition history, identify a genuine relation owner and current consumer, then persist/recompute effective N with overlap/unknown/counterfeit/removal negatives. Run separate B190/B194/B197/B157 checks. LA-036 is verification of truthful requested/effective identity and unsupported/fallback behavior; a new conditional/tree estimator is not required. |
| S3 | verification_remaining | Change adversarial mutation to consumed get_raw_manifest_bytes; add paired m/km fresh-consumer witness scaling both identification point and native interval. Join with S1 B31; serialize the expanded ~1.06 GiB prior-measured suite. |
| T2 | implementation_remaining | Complete U1-U5: existing B05/B08/B154 paths, LA-018/024/025, B131/B137 owner currentness, B164 commit-time authorization, LA-054 same-context metrics. B154 needs truthful batch/item/global-abort/cancel results, not a new publisher. LA-055 retains R2's declared exception and existing precedence; no deployment platform is required. |
| V1 | verification_remaining | Bind served service and profile readers to one owner-built temporary source root (including selected WMR/L2, L3/L6, and persisted V1 D-Cat paths); then run exact POST -> worker -> N5 -> CAS -> fresh GET node. This is a fixture-root correction, not an established product defect or performance result. |
| V2 | verification_remaining | Reuse same controlled-root fixture, then run two independent serial N4 nodes: meaningful two-child/N6-history/fresh GET, and TCP reopen with budget/sibling-failure/frontier checks. Each needs complete JUnit and current source readset; an abort is not a verdict. |
| V3 | implementation_remaining | Implement admitted content-change reissue for same candidate through WMR/N5/history and fresh GET; prove transport-ID/write-time-only controls do not trigger unnecessary computation, while S02 still persists the newly admitted source, its lineage, cost and acquisition state and retains the old N5 only after whole semantic-basis and current eligibility checks; and crash/replay preserves selected frontier. Share V1 served test-file lease. |
| V4 | implementation_remaining | Share one V4/V7 IR writer repair: use IRCanonSpec at the four current IR write calls, retain Core-owned digest CanonSpec, and preserve pre-effect foreign-spec refusal. Repair only selected WDI fixture owner mismatch, then exercise predictive POST/CAS/reopen/fresh GET with same setup but changed held-out outcomes; keep S10 predictive-only/limited. |
| V5 | implementation_remaining | Implement B108 valid local alias/null/zero/sign/unit behavior; carry exact typed metric_units and provenance through MethodJob/BenchmarkEvaluation/runner/CAS into native GP; bind B157 to its exact source-owned semantic representation: current scalar consumer supports 1.2 with method observations absent and refuses the distinct 1.3 method-observation representation until a verified adapter exists. Do not accept-all/current-literal or claim a new period-flow law. |
| V7 | implementation_remaining | Reuse V4's single IR writer repair and route fixture fix, then verify predictive chain by CAS reopen and same-CI/different-observation fresh GET. Keep B16 population and B32 source-time not_established; do not upgrade causal authority. |
| I1 | author_complete | No local author action remains for the bounded I1 exit. Evidence comprises 25 fresh PASS nodes, prior 20 PASS nodes, and independent full 18-source join GO. G/finding closure remains separate. |
| I2 | verification_remaining | The exact product-root schema-FQN CLI attempt timed out at 420 seconds with exit 124 and empty stdout/stderr; this is no census output and no product failure. The older approx. 230-second statement has no receipt and is not a measurement. First run the diagnosis note's bounded 90-second metadata-only Git-enumeration profile, then instrument selected-file read/decode/AST/serialization only if those stages are fast; rerun the unmodified public CLI for the full result. Reconcile release archives and installed CLI/discovery after resource review. Linux test is unrun, not unavailable; current Darwin skip is not Linux evidence. |
| I3 | implementation_remaining | Implement positive B80 cursor promotion with source-basis/evidence-currentness controls; bind B83 source-owned event keys and version; prove durable suppression at 86,399 seconds and acceptance at 86,400 across two independent processes. |
| DX0 | implementation_remaining | Close N1 namespace-effect proof by rebinding stale RAW proposals under a new identity (append-only history), plus opaque-boundary refusal, N2 operation-to-SLO consumers, current N5/N6/N7/N8 companions, and all 13 native SOTA rows. Re-freeze selectors/assets before Q2 installed wave; share its package lease. |

## Execution phases and leases

### Phase 0: admit source cut and packages

1. Root confirms reviewed task reports/addenda and applies exact source packet boundaries. BOOT0/T1 documentation packets at commits 81bc3861 and 76691bd2 are integration documentation, not code acceptance.
2. Keep the R1 child-exit failure bounded and unresolved: the first contour group observed SIGTERM where exit 73 was expected; the guard-only runner discriminator reproduced it. Diagnose actual child startup/exit timing versus the test's 30-second timeout. Do not raise limits blindly or label the cause harness-only/product-only.
3. Confirm task-specific disk reserves and current source/test pins before native waves. Use the admitted native-job slots and memory budget above; unknown-cost runs, native GP, and VM work run alone.

### Phase 1: five owner-bounded independent work packets

Root's policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/remaining19-detail-20261027-r1/execution-wave1/PLAN.md@1230f2f7032ec21de50e3fb2884bb7ea846288b065644db25b9ca5d282972450 already names these packets; use its path lists and write boundary.

- S3: consumed raw-manifest adversary seam and one paired unit-channel test. No runtime contract change absent a demonstrated product defect.
- V4/V7: one writer across shared IR CanonSpec callsites, plus WDI test-fixture correction. V4 and V7 semantic tests are staged after the shared repair.
- V1/V2: one writer across the two served-history helper/test pairs. Reuse candidate_cycle_source_profile.build_candidate_cycle_substrate_route_inputs; inject the same returned root into service/N4 and L6 readers, assert actual resolved owner paths, and retain controlled L2 and V1 D-Cat inputs. Run V1, then V2's two native nodes serially. The corrected-root resource cost is unmeasured; no L3 performance or numerical-codebug claim.
- R3: exact tenant_context test companion and B10 consumer witness. Add bounded B67/B68 app-scoped local-owner bridge through existing CacheReuseAuthorizer/current-epoch/CAS interfaces; preserve fail-closed behavior when owner evidence is absent.
- V5: alias semantics, exact typed metric_units/provenance path through the existing MethodJob/BenchmarkEvaluation owner and GP consumer, and B157 producer-version relation. The producer emits 1.2 without typed method observations and 1.3 with them. The current scalar consumer supports exactly its 1.2 representation and refuses 1.3 until a verified adapter exists; use one shared predicate and retain kind/media/profile/invocation joins.

Each packet returns exact preimage/postimage hashes, reviewed patch/postimage, test nodes/commands, expected semantic discriminator, resources, and self-review in its allocated RAW directory. Root reviews before applying. No task packet is accepted from an exit code or marker-only check.

### Phase 2: remaining independent task units

- S1 and S3 coordinate the single B31 two-channel/unit witness; S1 also owns B161 and its separate G528 route. Do not patch the shared test files independently.
- R1 runs the remaining four contour groups serially after I2 is complete. Keep activity-worker alone. Then run B148's two ordinary preservation modules and both separately expected-red property-removal controls. The failed child-exit node remains unresolved until exact startup/deadline evidence distinguishes the cause.
- S2 runs distinct owner/relation intake and the B200 persisted/fresh consumer extension only after a real relation owner and current consumer are named. Its bounded neighbor suites are independently schedulable.
- T2 implements/tests U1-U5 as distinct predicates; five focused command groups in tasks.json keep B154, LA-055, and production-right limits intact.
- V3 handles source-driven reissue under the V1 served-file lease. I3 handles event-key/promotion semantics and two-process replay. Neither gets a new global enum or broad registry.
- Q0 occurrence owners use the 127-bundle/291-occurrence matrix, keep repeated occurrences separate, and reuse unchanged evidence only after exact source/input/consumer/surface rebinding. Do not run uniform suites for all Q0 rows.
- I2 has a current exact-product-root CLI timeout (420 seconds, exit 124, empty streams); it is not a result. The historical approx. 230-second value is unsupported by a run receipt. Run the bounded 90-second Git enumeration profile described in I2/root-census-timeout-diagnosis-r1.md@48430225550902acf5722eded04e7cbf1e1523253badba7936ac639cb951c9de, then profile selected-file reads only if Git stages are fast. A complete public CLI census remains required. Package/archive and installed CLI work still waits for the host disk/inode gate. Linux startup remains conditional; inspect existing image/mount/volume/Python state and stop before any download or disk expansion.
- DX0 runs N1/N2 repairs and source checks before the full 13-row native SOTA freeze; it shares final Q2 package/installed-consumer lease.

### Phase 3: serialize shared owner and installed surfaces

1. Q1 C-A freezes Core/IR canonical profiles and readers before C-B/C-C state/Foundry/cache/idempotency. Bind the existing .3 packet's codec roster of 27 existing/new entries and all mandatory consumer companions to a92 before use; run C06 pre-materialization refusal and C07-C13 actual consumer/removal controls.
2. TC-A request semantics and TC-B closure interface work proceed on accepted CAN .2 in parallel with CAN .3. Their composed TC-C closure verifies the agreed owner snapshots. Q2-A then verifies the affected selected contracts; Q2-B regenerates canonical OpenAPI/client/dashboard artifacts and runs normal/corrupt-field checks; Q2-C prepares/reviews/reapplies/re-prepares exact package manifests and serially installs source wheel, rebuilt-sdist wheel, and rebuilt GCP archive wheel outside the checkout.
3. DX0's Q2 asset verification and repository SOTA uses the same frozen package inputs; no overlapping writers or installed build processes.
4. When all source and owners freeze, reconcile Q0's full 291 occurrences with explicit current outcome/evidence/boundary/limitation/next step. Then prepare the complete full-ID closeout proposal; independently bounded ready-task packets may be delivered to G in parallel before global closeout. G alone decides source acceptance and findings.

## Acceptance gates

- Accept each work unit against its original criterion, not the name of its test. Record input, resolved owner/provenance, produced artifact/event, bridge/lifecycle, fresh consumer/surface, and a discriminating negative/removal control.
- Every test claim carries exact source, test, fixture, and current readset identity, with full JUnit/stdout as required by the task run contract. An unrun, aborted, filtered, or unsupported run remains unverified.
- Current-slice proposals carry no new adjudication; preserve all historical closures, including B198, exactly. Author-complete is not equivalent to a formal closure.
- At final source freeze, execute focused tests, generated drift/corruption checks, architecture guards, and installed consumer checks in tasks.json. Full suites and expensive package waves run once after cross-owner review and resource admission.
- Before publication, re-read the aggregate and current task reports from the final branch; recompute report hashes, task counts, finding IDs and occurrence totals from the complete source files. Do not publish a stale working-tree snapshot.


## Root rulings and shared-interface preparation

- Transport occurrence IDs and write times are distinct from selected-view temporal semantics. V3 does not ignore valid/transaction/scenario/snapshot identity; its skipped-work basis and current eligibility are checked separately under G978 and TC-01. S02 persists the admitted source and its lineage/accounting; only redundant evaluation computation is skipped.
- Q1's codec roster is one candidate manifest, not a limit on mandatory state, Foundry, cache, schema, reader and installed companions. Rebind the mismatched Foundry patch under a new identity before testing it.
- Three parallel interface packets are preparation under already selected G contracts, not newly ratified semantics or runtime evidence: CAN resource budgets, TC/closure owners, and B09 basis/store/history. Root serializes common Core, generation-cycle, DTO, schema/generator and lock mutations.
- Preserve the existing S3 pytest node name while widening its body to the paired unit-channel witness. First-wave patches and passing focused tests do not close whole tasks or findings automatically.
- These statuses describe the assessed a92 source cut. Subsequent implementation commits and native receipts are recorded separately; current dirty postimages do not silently upgrade this table.
