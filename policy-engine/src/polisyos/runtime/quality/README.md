# Runtime Quality

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
