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
dynamic record attribute access are outside that data-value profile. Captured
ordinary modules require static attribute paths from referenced globals or
nonlocals. The graph reads those members directly from module dictionaries,
without running getters, and projects their supported Python helper graph;
same-version member replacement therefore invalidates checkpoint reuse and
compiler specialization. Unused module members are outside the selected graph.
Module transport/aliasing, dynamic imports, class-held modules and paths through
non-module objects are outside the supported static member graph. Nested Python
code uses the same referenced-global census. Except for the finite `getattr`
data-field profile below, local import bytecodes, directly
captured `__import__`, `compile`, `delattr`, `dir`, `eval`, `exec`, `getattr`,
`globals`, `locals`, `setattr` and `vars` builtins (including aliases), and the
checked function/class namespace attributes refuse strict admission. These
checks do not establish universal reflection refusal.

The actual `getattr` builtin has one finite data-field profile: every use must
select public fields on an unrebound runtime parameter, directly or in one
comprehension over a captured immutable tuple/frozenset of field names. Literal
or captured immutable string selectors are also bound. An optional default
must be that same runtime parameter. The projection binds the actual builtin,
source, complete selectors and existing captured values; it never infers a
runtime type or descriptor identity from a list of declared output names.
Captured module reflection, dynamic field-name inputs, private namespace
selectors, rebinding and getter transport retain strict refusal. This permits
ordinary scientific output dematerialization while explicitly leaving arbitrary
runtime targets, descriptors and returned context capabilities unproved.
Python's function symbol table binds the no-rebinding premise, including
exception names, definitions, imports and pattern captures. Generic functions
with a separate type-parameter scope are outside this getter profile and refuse
through the existing typed identity boundary.

An opaque builtin can return a runtime namespace without exposing its selected
members to this graph. The real `sys._getframe().f_globals["math"]` checkpoint
counterexample retains the same source and Python version while a replaced
helper runs in the remaining consumer: unchanged result 7 becomes 107 and the
replacement writes a filesystem effect. This path is currently admitted; its
native regression test deliberately remains FAIL. B74 is therefore LIMITED.
The next B owner needs a generic declared dependency or typed refusal strategy
for builtin-returned context capabilities, rather than another helper-specific
patch. The static member and direct capability controls remain finite facts.

Builtin implementations retain the Python/distribution version boundary.
Installed external callables whose internals cannot be projected retain an
explicit opaque boundary binding their selected source/type/FQN and installed
version. This keeps existing numerical extension/JAX callables usable, but does
not establish their mutable internal state, transitive library code, external
effects or arbitrary runtime hot-reload. Replacing a selected member with a
source-readable Python helper still binds that actual helper. Unavailable
Python functions, hostile runtime mutation, wrapped functions, custom descriptors/metaclasses, callable
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

The writer returns the selected profile of the actual guarded persisted
manifest, using the existing CAS-owned profile projection. The reader retains
that full typed reference for both guarded manifest and blob reads; an
unprofiled content ID is not admitted as a runnable plan.

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
