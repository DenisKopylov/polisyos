# Methods (`polisyos.foundry.methods`)

`polisyos.foundry.methods` is the typed method subsystem for reusable
computations: ABI contracts, registry/discovery, DAG composition, backend
dispatch, capability metadata, and the domain catalog under `catalog/`.

- Last updated: 2026-04-17

## Purpose

Use this package when a workflow needs reusable computation surfaces that are
independent of one specific Trinity execution graph. The methods layer is the
bridge between authored scientific methods and planner/runtime code that needs
typed discovery, versioning, dispatch, and evidence.

## Where to Start

- [__init__.py](__init__.py) for the exported facade and stable imports.
- [registry.py](registry.py) for `MethodRegistry`, version resolution, and
  scoped registries.

- [composer.py](composer.py) and [linker.py](linker.py) for DAG composition and
  slot compatibility.

- [catalog/README.md](catalog/README.md) for the domain-family tree.
- [catalog/AUTHORING.md](catalog/AUTHORING.md) and
  [catalog/NAMING.md](catalog/NAMING.md) for method authoring conventions.

- [cli/scaffold.py](cli/scaffold.py) and [cli/validator.py](cli/validator.py)
  for local authoring/validation workflows.

## Public Entrypoints

| Entrypoint                         | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `FoundryMethod`                    | Base protocol for typed methods.                                          |
| `MethodRegistry`                   | Registry with version resolution and scoped isolation helpers.            |
| `MethodComposer`                   | Builds method DAGs and ordered execution chains.                          |
| `SlotLinker`                       | Checks slot compatibility before composing methods.                       |
| `MethodDispatcher`                 | Dispatches methods to supported runtimes/backends.                        |
| `ensure_all_methods_registered()`  | Loads all shipped catalog families into a registry.                       |
| `build_method_catalog_snapshot()`  | Captures immutable registry inventory for docs, CI, and release evidence. |
| `build_method_capability_matrix()` | Produces machine-readable applicability/replay rows.                      |
| `advise_methods()`                 | Ranks candidate methods for a planning query.                             |

## Depends On / Depended On By

- Depends on: `polisyos.core` component/bootstrap surfaces, `polisyos.ir`
  contracts used by catalog families, and optional backend stacks such as JAX,
  NumPy, solver, Ray, and Bayesian runtimes.

- Depended on by: Foundry executor graph dispatch, Scientist compute/autotune
  flows, runtime control services, docs generation, and devx/quality tooling.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python -m polisyos.foundry.methods.cli.validator --help

uv run python - <<'PY'
from polisyos.foundry.methods.catalog_snapshot import (
    build_method_capability_matrix,
    build_method_catalog_snapshot,
)

snapshot = build_method_catalog_snapshot(run_id="docs")
print(snapshot.snapshot_id)
print(len(build_method_capability_matrix(snapshot, runnable_only=True)))
PY
```

The snapshot command may emit method-registration logs before the final
snapshot ID and runnable count.

## Test / Verification Commands

```bash
uv run pytest tests/unit/foundry/methods/test_registry.py \
  tests/unit/foundry/methods/test_discovery.py \
  tests/unit/foundry/methods/test_cli.py -q

uv run pytest tests/unit/foundry/methods/test_selection_advisor.py \
  tests/unit/foundry/methods/test_cross_backend_consistency.py \
  tests/unit/foundry/methods/backends/test_backend_determinism.py -q
```

## Reference Docs

- [catalog/README.md](catalog/README.md)
- [docs/reference/foundry/methods-catalog.md](../../../../docs/reference/foundry/methods-catalog.md)
- [docs/reference/foundry/frontier-methods.md](../../../../docs/reference/foundry/frontier-methods.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md](../../../../docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md)
