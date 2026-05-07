# Core (`polisyos.core`)

## Purpose

`polisyos.core` is the shared infrastructure layer for the rest of PolicyOS.
It owns the cross-module ABI, content-addressable storage, component
discovery/bootstrap, registry assembly, observability, and security primitives
that higher-level subsystems reuse.

`polisyos.ir` remains the canonical schema/reference layer. `polisyos.core`
depends on `polisyos.ir`, but not the other way around.

## Where to Start

- `src/polisyos/core/__init__.py` for the curated lazy facade.
- `src/polisyos/core/contracts/README.md` for the typed ABI shared across
  runtime and domain subsystems.

- `src/polisyos/core/artifacts/README.md` for CAS, manifest, signing, and
  provenance storage.

- `src/polisyos/core/components/README.md` and
  `src/polisyos/core/registry/README.md` for discovery/bootstrap wiring.

- `src/polisyos/core/security/README.md` for tenant isolation, authz, quotas,
  and audit surfaces.

- `src/polisyos/core/observability/README.md` for metrics, tracing, and
  propagation hooks.

- `src/polisyos/core/audit/README.md` for audit report assembly and verifier
  tooling.

## Public API

- Supported package entrypoint: `polisyos.core`
- Lazy facade exports from `src/polisyos/core/__init__.py`: `artifacts`,
  `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`,
  `evaluation`, `errors`, `llm`, `observability`, `pipeline`, `registry`,
  `resilience`, `run`

- Operationally important subpackages for local navigation: `audit`,
  `governance`, `security`, and `trace`. Treat them as implementation surfaces
  unless you also update the generated
  [Public Surface](../../../docs/reference/public-surface.md).

## Internal Layout

- `__init__.py` owns the public lazy facade.
- `contracts/`, `artifacts/`, `components/`, `registry/`, `security/`, and
  `observability/` are the main shared contract owners.
- `audit/`, `cache/`, `governance/`, `llm/`, and migration helpers remain
  implementation surfaces unless exposed by the facade and public-surface
  reference.
- Cross-package component discovery belongs in `components/` and `registry/`;
  do not create package-specific registries in Core without an architecture
  contract.

## Extension Points

`polisyos.core` provides component/bootstrap primitives but is not a user-facing
plugin host. Public extension hosts are declared in
[architecture/extension_points.toml](../../../architecture/extension_points.toml)
and should consume Core through documented contracts only.

## Depends on / depended on by

Depends on: `polisyos.ir` for canonical refs and schema-shaped payloads,
`polisyos.common` for shared helpers, and optional backend/runtime dependencies
pulled in by specific subpackages.

Depended on by: `polisyos.runtime`, `polisyos.fabric`, `polisyos.foundry`,
`polisyos.scientist`, `polisyos.lex`, `polisyos.scholar`, plus bootstrap and
release tooling.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.core as core; print(sorted(core.__all__))"`

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.core.contracts.runtime as runtime_contracts; import polisyos.core.registry as registry; print(runtime_contracts.__name__, registry.__name__)"`

## Tests

Run commands from the repository root `policy-engine/`.

- Smoke-tested: `uv run pytest -q tests/repo_quality/architecture/test_public_api_facades.py`
- Smoke-tested:
  `uv run pytest -q tests/unit/core/security/test_auth_middlewares.py tests/unit/core/security/test_router.py tests/unit/core/security/test_tenant_context.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/core/artifacts/test_async_store.py tests/unit/core/artifacts/test_storage_protocol_boundaries.py`

- Conceptual release gate: `uv run python tools/devx/workspace/core_runtime_mypy.py`
- Conceptual release gate:
  `uv run python tools/devx/workspace/core_runtime_basedpyright.py`

## Operability Links

- [Core component SLO](../../../ops/components/core/slo.yaml)
- [Core component runbooks](../../../ops/components/core/runbooks.md)
- [Security and compliance reference](../../../docs/reference/security-compliance.md)
- [CAS/OPA outage runbook](../../../docs/runbooks/cas-opa-outage.md)
- [Artifact signing/SBOM failure runbook](../../../docs/runbooks/artifact-signing-sbom-failure.md)

## Known Shims/Deprecations

There are no active package-local shims for `polisyos.core` in
[architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
New public Core exports must update the facade, public-surface reference, and
component/bootstrap compatibility checks together.

## Reference docs

- [Public Surface](../../../docs/reference/public-surface.md)
- [Security Model](../../../docs/explanation/security-model.md)
- [Security and Compliance](../../../docs/reference/security-compliance.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Artifacts](artifacts/README.md)
- [Audit](audit/README.md)
- [Cache](cache/README.md)
- [Components](components/README.md)
- [Contracts](contracts/README.md)
- [Governance](governance/README.md)
- [LLM](llm/README.md)
- [Observability](observability/README.md)
- [Registry](registry/README.md)
- [Security](security/README.md)

- Last updated: 2026-05-06
