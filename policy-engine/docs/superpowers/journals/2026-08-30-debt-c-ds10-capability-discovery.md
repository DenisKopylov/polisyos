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
