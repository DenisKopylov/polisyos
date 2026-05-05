# Foundry Audit Remediation Plan

> Living plan for hardening and upgrading `polisyos.foundry` to uncompromising
> SOTA based on the current consolidated audit bundle.
> Created: 2026-04-09
> Status: active implementation and release-gate hardening
> Related docs: [Foundry Reference](reference/foundry/index.md),
> [Methods Catalog](reference/foundry/methods-catalog.md),
> [Archived Foundry SOTA Plan](archive/plans/FOUNDRY_SOTA_PLAN.md)

---

## Scope and Inputs

This document covers the full Foundry execution and methods surface:

- `src/polisyos/foundry/**`
- `src/polisyos/foundry/methods/**`
- `src/polisyos/foundry/agent_sim/**`
- `src/polisyos/foundry/calibration/**`
- `src/polisyos/foundry/uncertainty/**`
- `src/polisyos/foundry/data_plane/**`
- `tests/unit/foundry/**`
- Foundry-facing documentation, benchmarks, and runtime quality gates

This plan consolidates three audit streams:

- deep SOTA gap audit for Foundry and Methods Catalog;
- bug / antipattern / optimization audit;
- consolidated correctness / JAX / thread-safety / performance audit.

Working assumption:

- until Phase 2 closes, large new method families land only if they remove a
  P0/P1 blocker or are fully isolated behind a new backend with dedicated tests;

- Foundry should move to fail-closed semantics by default, with explicit
  research-mode escape hatches instead of silent degradation;

- catalog breadth is valuable, but runtime correctness, reproducibility, and
  numerical integrity are higher-order priorities.

---

## Executive Summary

Foundry already has unusually strong foundations:

- mature ABI concepts (`MethodSignature`, `SlotSpec`, units, metadata);
- layered compile/execute architecture;
- lazy registry and multi-backend dispatch;
- CRDT-style merge and determinism tiers;
- strong causal catalog relative to most OSS alternatives.

The current gap to uncompromising SOTA is not architectural immaturity; it is
concentrated in four areas:

1. correctness leaks in executor, snapshot, calibration, and agent-sim hot paths;
2. insufficient direct tests for low-level execution internals and merge rules;
3. missing frontier method families in Bayesian, SBI, neural, and advanced
   policy/causal inference;
4. weak observability, capability discovery, and cross-platform numerical
   reproducibility for production-grade operation.

A second-pass review over previously under-audited Foundry zones adds one more
important theme:

1. compile/runtime semantics and catalog truthfulness still contain legacy
   shortcuts that can silently weaken correctness or overstate implementation
   depth.

The core principle of this plan is simple:

- first eliminate silent wrong answers, silent fallbacks, race conditions, and
  JAX-invalid semantics;

- then harden tests, benchmarks, observability, and deterministic behavior;
- only then accelerate catalog expansion toward frontier Bayesian, causal,
  policy, and ML methods.

---

## Target State

Foundry should exit this plan with the following properties:

- executor is fail-closed by default and every degradation is explicit;
- merge, patching, snapshot, and persistence paths are directly unit-tested and
  property-tested;

- JAX paths are pure-functional and free of Python mutation, host round-trips,
  and traced-shape hazards;

- compile lowering applies declared mechanism defaults and never silently drops
  executable runtime semantics;

- numerical guards are centralized, documented, and consistent across domains;
- concurrency-sensitive registry, cache, reload, and circuit-breaker paths are
  race-safe;

- Bayesian inference has a production backend with HMC/NUTS and SBI support;
- frontier causal and policy methods close the most visible SOTA gaps;
- ML/neural methods can serve as nuisance models and agent-sim submodules;
- reproducibility includes cross-version / cross-platform golden numerical tests;
- catalog metadata distinguishes heuristic baselines, structural estimators, and
  production-grade trainable methods instead of collapsing them into one quality
  label;

- docs expose a machine-readable capability matrix and a method selection
  advisor instead of forcing users to infer applicability manually.

---

## Non-Negotiable Sequencing Rules

1. No major catalog expansion before P0 correctness blockers are closed.
2. No silent fallback in hot paths without structured telemetry and an explicit
   strictness mode.
3. No performance refactor without benchmark evidence on realistic Foundry loads.
4. No JAX optimization that removes CPU fallback or makes behavior opaque.
5. Every new method family must ship with capability metadata, tests, and
   method-selection hints.
6. Every snapshot / cache / reload change must include corruption and recovery
   tests, not just happy-path checks.

---

## Priority Ladder

| Tier | Horizon    | Objective                                            | Includes                                                                                                                  |
| ---- | ---------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| T0   | 1-2 weeks  | Stop correctness leakage and silent corruption       | executor fail-open paths, snapshot restore bugs, JAX-invalid mutation, double merge, NaN guards, PPO masking, cache races |
| T1   | 2-6 weeks  | Harden execution kernel and persistence              | direct tests for private executor modules, merge properties, snapshot recovery, constraints hardening, concurrency fixes  |
| T2   | 1-2 months | Stabilize numerics, performance, and reproducibility | epsilon policy, vectorization, memory bounds, JIT compatibility, benchmark ratchet, x86/ARM golden tolerance budget       |
| T3   | 2-4 months | Close core SOTA infra and method-platform gaps       | real kernel fusion, adaptive backend routing, capability matrix, method advisor, NumPyro backend, SBI                     |
| T4   | 4-8 months | Close frontier catalog gaps                          | proximal causal, QTE, interference CATE, neural nuisances, conformal under shift, mean-field games, policy macro stack    |

---

## Phase Roadmap

### Phase 0 - Program Freeze and Backlog Normalization

Duration: 3-5 days

Deliverables:

- normalize the audit bundle into one tracked backlog with severity, owner,
  module, and acceptance criteria;

