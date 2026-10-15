# CAS and Storage Reference

Historical freshness marker: `2026-04-17`; this is not a current verification date.
Owner: `@runtime-owners`
Source of truth: `src/polisyos/core/artifacts/{protocol.py,store.py,backends/config.py}`, `src/polisyos/runtime/http/{dependencies.py,resilience.py}`, `src/polisyos/fabric/storage/tenant_cas.py`, and ADRs `0098`/`0103`
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; source inspection only. The validation commands below were not run, and no CAS backend or environment was inspected.
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_runtime_api_write_path_hardening.py tests/unit/runtime/http/test_api_maturity.py`
- `uv run pytest -q tests/unit/core/artifacts/backends/test_config.py tests/unit/fabric/test_storage_port.py tests/unit/fabric/test_duckdb_storage_access_control.py`

This page is manually maintained from the Core CAS contracts and runtime
binding code at the reviewed source snapshot. It describes repository behavior,
not the state or health of a live storage backend.

## Contract Boundary

Runtime-facing code depends on the backend-neutral `ArtifactStore` contract:

- `has(artifact_id)`
- `get_bytes(artifact_id)`
- `get_manifest(artifact_id)`
- `put_bytes(data, opts)`
- `put_json(obj, opts, canon_spec=None)`
- `verify(artifact_id)`
- `iter_artifact_ids()`

Async callers use the matching `AsyncArtifactStore` sibling contract.

The contract intentionally excludes backend-specific helpers such as raw root
paths, bulk import/export details, or signing internals unless callers opt into
those concrete extensions.

## Backend Selection

`ArtifactStoreConfig.from_env()` resolves the declarative CAS backend.

| Variable                       | Default        | Meaning                                                                |
| ------------------------------ | -------------- | ---------------------------------------------------------------------- |
| `POLISYOS_CAS_BACKEND`         | `filesystem`   | Backend selector: `filesystem`, `s3`, `gcs`, `cached_s3`, `cached_gcs` |
| `POLISYOS_CAS_ROOT`            | unset          | Filesystem CAS root; defaults to `.polisyos/cas` when omitted          |
| `POLISYOS_CAS_BUCKET`          | unset          | Required for cloud backends                                            |
| `POLISYOS_CAS_PREFIX`          | `polisyos-cas` | Object prefix for cloud backends                                       |
| `POLISYOS_CAS_REGION`          | `us-east-1`    | Region for S3-backed stores                                            |
| `POLISYOS_CAS_LOCAL_CACHE_DIR` | unset          | Local cache root for cached/object-backed stores                       |

Factory behavior:

- `filesystem` builds `FileSystemCAS`
- `s3` and `gcs` build direct object-store adapters
- `cached_s3` and `cached_gcs` wrap a remote object store with a local
  filesystem cache rooted at `.polisyos/cas/_cache` by default

## Runtime Binding

`build_runtime_api_context()` is the runtime HTTP binding point.

- It starts from `ArtifactStoreConfig.from_env()`.
- It then overrides `root` with the app-level `cas_root` argument before the
  store is built.

- The sync store is wrapped with `guard_runtime_cas(...)` before services see
  it.

- An async sibling is created through `build_async_artifact_store(...)`.
- `core_runs_root` is application-owned runtime state and should live under
  `.polisyos/runs` when the app-level CAS root is `.polisyos/cas`.

That means the runtime app factory, not raw process env alone, decides the
effective CAS root for one app instance.

## Filesystem CAS Layout

`FileSystemCAS` is the canonical local implementation. Its stable on-disk ABI
is:

- `<root>/artifacts/sha256/ab/cd/<hex>.blob`
- `<root>/artifacts/sha256/ab/cd/<hex>.manifest.json`
- `<root>/artifacts/sha256/ab/cd/<hex>.sig` for optional detached signatures

Semantics at the reviewed source revision:

- `put_bytes()` and `put_json()` derive the artifact ID from payload bytes.
- Every write persists a manifest sidecar.
- `put_json()` canonicalizes JSON before hashing/writing.
- `get_manifest()` validates manifest identity.
- `get_bytes()` reads the blob and verifies it against the manifest.
- Optional signing is controlled by `SigningConfig.from_env()` and may sign on
  write.

- `artifact_store_config()` exports a rebuildable declarative config for the
  live store instance.

## Tenant-Scoped CAS

`TenantScopedCAS` provides a compatibility wrapper for per-tenant filesystem
namespaces.

- Tenant roots resolve to `<root>/tenants/<tenant_id>`.
- Tenant IDs are validated before a scoped root is created.
- Storage usage is reconciled from regular files in `artifacts/sha256` and
  admitted from the exact absent blob, manifest-view, and signature members
  before publication. Imports admit their complete member set once before the
  first final member is written; an exact existing no-op has zero storage delta.
- A tenant-root lock serializes independent wrapper instances while each writer
  recomputes the materialized baseline. Staging files and ownership transaction
  journals are control state and are outside this storage-byte measure.
- `put_bytes`, canonical `put_json`, import, and sign-on-put use the same
  admission boundary. The public artifact-store protocol and on-disk member ABI
  stay unchanged.
- `resolve_cas_store(...)` returns the shared store when `tenant_id` is absent
  and a `TenantScopedCAS` wrapper when `tenant_id` is provided.

- `infer_tenant_id_from_cas_root(...)` can recover a tenant ID from an already
  scoped CAS path.

## Runtime Guardrails

Runtime HTTP paths do not call blocking CAS operations directly. They run
behind `BlockingDependencyGuard`.

| Guard family                                     | Default | Notes                                             |
| ------------------------------------------------ | ------- | ------------------------------------------------- |
| `POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS`           | `1.5`   | Max blocking CAS call duration before `504`       |
| `POLISYOS_RUNTIME_CAS_EXECUTOR_MAX_WORKERS`      | `4`     | Worker budget when a dedicated executor is needed |
| `POLISYOS_RUNTIME_CAS_BREAKER_FAILURE_THRESHOLD` | `3`     | Opens the CAS breaker after repeated failures     |
| `POLISYOS_RUNTIME_CAS_BREAKER_TIMEOUT_SECONDS`   | `30`    | Breaker open-state timeout                        |
| `POLISYOS_RUNTIME_CAS_BREAKER_WINDOW_SECONDS`    | `60`    | Failure accounting window                         |

Runtime behavior:

- timeouts surface as `504 content_addressed_storage_timeout`
- unavailable dependency states surface as
  `503 content_addressed_storage_unavailable`

- `FileNotFoundError` is not treated as dependency unavailability; it remains a
  normal missing-artifact path

## Related References

- [Artifact Inspection API](../api/artifacts.md)
- [Runtime Auth and Tenant Model](../api/auth-tenant-model.md)
- [Configuration Reference](../configuration.md)
- [ADR-0098: CAS Abstraction Boundary](../../adr/0098-cas-abstraction-boundary.md)
- [ADR-0103: Async CAS Adapter Roadmap](../../adr/0103-async-cas-adapter-roadmap.md)

## Transfer import disposition

The legacy `imported_artifacts` field counts unique artifact IDs recognized from received CAS members. It does not mean those IDs were verified or published. The typed import report separately carries received IDs, content-profile-canonical published and reused views, successful integrity-verifier results, and whether verification was requested. A default selector and an explicit alias of the same manifest profile normalize to one identity in these added view lists; `imported_refs` retains its compatibility selectors.

Published views are derived from manifest-stage entries in the durable owner transaction intent that completed, including an exact recovery retry. They do not mean this call wrote the member. Reused views are exact admitted existing views or completed transaction views without a manifest stage. The replay CLI exposes the same report in every JSON and text route. No disposition field asserts signature trust, external custody, provenance authority, or production currentness.
