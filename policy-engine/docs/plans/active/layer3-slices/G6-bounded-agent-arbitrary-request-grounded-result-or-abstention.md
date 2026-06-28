---
plan_id: layer3-g6-bounded-agent-arbitrary-request-grounded-result-or-abstention
title: "G6 - Bounded Agent Arbitrary Request Grounded Result Or Abstention"
type: slice-plan
status: active
created: 2026-06-10
revised: 2026-06-10
stability: ready-for-implementation
slice: G6
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - docs/plans/active/layer3-slices/G5-first-proving-ground-conversion.md
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/reference/policy-design-case-layer3-proving-ground-conversion.md
  - architecture/policy_design_case/layer3_g5_readiness_manifest.json
  - architecture/policy_design_case/layer3_g5_conversion_records.json
  - architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json
  - architecture/policy_design_case/layer3_g5_conversion_audit_surface.json
  - architecture/policy_design_case/layer3_g5_public_export_projection_refs.json
  - architecture/policy_design_case/layer3_g5_conformance_report.json
  - architecture/generated_artifacts.toml
  - architecture/public_surface/contract.toml
  - architecture/policy_design_case/inventory.json
  - src/polisyos/policy_grammar/__init__.py
  - src/polisyos/policy_grammar/_impl/compiler.py
  - src/polisyos/policy_grammar/_impl/schema.py
  - src/polisyos/policy_grammar/_impl/consumer.py
  - src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
  - src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py
  - src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py
  - src/polisyos/runtime/quality/prompt_tool_ledger.py
  - src/polisyos/runtime/quality/hypothesis_ledger.py
  - src/polisyos/runtime/quality/candidate_firewall.py
  - src/polisyos/runtime/quality/nl_replay_orchestration.py
  - src/polisyos/pdc/_impl/layer2_readiness.py
  - src/polisyos/pdc/_impl/layer2_design_search.py
  - src/polisyos/scientist/orchestration/llm/factory.py
  - src/polisyos/scientist/orchestration/llm/simulated_gateway.py
  - src/polisyos/scientist/agent/tools/registry.py
  - src/polisyos/scientist/agent/tools/schema.py
  - src/polisyos/scientist/agent/tools/tool_loop.py
  - src/polisyos/scientist/agent/tool_contracts.py
  - tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py
context_inputs:
  - tests/unit/policy_grammar/test_universal_policy_grammar_compiler.py
  - tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py
  - tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py
  - tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py
  - tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py
  - tests/unit/runtime/quality/test_prompt_tool_ledger.py
  - tests/unit/runtime/quality/test_candidate_firewall.py
  - tests/unit/scientist/agent/tools/test_tool_loop.py
  - tests/unit/scientist/agent/tools/test_tool_registry.py
  - tests/unit/scientist/agent/test_tool_contracts.py
cells_targeted:
  - layer3.g6_bounded_agent
  - layer3.g6_request_envelope
  - layer3.g6_candidate_grammar_expansion
  - layer3.g6_grounding_demand_identification
  - layer3.g6_orchestration_choice_audit
  - layer3.g6_g5_bridge
  - layer3.g6_agent_run_record
  - layer3.g6_public_reviewer_expert_machine_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g6_bounded_agent
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G6 - Bounded Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first bounded arbitrary-request agent that routes natural
language policy demand into the G5 grounded loop, then emits either a G5-grounded
result, a G5-grounded abstention, an out-of-envelope grounded abstention, or the
current G5 unchanged blocker without letting LLM text satisfy authority.

**Architecture:** G6 lives in `runtime/quality` as an adapter around existing
Scientist LLM/tool infrastructure, typed policy-grammar projections, replay
continuity helpers, and the G5 typed builders. The LLM/tool loop may generate
request parses, search choices, and counterexample probes, but G5 remains the
only bridge to conversion authority; every agent branch is recorded as
candidate-only and consumer-side firewalls must reject authority laundering.

**Tech Stack:** Python 3.14, strict Pydantic DTOs, `scientist/orchestration/llm`
gateway/simulation clients, `scientist.agent.tools` structured tool registry,
runtime-quality prompt/tool and hypothesis ledgers, runtime replay/continuity
helpers, G5 readiness builders, repo-quality artifact drift tests, and
architecture guardrails.

---

## Current Reality After G5

Fresh command run on 2026-06-10:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py --repo-root . --output-format json
```

Observed status:

- G5 readiness passes with no persisted artifact gaps.
- `g5_conversion_outcome = "unchanged_blocker"`.
- `g5_grounded_conversion_count = 0`.
- `g5_grounded_abstention_count = 0`.
- `g5_w12d_consumer_gate_status = "pass"`.
- `g5_envelope_expansion_rate = 0.0`.
- `g5_public_surface_status = "pass"`.

This is a real G5 loop and surface, but it is not a useful grounded design yet.
G6 must preserve that honesty. If the arbitrary request maps to the current
G5 pinned class, the agent may report the G5 unchanged blocker as a bounded
result of orchestration, not reword it into `grounded_limited` or
`grounded_abstention`. If a request is outside the declared G5 envelope, G6 may
emit an out-of-envelope grounded abstention with replayable envelope and search
reasons. If a future G5 run produces `typed_blocker -> grounded_limited` or
`typed_blocker -> grounded_abstention`, G6 must project that through the same
typed bridge without code-path change.

## Non-Negotiable Alignment Notes

G6 has two different status readings, and the implementation must keep them
separate:

- **Engineering readiness:** the bounded agent producer, ledgers, G5 bridge,
  surfaces, registrations, and negatives are implemented and replayable.
- **Grounded value closure:** an arbitrary request yields a G5-grounded result
  inside the declared envelope or a grounded abstention outside it.

With the current G5 artifacts, same-class MSME demand routes to
`unchanged_blocker`. G6 may pass engineering readiness while reporting
`g6_grounded_value_closure_status = "blocked_by_current_g5_unchanged_blocker"`
for same-class useful output. It must not mark same-class grounded value closure
as `pass` until G5 emits `typed_blocker -> grounded_limited` or
`typed_blocker -> grounded_abstention`. The outside-envelope path can close only
as a grounded abstention when search recall, index freshness, envelope refs, and
demand refs are present.

G6 must also avoid turning a small request classifier into a domain template
system. The implementation may use pinned-case fixtures in tests, but production
routing must be grammar/facet-first and joined to G5 envelope and claim-family
refs. Hardcoded keyword lists are allowed only as bounded test fixtures or
explainable fallback blockers; they cannot be the authority for request class,
grounding scope, or abstention quality.

The grammar/facet-first route has a concrete owner, but also an import-boundary
constraint. `architecture/imports/policy.toml` currently allows `runtime` to
import `scientist`, `pdc`, `core`, and `ir`, but not `policy_grammar`. Therefore
the default G6 implementation must not import `polisyos.policy_grammar` from
`src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`. Instead, reuse
`PolicyGrammarCompiler`, `PolicyGrammarIntent`, `PolicyGrammarConceptSpineRefs`,
and `require_compiled_universal_policy_design_case(...)` in the readiness/tooling
boundary to produce a typed `Layer3G6PolicyGrammarProjection` payload, then pass
that projection into the runtime G6 builder. A G6 classifier may prepare a
candidate intent, but consumer-ready envelope matching requires a compiled
universal policy design case projection plus concept/jurisdiction spine refs. If
policy grammar compilation is blocked or missing, the G6 envelope must become
`ambiguous_requires_abstention` with typed blocker codes instead of falling back
to keywords. If implementation chooses direct runtime imports instead, it must
add an explicit architecture-import task and prove the import guard still passes;
this plan's default path avoids that boundary change.

The search/abstention route also has a concrete owner: reuse the G0
`GroundingSearchLedger` discipline shape and the G0 freshness/recall rule that
search ledgers are control-plane records and authorize nothing. In G6, the
search ledger must keep `authoritative_for = ()`; only the separate
orchestration-choice audit/run record may be authoritative for G6 routing audit.

G6 also needs explicit replay continuity, not only ad-hoc replay keys. Reuse
`runtime/quality/nl_replay_orchestration.py` and `runtime/quality/replay.py` to
build a G6 orchestration-continuity record and replay manifest over the request
envelope, agent run, G5 invocation, readiness manifest, and public/export
projection refs. That continuity record is diagnostic/routing audit only; it
cannot satisfy producer-domain truth, evidence strength, closeout, or public
projection authority.

## Closure Contract

Source of truth: roadmap G6 section in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`.

G6 must deliver:

1. A bounded natural-language request envelope with raw request refs, normalized
   fingerprint, declared request class, envelope match, audience, demand-pull
   refs, and privacy-safe public projection.
2. A grammar-first expansion candidate using a typed projection from the
   existing `policy_grammar` compiler and consumer guard. LLM output is allowed
   only as `candidate_unverified` search/control input; deterministic grammar,
   concept-spine refs, and G5/G0-G5 contracts decide what is groundable.
3. A bounded agent-loop producer that actually invokes the existing
   `scientist/orchestration/llm` client surface and `scientist.agent.tools`
   tool loop in simulation/fake-client tests and in the runtime builder. A
   static builder-only trace is not enough for G6 closure. If no injected
   client is provided and `create_traced_gateway_client(...)` returns `None`,
   G6 must emit `layer3_g6_llm_client_unavailable` and stop in a typed blocker
   state rather than silently replacing the agent loop with a mock builder.
4. A grounding-demand record identifying required families such as source data,
   causal forecast, analytics proof, legal mandate, human-decision integrity,
   search recall, and declared envelope. This is a routing artifact, not
   evidence.
5. A bounded tool registry and tool-contract summary. The default G6 tool set is
   local and structured: request classification, G5 bundle read/build, G5
   conversion-record inspection, counterexample probe, and envelope-match probe.
   No unbounded filesystem glob, network search, shell, or ad-hoc Python
   execution is in scope.
6. A replayable G6 search ledger plus orchestration-choice audit covering tool
   selection, evidence selection, selected/rejected candidates, index/rule
   versions, budget cutoffs, incompleteness, rejected tools, rejected
   speculative branches, framing choices, counterexample refinements, model
   profile, tool schemas, and prompt/tool/hypothesis ledger refs. This is the T4
   and P25 load-bearing artifact; an ordinary tool transcript is not enough.
   The G6 search ledger should mirror G0's
   `typed_request_ref`, `normalized_query_refs`, `searched_index_refs`,
   `ranking_policy_ref`, selected/rejected candidate refs, cutoff,
   incompleteness, completeness status, and deterministic replay key, and it
   must keep `authoritative_for = ()`.
7. A candidate DesignRecord handoff. The agent may produce a
   `Layer3G6DesignRecordCandidate` for the composed loop to consume as
   candidate-only input, but the candidate is shadow until A/G5/G4 ground and
   promote it. G6 must never admit that candidate into claim, legal, closeout,
   proof, recommendation, or G4 source-design-record authority; G4 source
   resolution still requires full payload, replay ref, digest, and upstream
   `may_not_use_for` enforcement.
8. A prompt/tool parser ledger projection and hypothesis ledger entries for
   every LLM/candidate branch. The existing
   `PromptToolParserAuthorityLedger` is reused as lineage, not as proof that G6
   owns claim/legal authority; G6 readiness must not treat
   `validate_prompt_tool_parser_authority(...)` all-scope authority pass as a
   candidate-branch requirement. Candidate refs must be blocked by
   `candidate_firewall.py` when read in legal, data, method, participation,
   closeout, projection, claim, or obligation authority slots.