- mark all fail-open behavior as debt, not convenience;
- freeze non-critical new method work until T0 closure;
- define benchmark fixtures and representative workloads for executor,
  agent-sim, uncertainty, and calibration;

- publish a release-gating checklist for Foundry-specific regressions.

Exit gate:

- every audit finding is mapped to a workstream in this document;
- P0 owner and target PR slice are assigned.

### Phase 1 - Correctness Emergency Train

Duration: 1-2 weeks

Deliverables:

- close the highest-risk wrong-answer and corruption bugs;
- switch key runtime paths from silent failure to structured failure reporting;
- fix JAX-invalid mutation and snapshot restore bugs;
- stop cache / reload / circuit-breaker race conditions that can corrupt state or
  break runtime guarantees.

Exit gate:

- all P0 items closed or explicitly waived with rationale;
- no known silent wrong-answer path remains in executor, snapshot, or core
  agent-sim loops.

### Phase 2 - Execution Kernel Hardening

Duration: 2-4 weeks

Deliverables:

- direct unit suites for private executor modules;
- merge property tests and corruption recovery tests;
- bounded-memory logging / failure buffers;
- deduplication of duplicated execution logic and explicit immutable execution
  state model.

Exit gate:

- private executor internals have direct tests and property-based regression
  coverage;

- merge and snapshot behavior is deterministic and fail-closed under corrupt
  input.

### Phase 3 - Numerical Stability and JAX Semantics

Duration: 2-3 weeks

Deliverables:

- centralized epsilon / tolerance policy;
- stable bounded transforms and Hessian conditioning semantics;
- vectorized constraint and quantile logic;
- removal of Python mutation, traced `int()` calls, dynamic-shape traps, and
  host round-trips from hot JAX paths.

Exit gate:

- calibration, agent-sim, and uncertainty hot paths pass JIT-compatibility and
  NaN/Inf stress tests;

- no known O(n) Python loops remain in top-path numeric kernels where vectorized
  alternatives exist.

### Phase 4 - Performance, Concurrency, and Reproducibility

Duration: 2-4 weeks

Deliverables:

- lock and lifecycle hardening for caches, registry, compiler, discovery, and
  circuit-breakers;

- benchmark ratchet for Monte Carlo, merge, agent population updates, and
  registry lookup;

- cross-platform golden snapshots for selected numerical outputs;
- OpenTelemetry and per-method cost attribution hooks.

Exit gate:

- representative perf baselines are measured and enforced;
- deterministic drift budget is defined for x86 vs ARM and for supported
  Python/JAX combinations.

### Phase 5 - Bayesian, UQ, and Calibration Frontier

Duration: 4-8 weeks

Deliverables:

- NumPyro-backed HMC/NUTS runner;
- SBI stack for likelihood-free inference;
- hierarchical Bayesian and BART support;
- shift-aware conformal and explicit epistemic/aleatoric decomposition;
- Bayesian calibration with Kennedy-O'Hagan style emulator path.

Exit gate:

- Foundry can perform posterior sampling, posterior predictive checks, and
  likelihood-free calibration on policy-sized problems without ad hoc adapters.

### Phase 6 - Causal, ML, Agent-Sim, and Policy Frontier

Duration: 6-12 weeks

Deliverables:

- proximal causal inference and distributional causal effects;
- neural nuisance bridge and selected tabular deep-learning models;
- interference-aware heterogeneous effects and mean-field / network extensions in
  agent-sim;

- policy-economics stack for sufficient statistics, optimal taxation, SVAR
  multipliers, and DSGE/HANK-oriented integration.

Exit gate:

- the top SOTA catalog gaps from the audit are closed in dependency order, with
  method metadata, docs, and tests.

---

## Immediate Fix List (P0)

These are the fixes that should land first, before broader refactors.

