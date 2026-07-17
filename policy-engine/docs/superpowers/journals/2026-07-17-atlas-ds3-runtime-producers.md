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
2. The historical red-only
   `test_reference_shell_uses_only_shared_generated_client_home` failed because the
   package client had no `listGovernedProjections()` proof call. Its final behavioral
   replacement is `test_reference_shell_executes_shared_generated_client_proof`.
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
9. `8a4db34e2` — repair evidence, client checks, and first-review closure record.
10. `952a52a44` — bind projections to owner validators, type active channels, and
    regenerate the shared contract.
11. `202c1e48f` — add the initial DS19 disposition resolver and transport gate; the
    exact-head review later rejected its synthetic zero-residual proof, corrected below.
12. `c9a477a9f` — close the second independent-review record.
13. `7050786f2` — atomic exact-head producer/schema/client repair and verification.
14. Final closure evidence — this plan/journal commit.

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

### Second independent review and repair pass

The second independent review of `8a4db34e2` again returned **not ready**. It found that
top-level payload names were still insufficient evidence because nested owner data was
accepted without a content-bound validator; recursive provenance filtering missed the
real `capture_provenance` containers; the hidden-channel registry remained
contract-by-string while SSE/WS producers emitted dictionaries; the N13a journal's
owner semantic hash was mislabeled as byte identity; and replay did not bind an
`as_of` derived from filesystem mtime.

The repair observes P32/P29 rather than adding markers:

- An isolated worker invokes each canonical owner validator against exact component
  path-to-SHA-256 bindings. The parent verifies validator/version, every component
  identity, and the aggregate identity before caching a receipt. Dependency absence,
  timeout, malformed receipt, component drift, or owner issues produce a typed
  `invalid_source`; owner modules remain absent from normal HTTP imports.
- Top-level payload fields are source-specific types. All-null, wrong-shape,
  unrecognized owner identity, forged aggregate receipt, and component-drift probes
  fail. The canonical N13a validator additionally proves the census-to-journal semantic
  hash handshake.
- Provenance-only recursion covers each actual `capture_provenance` path, while a
  control proves semantic owner content and semantic producer identity still change the
  projection hash.
- The N13a related binding now names `owner_semantic_hash` separately from the resolved
  journal `artifact_content_hash` and states its semantic rule version.
- Replay addresses and request pins include `source_as_of`; identical bytes with a
  changed mtime retain their semantic projection hash but fail the stale time pin.
- Runs SSE and review WS payloads are strict versioned DTOs validated at final emission.
  The channel registry resolves their actual producer classes and honestly labels
  dashboard-consumer verification as `verification_missing`.
- The repository runtime contract checker initially exposed missing success examples
  and noncanonical Unicode serialization. The three DS3 GETs now have examples in the
  existing OpenAPI augmentation map, and the schema is produced by the canonical
  repository exporter.

### Exact-head review and structural repair pass

The independent review of `c9a477a9f` returned **not ready**. It demonstrated that the
N13a worker checked only schema/self-consistency rather than the canonical recomputation;
cached owner PASS receipts omitted transitive validator inputs; the HTTP service still
owned a provenance-field blacklist; N13a replay omitted journal/catalog identity; the
DS19 gate could claim closure from a synthetic register fixture; SSE timeout data
bypassed the typed final emitter; and the generated client/reference-shell proof lost
OpenAPI literal/discriminator truth and asserted only source markers.

The repair closes those classes rather than their examples:

- The worker calls the canonical N13a `--check` entrypoint with its catalog, capstone,
  substrate, value-gate, census, and journal inputs. Catalog absence fails closed as
  `owner_validator_dependency_missing_catalog`; a read-only production-catalog witness
  proves a corrupt decisive `binding_count` is rejected as `census_artifact_invalid`.
