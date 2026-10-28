# E02 dependency and parallelism analysis

Status: planning recommendation, read-only source analysis. This report does not authorize execution, accept source, or close a finding.

The continuation should use a graph of work units and evidence seams, rather than serialize the original task queue. The strongest immediate source blocker is G27-01. Its fixture/proof work, B13 invalidation research, N7 diagnosis, cache lifetime work, lease-capacity test preparation, checkpoint/vector reviews, CAN/TC work, and the R1/I2 diagnoses can proceed independently. Serialize actual shared mechanisms and their mandatory companions when composing source; do not serialize their research or every task carrying the same old dependency label.

## Evidence boundary

The only checkout used was `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, attached to `codex/e02-unified-local-20261009`. Entry and source readback matched HEAD `ad81c5b826bdfdda6aa2295b8641e9ae2a68b21a`, tree `df24ff6ff12e7039c0cbfbd47abc8bee82f5332e`. The current owner paths in the source table below were individually compared with HEAD and had no tracked differences. Mixed untracked material was preserved and was not treated as a runtime dependency by default.

No product/test source, index, ref, HEAD, environment, or production data was changed. No tests, application imports, builds, installs, workers, browser, payload census, or heavy checks were run. JSON parsing, Git metadata reads, and bounded source reads establish this report's facts; they establish no fresh runtime pass. The sole authored file is this report.

Paths below use `P = policy-engine/`. Handoff aliases are:

- **H:** `P/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/executor-handover-20261027/`; read `START-HERE.md`, `remaining-work.md`, `canonical-task-bindings.json`, and `proposal-index.json`.
- **D:** `P/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/task-status-detailed-20261027/`; `PLAN.md` and `tasks.json` describe the older a92 source assessment, with later deltas qualified by H.
- **G:** `P/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-review-followup-20261027/`; the authority for review routing is `dispositions.json#/items`, by G27 finding ID.
- **W:** `P/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/remaining19-detail-20261027-r1/`; reports under W retain their own older source cuts and are inputs, not a current-source verdict.

Root `AGENTS.md`, `P/CONTRIBUTING.md`, and the failure/repair register were read. The complete `tasks` array in `P/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json` and the complete H binding rows were parsed: each has 26 rows. This is a task-manifest JSON denominator, not a new code or finding census. Finding/occurrence quantities remain the manifest's declared denominator; this report does not re-adjudicate them.

## What the original dependency graph actually says

This is the complete grouping of the original `depends` edges, reproduced from the complete task array. An edge is preserved as an original planning fact; it is not automatically an instruction to delay every phase until the whole upstream row closes.

| Original prerequisite | Original downstream rows | Correct phase interpretation for continuation |
| --- | --- | --- |
| BOOT0 | Every other original row | `source` / `input` admission for research, edits and proof. The pinned checkout is already admitted for this analysis; continued execution must read back its actual state. |
| Q1 | R1, R2, R3, V1, V5, V6, Q2 | Selected source/owner identity is a `source` prerequisite. CAN .3 changes create affected contract and proof dependencies; they do not make all current .2 research wait for full Q1 completion. |
| R1 | R2, V6 | Preserve relevant runtime/cache/serialization proof when composing affected source. R2's accepted defining property and V6's new fixture/identity research are not blocked by every unresolved R1 occurrence. |
| R2 | I3 | `contract` / `source` cleanup and restart invariant. G27-06 reports the defining property satisfied on candidate `65ac853`; the four packet role labels are corrected, while later current-source deltas need separate affected-path qualification (see `analysis/runtime-routes.md`). This provenance update is not an I3 implementation prerequisite. |
| I1 | I4 | Serving/currentness `contract` and selected owner basis. G27-03 accepts the bounded bridge while retaining separate whole-LA-041 proof obligations. I4 fixture preparation need not wait for those unrelated checkpoint nodes. |
| S1 | S2, S3, V2, V3, V4, V7 | Relevant subject/source/unit/uncertainty `contract` at composition and final acceptance. Independent owner research, test preparation, direct bounded paths and source-gap diagnosis can start now. |
| T1 | T2 | Authority/input inventory at admission. Legitimate configured fixtures can test the contract; actual production rights, issuer, currentness and calibration facts remain separate input requirements. |

Q0, DX0 and DEC0 have no additional original task prerequisite. Their final acceptance can still depend on the composed candidate and affected evidence.

