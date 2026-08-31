# DS10 Capability-Discovery Debt Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adjudicate all twelve Task-C debt rows from current repository evidence, implement only real producer/bridge closures, and preserve every still-valid DS10 refusal as an explicit typed limitation.

**Architecture:** Reuse the existing six-kind owner-index federation and governed-projection service. Each positive closure must traverse the named producer, typed artifact or receipt, runtime bridge, consumer, and semantic test; an execution projection, world-model lookup, tuple stamp, or internal review posture may not substitute for the missing discovery or authority object. Rows that cannot cross that chain remain open with a measured missing-capability label and an exact closure probe; no adjacent object is promoted under P38 or ratified `W5-K01`.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, FastAPI runtime services, repository AST/JSON/TOML census scripts, and Playwright only for the permitted C13 receipt reissue.

**Spec:** `docs/plans/active/atlas-slices/DS10-capability-discovery.md`, the Task-C execution brief dated 2026-08-30, `docs/system-design-decisions/wave5-evidence-substitution-ratification.md` (`W5-K01`), and `docs/reference/policy-design-case-failure-patterns.md` (`P38`).

## Global Constraints

- Work only on attached branch `codex/debt-c-ds10-capability-discovery` in the existing worktree; never rebase, create another branch, force-push, or use a stash as storage.
- Do not edit `docs/plans/active/DEBT-REGISTER.md`, `docs/plans/active/LEDGER.md`, `docs/plans/active/layer3-slices/GY-engine-subordination.md`, `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`, or `tools/quality/validation/check_debt_ledger.py`.
- Do not edit anything below `apps/runtime-dashboard`; the Lex row is adjudicated by source/selection measurement and C13 may consume two no-writer Playwright outputs only.
- `src/polisyos/runtime/quality/promotion_sequence.py` belongs to task A and is excluded.
- In `src/polisyos/runtime/http/dependencies.py`, make at most one additive block and record its exact lines for hand-back.
- In `tests/unit/runtime/http/test_public_export.py`, append only `test_public_decision_projection_is_custody_bound`; do not restructure shared fixtures. If the file is absent on this base, create only the minimal test module required for that node and record the cross-branch creation overlap with task D.
- Temporary red probes for a row that remains open are removed before commit. Keeping a knowingly failing closure test would misstate the repository gate; the dossier retains the red receipt and the register correctly retains the unwritten closing artifact.
- Run only exact nodes and importer/blast-radius tests. Directory-wide and full-suite runs are forbidden.
- Before every commit run `git status -sb` and require the attached branch name.

## Pattern Pass

| Pattern | Existing risk in this cluster | Correct pattern | Acceptance signal |
| --- | --- | --- | --- |
| `P38`, `W5-K01` | execution/family booleans, tuple membership, world lookup, and reviewer posture can look adjacent to the missing producer | name the property, name the actual predicate, and preserve the divergent case; only owner-indexed, content-bound evidence may close | every positive row crosses its named real producer; every absent producer stays typed and open |
| `P01`/`P02`/`P12` | contract or provider port without producer/artifact/orchestration | producer → artifact/receipt → bridge → consumer → semantic test | exact named node passes through production path, not a direct DTO or fixture-only provider |
| `P03` | internal richness without API/audit projection | expose only already-custodied core; otherwise `surface_missing` or `surface_out_of_scope` | public/export test proves custody, or row stays open and task G remainder is named |
| `P04`/`P05`/`P09`/`P15` | discovery posture can be laundered into authority | independent execution and authority arms remain fail-closed | search/availability/review status alone cannot publish or admit authority |
| `P29`/`P32`/`P33` | marker tests or self-attested receipts can turn green without the property | run real path, bind content, verify provenance, and include a sibling falsifier | corrupt/missing/wrong-owner input stays red |
| `P35`/`P37` | stale denominator or declared completeness can decide a row | complete tracked-set walks and predicate-provenance labels | current denominator and each load-bearing predicate are recorded with command and exit |
| `P40`/`P41` | repeat repairs or inherited reds can be misowned | bucket same-class findings and replay from slice base when ownership matters | repeat P38 examples fold into the declared limitation; inherited reds are named, not repaired |

## Entry Control

- [x] **Step 1: Verify the worktree attachment and base**

  Run: `git status -sb && git symbolic-ref -q HEAD && git rev-parse HEAD`

  Observed: clean `codex/debt-c-ds10-capability-discovery` at `784d020148c56e9bfb3a3631909ba11232210a9f`.

