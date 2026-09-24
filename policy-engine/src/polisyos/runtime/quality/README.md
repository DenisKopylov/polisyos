# Runtime Quality

- Last updated: 2026-09-13

`polisyos.runtime.quality` owns Policy Design Case runtime-quality artifacts:
authority/status composition, evidence and claim binding, replay, closeout
checks, and audit-oriented exports.

This package may orchestrate producer-backed signals, but it does not make LLM
output, corpus stubs, simulations, or historical priors into current evidence
authority by itself. Those paths remain candidates, caps, context, or replay
inputs until a producer-owned capability admits them.

Rule replay lives in `rule_replay_engine.py`. Closed cases should replay through
their stored rule, capability, and data references, and C33 rule-change classes
must produce explicit revalidation triggers rather than silently changing old
closeout meaning.

Boundary notes:

- `production_invocation.py` is a runnable internal regression instrument over all
  tracked source, tooling and test Python files. It distinguishes calls from
  imports and definitions, follows explicit call paths to runnable roots, and
  reports new or regressed source mechanisms with no resolved path. Named caller
  task deferrals stay explicit. Static paths are diagnostic evidence; they do not
  establish runtime execution, persistence or authority. Its CLI persists and can
  recompute an exact receipt using the lane base. Discover it as
  `polisyos-tools validation check-production-invocation --base REF --receipt PATH`.
  Decorated or registered receivers and their known downstream paths remain
  `unresolved_by_construction`, distinct from direct `uninvoked` diagnostics;
  opaque receiver calls carry unresolved source sites without invented targets.
  Direct traversal stops at coroutine, generator, and lambda bodies; even explicit
  await/next resumption stays outside this conservative source measurement.
  Every stdout verdict names HTTP, DI/container, event-bus, callback, and dynamic
  receiver boundaries it did not measure. Exit 0 is a bounded clean delta,
  1 means direct regressions, 3 means newly unresolved receivers, and 2 means
  UNRUN with no complete verdict. Runtime dispatch is never inferred.
- `production_grounding_calibration.py` persists and replays source discovery
  for the exact current N7 request and world context. The generation controller
  carries the actual N8 requirement into this path. Its relation acceptance slot
  stays typed and empty: publication eligibility and source-row counts cannot
  supply proposal/reference relation gold or a calibration acceptance rule.
  The result is an audit refusal, with CG2 cold-start and N8 blocked; it grants
  no acquired grounding or world write.
- `global_case_index.py` recomputes a tenant/cell-scoped CAS inventory of canonical
  persisted S2 case bindings. The default capability-discovery provider consumes
  its verified snapshots and persists candidate-only search receipts. Coverage
  is limited to that binding vocabulary; terminality and policy authority are
  not established, and the authority appointment slot stays empty.
- Prefer neutral contracts from `polisyos.core.contracts` when lower-level
  packages need DTOs or protocols.
- Keep runtime-only persistence, ledger, replay, and validation wiring in this
  package.
- `acquisition_route_loop.py` owns verified current-route closure and crash-safe
  acquisition phase orchestration. It requires exact source job/CAS/progress/
  terminal-event and C01 cost agreement, persists no owner data itself, and
  resumes only same-case direct re-entry after a durable
  `world_committed_reentry_pending` head. Missing production owners remain typed
  non-closures, and the behavioral fixture can never establish active
  qualification or production world growth.
- `acquisition_world_growth.py` is the internal bridge from the canonical WDI
  execution port to native semantic-epoch admission and same-case N6 re-entry.
  It persists the actual live evidence and prior membership before admission,
  binds admitted observation delta to native owner readback, and persists the
  growth receipt before returning a positive result. A known persisted quarantine
  may be resumed by a separately authorized action after exact policy appointment,
  using the original evidence without another fetch. Admission and re-entry fences
  retain unknown outcomes; an unacknowledged effect is not permission to retry it.
- `semantic_epoch_qualification.py` is the internal native epoch policy owner.
  Its factory composes the existing `EpochDeployment` with independently checked
  signed policy selection, exact member/manifest binding, ancestry denominator,
  and query binding. The shared chronology path persists and reopens the native
  projection before returning qualified evidence. Empty policy or owner slots
  still refuse; configuring a reference alone establishes no native predicate.
