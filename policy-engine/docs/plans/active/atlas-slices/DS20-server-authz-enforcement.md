# Atlas DS20 Server Authorization Enforcement Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` to execute this plan task by task, with specification review followed by code-quality review after each implementation task.

**Goal:** Make every mutating Runtime HTTP operation fail closed behind a server-owned action permission, require fresh one-use step-up authentication for high-stakes actions, prohibit fixture identity outside development, and project one canonical permission vocabulary through OpenAPI into the generated runtime client.

**Architecture:** The Runtime HTTP layer owns a typed permission vocabulary and route requirement contract. An always-installed route-aware binder resolves the matched operation and its typed path/body/batch resource before OPA evaluation. A generic `require_action_permission` dependency then resolves genuine identity and checks the exact action permission; high-stakes routes layer a separate `require_step_up` dependency over it; the terminal decision is appended to the existing access-audit trail. App construction rejects unsafe routes without exactly one action dependency and rejects high-stakes routes without exactly one distinct step-up dependency, so either half cannot be omitted accidentally. OpenAPI projects the canonical permission enum and each operation's requirement; the generated TypeScript client consumes the enum, while operation extensions remain a server/schema audit contract.

**Tech stack:** Python 3.14.x, FastAPI/Starlette, Pydantic v2, PyJWT, pytest, Ruff, OpenAPI JSON, TypeScript, `openapi-typescript`, pnpm.

## 1. Scope, invariants, and fences

- Work only on branch `codex/atlas-ds20-server-authz` in `.worktrees/atlas-ds20`; do not merge.
- Writable paths are limited to:
  - `src/polisyos/runtime/http/**`
  - `schemas/**`
  - `packages/runtime-api-client/**`
  - DS20-scoped `tests/unit/runtime/http/**`
  - `docs/plans/active/atlas-slices/DS20-*`
- `apps/**`, `src/polisyos/runtime/quality/**`, and all other `src/**` paths are read-only.
- The DS19 disposition register is outside the writable fence. DS20 records the exact proposed lifecycle updates in its journal and closure report; an architect or the DS19 owner applies them.
- All unsafe HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) require exactly one action-permission dependency. Read-by-POST operations receive typed read/action permissions; there is no exemption.
- Absence, malformed state, unknown permission, missing identity, unbound resource, unavailable evaluator, missing step-up verifier, stale/replayed assertion, and audit persistence failure all deny.
- A UI decision, role name, coarse OPA allow/shadow result, fixture, or optimistic/offline state is never authorization. Action permission is never shadow-only.
- No second security log is introduced. Authorization and step-up decisions extend `RuntimeDataAccessAuditTrail`.
- No existing auth check is weakened. A conflicting check becomes a classified finding.

## 2. Required pattern pass

| Pattern | Existing failure in scope | Target repair | Acceptance signal |
|---|---|---|---|
| P01/P02 contract-only/thin orchestration | Roles and permission strings exist, but no mutating operation consumes an action requirement | Typed requirement is produced, bound, evaluated, audited, and consumed by every live unsafe operation | Live-router structural test plus request-level deny tests |
| P03 hidden internal richness | OPA and access audit exist without an operation-level public contract | OpenAPI exposes canonical permission enum and operation requirement extensions | Schema/client contract tests and two-run regeneration |
| P04/P05 status/authority leak | A coarse role or OPA result can precede action/resource enforcement | Exact action + concrete resource + step-up are fail-closed admission inputs | Permission-only high-stakes request is denied |
| P07/P08 replay/time conflation | Step-up has no freshness or replay semantics | Signed `iat`/`exp`/`jti`, bounded age, exact subject/action/resource/purpose, atomic consume | Stale and replayed assertions are denied |
| P09 warning lifecycle | Security denial can disappear into a response only | Append-only allow/deny/step-up events use the existing access-audit trail | Audit event assertions for both allow and deny |
| P10/P15 semantic/LLM authority | Client literals and UI hiding can be mistaken for authority | Server enum is authoritative; client is generated; UI remains non-authoritative | Unknown route permission fails; UI-hiding negative is server-denied |
| P12 producer handshake | Route decorators do not declare what the evaluator needs | Typed route requirement is the producer-to-binder/dependency handshake | App construction rejects missing or duplicate requirements |
| P13 governance gravity | Per-handler bespoke checks would multiply policy logic | One generic dependency, one binder, one verifier contract | No route-local permission algorithms |
| P26/P31 class-wide enforcement | 29 instances are unguarded; per-route patches would remain bypassable | Generic enumeration over the live router and generic request path | A newly added unguarded unsafe route fails automatically |
| P29/P32 authorial proof/trust by form | Marker or string presence could masquerade as enforcement | Tests execute the real dependency and remove/bypass properties adversarially | Keeping metadata while removing enforcement fails tests |
| P33/P34 teaching-to-test/exclusion | A fixed list could stay green while a sibling route bypasses it | Denominator derives from the live router; inherited failures remain isolated by recorded node IDs | Synthetic sibling route is rejected; baseline failures are unchanged |

