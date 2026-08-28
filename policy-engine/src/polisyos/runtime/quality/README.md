# Runtime Quality

- Last updated: 2026-08-28

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
- `chronology_qualification.py` is the production-internal, owner-qualified
  composition consumer. It resolves the one appointed admission/provenance
  container, independently reconciles native owner truth, and invokes the real
  full-prefix builder and verifier. Cluster 2 has no production family adapter,
  projection receipt, allocation writer, or call site: the consumer is
  `implemented_but_not_orchestrated` and its positive proof path terminates at
  `NativeProjectionCustodyGap`. The strict allocation history records those
  retained labels without promoting whole-history authenticity.
- `chronology_custody.py` is the single epoch acceptance/custody composition root. Its production
  provider resolves acceptance and holder appointments independently and currently returns two
  query-bound `not_established` outcomes: the acceptance owner and epoch-only independent holder
  are both `absent/unallocated`. The generic audit cold tier supplies no chronology appointment,
  object-version receipt, or readback challenge and therefore cannot promote whole-history
  authenticity. The two trust-snapshot domains bind exact appointed bytes; the plan supplies no
  authority DTO for those bytes, so their institutional meaning remains a bounded owner-carrier
  residual rather than a locally invented contract.
- `semantic_epoch.py` is the epoch-family producer and adapter over the common
  full-prefix protocol. It derives sparse owner-native L5, Lex and acquisition
  queries, preserves their complete denominators, and invokes the generic
  qualification consumer from the production acquisition composition. No
  predicate-policy signer is appointed, so that real call terminates at the
  typed `policy_admission_missing` result; the invocation implements the
  producer/consumer capability without establishing a positive epoch policy,
  custody, projection or whole-history authenticity claim.
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
  `absent/unallocated`, automatic global recipe execution remains
  `absent/unallocated`, and public export exposes only the limitation status,
  code, and vector ref—never numeric risk or raw evidence.
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
    recipe execution seam. Per-recipe canonical producers remain
    `producer_missing`, and a global automatic recompute owner remains
    `absent/unallocated`.
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