9. A G5 invocation bridge that calls typed G5 builders and consumer gates. It
   must not fabricate conversion records from JSON summaries and must not
   bypass `build_g5_w12d_consumer_gate` or G5 conversion eligibility semantics.
10. `Layer3G6AgentRunRecord` with candidate request parse, grounding demand,
   selected and rejected tool/evidence branches, G5 invocation refs, G5 outcome,
   abstention/blocker reasons, accountable principal refs, human-review posture,
   authority boundary, rule/schema versions, and replay fingerprint.
11. A result-or-abstention projection that has exactly one outcome:
   `g5_grounded_result`, `g5_grounded_abstention`,
   `out_of_envelope_grounded_abstention`, or `g5_unchanged_blocker`.
12. A demand-pull-vs-abstention health metric delta. It measures whether
    arbitrary request demand reaches a G5 grounding attempt or terminates in a
    bounded abstention/blocker, without optimizing for useful-design rate. It
    must include demand source refs, S12/S3 or accountable-principal refs when
    present, and explicit blockers when demand evidence is absent.
13. PUBLIC/REVIEWER/EXPERT/MACHINE surfaces. PUBLIC gets no raw prompt, raw tool
    transcript, or recommendation text; it sees request fingerprint, request
    class, G5 outcome, envelope status, denied uses, and safe refs. REVIEWER and
    EXPERT can inspect audit and G5 bridge refs. MACHINE gets artifact paths and
    replay keys.
14. Readiness CLI and generated artifacts registration mirroring G5's drift
    discipline.
15. A replay manifest and NL/replay orchestration-continuity record. G6 must
    persist request fingerprint, prompt/tool/hypothesis ledger refs, model/tool
    profile, policy-grammar projection refs, G5 artifact refs, search ledger
    refs, orchestration audit refs, and public projection refs in replayable
    form. Missing or mismatched continuity refs are blockers for replay status,
    not caveats.
16. Negative semantic tests proving: fluent LLM output cannot become authority,
    tool-choice bias cannot hide counterevidence, candidate refs fail closed
    without a hypothesis ledger, G5 bypass fails closed, non-allowlisted tools
    fail closed, raw prompt leaks fail public projection, hardcoded-template
    classification cannot satisfy request authority, out-of-envelope abstention
    without search recall/index freshness is blocked, cheap refusal without
    demand refs is blocked, G5 `may_not_use_for` cannot be ignored for G6
    orchestration authority, G6 DesignRecord candidates cannot bypass G4 source
    resolution, replay/continuity drift is high-impact, and out-of-envelope
    requests do not become G5 or G7 widening.

G6 engineering readiness is done when the readiness CLI passes over persisted G6
artifacts; an arbitrary MSME-support request routes to the G5 loop and preserves
the G5 outcome; an outside-envelope request yields a grounded abstention when
search/demand evidence is present; the positive fixture proves future G5
grounded results/abstentions project through the same bridge; and every
agent-laundering negative control fails closed. G6 grounded value closure is
done only when the readiness manifest also reports a real grounded result or
grounded abstention, not merely the current same-class `unchanged_blocker`.

## Scope Boundaries

In scope:

- Add G6 runtime-quality contracts/builders in a new focused module.
- Reuse `scientist/orchestration/llm` gateway and simulation mode for bounded
  model calls.
- Reuse `scientist.agent.tools` registry/tool loop and tool-contract summary for
  structured deterministic tool interfaces.
- Reuse `prompt_tool_ledger.py`, `hypothesis_ledger.py`, and
  `candidate_firewall.py` for candidate-to-authority discipline.
- Reuse G5 typed builders and persisted G5 artifacts for the grounding loop.
- Emit generated artifacts, audit/public surfaces, readiness manifest, and
  conformance report.

Out of scope:

- No agent authority.
- No production, rollout, approval, legal advice, publication, public
  recommendation, or policy recommendation authority.
- No G7 regional widening or non-pinned G5 conversion.
- No new search engine, data acquisition engine, legal engine, causal engine, or
  analytics engine.
- No lowering of G5 evidence floors, G4 promotion floors, S4-S14 floors, or
  closeout floors.
- No unbounded network, filesystem, shell, or dynamic tool access inside the G6
  default path.
- No raw prompt or raw transcript on PUBLIC surfaces.

## Pattern Pass

| Pattern | G6 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | `AgentRunRecord` exists but no real bridge consumes G5. | Build producer -> persisted artifacts -> G5 bridge -> surfaces -> negative tests. |
| P02 thin orchestration | Mature LLM/tool/G5 pieces coexist but do not exchange typed refs. | G6 audit must carry prompt/tool, hypothesis, tool-contract, G5 invocation, and result refs in one run record. |
| P03 hidden internal richness | Agent decisions are buried in logs. | PUBLIC/REVIEWER/EXPERT/MACHINE audit surface and generated artifact family. |
| P04 status lattice gap | Agent invents new result statuses outside G5/W12.D semantics. | Four local G6 outcomes only; G5 conversion outcome is preserved verbatim. |
| P05 authority dilution | Agent route or projection is mistaken for policy authority. | `authoritative_for` is G6 orchestration audit and routing only; denied uses include claim/legal/closeout/recommendation authority. |
| P07 rule replay gap | A request cannot be replayed under the same model/tool/rule set. | Store schema/rule versions, model profile, prompt fingerprint, tool schemas, and G5 artifact refs. |
| P08 time-role conflation | Request time, source observation time, G5 replay time, and model call time blur. | Persist request_received_at, agent_run_at, G5 artifact generated_at, source observed_through refs, and replay rule refs. |
| P09 warning lifecycle gap | Agent emits caveats that do not affect outcome. | Caveats are blockers, limitations, or existing owned warning refs; no G6 soft-pass caveat. |
| P10 semantic adequacy gap | Tests only validate fields. | Negative tests assert authority blocking, hidden counterevidence, raw prompt leak, and G5 bypass. |
| P13 governance gravity | G6 becomes a large alternate policy engine. | Keep G6 as adapter/controller/audit only; no new domain producer. |
| P15 LLM speculation laundering | Fluent agent text is read as claim, legal, or design authority. | Hypothesis ledger marks LLM branches candidate-only; candidate firewall is a conformance gate. |
| P16 epistemic-regime laundering | Grammar facets or request axes are mistaken for admissibility/regime authority. | Policy grammar projection authorizes compilation facets only; G5/A-side producers still own admissibility and closure. |
| P25 search-control laundering | Agent-selected frontier is projected as exhaustive or authoritative. | Search ledger plus orchestration-choice audit records selected/rejected branches, budget cutoffs, index/rule refs, and incompleteness. |
| P26 responsibility-integrity laundering | Human accountability is silently shifted to the agent. | G6 cannot approve high-stakes/out-of-envelope action and must preserve S7/P26 blockers from G5. |

Capability transition:

| Capability | Current label | Target label | Acceptance signal |
| --- | --- | --- | --- |
| Bounded arbitrary-request agent | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `surface_missing`, `semantic_test_missing` | `implemented` | Request -> agent producer -> persisted run record -> G5 bridge -> result/abstention surface -> negatives. |
| Policy grammar request projection | `bridge_missing`, `consumer_missing`, `semantic_test_missing` | `implemented` | Raw request -> `PolicyGrammarIntent` -> compiled case or typed blocker -> envelope/facet match -> negatives for missing spine and classifier-only routing. |
| Orchestration-choice audit | `producer_missing` | `implemented` | Tool/evidence/framing choices and rejected branches are replayable and tested. |
| G6 search ledger | `producer_missing`, `artifact_missing`, `semantic_test_missing` | `implemented` | Selected/rejected candidates, search health refs, budget cutoffs, and incompleteness are persisted and negatively tested. |
| Candidate DesignRecord handoff | `producer_missing`, `bridge_missing`, `consumer_missing` | `implemented` | Agent emits a candidate-only DesignRecord handoff consumed by G5 routing and blocked by candidate firewall in authority slots. |
| Candidate-to-authority firewall at agent scale | `implemented_but_not_orchestrated` | `implemented` | G6 conformance fails when agent candidate refs occupy authority slots. |
| G5 arbitrary-request bridge | `consumer_missing` | `implemented` | G6 calls typed G5 builders and blocks any G5 bypass or non-pinned widening. |
| Demand-pull-vs-abstention metric | `measured_by_prereq` | `implemented` for G6 demand routing | Health delta counts requested, routed, abstained, unchanged-blocker, and future grounded outcomes. |
| G6 generated/audit surface | `surface_missing` | `implemented` | Generated artifact family, inventory/docs/public-surface registration, readiness drift checks. |

## Code-Grounded Reality

Existing strengths to reuse:

- `src/polisyos/policy_grammar/_impl/compiler.py` already compiles
  `PolicyGrammarIntent` into a typed `UniversalPolicyDesignCase`,
  blocks missing concept-spine refs, and prevents LLM-candidate authority from
  satisfying protected authority slots.
- `architecture/imports/policy.toml` does not currently allow `runtime` to
  import `policy_grammar`. That is a real architecture constraint, not a
  missing import. G6 should consume a policy-grammar projection payload unless
  the implementation intentionally adds and justifies an import-policy change.
- `src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py` already provides
  the search-ledger, recall-seed, and index-freshness discipline G6 needs for
  out-of-envelope abstention quality. Its validator explicitly blocks search
  ledger authority leaks.
- `src/polisyos/runtime/quality/nl_replay_orchestration.py` and
  `src/polisyos/runtime/quality/replay.py` already provide continuity and
  replay-manifest helpers; G6 should reuse them instead of inventing a local
  replay fingerprint convention.
- `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py` already
  exposes strict G5 DTOs, `build_layer3_g5_bundle(...)`,
  `build_g5_w12d_consumer_gate(...)`, and G5 validation.
- G5 persisted artifacts are registered and the readiness CLI passes.
- G5 `G5_MAY_NOT_USE_FOR` explicitly includes
  `g6_arbitrary_request_orchestration`, so G6 may consume G5 outputs only
  through its own routing/audit bridge and may not reuse G5 conversion
  authority as G6 orchestration authority.
- `scientist/orchestration/llm/factory.py` can create traced gateway clients and
  deterministic simulation clients through `POLISYOS_LLM_SIMULATION_MODE=1`;
  without config or simulation it returns `None`.
- `scientist.agent.tools.registry.ToolRegistry` already validates JSON-schema
  arguments, returns structured errors, enforces response caps, and supports
  query-based tool selection.
- `scientist.agent.tools.tool_loop.run_tool_loop(...)` already records tool
  calls, errors, budgets, convergence, and degraded events, although it does not
  itself create a G6 authority-aware audit.
- `scientist.agent.tool_contracts.summarize_tool_contracts(...)` can block open
  schemas, missing timeouts, missing response caps, and structured-error gaps.
- `runtime/quality/prompt_tool_ledger.py` persists model/tool/parser lineage
  with strict requirements: rendered input refs, output refs, validation refs,
  authority-handoff refs, and per-tool output/rejection refs. A raw transcript
  is therefore insufficient input for G6 readiness.
- `runtime/quality/hypothesis_ledger.py` and
  `runtime/quality/candidate_firewall.py` already encode candidate-only source
  classes and consumer-side authority blocking.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already has the S2 pattern
  for grammar expansion, counterexample refinement, replayable search ledger,
  and shadow DesignRecord handoff.
- `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py` already enforces G4
  source DesignRecord resolution with full payload/replay/digest requirements
  and upstream `may_not_use_for` checks.

Current weak points G6 must account for:

