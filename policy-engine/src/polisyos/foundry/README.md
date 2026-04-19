# Foundry (`polisyos.foundry`)

Foundry is the PolicyOS computation layer: it turns Trinity bundles into
CAS-backed execution plans, binds runtime state, executes patch-first program
graphs, and hands off to methods, calibration, uncertainty, and agent-based
simulation surfaces.

- Last updated: 2026-04-17

## Purpose

Use `polisyos.foundry` as the narrow public facade for compile/execute
workflows. Everything else in this package tree exists to support that facade:
runtime contracts, method catalogs, calibration flows, reproducibility hooks,
and agent-sim tooling.

## Where to Start

- [quickstart.py](quickstart.py) for the smallest compile/execute path that
  writes real CAS artifacts.
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

## Public Entrypoints

| Entrypoint | Description |
|---|---|
| `compile()` | Compile a Trinity bundle into `foundry.program_graph`, `foundry.exec_plan`, and a compile report artifact. |
| `compile_program()` | Compatibility alias for `compile()` on the package facade. |
| `execute()` | Execute a compiled plan from `FoundryInputBindingsRef` and persist simulation evidence. |

The stable package facade is intentionally small. If a workflow needs lower
level helpers, start from the subpackage README for that area instead of
deep-importing ad hoc internals.

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
from polisyos.foundry.quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="foundry-docs-") as tmp:
    result = run_trivial_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
PY
```

## Test / Verification Commands

```bash
uv run pytest tests/foundry/test_quickstart.py \
  tests/foundry/test_compile_determinism.py \
  tests/foundry/test_execute_input_bindings.py -q

uv run pytest tests/foundry/test_executor_fail_semantics.py \
  tests/foundry/test_nan_guard.py -q
```

## Reference Docs

- [docs/reference/foundry/index.md](../../../docs/reference/foundry/index.md)
- [docs/reference/foundry/compile-execute.md](../../../docs/reference/foundry/compile-execute.md)
- [docs/reference/foundry/state.md](../../../docs/reference/foundry/state.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/FOUNDRY_REMEDIATION_PLAN.md](../../../docs/FOUNDRY_REMEDIATION_PLAN.md)
- [tests/foundry/README.md](../../../tests/foundry/README.md)
