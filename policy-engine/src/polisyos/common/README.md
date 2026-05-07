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

## Public API

- Supported package entrypoint: `polisyos.common`
- Lazy facade exports from `src/polisyos/common/__init__.py`:
  `async_tools`, `config`, `jax_env`, `logger`, `migrations`,
  `serialization`, `timestamps`

- Internal-but-frequently-touched helper: `env_parsing.py`; do not treat it as
  stable public surface without updating the facade and
  [Public Surface](../../../docs/reference/public-surface.md).

## Internal Layout

- `__init__.py` owns the public lazy facade.
- `serialization.py`, `timestamps.py`, and `async_tools.py` are the shared
  helper surfaces used across packages.
- `config.py`, `jax_env.py`, and `env_parsing.py` are early-process bootstrap
  helpers; keep domain behavior out of them.
- `migrations/` owns package-local migration manifest helpers.

## Extension Points

`polisyos.common` is not an extension host. Extension hosts should depend on
Common only for bootstrap-safe helpers and must declare their own entry-point
group in [architecture/extension_points.toml](../../../architecture/extension_points.toml).

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

## Tests

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `uv run pytest -q tests/unit/common/test_async_tools.py tests/unit/common/test_config_bootstrap.py tests/unit/common/test_fast_json_serialization.py tests/unit/common/test_serialization_properties.py tests/unit/common/test_timestamps.py tests/unit/common/test_migrations_purity.py`

- Conceptual release gate: `uv run python tools/devx/workspace/core_runtime_mypy.py`
- Conceptual release gate:
  `uv run python tools/devx/workspace/core_runtime_basedpyright.py`

## Operability Links

- [Common component SLO](../../../ops/components/common/slo.yaml)
- [Common component runbooks](../../../ops/components/common/runbooks.md)
- [Generated artifacts reference](../../../docs/reference/generated-artifacts.md)
- [Core / Common / Runtime audit plan](../../../docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md)

## Known Shims/Deprecations

There are no active package-local shims for `polisyos.common` in
[architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
Promoting an internal helper such as `env_parsing.py` requires a facade update,
public-surface refresh, and compatibility note.

## Reference docs

- [Public Surface](../../../docs/reference/public-surface.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Core / Common / Runtime Audit Remediation Plan](../../../docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md)
- [Common migrations](migrations/README.md)

- Last updated: 2026-05-06