- [x] **Step 2: Read the twelve register rows and governing records in full**

  Read the complete row text at register lines 235–243, 269, 274, and 374, plus `CONTRIBUTING.md`, `W5-K01`, and the failure/repair register before planning.

- [x] **Step 3: Recompute the anchor denominator before row work**

  Run the complete tracked-file AST walk and the independent `git ls-tree`/`git ls-files` counts. Observed control:

  ```text
  tracked_src_python_files=2611
  production_implementations=0
  protocol_declarations=2
  admission_rows=61
  admission_states={'admitted': 8, 'blocked': 1, 'candidate_shadow_only': 52}
  resource_kind/capability_purpose/passport_receipt/evidence_receipt/
  currentness_receipt/capability_discovery_provider key counts = 0 each
  ```

  The 2,611 file denominator disagrees with the recorded 2,579 by +32; this was reported before any row adjudication. The zero implementation and 61-row substance controls agree.

---

### Task 1: Freeze Baselines and Exact Red-Probe Discipline

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-c-ds10-capability-discovery.md`
- Temporary test edits only at the exact row identities listed in Tasks 2–4

**Interfaces:**
- Consumes: the twelve register closure signals and the current 2,611/0/61 control
- Produces: one command/result record per row and a stable before/after gate baseline

- [x] **Step 1: Finish the uv-bound debt-ledger baseline**

  Run: `PYTHONPATH=. uv run --extra test python tools/quality/validation/check_debt_ledger.py --check`

  Observed: exit 1 after roughly six minutes with 18 unresolved open-test identities and zero host-unknown collections. This is the known checker defect and cannot decide a row.

- [x] **Step 2: Record the docs-lifecycle baseline**

  Run: `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py`

  Expected baseline: exit 1 with exactly six findings (two `active_plan_metadata`, four `removed_stub_reference`).

- [x] **Step 3: Apply the same red-first lifecycle to each unwritten node**

  Add the exact node, make it exercise the real named path, and run it once. If it fails because the named producer/artifact/bridge is absent, record the failure and remove the temporary test before commit. If the real chain exists or can be wired within owned paths, keep the test and implement the minimal bridge until green.

### Task 2: Adapter and Owner-Index Producer Rows

**Files:**
- Create only on a positive closure: `tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py`
- Create only on a positive closure: `tests/unit/runtime/quality/test_adapter_registry_free_growth.py`
- Modify only on a positive closure: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify: `tests/unit/runtime/quality/test_capability_discovery.py`

**Interfaces:**
- Consumes: Layer-3 adapter admission registries, `CapabilityIndex`, owner receipts, and `CapabilityDiscoveryComposer`
- Produces: either a real owner-index provider/receipt bridge or a measured `producer_missing`/`artifact_missing` refusal

- [x] **Step 1: Probe `ds10-adapter-admission-capability-discovery-bridge` at its exact identity**

  Test identity: `tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness`.

  The test must pass a newly admitted row through the real admission builder and require `resource_kind`, capability purpose, passport/evidence/currentness receipts, and a concrete provider. It must reject a bare admitted flag and tuple-membership stamp. Run the exact node with `uv run --extra test pytest ... -q` and preserve open if the complete admission family still lacks those objects.

- [x] **Step 2: Probe `ds10-adapter-registry-data-only-free-growth` at its exact identity**

  Test identity: `tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation`.

  Mutate only the governed adapter contract data in test scratch, run the real post-G0 admission path, and require the new contract to appear without a Python switch. A missing builder or hard-coded owner map is an `open` result with the exact missing producer named, not an ambiguous missing-file result.

- [x] **Step 3: Probe the causal-method bridge**

  Test identity: `tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion`.

  Require the default runtime federation to return owner-indexed method rows plus a content-bound `CapabilityIndexOwnerReceipt`; assert `project_capability_features` booleans cannot satisfy the test. Wire only an existing release `CapabilityIndex` owner; otherwise remove the probe and retain `bridge_missing + semantic_test_missing`.

- [x] **Step 4: Probe owner-signed capability-purpose currentness**

  Test identity: `tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness`.

  Require an independently signed typed capability ref/digest/purpose binding to resolve through the DS9 currentness resolver. Assert a `governed_action_key`, inline self-stamp, and missing binding all remain non-authoritative. If the signed producer does not exist, preserve `bridge_missing + artifact_missing`.

- [x] **Step 5: Probe Layer-3 rejection richness**

  Test identity: `tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness`.

  Walk the complete G2/G3/GL owner set and require real selected/rejected candidates plus typed incompleteness from owner ledgers. Do not synthesize missing rejected rows in DS10. If an owner ledger lacks the facts, retain the typed limitation.

- [x] **Step 6: Run the retained capability-discovery blast radius and commit the coherent producer group**

  Run exact retained nodes plus `tests/unit/runtime/quality/test_capability_discovery.py` only. Before commit require `git status -sb` to show the attached branch.

### Task 3: HTTP, Case, Scientist, Public, and Lex Boundaries

**Files:**
- Modify only on a positive closure: `src/polisyos/runtime/http/services/control/capability_discovery.py`
- Modify only on a positive closure: `src/polisyos/runtime/http/dependencies.py` (one additive block)
- Modify: `tests/unit/runtime/http/test_capability_discovery_api.py`
- Modify: `tests/unit/runtime/http/test_control_api.py`
- Create/append only the named test: `tests/unit/runtime/http/test_public_export.py`
- Modify: `tests/integration/runtime_quality/test_data_state_substrate.py`
- Read only: `apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx`
- Read only: `apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.test.tsx`

**Interfaces:**
- Consumes: real source/connector registries, an appointed global case index if one exists, Scientist NodeRegistry/ToolRegistry snapshots, public custody projection, and fixed Lex trigger/search paths
- Produces: default discovery providers or precise typed refusals without cross-kind substitution

- [x] **Step 1: Probe connector/source production**

  Exact node: `tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed`.

  Require the control API lists to resolve through the installed connector and source-profile registries and bind their snapshots. A static response or fixture registry cannot close the row. If content production belongs to absent DS15 acquisition owners, preserve the limitation and name that producer.

- [x] **Step 2: Probe canonical global case indexing**

  Exact node: `tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index`.

  Require a default `case` provider whose owner is a canonical global index. Run-bound records and human-decision case strings are explicit negative variants. If no appointed index exists, retain `absent/unallocated` and state that task G's `ds8-global-case-index` half still lacks the same appointed producer.

- [x] **Step 3: Probe Scientist agent/tool discovery**

  Exact node: `tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface`.

  Require NodeRegistry/ToolRegistry snapshots, typed `ScientistCapabilityOwnerTruth`, a content-bound owner receipt, and an API-consumed result. Hold L4 entity/data lookup constant as the divergent P38 negative. If no default registry producer exists, retain `producer_missing`.

- [x] **Step 4: Probe public decision custody**

  Exact node: `tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound`.

  Require a public decision projection to resolve a current custody-bound signature and reject internal REVIEWER/EXPERT posture, MACHINE frontier output, and unsigned discovery. If DS12's public producer/promotion gate is absent, remove the red probe, retain `surface_missing`, and state that task G still lacks the signed public-decision surface.

- [x] **Step 5: Resolve the Lex mutation row manually**

  Run `uv run --extra test pytest tests/unit/runtime/http/services/test_lex_pipeline.py -q`. Then enumerate the exact frontend test titles, imports, trigger calls, discovery calls, and click paths from the two read-only Lex files. The property is: discovery rendering never invokes the fixed authenticated Lex mutation. The current implementation predicate is the measured call graph; a title-filter selecting zero tests is not evidence. Record `closed` only if the complete measured discovery interaction is disjoint from every trigger call; otherwise retain `open` and hand the exact frontend test/source change to task D without editing it.

- [x] **Step 6: Run only retained exact nodes and relevant importer tests, then commit**

  If `dependencies.py` changes, record the exact additive line range and include its nearest DI test. Do not run the whole HTTP suite.

### Task 4: Three Governed Projection Sources

**Files:**
- Modify: `src/polisyos/runtime/http/services/governed_projections.py`
- Modify: `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`
- Modify: `tests/unit/runtime/http/test_governed_projection_service.py`
- Modify: `tests/unit/runtime/http/test_governed_projection_validation_worker.py`

**Interfaces:**
- Consumes: canonical source artifacts and owner validators for `generation-cycle-disposition`, `capability-reality`, and `surface-readiness`
- Produces: an available validated projection or a reason-bound, owner-attributed typed unavailability; then a complete 13-projection census

- [x] **Step 1: Investigate `generation-cycle-disposition`**

  Execute the real projection and owner validator. If the source is valid under its declared dependency semantics, correct the validator/bridge and require `available`. Otherwise bind the exact invalid reason and owner lane; do not manufacture OR-Tools or reinterpret a null dependency.

- [x] **Step 2: Investigate `capability-reality`**

  Execute the real capability-ratchet validator against the canonical report. Correct a stale source/ref bridge only if the owner report validates; otherwise preserve `invalid_source` with its exact owner reason.

- [x] **Step 3: Investigate `surface-readiness`**

  Confirm whether a canonical live ledger and registered owner validator exist. The example ledger is never production evidence. If either is absent, preserve `artifact_missing` and bind the owner/reason; if both exist, wire the existing validator.

- [x] **Step 4: Run the exact three nodes plus the availability census**

  Add focused semantic tests that corrupt each source/owner binding and must fail. Recompute all thirteen projection states and record either `13/13 available` or the exact remainder with reason and owner. Close `three-unavailable-governed-producers` when all three investigations are reason-complete, even if an honestly retyped remainder remains.

- [x] **Step 5: Commit the governed-projection group**

  Verify branch attachment before commit and include only the source/worker/focused tests.

### Task 5: C13 Print-Receipt Reissue Without Frontend Writes

**Files:**
- Read only: the complete receipt-defined 11 `source_bindings`, including `apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx`; the fresh census establishes that `apps/runtime-dashboard/src/app/routes/routes.tsx` is not a receipt member and it remains read-only corridor context
- Modify only if the existing reissue tool supports the current source unchanged: the DS6 C13 receipt artifact owned by the independent print-evidence lane
- Test: `architecture/atlas_surfaces/test_frontend_disposition_register.py`

**Interfaces:**
- Consumes: two distinct zero-retry/no-writer Playwright terminal outputs and the complete current 11-binding hash census
- Produces: a current independently bound C13 receipt, or a precise task-D handoff

- [x] **Step 1: Recompute all eleven source hashes**

  Do not trust the historical 2/11 or 6/11 prose. Enumerate the admitted set and print every mismatch with current/expected digest.

- [x] **Step 2: Run two distinct no-writer Playwright executions only if current source can satisfy the receipt**

  Use zero retries and preserve each terminal output independently. If source changes are required, stop this row as `blocked` and hand task D the exact file/line/property change.

- [x] **Step 3: Reissue and verify**

  Run the exact DS6 C13 node and `.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check`. Close only when both exit zero and the complete 11-binding set is current.

- [x] **Step 4: State the overlap precisely**

  Close or block only `ds10-c13-print-receipt-reissue`; task D's `DS11-INHERITED-C13-PRINT-RECEIPT` remains its own row and must separately record inheritance/closure.

### Task 6: Verification, Dossier, and Readback

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-c-ds10-capability-discovery.md`
- Do not modify: all architect-owned register/ledger/plan files

