# Methods (`polisyos.foundry.methods`)

`polisyos.foundry.methods` is the typed method subsystem for reusable
computations: ABI contracts, registry/discovery, DAG composition, backend
dispatch, capability metadata, and the domain catalog under `catalog/`.

- Last updated: 2026-10-15

## Purpose

Use this package when a workflow needs reusable computation surfaces that are
independent of one specific Trinity execution graph. The methods layer is the
bridge between authored scientific methods and planner/runtime code that needs
typed discovery, versioning, dispatch, and evidence.

## Where to Start

- [api.py](api.py) and [__init__.py](__init__.py) for the exported facade and
  stable imports. Cross-package consumers use exact lazy owner exports for
  bootstrap work, forecasting registration, ambiguity contracts, mechanism
  families, and ordinal poverty estimation.
- [causal/README.md](causal/README.md) for the causal family facade; use
  [backends/__init__.py](backends/__init__.py) for the lazy `NumpyRunner` route.
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
- [catalog/mechanism/README.md](catalog/mechanism/README.md) for the
  runtime mechanism descriptor projection and its canonical registry owner.
- [catalog/AUTHORING.md](catalog/AUTHORING.md) and
  [catalog/NAMING.md](catalog/NAMING.md) for method authoring conventions.

- [cli/scaffold.py](cli/scaffold.py) and [cli/validator.py](cli/validator.py)
  for local authoring/validation workflows.

## Public API

| Entrypoint                         | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `FoundryMethod`                    | Base protocol for typed methods.                                          |
| `MethodRegistry` | Registry with version resolution and scoped isolation helpers. |
| `MethodSelectionReceipt` | Immutable receipt for the selected method and its declared selection basis. |
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
| `BootstrapExecutionWork`           | Typed bootstrap execution-work result consumed by Scientist packets.     |
| `AmbiguityCertificate`              | Existing optimization-family ambiguity contract.                         |
| `ensure_forecasting_methods_registered()` | Registers the existing forecasting family.                         |
| `get_mechanism_family_spec()`       | Resolves a mechanism family from its canonical owner.                     |
| `OrdinalMultidimensionalPovertyEstimator` | Existing ordinal poverty estimator.                                |

## Internal Layout

### Source-bound causal consumers

Import `causal_worker_execution_context`, `validate_source_bound_gcm_spec`,
`validate_source_bound_causal_estimator_interval`, and
`validate_source_bound_causal_worker_response` from `polisyos.foundry` for
cross-package use; the method package retains the same canonical aliases.
These lazy exports resolve to the existing canonical provider functions; they
introduce no second validator, artifact store or scheduler. The execution context
requires an actual CAS and source reference. The validators reopen source bytes
and reconcile the selected worker request, rows, graph, code/lock identity and
supported fitted values. Missing worker resources return a typed unavailable
failure; malformed or inconsistent bindings return a typed refusal.

Scientist causal query consumers use this facade before consuming a fitted model
or a separate refit estimator interval. Validation establishes supported
computation and source custody, not causal identification, sampling-law admission
or policy authority. The current Python 3.14 application's missing in-process
DoWhy/EconML dependencies do not count as a backend witness. See
[structural causal models](../../../../docs/reference/foundry/structural-causal-models.md)
for the selected Python 3.12 / DoWhy 0.14 profile and its supported estimands.

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

- Slot-layout types and builders belong to `polisyos.ir.kernel.slots`.
  `polisyos.foundry.methods.layout` retains direct compatibility bindings;
  `polisyos.foundry.methods.compiler.layout` retains the legacy alias with
  the same IR object identities. Both nested paths are internal under the
  [public-surface contract](../../../../architecture/public_surface/contract.toml).
  Foundry owners preserve both addresses for compatible callers until a
  separate lifecycle decision updates callers, references, and release notes.
  See [compiler layout compatibility](compiler/README.md#layout-compatibility).
- Package-level compatibility and deprecation records are governed by
  [architecture/shims.toml](../../../../architecture/shims.toml) and the
  method lifecycle/deprecation helpers under `lifecycle/`.
- Large-module budgets for this package are tracked in
  [architecture/module_size_budget.toml](../../../../architecture/module_size_budget.toml);
  extraction work must preserve method IDs, registry snapshots, and import
  compatibility until the relevant sunset is reached.
- Deprecated method IDs or renamed modules require compatibility tests plus a
  release note before the old surface is removed.
- The former `polisyos.foundry._registry` path is unlisted and internal under
  the public-surface contract, so the module is removed after repository imports
  migrate to `catalog/mechanism/runtime_registry.py`. This is not a supported
  external entrypoint; external deep-import and persisted-pickle populations
  remain unestablished.

## Reference Docs

- [AUTHORING.md](AUTHORING.md)
- [catalog/README.md](catalog/README.md)
- [docs/reference/foundry/methods-catalog.md](../../../../docs/reference/foundry/methods-catalog.md)
- [docs/reference/foundry/frontier-methods.md](../../../../docs/reference/foundry/frontier-methods.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md](../../../../docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md)

## Generated ABI semantics

The four committed method stubs are produced together by `polisyos-tools foundry generate-stubs`. The owner uses
parse-only stubgen with private callable inclusion, restores explicit source
annotations that stubgen treats as implicit receiver annotations, and emits
actual runtime Enum members as assignments. This preserves typed internal
consumers such as `_stable_digest` and Enum attribute/value semantics; canonical
Ruff formatting alone does not establish a valid typing ABI.

Regenerate into a new `--output-root`, inspect all four genuine outputs, and then
run the same owner with `--check`. The defining staged-owner test also invokes
strict mypy with all four canonical paths shadowed by the staged bytes and a
consumer derived from every Enum declared by the canonical owners. Member names
and expected value types come from runtime Enum objects, independently of the
producer transform. The type client also consumes the real private digest ABI.
No generated file should be corrected manually or by weakening `mypy.ini`.

`ParamsT` is contravariant because the method protocol only consumes it; this
corrects the static protocol declaration without changing the runtime call ABI.
Collection helpers accept the iterable contracts they actually traverse, and
executor helpers retain typed signatures through dispatch and cache composition.
Ray's optional backend must be available in a profile claiming its strict import
check; an absent Ray installation is an environment limitation, not a product PASS.
