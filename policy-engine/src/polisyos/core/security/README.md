# core.security

Tenant isolation primitives for cell-based multi-tenant deployments.

## Modules

- `cell.py` — immutable `CellSpec` / `TenantSpec` / `CellAssignment` models
- `registry.py` — in-memory tenant-to-cell registry with O(1) resolution
- `tenant_context.py` — contextvars + `tenant_scope()` runtime propagation
- `db_backend.py` — `DatabaseBackend` protocol with DuckDB/Postgres adapters
- `router.py` — framework-agnostic routing helpers for request tenant resolution
- `settings.py` — environment-driven settings for tenant-isolation behavior
- `identity.py` — user/service identity models and JWT/SPIFFE provider
- `access_scope.py` — immutable per-request access scope
- `delegation.py` — signed delegation token for inter-service user context
- `authz.py` — async OPA authorization client with fail-closed semantics

## Design goals

- fail-closed defaults for shared-cell PostgreSQL access
- compatibility with existing DuckDB-based workflows
- additive migration path (wrap, don't replace)
