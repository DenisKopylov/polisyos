# Atlas DS3 Runtime Producers & Export Infrastructure Implementation Plan

> **For agentic workers:** Execute this plan task by task with red-first tests. Do not
> merge this branch; stop after the architect-review handoff.

**Goal:** Put the frozen GY and Atlas governance artifacts behind lazy, typed HTTP
producers, establish the replayable packet convention later MACHINE twins reuse,
govern the existing non-OpenAPI realtime channels, and make
`packages/runtime-api-client` the single generated-client home proved by the reference
shell.

**Architecture:** Extend the existing runtime HTTP and export waist. A single strict
projection catalog owns stable IDs, source paths, source-specific narrow payload DTOs,
audience, authority limits, and absence behavior. The service reads sources only on
request, caches immutable serialized projections by source content hash, and emits a
discriminated available/missing/invalid packet with source identity, projection
identity, as-of/freshness, stable addressing, and replay pins.
The producer projects owner-recorded and validator-produced facts; it never recreates
owner semantics. Existing OpenLineage/PROV, artifact render/export, and
decision-validity endpoints remain the export implementations this packet convention
complements, not a second renderer stack.

**Tech stack:** Python 3.14, FastAPI optional-router guard, Pydantic v2 strict DTOs,
`tomllib`, SHA-256 canonical JSON projections, pytest, generated OpenAPI,
`openapi-typescript`, TypeScript 5.7, the existing JavaScript runtime client.

## Binding scope and fence

- Worktree: `.worktrees/atlas-ds3`; branch:
  `codex/atlas-ds3-runtime-producers`; base at plan time: `7b6933770`.
- Writable: `src/polisyos/runtime/http/**`, `schemas/**`,
  `packages/runtime-api-client/**`, `apps/runtime-reference-shell/**`, scoped
  `tests/**`, this `DS3-*` plan, and one DS3 journal.
- Read-only upstream owners: `runtime/quality`, `fabric`, `foundry`, `scientist`,
  `data_forge`, `architecture`, `production_data`, and the DS19 dashboard worktree.
- No deletes, dashboard edits, architecture edits, lockfile changes, audience
  enforcement, UI routes, endpoint removals, or merge.
- Revision-3 master status is current; `atlas-phase-a-synthesis.md` is binding only as
  the DS3 re-scope. Phase B is active.

## Pattern pass and capability state

Relevant failure modes are `P01` contract-only/producer re-derivation, `P02` thin
orchestration, `P03` hidden richness, `P05` authority leak, `P07` replay gap, `P08`
time-role conflation, `P10` semantic inadequacy, `P13` governance gravity, `P15`
projection authority laundering, `P27` owner bypass, `P29` marker-only proof, `P30`
misleading naming, `P31` instance patching, `P32` trust by form, `P33` teaching to a
probe, and `P34` dishonest exclusion.

The target correct pattern is:

`validated owner artifact -> narrow recorded projection -> content-addressed packet ->`
`HTTP/OpenAPI -> generated client -> reference-shell proof`, with negative tests for
absence, replay mismatch, re-derivation, label pinning, and sibling channel transports.

At plan time the frozen artifacts are `producer_missing`; the channel registry is
`contract_only`; Lex truth is `surface_missing`; client-home consolidation is
`implemented_but_not_orchestrated`. The readiness live source and validated proving-
ground result are `artifact_missing`. DS3 may close producer/bridge/surface/semantic
test gaps only for the portions enumerated below; it must not relabel an absent owner
artifact as implemented.

## Producer inventory and payload law

All stable producer addresses use
`GET /api/v1/exports/governed-projections/{projection_id}`. The catalog is
`GET /api/v1/exports/governed-projections`; replay is the same stable address plus both
`artifact_content_hash` and `projection_hash` query pins. Every packet declares
`projection_id`, `availability`, packet schema version, mandatory projection rule
version, optional owner source schema/rule versions, `audience`,
`authoritative_for`, `may_not_use_for`, source path, SHA-256 source content hash,
SHA-256 narrow projection hash, `as_of`, freshness basis/state, stable address, and
replay address. Source timestamps (`observed_at`, `generated_at`, `generated`, or
`as_of`) win; filesystem observation time is the honest fallback and is excluded from
the narrow projection hash.