**Interfaces:**
- Consumes: terminal receipts from Tasks 1–5
- Produces: twelve complete closure blocks, arithmetic, overlap handoff, out-of-scope list, and branch readback

- [x] **Step 1: Run targeted Python quality checks**

  Run Ruff only over changed Python files, the exact retained tests, and architecture guardrails if production imports changed. Do not run any directory-wide pytest command.

- [x] **Step 2: Replay the two before/after repository checks**

  Run the debt-ledger check in the same truly uv-bound environment used for baseline. Run docs lifecycle and require the same exact six findings as baseline.

- [x] **Step 3: Re-open the failure/repair register before closeout**

  Confirm no P38/W5-K01 substitution, no contract-only capability claim, and no public/internal authority collapse was introduced.

- [x] **Step 4: Finish the Register closure dossier**

  Append one block per row with verdict (`closed`, `open`, `blocked`, or `ambiguous`), exact deciding command/predicate and exit, and exact supersession prose. Include `12 = closed + open + blocked + ambiguous`, split `9 core + 3 adjacent`, and keep ambiguous at four or fewer.

- [x] **Step 5: Record declared overlaps and out-of-scope findings**

  Name task D's remaining C13 half and task G's remaining case-index/public-decision halves. Name out-of-scope defects without editing them.