- A lightweight worker-only dependency tracker records file bytes, directory listings,
  and absences consulted by every owner validator. The parent re-hashes the complete
  manifest before a cache hit, binds its aggregate into packet/replay identity, and
  also keys the receipt by the exact projected payload. Same-size, preserved-mtime
  dependency drift and changed-payload/same-source probes both force revalidation.
- Semantic projection hashes and rule versions now come only from the owner worker
  (`gy_content_hash` or N13a `semantic_content_hash`). The HTTP-local provenance
  blacklist was deleted; narrow acquisition provenance is omitted by the governed
  projector before validation.
- Both SSE snapshot and timeout variants pass through one discriminated
  `RunsChannelDataEvent` encoder. Keepalive comments remain the only non-data bypass,
  and the channel registry names the union rather than one happy-path snapshot.
- DS19 integration requires the canonical register and an actual zero-caller scan as
  one conjunction. On this pre-merge branch the five residual calls are reported as
  `pre_merge_collaboration_residual`, so integration remains `verification_missing`.
- `packages/runtime-api-client` exposes a deterministic canonical twin whose DTOs are
  aliases to `openapi-typescript` output. The raw generator pair remains byte-identical
  for the existing repository drift checker. The reference shell executes a real
  generated-client call with a stub transport and verifies both success and failure.

### Final exact-head review and repair pass

The next independent review found two remaining blockers. First, the dependency receipt
did not bind the already-imported canonical semantic-hasher module
`src/polisyos/pdc/_impl/gy_waist.py`, so a cached PASS could survive owner-source drift.
Second, the catalog-backed N13a witness exercised only the worker and ran at the old
60-second service timeout boundary; there was no catalog-backed positive through the
actual service bridge.