## Challenged edges and current source facts

**R1 does not have a semantic I2 prerequisite.** D/PLAN.md says both “root schedules them after I2” and “remaining four contour groups serially after I2.” Original R1 depends only on BOOT0/Q1. W/R1/report.json names runtime context, retry and runner serialization as the changed readset; I2 measures DFK references and installed CLI/archive discovery. Current `schema_fqn_census.py:1049` selects tracked, untracked and changed Git paths and binds their bytes. Therefore I2's final census needs a stable census denominator, while R1 needs its own stable source/test/input readset. Their diagnostic research is independent. Native slots, disk, or a concurrent mutable source readset can justify scheduling one after the other; “I2 must finish first” is not a demonstrated contract dependency.

**TC does not wait for CAN .3.** W/interface-freeze-preparation/tc/tc-interface-freeze-r2/interface-freeze.md, “Frozen ownership and sequencing,” explicitly permits the request artifact to use accepted Core .2. Current `common/canonical.py:50` still defaults to .2; current `NaturalLanguageRunRequest` is at `core/contracts/control.py:758`; `job_attempt_publication.py:57-104` admits v1/v2 snapshots. T-A request work and T-B closure/resolver work can be prepared independently under the selected TC-01 contract. T-C requires both. The shared Core manifest companion is a real schema/composition lease with CAN; full .3 writer enablement is not a prerequisite to TC authorship or a .2 request witness.

**G27-01 and B13 invalidation are separate obligations sharing a consumer.** Current `debug.py:384-427,2683-2691` still compares the result binding without profile, while the existing `manifest.py:303-318` identity owner includes ID, kind, media and profile. G27-01 can reuse that owner without waiting for CAN .3 or inventing a new ref DTO. G27-02's invalidation property is not supplied by this identity fix. W/g27-feedback/b13-basis-oracle/b13-basis-oracle.md proposes reuse of `SourceInvalidationEvent`, durable persistence/readback, and a bridge to fresh result serving. Current `research_dag/invalidation.py:23-177` has the typed event and DAG/ledger propagation; its source-node match is ID-based and its inspected functions do not supply the proposed run-result durable bridge. Treat that bridge as `artifact_missing`, `bridge_missing`, `consumer_missing`, and `semantic_test_missing` pending owner selection and implementation. One debug consumer writer can compose both changes, but an invalidation-engine project must not be inferred from G27-01.

**N7 is shared by V4/V7, not a substitute for I4's original LA-046 occurrences.** H records the four IR callsite changes as already preserved; D's earlier “repair CanonSpec first” description is stale for that bounded delta. The current blocking route still goes through `tests/_helpers/acquisition_production.py:368-434`, which requires a real producer-emitted route report. The live executor's `acquisition_surface_execution.py:261-280` requires the exact L1 data-snapshot variable route. Current `generation_cycle.py:17905-17935` chooses terminal kind using both grounding and value acquisition requirements. This is one route/producer projection seam for V4/V7. Their direct predictive CAS paths can be checked independently of the served route fixture, while the served predictive witness waits for the actual N7 route chain. G27-04 keeps both original LA-046 occurrences separate from N7 acquisition work.

**R3 and R4 share composition context, not one semantic prerequisite.** Current factory `create_traced_gateway_client` creates the cache wrapper and Core settlement session at `llm/factory.py:149-260`; ordinary NL calls at `nl_pipeline.py:475,8266` still construct clients. `prompt_cache.py:368` mutates settlement hooks on the wrapper. W/execution-wave2/r3-cache-bridge/author-20261027-08/candidate/handover-correction.md clarifies that R3 has the lifecycle lease it needs and identifies exact cache-client/session/origin lifetime plus request-local hooks as the structural stop condition. Separately, current `resilience.py:363-395` injects the same shared executor into CAS and control-store guards; `control_worker.py:189-224` ends its lease pulse on dependency failure; `compute/runner.py:1964` dispatches compute to the shared executor. These observations support a shared-capacity falsifier, not attribution of the historical errors or a proved production defect. If R4's minimal fix stays in the existing guard owner and its tests, it can remain disjoint from R3 edits. Only an actual lifecycle/container change needs the common R3 composition lease.

## Proposed work-unit edges