| Producer ID | Governed source artifact | Narrow projection scope | Consumer slice | Audience | Exact semantic/API test |
|---|---|---|---|---|---|
| `depth-n-cycle-board` | `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json` | Per-domain run identity; recorded `terminal_distribution`; recorded validator evidence witness/class; recorded `blocking_obligations` as weakest links; recorded acquisition stage/route; top-level `terminal_distributions` and depth evidence | DS7 Cycle Board, DS8 drilldown, later MACHINE twin | MACHINE | `test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving`; `test_depth_n_projection_accepts_unseen_terminal_labels_without_pinning`; `test_depth_n_projection_hash_ignores_provenance_only_rebaseline` |
| `value-gate` | `architecture/policy_design_case/layer3_gy_value_gate_contract.json` | Denominators; education/production advisor and value receipts, including any recorded `ValueOuterSet`; mode gates; recorded acquisition routing; disposition | DS7 value column, DS16 value surface | MACHINE | `test_value_gate_projection_contains_denominators_receipts_and_outer_set_slots` |
| `generation-cycle-disposition` | `architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json` | Task/owner/disposition records, bridge artifacts, method-availability gate, known residuals | DS7 honesty copy, DS10 explanation | EXPERT | `test_disposition_projection_is_narrow_and_audience_declared` |
| `engine-census` | `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json` | Counts, execution vocabulary, critical findings, subcensus summary; never the complete row table unless explicitly requested by a future projection | DS7/DS10 census context | EXPERT | `test_engine_census_projection_omits_full_rows` |
| `fork-b-relation-census` | `architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json` | Relation denominator/counts, authority, coverage manifest, certificate summaries, transport floor, known bridge limits; excludes the 16 MB relation table | DS7/DS10 census context | MACHINE | `test_fork_b_projection_omits_relation_table_and_binds_counts` |
| `acquisition-routing-contract` | `architecture/policy_design_case/layer3_gy_acquisition_contract.json` | Denominators, positive/no-result receipts, fail-closed receipt, grounding request, recorded rederive inputs and economics | DS7 base route, DS15 acquisition surface | MACHINE | `test_acquisition_contract_projection_preserves_owner_receipts`; `test_acquisition_projection_hash_ignores_receipt_provenance_rebaseline` |
| `n13a-acquisition-census` | `architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json`, optional until upstream merge/file presence | Observed catalog identity, projection bindings, family scorecards, metric resolutions, route evidence, growth backlog, fetch-plan generation | DS15 acquisition surface, DS7 route context | MACHINE | `test_n13a_census_returns_typed_absence_when_source_is_missing`; `test_n13a_census_projects_present_source` |
| `n13a-live-probe-journal` | `architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json`, optional until upstream merge/file presence | Observed selection plan, family receipts, and probe records; no new success inference | DS15 acquisition audit | EXPERT | `test_n13a_probe_journal_returns_typed_absence_when_source_is_missing`; `test_n13a_probe_journal_projects_present_source` |
| `capability-reality` | `architecture/policy_design_case/capability_reality_report.json` | Summary/readiness, capability claims, blockers/issues, chain clusters, ratchet integrity; no new readiness calculation | DS6 validation, DS7 capability truth | MACHINE | `test_capability_reality_projection_uses_reported_readiness` |
| `cluster-ownership` | `architecture/policy_design_case/cluster_ownership_map.toml` | Cluster/cell ownership, ratchet states, capability-chain fields, stop rule, authority/firewall fields | DS6 validation, DS7 ownership drilldown | EXPERT | `test_cluster_ownership_projection_parses_toml_without_reclassifying_cells` |
| `layer3-health-metrics` | `architecture/policy_design_case/layer3_health_metric_ledgers.toml` | Recorded metric ledgers, freeze values, owners, next-update rules and trend vocabularies | DS6 instrumentation | MACHINE | `test_layer3_health_projection_preserves_freeze_values` |
| `legacy-proving-ground` | Fixture identities: `tests/fixtures/universal-corpus/manifest.json` plus its 13 case files; validated runtime outcome source currently absent | Stable identity/domain/split and declared semantic expectations only, marked `fixture_only`; excludes metadata, producer pipeline, and raw source refs/hashes; separate `runtime_outcomes` remains typed `artifact_missing` | DS7 legacy cohort | EXPERT | `test_proving_ground_never_promotes_fixture_expectations_to_runtime_outcomes`; `test_proving_ground_has_thirteen_fixture_identities`; `test_proving_ground_projection_omits_producer_metadata_and_hash_ignores_it` |
| `surface-readiness` | Required live `surface-readiness-ledger.json` currently absent; the Revision-2 `.example.json` and DS1 live-app audit ledger are explicitly ineligible | `artifact_missing` when absent; any present file is `invalid_source` until DS0 registers a Revision-3-capable schema for DS19/DS20 and current capability labels; then projection-only entries/authority/as-of | DS6 validator, DS7 Cycle Board | MACHINE | `test_surface_readiness_rejects_example_as_live_authority`; `test_surface_readiness_returns_typed_absence_without_live_ledger`; `test_surface_readiness_present_but_fake_is_invalid_source`; `test_surface_readiness_rejects_revision_2_schema_at_live_path` |

