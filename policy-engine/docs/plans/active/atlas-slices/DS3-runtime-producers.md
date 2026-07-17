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
An isolated, lazy subprocess invokes each artifact owner's validator against exact
path-to-byte-hash bindings and the exact projected payload before an available packet
can be emitted. The worker records every repository file, directory listing, and
missing path consulted by the validator; cached PASS receipts are reused only after
those transitive identities still match. Missing validator dependencies, drift,
timeouts, and malformed receipts fail closed as typed `invalid_source`. The owner
worker supplies the semantic projection hash and rule version; the HTTP producer
projects owner-recorded and validator-produced facts but never recreates owner
semantics. Existing OpenLineage/PROV, artifact render/export, and decision-validity
endpoints remain the export implementations this packet convention complements, not a
second renderer stack.

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
`GET /api/v1/exports/governed-projections`; replay is the same stable address plus
`artifact_content_hash`, `projection_hash`, `source_dependency_hash`, and
`source_as_of` query pins. Every packet declares `projection_id`, `availability`,
packet schema version, mandatory projection rule version, optional owner source
schema/rule versions, `audience`,
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
| `acquisition-routing-contract` | `architecture/policy_design_case/layer3_gy_acquisition_contract.json` | Denominators, positive/no-result receipts, fail-closed receipt, grounding request, recorded rederive inputs and economics | DS7 base route, DS15 acquisition surface | MACHINE | `test_acquisition_contract_projection_preserves_owner_receipts`; recursive capture-provenance immunity and semantic-producer binding tests |
| `n13a-acquisition-census` | `architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json`, optional until upstream merge/file presence | Observed catalog identity, projection bindings, family scorecards, metric resolutions, route evidence, growth backlog, fetch-plan generation | DS15 acquisition surface, DS7 route context | MACHINE | `test_n13a_census_returns_typed_absence_when_source_is_missing`; `test_n13a_census_fails_closed_when_recompute_catalog_is_absent`; `test_n13a_valid_catalog_recomputes_through_service_within_bridge_budget`; `test_n13a_canonical_recompute_rejects_corrupt_decisive_metric` |
| `n13a-live-probe-journal` | `architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json`, optional until upstream merge/file presence | Observed selection plan, family receipts, and probe records; no new success inference | DS15 acquisition audit | EXPERT | `test_n13a_probe_journal_returns_typed_absence_when_source_is_missing`; `test_n13a_probe_journal_fails_closed_when_recompute_catalog_is_absent`; `test_n13a_journal_drift_cannot_bypass_missing_recompute_catalog` |
| `capability-reality` | `architecture/policy_design_case/capability_reality_report.json` | Summary/readiness, capability claims, blockers/issues, chain clusters, ratchet integrity; no new readiness calculation | DS6 validation, DS7 capability truth | MACHINE | `test_capability_reality_fails_closed_on_current_owner_validator_drift`; all-null and owner-identity negatives |
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

Projection hashes come only from the owner worker's semantic hash implementation over
the source-specific projection DTO. The HTTP service has no local field blacklist or
semantic hasher. Each PASS receipt binds the exact projected-payload hash plus a
content identity for every transitive validator dependency. The acquisition projector
omits its governed provenance envelopes before validation, while semantic producer
identities remain in the projection. A table-driven nested receipt-provenance test
requires the artifact hash to change while the owner semantic projection hash remains
identical; the legacy cohort hash covers only identity plus declared semantic
expectations. Replay pins bind four roles: source bytes, owner semantic projection,
transitive validation dependencies, and source time. Thus provenance-only upstream
rebaselines remain compatible, but validator-code/data drift and identical bytes with
changed filesystem observation time cannot replay under stale authority.

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
3. Generate the shared schema types at `packages/runtime-api-client/types.ts` using exactly
   `export_runtime_openapi_schema() -> schemas/runtime_api_v1.openapi.json -> npx
   --yes openapi-typescript@7.13.0`. The exact generator pin is package-owned and has
   no dashboard-local dependency; DS3 keeps the lockfile unchanged per its fence.
   The unchanged repository generator still produces `runtimeApiClient.ts/js` for its
   canonical drift checker. A package-owned deterministic postprocessor aliases every
   generated DTO to `types.ts` and emits `canonicalRuntimeApiClient.ts/js`; package
   `main`, `types`, and `exports` expose only that typed twin.
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
| `runs-list-live` | `/api/v1/runs/live` | SSE `policyos.runtime.runs_channel_data_event.v1`; discriminated snapshot/timeout variants through one final encoder | tenant runtime access + stream rate limit | dashboard `RunsLiveProvider` | Active typed producer; consumer verification remains `verification_missing`; keep `include_in_schema=False` |
| `run-detail-live` | `/api/v1/runs/{run_id}/live` | SSE `policyos.runtime.runs_channel_data_event.v1`; discriminated snapshot/timeout variants through one final encoder | run tenant access + stream rate limit | dashboard run live hook | Active typed producer; consumer verification remains `verification_missing`; keep `include_in_schema=False` |
| `review-live` | `/api/v1/review/live`, `review.presence`, `review.cursor`, `review.lock` | WS `policyos.runtime.review_collaboration_envelope.v1`, validated before transport error handling | review socket authentication, tenant binding, OPA action check, stream rate limit | dashboard review collaboration surface | Active typed producer; consumer verification remains `verification_missing`; DS5 owns browser auth/degradation enforcement |

