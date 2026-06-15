# Policy Design Case Layer 3 Bounded Agent

Owner: `team-runtime-quality`
Source of truth: `src/polisyos/runtime/quality/layer3_bounded_agent.py`, `tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py`, and `architecture/policy_design_case/layer3_g6_readiness_manifest.json`

G6 is the bounded arbitrary-request adapter for Policy Design Case Layer 3. It
accepts a natural-language request, projects it into policy-grammar routing
facets, runs an allowlisted agent/tool loop, and either routes a same-class
request through the G5 proving-ground bridge or emits a grounded abstention. It
does not mint claim, legal, closeout, publication, or policy-recommendation
authority.

Surface id: `layer3_g6_bounded_agent_surface`

Readiness CLI:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py --repo-root . --write --output-format json
```

## Authority Boundary

The G6 audit surface is authoritative only for:

- `layer3_g6_agent_orchestration_audit`
- `layer3_g6_g5_routing_decision`
- `layer3_g6_demand_pull_vs_abstention_reading`

It is not authoritative for production authority, rollout authority,
publication authority, approval authority, scorecard authority, closeout
authority, runtime closeout authority, public recommendation,
policy_recommendation, legal advice, `legal_authority`, `claim_authority`,
obligation authority, causal-effect authority, proof authority, G5 conversion
authority without G5, or `g7_region_widening`.

## Audience Surface

The generated audit surface is exposed to `PUBLIC/REVIEWER/EXPERT/MACHINE`:

- `PUBLIC` receives bounded request class, result-or-abstention status, denied
  uses, issue-code refs, and projection-only public refs. It does not receive
  raw prompts or raw upstream payloads.
- `REVIEWER` receives agent-run refs, G5 invocation refs, search-ledger refs,
  orchestration-choice audit refs, continuity refs, replay refs, and candidate
  DesignRecord handoff refs.
- `EXPERT` receives policy-grammar projection refs, concept-spine refs,
  tool-contract summary, prompt/tool and hypothesis ledger refs, conformance,
  route registry, and health metric refs.
- `MACHINE` receives persisted JSON/TOML artifacts for write-set completeness,
  manifest drift, replay continuity, G5 bridge checks, projection authority
  checks, and readiness validation.

## Generated Artifacts

Generated artifact family:
`policy-design-case-layer3-g6-bounded-agent-artifacts`

The family is registered in `architecture/generated_artifacts.toml` with
`stale_output_behavior = "fail"` and `drift_gate = "automated"`.

Primary persisted artifacts:

- `architecture/policy_design_case/layer3_g6_request_envelope.json`
- `architecture/policy_design_case/layer3_g6_policy_grammar_projection.json`
- `architecture/policy_design_case/layer3_g6_grounding_demand_record.json`
- `architecture/policy_design_case/layer3_g6_tool_contract_summary.json`
- `architecture/policy_design_case/layer3_g6_prompt_tool_ledger_projection.json`
- `architecture/policy_design_case/layer3_g6_hypothesis_ledger_projection.json`
- `architecture/policy_design_case/layer3_g6_search_ledger.json`
- `architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json`
- `architecture/policy_design_case/layer3_g6_design_record_candidate_handoff.json`
- `architecture/policy_design_case/layer3_g6_g5_invocation_plan.json`
- `architecture/policy_design_case/layer3_g6_g5_consumer_gate.json`
- `architecture/policy_design_case/layer3_g6_orchestration_continuity.json`
- `architecture/policy_design_case/layer3_g6_replay_manifest.json`
- `architecture/policy_design_case/layer3_g6_agent_run_records.json`
- `architecture/policy_design_case/layer3_g6_grounded_result_or_abstention.json`
- `architecture/policy_design_case/layer3_g6_agent_audit_surface.json`
- `architecture/policy_design_case/layer3_g6_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_g6_conformance_report.json`
- `architecture/policy_design_case/layer3_g6_agent_route_contract_registry.toml`
- `architecture/policy_design_case/layer3_g6_readiness_manifest.json`

## Policy Grammar Bridge

G6 consumes a policy grammar projection and concept-spine refs before routing a
request. The projection carries a compiled-case ref, routing facets, concept
spine refs, jurisdiction spine refs, and denied uses. Missing concept-spine refs
or blocked compilation produce typed blockers such as
`layer3_g6_policy_grammar_concept_refs_missing` and
`layer3_g6_policy_grammar_compile_blocked`.

The default runtime decision is no direct eager import of
`polisyos.policy_grammar` from `polisyos.runtime.quality.layer3_bounded_agent`.
The readiness validator may compile a projection as an external producer bridge,
but the runtime module consumes the projection artifact and keeps policy grammar
authority limited to routing facets.

## Search And Replay Boundary

The G6 search ledger is G0-shaped for replay and audit: it records normalized
query refs, searched index refs, selected evidence refs, selected candidate
refs, rejected candidate refs, selected/rejected tool names, search health refs,
ranking policy ref, cutoff budget ref, and a deterministic replay key.
Its authority boundary is explicit: `authoritative_for = ()`.

The agent loop trace is not a transcript-only substitute for audit. Replay
requires the agent run record, prompt/tool ledger projection, hypothesis ledger
projection, search ledger, G5 invocation refs, orchestration-choice audit,
orchestration continuity, replay manifest, model profile, prompt fingerprint,
tool schemas, schema version, and rule version. Unexplained replay divergence
must surface as `layer3_g6_replay_drift_unexplained`.

## Handoff And Bridge Boundaries

Candidate DesignRecord handoff is candidate-only. G6 may create a candidate
problem frame and counterexample-refinement refs for reviewer inspection, but it
cannot become a G4 source DesignRecord or bypass G4 source resolution. Attempts
to treat it as G4 source authority produce
`layer3_g6_g4_source_resolution_bypass_attempt`.

G6 may invoke G5 only for the pinned same-class envelope. It must preserve G5
conversion outcomes and must not inherit or erase G5 `may_not_use_for` denied
uses. A G5 bypass, non-pinned widening attempt, ignored denied use, or G7 region
widening attempt remains a G6 blocker rather than a recommendation.

## Public Projection Boundary

`layer3_g6_public_export_projection_refs.json` is projection-only. Its
`public_export_hook_status` is `out_of_scope_reference_only`, and
`public_export_bundle_route_registered` is false.

The public projection must preserve denied uses such as `claim_authority`,
`legal_authority`, `policy_recommendation`, `runtime_closeout_authority`,
`recommendation_authority`, and `g7_region_widening`. It may not carry
`raw_request`, raw prompts, raw upstream payloads, or allocation/recommendation
text.

## Readiness Signal

G6 readiness separates engineering readiness from grounded value closure.
`g6_engineering_readiness_status = "pass"` means the adapter, artifacts,
validator, G5 bridge, replay refs, public projection boundary, and docs
registration are wired. `g6_grounded_value_closure_status` can still be
`blocked_by_current_g5_unchanged_blocker` when the current same-class G5 result
is an unchanged blocker rather than useful grounded design value.

Task 11 closes when `--write` refreshes every expected G6 artifact, the
persisted readiness manifest has no runtime drift, generated artifacts and
Policy Design Case inventory are registered, reference docs/index/public-surface
markers are present, and the readiness validator reports all registration
statuses as `pass`.