- `acquisition_movement.py` is the internal supplier-receipt intake and native
  per-row GY movement family. `AcquisitionActionService` feeds durable terminal
  receipts to it; the existing Depth-N Cycle Board consumes its persisted,
  requalified projection. Supplier completion and signed GY admission are separate
  acts. Movement records a completed later N6 terminal under the new observations
  at the supplier's time; it guarantees neither a better grade nor current overlay
  availability. Missing supplier or projection custody retracts the projection.
  This intake does not close a debt-register row or enumerate all possible rows.
- These three modules are imported by their canonical internal module paths; they
  add no supported package-facade entrypoint. The canonical WDI cost-schedule row,
  institutional mandate/signing appointments, and exact epoch/GY policy admissions
  remain independently supplied inputs. The existing canonical cost producer and
  recomputing consumer refuse the default missing WDI row. Hypothetical fixture
  pricing is mechanism evidence, not an admitted production cost basis.
- `layer3_grounding_inventory.py` is the internal G0 pre-adapter inventory and
  firewall producer. It reads repository architecture/data artifacts, registers
  source touchpoints in shadow form, and enforces quarantine/status/import
  checks without admitting adapters or exporting a stable public facade.
- `layer3_proving_ground_conversion.py` is the G5 first proving-ground
  conversion resolver. It reads bounded Layer 3 persisted artifacts and G4
  handoff records to classify conversion inputs without rerunning upstream
  builders or widening authority.
- `layer3_bounded_agent.py` is the G6 bounded arbitrary-request adapter. It
  consumes policy-grammar projections, runs an allowlisted tool loop, bridges
  same-class requests to G5, and emits replay/continuity audit surfaces for a
  grounded result or abstention without claiming policy authority.
- `layer3_region_widening.py` is the G7 one-case-to-region widening producer.
  It composes G1/G4/G5/G6 readiness, region candidate grounding, mechanism
  reuse, marginal cost, S14 breadth handoff, replay, and projection-only audit
  surfaces without turning the current G5 unchanged blocker into grounded
  region breadth.
- `layer3_health_metric_governance.py` is the G8 health-metric governance and
  D4.4 corpus re-basing producer. It normalizes health metric signals, separates
  cross-metric diagnosis from authority, writes warning lifecycle and re-basing
  receipts, and exposes closeout-readable readiness without closeout authority.
- `runtime.quality` does not eagerly export G0, G5, G6, G7, or G8 modules. Import these
  internal audit producers by canonical module path when a validator or
  reference workflow needs them.
- `chronology_proof.py` is the sealed persistence adapter for the common
  policy-free full-prefix bytes. It derives fixed `ArtifactStore` manifests
  from an owner-qualified native reconciliation, reloads and reruns the real
  verifier, and keeps its one-shot process continuation private. The public
  reader establishes only CAS integrity plus the declared commitment prefix;
  family completeness, acceptance, native authority heads and custody remain
  family-owned and are not inferred from a green proof or audit sidecar.
- `chronology_qualification.py` independently reconciles native owner truth and
  invokes the existing full-prefix verifier. `epoch_deployment.py` captures typed
  per-deployment slots for policy resolution, native verification, signing-profile
  admission, acceptance and history custody. Empty configuration preserves the
  original refusals. `epoch_evidence_exchange.py` verifies exact signed transport;
  signatures do not establish native predicate semantics. A privileged native
  verifier must independently establish those semantics before qualification.
- `chronology_custody.py` remains the single acceptance/custody composition root.
  Its no-argument factory captures the current deployment-local resolver, registry
  and repository. A default deployment still has neither acceptance nor holder
  appointment. Filling independently verified appointment evidence is configuration;
  generic audit storage cannot stand in for independent epoch custody.
- `semantic_epoch.py` derives owner-native L5, Lex and acquisition queries and
  preserves complete denominators. Its configured constructor accepts the captured
  qualification collaborators; `from_unallocated_policy_authority` still emits
  `policy_admission_missing`. The pre-N9 positive query carrier remains a separate
  consumer boundary (EP-D03); native qualification alone cannot promote a candidate.
