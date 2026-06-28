# Policy Design Case Failure And Repair Patterns

Owner: `team-policyos-runtime`
Source of truth: `AGENTS.md`, `policy-engine/AGENTS.md`, and this register.

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
| P27 | Parallel re-implementation / canonical-owner bypass | Owner-first placement | Does an existing module already own this concept, or is new logic (a type, engine, gate, planner, or fixture) being created beside it — often named by slice/plan (`gy_*`, `slice0_*`) instead of by domain? | Locate the canonical owner by concept (grep the concept root across the owning packages) and extend it; route slice work into the owner and delete the parallel copy. Watch the dual symptom: orchestration over-concentrated in one slice god-file while thin wrappers proliferate — both are placement-by-slice-identity, not by owner. |
| P28 | Additive migration / un-strangled legacy | Strangle-fig replacement | After adding the better approach, can the superseded path still be reached by default (a fix gated behind a default-off flag, legacy left callable, zero deletions on a "replace/subordinate" change)? | Fence or delete the predecessor in the same change, flip the default to the corrected path, and record the sunset/guard so the two cannot coexist. A replacement that only adds a layer over the legacy default has not migrated anything. |
| P29 | Authorial proof / self-attested artifact | Recompute-from-live evidence | If the committed proof/benchmark/closure artifact were deleted, would the validator reproduce it from a real run — or does it only check shape/refs over a hand-authored payload (placeholder ids, round `…T00:00:00Z` times) or a strawman fixture corpus where the metric is vacuous, or only confirm that marker strings / field names are present while the runtime property it guards is broken? | Emit proofs from the real path; validators must re-derive the claim from live code/artifacts and fail on drift; benchmark substrates must be representative (real corpus or a declared `surface_out_of_scope` rationale), not trivially separable fixtures; the drift-check/self-check itself must FAIL on a corrupted artifact (verify the verifier) — a `--corrupt-field-drift-check` that returns success on a corrupted input is decorative. A gate/contract for a semantic property (a runtime cap, a round-trip, a strangle, a promotion rule) must **exercise the real runtime** (import + run the real path and assert the property holds/fails), not confirm that marker strings or field names are present; prove it with the *remove-the-property-keep-the-markers* probe — if the gate stays green when the runtime semantic property is deleted but its marker strings remain, the gate is form-based and must be rewritten to behavioral. **Stopping point (do not regress infinitely):** a verifier is *complete-by-construction* when it is GENERIC over the actual source of truth — it derives its check set from the runtime's own rejection reasons / the artifact's own schema fields / the actual objects (no hand-enumerated list), walks them recursively (including list elements and nested objects on a fully-non-default sample), and its exemptions are GENUINE constraints (a "justified default-only" field must be truly type-constrained, e.g. a `Literal`/discriminator, not a `str` loophole). Once it is generic with genuine exemptions, coverage of FUTURE additions is governed by THIS rule + review — not by recursively verifying the verifier. An audit that can only construct a HYPOTHETICAL future field/root that would escape a GENERIC mechanism (rather than an actual present gap or a non-generic enumerated set) is a GO, not a NO-GO; do not add another meta-level. |
| P30 | Provenance-named modules (plan/slice/wave-scoped file names) | Domain-function naming with discovery breadcrumbs | Does the module/file/symbol name describe the capability it owns, or only the plan/slice/wave that created it (`gy_*`, `slice0_*`, `wave5_*`)? Would an implementer grepping by concept find it and its relatives, or re-create them? | Name modules by the function they own, not their birth plan (`workspace_loop.py`, not `gy_loop.py`). If a provenance prefix is truly unavoidable, the module docstring must name the canonical owner(s) it extends and link related modules so the next implementer reads them before writing a parallel file. Provenance naming is the upstream enabler of P27. |
| P31 | Instance-patching over structural invariant (enumerate-and-route) | One chokepoint/invariant for the whole class | Is the fix closing the one named site while a sibling consumer/intake/surface of the SAME class stays open — so a synonym, another consumer, or another producer reopens it next round? | When a defect is an instance of a class (e.g. "authority emitted from unverified evidence", "bytes leave a surface without the admission gate"), close the class with ONE structural chokepoint/invariant — single intake AND single emission — not a per-site patch. Prove no sibling bypass by enumerating every write/read/intake of the class and grepping that each routes through the chokepoint. |
| P32 | Trust-by-form (presence/shape/string/keyword/self-attestation = permission; absence = permission) | Resolve-bind-verify evidence intake, fail closed on absence | Does an authority/promotion/Ring-2 decision admit evidence because a ref/field is PRESENT, well-SHAPED, name/keyword-matched, or self-stamped with a verifier role — or because it RESOLVES to a committed artifact, CONTENT-BINDS by hash to THIS claim/graph/program/port, and carries VERIFIER (non-producer) provenance? Does absence grant, or fail closed? | Admit evidence for an authority decision only via resolve + content-bind + verifier-provenance; presence/shape/keyword/string/inline/self-attestation is not evidence; unresolved/mismatched/missing → cap/block, never grant. This operationalizes P05/P10/P15 for reference-based evidence and is the unifying root behind `model_construct` bypass, synthetic-as-measurement, `no_authority->allowed`, keyword-feedback, and presence-of-ref laundering. |
| P33 | Witness-as-spec / teaching-to-the-test | Property fix + adversarial-variant self-generation | Does the fix make the EXACT acceptance/audit probe pass while a near-variant (synonym, malformed input, present-but-fake ref, cross-bound id, another consumer) re-breaks it? Is the probe being treated as the specification? | Fix the general property the probe samples, not the probe. Before claiming done, self-generate and pass adversarial variants of every probe (synonym, malformed, present-but-fake, partial-bind, sibling consumer). An audit probe is a witness, never the spec. |
| P34 | Premature-green via uncompleted exclusion | Completed isolation before exclusion | Is a failing test/lane excluded by calling it "honest-empty" or "unrelated / pre-existing dirty worktree" WITHOUT a completed revert/stash isolation proof? Could the change itself have caused it, or is a broken downstream state (inconsistent manifest, blocked-used-as-conversion) being asserted honest? | Complete the isolation — revert/stash only the change and confirm the failure is independent — before excluding it. Prove an "honest" downstream state is actually honest (consistent top==summary status, no laundering), not merely relabeled from a fail. |

