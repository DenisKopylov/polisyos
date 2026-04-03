# Core (`polisyos.core`)

`polisyos.core` is the shared infrastructure layer for the rest of PolicyOS. It hosts the
cross-module ABI, content-addressable storage, component discovery/bootstrap, telemetry,
security, registry building, and a few small runtime utilities that many domains reuse.

`polisyos.ir` remains the canonical schema/ref layer. `core` depends on `ir`, but not the other
way around.

## Role in System

- **Depends on:** `polisyos.ir` for canonical refs and schema-shaped payloads.
- **Used by:** `fabric`, `foundry`, `scientist`, `lex`, `runtime`, `scholar`, and bootstrap tooling.
- **Boundary function:** keeps shared infrastructure out of domain packages so the ABI stays stable.

## Key Concepts

- **Contracts first** - `core.contracts` defines the typed ABI surface for runtime, control, and artifact refs.
- **CAS and provenance** - `core.artifacts`, `core.trace`, and `core.audit` keep runs reproducible and inspectable.
- **Plugin bootstrap** - `core.components`, `core.discovery`, and `core.registry` wire component discovery into runtime registries.
- **NFR primitives** - `core.observability`, `core.security`, `core.resilience`, and `core.pipeline` provide common runtime guarantees.
- **LLM wrapper** - `core.llm` gives a traced, metered, retry-aware client facade for higher-level modules.
- **Validation profiles** - `core.governance` centralizes shared pass selection and policy strictness.

## Public API

`polisyos.core` exports 15 lazy submodules:
`artifacts`, `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`,
`evaluation`, `errors`, `llm`, `observability`, `pipeline`, `registry`, `resilience`, `run`.

Direct subpackages remain part of the package surface:
`audit`, `compiler`, `governance`, `security`, `trace`.

Reference docs:
- [artifacts/README.md](artifacts/README.md)
- [audit/README.md](audit/README.md)
- [cache/README.md](cache/README.md)
- [components/README.md](components/README.md)
- [contracts/README.md](contracts/README.md)
- [governance/README.md](governance/README.md)
- [llm/README.md](llm/README.md)
- [observability/README.md](observability/README.md)
- [registry/README.md](registry/README.md)
- [security/README.md](security/README.md)

## Where to Start

- Public facade / compatibility: `src/polisyos/core/__init__.py` and `docs/reference/public-surface.md`
- Contracts / typed ABI: `src/polisyos/core/contracts/`
- Registry/bootstrap wiring: `src/polisyos/core/registry/` and `src/polisyos/core/components/`
- Generated / contract-adjacent artifacts: `docs/reference/generated-artifacts.md`

## Current State

- Last updated: 2026-04-03
- Lazy exports: 15 submodules
- Recent ABI drift: `core.contracts.scientist` gained `CalibrationValidationBundleRef`, and `core.governance.ValidationProfile` now includes `strategic_response` in `mvp` and `strict`.
