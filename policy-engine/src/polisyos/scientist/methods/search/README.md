Current criterion-scope correction: [B109/B111/B100 errata](../../../../../docs/research/e02-cloud-test-plan/integration/reviews/original-criteria-errata-2026-10-06.md). B109 is fast/direct comparator acceptance; the served provider is additional capability. B111 keeps invalid-state/partial-denominator/finite-or-unavailable semantics; schema-v3 migration and finite-positive underflow are separately scoped. Historical outcomes and status counts below are retained.

# Search Methods (`polisyos.scientist.methods.search`)

## Purpose

`polisyos.scientist.methods.search` implements the iterative policy-optimization layer
for Scientist: candidate generation, staged evaluation, readiness and promotion
gating, lesson and benchmark registries, and optional funnel/strategy/frontier
logic used by policy-design and promotion workflows.

## Where to Start

- Root facade and lazy exports: [`__init__.py`](__init__.py)
- Legacy ask/evaluate compatibility facade: [`controller.py`](controller.py)
- Private lifecycle owner and shared facade bindings: [`lifecycle.py`](lifecycle.py) and [`lifecycle_support.py`](lifecycle_support.py)
- Native ask/tell service bridge: [`service.py`](service.py)
- Shared contract/type leaf and evaluation primitives: [`contracts.py`](contracts.py), [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py)
- Promotion funnel and rollout logic: [`funnel/`](funnel/), [`readiness.py`](readiness.py), and [`promotion_evidence.py`](promotion_evidence.py)
- Strategy implementations: [`strategies/`](strategies/)

The RL exploration wrapper's versioned checkpoint carries its Python random
state and the selected nested strategy state. Restore checks the search space,
linear-decay schedule and nested strategy/model identity before delegating to
the nested strategy's decoder. Untyped legacy wrapper snapshots and custom
exploration schedules lack this basis and are refused for checkpoint restore;
custom schedules can still be used without checkpointing. Nested owners remain
responsible for validating their own configuration and restore behavior. Grid
checkpoints bind both `points_per_dim` and `max_candidates` and validate the
cursor before changing any state; older Grid snapshots without these fields
are refused. The Bayesian no-fit Sobol continuation is tested for a matching
configuration; other Bayesian configuration compatibility and failure
atomicity are not established by the wrapper. This checkpoint is a
reproducibility aid, not evidence of a policy or source authority.

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

`_SearchLifecycleOwner` in `lifecycle.py` is the sole internal owner of search
configuration, evaluation, mutable run state, and run flow. `SearchController`
remains the historical typed forwarding facade, and `LegacySearchServiceAdapter`
keeps its ask/tell interface while forwarding to that same owner.
`SearchLoopRunner` constructs the owner directly, so autotune does not create a
compatibility controller. The owner is internal and is not added to package
exports; `SearchService` and all existing public exports stay unchanged.

## Policy-runtime VOI packet qualification

New qualified VOI observations retain the exact packet manifest view returned by the
policy-runtime packet writer. The fresh funnel admission and snapshot restore both
reopen that selected view and reconcile its manifest digest with the reference, then
check its selected candidate and evaluation-vector inputs. The Core `put_json` default
remains profileless; it is not rebound by artifact ID or by reading whichever manifest
view is current later. Historical profileless packets and 1.3 VOI snapshots remain
readable as score-only candidate history. A missing, malformed, or mismatched selected
view withholds the packet claim while retaining an otherwise valid score-only row.
This manifest-view binding establishes no external authority, unit, calibration, or
scientific adequacy.

## Candidate identity and evaluated input

Level 5 keeps finite stress outcomes separate from model uncertainty. Its
observed-sample diagnostic uses the fresh persisted-source resolution, with
per-scenario passing and violated counts rather than retained issue payloads.
An inline score or scope-shaped metadata does not establish that sample. A
partial source remains partial; an unavailable denominator does not receive a
fraction. The observed finite fraction establishes neither population failure
probability nor model uncertainty. Level 5 preserves the prior model estimate
and its declared provenance, or the existing unassessed envelope when absent.
This diagnostic does not change source admission or promotion authority.

