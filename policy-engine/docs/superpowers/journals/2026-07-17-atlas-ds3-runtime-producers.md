# Atlas DS3 Runtime Producers & Export Infrastructure Journal

## 2026-07-17 — binding and red phase

- Created the fenced worktree `.worktrees/atlas-ds3` on
  `codex/atlas-ds3-runtime-producers` from `7b6933770`.
- Read the Revision-3 preamble, Phase-A rebaseline, DS3 master section, synthesis
  PI-01..PI-03, DS1 N021/N022, GY §3.5.10/§3.5.11, contributor rules, and the
  failure/repair register before design.
- Committed the binding plan as `9516d35cb`.
- Baseline runtime-fixture collection did not reach a test in three minutes: the
  existing eager `runtime.http.services -> runtime.quality -> scientist -> foundry`
  import chain was still loading the causal catalog. It was interrupted and recorded,
  not classified as a DS3 test failure. The DS3 service will remain import-lazy; final
  fixture verification must be rerun after implementation.

### Observed red receipts

All commands used plugin-autoload-disabled pytest only to isolate the new contract from
the unrelated eager startup chain; final verification uses the repository command.

1. `test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving`
   failed collection because
   `src/polisyos/runtime/http/services/governed_projections.py` did not exist.
2. `test_reference_shell_uses_only_shared_generated_client_home` failed because the
   package client had no `listGovernedProjections()` proof call.
3. `test_committed_openapi_preserves_lex_truth_fields` failed because the committed Lex
   result schema lacked the upstream grounding, authority, hallucination, document,
   temporal, provenance, and provision-anchor fields.
4. `test_committed_openapi_has_governed_export_contracts` failed because all three DS3
   export/channel paths were absent.

The failures match the missing producer/client/contract behavior. No positive runtime
implementation existed when they were captured.

## 2026-07-17 — implementation and closure

### Scoped commit sequence

1. `9516d35cb` — binding task plan.
2. `e979a5cf4` — red producer/client/contract tests.
3. `34545cdde` — lazy governed artifact projections and channel registry.
4. `a92fcce6e` — Lex owner-result truth fields preserved through HTTP.
5. `3b2c2cd91` — shared generated-client home, OpenAPI/types, and reference-shell proof.
6. `48118be16` — shared replay binding through existing owner exporters.
7. `9a0e2b743` — initial closure evidence and architect-review handoff.
8. `99090d923` — close the independent review's producer/replay/type findings.
9. The commit containing this journal — final repair receipts and fence evidence.

### Independent architect-review repair pass

The first independent review returned **not ready** with one Critical and eight
Important findings. Each was reproduced before repair:

- `{}` at the exact readiness path was incorrectly available and authority-looking;
  Revision-2 content at that path was also accepted.
- Available payloads were one `dict[str, Any]`, empty projections could pass, and the
  available/missing/invalid state invariants were not encoded.
- Nested receipt observation time changed the acquisition projection hash, while the
  legacy proving-ground projection included producer metadata and full case records.
- A returned nested dictionary could mutate the cached payload without changing its
  cached projection hash.
- Malformed JSON/TOML/composite sources escaped as exceptions rather than typed
  `invalid_source` packets.
- Five owner artifacts had no source rule, so the packet lacked an always-present
  producer/projection rule version; the N13a census also mislabeled its journal binding
  as its own declared content hash.
- POST artifact render advertised replay but ignored the replay pin, and render/export
  ignored `tx_at` when `valid_at` was absent.
- The shared type generator still depended on the rejected dashboard-local install.

The repair added strict source-specific payload DTOs, a discriminated state union plus
projection/payload validator, mandatory `policyos.runtime.governed_projection.v1`,
immutable serialized cache entries, stable-stat verification including inode/ctime,
typed load-error translation, named related-artifact bindings, nested provenance hash
exclusions, and narrowed 13-case expectations. Readiness now remains absent when the
live file is absent and fails as `invalid_source` for fake/malformed/Revision-2 bytes;
no DS3-local owner schema was invented. Artifact replay now accepts a POST query pin,
normalizes renderer-owned observation clocks out of the semantic hash, and resolves
time roles as `valid_at -> tx_at -> observation`. The shared package invokes exact
`openapi-typescript@7.13.0` directly without a dashboard or lockfile dependency.

Final TypeScript verification also caught and closed a generated-name collision between
the client generator's `JsonValue` and Pydantic's first generic JSON schema. The final
contract uses a non-recursive `ProjectionJsonValue` schema for nested owner JSON while
keeping every producer's top-level dependency fields strict and required.

### Producer closure inventory

Hashes below were read from the final producer against the governed artifacts in this
worktree. `surface-readiness` is intentionally an honest absence, not a projection of
the ineligible example or DS1 audit ledger.

