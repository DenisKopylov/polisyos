# Foundry (`polisyos.foundry`)

Foundry is the PolicyOS computation layer: it turns Trinity bundles into
CAS-backed execution plans, binds runtime state, executes patch-first program
graphs, and hands off to methods, calibration, uncertainty, and agent-based
simulation surfaces.

- Last updated: 2026-10-21

## Purpose

Use `polisyos.foundry` as the narrow public facade for compile/execute
workflows and the generic text-embedding contract and implementations.
Everything else in this package tree exists to support that facade: runtime
contracts, method catalogs, calibration flows, reproducibility hooks, and
agent-sim tooling.

The package-local `polisyos.foundry.runtime` modules provide execution helpers
for fingerprints, numeric and NaN safeguards, profiles, and tracing. They remain
distinct from top-level `polisyos.runtime`, which owns lifecycle, replay,
verification, and HTTP. The shared basename does not relax cross-package import
boundaries.

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
| `data_plane.prepare_input_bindings()` | Resolve a selected Fabric snapshot and registry, apply the real binding rules, and inspect the complete candidate state without writing CAS artifacts. |
| `data_plane.InputBindingsPreparation` | Worker-local computed state, effective rules, applied IDs and warnings. It is neither an authority receipt nor an admitted evaluation-retention basis. |
| `data_plane.prepare_hte_observational_input()` | Prepare a bounded, selected-profile HTE input for candidate method execution. |
| `data_plane.PreparedHTEObservationalInput` | Worker-local prepared data plus source/effective refs and typed input metadata. |
| `data_plane.HTEInputPreparationRefusal` | Typed refusal from selected-profile HTE input preparation. |
| `data_plane.HTEPhysicalSourceMaterializationBinding` | Strict physical slot-to-selected-payload binding; carries no semantic variable, query, unit, causal, population, law, currentness, or publication authority. |
| `data_plane.load_hte_physical_source_materialization_binding()` | Resolve and recompute an opt-in profile-bound physical binding against the consumer's exact submitted and effective input refs. |
| `data_plane.HTEInputLimits` | Type alias for Core's four-field `CoreJsonReadLimits`; construct limits with `CoreJsonReadLimits(max_bytes=payload_byte_limit, max_depth=depth_limit, max_elements=element_limit, max_manifest_bytes=manifest_byte_limit)` using explicit field names. |

`prepare_input_bindings()` and `build_input_bindings()` use the same maintained
rule and state-materialization owner. The writer recomputes the preparation from
its selected input refs; it does not accept a caller's prepared state or digest
as authority. This preparation only establishes the actual effective numerical
input to the existing writer. It does not decide equivalence of evaluations,
currentness, native acquisition admission, or permission to skip a later stage.

The HTE input exports are an additive public-stable API through the existing
`polisyos.foundry.data_plane` entrypoint; see the [release fragment](../../../release-fragments/unreleased/2026-10-21-e02-hte-physical-source-binding.toml).
`HTEInputLimits` is a typing alias,
not a runtime constructor; create the value with `CoreJsonReadLimits` from
`polisyos.core.artifacts`, naming `max_bytes`, `max_depth`, `max_elements`,
and `max_manifest_bytes` explicitly so documentation does not rely on
positional field order. For example: `CoreJsonReadLimits(max_bytes=payload_byte_limit,
max_depth=depth_limit, max_elements=element_limit,
max_manifest_bytes=manifest_byte_limit)`. The physical binding is emitted only when
an @2 caller opts in with `materialization_binding_version="physical_v1"`;
legacy callers retain their output bytes and create no additional artifact. Its
reader reloads the selected effective input and recomputes the array-slot
mapping. For legacy input it also re-reads the submitted profile and re-runs
the exact normalization before accepting the effective payload. Feature names
and metadata are not used as source identity. The binding
proves physical slot, payload field/index, shape, dtype, values, and row-order
materialization only. The producer prepares candidate input only and does not
establish method compatibility, units/context, causal identification,
external truth, scientific validity, or publishability. Runtime may pass its
already-materialized DTO to the reader, which rejects physical array or row
order differences before capturing the anchor. The generated
public-surface inventory still reports `unresolved_exports` for this entrypoint;
the inventory owner’s regeneration and review remain pending. This README does
not claim that inventory review has occurred.