These are recommendations, not newly ratified contracts. Types describe why an edge exists. Phase identifies where it binds; work in earlier independent phases can proceed.

| From → to | Type | Binding phase | Readiness/acceptance condition |
| --- | --- | --- | --- |
| Exact source and selected proposal bytes → each author/reviewer | `source`, `input` | research; edit | Bind preimages and issued patch/report identity. H/proposal-index states application/review status; an old path alone is not an issued version. |
| G27-01 r5 fixture review → A/A valid fixture → old-product A/B red | `proof`, `input` | testing | The current A/A fixture fails before the target. Reach the intended boundary before interpreting a red as the identity defect. |
| Existing complete-ref owner → G27-01 consumer repair → both fresh selectors/removal probe | `source`, `contract`, `proof` | edit; testing | G27-01: exact profile/presence conflicts, explicit ID and default-from-state served paths. Keep original source failure demonstrated. |
| B13 persisted basis/event contract → debug currentness bridge → fresh invalidation refusal | `contract`, `source`, `proof` | research; edit; testing | G27-02: actual persisted lineage/event, nonmatching-event control, preserved independent result/history. Retained-ref removal is a separate missing test. |
| G27-01 and G27-02 changes → composed V6 result consumer | `composition`, `shared-resource` | edit; testing | One `debug.py` writer; shared integration fixtures assigned once. Research and test design remain parallel; source acceptance and whole-B13 acceptance remain distinct. |
| I1 r4 and I4 r2 independent reviews → selected native tests | `proof`, `input` | testing | G27-03's checkpoint/recovery matrix and G27-04's deterministic flat NPZ/HNSW migration have separate predicates. Correct I4's encoder-count assertion first. Neither needs model redownload or N7 repair. |
| N7 actual route diagnosis/producer projection → V4/V7 served changed-outcome witness | `source`, `input`, `proof` | edit; testing | Preserve grounding and live-route guards; do not manufacture a planner record. Use one V4/V7 mechanism writer plus helper/test companions. |
| V1 controlled-root helper admission → V1 positive → V2 selected positives | `input`, `proof`, `shared-resource` | testing | Cheap root falsifier first, then first unknown-cost V1 alone, then V2's serial nodes. This orders fixture admission and resource measurement, not V2 research. |
| Selected G978 basis semantics + TC exact-view law → V3 retention/reissue composition | `contract`, `composition` | edit; final acceptance | Prepare pure basis work now; actual retained evaluation must reconcile source admission, semantic basis, current eligibility and persisted action/history. Shared cycle/lifecycle paths need composition with N7/TC/R3, not whole-queue waiting. |
| R3 exact cache/session owner + request-local hooks → ordinary second-POST reuse/fresh ledger/API | `contract`, `source`, `proof` | edit; testing | The author06 candidate is unapplied/static NO-GO. Temporary self-owned CAS/current local owner is a valid software input; production source permission is not inferred. |
| R4 synchronized cap-one witness → structural guard change if red → fencing/terminal proof | `proof`, `source` | testing; edit; testing | Show real occupied compute/queue and renewal before release; use actual persisted owner/attempt/expiry. Existing B56 acceptance remains intact; no numerical rerun for arithmetic. |
| R3/R4 actual overlapping paths → composed control lifetime | `composition`, `shared-resource` | edit; affected testing | Share lifecycle/container only if touched; `resilience.py`-only capacity work need not wait for R3 semantic completion. Keep cache settlement and compute scheduling as distinct owners. |
| Relevant S1 source/request/array/unit contract → S3 full B31 and affected scientific consumers | `contract`, `input`, `proof` | edit; testing; final acceptance | S3 e22/8020 bounded receipts are preserved; do not rerun unchanged repairs by HEAD alone. S1's explicit API candidate path is not the missing automatic funnel relation. |
| S2 actual relation owner/consumer selection → persisted effective-N bridge | `input`, `contract` | research; edit | W/S2/report.json S2-W1 is ready independently; S2-W2 waits for a genuine relation owner and real consumer. Neighbor checks can proceed separately. |
| T1 inventory + controlled current-owner inputs → T2 U1-U5 | `input`, `contract`, `proof` | edit; testing | Exercise valid fixture positives plus forged/stale/revoked negatives. Actual institutional facts stay `not_established` until supplied and admitted; they do not block generic software tests. |
| Accepted R2 cleanup invariant → I3 cursor/event work | `contract`, `source` | edit; testing | Preserve accepted R2 source paths. B79/B80 product r7d and test r8b must be reviewed together; B83 key/grain/version and independent-process horizon proof are separate. Shared streaming-oracle test writes have one owner. |
| CAN C-A API/readers/resource admission → C-B/C-C state/Foundry/cache consumers | `contract`, `schema`, `source` | edit; testing | Prepare consumer analysis in parallel; compose after C-A interface freeze. Rebind mismatched Foundry identity. Do not enable .3 on a projection/materialization proxy. |
| TC T-A + TC T-B/Core companion → T-C producer/actual temporal consumer/closure | `contract`, `schema`, `composition` | edit; testing | T-A/T-B may use accepted .2. Shared Core manifest/export/write-contract/IR-adapter companions get one writer; reader-first rollout before new writers. |
| Final public DTO/route/manifest changes → canonical generated family | `schema`, `source`, `composition` | edit; testing | Q2 owns generation from real source, then client/dashboard validators and launch producers. Group all affected public deltas once; do not repeatedly regenerate against moving DTOs. |
| Frozen sources + generated outputs + locks/build inputs → exact installed consumers | `input`, `proof`, `shared-resource` | testing; final acceptance | Q2-C, DX0 assets and I2 installed/archive obligations share a package/build lease. One exact prepared manifest; serial source-wheel, rebuilt-sdist and rebuilt-GCP-archive consumers. |
| Stable I2 Git-visible text denominator → final census → discovered-input round trips | `source`, `input`, `proof` | testing | Diagnostic profiling is independent of R1. Round-trip only actual discovered historical inputs; absence outside scanner selection stays unresolved. |
| Per-occurrence owner outcomes → Q0 whole reconciliation → G review/integration | `proof`, `composition` | final acceptance | Q0 research/rebinding proceeds continuously. Only final global claim waits for exact current occurrence evidence and composed source. G remains acceptance/closure owner. |

