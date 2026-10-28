# Retrieval (`polisyos.fabric.retrieval`)

`polisyos.fabric.retrieval` turns a `DataNeed` into deterministic resolution,
bounded live discovery, executable fetch plans, previews, and promotion
signals.

## Persisted fetch custody

Fetch payloads and their JSON receipts/bindings are written through the artifact store's
canonical JSON API using the declared core profile. JSON persistence is built from the byte
snapshot captured before the CAS write, so a later mutation of connector-owned data cannot change
the profiled object being stored. Arrow IPC payloads remain media-specific byte streams. Readers
continue to require the declared profile; profileless historical JSON is not upgraded or treated
as verified by this capture path.
The reader uses the Core profile-addressed manifest capability when the store
provides it. Otherwise, it falls back only to Core's default-profile resolver;
profileless refs and non-default profiles remain refused.


`execute_fetch_plans(..., persist_payload=True)` requires a real
`DatasetCatalogGraph` and CAS. The actual chosen plan, including a fallback,
must resolve through that graph. The executor persists the complete connector
payload and a `polisyos.fabric.fetch_receipt.v1` receipt; `DataContextMetric`
carries their typed `payload_ref` and `fetch_receipt_ref`. Its `sample_rows`
remain a preview and cannot substitute for the persisted payload.


`execute_persisted_fetch_capture` is the single-plan bounded capture operation
for callers that must check a local route and then verify persisted custody.
The service owns the exact plan, effective connector configuration, registration
snapshot, catalog binding, and CAS store across both callbacks. The preflight
view exposes plan, catalog-binding, and effective-config fingerprints,
connector identities, and classified inputs for the selected route. It also
carries the captured source-profile fingerprint when a named profile supplied
the config; these are transient digests, not a claim that the live profile
registry remains current. For `files.tabular`, the connector reads only the
owner-bound effective `ConnectionConfig.url`; the route check always resolves
that value under the approved root using the same local-path parser as the
registered file connector. The effective route is not trimmed or shell-expanded;
relative effective paths refuse before execution because the connector would
resolve them against its process working directory. When the selected catalog binding supplies
`connector_params.url` or `connector_params.path`, each supplied value must be
well-formed and resolve to the same file. If those keys are absent, the captured
profile/default config supplies the route. `DistributionResult.url` and
`source_locator` remain bound catalog metadata but are not substituted for the
transport input. A local path is transient for a root check and must not be
persisted or logged. The postflight view exposes metric summaries and scalar
CAS references, not sample rows or payload content. Both callbacks may refuse by
raising and must return `None`; their return values do not establish admission.
After the callbacks, the owner revalidates the original catalog binding,
the captured effective-config fingerprint, store identity, and connector
registration. The same captured config is used throughout the operation; a
later profile-registry update does not silently reroute this fetch, and the
capture does not establish live profile currentness. Explore-lane promotion
candidates are queued only after postflight succeeds and that owner recheck
completes. This path establishes
bounded local fetch custody only; it does not prove historical timing, current
source truth, or scientific validity.

`custody.resolve_persisted_fetch` resolves the full CAS chain, rechecks the
catalog source bytes, and repeats the exact full request through the registered
connector. A changed or unavailable source refuses current verification.
The comparison establishes current returned-content agreement. It does not
prove that the historical request happened at its recorded time, nor establish
scientific source truth. Capture timing stays in the raw receipt and cannot
authorize a time-sensitive or execution-cost claim.

Current N9 measurement admission uses
`MeasurementRootProducer.produce_from_fabric_fetch` with an explicit design
problem and a source requirement derived through the existing catalog owner.
Both existing connector and source-contract admission gates still apply.
The registry's full result validator checks the actual configured contract,
including schema, completeness, row counts and staleness. The root binds that
contract's ID, version and behavioral content hash; the current N9 reader
rechecks the same predicate and refuses a changed contract. Description and
creation metadata are outside that existing behavioral hash.
Each successful source recheck creates a fresh verification event, with its
own UTC `source_agreement_checked_at` and immutable authority identity. It
retains the original fetch reference without rewriting its capture time.
Catalog-only roots remain historical/fixture inputs and cannot discharge the
current MEASUREMENT obligation.

Last updated: 2026-04-17.

## Candidate scope limits