- [x] **Step 6: Commit the final dossier and read back branch state**

  Run `git status -sb`, commit the journal/plan closeout, then re-read `git status -sb`, `git log --oneline`, and the committed file set from the attached branch before reporting delivery.

  Observed: the dossier commit was attached to the requested branch, the post-commit tree was clean,
  and committed-file readback returned exactly the plan and journal. The committed dossier parsed as
  12 headings = 1 closed + 10 open + 1 blocked + 0 ambiguous.

## Round 2 — Producer Execution and Terminal Dispositions

Round 1 is the measured starting point. Round 2 supersedes its verdicts append-only; it does not
rewrite the earlier evidence. Every row must terminate `closed` or `blocked`, except an executable
Group-1 row left unfinished because this lane exhausted its own budget, which must be reported
plainly as `open` rather than mis-typed as blocked.

### Round-2 invariants and approved corrections

- Preserve the four P38/W5-K01 boundaries exactly: execution booleans are not owner-indexed method
  rows; `admitted=True` or tuple membership is not capability evidence; L4 world lookup is not
  Scientist agent/tool discovery; internal REVIEWER/EXPERT posture is not public authority.
- Reuse the existing exported `CapabilityIndex` compiler/owner surface. Do not create a parallel
  DS10 index, compile per HTTP request, or promote `project_capability_features` execution facts.
