# TCS-01 — tenant-bound control-job status

## Property and scope

A request under verified tenant and cell scope may receive a control-job status projection only when the canonical persisted job owner matches that scope. Apply the owner predicate to direct job-ID and Lex pipeline-ID status reads, before projecting fields or performing Lex output-directory progress collection or progress writes. Missing or unresolved legacy ownership is inaccessible to tenant status readers; it must not be inferred from the current caller. Newly produced same-tenant candidate work remains available.

This is a new E02-R2 task, not an E02 regression. The public GET status gap is distinct from R1/CYC-01 and R13/ACQ-01. Keep GET /runs/{run_id} as an owner-checked consistency control. The intended audience for /control/workers and /control/outbox remains unresolved; do not claim either is a tenant leak or include them in this task.

## Owner and production path

Reuse the existing ControlPlaneStore and ControlPlaneService as the canonical owner. The production chain is authenticated request scope → route and authorization middleware → status service → runtime-supplied, possibly guarded control-store proxy → canonical job/pipeline lookup → HTTP projection. Current OPA tenant equality is based on caller scope; it does not establish the selected row's owner.

The existing producer owner source is _attach_job_actor_scope: it derives tenant_id and cell_id from the resolved execution policy actor, persists them in the immutable job payload, and the worker re-enters that scope. Carry this verified owner through the existing canonical job-store contract and enforce it at read. Do not infer ownership from path/header input, create a second owner registry, rebuild a store, or use a global getter as a status fallback. If duplicated owner data is stored on the row, enforce equality with the admitted payload scope. Historical rows with no independently reconciled owner remain inaccessible pending an authorized provenance-preserving transition.

The default service uses GuardedDependencyProxy, which forwards arguments; prove the owner predicate through that production proxy. Keep the internal production_approval_binding fallback and /runs/{run_id} projections unless a traced consumer contract specifically requires an edit. Do not remove an internal path by adjacency alone.

## Candidate write set and exact baseline scope

No product or test files have been changed for this task. First require BASELINES_DONE and broker-admitted four-base whole-file replay for every file below; any added test path absent from the frozen denominator needs separate admission before editing. The broker identified this exact off-100 existing-path union for TCS-01 and will replay it after custom99: policy-engine/tests/unit/runtime/http/test_control_api.py; policy-engine/tests/unit/runtime/http/test_runtime_rego_authorization_parity.py; policy-engine/tests/unit/runtime/http/test_runtime_api_authz.py; policy-engine/tests/unit/runtime/http/test_runtime_api_observability.py; policy-engine/tests/unit/runtime/http/test_workspace_loop_transition.py; policy-engine/tests/unit/runtime/http/test_runtime_api_write_path_hardening.py; policy-engine/tests/unit/runtime/http/services/test_lex_pipeline.py. This is an admission plan only; all seven P41 outcomes are UNRUN. test_control_service_di.py, test_normative_generation_bridge.py, and test_normative_evidence_intake.py are already in the 100-file denominator.

Core candidate production write set:
- policy-engine/src/polisyos/runtime/http/routes/control.py
- policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py
- policy-engine/src/polisyos/runtime/http/services/control/lex_pipeline.py
- policy-engine/src/polisyos/runtime/http/services/control_plane_store.py

Candidate test write set and preserving identities:
- policy-engine/tests/unit/runtime/http/test_control_api.py — extend TestCapabilities.test_get_control_job_status_returns_record with a paired cross-tenant served read; add a served Lex owner test because current unit HTTP tests have no Lex status ownership case.
- policy-engine/tests/unit/runtime/http/test_control_plane_store.py — persisted owner and owner-filtered get_job/get_job_by_pipeline behavior, including the runtime proxy path.
- policy-engine/tests/unit/runtime/http/test_runtime_deployment_security.py — extend test_service_principal_grant_reaches_opa_and_blocks_sibling_mutation to use an existing foreign job under RUNS_VIEW.
- policy-engine/tests/unit/runtime/http/test_runtime_rego_authorization_parity.py::test_server_service_read_expectation_matches_rego — retain as path-permission-only control.
- policy-engine/tests/unit/runtime/http/test_runtime_api_authz.py::test_runtime_api_denies_cross_tenant_run_access — retain run-owner control.
- policy-engine/tests/unit/runtime/http/test_control_service_di.py::test_process_nl_job_enters_persisted_tenant_scope — retain producer-to-payload-to-worker scope control, not status-ownership evidence.
- policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py::test_every_current_job_reader_replays_persisted_authority — preserve mocked reader and authority-replay behavior with explicit fixture scope if the reader contract changes.
- policy-engine/tests/unit/runtime/http/services/test_lex_pipeline.py — add service-level owner coverage; no current status-owner case was found.