- There is no current G6 producer that calls the LLM/tool loop and then bridges
  into G5; adding only DTO builders would leave the capability
  `implemented_but_not_orchestrated`.
- There is no current raw-request-to-`PolicyGrammarIntent` bridge in Layer 3.
  G6 must add a small projection bridge around `policy_grammar` in the
  readiness/tooling boundary, not a parallel grammar system inside
  `runtime/quality`.
- Policy grammar cannot be treated as domain authority. Its compiled case can
  support compilation/facet routing, but G5/A-side producers still decide
  admissibility, limits, and closure.
- `ToolLoopResult` is not an authority boundary. It must be projected into a G6
  audit record before any downstream consumer reads it.
- Existing LLM simulation returns generic JSON for many prompts. G6 tests should
  use deterministic fake clients/tool results for exact branches and only use
  simulation mode for integration sanity.
- `create_traced_gateway_client(...)` can return `None`. G6 must expose that as
  `layer3_g6_llm_client_unavailable` instead of quietly substituting a static
  trace.
- G5 readiness passes while preserving `unchanged_blocker`; G6 must not treat
  G5 pass as a grounded useful result.
- G5 `build_g5_w12d_consumer_gate(...)` rejects non-pinned cases. G6 can route
  arbitrary requests only into the same pinned class or abstain; G7 owns region
  widening.
- G0 search ledgers authorize nothing. G6 should keep the same boundary: search
  ledger as replay/control-plane, orchestration audit as the G6-owned routing
  authority.
- `prompt_tool_ledger.py` is an authority ledger, so G6 must state explicitly
  that its prompt/tool usage is lineage for candidate/orchestration, not claim
  authority. Hypothesis ledger and candidate firewall are mandatory companions,
  and G6 readiness should not misread prompt/tool ledger all-scope status as
  G6 claim/legal authority.
- `hypothesis_ledger.py` requires unverified candidates to forbid every target
  authority slot and requires validation refs for admitted candidates. G6 should
  keep LLM/tool branches `candidate_unverified` or `rejected_speculation`; if a
  future branch is admitted, that is a later producer/reader validation task,
  not part of this slice.
- G4 does not accept ref-only DesignRecord promotion. A G6
  `Layer3G6DesignRecordCandidateHandoff` is a candidate bridge only and must not
  be passed to `resolve_g4_source_design_record(...)` as a resolved source.
- NL replay continuity requires carrier/concept/jurisdiction/claim-registry and
  producer-binding refs across surfaces. G6 may not claim continuity `pass`
  unless those refs propagate through request, run, readiness, and projection
  surfaces; partial continuity is a typed replay blocker.

## File Structure

Create:

- `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` - G6 contracts,
  builders, policy-grammar projection consumer, G0-shaped search ledger
  projection, G5 bridge, replay/continuity projections, audit/result
  projections, conformance checks. This module must not directly import
  `polisyos.policy_grammar` unless the plan is intentionally changed to include
  an import-policy update.
- `tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py` -
  readiness CLI, write mode, persisted artifact drift, docs/registration checks.
- `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py` - DTO, builder,
  bridge, audit, health, and negative unit tests.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py` -
  readiness CLI, artifact family, docs, public surface, and drift tests.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness_cli.py` -
  CLI JSON output, typed issue-code exposure, and exact write-artifact set
  smoke tests.
- `docs/reference/policy-design-case-layer3-bounded-agent.md` - generated audit
  surface documentation.

Modify:

- `architecture/generated_artifacts.toml` - register G6 generated artifact family.
- `architecture/policy_design_case/inventory.json` - register
  `layer3_g6_bounded_agent_surface`.
- `docs/reference/generated-artifacts.md` - add regenerated G6 artifact family.
- `docs/reference/public-surface.md` - add G6 generated audit surface paragraph.
- `docs/reference/documentation-inventory.md` and `docs/reference/index.md` if
  the G5 readiness pattern requires reference index coverage.
- `src/polisyos/runtime/quality/README.md` - add G6 as a runtime-quality adapter
  surface and note that it is not exported through `runtime.quality.__init__`.

Avoid unless explicitly justified:

- `architecture/imports/policy.toml` - do not add `policy_grammar` to
  `internal.allow.runtime` on the default path. If implementation chooses the
  direct-import path, add a red architecture test first and document why the
  projection-bridge path is insufficient.
- `architecture/public_surface/contract.toml` - `polisyos.runtime.quality` is
  already covered by the runtime public entrypoint; G6 should add generated
  audit docs, not a new public package/API row.
- `src/polisyos/runtime/quality/__init__.py` - G0/G5 are not exported there, so
  G6 should not add broad eager exports.

Do not modify:

- `pdc` waist contracts.
- `policy_grammar` compiler/consumer contracts; only the G6 readiness/tooling
  boundary may import them to produce the runtime projection payload.
- G5 conversion semantics, except for type imports used by G6.
- W12.D outcome lattice.
- Scientist LLM/tool internals unless a narrow bug blocks adapter use.
- G0 search-ledger/freshness semantics.
- G4 source DesignRecord promotion semantics.

Expected persisted artifacts:

```text
architecture/policy_design_case/layer3_g6_dependency_readiness_snapshot.json
architecture/policy_design_case/layer3_g6_request_envelope.json
architecture/policy_design_case/layer3_g6_request_classification.json
architecture/policy_design_case/layer3_g6_policy_grammar_projection.json
architecture/policy_design_case/layer3_g6_grammar_expansion_candidates.json
architecture/policy_design_case/layer3_g6_grounding_demand_record.json
architecture/policy_design_case/layer3_g6_tool_contract_summary.json
architecture/policy_design_case/layer3_g6_prompt_tool_ledger_projection.json
architecture/policy_design_case/layer3_g6_hypothesis_ledger_projection.json
architecture/policy_design_case/layer3_g6_search_ledger.json
architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json
architecture/policy_design_case/layer3_g6_counterexample_refinement_record.json
architecture/policy_design_case/layer3_g6_design_record_candidate_handoff.json
architecture/policy_design_case/layer3_g6_candidate_authority_firewall_report.json
architecture/policy_design_case/layer3_g6_g5_invocation_plan.json
architecture/policy_design_case/layer3_g6_g5_consumer_gate.json
architecture/policy_design_case/layer3_g6_orchestration_continuity.json
architecture/policy_design_case/layer3_g6_replay_manifest.json
architecture/policy_design_case/layer3_g6_agent_run_records.json
architecture/policy_design_case/layer3_g6_grounded_result_or_abstention.json
architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json
architecture/policy_design_case/layer3_g6_agent_audit_surface.json
architecture/policy_design_case/layer3_g6_public_export_projection_refs.json
architecture/policy_design_case/layer3_g6_conformance_report.json
architecture/policy_design_case/layer3_g6_health_metric_delta.toml
architecture/policy_design_case/layer3_g6_agent_route_contract_registry.toml
architecture/policy_design_case/layer3_g6_registry_ratchet_delta.json
architecture/policy_design_case/layer3_g6_readiness_manifest.json
```

## Task 1: Red Baseline And Constants

**Files:**

- Create: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py`
- Create: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Create: `tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py`

- [x] **Step 1: Add red tests for the G6 contract surface**

Add tests that fail because the module and CLI do not exist:

```python
import pytest

def test_layer3_g6_constants_define_candidate_only_boundary() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    assert g6.G6_SCHEMA_VERSION == "policyos.policy_design_case.layer3_g6_bounded_agent.v1"
    assert g6.G6_RULE_VERSION == "policyos.layer3.g6.bounded_agent.v1"
    assert "claim_authority" in g6.G6_MAY_NOT_USE_FOR
    assert "policy_recommendation" in g6.G6_MAY_NOT_USE_FOR
    assert "layer3_g6_agent_orchestration_audit" in g6.G6_AUTHORITATIVE_FOR
```

Add repo-quality expectations:

```python
EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g6_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g6_request_envelope.json",
    "architecture/policy_design_case/layer3_g6_request_classification.json",
    "architecture/policy_design_case/layer3_g6_policy_grammar_projection.json",
    "architecture/policy_design_case/layer3_g6_grammar_expansion_candidates.json",
    "architecture/policy_design_case/layer3_g6_grounding_demand_record.json",
    "architecture/policy_design_case/layer3_g6_tool_contract_summary.json",
    "architecture/policy_design_case/layer3_g6_prompt_tool_ledger_projection.json",
    "architecture/policy_design_case/layer3_g6_hypothesis_ledger_projection.json",
    "architecture/policy_design_case/layer3_g6_search_ledger.json",
    "architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json",
    "architecture/policy_design_case/layer3_g6_counterexample_refinement_record.json",
    "architecture/policy_design_case/layer3_g6_design_record_candidate_handoff.json",
    "architecture/policy_design_case/layer3_g6_candidate_authority_firewall_report.json",
    "architecture/policy_design_case/layer3_g6_g5_invocation_plan.json",
    "architecture/policy_design_case/layer3_g6_g5_consumer_gate.json",
    "architecture/policy_design_case/layer3_g6_orchestration_continuity.json",
    "architecture/policy_design_case/layer3_g6_replay_manifest.json",
    "architecture/policy_design_case/layer3_g6_agent_run_records.json",
    "architecture/policy_design_case/layer3_g6_grounded_result_or_abstention.json",
    "architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json",
    "architecture/policy_design_case/layer3_g6_agent_audit_surface.json",
    "architecture/policy_design_case/layer3_g6_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g6_conformance_report.json",
    "architecture/policy_design_case/layer3_g6_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g6_agent_route_contract_registry.toml",
    "architecture/policy_design_case/layer3_g6_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g6_readiness_manifest.json",
}
```

- [x] **Step 2: Run the red tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py::test_layer3_g6_constants_define_candidate_only_boundary -q
```

Expected: fail with missing `layer3_bounded_agent`.

- [x] **Step 3: Add minimal constants and issue dictionary**

In `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`, add:

```python
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]
G6_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g6_bounded_agent.v1"
G6_RULE_VERSION = "policyos.layer3.g6.bounded_agent.v1"
G6_SURFACE_ID = "layer3_g6_bounded_agent_surface"


class _G6Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

G6_AUTHORITATIVE_FOR = (
    "layer3_g6_agent_orchestration_audit",
    "layer3_g6_g5_routing_decision",
    "layer3_g6_demand_pull_vs_abstention_reading",
)
G6_MAY_NOT_USE_FOR = (
    "production_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "g5_conversion_authority_without_g5",
    "g7_region_widening",
)
ALL_ISSUE_CODES = (
    "layer3_g6_g5_readiness_missing",
    "layer3_g6_request_envelope_missing",
    "layer3_g6_policy_grammar_projection_missing",
    "layer3_g6_policy_grammar_compile_blocked",
    "layer3_g6_policy_grammar_concept_refs_missing",
    "layer3_g6_runtime_imports_policy_grammar",
    "layer3_g6_classifier_only_match_not_authority",
    "layer3_g6_llm_client_unavailable",
    "layer3_g6_agent_loop_trace_missing",
    "layer3_g6_agent_candidate_used_as_authority",
    "layer3_g6_design_record_candidate_used_as_authority",
    "layer3_g6_orchestration_choice_audit_missing",
    "layer3_g6_rejected_branch_memory_missing",
    "layer3_g6_search_ledger_missing",
    "layer3_g6_search_ledger_authority_boundary_leak",
    "layer3_g6_outside_g5_envelope",
    "layer3_g6_outside_envelope_abstention_without_search_health",
    "layer3_g6_cheap_refusal_without_demand_signal",
    "layer3_g6_tool_contract_not_ready",
    "layer3_g6_non_allowlisted_tool_attempt",
    "layer3_g6_tool_loop_transcript_only_not_audit",
    "layer3_g6_g5_bypass_attempt",
    "layer3_g6_g5_may_not_use_for_ignored",
    "layer3_g6_non_pinned_g5_widening_attempt",
    "layer3_g6_g7_region_widening_attempt",
    "layer3_g6_g4_source_resolution_bypass_attempt",
    "layer3_g6_prompt_tool_ledger_missing",
    "layer3_g6_prompt_tool_ledger_misread_as_authority",
    "layer3_g6_candidate_without_hypothesis_ledger",
    "layer3_g6_orchestration_continuity_missing",
    "layer3_g6_orchestration_continuity_refs_missing",
    "layer3_g6_replay_manifest_missing",
    "layer3_g6_replay_drift_unexplained",
    "layer3_g6_public_raw_prompt_leak",
    "layer3_g6_persisted_artifact_missing",
)
```