| Producer | Artifact identity | Narrow projection hash | Consumer slice | Audience | Passing semantic test |
|---|---|---|---|---|---|
| `depth-n-cycle-board` | `layer3_gy_depth_n_universality_contract.json`<br>`sha256:29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6` | `sha256:381810985e695cbf29f0f00fc17f291b5c68610897a608251c070294ff9d4379` | DS7 Cycle Board / DS8 drilldown | MACHINE | `test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving`; unseen-label and provenance-only-rebaseline tests |
| `value-gate` | `layer3_gy_value_gate_contract.json`<br>`sha256:755d67837fd74b7e7fb35aff6ae3b355f5b1fafd9381b8964d1a02a18ae937cb` | `sha256:d42cca389816c466d95b7d87c3eda11abc64afb7021182d43f3c47b5f015d541` | DS7 value column / DS16 | MACHINE | `test_value_gate_projection_contains_denominators_receipts_and_outer_set_slots` |
| `generation-cycle-disposition` | `layer3_gy_generation_cycle_disposition_ledger.json`<br>`sha256:69757955ac4797e916a439bd19484278cfee5fa7da732c52e75f0b2e76e57e10` | `sha256:b5f9771158af35b72a7c3c7354273b86667ddcb9f017e2d2c39ce9d265ada4e5` | DS7 honesty / DS10 explanation | EXPERT | `test_disposition_projection_is_narrow_and_audience_declared` |
| `engine-census` | `layer3_gy_engine_census.json`<br>`sha256:ca72e8bb9eda519b9da9f2c81d0069e2b7cb940308ad8c012b99f241f2652dd3` | `sha256:063147caa2de7e89a6730e4d7955d840be9f5a3a747910af968cabd582d2e06c` | DS7 / DS10 census | EXPERT | `test_engine_census_projection_omits_full_rows` |
| `fork-b-relation-census` | `layer3_gy_n10_cg1_l2_relation_census.json`<br>`sha256:1c004559fe41cc84296ebb05edcfd4f5f95ade9542b2992aa52543ccb0c3bca4` | `sha256:d34cca7c3a9c5bf8f707497d4be845d3d6f42dbc5ba915a71f44e16a664e5c22` | DS7 / DS10 census | MACHINE | `test_fork_b_projection_omits_relation_table_and_binds_counts` |
| `acquisition-routing-contract` | `layer3_gy_acquisition_contract.json`<br>`sha256:23ebac67c73963be8bd64fb3052d785904d1b7a7bcbea6ee79fecea9c5539bdd` | `sha256:85cc338a2bc9870ebb685f23ca5ce515cb6a5ff6b8c4069d46bdbd23df58f3b3` | DS7 base route / DS15 | MACHINE | receipt preservation and nested provenance-rebaseline tests |
| `n13a-acquisition-census` | `layer3_gy_n13a_acquisition_census.json`<br>`sha256:63212c8ccdcd80e96f8ae5903a74e4587090cfe096392e00069d30c17ba64791` | `sha256:4f7e57e921e6034d6dd3fa2c063e941898065a6688ffda7e2520dca0a2c35f8e` | DS15 / DS7 route context | MACHINE | present-source and typed-absence tests |
| `n13a-live-probe-journal` | `layer3_gy_n13a_live_probe_journal.json`<br>`sha256:027b3824f77c325ec4550afbf1ea75fb7a4b70c78070d6bb3cb471d73110d3fd` | `sha256:4c1d2cbaf542b29a56c5e9212b53dac72222e58989bb77008b42134bfe7ed462` | DS15 audit | EXPERT | present-source and typed-absence tests |
| `capability-reality` | `capability_reality_report.json`<br>`sha256:9a0a8baf637a886a059729b36902cad56b33443cf05cfa59adb32ccbd1dc20c6` | `sha256:123def0f14990752d5319c5fb2d2ed2b6f6a87a2c045195b4c4ce91add087521` | DS6 / DS7 | MACHINE | `test_capability_reality_projection_uses_reported_readiness` |
| `cluster-ownership` | `cluster_ownership_map.toml`<br>`sha256:b9409bc276d77d60919fab996ced4d01189c276eb38edad1eaa23e831edd69f4` | `sha256:577e68ce31aaa16a16ef6735f946770c9c821b9631bf6b852a86751c3bbc9bb7` | DS6 / DS7 | EXPERT | `test_cluster_ownership_projection_parses_toml_without_reclassifying_cells` |
| `layer3-health-metrics` | `layer3_health_metric_ledgers.toml`<br>`sha256:1b3f19fc0d039a417dbdd45ccada02be9e1998a340cedcbf85d67b7925e97ac5` | `sha256:2f097e220103821a3ae4f30fc6aec7b9535dd436abe9e8e1958d281fae39f26b` | DS6 instrumentation | MACHINE | `test_layer3_health_projection_preserves_freeze_values` |
| `legacy-proving-ground` | 13 fixture identities<br>`sha256:c289f814835f60178b54fd6edeb5748d3c58865f8257ab9afabd4768637aa0c7` | `sha256:bb8e9a536ee4bdd5fcca797bba91974d7a30fd2951777fca59ac8555d16742d5` | DS7 legacy cohort | EXPERT | identity, fixture-not-runtime-outcome, and metadata-rebaseline tests |
| `surface-readiness` | canonical live ledger absent (`artifact_missing`) | none (`projection_missing`) | DS6 / DS7 | MACHINE | example, typed-absence, present-fake, and Revision-2 rejection tests |

