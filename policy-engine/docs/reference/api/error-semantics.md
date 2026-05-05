# Runtime API Error Semantics

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/errors.py`, `src/polisyos/runtime/http/{authz_middleware.py,jwt_auth_middleware.py,cell_router_middleware.py,mutation_policy.py}`, `src/polisyos/core/errors.py`, and `src/polisyos/core/security/exceptions.py`
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_error_semantics.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
- `uv run pytest -q tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`

This page is manually maintained from the runtime exception handlers and the
middleware/route helpers that emit typed `application/problem+json` responses.

## Problem Envelope

Runtime errors use `RuntimeApiProblem` and media type
`application/problem+json`.

| Field                    | Meaning                                                  |
| ------------------------ | -------------------------------------------------------- |
| `type`                   | Problem type URI; defaults by HTTP status                |
| `title`                  | Human-readable summary                                   |
| `status` / `status_code` | HTTP status code                                         |
| `detail`                 | Client-safe diagnostic text                              |
| `code`                   | Stable machine-oriented code                             |
| `error`                  | Short error family label used by middleware/helper paths |
| `instance`               | Request path                                             |
| `request_id`             | Correlation identifier when available                    |

Handlers may also append `context` with sanitized request/exception metadata.

## Sanitization Rules

- Problem details are scrubbed before leaving the process.
- S3 URLs, AWS ARNs, bucket/region/endpoint assignments, credentials, tokens,
  passwords, and access-key patterns are redacted.

- `detail` is capped at 2000 characters.
- `context` values are sanitized and capped at 256 characters each.

## Context Extension

When present, `context` can contain:

- `request_id`
- `tenant`
- `run_id`
- `artifact_id`
- `dependency`
- `retry_state`
- `stage`
- `category`

These keys are populated from request state, path/query params, and typed
exception fields.

## Direct Runtime Helpers

`errors.py` exposes helper constructors for route/service code:

| Helper                      | Status | `error`                     | Default `code`         |
| --------------------------- | ------ | --------------------------- | ---------------------- |
| `bad_request(...)`          | `400`  | `bad_request`               | `bad_request`          |
| `unauthorized(...)`         | `401`  | `unauthorized`              | `unauthorized`         |
| `forbidden(...)`            | `403`  | `forbidden`                 | `forbidden`            |
| `not_found(...)`            | `404`  | `not_found`                 | `not_found`            |
| `not_acceptable(...)`       | `406`  | `not_acceptable`            | `not_acceptable`       |
| `rate_limited(...)`         | `429`  | `rate_limited`              | `rate_limited`         |
| `unprocessable_entity(...)` | `422`  | `request_validation_failed` | `unprocessable_entity` |
| `service_unavailable(...)`  | `503`  | `service_unavailable`       | `service_unavailable`  |
| `gateway_timeout(...)`      | `504`  | `gateway_timeout`           | `gateway_timeout`      |
| `internal_error(...)`       | `500`  | `internal_error`            | `internal_error`       |

## Dependency Guard Errors

`RuntimeDependencyError` is used for guarded CAS/control-store paths.

| Exception                           | Status | Typical code shape         |
| ----------------------------------- | ------ | -------------------------- |
| `RuntimeDependencyUnavailableError` | `503`  | `<dependency>_unavailable` |
| `RuntimeDependencyTimeoutError`     | `504`  | `<dependency>_timeout`     |

Observed runtime examples include:

- `content_addressed_storage_timeout`
- `control_plane_store_timeout`
- `control_plane_store_unavailable`
- `authz_dependency_timeout`
- `authz_dependency_unavailable`

## Core Exception Mapping

`install_exception_handlers()` maps typed core/runtime exceptions into problem
responses as follows:

| Exception                                           | Status | Code                                             | Error label           |
| --------------------------------------------------- | ------ | ------------------------------------------------ | --------------------- |
| `CrossTenantAccessError`                            | `403`  | `cross_tenant_access_denied`                     | `forbidden`           |
| `AuthorizationDeniedError`                          | `403`  | `authorization_denied` or exception code         | `forbidden`           |
| `AuthorizationError`                                | `403`  | `authorization_error` or exception code          | `forbidden`           |
| `IdentityNotAvailableError`                         | `503`  | `identity_unavailable` or exception code         | `service_unavailable` |
| `IdentityVerificationError`, `TokenValidationError` | `401`  | `identity_verification_failed` or exception code | `unauthorized`        |
| `TenantIsolationError`                              | `403`  | `tenant_isolation_denied` or exception code      | `forbidden`           |
| `ExecutionProfileError`                             | `400`  | exception code                                   | `bad_request`         |
| `PolicyFlagForbiddenError`                          | `403`  | exception code or `policy_flag_forbidden`        | `forbidden`           |
| `PolicyOSError(category=TRANSIENT)`                 | `503`  | `exc.code` or `policyos_transient`               | `service_unavailable` |
| `PolicyOSError(category=VALIDATION)`                | `400`  | `exc.code` or `policyos_validation`              | `bad_request`         |
| other `PolicyOSError`                               | `500`  | `exc.code` or `policyos_<category>`              | `internal_error`      |

## Framework Exception Mapping

| Exception                        | Status             | Code                        |
| -------------------------------- | ------------------ | --------------------------- |
| `KeyError`                       | `404`              | `not_found`                 |
| `ValueError`                     | `400`              | `bad_request`               |
| FastAPI `RequestValidationError` | `422`              | `request_validation_failed` |
| FastAPI `HTTPException(401)`     | `401`              | `unauthorized`              |
| FastAPI `HTTPException(403)`     | `403`              | `forbidden`                 |
| FastAPI `HTTPException(404)`     | `404`              | `not_found`                 |
| other FastAPI `HTTPException`    | passthrough status | `http_error`                |

## Middleware-Specific Codes

Not every runtime error flows through the core exception mapper. Several
middlewares emit typed problems directly:

- JWT auth: `missing_bearer_token`, `invalid_token`, `mfa_required`,
  `tenant_binding_mismatch`

- Tenant/cell routing: `missing_tenant_id`, `tenant_not_found`,
  `cell_binding_mismatch`, `cross_tenant_access`

- Fail-closed perimeter: `missing_access_scope`
- Mutation protection: `idempotency_key_reused`,
  `idempotency_request_in_progress`, `rate_limit_exceeded`

These direct codes are part of the current runtime contract and should be used
as the client-facing source of truth, not inferred from generic status codes.