- [x] **Step 4: Run the constants test**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py::test_layer3_g6_constants_define_candidate_only_boundary -q
```

Expected: pass.

## Task 2: Request Envelope And Grammar Expansion

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add tests for request envelope and candidate-only parse**

```python
def _policy_grammar_projection_fixture(
    request_id: str,
    *,
    fixture_id: str = "ua-msme",
    status: str = "pass",
    compiled_case_status: str = "compiled",
    issue_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": (
            f"universal-policy-design-case:layer3-g6:{fixture_id}"
            if status == "pass"
            else None
        ),
        "compiled_case_status": compiled_case_status,
        "status": status,
        "authority_state": "compilation_facets_only" if status == "pass" else "blocked",
        "facet_summary": {
            "jurisdiction": "UA" if fixture_id == "ua-msme" else "outside_g5",
            "policy_family": "ua_msme_support"
            if fixture_id == "ua-msme"
            else "outside_g5_pinned_class",
            "instrument": "concessional_credit"
            if fixture_id == "ua-msme"
            else "unemployment_insurance",
        },
        "concept_spine_refs": {
            "concept_spine_ref": f"cas://concept-spine/layer3-g6/{fixture_id}",
            "jurisdiction_spine_ref": f"cas://jurisdiction-spine/layer3-g6/{fixture_id}",
        },
        "issue_codes": issue_codes,
        "authoritative_for": ("layer3_g6_policy_grammar_routing_facets",),
        "may_not_use_for": ("legal_authority", "claim_authority", "closeout_authority"),
    }


def test_g6_request_envelope_classifies_msme_request_without_authority() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture("req-msme-1")
    )
    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=grammar,
    )
    candidate = g6.build_g6_grammar_expansion_candidate(envelope)

    assert grammar.status == "pass"
    assert grammar.compiled_case_status == "compiled"
    assert grammar.authority_state == "compilation_facets_only"
    assert "legal_authority" in grammar.may_not_use_for
    assert envelope.request_class == "ua_msme_support"
    assert envelope.envelope_match_status == "same_class_as_g5_pinned_case"
    assert envelope.raw_request_fingerprint.startswith("sha256:")
    assert envelope.matched_envelope_refs
    assert candidate.authority_state == "candidate_unverified"
    assert "claim_authority" in candidate.may_not_use_for
```

Also add an outside-envelope case:

```python
def test_g6_request_envelope_marks_outside_envelope_request() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture(
            "req-outside-1",
            fixture_id="outside-envelope",
        )
    )
    envelope = g6.build_g6_request_envelope(
        "Design a national unemployment insurance program for a different country.",
        request_id="req-outside-1",
        policy_grammar_projection=grammar,
    )

    assert envelope.envelope_match_status == "outside_g5_envelope"
    assert envelope.request_class == "outside_g5_pinned_class"
```

Add a policy-grammar blocker case:

```python
def test_g6_request_envelope_blocks_when_policy_grammar_cannot_compile() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture(
            "req-ambiguous-no-spine",
            fixture_id="ambiguous",
            status="fail",
            compiled_case_status="blocked",
            issue_codes=("layer3_g6_policy_grammar_concept_refs_missing",),
        )
    )
    envelope = g6.build_g6_request_envelope(
        "Do something beneficial someday.",
        request_id="req-ambiguous-no-spine",
        policy_grammar_projection=grammar,
    )

    assert envelope.envelope_match_status == "ambiguous_requires_abstention"
    assert grammar.status == "fail"
    assert "layer3_g6_policy_grammar_concept_refs_missing" in grammar.issue_codes
    assert "layer3_g6_policy_grammar_compile_blocked" in envelope.issue_codes
```

- [x] **Step 2: Add strict DTOs and policy-grammar adapter**

Implement Pydantic models with `ConfigDict(extra="forbid")`:

```python
from collections.abc import Mapping

Layer3G6EnvelopeMatchStatus = Literal[
    "same_class_as_g5_pinned_case",
    "outside_g5_envelope",
    "ambiguous_requires_abstention",
]
Layer3G6RequestClass = Literal[
    "ua_msme_support",
    "outside_g5_pinned_class",
    "ambiguous",
]

class Layer3G6RequestEnvelope(_G6Model):
    schema_version: str = G6_SCHEMA_VERSION
    rule_version: str = G6_RULE_VERSION
    request_id: str
    raw_request_ref: str
    raw_request_fingerprint: str
    request_class: Layer3G6RequestClass
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    matched_envelope_refs: tuple[str, ...] = Field(default=())
    facet_match_record: dict[str, Any] = Field(default_factory=dict)
    policy_grammar_projection_ref: str | None = None
    compiled_policy_case_ref: str | None = None
    policy_grammar_blocker_codes: tuple[str, ...] = Field(default=())
    requested_audience: str = "REVIEWER"
    request_received_at: datetime
    demand_signal_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR

class Layer3G6PolicyGrammarProjection(_G6Model):
    projection_id: str
    request_id: str
    intent_ref: str
    compiled_case_ref: str | None = None
    compiled_case_status: str
    status: Literal["pass", "fail"]
    authority_state: Literal[
        "compilation_facets_only",
        "candidate_unverified",
        "blocked",
    ]
    facet_summary: dict[str, Any] = Field(default_factory=dict)
    concept_spine_refs: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_policy_grammar_routing_facets",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR

class Layer3G6GrammarExpansionCandidate(_G6Model):
    candidate_id: str
    request_id: str
    source_class: Literal["deterministic_grammar", "llm_candidate"] = "deterministic_grammar"
    authority_state: Literal["candidate_unverified"] = "candidate_unverified"
    candidate_problem_frame: dict[str, Any]
    target_authority_slots: tuple[str, ...] = ("claim_authority",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR
```

Implement `validate_g6_policy_grammar_projection(payload: Mapping[str, Any])
-> Layer3G6PolicyGrammarProjection` and
`build_g6_request_envelope(raw_request: str, *, request_id: str,
policy_grammar_projection: Layer3G6PolicyGrammarProjection | Mapping[str, Any]
| None = None, matched_envelope_refs: tuple[str, ...] | None = None,
demand_signal_refs: tuple[str, ...] = (), requested_audience: str = "REVIEWER")
-> Layer3G6RequestEnvelope`.

`validate_g6_policy_grammar_projection(...)` must require a non-empty
`projection_id`, `intent_ref`, `concept_spine_refs.concept_spine_ref`,
`concept_spine_refs.jurisdiction_spine_ref`, `facet_summary`, and denied uses
covering `legal_authority`, `claim_authority`, and `closeout_authority`. It
must reject `authoritative_for` values outside
`("layer3_g6_policy_grammar_routing_facets",)`.

The readiness CLI owns actual compiler invocation. Add helper
`_build_policy_grammar_projection_for_g6(...)` in
`tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py` that
constructs a `PolicyGrammarIntent`, compiles it with `PolicyGrammarCompiler`,
and calls `require_compiled_universal_policy_design_case(...)` before emitting a
projection with `status="pass"`. Use a deterministic authority profile like:

```python
UniversalAuthorityProfile(
    profile_id=f"layer3-g6-policy-grammar:{request_id}",
    authority_type=PolicyLayerLevel.FEDERAL,
    source_classification="deterministic_producer",
    authoritative_for=("compilation_facets",),
)
```

This authorizes compilation/facet routing only. It does not authorize legal,
claim, evidence, recommendation, closeout, or G5/G4 authority. If concept spine
refs are missing or the compiler returns a blocked case, return
`status="fail"` with `layer3_g6_policy_grammar_concept_refs_missing` or
`layer3_g6_policy_grammar_compile_blocked`.

Add a no-direct-import architecture negative:

```python
def test_g6_runtime_module_does_not_import_policy_grammar() -> None:
    from pathlib import Path

    module_text = Path(
        "src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py"
    ).read_text(encoding="utf-8")

    assert "polisyos.policy_grammar" not in module_text
```

Envelope matching rule: build normalized request facets from the compiled
policy grammar projection first
(`jurisdiction`, `subject`, `instrument`, `time_context`, `policy_family`,
`stakes`, `audience`) and join them to G5 pinned-case envelope refs and
claim-family refs from the typed G5 bundle. Same-class routing requires a
non-empty `matched_envelope_refs` tuple and a `facet_match_record` explaining
which facets matched or failed. Tests may use MSME/Ukraine wording and fixture
concept-spine refs, but the implementation must not treat a hand-maintained
keyword list as authority for request class, grounding scope, or abstention
quality. A classifier-only match without G5 envelope refs must return
`ambiguous_requires_abstention` and issue
`layer3_g6_classifier_only_match_not_authority`.

Add a negative:

```python
def test_g6_classifier_only_match_without_g5_refs_is_not_authority() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Ukraine MSME loans",
        request_id="req-msme-no-refs",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-no-refs"),
        matched_envelope_refs=(),
    )

    assert envelope.envelope_match_status == "ambiguous_requires_abstention"
    assert "layer3_g6_classifier_only_match_not_authority" in envelope.issue_codes
```

- [x] **Step 3: Run envelope tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py -q
```

Expected: current task tests pass; later task tests may still fail until added.

## Task 3: Grounding Demand And Tool Contract Summary

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add tests for grounding-demand and strict tools**

```python
def test_g6_grounding_demand_names_g5_required_families() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    demand = g6.build_g6_grounding_demand_record(envelope)

    assert demand.status == "route_to_g5"
    assert set(demand.required_grounding_families) >= {
        "g1_source_contracts",
        "g4_promotion_handoff",
        "g5_conversion_record",
        "search_recall_freshness",
    }
    assert "new_agent_authority" not in demand.required_grounding_families
```

```python
def test_g6_tool_contract_summary_requires_strict_allowlisted_tools() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    registry = g6.build_g6_tool_registry(repo_root=g6.DEFAULT_REPO_ROOT)
    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "pass"
    assert summary.tool_contract_summary.default_enable_ready is True
    assert "layer3_g6_build_g5_bundle" in summary.allowed_tool_names
```

- [x] **Step 2: Implement G6 tool registry**

Use existing `ToolDefinition`, `ToolRegistry`, and
`summarize_tool_contracts(...)`; do not create a parallel tool-readiness
schema. `Layer3G6ToolContractSummary` is a small projection over
`ToolContractSummary` and `tool_contract_default_blockers(...)`, preserving the
upstream blocker names in `blocker_codes`. Tool names:

