# Foundry (`polisyos.foundry`)

Foundry is the PolicyOS computation layer: it turns Trinity bundles into
CAS-backed execution plans, binds runtime state, executes patch-first program
graphs, and hands off to methods, calibration, uncertainty, and agent-based
simulation surfaces.

- Last updated: 2026-10-19

## Purpose

Use `polisyos.foundry` as the narrow public facade for compile/execute
workflows and the generic text-embedding contract and implementations.
Everything else in this package tree exists to support that facade: runtime
contracts, method catalogs, calibration flows, reproducibility hooks, and
agent-sim tooling.

## Where to Start

- [_internal/quickstart.py](_internal/quickstart.py) for an internal
  docs/test helper that writes real CAS artifacts; it is not a supported
  public import path.

- [compile/api.py](compile/api.py) for the public `compile()` contract and
  failure semantics.

- [compile/randomization.py](compile/randomization.py) for the canonical
  reproducible randomization and treasury-plan owner; the retained
  [mechanisms/treasury.py](mechanisms/treasury.py) path is a direct
  compatibility facade for existing callers.

- [execute/mechanisms/](execute/mechanisms/) for the canonical fiscal and
  labor patch-emission mechanisms. The retained
  [mechanisms/fiscal.py](mechanisms/fiscal.py) and
  [mechanisms/labor.py](mechanisms/labor.py) paths are forwarding facades that
  preserve existing imports; runtime method descriptors resolve the canonical
  execution owner.

- [execute/api.py](execute/api.py) for `execute()`, input bindings, and replay
  behavior.

- [__init__.py](__init__.py) for the lazy public embedding exports and
  [methods/backends/protocol.py](methods/backends/protocol.py) for their
  Foundry-owned implementation.

- [contracts/README.md](contracts/README.md) for runtime state, patch, and
  fidelity contracts.

- [methods/README.md](methods/README.md) for the reusable method ABI, registry,
  dispatch, and catalog surfaces.
- [methods/catalog/mechanism/README.md](methods/catalog/mechanism/README.md)
  for runtime mechanism descriptors derived from the canonical MethodRegistry.

- [calibration/README.md](calibration/README.md) for measurement-aware fit
  loops and uncertainty hand-off.

- [validation/README.md](validation/README.md) for legal subject recognition
  against independently addressed membership sources, before numeric checks.

- [agent_sim/README.md](agent_sim/README.md) for low-level ABM/RL executors and
  wiring.

- [plugins/README.md](plugins/README.md) for plugin-driven domain simulation on
  top of `agent_sim`.

## Public API

| Entrypoint                    | Description                                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `compile()`                   | Compile a Trinity bundle into `foundry.program_graph`, `foundry.exec_plan`, and a compile report artifact. |
| `compile_program()`           | Compatibility alias for `compile()` on the package facade.                                                 |
| `execute()`                   | Execute a compiled plan from `FoundryInputBindingsRef` and persist simulation evidence.                    |
| `admit_execution_source()`     | Recompute a persisted simulation result's source mode and complete selected basis inventory.               |
| `SnapshotStateLayoutError`   | Stable exception identity for valid state bytes that do not reconstruct the canonical `GlobalState`; legacy consumers may handle this specific compatibility case. |
| `EmbedderProtocol`            | Structural contract for fixed-dimensional text embedders.                                                 |
| `TFIDFEmbedder`               | Dependency-free fitted TF-IDF text embedder.                                                               |
| `SentenceTransformerEmbedder` | Optional sentence-transformers adapter whose dependency loads only on construction.                        |
| `MethodRouteConstraint`       | Stable candidate route constraint contract, implemented by the existing method-selection owner. |
| `method_accepts_input_contract()` | Stable relation predicate over a method's actual input slots and executable type hints. |

The route interface's stable import boundary does not grant evidence authority.
Its output remains a candidate search constraint; it certifies neither a source
manifest nor observed data, causal effects, legal admissibility, or promotion.
Internal method-selection implementation paths retain their existing maturity.