Notes:

- P15 extends P05 for LLM-generated content. Both require consumer-side
  `authoritative_for` / `may_not_use_for` enforcement, but P15 also needs
  source classification such as `deterministic_producer`, `llm_candidate`,
  `llm_critic`, and `llm_drafter`.
- Build-time validity without runtime enforcement is a P01/P10 variant. A
  proof, benchmark, or offline validator is not runtime authority until the
  runtime path consumes it and fails closed when it is absent or failing.
- P27 is the net-new sibling of P06 and P12. P06 covers drift toward a
  deprecated compatibility path; P12 covers producers that do not coordinate;
  P27 covers building a *fresh* type/engine/gate beside a live canonical owner
  instead of extending it. Slice/plan identity (`gy_*`) is not a module
  boundary.
- P28 extends P06's sunset discipline from compatibility shims to whole-approach
  replacement: when the new path lands, the predecessor must be deleted or
  guarded and the default flipped, not left as the reachable default.
- P29 is the evidence-artifact dual of the build-time note. A proof is authority
  only when it is *emitted by* the run it claims and the validator *recomputes*
  it from live code/artifacts. A hand-authored proof packet, or a closure metric
  computed on a strawman fixture corpus, reproduces the very `authorial-refs`
  laundering it is meant to prevent.
- P30 is the upstream enabler of P27 (and so of P28). A module named for its plan
  (`gy_loop.py`) hides its function, so the owner-first grep misses it and the next
  plan re-implements `workspace_loop` again beside it. Naming by function is the
  cheapest structural defense against parallel re-implementation: it makes the
  existing owner self-evident, so reuse/extension becomes the path of least
  resistance. The fix is not cosmetic — it changes which file the next implementer
  opens first.
