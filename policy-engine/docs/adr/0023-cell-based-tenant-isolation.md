# ADR-0023: Cell-Based Tenant Isolation Foundation

## Status

Accepted

## Date

2026-02-08

## Context

PolicyOS needs tenant isolation suitable for government workloads. Existing data access is DuckDB-centric and has no built-in tenant boundary enforcement.

## Decision

1. Introduce a `core/security` package with immutable `CellSpec`/`TenantSpec`, tenant context propagation, and backend abstractions.
2. Use a dual database strategy:

   - Shared cells: PostgreSQL with enforced RLS per tenant.
   - Dedicated/local simulation paths: DuckDB compatibility backend.
3. Introduce a tenant-aware HTTP middleware (`CellRouterMiddleware`) for request-to-cell resolution.
4. Keep backward compatibility via additive changes and feature-flag-controlled rollout.
5. Add Helm chart primitives for namespace-level isolation and default-deny networking.

## Consequences

- Stronger blast-radius isolation for multi-tenant deployments.
- Added operational complexity (PostgreSQL migrations, routing layer, cell registry lifecycle).
- Lower regression risk due to wrap-not-replace migration strategy.

## Verification

- Unit tests for cell models, registry, and tenant scope.
- Integration tests for router behavior and PostgreSQL RLS isolation.
- Prometheus alerts for cross-tenant incidents and routing failures.
