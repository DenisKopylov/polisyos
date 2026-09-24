# R7 — governed acquisition egress map

Status: read-only design analysis recorded from `codex/e02r2-can01-audit` at `53d2480a1f7b809a51d3ac8faa405f3817f2f376`. This document is the only intended change in this worktree for this task. No source was edited and no test or native job was run before the P41 baseline.

## Property and observed divergence

For a governed live acquisition, every outbound request must be authorized by the attempt's request scope and recorded in its evidence journal before transport. Connection acquisition must not emit a separate health request outside that scope. Ordinary, non-governed connector users retain configured active-on-acquire validation.

The World Bank connector's `health_check` requests `/country/US/indicator/NY.GDP.MKTP.CD` (`policy-engine/src/polisyos/fabric/connectors/sources/world_bank.py@ff19ae201c1145c34589645eecdedea54f459ba6`, lines 139–149). A governed WDI execution may authorize a different country and indicator. The active health check is not harmless preflight: it is an actual out-of-scope GET.

## Production path and ordering

| Stage | Production path | Behavior relevant to R7 |
|---|---|---|
| Owner entry | `AcquisitionSurfaceExecution.execute`, `policy-engine/src/polisyos/runtime/http/services/acquisition_surface_execution.py@74bfe81aa16b00561c7650032593bd2be722d67e`, lines 404–442 | The default production branch calls `execute_live_catalog_acquisition`; an injected executor is a separate branch. The owner bridge supplies the bound entry, attempt, constraints, journal path and store. |
| Resolve and authorize | `execute_live_catalog_acquisition`, `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@58b528e659121696e97da333f1b44a0c60e83d7f`, lines 716–750 and 803–820 | Resolves catalog authority and scope, then builds the exact request authorization. `build_live_execution_authorization` in `policy-engine/src/polisyos/fabric/data_plane/evidence_journal.py@75a1bcd3fcb2444bd5210aebcb9df47598a1b6fa`, lines 1256–1276, constructs the typed authorization and calls `require_authorized_execution` before returning. |
| Bind journal request | `acquisition_executor.py`, lines 821–822 | Opens the append-only journal and appends the authorized request before starting ingestion. |
| Start governed ingestion | `acquisition_executor.py`, lines 828–847 and 985–998 | Derives exact expected URL and query parameters, constructs `_LiveHTTPExecutionObserver`, then calls `run_orchestrated_ingestion` with that observer and the owner-supplied ingestion store. |
| Orchestration | `run_orchestrated_ingestion`, `policy-engine/src/polisyos/fabric/data_plane/orchestrator.py@ac910576602078fcfd966d1e26ac8e270e767d08`, lines 509–543 | Forwards the manifest, connection config, sink, observer and dependencies to `run_connectors_ingestion`. |
| Per-dataset fetch | `run_connectors_ingestion` and `_sync_fetch`, `policy-engine/src/polisyos/fabric/ingestion/ingestion.py@1fc971dd3abbd5fa85f8fd11a4e90b0d510fa1c5`, lines 671–706, 821–842 and 929–936 | `_sync_fetch` calls `registry.get_connection` at line 687. Only after that returns does it install the raw HTTP observer at lines 690–697, then call `connector.fetch`. |
| Registry and pool | `ConnectorRegistry.get_connection`, `policy-engine/src/polisyos/fabric/connectors/registry_core_parts.py@6afd872b60e956c89615dc282ec1bc5f33994311`, lines 662–757 | The registry creates a `PoolConfig` with its default `validate_on_acquire=True` at lines 708–710, then calls `pool.acquire()` at 755. |
| Active validation | `ConnectionPool._acquire_owned`, `policy-engine/src/polisyos/fabric/connectors/pool.py@dedeee7949722e7b88b6010f7b46286c2c6f70bf`, lines 331–402 | After selecting either an idle connection or creating a new one, it validates at lines 392–402 when the pool config is true. That invokes the connector health check before `_sync_fetch` can install the governed observer. |
| Actual fetch enforcement | `_LiveHTTPExecutionObserver.before_request`, `acquisition_executor.py`, lines 571–599; HTTP transport in `policy-engine/src/polisyos/fabric/connectors/sources/http_base.py@2ee304b7480835f61c2a2465cfb4ba3c765fe155`, lines 425–443 | For the actual fetch, the observer appends a transport attempt and heartbeat, checks the exact authorized scope, and is called before `session.get`. This protection does not cover `get_connection` or its health check because the observer is not attached yet. |