### Recompute-not-pin (`§3.5.10`)

The HTTP service must select the capstone's recorded validator outputs. It must not infer
an evidence class from issue text, recompute weakest links from a local rule, or map
terminal labels through a local vocabulary. A source with a missing recorded evidence
witness fails closed as `invalid_source`; the endpoint does not manufacture it. Tests
mutate the recorded witness and terminal labels to novel values and require the response
to follow the governed fields. This proves projection, not a second semantic owner.

### Narrow projection hashes (`§3.5.11`)

Projection hashes are canonical JSON hashes of source-specific dependency DTO dumps.
Source content hashes, timestamps/as-of, producer/provenance notes, source paths,
addresses, and freshness are recursively excluded. A nested receipt-provenance test
requires the artifact hash to change while the projection hash remains identical; the
legacy cohort hash covers only identity plus declared semantic expectations. Replay
pins check both identities: source pin protects byte replay; projection pin protects
the consumer contract.

### Source-prerequisite decisions

- **Readiness:** do not serve `surface-readiness-ledger.example.json`, derive readiness
  from routes, or promote the DS1 audit ledger. Until a canonical live artifact validates
  under an owner-registered Revision-3-capable schema, absence emits
  `artifact_missing`, while present fake/malformed/Revision-2 bytes emit
  `invalid_source`. DS6 remains the sole behavioral verifier.
- **Proving ground:** fixture records provide identities/expectations only. They are
  never runtime evidence. Until the upstream owner names a persisted validated result,
  `runtime_outcomes` is typed absent and its `may_not_use_for` includes readiness,
  outcome, admissibility, and publication claims.
- **Base-versus-later slices:** DS3 emits format-agnostic base projections. DS15/DS16
  own acquisition/value execution and consumer-specific semantics; DS3 does not claim
  those later capabilities.

## Client-home decision (PI-01)

**Decision:** `packages/runtime-api-client` is the one generated-client home.

Evidence and procedure:

1. It is already a workspace package with its own tests, architecture fence, TypeScript
   check, and JavaScript runtime client, and the reference shell already imports it.
2. The dashboard-local `apps/runtime-dashboard/src/api/types.ts` is generated only for
   one application and cannot be imported by later MACHINE twins without reversing the
   dependency direction.
3. Generate the shared schema types at
   `packages/runtime-api-client/types.ts` using exactly
   `export_runtime_openapi_schema() -> schemas/runtime_api_v1.openapi.json -> npx
   --yes openapi-typescript@7.13.0`. The exact generator pin is package-owned and has
   no dashboard-local dependency; DS3 keeps the lockfile unchanged per its fence.
   Continue regenerating `runtimeApiClient.ts/js` from the same committed OpenAPI
   until its runtime wrapper is replaced in a separately approved slice.
4. The reference shell proves the selected home by calling the governed-projection
   catalog through the package client. No dashboard file moves in DS3.
5. The rejected alternative is dashboard-local ownership. Revisit only if the dashboard
   becomes the sole runtime consumer and the package has no external/reference-shell
   consumer, or an approved workspace-wide SDK package supersedes both homes.

The dashboard-local file remains a DS4+/DS19-free migration concern; DS3 neither edits
nor deletes it. No third client is introduced.

## Channel governance (PI-02/PI-03 and DS1-N021)

The registry is exposed at `GET /api/v1/exports/channel-registry` and uses strict entries
with channel ID, path template, transport, message contract, auth class, consumers,
owner, schema visibility, and status. The two SSE routes and review WS stay under their
existing auth defaults.

