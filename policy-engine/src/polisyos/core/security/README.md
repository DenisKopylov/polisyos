# Security (`polisyos.core.security`)

`core.security` is the shared zero-trust, multi-tenant runtime layer for PolicyOS. It covers cell
routing, identity/authz, delegation, chained audit, TEE, SBOM, SLSA, and quota enforcement.

## Role in System

- **Depends on:** `core.cache` for fast local memoization and shared runtime settings.
- **Used by:** `runtime/http`, audit export tooling, and any execution path that needs tenant isolation or attestation.
- **Boundary function:** keeps security primitives centralized so each product layer does not reimplement them.

## Key Concepts

- **Tenant and cell routing** - `cell.py`, `router.py`, and `tenant_context.py` keep requests scoped correctly.
- **Identity and authz** - `identity.py`, `access_scope.py`, `delegation.py`, and `authz.py` model request trust and authorization.
- **Audit chain** - chained logs, sinks, and verifiers provide tamper-evident records.
- **Chronology full-prefix verification** - `full_prefix.py` incrementally recomputes the exact
  domain-separated native prefix. It has only `verified`/`rejected` outcomes and cannot infer
  acceptance, currentness, completeness, or a native authority head.
- **TEE and attestation** - `tee.py` and `tee_middleware.py` gate sensitive execution paths.
- **SBOM and SLSA** - supply-chain checks and attestation clients enforce release discipline.
- **Quota enforcement** - `quota_registry.py` and `quota_enforcer.py` keep tenant/resource usage bounded.

## Public API

- routing/tenant: `CellRegistry`, `resolve_routing`, `tenant_scope`
- identity/authz: `AccessScope`, `OPAClient`
- delegation: delegation token helpers in `delegation.py`
- audit: audit sink/verifier helpers in `audit_sink.py` and `audit_verifier.py`
- chronology: `FullPrefixVerifier` and `build_full_prefix_bundle`, re-exported only through the
  admitted `polisyos.core` root public facade
- attestation: TEE and SBOM/SLSA helpers in `tee.py`, `sbom.py`, and `slsa/`

## Current State

- Last updated: 2026-08-24
- The package tree now includes `namespace.py`, `quota_enforcer.py`, and `quota_registry.py` alongside the existing zero-trust primitives.
- `runtime/http` remains the main consumer of the security middleware chain.
