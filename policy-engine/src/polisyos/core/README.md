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

- `src/polisyos/core/canon/README.md` for Core's canonical codec, direct bounded
  encoder, and version/reader limitations.

- `src/polisyos/core/components/README.md` and
  `src/polisyos/core/registry/README.md` for discovery/bootstrap wiring.

- `src/polisyos/core/security/README.md` for tenant isolation, authz, quotas,
  and audit surfaces.

- `src/polisyos/core/observability/README.md` for metrics, tracing, and
  propagation hooks.

- `src/polisyos/core/audit/README.md` for audit report assembly and verifier
  tooling.

## Public API

- Read-only local artifact access: `polisyos.core.artifacts.ArtifactReader` and
  `FileSystemCAS.open_existing_read_only` expose only verified reads over an already-existing
  CAS. See [the read-only CAS contract](artifacts/README.md#read-only-local-cas-access); this is
  not an HTTP endpoint or an authority claim.

- Supported package entrypoint: `polisyos.core`
- Narrow worker-lifecycle API leaf: `polisyos.core.run.worker_lifecycle`.
  This does not make `polisyos.core.run` or `RunContext` a supported package API.
- Lazy facade exports from `src/polisyos/core/__init__.py`: `artifacts`,
  `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`,
  `evaluation`, `errors`, `llm`, `observability`, `pipeline`, `registry`,
  `resilience`, `run`

- Operationally important subpackages for local navigation: `audit`,
  `governance`, `security`, and `trace`. Treat them as implementation surfaces
  unless you also update the generated
  [Public Surface](../../../docs/reference/public-surface.md).

`run` is available as a lazy attribute of `polisyos.core`, but the supported
surface is limited to the explicit `polisyos.core.run.worker_lifecycle` leaf.
The `polisyos.core.run` package and `RunContext` remain internal; lazy
availability alone does not make a package or class public. `WarningRecord`
remains the existing supported public model from `polisyos.core.artifacts`.

Worker dispatch staging and parent receipt admission belong to
`polisyos.core.run.worker_lifecycle.WorkerLifecycleCapability`. It accepts only
the exact active Core parent context, and worker receipts return through Core's
existing `RunContext.merge_worker_events` writer. The worker view refuses
finalization and suspension and hides ordinary lifecycle-owner attributes; it
is a Python API boundary, not a process sandbox.

Internal run trace events: `polisyos.core.run.RunContext.emit` accepts optional
typed `WarningRecord` values and stores them in the existing trace `warnings`
collection. Omitting the argument preserves the existing empty-list trace
output; warning transport does not change metric, lifecycle, or authority
semantics. The process that acquired a run's active lease owns `finalize()` and
`suspend_for_resume()`; a forked child can continue to stage ordinary events and
inputs/outputs, but cannot terminalize or release its inherited parent lease.

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
- The basename `discovery` is scoped: `polisyos.core.discovery` owns plugin and
  entry-point primitives, while Scientist causal graph discovery lives under
  `polisyos.scientist.methods.discovery`. Keep imports package-qualified; this
  namesake does not relax cross-package import boundaries.

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
- [Run](run/README.md)
- [Security](security/README.md)

- Last updated: 2026-05-06

Epoch deployment composition imports the existing
`FileSystemSignedArtifactEvidenceRepository` through this lazy Core facade.
The repository verifies exact persisted bytes; it does not appoint a signer or
replace independent origin/profile admission. Exact appointment verification
helpers are available through the existing `core.security` facade.

## Selected canonical-profile reads

Core semantic artifact readers resolve the exact selected manifest sidecar and
read its raw profile before consuming JSON bytes. A present malformed, partial,
unsupported, or byte-nonconformant profile is a typed refusal; it is never
replaced with reader defaults. The default Core semantic read refuses absence.
A deliberate candidate-only compatibility call yields
`profile_absent_unqualified_candidate`; `.value` then refuses, and no source-qualified
historical eligibility is established. Core uses its own canonical codec and typed-tag
set through `core.artifacts.canonical_profile`; IR's separate profile contract
and exception identity remain unchanged. This is reader conformance, not signer
appointment or producer attestation.

### Raw manifest inspection for canonical profile readers

First-party artifact stores expose the optional `RawManifestBytesReader` capability. It
returns the exact selected sidecar bytes behind the storage owner/view boundary without
constructing `ArtifactManifest`; a shared semantic reader then strictly parses the
profile, resolves the typed selected manifest, and consumes the same selected payload.
Stores without this capability cannot prove profile absence and fail closed for semantic
JSON reads. Existing `get_manifest_bytes` behavior remains unchanged for signature and
compatibility callers.

## Exact E02 cross-package routes

Core governance and LLM entrypoints are supported as narrow owner facades. The `core.artifacts`, `core.contracts`, and `core.security` facades expose only the exact DTOs, protocol, and wire constants required by typed consumers. Their exports preserve the defining object; public route availability does not grant caller authority or producer attestation. `Common.canonical_profile` remains storage-agnostic, while Core canonical tags and refusal identity stay Core-owned.

The `core.contracts` facade also exposes the existing `RegisteredSQLAdmissionBinding`,
`RegisteredSQLUseContract`, and `data_snapshot_manifest_inputs_match` definitions to
the bounded execution-input owner. They preserve the original objects and do not
assert external rights, SQL freshness, or producer authority.

## Run-owner invocation basis

New run-owner snapshots use schema `1.0.2` and append an optional selected-profile
tail for engine invocation records. Each start record binds one attempt to the
full selected `WorkflowSpec` and `ExperimentState` refs; its completion record
binds the returned status, outcome-state ref, and output refs. Snapshot schema
`1.0.1` remains a separate read shape with its original bytes and hash, and a
history without an invocation tail returns no positive source binding.

`RunContext.read_runtime_invocation_attempts()` reads the current trace and
owner chain again from CAS. Ordinary `RunContext.emit()` events cannot advance
that chain. This is an execution-input record, not a sandbox or a claim about
who authored the input before dispatch; callers without the owner-linked basis
remain `not_established` for source origin.