| ID    | Files                                              | Problem                                                                                                 | Required fix                                                                                               | Acceptance evidence                                                                           |
| ----- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| P0-01 | `agent_sim/state.py`, `analysis/distributional.py` | Gini metrics disagree and inactive agents bias inequality upward                                        | unify Gini semantics around active-agent filtering and shared helper usage                                 | regression tests for zero-inactive, mixed-active, and parity against `compute_gini_hard`      |
| P0-02 | `_executor_snapshots.py`                           | `from __future__ import annotations` breaks nested dataclass restore; scalar Python values are dropped  | resolve forward refs via real type hints; add scalar codec and explicit unsupported-type errors            | snapshot round-trip tests for nested dataclasses, scalars, forward refs, and corrupt payloads |
| P0-03 | `calibration/pure_executor.py`                     | Python mutation inside `jax.lax.scan` produces trace-only side effects                                  | replace nonlocal mutation with explicit immutable carry / outputs                                          | JIT and eager parity tests on patch records and mutating-node tracking                        |
| P0-04 | `agent_sim/population_executor.py`                 | `jnp.where` over Python-int leaves corrupts types; PRNG key reused across lifecycle stages              | split pytrees by numeric vs static leaves; split RNG keys per stage                                        | JIT compatibility tests over mixed leaf types and RNG independence checks                     |
| P0-05 | `execute/api.py`                                   | merged state delta is applied twice                                                                     | return and consume a single authoritative merged state from executor                                       | execution parity tests showing single merge path only                                         |
| P0-06 | `methods/cache.py`                                 | SQLite connection lifecycle is race-prone (`__del__`, `_get_conn`, validity checks)                     | remove destructor-close semantics; add explicit close and locking around connection lifecycle              | concurrency tests with repeated open/invalidate/restore under load                            |
| P0-07 | `methods/hot_reload.py`                            | reload version is bumped before invalidation, exposing stale state                                      | make reload transactional: stage -> invalidate -> swap -> version bump -> publish                          | hot-reload race tests and monotonic version visibility checks                                 |
| P0-08 | `agent_sim/rl.py`                                  | PPO advantage normalization mixes active and inactive agents                                            | mask both normalization and loss paths consistently                                                        | gradient parity tests for partially inactive populations                                      |
| P0-09 | `agent_sim/vfi.py`                                 | no hard iteration cap can hang execution                                                                | add `max_iterations`, divergence detection, and explicit failure mode                                      | convergence and non-convergence tests with bounded runtime                                    |
| P0-10 | `agent_sim/mpc.py`                                 | `jax.device_get()` in trainable path kills JIT and uncertainty branch is effectively dead               | keep everything device-native in trainable path; implement real uncertainty estimate or remove dead branch | JIT perf test and planner-behavior tests with non-zero uncertainty                            |
| P0-11 | `calibration/bijectors.py`                         | asymmetric / non-bijective epsilon handling around bounds                                               | rederive bounded transforms with symmetric stable forward/inverse maps                                     | boundary gradient tests and round-trip tests near both bounds                                 |
| P0-12 | `runtime/nan_guard.py`                             | fail-open behavior when slot missing or unexpected exception occurs                                     | fail-closed for missing slots; replace bare catches with typed error handling                              | `test_nan_guard` cases for missing slot, JAX API failure, NaN propagation                     |
| P0-13 | `methods/backends/circuit_breaker.py`              | HALF_OPEN allows multiple concurrent probes                                                             | reserve single probe atomically under lock                                                                 | multithreaded HALF_OPEN tests                                                                 |
| P0-14 | `agent_sim/training.py`                            | new executor object per episode causes JIT recompilation thrash                                         | reuse executor or compile once outside episode loop                                                        | training benchmark showing compile count collapse                                             |
| P0-15 | `calibration/report.py`                            | double-escaped regex rejects valid versions                                                             | fix regex and add schema-version validation tests                                                          | direct report validation tests                                                                |
| P0-16 | `_executor_graph.py`                               | broad `except Exception`, dead `RuntimeWarning` branch, nonlocal mutation, potential fail-open dispatch | introduce typed failure taxonomy, immutable pending-record handling, and fail-closed default               | executor failure semantics tests plus branch coverage on exception classification             |
| P0-17 | `analysis/distributional.py`                       | percent delta uses `abs(before)` and misreports negative-baseline changes                               | use signed semantics with explicit edge-case policy for debt / transfer scenarios                          | tests for negative-to-more-negative, negative-to-less-negative, and zero baseline             |
| P0-18 | `agents.py` and action routing paths               | fragile observation parsing and silent action-column fallback corrupt model inputs/outputs              | validate observation paths and action arity strictly                                                       | model-input validation tests and invalid-shape rejection tests                                |

---

## Additional Findings From Second-Pass Review

These findings come from a deeper pass over folders and files that were mostly
outside the first audit hotspot set.

| ID    | Files                                 | Problem                                                                                                                                                                                                  | Required fix                                                                                                                                                | Suggested priority |
| ----- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| D2-01 | `compile/_lowering.py`                | `_merge_effective_params()` iterates over `mechanism_spec.params` but never materializes defaults, so runtime mechanism defaults are silently ignored during lowering                                    | derive effective params from mechanism defaults first, then overlay binding overrides and intervention params; add regression tests for default propagation | P0                 |
| D2-02 | `agent_sim/graph_mechanisms.py`       | `NetworkLendingMechanism` credits borrower wealth and debt but never debits lender wealth, minting assets out of thin air                                                                                | redesign lending flow as balanced bilateral transfer with lender-side state updates and conservation tests                                                  | P0                 |
| D2-03 | `agent_sim/distributions.py`          | `DistributionConfig` defaults to `mode=HARD` but `use_approximate=True`, so nominally hard quantiles still route through stochastic approximation by default                                             | make exact behavior the default for `HARD`, and gate sampled quantiles behind an explicit approximate mode with telemetry                                   | P1                 |
| D2-04 | `mechanisms/labor.py`                 | `LaborMarketMechanism` reuses the same RNG key for employment and firm assignment, and has no preflight guard for `n_firms == 0` before `randint(..., maxval=n_firms)`                                   | split keys for independent draws and fail fast when firm cardinality is zero                                                                                | P1                 |
| D2-05 | `mechanisms/treasury.py`              | `build_treasury_plan()` stores `root_seed` but does not mix it into `node_salts` or `stream_salts`, so changing root seed does not change the actual treasury plan                                       | include `root_seed` in salt derivation and add replay-drift tests                                                                                           | P1                 |
| D2-06 | `calibration/preflight.py`            | `resolve_steps()` returns `0` when no targets are resolved, and `prepare_targets()` silently skips targets missing from `raw_targets` instead of failing or warning                                      | fail closed on empty target sets by default and validate target completeness before alignment                                                               | P1                 |
| D2-07 | `calibration/uncertainty_adapter.py`  | Hessian/Gaussian envelopes are labeled `is_heuristic_ci=False` and `gate_eligible=True` even when they are normal-approximation artifacts and may be non-identifiable                                    | mark these intervals heuristic by default, downgrade gate eligibility on weak identifiability, and expose uncertainty provenance explicitly                 | P1                 |
| D2-08 | `methods/backends/jax_runner.py`      | JAX runner does not inject `__seed__` into params while many methods rely on it, and it hardcodes `DeterminismTier.STRICT_CPU` regardless of actual device/runtime                                       | inject backend seed semantics consistently and derive determinism tier from runtime/device fingerprint instead of hardcoding                                | P1                 |
| D2-09 | `methods/backends/checkpointing.py`   | checkpoint writes are non-atomic (`JSON` before sidecars), checkpoint save/load failures are swallowed, and corrupt checkpoints silently degrade to `None`                                               | switch to temp-file + atomic rename, checksums/manifest validation, and structured checkpoint failure reporting                                             | P1                 |
| D2-10 | `compile/_graph.py`                   | `_slot_dependency_edges()` performs an O(n^2) writer-reader scan over mechanism nodes, which will not scale to large compiled graphs                                                                     | build slot writer/reader indices and derive edges by slot intersection instead of pairwise node scans                                                       | P2                 |
| D2-11 | `methods/base.py`                     | contract enforcement uses raw `eval()` for pre/post/invariant checks, creating an execution surface and opaque runtime cost inside method loading                                                        | replace string-eval contracts with validated AST predicates or compiled safe callables                                                                      | P2                 |
| D2-12 | `methods/catalog/ml/transformers.py`  | `TabularTransformerEstimator` is a random self-attention feature encoder plus ridge head, not a trainable FT-Transformer/TabTransformer-class implementation                                             | relabel as heuristic/random-feature baseline or replace with a true trainable tabular transformer backend                                                   | P2                 |
| D2-13 | `methods/selection_history.py`        | `record()` appends JSONL outside the store lock and `_append_jsonl()` swallows `OSError`, so auto-persist can silently lose or corrupt history under concurrent writers                                  | serialize persistence through a dedicated append lock or writer queue, rotate/validate JSONL, and surface persistence health explicitly                     | P1                 |
| D2-14 | `methods/components_bridge.py`        | `bootstrap_method_registry_from_components()` mutates the default resolution policy of the shared registry as a bootstrap side effect, creating global method-selection drift outside the bootstrap call | make resolution policy local to bootstrap/lookup or restore the previous policy after registration; add singleton-leak regression tests                     | P2                 |
| D2-15 | `methods/backends/adapters.py`        | `to_numpy()` catches any failure from `jax.device_get()` and may return the original tree unchanged, silently leaking JAX/device values across NumPy/Solver/Bayesian backend boundaries                  | fail closed on adaptation errors and only apply narrow fallback logic for explicitly supported scalar/array leaves                                          | P1                 |
| D2-16 | `methods/backends/bayesian_runner.py` | `BayesianRunner.is_available()` always returns `True` and execution is a NumPy RNG passthrough, so Foundry advertises a Bayesian backend even when no Bayesian inference stack is present                | gate availability on real backend dependencies and relabel the current implementation as an experimental stub until NumPyro-backed execution lands          | P1                 |
| D2-17 | `mechanisms/fiscal.py`                | `IncomeTax` applies `self.rate` directly while `TaxSubsidy` clamps to `[0,1]`, so out-of-domain rates can create negative taxes or >100% levies without validation                                       | enforce or validate fiscal rate domains consistently across public mechanisms and add out-of-range regression tests                                         | P2                 |
| D2-18 | `methods/backends/chain_executor.py`  | fused JAX result construction hardcodes `DeterminismTier.STRICT_CPU`, so heterogeneous fused chains can overclaim reproducibility guarantees on non-CPU or non-strict executions                         | derive determinism tier from actual runtime/device fingerprint and propagate it through fused result metadata                                               | P1                 |