Legal correspondence uses the `LegalCorrespondenceRequest` and
`LegalCorrespondenceResult` facade contracts, with `LegalSubjectIdentity`,
`LegalSubjectMembership`, and `LegalSubjectMembershipSource` for its source data.
`persist_legal_subject_membership_source()` persists separate source tables;
`produce_legal_subject_spine()` binds their content-addressed references without
accepting a proposed mapping. `recognize_legal_correspondence()` compares subjects,
and `persist_legal_correspondence_result()` retains the result for audit.
Frozen annotation sources use `LegalSubjectAnnotationSource`,
`persist_legal_subject_annotations()`, and `bind_legal_subject_annotations()` to
bind independently declared annotations to current entity content.
Recognition is relative to the addressed source. Synthetic provenance remains
explicit, and neither synthetic data nor an unverified authority reference grants
legal authority.

Cross-owner runtime imports use the exact Foundry owner facades: `data_plane`,
`execute`, `methods`, `methods.backends`, `methods.causal`, `calibration`,
`analysis`, `uncertainty`, and `validation`. These exports resolve to their
canonical owner objects and preserve existing runtime semantics. The routes add
no evidence, authority, or institutional claims.

The stable package facade is intentionally small. If a workflow needs lower
level helpers, start from the subpackage README for that area instead of
deep-importing ad hoc internals.

The former private `polisyos.foundry._registry` module is removed; mechanism
runtime descriptors belong to the catalog owner linked above.

## DataSnapshot input binding

Foundry's DataSnapshot loader reconciles the snapshot's typed refs with the
selected CAS parent edges. For schema 0.3, it also reconciles the declared
lineage refs with those edges. This is candidate input-binding consistency; it
does not independently verify the source owner's basis or admit an owner
family. Protected Runtime consumers perform the fresh owner-family readback
before emitting a bound World Model Record. Direct Foundry binding and execution
remain operational candidate paths and do not grant promotion or publication
authority. External institution signatures and source truth remain outside this
contract.

## Execution-source admission

`polisyos.foundry.execute.admit_execution_source()` reopens the selected
simulation result and recomputes its source mode through the Foundry owner. It
returns `legacy_profileless`, `single_step_basis`, or `feedback_uncomposed` with
the exact selected refs and manifests. A single-step result also carries the
complete source inventory that the owner just recomputed and matched to the
persisted basis manifest; the other two modes carry no basis inventory.

Owner-detected source-mode, profile, edge, and inventory refusals raise
`ExecutionSourceAdmissionRefusal`, a `ValueError` subtype whose `reason` is the
existing owner refusal string. Other typed `ValueError` subclasses pass through
unchanged; this preserves CAS `ArtifactIntegrityError` and malformed-payload
`pydantic.ValidationError` identities, distinguishing corrupt bytes and invalid
payloads from a well-formed source that fails an owner relation. The
result describes source identity and mode only. It does not establish causal
validity, risk meaning, legal admissibility, policy effects, or promotion
authority. Consumers that need a replayable single-step source continue to
withhold `feedback_uncomposed` results.

## Candidate-only welfare execution-source identity (B161)

A caller that needs a source-bound welfare observation opts into exact manifest
profile returns on the selected compile, binding, and execute calls. The Foundry
executor persists `FoundryExecutionInputBasis` from the actual request, resolved
`ExecPlan`/`ProgramGraph`/Trinity and candidate source, selected `DataSnapshot`,
input bindings, registry bundle members, parameter overrides, and recomputed
effective execution posture. The basis is an identity record: it does not certify
a risk quantity, unit, valid time, refinement law, or authority.

The basis ref and selected result/metrics/state-delta profiles cross the welfare
producer into its method config, Monte Carlo sample bundle, propagation report,
and welfare bundle. A fresh search consumer resolves the selected manifests by
profile, verifies their contents and parent edges, and recomputes the execution
source relation before it emits a `SourceBoundRiskObservation` audit ref. The
relation distinguishes the same selected DataSnapshot, the same artifact bytes
under a different selected profile, and a different artifact ID. Those labels
measure source identity only.

`SimulationResult` schema 1.4 records `single_step_basis` only for a captured
single-step call. Feedback execution is marked `feedback_uncomposed` and carries
no single-step basis; the B161 observation consumer withholds it. Calls that do
not request selected profiles retain their existing profileless output behavior.
Even a recomputed source relation remains candidate-only: search-risk meaning,
unit, validity/currentness, same-scope refinement, and permission to lower or
supersede a historical maximum remain `not_established`.

## Internal Layout

### Source-bound causal computation