## Writer and companion leases

Root remains the canonical writer and publisher. A remote or local author produces a proposal on its admitted immutable source; it does not silently acquire the canonical checkout. One writer covers a mechanism and all mandatory companions. The lease includes tests, release fragments, relevant registries/exports, public/generated outputs, measurement/status records and source manifests when forced by that mechanism. Those companions are outside any mechanism path-count cap (P39).

Recommended contention boundaries:

| Lease | Shared mechanism/companions | Can proceed independently |
| --- | --- | --- |
| Result read identity/currentness | `runtime/http/services/debug.py`, debug unit fixtures, V6 integration fixture; existing complete-ref and invalidation owner companions | G27-01 fixture review; B13 durable-event/lineage research; retained-ref test design |
| Generation-cycle/acquisition basis | `runtime/quality/generation_cycle.py`, acquisition helper, V4/V7 route fixtures; coordinate V3 basis work and R3 B10 witness if they require source edits | Direct predictive CAS tests; V1 controlled-root helper work; B10 test-only preparation on frozen source |
| Controlled candidate substrate | `tests/_helpers/candidate_cycle_source_profile.py`, served-history/recursive fixtures used by V1/V2/V3 | N7 source diagnosis; scientific relation work |
| Cache/session lifetime | R3 container, lifecycle, NL pipeline, factory, prompt-cache/traced settlement seam and ordinary-route integration test | R4 event test and guard-owner proposal; C07 first phase avoids lifecycle writes; its actual ordinary-request transport is a later C05/root composition dependency, not established disjoint by author08 |
| Control service capacity | `runtime/http/resilience.py`, existing worker/store/shared-executor companions; broaden lease only if actual lifecycle/container change is necessary | Cache owner analysis and disjoint R3 source work |
| Scientific source bindings | S1 `uncertainty.py`/`hte_source_projection.py` and its outbox test; single shared B31/S3 witness | V5 typed source-profile/metric proposal review; S2 relation-owner research; separate finite G528 route |
| Fabric progress/key/replay | I3 modes/ingestion/orchestrator/export companions and one streaming-oracle test owner | B79/B80 binding and B83 key/horizon research; maintain R2 cleanup invariants |
| Core/IR persistence and authority contracts | CAN codecs/profile/store/readers, Core manifest/export/write contract, IR adapter, TC closure companion and authority resolver | TC request intent preparation; state/Foundry/cache consumer analysis |
| Public/generated/package family | Core request/response DTOs, OpenAPI exporter/contract fixture, generated client/dashboard types, validators/launch producers/locales if rendered, relevant locks/build manifests | Domain test design and source-only review. Dependency changes require the single lock owner; unrelated authors must not regenerate locks. |