The dashboard's `/api/v1/collaboration/**` REST and `/api/v1/collaboration/live`
transports were phantom at plan time. `main` later advanced through DS19 merge
`f9f69e807` and gained register authority at
`architecture/atlas_surfaces/frontend-disposition-register.json`. DS3 observes that
authority out of band: `feature-collaboration`, `transport-rest-collaboration`, and
`transport-ws-collaboration` are dated `deleted` and `strangled` dispositions. This
branch does not contain that merge or register and still has five dashboard caller
transports, so DS19 integration is `verification_missing`, not consumed or verified.
DS3 adds no phantom HTTP producer or registry entry. The transport contract test
classifies the live branch as `pre_merge_collaboration_residual` and permits only the
enumerated collaboration residual. If a later branch contains the canonical register,
the same test requires actual zero residual callers; a register-shaped fixture cannot
substitute for that caller scan.

The out-of-band register records the 37 uncalled OpenAPI dispositions at 13 `wire` and
24 `retire`. They remain disposition authority, not implementation evidence: the register
explicitly forbids using a frontend-only decision to delete server endpoints and
forbids claiming pending rebind/retirement as implemented. DS3 records those decisions
as build-or-remove recommendations only, without deleting endpoints or adding UI
consumers; later owning slices must execute and verify the wire/retire actions.

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
- `test_owner_validation_receipt_rejects_forged_aggregate_binding`
- `test_projection_packets_require_identity_as_of_and_freshness`
- `test_projection_cache_reuses_content_hash_key_until_source_changes`
- `test_path_cache_detects_same_size_rewrite_with_preserved_mtime`
- `test_projection_cache_cannot_be_corrupted_through_returned_nested_payload`
- `test_owner_validation_cache_revalidates_when_semantic_hasher_bytes_drift`
- `test_owner_validation_cache_binds_exact_projected_payload`
- `test_n13a_valid_catalog_recomputes_through_service_within_bridge_budget`
- `test_replay_identity_and_pin_bind_owner_validation_dependencies`
- `test_n13a_owner_hash_ignores_run_economics_but_replay_binds_changed_bytes`
- `test_projection_packets_encode_distinct_available_missing_and_invalid_states`
- `test_available_projection_payloads_are_source_specific_strict_models`
- `test_available_packet_rejects_payload_for_a_different_projection`
- `test_replay_pin_rejects_artifact_hash_mismatch`
- `test_replay_pin_rejects_projection_hash_mismatch`
- `test_replay_identity_binds_filesystem_fallback_as_of_for_identical_bytes`
- `test_malformed_single_file_sources_return_typed_invalid_source`
- `test_malformed_proving_ground_case_returns_typed_invalid_source`
- all producer tests named in the inventory table

### Owner-validation and channel behavior

- `test_all_null_capability_report_fails_owner_validation`
- `test_component_hash_mismatch_fails_before_owner_validator`
- `test_owner_receipt_binds_cluster_validator_transitive_dependencies`
- `test_owner_receipt_binds_canonical_semantic_hasher_source`
- `test_projection_hash_is_computed_by_canonical_gy_hash_owner`
- `test_n13a_fails_closed_without_canonical_recompute_catalog`
- `test_n13a_canonical_recompute_rejects_corrupt_decisive_metric`
- `test_n13a_journal_drift_cannot_bypass_missing_recompute_catalog`
- `test_normal_projection_import_does_not_import_owner_validators`
- `test_hidden_runs_sse_channels_emit_versioned_contracts`
- `test_runs_sse_emission_rejects_marker_complete_malformed_payload`
- `test_runs_sse_timeout_emits_a_versioned_strict_contract`
- `test_runs_sse_final_encoder_rejects_malformed_timeout_data`
- `test_runs_sse_snapshot_and_timeout_share_final_data_encoder`
- `test_runs_sse_keepalive_comment_bypasses_data_encoder`
- `test_review_websocket_snapshots_emit_versioned_contract_identity`
- `test_dispatch_rejects_marker_complete_malformed_review_snapshot`

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
- `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py::test_ds19_integration_requires_register_and_zero_callers`
- `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py::test_reference_shell_executes_shared_generated_client_proof`
- `tests/unit/runtime/http/test_control_api.py::test_lex_search_preserves_truth_fields_through_api`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_generated_runtime_client_includes_governed_projection_wrappers`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_openapi_typescript_output_matches_committed_shared_types`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_schema_and_clients_regenerate_byte_identically_twice`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_shared_client_generation_is_package_owned_and_version_pinned`

