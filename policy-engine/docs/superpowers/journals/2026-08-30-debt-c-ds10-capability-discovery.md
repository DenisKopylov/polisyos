# Task C — DS10 capability discovery closure journal

Date: 2026-08-30
Branch: `codex/debt-c-ds10-capability-discovery`
Entry commit: `784d020148c56e9bfb3a3631909ba11232210a9f`

## Entry and governing evidence

- Worktree attachment: `git status -sb`, `git symbolic-ref -q HEAD`, and `git rev-parse HEAD` all completed exit 0. The tree was clean and attached to the requested branch.
- Read in full before planning: all twelve `DEBT-REGISTER.md` rows at lines 235–243, 269, 274, and 374; `CONTRIBUTING.md`; the P01–P41 failure/repair table including P38; `wave5-evidence-substitution-ratification.md` including ratified `W5-K01`; and the DS10 active plan's explicit non-closures.
- `uv sync --frozen` completed exit 0 and created the worktree-local environment.

## Anchor control — disagreement reported before row work

The requested 2,579-file denominator does not hold at this branch tip. A complete AST walk over the tracked set and two independent tracked-path counts agree on **2,611 unique `src/**/*.py` paths**:

```text
git ls-files -- 'src/**/*.py' | wc -l                                      -> 2611
git ls-tree -r --name-only HEAD -- src | awk '/\.py$/ {count++} END ...'  -> 2611
git ls-files -- 'src/**/*.py' | sort -u | wc -l                            -> 2611
```

The AST walk completed exit 0 after about 64 seconds and found:

```text
tracked_src_python_files=2611
production_implementations=0
protocol_declarations=2
protocol_declaration=src/polisyos/runtime/quality/capability_resolver.py:162:CapabilityLiveOperationRegistry.resolve_operation
protocol_declaration=src/polisyos/runtime/quality/capability_resolver.py:170:CapabilityConformanceVerifier.verify_conformance
admission_rows=61
admission_states={'admitted': 8, 'blocked': 1, 'candidate_shadow_only': 52}
admission_prohibited_key_counts={
  'resource_kind': 0,
  'capability_purpose': 0,
  'passport_receipt': 0,
  'evidence_receipt': 0,
  'currentness_receipt': 0,
  'capability_discovery_provider': 0,
}
```

Control disposition: the path denominator is **2,611, not 2,579 (+32)**. The substantive anchor agrees: **0 concrete implementations / 2,611 tracked Python paths**, plus two Protocol declarations; **61 admission rows**; zero occurrences of each named DS10 capability key/provider in those 61 rows.

## Baselines

- `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` completed exit 0 but reported `closure_signal_collection_host_unknown=32` and `pytest is unavailable`; this is an explicit non-receipt and will not be used as evidence.
- `PYTHONPATH=. uv run --extra test python tools/quality/validation/check_debt_ledger.py --check` completed exit 1 after roughly six minutes. It reported `closure_signal_identity_unresolvable=18`, `closure_signal_collection_host_unknown=0`, and the matching 18 informational count/exit disagreements. Eight unresolved identities are this task's DS10 pytest nodes; the other ten are the registered DS11/decision-validity peers. This is the known `debt-closure-signals-name-unwritten-tests` checker defect and is baseline evidence only, not a verdict for any row.
- `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` completed exit 1 with exactly six findings: two `active_plan_metadata` findings for architect-owned `LEDGER.md`, and four `removed_stub_reference` findings. This is the required before-state.

## Pattern stance

- P38 property: a capability-discovery row is produced by its named owner index with content-bound receipt/provenance; execution availability, an admitted adapter identity, world-model lookup, or review posture is not that property.
- Current implementation predicate: DS10 composes installed finite-kind providers and reports `producer_missing` for absent kinds; the adapter operation/conformance ports have only Protocol declarations.
- Divergent cases held fixed: execution may be available while no method row exists; a bridge adapter may be admitted while no DS10 kind/purpose/receipt/provider exists; L4 lookup may return world data while no Scientist agent/tool index exists; an internal reviewer result may exist while public custody authority is absent.
- `W5-K01` consequence: more same-stream rows do not establish a missing object. Those four divergent cases cannot close their rows.

## Row ledger (initial state, not verdicts)

| row | exact probe or deciding predicate |
| --- | --- |
| `ds10-adapter-admission-capability-discovery-bridge` | exact named pytest node through real admission builder; reject admitted-flag/tuple substitutes |
| `ds10-lex-pipeline-mutation-boundary` | backend file plus complete read-only frontend call-graph/title measurement; zero-selected title is not evidence |
| `ds10-causal-method-index-provider-bridge` | exact named node requires default owner-index method rows and content-bound receipt |
| `ds10-owner-signed-capability-purpose-binding` | exact named node requires independent signed ref/digest/purpose joined to DS9 currentness |
| `ds10-connector-acquisition-content` | exact named control-API node requires real connector/source-profile producer snapshots |
| `ds10-public-decision-rendering` | exact named public-export node requires custody-bound public decision, not internal posture |
| `ds10-global-case-index-producer-allocation` | exact named API node requires appointed canonical global index; run-bound case strings are negative |
| `ds10-world-agent-capability-discovery-boundary` | exact named integration node requires Scientist registry snapshots; L4 lookup is negative |
| `ds10-layer3-owner-ledger-rejection-richness` | exact named node walks complete G2/G3/GL owners and forbids synthesized rejections |
| `three-unavailable-governed-producers` | investigate all three sources and recompute the complete 13-projection availability/reason census |
| `ds10-adapter-registry-data-only-free-growth` | exact named node mutates governed contract data and runs real post-G0 admission |
| `ds10-c13-print-receipt-reissue` | complete current 11-binding hash census plus two distinct zero-retry/no-writer outputs; no frontend source writes |

## C13 currentness investigation

The complete receipt-defined set is eleven paths. Its current-byte census completed exit 0 with **5/11 current and 6/11 stale**:

```text
stale  AmbientTelemetryHud.tsx    232392b0... -> a06e6a98...
stale  OperatorCraftPanel.tsx     687a831d... -> 8d94ade6...
stale  RunDetailLayout.tsx        514ddff6... -> f4533fee...
stale  RunReportPage.tsx          4bb0bea6... -> 5f51a10e...
stale  RunReportPage.test.tsx     d3b5819e... -> 30023d27...
stale  runtime-dashboard.visual.spec.ts
                                  c472f411... -> 3a69dd55...
```

The other five bindings match. `apps/runtime-dashboard/src/app/routes/routes.tsx` is not a member of the receipt's declared `source_bindings`. The supplied two-binding premise therefore disagrees both with the register's existing 6/11 subject sweep and with this fresh 6/11 census.

The exact admission test:

```text
uv run --extra test pytest architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q
```

completed exit 1 at the first stale whole-file binding. The authorized run-one browser command then used `CI=1`, `PLAYWRIGHT_RETRIES=0`, `--workers=1`, `--retries=0`, `--update-snapshots=none`, the exact `DS8 governed run paper` grep, and scratch-only JSON/output paths. It completed exit 1 before selecting a test:

```text
expected=0 skipped=0 unexpected=0 flaky=0
TypeError: Module ".../src/shared/i18n/locales/en.json" needs an import attribute of "type: json"
Error: No tests found
```

