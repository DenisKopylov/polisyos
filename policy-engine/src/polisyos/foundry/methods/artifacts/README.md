# Foundry Method Artifacts

`polisyos.foundry.methods.artifacts` owns immutable provenance records for
method, chain, and execution evidence.

## Home

- `parts.py` exposes the public artifact functions and dataclasses.
- `_chain.py`, `_method.py`, `_evidence.py`, `_fingerprint.py`, and
  `_records.py` are private implementation slices.
- Public callers should import from `polisyos.foundry.methods.artifacts`.

## Runtime implementation identity

`implementation_identity_projection()` supplies the same code graph to
checkpoint request identity and compiler specialization. It delegates source
hashing to `compute_source_hash`; each consumer uses its existing canonical
digest. Class identity binds all supported runtime class attributes and bases,
including ordinary functions, static methods, class methods and all property
accessors. The projection reads descriptor functions without invoking them.
Function identity includes defaults, referenced globals/nonlocals/builtins and
custom immutable attributes. A same-class helper replacement changes identity
even when the original class and entrypoint source text stay unchanged.

The supported graph uses ordinary Python classes and inspectable, undecorated
Python functions with immutable scalar, bytes, tuple, frozenset and string-keyed
mapping-proxy captures. Frozen dataclass records bind their directly stored
immutable field values and declared class source; arbitrary record methods and
dynamic record attribute access are outside that data-value profile. Imported
module and builtin implementation boundaries use installed distribution or
Python versions; this does not establish mutable module contents or external
effects. Dynamic imports/reflection, hostile runtime mutation, unavailable
Python functions, wrapped functions, custom descriptors/metaclasses, callable
instances and mutable captured values do not establish strict code closure.
Known unsupported graph values raise `SourceIdentityUnavailableError` before
execution. The `strict=False` legacy profile records explicit unavailable
markers and must not be presented as complete source identity.

## Authoring Rules

- Git provenance probes use fixed private Git subcommands with argument vectors
  and no shell. Source-derived root paths are `-C` operands; the `ls-tree` path
  follows `--`. The configured local Git executable and repository remain
  environment premises; this lookup grants no evidence authority or permission.
- Keep artifact payloads deterministic and content-addressable.
- Add schema-version changes beside compatibility tests.
- Do not add backend execution logic here; backend receipts are passed in from
  `backends/` and persisted here.
