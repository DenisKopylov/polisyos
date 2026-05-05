# Runtime Auth and Tenant Model

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/app.py`, `src/polisyos/runtime/http/{jwt_auth_middleware.py,cell_router_middleware.py,authz_middleware.py,fail_closed_middleware.py,dev_identity_middleware.py,security.py}`, `src/polisyos/runtime/http/routes/auth.py`, `src/polisyos/core/security/settings.py`
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_auth_api.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_api_maturity.py`
- `uv run pytest -q tests/unit/core/security/test_auth_middlewares.py tests/unit/core/security/test_router.py tests/unit/core/security/test_tenant_context.py`

This page is manually maintained from the runtime HTTP security chain. It
describes current request authentication, tenant routing, cell binding, and
authorization behavior for the `/api/v1` runtime surface.

## Middleware Order

When runtime security middlewares are enabled, `create_runtime_api_app()` keeps
the request chain in this exact order:

1. `JWTAuthMiddleware`
2. `CellRouterMiddleware`
3. `AuthzMiddleware`

`_assert_runtime_security_middleware_order()` treats any reordering as a boot
error.

Public-path bypasses are limited to `/health`, `/ready`, `/metrics`, and
`/auth/callback`.

## Authentication Modes

### Security middlewares enabled

- Non-public HTTP routes require `Authorization: Bearer <token>`.
- Missing or empty bearer tokens return `401` with code
  `missing_bearer_token`.

- The configured identity provider resolves `UserIdentityClaims`.
- If `POLISYOS_CELL_ID` is set, JWT validation also enforces that cell binding.
- MFA failures return `403 mfa_required`.
- Token validation failures return `401 invalid_token`.
- The resolved claims are projected into `request.state.user_claims`,
  `request.state.authenticated_tenant_id`, and `request.state.access_scope`.

### Security middlewares disabled

- `FailClosedAccessScopeMiddleware` still denies non-public requests without an
  access scope.

- `DevelopmentFixtureIdentityMiddleware` is installed only when fixture
  identity is explicitly enabled through
  `POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY` or the app factory override.

- The fixture identity is fixed to tenant
  `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`, cell `cell-a`, role `analyst`, and
  user `fixture-analyst`.

## Tenant and Cell Routing

`CellRouterMiddleware` resolves the effective tenant and cell before route
handlers run.

- The effective tenant comes from JWT claims first, then from `X-Tenant-ID`
  when claims are absent.

- If both JWT claims and `X-Tenant-ID` are present, they must match or the
  request fails with `403 tenant_binding_mismatch`.

- Missing tenant routing metadata fails closed with
  `401 missing_tenant_id`.

- Unknown or unregistered tenants fail with `403 tenant_not_found`.
- If the JWT claims are bound to a different cell than the routed tenant, the
  request fails with `403 cell_binding_mismatch`.

- Successful routing sets `request.state.tenant_id`, `cell_id`, and
  `cell_tier`, enters `tenant_scope(...)`, and emits `X-Cell-ID` and
  `X-Cell-Tier` response headers.

## Access Scope and Authorization

- `JWTAuthMiddleware` derives `AccessScope` from authenticated user claims.
- `AuthzMiddleware` consumes that scope plus resource metadata attached by route
  dependencies and services.

- Requests without any access scope fail closed with
  `403 missing_access_scope` when the authz middleware is active.

- OPA decisions are evaluated per request through `AuthzInput.for_http_request(...)`.
- Denied OPA decisions return `403 authorization_denied` when enforce mode is
  active.

- If shadow mode is enabled, the request is allowed but the response carries
  `X-PolicyOS-Authz-Shadow-Deny: true`.

## Delegation and Service Identity

`AuthzMiddleware` also supports delegation tokens for service-to-service calls.

- Delegation tokens ride in `x-policyos-context` by default.
- The peer SPIFFE identity is read from `l5d-client-id` by default.
- Delegation is denied when the verifier is not configured, the peer identity
  is missing, the peer is untrusted, or
  `POLISYOS_SERVICE_SPIFFE_ID` is unset.

- Verified delegation claims replace the request access scope before OPA
  evaluation.

## `/api/v1/auth/me`

`GET /api/v1/auth/me` returns the frontend-facing principal envelope.

- With fixture identity enabled, it returns the explicit dev fixture principal.
- With JWT security enabled, it reflects the resolved authenticated claims.
- Roles are mapped to runtime permissions in `routes/auth.py`.
- `feature_overrides.enableReviewCollaboration` is derived from the
  `runs.review` permission.

- Without a usable access scope or claims, the endpoint fails closed rather
  than manufacturing an identity.

## Route-Level Tenant Guards

Authentication and authz happen before route logic, but runtime services still
re-check tenant scoping at the resource boundary.

- Run reads can return `403 run_tenant_mismatch`.
- Artifact reads can return `403 artifact_tenant_mismatch`.
- Unscoped artifacts can return `403 artifact_tenant_unscoped`.
- Cross-tenant debug compare requires an explicit capability and otherwise
  returns `403 cross_tenant_compare_forbidden`.

- Cross-tenant violations raised deeper in Core map to
  `403 cross_tenant_access_denied`.

## Dependency Failure Semantics

- OPA timeouts return `504 authz_dependency_timeout`.
- Open OPA breaker state or unreachable authz dependencies return
  `503 authz_dependency_unavailable`.

- When runtime security is required by the execution profile, app bootstrap
  fails if the identity provider, cell registry, or OPA client is missing.