These are contention boundaries, not permanent organizational silos. When a proposal changes the boundary, publish the additional paths before application. Do not reserve an entire task's transitive future work when only one file is contended.

## Launch front, readiness waves and critical paths

**Launch front — recommendation:** admit standalone packets for G27-01 r5 review/fixture, B13 existing-owner bridge design, N7 route diagnosis, R3 cache/session/hook repair design, R4 event-driven capacity test, I1/I4 partial-review completion, V5 r13 independent review, S1 request/source/array relation, I3 key/progress work, CAN resource/reader work and TC request/closure work. R1 child startup/deadline diagnosis and I2 bounded Git-enumeration diagnosis can launch alongside them. Q0 per-occurrence research and surgical R2/R4 documentation corrections need no native wave. No packet may treat the old proposal index or author-complete label as current proof.

**Source/proof wave:** after independent proposal review and exact preimage readback, root composes only the leased mechanisms. Freeze each bounded readset before its targeted witness; unrelated research continues. G27-01's valid fixture and intended old-product red precede repair. I1/I4 deterministic witnesses, existing direct predictive paths, and independent scientific/Fabric controls can be scheduled when their own inputs are ready. Global source freeze is not a prerequisite for every bounded test; it is required for the final composed expensive wave.

**Final family wave:** compose all public/Core/IR/TC/V3 changes that affect the generated family, freeze source and finish reviews, batch blocking fixes, freeze selected profiles and inputs, then generate once and run affected semantic/drift/corruption checks. Refresh exact package manifests and perform the installed/native closeout wave once under the common build lease. Continue Q0 reconciliation from actual receipts and route a source-bound proposal to G. G's affected replay on integrated source is a different receipt.

There is no justified single elapsed-time critical path from these documents. The following prerequisite chains can independently determine finish readiness:

1. **V6 source acceptance:** valid A/A fixture → intended profile-conflict red → complete identity repair/review → both fresh served selectors and property-removal control → G27-01 source-acceptance request. Whole B13 additionally needs persisted exact-basis invalidation and retained-ref removal, not just this chain.
2. **Served predictive/source route:** actual N7 gap/report projection → strict live route → V4/V7 ordinary producer/CAS/reopen/fresh changed-outcome consumer. The preserved IR callsite repair is an input, not work to repeat.
3. **Exact-view/public persistence:** CAN C-A and TC T-A/T-B prepared in parallel → shared Core companion/readers → consumer/closure/state/Foundry/cache composition and V3's affected basis → canonical generated family → exact installed consumers/DX0 companions → current Q0/G package.
4. **Control lifetime:** R3 cache/session/request-hook owner → ordinary second POST and reopened accounting; independently, cap-one guarded-control witness → capacity fix if demonstrated → expiry/fencing/terminal custody. Shared application paths are composed before affected runtime proof.
5. **Scientific/authority inputs:** S1 actual source/request relation, S2 relation evidence, and T2 current-owner facts → their real fresh consumers. Code cannot create missing institutional facts; final scope may remain explicitly limited where the original criterion permits it.

## Cloud, local and hybrid concurrency

Cloud tasks should be standalone. Each task receives the exact published commit/tree, selected patch/report identities, selected decisions, original criterion IDs, allowed mechanism/companion paths, portable fixtures, expected falsifiers, output identity, and stopping rule before launch. It must finish with a self-contained proposal or evidence packet. Do not depend on useful mid-run messaging, a shared mutable RAW directory, or a later clarification from another running cloud task.