| Registry ID | Runtime path / channels | Transport and contract | Existing auth class | Consumer | DS3 disposition |
|---|---|---|---|---|---|
| `runs-list-live` | `/api/v1/runs/live` | SSE `runtime.runs.list.snapshot.v1` plus cursor/retry framing | tenant runtime access + stream rate limit | dashboard `RunsLiveProvider` | Govern as active typed channel; keep `include_in_schema=False` |
| `run-detail-live` | `/api/v1/runs/{run_id}/live` | SSE `runtime.run.detail.snapshot.v1` plus cursor/retry framing | run tenant access + stream rate limit | dashboard run live hook | Govern as active typed channel; keep `include_in_schema=False` |
| `review-live` | `/api/v1/review/live`, `review.presence`, `review.cursor`, `review.lock` | WS envelope contracts already enforced by review hub | review socket authentication, tenant binding, OPA action check, stream rate limit | dashboard review collaboration surface | Govern as active typed hub; DS5 owns browser auth/degradation enforcement |

The dashboard's `/api/v1/collaboration/**` REST and `/api/v1/collaboration/live`
transports remain phantom at plan time. DS19 branch
`codex/atlas-ds19-strangle-wave` has no merged register commit yet. DS3 records the
dated recommendation **remove/strangle (2026-07-17)** because there is no server or
validated consumer capability; it does not implement, register, delete, or exempt those
paths. When DS19's register lands before closeout, consume its decision in tests; else
N021 closes the DS3-owned active-channel portion and reports the DS19-owned phantom
residual explicitly.

The 37 uncalled OpenAPI operations likewise remain untouched; DS19 owns their
build/remove dispositions.

## Export convention and Lex truth bridge

- The governed packet and existing OpenLineage/PROV, artifact render/export, and
  decision-validity routes share one canonical projection hasher and replay-address
  builder. Existing exporters keep their owner payloads and add the typed convention
  through documented response headers plus a fail-closed `export_projection_hash` pin.
- Human HTML/PDF/DOCX rendering and `PRINT_AND_EXPORT.md` are out of DS3: DS8/DS12 own
  human export surfaces. DS3 supplies the format-agnostic MACHINE packet only.
- DS1-N022 is closed at the HTTP/generated-client boundary by a strict HTTP projection
  of upstream `LegalFactResult`. `LexSearchResultItem` must carry trust, grounding,
  canonical/reference-resolution, structure/constraint/route, fused-confidence and
  consistency, hallucination/quality, document/version/jurisdiction/domain, temporal,
  provenance, and provision-anchor fields. The HTTP service uses the existing Lex
  owner search/store and does not reproduce its SQL or verification logic. DS10 still
  owns the UI/export presentation of these fields.

## Red-first test inventory

Add the following tests before their positive implementation and observe the expected
failure for each owned behavior:

### `tests/unit/runtime/http/test_governed_projection_service.py`

- `test_runtime_http_import_does_not_read_governed_artifacts`
- `test_projection_packets_require_identity_as_of_and_freshness`
- `test_projection_cache_reuses_content_hash_key_until_source_changes`
- `test_path_cache_detects_same_size_rewrite_with_preserved_mtime`
- `test_projection_cache_cannot_be_corrupted_through_returned_nested_payload`
- `test_projection_packets_encode_distinct_available_missing_and_invalid_states`
- `test_available_projection_payloads_are_source_specific_strict_models`
- `test_available_packet_rejects_payload_for_a_different_projection`
- `test_replay_pin_rejects_artifact_hash_mismatch`
- `test_replay_pin_rejects_projection_hash_mismatch`
- `test_malformed_single_file_sources_return_typed_invalid_source`
- `test_malformed_proving_ground_case_returns_typed_invalid_source`
- all producer tests named in the inventory table

### `tests/unit/runtime/http/test_governed_projection_api.py`

- `test_governed_projection_catalog_is_typed_and_complete`
- `test_governed_projection_endpoint_uses_runtime_api_env`
- `test_governed_projection_endpoint_preserves_existing_auth_defaults`
- `test_governed_projection_openapi_encodes_typed_states_and_payloads`
- `test_channel_registry_covers_every_active_hidden_runtime_channel`
- `test_channel_registry_rejects_unknown_channel_fields`

