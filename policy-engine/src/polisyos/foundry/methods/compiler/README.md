# Foundry Method Compiler

`polisyos.foundry.methods.compiler` owns method compilation, slot layout, and
hot-reload cache invalidation.

## Home

- `__init__.py` is the canonical `MethodCompiler` and `CompilationCache` API.
- `plan_optimizer.py` turns method DAGs into backend-aware execution plans.
- `layout.py` owns slot-family layout manifests used by compile-time contracts.
- `specialization.py` builds deterministic specialization keys for compiled variants.
- `hot_reload.py` owns source watching and generation invalidation helpers.

## Authoring Rules

- Keep compilation deterministic and keyed by explicit specialization state.
- Do not register methods from compiler code; registration belongs in
  `selection/registry.py` and catalog family bootstrap modules.
- Optional runtime integrations must degrade gracefully when dependencies are
  unavailable.

## Compilation identity and chain inputs

`MethodCompiler` keys its immutable kernels by the current method ABI and the
shared artifact implementation-identity projection, as well as static parameters,
input shape/dtype and backend configuration. Changing a same-FQN implementation
or supported helper descriptor selects another kernel. Current dynamic defaults
bind a separate handle to that kernel. An already traced JAX handle retains its
traced computation; an untraced handle refuses source drift before tracing.
Plain Python execution checks the same identity before each body call.

The source projection has the finite supported Python graph described in
`../artifacts/README.md`. Mutable captures, unknown function source and unsupported
dynamic descriptors raise `CompilationError`; module/distribution versions do
not establish mutable module contents or external-effect identity. Low-level
`build_specialization()` callers may omit `implementation_hash` for compatibility,
but that profile does not establish source-bound reuse.

The cache reconciles a ready entry and its generation while claiming a shared
flight. A peer that publishes between the first miss and the claim is reused.
Publication and follower wakeup share the generation lock. Cooperative follower
timeout/cancellation does not cancel a leader's physical compilation.

Compiled chains use the sequential executor's canonical input materializer,
parameter merge and context merge. The backend facade's
`collect_chain_node_inputs` and `merge_chain_execution_context` are internal
delegations to those existing owners, not a second payload algorithm or stable
external API. Bound outputs remain occurrence-keyed. Per-occurrence UUID dynamic
overrides take precedence over FQN overrides; static overrides require
recompilation.

Shape preparation propagates declared output shapes through actual compiled
bindings without running a scientific body. Unknown data-dependent bound shapes
are refused. Declared downstream dtype is provisional: execution reconciles the
actual materialized shape/dtype and selects its corresponding cached kernel before
the body. Warmup explicitly executes numerical steps and is distinct from this
preparation. This contract does not implement parallel DAG execution, checkpoint
resume, automatic retry or exactly-once external effects.