Cross-cutting verification gaps found during this pass:

- `agent_sim/graph_mechanisms.py` has no obvious dedicated direct test coverage;
- `agent_sim/jit_training.py` lacks direct focused test suites despite being a
  high-risk JAX training path;

- `methods/backends/checkpointing.py` relies heavily on indirect coverage and
  should get corruption/recovery tests;

- `mechanisms/labor.py` and `mechanisms/treasury.py` need direct semantic tests,
  not only incidental integration exposure.

- `tests/unit/foundry/methods/test_selection_v2.py` exercises thread safety only for
  in-memory history, not persisted concurrent JSONL append;

- `tests/architecture/test_components_bridge.py` and
  `tests/unit/foundry/methods/test_components_bootstrap_adapter.py` do not assert
  that bootstrap leaves registry default-policy behavior unchanged;

- `tests/unit/foundry/methods/backends/test_backends.py` validates Bayesian
  passthrough behavior, not backend dependency truthfulness or availability
  gating;

- `tests/unit/foundry/mechanisms/test_fiscal.py` covers nominal tax/subsidy rates only and does
  not constrain out-of-domain fiscal parameter behavior;

- fused-chain and JAX-runner tests do not currently enforce that reported
  determinism tiers match actual runtime/device posture.

---

## Workstreams

### WS-1 Correctness and Fail-Closed Runtime

Purpose:

- eliminate silent wrong answers, silent skips, and ambiguous runtime states.

Audit findings covered:

- broad exception swallowing in `_executor_graph.py`, `runtime/nan_guard.py`,
  `methods/cache.py`, `methods/registry.py`, `plan_optimizer.py`,
  `dispatch.py`, `calibrator.py`, `_executor_snapshots.py`;

- stale mechanism lookup / `mechanism_type=None` crash risk;
- duplicated execution logic for `op` and `mechanism` nodes;
- frozen dataclass mutation via `object.__setattr__`;
- silent lifecycle no-op on invalid transition;
- selector / observation parsing and action routing silent fallbacks;
- fail-open NaN guard and schema overwrite without warning;
- compile lowering that drops mechanism defaults;
- graph mechanisms that violate conservation semantics;
- runtime backend seed propagation that diverges from reproducibility metadata;
- backend adaptation layers that can fail open and silently leak device-native
  state across backend boundaries.

Primary files:

- `_executor_graph.py`
- `_executor_models.py`
- `_executor_ops.py`
- `_executor_patching.py`
- `runtime/nan_guard.py`
- `methods/exceptions.py`
- `methods/lifecycle.py`
- `methods/slot_schema.py`
- `agents.py`
- `methods/backends/adapters.py`

Required changes:

- add a typed failure taxonomy and strictness modes;
- make `execute_program_graph()` return structured degradation artifacts instead
  of silently skipping work;