- `layer3_g6_classify_request`
- `layer3_g6_build_g5_bundle`
- `layer3_g6_read_g5_conversion`
- `layer3_g6_probe_counterexample`
- `layer3_g6_probe_envelope_match`

Every tool schema must use:

```python
{
    "type": "object",
    "properties": {"request_id": {"type": "string"}},
    "required": ["request_id"],
    "additionalProperties": False,
}
```

Use narrower schemas when a tool needs `case_id`, `candidate_id`, or
`counterexample_text`; keep `additionalProperties` false and
`response_max_chars <= 120_000`.

Every registered tool must also set a positive `timeout_s`, a non-null
`response_max_chars`, and a deterministic local handler. Default G6 must not
register network, shell, filesystem-write, or open-ended search tools. The only
filesystem reads allowed in this slice are repo-local G5/readiness artifacts
needed to build typed G6 projections.

- [x] **Step 3: Add an open-schema negative**

```python
def test_g6_tool_contract_summary_blocks_open_schema_tool() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.agent.tools.schema import ToolDefinition

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="unsafe_tool",
            description="Unsafe open schema",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            timeout_s=5.0,
            response_max_chars=4096,
        ),
        lambda: {},
    )

    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "fail"
    assert "tool_schema_not_ready" in summary.blocker_codes
```

Add equivalent negatives for `runtime_missing_timeout`,
`runtime_missing_response_cap`, and a non-allowlisted tool-name attempt. These
must surface as G6 readiness blockers rather than being hidden inside the raw
Scientist tool-contract summary.

## Task 4: Prompt/Tool And Hypothesis Ledger Projection

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add tests for candidate lineage and firewall**

```python
def test_g6_candidate_ledgers_block_agent_parse_as_claim_authority() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6
    from polisyos.runtime.quality.candidate_firewall import candidate_firewall_issues_for_payload

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    candidate = g6.build_g6_grammar_expansion_candidate(envelope)
    prompt_ledger = g6.build_g6_prompt_tool_ledger_projection(
        run_id="g6-run-1",
        job_id="g6-job-1",
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=(),
    )
    hypothesis = g6.build_g6_hypothesis_ledger_projection(
        run_id="g6-run-1",
        job_id="g6-job-1",
        prompt_tool_ledger=prompt_ledger,
        candidates=(candidate,),
    )

    issues = candidate_firewall_issues_for_payload(
        {"selected_claim_refs": [hypothesis.entries[0].candidate_ref]},
        hypothesis_ledger=hypothesis,
        authority_slots=("claim_authority",),
        surface="layer3_g6_agent_run_record",
    )

    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_candidate_unverified"
    }
```

- [x] **Step 2: Implement ledger builders**

Use `PromptToolParserAuthorityLedger` and
`build_hypothesis_ledger_from_prompt_tool_ledger(...)`, but wrap the prompt
ledger in a `Layer3G6PromptToolLedgerProjection`. G6 projection readiness is
about lineage presence, tool allowlist/schema refs, validation refs, and a
candidate-only handoff; it is not a claim that the prompt/tool authority ledger
has admitted G6 output into protected authority slots. Do not call
`validate_prompt_tool_parser_authority(...)` with all `AUTHORITY_SCOPES` as the
success condition for a candidate branch.

The prompt/tool ledger step must set:

- `step_kind = "layer3_g6_agent_orchestration_candidate"`
- `authority_scopes = ("claims",)` because the candidate could be misread as a
  claim, while the G6 projection keeps the branch candidate-only.
- parser contract refs under `repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- validation ref `layer3-g6://validation/candidate-only`
- authority handoff consumer `polisyos.runtime.quality.proving_ground.bounded_request_agent`
- handoff status `not_applicable`

Add a negative proving G6 fails closed if prompt/tool authority status is
mistaken for G6 claim authority:

```python
def test_g6_prompt_tool_ledger_pass_cannot_be_read_as_claim_authority() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    projection = g6.build_g6_prompt_tool_ledger_projection(
        run_id="g6-run-ledger-authority-negative",
        job_id="g6-job-ledger-authority-negative",
        envelope=g6.build_g6_request_envelope(
            "Can Ukraine improve affordable loans for wartime MSMEs?",
            request_id="req-ledger-negative",
            policy_grammar_projection=_policy_grammar_projection_fixture(
                "req-ledger-negative"
            ),
        ),
        candidates=(),
        tool_call_refs=("tool-call://fixture/g5-bundle",),
        force_authority_summary_status="pass",
    )

    assert projection.status == "fail"
    assert "layer3_g6_prompt_tool_ledger_misread_as_authority" in projection.issue_codes
```

The hypothesis ledger entries must set:

- `source_class = "llm_candidate"` or `deterministic_producer`.
- `candidate_kind = "request_parse"` or `"counterexample_branch"`.
- `admission_state = "candidate_unverified"` for live branches.
- `admission_state = "rejected_speculation"` for branches rejected by
  counterexample refinement.
- `target_authority_slots` includes any slot the branch might be mistaken for.

## Task 5: Orchestration-Choice Audit

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add audit tests**

```python
def test_g6_orchestration_choice_audit_records_selected_and_rejected_branches() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    audit = g6.build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=("unbounded_web_search",),
        selected_evidence_refs=("repo://architecture/policy_design_case/layer3_g5_conversion_records.json",),
        rejected_branch_refs=("candidate://g6/rejected/legal-advice-answer",),
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        budget_cutoff_reason="single_g5_route_budget",
    )

    assert audit.status == "pass"
    assert audit.replayable is True
    assert "unbounded_web_search" in audit.rejected_tool_names
    assert audit.selected_tool_names == ("layer3_g6_build_g5_bundle",)
```

Add a negative:

```python
def test_g6_orchestration_choice_audit_fails_without_rejected_branch_memory() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "MSME loans in Ukraine",
        request_id="req",
        policy_grammar_projection=_policy_grammar_projection_fixture("req"),
    )
    audit = g6.build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=(),
        selected_evidence_refs=("repo://architecture/policy_design_case/layer3_g5_conversion_records.json",),
        rejected_branch_refs=(),
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        budget_cutoff_reason="single_g5_route_budget",
    )

    assert audit.status == "fail"
    assert "layer3_g6_rejected_branch_memory_missing" in audit.issue_codes
```

- [x] **Step 2: Implement audit DTO and builder**

The audit should include:

- `request_id`
- `selected_tool_names`
- `rejected_tool_names`
- `selected_evidence_refs`
- `rejected_branch_refs`
- `framing_choices`
- `counterexample_probe_refs`
- `prompt_tool_ledger_ref`
- `hypothesis_ledger_ref`
- `tool_contract_summary_ref`
- `budget_cutoff_reason`
- `replay_fingerprint`
- `authoritative_for = G6_AUTHORITATIVE_FOR`
- `may_not_use_for = G6_MAY_NOT_USE_FOR`

Status is `pass` only when at least one selected tool, one selected evidence ref,
one rejected branch or rejected tool, one framing choice, and a replay
fingerprint exist.

- [x] **Step 3: Add a bounded agent-loop producer test**

```python
@pytest.mark.asyncio
async def test_g6_agent_loop_uses_llm_tool_loop_and_emits_search_ledger() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-loop-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-loop-1"),
        client=g6.FakeG6ToolCallingClient(
            tool_sequence=("layer3_g6_classify_request", "layer3_g6_build_g5_bundle"),
        ),
        max_iterations=3,
    )

    assert result.agent_loop_trace.status == "pass"
    assert result.search_ledger.status == "pass"
    assert result.search_ledger.selected_candidate_refs
    assert result.search_ledger.rejected_candidate_refs
    assert result.search_ledger.authoritative_for == ()
    assert result.orchestration_choice_audit.replayable is True
```

Implement the test fake in `layer3_bounded_agent.py`:

```python
from types import SimpleNamespace


class FakeG6ToolCallingClient:
    """Deterministic OpenAI-shape tool-calling client for G6 loop tests."""

    def __init__(self, tool_sequence: tuple[str, ...]) -> None:
        self._tool_sequence = tuple(tool_sequence)
        self._index = 0

    async def generate(self, *, messages: list[dict[str, object]], tools: list[dict[str, object]]):
        del messages, tools
        if self._index >= len(self._tool_sequence):
            return SimpleNamespace(
                content='{"status":"g6-loop-complete"}',
                tool_calls=[],
                usage=SimpleNamespace(total_tokens=1),
                raw={"choices": [{"message": {"content": '{"status":"g6-loop-complete"}'}}]},
            )
        tool_name = self._tool_sequence[self._index]
        self._index += 1
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id=f"call-{self._index}",
                    name=tool_name,
                    arguments={"request_id": "req-msme-loop-1"},
                )
            ],
            usage=SimpleNamespace(total_tokens=1),
            raw={},
        )
```

Add unavailable-client and transcript-only negatives:

```python
@pytest.mark.asyncio
async def test_g6_agent_loop_fails_closed_when_llm_client_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    monkeypatch.setattr(g6, "create_traced_gateway_client", lambda **_: None)

    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-no-client",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-no-client"),
        client=None,
        max_iterations=3,
    )

    assert result.agent_loop_trace.status == "blocked"
    assert "layer3_g6_llm_client_unavailable" in result.agent_loop_trace.issue_codes
```

```python
def test_g6_search_ledger_blocks_authority_and_transcript_only_trace() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    ledger = g6.build_g6_search_ledger(
        request_id="req-transcript-only",
        typed_request_ref="layer3-g6://request/req-transcript-only",
        normalized_query_refs=("query://g6/msme",),
        searched_index_refs=("repo://architecture/policy_design_case/inventory.json",),
        selected_candidate_refs=("candidate://g6/msme-route",),
        rejected_candidate_refs=(),
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=(),
        selected_evidence_refs=("repo://architecture/policy_design_case/layer3_g5_conversion_records.json",),
        completeness_status="partial_budget_cutoff",
        absence_or_incompleteness_reason=None,
        authoritative_for=("claim_authority",),
    )

    assert ledger.status == "fail"
    assert "layer3_g6_search_ledger_authority_boundary_leak" in ledger.issue_codes
    assert "layer3_g6_tool_loop_transcript_only_not_audit" in ledger.issue_codes
```

- [x] **Step 4: Implement the bounded agent-loop producer**

`run_layer3_g6_bounded_agent_loop(...)` must call the existing
`scientist.agent.tools.tool_loop.run_tool_loop(...)` with the G6 tool registry.
It may accept an injected fake client in tests and should support
`POLISYOS_LLM_SIMULATION_MODE=1` through
`scientist/orchestration/llm.create_traced_gateway_client(...)` for integration
sanity. If no injected client is supplied and
`create_traced_gateway_client(...)` returns `None`, return a blocked typed
result with `layer3_g6_llm_client_unavailable`; do not fabricate a successful
agent trace. The producer returns a typed result containing:

- `Layer3G6AgentLoopTrace`
- `Layer3G6SearchLedger`
- `Layer3G6OrchestrationChoiceAudit`
- `Layer3G6PolicyGrammarProjection`
- prompt/tool ledger projection
- hypothesis ledger projection
- selected G5 invocation inputs

The `Layer3G6AgentLoopTrace` must be a projection of
`ToolLoopResult.content`, `tool_calls_made`, `iterations`, `total_tokens`,
`converged`, `convergence_reason`, `final_score`, `evaluation_history`, and
`degraded_events`. If the trace has degraded events, failed tool calls, a
non-converged stop, or only a final text answer with no tool evidence, those
signals must appear in G6 issue codes and in the orchestration audit. The trace
is never itself authority.

