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

## Reversible cold chain plans

`CompiledChainPlan` is an internal, versioned executable-plan projection beside
the unchanged `ChainArtifact` 1.0 provenance recipe. `from_chain()` captures the
actual compiled occurrence UUIDs, insertion/instance order, static and dynamic
parameters, signature ABI, slot bindings, composition cache keys and complete
effective predecessor graph. Data-flow connections remain distinct from
ordering-only `requires` edges. Its immutable canonical bytes use wire 1.0.0 and
CAS kind `foundry.compiled_chain_plan`.

`store_compiled_chain_plan()` writes those bytes through the normal CAS owner.
`load_compiled_chain_plan()` retains the exact typed, selected-manifest
`ArtifactRef` for both guarded manifest and blob reads, checks kind/media/schema,
then returns a real `CompiledMethodChain`. Intake rebuilds with the existing
composer/linker and STRICT validation. It reconciles current and returned
signature ABI, complete parameter partitions, concrete occurrences, computed
binding compatibility, effective graph, execution order and composition cache
keys before a scientific body runs. Missing/ambiguous requirements and cycles
retain the existing typed refusals; a changed essential edge cannot silently
be replaced by a reader default. Original warnings are captured as advisory
provenance; restored warnings are recomputed by the current STRICT builder.

The payload profile is finite plain JSON scalars, lists and string-keyed objects;
nonfinite numbers, tuple/array/dtype/custom Python values and the canonical
`_type` parameter key are refused before plan publication. There is no implicit
default or value coercion to materialize an unsupported runtime payload.

This is fresh cold execution against the current registry implementation,
assuming that registry remains stable across restoration and execution. ABI and
plan hashes do not attest historical implementation code, permission, scientific
validity, cached results or checkpoint prefixes. Strict checkpoint/JIT identity
remains owned by those consumers. Caller initial state, seed, permitted parameter
overrides and external effects remain explicit execution inputs. Legacy recipe
artifacts are not promoted to runnable plans and their content/schema is unchanged.