Before and after that no-writer attempt, the environment tuple digest was identically `867883c4c6ab6fb16d7b6c2a5e06599c0772df05593b08d4da1d549a9f998c23`; the governed snapshot remained SHA-256 `26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a`, 19,197 bytes; and `git diff --exit-code -- apps/runtime-dashboard` completed exit 0. A second expensive run cannot create an independent passing receipt after the first run selected zero tests, so the row stops as `blocked` under the frontend-corridor rule.

### C13 review correction — exact Task D handoff

The immediate source repair belongs to Task D at `apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx:25-26`: make both static locale imports Node 22 ESM JSON imports by appending `with { type: "json" }` to the `en.json` and `uk.json` import declarations. TypeScript 5.7 under this app's `module: "ESNext"`, `moduleResolution: "Bundler"`, and `resolveJsonModule: true` accepts that exact syntax in a no-write `transpileModule` probe (exit 0, no diagnostics). The acceptance signal is not the syntax probe: the exact `DS8 governed run paper` Playwright selection must collect and pass all 3 tests twice, each with exit 0, zero retries, `--update-snapshots=none`, distinct raw output, and an unchanged governed snapshot. Task D must then rebind the six stale members so the complete C13 census reads 11/11 current and replay the exact C13 admission node. This handoff does not close Task D's separate `DS11-INHERITED-C13-PRINT-RECEIPT` row.

## Closeout verification

- The exact retained blast radius completed exit 0 with **9/9 tests passed**: all three backend
  Lex tests, the typed missing-owner API test, both connector/profile list tests, and three focused
  capability-discovery boundary tests for Scientist ownership, missing case production, and owner
  frontier facts. No directory-wide or full-suite test command was run.
- `PYTHONPATH=. uv run --extra test python tools/quality/validation/check_debt_ledger.py --check`
  completed exit 1 with the same **18 unresolved identities**, **0 host-unknown collections**, zero
  input-unresolvable/selects-nothing/collection-failed findings, and the same 18 count/exit
  disagreements as the entry baseline. The only changed path inside the checker's plan inventory is
  this Task-C plan: its filename adds an already-present `DS10` set member and it contains no
  `## Explicit non-closure` section. The journal is outside that input set. The measured before/after
  equality therefore assigns no new checker finding to Task C.
- `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` completed exit 1
  with the same **6 findings = 2 active-plan metadata + 4 removed-stub references** as the entry
  baseline.
- There are no retained Python, TypeScript, test, runtime, or architect-owned changes, so Ruff,
  architecture guardrails, and a frontend build would exercise no changed mechanism and were not run.

## Register closure dossier

No architect-owned register file was edited. The blocks below are the exact append-only
handoff for the architect.

### `ds10-adapter-admission-capability-discovery-bridge`

- Verdict: `open` — `producer_missing + artifact_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness -q` completed exit 1. The real `_adapter_admissions(...)` path returned an admitted `AdapterAdmissionRecord`, then the probe failed because it has no `resource_kind`; purpose, passport/evidence/currentness receipts, and a provider are absent too. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `producer_missing + artifact_missing`.** A fresh complete control counts 2,611 tracked `src/**/*.py` files, not the inherited 2,579, and still finds zero concrete `resolve_operation`/`verify_conformance` implementations. The 61-row admission family still carries zero DS10 capability-kind, purpose, passport/evidence/currentness receipt, or provider fields. The exact red probe reached `_adapter_admissions(...)`: an admitted record has no `resource_kind`. Admission and tuple conformance remain explicit P38/W5-K01 negatives; close only through an owner-produced typed discovery artifact and bridge.

### `ds10-lex-pipeline-mutation-boundary`

- Verdict: `open` — `semantic_test_missing`.
- Deciding command/predicate: `uv run --extra test pytest tests/unit/runtime/http/services/test_lex_pipeline.py -q` completed exit 0 with 3/3 tests passed. A complete TypeScript AST/source walk of the 717-line page and 230-line test completed exit 0: zero capability imports/calls; `triggerMutation.mutate` occurs only in `handleTrigger` and the Launch button; `searchMutation.mutate` occurs only in `handleSearch` and the Enter/Search paths. The two real Vitest titles do not exercise discovery while asserting trigger-zero.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `semantic_test_missing`.** The backend Lex facade remains 3/3 green, and the complete frontend call graph keeps search and authenticated trigger mutations disjoint. That source argument is not the missing semantic witness: neither existing Vitest title exercises Enter/Search while requiring `useLexTriggerMock` to have zero calls. Task D must append that focused test in `LexKnowledgeGraphPage.test.tsx`; no Lex source defect or mutation widening is established, and a zero-selection title filter remains a non-receipt.

### `ds10-causal-method-index-provider-bridge`

- Verdict: `open` — `bridge_missing + semantic_test_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion -q` completed exit 1 with `StopIteration`: `resolve_control_registry_providers()` supplied no default capability-discovery provider or `CapabilityIndexOwnerReceipt`. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `bridge_missing + semantic_test_missing`.** The exact default-bootstrap probe finds no method provider and no content-bound `CapabilityIndexOwnerReceipt`; the default provider tuple is empty. `project_capability_features` availability booleans were held as the P38 negative and cannot become owner-indexed method rows. The foundry/methods release owner still owes the default provider bridge and exact semantic witness.

### `ds10-owner-signed-capability-purpose-binding`

- Verdict: `open` — `bridge_missing + artifact_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness -q` completed exit 1: a receipt-shaped ref/digest/purpose/consumer/audience/signature/expiry claim resolved `bridge_missing`, not `admitted_authority`. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `bridge_missing + artifact_missing`.** The authority resolver still has no positive owner-binding producer or DS9 currentness join. Even a complete receipt-shaped claim remains `bridge_missing`; `governed_action_key`, an inline self-stamp, and a missing binding remain non-authoritative. Close only through an independently signed typed capability-purpose artifact and its currentness-resolver bridge.

### `ds10-connector-acquisition-content`

- Verdict: `open` — `producer_missing + artifact_missing + bridge_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed -q` completed exit 1. The two real list endpoints returned HTTP 200, but the default source discovery returned `source:producer_missing`, no results, and no `SourceProfileOwnerReceipt`. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `producer_missing + artifact_missing + bridge_missing`.** The control lists genuinely enumerate the default Fabric connector/profile registries, but they expose in-memory DTOs, not a paired persisted snapshot or owner receipt. Default source discovery returns `source:producer_missing` and no result, and production has no `SourceProfileOwnerReceipt` constructor/provider. DS15/team-fabric still owns the acquisition-content snapshot producer; DS10 must not promote list availability into discovery evidence.

### `ds10-public-decision-rendering`

- Verdict: `open` — `surface_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound -q` completed exit 1. The real compiler kept REVIEWER, MACHINE, unsigned-discovery, and purported current-signature candidates `public_export_status == "blocked"`; no current custody-bound published projection exists. The temporary absent-at-entry test file was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `surface_missing`.** The real compiler correctly keeps internal REVIEWER/MACHINE and unsigned discovery candidates blocked, but no DS12 producer resolves a current custody-bound signature into a persisted public decision projection. Public-looking compiler output is still a candidate, not custody or publication authority. Task G retains `ds8-signed-public-decision-surface`: it still needs the DS12 promotion/signature/currentness producer and signed public surface.

### `ds10-global-case-index-producer-allocation`

