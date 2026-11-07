# Components (`polisyos.core.components`)

`core.components` is PolicyOS's component model and bootstrap layer. It defines component ids,
metadata, capabilities, discovery rules, registries, and the bootstrap flow that turns discovered
components into runtime registries.

## Role in System

- **Depends on:** nothing domain-specific; it sits on top of shared runtime primitives.
- **Used by:** `fabric`, `foundry`, `lex`, `scientist`, `scholar`, `registry`, and CLI/bootstrap tooling.
- **Boundary function:** turns package metadata and entry points into consistent runtime registries.

## Key Concepts

- **Component identity** - `ComponentId` encodes namespace, name, and SemVer.
- **Component metadata** - `ComponentMetadata` and `ComponentDep` describe what a component is and what it needs.
- **Capabilities** - flags capture cross-cutting abilities such as CAS reading or execution rights.
- **Discovery** - entry-point and dev-scan discovery can be combined with explicit
  precedence rules. Builtin declarations use the typed
  `DeclaredBuiltinLoader(target, group)` contract; existing callable and
  `(name, callable)` loader forms remain supported. For declared loaders, the
  group determines the required `ComponentKind`; discovery rejects providers
  whose metadata kind disagrees and records the group on each discovered
  component source. Manifest v2 records every declared loader's discovery name,
  target, and group before loading, including empty and failed loaders; discovery
  without declared loaders retains the v1 payload shape and identity. Foundry's
  default provider now uses this typed route while its exported callable tuple stays
  available for compatibility. The `builtin_loaders` target tuple remains unchanged.
  Fabric entry-point discovery also records the host-computed declaring distribution,
  entry-point declaration, and loaded target byte bindings in manifest v3. Editable
  source binding is limited to the exact first-party project root; third-party editable
  origins remain not established. This binds source origin and byte consistency, not
  publisher identity, permission, or transitive source closure.
  Entry-point enumeration and identity outcomes are reconciled for selected groups. Fabric
  provider-origin and factory predicates additionally account for every binding and factory result.
  A completed empty group is explicit; failed or partial enumeration remains not established.
  Fabric refuses mixed factory output containing invalid result rows; other component families
  retain their existing valid-sibling behavior.
- **Registry** - `ComponentRegistry` stores multiple versions and resolves exact or compatible matches.
- **Bootstrap** - `build_components_index()` and `bootstrap_plugin_registries()` wire the discovered index into runtime domains.

## Public API

- discovery evidence: `ProviderOriginBinding` and `ProviderModuleBinding` are additive stable-facade exports with their existing class identities.
- direct source observation: `describe_callable_source(function, expected_module=...)` reconciles a direct Python function against its actual module source and returns its file digest without invoking it. DOE uses this facade instead of importing the private component origin reader. This observation supplies no installed-distribution, dependency, publisher or execution authority.
- identity/metadata: `ComponentId`, `ComponentKind`, `ComponentMetadata`, `ComponentDep`, `Capability`
- discovery/registry: `discover_components`, `BuiltinLoaderSpec`,
  `DeclaredBuiltinLoader`, `ComponentRegistry`, `build_components_index`
- bootstrap/CLI: `bootstrap_plugin_registries`, `ComponentProvider`, `ComponentFactory`

## Current State

- Last updated: 2026-04-03
- The tree includes the Core CLI handlers `_cli_audit.py`, `_cli_crypto.py`, `_cli_lex.py`, `_cli_replay.py`, and `_cli_scholar.py`; cross-product Scientist command composition lives in `tools/ops_runners/runtime_cli.py`.
- Component discovery still supports both entry points and local dev-scan fallback.
