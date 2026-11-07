# Foundry Method Compiler

`polisyos.foundry.methods.compiler` owns method compilation and hot-reload
cache invalidation. Slot-layout types and builders belong to
`polisyos.ir.kernel.slots`.

## Home

- `__init__.py` is the canonical `MethodCompiler` and `CompilationCache` API.
- `plan_optimizer.py` turns method DAGs into backend-aware execution plans.
- `layout.py` retains the legacy import address for IR-owned slot-layout types
  and builders. First-party compiler callers import the IR owner directly.
- `specialization.py` builds deterministic specialization keys for compiled variants.
- `hot_reload.py` owns source watching and generation invalidation helpers.

## Layout Compatibility

`polisyos.foundry.methods.layout` is the direct Foundry compatibility facade;
`polisyos.foundry.methods.compiler.layout` is the legacy compatibility alias.
Both import the same three types and two builders directly from
`polisyos.ir.kernel.slots`. Neither address introduces a second layout owner
or requires a caller to traverse the other module.

Both nested addresses are internal under the
[public-surface contract](../../../../../architecture/public_surface/contract.toml).
Existing compatible callers can continue to use either address. Foundry owners
maintain these bindings; a separate tracked lifecycle decision must migrate
remaining callers and references, preserve the identity tests, and record
compatibility and release notes before removing either address. This change
sets no removal date and adds no public-stable entrypoint.

## Authoring Rules

- Keep compilation deterministic and keyed by explicit specialization state.
- Do not register methods from compiler code; registration belongs in
  `selection/registry.py` and catalog family bootstrap modules.
- Optional runtime integrations must degrade gracefully when dependencies are
  unavailable.
- Compiler methods accept registered, generically erased `FoundryMethod` classes
  and previously supported structural `FoundryMethodProtocol` classes. The
  registry continues to accept specialized state and parameter types. Kernel
  compilation consumes the declared signature and the class's `pure_step`;
  neither typing path changes the runtime method or its admission.

## Compiled chain context boundary

`MethodCompiler.compile_chain()` replays the canonical composer validation before
compilation. `CompiledChainExecutor.__call__()` replays it again and reconciles
the bound compiled method occurrences, signatures and static specialization with
that plan before executing. Unknown, erased or inconsistent validation refuses.
The executor exposes `warnings` and typed `validation_context` properties, so a
reusable handle retains the actual compiler limitations, including mode OFF.

The existing call contract still returns raw state. That raw value has no
`ChainExecutionResult` diagnostic envelope and must not be described as carrying
warnings or compiler provenance. Consumers needing a transferable contextual
result must retain the executor's diagnostic surface or use the heterogeneous
chain result API. A new raw-state diagnostic envelope and full DAG slot-routing
adaptation for compiled kernels are `surface_out_of_scope` for this compatible
companion; no such capability or custody claim is made. Compiler validation
proves current mechanical checks, not scientific or institutional authority.

## Selected executable and cache scope

The JAX runner compiles the actual method class selected by its caller, including
when the caller explicitly supplies an isolated registry. Ambient `registry_scope()`
default selection is a separate concern. The compiler and fused runtime caches
bind an in-process entry to that class, the admitted signature digest and its
captured `pure_step` callable (including a Python code-object identity). Strong references prevent a reused
object address from reviving an unrelated entry. Opaque non-Python callables are
not reused. These bindings are process-local; they do not alter the deterministic
`Specialization.cache_key` or claim source provenance. Mutable globals, closure
cells and externally mutable dependencies are not frozen by this identity.

An unqualified `CompilationCache.get(spec)` returns the sole matching entry,
or `None` when several implementations match. Public `put` preserves a bound
handle's implementation identity; `invalidate(spec)` clears all matching
implementation variants. Compiler code requests its exact variant.
An unqualified sole-entry lookup is an inspection result, not proof of which
method a caller selected. The binding does not freeze a previously returned
handle against concurrent in-place code, global, or closure mutation.
Callers supplying a custom compiler remain responsible for its implementation;
an unbound returned handle refuses at the JAX runner, but a self-attested field
is not independent proof against a malicious compiler override.

Before a fused pair, both selected classes must match the compiled signatures;
the already selected first class is passed to input preparation rather than
re-resolved. Async preparation and Ray submission use the same signature
predicate. Ray runtime verification is separately required.

## Preparation and actual JAX specialization

Chain preparation propagates declared shapes as data-only `ShapeSpec` values.
`SlotSpec` has no output-dtype declaration, so those derived inputs carry
`dtype="unknown"`; preparation neither borrows a stale sample/input dtype nor
allocates output-sized NumPy placeholders. Unknown data-dependent dimensions
still refuse before any method body runs.

The prepared object contains a reusable lazy JAX wrapper. Its planning
specialization is not an already lowered machine executable: JAX traces and
specializes using the actual whole-state arrays when called, including an
upstream result whose dtype differs from the original sample. Explicit
trace/lower/compile and warmup calls are separate work and are reported
separately from wrapper construction. This does not add general slot routing,
an output-dtype inference engine, or safe tracing for arbitrary impure methods.

A leader also rechecks the cache after claiming a new flight. If an earlier
flight published between miss and claim, the new leader republishes the ready
kernel through the normal generation-guarded terminal path, releasing followers
with their own current dynamic defaults instead of building another wrapper.