- replace ambiguous fallbacks with explicit validation errors;
- deduplicate mechanism/op dispatch or extract a shared execution kernel;
- remove mutation of frozen runtime models in hot paths;
- add context-rich exceptions for path traversal, selector coercion, and
  invalid lifecycle transitions;

- make backend-boundary adaptation fail closed, with typed diagnostics instead
  of silent host/device leakage.

Tests and acceptance:

- expand `tests/unit/foundry/runtime/test_executor_fail_semantics.py`;
- add direct unit tests for node dispatch and failure classification;
- ensure all unexpected executor failures include node id, method FQN, and slot
  context;

- no bare `except Exception` or `except:` remains in executor hot paths unless
  rethrown with telemetry.

### WS-2 Executor, Merge, Snapshot, and Persistence Hardening

Purpose:

- make low-level state transformation deterministic, test-dense, and recoverable
  under corruption.

Audit findings covered:

- zero direct tests for `_executor_graph.py`, `_executor_ops.py`,
  `_executor_patching.py`, `_executor_snapshots.py`, `_executor_models.py`,
  `_execution_posture.py`;

- missing merge tests for >3 writers, type mismatches, commutativity, and
  idempotence;

- missing corrupt snapshot, partial write, and large-state serialization tests;
- snapshot recursion / eager load problems;
- nested dataclass restore and scalar persistence bugs;
- checkpoint persistence that is non-atomic and degrades silently on load/save failures.

Primary files:

- `_executor_graph.py`
- `_executor_ops.py`
- `_executor_patching.py`
- `_executor_snapshots.py`
- `_executor_models.py`
- `_execution_posture.py`
- `test_merge_determinism.py`
- `test_merge_engine_regressions.py`

Required changes:

- introduce private-module unit suites instead of relying almost entirely on
  `test_executor_runtime_semantics.py`;

- add Hypothesis-driven merge properties for commutativity, associativity where
  applicable, and idempotence;

- add explicit snapshot format versioning, checksum, and two-phase write;
- support forward-ref type resolution and scalar codecs in snapshot restore;
- replace deep recursive flattening with iterative traversal for large states;
- avoid eager full materialization when loading large NPZ snapshots.

Tests and acceptance:

- new focused tests for corrupt snapshot recovery and partial writes;
- randomized concurrent-writer merge tests;
- large-state round-trip tests with bounded memory;
- executor internals reach direct line coverage target of at least 90%.

### WS-3 Concurrency, Cache, Reload, and Registry Safety

Purpose:

- remove race conditions and lifecycle ambiguity from long-running Foundry
  processes.

Audit findings covered:

- SQLite connection races in `methods/cache.py`;
- cache validity query without lock;
- double-checked locking on registry lazy factory load;
- global cache invalidation by replacement in `methods/compiler.py`;
- `_loaded_modules` mutation without lock in discovery;
- inflight compile race window;
- unsafely shared `@lru_cache` state in dispatcher;
- reload version visibility without lock;
- module class substitution and root-module globals mutation hazards;
- selection-history auto-persist append races and silent telemetry loss;
- component bootstrap mutating shared registry resolution policy as a side
  effect.

Primary files:

- `methods/cache.py`
- `methods/registry.py`
- `methods/compiler.py`
- `methods/hot_reload.py`
- `methods/backends/dispatch.py`
- `foundry/__init__.py`
- `methods/selection_history.py`
- `methods/components_bridge.py`

Required changes:

- convert cache lifecycle to explicit context-managed ownership;
- audit every read/write path touching shared mutable registry/cache state;
- replace destructive cache swaps with generation-based invalidation tokens;
- make hot reload a transactional publication step;
- bound audit/event logs with ring buffers or rotating sinks;
- cache dynamic imports at registration time instead of property access in loops;
- serialize persisted selection-history writes or centralize them behind a
  dedicated writer;

- eliminate bootstrap-time mutation of shared registry selection policy;
- document and test thread-safety guarantees explicitly.

Tests and acceptance:

- concurrency stress tests for cache open/close/invalidate/restore;
- reload and registry tests with parallel readers/writers;
- persisted selection-history append stays valid under concurrent writers;
- component bootstrap leaves pre-existing registry default policy unchanged
  unless explicitly requested;

- no process-global profiler toggle in concurrent test mode;
- audit/event memory growth is bounded.

### WS-4 Numerical Stability, Constraints, and Calibration Math

Purpose:

- remove numerically unstable transforms and inconsistent semantics across
  calibration, constraints, distributional metrics, and policy losses.

Audit findings covered:

- asymmetric bijectors and non-bijective epsilon handling;
- damping order in Hessian repair;
- clipped condition number diagnostics;
- `exp(log_std)` overflow and `log(variance)` underflow in actor-critic;
- `gamma -> 0` divide-by-zero in CARA utility;
- inconsistent epsilon use across graph and reward code;
- silent NaN propagation in losses and constraints;
- invalid quantile parameter handling;
- precision loss from `numpy -> float -> str -> Decimal` round-trips;
- zero-weight normalization failure;
- phantom inequality / hardcoded normalization / overflowing penalties;
- negative-baseline percent-delta semantics;
- calibration uncertainty envelopes whose semantics are overconfident relative to
  their Hessian/Gaussian approximation basis;

- public fiscal mechanisms with inconsistent parameter-domain enforcement.

Primary files:

- `calibration/bijectors.py`
- `calibration/hessian.py`
- `calibration/loss.py`
- `constraints_engine.py`
- `agent_sim/actor_critic.py`
- `agent_sim/rewards.py`
- `analysis/distributional.py`
- `loss.py`
- `mechanisms/fiscal.py`

Required changes:

- centralize numeric guardrails and epsilon policy by domain;
- replace ad hoc bounded transforms with stable, symmetric parameterizations;
- validate quantile and weighting parameters at the boundary, not deep in NumPy;
- add NaN/Inf fail-closed behavior before aggregation and Decimal conversion;
- standardize economic metric semantics for zero, negative, and debt-like values;
- validate policy/mechanism parameter domains at public entrypoints instead of
  assuming upstream callers already clamped them;