### Existing contract suites

- `tests/unit/runtime/http/test_lineage_api.py::test_runtime_lineage_exports_bind_shared_replay_contract`
- `tests/unit/runtime/http/test_bureaucratic_rendering_api.py::test_bureaucratic_render_and_export_bind_shared_replay_contract`
- `tests/unit/runtime/http/test_bureaucratic_rendering_api.py::test_bureaucratic_render_accepts_current_replay_pin_and_rejects_stale_pin`
- `tests/unit/runtime/http/test_bureaucratic_rendering_api.py::test_bureaucratic_render_and_export_use_tx_at_when_valid_at_is_absent`
- `tests/unit/runtime/http/test_bureaucratic_rendering_api.py::test_bureaucratic_export_preserves_publication_authority_boundary`
- `tests/unit/runtime/http/test_control_api.py::test_decision_validity_exports_bind_shared_replay_contract`
- `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py::test_every_runtime_client_transport_has_openapi_or_governed_channel_contract`
- `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py::test_reference_shell_uses_only_shared_generated_client_home`
- `tests/unit/runtime/http/test_control_api.py::test_lex_search_preserves_truth_fields_through_api`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_generated_runtime_client_includes_governed_projection_wrappers`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_openapi_typescript_output_matches_committed_shared_types`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_schema_and_clients_regenerate_byte_identically_twice`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_shared_client_generation_is_package_owned_and_version_pinned`

The generic transport test derives REST operations from the committed OpenAPI and
generated/shared callers, and raw SSE/WS constructions from source, then resolves each
against OpenAPI, the typed registry, or a merged DS19 disposition. It does not maintain
a hand-written allowlist of current active channels. Dynamic lineage paths and
`/auth/me` are mutation cases. The unmerged DS19 phantom residual is asserted and
reported separately, not silently ignored.

## Execution tasks

### Task 1: Commit this binding plan

1. Add only this file.
2. Verify `git diff --check` and `git status --short`.
3. Commit: `docs(atlas): bind DS3 runtime producer plan`.

### Task 2: Establish red tests

1. Add the service/API/transport/Lex/client-generation tests above.
2. Run focused nodes and capture expected failures in the DS3 journal.
3. Keep unrelated baseline failures separate; complete an honest isolation before any
   exclusion (`P34`).
4. Commit the red tests only after their failure reasons match the missing behavior:
   `test(atlas): seed DS3 producer contract negatives`.

### Task 3: Implement strict lazy projection packets

Files:

- Create `src/polisyos/runtime/http/services/governed_projections.py`.
- Create `src/polisyos/runtime/http/routes/governed_projections.py`.
- Modify `src/polisyos/runtime/http/app.py` only to register the optional router.

Implementation sequence:

1. Define strict audience, freshness, source identity, replay-pin, catalog-entry,
   source-specific payload, discriminated state packet, and typed-error DTOs. A packet
   validator rejects payloads belonging to a different projection ID.
2. Define the complete source registry and small source-specific projectors.
3. Add lazy JSON/TOML/composite loading with stable stat lookup and
   content-hash-keyed immutable serialized caches; no source read at import or app
   construction. Decode/composite failures preserve observed byte identity and become
   typed `invalid_source` packets.
4. Canonically hash only declared projection data.
5. Implement typed absence/invalid-source and 409 replay mismatch behavior.
6. Register catalog and packet routes under existing security defaults and optional
   FastAPI guard.
7. Run the focused service/API tests green.
8. Commit: `feat(runtime): expose governed artifact projections`.

### Task 3a: Bind the convention through existing exporters

Files:

- Add one HTTP-local export replay binding helper under
  `src/polisyos/runtime/http/services/`.
- Extend only the existing lineage OpenLineage/PROV, artifact render/export, and
  decision-validity routes.

Steps:

1. Define one strict replay-binding DTO and one documented response-header contract
   carrying stable address, narrow projection hash, replay address, and as-of.
2. Compute hashes over the owner export's stable semantic projection, excluding only
   request-envelope and observation-time fields that are carried separately.
3. Add `export_projection_hash` replay pins to existing GET exporters and the existing
   POST render exporter; a mismatched pin fails with 409 and never falls through to an
   unpinned response.