For `resolve()`, retrieval joins each selected target to the complete
reconciled catalog binding population by metric, connector, request dataset,
profile, and source admitted for the active run profile before comparing typed
coverage. Plan metadata and identifier spelling do not establish that relation.
A mismatch is excluded from `ResolveOutcome.fetch_plans`, public `candidates`,
and plan fallbacks only when country coverage is definite or time bounds are
disjoint; partial time overlap remains unverified. Reconciliation, profile,
and exact dataset-read refusals propagate. Unknown identity or coverage remains
an unverified candidate. The same predicate gates FastLane, catalog, and
ExploreLane selections. The local index retains raw discovery facets; each
resolve request is checked before candidate or plan emission. Standalone
discovery remains a raw metadata-candidate surface and does not emit selected
plans or imply a run-profile admission. The country normalizer is reused through
the catalog read API facade. This does not prove fetched-row scope or scientific
availability.

## Purpose

Use this package when you need the bridge between catalog knowledge and actual
fetch execution. Retrieval owns the fast-lane catalog resolution path, the
bounded explore lane, and the execution surfaces that turn candidates into
connector-backed results.

## Where to Start

- Read [__init__.py](./__init__.py) to see the exported retrieval surface.
- Read [service.py](./service.py) for the top-level orchestration and bounded
  local-index state.

- Read [executor.py](./executor.py) and [explore_lane.py](./explore_lane.py)
  for fetch execution and live discovery behavior.

- Read [../catalog/README.md](../catalog/README.md) and
  [../connectors/README.md](../connectors/README.md) for the upstream contract
  and source-binding surfaces that retrieval composes.

## Public Entrypoints

| Entrypoint                                             | Description                                                                 |
| ------------------------------------------------------ | --------------------------------------------------------------------------- |
| `RetrievalService`                                     | Main resolve, discover, and execute service.                                |
| `FetchExecutor`                                        | Executes fetch plans with preview/full gating.                              |
| `ExploreLaneDiscovery` / `ExploreLaneLimits`           | Bounded live discovery helper and its runtime limits.                       |
| `ResolveOutcome`, `DiscoverOutcome`, `ExecuteOutcome`  | Stable result wrappers returned by retrieval orchestration.                 |
| `RetrievalProviders` / `resolve_retrieval_providers()` | Dependency bundle and resolver for registry, profiles, tracer, and metrics. |

## Depends On / Depended On By

- Depends on: `polisyos.fabric.catalog`, `polisyos.fabric.connectors`,
  `polisyos.data_forge.read_api.catalog`, and
  `polisyos.core.contracts.control`.

- Depended on by: `polisyos.runtime.http.services.control` and any runtime or
  data-access flow that needs metric-driven fetch planning instead of direct
  connector calls.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "RetrievalService|FetchExecutor|ExploreLaneDiscovery" src/polisyos/fabric/retrieval`
  Jump to the main retrieval entrypoints. Smoke-tested on 2026-04-17.

- `rg -n "FastLaneResolver|SourceBinding|MetricSearcher" src/polisyos/fabric/catalog src/polisyos/fabric/retrieval`
  Follow the boundary between retrieval and catalog resolution. Smoke-tested on
  2026-04-17.

- `rg -n "max_local_index_docs|max_promotion_candidates" src/polisyos/fabric/retrieval/service.py`
  Inspect the bounded-state controls for local indexing and promotion queues.
  Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/test_retrieval_service_catalog.py -q`
  Retrieval service smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/test_data_catalog.py tests/unit/fabric/test_entity_resolution.py -q`
  Catalog and entity-resolution integration smoke suite. Smoke-tested on
  2026-04-17.

- `uv run pytest tests/unit/fabric -q`
  Full Fabric suite. Conceptual in this README refresh; not run in this pass.

## Reference Docs

- [Fabric reference index](../../../../docs/reference/fabric/index.md)
- [Fabric connectors reference](../../../../docs/reference/fabric/connectors.md)
- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Catalog README](../catalog/README.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)


## Catalog read-source failures

Catalog's public read API exposes `CatalogReadSourceError`, a subtype of the
existing `CatalogSelectionError`. Retrieval preserves that whole owner-issued
family across publish identity, metric binding, dataset lookup and fetch-target
lookup. A changed/missing native source or visible WAL is an error, never an
empty catalog or optional-provider fallback. Unrelated provider exceptions keep
the existing limited fallback behavior, even if they carry a code-looking field.
This changes no source truth/currentness or fetch permission. The Runtime
acquisition adapter maps these failures into its existing binding error and
retains the exact cause for a persisted N7 refusal.
