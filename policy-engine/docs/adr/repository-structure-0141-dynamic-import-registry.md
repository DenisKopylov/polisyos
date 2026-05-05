# ADR-RSR-0141: Dynamic Import Registry

## Status

Accepted

## Date

2026-05-03

## Context

Dynamic imports hide dependencies from static import gates. Scientist and
Foundry decomposition is risky unless every dynamic import pattern that can
resolve an in-repository FQN has an explicit whitelist.

## Decision

1. `architecture/dynamic_imports.toml` is the source of truth for dynamic import
   patterns found in `src/`, `tools/`, and frontend runtime-api-client scripts.
2. Each entry records `pattern`, `source_file`, `line`, `call`, `owner`,
   `allowed_targets`, and notes.
3. `dynamic_imports_gate` fails when a current dynamic import call is missing
   from the registry, when a registry entry is stale, or when an allowed target
   cannot be resolved.
4. Plugin and user-supplied patterns may have an empty `allowed_targets` list,
   but they must still be inventoried and owner-tagged.

## Consequences

Future decomposition work cannot silently break importlib, entry-point, or
plugin discovery paths.

## Related Decisions

- ADR-RSR-0143 Decomposition Blueprint Contract.