- `acquisition_epoch_admission.py` is an internal operational module CLI. It resolves
  the configured canonical acquisition provision, invokes the existing complete
  semantic-epoch producer from persisted evidence refs, and reads its exact durable
  refusal or native activation back before JSON output. A configured native owner
  must establish the positive admission; `policy_admission_missing` remains a
  refusal. Historical production receipts preserve their original bytes when the
  optional chronology-projection ref was absent; that compatibility does not supply
  the projection custody required for current positive qualification.
- `epoch_custody_audit.py` is an internal module CLI that invokes the existing
  no-argument custody provider, persists the candidate request and exact typed
  result, and reads both back before emitting an audit reference. The no-holder
  and no-acceptance-owner outcomes remain `not_established`; audit persistence
  does not authenticate the opaque history references.
- `semantic_epoch_store.py` is the epoch family's append-only native history
  repository. Its compare-and-append head index and full-prefix reconstruction
  never become a shared physical chronology log or an authority head.
- `epoch_validity_cascade.py` and `open_world_risk.py` bind the complete
  post-generation candidate denominator to independently reloaded epoch and
  deployment query artifacts before N9. The production epoch query consumes
  the real unallocated-policy qualification path and records
  `policy_admission_missing`; the deployment default persists one
  `not_established` row per model, obligation, and calibration component.
  Neither negative mints policy or deployment authority. Positive lifecycle
  evidence remains `producer_missing`, its institutional owner remains
  `absent/unallocated`, and public export exposes only the limitation status,
  code, and vector ref—never numeric risk or raw evidence.
- `epoch_certificate_issuance.py` implements the Runtime owner behind the neutral
  Scientist issuance port. The actual decision-packet builder prepares a complete
  basis, persists its packet and admits canonical completion. Its frozen owner
  index binds packet, exact executable recipe, source basis and native history.
  No input resolver means a typed nonreceipt, never an empty admitted inventory.
- `epoch_transition_inputs.py` reads canonical native receipt/predecessor sources,
  the complete issuance inventory and independently admitted owner dispositions.
  It computes exact native full-basis deltas; their event carrier remains EP-D04.
  An empty monitor census cannot establish absence of native change.
- `epoch_transition_origin.py` admits a canonical execution record only after exact
  signed persistence and profile admission. Readback recomputes the transition from
  frozen input receipts. A signed artifact copied into CAS cannot substitute for
  origin-owner membership or cryptographic verification.
- `epoch_transition_verification.py` wires the registered run-control epoch-batch
  route to canonical production, origin verification, complete Scientist impact
  enumeration and the existing strict batch owner. Missing configuration retains
  `NoEpochTransitionVerifier`; the request cannot configure authority. Runtime
  dispositions are projected through existing Decision Validity statuses, with
  `reissue` retaining staleness until actual replacement evidence arrives.
- `epoch_denominator_reconciliation.py` recomputes the distinct Runtime and Scientist
  denominators. The configured intake produces a sidecar and invokes its unchanged
  strict reader. First admission freezes an exact handle; replay does not rescan
  newly registered packets. Empty deployments retain a typed unavailable reader.
- `epoch_staleness_projection.py` is the read-only temporal-surface compiler.
  It preserves the real `policy_admission_missing` and
  `epoch_transition_signer_not_established` institutional nonreceipts, while
  classifying the derived recompute projection separately as engineering
  `producer_missing + bridge_missing`. The named candidate owner is
  `polisyos.runtime.quality.derived_observations`; no signer appointment is
  implied by that assignable gap. Positive transition examples remain
  `fixture_only` until an exact owner reader exists.
  The negative path carries these bounded residuals without promoting them:

  - canonical target dispositions remain `producer_missing` for the Decision
    Validity, incident, appeal, correction, and retraction owners. Closure
    requires an appointed complete `EpochPerturbationAdjudicationProvider`
    whose owner evidence is independently reloaded;
  - epoch transition signing profile, signer, exact signed-evidence repository,
    and producer identity remain `absent/unallocated`; the default returns
    `epoch_transition_signer_not_established` and cannot issue a positive
    transition;
  - positive deployment-lifecycle evidence and its institutional query owner
    remain `producer_missing` and `absent/unallocated`, respectively;
  - the verifier-provenance artifact is content-bound and independently
    replayed, but no owner-lineage appointment exists, so positive verifier
    provenance remains `not_established`;
  - the declared-scope manifest is independently reconstructed from persisted
    owner inputs but is not itself persisted as historical owner bytes; exact
    manifest-history replay therefore remains `not_established`;
  - completed-generation denominator admission is process-local. A coherent
    but unadmitted CAS denominator is rejected, but cross-process provenance
    cannot distinguish an owner-issued denominator from forged coherent bytes
    without a persistent generation-owner admission receipt/index, which is
    `absent/unallocated`; the bounded consequence is fail-closed denial of
    service, never false promotion; and
  - recipes are bound as inert bytes and a complete source census rejects any
    ambient execution seam. `derived_observations.py` already owns
    `DerivedSeries`, derivation certificates/materializations, and
    `materialize_derivation`; what remains is an epoch-inheritance/recompute-
    status producer plus temporal read bridge, classified as engineering
    `producer_missing + bridge_missing`, not institutional
    `absent/unallocated`.