`Layer3G6SearchLedger` should intentionally mirror G0's
`GroundingSearchLedger` shape:

```python
class Layer3G6SearchLedger(_G6Model):
    ledger_id: str
    typed_request_ref: str
    normalized_query_refs: tuple[str, ...]
    searched_index_refs: tuple[str, ...]
    ranking_policy_ref: str | None = None
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    selected_tool_names: tuple[str, ...] = Field(default=())
    rejected_tool_names: tuple[str, ...] = Field(default=())
    selected_evidence_refs: tuple[str, ...] = Field(default=())
    cutoff_budget_ref: str | None = None
    absence_or_incompleteness_reason: str | None = None
    completeness_status: Literal[
        "complete_with_candidates",
        "complete_no_hit",
        "partial_budget_cutoff",
        "partial_tool_or_index_gap",
    ]
    deterministic_replay_key: str
    search_health_refs: tuple[str, ...] = Field(default=())
    status: Literal["pass", "fail"]
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR
```

Status is `pass` only when the ledger has a typed request ref, normalized query
refs, searched index refs, selected and rejected candidate/tool memory, a
cutoff or explicit completeness reason, and a deterministic replay key. If it
is derived only from `ToolLoopResult.tool_calls_made` without rejected branches
or incompleteness, it must fail with
`layer3_g6_tool_loop_transcript_only_not_audit`. If `authoritative_for` is
non-empty, fail with `layer3_g6_search_ledger_authority_boundary_leak`.

The orchestration audit must also carry `tool_contract_summary_ref`; if
`build_g6_tool_contract_summary(...).tool_contract_summary.default_enable_ready`
is false, the agent loop may still return a typed blocked result, but it cannot
emit a passing search ledger or run record.

- [x] **Step 5: Add candidate DesignRecord handoff test**

```python
def test_g6_design_record_candidate_handoff_stays_candidate_only() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6
    from polisyos.runtime.quality.candidate_firewall import candidate_firewall_issues_for_payload

    handoff = g6.build_g6_design_record_candidate_handoff(
        request_id="req-msme-1",
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
    )

    assert handoff.status == "candidate_only"
    assert "claim_authority" in handoff.may_not_use_for
    issues = candidate_firewall_issues_for_payload(
        {"design_record_ref": handoff.design_record_candidate_ref},
        hypothesis_ledger=handoff.hypothesis_ledger,
        authority_slots=("claim_authority",),
        surface="layer3_g6_composed_loop_candidate_handoff",
    )
    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_candidate_unverified"
    }
```

Add a G4 source-resolution bypass negative:

```python
def test_g6_design_record_candidate_cannot_be_used_as_g4_source_record() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    handoff = g6.build_g6_design_record_candidate_handoff(
        request_id="req-msme-g4-negative",
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
    )
    report = g6.validate_g6_design_record_candidate_not_g4_source(
        repo_root=Path("."),
        handoff=handoff,
    )

    assert report.status == "fail"
    assert "layer3_g6_g4_source_resolution_bypass_attempt" in report.issue_codes
```

- [x] **Step 6: Implement candidate handoff DTO**

`Layer3G6DesignRecordCandidateHandoff` is the bridge that satisfies the roadmap
"counterexample-refine loop -> DesignRecord" clause without promoting agent text
to authority. It must carry:

- `design_record_candidate_ref`
- `candidate_problem_frame`
- `counterexample_refinement_refs`
- `composed_loop_consumer_ref`
- `g5_invocation_plan_ref`
- `hypothesis_ledger`
- `status = "candidate_only"`
- `authoritative_for = ("layer3_g6_candidate_handoff_audit",)`
- `may_not_use_for = G6_MAY_NOT_USE_FOR`

The optional G4 validation helper must call or mirror
`layer3_promotion_gate.resolve_g4_source_design_record(...)` semantics enough to
prove that a G6 candidate handoff is not a resolved G4 source. It should fail
with `layer3_g6_g4_source_resolution_bypass_attempt` whenever the handoff lacks
full payload, replay ref, digest, or an upstream boundary that allows G4 source
promotion.

## Task 6: G5 Invocation Bridge

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add tests preserving current G5 unchanged blocker**

```python
def test_g6_routes_msme_request_to_g5_and_preserves_unchanged_blocker() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
    )

    assert invocation.status == "pass"
    assert invocation.g5_case_id == "ua-msme-affordable-loans-2022"
    assert invocation.g5_conversion_outcome == "unchanged_blocker"
    assert invocation.g5_bypass_detected is False
```

- [x] **Step 2: Add tests for outside-envelope abstention**

```python
def test_g6_outside_envelope_request_does_not_call_non_pinned_g5() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Design national unemployment insurance for a different country.",
        request_id="req-outside-1",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-outside-1",
            fixture_id="outside-envelope",
        ),
        demand_signal_refs=("s12-demand://fixture/outside-envelope",),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        search_health_refs=(
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        ),
    )

    assert invocation.status == "abstain"
    assert invocation.g5_case_id is None
    assert "layer3_g6_outside_g5_envelope" in invocation.issue_codes
```

Add a negative:

```python
def test_g6_outside_envelope_abstention_requires_search_health_and_demand_refs() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Design national unemployment insurance for a different country.",
        request_id="req-outside-no-health",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-outside-no-health",
            fixture_id="outside-envelope",
        ),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        search_health_refs=(),
    )

    assert invocation.status == "fail"
    assert "layer3_g6_outside_envelope_abstention_without_search_health" in invocation.issue_codes
    assert "layer3_g6_cheap_refusal_without_demand_signal" in invocation.issue_codes
```

Add a G5 authority-boundary negative:

```python
def test_g6_bridge_rejects_g5_conversion_as_g6_orchestration_authority() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-g5-authority-negative",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-g5-authority-negative"
        ),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        requested_authority_from_g5=("g6_arbitrary_request_orchestration",),
    )

    assert invocation.status == "fail"
    assert "layer3_g6_g5_may_not_use_for_ignored" in invocation.issue_codes
```

- [x] **Step 3: Implement bridge**

`build_g6_g5_invocation_plan(...)` must:

- call `g5.build_layer3_g5_bundle(repo_root)` for same-class requests;
- read the first G5 conversion record from the typed bundle;
- call `g5.build_g5_w12d_consumer_gate({"case_id": g5.G5_PINNED_CASE_ID}, ...)`;
- fail closed if the consumer gate is not `pass`;
- fail closed if any supplied `case_id` differs from G5's pinned case;
- fail closed if any caller asks to use G5 artifacts for a purpose present in
  `g5.G5_MAY_NOT_USE_FOR`, especially `g6_arbitrary_request_orchestration`;
- fail closed for outside-envelope abstention when search recall/index freshness
  refs or demand refs are missing;
- preserve `conversion_outcome` exactly.

Do not create a new G5 conversion record in G6.

## Task 7: Agent Run Record And Result Projection

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add tests for current and future G5 outcomes**

```python
def test_g6_agent_run_record_maps_current_g5_unchanged_blocker() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )

    assert record.outcome == "g5_unchanged_blocker"
    assert record.g5_conversion_outcome == "unchanged_blocker"
    assert record.engineering_readiness_status == "pass"
    assert record.grounded_value_closure_status == "blocked_by_current_g5_unchanged_blocker"
    assert "claim_authority" in record.may_not_use_for
    assert record.orchestration_choice_audit.status == "pass"
```

Add a synthetic projection test that does not mutate G5:

```python
def test_g6_result_projection_accepts_future_g5_grounded_abstention_fixture() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    result = g6.build_g6_grounded_result_or_abstention(
        request_id="req-fixture",
        g5_conversion_outcome="typed_blocker -> grounded_abstention",
        envelope_match_status="same_class_as_g5_pinned_case",
        g5_record_refs=("layer3-g5-conversion-record:fixture",),
        abstention_reason_refs=("layer3-g5://abstention/fixture",),
    )

    assert result.outcome == "g5_grounded_abstention"
    assert result.grounding_disposition == "grounded_abstention"
```

- [x] **Step 2: Implement run and result DTOs**

Use:

```python
Layer3G6AgentOutcome = Literal[
    "g5_grounded_result",
    "g5_grounded_abstention",
    "out_of_envelope_grounded_abstention",
    "g5_unchanged_blocker",
]
```

Mapping:

- `typed_blocker -> grounded_limited` -> `g5_grounded_result`
- `typed_blocker -> grounded_abstention` -> `g5_grounded_abstention`
- outside envelope -> `out_of_envelope_grounded_abstention`
- `unchanged_blocker` -> `g5_unchanged_blocker`

The run record owns orchestration audit and routing only. It does not own claim,
legal, proof, recommendation, or closeout authority. It must carry both:

- `engineering_readiness_status`: `pass`, `fail`, or `blocked`.
- `grounded_value_closure_status`: `pass`,
  `blocked_by_current_g5_unchanged_blocker`,
  `blocked_by_missing_search_or_demand_refs`, or `fail`.

`grounded_value_closure_status` is `pass` only for
`g5_grounded_result`, `g5_grounded_abstention`, or
`out_of_envelope_grounded_abstention` with search health and demand refs.

- [x] **Step 3: Add replay manifest and continuity tests**

```python
def test_g6_replay_manifest_and_continuity_bind_request_run_g5_and_projection_refs() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-replay-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-replay-1"),
    )
    continuity = g6.build_g6_orchestration_continuity(record)
    replay_manifest = g6.build_g6_replay_manifest(record, continuity=continuity)

    assert continuity.status == "pass"
    assert continuity.record["schema_version"] == (
        "policyos.runtime.nl_replay_orchestration_continuity.v1"
    )
    assert continuity.record["carrier_ref"]
    assert continuity.record["concept_spine_ref"]
    assert continuity.record["runtime_claim_registry_ref"]
    assert replay_manifest.status == "pass"
    assert replay_manifest.manifest["orchestration_continuity"]["continuity_ref"]
    assert replay_manifest.manifest["prompt_tool_parser_ledger"]
```

```python
def test_g6_replay_drift_blocks_readiness() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-replay-drift",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-replay-drift"),
    )
    continuity = g6.build_g6_orchestration_continuity(record)
    baseline = g6.build_g6_replay_manifest(record, continuity=continuity)
    replay = {
        **baseline.manifest,
        "orchestration_continuity": {
            **baseline.manifest["orchestration_continuity"],
            "carrier_ref": "evidence-spine:g6-other-carrier",
        },
    }
    drift = g6.explain_g6_replay_drift(
        baseline_manifest=baseline.manifest,
        replay_manifest=replay,
    )

    assert drift.status == "fail"
    assert "layer3_g6_replay_drift_unexplained" in drift.issue_codes
```

- [x] **Step 4: Implement replay DTOs and builders**

Use existing helpers from `runtime/quality/nl_replay_orchestration.py` and
`runtime/quality/replay.py`:

- `build_nl_replay_orchestration_continuity(...)`
- `validate_nl_replay_orchestration_continuity(...)`
- `build_replay_manifest(...)`
- `explain_replay_drift(...)`

`build_g6_orchestration_continuity(record)` must pass enough G6 surfaces to the
NL replay helper to satisfy continuity:

- request context with carrier, concept spine, jurisdiction spine, and
  policy-grammar projection refs;
- workflow/job state with agent run, search ledger, orchestration audit, and
  prompt/tool/hypothesis ledger refs;
- replay manifest or pending replay refs;
- quality-evidence payload carrying runtime claim registry,
  producer-handshake/producers, and selected producer-binding refs;