The internal [selected-row candidate scope owner](data_plane/selected_row_candidate_scope.py)
persists a source binding and quantity, treatment-contrast, population, and outcome
projections for an explicit HTE request. Its bounded fresh reader reopens the
selected input and recomputes the physical rows, arrays, method profile, and
lineage. Declared variable-to-slot meaning remains `consumer_asserted`; units
remain unknown. Runtime and Search lifecycle orchestration is `bridge_missing`.
The helper is internal and is not exported by the `data_plane` facade.

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

## Bounded numeric NPZ inputs

The existing `polisyos.foundry.execute` facade exposes `read_numeric_npz_bounded`
and `BoundedNumericNPZError`. The decoder accepts a bounded immutable NPZ member,
an exact ordered member inventory, explicit entry/element/byte limits and numeric
array shape; it preflights the central directory and NPY headers, refuses object
arrays and compressed members, and returns owned read-only arrays. It does not
select or authenticate a CAS artifact: consumers must use a bounded selected-view
reader and their own typed lineage and input policy. The existing
`read_state_snapshot_inputs_bounded` keeps its selected-snapshot contract and
one-dimensional semantics through the same decoder. Runtime verification is pending.

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

## Candidate method-metric execution capture

A versioned `CompileRequest` may select explicit objective/node/output-slot
bindings. The compiler persists those bindings as
`foundry.method_metric_binding_set` and attaches the full selected ref to the
existing `foundry.exec_plan` manifest under `method_metric_bindings`; the
`ExecPlan` payload version is unchanged. During execution, a shared capture
records each planned and actual method occurrence, including repeated feedback
invocations, dispatch reconciliation, bounded input/prestate identities, output
slot inventory, and selected scalar output payloads. The resulting
`foundry.method_execution_bundle` links the binding set, plan, graph, environment
manifest when captured, and each output/sidecar by exact selected-profile edges.
`SimulationResult` 1.4 remains unchanged.

The existing 128-row method binding ceiling is enforced at all intake boundaries. `CompileRequest` constrains the collection during strict model validation, and the compiler rechecks its raw list length before any objective, node, selection, or uniqueness traversal. Persisted binding sets use Core `read_core_json_artifact_bounded` with a 1 MiB payload cap, a 32,768-element lexical cap, a depth cap of 16, and a 64 KiB manifest cap. The exact decoded `bindings` array is counted before typed Pydantic materialization, then the model retains its own 128-row defense. No oversized set is truncated or accepted by an unbounded fallback.

The capture is source evidence for a candidate observation. It does not establish
that the metric meaning is causally valid or that a policy is admissible,
publishable, or institutionally authorized. Environment capture occurs before
dispatch and is not proof of the actual backend for every invocation; dispatch
identity is recorded separately and stays not-established when it cannot be
reconciled. The RunSimulation node carries full selected-profile graph refs in its existing
`ExperimentState.artifacts_index` bridge, but the Runtime current-fence handoff and
Scientist projection consumer remain separate owner slices. Every binding-bearing
`execute_program_graph` call auto-creates or joins the shared capture. The
source-enumerated callers preserve the refs through the public ExecuteResult,
RunSimulation state bridge, horizon trajectory rows, and AD02's LocalBackend
JobResult companion. The Runtime legacy-shadow current-fence handoff and
Scientist projection consumer remain separate owner slices. Default
WorkspaceLoop and registered S2 remain unconnected.

