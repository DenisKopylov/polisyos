Current criterion-scope correction: [B109/B111/B100 errata](../../../../../docs/research/e02-cloud-test-plan/integration/reviews/original-criteria-errata-2026-10-06.md). B109 is fast/direct comparator acceptance; the served provider is additional capability. B111 keeps invalid-state/partial-denominator/finite-or-unavailable semantics; schema-v3 migration and finite-positive underflow are separately scoped. Historical outcomes and status counts below are retained.

# Search Methods (`polisyos.scientist.methods.search`)

## Purpose

`polisyos.scientist.methods.search` implements the iterative policy-optimization layer
for Scientist: candidate generation, staged evaluation, readiness and promotion
gating, lesson and benchmark registries, and optional funnel/strategy/frontier
logic used by policy-design and promotion workflows.

## Where to Start

- Root facade and lazy exports: [`__init__.py`](__init__.py)
- Legacy ask/evaluate controller: [`controller.py`](controller.py)
- Native internal service bridge: [`service.py`](service.py)
- Shared contract/type leaf and evaluation primitives: [`contracts.py`](contracts.py), [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py)
- Promotion funnel and rollout logic: [`funnel/`](funnel/), [`readiness.py`](readiness.py), and [`promotion_evidence.py`](promotion_evidence.py)
- Strategy implementations: [`strategies/`](strategies/)

## Public Entrypoints

- Root contract surface in [`contracts.py`](contracts.py): `SearchService`, `CandidateProposal`, `EvaluationBundle`, and `TellResult`
- Legacy controller in [`controller.py`](controller.py): `SearchController`, `SearchConfig`, `SearchResult`, and `SearchIteration`; protected provider search uses `TracedLLMCandidateGenerator` and its typed refusal `SearchBudgetProducerUnsupportedError`
- Evaluation primitives in [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py): `CompositeObjective`, `CheapStage`, `ExpensiveStage`, and `StoppingPresets`
- Registry and lesson surfaces in [`benchmark_registry.py`](benchmark_registry.py), [`lessons.py`](lessons.py), [`pareto_registry.py`](pareto_registry.py), and [`registry_contracts.py`](registry_contracts.py)
- Rollout helpers in [`adversarial.py`](adversarial.py), [`latent_governance.py`](latent_governance.py), [`promotion_evidence.py`](promotion_evidence.py), and [`compliance_audit.py`](compliance_audit.py)
- Search strategies in [`strategies/`](strategies/): random, grid, Bayesian, multi-objective, neural, and arbitration helpers


The contracts module is the import-safe type leaf for search DTOs, run/result
records, transitions, and the native controller port. Compatibility imports
retain historical controller/run-state class identities; concrete adapters and
funnel implementations are not statically imported by this leaf.

## Pareto Basis Declaration

SearchConfig may receive caller-owned ParetoBasisScope values by view through
pareto_objective_basis_by_view. The controller forwards these typed values through the existing
registry update contract. An empty mapping preserves observed/unknown basis behavior; ranking
against named axes requires an explicit declared scope. This declaration describes the chosen
comparison basis and does not prove that the basis is complete or authoritative.

## Pareto Assessment Projection (B111)