- P31/P32/P33 came from the GY-G composition saga (~7 NO-GO rounds). They are the
  meta-lessons: each round flipped the named probe (P33) but a sibling consumer of the
  same class reopened it (P31), because the gate trusted a ref by form rather than
  resolving it (P32). The break-the-cycle move is always the same: turn the instance fix
  into one structural invariant (single intake + single emission), admit evidence only by
  resolve+content-bind+verifier-provenance, and self-generate adversarial variants before
  declaring done. P34 is the partner: do not let an excluded "honest/unrelated" failure
  close the loop without a completed isolation.

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
| P27 | `src/polisyos/runtime/quality/workspace/loop.py` remains too broad; guardrails now require `WorkspaceSearchLedger` to extend canonical `SearchLedger`, GY acquisition to call `runtime/quality/acquisition_planner.py`, the Slice-0 catalog to use `data_forge/read_api/catalog.py`, and `workspace/spine_repair_gates.py` lex checks to delegate to `scientist/policy_design/search.py` |
| P28 | `src/polisyos/scientist/policy_design/search.py` now defaults `require_explicit_parameter_bounds=True`; legacy inferred bounds must be explicit compatibility/test posture, with remaining strangle anchors in `architecture/shims.toml` and `architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json` |
| P29 | `architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json` is recomputed by `tools/quality/validation/check_layer3_gy_loop_artifacts.py --check`; remaining representative-substrate risk lives in `architecture/policy_design_case/layer3_gy_semantic_benchmark.json` until F4/F7 run on a real corpus |
| P30 | `src/polisyos/runtime/quality/workspace/loop.py`, `workspace/foundry_consumption.py`, `workspace/agent_proposal_bridge.py`, `workspace/scientist_node_adapters.py`, `proving_ground/bounded_request_agent.py`, `adapter_contracts.py`, `semantic_binding.py`, `data_forge_binding.py`; the 124-file `src/polisyos/runtime/quality/` namespace |
| P31/P32/P33 | `src/polisyos/runtime/quality/design_axes/coupling_composition.py` (GY-G: `resolve_bind_verify` single intake, the `verified_evidence` collection, and the single authority-emission chokepoint + guard) vs the per-site patches that kept reopening on the next consumer (consistency -> P14 -> cert -> emergent grounding -> SubDesignContract port intake); `src/polisyos/pdc/_impl/gy_waist.py` `assert_ring2_verifier_provenance` (Phase-0 boundary check the composition gate must reuse) |
| P34 | the GY-G G5 exclusion (`layer3_proving_ground_conversion.py` no-governed-input terminal — asserted honest, was laundering blocked-as-conversion) and the canary/public-export exclusion (`runtime/quality/public_export.py` dirty worktree — only confirmed unrelated after a completed stash isolation) |

## Repair Priority

1. Fix authority, status, and soft-gate ambiguity first: `P05`, `P04`, `P09`.
2. Prevent LLM or projection content from laundering into authority: `P15`, `P05`, `P10`.
3. Make capability real on its canonical owner — named by function so the owner is discoverable, with the predecessor strangled and a representative substrate: `P01`, `P02`, `P27`, `P28`, `P29`, `P30`.
3a. For any authority/promotion/Ring-2 decision: close the class with one structural invariant, admit evidence only by resolve+content-bind+verifier-provenance, test the property not the probe, and finish isolation before excluding a failure: `P31`, `P32`, `P33`, `P34`.
4. Expose what the system knows to external audiences: `P03`.
5. Protect replay and reproducibility with rule and time semantics: `P07`, `P08`.
6. Preserve evidence strength truthfulness: `P14`.
7. Protect universal-design axis declarations, composition, search, and delegation: `P16` through `P26`.
8. Run complexity audits continuously so repairs do not add ceremonial load: `P13`.

## Maintenance Rules

- Do not add a new enum, gate, artifact family, or public projection without checking P01, P03, P04, P05, P09, P10, and P13.
- Do not create a new module, type, engine, gate, planner, or fixture under a slice/plan name without checking P27: confirm no canonical owner already holds the concept, and prefer extending the owner over a parallel file.
- Do not name a new module, file, or public symbol after the plan/slice/wave that created it (P30): name it by the capability it owns. If a provenance prefix is unavoidable, the module docstring must point to the canonical owner and related modules.
- Do not land a replacement, repair, or "subordinate the engine" change without checking P28: in the same change, delete or guard the superseded path and flip the default to the corrected one; a default-off fix or a zero-deletion replacement has not migrated.
- Do not commit a proof, benchmark, capability, or closure artifact without checking P29: it must be emitted by the real run, recomputed by its validator from live code/artifacts, and measured on a representative substrate (or marked `surface_out_of_scope`); confirm the drift/self-check itself fails on a corrupted artifact.
- Do not fix an authority/promotion/gate/admission defect site-by-site without checking P31/P32: close the whole class with one structural invariant (single intake + single emission), admit evidence only by resolve+content-bind+verifier-provenance (never presence/shape/keyword/self-attestation), and grep that every sibling consumer/intake routes through it.
- Do not declare a fix done by passing the named probe without checking P33/P34: fix the property and self-generate adversarial variants (synonym, malformed, present-but-fake, sibling consumer); do not exclude a failing test as "honest/unrelated" without a completed revert/stash isolation.
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