The active pool check therefore sits between authorization/journal setup and the authorized fetch, but outside the observed transport path. Suppressing this preflight does not change the actual fetch's authorization: that continues to be enforced by `_LiveHTTPExecutionObserver` immediately before the transport call.

## Smallest per-call propagation

Keep `PoolConfig.validate_on_acquire=True` and add an optional per-acquisition override whose `None` value means “use the pool's configured behavior.” The governed live executor selects passive acquisition only after the exact live authorization has passed and its request has been appended to the attempt journal. Do not mutate shared pool configuration: a passive governed acquisition and an ordinary active acquisition may use the same registry and pool at different times.

| Hop | Proposed parameter | Ordinary callers |
|---|---|---|
| `execute_live_catalog_acquisition` → `run_orchestrated_ingestion` | Pass explicit `validate_on_acquire=False` only on the canonical live acquisition call after authorization and request journaling. | No other mode chooses passive acquisition. |
| `run_orchestrated_ingestion` → `run_connectors_ingestion` | Add `validate_on_acquire: bool \| None = None` and forward it. | Omission preserves current behavior. Other `run_orchestrated_ingestion` callers are `runtime/http/services/control/run_lifecycle.py:4284`, `fabric/data_plane/modes.py:464,566`; all keep the default. |
| `run_connectors_ingestion` → `_sync_fetch` | Add the optional value at the ingestion boundary and forward for each manifest fetch. | Existing facade `fabric/connectors/ingestion/connectors_ingestion.py@4793f4ff68993762f6c8b95a2fd48eb459d22929` does not need a new argument; its ordinary path retains the default. |
| `_sync_fetch` → `registry.get_connection` | Forward the optional override with the connection request; preserve observer installation after acquisition. | Ordinary ingestion calls pass `None`. |
| `ConnectorRegistry.get_connection` → `pool.acquire` | Accept a keyword-only optional override; do not alter the pool key or shared config. | Existing callers in retrieval, API helpers, cache prefetch/invalidation, and `fabric/data_plane/streaming.py` omit the override and retain active validation. |
| `ConnectionPool.acquire` → `_acquire_owned` | Resolve `None` to `self._config.validate_on_acquire`; otherwise use the per-call value for this lease only. Both fresh and reused handles in `_acquire_owned` pass through its validation branch. `acquire_with_connector` keeps the default. | Default remains active. Do not remove health validation from ordinary use. |

The live entrypoint is the only place that selects passive acquisition. The override is not itself authority and must not be inferred from an observer object's presence or a caller-provided “governed” string. The actual fetch remains observer-gated. The pool also has an `_get_idle_connection` helper with a separate config check (`pool.py`, lines 642–667); repository census found no caller. If that helper becomes part of the acquire route, it must use the same effective per-call decision rather than silently reintroducing a probe.

## Behavioral controls and removal probes

1. **Remove the passive-acquire behavior while retaining all markers.** Keep the authorization object, journal request, observer, and normal fetch unchanged, but force `validate_on_acquire=True` on the governed acquisition. The existing integrated test `test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport` in `policy-engine/tests/unit/runtime/quality/test_live_acquisition_executor.py@21a741caf97a9982864f8817f354749c9d006b41`, lines 1208–1285, intercepts `aiohttp` and asserts exactly one request: the authorized UKR indicator request at line 1284. It must turn red by recording the extra US GDP health GET; it does not need real network access. Keep this as a transport-level assertion, not a marker/field assertion.
2. **Remove observer scope enforcement while retaining authorization and journal markers.** Add an adversarial variant at the same real executor boundary that makes the connector attempt a URL or query outside the authorization. Keep authorization construction, request-journal append, and observer attachment in place. Assert the out-of-scope attempt is journaled and rejected before the intercepted transport receives it. Removing the observer callback or its exact-scope check while retaining those markers must cause the test to observe the forbidden intercepted request and fail. This distinguishes journal/authorization form from the transport property.
3. **Positive ordinary-use control.** In `policy-engine/tests/unit/fabric/connectors/test_registry.py@e26f1a95101895a0f3d6b615e671c8275e9a20a7`, use the deterministic `_Net01LifecycleConnector` (health-check event at lines 114–146) and a fresh registry fixture (lines 352–367). Prove that omitted override invokes active validation, while an explicit per-call passive acquisition does not; also verify the ordinary validation setting remains true. Cover a reused idle connection as well as a new connection, so a fix cannot suppress only one of the two paths. Existing NET-01 lifecycle tests around lines 1140–1174 test release validation, not this acquire control.