The registry's typed `view_assessments` supplies assessment status for each
projection; `eligible_candidate_hashes` identifies that projection's
assessment denominator. The v3 `PolicyFrontierReport` DTO validator compares
the supplied source-feasible set with the global projection's eligible
identities, checks for duplicates within each supplied set and overlap
between the source-feasible and unknown sets, and requires the projection
assessment status to be `denominator_limited` exactly when the source-feasible
set differs from
projected eligible identities or the supplied unknown set is nonempty. It
does not check unknown identities for projection membership or independently
reconcile them against the projection. However, the ordinary
`PolicyArtifactBuilder._build_frontier_report` path sets the report's source
identities from the same projection and leaves
the unknown set empty. That self-derived equality is not an independent source
observation: it cannot detect a candidate omitted before registry projection
or establish upstream population completeness. The independent producer input
and bridge are not established. A missing registry remains basis-limited and
unranked. See the [policy-design package README](../../policy_design/README.md#persisted-frontier-artifacts)
for artifact versions and rollout limits.

## Depends On / Depended On By

- Depends on: [`../../governance/README.md`](../../governance/README.md), `doe`, policy-design/search-specific runtime helpers, and artifact persistence surfaces
- Depended on by: policy-design workflows, builtin planning/decision nodes, frontier rollout gates, and benchmark/promotion flows described in [`../../orchestration/workflows/README.md`](../../orchestration/workflows/README.md) and [`../../nodes/README.md`](../../nodes/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.methods.search import CompositeObjective, StoppingPresets; from polisyos.scientist.methods.search.controller import SearchConfig, SearchController; print(CompositeObjective.__name__, SearchConfig.__name__, SearchController.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/methods tests/unit/scientist/search -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/search/test_controller_api.py tests/unit/scientist/search/test_search_loop.py tests/unit/scientist/search/test_benchmark_registry.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../../docs/reference/scientist/index.md`](../../../../../docs/reference/scientist/index.md)
- Agent/search reasoning reference: [`../../../../../docs/reference/scientist/agent-search-reasoning.md`](../../../../../docs/reference/scientist/agent-search-reasoning.md)
- Frontier rollout contract: [`../../../../../docs/reference/scientist/frontier-runtime.md`](../../../../../docs/reference/scientist/frontier-runtime.md)
- Reliability gate context: [`../../../../../docs/reference/scientist/reliability-scorecard.md`](../../../../../docs/reference/scientist/reliability-scorecard.md)
- Cross-package navigation: [`../../orchestration/workflows/README.md`](../../orchestration/workflows/README.md), [`../../governance/README.md`](../../governance/README.md), and [`../../../../../tests/unit/scientist/README.md`](../../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-10-12

## Configured uncertainty observation intake

`uncertainty.py` defines routing-only `SearchUncertaintyBasis` and
`SearchUncertaintyObservation` artifacts. The funnel resolves native producer
observation refs from CAS, binds the full configured basis and candidate, checks
that the supplied envelope equals the stage envelope, and preserves exact selected
manifest views in input lineage. Missing, foreign, corrupted, or substituted inputs
leave current uncertainty `not_established`; historical maxima remain available.

Current observations are aggregated conservatively across every supplied risk.
No observation supersedes another: producer provenance, current scientific
refinement law and publication authority are not supplied by CAS identity.
B161 lowering remains held until the actual producer-owned refinement contract
is admitted. L3/L4 forward native producer observation refs without minting them.

## Monetary evidence and VOI

Funnel stage costs carry an explicit `reported`, `estimated`, or `unknown` origin.
Configuration and duration-based values remain estimates; unknown stage cost is
nullable and does not become zero. VOI keeps unknown observations for audit but
does not train its cost model from them or from legacy untyped amounts. It prefers
eligible reported-cost history, then uses estimated history only with the explicit
`estimated_history_heuristic` basis, and otherwise uses configured stage cost as an
estimate. These cost signals do not establish native evaluator work counts or
scientific price calibration.

## Durable provider owner path (B120 candidate)

The owner-bound candidate-generation path requires a `BudgetMiddleware`, a typed
`BudgetLedgerProducerRunBinding`, and the concrete `TracedLLMCandidateGenerator`.
Before `SearchLoopRunner` invokes generator context callbacks, and before a direct
`SearchController` can run, the adapter is checked against the exact middleware,
`nl-run:<run_id>` key, readable durable owner identity, and typed run binding. The
adapter itself serializes the full candidate input without dropping unsupported
values and calls that exact `TracedLLMClient`; malformed provider output is refused.
After a generated candidate, a missing, pending, unknown, or mismatched settlement
is unavailable before the next Stage A/B evaluation. Other candidate generators
remain available to unprotected search; in protected mode they receive a typed
refusal before invocation and must migrate to the adapter. A provider call can
cross the configured stop threshold because the actual charge is known only after
the call settles. The durable owner can stop a
later evaluation after the crossing charge, but this path does not reserve a
pre-dispatch price, restore search state, or claim external billing truth.

This verifies only selected candidate-generation calls. The generic Stage A and
Stage B evaluator callables have no owner-carrying type contract here; if an
evaluator invokes a provider, this adapter does not prove that call is covered by
the selected owner. Whole-search cost admission therefore remains limited.

The focused fixture sends two runtime Gateway calls through `TracedLLMClient`
against a controlled HTTP response, records both committed events under the
selected run binding, and shows the owner-reported
`$0.50` spend crossing a `$0.30` search stop threshold before another Stage B
evaluation. The test does not establish a guarantee that the next provider call
will be priced or blocked before dispatch.

## Typed objective handling (B123 candidate)

A present malformed typed evaluation does not fall back to a legacy scalar in the
tested ObjectiveStack-to-best/frontier path. The current internal candidate-state
transfer through the Pareto registry and a fresh warm-start receiver does not
establish protected publication, a canonical publication ref, or authority. Those
claims remain limited pending the actual protected consumer path.

## Native replay and resume (LA-033 evidence)

The focused Foundry CLI replay and remediation resume tests exercise the native
producer path, persisted replay result, and fresh resume from the stored CAS head.
They do not set an import-time budget threshold or establish production-wide
currentness; no production inputs are rewritten for these tests.


## Import-safe contracts and funnel DTO ownership

The canonical dotted import of `contracts.py` is kept free of the controller and funnel runtime.
Adversarial exports on the package facade remain available through lazy lookup. The concrete
`FunnelTicket`, `FunnelOutcome`, and `FunnelTraceStep` dataclasses are owned by `funnel/types.py`;
`funnel/orchestrator.py` re-exports the same classes under their historical module path so existing
imports and pickle resolution remain stable. The contracts use those concrete DTOs for their
static service signatures instead of a reduced outcome view.


## Candidate-only source-bound welfare observation (B161)

The runtime may carry an existing `ir.welfare_bundle` ref into the funnel. For a
new source-bound run, the producer chain opts into exact manifest-profile returns
for the selected candidate, compiled `ProgramGraph` and `ExecPlan`, input
bindings, and executed Foundry artifacts. Foundry persists a typed
`FoundryExecutionInputBasis` from the actual `ExecuteRequest`, its selected
source graph (`ModelSpec`/Trinity/candidate, data snapshot, input bindings, and
registry members), and the recomputed effective posture. It emits no risk,
refinement, unit, valid-time, or authority conclusion.

The welfare node carries the selected basis edge through method config, Monte
Carlo sample bundle, propagation report, and `WelfareBundle`. It also emits
schema 1.1 `WelfareSampleBundle` artifacts with the actual PE response and
post-GE component vectors for every successful draw, using the same label order
as the selected `ir.welfare_weights` payload. `WelfareBundle` schema 1.1 also
stores the actual nominal PE and post-GE component operands returned by the same
evaluator. The fresh reader recomputes nominal PE/GE/total and every MC
PE/GE/total scalar from the exact selected weight payload. It reconciles all
typed welfare source refs (policy, weights, social-weight manifest, baseline,
PE/GE models, uncertainty/dependence/channel sources and method/sample refs)
with their exact selected manifest roles. It also binds the report and sample
to the same execution basis, report-to-sample edge, and sample-to-applied-weight
edge, and checks the welfare bundle's SimulationResult and Metrics edges against
the executed sources.

The welfare context returns the same-write selected profile when it materializes
a social-weight manifest; explicitly supplied profileless manifest refs remain
unqualified. That manifest is provenance/context only; the actual applied vector
is the separate `ir.welfare_weights` artifact. For the source-basis path, the
existing single-component `[1.0]` fallback is persisted as the exact selected
weight artifact; the ordinary legacy path retains its existing no-ref fallback.
The reader resolves each content-bound weight artifact and recomputes the nominal
outputs and every stored PE, total and GE draw from their raw component vectors
and the exact persisted weight vector. It does
not normalize weights. A detached policy or weight role edge, or a changed
weight artifact paired with the old sample and report, cannot retain a candidate
observation just because its status/count markers remain. It recomputes the
candidate-to-execution source relation,
draw attempts, counts, summary and interval before exposing schema 1.2
`scientist.search.source_bound_risk_observation` through the existing
`FunnelOutcome.audit_refs` surface. CAS identity results remain source
identities only, not scientific scope or risk-refinement findings.

The artifact keeps nominal welfare separate from sampled mean/spread and labels
its authority purpose `candidate_only_audit_measurement`, admission
`candidate_only`, and scope relation `consumer_asserted`. Unit, valid time, risk
interpretation, and permitted refinement remain `not_established`. Manifest
creation time is source production time only. It never populates
`current_uncertainty`, changes routing or promotion, or lowers/supersedes a
historical maximum. Feedback runs are explicitly `feedback_uncomposed` and
withheld. Historical WelfareBundle schema 1.0 and sample schema 1.0 remain
readable by the IR loader, but have no nominal operands or draw component vectors
and cannot be promoted to a newly verified source-bound observation; no source
or history is backfilled. Other welfare
methods remain outside this adapter. Existing `audit_refs` and artifact
content routes are reused.


The source-bound observation builder adapts the caller's Core store once with
`ensure_ir_artifact_store` before the IR welfare, weight, method, report, and
sample reads. Core manifest/source verification continues against the original
store, and the selected typed refs pass unchanged through the adapter.


## Selected-profile CAN source intake (B161 S1)

The Ukraine runtime-bundle producer carries the exact selected `DataSnapshotRef` returned by the CAS write through `runtime_bundle_manifest.json`, the intake receipt, Foundry bindings, and the execution-input basis. The source verifier resolves that selected manifest before parsing each typed Core JSON member. It checks the manifest's owner-declared artifact schema as well as canonical bytes and Pydantic content; a valid content hash, kind, field shape, or Monte Carlo marker alone does not establish the typed source contract.

A selected DataSnapshot without its exact owner schema remains unqualified for this candidate source path. Legacy ID-only runtime bundles remain readable and profileless: intake never infers a selected profile or schema from the artifact ID. The observation remains candidate-only; no risk interpretation, same-subject refinement relation, unit, valid-time/currentness, issuer authority, normalization, routing, or historical-maximum change is inferred.

The exact schema name and version come from the typed model owner, never from `model.__name__`, an artifact field name, or a caller-supplied alias. The candidate verifier applies one generic check to the complete typed Core JSON source quantity; the test alters both schema name and version while preserving bytes, canonical profile, role edges, and source markers.

The selected-source identity check covers the full typed DTO quantity: each source model owns literal kind/media and artifact-schema descriptors, and the fresh reader compares both the selected ref and resolved manifest to those descriptors. It also enforces owner identity when reconstructing `SimulationResult` from the WelfareBundle edge and `StateDelta` from the SimulationResult edge. Tests keep bytes, schema, canonical settings, source edges, and candidate/Monte Carlo markers intact while changing only kind or media type. The fixed-step producer fixture passes a non-empty `tax_cut.rate` override through a selected `ParameterOverrideBundle`; it does not create a ref only for the test matrix. This remains candidate-only source measurement, with external risk/refinement meaning, unit, time/currentness, and authority not established.


For this candidate-source path, the fresh reader also reconciles each selected DataSnapshot's data_ref and optional uncertainty_envelope_ref to one exact selected manifest edge. New Ukraine runtime snapshots persist their payload profile and data_ref edge. Existing snapshots without those edges remain readable by general artifact consumers but are withheld from this source-bound candidate observation; there is no historical backfill. A same-bytes, different-profile snapshot remains candidate-only only when its own source edges still match its typed payload.

When a welfare producer receives feedback_uncomposed, it persists the measurement with the actual feedback-result edge and without an execution-basis edge. The source-bound consumer still withholds that observation because the typed execution status has no composed single-step basis. This does not change risk meaning, refinement, units, valid time/currentness, or authority: each remains not_established. When `ExecuteRequest.return_selected_profile` is true, the nested feedback-result ref preserves the exact profile returned by the CAS producer write; the default remains false and legacy feedback artifacts are not backfilled.