The bounded source-admission entry point is
`polisyos.foundry.execute.admit_execution_source_bounded`, exported from the stable `polisyos.foundry.execute` facade with `BoundedExecutionSourceReader` and `ExecutionSourceBoundedReadRefusal`. It reuses the
existing source-basis predicate and requires one server-owned
`BoundedExecutionSourceReader` for every selected manifest, lineage edge, and
typed payload read. The admission reports its aggregate observed read bytes and
propagates a typed refusal when the shared budget is exhausted. Its edge reader
must use Core's selected `InputRef` resolver
`read_core_input_manifest_profile_bounded`; no profileless/default fallback is
available on this path. The legacy `admit_execution_source` API keeps its prior
compatibility behavior. Runtime admission, candidate projection, and a real
Core-backed bounded-reader replay are separate verification work; this package
does not claim them complete.


## Selected method plans

A version 1.2 CompileRequest may carry an exact selected scientist.execution_plan
reference. The plan manifest must bind the same selected Trinity candidate profile;
the compiled ProgramGraph keeps that plan as execution_plan_source. The compiler
adapts only registered PURE methods whose complete signature, backend, parameters,
input slots, return slots, and dependencies match the selected plan. Unsupported or
malformed plans refuse as a whole.

Method return slots remain in the plan and method metric binding, while
ProgramNode.outputs remains the state-patch plane. The current adapter does not
transfer a method return into another planned method or lowered mechanism; it refuses
a plan that declares such a consumer, including a consumer reachable by dependency
whose slot name appears aliased. A selected nonempty method graph (nodes or declared edges) without a
supported method metric binding is typed-refused before the compiler runs or
compile artifacts are emitted. Empty selected plans and absent selected refs
retain the legacy mechanism-only route; request versions 1.0 and 1.1 retain
their no-plan behavior. This candidate execution chain does not establish
scientific appropriateness or publication authority.

The public `polisyos.foundry.compile.replay_method_program_graph` facade is a
read-only replay of the canonical zero-mechanism method compiler graph and order.
Its caller must content-read and reconcile exact selected Trinity, lowering,
constraint registry and Scientist plan profiles first. It checks lowering content
against Trinity and retains the full merge/check operator plane. It writes no CAS
objects and issues no completion, observation or publication authority. Enabled
intervention mechanisms remain outside this bounded replay profile.

The `polisyos.foundry.compile.build_method_housekeeping_nodes` facade delegates
to the compiler's canonical merge/check node and edge builder for one method,
including collision handling. It does not validate the supplied node's kind or
semantic inputs, and grants no execution, completion, or publication authority.

The `polisyos.foundry.compile` facade exposes `program_graph_input_refs` and
`execution_plan_input_refs`, the same ordered selected-edge builders used by the
Trinity compiler writer, together with the existing `TreasuryPlan` and
`build_treasury_plan` owner. These functions describe input identity only; they do
not verify a source, establish completeness of a caller's basis, or grant
authority. Callers must independently select and validate the supplied refs.

The `polisyos.foundry.execute.execution_input_basis_sources` facade derives the
producer-owned, ordered source-role and selected-reference pairs from a typed
execution input basis. Foundry uses it for both basis creation and re-entry;
this enumeration alone is neither source admission nor authority.

### Prospective acquired JSON values

`data_plane.prepare_json_input_binding_values` resolves the real registry and
uses the same rule validation, entity layout, materialization and error fold as
`build_input_bindings`, without inventing a DataSnapshot or writing artifacts.
Its immutable input bytes are numerical input, not source admission. The Runtime
acquisition bridge separately replays actual Data Forge source custody and passes
its exact preparation to the real materializer, then reconciles every actual
new bound-state codec value and rule before context/N5 admission.

`execute.state_snapshot_value_projection` derives the full leaf denominator from
the maintained snapshot codec and preserves paths, shapes, dtypes and exact
immutable value bytes (including signed zero and non-target/vector values).
Equality compares those bytes directly; a derived digest is receipt-only. The
prospective JSON port reuses the real Core CAN.2 payload encode/decode law
before binding, including its numeric normalization. The projection compares
consumed state values, not NPZ archive bytes or contextual snapshot refs. It is
one facet of a future complete semantic evaluation basis: model/NCM, native
context/profile, backend, current requirement and eligibility still need their
actual owners. It does not establish complete equality, evaluation retention or
authority. Runtime qualification and generated public-surface review are pending.
