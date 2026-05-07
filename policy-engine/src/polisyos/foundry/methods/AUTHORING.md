# Foundry Methods Authoring Contract

Owner: `team-foundry`
Applies to: `src/polisyos/foundry/methods/**`
Last updated: 2026-05-05

## Purpose

This package owns reusable typed method contracts, registries, catalog
families, dispatch, lifecycle helpers, and method selection.

## Allowed File Categories

- Product Python modules, package-local `.pyi` stubs, and README/AUTHORING docs.
- Catalog families under `catalog/`.
- Method tests only when they are package-local test helpers; normal tests live
  under `tests/unit/foundry/methods/`.

## Public/Private Boundary

The public boundary is the package facade and documented API modules. `_internal`
and backend helper modules are private unless exported by README and
`architecture/public_surface.toml`.

## Naming Convention

Use snake_case module names. Catalog families use stable domain nouns such as
`causal`, `bayesian`, or `optimization`; compatibility wrappers must name the
target in the module docstring.

## Test Location

Use `tests/unit/foundry/methods/` for unit coverage and
`tests/unit/foundry/methods/catalog/<family>/` for catalog behavior.

## Fixture/Data Policy

Do not commit large datasets here. Small deterministic method examples belong
in test fixtures or generated snapshots registered in architecture contracts.

## Generated File Policy

Committed generated outputs must be listed in `architecture/generated_artifacts.toml`.
Method catalog snapshots are produced by `build_method_catalog_snapshot()`.

## Extension Points

External methods use `polisyos.foundry_methods` from
`architecture/extension_points.toml`. The canonical authoring path is:

1. Implement a class with `MethodSignature`, `MethodMetadata`, and static
   `pure_step()`.
2. Wrap it with `polisyos.foundry.extensions.component_for_method()`.
3. Publish exactly one `polisyos.foundry_methods` entry point that exposes the
   resulting `FoundryMethodPlugin`.

Builtin catalog methods use the same component path through
`polisyos.foundry.extensions._builtin_loader:builtin_foundry_method_components`
before the bridge registers them in `selection/registry.py`.

`polisyos.foundry.plugins` and the `polisyos.plugins` entry-point group are
legacy agent-simulation domain-plugin surfaces. They are not accepted for new
Foundry method extensions.

## Deprecation And Shim Policy

Deprecated method IDs, renamed modules, and wrapper-only compatibility surfaces
must be recorded in `architecture/shims.toml` or the method deprecation registry.
