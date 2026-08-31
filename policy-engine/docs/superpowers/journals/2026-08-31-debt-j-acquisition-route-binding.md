# Task J — Acquisition Route Binding Journal

Branch: `codex/debt-j-acquisition-route-binding`
Entry: `3be0797749a3a4dab0e16e7769ed8a2d02646134`
Owned row: `acquisition-route-to-n13b-authority-binding`

## Design decision before source edits

The route does not choose an arbitrary catalog row. The binding accepts only a current
`data_requirement` / `data_snapshot_release` route whose sole missing field is
`canonical_variable_observations:<variable_id>`. It resolves the canonical acquisition-authority
registry and requires exactly one `live_fetch` entry whose `target_variable` equals that
`variable_id`. It then reopens that entry through `CanonicalAcquisitionAuthority`, content-binds
the registry and provision identities, and requires the resolved registration's connector to be
exactly `worldbank.wdi`. No match, multiple matches, a non-live lane, owner drift, or another
connector fails closed before the connector provider is reached.

The N13a authority provision, not the route or runtime, mints the admissible `attempt_id` values:
each is already bound to one entry and one recomputed harness receipt. The production port takes an
exclusive, append-only lease for one still-unused provisioned attempt under the server-owned
runtime state root before execution. The lease is keyed globally within that runtime root by the
attempt identity and records the exact tenant/cell/run/route/entry binding. Existing or malformed
leases are not reusable; exhaustion fails closed. This preserves the current exact-attempt harness
contract instead of manufacturing fresh authority from a reusable family badge.

`LiveCatalogExecutionConstraints` are supplied by the binding, never by the HTTP caller. Country
is the current `DesignProblem.jurisdiction_time.region` and must already be exact ISO-3166 alpha-3
and a member of the authority entry's `country_codes`. The initial rule accepts one exact
four-digit `data_time` year and sets `start_year == end_year`; it uses a versioned World Bank WDI
operational ceiling of page size 1,000, 65,536 raw/decompressed bytes, 15 seconds total and 5
seconds heartbeat. `_require_constraints_within_authority_scope` remains decisive and is run while
binding, then again by the executor. Candidate route scope can only narrow the owner grant; it
cannot enlarge it.

`journal_path` and `cas_root` are derived beneath the `ControlPlaneService` runtime root from a
SHA-256 scope key over tenant, cell, run and route. The port exposes no raw-path parameters. The
route-specific journal and evidence CAS are therefore server-selected and tenant/route separated,
while the attempt lease is deployment-global so the same authority-provisioned attempt cannot be
replayed through another tenant or route.

The first binding is deliberately World-Bank-WDI-only. The operational route projection states
this without a schema/client change by adding
`connector_families_except_worldbank.wdi:surface_out_of_scope` to its existing typed
`external_nonclosures` surface. `authority_capability` and `execution_capability` retain their
existing `Literal["ready", "producer_missing"]` contract and move only when their real providers
exist. `AcquisitionOwnerExecutionResult` does not change: the architect's narrowing makes the
production class/path, rather than the legacy `authority_badge` literal, the relevant
distinguishing fact.

## Pattern pass

- P01/P02/P12: close the route-to-executor bridge with the existing authority registry,
  provision, live executor, journal and CAS owners; do not add a parallel acquisition owner.
- P05/P15/P32: resolve + content-bind the canonical registry/provision/harness receipt; the route
  supplies a requested subset and never mints authority.
- P07/P08: preserve the current route replay pins, use an exact provisioned attempt once, and keep
  `data_time` distinct from execution time.
- P29/P33/P37/P38: behavioral red/green proof must show the real concrete port reaches the executor
  on the complete binding and that every missing or drifted input refuses before the connector
  provider. Marker or source-text checks are insufficient.
- P27/P31: extend `acquisition_executor.py` and the existing action-service port seam; no wrapper
  around `_worker_harness`, no sibling raw executor path.

Target capability state for the owned row: `closed`. The persisted carrier is the existing
request/raw-response journal plus evidence CAS; the HTTP projection is the existing route surface;
negative and integration semantic tests are required before closure.

## Collision section

- Task A owns only `runtime/quality/promotion_sequence.py`, `generation_cycle.py`, and their two
  unit tests. Task J does not read for design authority or write those paths.
- Task I owns `runtime/http/openapi_contract.py` and the two authorization tests. Task J makes no
  schema/client/OpenAPI change and does not write those paths.
- Task D owns `apps/runtime-dashboard/**`, `runtime/http/container.py`, `control_worker.py`, and
  `run_lifecycle.py`. Task J derives roots from the existing control service and does not write
  those paths.

## Register closure dossier

To be appended after fresh verification. The row will end only `closed` or `blocked`, with the
deciding commands, exit codes, and exact append-only prose.
