# Methods (`polisyos.foundry.methods`)

`polisyos.foundry.methods` is the typed method subsystem for reusable
computations: ABI contracts, registry/discovery, DAG composition, backend
dispatch, capability metadata, and the domain catalog under `catalog/`.

- Last updated: 2026-08-27

## Purpose

Use this package when a workflow needs reusable computation surfaces that are
independent of one specific Trinity execution graph. The methods layer is the
bridge between authored scientific methods and planner/runtime code that needs
typed discovery, versioning, dispatch, and evidence.

## Where to Start

- [api.py](api.py) and [__init__.py](__init__.py) for the exported facade and
  stable imports.
- [backends/protocol.py](backends/protocol.py) for the Foundry-owned generic
  embedder implementation. Cross-package callers import its three public names
  from `polisyos.foundry`; backend package paths remain internal.
- [../extensions/](../extensions/) for the canonical external method plugin
  contract, entry-point discovery, and builtin-loader bridge.
- [selection/registry.py](selection/registry.py) for `MethodRegistry`,
  [selection/resolution.py](selection/resolution.py) for version resolution,
  and [selection/README.md](selection/README.md) for registration ownership.

- [components/composer.py](components/composer.py) and
  [components/linker.py](components/linker.py)
  for DAG composition and slot compatibility.

- [artifacts/README.md](artifacts/README.md) for method execution provenance.
- [compiler/README.md](compiler/README.md) for compilation, layout, and
  hot-reload helpers.
- [components/README.md](components/README.md) for component bridge and chain
  helper ownership.
- [lifecycle/README.md](lifecycle/README.md) for compatibility, deprecation,
  observability, and monitoring helpers.

- [catalog/README.md](catalog/README.md) for the domain-family tree.
- [catalog/AUTHORING.md](catalog/AUTHORING.md) and
  [catalog/NAMING.md](catalog/NAMING.md) for method authoring conventions.

- [cli/scaffold.py](cli/scaffold.py) and [cli/validator.py](cli/validator.py)
  for local authoring/validation workflows.

## Public API

| Entrypoint                         | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `FoundryMethod`                    | Base protocol for typed methods.                                          |
| `MethodRegistry`                   | Registry with version resolution and scoped isolation helpers.            |
| `MethodComposer`                   | Builds method DAGs and ordered execution chains.                          |
| `SlotLinker`                       | Checks slot compatibility before composing methods.                       |
| `MethodDispatcher`                 | Dispatches methods to supported runtimes/backends.                        |
| `polisyos.foundry.EmbedderProtocol` | Structural contract for fixed-dimensional text embedders.                |
| `polisyos.foundry.TFIDFEmbedder`    | Dependency-free fitted TF-IDF text embedder.                              |
| `polisyos.foundry.SentenceTransformerEmbedder` | Optional adapter with lazy dependency loading.                 |
| `ensure_all_methods_registered()`  | Loads installed Foundry method extensions into a registry.                |
| `build_method_catalog_snapshot()`  | Captures immutable registry inventory for docs, CI, and release evidence. |
| `build_method_capability_matrix()` | Produces machine-readable applicability/replay rows.                      |
| `advise_methods()`                 | Ranks candidate methods for a planning query.                             |

## Internal Layout

- `api.py` and `__init__.py` own the stable lazy facade. Treat `api.py` as the
  public-surface map; add exported names there instead of exposing loose
  implementation modules.
- `base.py`, `exceptions.py`, `types/`, and `artifacts/` hold ABI contracts,
  validation errors, shape/type helpers, and persisted evidence models.
- `selection/`, `components/`, `compiler/`, and `backends/` own registry,
  composition, compilation, and runtime dispatch. Backend modules are internal;
  the root `polisyos.foundry` facade owns the three public embedding aliases.
- `catalog/` holds builtin domain families. High-complexity families such as
  `catalog/causal` carry local README/AUTHORING docs and module-size budgets.
- `lifecycle/` owns compatibility, deprecation, observability, and method
  monitoring helpers.
- `_internal/` is private implementation code. Do not import it from outside
  the package or document it as public API.

## Extension Points

- External method packages use the `polisyos.foundry_methods` entry-point group
  declared in
  [architecture/extension_points.toml](../../../../architecture/extension_points.toml).
- Builtins register through `components/bridge.py`, catalog-local
  `_registry_boot.py` modules, and `selection/registry.py`; external plugins
  must follow the same metadata and compatibility rules.
- Authoring rules live in [AUTHORING.md](AUTHORING.md) and
  [catalog/AUTHORING.md](catalog/AUTHORING.md). Use
  [examples/extensions/README.md](../../../../examples/extensions/README.md)
  as the extension-example index when adding installable examples.

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
from polisyos.foundry.methods.catalog.snapshot import (
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

## Tests

```bash
uv run pytest tests/unit/foundry/methods/test_registry.py \
  tests/unit/foundry/methods/test_discovery.py \
  tests/unit/foundry/methods/test_cli.py -q

uv run pytest tests/unit/foundry/methods/test_selection_advisor.py \
  tests/unit/foundry/methods/test_cross_backend_consistency.py \
  tests/unit/foundry/methods/backends/test_backend_determinism.py -q
```

Broader package ownership lives in
[tests/unit/foundry/methods/README.md](../../../../tests/unit/foundry/methods/README.md).
Catalog-family tests should mirror the package layout under
`tests/unit/foundry/methods/catalog/<family>/`.

## Operability Links

- [Foundry component SLO](../../../../ops/components/foundry/slo.yaml)
- [Foundry component runbooks](../../../../ops/components/foundry/runbooks.md)
- [Foundry observability and reproducibility](../../../../docs/reference/foundry/observability-reproducibility.md)
- [Benchmark regression triage runbook](../../../../docs/runbooks/benchmark-regression-triage.md)
- [Retained artifact recovery runbook](../../../../docs/runbooks/retained-artifact-recovery.md)

## Known Shims/Deprecations

- Package-level compatibility and deprecation records are governed by
  [architecture/shims.toml](../../../../architecture/shims.toml) and the
  method lifecycle/deprecation helpers under `lifecycle/`.
- Large-module budgets for this package are tracked in
  [architecture/module_size_budget.toml](../../../../architecture/module_size_budget.toml);
  extraction work must preserve method IDs, registry snapshots, and import
  compatibility until the relevant sunset is reached.
- Deprecated method IDs or renamed modules require compatibility tests plus a
  release note before the old surface is removed.

## Reference Docs

- [AUTHORING.md](AUTHORING.md)
- [catalog/README.md](catalog/README.md)
- [docs/reference/foundry/methods-catalog.md](../../../../docs/reference/foundry/methods-catalog.md)
- [docs/reference/foundry/frontier-methods.md](../../../../docs/reference/foundry/frontier-methods.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md](../../../../docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md)
