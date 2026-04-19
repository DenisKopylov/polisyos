# Common (`polisyos.common`)

## Purpose

`polisyos.common` is the lowest reusable layer in the PolicyOS dependency
graph. It owns side-effect-sensitive bootstrap helpers, logging, async
bridging, canonical JSON serialization, UTC time utilities, and package-local
migration primitives. Keep domain logic out of this package.

## Where to Start

- `src/polisyos/common/__init__.py` for the lazy facade contract.
- `src/polisyos/common/serialization.py` for canonical JSON helpers and
  round-trip guarantees.
- `src/polisyos/common/timestamps.py` for aware-UTC parsing and formatting.
- `src/polisyos/common/async_tools.py` for sync/async bridge utilities and the
  shared executor.
- `src/polisyos/common/config.py` and `src/polisyos/common/jax_env.py` for
  early-process bootstrap behavior.
- `src/polisyos/common/migrations/README.md` for package-local artifact
  migrations.
- `src/polisyos/common/env_parsing.py` if you are working on bootstrap
  internals; it is intentionally not part of the exported facade.

## Public entrypoints

- Supported package entrypoint: `polisyos.common`
- Lazy facade exports from `src/polisyos/common/__init__.py`:
  `async_tools`, `config`, `jax_env`, `logger`, `migrations`,
  `serialization`, `timestamps`
- Internal-but-frequently-touched helper: `env_parsing.py`; do not treat it as
  stable public surface without updating the facade and
  [Public Surface](../../../docs/reference/public-surface.md).

## Depends on / depended on by

Depends on: Python stdlib plus a small set of optional bootstrap/runtime
dependencies pulled in by individual helper modules.

Depended on by: `polisyos.core`, `polisyos.runtime`, `polisyos.fabric`,
`polisyos.foundry`, `polisyos.scientist`, `polisyos.lex`,
`polisyos.scholar`, and workspace tooling.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.common as common; print(sorted(common.__all__))"`
- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION; print(MANIFEST_CURRENT_VERSION)"`

## Test/verification commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `uv run pytest -q tests/common/test_async_tools.py tests/common/test_config_bootstrap.py tests/common/test_fast_json_serialization.py tests/common/test_serialization_properties.py tests/common/test_timestamps.py tests/common/test_migrations_purity.py`
- Conceptual release gate: `uv run python tools/workspace/core_runtime_mypy.py`
- Conceptual release gate:
  `uv run python tools/workspace/core_runtime_basedpyright.py`

## Reference docs

- [Public Surface](../../../docs/reference/public-surface.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Core / Common / Runtime Audit Remediation Plan](../../../docs/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md)
- [Common migrations](migrations/README.md)

- Last updated: 2026-04-17