- Verdict: `open` — `absent/unallocated`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index -q` completed exit 1. Default ordinary/run-bound and human-decision case queries both returned HTTP 200 with no results and `case:producer_missing`; no canonical owner result exists. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `absent/unallocated`.** Default case discovery has no case receipt type, provider, appointed owner, or canonical index and returns `case:producer_missing`. Run-bound records and human-decision `case_id` strings were exercised as explicit P38 negatives and remain scoped bindings, not a global index. Task G's `ds8-global-case-index` half still lacks the same appointed canonical producer and content-bound provider; DS10 creates no competing store.

### `ds10-world-agent-capability-discovery-boundary`

- Verdict: `open` — `producer_missing`.
- Deciding command: `uv run --extra test pytest tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface -q` completed exit 1 after the corrected normal application lifespan. Real `NodeRegistry` and `ToolRegistry` instances existed, but the API returned no results and `agent:producer_missing`; the L4 lookup phrase did not change that result. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `producer_missing`.** Live Scientist NodeRegistry/ToolRegistry execution objects still have no persisted dual snapshot, `ScientistCapabilityOwnerTruth`, `ScientistRegistryOwnerReceipt`, or default API-installed agent provider. The exact lifespan-bound API probe returns `agent:producer_missing`. L4 `agent_registry_full` entity/data lookup remains the W5-K01 divergent negative and cannot supply Scientist discovery.

### `ds10-layer3-owner-ledger-rejection-richness`

- Verdict: `open` — `producer_missing + bridge_missing`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness -q` completed exit 1 against a test-only composite root with the owner data linked read-only. All real builders completed; the assertion named missing selected/rejected/incompleteness facts in `G2[0]`, `G3[0]`, and `GL[0..6]`. The temporary red test was removed. The earlier worktree-data failure is excluded as a non-receipt.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `producer_missing + bridge_missing`.** A corrected complete G2/G3/GL owner walk used the appointed read-only data root and reached all nine native ledgers. G2 lacks nonempty selected/rejected candidates and typed incompleteness; G3 has a selected candidate but no rejection/incompleteness receipt; seven GL ledgers use `selected_row_refs`/`candidate_rows` and expose neither rejected candidates nor typed incompleteness. DS10 still refuses to synthesize those facts. `artifact_missing` is expressly withdrawn because the corrected run reached the owner artifacts.

### `three-unavailable-governed-producers`

- Verdict: `closed` — reason-complete retyping, not 13/13 availability.
- Deciding predicate: at the actual worktree root, with `/Users/deniskopylov/polisyos/policy-engine/production_data` linked read-only under a validated cleanup trap, `GovernedProjectionService(Path.cwd()).get(...)` was evaluated for every inherited Task-C `ProjectionId` except later `acquisition-growth`. The process completed exit 0 with `13 projections = 7 available + 5 invalid_source + 1 artifact_missing`; cleanup `test ! -e production_data && test ! -L production_data` completed exit 0. The three row members were `0 available + 2 invalid_source + 1 artifact_missing`.
- Exact prose to append:

> **TASK-C CLOSURE 2026-08-31 — `closed` as a reason-complete investigation.** The current enum has 14 IDs; the inherited 13-ID population excludes later available `acquisition-growth`. A stable actual-root census completed exit 0 as `13 projections = 7 available + 5 invalid_source + 1 artifact_missing`. The three named members are now owner/reason-bound: `generation-cycle-disposition` is `invalid_source` because team-runtime-quality's declared validator reports `owner_validator_dependency_missing_ortools_sat_python_cp_model`; `capability-reality` is `invalid_source` because its owner report reports `capability_repo_ref_anchor_missing` and `capability_repo_ref_file_missing` and needs reissue; `surface-readiness` is `artifact_missing` because the live ledger is absent and the owner validator is unregistered. No solver, example ledger, or adjacent artifact was substituted. This closes the investigation with an exact remainder, not with 13/13 green.

### `ds10-adapter-registry-data-only-free-growth`

- Verdict: `open` — `producer_missing`; no longer `ambiguous`.
- Deciding command: `uv run --extra test pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q` completed exit 1. The real loader read an otherwise valid appended TOML row, but the status stayed `fail` because the new ID is absent from fixed Python tuple `G3_ADAPTER_PATH_IDS`. The temporary red test was removed.
- Exact prose to append:

> **TASK-C RECHECK 2026-08-31 — `open`, `producer_missing`; ambiguity resolved.** The exact witness now exists as a measured temporary red: a data-only, otherwise valid adapter-contract row is read by the real loader but rejected as unknown because admission is gated by fixed Python tuple `G3_ADAPTER_PATH_IDS`. Treating TOML membership alone as owner authority would be P37/P38 trust-by-form, so this slice does not delete the gate. Close only with a data-driven post-G0 owner admission producer and independent semantic verification.

### `ds10-c13-print-receipt-reissue`

- Verdict: `blocked` — `verification_missing`, frontend-corridor handoff required.
- Deciding commands: `uv run --extra test pytest architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q` completed exit 1 on stale source bytes. The authorized zero-retry/no-writer Playwright command with grep `DS8 governed run paper`, `--workers=1`, `--retries=0`, `--update-snapshots=none`, and scratch-only output completed exit 1 with zero selected tests because Node rejected `LocaleProvider.tsx`'s JSON import, then reported `No tests found`. The dashboard diff remained empty and the governed snapshot hash/size did not change.
- Exact prose to append:

> **TASK-C HANDOFF 2026-08-31 — `blocked`, `verification_missing`.** The complete current receipt set is `11 bindings = 5 current + 6 stale`; `apps/runtime-dashboard/src/app/routes/routes.tsx` is not a member. The exact C13 node fails on stale bytes, and the first authorized zero-retry/no-writer run selects zero tests because Node 22 rejects the locale JSON import. Task D must change `apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx:25-26` so both static JSON imports use `with { type: "json" }`, then obtain two distinct 3/3 passing no-writer outputs, keep the governed snapshot unchanged, rebind all six stale members to reach 11/11 current, and replay C13. Task D's separate `DS11-INHERITED-C13-PRINT-RECEIPT` half remains open until it records its own inheritance/closure.

## Dossier arithmetic

- All measured rows: **12 rows = 1 closed + 10 open + 1 blocked + 0 ambiguous**.
- Core DS10 limitations: **9 core rows = 0 closed + 9 open + 0 blocked + 0 ambiguous**.
- Adjacent rows: **3 adjacent rows = 1 closed + 1 open + 1 blocked + 0 ambiguous**.

The stop threshold was not approached: **0/12 measured rows are ambiguous**. An unwritten
closure test was treated as the artifact closing work must create, not as ambiguity; each of the
eight absent core Python identities, plus the adjacent data-only identity, was written and run red
at its exact name before removal.

## Anchor denominator and admission control

- Tracked Python population: **2,611 unique tracked `src/**/*.py` paths**, measured independently
  by `git ls-files`, `git ls-tree`, and the AST walker; inherited prose says 2,579, a difference of
  **32 tracked Python paths**.
- Concrete production implementations: **0 concrete implementations / 2,611 tracked Python
  paths**. Two Protocol declarations are not implementations.
- Layer-3 admission population: **61 admission rows = 8 admitted + 52 candidate-shadow-only + 1
  blocked**. Across all 61 rows, each of the six DS10 capability keys/provider counts is 0/61.

## Declared overlap handoff

- Task D / `DS11-INHERITED-C13-PRINT-RECEIPT`: still lacks a Node-loadable exact visual selection,
  two distinct passing zero-retry/no-writer outputs, 11/11 current source bindings, and its own
  inheritance/closure record. Task C changed no dashboard source and did not close D's half.
- Task G / `ds8-global-case-index`: still lacks an appointed canonical global-index owner, the
  durable index/snapshot, a content-bound case owner receipt/provider, and an API-consumed result.
  Task C kept run-bound and human-decision case IDs non-substitutable.