- The owner-purpose row requires the independent signed producer act itself. Independent verification
  is a separate operation. The measured repository is producer-side-signing world: the deployment
  custody signer signs producer-owned canonical bytes and the resolver independently verifies those
  bytes before the DS9 currentness join; no appointed human authority is required.
- The Scientist row closes only if Task C builds a typed NodeRegistry/ToolRegistry discovery
  producer, persisted owner truth and default provider. A census proving absence is only blocker
  evidence. Build lazily and cache the immutable snapshot: eager Scientist discovery executes a
  large Foundry validator during ordinary HTTP startup and is not an acceptable bootstrap cost.
- G2, G3, and every GL ledger produce their own selected/rejected candidates, cutoff facts, and
  typed incompleteness before DS10 projects them. Projection-time invented rejections are forbidden.
- Adapter admission becomes generic/data-driven only after every row preserves its operation
  semantics and passes evidence/currentness verification. TOML membership never admits on its own.
- C13 binds only to D's final dashboard bytes. Recompute the complete 11-path binding set and its
  intersection with D's complete round-1 plus round-2 changed set immediately before capture and
  again before receipt emission. A non-empty intersection while D is still active blocks on
  `task D's round-2 dashboard freeze`; it is not permission to bind an intermediate commit.
- C13 owns append-only new raw-evidence paths, its exact conjunction test, and only the narrow checker
  change required to select the new immutable evidence generation. Existing raw files remain
  byte-identical, no predicate is loosened, and the exact checker diff is included in the hand-back.
  Any DS6 receipt payload edit must name its fields and prove them disjoint from task G's
  621-files/759-roots/126-obligated/126-covered projection before writing.
- The connector successor is not task E. It is an unowned paired persisted connector/source-profile
  snapshot producer, content-bound `SourceProfileOwnerReceipt`, and default discovery provider.
- The public-decision successor is task A's EFFECT resolution followed by a standalone DS12
  promotion/signature/currentness slice. The global-index successor is the first DS12/DS13/DS14
  scope plan that consumes task G's `ds8-global-case-index` obligation from
  `architecture/atlas_surfaces/slice-scope-obligations.json` and appoints the canonical index/store
  producer. Task C does not close either task-G half.
- Write every named test at its exact identity and run it red before product code. After each
  coherent implementation, run only that node plus its direct importer/blast-radius nodes, review,
  commit, and re-read branch attachment. Never run a directory-wide or full suite.

### Round-2 measured controls

- Production census control: 2,611 tracked `src/**/*.py`; 0/2,611 concrete
  `resolve_operation`/`verify_conformance` implementations before this round; 61 Layer-3 admission
  rows = 8 admitted + 52 candidate-shadow-only + 1 blocked, with 0/61 DS10 capability keys.
- Baseline ledger check: project-bound `check_debt_ledger.py --check` exits 1 with exactly 18 blocking
  `closure_signal_identity_unresolvable` findings. Round 2 may remove only its own identities and may
  not grow the blocker set. Docs lifecycle exits 1 with exactly six findings.
- C13 preflight control: the canonical 11 bindings intersect D's committed round-1 dashboard set at
  `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`. D's round-1 head is not a
  round-2 freeze; this intersection must be recomputed against D's final round-2 head.

