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

### `acquisition-route-to-n13b-authority-binding`

- **Verdict:** `closed`.
- **Implementation receipt:** `ab05936ea` (`feat: bind acquisition routes to live authority`).
- **Capability chain:** the strict `WorldBankWDIRouteExecutionBinding` is produced from the
  canonical registry/provision/receipt owners; a durable reservation and one-shot execution claim
  are persisted below the control-plane runtime root; the production factory bridges that binding
  to `execute_live_catalog_acquisition`; the existing quarantine result consumes the four persisted
  evidence refs; the route projection exposes readiness and the WDI-only limitation; behavioral
  unit/integration tests cover both positive and negative directions.
- **Pattern closure:** P01/P02/P12 close at the factory-owned route-to-executor bridge; P05/P15/P32
  close through resolve + content binding rather than caller assertions; P07/P08 close through a
  provision-minted attempt plus durable reservation/claim and explicit data-year constraints;
  P29/P33 close through real calls rather than markers; P31 closes public reservation at one
  action-service chokepoint; P37/P38 classify readiness from factory composition plus recomputed
  route binding, not from an injected port's class or badge. P03 is bounded honestly by the WDI-only
  surface statement. The executor gained only the canonical scope-check facade and remains 2,373
  lines; the route DTO/resolver/lease belong to the HTTP acquisition surface module rather than
  pushing that owner past its pending 2,500-line boundary.

#### Design answer delivered

One current L1 route maps to the sole `live_fetch` catalog entry whose `target_variable` equals the
sole `canonical_variable_observations:<variable_id>` demand. The canonical authority must reopen
that exact entry, and the resolved registry/provision identities, live registration, license/L5
chain and provisioned harness receipt must remain content-bound. The entry authorizes only the
country set and temporal interval it owns; route-derived constraints must be a subset under the
executor's canonical scope checker. The first and only implemented connector family is
`worldbank.wdi`.

The N13a provision mints each `attempt_id`; neither the route nor the runtime invents one. Public
execution atomically creates an exclusive reservation for the exact tenant/cell/run/route binding
before any authority-provider method, action reservation or job enqueue. The worker atomically
creates a second one-shot claim before connector execution. A matching unclaimed reservation is
restart-reusable by that exact route; a claim, a cross-route lease, malformed bytes or exhaustion is
never reusable. This removes the preflight/execute race while keeping read projections side-effect
free.

Constraints are supplied by the binding: exact ISO-3 route region, exact four-digit data year with
`start_year == end_year`, page size 1,000, raw and decompressed ceilings of 65,536 bytes, total
timeout 15 seconds and heartbeat 5 seconds. The existing owner-scope checker runs during binding
and again inside the executor. `journal_path` and `cas_root` are not accepted from a caller: the
production factory takes `ControlPlaneService._cas_root`, and the port derives a SHA-256
tenant/cell/run/route subtree beneath it. Attempt reservation remains deployment-global within that
root.

#### Red-first proof, both directions

- Positive resolver red: the exact resolver node exited 1 with missing
  `resolve_world_bank_wdi_route_execution_bindings`; after implementation the focused resolver set
  passed, and the final complete unit file passed 39 tests (exit 0).
- Positive production bridge red: the concrete-port node first failed because the production module
  did not exist; the later factory node exposed a real missing facade export and exited 1. The final
  integration file exercises canonical factory owners, durable reserve -> claim, governed paths and
  the production executor symbol: 11 passed (exit 0).
- Negative public-boundary red: the four entry/scope/attempt/replay variants reached
  `authority_provider.for_request` (exit 1). After the single route-binding chokepoint they all fail
  with their exact typed code before a provider call, reservation or enqueue: 4 passed (exit 0).
- Missing-authority red: a valid route created an attempt lease before reporting
  `acquisition_authority_producer_missing` (exit 1). Presence is now checked first and the lease root
  remains absent: the exact node passed (exit 0).
- Fixture/injection negatives: `_FixturePort` and an externally supplied concrete port remain
  `producer_missing`; public execution refuses before provider use. Only the factory-returned
  instance can project `ready`. The direct `_worker_harness` was neither wrapped nor relabelled.
- Drift/scope negatives cover malformed route shape, missing/ambiguous entry, registry/provision/
  receipt drift, non-WDI registration, cross-country/year constraints and missing attempts before
  executor use. A used attempt is rejected across tenant/route scope.

#### Deciding verification commands

- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_live_acquisition_executor.py -q`
  -> exit 0, 39 passed.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/integration/core_runtime/test_acquisition_route_execution_binding.py -q`
  -> exit 0, 11 passed.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/http/test_acquisition_control_worker.py tests/unit/runtime/http/test_runtime_service_container.py -q`
  -> exit 0, 10 passed.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/runtime/http/services/acquisition_action_service.py src/polisyos/runtime/http/services/acquisition_surface_execution.py src/polisyos/runtime/quality/acquisition_executor.py tests/integration/core_runtime/test_acquisition_route_execution_binding.py tests/unit/runtime/quality/test_live_acquisition_executor.py`
  -> exit 0, all checks passed.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m mypy --follow-imports=silent src/polisyos/runtime/http/services/acquisition_surface_execution.py`
  -> exit 0.
- `uv run polisyos-tools architecture guardrails check --skip-generated-checks` -> exit 0. This is
  the deciding import/public/deep-import gate: no `[ARCH001]`, exception or baseline change.
- Full `uv run polisyos-tools architecture guardrails check` -> exit 1 only at the
  `trust-claim-posture-register` output probe; both TypeScript generated-output probes are clean.
  Exact replay at entry `3be079774` produces the same trust validation error. Under P41 it is
  recorded `not_established`, not called inherited: that probe walks all 2,615 `src/**/*.py` files
  and three J source paths intersect its denominator. The J-specific architecture property above is
  independently green.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check`
  -> exit 1 with 19 `closure_signal_identity_unresolvable` findings on both J and exact entry-base
  replay; set delta is zero. This contradicts the supplied count of 18. The extra member on both refs
  is `runtime-authorization-denominator-reconciliation`, selecting the absent
  `tests/unit/runtime/http/test_runtime_step_up_authz.py::test_router_and_openapi_high_stakes_denominators_agree`.
  A minimal `uv run` environment without pytest returned a non-receipt and is explicitly excluded.
- `PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_docs_lifecycle.py --repo-root .`
  -> exit 1 with exactly the six supplied findings; this journal adds none.
- `git diff --name-only 3be079774..HEAD -- schemas/runtime_api_v1.openapi.json packages/runtime-api-client src/polisyos/runtime/http/openapi_contract.py apps/runtime-dashboard`
  -> exit 0 with an empty result.

#### World Bank scope and result-contract decision

The route projection always states
`connector_families_except_worldbank.wdi:surface_out_of_scope`. When a factory port exists but its
exact route binding is unavailable, it reports
`worldbank.wdi_route_binding:producer_missing`; it reserves `bridge_missing` for an actually absent
production bridge. No result/schema/client change was required. The existing readiness literals
carry the non-fixture reading, `AcquisitionOwnerExecutionResult` is unchanged, and its legacy
fixture badge remains untouched under the architect's narrowed contract decision. The forbidden
path diff above is empty.

#### What remains for Task E's rows (not closed here)

- `ds15-production-n13b-execution-handshake`: after J lands, the typed binding, canonical factory,
  persistent reservation/claim, real executor call and quarantine result are implemented. E still
  owns the end-to-end closure signal that constructs the full production action service with its PA2
  authority provider, drives public reservation through the durable worker job, and observes the
  factory-owned port result outside `_worker_harness`. Until that merged proof runs, label the E row
  `verification_missing`, not closed. Its recorded direct manually-created-job/fixture-injection
  residual remains a bounded limitation.
- `ds15-fresh-positive-production-route`: J deliberately stops at
  `quarantined_no_growth` and rejects re-entry. E still needs the semantic-epoch policy authority,
  deterministic admission/passport and overlay activation, a fresh reissued provision attempt, a
  positive admitted observation delta, world commit and re-entry proof. The positive-growth chain
  remains `absent/unallocated` at the semantic-epoch/admission prerequisite, not closed.

#### Named question for the architect

The supplied ledger baseline says 18, while exact project-interpreter runs at both entry
`3be079774` and J produce the same 19-member set. The nineteenth artifact is the Task-I-owned test
`tests/unit/runtime/http/test_runtime_step_up_authz.py::test_router_and_openapi_high_stakes_denominators_agree`.
Should that exact test land before consolidation, or should the published baseline statement be
corrected to 19? J cannot supply the file and made no authorization-path change.

#### Exact append-only prose for the architect-owned Register

> `acquisition-route-to-n13b-authority-binding` — **closed** at `ab05936ea`. A current exact L1
> variable route now resolves one content-bound canonical `worldbank.wdi` authority entry, derives
> only constraints within that entry, atomically reserves and one-shot claims a provision-minted
> attempt, derives journal/CAS paths beneath the control-owned runtime root, and reaches
> `execute_live_catalog_acquisition` through a factory-owned tenant/run route port. Missing authority,
> entry, scope, fresh attempt, canonical factory ownership or provider fails before provider use,
> action reservation and enqueue. The existing route surface states the WDI-only bound; no
> result/schema/client contract changed. Evidence: 39 unit + 11 binding integration + 10 importer
> tests, Ruff, focused mypy and the import/public architecture guard all exit 0. Full architecture
> remains `not_established` only at the base-reproduced trust-posture probe; debt-ledger set delta to
> entry is zero (19/19, with the stated 18-pin discrepancy handed back); docs lifecycle remains 6.
> Task E rows are not closed: the production service-to-worker closure signal is
> `verification_missing`, and fresh positive epoch/admission/world growth remains
> `absent/unallocated`.
