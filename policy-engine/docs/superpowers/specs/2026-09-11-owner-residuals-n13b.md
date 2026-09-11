# N13b execution handshake: owner decision before execution

Date: 2026-09-11. Row: `ds15-production-n13b-execution-handshake`.
Lane: `codex/owner-residuals`; immutable merge base:
`cc74d65813d7bb1259a0f82f6c3cc8b131661a97`.
Stage 1 decision: **route the remaining authority-intake dependency to team-runtime;
do not build another N13b executor**. No source change preceded this decision.

## Findings and the actual closure predicate

**OR-N13-01 — the executor producer exists.** The delivered vocabulary is
`WorldBankWDIAcquisitionExecutionPort`,
`build_production_world_bank_wdi_execution_port`,
`resolve_world_bank_wdi_route_execution_bindings`, and
`execute_live_catalog_acquisition`. The source owner is
`src/polisyos/runtime/http/services/acquisition_surface_execution.py`;
the existing execution owner is `src/polisyos/runtime/quality/acquisition_executor.py`.
The concrete port resolves current route/authority/attempt/constraints, reserves and
claims an attempt, derives tenant/route storage below the control root, calls the real
executor, and returns `quarantined_no_growth` with the four evidence references.
It is not the test `_Port`, and a legacy fixture badge does not erase its implementation.

The allowed predecessor finding is the explicitly named residual under
`ds15-production-n13b-execution-handshake` in
`docs/superpowers/journals/2026-08-31-debt-j-acquisition-route-binding.md`, section
“What remains for Task E's rows (not closed here)”. That finding says the binding,
canonical factory, durable reservation/claim, executor call and quarantine result are
implemented; E's remaining signal is a full production action service with its PA2
provider, public reservation, durable worker job and factory-owned result outside
`_worker_harness`. It identifies `verification_missing`, not a missing executor.
The older E journal's zero-implementation claim is superseded by these measured bytes.
Neither DEBT-REGISTER.md nor LEDGER.md is evidence for this decision.

**OR-N13-02 — the same-row end-to-end production signal is not available from the
current composition.** `AcquisitionActionService` constructs the port when none is
injected and binds `handle_job` to the real control service. But `RuntimeContainer`
supplies the authority provider only from
`RuntimeContainerOverrides.acquisition_authority_provider`, whose default is `None`.
`execute` calls `_require_authority_provider` before reserving an attempt; the latter
raises `acquisition_authority_producer_missing`. `request_decision` has the same intake.
The required `for_request` / `for_job` production provider is a Protocol, not an
implementation or a configured appointment.

**OR-N13-03 — a development override cannot close a production handshake.**
`create_runtime_api_app` rejects `container_overrides` in every non-dev profile.
`RuntimeDeploymentSecurity` contains the independently inspected fields `config`,
`identity_provider`, `cell_registry`, `opa_client`, `step_up_verifier`,
`principal_grants`, and `human_decision_custody`; none supplies acquisition authority.
This independently reproduces findings U15-F02, U15-F04 and U15-F06 in
`docs/superpowers/specs/2026-09-10-uninvoked-ds15.md`. A test-created provider or a
bypass of the closed bootstrap boundary would establish a different property.

**OR-N13-04 — the destination is named but not registered as an active task.**
U15-F06 assigns `DS15-MANDATE-INTAKE` to `team-runtime`: build the sanctioned governed
deployment intake/selection and compose PA2 with actual DS20 permission proof and
separately signed institutional currentness/delegation. The prior completion journal
`docs/superpowers/journals/uninvoked/completion.md` repeats that named deferral.
A complete walk of the **90 tracked Markdown files under `docs/plans/active/`, excluding
DEBT-REGISTER.md and LEDGER.md because they are not evidence**, finds zero occurrences
of `DS15-MANDATE-INTAKE`. This is not an active-plan registration. The architect must
register that task; this lane must not invent a second ID or call the deferral discharged.
The named destination is team-runtime, not Foundry, N13b's data executor, or the closed
DS15 surface lane. GY-PA2's active-plan standing is complete for its guarded adapter;
its universal effect-intake residual is a different mechanism and is not absorbed here.

## Complete denominator and independent derivation

The root's shared census is the complete tracked `src/**/*.py` denominator and uses the
existing `production_invocation.audit_repository`, including tracked tools/tests and
project-script entry points. The source census independently reconciles the Git index,
base tree and recursive filesystem sets: 2,654 parses, no errors, 36,135 sync plus
879 async definitions, 9,935 classes; sorted-path SHA-256
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
Its result must be read alongside the registered HTTP,
callback and receiver blind spot, not interpreted as runtime reachability.

The independently executed row census parsed all **2,654 tracked
`policy-engine/src/**/*.py` files** with Python AST. It finds these exact strict
`execute` / `reenter` / `resume_reentry` declarations:

| Source path | AST class | Role |
| --- | --- | --- |
| `src/polisyos/runtime/http/services/acquisition_action_service.py` | `AcquisitionExecutionPort` | Protocol |
| `src/polisyos/runtime/http/services/acquisition_surface_execution.py` | `WorldBankWDIAcquisitionExecutionPort` | Concrete producer |

The same complete pass finds one class declaring both `for_request` and `for_job`:
`AcquisitionAuthorityGatewayProvider`, the Protocol. This structural census does not
alone prove absence: the independent trace starts from app bootstrap and its attested
deployment input, follows the container constructor and source assignments, and observes
the default-None intake and exact pre-reservation refusal above. The complete source
call census also resolves the container's `AcquisitionActionService(...)`, the service's
factory call, its worker registration/enqueue calls, and the port's executor call.
No conclusion relies on a predicted name or adjacency in a file.