- bundle/readiness payload with expected artifact paths and readiness status;
- inspection payload carrying the orchestration-continuity component evidence
  ref;
- export/public projection payload with safe projection refs.

The helper-required surfaces are `request_context`, `workflow_state`,
`job_progress`, `replay_manifest`, `bundle`, `inspection`, `readiness`, and
`export`. Required ref families are `carrier_ref`, `concept_spine_ref`,
`jurisdiction_spine_ref`, `runtime_claim_registry_ref`, and
`producer_binding_refs`; singleton refs must not drift across surfaces.

If required refs are missing, return `status="fail"` with
`layer3_g6_orchestration_continuity_refs_missing`. If the continuity record is
missing entirely, readiness fails with
`layer3_g6_orchestration_continuity_missing`.

`build_g6_replay_manifest(record, continuity)` must include request payload
fingerprint, provider/model metadata, prompt template fingerprints,
tool/schema refs, policy-grammar projection refs, G5 artifact refs, search
ledger refs, orchestration audit refs, authority envelopes, prompt/tool parser
ledger, registry refs, and orchestration continuity. `explain_g6_replay_drift`
wraps `explain_replay_drift(...)`; any `unexplained_drift` or
`accepted_drift_non_ready` becomes G6 `status="fail"`.

## Task 8: Public/Audit Surfaces And Health Delta

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add surface and health tests**

```python
def test_g6_public_surface_hides_raw_prompt_and_denies_recommendation_authority() -> None:
    from pathlib import Path
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    surface = g6.build_g6_agent_audit_surface(record)

    assert surface.status == "pass"
    assert "raw_request" not in surface.PUBLIC
    assert surface.public_projection_contract_verification["status"] == "pass"
    assert surface.PUBLIC["authority_role"] == "projection_only"
    assert "policy_recommendation" in surface.PUBLIC["may_not_be_used_for"]
    assert surface.MACHINE["agent_run_record_refs"]
```

```python
def test_g6_health_delta_counts_demand_pull_and_abstention() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    delta = g6.build_g6_demand_pull_vs_abstention_delta(
        request_count=2,
        g5_routed_count=1,
        g5_grounded_result_count=0,
        g5_grounded_abstention_count=0,
        g5_unchanged_blocker_count=1,
        out_of_envelope_abstention_count=1,
        demand_source_refs=("s12-demand://fixture/outside-envelope",),
        accountable_principal_refs=("principal://runtime-quality-reviewer",),
    )

    assert delta.status == "pass"
    assert delta.readings["demand_reached_g5_rate"] == 0.5
    assert delta.readings["abstention_or_blocker_rate"] == 1.0
    assert delta.demand_source_refs
```

- [x] **Step 2: Implement all-audience surfaces**

PUBLIC fields:

- `surface_id`
- `request_fingerprint`
- `request_class`
- `envelope_match_status`
- `outcome`
- `g5_conversion_outcome`
- `safe_g5_refs`
- `denied_uses`
- `authority_role = "projection_only"`
- `projection_policy`
- `may_not_be_used_for`

REVIEWER fields:

- run record refs
- G5 invocation refs
- orchestration-choice audit refs
- blocker and abstention refs

EXPERT fields:

- tool-contract summary refs
- prompt/tool ledger refs
- hypothesis ledger refs
- candidate firewall refs
- conformance refs

MACHINE fields:

- generated artifact paths
- schema/rule versions
- replay fingerprint
- drift keys

The builder should call
`assert_policy_design_projection_not_authority(...)` or
`verify_policy_design_case_projection_consumer_contract(...)` from
`runtime/quality/projection_semantics.py` for the PUBLIC projection shape. If
G6 cannot provide a full closeout truth fixture, it must still use
`assert_policy_design_projection_not_authority(...)` and record
`public_projection_contract_verification.status = "pass"` only when the
projection is `projection_only`, `authoritative_for` is empty, and denied uses
include at least `claim_authority`, `scorecard_authority`,
`runtime_closeout_authority`, `policy_recommendation`, and
`recommendation_authority`.

## Task 9: Conformance Report

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py`

- [x] **Step 1: Add conformance negative tests**

Required negative IDs:

```python
REQUIRED_G6_NEGATIVES = {
    "agent_fluent_output_as_authority",
    "tool_choice_bias_hides_counterevidence",
    "agent_loop_trace_missing",
    "search_ledger_missing",
    "search_ledger_authority_boundary_leak",
    "tool_loop_transcript_only_not_audit",
    "llm_client_unavailable",
    "policy_grammar_compile_blocked",
    "policy_grammar_concept_refs_missing",
    "runtime_imports_policy_grammar",
    "hardcoded_template_classifier_only",
    "design_record_candidate_as_authority",
    "design_record_candidate_as_g4_source_record",
    "g5_bypass_attempt",
    "g5_may_not_use_for_ignored",
    "non_allowlisted_tool_attempt",
    "candidate_without_hypothesis_ledger",
    "public_raw_prompt_leak",
    "outside_envelope_abstention_without_search_health",
    "cheap_refusal_without_demand_signal",
    "out_of_envelope_g5_widening_attempt",
    "prompt_tool_ledger_missing",
    "prompt_tool_ledger_misread_as_authority",
    "orchestration_continuity_missing",
    "orchestration_continuity_refs_missing",
    "replay_manifest_missing",
    "replay_drift_unexplained",
    "orchestration_choice_audit_missing",
    "g7_region_widening_attempt",
}
```

Test:

```python
def test_g6_conformance_report_covers_agent_laundering_negatives() -> None:
    from polisyos.runtime.quality import layer3_bounded_agent as g6

    report = g6.build_g6_conformance_report()
    negative_ids = {item.negative_id for item in report.negative_results}
    observed_codes = {
        code for item in report.negative_results for code in item.observed_issue_codes
    }

    assert report.status == "pass"
    assert negative_ids >= REQUIRED_G6_NEGATIVES
    assert "layer3_g6_agent_candidate_used_as_authority" in observed_codes
    assert "layer3_g6_g5_bypass_attempt" in observed_codes
    assert "layer3_g6_g5_may_not_use_for_ignored" in observed_codes
    assert "layer3_g6_classifier_only_match_not_authority" in observed_codes
    assert "layer3_g6_policy_grammar_compile_blocked" in observed_codes
    assert "layer3_g6_runtime_imports_policy_grammar" in observed_codes
    assert "layer3_g6_non_allowlisted_tool_attempt" in observed_codes
    assert "layer3_g6_candidate_without_hypothesis_ledger" in observed_codes
    assert "layer3_g6_prompt_tool_ledger_missing" in observed_codes
    assert "layer3_g6_search_ledger_authority_boundary_leak" in observed_codes
    assert "layer3_g6_rejected_branch_memory_missing" in observed_codes
    assert "layer3_g6_g4_source_resolution_bypass_attempt" in observed_codes
    assert "layer3_g6_replay_drift_unexplained" in observed_codes
    assert "layer3_g6_outside_envelope_abstention_without_search_health" in observed_codes
    assert "layer3_g6_g7_region_widening_attempt" in observed_codes
```

- [x] **Step 2: Implement conformance report**

Each negative result must include:

- `negative_id`
- `status`
- `expected_issue_codes`
- `observed_issue_codes`
- `fixture_ref`

The report also carries:

- `candidate_firewall_check`
- `tool_contract_check`
- `agent_loop_trace_check`
- `search_ledger_check`
- `g5_bridge_check`
- `public_projection_boundary_check`
- `replay_manifest_check`
- `orchestration_continuity_check`
- `runtime_import_boundary_check`
- `performance_contract`

Build these checks from the shared helpers where possible:
`candidate_firewall_issues_for_payload(...)`,
`summarize_tool_contracts(...)`,
`tool_contract_default_blockers(...)`,
`assert_policy_design_projection_not_authority(...)`, and
`verify_policy_design_case_projection_consumer_contract(...)`. G6-specific
issue codes may wrap those helper results, but the conformance report should
not reimplement candidate-firewall, projection-boundary, or structured-tool
readiness semantics with ad-hoc string checks.

Performance contract:

```python
{
    "bounded_artifact_read_policy": "explicit_expected_paths_only",
    "request_path_repo_glob_allowed": False,
    "network_tool_access_default": False,
    "shell_tool_access_default": False,
    "g5_builder_import_mode": "lazy",
    "llm_simulation_mode_supported": True,
}
```

## Task 10: Readiness CLI And Artifact Writer

**Files:**

- Modify: `tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness_cli.py`

- [x] **Step 1: Add repo-quality tests**

The repo-quality test modules should mirror G5's pattern and import both the
validator module and the runtime constants explicitly:

```python
import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality import layer3_bounded_agent as g6

from tools.quality.validation import check_policy_design_case_layer3_g6_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_ARTIFACT_PATHS = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}
EXPECTED_MANIFEST_DRIFT_KEYS = {
    "g6_engineering_readiness_status",
    "g6_grounded_value_closure_status",
    "g6_policy_grammar_status",
    "g6_agent_loop_trace_status",
    "g6_llm_client_status",
    "g6_search_ledger_status",
    "g6_search_ledger_authority_boundary_status",
    "g6_design_record_candidate_handoff_status",
    "g6_g4_source_design_record_boundary_status",
    "g6_g5_bridge_status",
    "g6_g5_may_not_use_for_boundary_status",
    "g6_orchestration_choice_audit_status",
    "g6_orchestration_continuity_status",
    "g6_replay_manifest_status",
    "g6_replay_drift_status",
    "g6_runtime_import_boundary_status",
    "g6_public_projection_contract_status",
    "g6_outside_envelope_abstention_quality_status",
    "g6_demand_pull_vs_abstention_status",
}


def _validator():
    return validator
```

```python
def test_layer3_g6_readiness_passes_for_persisted_runtime_bundle() -> None:
    validator = _validator()

    write_report = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g6_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert validation["summary"]["g6_g5_bridge_status"] == "pass"
    assert validation["summary"]["g6_policy_grammar_status"] == "pass"
    assert validation["summary"]["g6_agent_loop_trace_status"] == "pass"
    assert validation["summary"]["g6_llm_client_status"] in {"pass", "blocked_with_typed_issue"}
    assert validation["summary"]["g6_search_ledger_status"] == "pass"
    assert validation["summary"]["g6_search_ledger_authority_boundary_status"] == "pass"
    assert validation["summary"]["g6_orchestration_choice_audit_status"] == "pass"
    assert validation["summary"]["g6_orchestration_continuity_status"] == "pass"
    assert validation["summary"]["g6_replay_manifest_status"] == "pass"
    assert validation["summary"]["g6_runtime_import_boundary_status"] == "pass"
    assert validation["summary"]["g6_public_projection_contract_status"] == "pass"
    assert validation["summary"]["g6_engineering_readiness_status"] == "pass"
    assert validation["summary"]["g6_grounded_value_closure_status"] in {
        "pass",
        "blocked_by_current_g5_unchanged_blocker",
    }
```

```python
def test_layer3_g6_readiness_mirrors_exact_artifact_and_drift_scaffold() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validation["artifacts"]["written_artifact_paths"]) == expected_paths
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g6_manifest_runtime_drift_key_count"] == 0
```

```python
def test_layer3_g6_write_path_must_include_every_expected_artifact(monkeypatch: Any) -> None:
    validator = _validator()
    omitted = Path("architecture/policy_design_case/layer3_g6_agent_run_records.json")
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g6_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }
```

Add CLI smoke tests mirroring G5:

```python
def test_layer3_g6_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g6_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": g6.G6_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g6_orchestration_continuity_refs_missing",
                    "path": "$.orchestration_continuity",
                    "message": "G6 replay continuity is missing required refs.",
                }
            ],
            "summary": {
                "schema_version": g6.G6_SCHEMA_VERSION,
                "g6_orchestration_continuity_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g6_readiness",
        fake_validate_layer3_g6_readiness,
    )
    output = tmp_path / "layer3-g6-readiness.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert calls == [(REPO_ROOT, False)]
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "layer3_g6_orchestration_continuity_refs_missing"
    assert "layer3_g6_orchestration_continuity_refs_missing" in stdout