A bare candidate is its full JSON-native dictionary: key spelling alone never
removes a value. Non-string keys, non-finite numbers, Decimal objects and other
native objects are refused because their JSON projection would not preserve the
value seen by an evaluator after restart. Unknown candidate semantics, including
seeds and input versions, belong in the payload. Unbound proposal metadata is
refused instead of silently omitted.

`StrategyAdapter` retains producer-only fields in a typed
`CandidateStrategyContext`; these fields do not enter either the evaluated
candidate or the unrestricted evaluator context. Only an exact funnel-owned
callable receives the proposal separately, and only the same funnel owner can
link the actual Stage A ticket to Stage B. User-provided context keys, including
underscore-prefixed keys, remain evaluator input. Independent funnel requests
run the current stages; no prior aggregate routing, warning, or grant decision is
cached. A matching live Stage A/B split keeps the same ticket but runs its gates
again, with both physical attempts retained in its trace. An opaque or changed
context uses a fresh linked ticket and preserves the preceding attempt's trace.
These measures do not authenticate arbitrary callback behavior.

Policy producers reconstruct `PolicyCandidateSchema`, use its existing hash,
and deliver its JSON projection to the evaluator. Evaluators needing native
Decimal/Value objects need a separately established lossless typed contract.
The current policy node drops strategy-supplied semantic metadata, so such a
suggestion is refused before Stage A. In particular, native Bayesian suggestions
that supply `acquisition_type` remain unsupported by this path until the
consumer meaning and transport are wired; this boundary does not claim full
B124 closure.

Pareto 3.1 retains subject, proposal, and evaluation references and recomputes
identity on fresh read. A matching digest or a caller-writable CAS edge is
consistency, not proof that a producer executed that candidate. Generic
policy-vector entries therefore stay candidate-only and do not establish a
feasible-policy ranked view. Nonempty old snapshots lack an independently bound
evaluation-to-subject relation and are refused without rewriting; re-evaluate
or provide a separately verified migration.

A separate bounded comparison supports one candidate-grade objective from the
registered `policy.evaluation.ex_ante_simulation@1.0.0` method. Runtime resolves
each completed source in the authorized tenant/cell, replays the selected
Foundry/AD01 inputs and whole-objective rule, and compares only sources with the
same complete method, input layout, baseline, environment, registry, execution
settings, and objective contract. The selected candidate's model source and
actual binding must agree. Only the candidate and verified scenario input may
vary. The planner emits a candidate-only, revalidation-required snapshot; the
method-metric-comparison API reopens the completed scoped run and both source selections on
each authorized read. This one-axis model-input contrast does not install a
champion or establish external representativeness, causality, calibration,
feasibility, legal permission, or publication authority. Unsupported or stale
sources are limited rather than ranked.

Current-run transfer history can use the existing manager when a complete
`transfer_fingerprint` matches the actual space and objective rules. Replica
metadata and proposal are retained. Fingerprint tenant and origin are declared,
not independently authenticated; a semantic digest is not a Core artifact ID.
The persisted funnel projection retains the selected source and actual traces,
but arbitrary stages without selected source binding remain candidate-only.
Authentication of a transfer-index producer, durable ticket serialization, a
resolved candidate artifact for downstream artifact-only warm-start consumers,
and external authority remain separate capabilities.

## Pareto Basis Declaration

SearchConfig may receive caller-owned ParetoBasisScope values by view through
pareto_objective_basis_by_view. The controller forwards these typed values through the existing
registry update contract. An empty mapping preserves observed/unknown basis behavior; ranking
against named axes requires an explicit declared scope. This declaration describes the chosen
comparison basis and does not prove that the basis is complete or authoritative.

## Transfer source-scope binding

LessonCard advances to schema 2.0, LessonIndexSnapshot to 3.0, ParetoRegistrySnapshot to 3.1, and TransferSourceScope to 2.0. New lesson and Pareto transfer records use v3 namespaces whose full scope digest includes authenticated, unknown, or explicitly unscoped status. The persisted typed body carries the same status and fresh readers recompute the path/body binding before transfer. Existing v2 namespaces lack that status and remain legacy-unbound; they are not reinterpreted or rewritten. A missing binding is never inferred to mean unscoped. The locator binds bytes and scope fields but does not establish independent source authority.