| Phase | Cloud | Local | Hybrid rule |
| --- | --- | --- | --- |
| Analysis | Independent owner/source reviews, dependency challenges, proposed tests, semantic falsifiers, Q0 occurrence research and CAN/TC interface work can run concurrently on published source. | Inspect preserved untracked proposal/review bytes and local owner/environment facts; decide what sanitized context to publish. | Missing RAW report bytes are not inherently private runtime inputs. Publish a sanitized factual summary with source/finding IDs, exact limitations and available hashes when sufficient. An absolute `/Users/...` locator alone does not prove private bytes are needed. |
| Editing | Independent authors may prepare disjoint proposals on the same published base. One author owns each mechanism plus its companions; overlapping family proposals require an agreed interface and later composition. | Root performs canonical readback/application, resolves overlap and preserves append-only history. Local authoring can own mechanisms requiring unpublished local facts. | A cloud patch is candidate output. Check exact preimages and imported companions, independently review, compose, then rebind affected proof. No parallel canonical writers. |
| Compute/testing | Portable controlled CAS/SQLite/checkpoint/array fixtures can support separate source-bound jobs after locked runtime/platform admission. Linux-specific I2 evidence may be collected on a genuinely supported Linux environment. | Retained native/backend/environment facts, private read-only owner inputs and tests whose platform contract is local remain local. | Ship only published bytes and portable sanitized fixtures. Do not upload production data, existing CAS, credentials, environments, or recovery payloads. Record platform/backend differences; a portable pass is not automatically the original native/installed acceptance. |
| Final acceptance | Independent reviews and portable affected witnesses can arrive as immutable packets. | Root freezes the composed candidate, profiles, selected inputs and build manifests; G accepts/integrates/updates findings. | Final generated/package consumers bind one exact composition, not a collection of passing jobs on different bases. |

Keep local compute admission separate from agent concurrency. The inherited local plan admits at most two **measured native jobs** with combined measured RSS at most 4 GiB and one numerical thread each; first unknown V1/V2, native GP and VM jobs run alone. Preserve the 6 GiB floor and R1's larger 8 GiB reserve. These are source-qualified planning limits from D/PLAN.md and G/PLAN.md, not fresh resource measurements. They do not limit read-only research agents. No current disk or cloud capacity was measured by this report.

For a future cloud worker described as roughly 32 GB disk, measure actual free bytes/inodes, source checkout size, locked environment/build-cache footprint, scratch outputs and required reserve before admitting compute. A nominal disk size is not a usable-space receipt. Use the existing locked recipes and one build environment per actual need; do not assume all local runtime profiles fit or make copies to create apparent isolation. Bound concurrent cloud compute from those measurements independently of local memory limits. A cloud analysis packet needs no compute reservation merely because it analyzes a native task.

## Pattern pass and acceptance limits

- **P01/P02/P03:** TC and B13 are not made real by contract prose. Preserve exact missing-state labels and require producer → persisted artifact/event → bridge → fresh consumer/surface → semantic negative. Current generic surfaces do not prove a new consumer bridge.
- **P31/P32/P33/P40:** G27-01 is the complete-view identity class; G27-02 is the separate basis-validity class. R3 cache session/hook escapes are the same cache provenance/lifetime class, not another per-call patch. Name the class before repair; on a second same-class escape widen the actual owner or declare/run a bounded residual. A fixture red before the intended seam is not the target falsifier.
- **P35/P36:** historical task reports retain their original cut; G facts are cited by G27 ID. The task graph was reproduced from the complete task JSON, not a sampled summary. This report makes no repository-wide absence or runtime-success claim.
- **P37/P38:** source/preimage equality was recomputed for the listed paths. Runtime readiness, current resources and unrun proposal behavior remain `not_established`; do not turn them green using an author label, file path, configured cap, timeout signal or profile marker. An independent task can start from sufficient published context without copying private payloads.
- **P39/P41:** budget the mechanism separately from forced companions. Preserve deciding outputs; do not call any red inherited without exact slice-base replay and zero complete-input intersection. No such isolation or exclusion was performed here.

The acceptance signal for this planning report is a phase-qualified edge with an identified property, owner/input, actual contention boundary and deciding proof. It is not completion of any E02 capability, source acceptance or G finding closure.

## Current source identities used for the challenged edges

These exact tracked blobs were read in the pinned checkout and compared with HEAD. The table is the declared inspected set; it is not a complete repository dependency closure.