```

```python
def test_layer3_g6_readiness_cli_write_mode_reports_exact_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    expected = sorted(path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS)

    monkeypatch.setattr(
        validator,
        "validate_layer3_g6_readiness",
        lambda repo_root, *, write=False: {
            "schema_version": g6.G6_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {"schema_version": g6.G6_SCHEMA_VERSION},
            "artifacts": {"written_artifact_paths": expected},
            "write": write,
        },
    )
    output = tmp_path / "layer3-g6-write.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--write",
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["write"] is True
    assert sorted(payload["artifacts"]["written_artifact_paths"]) == expected
```

- [x] **Step 2: Implement CLI structure**

Mirror G5's validator pattern:

- constants for expected paths;
- `EXPECTED_MANIFEST_DRIFT_KEYS`;
- `validate_layer3_g6_readiness(repo_root: Path, *, write: bool = False)`;
- `main(...)`;
- `_write_artifacts(...)`;
- `_validate_persisted_artifacts(...)`;
- `_validate_registration_and_docs(...)`;
- `_validate_runtime_surfaces(...)`;
- JSON and text output modes.

`_validate_runtime_surfaces(...)` must include the runtime import-boundary
check, public projection contract check, tool-contract summary check,
prompt/tool and hypothesis ledger projection checks, replay-manifest check, and
orchestration-continuity refs check. `_write_artifacts(...)` must return the
exact expected path set; extra or missing paths should fail readiness rather
than being silently accepted.

`EXPECTED_MANIFEST_DRIFT_KEYS` must include both readiness and value-closure
readings:

```python
"g6_engineering_readiness_status",
"g6_grounded_value_closure_status",
"g6_policy_grammar_status",
"g6_agent_loop_trace_status",
"g6_llm_client_status",
"g6_search_ledger_status",
"g6_search_ledger_authority_boundary_status",
"g6_design_record_candidate_handoff_status",
"g6_g4_source_design_record_boundary_status",
"g6_g5_bridge_status",
"g6_g5_may_not_use_for_boundary_status",
"g6_orchestration_choice_audit_status",
"g6_orchestration_continuity_status",
"g6_replay_manifest_status",
"g6_replay_drift_status",
"g6_runtime_import_boundary_status",
"g6_public_projection_contract_status",
"g6_outside_envelope_abstention_quality_status",
"g6_demand_pull_vs_abstention_status",
```

CLI command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py --repo-root . --write --output-format json
```

## Task 11: Generated Artifact Registration And Reference Docs

**Files:**

- Modify: `architecture/generated_artifacts.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `docs/reference/public-surface.md`
- Create: `docs/reference/policy-design-case-layer3-bounded-agent.md`
- Modify: `docs/reference/documentation-inventory.md`
- Modify: `docs/reference/index.md`
- Modify: `src/polisyos/runtime/quality/README.md`

- [x] **Step 1: Add G6 generated artifact family**

Add a `[[family]]` entry:

```toml
id = "policy-design-case-layer3-g6-bounded-agent-artifacts"
label = "Policy Design Case Layer 3 G6 bounded-agent artifacts"
owner = "team-runtime-quality"
approval_owner = "team-runtime-quality"
lifecycle = "generated_committed"
generator = "Layer 3 G6 readiness validator write mode"
verifier = "Layer 3 G6 readiness validator and architecture guardrails"
promotion_target = "registered Policy Design Case G6 bounded-agent audit surface artifacts"
stale_output_behavior = "fail"
source_of_truth = "src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py and tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py"
regenerate_commands = [
  "uv run python tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py --repo-root . --write --output-format json",
]
commit_policy = "committed_after_task10_write"
freshness_rule = "Regenerate and commit whenever the Layer 3 G6 bounded-agent runtime builder, validator, route registry, public projection refs, G5 bridge, or orchestration-choice audit rules change."
drift_gate = "automated"
workflow = "tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py"
check_cwd = "."
```

Set `outputs` to the expected artifact list from this plan.

- [x] **Step 2: Add reference doc**

`docs/reference/policy-design-case-layer3-bounded-agent.md` must include:

- surface id `layer3_g6_bounded_agent_surface`;
- readiness CLI;
- authority boundary;
- audience surface;
- generated artifact family;
- policy grammar projection and concept-spine requirements;
- policy grammar projection bridge and the default no-direct-runtime-import
  decision for `polisyos.policy_grammar`;
- G0-shaped search ledger boundary with `authoritative_for = ()`;
- NL/replay orchestration continuity and replay-manifest drift behavior;
- public projection boundary;
- agent loop trace and search ledger replay fields;
- candidate DesignRecord handoff boundary;
- G4 source DesignRecord non-bypass boundary;
- G5 `may_not_use_for` non-inheritance boundary;
- engineering readiness versus grounded value closure status;
- readiness signal.

Also update `src/polisyos/runtime/quality/README.md` with a concise G6 entry:
bounded arbitrary-request adapter, policy-grammar projection consumer, G5
bridge, replay/continuity surface, and explicit note that `runtime.quality` does
not eagerly export G0/G5/G6 modules.

Use G5's reference doc shape, but G6-specific denied uses must include
`claim_authority`, `legal_authority`, `policy_recommendation`, and
`g7_region_widening`.

- [x] **Step 3: Register public surface paragraph**

Add a paragraph in `docs/reference/public-surface.md` under Policy Design Case
Generated Audit Surfaces:

```markdown
`layer3_g6_bounded_agent_surface` is a generated PUBLIC/REVIEWER/EXPERT/MACHINE
Policy Design Case audit surface documented in
`docs/reference/policy-design-case-layer3-bounded-agent.md`. It publishes
agent-run refs, policy-grammar projection refs, G5 invocation refs,
search-ledger refs, replay-manifest refs, orchestration-continuity refs,
candidate DesignRecord handoff refs, orchestration-choice audit refs, and
projection-only public refs;
`layer3_g6_public_export_projection_refs.json` records
`out_of_scope_reference_only` and does not register a public-export bundle route.
```

## Task 12: Verification And Closeout

**Files:**

- All files touched above.

- [x] **Step 1: Run focused tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness_cli.py -q
```

Expected: all pass.

- [x] **Step 2: Write and validate artifacts**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py --repo-root . --write --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py --repo-root . --output-format json
```

Expected: both return exit code 0 and `status = "pass"`.

- [x] **Step 3: Run G5 guard to prove G6 did not mutate G5 semantics**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py --repo-root . --output-format json
```

Expected: exit code 0. The current repo may still report
`g5_conversion_outcome = "unchanged_blocker"`; that is acceptable for G6 as long
as G6 preserves it and does not mint grounded authority.

- [x] **Step 4: Run architecture guardrails**

```bash
cd policy-engine
uv run polisyos-tools architecture guardrails check
```

Expected: exit code 0, or only pre-existing unrelated failures documented in
the implementation summary.

- [x] **Step 5: Run runtime API contract check**

```bash
cd policy-engine
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Expected: exit code 0, or only pre-existing unrelated failures documented in
the implementation summary. G6 should not require widening
`architecture/public_surface/contract.toml`.

- [x] **Step 6: Pattern closeout**

Before final implementation summary, reopen
`docs/reference/policy-design-case-failure-patterns.md` and report the relevant
G6 closure IDs: `P01`, `P02`, `P03`, `P04`, `P05`, `P07`, `P08`, `P09`,
`P10`, `P13`, `P15`, `P16`, `P25`, and `P26`.

## Acceptance Checklist

- [x] G6 module uses strict Pydantic DTOs and local status literals.
- [x] G6 request envelope consumes a typed projection produced by
  `policy_grammar.PolicyGrammarCompiler` in the readiness/tooling boundary,
  uses concept/jurisdiction spine refs and grammar/facet matching joined to G5
  envelope refs, and keeps classifier-only keyword matches as blockers, not
  authority.
- [x] `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` does not directly
  import `polisyos.policy_grammar` on the default implementation path.
- [x] Blocked policy grammar compilation or missing concept-spine refs produce
  typed blockers, not same-class routing.
- [x] The bounded agent-loop producer invokes the existing LLM/tool-loop surface
  in tests or simulation and emits an agent loop trace.
- [x] Missing LLM client/config produces `layer3_g6_llm_client_unavailable`
  instead of a silent static mock trace.
- [x] LLM/agent output is candidate-only and represented in hypothesis ledger.
- [x] Prompt/tool ledger usage is a G6 lineage projection and is not treated as
  prompt/tool parser authority for G6 claim/legal authority.
- [x] Candidate firewall rejects G6 candidates in authority slots.
- [x] Tool registry is allowlisted, schema-strict, bounded, and response-capped.
- [x] G6 search ledger records selected/rejected candidates, budget cutoffs,
  incompleteness, and search health refs.
- [x] G6 search ledger mirrors the G0 control-plane boundary and keeps
  `authoritative_for = ()`; orchestration audit owns G6 routing authority.
- [x] A raw `ToolLoopResult` transcript without rejected-branch/incompleteness
  memory cannot satisfy G6 audit/search readiness.
- [x] Orchestration-choice audit records selected and rejected tool/evidence
  branches, framing choices, and replay fingerprint.
- [x] G6 persists an NL/replay orchestration-continuity record and replay
  manifest; unexplained replay drift fails readiness.
- [x] Candidate DesignRecord handoff is persisted and remains candidate-only.
- [x] Candidate DesignRecord handoff cannot be used as a G4 source DesignRecord
  without full payload, replay ref, digest, and upstream boundary checks.
- [x] G5 bridge calls typed G5 builders and preserves G5 conversion outcome.
- [x] G5 `may_not_use_for` is enforced; G5 artifacts are not reused as G6
  arbitrary-request orchestration authority.
- [x] Current G5 unchanged blocker is not reworded as grounded result.
- [x] Readiness manifest distinguishes engineering readiness from grounded value
  closure while current G5 remains `unchanged_blocker`.
- [x] Future G5 grounded result/abstention fixture projects through the same
  G6 result mapping.
- [x] Out-of-envelope requests produce grounded abstention only with search
  recall/index freshness and demand refs; otherwise they fail closed.
- [x] PUBLIC surface has no raw prompt, raw transcript, or recommendation text.
- [x] PUBLIC projection uses shared projection authority checks where possible
  and records `public_projection_contract_verification.status = "pass"` only
  for projection-only, empty-authority, deny-listed projections.
- [x] Generated artifact family, inventory, public-surface docs, and reference
  docs are registered.
- [x] Readiness CLI passes in write and read modes.
- [x] Separate G6 readiness CLI smoke tests cover JSON issue-code output and
  exact write-artifact paths.
- [x] Negative semantic tests cover LLM authority laundering, hidden
  counterevidence, G5 bypass, non-allowlisted tools, missing ledgers, public raw
  prompt leaks, classifier-only authority, cheap refusal, missing search health,
  DesignRecord-candidate laundering, runtime import-boundary violations,
  replay/continuity drift, and G7 widening attempts.
