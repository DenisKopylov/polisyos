# Search Strategies (`polisyos.scientist.methods.search.strategies`)

`search.strategies` contains candidate generators and runtime helpers for
sample-efficient policy search, from basic random/grid variants to optional
Bayesian and multi-objective methods.

## Role in the system

- **Depends on:** `search`, with optional `torch`/`botorch`/`gpytorch` dependencies
- **Used by:** `SearchController`, policy-design optimization loops
- The package separates the parameter space and candidate generation from the orchestration code in `search.controller`.

## Key concepts

- **SearchStrategy** — base protocol for candidate generators.
- **SearchSpace + codecs** — parameter definitions and conversion to runtime form.
- **Deterministic baselines** — `RandomSearchStrategy`, `GridSearchStrategy`.
- **Advanced optimizers** — optional Bayesian and multi-objective backends.
- **WS-3C policy toolkit** — offline-gated BOHB/ASHA, CMA-ES, learned VOI,
  learned routing, GP surrogate, constraint propagation and PBT helpers.

- **Resource arbitration** — memory/resource limits for expensive strategy paths.

## Public API

- `SearchStrategy`, `BaseSearchStrategy`, `StrategyAdapter`
- `SearchSpace`, `ParameterCodec`, `ScalarParameterCodec`
- `PolicyCandidate`, `Evaluation`, `StrategyState`
- `RandomSearchStrategy`, `GridSearchStrategy`
- `ResourceArbiter`, `ResourceMode`, `memory_cleanup(...)`
- optional: `BayesianConfig`, `BayesianOptimizer`, `MOConfig`, `MOBayesianOptimizer`
- WS-3C: `AdvancedSearchPolicyConfig`, `ASHAScheduler`, `BOHBSampler`,
  `CMAESExplorer`, `GaussianProcessCheapStageSurrogate`,
  `ExplicitConstraintPropagator`, `LearnedVOIPolicy`, `LearnedRoutingPolicy`,
  `PopulationBasedTrainingScheduler`

Details: [Reference →](../../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-14
  - WS-3C advanced policy surface updated: 2026-04-12
  - Canonical path moved under `polisyos.scientist.methods.search`: 2026-05-05
- Python source: 24 modules excluding `__init__.py` (25 `.py` files including
  `__init__.py`) in snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
- Static public surface: 36 names in `__all__`, including 18 base names and 18
  WS-3C toolkit names; optional Bayesian imports can append four names when their
  dependencies load successfully.
- README synchronized with the package's current lazy/optional import behavior.

`NeuralSearchStrategy` can checkpoint the Sobol phase with a selected transfer
corpus. Give it the existing `TransferLearningManager` and receiver
`RunFingerprint`, then call `warm_start_from_transfer` with source fingerprints
carrying exact selected history profiles. The manager reopens and reconciles
the selected CAS histories when a checkpoint is written, restored, or consumed;
cached transfer bytes also require live selected-CAS verification. Verification
and subsequent use are not atomic against concurrent mutation.
The selected source list admits at most one history per run, even when two
manifest profiles describe the same content, so the same observations cannot
be counted twice through profile aliases.
An unselected warm corpus, incompatible basis, damaged selected history,
legacy count-only checkpoint, and checkpoint after attempting a surrogate fit
are refused. The transfer reader currently reconstructs observation timestamps,
so this checkpoint does not preserve their original time or establish temporal
provenance. The matching synthetic Sobol path is verified; deterministic fitted
GP continuation and an automatic production caller remain unestablished.

`BayesianOptimizer.warm_start` stores every rejected `Evaluation` together
with its original rejection reason in `StrategyState.metadata.warm_start_rejections`
(version 1). `StrategyState.to_artifact/from_artifact` and `set_state/get_state`
carry this history independently of the optional GP backend. The snapshot
retains the full candidate ID, provenance, parameters, outcomes, and metadata;
repeated rejected attempts remain separate entries. These records are not part
of the training corpus and do not change existing compatibility/admission
predicates. For an older checkpoint without a ledger, `complete=false` explicitly
records the limitation: earlier entries and reasons that were lost are not
recovered. This field does not prove scientific provenance, refinement
permission, or production admission law.

The cold-start Sobol index and adaptive single-candidate acquisition planning
use the same admitted/deduplicated corpus as the training path: whole and
warm+current representations of the same admitted records produce a consistent
plan. Batch planning retains the existing fixed qEI path; current-request
iteration and full-refit counters retain their previous meaning regardless of
the warm-history count.

### Transfer history cache

Direct `TransferLearningManager.get_warm_start_evaluations` calls must supply the
keyword-only `target_fingerprint`. Omission raises `TypeError`; a supplied
non-fingerprint or incomplete target returns no evaluations before any history
read. `WarmStartBridge` already supplies its current target. Matching target and
history fields permit candidate reuse only; they do not establish external
permission, source custody, or semantic comparability of undeclared units.

`TransferLearningManager` retains only verified canonical history bytes in its
LRU cache. The key binds the full `ArtifactRef` (artifact ID, kind, media type,
and selected manifest profile) to the complete run identity. On every cache hit,
the cache rechecks the selected CAS profile and byte digest, then decodes the
record again; mutable `Evaluation` objects and nested values are not shared
between reads.

The cache is limited to 128 entries and 32 MiB in aggregate retained payload
bytes (`len(raw_payload_bytes)`). This bounds retained payload data, not RSS or
Python overhead. History larger than the limit is read and verified but not
cached. Eviction does not delete the CAS artifact or prevent reading the exact
old ref. New index rows retain the profile hash returned by the same CAS write;
older index rows without one retain a profileless compatibility ref that still
passes through the canonical reader.