The test-file write set is therefore the two files above. Both must be replayed at all four P41 bases before any test edit: `78187878e`, `00d946c2b`, `5fd3ebcc1`, and the frozen integration head. The integrated live-executor test is already in the assigned Appendix A/B comparison set; the registry test is an additional touched-file denominator. No baseline was run by this analysis worker.

## Proposed source write set

Only these mechanism files need edits for the propagation above:

- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py` — select passive validation on the canonical live path after the authorization and journal request exist.
- `policy-engine/src/polisyos/fabric/data_plane/orchestrator.py` — accept and forward the optional per-call value.
- `policy-engine/src/polisyos/fabric/ingestion/ingestion.py` — carry it from the public ingestion function through `_sync_fetch` to the registry.
- `policy-engine/src/polisyos/fabric/connectors/registry_core_parts.py` — forward it into the pool lease acquisition.
- `policy-engine/src/polisyos/fabric/connectors/pool.py` — make validation choice lease-local while preserving the configured default for every ordinary caller.

No change is needed in `AcquisitionSurfaceExecution`, the generic `fabric/api.py` registry protocol, the `connectors_ingestion.run` facade, or the World Bank health-check implementation: policy selection belongs to the already-authorized live owner, while generic surface callers must continue using ordinary active validation.

## P37 / P38

- **P37 — what the gate turns on.** The authority predicate is the recomputed `LiveExecutionAuthorization` for the exact attempt, connector, profile, dataset, request, schema, baseline, harness receipt and budget; `require_authorized_execution` checks it before execution continues. The journal request is appended before ingestion. The passive choice must be made from that already-validated owner path, not inferred from a declaration that a caller is governed. Per actual fetch, `_LiveHTTPExecutionObserver.before_request` persists the transport attempt and evaluates exact connector/URL/query scope before `session.get`.
- **P38 — implementation/property divergence.** The property is “no network request outside the attempt's authorized and journaled transport scope.” Current acquire logic tests the pool's `validate_on_acquire` configuration, then calls the connector's liveness method; it does not test authorization scope. The divergent case is the World Bank US GDP health GET before an authorized UKR WDI GET. Observer presence is not proof of coverage because `_sync_fetch` installs it only after `registry.get_connection` returns.

The owner-first repair is a per-call passive acquire option on the one governed production call, leaving ordinary active validation intact. This is aligned with the GY N13b rule that governed acquisition enters through the canonical ingestion/world-growth path; no second data-write route is introduced (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@9d510e2ee43fd017028542f180008cd2c2aacb37`, N13b around lines 2787–2806). The identity boundary assigns PolicyOS the typed evidence contract and scoped claim reaction rather than an unrelated health request (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@873198b24d7fe8edf204be44374d20c9256cd24e`, §5).

## P41 checkpoint and status

The parent lane reports a provisional checkpoint that Appendix B's intercepted live-acquisition test is `PASS_TO_FAIL` from main to the Phase0 merge, with the full four-base matrix pending. Treat that as a hypothesis until the exact four-base replay is complete. The test itself provides a strong discriminator for this class because its intercepted call list distinguishes the authorized WDI transport from a hidden liveness request. This analysis did not modify source before that baseline and did not run tests.

Pattern sources: `AGENTS.md@94173d77ab34173f12883ee6575db4a461f6df98`, P31/P32/P37/P38 guidance; `policy-engine/docs/reference/policy-design-case-failure-patterns.md@7f4cc9ab9541a44c26e4648a2c08326e53743492`, P31, P37 and P38.
