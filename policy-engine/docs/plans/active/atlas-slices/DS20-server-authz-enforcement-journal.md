# Atlas DS20 Server Authorization Enforcement Journal

## 2026-07-18 — Isolation and baseline

### Worktree and base

- Worktree: `/Users/deniskopylov/polisyos/.worktrees/atlas-ds20`
- Branch: `codex/atlas-ds20-server-authz`
- Base/main at creation: `d5f83a26b1815ddc8f3156aafc87d8d89ba97157`
- Initial `git log main --oneline -3`:
  - `d5f83a26b chore: ignore pnpm store and apps build outputs`
  - `71f438ad5 docs: Atlas plan — DS3 closed & merged; debt table extended`
  - `e451cec56 merge: land Atlas DS3`
- Main checkout was clean. `.worktrees/` is ignored.

### Required reading completed in order

1. Revision-3 preamble and doctrine in `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`.
2. DS20 section.
3. DS5 section and its downstream vocabulary/audience obligations.
4. Phase-A synthesis DS4/DS5 authorization lines PI-07 through PI-10.
5. Surface constitution Law 9 and Law 11 enforcement halves.
6. DS1 authorization hotspot and seeded negatives N009 through N013.
7. Policy Design Case failure/repair register before design.

### Parallel-lane collision check

The active GY-N13b branch/worktree was compared with current `main`. Its current committed and uncommitted changes are in fabric/runtime-quality/test areas and do not touch `src/polisyos/runtime/http/**`. DS3 is already in the base. There is no genuine HTTP overlap at plan time. This check must be repeated before implementation commits and closeout; any later real overlap is a stop condition.

`git merge-tree "$(git merge-base HEAD main)" HEAD main` produced no conflict output at the pre-plan-commit checkpoint.

### Live unsafe-operation denominator

Introspection of `create_runtime_api_app()` produced exactly 29 unsafe routes:

- POST: 29
- PUT: 0
- PATCH: 0
- DELETE: 0

The full ordered denominator, permission mapping, step-up mapping, and exact parameterized deny-test IDs are recorded in the implementation plan. DS3's newly merged governed-projection/channel-contract/export-replay routes are GET-only.

### Toolchain baseline

Bootstrap invocation:

```bash
python3 -m tools.cli workspace bootstrap \
  --profile runtime \
  --skip-frontend \
  --skip-playwright \
  --skip-hooks \
  --no-install-uv
```

It created the local `.venv`, then the bootstrap's direct-file doctor subprocess failed with inherited `ModuleNotFoundError: No module named 'tools'`. The supported module invocation passed:

```bash
python3 -m tools.cli workspace doctor --skip-playwright
```

Pinned pnpm dependencies were installed with:

```bash
corepack pnpm install --frozen-lockfile --ignore-scripts
```

The two generation/canonicalization tests that initially lacked Prettier then passed.

Canonical runtime contract baseline:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml \
  polisyos-tools runtime check-runtime-api-contract