- Task G / `ds8-signed-public-decision-surface`: still lacks the DS12 current-signature promotion
  producer, persisted custody-bound decision artifact, and signed public projection/surface. Task C
  kept internal posture, MACHINE output, and compiler candidates non-authoritative.

## Out-of-scope findings, not acted on

- The task's C13 premise names two stale bindings including `routes.tsx`; the canonical receipt set
  instead has six stale members and excludes that file. Only the Task-C dossier/handoff was corrected.
- Current `ProjectionId` has **14 enum members**, while the inherited governed-projection debt
  population has **13 members** and excludes later available `acquisition-growth`; no catalog was
  rewritten.
- Three projections outside `three-unavailable-governed-producers` — `depth-n-cycle-board`,
  `value-gate`, and `acquisition-routing-contract` — also report the declared missing OR-Tools
  validator dependency in the stable census; no environment or owner contract was changed.
- The truly uv-bound debt-ledger checker still reports **18/18 closure identities unresolved** at
  exit 1 under the known unwritten-test checker defect. The unbound exit-0 run remains a non-receipt.
- Docs lifecycle remains the inherited **6 findings = 2 active-plan metadata + 4 removed-stub
  references**; architect-owned lifecycle documents were not changed.

## Round-2 corrected preflight — 2026-08-31

This is an append-only control record for round 2. It replays the deciding sets before any new
producer is written. The four P38/W5-K01 refusals remain fixed: execution availability is not a
method-owner row; admission/TOML membership is not capability evidence; L4 world lookup is not
Scientist agent/tool discovery; and internal REVIEWER/EXPERT posture is not public authority.

### Complete denominators and absence controls

The tracked production denominator remains **2,611 `src/**/*.py` files**. The complete AST walk
recorded above remains current because this branch's merge base has not moved; its exact command
and output are **0 concrete `resolve_operation`/`verify_conformance` implementations / 2,611**, two
Protocol declarations, and **61 admission rows = 8 admitted + 52 candidate-shadow-only + 1
blocked**, with 0/61 DS10 capability kind, purpose, passport/evidence/currentness receipt, or
provider fields. A replayed path census, `git ls-files -- 'src/**/*.py' | wc -l`, completed exit 0
with 2,611.

For the successor rows, complete tracked searches were run over the same 2,611-file source
population. `git grep -n -i -E 'global.?case.?index|canonical.?case.?index' -- 'src/**/*.py'`
completed exit 1 with zero matches; the corresponding public projection search for
`PublicDecisionProjection|SignedPublicDecisionProjection` also completed exit 1 with zero matches.
The narrower connector/runtime family contains **406 tracked Python files**; the full source
search finds `SourceProfileOwnerReceipt` only as DS10's type/validator declaration and has no
constructor, persisted paired connector/source-profile snapshot producer, or default source
provider. These are censuses of a missing producer, not a license to promote list DTOs.

The owner-signed capability-purpose row is in the producer-side-signing world, not an
appointment-bound signing world. `src/polisyos/runtime/http/deployment_security.py:463-571` loads a
deployment-owned `Ed25519Signer`, strict `Ed25519Verifier`, and producer identity; the replayed
excerpt command completed exit 0. `src/polisyos/runtime/http/services/human_decisions.py:2112-2183`
then persists bytes, signs them with that custody key, and independently verifies the resulting
signature and identity (exit 0). The future DS10 binding must reuse that producer act and only
then join DS9 currentness; verification alone remains an explicit non-substitute.

### C13 binding intersection — a freeze gate, not a closure

The canonical receipt parser completed exit 0 with **11/11 source bindings**:

1. `apps/runtime-dashboard/src/styles/print.css`
2. `apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx`
3. `apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx`
4. `apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx`
5. `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`
6. `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.parity.test.tsx`
7. `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx`
8. `apps/runtime-dashboard/src/features/runs/route.tsx`
9. `apps/runtime-dashboard/e2e/helpers/pdfGeometry.ts`
10. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
11. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/run-report-identity-a4-print-chromium-darwin.png`

The reproduced command was a receipt JSON parse plus
`git -C /Users/deniskopylov/polisyos/.worktrees/debt-d-ds11-trust-posture diff --name-only
784d020148c56e9bfb3a3631909ba11232210a9f..HEAD`, followed by normalization that removes the
repository `policy-engine/` prefix and exact set intersection. It completed exit 0 at Task D head
`0fdd402f6259365f62cd1c62f58119317853cb6d`: **20 changed paths from base, 9 dashboard paths, and
1/11 C13 intersection** —
`apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`. Task D's worktree was clean
at measurement, but its round-2 journal expressly says that it will commit/read back one immutable
dashboard freeze before this receipt is reissued. Therefore clean is not a freeze; C13's current
gate is **Task D's round-2 dashboard freeze at its final head**, naming that intersecting path.
No C13 capture or receipt bytes are claimed here.

### Concrete successor objects

- `ds10-connector-acquisition-content` is blocked by an **unowned paired
  `ConnectorSourceProfileSnapshotProducer`**, which must persist matching connector and
  source-profile snapshots and emit a content-bound `SourceProfileOwnerReceipt`, then supply the
  default discovery provider. Task E's current round-2 plan has zero mentions of a connector/source
  snapshot or `SourceProfileOwnerReceipt` (exit 0, zero results); it owns no such successor. The
  blocker is deliberately not attributed to task E.
- `ds10-public-decision-rendering` is blocked by **task A's EFFECT investigation resolution plus a
  standalone DS12 promotion slice** that produces a current-signature, custody-bound public
  decision artifact/projection. `rg --files docs/plans/active/atlas-slices | rg '/DS12[^/]*\\.md$'`
  completed exit 0 with zero DS12 slice-plan files, so no existing plan is being treated as that
  producer.
- `ds10-global-case-index-producer-allocation` is blocked by **the first DS12/DS13/DS14
  scope-setting plan that consumes `atlas-ds8-residual-scope-obligations` and appoints the canonical
  global case-index/store producer**. Task G's
  `architecture/atlas_surfaces/slice-scope-obligations.json` parses exit 0 as target slices
  DS12/DS13/DS14, input `ds8-global-case-index`, `acknowledgement_status: candidate_only`, and
  `closure_effect: none`. This is the same successor object as G's half, not a second DS10 index.

### Focused documentation check

After this append, `PYTHONPATH=. uv run python
tools/quality/validation/check_docs_lifecycle.py` must remain exit 1 with exactly the inherited six
findings; this journal intentionally contains only `apps/runtime-dashboard` paths and does not add
the stale lifecycle path spelling.

### Task 7 review fix — complete D set and zero-safe successor census

The C13 normalization is now fully auditable. At the same Task D head
`0fdd402f6259365f62cd1c62f58119317853cb6d`, the complete base-to-current changed set from
`git -C /Users/deniskopylov/polisyos/.worktrees/debt-d-ds11-trust-posture diff --name-only
784d020148c56e9bfb3a3631909ba11232210a9f..HEAD | sort` completed exit 0 with these **20 paths**:

1. `policy-engine/apps/runtime-dashboard/e2e/helpers/runtime-dashboard.ts`
2. `policy-engine/apps/runtime-dashboard/package.json`
3. `policy-engine/apps/runtime-dashboard/playwright.config.ts`
4. `policy-engine/apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py`
5. `policy-engine/apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`
6. `policy-engine/apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx`
7. `policy-engine/apps/runtime-dashboard/src/test/a11y/color-blind-simulation.spec.ts`
8. `policy-engine/apps/runtime-dashboard/src/test/a11y/keyboard-journeys.spec.ts`
9. `policy-engine/apps/runtime-dashboard/src/test/a11y/screen-reader-snapshots.spec.ts`
10. `policy-engine/docs/plans/active/atlas-slices/DS11-trust-posture-debt-closure.md`
11. `policy-engine/docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current/receipt.json`
12. `policy-engine/docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current/run-1/last-run.json`
13. `policy-engine/docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current/run-1/results.json`
14. `policy-engine/docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current/run-2/last-run.json`
15. `policy-engine/docs/plans/active/atlas-slices/receipts/ds11-page-a11y-current/run-2/results.json`
16. `policy-engine/docs/superpowers/journals/2026-08-30-debt-d-ds11-trust-posture.md`
17. `policy-engine/docs/superpowers/plans/2026-08-30-debt-d-ds11-trust-posture.md`
18. `policy-engine/tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py`
19. `policy-engine/tests/repo_quality/docs/test_accessibility_evidence.py`
20. `policy-engine/tests/repo_quality/frontend/test_fixture_runtime_bound_paper.py`

Removing exactly the leading `policy-engine/` component from each changed path produces the
repository-relative set. Intersecting it with the ordered eleven receipt paths listed above has
**cardinality 1/11** and exactly one member:
`apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`. The eight other dashboard
changes and all eleven non-dashboard changes are retained in the denominator; none was silently
dropped by normalization.

The DS12 absence predicate has also been replayed without the false green semantics of an empty
`rg` pipeline. `PYTHONPATH=. uv run python` ran
`sorted(Path('docs/plans/active/atlas-slices').glob('DS12*.md'))`, printed
`ds12_slice_plan_files=0`, asserted that the list was empty, and completed exit 0. That is the
zero-safe evidence for the missing standalone DS12 slice plan.

Finally, the connector producer census was rerun over the full **2,611 tracked `src/**/*.py`**
population, not the 406-file connector/runtime subset. A `PYTHONPATH=. uv run python` complete
line-walk read each tracked source file, distinguished `class SourceProfileOwnerReceipt` from call
sites, and counted exact named producer signatures. It completed exit 0 with:

```text
full_tracked_src_python_denominator=2611
source_profile_owner_receipt_constructor_calls=0
paired_connector_source_profile_snapshot_producer_definitions=0
concrete_source_capability_discovery_provider_definitions=0
all_concrete_capability_provider_classes=1
src/polisyos/runtime/quality/capability_discovery.py:306:class LexCapabilityDiscoveryProvider:
```

The paired-producer predicate requires one definition name containing `connector`, `snapshot`, and
both `source` and `profile`; it is the exact future
`ConnectorSourceProfileSnapshotProducer` object named in this handoff. The only
`SourceProfileOwnerReceipt` occurrences remain its DS10 class, validator return/type union,
resource-kind validator map, and export: no producer calls it. The only concrete provider class is
Lex, so the default `capability_discovery_providers=()` in
`runtime/http/services/control_registry_providers.py` has no source provider to install. This
settles the block on the unowned producer while preserving connector list DTOs as a P38 negative.

## Round-2 resume after the dashboard freeze — appended 2026-08-31

The Scientist registry producer was committed first at `f282f774a`, exactly as instructed. An
ordinary no-ff merge of `main` followed at `11a3c9f60`; freeze commit
`03c5783609271c27d6f3d212b76dda7eddef2074` is an ancestor. No evidence below reads task D's
branch. The dashboard/workspace freeze has 1,314 tracked paths and independently supplied digest
`sha256:dbf87693dde8107b4672a9cf52e5877ddb1b6b779b5424672002c2922c829bb5`.

### Final C13 binding intersection and current-byte census

The exact complete-set command was:

```text
git diff --name-only 784d020148c56e9bfb3a3631909ba11232210a9f..03c5783609271c27d6f3d212b76dda7eddef2074 -- apps/runtime-dashboard package.json pnpm-lock.yaml pnpm-workspace.yaml
```

It completed exit 0 with the following **26/26 changed dashboard paths**; the three Policy Engine
workspace files named in the pathspec did not change:

1. `apps/runtime-dashboard/e2e/helpers/runtime-dashboard.ts`
2. `apps/runtime-dashboard/package.json`
3. `apps/runtime-dashboard/playwright.config.ts`
4. `apps/runtime-dashboard/scripts/check-public-claim-copy.mjs`
5. `apps/runtime-dashboard/scripts/run-ds18-time-semantics-outcome.mjs`
6. `apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py`
7. `apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/bureaucratic-document-ast.ts`
8. `apps/runtime-dashboard/src/features/artifacts/bureaucratic/export/export-html.ts`
9. `apps/runtime-dashboard/src/features/export/social/email-fixtures.ts`
10. `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts`
11. `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`
12. `apps/runtime-dashboard/src/features/trust/components/AccessibilityEvidence.tsx`
13. `apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.tsx`
14. `apps/runtime-dashboard/src/features/trust/components/PostureMethodology.tsx`
15. `apps/runtime-dashboard/src/features/trust/copy/useTrustCopy.ts`
16. `apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx`
17. `apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx`
18. `apps/runtime-dashboard/src/shared/lib/domain/epochSemantics.ts`
19. `apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx`
20. `apps/runtime-dashboard/src/test/a11y/color-blind-simulation.spec.ts`
21. `apps/runtime-dashboard/src/test/a11y/keyboard-journeys.spec.ts`
22. `apps/runtime-dashboard/src/test/a11y/screen-reader-snapshots.spec.ts`
23. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`
24. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`
25. `apps/runtime-dashboard/src/test/evidence/ds18-execution-outcome.schema.json`
26. `apps/runtime-dashboard/src/test/evidence/ds18ExecutionOutcome.ts`

The canonical receipt JSON still enumerates the eleven C13 bindings listed in the earlier entry.
Exact normalized set intersection completed exit 0 with **1/11 member**:
`apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`. A complete SHA-256 replay over
all eleven final files completed exit 0 with **5/11 current and 6/11 stale**. The stale bindings are
`AmbientTelemetryHud.tsx` (`a06e6a98...`), `OperatorCraftPanel.tsx` (`8d94ade6...`),
`RunDetailLayout.tsx` (`f4533fee...`), `RunReportPage.tsx` (`bfd0a87a...`),
`RunReportPage.test.tsx` (`30023d27...`), and `runtime-dashboard.visual.spec.ts`
(`3a69dd55...`). This reproduces the register's six-row subject sweep against the final bytes.

### C13 reissue attempt exposes a newer semantic incompatibility

The exact conjunction node was run red-first after the merge and exited 1 at the first stale
binding, `AmbientTelemetryHud.tsx`. The environment probe then exited 0 at capture commit
`11a3c9f608ebc0df567f435ee21b4f775604cb60`, with tuple SHA-256
`795cf39ca70376a5067917e51294c696013e6f63e645d864dc0f2badda92a27c`; the new raw probe is
`environment-reissue-before.json`, leaving all three admitted historical probes byte-identical.

Capture attempt 1 used the registered C13 command: Chromium, one worker, zero retries,
`--update-snapshots=none`, JSON reporter, the exact `DS8 governed run paper` grep, and distinct
`run-3` output. It exited **1** with **3 selected = 0 expected + 3 unexpected**, raw result SHA-256
`c25f674d11a722d91c56e2f38baaed4c623ecffc34d2093c779a6114308d2809`. All three governed titles
were selected, but each report request returned HTTP 409 before its substantive predicate. The
body is `code=run_paper_source_invalid`, detail `terminal run manifest must name exactly one
run-bound DesignRecord binding`.

This is not a browser retry or the repaired JSON-loader break. Current production contract
`tests/unit/runtime/http/test_run_paper_api.py::test_run_paper_rejects_terminal_run_without_exact_case_binding`
was replayed and exited 0. The same test file also pins both old empty/growth fixture runs to 409.
The three C13 tests still require those unbound `core`, `empty`, and `growth` runs to return 200,
and the semantic title still asserts the superseded `artifact_missing` case record. A second
identical heavy capture cannot become admissible evidence and was not run.

The C13 row is therefore executable only after a landable dashboard test/fixture migration: the
three governed titles in `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts` must exercise
run-bound DesignRecord fixtures and assert the current `record_available_authority_abstaining`
shape; the fixture producer in `apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py` (and
its runtime helper if needed) must provide distinct bound empty/growth runs without weakening the
strict 409 contract. Both files are in the frozen dashboard corridor, so Task C makes no source
change. This is the exact architect routing question and the `blocked_by` object for C13.

No C13 receipt or checker predicate was loosened. The exact diff to
`architecture/atlas_surfaces/check_frontend_disposition_register.py` is **empty**.

## Round-2 final Register closure dossier — appended 2026-08-31

This section supersedes the round-1 verdicts above without rewriting them. No architect-owned
register, ledger, master plan, published denominator, dashboard source, OpenAPI source, schema, or
runtime client file was edited.

The final targeted closure wave was:

```text
PYTHONPATH=. uv run --extra test pytest -q \
tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness \
tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation \
tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion \
tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness \
tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness \
tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface \
tests/unit/runtime/http/services/test_lex_pipeline.py
```

It completed exit **0** with **9/9 selected tests passed**. Every new pytest identity was written
and observed red before its producer was implemented. The four controlling P38/W5-K01 negatives
remain unchanged: execution availability is not an owner-indexed method row; registry membership or
`admitted=True` is not capability evidence; L4 lookup is not Scientist agent/tool discovery; and
internal REVIEWER/EXPERT posture is not public decision authority.

The final complete AST census used `git ls-files -- 'src/**/*.py'`, parsed every returned file, and
classified only non-Protocol/non-abstract bodies as implementations. It completed exit 0 as:

```text
tracked_src_python=2615
named_definitions=4
protocol_or_abstract_stubs=2
concrete_implementations=2
src/polisyos/runtime/quality/adapter_contracts.py:279:VerifiedAdapterAdmissionProducer.resolve_operation:concrete=true
src/polisyos/runtime/quality/adapter_contracts.py:301:VerifiedAdapterAdmissionProducer.verify_conformance:concrete=true
src/polisyos/runtime/quality/capability_resolver.py:162:CapabilityLiveOperationRegistry.resolve_operation:concrete=false
src/polisyos/runtime/quality/capability_resolver.py:170:CapabilityConformanceVerifier.verify_conformance:concrete=false
```

This disagrees with the original 2,579 control by **+36 paths** and with Task C's pre-merge 2,611
control by **+4 paths**. The required merge brought five tracked Python additions and F's deletion
of `src/polisyos/core/observability/truthfulness.py`, a net +4. The substantive implementation
measurement moved from **0/2,611** at Task C entry to **2/2,615** now; both concrete methods belong
to the operation-bound adapter producer built here.

A complete replay over the five tracked `layer3*_adapter_admission_registry.json` files completed
exit 0 at **61 rows = 8 admitted + 52 candidate-shadow-only + 1 blocked**. The legacy rows still
contain **0/61** instances of each named DS10 capability key/provider: `resource_kind`,
`capability_purpose`, `passport_receipt`, `evidence_receipt`, `currentness_receipt`, and
`capability_discovery_provider`. That unchanged historical population is not used as the new
producer's evidence; generic data-only admission through a newly supplied verified row is the
behavioral closure.

### `ds10-adapter-admission-capability-discovery-bridge`

- Verdict: `closed`.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness` completed exit 0; it was replayed in the final 9/9 closure wave above.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`.** `VerifiedAdapterAdmissionProducer` now resolves the operation declared by a contract row, executes it, verifies operation-bound semantic preservation, verifies a current receipt, and emits a content-bound passport/evidence/currentness bundle. `AdapterCapabilityDiscoveryProvider` consumes only that verified admission and emits a typed `method` row plus `AdapterCapabilityOwnerReceipt` carrying capability purpose and all three receipt families; a purpose mismatch produces a typed rejection. A bare registry member, tuple membership, and `admitted=True` remain explicit failing negatives. The complete source census is 2 concrete operation/conformance implementations / 2,615 tracked Python files; the unchanged 61 legacy admission rows remain 0/61 for DS10 capability keys and were not relabelled as evidence.

### `ds10-lex-pipeline-mutation-boundary`

- Verdict: `closed` by the register's manual-resolution route.
- Deciding command/predicate: `PYTHONPATH=. uv run python` read the complete 717-line page and 230-line test, asserted 947 total lines, and completed exit 0 with `capability_discovery_literals=0`, one `triggerMutation.mutate`, one `searchMutation.mutate`, one Launch binding, one Search-button binding, and one Enter binding. `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/http/services/test_lex_pipeline.py` completed exit 0 with 3/3 tests passed. Vitest title selection remains unsupported by the checker by design, so no zero-selection runner output is promoted into evidence.
- Exact prose to append:

> **TASK-C ROUND-2 MANUAL CLOSURE 2026-08-31 — `closed`.** The complete 947-line frontend population has zero capability-discovery imports, calls, or literals. Its only mutations are exactly one `handleTrigger -> triggerMutation.mutate` path bound to the Launch control and exactly one `handleSearch -> searchMutation.mutate` path bound independently to Enter and Search; the three backend Lex boundary tests pass. Because the row explicitly assigns unsupported Vitest selection to manual resolution, this complete call-graph measurement proves the boundary without inventing a runner receipt. No Lex or dashboard source changed.

### `ds10-causal-method-index-provider-bridge`

- Verdict: `closed`.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion` completed exit 0 and was replayed in the final closure wave.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`.** The ordinary provider bootstrap now lazily reads persisted `CapabilityIndex` owner rows and emits a content-bound `CapabilityIndexOwnerReceipt`; replayed search rows exactly equal the owner's persisted method projection. Every result retains `execution=not_established`, `authority=bridge_missing`, and an empty authoritative-purpose set. No `project_capability_features` execution/backend boolean is converted into a discovery row, so the execution-to-discovery P38 boundary remains intact.

### `ds10-owner-signed-capability-purpose-binding`

- Verdict: `closed`; this repository is in the **producer-side signing world**, not the appointment world.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness` completed exit 0 and was replayed in the final closure wave.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`; producer-side signing world.** `CapabilityPurposeBindingProducer` canonicalizes and persists the ref/digest/purpose/audience/consumer binding in CAS and signs those bytes with a producer-held Ed25519 key. A separate trusted `CapabilityPurposeBindingVerifier` resolves the artifact, content-binds it, verifies signature and producer identity, and only then joins the DS9 approval-packet currentness resolver. Wrong identity, byte tamper, purpose mismatch, missing binding, and stale DS9 currentness all fail closed. The signature is therefore an actual producer act followed by independent verification; verification was not substituted for signing, and no institutional appointment is required.

### `ds10-connector-acquisition-content`

- Verdict: `blocked`.
- `blocked_by`: the registered successor row `acquisition-route-to-n13b-authority-binding` landing a current content-bound route-to-authority-entry, attempt-identity, and `LiveCatalogExecutionConstraints` binding and exercising a tenant-bound N13b implementation outside the badged harness. A register parser found exactly one row with that ID and completed exit 0.
- Complete producer census: `PYTHONPATH=. uv run python` parsed all **2,615 tracked `src/**/*.py` files** and completed exit 0 with one `SourceProfileOwnerReceipt` class definition, **0 constructor calls**, and **0 class/function definitions** matching the complete connector+source+profile+snapshot+producer identity.
- Exact prose to append:

> **TASK-C ROUND-2 TERMINAL VERDICT 2026-08-31 — `blocked`; `blocked_by: acquisition-route-to-n13b-authority-binding`.** DS15 must first land the registered content-bound route-to-authority-entry / attempt-identity / `LiveCatalogExecutionConstraints` binding and exercise a tenant-bound N13b implementation outside the badged harness. The current 2,615-file AST census still finds only the `SourceProfileOwnerReceipt` type, zero constructors, and zero paired connector/source-profile snapshot producers. The named unowned artifact remains `ConnectorSourceProfileSnapshotProducer`: it must persist matching connector and source-profile snapshots and emit a content-bound `SourceProfileOwnerReceipt`, then supply the default source discovery provider. The architect must make that producer an explicit conjunct or appointment of the registered DS15 successor; if the successor lands without it, this row remains blocked. Connector/profile list DTOs are still a P38 negative, never discovery evidence.

### `ds10-public-decision-rendering`

- Verdict: `blocked`.
- `blocked_by`: registered row `gy-n9-effect-obligation-producer-and-evaluator-missing`, followed by a standalone DS12 promotion slice that consumes a current custody signature and persists the public decision projection. A register parser found exactly one row with that ID at exit 0; a zero-safe `Path.glob('DS12*.md')` census completed exit 0 with `ds12_slice_plan_files=0`.
- Exact prose to append:

> **TASK-C ROUND-2 TERMINAL VERDICT 2026-08-31 — `blocked`; `blocked_by: gy-n9-effect-obligation-producer-and-evaluator-missing` plus the standalone DS12 promotion slice that follows it.** The first object must land the effect-evidence contract field, producer, and evaluator required for a governed promotion; DS12 must then resolve a current custody signature into a persisted public decision artifact/projection. Internal REVIEWER/EXPERT discovery posture and MACHINE/compiler candidates remain non-authoritative and cannot close the row. The overlap `ds8-signed-public-decision-surface` still lacks this same DS12 custody-bound producer and public surface; Task C closes neither half by substitution.

### `ds10-global-case-index-producer-allocation`

- Verdict: `blocked`.
- `blocked_by`: the first DS12/DS13/DS14 scope-setting plan that claims the `ds8-global-case-index` obligation carried by `architecture/atlas_surfaces/slice-scope-obligations.json` and appoints the canonical global index producer. On this merged branch, a zero-safe existence predicate completed exit 0 with `slice_scope_obligations_exists=False`; the manifest itself therefore must land before such a plan can consume it. No peer branch was read.
- Exact prose to append:

> **TASK-C ROUND-2 TERMINAL VERDICT 2026-08-31 — `blocked`; `blocked_by` the first DS12/DS13/DS14 scope-setting plan that consumes the `ds8-global-case-index` obligation from `architecture/atlas_surfaces/slice-scope-obligations.json` and appoints the canonical global case-index producer.** The supplied obligation has `closure_effect: none`, so carrying it is explicitly not closure; on the current merged branch the manifest path itself has not landed. The appointed producer must persist the canonical index/snapshot, emit a content-bound case-owner receipt, and install the provider. Run-bound records and human-decision `case_id` strings remain scoped identifiers, not a global index. The overlap `ds8-global-case-index` blocks on this exact same object, not a second DS10 store.

### `ds10-world-agent-capability-discovery-boundary`

- Verdict: `closed`.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface` completed exit 0 and was replayed in the final closure wave.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`.** The ordinary control-registry path now installs a lazy `ScientistRegistryCapabilityDiscoveryProvider`. On first search it reads real `NodeRegistry` and `ToolRegistry` instances, canonicalizes and persists their bytes separately, emits content-bound `ScientistCapabilityOwnerTruth` rows and a dual-snapshot `ScientistRegistryOwnerReceipt`, and returns them through the ordinary capability API. Request-scoped registries outside the snapshot are carried honestly as typed `recall_unmeasured`. The integration witness proves factories are lazy and persisted bytes resolve; L4 world-model entity/data lookup remains an exercised non-substitute and contributes no Scientist row.

### `ds10-layer3-owner-ledger-rejection-richness`

- Verdict: `closed`.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness` completed exit 0 and was replayed in the final closure wave.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`.** The native G2, G3, and seven GL owner builders now emit their selected and rejected candidates, requested/evaluated/cutoff facts, and typed incompleteness before DS10 sees them. The aggregate witness reaches all nine owner ledgers and proves the DS10 projection is lossless across each family's native refs/reasons. DS10 no longer reconstructs missing rejection richness or infers completeness from an adjacent success flag.

### `three-unavailable-governed-producers`

- Verdict: `closed`, retaining the architect-accepted round-1 result; this row was not rebuilt in round 2.
- Deciding predicate: the stable actual-root `GovernedProjectionService.get(...)` census over the inherited 13-ID population completed exit 0 as **13 projections = 7 available + 5 invalid_source + 1 artifact_missing**. The three named members were **0 available + 2 invalid_source + 1 artifact_missing**; cleanup of the temporary read-only data link completed exit 0.
- Exact prose to append:

> **TASK-C CLOSURE 2026-08-31 — `closed` as a reason-complete investigation.** The current enum has 14 IDs; the inherited 13-ID population excludes later available `acquisition-growth`. A stable actual-root census completed exit 0 as `13 projections = 7 available + 5 invalid_source + 1 artifact_missing`. The three named members are owner/reason-bound: `generation-cycle-disposition` is `invalid_source` because the declared validator reports missing `ortools.sat.python.cp_model`; `capability-reality` is `invalid_source` because its capability-repository anchor/file is missing and needs reissue; `surface-readiness` is `artifact_missing` because the live ledger is absent and its owner validator is unregistered. No solver, example ledger, or adjacent artifact was substituted. This closes the investigation with an exact remainder, not with 13/13 green.

### `ds10-adapter-registry-data-only-free-growth`

- Verdict: `closed`.
- Deciding command: `PYTHONPATH=. uv run --extra test pytest -q tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation` completed exit 0 and was replayed in the final closure wave.
- Exact prose to append:

> **TASK-C ROUND-2 CLOSURE 2026-08-31 — `closed`.** A temporary governed TOML mutation adds a previously unknown adapter identity with a declared semantic-identity operation, purpose, passport, producer evidence, and currentness; the generic G3 builder admits it without adding that identity to Python source. The same witness proves TOML membership without the capability declaration is rejected, semantic loss is rejected, and stale currentness is rejected. Growth is therefore data-only only after per-row semantic preservation and evidence/currentness verification; registry membership alone never admits.

### `ds10-c13-print-receipt-reissue`

- Verdict: `blocked` — `verification_missing`.
- `blocked_by`: a dashboard-corridor source migration in `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts` and `apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py` (plus the runtime fixture helper only if required) that gives `core`, `empty`, and `growth` distinct run-bound DesignRecord fixtures and updates the three governed assertions to current `record_available_authority_abstaining` semantics without weakening the strict HTTP 409 contract.
- Binding predicate: the ordered eleven paths are the same complete list above: `print.css`; `AmbientTelemetryHud.tsx`; `OperatorCraftPanel.tsx`; `RunDetailLayout.tsx`; `RunReportPage.tsx`; `RunReportPage.parity.test.tsx`; `RunReportPage.test.tsx`; `features/runs/route.tsx`; `e2e/helpers/pdfGeometry.ts`; `e2e/runtime-dashboard.visual.spec.ts`; and its governed Darwin PNG. Their final-byte census completed exit 0 as **11 bindings = 5 current + 6 stale**. D's complete **26-path** freeze delta is enumerated under `Final C13 binding intersection and current-byte census` above; exact normalized intersection completed exit 0 at **1/11**, `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`.
- Capture receipt 1: the registered Chromium/one-worker/zero-retry/`--update-snapshots=none` command selected all three governed titles and exited 1 at **0 expected + 3 unexpected**, with every retry index 0. Raw JSON is `ds6-c13-raw/run-3/results.json`, SHA-256 `c25f674d11a722d91c56e2f38baaed4c623ecffc34d2093c779a6114308d2809`.
- Capture receipt 2: the same registered command with a distinct `run-4` output selected the same three titles and exited 1 at **0 expected + 3 unexpected**, with every retry index 0. Raw JSON SHA-256 is `4596542a9027c1c825a3d1b2fe4c52969032c658c2d3c94dbdfc70613bf9f9e2`; its screenshots, error contexts, videos, and traces are retained beside it. Both results record one worker, Chromium retries 0, and `updateSnapshots=none`. `git diff --exit-code main...HEAD -- apps/runtime-dashboard` completed exit 0.
- Deciding gates: `PYTHONPATH=. uv run --extra test pytest -q architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes` completed exit 1 at stale `AmbientTelemetryHud.tsx`. `PYTHONPATH=. uv run --extra test python architecture/atlas_surfaces/check_frontend_disposition_register.py --check` completed exit 1 with the same C13 failure plus out-of-scope DS18/C06 drift. The exact Task-C diff to that checker is empty: `git diff --exit-code main...HEAD -- architecture/atlas_surfaces/check_frontend_disposition_register.py` completed exit 0.
- Exact prose to append:

> **TASK-C ROUND-2 HANDOFF 2026-08-31 — `blocked`, `verification_missing`; `blocked_by` the dashboard-corridor run-paper fixture/spec migration.** Against D's final freeze, the eleven C13 bindings intersect D's 26 changed paths at exactly one member, `RunReportPage.tsx`, and the final-byte replay is `11 = 5 current + 6 stale`. Two distinct current zero-retry/no-writer captures each select all three governed titles but fail 0/3 before the governed property: the old `core`/`empty`/`growth` fixtures have no exact run-bound DesignRecord and production correctly returns `run_paper_source_invalid`/HTTP 409. Their JSON digests are `c25f674d...` and `4596542a...`; dashboard source and the governed snapshot remain unchanged. The exact conjunction and global disposition check both remain exit 1, so no stale receipt was reissued and no predicate was weakened. Land distinct run-bound fixtures and current `record_available_authority_abstaining` assertions in `runtime-dashboard.visual.spec.ts` and `serve_fixture_runtime_api.py`, then take two passing captures, bind all 11/11 current bytes, and replay both gates. `DS11-INHERITED-C13-PRINT-RECEIPT` remains blocked on that same migration plus this reissue and still needs its own append-only closure; Task C does not close D's half.

## Round-2 dossier arithmetic

- All rows: **12 measured rows = 8 closed + 4 blocked + 0 unfinished/open**.
- Core limitations: **9 core rows = 6 closed + 3 blocked**.
- Adjacent rows: **3 adjacent rows = 2 closed + 1 blocked**.
- Closed core: adapter admission bridge, Lex mutation boundary, causal-method bridge,
  owner-signed purpose binding, Scientist registry discovery, and Layer-3 owner richness.
- Blocked core: connector acquisition content, public decision rendering, and global case index.
- Closed adjacent: governed-producer investigation and adapter data-only growth.
- Blocked adjacent: C13 receipt reissue.

No row is `open`, `ambiguous`, or disguised as blocked because Task C ran out of budget.

## Explicit-non-closure and overlap handoff

The architect must move these **7 now-closed entries** out of
`docs/plans/active/atlas-slices/DS10-capability-discovery.md`'s `## Explicit non-closure` table in
the same register transcription:

1. generic post-G0 registry data-only free growth;
2. admitted-adapter capability-discovery bridge;
3. owner-signed typed capability-purpose authority binding;
4. default causal-method `CapabilityIndex` bridge;
5. G2/G3/GL rejected/incompleteness richness;
6. Lex pipeline mutation; and
7. L4 world-agent lookup.

The table's C13, connector/acquisition, public-decision, and global-case entries remain honest
non-closures with the superseding blocker objects above.

- `DS11-INHERITED-C13-PRINT-RECEIPT` still lacks the dashboard fixture/spec migration, two passing
  current captures, 11/11 rebinding, green conjunction/global checks, and its own DS11 append. Task C
  produced two honest failing capture receipts and did not close the other half.
- `ds8-global-case-index` still lacks the same landed scope-obligation manifest, claiming
  DS12/DS13/DS14 plan, appointed canonical producer, persisted index, and content-bound provider.
- `ds8-signed-public-decision-surface` still lacks the same EFFECT producer/evaluator resolution and
  DS12 custody-bound promotion/public projection.

## Final checker delta and out-of-scope findings

- The project-bound debt checker completed exit 1 after the final source commits with
  `closure_signal_identity_unresolvable=9`, down from the corrected entry baseline of 18. All five
  newly written core identities and the adjacent free-growth identity resolve. The only Task-C
  Python identities still unresolved are the three intentional successor blocks: connector,
  public decision, and global case. Lex remains an informational unsupported-runner manual route.
  Task C added no blocker.