- `evaluation_modes.py` owns the exact six executable evaluation modes and a
  strict no-default resolver. `evaluation_safety.py` owns generic ratified
  mode-basis plus domain-pack admission, appointed evidence verification, the
  promotion-independent safety core, post-core N9 classification, certificate
  lineage replay, and immediate consumer revalidation. Positive in-process
  authority carries a private producer capability; persistence consumers must
  replay public raw DTOs through the exported basis, pack, requirement, core,
  event, certificate, and revision reconciliation procedures rather than
  deserialize that capability. The capability is bound to canonical public
  bytes, so a copied or mutated authority must be re-admitted. Basis and
  revision-cause admission resolve typed, independent attestations over the
  exact subject, purpose, rule/schema, component, and effective time. The
  frozen core and certificate bind the appointed evaluator plus the complete,
  non-empty evaluation-input denominator and provenance; Foundry derives its
  input ref from the actual N5 observation. Each positive consumer receipt
  binds the canonical hash of the complete context plus a fresh consumer-
  generated UUID4 challenge, so an unchanged receipt cannot replay across a
  changed context or a second owner call. Consumer replay validates the full
  revision graph while selecting the unique head effective at its current
  verification time. A pack's `source_pack_ref` identifies its
  upstream domain-owned source and participates in the normalized pack hash;
  the normalized pack's external CAS identity is supplied separately as
  `pack_ref`, avoiding self-referential bytes. Intake and canonical request
  identities follow the same external-ref rule. C01 persists or executes
  nothing: CAS/event
  resolution, orchestration, and authority-grade metrics remain C02/C03 work.
- The public experimental facade exports the canonical C04 verification-only
  contracts used by Scientist: `EvalSafetyAdmissionChallenge`,
  `EvalSafetyVerifierPort`, `EvaluationExecutionContext`, `WorldModelRecord`,
  `evaluation_safety_consumer_admission_is_verified`,
  `resolve_evaluation_mode`, and `world_model_record_content_hash`. Scientist
  transports an externally supplied context and verifier unchanged; the causal
  and production evaluation owners fail closed before work, bind the actual
  attempted inputs and world-model record, and cannot be satisfied by promotion
  state. These contracts certify an attempt only. They execute no pilot or
  deployment, appoint no verifier or institution, and confer no execution,
  pilot, deployment, promotion, or governance authority.
- `non_data_acquisition.py` composes the unchanged acquisition planner and its
  persisted report with Fabric's non-data intake owner. It accepts an existing
  typed gap and binds its claim identity; CG5 routing does not establish a missing
  object or lift its candidate ceiling.
- `adaptation_transition.py` composes the existing control outbox, Core CAS and
  PDC authority boundary for durable candidate response custody. Requests survive
  worker interruption and duplicate delivery; the sole decision remains
  `failed_safe`, names the missing signer role, and carries a conservative posture
  and escalation clock. Snapshot readback checks temporal availability and restart
  expiry. No institutional appointment, protected execution or restart approval
  is issued.