A live request AccessScope is reconciled with every supplied tenant hash at producer and fresh-consumer boundaries. A routed tenant without AccessScope, and an omitted tenant, remain unknown. Only an explicit tenant_scope_status=declared_unscoped declaration represents an unscoped source. Unknown-to-unknown matches remain candidate-only and carry the unknown status on both the source row and returned artifact; unknown cannot join an authenticated or declared-unscoped source, and cannot authorize cross-tenant opt-in. A lesson card's origin_tenant_hash is data, not owner proof: writers bind records to the explicit source TransferContext or active caller context.

## Transfer schema and request-scope admission

New LessonCard writes use payload and manifest schema 2.0; exact historical 1.0 cards remain readable, and a later write emits 2.0. LessonIndexSnapshot writes use schema 3.0; ParetoRegistrySnapshot writes use schema 3.1 and candidate identity rule `candidate_subject_v2`. The Pareto parser recognizes historical 1.0, 2.0, 2.1, and 3.0 forms plus current 3.1; an unknown version is a typed invalid-source refusal. A nonempty historical Pareto snapshot lacks a verified evaluation-to-subject binding and the active reader refuses it: its bytes remain unchanged for a separately verified migration or re-evaluation. Recognition does not establish source identity: active get_snapshot reads refuse unbound historical snapshots with SOURCE_BINDING_MISSING, and catalog transfer withholds them before returning seeds. LessonIndex 1.0 is also schema-recognized, but its active reader refuses a snapshot without source_scope. No reader infers source identity from a locator or unbound body. CAS lesson readers resolve the selected manifest profile, then require its kind, media type, schema name, and version to match the typed payload. A declaration/body mismatch is refused before transfer use.

Only an absent context or an explicit null nested transfer_context means no nested scope was supplied. A malformed present context, nested scope, status, or cross-tenant flag is refused as INVALID_REQUEST_SCOPE; string truthiness and fallback defaults do not turn malformed data into an unknown candidate scope. Unknown remains candidate-only and does not establish ownership or cross-tenant authority. The shared intake reconciles every supplied task family, domain, run identifier, tenant hash, scope status, cross-tenant opt-in, and timestamp across outer mappings, nested/typed contexts, and explicit caller keywords before selecting a context or candidate fallback. Typed-context defaults that are absent from model_fields_set are fallback values, not declarations; contradictory present values and malformed present values are refused.

A tenant hash is a non-empty identity. Empty or whitespace-only strings are rejected by the typed context, source-scope body, resolver, and partition helper. Explicit None remains the unscoped partition and distinct from every valid hash; this does not establish cross-tenant authority.

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

- Last updated: 2026-10-22

## Search uncertainty current-state lifecycle (AD06 / B161)

The historical SearchUncertaintyBasis / SearchUncertaintyObservation v1 artifacts
remain available for routing history. They cannot populate the current uncertainty
projection, even when their bytes and stage envelope match. The ordinary
uncertainty_envelope remains the conservative historical maximum; the typed
search_uncertainty_current_read surface carries any separately admitted task-scoped
record. Current-read schema 2.0 also resolves the selected current observation,
basis, refinement and scoring profile bodies from their exact profiled CAS refs. It
preserves the historical refs and states only the pinned task epoch; live
currentness remains not_established.

The stage feedback `uncertainty_current_status` describes the resolved current
assessment for the selected task, rather than repeating the immutable pre-dispatch
admission state. It is a task-epoch candidate diagnostic, separate from score
availability, and grants no authority. `search_uncertainty_current_read` is the
inspectable source for the selected basis, observation, refinement, outstanding
unknowns and contested successors. The ordinary envelope is historical; it cannot
supply an independently current risk. The selected state is matched by the exact
admitted basis and predecessor, not by counting obligations; other obligations
remain visible in the typed read. If the selected state cannot be resolved, the
summary is `not_established`. It is not an aggregate across obligations. Consumers
needing the other obligations must read the typed projection. Reissue retains old
artifacts as history, not the current state.