- Focused Ruff over all 16 changed Python files completed exit 0 with `All checks passed!`.
- Architecture guardrails completed exit 1 only at the inherited
  `trust-claim-posture-register` generator probe (`DS11-CLAIM-LIFECYCLE-ORCHESTRATION` is not exactly
  appointed and open); runtime API/client freshness remained clean. No Task-C import finding exists.
- The focused G3 task-7 conformance red `layer3_g3_w12d_consumer_gate_missing` was replayed from
  committed pre-adapter Task-C head `67ce44e5a` and reproduced unchanged, while adapter registry,
  admission, and adapter checks passed. It is inherited and was not widened into this task.
- The global frontend checker additionally reports DS18 time-semantics and C06 baseline-lint receipt
  drift. Task C changed neither owner artifact nor checker predicate.
- `architecture/atlas_surfaces/slice-scope-obligations.json` is absent from this merged branch even
  though the supplied G handoff says that paused lane carries it. Per the no-peer rule, no other
  branch was read; the architect must land that exact manifest before the global-index successor
  plan can consume it.
- After the complete dossier and both new C13 capture receipts were present,
  `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` completed exit 1 with
  exactly the inherited **6 findings = 2 `active_plan_metadata` findings on architect-owned
  `LEDGER.md` + 4 `removed_stub_reference` findings**. This journal added no seventh finding.