- `vocabulary_crosswalk.py` owns canonical movement admission and the E/X/V/C
  identities consumed by `constrained_response.py`. The versioned reference at
  `docs/reference/canonical-vocabulary-crosswalk.v1.json` and its recomputing
  `tools.quality.validation.check_canonical_vocabulary_crosswalk` checker preserve
  candidate source identities beside the existing custody status and refuse
  blocking semantic loss.
- `constrained_response.py` appends constrained E/X/V/C candidate history through
  the existing `adaptation_transition.py` custody store. Its non-test caller is
  `response_corpus_evaluator.py`; `tools.check_response_corpus` independently
  grades the persisted replay and sealed transition expectations. It introduces
  no second state store or Atlas status. Live scheduling remains GY-O1/GY-O3;
  external execution, restart authority and institutional appointments remain
  unestablished, and DS12 owns the later dashboard projection.
- `operator_comprehension.py` extends the existing diagnostic event log with sealed
  synthetic trials and recomputed audit results. Training and sealed examples are
  disjoint; absent eligible opportunities and failed safety cells have fixed
  non-result outcomes. Internal candidate estimators expose no WP-09 bound through
  the public projection, and `human_comprehension_established` is always false.
- Public experimental exports must be reflected in the public-surface
  inventory and release fragments before release promotion.

Workspace ownership:

- `polisyos.pdc._impl.gy_waist` owns the Ring-1/Ring-2 GY contracts. It must
  remain engine-free and must not import runtime, Scientist, Foundry, or HTTP
  modules.
- `workspace/loop.py` owns the Phase-2 orchestration bridge. `WorkspaceLoop.run_intent`
  is the demonstrated authority path for Phase-2 proofs: intent selection,
  playbook projection, legacy adapter execution, spine gates, Foundry
  consumption, candidate events, and the resulting `SearchExitContract`.
- `workspace/workflow_playbook_projection.py` is a projection layer over canonical Scientist
  `WorkflowSpec` definitions and `NodeRegistry`/`NodeSpec` metadata. It must not
  become a hand-maintained workflow table.
- `workspace/scientist_node_adapters.py` owns the `ScientistNodeAdapter` and GY-specific shape checks.
  Semantic adapter preservation remains owned by `adapter_contracts.py`.
- `workspace/spine_repair_gates.py` contains shared typed helpers for GY proofs. Enforcement
  belongs in the existing domain homes: `scientist.policy_design.search` for
  bounds/frontier repair, Scientist causal/search nodes for blocked inputs, and
  governance nodes for normative arbitration plus the phase-5 judge gate.
- `workspace/foundry_consumption.py` owns the Phase-2 ESTIMATE/SIMULATE bridge: consumed Foundry
  method outputs, persisted `MethodOutputConsumptionRecord`s, and
  `ConstraintStore` ingestion/consumption. Do not split constraints into a
  parallel Phase-2 sidecar.
- `workspace/agent_proposal_bridge.py` is a thin GY projection over `proving_ground/bounded_request_agent.py` and the
  existing knowledge-tool/tool-loop homes. Agent outputs remain Ring-1
  candidate-only; VOI/usefulness scores pass through GY-H normalization.
- `cycle_substrate.py` owns the content-bound candidate-evidence envelope shared
  by one generation-cycle run. It binds canonical substrate-registry, world,
  intervention, lever, and transport evidence without loading packs by filename
  or granting grounding, transport, or promotion authority.
- `confidence_ledger.py` owns durable anytime-valid promotion-risk accounting.
  It resolves data-registered instruments through code-owned proof kernels,
  binds predictable claims to the prior ledger head, burns exact schedule risk
  before execution, and exposes only the narrow N9 promotion and future N12
  epoch-reference projections. Its bound is always conditional on obligation
  completeness and validator soundness; fixed-time labels and caller-authored
  spend never confer promotion authority.
- `obligation_coverage.py` owns the negative-only coverage envelope over the
  canonical registry and runtime semantic-ledger projection. It has an
  unresolved open-world arm and a verifier-proven concrete-omission arm; the
  latter is reachable only through a CAS-resolved, content-bound, exact-scope
  witness. It emits no positive completeness arm and claim narrowing cannot
  rescue the protected action.