- publish numeric invariants in tests and docs.

Tests and acceptance:

- extend `tests/unit/foundry/calibration/test_bijectors.py`,
  `test_hessian.py`, `test_loss.py`, and `test_measurement.py`;

- add constraints NaN and invalid-parameter regression tests;
- stress-test actor-critic parameter extremes and zero-agent edge cases;
- add fiscal rate boundary tests covering negative and >1.0 rate inputs;
- document tolerances and expected failure modes.

### WS-5 JAX Semantics, Performance, and Memory Discipline

Purpose:

- remove patterns that are technically valid in eager Python but invalid,
  misleading, or catastrophically slow under JAX and production workloads.

Audit findings covered:

- Python mutation inside `lax.scan`;
- `device_get()` in trainable path;
- Python loops over quantile grids and elementwise Decimal checks;
- unbounded lists for MC samples, failure cards, and audit logs;
- Sobol chunk regeneration with O(n^2) cost;
- scatter-heavy population update loops;
- O(n^2) soft sort / soft rank memory behavior;
- lazy imports in hot loops;
- warmup double-scan behavior;
- `array.tolist()` and other host materialization in data-plane paths;
- traced `int()` / dynamic shape patterns in graph code and training;
- compile graph edge construction with quadratic slot-dependency scans;
- misleading `HARD` distribution defaults that still use stochastic approximate quantiles;
- fail-open JAX-to-host adaptation in backend boundary utilities.

Primary files:

- `calibration/pure_executor.py`
- `uncertainty/monte_carlo.py`
- `agent_sim/analysis.py`
- `agent_sim/population.py`
- `data_plane/bindings.py`
- `_executor_graph.py`
- `runtime/__init__.py`
- `agent_sim/training.py`
- `agent_sim/graphs.py`
- `methods/backends/adapters.py`

Required changes:

- convert mutation-heavy kernels to pure-functional carries and outputs;
- vectorize quantile and transition accounting;
- preallocate or chunk MC/QMC storage deterministically;
- replace sequential scatter patterns with `vmap` or batched transforms where
  semantically valid;

- remove unnecessary host round-trips from training and binding paths;
- make backend adaptation explicit and fail closed when JAX-to-host conversion
  fails unexpectedly;

- bound all runtime-side in-memory telemetry structures.

Tests and acceptance:

- extend `tests/unit/foundry/agent_sim/test_jit_compatibility.py`;
- add performance regression suites for Monte Carlo, quantile mapping, and
  population stepping;

- no known JIT-only semantic divergence remains in core agent-sim/calibration
  loops;

- benchmark results are stored and compared over time.

### WS-6 Test Architecture and Benchmark Ratchet

Purpose:

- raise confidence in low-level correctness and make performance regressions
  visible before they land.

Audit findings covered:

- no unit tests for executor internals;
- no unit tests for `fiscal.py`, `labor.py`, `treasury.py`;
- weak coverage in spatial, ML, and several infra modules;
- deferred benchmark domains for Bayesian, optimization accuracy, and survey
  accuracy;

- missing numerical snapshot testing across Python/JAX versions;
- no dedicated direct test suites for `agent_sim/jit_training.py`,
  `agent_sim/graph_mechanisms.py`, and checkpoint corruption/recovery paths.

Primary surfaces:

- `tests/unit/foundry/**`
- benchmark tooling under `tools/research/benchmarks/**`
- Foundry golden fixtures under `tests/unit/foundry/golden/**`

Required changes:

- add direct unit suites for all private executor modules;
- create domain packs for fiscal/labor/treasury mechanisms;
- add fuzz/property tests for constraints, merge, bindings, and slot schemas;
- expand goldens to cross-version and cross-platform numerical checks;
- restore deferred benchmark domains and make them part of release gating;
- ratchet coverage by domain instead of only by global percentage.

Suggested minimum targets:

- executor internals: >= 90%
- core mechanisms: >= 85%
- Bayesian methods: >= 80%
- ML methods: >= 70%
- spatial methods: >= 75%
- `trace.py`, `queue.py`, `specs.py`, `profiles.py`: non-zero direct coverage

Exit gate:

- Foundry release gate includes correctness, fuzz/property, and performance
  evidence instead of only broad integration smoke.

### WS-7 Methods Infrastructure and Catalog Ergonomics

Purpose:

- make the method platform itself production-grade, not just the individual
  methods living inside it.

Audit findings covered:

- kernel fusion detected but not executed;
- static backend dispatch without runtime cost model;
- no auto-batching for small JAX calls;
- limited type/effect tracking in composition;
- hot reload without sandboxed diff/update semantics;
- shallow snapshot exposure from registry;
- missing machine-readable capability matrix;
- missing method selection advisor;
- insufficient distinction between heuristic baselines and production-grade
  implementations in catalog metadata and docs;

- component bootstrap changing shared registry selection behavior.

Primary files:

- `methods/plan_optimizer.py`
- `methods/backends/dispatch.py`
- `methods/composer.py`
- `methods/registry.py`
- `methods/hot_reload.py`
- `reference/foundry/methods-catalog.md`

Required changes:

- implement real fusion / batching, not placeholder detection only;
- add runtime profile-driven JAX vs NumPy selection;
- extend method metadata with effect, shape, and dependency semantics where
  feasible;

- publish immutable registry snapshots instead of shallow mutable views;
- make hot reload diff-based and sandboxed;
- add a catalog truthfulness rubric so random-feature baselines, structural
  scoring methods, and frontier trainable implementations are not presented as
  equivalent depth;

- decouple component bootstrap from global registry-policy mutation;
- generate a machine-readable capability matrix and expose a method advisor for
  planners and docs.

