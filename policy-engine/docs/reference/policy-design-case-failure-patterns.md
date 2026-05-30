# Policy Design Case Failure And Repair Patterns

This is the on-demand register behind the root `AGENTS.md` failure lens. Use it when changing Policy Design Case, governance, evidence, runtime quality, producer, API, dashboard, export, or research-plan behavior.

## How To Use

- Before design: identify which pattern IDs the change could create or close.
- During exploration: record existing anti-patterns found in touched code instead of treating them as background noise.
- During implementation: prefer the correct pattern in the register over new contract vocabulary.
- Before closeout: mention any relevant pattern IDs in the PR or final summary when the change is governance-significant.
- Keep this register compact. Add a new row only for recurring or systemic failures; move long examples to ADRs, plans, or backlog docs.

## Capability Reality Check

Capability = `typed contract/artifact + producer + persisted artifact/event + orchestration bridge + consumer + verification + external/audit/API/dashboard surface or explicit out_of_scope + negative/e2e semantic test`.

If any part is missing, do not call the capability implemented. Mark it precisely as `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, or `semantic_test_missing`.

| Label | Meaning |
| --- | --- |
| `contract_only` | Type/schema/status exists, but no producer, consumer, or workflow uses it. |
| `producer_missing` | A consumer expects an event/artifact, but no deployed producer emits it. |
| `artifact_missing` | Producer logic exists, but the artifact/event is not persisted, queryable, or replayable. |
| `bridge_missing` | Producer and consumer both exist, but orchestration does not connect them. |
| `consumer_missing` | Artifact/event is produced and persisted, but no downstream reader acts on it. |
| `verification_missing` | The chain is wired, but no automated check proves the end-to-end behavior. |
| `implemented_but_not_orchestrated` | A component works in isolation but is not integrated into the runtime workflow. |
| `surface_missing` | Internal capability exists, but API, dashboard, audit, export, or public surface cannot inspect it. |
| `surface_out_of_scope` | No external surface is intentionally provided; the rationale and owner are documented. |
| `semantic_test_missing` | Structural tests pass, but no test proves content-level adequacy or correct authority semantics. |

`semantic_test_missing` capabilities cannot graduate to `implemented`.
Semantic tests should live next to the relevant unit/integration suite, or in a
dedicated semantic/regression fixture when the behavior spans producers. They
must verify content-level adequacy, not only constructor validity, field
presence, checksum integrity, or schema compatibility.

## Register

| ID | Anti-pattern | Correct pattern | Diagnostic question | Closure move |
| --- | --- | --- | --- | --- |
| P01 | Contract-only capability | Demonstrated capability chain | Does the typed event/status/packet flow from real input through producer, persisted artifact/event, bridge, consumer, visible effect, and negative test? | Prove the full chain before claiming capability. |
| P02 | Component sophistication with thin orchestration | Bridge-first orchestration | Do mature components exchange binding artifacts, or only coexist? | Add explicit workflow bridges, especially evidence -> `ClaimRecord` -> lifecycle. |
| P03 | Internal richness with poor external surface | Multi-audience projection | Can PUBLIC/REVIEWER/EXPERT/MACHINE surfaces inspect what the internals know? | Expose typed projections for assurance, invariants, uncertainty, status, and contestability. |
| P04 | Status enum proliferation | Composed status lattice | How does the new status combine with support, publishability, readiness, faithfulness, freshness, admissibility, validity, overridability, and review action? | Keep local statuses, but define cross-status composition rules and mixed-status tests. |
| P05 | Authority dilution | Purpose-scoped authority boundary | Can downstream code confuse projection/diagnostic/package/export with authority? | Boundary/public/closeout artifacts must declare `authoritative_for` and `may_not_use_for`, with consumer-side enforcement. |
| P06 | Shim drift / canonical ownership ambiguity | Sunset-enforced canonical ownership | Are anchors or tests using deprecated compatibility paths or accepted legacy behavior? | Use canonical owners; preserve shim sunset dates, behavioral legacy retirement criteria, and deprecation warnings. |
| P07 | Schema versioning without rule evolution | Rule-versioned semantic replay | Can old closed cases replay under the exact schemas, taxonomies, and rules that closed them? | Store rule/taxonomy version refs and add replay, migration, grandfathering, and reissue behavior for tightened rules. |
| P08 | Time semantics fragmentation | Time-role algebra | Are legal, policy, data, observation, valid, transaction, ingestion, publication, detection, forecast, freshness, retention, and replay times distinct? | Model time roles explicitly and block, transform, project, or limit mismatches. |
| P09 | Implicit soft gates | Owned warning lifecycle | Do warnings have owners, aging rules, accepted-deficit policy, escalation rules, and closeout/publication impact? | Convert soft gates into owned warning lifecycles; test warning aggregation and aging. |
| P10 | Structural-only validation | Semantic adequacy validation | Does "pass" mean semantic adequacy, or only required fields/checksums exist? | Add semantic probes, expert-disagreement fixtures, negative controls, or adversarial cases. |
| P11 | Failure-only memory | Balanced learning memory | Does cross-run learning capture successes as well as failures? | Add success-pattern retrieval/reuse where failure lessons are used. |
| P12 | Producer fragmentation | Producer handshake protocol | Do Lex/Fabric/Scholar/Foundry/Scientist coordinate before post-hoc conflict detection? | Use shared concept/scope handshakes before producer emission where meaning must align. |
| P13 | Contract gravity well | Proportional governance | Does a required gate/artifact justify its marginal cost for producing a valid PDC? | Make requirements authority-level-gated or optional unless their value is load-bearing. |
| P14 | Raw evidence count inflation | Effective independence accounting | Do multiple sources collapse through shared data, authors, methods, lineage, prompts, institutions, or assumptions? | Report effective independent evidence count and collapse reasons before claiming strong support. |
| P15 | LLM speculation laundering | Candidate-to-authority firewall | Can LLM-generated risks, claims, legal readings, participation claims, or method choices become authoritative without producer evidence? | Keep LLM output as `candidate_unverified`, `rejected_speculation`, `typed_blocker`, or `limitation` until producer authority validates it. |
| P16 | Epistemic-regime laundering | Gate-owned regime declaration | Can a design claim risk-regime precision without evidence, or hide available evidence behind precaution/robustness language? | Classify epistemic regime on the A-side, per claim, with asymmetric false-precision penalties and downgrade/upgrade firewalls. |
| P17 | Decomposition / partial-equilibrium laundering | Coupling-gated composition | Is whole-design authority assembled from parts before decomposition validity and cross-effects are grounded? | Prove modular or near-decomposable boundaries before composing authority; entangled cases need system-level evidence or downgrade. |
| P18 | Streetlight measurability laundering | Measurability adequacy declaration | Are measurable proxies optimized and projected as if they exhausted the policy value? | Represent unmeasured/qualitative constructs as limitations or ignorance, with proxy validity and value-loss disclosure. |
| P19 | Aggregation laundering | Subject-granularity and aggregation validity | Does evidence at one aggregation level close claims at another level without ecological-error checks? | Emit aggregation-validity records and block or limit individual/group/jurisdiction scope drift. |
| P20 | Normative choice laundering | Authorized value-choice provenance | Does the system or LLM silently choose objectives, social weights, or value tradeoffs? | Require authorized value inputs, show alternative schedules, and expose multi-principal incompatibilities rather than resolving them silently. |
| P21 | Capacity-feasibility laundering | State-capacity grounded feasibility | Does a design assume administrative, fiscal, enforcement, or delivery capacity that the actor lacks? | Ground capacity assumptions and make absent capacity a blocker, limitation, or design-to-build-capacity obligation. |
| P22 | Mandate-legitimacy laundering | Mandate and legitimacy authority | Are goals or social weights treated as authorized without participation, legal mandate, or governance provenance? | Emit mandate/legitimacy records before objectives and value weights can close. |
| P23 | Stakes and commitment laundering | Stakes/reversibility-gated floors | Are low-stakes or reversible evidence floors applied to irreversible, high-stakes, or catastrophic commitments? | Classify stakes, reversibility, and option value; raise floors or require adaptive/precautionary design when needed. |
| P24 | Strategic-response laundering | Response-model validity | Are pre-policy effects transported into a post-policy world whose incentives and behavior change? | Model Goodhart/Lucas/performativity/capture response or limit claims and route response back into system dynamics. |
| P25 | Search-control laundering | Replayable search frontier boundary | Is a search frontier, best-so-far candidate, or control-plane summary projected as exhaustive, replayable, or authoritative? | Persist `SearchLedger`, search incompleteness, budget cutoffs, and frontier provenance; keep frontier support separate from producer evidence. |
| P26 | Responsibility-integrity laundering | Mandate-bounded human decision integrity | Does the system shift responsibility to a human who was not informed enough to approve, or does the human shift responsibility back to "the AI"? | Require mandate-bounded `HumanDecisionRecord`, active choice for high-stakes/value-laden decisions, disconfirming evidence, and responsibility-integrity checks. |

Notes:

- P15 extends P05 for LLM-generated content. Both require consumer-side
  `authoritative_for` / `may_not_use_for` enforcement, but P15 also needs
  source classification such as `deterministic_producer`, `llm_candidate`,
  `llm_critic`, and `llm_drafter`.
- Build-time validity without runtime enforcement is a P01/P10 variant. A
  proof, benchmark, or offline validator is not runtime authority until the
  runtime path consumes it and fails closed when it is absent or failing.

## Grounding Anchors

These are navigation hints, not complete examples. Keep long analysis in ADRs,
plans, or backlog docs.

| Pattern | Useful anchors |
| --- | --- |
| P01 | `src/polisyos/scientist/governance/continuous/monitors.py`, `src/polisyos/ddm/integration/monitor.py` |
| P02 | `src/polisyos/scientist/evidence/claims/models.py`, `src/polisyos/ir/analytics/*`, `src/polisyos/runtime/quality/semantic_binding.py` |
| P03 | `src/polisyos/core/contracts/runtime.py`, `src/polisyos/runtime/http/services/control/response_shapes.py`, `packages/runtime-api-client/` |
| P04 | `src/polisyos/runtime/quality/scorecard.py`, `approval.py`, `phase_barriers.py`, `src/polisyos/scientist/validation/claim_support.py` |
| P05 | `src/polisyos/runtime/quality/authority.py`, `projection_semantics.py`, `public_export.py`, `authority_reconciliation.py` |
| P06 | `architecture/shims.toml`, `src/polisyos/scientist/evidence/_shim.py`, `src/polisyos/scientist/methods/_compat.py` |
| P07 | `src/polisyos/runtime/quality/schema_compat.py`, `architecture/production_quality/schema_compatibility.toml`, `src/polisyos/scientist/methods/research_dag/replay.py` |
| P08 | `src/polisyos/runtime/http/services/temporal.py`, `src/polisyos/core/contracts/runtime.py`, `src/polisyos/ir/governance/temporal_logic.py` |
| P09 | `src/polisyos/scientist/validation/decision_validity.py`, `src/polisyos/runtime/quality/effective_mode.py`, `src/polisyos/runtime/quality/scorecard.py` |
| P10 | `src/polisyos/core/audit/verifier.py`, `src/polisyos/scientist/validation/citation_faithfulness.py`, `tests/fixtures/production_quality/` |
| P11 | `src/polisyos/scientist/orchestration/memory/failure_lessons.py`, `src/polisyos/scientist/methods/search/lessons.py` |
| P12 | `src/polisyos/runtime/quality/semantic_binding.py`, `src/polisyos/scientist/cross_graph/compiler.py`, `src/polisyos/scientist/cross_graph/conflict.py` |
| P13 | `src/polisyos/runtime/quality/formal_invariants.py`, `src/polisyos/runtime/quality/invariants.py`, `src/polisyos/runtime/quality/scorecard.py` |
| P14 | `src/polisyos/foundry/methods/consensus.py`, `src/polisyos/foundry/methods/equivalence/`, `src/polisyos/scholar/search/models.py` |
| P15 | `src/polisyos/scientist/policy_design/adversary.py`, `src/polisyos/runtime/quality/prompt_tool_ledger.py`, `src/polisyos/scientist/publishing/publisher.py` |
| P16 | `src/polisyos/runtime/quality/capability_white_space.py`, `src/polisyos/scholar/_impl/evidence.py`, `src/polisyos/calibration/` |
| P17 | `src/polisyos/foundry/coupling/des_kernel.py`, `src/polisyos/foundry/methods/catalog/causal/dynamic_graph_dscm.py`, `src/polisyos/pdc/` |
| P18 | `src/polisyos/runtime/quality/semantic_binding.py`, `src/polisyos/fabric/claims/`, `src/polisyos/data_forge/` |
| P19 | `src/polisyos/runtime/quality/concept_spine.py`, `src/polisyos/fabric/entity_resolution/`, `src/polisyos/ir/world/` |
| P20 | `src/polisyos/foundry/welfare/social_weight_provenance.py`, `src/polisyos/participation_requirement/` |
| P21 | `src/polisyos/participation_requirement/`, `src/polisyos/scientist/governance/`, `src/polisyos/runtime/quality/approval.py` |
| P22 | `src/polisyos/participation_requirement/`, `src/polisyos/lex/`, `src/polisyos/scientist/governance/` |
| P23 | `src/polisyos/runtime/quality/case_lifecycle.py`, `src/polisyos/runtime/quality/cost_gate.py`, `src/polisyos/scientist/policy_design/` |
| P24 | `src/polisyos/foundry/methods/catalog/causal/strategic.py`, `src/polisyos/foundry/methods/catalog/causal/policy_learning.py`, `src/polisyos/scientist/feedback/` |
| P25 | `src/polisyos/scientist/methods/search/`, `src/polisyos/scientist/agent/drafter_multipass.py`, `src/polisyos/runtime/quality/capability_ratchet.py` |
| P26 | `src/polisyos/runtime/quality/human_review.py`, `src/polisyos/runtime/quality/approval.py`, `src/polisyos/scientist/governance/` |

## Repair Priority

1. Fix authority, status, and soft-gate ambiguity first: `P05`, `P04`, `P09`.
2. Prevent LLM or projection content from laundering into authority: `P15`, `P05`, `P10`.
3. Make capability real through producer and bridge wiring: `P01`, `P02`.
4. Expose what the system knows to external audiences: `P03`.
5. Protect replay and reproducibility with rule and time semantics: `P07`, `P08`.
6. Preserve evidence strength truthfulness: `P14`.
7. Protect universal-design axis declarations, composition, search, and delegation: `P16` through `P26`.
8. Run complexity audits continuously so repairs do not add ceremonial load: `P13`.

## Maintenance Rules

- Do not add a new enum, gate, artifact family, or public projection without checking P01, P03, P04, P05, P09, P10, and P13.
- Do not touch compatibility roots or imports without checking P06.
- Do not change admissibility, taxonomy, claim-support, or closeout logic without checking P04, P07, P08, and P10.
- Do not change monitoring, DDM, invalidation, reissue, or calibration behavior without checking P01, P02, P07, P08, and P09.
- Do not change evidence producers or cross-graph compilation without checking P02, P08, P11, P12, and P14.
- Do not change LLM formulation, critic, drafting, summarization, or tool-repair behavior without checking P05, P10, P13, and P15.
- Do not change universal policy-design axes, regime classification, decomposition, value choices, capacity, mandate, stakes, strategic-response modeling, design search, or delegation without checking P16 through P26.

## Pattern Lifecycle

- Add a pattern only when it is recurring, systemic, and not already covered by
  an existing row.
- A pattern can graduate to a historical section only after no new instances
  have been recorded for at least six months and an active maintenance rule or
  automated guard prevents recurrence.
- Graduated patterns keep their IDs for archaeological references; new
  patterns use the next available ID.
- If a pattern starts creating ceremonial load, check P13 before expanding it.

## Capability Ratchet

Use the missing-state labels as a maturity metric in implementation plans,
backlogs, and PR summaries. A useful periodic snapshot is:

```text
capability_claims_total:
implemented:
contract_only:
producer_missing:
artifact_missing:
bridge_missing:
consumer_missing:
verification_missing:
implemented_but_not_orchestrated:
surface_missing:
surface_out_of_scope:
semantic_test_missing:
```

The ratchet is directional: over time, capability claims should move from
missing-state labels toward `implemented`, or be explicitly scoped out. New
work should not increase `contract_only`, `bridge_missing`, or
`semantic_test_missing` without a named follow-up owner.

W1.A makes this executable through
`architecture/policy_design_case/capability_reality_report.json` and
`tools/quality/validation/check_policy_design_case_capability_ratchet.py`. The
report includes debt points, purpose multipliers, readiness bands, and
burn-down templates; a red readiness band is acceptable when the report is
honest and owned, but the affected capability still cannot be called
implemented.