The pre-dispatch Scientist owner reads the selected method FQN and canonical
parameters from `ExperimentState`, records every selected state artifact ref,
input, produced artifact and report ref, and captures the instantiated L0-L6
stage configuration in a strict Search task context. Profile-qualified refs are
included in the source graph; profileless refs are named individually as missing
source selections and are not rebound through the artifact ID. Execution-plan
and method-catalog snapshot persistence retain the exact manifest profiles
returned by their same-write CAS operations, allowing the source graph to bind
the producer-selected plan and catalog views. Existing profileless plan or
catalog refs remain missing; Search does not retrofit their historical views.
The plan/catalog content join also compares any declared `run_id` in those
selected artifacts with the active Search run. A cross-run plan or catalog
snapshot remains an explicit unresolved slice; a matching method name and
parameters do not repair that owner-scope mismatch. It also requires a unique
catalog entry and an exact method-version match: either the plan node's explicit
version or a version embedded in the selected FQN must agree with the catalog;
an unversioned plan node and FQN remain unresolved.
This policy-runtime owner context does not convert that plan/catalog identity into
an HTE method ABI/profile/rule/procedure binding. It also
has no typed bridge from a selected `CausalQuery` or `EstimandAST` to the HTE
request and source-column roles, population, and unit. A workflow
`execution_profile` is not an inference profile, and the free-text
`CausalEffectReport.estimand` is not a typed estimand or variable binding. Those
unresolved slices remain `not_established`; candidate evaluation continues. If a
complete owner-selected task basis is supplied, Search may persist only a
numeric-free `unassessed` obligation before execution.

The per-ticket current pointer is stored beside the existing CAS owner state with
an atomic durable write and process lock. It binds ticket generation and projection
revision to immutable history. Reissue advances the generation and retains earlier
records as history. A successor can replace only the explicit unassessed record for
the same basis and ticket generation. A second distinct same-generation successor
is preserved as a contested state. Cold reads recompute the selected basis inventory
from CAS. The Runtime owner candidate resolves the exact immutable
`job_completed` event, its Search outbox envelope, the event-embedded selection and
owned attempt anchor; this also works for a completed historical attempt after a
later attempt becomes current. The Search consumer is called with the configured
CAS and owner API plus the exact job/event identity; it reloads the owner-selected
Search binding and HTE content, then records a first assessment through the
existing ticket CAS. In the composed path, Runtime may acknowledge only after the
CAS result is read back as admitted or already admitted; an unresolved typed
receipt remains pending for retry. A fresh Search read returns the bounded
persisted projection plus typed payloads resolved from its selected refs; it does
not fit, assess arrays, or write authority. The returned as-of view is not a live
currentness claim. The public RunDetails/API/dashboard consumer is not part of this
Search-owned read and remains a separate surface gap. This Search source packet
defines the receiver API; its Runtime dispatch callsite must be present in the
composed source freeze before the end-to-end route can be called complete.

The receiver content-joins the immutable HTE physical materialization binding to
the same selected source bytes and row order before it can admit a first
assessment. That binding attests physical input materialization, not which causal
variable a source field represents, the unit, or population coverage. A
physically joined point or conditional-native interval can therefore be retained
as a same-basis candidate assessment with those dimensions explicitly
`not_established`; it does not establish population coverage or justify a
unit-normalized routing score. Caller-copied point or interval values cannot
become a Search observation or routing score.

The selected refinement relation is `unassessed_to_assessed_same_basis@1.0`, and the
proposed derived quantity is `relative_interval_halfwidth_routing@1.0`, for candidate
ordering only. Assessment admission resolves the exact typed HTE outcome and
inference basis, then uses a single selected-profile HTEResult v1 as the interval
value carrier; point-only outcomes keep the point artifact, and an unrepresentable
native capture may remain as a typed diagnostic basis. It reconciles those bytes,
source, method, profile, request, selected rows and owner attempt against the
frozen Search task basis. The score remains unavailable whenever unit or scope
comparison is not established. It is not a probability, calibrated risk, pruning
rule, evidence-strength claim, or publication authority. Independent constraints
and unknown dimensions remain separate. Live validity is not inferred from a
task-epoch read. L3/L4 stage envelopes and legacy v1 CAS refs do not mint a native
HTE outcome or Runtime attempt association.

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


### Declared scope and fallback identities