If a service reader signature or default behavior changes, also replay and preserve these direct-importer test files: policy-engine/tests/unit/runtime/http/test_normative_evidence_intake.py; policy-engine/tests/unit/runtime/http/test_runtime_api_observability.py; policy-engine/tests/unit/runtime/http/test_workspace_loop_transition.py; policy-engine/tests/unit/runtime/http/test_control_service_di.py; mocked readers in policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py; and status use in policy-engine/tests/unit/runtime/http/test_runtime_api_write_path_hardening.py. Trace production importers before including them: policy-engine/src/polisyos/runtime/http/services/control/workspace_loop_transition.py, policy-engine/src/polisyos/runtime/http/services/control/production_approval_binding.py, and policy-engine/src/polisyos/runtime/http/routes/runs.py are conditional only. Add every newly affected test file to the broker's four-base whole-file replay.

## Served witnesses

- Main negative: in one real app with two independently authenticated tenants and the same admin role/OPA composition, tenant B creates a job through the normal launch and worker path. B reads the returned ID successfully. Tenant A requests that known ID and receives an indistinguishable not-found/inaccessible result with no foreign status/progress fields and no mutation.
- Lex negative/control: B creates a pipeline through the ordinary producer path; A's read of the known pipeline ID is refused before output-directory progress collection or upsert, while B can read its own status.
- Service permission negative: extend the existing RUNS_VIEW service-principal path to read an existing foreign job and prove path permission does not override stored row ownership.
- Guarded-store control: execute the tenant-filtered lookup through the actual production GuardedDependencyProxy.
- Preserving controls: same-tenant job and Lex reads remain available; GET /runs/{run_id} still succeeds for its stored owner and refuses another tenant; the Rego parity test remains only a path-permission control.

## Removal probe and attribution

Remove only the canonical persisted-owner comparison while retaining owner data, route/authz markers, and test setup. The served foreign-job assertion must turn red by observing the foreign projection or failing its explicit no-foreign-fields assertion. Keep one valid same-tenant read as the property-preserving control.

The source audit and independent review agree that the selected route, authz, store-reader and actor-scope function bodies are unchanged at 78187878e, 00d946c2b, 5fd3ebcc1, and Phase 0 f0a7a6a3. This is therefore pre-existing and not attributable to E02 or the Phase 0 merge. This is source attribution only: none of the listed tests or served requests has been run for TCS-01. Behavioral status, guarded-proxy ownership, service-principal foreign-row behavior, historical-row handling, removal probe, preserving controls, and P41 replay are all UNRUN.

## Evidence and bounded decisions

Source audit: /Users/deniskopylov/.codex/scratch/e02-r2-job-status-tenant-boundary-audit-20260925.md@sha256:a73a9200c2a87e21dd99f40aef33249fd68fe933c6db44dca4a8fdbf006e2ff0

Independent review: /Users/deniskopylov/.codex/scratch/e02-r2-tcs01-independent-review-20260925.md@sha256:361a9c72b5cfa79c9d48d931efec95bfb96991c1a304e3a04e6f9acda110a634

The independent review approves this as a separate source-level task, not as behavioral proof. Workers/outbox audience, owner reconciliation for historical rows, and any broader authority expansion remain unresolved. The task advances GY Phase 8 durable custody only; it claims no GY or Atlas closure. Relevant pattern checks: P05, P12, P31, P32, P37, P38, P40.