Both were captured red before repair. The worker dependency tracker now records every
repository-backed module loaded by the canonical owner validator, normalizing bytecode
paths to source. The exact `gy_waist.py` drift test forces cache revalidation, and the
receipt test proves that module is bound. For N13a, the worker temporarily scopes the
canonical checker's repository root to the requested fixture root, the service budget is
120 seconds (above the owner artifact's measured 82.5-second capture), and a read-only
catalog-backed service test proves a valid census becomes `available`. A separate
catalog-backed corrupt decisive-metric test still fails for `census_artifact_invalid`.
The same independent reviewer rechecked the exact repaired tree and returned **READY**
with no new Critical or Important finding.

### Producer closure inventory

Hashes below were read from the repaired producer against the governed artifacts in
this worktree. Five sources pass their owner validators and expose projection and
transitive dependency hashes, seven fail closed under current owner
validation/dependency reality, and readiness is absent.
`surface-readiness` is intentionally an honest absence, not a projection of the
ineligible example or DS1 audit ledger.

| Producer | Artifact identity | Current state / owner projection hash / dependency hash | Consumer slice | Audience | Passing semantic test |
|---|---|---|---|---|---|
| `depth-n-cycle-board` | `layer3_gy_depth_n_universality_contract.json`<br>`sha256:29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6` | `invalid_source`; no exported projection hash; `owner_validator_dependency_missing_ortools_sat_python_cp_model` | DS7 Cycle Board / DS8 drilldown | MACHINE | recorded-output, missing-witness, unseen-label, provenance-only, and missing-owner-dependency tests |
| `value-gate` | `layer3_gy_value_gate_contract.json`<br>`sha256:755d67837fd74b7e7fb35aff6ae3b355f5b1fafd9381b8964d1a02a18ae937cb` | `invalid_source`; no exported projection hash; missing OR-Tools owner dependency | DS7 value column / DS16 | MACHINE | `test_value_gate_projection_contains_denominators_receipts_and_outer_set_slots`; missing-owner-dependency test |
| `generation-cycle-disposition` | `layer3_gy_generation_cycle_disposition_ledger.json`<br>`sha256:69757955ac4797e916a439bd19484278cfee5fa7da732c52e75f0b2e76e57e10` | `invalid_source`; no exported projection hash; missing OR-Tools owner dependency | DS7 honesty / DS10 explanation | EXPERT | disposition scope, missing/null dependency, and owner-dependency tests |
| `engine-census` | `layer3_gy_engine_census.json`<br>`sha256:ca72e8bb9eda519b9da9f2c81d0069e2b7cb940308ad8c012b99f241f2652dd3` | `available`<br>projection `sha256:063147caa2de7e89a6730e4d7955d840be9f5a3a747910af968cabd582d2e06c`<br>dependencies `sha256:4560cdacc48625ecb848045f5e46f17cea88fe05b8d1b639363732bf0937b6a8` | DS7 / DS10 census | EXPERT | `test_engine_census_projection_omits_full_rows`; canonical owner-worker pass |
| `fork-b-relation-census` | `layer3_gy_n10_cg1_l2_relation_census.json`<br>`sha256:1c004559fe41cc84296ebb05edcfd4f5f95ade9542b2992aa52543ccb0c3bca4` | `available`<br>projection `sha256:b06d8aa4e1750245f81561562d12d6edb4ae54898f97b9cc3023a7f013427516`<br>dependencies `sha256:9c92ef5dc50492d2d224f680d7f8d6cf0fe2cb440fcea790c103c49323bc6495` | DS7 / DS10 census | MACHINE | `test_fork_b_projection_omits_relation_table_and_binds_counts` |
| `acquisition-routing-contract` | `layer3_gy_acquisition_contract.json`<br>`sha256:23ebac67c73963be8bd64fb3052d785904d1b7a7bcbea6ee79fecea9c5539bdd` | `invalid_source`; no exported projection hash; missing OR-Tools owner dependency | DS7 base route / DS15 | MACHINE | receipt preservation, table-driven capture-provenance immunity, semantic owner-content/producer binding, and owner-dependency tests |
| `n13a-acquisition-census` | `layer3_gy_n13a_acquisition_census.json`<br>`sha256:63212c8ccdcd80e96f8ae5903a74e4587090cfe096392e00069d30c17ba64791` | `invalid_source`; no exported projection hash; canonical recompute catalog absent | DS15 / DS7 route context | MACHINE | typed catalog absence, catalog-backed valid service recomputation within the bridge budget, and corrupt decisive-metric rejection |
| `n13a-live-probe-journal` | `layer3_gy_n13a_live_probe_journal.json`<br>`sha256:027b3824f77c325ec4550afbf1ea75fb7a4b70c78070d6bb3cb471d73110d3fd` | `invalid_source`; no exported projection hash; canonical recompute catalog absent | DS15 audit | EXPERT | typed catalog absence and shared canonical recompute tests |
| `capability-reality` | `capability_reality_report.json`<br>`sha256:9a0a8baf637a886a059729b36902cad56b33443cf05cfa59adb32ccbd1dc20c6` | `invalid_source`; no exported projection hash; `capability_repo_ref_file_missing` | DS6 / DS7 | MACHINE | actual-owner drift, all-null, invalid-field, and missing/unrecognized owner-contract tests |
| `cluster-ownership` | `cluster_ownership_map.toml`<br>`sha256:b9409bc276d77d60919fab996ced4d01189c276eb38edad1eaa23e831edd69f4` | `available`<br>projection `sha256:757666630746b9cd71c5ccbc8e1887f0ee2576e14eacc6831eb89a75a3c423e4`<br>dependencies `sha256:2a624828139f05f60ea76239589745cf593921ad6bda1c24f04761854fe074ab` | DS6 / DS7 | EXPERT | projection preservation plus transitive owner-dependency receipt test |
| `layer3-health-metrics` | `layer3_health_metric_ledgers.toml`<br>`sha256:1b3f19fc0d039a417dbdd45ccada02be9e1998a340cedcbf85d67b7925e97ac5` | `available`<br>projection `sha256:2f097e220103821a3ae4f30fc6aec7b9535dd436abe9e8e1958d281fae39f26b`<br>dependencies `sha256:df0fba44af44512dc941485af6319ae0a446617ed18ca41fa7f29735e4f7f1c5` | DS6 instrumentation | MACHINE | `test_layer3_health_projection_preserves_freeze_values` |
| `legacy-proving-ground` | 13 fixture identities<br>`sha256:c289f814835f60178b54fd6edeb5748d3c58865f8257ab9afabd4768637aa0c7` | `available` fixture identity only<br>projection `sha256:2a084d85888f9b36647ab7ab20bcf84666a65416610e0642c510a598d9182409`<br>dependencies `sha256:7aa9ff088d92da6d756c83fcabcf50674e790b0eae7c4911aa0b388dcfa1f22a` | DS7 legacy cohort | EXPERT | canonical 13-case owner load, fixture-not-runtime-outcome, and owner-valid metadata-rebaseline tests |
| `surface-readiness` | canonical live ledger absent | `artifact_missing`; no projection hash | DS6 / DS7 | MACHINE | example, typed-absence, present-fake, and Revision-2 rejection tests |

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

| Registry ID | Path | Producer contract | Auth class | Consumer | Capability state |
|---|---|---|---|---|---|
| `runs-list-live` | `/api/v1/runs/live` | `channel_contracts:RunsChannelDataEvent` / `policyos.runtime.runs_channel_data_event.v1` (snapshot + timeout) | `runtime_tenant_access+stream_rate_limit` | dashboard `RunsLiveProvider` | `verification_missing` |
| `run-detail-live` | `/api/v1/runs/{run_id}/live` | `channel_contracts:RunsChannelDataEvent` / `policyos.runtime.runs_channel_data_event.v1` (snapshot + timeout) | `runtime_run_tenant_access+stream_rate_limit` | dashboard `useRunLiveUpdates` | `verification_missing` |
| `review-live` | `/api/v1/review/live` (`review.cursor`, `review.lock`, `review.presence`) | `channel_contracts:ReviewSnapshot` / `policyos.runtime.review_collaboration_envelope.v1` | `runtime_review_socket_auth+tenant_opa_action+stream_rate_limit` | dashboard review collaboration surface | `verification_missing` |

At closeout, `main` advanced through DS19 merge `f9f69e807` and the canonical frontend
disposition register. The DS3 branch does not contain that merge or register; it
observes the architecture-owned authority out of band and records the integration as
`verification_missing`:

- `feature-collaboration`, `transport-rest-collaboration`, and
  `transport-ws-collaboration` are `deleted` and `strangled` by DS19 on 2026-07-17.
  DS3 adds no phantom server route or registry entry. Five phantom caller transports
  remain on this pre-merge branch, so its live transport result is
  `pre_merge_collaboration_residual`, not post-strangle verification. The same gate
  requires the canonical register and an actual zero-residual caller scan together
  before it can return `integrated_zero_residual`; a negative proves that valid-looking
  register content with a remaining caller cannot claim integration.
- The 37 uncalled OpenAPI operations have 13 `wire` and 24 `retire` dispositions.
  These remain decision-only rather than capability graduation. The register expressly
  forbids using the frontend decision to delete server endpoints or claiming pending
  work as implemented, so DS3 records build-or-remove recommendations, leaves those
  operations unchanged, and requires later owners to execute the decisions.

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
- Package `main`, `types`, and root `exports` point to
  `canonicalRuntimeApiClient.js/ts`, whose DTO aliases are the discriminated/literal
  OpenAPI types. The raw `runtimeApiClient.*` pair remains generator-owned solely so
  the existing repository contract checker stays authoritative.
- The reference-shell proof executes `listGovernedProjections()` through the public
  canonical entrypoint with a stub fetch and asserts both successful consumption and
  transport-failure behavior.

The final canonical generation sequence ran twice with byte-identical results:

| Generated file | SHA-256 on run 1 and run 2 |
|---|---|
| `schemas/runtime_api_v1.openapi.json` | `16188033a7f5be7a42844a244320aa34edd6286570dd4255c43bb6f5a6949134` |
| `packages/runtime-api-client/types.ts` | `e5430a16b949de4d020946dbf3fc1ff3bb27306b3e067620d9ad88be07d778ad` |
| `packages/runtime-api-client/runtimeApiClient.ts` | `774d8683319d0f80e2437cf8cab00c6609f34c5a8750f671e8ae7e3cb5c8832e` |
| `packages/runtime-api-client/runtimeApiClient.js` | `7a1094444cf72ab1ba7b6daf11bc85f4e07c289ac21c84b516724cff0f8e3945` |
| `packages/runtime-api-client/canonicalRuntimeApiClient.ts` | `d06db70c79c2e497e69c0d141449f0ddb1ac958cdd2dc8f39971fc99c61ee9f4` |
| `packages/runtime-api-client/canonicalRuntimeApiClient.js` | `6d7465160421459492cbef22102f4f9abc1e777803706b9730e2ebfe511e9568` |

### Fresh targeted verification receipts

- Governed projection service: 65 passed and 1 catalog-gated test skipped by default,
  including strict source/payload states,
  owner receipt/component/payload binding, same-size transitive dependency drift,
  malformed sources, cache isolation, narrow hashes, dependency/time replay, and
  import-laziness.
- Isolated owner worker plus governed projection/channel API: 18 passed and 1 skipped.
  The skip is the explicitly opt-in read-only production catalog witness.
- Rerunning the catalog-backed service positive with
  `POLISYOS_N13A_PRODUCTION_CATALOG` produced 1 passed and exercised the canonical
  recomputation through the real service within its 120-second budget. Rerunning the
  catalog-backed adversarial worker test produced 1 passed and rejected the corrupt
  decisive metric through the canonical checker.
- Runs SSE snapshot/timeout chokepoint plus runtime client/DS19/reference-shell bridge:
  12 passed. The bridge reports this branch's five phantom callers as
  `pre_merge_collaboration_residual`; canonical-register integration remains
  `verification_missing`.
- Existing OpenLineage/PROV, artifact render/export, decision-validity, Lex truth, and
  review-WS selection: 11 passed, including replay mismatch, publication-authority,
  transaction-time, and malformed-emission negatives.
- OpenAPI/client hardening file: 13 passed, including repository success examples,
  raw compatibility drift, canonical-twin derivation, and two independent generation
  runs.
- A final combined runs/channel, OpenAPI-hardening, and reference-shell bridge selection
  passed 29 tests. The two pre-existing control-plane feedback/reissue failures were
  reproduced unchanged from committed `c9a477a9f` in an isolated temporary archive
  before applying the documented focused exclusion; they are not DS3 regressions.
- The canonical repository `check_runtime_api_contract.py` command passed after the
  final schema/client replay.
- Ruff passed across every changed Python path with no ignores.
- Shared client: TypeScript passed; 4 Node tests passed; architecture, ESLint, and
  Prettier passed.
- Reference shell: TypeScript passed; 2 behavioral Node tests passed; architecture,
  ESLint, and Prettier passed.
- The explicit six-file regeneration replay ran twice and produced identical SHA-256
  values recorded above.
- No full pytest or browser suite was run, per DS3 scope.

### Fence and authority closeout

- `git diff --check` passed; no files were deleted.
- Final `git diff --stat main...HEAD`: 52 files, 34,063 insertions and 883 deletions
  (predominantly generated schema/types).
- Every changed path is inside the DS3 fence: runtime HTTP, schema, shared client,
  reference-shell proof, scoped tests, the DS3 plan, and this journal.
- No runtime-quality, fabric, foundry, scientist, data-forge, dashboard source,
  architecture register, production-data, brand, or lockfile path changed.
- Missing live readiness remains `artifact_missing`; proving-ground expectations remain
  `fixture_only` with runtime outcomes absent. Audience enforcement remains DS20/DS5.
- Branch stops unmerged for architect review.