`resolve_transfer_context` reconciles present scope declarations from typed contexts, mappings, and explicit arguments. `fallback_run_id` is used only if no run ID was declared; it cannot override or conflict with a present value. `LessonQuery` predicates are evaluated against the record at each pipeline stage: local reads match the persisted record's current namespace, while transfer source selection applies the same content and scope predicates before projection. A typed `target_context` selects the destination; `origin_domain` remains source provenance and never substitutes for a persisted target record's `domain`. `task_family` must match the transfer contract and `source_run_id` remains source provenance. `query_with_transfer` recomputes effective trust and confidence before charging its final `limit`; a rejected high-ranked candidate cannot hide a later eligible result. Direct `find_transfer_candidates` calls remain capped as raw candidate inspection. A present `tenant_hash` query selector is reconciled with the target context and a conflict refuses. When the legacy optional target is omitted, a source run ID is never promoted to the target run. SearchController binds its current search ID as the target-run fallback; an actually declared conflicting run remains a refusal.


## Completed funnel result reuse

A new submission of a compatible completed result receives a fresh organizational
FunnelTicket, parent and lineage through the same Search uncertainty admission as
an uncached submission. A live split Stage A/B request retains its existing ticket.
`result_reuse_source_ticket_id` identifies the retained result history; it does not
identify a newly executed evaluator invocation. Retained stage prices remain
historical in the trace, while the new request's aggregate cost is unknown until
an actual owner supplies a charge. Reuse adds no scientific observation,
correlation sample or lesson.

Fresh native result projection resolves each selected work packet from the current
CAS/access boundary and preserves its actual execution run, ticket, attempt and
source-result ref. A copied feedback ref or status is not evidence. An unavailable
or conflicting retained packet limits the fresh outcome instead of relabeling that
work as executed for the new request. The ordinary non-reuse serialized shape and
legacy work packets retain their existing history/parser compatibility. Schema
1.0 does not qualify as current-config work evidence. The additional lineage/reuse
projection is emitted only for reused results. These engineering identities grant
no publication or source-currentness authority.

Retained source history is finalized only through a derived current projection;
all public convenience paths consume that projection. Stage A selects its same
highest eligible level after admission, so a later refused stage does not erase
an independently allowed lower-stage exploratory result.

Generic custom-stage context compatibility still depends on the existing cache
identity filter. Its known-key bindings do not prove that omitted timestamps or
object-valued context are neutral to every evaluator. A complete evaluated-input
projection requires the separately owned strict payload/context bridge; this
result-reuse repair does not establish that broader compatibility.

## Explicit plateau profiles and stress direction

`StoppingPresets.default(tolerance_profile=PlateauToleranceProfile(...))` extends
the existing lifecycle stopping owner. The caller supplies a typed direction,
nonempty declared objective scale and finite nonnegative absolute/relative
tolerances. Signed gain is compared in that configured scale; no implicit
direction or unit conversion is supplied. Historical profile-free behavior is
retained. The source-reconciled lifecycle history still decides whether an
objective value exists; a missing/invalid source value cannot become a plateau.
The profile unit labels the explicitly configured scalar scale, not a new
measurement authority or a globally selected tolerance.

Stress evaluation freezes its typed raw direction before sampling or evaluator
work. `StressObjectiveDirectionError` refuses unresolved values instead of
letting them fall through to minimization. The existing duck-composite lower-tail
compatibility convention remains candidate-only. Full stress occurrence counts
and bounded examples remain distinct. The current selected-objective-intent
limitation stays explicit until an independent selected input owner is joined;
changing a presentation cap or adding a direction label cannot establish it.

## Lesson evidence age on transfer (B137)

Local lesson reads and transfer materialization apply the same evidence-age confidence cap before effective-quality filtering. The source CAS record remains unchanged; a stale lesson within the transfer TTL window may remain available at reduced weight. Read or transfer activity does not establish a new evidence verification. An authorized scientific revalidation producer and production authority remain unestablished.

### Persisted sensitivity priors

`SensitivityAwareCandidateGenerator.from_artifact` reopens a fully selected DOE
experiment and reproduces its numerical result before adding `_sensitivity`
metadata. The metadata includes the exact CAS selector and design/analysis
identities; this is an exploratory prior, not a ranking or promotion grant.
Unselected profiles, changed plan/data/results or unreconciled native numerical
sources refuse before adapter construction. This is a replayed snapshot, not
an ongoing source-currentness certification. Direct in-process construction
remains a legacy candidate-only route. See the [DOE owner](../doe/README.md#selected-experiment-replay).