### Task 7: Corrected Preflight and Successor Blocks

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-c-ds10-capability-discovery.md`
- Read only: D's branch, task G's scope manifest, DS12/DS15 plans, connector/source registries, public
  decision producers, and the canonical C13 disposition receipt

**Interfaces:**
- Consumes: complete producer censuses, D/G branch state, and the exact successor evidence
- Produces: reproducible round-2 control receipts and three concrete `blocked_by` objects

- [ ] **Step 1: Freeze all denominators and searches**

  Record the exact tracked-file, implementation, admission-family, connector/source-profile,
  public-decision, and global-index commands with denominators and zeros. A search-index query or
  sample is not a zero.

- [ ] **Step 2: Recompute C13's eleven-path intersection**

  Enumerate all eleven paths from the receipt, D's complete changed set from the shared base through
  its current head, and the normalized set intersection. Record D's head and task status. This is a
  gate on later capture, not a receipt reissue.

- [ ] **Step 3: Type the three successor rows**

  Bind connector acquisition to the explicitly unowned paired snapshot producer and
  `SourceProfileOwnerReceipt`; public decision to EFFECT plus the standalone DS12 promotion slice;
  and global index to the same first scope-setting plan/object named by task G. Do not retain a red
  closure test for a non-executable successor row.

- [ ] **Step 4: Commit the preflight record and obtain task review**

  Verify branch attachment, commit only the appended plan/journal record, and independently review
  the denominators, intersections, and blocker identities.

### Task 8: Scientist Typed Discovery Surface and Lex Manual Closure

**Files:**
- Modify: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify as needed: `src/polisyos/runtime/quality/data_state_substrate.py`
- Modify as needed: `src/polisyos/runtime/http/services/control_registry_providers.py`
- Modify as an additive block only if required: `src/polisyos/runtime/http/dependencies.py`
- Modify: `tests/integration/runtime_quality/test_data_state_substrate.py`
- Read only: Scientist NodeRegistry/ToolRegistry and the two Lex frontend files

**Interfaces:**
- Consumes: public NodeRegistry snapshots/listing, ToolRegistry definitions, an owned immutable
  artifact store, and the fixed Lex call graph
- Produces: a strict persisted Scientist owner snapshot/receipt, a lazy cached default `agent`
  discovery provider, API-consumable typed results, and a measured manual Lex boundary proof

- [ ] **Step 1: Write and run the exact Scientist red**

  Add
  `tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface`.
  It must require real node/tool-backed typed results and content-bound owner evidence through the
  default path, while holding L4 entity/data lookup constant as a negative. Run that node and record
  the expected producer/default-provider failure before implementation.

- [ ] **Step 2: Build the typed producer and bridge**

  Produce strict node/tool capability records and an immutable persisted snapshot/receipt from the
  public Scientist registries. Resolve it lazily on the first `agent` query and cache it; do not
  import L4 lookup or eagerly execute the expensive Foundry scan at container construction.

- [ ] **Step 3: Prove the Lex manual closure**

  Re-run the complete page/test source census: zero capability-discovery imports/calls, exactly the
  `handleTrigger -> triggerMutation.mutate` and `handleSearch -> searchMutation.mutate` paths, and
  distinct buttons. Run the three exact backend Lex tests. Explain why the implementation call graph
  establishes disjointness even though Vitest title selection is unsupported by design.

- [ ] **Step 4: Verify, review, and commit**

  Run the Scientist exact node, its direct discovery/API importer node if changed, the exact Lex
  backend nodes, focused Ruff, and architecture imports if production wiring changed. Commit only
  after an independent task review approves the real producer and P38 negatives.

### Task 9: Default Causal-Method CapabilityIndex Provider

**Files:**
- Modify: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify as needed: `src/polisyos/runtime/quality/capability_index.py`
- Modify as needed: `src/polisyos/runtime/http/services/control_registry_providers.py`
- Modify: `tests/unit/runtime/quality/test_capability_discovery.py`

**Interfaces:**
- Consumes: persisted/current `CapabilityIndex` owner rows compiled from Foundry method contracts
- Produces: a default method discovery provider that projects owner-indexed rows without execution
  promotion or per-request compilation

- [ ] **Step 1: Write and run the exact red**

  Add
  `tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion`.
  Require owner identity, operation rows, provenance/currentness, and a negative case where adjacent
  execution booleans stay true but no owner row exists.

- [ ] **Step 2: Bridge the existing index owner**

  Load or receive the immutable compiled index once, validate its owner receipt/currentness, and
  project only its method rows. Never consult `project_capability_features` as a substitute.

- [ ] **Step 3: Verify, review, and commit**

  Run the exact node plus direct compiler/discovery importer nodes, focused Ruff, and architecture
  imports. Commit after independent review confirms no parallel index or request-time compiler.

### Task 10: Producer-Signed Capability-Purpose Binding

**Files:**
- Modify: `src/polisyos/runtime/quality/capability_authority.py`
- Modify as needed: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify as needed: `src/polisyos/runtime/http/services/control_registry_providers.py`
- Modify: `tests/unit/runtime/quality/test_capability_authority.py`
- Modify: `tests/unit/runtime/quality/test_capability_discovery.py`

**Interfaces:**
- Consumes: strict capability identity/purpose bytes, the deployment custody signer/verifier, a
  content-addressed artifact store, and sealed DS9 currentness
- Produces: the independent producer signature, persisted binding artifact/manifest, strict resolver,
  and verified authority-purpose/currentness join

- [ ] **Step 1: Write and run the exact red**

  Add
  `tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness`.
  It must fail without an actual producer signature and reject an inline digest, self-attestation,
  wrong signer identity, byte tamper, purpose mismatch, stale DS9 packet, and verification without
  the signing act.

- [ ] **Step 2: Build signing, persistence, resolution, and join**

  Canonicalize and persist the binding, have the producer sign the exact content/manifest using the
  runtime custody key, independently verify trust/identity/coordinates/expiry, and only then join the
  DS9 resolver's current packet. Keep signature and verification as distinct evidence.

- [ ] **Step 3: Verify, review, and commit**

  Run the exact node plus direct authority/signing/currentness importer nodes, focused Ruff, and
  architecture imports. Commit after independent review confirms this is producer-side signing
  world and no appointed-human placeholder was smuggled in.

### Task 11: Owner-Produced Layer-3 Rejection Richness

**Files:**
- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Modify: `src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py`
- Modify: `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py`
- Modify: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify: the three mirrored focused unit-test files
- Modify: `tests/unit/runtime/quality/test_capability_discovery.py`

**Interfaces:**
- Consumes: each G2/G3/GL owner's real candidate evaluation and search cutoff
- Produces: owner-emitted selected/rejected candidates, requested/evaluated/cutoff facts, typed
  completeness/status/reasons, then a lossless DS10 projection

- [ ] **Step 1: Write and run the exact aggregate red**

  Add
  `tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness`.
  Exercise one G2, one G3, and every GL ledger; require rejected candidates and honest incomplete
  status from the native owner rather than a DS10 reconstruction.

- [ ] **Step 2: Extend each native producer before the projection**

  Add typed richness to the owner ledger/build result and compute it at the point candidates are
  accepted/rejected/cut off. Adapt DS10 only after all three owner families expose the same semantic
  minimum; preserve family-specific reasons.

- [ ] **Step 3: Verify, review, and commit**

  Run the aggregate node and the exact G2/G3/GL focused tests, focused Ruff, and architecture imports.
  Commit after independent review walks all nine owner ledgers and proves DS10 invents no facts.

### Task 12: Generic Verified Adapter Admission and Data-Only Growth

**Files:**
- Modify: `src/polisyos/runtime/quality/adapter_contracts.py`
- Modify as needed: owned `src/polisyos/runtime/quality/proving_ground/**`
- Modify as needed: `src/polisyos/runtime/quality/capability_discovery.py`
- Create: `tests/unit/runtime/quality/test_adapter_registry_free_growth.py`
- Create: `tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py`
- Modify only focused existing adapter/proving-ground tests that mirror changed owners

**Interfaces:**
- Consumes: one semantically preserved operation contract per adapter row, producer evidence,
  passport, authority purpose, and currentness
- Produces: generic admitted adapter records and discovery results with no name-specific code path;
  a new valid contract row reaches admission through data-only mutation

- [ ] **Step 1: Write and run both exact reds in order**

  First add
  `tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation`;
  run it red on the name-specific/static registry. Then add
  `tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness`;
  run it red on missing capability evidence. The mutation is a temporary contract-data fixture, not
  a production TOML edit.

- [ ] **Step 2: Generalize the contract-row producer**

  Parse and verify every row generically, preserve operation semantics, fail closed on missing or
  stale evidence, and emit the typed discovery payload. Prove tuple membership and `admitted=True`
  remain insufficient by themselves. Do not add blanket `resolve_operation` or
  `verify_conformance` stamps.

- [ ] **Step 3: Verify, review, and commit**

  Run both exact nodes plus only direct existing adapter/proving-ground importer nodes, focused Ruff,
  and architecture imports. Recompute 2,611 implementation and 61-row admission denominators, then
  commit after independent review confirms data-only free growth and semantic preservation.

### Task 13: C13 Final-Byte Capture and Receipt Reissue

**Files:**
- Append only: `docs/plans/active/atlas-slices/receipts/ds6-c13-raw/**`
- Modify conditionally and only within the C13 marker payload:
  `docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md`
- Modify narrowly: `architecture/atlas_surfaces/check_frontend_disposition_register.py`
- Append exact conjunction only: `architecture/atlas_surfaces/test_frontend_disposition_register.py`
- Read only: all eleven dashboard bindings and every other atlas-surface file

**Interfaces:**
- Consumes: D's frozen final dashboard tree, two distinct zero-retry/no-writer Playwright captures,
  immutable raw evidence, and an eleven-binding hash census
- Produces: a reissued current C13 receipt and green conjunction/global gate, or a concrete freeze
  block with all preparatory evidence preserved

- [ ] **Step 1: Recheck D freeze and exact set intersection**

  Enumerate the eleven paths and D's complete changed set at its current head. If they intersect and
  D is still active, do not emit a supposedly final receipt; name the intersecting paths and
  `blocked_by: task D's round-2 dashboard freeze`. Continue with every safe preparatory step that can
  bind to immutable evidence without claiming finality.

- [ ] **Step 2: Prove G disjointness before any payload edit**

  Name the exact C13 fields to change: capture output/digest references, command/environment,
  `raw_artifacts`, `evidence_revision`, `verified_revision`, `source_bindings`, receipt identity and
  digest. Compare those marker-local fields and changed paths with G's final projection set. Any
  overlap stops the payload edit and preserves G's closure.

- [ ] **Step 3: Capture twice without writers**

  Against D's final bytes, run two distinct Playwright executions with retries zero and snapshot
  updating disabled. Require all three governed titles in each output and prove the tracked dashboard
  diff and governed snapshot bytes are unchanged. Append only new run/environment artifacts; never
  rewrite the historical evidence generation.

- [ ] **Step 4: Reissue and verify**

  Red-first add the exact C13 conjunction node named by the register, then make the narrow generation
  selection/binding change. Run that exact node and
  `.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check`.
  Close only on two valid captures, 11/11 current bindings, and both exits zero. Print the exact
  checker diff in the dossier. If finality is blocked, retain only honest preparatory artifacts/tests
  that do not pretend an intermediate D head is current.

- [ ] **Step 5: Review and commit**

  Independently review immutability of every historical raw file, no dashboard writes, G disjointness,
  exact predicate strength, and the D-overlap statement before committing.

### Task 14: Round-2 Verification, Dossier, and Branch Readback

**Files:**
- Modify append-only: `docs/superpowers/journals/2026-08-30-debt-c-ds10-capability-discovery.md`
- Do not modify: every architect-owned register/ledger/master-plan/denominator file

**Interfaces:**
- Consumes: reviewed commits and terminal receipts from Tasks 7–13
- Produces: twelve supersession blocks, measured arithmetic, overlap handoffs, checker delta, and
  committed branch readback

- [ ] **Step 1: Run targeted closeout only**

  Run each retained exact closure node, focused importer nodes for changed modules, focused Ruff,
  architecture guardrails, the project-bound debt checker, docs lifecycle, and any changed
  architecture checker. Do not run a directory or full suite. Confirm the ledger blocker set did not
  grow and docs lifecycle remains exactly six findings.

- [ ] **Step 2: Re-open the failure/repair register**

  Audit P01/P02/P29/P32/P37/P38/P41 and W5-K01 against the implementation, including the four exact
  non-substitution boundaries and negative tests.

- [ ] **Step 3: Append all twelve dossier blocks**

  Every block states verdict, exact deciding command/predicate and exit, and exact supersession prose.
  Include `12 = closed + blocked + unfinished`, core 9 versus adjacent 3; the complete C13 11-path
  census/intersection/D head; producer-side-signing evidence; Scientist producer or complete block
  census; each successor object; Lex's manual proof; D/G overlap residues; the unowned connector
  producer; and any out-of-scope finding.

- [ ] **Step 4: Freeze, independently review, commit, and read back**

  Freeze source, obtain final branch review, batch only blocking fixes, run the expensive targeted
  wave once after the last fix, verify branch attachment, commit the dossier, then read the attached
  branch's status, log, committed file set, and dossier arithmetic before hand-back.