```

Result: green, `Runtime API contract check passed.`

Broad HTTP Ruff baseline:

```bash
.venv/bin/ruff check src/polisyos/runtime/http tests/unit/runtime/http
```

Result: 57 inherited diagnostics. DS20 will use changed-file Ruff and verify that it introduces zero new diagnostics.

Scoped HTTP pytest baseline has six inherited failures:

1. `tests/unit/runtime/http/test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation`
2. `tests/unit/runtime/http/test_debug_api.py::test_feedback_endpoint_returns_feedback_loop`
3. `tests/unit/runtime/http/test_debug_api.py::test_equilibria_endpoint_returns_multiplicity_report`
4. `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report`
5. `tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane`
6. `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py::test_feedback_evaluate_mutation_is_audited`

The first is an out-of-fence `runtime/quality` architecture debt. The remaining five are manifestations of the registered control-plane fixture-drift baseline. A focused rerun reproduced all six failures before any tracked edit. DS20 must not fix, hide, or expand them.

### Vocabulary finding

The old server `_ROLE_PERMISSIONS` contains 12 values; the read-only dashboard `PERMISSION_KEYS` contains 15. Its unmatched literals are:

- `collaboration.comment`
- `collaboration.share`
- `collaboration.view`

DS20 makes the server vocabulary authoritative but does not launder these client-only literals into server authority. They remain a DS5 lint/strangle finding; DS20 does not edit `apps/**`. The generated package carries the server enum for DS4/DS5 to consume.

### Fence/register finding

The authoritative DS19 disposition register is `architecture/atlas_surfaces/frontend-disposition-register.json`, outside the explicit DS20 writable fence. DS20 will record proposed N009-N013/auth-row lifecycle changes in its closure artifact and hand them to the DS19 owner rather than violating the fence. The 29 frontend operation dispositions themselves remain owned by their existing destination slices; DS20 changes their orthogonal server-authz state and therefore does not rewrite their wire/rebind/retire disposition.

### Initial capability classification

- Action-permission contract: `producer_missing`
- Route-to-policy resource binding: `bridge_missing`
- Mutating route enforcement: `consumer_missing`
- Per-operation deny proof: `verification_missing`, `semantic_test_missing`
- OpenAPI/client vocabulary: `surface_missing`
- DS9 approval UX/mandate/dissent work: explicitly downstream and not part of the DS20 completion claim

## 2026-07-18 — Pre-commit specification review

A read-only review caught and corrected the following before the first commit:

- Restored the canonical DS1 mapping: N009 generic action authorization, N010 fail-open UI identity, N011 production fixture identity, N012 production approval integrity, N013 step-up.
- Kept the three collaboration literals as DS5 findings rather than promoting deleted client vocabulary into server authority.
- Added explicit per-permission role grants, typed body/batch resource binding with ownership lookup and body replay, external IdP step-up producer/transport/config, concurrent replay proof, review-WebSocket fixture coverage, and a typed audit-event handoff.
- Added HTTP-layer production-approval principal/scorecard/signature negatives while retaining honest DS9 `artifact_missing`/`consumer_missing` labels for exposure receipts and final server signing.
- Corrected the DS19 register location and limited the handoff to N009-N013/auth rows rather than rewriting orthogonal operation dispositions.
- Corrected Python support to 3.14.x; added the Runtime HTTP README obligation and an out-of-fence release/public-surface handoff.

## 2026-07-18 — Post-plan live ownership API correction

Task-4 read-only exploration found that the committed plan overclaimed generic tenant ownership for identifiers that today's container cannot verify. Trustworthy ownership resolution currently exists for runs and content-backed/run-linked CAS artifacts. Promotion candidates are globally stored without a tenant field; basin/continuation IDs are logical target strings; lineage ownership is resolvable only for supported artifact/run/scenario forms; fabric child selectors and several analytical IDs are not ownership facts.

The plan is corrected before source implementation under P32:

- Binding source and binding authority are separate typed values.
- Only server-resolved run/artifact facts may say `ownership_verified`.
- Resolved-but-unscoped selectors retain `content_resolved_unscoped`; caller tenant is never substituted as owner.
- New logical targets are candidate slots, not existing/conflict-checked objects.
- Request composites are exact body/selector bindings, not authority claims.
- Unknown owned IDs and unsupported lineage forms deny; supported limited bindings remain visibly limited to OPA, the action dependency, and audit.

This preserves the required pre-OPA resource binding without manufacturing evidence or making legitimate create/optional request modes impossible.

## 2026-07-18 — Task 4 action permission and pre-OPA binding receipt

The red-first structural spine observed all expected failures before implementation:

- all 29 live unsafe routes lacked a genuine action dependency;
- missing, duplicate, marker-only, and synthetic sibling declarations failed the app contract;
- the OpenAPI action/resource extensions were absent;
- a late unguarded mutation reached neither a reliable construction failure nor a typed resource;
- an owned run batch reached OPA as the legacy generic `http_resource`;
- required selector, disjunctive selector, parent, and handler-rebind adversarial tests failed.

Task 4 now installs one exact `ActionPermissionDependency` and one frozen `ResourceBindingSpec` on every live unsafe route. App construction and lifespan validation enumerate the live FastAPI router; middleware repeats the check for late-added routes and executes the exact declared dependency before reading or resolving the body. The downstream FastAPI dependency must consume the same frozen resource object before a handler response is emitted. Middleware and validation short-circuits retain the preflight proof without pretending the handler dependency ran. A handler-side replacement is rejected with `authorization_binding_integrity_violation`.

The binder now has closed source/authority variants; exact bounded body capture/replay; required fields, DNF alternatives, and required-parent constraints; run/artifact ownership lookup; limited candidate/request/unscoped authority; duplicate-preserving batch digests; and versioned resource URNs. Unsupported lineage forms, unknown owned identifiers, cross-tenant resources, malformed JSON, duplicate JSON keys, non-finite values, and oversized bodies deny before OPA. Duplicate batch occurrences remain a valid response-order-preserving API contract and are protected from digest collision by the exact body hash.

Focused verification:

```text
.venv/bin/pytest tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_permission_vocabulary.py -q
.....................................

.venv/bin/ruff check <Task-4 changed Python files>
All checks passed!

.venv/bin/basedpyright --outputjson \
  src/polisyos/runtime/http/authorization.py \
  src/polisyos/runtime/http/authz_middleware.py \
  src/polisyos/runtime/http/resource_binding.py
0 errors
```

The first full scoped HTTP run found 26 failures. Four middleware short-circuit regressions (idempotency replay, request-rate limiting, rate-limit telemetry, and CSRF) and one duplicate-preserving artifact-batch regression were corrected without bypassing action preflight or binding. A `--lf` rerun leaves 21 classified failures:

- the same six baseline-red node IDs recorded above (one architecture debt and five control-plane fixture-drift nodes); and
- 15 intentional fail-closed disposition changes in read-only legacy tests: four production-approval fixture-analyst calls, seven decision-validity/publication fixture-analyst calls, one empty-ingest pre-OPA selector rejection, one nonexistent-promotion rejection, and two unknown-lineage rejections.

Those 15 tests assert the pre-DS20 insecure behavior: an analyst fixture performing admin-only mutations, malformed resource selectors reaching handler validation, or unknown resources reaching mutation handlers. They are not made green by weakening the new checks. Task 6 supplies the explicit authorized/unauthorized/absent-identity matrix; the legacy tests require an owner-approved authz-aware fixture/disposition update outside this slice's authz-test-only edits.

The GY-N13b branch advanced to `7d6239707`; its branch-only diff still has no `src/polisyos/runtime/http/**` path, so no parallel-writer collision exists at this checkpoint. `main` remains `d5f83a26b`.

One cross-fence limitation is classified rather than hidden: promotion binding hashes the resolved candidate and correctly labels it `content_resolved_unscoped`, but the public retrieval mutation API has no expected-version/digest compare-and-set. A concurrent candidate change between OPA and the handler therefore cannot be closed atomically without modifying the read-only Fabric retrieval service. DS20 does not reach into its private lock or claim atomic closure; architect review must assign the compare-and-set producer repair before this limitation can be declared closed.

### Task 4 adversarial review corrections

The first Task-4 reviews were blocked and produced four in-fence repairs:

- Production approval now resolves the persisted scorecard, rejects a scorecard whose durable `run_id` differs from the owned path run, hashes the normalized scorecard into the OPA resource, freezes its canonical bytes, and makes the handler consume that exact snapshot. The old post-OPA resolver was removed.
- Batch bindings exclude raw body order from the authorization-resource digest while retaining the exact body hash for audit/replay. Canonical selector multisets make forward and reverse batches identical; every occurrence is still resolved and a cross-tenant member denies before OPA.
- The exact raw query string is hashed into every authorization resource, so temporal/branch/snapshot mutation semantics cannot share an OPA resource merely because path and body match.
- Scenario creation resolves the actual canonical target slot before OPA, detects a persisted ID owned by another baseline run, freezes the authorized revision, and performs an atomic repository compare-and-save. A forced write between OPA and the handler returns `scenario_authorization_binding_changed` rather than overwriting the authorized slot.

Durable adversarial coverage also proves byte-identical downstream body replay; duplicate-key and invalid-UTF-8 rejection; encoded-body rejection; body-ceiling rejection; cross-run scorecard rejection; query-sensitive resource IDs; cross-run scenario collision rejection; and post-policy scenario revision race rejection. The focused authorization/vocabulary suite is now 49/49 green, the scenario API suite is 11/11 green, changed-file Ruff is green, and the four authorization/binding modules report zero basedpyright errors.

A second inherited authority limitation is recorded under P32 rather than silently changed: the existing production-approval adapter marks a content-addressed persisted scorecard identity as verified, but the HTTP-visible artifact contract does not expose verifier provenance that distinguishes an authoritative quality producer from a tenant-authored artifact. DS20 preserves that pre-existing eligibility behavior while adding permission, resource, and (in Task 5) step-up enforcement. Architect review must assign the verifier-provenance producer/contract repair; DS20 does not falsely claim that CAS presence alone proves scorecard authority.

### Task 4 second adversarial review: fail-closed execution authority

A second security review reproduced four additional in-fence gaps. All four now have durable negatives and structural repairs:

- Unsafe OPA denies no longer inherit the read-path shadow/enforcement toggle. Every unsafe request treats an OPA deny as terminal `403 authorization_denied`, including `authz_enforce=False` and shadow mode; neither handler executes.
- Delegated identity is now the single effective principal through action preflight, resource resolution/CAS access, OPA, handler execution policy, and audit attribution. A delegated analyst carried by an outer admin token is denied the admin-only mock-fallback flag, and the binding/OPA probes observe the delegated analyst rather than the outer JWT principal.
- Production approval never interprets either client overlay data or persisted scorecard data as a host-filesystem write command. The HTTP route persists only to the configured CAS; both overlay and artifact-authored `quality_evidence_bundle_path` probes leave the attacker path absent. Persisted scorecards also have explicit wrong/absent schema negatives that deny before OPA and packet persistence.
- Scenario revision compare-and-save is no longer process-local. The existing dual-backend `ControlPlaneStore` now owns a transactional `runtime_scenario_heads` logical-head table. Revision zero is insert-only; later writes are conditional on the exact immutable baseline run and expected revision; every accepted update advances exactly one revision. The immutable scenario artifact is written first, but only the successful SQL head CAS makes it authoritative. Repository reads, lists, collision checks, and fresh-context hydration resolve the head's exact artifact and verify kind, schema, scenario id, baseline run, revision, and manifest hash. Losing or legacy unheaded CAS objects are never selected.

Scenario CAS proof includes two independent SQLite store instances racing for one create (one winner), two complete runtime apps binding the same expected revision before OPA (one `200`, one `409`), baseline-run rebinding denial, corrupted-head content denial before OPA, durable-head-store absence denial before OPA, fresh-context survival, and an unheaded conflicting candidate remaining invisible. The PostgreSQL path uses the same insert-only/conditional-update linearization statements and schema, but this workstation has no configured `POLISYOS_CONTROL_POSTGRES_DSN`; no local PostgreSQL execution receipt is claimed. CI/architect review must execute the existing backend variant with a real DSN rather than accepting a mocked SQL-string proof.

Focused verification after these repairs:

```text
uv run --extra runtime --extra ml pytest -q \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_scenarios_api.py \
  tests/unit/runtime/http/test_control_plane_store.py
all selected tests passed

uv run ruff check <all Task-4 changed Python files>
All checks passed!

git diff --check
clean
```

`main` remains `d5f83a26b`. GY-N13b advanced through `17639f540`; its branch-only diff still contains no `src/polisyos/runtime/http/**` path, so the stop-on-overlap rule has not fired.

### Task 4 final review closure

The final Task-4 review found and closed two proof/authority gaps:

- Delegation now has an exact action-preflight negative: an outer ADMIN token delegated to an ANALYST is denied an ADMIN-only production-approval permission before resource binding, OPA, or handler execution. The same test inspects the existing append-only mutation audit and proves that a rejected managed control mutation records `delegated-analyst`, not the outer administrator, as actor.
- A persisted scenario using the generated default scenario ID can no longer be hidden by an ephemeral list projection. The durable SQL head wins, and a route-level test proves the list contains exactly one matching scenario with the persisted revision and manifest hash.

The re-review passed both targeted tests. The combined authorization, scenario API, and control-plane-store suites passed after these corrections, as did changed-file Ruff and `git diff --check`.

A fresh serial scoped HTTP run retained the same 21 classified failures recorded above: the six inherited baseline nodes and the 15 legacy expectations invalidated by fail-closed authorization/resource binding. No additional failure class appeared. This receipt does not convert those intentional legacy expectation changes into regressions or weaken authorization to satisfy them.

The Task-4 OpenAPI action/resource projection changed the canonical contract, so the DS3 pipeline was replayed twice in full. Both runs produced byte-identical files with these SHA-256 receipts:

```text
3048cb03cedb82760605f0fd15e7ff8fa4939878b7d28d3e6573f25f8dce3c6a  schemas/runtime_api_v1.openapi.json
137ba30652cc89ff37317d055ab63704e0ccdfdb705e618851fb7ed2f015e644  packages/runtime-api-client/types.ts
82e61027952eaad307a9f1685e23449c8911235ed269203969025ec34dc0ad94  packages/runtime-api-client/runtimeApiClient.ts
7a1094444cf72ab1ba7b6daf11bc85f4e07c289ac21c84b516724cff0f8e3945  packages/runtime-api-client/runtimeApiClient.js
45a31882719cc949f6e1d453b8a6033ee2047f76deec1f184cb8ce95a9bcdd2d  packages/runtime-api-client/canonicalRuntimeApiClient.ts
6d7465160421459492cbef22102f4f9abc1e777803706b9730e2ebfe511e9568  packages/runtime-api-client/canonicalRuntimeApiClient.js
```

The post-regeneration runtime-contract checker passed, the generated client TypeScript typecheck passed, and its architecture checker passed.

## 2026-07-18 — Task 5 step-up, fixture prohibition, and authorization-audit receipt

Task 5 closes the high-stakes authentication and fixture-identity portions of the
server security floor. The closed step-up vocabulary contains exactly five classes
and maps exactly six live operations: acquisition approval, promotion approve and
reject, decision-validity publication, run reissue/revocation, and production
approval. Every mapped operation carries one direct `StepUpDependency` after its
action dependency; app construction, lifespan startup, late-route preflight, and the
OpenAPI projection reject missing, duplicate, marker-only, misordered, unexpected,
or mismatched declarations.

The external assertion verifier now requires an explicit trusted algorithm set,
issuer, audience, active non-revoked key ID, and a static verification key or JWKS
source. A signed proof is accepted only when its subject, tenant, method, canonical
route, action permission, resource ID/digest/kind/authority, exact request-body hash,
step-up class, and (for production approval) persisted scorecard reference and
content hash all match the frozen authorization context. Freshness, future issuance,
expiration, base-user MFA, assertion MFA/assurance, human-principal type, and unique
assertion ID all fail closed. The replay producer is the existing control-plane
store: SQLite and PostgreSQL use one unique hashed assertion ID in a transaction;
two independent SQLite store instances racing on the same assertion produced one
winner and one denial.

An adversarial review found a structural execution bypass after the first green
implementation: replacing `APIRoute.app` preserved all dependency markers but
skipped FastAPI dependency execution, returned `200`, and performed the probe
mutation without a step-up header. That witness is permanent. Middleware now seals
the exact dependency objects during preflight and executes the bound action proof
and, where mapped, the step-up proof after OPA allow but before dispatch to any route
application. FastAPI's later dependency pass reuses those exact proofs without a
second replay consumption. A successful unsafe response additionally requires the
bound action proof and exact live step-up context. The marker-preserving replacement
probe now returns `403 step_up_required` with no mutation receipt.

Production approval no longer accepts self-asserted reviewer authority: override
identity must equal the verified effective subject, client-authored signatures deny
before OPA, the exact persisted scorecard bytes are normalized and hashed into the
step-up context, and a replay or missing/invalid step-up cannot persist a second
approval packet. Exact-body and exact-scorecard hashes are independently recomputed
in tests; wrong scorecard reference/hash signed claims deny.

Fixture identity is now confined to the development profile. Explicit or
environment-requested fixture identity aborts research, governed, and production
startup; an identity provider cannot smuggle the reserved fixture issuer through
HTTP or review WebSocket verification; `/auth/me` requires verified claims even if
a route-local fixture fallback is requested; empty verified roles remain empty; and
a fixture principal cannot request a non-development execution profile. The old
safe-read shadow service identity synthesis is removed.

Authorization decisions append one strict
`polisyos.runtime.authorization_audit.v1` event to the existing access-audit trail;
there is no second log. Permission, binder, OPA deny/timeout/unavailable, missing
identity, and step-up denials are covered, as are lower- and high-stakes allows.
Bearer material, step-up assertions, and request-body values are absent from the
closed event shape. An allow-path append failure blocks handler execution with 503;
a denial-path append failure preserves the original denial.

Red-first receipts include permission-only production approval persisting a packet,
the route-application structural bypass returning 200 and mutating, fixture claims
crossing non-development/provider boundaries, missing authorization audit events,
and client-authored override identity/signature reaching approval. All are now
green. The complete Task-5/adjacent scoped set collected and passed 163 tests across
the step-up, fixture, audit, action-authz, control-store/hardening, auth, and review
collaboration modules. Changed-file Ruff and `git diff --check` pass; the seven
changed authorization/security modules report zero basedpyright errors. A focused
review of the pre-dispatch repair found no remaining double-execution, audit-order,
or replay defect.

The step-up OpenAPI extension changed only the canonical schema projection; the
generated client bytes otherwise remained stable. Two full serial DS3 pipeline runs
were byte-identical:

```text
4fba08981fd1e151e27541200148f75b1e3795d0ed6dd5f15931596c28905e52  schemas/runtime_api_v1.openapi.json
137ba30652cc89ff37317d055ab63704e0ccdfdb705e618851fb7ed2f015e644  packages/runtime-api-client/types.ts
82e61027952eaad307a9f1685e23449c8911235ed269203969025ec34dc0ad94  packages/runtime-api-client/runtimeApiClient.ts
7a1094444cf72ab1ba7b6daf11bc85f4e07c289ac21c84b516724cff0f8e3945  packages/runtime-api-client/runtimeApiClient.js
45a31882719cc949f6e1d453b8a6033ee2047f76deec1f184cb8ce95a9bcdd2d  packages/runtime-api-client/canonicalRuntimeApiClient.ts
6d7465160421459492cbef22102f4f9abc1e777803706b9730e2ebfe511e9568  packages/runtime-api-client/canonicalRuntimeApiClient.js
```

The canonical runtime-contract checker and generated-client TypeScript typecheck
both pass. `main` remains `d5f83a26b`; merge-tree inspection is conflict-free.
GY-N13b advanced to `3438bf2e6` and still has no branch-only
`src/polisyos/runtime/http/**` path, so the stop-on-overlap rule has not fired.

Task 6 must convert the 31 legacy HTTP expectations invalidated by Tasks 4/5 to
authz-aware fixtures or explicit fail-closed assertions (15 action/resource-binding
changes plus 16 high-stakes ingest/promotion step-up changes). They are DS20-caused,
not inherited baseline debt, and cannot remain classified as inherited at closure.

## 2026-07-19 — Task 6 denominator proof and legacy-fixture conversion

Task 6 converted all 31 DS20-invalidated legacy expectations without weakening an
authorization check. Tests that legitimately exercise a mutation now install a
verified principal, exact role grant, allow-policy witness, and (for high-stakes
operations) a request-bound one-use step-up assertion. Tests whose old expectation
depended on malformed, unknown, cross-tenant, or fixture-authored authority now
assert the earlier fail-closed response and prove the handler side effect is absent.

Live-router introspection still yields exactly 29 unsafe operations, all `POST`.
The matrix independently proves:

- 29/29 carry exactly one direct typed action-permission dependency;
- 29/29 deny a verified principal lacking the exact permission with `403`;
- 29/29 deny absent identity with `401`; and
- 29/29 admit an authorized request into the real handler with `200`.

Six live operations carry a second direct step-up dependency across five declared
classes: acquisition approval; promotion approval and rejection; publication; run
reissue/revocation; and production approval. Valid permission without the exact
fresh assertion denies, and stale, expired, replayed, wrong-subject, wrong-tenant,
wrong-route, wrong-body, wrong-resource, wrong-class, and wrong-scorecard assertions
deny before handler execution.

The structural tests enumerate the application router rather than an authored
route list. They reject missing, duplicate, indirect, marker-only, mismatched, or
misordered action and step-up dependencies. A synthetic late-added unsafe route is
also rejected before service. Route-contract permission values must be exact members
of `RuntimePermission`; no unknown literal can acquire authority by appearing in a
decorator or client.

The focused DS20 gate collected 268 tests and passed in full. Its coverage includes
the action matrix, canonical vocabulary, step-up, fixture prohibition, fixture
loader, authorization access-audit, audience denials, N009-N013, and adversarial
binding follow-ups. The final scoped HTTP suite collects 699 tests. Its first final
pass retained the six inherited failures and two inherited skips, plus one read-only
SSE snapshot timing failure. That SSE node passed immediately in isolation and in
its complete module; the module retained only the two already-recorded control-plane
fixture failures. A pre-review repeat produced exactly the six pre-edit failures and
two inherited skips, with the SSE node green. After the final seal/`nbf` repairs, a
fresh 699-test serial run again produced exactly those six failures and two skips,
with no additional failure. The timing observation is not folded into the baseline.

## 2026-07-19 — Final adversarial review repairs

Two review rounds found additional in-fence defects. Each was first reproduced by a
negative witness and then repaired at the shared enforcement layer:

- Resource binders, OPA calls, JWKS verification/retrieval, replay consumption, and
  durable authorization-audit appends no longer block the ASGI event loop. AnyIO
  worker-thread boundaries preserve the same fail-closed exceptions. A deliberately
  slow binder no longer stalls an unrelated health request.
- Delegation-contract rejection, dependency override/replacement, unbound-resource
  rejection, and other preflight failures now append exact denial events to the
  existing access-audit trail. There is still one log and one terminal decision per
  unsafe request.
- Authorization state is sealed before handler dispatch. Direct replacement, nested
  mutation, and bulk clearing of the frozen route requirement, bound resource,
  permission proof, or step-up proof is detected before a malicious replacement
  handler can perform a side effect. An allow audit event means authorization
  admission under the sealed context, not handler success.
- Server-emitted `run:{run_id}:telemetry` lineage is recognized as an owned run
  descendant rather than denied as an unknown selector.
- Scenario lineage now freezes the exact durable head and manifest before OPA,
  rechecks the head after policy evaluation, and projects only that frozen manifest.
  A concurrent head advance returns `409` rather than projecting a resource other
  than the one authorized.
- `/auth/me` OpenAPI examples derive the analyst grant list from the canonical enum
  mapping and cannot silently become a second permission vocabulary.

The six new audit/sealing/event-loop witnesses failed before their repairs and pass
after them. A combined authorization/audit/binding follow-up run passed 52 tests;
the focused 268-test gate also passed after these changes. Changed-file Ruff and
`git diff --check` are green. Focused basedpyright at error level reports zero errors.

## 2026-07-19 — Cross-fence production integration findings

Read-only validation against OPA 1.15.2 exercised both
`ops/policy/policies/**` and the Helm policy bundle. The canonical policies do not
yet understand DS20's action/resource contract:

- an ADMIN ingestion request with the truthful empty-tenant binding is denied with
  `allow=false` and a failed tenant boundary;
- an ANALYST run launch against a same-tenant collection is denied by the legacy
  RBAC path; and
- promotion's truthful `content_resolved_unscoped` binding fails the tenant boundary
  and stale role mapping.

There is no honest HTTP-only repair. Assigning the caller tenant to an unowned or
unscoped resource fabricates ownership; skipping or rewriting the OPA decision would
weaken the security floor. This is `bridge_missing` plus `semantic_test_missing` for
the policy/Helm owner and blocks truthful end-to-end production admission even
though HTTP enforcement itself is complete.

Two production consumers also fail before reaching the API under the new floor:

- `tools/ops_runners/runtime/local_production_canary.py` requests fixture identity
  and now exits before network I/O; and
- `tools/quality/testing/local_prod_debug_probe.py` starts a production app without
  a configured step-up verifier and now exits fail closed.

The required consumer/runbook repairs are outside the DS20 fence. Their state is
`consumer_missing` plus `verification_missing`; ownership is handed to the canary,
debug-probe, and runbook lanes rather than weakening production startup.

Two pre-existing authority limitations remain explicit. Promotion candidate
consumption has no expected-digest/version compare-and-set, so the truthful
`content_resolved_unscoped` snapshot can race after OPA. Production scorecard
eligibility proves durable CAS identity but not verifier provenance; treating CAS
presence as quality authority would repeat P32. Those repairs require out-of-fence
producer/contracts and are not silently altered here. PostgreSQL replay and scenario
CAS statements share the tested SQLite contract but were not locally executed
because no `POLISYOS_CONTROL_POSTGRES_DSN` is configured.

## 2026-07-19 — Canonical projection and closeout validators

The final OpenAPI example correction was regenerated twice through the DS3 pipeline.
Both complete serial runs were byte-identical, with final per-file receipts:

```text
f94c87d56cf1cc3658c3c9330bd202fc2061fc2debad16a407d0aabf322cb0cb  schemas/runtime_api_v1.openapi.json
137ba30652cc89ff37317d055ab63704e0ccdfdb705e618851fb7ed2f015e644  packages/runtime-api-client/types.ts
82e61027952eaad307a9f1685e23449c8911235ed269203969025ec34dc0ad94  packages/runtime-api-client/runtimeApiClient.ts
7a1094444cf72ab1ba7b6daf11bc85f4e07c289ac21c84b516724cff0f8e3945  packages/runtime-api-client/runtimeApiClient.js
45a31882719cc949f6e1d453b8a6033ee2047f76deec1f184cb8ce95a9bcdd2d  packages/runtime-api-client/canonicalRuntimeApiClient.ts
6d7465160421459492cbef22102f4f9abc1e777803706b9730e2ebfe511e9568  packages/runtime-api-client/canonicalRuntimeApiClient.js
```

The exact OpenAPI/server/generated-union test, the two-run regeneration test, and
the committed package-pipeline test all pass. The canonical runtime-contract checker
passes, and the generated runtime client TypeScript typecheck passes.

The architecture guardrail remains baseline-red, with no DS20-added edge. It reports
five inherited DS3 additions (`channel_contracts` to two core modules,
`lex_pipeline` to the Lex store, and `lex_search_projection` to two modules) and
three removed baseline edges caused by DS20 improving imports (`execution_policy`
to identity and `routes.runs` to artifact IDs/canon). Synchronizing the baseline is
outside the writable fence; the improvement is not reverted merely to make the
snapshot green.

Pattern closeout re-read confirms the structural target: P05/P10/P26 authority and
audience decisions are server-enforced; P29 is behavioral live-router proof rather
than marker inspection; P31 is closed with shared preflight/state sealing rather
than per-route patches; P32 keeps ownership and scorecard provenance truthful; and
P33/P34 adversarial variants and completed exclusion runs prevent probe-shaped or
baseline-laundered green claims. The remaining Rego bridge, consumer, CAS, and
provenance work retains precise `bridge_missing`, `consumer_missing`,
`verification_missing`, `semantic_test_missing`, and `artifact_missing` labels.

### Independent final review: base-descriptor seal and `nbf`

The final independent review found no Critical issue and two Important in-fence
defects. Both were reproduced red-first:

- Because the first seal used `dict` subclasses, `dict.__setitem__` could bypass the
  overridden mutators. The response-time integrity check returned 503, but only after
  the malicious probe recorded a handler side effect.
- PyJWT `nbf` verification was delegated to the injected-clock path, but that path
  checked only `iat` and `exp`. A correctly signed and exactly bound token with
  `nbf=now+300` was accepted immediately.

The sealed resource and ASGI state are now `MutableMapping` wrappers, not `dict`
subclasses. Protected values live behind `MappingProxyType`; mutable non-authority
state is stored separately. Direct base-`dict` descriptors therefore fail before the
handler's next statement, while normal mutation attempts still raise the structured
integrity error. The access-audit consumer accepts the read-only mapping interface,
so resource attribution does not regress.

The step-up verifier now parses optional `nbf` as an exact integer under its injected
clock, rejects activation beyond configured clock skew with
`step_up_not_yet_valid`, and rejects an expiry at or before `nbf`. Invalid `nbf`
shape fails closed. The two witnesses changed from 2/2 red to 2/2 green; sibling
outer-state, malformed-window, invalid-type, and skew-boundary variants also pass.
The fresh complete focused gate now collects 268 tests.

Independent re-review closed both Important findings and found no remaining Critical
or Important issue. It exercised every direct base-`dict` mutator against both
protected wrappers and the optional/malformed/boundary `nbf` cases. The affected two
test modules passed 75 tests in that review; no reviewer file edits were made.

Final collision inspection found `main` unchanged at `d5f83a26b`. GY-N13b advanced
to `72e20ff8b` and still has zero branch-only `src/polisyos/runtime/http/**` paths.
The current-base `git merge-tree` preview emitted no conflicts. The branch remains
unmerged for architect review.

## 2026-07-19 — DS20-B cross-fence closure

The architect-ratified extension was frozen in `45f7733cd` before cross-fence
implementation. Its closeout verdicts are:

| Blocker | Verdict | Evidence |
|---|---|---|
| B1 Rego bridge | `closed` | Canonical policy consumes the exact server action/resource envelope; vocabulary and behavioral decision parity are executable. |
| B2 ops probe identity | `closed` | Canary and debug probe use strict deployment composition, dedicated minimal-grant principals, and injected short-lived bearers; no fixture or allow-all bypass remains. |
| B3 promotion CAS | `typed-limitation` | N13b owns the exact Fabric producer; no Fabric path changed. The authorize→mutate interval remains unbounded and non-atomic. |
| B4 verifier provenance | `closed` | Non-development bootstrap accepts only the exact deployment-factory bundle and rejects protocol-shaped/test verifiers. The external IdP contract is documented. |
| B5 PostgreSQL proof | `environment-blocked` | Four real-PG-only proofs exist with no SQLite fallback, but this host has no DSN, `pg_isready`, or reachable Docker daemon. |

### B1 red/green and parity

OPA 1.15.2's pre-edit 20-test harness was green while three new truthful DS20
witnesses were red: unscoped ingestion, same-tenant launch, and unscoped promotion
were all denied by the legacy tenant/role policy. The repair adds one deny-by-default
action-permission module and composes it into the canonical decision. The final
`opa check --strict ops/policy/policies` plus
`opa test --fail-on-empty -v ops/policy/policies` receipt is 45/45 passed.

The Rego vocabulary-parity test extracts the policy's declared values and requires
exact equality with all 33 `RuntimePermission` values. The decision-parity suite
builds the same sealed OPA input through the live server types and compares server
expectation with Rego for the principal × operation × resource matrix. Unknown
permission, resource class, binding authority, authorization source, extra grant,
and missing action contract all deny. A marker-only or allow-by-omission policy
cannot satisfy the suite.

The Helm chart mirror at `ops/cloud/helm/polisyos-cell/policies/**` was explicitly
outside the grant. It is now stale relative to canonical Rego and remains an honest
deployment `bridge_missing`/`verification_missing` limitation for its owner.

### B2/B4 deployment producer and probe consumers

`DeploymentSecurityConfig` resolves issuer, audience, trusted asymmetric algorithms,
JWKS URI/key rotation, OPA endpoint, cell routing, service-principal grants, step-up
freshness, replay storage, and source provenance through the deployment path. The
factory binds the exact managed-principal key
`(issuer, audience, subject, tenant, cell)` to canonical enum grants. Unknown
principals, grants, algorithms, keys, sources, and cells fail closed. An exact
factory-produced bundle is required in non-development profiles; directly composed
collaborators or test verifiers abort bootstrap.

The canary requires `POLISYOS_RUNTIME_CANARY_BEARER_TOKEN` and uses only
`runs.launch` plus `runs.view`. The debug probe requires
`POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN` and uses only `runs.view`. Both tokens are
sanitized from diagnostics. The production-chain debug witness uses a genuine RS256
JWT and canonical Rego: bad signature returns 401, the exact principal without the
required grant returns 403, and the exact `runs.view` grant reaches the protected
missing-run handler and returns 404. The runbook names the external IdP fields,
Keycloak `realm_access.roles` / `resource_access[polisyos-runtime].roles`, and MFA
`acr`/`amr`; a client-authored `mfa_verified` boolean is not accepted as provenance.

The guardrail initially exposed six new deep imports. The repair moved the OPA input
implementation onto the existing authorization-middleware edge and left
`opa_input.py` as an exact typed alias. The deployment root now consumes exact
runtime re-exports from the middleware modules that already owned the cell and
identity edges. `cell_router_middleware.py` and `jwt_auth_middleware.py` are therefore
recorded in the plan's existing-HTTP-fence guardrail addendum. No dynamic import,
core file, guardrail exception, or baseline update was used. Independent review
confirmed exact class identity/AST equivalence and no new architecture bypass.

### B3 ownership stop and quantified limitation

N13b ref `72e20ff8b` changes
`src/polisyos/fabric/retrieval/service.py`, the exact promotion mutation owner. The
mandatory ownership stop therefore fired even though the merge tree is textually
clean. No Fabric facade or storage file was edited. The race begins when the HTTP
binder copies the promotion candidate and ends only when the Fabric retrieval
service acquires its mutation lock. It spans OPA, step-up, scheduler delay, and has
no enforced upper bound; the lock releases before downstream persistence. A
post-mutation comparison plus 409 would detect some drift but could not roll back the
already-authoritative mutation, so DS20-B does not present that as CAS. The handoff
is a generic revision-CAS primitive at the public Fabric facade, owned by N13b/Fabric.

### B5 executable real-PostgreSQL proof and environment block

`test_runtime_postgres_linearizability.py` provisions one unique schema per test and
uses independent durable store/app instances. Its four properties are: exactly one
winner consumes a step-up assertion; two scenario CAS writers produce one mutation
and one 409; a corrupted durable head denies before OPA; and a fresh app ignores an
unheaded CAS artifact. Connection/provisioning failures alone become explicit
`environment_blocked` skips; assertion/property failures remain failures.

This workstation has no `POLISYOS_TEST_PG_DSN`, no `pg_isready`, and Docker reports
that its daemon is unreachable. The final focused run therefore has four explicit
PG skips. Cloud reproduction is:

```text
POLISYOS_TEST_PG_DSN='postgresql://...' uv run --extra test --extra runtime --extra multi-tenant pytest -q tests/unit/runtime/http/test_runtime_postgres_linearizability.py
```

The SQLite proofs remain labeled interim; no unexecuted PostgreSQL property is
claimed true.

### Final serialized verification receipts

- OPA strict plus Rego harness: 45/45 passed.
- DS20-B focused set: 75 selected, 70 passed, five explicit skips (four B5 plus the
  existing optional debug-probe PostgreSQL integration).
- Original focused DS20 gate after the import-boundary repair: 268/268 passed.
- Original scoped HTTP denominator after the same repair: exactly six inherited
  failures and two inherited skips, with the same node identities and no additional
  failure. The previously isolated order-sensitive SSE observation did not recur.
- Runtime API contract checker: passed.
- Runtime client TypeScript, architecture, four JavaScript tests, and ESLint: passed.
- Changed-file Ruff: only two inherited `SIM114` findings at canary lines 1117/1119,
  both blamed to `5c4823ee7c`; all task code passes with that inherited rule excluded.
- Task enforcement/deployment/test basedpyright: zero errors. A wider scan of both
  legacy probe scripts reports 26 diagnostics, all blamed to pre-DS20 lines and none
  in a DS20-B hunk.
- `git diff --check`: passed.
- Runtime schema/client diff against `9b5e4f69c`: empty. All six prior hashes are
  unchanged, so DS20-B required no regeneration.
- Architecture guardrail: zero DS20-B additions; exactly five inherited DS3 deep
  imports remain and three DS20 removals are unclaimed improvement. The baseline file
  is byte-untouched.
- `git merge-tree --write-tree HEAD main` and the N13b equivalent both exit zero.
  N13b has no textual overlap with DS20-B, while its semantic ownership of the Fabric
  producer remains the B3 stop condition.

All implementation-task re-reviews approved with no remaining Critical, Important,
or Minor finding. The branch remains unmerged for the final whole-branch review and
architect disposition.