- `confidence_ledger_surface.py` owns the exact local risk-spend projection.
  It derives all 15 obligation allocations, 13 instrument definitions, actual
  ledger instances, the complete six-route registry, registry/profile blockers,
  the explicit honest-zero positive register, and exact-or-blocked safety
  reasons. Class rows and the one scope-total row expose allocation, spent,
  remaining, and overspend as conditional amounts, so consumers perform no
  budget arithmetic. Every amount retains its exact rational,
  envelope/scope/owner binding, and both conditionality disclosures; no parent,
  family, sequence, or cross-scope total is asserted.
# S3 observation routing and law correspondence

`intervention_substrate` owns the generic L6 manifest parser and resolves every
route against actual Foundry input contracts. N8 derives its route constraint from
the manifest at selection and receipt replay; N4 consumes the same full route set
for candidate search. Repeated families are ambiguous even when their modes or
targets differ. The closed IR observation-family enum is not a registration gate
for data-only family growth.

`FoundryValuePort` and the controller's lazy default accept an optional
`observation_family`. The selection input preserves it through reentry and binds
it through the existing route owner. An omitted manifest uses the freshly
verified `CycleSubstrateContext.intervention_substrate` source when available;
an explicit override must match that bound source. Missing family scope remains
an honest refusal for ambiguous source routes. Explicit null source is invalid,
and the private omission sentinel is preserved through configuration forwarding.

Bundle, knob and route records retain lift v2. Law-resolution records use v3;
the current S3 report uses v4 and independently requires its own synthetic
marker. The strangle packet uses v2. Foundry's
`legal_correspondence` owner resolves separately addressed source memberships and
compares namespace, namespace version and subject identity before runtime asks
L3 to evaluate a numerical threshold. Missing subject returns ambiguous with
numeric evaluation not run. Source-relative recognition and the real threshold
result remain distinct from current legal authority, which is blocked for
synthetic or unverified source identity. Synthetic annotations are retained in
both controlling source artifacts and derived results. Historical v1/v2 law
records retain their original projections and do not acquire current authority.

The real L6 bundle still lacks an independently authorized legal-subject spine.
The CORR controls exercise every real executable pair against independently
addressed marked annotations, including correct and transposed pairs. Their
mechanical proof does not supply the requirement
`lever-legal-subject-key-in-the-norm-namespace`.

## CG2 admission accounting and pre-outcome frames

`grounding_bind.GroundingBindGate` remains the sole binder. Its v2 decisions
carry synthetic ancestry, a run-admission observation and a recomputed strangle
of per-attempt charging. `grounding_risk.GroundingRunBudget` extends existing
Core CAS and Fabric locking: only admitted bindings debit the configured run
allowance. Replayed admissions are idempotent; missing cache heads cannot reset
spend, and unresolved durable state cannot create a new balance. Exhaustion or
missing persistence retains candidate custody under INT-K06 with no correctness
number. Historical v1 certificate serialization omits the added v2 fields.

`grounding_calibration` owns dated input-only frames and constructed-mismatch
suite declarations. Difficulty depends on input structure; source-sharing
components are the declared observation unit. Model, prompt, birth cohort and
reference changes stale the epoch scope. No empirical calibration is issued by
this mechanism. Refusal sensitivity has its own named output and always carries:
A high refusal rate on constructed mismatches is not evidence that accepted
bindings are correct.

The current CG2 contract report retains the canonical reference attempt and its
confidence-withholding result separately from the marked structural mechanism
controls. A green mechanism report grants no canonical admission credit. The
registered refusal-result checker recomputes the unchanged dated declaration;
`--check` never replaces the persisted result.

CG2 and CG3 report envelopes use v3 for their shared complete proof-world input.
The existing `grounding_calibration` owner resolves the independently addressed
declaration against the original Core artifact, including its byte identity,
schema, logical world hash and creation time. A fresh WMR with an equal logical
hash is not the declared input. Missing source custody fails closed; the marker
and report purpose keep these synthetic controls outside production authority.
Certificate epochs remain v2.

CG3 retains the existing novelty and shadow-registration owners. Current v2
certificates, registry patches and admission ledgers each carry their own
synthetic provenance. A mechanically admitted novel lever can enter the shadow
registry while remaining non-promotable. The admission owner recomputes source
ancestry instead of trusting a caller's CG2 flag. Historical v1 child bodies and
hashes remain readable without acquiring the added v2 fields.