### Shared export and channel governance

`policyos.runtime.export_replay_binding.v1` is used by governed packets and the existing
OpenLineage/PROV, artifact render/export, and decision-validity routes. The common
helper owns canonical narrow hashing and replay-address construction. Existing GET
exporters and POST artifact render accept `export_projection_hash`; a stale pin returns
409. Renderer observation clocks are excluded from semantic hashes, and validity time
precedes transaction time, which precedes request observation. Every bound response
carries stable address, projection hash, replay address, and as-of headers. The artifact
negative also proves replay work did not bypass a `may_not_use_for: publication`
boundary.

| Registry ID | Path | Contract | Auth class | Consumer |
|---|---|---|---|---|
| `runs-list-live` | `/api/v1/runs/live` | `policyos.runtime.runs_list_snapshot.v1` | `runtime_tenant_access+stream_rate_limit` | dashboard `RunsLiveProvider` |
| `run-detail-live` | `/api/v1/runs/{run_id}/live` | `policyos.runtime.run_detail_snapshot.v1` | `runtime_run_tenant_access+stream_rate_limit` | dashboard `useRunLiveUpdates` |
| `review-live` | `/api/v1/review/live` (`review.cursor`, `review.lock`, `review.presence`) | `policyos.runtime.review_collaboration_envelope.v1` | `runtime_review_socket_auth+tenant_opa_action+stream_rate_limit` | dashboard review collaboration surface |

DS19's disposition register was not merged during DS3. The dated DS3 recommendation
for phantom `/api/v1/collaboration/**` REST/live traffic remains remove/strangle
(2026-07-17); DS3 did not add, delete, register, or exempt it. The 37 uncalled OpenAPI
operations remain untouched for DS19 disposition.

### Client-home decision and generation receipt

- Selected: `packages/runtime-api-client`, proven by the reference shell calling
  `listGovernedProjections()` through that package.
- Rejected: dashboard-local generated ownership, because it reverses the dependency for
  the reference shell and later MACHINE twins.
- Revisit only if the dashboard becomes the sole runtime consumer and the package has
  no external/reference-shell consumer, or an approved workspace-wide SDK supersedes
  both homes.
- Dashboard source and lockfiles were not changed.
- The package now owns exact `npx --yes openapi-typescript@7.13.0`; regeneration has
  no dependency on `apps/runtime-dashboard`.

The final canonical generation sequence ran twice with byte-identical results:

| Generated file | SHA-256 on run 1 and run 2 |
|---|---|
| `schemas/runtime_api_v1.openapi.json` | `2b30cf8a84f3fe985e16a0edc2f45346fcc80149ac61b718d0fed4ef04d5b79e` |
| `packages/runtime-api-client/types.ts` | `706b0048f642c85ea7cd8fe8c3c3960a7d13f4dc26c2045cd38e1f1c04c74260` |
| `packages/runtime-api-client/runtimeApiClient.ts` | `fe5deb1641bc0f82a34ac7d45191e54a98a003b79d71bad3424ebe3d872c5243` |
| `packages/runtime-api-client/runtimeApiClient.js` | `40b63431602abd2e1ad9f9dc69bae17657b1e8d638db9192bc03184d04a0d5eb` |

### Fresh targeted verification receipts

- Governed projection service: 39 passed, including typed-state/payload, fake-source,
  malformed-source, cache-isolation, narrow-hash, and stable-stat negatives.
- Governed projection/channel API file: 6 passed.
- Existing artifact render/export file, including publication, POST pin, and tx-only
  negatives: 8 passed.
- Existing lineage file, including no-cursor PROV and replay: 6 passed.
- Lex plus decision-validity run/packet/replay selection: 4 passed.
- OpenAPI/client regeneration contract selection: 5 passed.
- Runtime client-home/transport bridge: 5 passed.
- Ruff check: all 18 changed Python paths passed.
- Shared client: TypeScript, two Node tests, architecture, ESLint, and Prettier passed.
- Reference shell: TypeScript, architecture, ESLint, and Prettier passed.
- No full pytest or browser suite was run, per DS3 scope.

### Fence and authority closeout

- `git diff --check` passed; no files were deleted.
- Final `git diff --stat main...HEAD`: 30 files, 26,629 insertions,
  1,124 line replacements/removals (predominantly generated schema/types).
- Every changed path is inside the DS3 fence: runtime HTTP, schema, shared client,
  reference-shell proof, scoped tests, the DS3 plan, and this journal.
- No runtime-quality, fabric, foundry, scientist, data-forge, dashboard source,
  architecture register, production-data, brand, or lockfile path changed.
- Missing live readiness remains `artifact_missing`; proving-ground expectations remain
  `fixture_only` with runtime outcomes absent. Audience enforcement remains DS20/DS5.
- Branch stops unmerged for architect review.