| Current source pointer | Relevant seam |
| --- | --- |
| `P/src/polisyos/runtime/http/services/debug.py@fed9ff4d8dd328ec606943d46c47fad49cb26c42:384` and `:2683` | G27-01 node/state comparison and existing result consumer |
| `P/src/polisyos/core/artifacts/manifest.py@f1b3372d9e209cf823bacf7dc38eecd76b6780bb:183` and `:303` | Legacy closure companion and complete ArtifactRef identity owner |
| `P/src/polisyos/scientist/methods/research_dag/invalidation.py@c178be78a6cecca72da59ea5254b6f1c9d1a349e:23` | B13 existing typed event/propagation owner |
| `P/src/polisyos/runtime/http/resilience.py@57c3236ced6a25a2233e364fe4802f5cf4e04f93:125` and `:363` | Guard failure mapping and shared executor injection |
| `P/src/polisyos/runtime/http/services/control_worker.py@9584c2a30ef59cd0dbdfdad1186bc0d2c9032c6f:189` | Actual lease-pulse failure path |
| `P/src/polisyos/runtime/http/services/control/run_lifecycle.py@5bc7b95cb714e687d38cccecea7877a43ce347ed:3916` | Shared control lifecycle/composition owner |
| `P/src/polisyos/runtime/http/services/control/nl_pipeline.py@bd8f8a135e91089b610bd7e12d39c39c917ddfc6:475` and `:8266` | Ordinary NL client factory boundaries |
| `P/src/polisyos/scientist/orchestration/llm/factory.py@2a21661d9b9646923db4d035a11910e79950aa00:149` | Cache wrapper/session construction |
| `P/src/polisyos/scientist/orchestration/llm/prompt_cache.py@a862b9792a31055ee8781006ef3160fec6e21b61:123` and `:368` | Existing authorizer and mutable settlement-hook seam |
| `P/src/polisyos/runtime/quality/generation_cycle.py@96d52206572235131fc4d6cc2270f3b04dd740cc:12245` and `:17905` | Grounding selection and acquisition terminal decision |
| `P/tests/_helpers/acquisition_production.py@832f4889db1c7f1245458602156e644f113862a9:368` | Actual N7 producer/report fixture seam |
| `P/src/polisyos/runtime/http/services/acquisition_surface_execution.py@a066a6d2d88d4835cb5f1a59f57b70161565e4e7:261` | Strict live variable route predicate |
| `P/src/polisyos/common/canonical.py@25fa43311ba8a04a25845a1863898399a7eed958:50` | Current explicit .2 codec default |
| `P/src/polisyos/core/contracts/control.py@cae2159ef38cb696a04d6ee052439b57c6e45a50:758` | Existing NL request owner |
| `P/src/polisyos/runtime/http/services/control/job_attempt_publication.py@e1cbef9c0ed423618406b132110a57b9389c6d8e:57` | Current v1/v2 durable request versions |
| `P/src/polisyos/runtime/quality/authority.py@a939aea459c68762df5d2983c4f22f5a44cd4b8c:1101` | Existing legacy same-input closure owner |
| `P/src/polisyos/fabric/data_plane/modes.py@a2abe40720dfffe429d0416598ad0df95946dd65:563` | I3 confirmed-cursor no-op boundary |
| `P/src/polisyos/fabric/ingestion/ingestion.py@9c0d33cf03e42de296390473ee1b1583ffb1876a` and `P/src/polisyos/fabric/data_plane/orchestrator.py@c49acc073d1a82a458826a9467aa035b1d5837b8:410` | I3 progress/persistence companion owners |
| `P/tools/quality/validation/schema_fqn_census.py@247f7d3517146a04bf908b6167e835f020f6c9b9:1049` | I2 actual Git-visible text/input denominator |
| `P/architecture/generated_artifacts.toml@9d1dc33bcd848e52feb98fb970ac40081d9019be:732`, `:799`, `:869` | Canonical OpenAPI → client → dashboard source/generated family |


## Coordinator reconciliation after independent critique

The author08 correction establishes R3 lease availability, not S1 transport independence. First-wave C07 is explicitly narrowed to uncertainty/projection/outbox owner and exact unapplied caller-transport proposal. Its ordinary explicit POST/fresh-consumer application waits for the shared lifecycle source returned by C05/root; earlier-funnel binding remains a separate missing bridge. Owner/oracle preparation remains parallel. C09 edits acquisition_production.py, which V1 imports: record the module readset and requalify V1 after composition, without inventing a shared writer or making isolated research wait. All public schema/generated/lock family applications have one later root-selected writer; independent authors return mandatory companion proposals.
