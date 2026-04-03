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
- **Discovery** - entry-point and dev-scan discovery can be combined with explicit precedence rules.
- **Registry** - `ComponentRegistry` stores multiple versions and resolves exact or compatible matches.
- **Bootstrap** - `build_components_index()` and `bootstrap_plugin_registries()` wire the discovered index into runtime domains.

## Public API

- identity/metadata: `ComponentId`, `ComponentKind`, `ComponentMetadata`, `ComponentDep`, `Capability`
- discovery/registry: `discover_components`, `ComponentRegistry`, `build_components_index`
- bootstrap/CLI: `bootstrap_plugin_registries`, `ComponentProvider`, `ComponentFactory`

## Current State

- Last updated: 2026-04-03
- The tree now includes the CLI facades `_cli_audit.py`, `_cli_crypto.py`, `_cli_lex.py`, `_cli_replay.py`, `_cli_scholar.py`, and `_cli_scientist.py`.
- Component discovery still supports both entry points and local dev-scan fallback.