4. Resolve time roles as `valid_at -> tx_at -> request observation`, keeping
   renderer-owned observation clocks outside semantic hashes.
5. Prove render/export, OpenLineage/PROV, and decision-validity all use the helper.
6. Regenerate OpenAPI and the shared client only after these route contracts are green.

### Task 4: Govern active channels and close the HTTP Lex truth drop

Files:

- Extend the governed projection service/route with the derived channel registry.
- Add an HTTP-local strict Lex result projection under
  `src/polisyos/runtime/http/services/control/`.
- Modify `services/control/lex_pipeline.py` and `routes/control.py` only at the HTTP
  projection boundary.

Steps:

1. Derive active hidden HTTP channels from the installed runtime routes; fail if a
   hidden active route lacks a registry entry or a registry entry names no route.
2. Preserve the existing auth mechanism in registry metadata without enforcing a new
   audience rule.
3. Replace the lossy Lex response projection with an owner-result projection carrying
   all truth fields; do not duplicate owner SQL.
4. Run channel, DS1-N021-owned, and N022 tests green.
5. Commit: `feat(runtime): govern realtime channels and preserve Lex truth`.

### Task 5: Regenerate schema and consolidate the client home

Files:

- Regenerate `schemas/runtime_api_v1.openapi.json`.
- Regenerate `packages/runtime-api-client/runtimeApiClient.ts` and `.js`.
- Add generated `packages/runtime-api-client/types.ts` and update only package-local
  config/docs/architecture fence as required.
- Modify `apps/runtime-reference-shell/app.js` only to exercise the catalog through the
  package; no new page/route.

Canonical commands (serial where shared scratch is involved):

```bash
PYTHONPATH=src uv run python -c 'from pathlib import Path; import json; from polisyos.runtime.http.app import export_runtime_openapi_schema; Path("schemas/runtime_api_v1.openapi.json").write_text(json.dumps(export_runtime_openapi_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")'
npx --yes openapi-typescript@7.13.0 schemas/runtime_api_v1.openapi.json -o packages/runtime-api-client/types.ts
PYTHONPATH=src uv run python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js
```

Run the sequence twice and compare hashes/working-tree diff. Commit schema and clients
together: `build(runtime): regenerate shared API client contract`.

### Task 6: Targeted verification and architect-review handoff

Run, serially:

```bash
uv run pytest -q tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_governed_projection_api.py
uv run pytest -q tests/unit/runtime/http/test_control_api.py -k 'lex_search_preserves_truth_fields_through_api'
uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py -k 'governed_projection or openapi_typescript or regenerate_byte_identically or committed_runtime_client'
uv run pytest -q tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py
uv run ruff check src/polisyos/runtime/http/app.py src/polisyos/runtime/http/routes/governed_projections.py src/polisyos/runtime/http/services/governed_projections.py src/polisyos/runtime/http/routes/control.py src/polisyos/runtime/http/services/control tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_governed_projection_api.py tests/unit/runtime/http/test_control_api.py tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py
corepack pnpm --dir packages/runtime-api-client run typecheck
corepack pnpm --dir packages/runtime-api-client run test
corepack pnpm --dir packages/runtime-api-client run check:architecture
corepack pnpm --dir apps/runtime-reference-shell run typecheck
corepack pnpm --dir apps/runtime-reference-shell run check:architecture
```

No full pytest or browser suite. Re-open the failure/repair register before closeout.

## Closure contract

The architect-review handoff includes:

1. A final producer table: producer -> source artifact -> exact narrow projection hash
   -> consumer -> audience -> passing test, including honest absence rows.
2. The active channel registry and an explicit DS19-owned collaboration/uncalled
   residual (or consumed DS19 disposition if it merged).
3. The client-home decision, rejected alternative, revisit condition, and proof that
   the reference shell imports only the package home.
4. Two-run byte-identity receipts for OpenAPI, `types.ts`, and runtime client outputs.
5. Fresh targeted pytest, Ruff, package/reference-shell typecheck/test/architecture
   receipts.
6. `git diff --stat main...HEAD`, `git diff --check`, path-fence audit, scoped commits,
   and a clean tree.
7. No claims of readiness/outcome authority for missing live readiness or proving-
   ground result artifacts; no claims that DS5/DS10/DS15/DS16/DS20 enforcement or UI
   work is complete.
8. Stop without merge for architect review.