Test enumeration uses both `ast.FunctionDef` and `ast.AsyncFunctionDef`. In particular,
the two worker tests and two production-boundary tests are async; they cannot be omitted
by a `^def test_` search. Their existing fixture-only status is retained.

## Non-test callers and discoverability, fixed before any code

| Boundary | Exact existing non-test caller |
| --- | --- |
| Served request | `routes/acquisitions.py:execute_run_acquisition_route`, registered POST `/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute`; `app.py` includes its router |
| Real service/factory | `container.py:RuntimeContainer.startup` constructs `AcquisitionActionService`; its `__init__` calls `build_production_world_bank_wdi_execution_port` |
| Durable action bridge | `AcquisitionActionService.execute` calls `enqueue_acquisition_job`; `ControlPlaneService._process_control_job` invokes the registered `handle_job` callback |
| Concrete effect | `AcquisitionActionService.handle_job` passes its `_effect` callback to PA2; the callback calls the concrete port's `execute`, which calls `execute_live_catalog_acquisition` |
| Consumer | `handle_job` consumes `AcquisitionOwnerExecutionResult`, appends terminal phase/loop evidence, and exposes its receipt through the route projection |

The route is discoverable by its OpenAPI operation ID `execute_run_acquisition_route`.
It is not a `polisyos-tools` command, for a stated reason: the requested action requires
the request-bound DS20 floor, tenant scope and live step-up; adding a local command would
not supply these authorization facts. No new callable or loose `main()` is proposed.
The static graph cannot settle the HTTP handler or worker/effect callbacks, and this
lane does not convert its green exit into production-execution proof.

## Persisted evidence and execution-stage checks

The existing port writes append-only attempt reservation and one-shot execution-claim
files under the control root; the executor writes its request/raw/terminal JSONL journal
and evidence CAS. `CanonicalAcquisitionAuthority.resolve_live_source_execution` reopens
and verifies those concrete bytes; `resolve_journal_event_ref` resolves exact journal
records. The service's existing phase and terminal sinks persist CAS/event/head bindings;
`_read_phase_receipt` and the route projection are the exact readers. An executor receipt
or fixture worker receipt cannot be relabelled a receipt of the absent full production
PA2 composition.

After this document is committed, run only the following named witness nodes; each gate
is the sole command in its invocation. Retain complete deciding outputs under the root's
gitignored `docs/superpowers/journals/residuals/n13b/raw/` and record hashes in the one
completion journal.

- `tests/integration/core_runtime/test_acquisition_route_execution_binding.py::test_production_factory_owns_authority_files_runtime_root_and_executor`
- `tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport`
- `tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_uses_orchestration_and_returns_reopenable_one_call_evidence`
- `tests/integration/core_runtime/test_acquisition_route_execution_binding.py::test_missing_authority_owner_refuses_before_attempt_reservation`
- `tests/unit/runtime/http/test_runtime_deployment_security.py::test_non_development_bootstrap_rejects_runtime_container_override`
- `tests/unit/runtime/http/test_runtime_authorization_access_audit.py::test_acquisition_get_rego_denies_same_permission_proxy_before_projection`

The final node sends a real request to the included acquisition GET and checks its
wrong-resource refusal before projection. It establishes that HTTP boundary only,
not the absent authority-provider callback or a successful execute request.

The missing-authority node is a negative for its own reason: the real factory-shaped
port is available but the provider is absent, so no attempt reservation may be written.
Removal probe: in the isolated test process, replace only
`AcquisitionActionService._require_authority_provider` with a version returning its
stored value without the absent-provider refusal; rerun the **unchanged** negative node.
The negative must become red, and the exact original source bytes remain untouched.
This proves the refusal boundary, not a completed production handshake. A real served
acquisition-request witness may be added only to measure the current refusal using the
unchanged production app/service; it must not inject a provider or claim successful
worker execution. Until measured, HTTP request execution remains `not_established`.

No source repair is authorized by this routing decision. If these witnesses reveal a
new owner defect, bucket it under P40 and route it rather than changing closed code.
No current-production happy-path receipt is promised: it depends on the missing governed
intake, which the named destination must deliver before E's complete closure signal can
run. A passing component test is not permission to close that signal.

## Pattern pass and verdict boundary

P01/P02/P12: the producer is present; the remaining end-to-end authority intake is a
separate chain. P27/P30: use delivered vocabulary and the existing production port.
P05/P32/P37: never create signed delegation, appointment, DS20 proofs or admission from
a test override. P29/P33: exact-read persisted evidence and an unchanged negative under
call removal are distinct from a constructor witness. P35/P36: complete AST denominator
and finding IDs supersede old zero counts. P38: class identity/static reachability is
not a full served production execution; a dev provider and a missing HTTP callback are
the concrete divergent cases. P40: any deeper instance of the already declared intake
absence belongs to the same routed class, not a repair ladder.

Capability states: executor producer/bridge/artifact exist; the required full production
handshake is not verified, and its governed acquisition authority-intake producer is
missing. The result is **routed-to-another-owner**, not `built` or
`already-existed-and-verified`. The request-path verification and the architecture verdict
will be reported with their actual measured codes, never inferred from this decision.

Untouched: closed Task J producer/binding source, closed DS15/PA2/bootstrap source,
semantic-epoch policy authority, positive world growth and same-case re-entry, and the
other four requested rows. No governed epoch transition is planned. Any later necessary
transition must be declared from this lane's immutable merge base above before writing.
