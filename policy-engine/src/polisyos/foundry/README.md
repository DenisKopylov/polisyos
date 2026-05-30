# Foundry (`polisyos.foundry`)

Foundry is the PolicyOS computation layer: it turns Trinity bundles into
CAS-backed execution plans, binds runtime state, executes patch-first program
graphs, and hands off to methods, calibration, uncertainty, and agent-based
simulation surfaces.

- Last updated: 2026-05-06

## Purpose

Use `polisyos.foundry` as the narrow public facade for compile/execute
workflows. Everything else in this package tree exists to support that facade:
runtime contracts, method catalogs, calibration flows, reproducibility hooks,
and agent-sim tooling.

## Where to Start

- [quickstart/__init__.py](quickstart/__init__.py) for the public quickstart
  import path and [_quickstart.py](_quickstart.py) for the smallest
  compile/execute path that writes real CAS artifacts.

- [compile/api.py](compile/api.py) for the public `compile()` contract and
  failure semantics.

- [execute/api.py](execute/api.py) for `execute()`, input bindings, and replay
  behavior.

- [contracts/README.md](contracts/README.md) for runtime state, patch, and
  fidelity contracts.

- [methods/README.md](methods/README.md) for the reusable method ABI, registry,
  dispatch, and catalog surfaces.

- [calibration/README.md](calibration/README.md) for measurement-aware fit
  loops and uncertainty hand-off.

- [agent_sim/README.md](agent_sim/README.md) for low-level ABM/RL executors and
  wiring.

- [plugins/README.md](plugins/README.md) for plugin-driven domain simulation on
  top of `agent_sim`.

## Public API

| Entrypoint          | Description                                                                                                |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `compile()`         | Compile a Trinity bundle into `foundry.program_graph`, `foundry.exec_plan`, and a compile report artifact. |
| `compile_program()` | Compatibility alias for `compile()` on the package facade.                                                 |
| `execute()`         | Execute a compiled plan from `FoundryInputBindingsRef` and persist simulation evidence.                    |

The stable package facade is intentionally small. If a workflow needs lower
level helpers, start from the subpackage README for that area instead of
deep-importing ad hoc internals.

## Internal Layout

- [`api.py`](api.py), [`__init__.py`](__init__.py), [`compile/`](compile/),
  and [`execute/`](execute/) own the stable public compile/execute surface.
- [`contracts/`](contracts/README.md) owns runtime state, patch, and fidelity
  contracts used by compilation and execution.
- [`methods/`](methods/README.md) owns reusable method ABI, registries, and
  catalog families.
- [`agent_sim/`](agent_sim/README.md), [`calibration/`](calibration/README.md),
  [`uncertainty/`](uncertainty/README.md), and domain helpers are
  implementation surfaces unless exported by the root facade.
- [`welfare/`](welfare/) owns welfare-bound sidecars, social-weight schedule
  helpers, and the W8.D Pareto frontier/social-weight provenance emitter used
  to expose tradeoff facts separately from governance value choices.
- [`execute/_internal/`](execute/_internal/) is private executor support.

## Extension Points

- External reusable methods use `polisyos.foundry_methods`; see
  [methods/README.md](methods/README.md) and
  [architecture/extension_points.toml](../../../architecture/extension_points.toml).
- Domain simulation plugins are documented in [plugins/README.md](plugins/README.md)
  and build on `agent_sim` rather than the root facade.

## Depends On / Depended On By

- Depends on: `polisyos.core` artifact, registry, and contract layers;
  `polisyos.ir` Trinity/model contracts; optional scientific runtimes exposed by
  subpackages.

- Depended on by: `polisyos.scientist` execution and autotune flows,
  `polisyos.runtime.http` control services, release-acceptance flows, and local
  demos/benchmarks.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry._quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="foundry-docs-") as tmp:
    result = run_trivial_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
PY
```

## Tests

```bash
uv run pytest tests/unit/foundry/facade/test_quickstart.py \
  tests/unit/foundry/compile/test_compile_determinism.py \
  tests/unit/foundry/runtime/test_execute_input_bindings.py -q

uv run pytest tests/unit/foundry/runtime/test_executor_fail_semantics.py \
  tests/unit/foundry/runtime/test_nan_guard_public.py -q
```

Package test ownership is documented in
[tests/unit/foundry/README.md](../../../tests/unit/foundry/README.md). Run the
methods suite when changes touch `methods/` registration, dispatch, or catalog
metadata.

## Operability Links

- [Foundry component SLO](../../../ops/components/foundry/slo.yaml)
- [Foundry component runbooks](../../../ops/components/foundry/runbooks.md)
- [Foundry observability and reproducibility](../../../docs/reference/foundry/observability-reproducibility.md)
- [Replay or restore runbook](../../../docs/runbooks/replay-or-restore.md)
- [Benchmark regression triage runbook](../../../docs/runbooks/benchmark-regression-triage.md)

## Known Shims/Deprecations

- Root public exports stay intentionally narrow. Promote new compile/execute
  API through `api.py`, public-surface docs, and a compatibility note before
  removing old import paths.

## Reference Docs

- [docs/reference/foundry/index.md](../../../docs/reference/foundry/index.md)
- [docs/reference/foundry/compile-execute.md](../../../docs/reference/foundry/compile-execute.md)
- [docs/reference/foundry/state.md](../../../docs/reference/foundry/state.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md](../../../docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md)
- [tests/unit/foundry/README.md](../../../tests/unit/foundry/README.md)