## N4 source custody through N6 and N9

`generation_source` persists the existing N4 organ's typed Trinity bundle,
candidate atoms, parsed-candidate provenance, grounding inputs and bound cycle
substrate in Core CAS. It replays the complete source and resolves the exact
problem/candidate/atom identity. N6's default N4 port retains the organ instead
of discarding it after projecting a result. Current run and acquisition-reentry
v2 envelopes retain the source references, source limitations and a recomputed
preservation strangle. Repeated identical source occurrences are idempotent;
conflicting occurrences do not yield writer inputs.

The capsule uses Core's typed canonical codec so Decimal values survive custody.
N9's existing EFFECT writer owns its JSON wire projection; the handoff accepts
that projection only when the real grounding owner reproduces the complete
original certificate. Missing references or changed grounding semantics produce
`not_established`. Missing writer inputs stay absent. The mechanism neither
reconstructs a design from catalog defaults nor supplies protected admission.

The N9 evidence bridge uses v3 to separate the real producer's mechanical
disposition from authority. Its own synthetic marker is recomputed from actual
source bytes and the bound candidate. The independently persisted independence
and EFFECT source records use v2 and carry their own marker as well. Synthetic
evidence cannot resolve as authority-grade established evidence. Historical
bridge v1/v2 and source v1 bodies retain their original epochs; N9 receipt v6
and owner projection v3 remain unchanged.

## Protected promotion request custody

`promotion_safety` is the N9 protected-mode request custody owner. The canonical
N9 evidence intake persists the exact candidate/problem/value-receipt/mode scope
and attempted signed source references through the existing CAS, carries the
request in `producer_root_refs`, and independently replays it at the EvalSafety
obligation. Source signatures establish candidate attribution only. The
promotion-purpose rule, appointed authority and independently verified acceptance
remain typed-empty; every protected attempt still refuses `scope_insufficient`.
The request exposes actual reads and named unresolved scientific boundaries.
Historical no-request receipts and the attempted-evaluation O0 authority remain
unchanged; request custody uses its own additive v1 schema.

## Promotion evidence input selection

The default N9 production port and `GenerationCycleController` consume the fixed
`PromotionRuntime.promotion_evidence_source` slot. `N9PromotionEvidenceSource` captures
typed selections as immutable JSON and matches the exact problem binding, candidate
artifact identity/hash and whole-summary hash. It forwards existing independence and
measurement writer inputs, the configured measurement catalog/providers, candidate
promotion-safety source refs and an optional G4 record ref. Selection grants no
authority: the existing producer/replay owners decide admissibility. Every selection,
including the default empty slot, persists an audit receipt naming actual inputs read
and `unresolved_by_construction` boundaries. S6/S7/S8 flags are excluded from this
selector; their existing empty canonical projection slots retain the real refusals
until evidence-to-protected-purpose admission semantics are established. The generation
decision-front replay carries the same epoch resolver used to admit the candidate.

## S8 generation disposition

`design_axes.value_choice_provenance.NormativeValueScheduleOwner` owns the source-aware
S8 admission and selection projection. The generation path uses authorization and
admission v2; standalone v1 remains readable under its own schema. A generation
binding identifies exact compiled and leaf CAS sources plus the node. S8 verifies
the leaf source and signed frontier; the existing HTTP compiled-run owner verifies
the parent-to-leaf association. A standalone S8 leaf explicitly records compiled
membership as `not_established`.

Generation dispositions preserve every source candidate front and carry a typed
request when authorization is missing. Existing authorized Pareto evidence reaches
the same ranked consumer when its source, independent signatures, deployment role,
scope and time are valid. Current projection recomputes persisted content and
rechecks authority; it does not copy a historical `authorized` field. The additive
artifacts do not change the generation, promotion or standalone S8 epochs.

Stage 2 delivery boundaries and deciding evidence are recorded in
[`2026-09-12-epoch-positive-path-stage1.md`](../../../../docs/superpowers/specs/2026-09-12-epoch-positive-path-stage1.md)
under the appended Stage 2 sections. Historical labels in the temporal-surface
paragraph describe its unchanged consumer; they do not establish absence of the
new canonical owner mechanisms. No institution is appointed by these modules.