Capability state before DS20: `producer_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, and `semantic_test_missing` for action authorization. Target state: complete capability for the Runtime HTTP enforcement floor, with an external identity provider explicitly owning step-up assertion production. The dashboard's generated-type rebind remains `consumer_missing` for DS4/DS5, and DS9 mandate/dissent/exposure-receipt UX remains explicitly downstream; neither is silently claimed complete.

## 3. Baseline and collision receipt

- Base: `d5f83a26b1815ddc8f3156aafc87d8d89ba97157` (`main`, 2026-07-18).
- Initial `main --oneline -3`: `d5f83a26b`, `71f438ad5`, `e451cec56`.
- Live Runtime app denominator: **29 POST, 0 PUT, 0 PATCH, 0 DELETE**.
- DS3 governed-projection/channel-contract/export-replay additions are GET-only; they do not change the unsafe denominator.
- GY-N13b was checked against `main`: its current committed and working-tree changes do not touch `src/polisyos/runtime/http/**`. Re-check before every implementation commit and before closeout; stop on genuine overlap.
- Supported doctor command is green. The runtime-profile bootstrap installed `.venv`; its final direct-file doctor launch hit the inherited `ModuleNotFoundError: tools`, while `python3 -m tools.cli workspace doctor --skip-playwright` passed.
- Scoped HTTP baseline has six inherited failures: one out-of-fence runtime-quality architecture violation and five control-plane fixture-drift manifestations. All other scoped tests pass after installing pinned pnpm dependencies.
- Broad HTTP Ruff baseline contains 57 inherited diagnostics. DS20 requires zero new diagnostics and runs Ruff on changed files plus focused tests.
- Canonical runtime API contract checker passes.

The journal records exact commands and node IDs.

## 4. Canonical permission vocabulary

The server enum is the only hand-authored vocabulary. Role grants import enum members; route requirements accept enum members, never strings; `/auth/me` projects the enum through OpenAPI; generated TypeScript consumes that schema. Existing UI literals are read-only inputs to the migration finding, not an authority source.

### 4.1 Preserved server/client-facing permissions

| Permission | Purpose |
|---|---|
| `dashboard.view` | View dashboard shell |
| `evidence.promotions.approve` | Approve evidence promotion |
| `evidence.promotions.reject` | Reject evidence promotion |
| `evidence.review` | Review evidence |
| `evidence.view` | View evidence |
| `knowledge.view` | View knowledge surfaces |
| `mode.analyst` | Enter analyst mode |
| `platform.admin` | Administer platform |
| `platform.view` | View platform status |
| `runs.launch` | Launch a run |
| `runs.review` | Review runs |
| `runs.view` | View runs |

### 4.2 New operation-level permissions

| Permission | Operations | Initial grants |
|---|---|---|
| `analysis.execute` | Attractor, Lyapunov, basin-map, continuation analysis | admin, analyst, service, system |
| `artifacts.batch.read` | Batch artifact lookup | admin, analyst, viewer, service, system |
| `artifacts.render` | Bureaucratic artifact rendering | admin, analyst, service, system |
| `decisions.validity.publish` | Decision-validity event publication | admin |
| `evidence.acquire` | Data ingest/acquisition execution | admin, analyst |
| `evidence.discover` | Data source discovery | admin, analyst, service, system |
| `evidence.preview` | Fetch-plan preview | admin, analyst, service, system |
| `evidence.resolve` | Data-needs resolution | admin, analyst, service, system |
| `evidence.sae.analyze` | SAE causal-frontier analysis | admin, analyst, service, system |
| `fabric.impact.analyze` | Fabric impact analysis | admin, analyst, service, system |
| `fabric.quality.read` | Batch fabric-quality lookup | admin, analyst, viewer, service, system |
| `fabric.trust.read` | Batch fabric-trust lookup | admin, analyst, viewer, service, system |
| `knowledge.search` | Lex graph search | admin, analyst, viewer, service, system |
| `knowledge.trigger` | Lex pipeline trigger | admin, analyst, service, system |
| `lineage.batch.read` | Batch lineage lookup | admin, analyst, viewer, service, system |
| `mobility.analyze` | Mobility estimate/bounds | admin, analyst, service, system |
| `runs.batch.read` | Batch run lookup | admin, analyst, viewer, service, system |
| `runs.feedback.evaluate` | Evaluate run feedback | admin, analyst, service, system |
| `runs.production_approval.create` | Create production approval | admin |
| `runs.reissue` | Reissue/revoke prior run authority | admin |
| `scenarios.create` | Create run scenario | admin, analyst |

### 4.3 Vocabulary contract tests

- `test_runtime_permission_values_are_unique_and_stable`
- `test_role_grants_only_contain_runtime_permission_members`
- `test_openapi_projects_runtime_permission_enum`

Route-consumption tests (`test_route_requirement_rejects_unknown_permission` and `test_each_mutating_operation_projects_action_permission_extension`) land with the generic dependency in Task 4. `test_generated_client_permission_union_matches_server_openapi_enum` lands with regeneration in Task 7, so no commit deliberately contains a red generated-artifact assertion.

The current read-only dashboard has three literals absent from the server (`collaboration.comment`, `collaboration.share`, `collaboration.view`). They are **not** promoted into authority: they remain an explicit DS5 lint/strangle finding, because DS20 may not edit `apps/**` and DS19 has already strangled the collaboration capability. The generated package becomes the client vocabulary source DS4/DS5 must consume; the current dashboard hand-authored list is reported as `consumer_missing`, not misrepresented as removed.

Role grants are a typed projection over the enum, not a second vocabulary. The table above is normative for new grants; existing grants remain intact. `runs.launch` retains admin/analyst/service/system, and the existing promotion permissions retain admin/analyst/service/system for response compatibility, but their human step-up class denies non-user principals before execution. An enum member omitted from every role remains ungranted, not implicitly public. Every grant is exercised by an allow and a deny test. The dependency accepts only middleware-verified `UserIdentityClaims` or a cryptographically verified delegated/SPIFFE `AccessScope`; raw role/permission headers never create a principal. DS5 may re-scope audience grants later, but cannot change the vocabulary or bypass the dependency.

## 5. Step-up model

`StepUpClass` is a closed enum with:

- `promotion`
- `production_approval`
- `publication`
- `revocation`
- `acquisition_approval`

The acquisition class is declared now for N13b's later dedicated approval route; DS1-N013 also requires the present connector-ingest/acquisition-execution route to use it. The producer is the configured external identity provider/step-up service, not PolicyOS or the browser. It delivers a signed assertion in `X-PolicyOS-Step-Up`; `RuntimeSecurityConfig` carries a verifier configured with trusted algorithms, issuer, audience, maximum age, clock skew, and an atomic replay store. A signed assertion binds issuer, audience, subject, tenant, HTTP method, canonical route, action permission, resource binding, step-up purpose/class, request-body SHA-256, issued-at, expiry, MFA/assurance, and unique `jti`. Production approval also binds the persisted scorecard reference/body digest; no client-authored evidence or signature is trusted as a step-up fact. The verifier enforces signature/issuer/audience, freshness/future-skew, exact request binding, and atomic one-use replay consumption. PolicyOS intentionally exposes no assertion issuer in DS20; the external IdP contract is the producer boundary, not `producer_missing`. Missing verifier or replay store fails closed.

All five current classes require a verified user principal and MFA/step-up assurance; a service/system role cannot satisfy them merely because its legacy `/auth/me` projection contains a permission. A future machine-governed approval must introduce a separately reviewed assurance class and tests rather than reuse a human class.

Current high-stakes bindings:

| Operation | Step-up class |
|---|---|
| data promotion approve/reject | `promotion` |
| production approval | `production_approval` |
| decision-validity publication | `publication` |
| run reissue | `revocation` |
| data ingest/acquisition | `acquisition_approval` |

Tests:

- `test_high_stakes_action_permission_without_step_up_is_denied`
- `test_step_up_assertion_with_wrong_action_or_resource_is_denied`
- `test_stale_step_up_assertion_is_denied`
- `test_future_step_up_assertion_is_denied`
- `test_replayed_step_up_assertion_is_denied`
- `test_concurrent_replay_allows_exactly_one_step_up_consumer`
- `test_valid_step_up_assertion_is_consumed_once`
- `test_missing_step_up_verifier_fails_closed`

## 6. Live mutating-operation denominator and exact red-first cases

The three exact test function names are:

- `test_mutating_operation_authorized_request_reaches_handler`
- `test_mutating_operation_without_permission_is_denied_403`
- `test_mutating_operation_without_identity_is_denied_401`

Pytest appends the square-bracketed Case ID from the table to each function name. Therefore row `analyze-attractors`, for example, has the exact node IDs `test_mutating_operation_authorized_request_reaches_handler[analyze-attractors]`, `test_mutating_operation_without_permission_is_denied_403[analyze-attractors]`, and `test_mutating_operation_without_identity_is_denied_401[analyze-attractors]`; the same deterministic naming applies to every listed row through `create-run-scenario`.

The dependency executes before body validation in the deny cases, proving an invalid/minimal body cannot bypass or obscure admission. Authorized cases call the live app with valid minimal payloads, route resources, service fixtures, exact permission, and fresh step-up where applicable; each must reach the real handler and return its documented 2xx response while emitting an allow audit event. A 404/409/422/5xx response is not accepted as the authorized proof.

Each requirement also declares a typed `ResourceBindingSpec`. Live-API review showed that only runs and content-backed CAS artifacts currently have trustworthy tenant-ownership resolvers; promotion, logical analysis, generic lineage, and several derived selectors do not. DS20 therefore separates binding source from binding authority instead of laundering a request ID into tenant ownership (P32).

The closed source variants are `owned_existing_path`, `owned_existing_batch`, `resolved_selector`, `resolved_selector_batch`, `candidate_target_slot`, `owned_parent_or_request_composite`, `request_composite`, and `tenant_collection`. The frozen result carries one of `ownership_verified`, `content_resolved_unscoped`, `candidate`, `request_bound`, or `tenant_collection`. `ownership_verified` is available only after server-side resolution and exact tenant comparison. `content_resolved_unscoped` proves the object/selector exists and content-binds its digest but explicitly does **not** claim tenant ownership; the OPA resource kind and audit event retain that limitation. `candidate` binds a new target slot relative to a verified parent/tenant where available, without inventing conflict detection. This prevents both fail-open generic resources and fail-closed rejection of legitimate create/optional-mode requests.

The pre-OPA binder first performs exact action-permission preflight so malformed/unknown resources cannot become an oracle. It then reads at most the configured JSON-body ceiling, validates JSON, applies the route's variant, canonicalizes unordered sets, resolves only facts supported by the installed runtime container, includes the binding-authority label and SHA-256 of the exact request bytes, and replays the identical bytes downstream. Request-carried tenant claims never establish ownership. A field is required only when its request schema and binding variant require it. Malformed bodies, unknown/cross-tenant **owned** identifiers, excessive bodies, duplicate identifiers where forbidden, or an empty owned batch deny before OPA; request/candidate modes bind their honest limited authority instead. Where the existing `AuthzInput` has no composite/authority field, the versioned digest is encoded in `resource_artifact_id` and the authority label in the route-specific `resource_kind`; it is never replaced by generic `http_resource` or caller-tenant-as-owner.

| # | Case ID | Method and path | Permission | Resource binding before OPA | Step-up |
|---:|---|---|---|---|---|
| 1 | `analyze-attractors` | `POST /api/v1/analysis/attractors` | `analysis.execute` | `tenant_collection`: `runtime.analysis.attractors` + body digest | — |
| 2 | `analyze-lyapunov` | `POST /api/v1/analysis/lyapunov` | `analysis.execute` | `tenant_collection`: `runtime.analysis.lyapunov` + body digest | — |
| 3 | `persist-basin-map` | `POST /api/v1/analysis/basin-map` | `analysis.execute` | `candidate_target_slot`: logical analysis/basin selectors + body digest; no ownership claim | — |
| 4 | `persist-continuation-branch` | `POST /api/v1/analysis/continuation` | `analysis.execute` | `candidate_target_slot`: logical analysis/branch selectors + body digest; no ownership claim | — |
| 5 | `get-artifact-batch` | `POST /api/v1/artifacts/batch` | `artifacts.batch.read` | `owned_existing_batch`: canonical content-backed `artifact_ids` | — |
| 6 | `render-bureaucratic-artifact` | `POST /api/v1/artifacts/{packet_id}/render` | `artifacts.render` | `owned_existing_path`: content-backed `packet_id` + body digest | — |
| 7 | `launch-run` | `POST /api/v1/control/runs` | `runs.launch` | `tenant_collection`: `runtime.run_collection` + body digest | — |
| 8 | `evaluate-run-feedback` | `POST /api/v1/control/runs/{run_id}/feedback/evaluate` | `runs.feedback.evaluate` | `owned_existing_path`: `run_id` | — |
| 9 | `launch-nl-run` | `POST /api/v1/control/runs/nl` | `runs.launch` | `tenant_collection`: `runtime.run_collection` + body digest | — |
| 10 | `reissue-run` | `POST /api/v1/control/runs/{run_id}/reissue` | `runs.reissue` | `owned_existing_path`: `run_id` | `revocation` |
| 11 | `publish-decision-validity-event` | `POST /api/v1/control/decision-validity/events` | `decisions.validity.publish` | `request_composite`: source/dependency/dedupe fields + digest | `publication` |
| 12 | `ingest-data` | `POST /api/v1/control/data/ingest` | `evidence.acquire` | `request_composite`: optional binding/dataset/fetch-plan fields + digest | `acquisition_approval` |
| 13 | `resolve-data-needs` | `POST /api/v1/control/data/resolve` | `evidence.resolve` | `request_composite`: canonical data-need tuples + digest | — |
| 14 | `discover-data-sources` | `POST /api/v1/control/data/discover` | `evidence.discover` | `request_composite`: canonical data-need tuples + digest | — |
| 15 | `preview-fetch-plan` | `POST /api/v1/control/data/preview` | `evidence.preview` | `request_composite`: fetch-plan fields + digest | — |
| 16 | `estimate-causal-frontier-sae` | `POST /api/v1/control/analytics/sae/causal-frontier` | `evidence.sae.analyze` | `request_composite`: optional areas/exposure + digest | — |
| 17 | `approve-data-promotion` | `POST /api/v1/control/data/promotion/{promotion_id}/approve` | `evidence.promotions.approve` | `resolved_selector`: candidate content digest, explicitly tenant-unscoped | `promotion` |
| 18 | `reject-data-promotion` | `POST /api/v1/control/data/promotion/{promotion_id}/reject` | `evidence.promotions.reject` | `resolved_selector`: candidate content digest, explicitly tenant-unscoped | `promotion` |
| 19 | `trigger-lex-pipeline` | `POST /api/v1/control/lex/trigger` | `knowledge.trigger` | `tenant_collection`: `runtime.lex_workspace` + body digest | — |
| 20 | `search-lex-graph` | `POST /api/v1/control/lex/search` | `knowledge.search` | `tenant_collection`: `runtime.lex_workspace` + query digest | — |
| 21 | `get-fabric-quality-batch` | `POST /api/v1/fabric/quality/batch` | `fabric.quality.read` | `owned_parent_or_request_composite`: owned run when present; child selectors remain request-bound | — |
| 22 | `get-fabric-trust-batch` | `POST /api/v1/fabric/trust/batch` | `fabric.trust.read` | `owned_parent_or_request_composite`: owned run when present; child selectors remain request-bound | — |
| 23 | `analyze-fabric-impact` | `POST /api/v1/fabric/impact` | `fabric.impact.analyze` | `owned_parent_or_request_composite`: owned run when present; otherwise limited selector digest | — |
| 24 | `get-lineage-batch` | `POST /api/v1/lineage/batch` | `lineage.batch.read` | `resolved_selector_batch`: resolve supported artifact/run/scenario forms; unknown form denies | — |
| 25 | `estimate-mobility` | `POST /api/v1/mobility/estimate` | `mobility.analyze` | `tenant_collection`: `runtime.mobility_estimate` + body digest | — |
| 26 | `compute-mobility-bounds` | `POST /api/v1/mobility/bounds` | `mobility.analyze` | `tenant_collection`: `runtime.mobility_bounds` + body digest | — |
| 27 | `get-runs-batch` | `POST /api/v1/runs/batch` | `runs.batch.read` | `owned_existing_batch`: canonical `run_ids` | — |
| 28 | `create-run-production-approval` | `POST /api/v1/runs/{run_id}/production-approval` | `runs.production_approval.create` | `owned_existing_path`: owned `run_id`; scorecard content must bind to that run | `production_approval` |
| 29 | `create-run-scenario` | `POST /api/v1/runs/{run_id}/scenarios` | `scenarios.create` | `candidate_target_slot`: owned parent run + revisioned scenario slot/body digest | — |

Structural spine tests:

- `test_live_mutating_route_denominator_is_29`
- `test_openapi_mutating_denominator_matches_live_router`
- `test_mutating_routes_have_exactly_one_action_permission_dependency`
- `test_high_stakes_routes_have_exactly_one_distinct_step_up_dependency`
- `test_step_up_dependency_cannot_replace_action_permission_dependency`
- `test_mutating_route_without_action_permission_fails_app_contract`
- `test_mutating_route_with_duplicate_action_permissions_fails_app_contract`
- `test_mutating_route_marker_without_executable_dependency_fails_app_contract`
- `test_new_sibling_mutating_route_is_automatically_in_denominator`

Task 2 writes the action-dependency structural red first. The two distinct-step-up structural tests are added red-first in Task 5 immediately before the six high-stakes route dependencies (across five classes) are attached; no Task-4 commit contains a test for a dependency whose implementation is deferred.

The denominator assertion is a drift receipt, while coverage derives from the live router and fails with the concrete uncovered operation list. When main legitimately adds a route, the expected count and case table are updated together only after it has a requirement and the three request-level cases.

## 7. Identity, resource binding, audience, and audit

### 7.1 Fixture identity removal and blast radius

- App startup rejects `allow_fixture_identity=True` for every non-development deployment profile, including production/governed profiles.
- `/auth/me` never synthesizes `_fallback_identity`; it returns only middleware-verified claims or 401.
- Development fixture middleware remains an explicit development-only test/dev facility and may not cross the startup invariant.
- Existing tests relying on implicit `/auth/me` fallback are converted to explicit verified claims or classified as inherited fixture-drift; no global permissive default is introduced.

Tests:

- `test_fixture_identity_is_refused_in_production_profile`
- `test_fixture_identity_is_refused_in_governed_profile`
- `test_fixture_identity_remains_explicitly_available_in_development_profile`
- `test_auth_me_without_verified_claims_is_401_even_when_fallback_was_requested`
- `test_auth_me_returns_only_middleware_verified_identity`
- `test_review_websocket_cannot_start_with_fixture_identity_in_non_dev_profile`

### 7.2 Bind before OPA

A route-aware middleware resolves the matched `APIRoute`, typed binding spec, path parameters, bounded/replayable JSON body, exact permission, step-up class, and stable single/composite resource identifier before the existing OPA middleware runs. Unsafe requests without a bound typed requirement are rejected before OPA. OPA receives the same immutable binding later consumed by the route dependency; rebinding or handler-side mutation is rejected. A batch is one canonical multi-resource binding, not a generic collection allow, and its handler must independently retain existing per-item tenant checks.

Tests:

- `test_opa_receives_bound_route_resource_before_evaluation`
- `test_opa_never_evaluates_an_unbound_mutating_resource`
- `test_bound_resource_contains_concrete_path_identifier`
- `test_body_resource_binding_is_available_to_opa_and_body_reaches_handler_unchanged`
- `test_batch_resource_binding_is_order_independent_and_contains_every_identifier`
- `test_owned_body_resource_binding_rejects_cross_tenant_identifier_before_opa`
- `test_unscoped_selector_binding_never_claims_caller_tenant_ownership`
- `test_missing_declared_body_resource_field_denies_before_opa`
- `test_route_cannot_rebind_resource_after_opa_decision`

### 7.3 Audience and UI-hiding negatives

DS5 owns the final audience algebra. DS20 proves the enforcement half now:

- `test_public_principal_is_denied_reviewer_operation_server_side` directly calls `POST /api/v1/runs/{run_id}/production-approval`.
- `test_public_principal_is_denied_expert_operation_server_side` directly calls `POST /api/v1/control/analytics/sae/causal-frontier`.
- `test_hidden_client_action_remains_denied_when_called_directly`
- `test_role_name_without_exact_permission_is_denied`
- `test_unverified_permission_header_is_ignored`
- `test_service_principal_cannot_satisfy_human_step_up_class`
- `test_coarse_opa_allow_without_exact_permission_is_denied`

### 7.4 Existing append-only audit trail

Extend `RuntimeDataAccessAuditTrail` with a strict typed `RuntimeAuthorizationAuditEvent` carrying schema version, timestamp, request/operation ID, authorization outcome, permission, bound-resource digest/kind, step-up class/outcome, principal/tenant identifiers, OPA policy/version when available, and a stable denial reason. Never persist bearer/step-up tokens or raw request bodies. One shared idempotent terminal emitter is called by the JWT/fail-closed perimeter (missing/invalid identity), resource binder (binding denial), `AuthzMiddleware` (OPA deny/timeout/unavailable), action dependency, and step-up dependency. Its request-state terminal flag prevents double events when a downstream component has already emitted. Audit append failure denies every mutation; if the request was already denied, the denial remains fail-closed and the append failure is surfaced in metrics/logging without converting it to allow. DS9's later consumer can calculate review effectiveness from this stable event; that consumer is `consumer_missing` by design and outside the DS20/runtime-quality fence, not replaced by a second log.

Tests:

- `test_authorization_allow_is_appended_to_existing_access_audit_trail`
- `test_authorization_deny_is_appended_to_existing_access_audit_trail`
- `test_resource_binding_denial_is_appended_before_opa`
- `test_opa_denial_and_timeout_are_appended_once`
- `test_missing_identity_denial_is_appended_without_unbound_authority_claims`
- `test_step_up_denial_is_appended_without_token_material`
- `test_high_stakes_action_denies_when_access_audit_append_fails`
- `test_lower_stakes_action_denies_when_access_audit_append_fails`

## 8. DS1 seeded negatives N009-N013

| ID | Red-first test(s) | DS20 closure claim |
|---|---|---|
| N009 generic action authz | live-router structural tests plus all 29 × 3 cases | Closed when denominator is N/N and a synthetic sibling fails construction |
| N010 fail-open UI identity | `test_ds1_n010_ui_fallback_identity_cannot_authorize_any_mutation` plus all 29 absent-identity cases | The fallback's authority effect is closed server-side: its direct calls are 401 and it cannot reach a handler. The still-rendered dashboard placeholder is an out-of-fence DS5 `consumer_missing` finding, so DS20 does not falsely claim the UI presentation itself was deleted |
| N011 fixture identity | fixture/profile, review-WebSocket, and `/auth/me` tests in §7.1 | Closed server-side: non-dev fixture configuration is impossible and missing genuine identity is 401 |
| N012 production approval | production-approval action/step-up tests; `test_production_approval_override_identity_must_equal_verified_subject`; `test_production_approval_rejects_client_asserted_signature`; `test_production_approval_binds_persisted_scorecard_in_step_up`; `test_production_approval_denial_never_persists_packet` | DS20 closes HTTP admission, verified-principal attribution for overrides, client-signature self-assertion, scorecard/request binding, replay, and cross-tenant denial. Evidence-exposure receipt plus the final server-signed mandate/dissent record remain DS9 `artifact_missing`/`consumer_missing` because their core/runtime-quality contracts are outside the writable fence; no over-claim |
| N013 step-up | high-stakes class table and verifier tests | Closed for all present class members; acquisition class remains ready for a future N13b route and structural coverage forces its declaration |

## 9. Implementation tasks and red/green gates

### Task 1: Commit the executable plan and baseline journal

**Files:**

- Create `docs/plans/active/atlas-slices/DS20-server-authz-enforcement.md`
- Create `docs/plans/active/atlas-slices/DS20-server-authz-enforcement-journal.md`

**Steps:**

1. Record live denominator, exact test IDs, vocabulary, step-up classes, fixture blast radius, pattern pass, inherited failures, collision receipt, and fence conflict.
2. Run `git diff --check` and scan for unresolved markers.
3. Commit only the plan and journal: `docs: plan Atlas DS20 server authorization`.

### Task 2: Write the structural and vocabulary contract tests red-first

**Files:**

- Modify `tests/unit/runtime/http/test_runtime_api_authz.py`
- Create `tests/unit/runtime/http/test_runtime_permission_vocabulary.py`

**Red command:**

```bash
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_permission_vocabulary.py -q
```

**Expected red:** the live structural test reports all 29 uncovered without importing a future marker, and the vocabulary test cannot import the canonical enum. Capture the full failing node IDs/output.

Do not stage or commit the red structural test. Leave it as the executable failing specification for Task 4. Task 3 first turns only the vocabulary slice green and commits no failing test.

**Commit:** none; this is the mandatory red receipt.

### Task 3: Implement and project the canonical permission vocabulary

**Files:**

- Create `src/polisyos/runtime/http/permissions.py`
- Modify `src/polisyos/runtime/http/routes/auth.py`
- Modify `src/polisyos/runtime/http/openapi_contract.py`
- Modify `src/polisyos/runtime/http/app.py`
- Modify `src/polisyos/runtime/http/README.md`
- Update Task 2 tests

**Red-first slices:** enum absence, role-map enum membership, and the dynamically generated OpenAPI enum. Operation extension and generated-client equality remain assigned to Tasks 4 and 7 respectively.

**Green command:**

```bash
.venv/bin/pytest tests/unit/runtime/http/test_runtime_permission_vocabulary.py -q
.venv/bin/ruff check \
  src/polisyos/runtime/http/permissions.py \
  src/polisyos/runtime/http/routes/auth.py \
  src/polisyos/runtime/http/openapi_contract.py \
  src/polisyos/runtime/http/app.py \
  tests/unit/runtime/http/test_runtime_permission_vocabulary.py
```

**Commit:** `feat: own runtime permission vocabulary`

### Task 4: Add generic route requirements, pre-OPA resource binding, and wire all 29 routes

**Files:**

- Create `src/polisyos/runtime/http/authorization.py`
- Modify `src/polisyos/runtime/http/access_audit.py`
- Modify `src/polisyos/runtime/http/app.py`
- Modify `src/polisyos/runtime/http/authz_middleware.py`
- Modify `src/polisyos/runtime/http/routes/analysis.py`
- Modify `src/polisyos/runtime/http/routes/artifacts.py`
- Modify `src/polisyos/runtime/http/routes/control.py`
- Modify `src/polisyos/runtime/http/routes/fabric.py`
- Modify `src/polisyos/runtime/http/routes/lineage.py`
- Modify `src/polisyos/runtime/http/routes/mobility.py`
- Modify `src/polisyos/runtime/http/routes/runs.py`
- Modify `src/polisyos/runtime/http/routes/scenarios.py`
- Update `tests/unit/runtime/http/test_runtime_api_authz.py`

**Red-first slices:** missing/duplicate/marker-only action dependencies, sibling route, unknown permission, unbound/body/batch OPA resource, shared pre-dependency audit emission, and direct 403/401 behavior. Step-up structural tests are deliberately not introduced until Task 5.

**Green command:**

```bash
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_authz.py -q
.venv/bin/ruff check \
  src/polisyos/runtime/http/authorization.py \
  src/polisyos/runtime/http/access_audit.py \
  src/polisyos/runtime/http/app.py \
  src/polisyos/runtime/http/authz_middleware.py \
  src/polisyos/runtime/http/routes/analysis.py \
  src/polisyos/runtime/http/routes/artifacts.py \
  src/polisyos/runtime/http/routes/control.py \
  src/polisyos/runtime/http/routes/fabric.py \
  src/polisyos/runtime/http/routes/lineage.py \
  src/polisyos/runtime/http/routes/mobility.py \
  src/polisyos/runtime/http/routes/runs.py \
  src/polisyos/runtime/http/routes/scenarios.py \
  tests/unit/runtime/http/test_runtime_api_authz.py
```

**Commit:** `feat: enforce action permissions on runtime mutations`

### Task 5: Add step-up, fixture prohibition, and audit events

**Files:**

- Create `src/polisyos/runtime/http/step_up.py`
- Modify `src/polisyos/runtime/http/authorization.py`
- Modify `src/polisyos/runtime/http/access_audit.py`
- Modify `src/polisyos/runtime/http/app.py`
- Modify `src/polisyos/runtime/http/authz_middleware.py`
- Modify `src/polisyos/runtime/http/jwt_middleware.py`
- Modify `src/polisyos/runtime/http/fail_closed_middleware.py`
- Modify `src/polisyos/runtime/http/security.py`
- Modify `src/polisyos/runtime/http/routes/auth.py`
- Modify `src/polisyos/runtime/http/routes/control.py`
- Modify `src/polisyos/runtime/http/routes/runs.py`
- Create `tests/unit/runtime/http/test_runtime_step_up_authz.py`
- Create `tests/unit/runtime/http/test_runtime_fixture_identity_prohibition.py`
- Create `tests/unit/runtime/http/test_runtime_authorization_access_audit.py`

**Red-first slices:** add the distinct-step-up structural tests, observe all six high-stakes operations across five classes uncovered, then attach executable `require_step_up` dependencies in `routes/control.py` and `routes/runs.py`; permission-only high-stakes, stale, future, replay, wrong binding, missing verifier, production/governed fixture, fallback `/auth/me`, perimeter/OPA/step-up audit allow/deny/failure.

**Green command:**

```bash
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_step_up_authz.py \
  tests/unit/runtime/http/test_runtime_fixture_identity_prohibition.py \
  tests/unit/runtime/http/test_runtime_authorization_access_audit.py -q
.venv/bin/ruff check \
  src/polisyos/runtime/http/step_up.py \
  src/polisyos/runtime/http/authorization.py \
  src/polisyos/runtime/http/access_audit.py \
  src/polisyos/runtime/http/app.py \
  src/polisyos/runtime/http/authz_middleware.py \
  src/polisyos/runtime/http/jwt_middleware.py \
  src/polisyos/runtime/http/fail_closed_middleware.py \
  src/polisyos/runtime/http/security.py \
  src/polisyos/runtime/http/routes/auth.py \
  src/polisyos/runtime/http/routes/control.py \
  src/polisyos/runtime/http/routes/runs.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_step_up_authz.py \
  tests/unit/runtime/http/test_runtime_fixture_identity_prohibition.py \
  tests/unit/runtime/http/test_runtime_authorization_access_audit.py
```

**Commit:** `feat: require step-up for high-stakes mutations`

### Task 6: Complete per-operation, audience, and seeded-negative coverage

**Files:**

- Complete `tests/unit/runtime/http/test_runtime_api_authz.py`
- Create `tests/unit/runtime/http/test_authorization_audience_denials.py`
- Create `tests/unit/runtime/http/test_ds20_seeded_negatives.py`

**Red-first slices:** add one operation at a time in denominator order; observe 403/401 before adding its route requirement or grant fixture. Add authorized admission last. N009-N013 tests call the real live app/dependency path.

**Green command:**

```bash
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_authorization_audience_denials.py \
  tests/unit/runtime/http/test_ds20_seeded_negatives.py -q
.venv/bin/ruff check \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_authorization_audience_denials.py \
  tests/unit/runtime/http/test_ds20_seeded_negatives.py
```

**Commit:** `test: prove runtime authorization deny paths`

### Task 7: Regenerate schema and canonical runtime client reproducibly

**Files:**

- Regenerate `schemas/runtime_api_v1.openapi.json`
- Regenerate `packages/runtime-api-client/types.ts`
- Regenerate `packages/runtime-api-client/runtimeApiClient.ts`
- Regenerate `packages/runtime-api-client/runtimeApiClient.js`
- Regenerate `packages/runtime-api-client/canonicalRuntimeApiClient.ts`
- Regenerate `packages/runtime-api-client/canonicalRuntimeApiClient.js`
- Modify `packages/runtime-api-client/README.md` to name the generated permission enum as the consumer contract
- Modify `tests/unit/runtime/http/test_runtime_api_contract_hardening.py` with `test_generated_client_permission_union_matches_server_openapi_enum`
- Do not run or commit the dashboard generator under `apps/**`

**Commands, serially:**

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate
ds20_regen_hash_1="$(shasum -a 256 \
  schemas/runtime_api_v1.openapi.json \
  packages/runtime-api-client/types.ts \
  packages/runtime-api-client/runtimeApiClient.ts \
  packages/runtime-api-client/runtimeApiClient.js \
  packages/runtime-api-client/canonicalRuntimeApiClient.ts \
  packages/runtime-api-client/canonicalRuntimeApiClient.js | shasum -a 256)"
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate
ds20_regen_hash_2="$(shasum -a 256 \
  schemas/runtime_api_v1.openapi.json \
  packages/runtime-api-client/types.ts \
  packages/runtime-api-client/runtimeApiClient.ts \
  packages/runtime-api-client/runtimeApiClient.js \
  packages/runtime-api-client/canonicalRuntimeApiClient.ts \
  packages/runtime-api-client/canonicalRuntimeApiClient.js | shasum -a 256)"
test "$ds20_regen_hash_1" = "$ds20_regen_hash_2"
corepack pnpm --dir packages/runtime-api-client run typecheck
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_schema_and_clients_regenerate_byte_identically_twice \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_committed_runtime_client_matches_package_generation_pipeline -q
```

Capture hashes after run one and assert identical hashes after run two; do not rely only on a clean diff.

**Commit:** `build: project runtime permission vocabulary`

### Task 8: Closeout verification, register handoff, and architect-review package

**Files:**

- Update `docs/plans/active/atlas-slices/DS20-server-authz-enforcement-journal.md`
- Create `docs/plans/active/atlas-slices/DS20-server-authz-enforcement-closure.md`

**Verification, serial where shared `.tmp` is involved:**

```bash
.venv/bin/pytest \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_permission_vocabulary.py \
  tests/unit/runtime/http/test_runtime_step_up_authz.py \
  tests/unit/runtime/http/test_runtime_fixture_identity_prohibition.py \
  tests/unit/runtime/http/test_runtime_authorization_access_audit.py \
  tests/unit/runtime/http/test_authorization_audience_denials.py \
  tests/unit/runtime/http/test_ds20_seeded_negatives.py -q
git diff --name-only main...HEAD -- '*.py' | xargs .venv/bin/ruff check
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools architecture guardrails check
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
corepack pnpm --dir packages/runtime-api-client run typecheck
git diff --check main...HEAD
git diff --check
git diff --stat main...HEAD
git status --short
```

Then:

1. Re-run the full scoped HTTP suite only to compare with the six recorded inherited baseline failures; no full repository pytest.
2. Re-read the failure/repair register and record pattern closure by ID.
3. Recompute the live denominator and report `N/N dependency`, `N/N 403`, `N/N 401`, and `N/N authorized admission` independently.
4. Compare current `main` and GY-N13b route diffs; stop if overlap appeared.
   Also run a current-base `git merge-tree` preview and record the result before each implementation commit and at closeout.
5. Record the N009-N013/auth-row lifecycle proposal for the DS19 owner without editing `architecture/atlas_surfaces/frontend-disposition-register.json`. The 29 route disposition rows remain unchanged because DS20's security floor is orthogonal to their wire/rebind/retire destination; no disposition is falsely marked resolved.
6. Record DS5 handoff: enum/schema/generated type, role-grant semantics, and client-literal lint debt.
7. Record DS9 handoff: authorization/step-up audit events and the deliberately unclaimed mandate/dissent/exposure-receipt/server-signature work.
8. Classify the Runtime API v1/OpenAPI change as `public_stable` and record the required release-fragment/public-surface migration handoff; those paths are outside the writable fence. Confirm the internal Python modules are not added to the package public facade.
9. Obtain final specification review and code-quality review over `main...HEAD`.
10. Commit closure documentation. Leave the clean branch unmerged for architect review.

## 10. Completion criteria

DS20 is complete only when all are true:

- Live denominator is recomputed and every unsafe operation is covered: `N/N` dependency, per-permission 403, absent-identity 401, and authorized admission.
- A synthetic new unsafe route cannot construct/serve without exactly one executable typed requirement.
- The server enum is the only authoritative authored vocabulary and the canonical package client reproduces it byte-identically in two runs; the read-only dashboard duplicate is explicitly `consumer_missing` for DS4/DS5, not counted as authority.
- High-stakes operations deny without a fresh, correctly bound, one-use step-up assertion.
- Fixture identity is rejected outside development and `/auth/me` has no fallback identity path.
- OPA cannot evaluate an unsafe request before concrete resource binding.
- Authorization telemetry lands only in the existing append-only access-audit trail.
- N009-N013 statuses are evidenced without claiming DS5 or DS9 downstream work complete.
- Changed-file Ruff, architecture guardrails, runtime contract, client typecheck, reproducibility checks, and focused tests pass; scoped-suite results are baseline-relative to the six inherited failures.
- Fence proof, collision proof, clean tree, commits, and architect-review handoffs are recorded. No merge occurs.