Cross-package consumers import `causal_worker_execution_context`,
`validate_source_bound_gcm_spec`,
`validate_source_bound_causal_estimator_interval`, and
`validate_source_bound_causal_worker_response` from `polisyos.foundry`.
Each lazy export resolves to the existing canonical method-provider function,
with its original callable and pickle identity. The context binds an actual
source reference and CAS to the selected worker invocation. The validators
reopen the source and reconcile rows, graph, request, worker code/lock and
supported fitted outputs. They introduce no second scheduler or artifact store.
Source custody and supported numerical execution remain distinct from causal
identification, sampling-law admission and policy authority. See
[structural causal models](../../../docs/reference/foundry/structural-causal-models.md).

- [`api.py`](api.py), [`__init__.py`](__init__.py), [`compile/`](compile/), and
  [`execute/`](execute/) own the stable public Foundry facades.
- [`contracts/`](contracts/README.md) owns runtime state, patch, and fidelity
  contracts used by compilation and execution.
- [`methods/`](methods/README.md) owns reusable method ABI, registries, and
  catalog families; its backend modules remain internal implementation paths.
- [`agent_sim/`](agent_sim/README.md), [`calibration/`](calibration/README.md),
  [`uncertainty/`](uncertainty/README.md), and domain helpers are
  implementation surfaces unless exported by the root facade.
- [`welfare/`](welfare/) owns welfare-bound sidecars, social-weight schedule
  helpers, and the W8.D Pareto frontier/social-weight provenance emitter used
  to expose tradeoff facts separately from governance value choices.
- [`execute/_internal/`](execute/_internal/) is private executor support.

## Extension Points

- External reusable methods use `polisyos.foundry_methods`; see
  [methods/README.md](methods/README.md) and
  [architecture/extension_points.toml](../../../architecture/extension_points.toml).
- Domain simulation plugins are documented in [plugins/README.md](plugins/README.md)
  and build on `agent_sim` rather than the root facade.
- Foundry method discovery retains the exported `(target, callable)` builtin loader
  tuple. The default selection is represented by Core's typed declaration at discovery
  and checked by catalog admission through the same selected-spec helper; the target and
  group remain owned by `architecture/extension_points.toml`. Explicit tuple/callable
  replacements keep their legacy v1 discovery shape.

## Depends On / Depended On By

- Depends on: `polisyos.core` artifact, registry, and contract layers;
  `polisyos.ir` Trinity/model contracts; optional scientific runtimes exposed by
  subpackages.

- Depended on by: `polisyos.scientist` execution and autotune flows,
  `polisyos.runtime.http` control services, release-acceptance flows, and local
  demos/benchmarks.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry._internal.quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="foundry-docs-") as tmp:
    result = run_trivial_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
PY
```

## Tests

```bash
uv run pytest tests/unit/foundry/facade/test_quickstart.py \
  tests/unit/foundry/compile/test_compile_determinism.py \
  tests/unit/foundry/runtime/test_execute_input_bindings.py -q

uv run pytest tests/unit/foundry/runtime/test_executor_fail_semantics.py \
  tests/unit/foundry/runtime/test_nan_guard_public.py -q
```

Package test ownership is documented in
[tests/unit/foundry/README.md](../../../tests/unit/foundry/README.md). Run the
methods suite when changes touch `methods/` registration, dispatch, or catalog
metadata.

## Operability Links

- [Foundry component SLO](../../../ops/components/foundry/slo.yaml)
- [Foundry component runbooks](../../../ops/components/foundry/runbooks.md)
- [Foundry observability and reproducibility](../../../docs/reference/foundry/observability-reproducibility.md)
- [Replay or restore runbook](../../../docs/runbooks/replay-or-restore.md)
- [Benchmark regression triage runbook](../../../docs/runbooks/benchmark-regression-triage.md)

## Known Shims/Deprecations

- Root public exports stay intentionally narrow. Promote new compile/execute
  API through `api.py`, public-surface docs, and a compatibility note before
  removing old import paths.

## Reference Docs

- [docs/reference/foundry/index.md](../../../docs/reference/foundry/index.md)
- [docs/reference/foundry/compile-execute.md](../../../docs/reference/foundry/compile-execute.md)
- [docs/reference/foundry/state.md](../../../docs/reference/foundry/state.md)
- [docs/reference/foundry/observability-reproducibility.md](../../../docs/reference/foundry/observability-reproducibility.md)
- [docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md](../../../docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md)
- [tests/unit/foundry/README.md](../../../tests/unit/foundry/README.md)
