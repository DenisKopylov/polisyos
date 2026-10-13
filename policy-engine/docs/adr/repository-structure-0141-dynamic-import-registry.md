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

1. `architecture/imports/dynamic.toml` is the source of truth for dynamic import
   patterns found in `src/`, `tools/`, and frontend runtime-api-client scripts.
2. Each entry records `pattern`, `source_file`, `line`, `call`, `owner`,
   `allowed_targets`, and notes.
3. `dynamic_imports_gate` fails when a current dynamic import call is missing
   from the registry, when a registry entry is stale, or when an allowed target
   cannot be resolved.
4. Plugin and user-supplied patterns may have an empty `allowed_targets` list,
   but they must still be inventoried and owner-tagged.
5. Extension plugin discovery is not treated as an ad hoc import. It must use a
   declared entry-point group or builtin loader from
   `architecture/extension_points.toml`.
6. New dynamic-import registry entries must identify `owner`, `target` or
   `allowed_targets`, and `verifier`. `target` names the intended import,
   extension point, or builtin loader; `verifier` names the gate, smoke test, or
   owner review that proves the dynamic edge remains intentional.
7. The dynamic-import gate derives the expected registry from the complete
   `collect_dynamic_imports` result rendered by `render_dynamic_imports_toml`.
   It compares each current row's full field set and values, including the
   collector-derived `id`, owner, target, verifier, allowed targets, and notes;
   unknown, missing, duplicated, stale, malformed, and source-mismatched rows
   fail closed. Stable header fields likewise match the canonical renderer.
8. `review_owner`, `reviewed_at`, and `review_expires` remain external review
   decisions: source inventory reconciliation neither issues nor renews them.
   This gate requires them to remain present as nonempty strings but does not
   authenticate the issuer. The separate repository closeout check continues
   to reject an expired `review_expires`. A green inventory comparison is not
   review approval, and empty `allowed_targets` remain review-required.

## Consequences

Future decomposition work cannot silently break importlib, entry-point, or
plugin discovery paths. Extension points and ad hoc imports remain separate
review concepts: extension points are versioned ABI contracts; ad hoc dynamic
imports are explicit exceptions with owners and verifiers.

## Related Decisions

- ADR-RSR-0143 Decomposition Blueprint Contract.
- ADR-RSR-0135 Versioning Out of Package Names And Compatibility Contracts.