Exit gate:

- Foundry can answer "which methods apply to my problem?" with code, not only
  with prose or tribal knowledge.

### WS-8 Bayesian, Uncertainty Quantification, and Calibration Frontier

Purpose:

- close the weakest frontier domain gaps identified in the audit.

Audit findings covered:

- missing HMC/NUTS, EP, SVGD, normalizing flows, SBI, hierarchical Bayes, BART,
  factor graphs;

- shift-aware conformal gaps;
- no explicit uncertainty decomposition;
- no calibrated interval stack or value-of-information analysis;
- no multi-fidelity UQ;
- no Kennedy-O'Hagan, history matching, ABC, multi-output, or robust
  calibration;

- Bayesian backend surface that overclaims availability relative to actual
  installed inference stack and runtime semantics.

Primary files and surfaces:

- `methods/bayesian/**`
- `methods/catalog/bayesian/**`
- `uncertainty/**`
- `calibration/**`
- `bayesian_runner.py` protocol integration points

Required changes:

- add NumPyro-backed sampling runner with HMC/NUTS as the first-class backend;
- make Bayesian backend health/availability reflect actual installed samplers,
  not a generic passthrough implementation;

- add SBI interfaces (NPE/NLE/NRE) for likelihood-free policy problems;
- support hierarchical partial pooling and BART for policy heterogeneity;
- add weighted/adaptive conformal under distribution shift;
- introduce epistemic/aleatoric decomposition contract;
- add Bayesian calibration flows with emulator support and posterior diagnostics.

Exit gate:

- Bayesian and UQ methods are no longer the weakest link in the catalog.

### WS-9 Causal, ML, Agent-Sim, and Policy Frontier

Purpose:

- close the highest-value method-family gaps after runtime hardening is done.

Audit findings covered:

- proximal causal inference;
- QTE / unconditional distributional treatment effects;
- causal offline RL / stronger OPE;
- multi-violation sensitivity analysis;
- rate-optimal nuisance handling for DML;
- causal representation learning;
- interference-aware heterogeneous effects;
- moment-inequality partial identification;
- staggered DiD with continuous treatment;
- FT-Transformer / TabNet and neural nuisance models;
- foundation-model policy analysis pipeline;
- GNN, Neural ODE/SDE, self-supervised representation learning;
- mean-field games, mechanism design, coalition formation, bounded rationality,
  social learning, Krusell-Smith, continuous-time agents;

- sufficient-statistics welfare, optimal taxation, fiscal multipliers, DSGE/HANK,
  political economy, behavioral public finance.

Required sequencing:

1. proximal causal inference
2. SBI and neural nuisance bridge
3. QTE / distributional causal effects
4. interference and network-aware CATE
5. mean-field / heterogeneous-shock agent extensions
6. policy macro and public-finance modules

Exit gate:

- the audit's Tier 1 and Tier 2 catalog blockers are closed in dependency order,
  with method metadata, tests, docs, and runnable examples.

### WS-10 Observability, Reproducibility, and Documentation

Purpose:

- make Foundry diagnosable, reproducible, and discoverable as a production
  computational system.

Audit findings covered:

- no method-level OpenTelemetry spans;
- no production per-method cost attribution;
- no deterministic floating-point story across x86/ARM;
- no numerical snapshot matrix across Python/JAX versions;
- no machine-readable capability matrix;
- no automated method selection advisor;
- reproducibility metadata that can disagree with actual seed propagation and
  treasury salt derivation;

- determinism metadata hardcoded to `STRICT_CPU` in JAX/fused paths even when
  actual runtime posture differs;

- backend availability claims that can disagree with installed runtime stacks.

Primary surfaces:

- `runtime/**`
- `methods/backends/**`
- `profiler.py`
- Foundry docs under `docs/reference/foundry/**`

Required changes:

- add per-method tracing hooks and run-level cost attribution;
- define deterministic mode, tolerance budgets, and replay semantics;
- add cross-platform numerical goldens to CI or scheduled acceptance runs;
- generate and publish capability metadata as tracked artifact;
- derive determinism tiers and backend availability from runtime fingerprints
  and installed capabilities instead of hardcoded labels;

- expose a CLI or docs-assisted advisor for method selection.

Exit gate:

- an operator can explain what Foundry ran, how much it cost, why it degraded,
  and which methods were applicable without reading source code.

---

## 90-Day Delivery Slices

| Window     | Outcome                       | Must ship                                                                                                                                                                                                                                                  |
| ---------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Days 0-30  | Correctness stabilization     | P0 fixes, fail-closed executor semantics, snapshot restore fix, cache/reload race fixes, direct executor unit tests started                                                                                                                                |
| Days 31-60 | Hardening and reproducibility | merge properties, snapshot corruption recovery, checkpoint atomicity, selection-history persistence hardening, fail-closed backend adaptation, vectorized constraints/quantiles, bounded logs, reproducibility metadata truthfulness, x86/ARM drift budget |
| Days 61-90 | First frontier unlock         | NumPyro HMC/NUTS backend, SBI v1, proximal causal v1, neural nuisance bridge v1, capability matrix and advisor v1                                                                                                                                          |

---

## Suggested PR Slicing

1. `executor-fail-closed-and-gini-fixes`
2. `snapshot-roundtrip-and-corruption-recovery`
3. `cache-reload-registry-selection-history-hardening`
4. `agent-sim-jax-semantics-and-training-compile-fix`
5. `constraints-and-calibration-numeric-stability`
6. `merge-property-tests-and-private-executor-unit-suites`
7. `backend-metadata-truthfulness-and-cross-platform-goldens`
8. `numpyro-backend-hmc-nuts`
9. `sbi-and-neural-nuisance-bridge`
10. `proximal-causal-and-distributional-effects`
11. `capability-matrix-and-method-advisor`