The generic transport test derives REST operations from the committed OpenAPI and
generated/shared callers, and raw SSE/WS constructions from source, then resolves each
against OpenAPI, the typed registry, or the content-checked DS19 collaboration
disposition. It does not maintain a hand-written allowlist of current active channels.
Dynamic lineage paths and `/auth/me` are mutation cases. The pre-merge DS19 phantom
residual is asserted and reported separately; canonical register presence changes the
assertion only when the live caller scan is also zero.

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
- Regenerate compatibility-owned `packages/runtime-api-client/runtimeApiClient.ts` and
  `.js`, then deterministically derive public `canonicalRuntimeApiClient.ts` and `.js`.
- Regenerate `packages/runtime-api-client/types.ts` and update only package-local
  config/docs/architecture fence as required.
- Modify `apps/runtime-reference-shell/app.js` only to exercise the catalog through the
  package; no new page/route.

Canonical commands (serial where shared scratch is involved):

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate
```

Run the sequence twice and compare hashes/working-tree diff. Commit producer, schema,
and generated-client changes atomically so no commit exposes a producer/schema/client
contract mismatch.

### Task 6: Targeted verification and architect-review handoff

Run, serially:

```bash
uv run pytest -q tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_governed_projection_validation_worker.py tests/unit/runtime/http/test_governed_projection_api.py
POLISYOS_N13A_PRODUCTION_CATALOG=/absolute/read-only/catalog.duckdb uv run pytest -q tests/unit/runtime/http/test_governed_projection_service.py::test_n13a_valid_catalog_recomputes_through_service_within_bridge_budget
POLISYOS_N13A_PRODUCTION_CATALOG=/absolute/read-only/catalog.duckdb uv run pytest -q tests/unit/runtime/http/test_governed_projection_validation_worker.py::test_n13a_canonical_recompute_rejects_corrupt_decisive_metric
uv run pytest -q tests/unit/runtime/http/test_review_collaboration_service.py tests/unit/runtime/http/test_review_collaboration_api.py tests/unit/runtime/http/test_runs_api.py -k 'not evaluate_feedback_endpoint and not reissue_endpoint'
uv run pytest -q tests/unit/runtime/http/test_control_api.py -k 'lex_search_preserves_truth_fields_through_api'
uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py -k 'openapi_contract_includes_examples or governed_projection or openapi_typescript or regenerate_byte_identically or committed_runtime_client'
uv run pytest -q tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run ruff check src/polisyos/runtime/http/openapi_contract.py src/polisyos/runtime/http/routes/governed_projections.py src/polisyos/runtime/http/routes/runs.py src/polisyos/runtime/http/services/channel_contracts.py src/polisyos/runtime/http/services/governed_projection_dependencies.py src/polisyos/runtime/http/services/governed_projection_validation_worker.py src/polisyos/runtime/http/services/governed_projections.py tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_governed_projection_validation_worker.py tests/unit/runtime/http/test_governed_projection_api.py tests/unit/runtime/http/test_runs_api.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py
corepack pnpm --dir packages/runtime-api-client run typecheck
corepack pnpm --dir packages/runtime-api-client run test
corepack pnpm --dir packages/runtime-api-client run check:architecture
corepack pnpm --dir packages/runtime-api-client run lint
corepack pnpm --dir packages/runtime-api-client run format:check
corepack pnpm --dir apps/runtime-reference-shell run typecheck
corepack pnpm --dir apps/runtime-reference-shell run test
corepack pnpm --dir apps/runtime-reference-shell run check:architecture
corepack pnpm --dir apps/runtime-reference-shell run lint
corepack pnpm --dir apps/runtime-reference-shell run format:check
```

No full pytest or browser suite. Re-open the failure/repair register before closeout.

## Closure contract

The architect-review handoff includes:

1. A final producer table: producer -> source artifact -> exact narrow projection hash
   -> consumer -> audience -> passing test, including honest absence rows.
2. The active channel registry plus the out-of-band DS19 collaboration and 37-operation
   dispositions, with integration labeled `verification_missing` until the canonical
   register and zero-residual dashboard state are present together, and without
   treating decision-only rows as implemented capability.
3. The client-home decision, rejected alternative, revisit condition, and proof that
   the reference shell imports only the package home.
4. Two-run byte-identity receipts for OpenAPI, `types.ts`, raw compatibility outputs,
   and public canonical client outputs.
5. Fresh targeted pytest, Ruff, package/reference-shell typecheck/test/architecture
   receipts.
6. `git diff --stat main...HEAD`, `git diff --check`, path-fence audit, scoped commits,
   and a clean tree.
7. No claims of readiness/outcome authority for missing live readiness or proving-
   ground result artifacts; no claims that DS5/DS10/DS15/DS16/DS20 enforcement or UI
   work is complete.
8. Stop without merge for architect review.