The point of this slicing is not ceremony; it is to keep risky runtime changes
small enough that regressions can be localized quickly.

---

## Traceability Matrix

Every major audit block maps to at least one workstream in this plan.

| Audit block                                                                                                 | Covered by        |
| ----------------------------------------------------------------------------------------------------------- | ----------------- |
| Executor fail-open semantics, duplicated dispatch, snapshot persistence, merge edge cases                   | WS-1, WS-2        |
| Cache, registry, compiler, hot reload, discovery, circuit-breaker thread safety                             | WS-3              |
| Bijectors, Hessian, constraints NaN handling, distributional deltas, actor-critic stability                 | WS-4              |
| JAX mutation, host round-trips, Sobol O(n^2), scatter-heavy loops, traced ints, warmup duplication          | WS-5              |
| Missing direct tests, mechanism test gaps, weak domain coverage, deferred benchmarks                        | WS-6              |
| Kernel fusion placeholder, static dispatch, capability matrix gap, method advisor gap                       | WS-7, WS-10       |
| Compile lowering default-drop bugs, compile graph scaling, seed semantics, treasury plan drift              | WS-1, WS-5, WS-10 |
| Checkpointing atomicity and silent checkpoint degradation                                                   | WS-2, WS-3        |
| Calibration target completeness and heuristic CI labeling                                                   | WS-4, WS-10       |
| Catalog depth mismatch between heuristics and true trainable methods                                        | WS-7, WS-9        |
| Selection-history persistence races and bootstrap-time registry-policy leakage                              | WS-3, WS-7        |
| Fail-open backend adaptation and hardcoded fused/JAX determinism metadata                                   | WS-1, WS-5, WS-10 |
| Bayesian backend availability/capability overclaim relative to actual inference stack                       | WS-8, WS-10       |
| Public fiscal parameter-domain guard gaps                                                                   | WS-4              |
| Bayesian backend weakness, SBI absence, conformal-under-shift, Bayesian calibration gaps                    | WS-8              |
| Proximal causal, QTE, multi-bias sensitivity, interference CATE, continuous-treatment DiD                   | WS-9              |
| Neural nuisance models, tabular DL, GNN, Neural ODE/SDE, representation learning                            | WS-9              |
| Mean-field games, mechanism design, coalition formation, social learning, continuous-time agents            | WS-9              |
| Sufficient statistics, optimal taxation, SVAR multipliers, DSGE/HANK, political economy, behavioral finance | WS-9              |
| OpenTelemetry, cost attribution, x86/ARM determinism, numerical goldens, docs discoverability               | WS-10             |

---

## D1 Docs Impact Table

| D1 doc cluster                              | Exact files                                                                                                                                                                                                                                                                                                                                             | Source of truth                                                                                                              | Validation command or evidence                                                                                                                                                                                                                                                      | Backlog / priority |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| Foundry reference set                       | `docs/reference/foundry/index.md`, `docs/reference/foundry/compile-execute.md`, `docs/reference/foundry/calibration.md`, `docs/reference/foundry/methods-catalog.md`, `docs/reference/foundry/frontier-methods.md`, `docs/reference/foundry/observability-reproducibility.md`, `docs/reference/foundry/agent-sim.md`, `docs/reference/foundry/state.md` | `polisyos.foundry` facade, compile/execute APIs, calibration and methods subsystems, runtime fingerprints, agent-sim modules | `uv run pytest tests/unit/foundry/facade/test_quickstart.py tests/unit/foundry/compile/test_compile_determinism.py tests/unit/foundry/runtime/test_execute_input_bindings.py tests/unit/foundry/runtime/test_nan_guard_public.py tests/unit/foundry/calibration/test_measurement.py tests/unit/foundry/methods/backends/test_numerical_stability.py -q` | none               |
| Explanation, how-to, and benchmark surfaces | `docs/explanation/causal-engine.md`, `docs/how-to/run-causal-analysis.md`, `docs/how-to/run-benchmarks.md`, `docs/benchmarks/confidential-computing-overhead.md`                                                                                                                                                                                        | causal-engine architecture notes, benchmark suite registry, current benchmark commands, measurement methodology              | `uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -q`                                                                                                                                                                                                                    | none               |
| Package boundary READMEs                    | `src/polisyos/foundry/README.md`, `src/polisyos/foundry/methods/README.md`, `src/polisyos/foundry/calibration/README.md`, `src/polisyos/foundry/agent_sim/README.md`                                                                                                                                                                                    | package facades, catalog/method boundaries, calibration loops, agent-sim runtime boundary                                    | runnable quickstart in `docs/reference/foundry/index.md` plus the package-local pytest slices referenced from each README                                                                                                                                                           | none               |

D1 closure note: all required D1-L3 pages are present. A dedicated generated
capability-matrix page remains a P2 D2 enhancement, not a D1 blocker.

## Definition of Done for "Foundry SOTA"

Foundry should not be described as SOTA-ready until all of the following are
true:

- no open P0 or P1 correctness issues remain in executor, snapshot, calibration,
  uncertainty, or agent-sim core loops;

- fail-closed is the default runtime posture, with explicit research-mode
  override only where necessary;

- private executor internals, merge semantics, and snapshot recovery are directly
  tested, not only indirectly exercised;

- cross-platform numerical drift is measured and bounded;
- Bayesian inference includes production posterior sampling and SBI support;
- at least the Tier 1 catalog gaps from the audit are closed:
  proximal causal inference, HMC/NUTS, SBI, real kernel fusion / adaptive
  backend routing, and execution hardening;

- method capability metadata is machine-readable and powers an advisor path;
- operator observability covers per-method timing, degradation, and cost;
- benchmark and golden regression suites are part of release acceptance.

Until then, the honest status is:

- architecturally strong;
- method-rich in several domains;
- not yet uncompromisingly reliable enough to claim full SOTA without caveats.
