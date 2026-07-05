# GY-N0 Generation-Cycle Surface Investigation

## Goal

This is the census half of GY-N0 for the Phase 5 B-on-A Generation Cycle slice. The goal is to capture, from actual code execution paths and function bodies, what the PolicyOS generation-cycle surface really contains: what each relevant file does, how files interconnect, and what is real vs shadow vs stub vs hardcoded vs dead.

This document is intentionally a living, multi-pass notebook. It is the source of truth for later GY-N1..N7 rewrite work and for the disposition ledger.

## Method

- Read function bodies before making claims. File names, module names, docstrings, and comments are not evidence by themselves.
- Trace data flow across producers, typed artifacts, orchestration bridges, consumers, verification, and external/audit/API/dashboard surfaces.
- Where a verdict depends on whether a function computes real output, run a small read-only throwaway probe with `JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src"`.
- Anchor each claim with `file:line` and/or probe output.
- Prefer depth over breadth per pass. It is acceptable and expected that early findings are revised as later files reshape the picture.

## Convention

All findings are **PROVISIONAL** until enough connected files have been read to prove or revise them. Revisions are expected and valuable: one file can give a first impression, two more can overturn it, and several passes should converge on precise dispositions.

Verdict vocabulary:

- `REAL`: performs substantive computation or orchestration and is reachable by a live owner.
- `SHADOW`: resembles a real path but is parallel, disconnected, demo-only, or not the authority path.
- `STUB`: placeholder behavior, unimplemented branch, no-op, or contract without meaningful producer/consumer behavior.
- `HARDCODED`: output dominated by fixed constants/templates rather than input-sensitive computation.
- `DEAD`: not reachable by observed callers or only retained compatibility surface.

Capability labels for incomplete surfaces: `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, `semantic_test_missing`.

## Coverage Tracker

### Repo Guidance / Pattern Lens

- [done] `policy-engine/CONTRIBUTING.md`
- [done] `policy-engine/docs/reference/policy-design-case-failure-patterns.md`

### Front Door / NL Typing

- [done] `runtime/http/services/control/nl_pipeline.py` (front-door path, Pass 1 relevant bodies)
- [done] scientist node `node_plan_policy_request`
- [done] typed NL output / `DesignProblem`-like owners discovered from code in Pass 1
- [done] `runtime/quality/assurance_case.py` intent/PDC builders reached by NL pipeline
- [done] `scientist/agent/protocols.py` `ProblemFrame` / `DataNeedSpec`
- [done] `scientist/agent/pi.py`
- [done] `scientist/agent/data_need_extractor.py`

### Generative DAG

- [done] `scientist/orchestration/workflows/policy_design.py`
- [done] `scientist/orchestration/workflows/builder.py` (selection/run path bodies)
- [done] `scientist/orchestration/workflows/selection.py`
- [done] `scientist/orchestration/workflows/engine_simple.py`
- [done] `scientist/orchestration/workflows/engine_langgraph.py`
- [done] policy-design nodes: plan / legal candidate pack / draft policy options / formalize / hierarchical-search
- [done] `scientist/api.py` (`run_experiment`)
- [done] `scientist/validation/policy_verified/service.py` (request/legal/option/formalize bodies)
- [done] `scientist/validation/policy_verified/models.py` (policy request/option contracts)
- [done] `lex/interventions.py` (`HierarchicalPolicySearchAdapter`)
- [done] `lex/intervention_artifacts.py` (`LexPolicyBundleInput`)
- [done] `scientist/policy_design/search.py` (coordinator/generation/search bodies)
- [done] `scientist/policy_design/schema.py` (`PolicyCandidateSchema.from_trinity_bundle`)

### Shadow Design Search

- [done] `pdc/_impl/layer2_design_search.py` (Pass 2 core S2 runner, constructors, projection, persistence)
- [done] `run_s2_shadow_design_loop`
- [done] `_candidate`
- [done] `_grammar_expansion`
- [done] `SearchIteration`, `no_retry_without_new_grammar`, `RefinementDecision`, `CounterexampleRecord`
- [done] S2 caller/import scan (`src`, validator tools, tests)

### Honest Backbone Loop

- [done] `runtime/quality/workspace/loop.py` (Pass 2 loop/foundation bodies)
- [done] `run_fixture`
- [done] `run_intent`
- [done] `select_search_terminal`
- [done] `OperationRegistry`
- [done] BIND / ESTIMATE / VERIFY operation flow
- [done] ESTIMATE to foundry reachability through Phase-2 `FoundryMethodOutputConsumer`
- [done] acquisition handling in Slice-0 fixture path

### Value / Outcome / Causal / Optimization

- [done] `runtime/quality/design_axes/outcome_prediction.py` (Pass 2 S10 gate/readiness bodies)
- [done] `scientist/nodes/builtins/simulate/run_causal_evaluation.py` (Pass 2 discovered reachable Foundry-method executor)
- [done] foundry causal catalog under `foundry/methods/catalog/causal/*` (Pass 2 dependency/fallback slices only)
- [done] foundry optimization catalog under `foundry/methods/catalog/optimization/*` (Pass 2 dependency/fallback slices only)
- [done] econml / dowhy / cvxpy runtime import risk check
- [done] statsmodels / jax / scipy / pymoo reachable-method probe
- [done] Pass 3 bounded candidate -> causal effect -> production policy runtime value probe

### Acquisition

- [done] `runtime/quality/acquisition_planner.py` (Pass 2 path used by workspace loop)

### Promotion / Authority / Two-Ring Waist

- [done] `runtime/quality/proving_ground/governed_promotion_gate.py` (Pass 2 G4 bodies/probes)
- [done] `pdc/_impl/gy_waist.py` (Pass 2 Ring-2 / authority derivation / waist contracts)
- [done] `pdc/_impl/layer2_readiness.py` (Pass 2 authority boundary/readiness contracts)
- [done] `runtime/quality/proving_ground/status_decision_reducers.py` (`reduce_g4_promotion_state`, Pass 2 support read)
- [done] `scientist/nodes/builtins/decide/run_policy_promotion.py` (Pass 2 direct node status)
- [done] `scientist/methods/search/promotion_evidence.py` and `scientist/methods/search/judge_stack.py` promotion coordinator slices (Pass 2)

### Bounded Agent

- [done] `runtime/quality/proving_ground/bounded_request_agent.py` (Pass 2 G6 execution spine/probes)
- [done] `runtime/quality/workspace/agent_proposal_bridge.py` (Pass 2 bridge/probes)

### Newly Discovered Owners

- [done] `scientist/orchestration/llm/cycle.py` (`build_default_execution_plan`, preflight/evaluator/reproducibility; Pass 3 generator/value selection slices)
- [done] `scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py` (Pass 3 runtime/promotion slices)
- [done] `scientist/agent/drafter_clients.py`, `_drafter_llm.py`, `_drafter_orchestrator.py`, `_drafter_parsing.py`, `formalizer.py`, `critic.py`, `informed_critic.py` (Pass 3 generator/critic slices)
- [done] `fabric/retrieval` retrieval service path (Pass 3)
- [done] Scholar search/discover/OpenAlex/Fabric acquisition execution owners (Pass 3)
- [done] candidate firewall / entailment / SKG grounding owners (Pass 3)
- [done] DesignProblem candidate type census (Pass 3)
- [done] remaining design axes + scorecard + method selection registry (Pass 3)
- [done] `scientist/nodes/builtins/compile/compile_foundry.py` (Pass 2)
- [done] `scientist/nodes/builtins/causal/run_causal_readiness.py` (Pass 2)
- [done] `scientist/nodes/builtins/simulate/run_simulation.py` (Pass 2)
- [done] `scientist/nodes/builtins/decide/policy_runtime_support.py` (Pass 2)
- [done] `scientist/policy_design/objectives.py` (`ObjectiveStack.evaluate`, Pass 2 support read)
- [done] `runtime/quality/workspace/foundry_consumption.py` (Pass 2)
- [done] `runtime/quality/workspace/scientist_node_adapters.py` (Pass 2)
- [done] `runtime/quality/workspace/workflow_playbook_projection.py` (Pass 2)
- [done] `foundry/methods/selection/advisor.py` (Pass 4 ranking/cost/consensus bodies and probe)

### Pass 4: North-Star Completion Sweep

- [done] isolated Python 3.13 dependency/runtime experiment (`econml`, `dowhy`, `cvxpy`, JAX, statsmodels, targeted loop/value/core tests)
- [done] world-model representation/construction (`foundry/agent_sim/world`) and simulation bridge
- [done] joint simulation vs pairwise-only composition (`CompositionCertificate`, `coupling_composition`, GY-G recursion)
- [done] typed intervention atom / policy grammar / candidate parameterization census
- [done] post-deployment confirmatory and exploratory monitoring (`ddm/detectors`, `ddm/calibration/multiple_testing`, deployed-effect tracking)
- [done] `RequiredDataSpec` / available-data / world-model data binding / VOI gap consumption
- [done] Fabric connector and acquisition execution depth (plan -> search -> ingest -> SKG -> loop re-entry)
- [done] authority derivation and effective evidence-independence (`AuthorityDerivationTrace`, evidence-kind/decision-grade, effective independence graph)
- [done] north-star organ checklist and Pass-4 revisions to cross-cutting maps and GY-N1..N7 mapping
- [done] final coverage-tracker walk and Pass-5 start/remainder items

### Pass 5: Final Hidden-Code Sweep / World-Model Correction

- [done] `fabric/world` store/materialize/query/snapshot correction (Pass 5)
- [done] `fabric/world/store/{emit,persist,segments,validate,snapshots}.py`
- [done] `fabric/world/materialize/{duckdb,projections,sql,staging,kuzu}.py`
- [done] `fabric/world/query.py`
- [done] hidden useful-code subsystem sweep across `src/polisyos/*` for the missing/partial cycle needs
- [done] `ir/model_layer/model_spec.py` + `core/contracts/trinity.py` hidden world-model contract owner
- [done] `data_forge/kernel/snapshot/{finalize,time_travel}.py`, `data_forge/kernel/artifacts.py`, `runtime/quality/data_forge_binding.py`
- [done] `foundry/data_plane/bindings.py` + `foundry/execute/api.py` data-snapshot-to-`GlobalState` binding
- [done] `scientist/methods/search/voi_scheduler.py` + `scientist/methods/search/strategies/advanced_policy.py`
- [done] `foundry/methods/catalog/bayesian/{variational,protocols}.py`, `foundry/methods/catalog/econometrics/expansion.py`, `foundry/calibration/uncertainty_adapter.py`
- [done] `ir/analytics/transportability.py`, `foundry/methods/catalog/causal/{transport_engine,transport_check,density_ratio}.py`, `method_requirement/*`
- [done] `foundry/methods/catalog/simulation/coupled.py`, `simulation/dynamics.py`, NCM and shared-state executor precision pass
- [done] intervention atom binding contract refinement after sweep
- [done] WorldModelRecord / lifecycle envelope contract after sweep
- [done] joint-simulation horizon-controller contract after sweep
- [done] live credentialed LLM gateway probe
- [done] live OpenAlex provider probe

## Per-Asset Findings

### Repo Guidance / Pattern Lens

Status: done for Pass 1 setup.

What it says:

- `policy-engine/CONTRIBUTING.md:53-66` sets style constraints that matter if later GY tasks become code work: public APIs typed, strict Pydantic DTOs via `extra="forbid"`, lazy imports for heavy/boundary-sensitive modules, and Google-style docstrings.
- `policy-engine/CONTRIBUTING.md:93-128` establishes architecture boundaries. For this investigation, the important fact is that `runtime` is allowed to import `scientist`, `lex`, `foundry`, `fabric`, `core`, `ir`, and `common`, while `foundry` must not import `scientist` or `runtime`. That directionality matters when judging whether the GY workspace loop can legitimately reach foundry methods versus whether foundry methods should know about the loop.
- `policy-engine/CONTRIBUTING.md:25-40` says heavyweight Foundry/Scientist work belongs behind the optional `research` dependency group, while runtime baseline is separate. This is the first reason to explicitly check econml/dowhy/cvxpy availability on the active Python.
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md:16-35` defines the capability reality check and the precise missing-state labels this notebook will use.
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md:69` (`P25`) is directly relevant to any search loop: persist search frontier, search incompleteness, budget cutoffs, and frontier provenance; do not project best-so-far as authoritative.
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-74` (`P27`, `P30`) are directly relevant to GY because the register already names `runtime/quality/workspace/loop.py` as too broad and flags plan/slice-named modules as bypass risks.
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md:75-78` (`P31`-`P34`) are the closeout lens for authority/promotion decisions: one structural invariant, resolve-bind-verify evidence intake, adversarial variants, and completed isolation before excluding failures.
- Grounding anchors in `policy-engine/docs/reference/policy-design-case-failure-patterns.md:151-155` pre-identify several files that overlap this census: `src/polisyos/runtime/quality/workspace/loop.py`, `workspace/agent_proposal_bridge.py`, `proving_ground/bounded_request_agent.py`, `scientist/policy_design/search.py`, and `pdc/_impl/gy_waist.py`.

Investigation impact:

- Treat search/generation claims as suspect until the code proves there is a persisted ledger, budget/cutoff provenance, and a consumer that acts on the result.
- Treat plan-named or slice-local GY code as possible `SHADOW`/`P27` until it is proven to extend the canonical owner.
- Treat authority/promotion paths as incomplete unless evidence resolution, content binding, verifier provenance, and consumer enforcement are visible in code.

Verdict:

- Guidance is not itself product code, but it sets the required evidence bar for this notebook. Relevant anti-patterns for the first pass: `P01`, `P02`, `P05`, `P10`, `P15`, `P25`, `P27`, `P30`, `P31`, `P32`, `P33`, `P34`.

### `runtime/http/services/control/nl_pipeline.py`

Status: done for Pass 1 front-door path. This is a huge runtime control mixin; only the generation-cycle relevant function bodies were read in this pass.

What it does:

- Defines `NaturalLanguageRunMixin._execute_nl_pipeline(...)` as the durable control-plane path for an NL request (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1131-1159`). It is not a small NL parser; it nests the full runtime job flow, artifact publication, model-variant execution, runtime-quality publication, and final Scientist workflow handoff.
- Imports runtime/foundry/scientist producers lazily inside the nested async pipeline (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1175-1275`). This includes `build_policy_intent_envelope`, `build_policy_design_case_profile`, Scientist agent mocks/LLM agents, `build_default_execution_plan`, execution preflight/evaluator persistence, and policy grounding reports.
- Canonicalizes metric payloads in context/execution-plan/stop criteria/governance/expected outputs before work starts (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1436-1495`). Serious profiles fail on unknown metrics (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1440-1448`).
- Publishes runtime-quality artifacts through `_persist_and_publish_runtime_quality_payload`, which calls `write_runtime_authority_artifact` with `authority_role="producer_authority"` and `provenance_kind="runtime_emitted"`, then records CAS ref, diagnostic event ref, authority envelope ref, manifest ref, and payload hash back into `runtime_quality_refs` / `runtime_quality_evidence` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:2914-3035`).
- Builds a runtime `PolicyIntentEnvelope` before model variants run (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3128-3219`). The envelope is field extraction from `context` plus defaults: `policy_problem` falls back to the raw `nl_request`; `proposed_intervention` falls back to `domain_hint` or `"independent policy analysis"`; authority level is reconciled against the runtime profile (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3131-3194`).
- Builds a capability duty ledger from the fixed `POLICY_DESIGN_REQUIRED_CAPABILITIES` tuple, sets each duty to `selected`, then manually sets `ledger_payload["status"] = "pass"` before publication (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3263-3288`). This is a load-bearing hardcoded pass marker until a later file proves downstream validation demotes it.
- Builds concept and jurisdiction spines after intent materialization (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3375-3499`). The concept spine uses raw text terms extracted from the intent; the jurisdiction spine is seeded from a synthetic lex normative report with `"status": "blocked"` and issue `jurisdiction_spine_seed_requires_lex_norms` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3344-3373`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3417-3445`).
- Builds and persists a runtime PDC profile from intent + capability ledger + spines before any model variants execute (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3501-3570`, call site `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:5579-5603`).
- Runs one or more `_run_variant(...)` executions. If there is no gateway LLM client, it falls back to mock PI/data-need/drafter/formalizer/critic when allowed (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4221-4288`). The variant path creates a Scientist agent `ProblemFrame`, extracts `DataNeedSpec`s, builds/persists an `ExecutionPlan`, preflights it, resolves/fetches retrieval data, drafts/formalizes/critiques/refines, stores a Trinity bundle and final policy claims, and returns a selected variant payload (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4448-5577`).
- The default `ExecutionPlan` is built with `method_dag=[]` when no explicit plan payload is supplied (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4519-4529`). If preflight fails, the lightweight replan also clears `method_dag` and `method_edges` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4654-4664`).
- After model variants complete, selection is first approved variant with a bundle, otherwise first non-failed variant, otherwise a last-resort mock fallback if allowed (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:5695-5724`). Selection itself is not a policy design search; it is model-variant selection.
- The selected variant is wrapped into `state_payload` and passed to `polisyos.scientist.api.run_experiment(...)` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6389-6597`). The state payload carries refs for final claims, execution plan, method catalog, preflight, evaluator, iteration state, reproducibility, runtime quality refs/evidence, retrieval telemetry, and flags, but it does not contain a `DesignProblem` object in the bodies read (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6394-6525`).
- For serious profiles, after `run_experiment`, it looks for or builds a Foundry method report (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6655-6719`) and then persists it as runtime quality evidence with Trinity/data/input refs when present (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6720-6786`).

What it calls:

- Runtime-quality builders in `runtime/quality/assurance_case.py`: `build_policy_intent_envelope`, capability ledger/profile/spine builders (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1212-1220`, bodies summarized below).
- Scientist agent circuit: `MockPIAgent`/`LLMPIAgent`, `MockDataNeedExtractorAgent`/`LLMDataNeedExtractorAgent`, drafter, formalizer, critic (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1242-1254`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4266-4288`).
- Scientist cycle helpers: `build_default_execution_plan`, `preflight_execution_plan`, `evaluate_iteration`, and persistence helpers (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1259-1269`, call sites `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4484-4729`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:5123-5135`).
- `polisyos.scientist.api.run_experiment` after local variant selection (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6576-6597`).

What calls it:

- Not traced in Pass 1. Open question: identify the HTTP route/service method that invokes `_execute_nl_pipeline` and whether all external NL entrypoints route through this mixin.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Verdict: `REAL` runtime control wrapper, but generation semantics are mixed: runtime intent/PDC publication is `REAL` persistence, default method planning is `HARDCODED/EMPTY`, capability duty status is provisionally `HARDCODED`, and mock NL interpretation is `HARDCODED`.
- Evidence for `REAL`: artifacts are persisted through `write_runtime_authority_artifact`, diagnostic event refs and authority envelope refs are retrieved from CAS and published into progress/state (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:2940-3035`).
- Evidence for `HARDCODED/EMPTY`: default execution plan always receives `method_dag=[]` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4519-4529`), replan clears method DAG again (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4654-4664`), and capability ledger is assigned `"status": "pass"` immediately after construction (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3282-3288`).
- Evidence for no direct `DesignProblem` in this path so far: the front-door typed objects read are runtime `PolicyIntentEnvelope` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3128-3219`) and Scientist agent `ProblemFrame` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4448-4458`), then `state_payload` for `run_experiment` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6389-6525`). No body read constructs a `DesignProblem`-named type.

Disposition hint:

- `REWORK_TO_FIT`: reuse the real artifact publication, runtime intent, and state handoff machinery, but do not treat the existing NL pipeline as the B-on-A generation cycle. It is an agent-circuit runner with runtime-quality sidecars and an eventual Scientist workflow handoff. For GY, the empty/default plan and hardcoded capability pass need explicit disposition.

Open questions:

- Which HTTP service method calls `_execute_nl_pipeline`?
- Does `scientist.api.run_experiment` consume the execution plan/final claims in a way that creates real candidate generation, or is it a separate Scientist DAG with different semantics?
- Does any downstream profile builder demote the hardcoded capability ledger `"pass"` when required duties are not actually produced/consumed?

### `runtime/quality/assurance_case.py` Intent/PDC Builders

Status: done for Pass 1 front-door calls only.

What it does:

- Defines the required Policy Design Case capability names as a fixed tuple: `lex`, `fabric`, `scholar`, `foundry`, `scientist`, `compiler`, `review`, `publication`, `audit` (`policy-engine/src/polisyos/runtime/quality/assurance_case.py:94-104`).
- `build_policy_intent_envelope(...)` creates a dict with schema, identity, policy problem/outcome/intervention/jurisdiction/population/time fields, requester preference, authority level, lists, authoring provenance, and generated time, then immediately calls `validate_policy_intent_envelope(...)` (`policy-engine/src/polisyos/runtime/quality/assurance_case.py:311-359`).
- `validate_policy_intent_envelope(...)` requires schema version, required text fields, valid authority mapping, non-empty authoring provenance, and adds `requester_preference`, `analysis_independence`, requester capture risk, and challenge-depth policy (`policy-engine/src/polisyos/runtime/quality/assurance_case.py:362-425`).
- `build_policy_design_case_profile(...)` validates intent if present and starts building a runtime-quality assurance profile from runtime authority and related nodes (`policy-engine/src/polisyos/runtime/quality/assurance_case.py:428-455`; full body not read in Pass 1).

What calls it:

- `nl_pipeline.py` imports and calls these builders inside `_execute_nl_pipeline` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:1212-1220`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3148-3195`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3513-3532`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Verdict for the bodies read: `REAL` validation/normalization for runtime intent capture, with fixed capability vocabulary. It is not candidate generation and not a search loop.
- Missing capability label for generation-cycle use: `bridge_missing` until a later pass proves this intent envelope is consumed by a candidate generator rather than only persisted/profiled.

Disposition hint:

- `USE_AS_IS` for intent capture and authority-aware runtime profile input; `REWORK_TO_FIT` if later GY tasks need this to become the canonical NL -> generation-cycle bridge.

Open questions:

- Read full `build_policy_design_case_profile` and capability ledger functions if GY-N1/N2 need to reuse the runtime PDC profile as a control artifact.

### `scientist/agent/protocols.py`, `scientist/agent/pi.py`, `scientist/agent/data_need_extractor.py`

Status: done for Pass 1 NL typing bodies.

What they do:

- `ProblemFrame` is a frozen dataclass with `frame_id`, `domain`, `problem_statement`, actors/goals/constraints/success criteria/assumptions/context/created_at (`policy-engine/src/polisyos/scientist/agent/protocols.py:74-97`). It is the Scientist agent-circuit typed problem object seen in the NL pipeline; it is not named `DesignProblem`.
- `DataNeedSpec` is a frozen dataclass with metric/geography/time/granularity/quality/purpose (`policy-engine/src/polisyos/scientist/agent/protocols.py:119-130`).
- `MockPIAgent.create_problem_frame(...)` rejects empty requests, derives a deterministic `frame_id`, classifies domain via keyword checks, emits fixed constraints, fixed success criteria, fixed assumptions, and actor sets keyed by domain (`policy-engine/src/polisyos/scientist/agent/pi.py:82-133`).
- `LLMPIAgent.create_problem_frame(...)` calls an LLM with `response_format={"type": "json_object"}`, constructs a `ProblemFrame` from JSON, but on JSON/key failure falls back to a minimal `ProblemFrame` using the raw request as statement/goal (`policy-engine/src/polisyos/scientist/agent/pi.py:205-249`).
- `MockDataNeedExtractorAgent.extract_data_needs(...)` concatenates problem statement/goals/constraints, extracts years with regex, maps simple geography keywords to `UKR`/`EU*`/`USA`, maps a short keyword list to metrics, and defaults to `us.macro.gdp_nominal` if no metric keyword is found (`policy-engine/src/polisyos/scientist/agent/data_need_extractor.py:34-92`).
- `LLMDataNeedExtractorAgent.extract_data_needs(...)` asks an LLM for JSON data needs, validates rows into `DataNeedSpec`, optionally boosts quality for dataset-catalog hits, and falls back to the mock extractor on parse/no-usable-needs when fallback is allowed (`policy-engine/src/polisyos/scientist/agent/data_need_extractor.py:95-171`, catalog enrichment `policy-engine/src/polisyos/scientist/agent/data_need_extractor.py:173-206`).

What calls them:

- `nl_pipeline.py` constructs mock or LLM versions depending on gateway client availability (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4266-4288`) and calls `create_problem_frame` / `extract_data_needs` during `_run_variant` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:4448-4482`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `ProblemFrame` / `DataNeedSpec`: `REAL` in the agent circuit as typed contracts, but only `contract/artifact-ish` dataclasses unless persisted through later artifacts.
- `MockPIAgent`: `HARDCODED` but input-sensitive; keyword domain classification and fixed constraints/success criteria/assumptions prove it is not a real policy-design problem formulation (`policy-engine/src/polisyos/scientist/agent/pi.py:93-132`).
- `LLMPIAgent`: `REAL LLM candidate` for problem framing, but per P15 it is candidate content, not authority; fallback is minimal/hardcoded (`policy-engine/src/polisyos/scientist/agent/pi.py:220-249`).
- `MockDataNeedExtractorAgent`: `HARDCODED` keyword extractor with a default GDP metric (`policy-engine/src/polisyos/scientist/agent/data_need_extractor.py:37-44`, `policy-engine/src/polisyos/scientist/agent/data_need_extractor.py:67-72`).
- `LLMDataNeedExtractorAgent`: `REAL LLM candidate` plus optional catalog enrichment, but fallback-to-mock keeps the path non-authoritative unless strict fallback is disabled.

Disposition hint:

- `REWORK_TO_FIT`: keep the typed `ProblemFrame` contract if the generation cycle needs the existing agent circuit, but do not treat mock problem/data-need outputs as evidence. For GY, a canonical bridge is needed between runtime `PolicyIntentEnvelope`, Scientist `ProblemFrame`, and any eventual `DesignProblem`/candidate contract.

Open questions:

- Does the Scientist policy-design DAG define a separate `DesignProblem` or `PolicyDesignRequest` and can it be reached from this front door?
- Are `ProblemFrame` dataclasses persisted anywhere as first-class artifacts, or only embedded indirectly in Trinity/final claims reports?

### `scientist/orchestration/workflows/policy_design.py`

Status: done.

What it does:

- Defines `policy_design_workflow_spec()` returning a `WorkflowSpec` with `workflow_id="scientist_policy_design"` and `error_policy="continue"` (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:13-27`).
- Requires state binds `run_id` and `inputs.registry_bundle_ref` (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:28-31`).
- Declares a fixed DAG: start -> plan request, data snapshot/literature/causal/execution/preflight branches, legal source pack expansion/verification, draft options, formalize verified policy, data-plane/foundry/cross-graph/causal readiness/search/simulation/evaluation/governance/report/blueprint/translation/output/decision packet (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:32-270`).
- The generation-related aliases are `plan_policy_request` (`node_plan_policy_request`), `draft_policy_options`, `formalize_verified_policy`, and `run_hierarchical_policy_search` (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:34-38`, `policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:89-118`).

What it calls:

- No function calls except constructing `WorkflowSpec` / `NodeInvocation`. Actual work is delegated to node registry resolution by `WorkflowExecutor`.

What calls it:

- `run_policy_design_workflow()` builds this spec and passes it to `WorkflowExecutor.execute(...)` (`policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py:712-721`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Verdict: `REAL` DAG declaration, `HARDCODED` topology, no computation by itself. It is live when selected by `run_experiment` / builder. Candidate-generation claims in its docstring are not evidence; the body only names nodes.

Disposition hint:

- `USE_AS_IS` as a registry-visible DAG skeleton; generation-cycle work should modify/reuse the node owners, not this spec alone.

Open questions:

- The workflow has `error_policy="continue"`; later pass should inspect `WorkflowExecutor` behavior to see how skipped/failed generation nodes affect downstream authority.

### `scientist/api.py`, `workflows/selection.py`, `workflows/builder.py`

Status: done for run-selection bodies.

What they do:

- `scientist.api.run_experiment(...)` validates top-level `ExperimentState` keys, prepares initial state, imports workflow builder functions, resolves workflow id, and runs `run_selected_workflow(...)` under observability metrics/spans (`policy-engine/src/polisyos/scientist/api.py:212-328`).
- Workflow selection returns `scientist_policy_design` if `params.workflow_id` is explicit (`policy-engine/src/polisyos/scientist/orchestration/workflows/selection.py:42-48`) or if `_should_use_policy_design(...)` sees `execution_profile == "policy_design"` or truthy `params.policy_mode` (`policy-engine/src/polisyos/scientist/orchestration/workflows/selection.py:85-97`).
- `_should_use_policy_verified(...)` is separate: policy question/request/problem/research question without Trinity can route to `scientist_policy_verified`, not `scientist_policy_design`, unless policy-design flags are present (`policy-engine/src/polisyos/scientist/orchestration/workflows/selection.py:64-82`).
- `run_selected_workflow(...)` dispatches to `run_policy_design_workflow(...)` when resolved id is `scientist_policy_design`; otherwise dispatches discovery / policy verified / causal full / default (`policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py:510-632`).
- `run_policy_design_workflow(...)` prepares state with `workflow_id="scientist_policy_design"`, sets `params.policy_mode=True`, defaults execution profile to `policy_design`, pins registry/graph prior refs, ensures snapshot binding, attaches foundry obligations if required, creates default Foundry/Fabric ports where needed, acquires run lock, builds execution context, builds builtin node registry, creates a CAS checkpoint hook, executes the policy-design workflow, then attaches a foundry method report if required (`policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py:635-724`).

What calls them:

- `nl_pipeline.py` calls `run_experiment(state_payload, store=self._artifact_store)` after model variant selection (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6576-6597`).
- `run_experiment` calls builder selection (`policy-engine/src/polisyos/scientist/api.py:275-306`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Verdict: `REAL` live routing/execution path. Important fork: raw policy request params alone can select `scientist_policy_verified`; `scientist_policy_design` requires `execution_profile=policy_design`, explicit `workflow_id`, or `policy_mode`.
- `builder.py` is `REAL` orchestration, but selection semantics mean the NL pipeline only reaches `scientist_policy_design` if its `state_payload` has policy-design profile/flag. In the NL pipeline body read, `state_payload["execution_profile"]` is the runtime execution profile, and params include flags but not an explicit `workflow_id` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:6394-6525`). Whether runtime `execution_profile` equals `policy_design` is caller-dependent and still open.

Disposition hint:

- `USE_AS_IS` for workflow dispatch. For GY, make the desired world explicit: if B-on-A generation cycle means `scientist_policy_design`, state must set the selector fields deliberately.

Open questions:

- Probe `resolve_workflow_id` with representative NL pipeline `state_payload` profiles: `research`, `governed`, `production`, `policy_design`, plus `policy_mode`.

### `workflows/engine_simple.py` and `workflows/engine_langgraph.py`

Status: done.

What they do:

- `SimpleLoopEngine` executes an ordered list of pure callables until a terminal node name or `state["pruned"]` (`policy-engine/src/polisyos/scientist/orchestration/workflows/engine_simple.py:11-38`). It also supports a stateful `step(...)` over the same list (`policy-engine/src/polisyos/scientist/orchestration/workflows/engine_simple.py:40-54`).
- `LangGraphEngine` wraps an externally supplied compiled LangGraph object and invokes/streams it (`policy-engine/src/polisyos/scientist/orchestration/workflows/engine_langgraph.py:12-57`). Its `from_existing_workflow()` classmethod rejects the removed legacy builder path (`policy-engine/src/polisyos/scientist/orchestration/workflows/engine_langgraph.py:73-78`), and `LangGraphEngineFactory.create()` raises unless a build callback is supplied (`policy-engine/src/polisyos/scientist/orchestration/workflows/engine_langgraph.py:81-93`).

What calls them:

- Not traced as live in Pass 1. The live policy-design workflow uses `WorkflowExecutor` in `builder.py`, not either of these wrappers (`policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py:719-721`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `SimpleLoopEngine`: `REAL` small sequential runner for tests/prototypes, but not observed as the live Scientist policy-design engine. It can run loops only in the sense of ordered callables; no built-in revisit/cycle semantics.
- `LangGraphEngine`: `SHADOW/LEGACY`. It can invoke a supplied compiled graph, but the legacy builder path is explicitly removed. Without a supplied `build_func`, factory creation raises.

Disposition hint:

- `DELETE` or keep as compatibility only for `LangGraphEngine` if no callers need it. `SimpleLoopEngine` is `USE_AS_IS` for tests/prototypes, not for GY runtime authority.

Open questions:

- Search callers for `SimpleLoopEngine` and `LangGraphEngineFactory` in a later pass to decide whether either is dead.

### Policy-Design Node Chain: Plan, Legal Candidate Pack, Draft Options, Formalize

Status: done.

What it does:

- `PlanPolicyRequestNode.execute(...)` is the Scientist `node_plan_policy_request`: if a policy request frame ref already exists, it returns unchanged; otherwise it calls `build_policy_request_frame(ctx, state)`, persists the frame, writes `state.policy_request_ref`, indexes the artifact, sets default `params.policy_answer_mode="verified_async"`, and defaults execution profile to `policy_verified_async` (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py:65-97`).
- `build_policy_request_frame(...)` builds `PolicyRequestFrame` from state params or research intent. It falls back to `"Design a policy option set grounded in applicable legal sources."` if no request exists, and defaults jurisdiction to `"UA"` (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:78-131`).
- `AssembleLegalCandidatePackNode.execute(...)` loads the request frame, calls `assemble_legal_candidate_pack(...)`, and persists the pack with request/profile input refs (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/assemble_legal_candidate_pack.py:64-113`).
- `assemble_legal_candidate_pack(...)` builds a legal toolkit from configured legal DB; if unavailable, it returns a `LegalCandidatePack` with the policy question as the only query, no hits, source status, and a `legal_graph_unavailable` note (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:134-148`). If available, it runs planned recall queries through the toolkit, dedupes fact/provision hits, and records hit reasons/source family/anchor hints (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:149-183`).
- `_build_legal_toolkit(...)` requires a configured legal DB path and an existing file; otherwise returns `None` (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:646-663`).
- `_plan_recall_queries(...)` derives queries from policy question/goals/constraints/domain and appends four Ukrainian legal phrase templates (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:744-769`).
- `DraftPolicyOptionsNode.execute(...)` loads policy request and source verification report, then calls `draft_policy_option_set(...)` and persists the option set (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/draft_policy_options.py:67-113`).
- `draft_policy_option_set(...)` always creates one verified option with `option_id="verified_option_1"`, title `"Verified policy option"`, summary equal to `frame.policy_question`, legal refs from claim citation labels, evidence links to the first 20 verified claims, and extracted constraints/thresholds/timing. It optionally creates one hypothesis option with `option_id="hypothesis_option_1"` when unresolved critical gaps exist and `allow_hypotheses` is true (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:457-515`).
- `FormalizeVerifiedPolicyNode.execute(...)` skips if Trinity input already exists; otherwise loads request/option set and calls `formalize_policy_option_set(...)`, then writes `inputs.trinity_bundle_ref` and `params.policy_trinity_generated=True` (`policy-engine/src/polisyos/scientist/nodes/builtins/compile/formalize_verified_policy.py:63-93`).
- `formalize_policy_option_set(...)` takes the first verified or hypothesis option, constructs a `DraftResult` with one intervention using fixed `mechanism_type="tax_subsidy"`, `target_population="all"`, and `parameters={"rate": "0.1"}`, then calls `asyncio.run(MockFormalizerAgent().formalize(draft))` and persists a Trinity bundle (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:518-558`).
- `MockFormalizerAgent.formalize(...)` delegates to `_build_trinity_bundle_from_draft(...)` (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1426-1444`). That builder hardcodes primary objective `metric_id="avg_income"`, `data_snapshot_ref=ZERO_ARTIFACT_REF`, `AgentConfig(total_agents=1000, max_agents=1000)`, and `EnvironmentConfig(random_seed=42, stochastic=True)` (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1357-1414`). Intervention conversion defaults to `tax_subsidy`, target `id == all`, schedule `{start_step: 0, duration_steps: 12}`, and params `{"rate": "0.1"}` when not supplied (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1277-1355`, defaults at `policy-engine/src/polisyos/scientist/agent/formalizer.py:816-826`).

What calls it:

- The policy-design workflow spec wires these nodes in order: plan -> legal pack -> source expansion/verification/gap review -> draft options -> formalize (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:34-98`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `PlanPolicyRequestNode`: `REAL` persistence of a typed request frame, but not candidate generation.
- `assemble_legal_candidate_pack`: `REAL` legal retrieval when a legal DB exists; otherwise `STUB/blocked record` with no candidates.
- `draft_policy_option_set`: `HARDCODED` policy option generation: one verified option, one optional hypothesis option, fixed IDs and titles, no combinatorial generation.
- `formalize_policy_option_set`: `HARDCODED` Trinity generation from option text: fixed mechanism, target, parameter, objective metric, zero data ref, agent config, seed.

Disposition hint:

- `REWORK_TO_FIT`: keep the request-frame and legal-source retrieval surfaces, but do not present the verified-policy option/formalization path as a real generator. It is useful as a skeleton and legal grounding bridge.

Open questions:

- Read source expansion/verification/gap recovery nodes fully if GY later wants A-side legal grounding reuse.
- Confirm with a probe that a minimal request with no legal DB yields no legal hits and still drafts/forms a single tax-subsidy option after a fabricated verification report.

### `RunHierarchicalPolicySearchNode`, `lex.interventions.HierarchicalPolicySearchAdapter`, and `scientist/policy_design/search.py`

Status: done for first-pass search path.

What it does:

- `RunHierarchicalPolicySearchNode.execute(...)` resolves a starting `PolicyCandidateSchema` from `params.policy_candidate_schema`, `params.lex_policy_bundle_input`, or `inputs.trinity_bundle_ref`; if none exists, it skips (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:181-200`, resolver `policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:293-323`).
- It fences legacy inferred bounds: runtime search config cannot set `require_explicit_parameter_bounds=False` or `allow_legacy_shadow_inferred_bounds=True` (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:267-290`).
- It calls `HierarchicalPolicySearchAdapter.run_search(...)` with a Stage-B evaluator that runs a compile/readiness/simulation/evaluation subpipeline for each candidate payload (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:202-218`).
- Stage-B evaluator persists a candidate Trinity bundle, clears candidate artifact keys, executes `CompileFoundryNode`, `CompileCrossGraphEvidenceNode`, `ResolveParametersNode`, `RunCausalReadinessNode`, `evaluate_counterfactual_gate`, `RunSimulationNode`, then builds `build_policy_runtime_evaluation(...)` with `ProductionPolicyEvaluationBackend` plus loaded uncertainty/distributional/causal/cross-graph/governance/ambiguity reports (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:325-450`).
- Champion selection ranks evaluated candidate records by feasible flag, policy value, welfare+employment, and negative blocker count; if no records, falls back to accepted structure candidate or original candidate (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:488-576`).
- It persists the champion Trinity bundle and a policy frontier report when records exist (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:226-264`, persistence `policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:628-702`).
- `LexPolicyBundleInput` is the bridge contract for Lex-compiled interventions into Scientist/Foundry; it wraps a Trinity bundle plus compiled interventions, temporal sequences, strategic response bundle, and metadata (`policy-engine/src/polisyos/lex/intervention_artifacts.py:88-118`).
- `HierarchicalPolicySearchAdapter.build_candidate(...)` wraps a Trinity/Lex bundle into `PolicyCandidateSchema`, deriving metadata including fixed `jurisdiction="UA"` and `country="ua"`, domain, dynamic/strategic/compiled intervention ids, and sequence ids (`policy-engine/src/polisyos/lex/interventions.py:812-866`).
- `PolicyCandidateSchema.from_trinity_bundle(...)` derives rollout steps from policy interventions, parameter schedule entries from policy parameters, evidence assumptions from model assumptions, and a default target population description; it does not invent new policy mechanisms (`policy-engine/src/polisyos/scientist/policy_design/schema.py:293-339`).
- `HierarchicalSearchCoordinator.generate_structure_candidates(...)` seeds structure candidates from the base candidate, fallback variants, transfer seeds, rollout reversal, and hybrid seeds, then applies a constraint critic and optional structure validator (`policy-engine/src/polisyos/scientist/policy_design/search.py:241-310`).
- Hybrid seeds are deterministic transformations: add a monitoring signal for an untracked objective/KPI metric, add a transport assumption, or promote a model assumption into a policy evidence assumption. The code checks gateway availability only to set source metadata; the read body does not call an LLM to create seeds (`policy-engine/src/polisyos/scientist/policy_design/search.py:738-787`, seed builders `policy-engine/src/polisyos/scientist/policy_design/search.py:789-878`).
- Parameter search requires explicit finite lower/upper bounds by default (`HierarchicalSearchConfig.require_explicit_parameter_bounds=True`, `policy-engine/src/polisyos/scientist/policy_design/search.py:63-78`). `build_parameter_search_spec(...)` calls `derive_phase2_parameter_bounds(...)` and raises if bounds are missing/invalid (`policy-engine/src/polisyos/scientist/policy_design/search.py:312-430`).
- `derive_phase2_parameter_bounds(...)` is fail-closed: missing lower or upper creates a `Phase2BoundsBlocker` with reason `"Lex search bounds are missing or invalid; no default zero may be used."` and frontier provenance `"frontier_only_not_producer_evidence"` (`policy-engine/src/polisyos/scientist/policy_design/search.py:1228-1308`).
- When parameter search runs, `_run_blueprint_parameter_search(...)` uses a `StrategyAdapter` over `MOBayesianOptimizer`; each iteration generates a candidate, calls Stage A (default always-pass if none supplied), calls Stage B, records `SearchIteration`, tracks best candidate/rank, and stops at max iterations or stopping policy (`policy-engine/src/polisyos/scientist/policy_design/search.py:464-564`, loop helper `policy-engine/src/polisyos/scientist/policy_design/search.py:925-1040`, default Stage A `policy-engine/src/polisyos/scientist/policy_design/search.py:1150-1152`).
- If no tunable parameters exist, the adapter runs a parameterless path: coordinator structure search, then exactly one Stage-B evaluation per accepted structure, with a `SearchResult` marked `SearchStatus.CONVERGED`, `iterations_completed=1`, `stopping_reason="parameter_search_not_required"`, and `telemetry={"parameterless_candidate": True}` (`policy-engine/src/polisyos/lex/interventions.py:1023-1036`, `policy-engine/src/polisyos/lex/interventions.py:1072-1151`).

What calls it:

- The policy-design workflow calls `RunHierarchicalPolicySearchNode` after formalized policy, data-plane gate, preflight, and causal graph reconciliation (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:109-118`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `RunHierarchicalPolicySearchNode`: `REAL` orchestration bridge for search and candidate evaluation when a candidate exists.
- `HierarchicalSearchCoordinator`: `REAL` search loop when explicit tunable bounds exist; `REAL but bounded/single-evaluation` parameterless path when no tunable params exist; `FAIL-CLOSED` when tunable params lack explicit bounds.
- Candidate generation is `REWORK_TO_FIT`: it mutates/wraps a starting candidate and adds deterministic surface assumptions; it does not synthesize a novel policy family from NL. With the verified-policy formalizer upstream, the starting candidate is heavily hardcoded.
- Frontier report is `REAL` persisted surface from records, but its own metadata marks source as search frontier, not producer evidence (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:695-700`; bounds gate also marks frontier authority as non-producer evidence at `policy-engine/src/polisyos/scientist/policy_design/search.py:1298-1306`).

Disposition hint:

- `USE_AS_IS` for the search coordinator and fail-closed bounds gate; `REWORK_TO_FIT` for candidate source/generation. The likely GY move is to feed this coordinator real B candidates and real Stage-B value/grounding, not to rewrite the optimizer.

Open questions:

- Run a minimal probe to show default mock-formalized candidates fail closed on missing explicit bounds, and a parameterless candidate path does one Stage-B evaluation.
- Read `CompileFoundryNode`, `RunSimulationNode`, and `build_policy_runtime_evaluation` to determine whether Stage B value is actually computed or falls back/hardcodes in typical GY state.

Probe evidence:

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
RAISED ValueError: Lex search bounds are missing or invalid; no default zero may be used.
  File ".../src/polisyos/lex/interventions.py", line 1024, in run_search
    coordinator.build_parameter_search_spec(resolved_candidate)
  File ".../src/polisyos/scientist/policy_design/search.py", line 347, in build_parameter_search_spec
    raise ValueError(phase2_bounds.blocker.reason)
ValueError: Lex search bounds are missing or invalid; no default zero may be used.
```

The probe built a candidate via `MockFormalizerAgent().formalize(...)` and `PolicyCandidateSchema.from_trinity_bundle(...)`, then called `HierarchicalPolicySearchAdapter.run_search(...)` with a trivial Stage-B evaluator. The evaluator was never reached because the default mock-formalized candidate carries a tunable parameter without explicit Lex bounds, and the adapter raises at `lex/interventions.py:1024` through `scientist/policy_design/search.py:347`. This confirms the fail-closed bounds gate is real on the default verified-policy/formalizer output.

Revision impact:

- Earlier open question "run a minimal probe..." is partly closed: the default mock-formalized path fails closed before search evaluation. A second probe with an explicitly non-tunable or bounded candidate is still needed to demonstrate the parameterless/success path.

### Probe Addendum: Mock NL Typing and Workflow Selection

Status: done for Pass 1 probes.

Mock PI/data-need probe:

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
{
  "frame": {
    "actors": [
      "government",
      "citizens",
      "businesses"
    ],
    "assumptions": [
      "Current economic conditions remain stable",
      "No major external shocks occur"
    ],
    "constraints": [
      "Budget deficit must not exceed 3%",
      "Policy must be politically feasible"
    ],
    "context": {
      "original_request": "Ukraine income subsidy for unemployed workers in 2024",
      "source": "mock_pi"
    },
    "created_at": "2026-06-24 11:58:23.565220+00:00",
    "domain": "economic",
    "frame_id": "pf_0ce286949e1090e5",
    "goals": [
      "Address: Ukraine income subsidy for unemployed workers in 2024"
    ],
    "problem_statement": "Ukraine income subsidy for unemployed workers in 2024",
    "success_criteria": {
      "primary_metric": "improvement_rate",
      "threshold": 0.1,
      "timeframe_months": 12
    }
  },
  "needs": [
    {
      "geography": "UKR",
      "granularity": "annual",
      "metric": "agent.income.salary",
      "purpose": "policy_drafting",
      "quality_min": 0.6,
      "time_end": "2024",
      "time_start": "2024"
    }
  ]
}
```

Evidence interpretation:

- This confirms the code reading in `scientist/agent/pi.py:82-133` and `scientist/agent/data_need_extractor.py:34-92`: the mock path is input-sensitive, but it is still a template/keyword path. The request text influenced domain (`economic`), geography (`UKR`), year (`2024`), and metric (`agent.income.salary`), while actors, constraints, assumptions, success criteria, and goal phrasing came from fixed templates.
- Verdict remains `HARDCODED` for mock NL interpretation, with enough input sensitivity that it is not a pure constant stub.

Workflow selector probe:

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
default_empty: scientist_default
explicit_policy_design: scientist_policy_design
policy_design_profile: scientist_policy_design
policy_mode_true: scientist_policy_design
plain_policy_request_ref_input: scientist_default
top_level_policy_request_ref: scientist_default
trinity_ref_only: scientist_default
```

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
policy_question_param: scientist_policy_verified
policy_request_param: scientist_policy_verified
problem_statement_param: scientist_policy_verified
verified_async_answer_mode: scientist_policy_verified
policy_verified_async_profile: scientist_policy_verified
```

Evidence interpretation:

- The probe confirms `selection.py:42-61`, `selection.py:64-82`, and `selection.py:85-97`: `scientist_policy_design` is selected only by explicit workflow id, `execution_profile="policy_design"`, or truthy `policy_mode`. Plain artifact refs named policy/trinity refs do not select it. Plain policy text params select `scientist_policy_verified`.
- The strict `ExperimentState`/`ArtifactRef` contract also surfaced during probing: `ExperimentState.inputs` only accepts `ArtifactRef` values (`scientist/orchestration/engine/state.py:49-55`), `ArtifactRef` forbids extras and requires `artifact_id`, `kind`, and `media_type` (`core/artifacts/manifest.py:199-205`), and `artifact_id` must start with `sha256:` (probe validation failure before the successful selector run).

Revision impact:

- Was: "raw policy request params alone can select `scientist_policy_verified`; artifact refs still open." Now: policy/question/request/problem params select `scientist_policy_verified`, but `policy_request_ref`/`trinity_bundle_ref` artifact refs alone select `scientist_default` in the probed shape. The B-on-A cycle must set selector params deliberately.

### Runtime Dependency Risk: Foundry Causal/Optimization on Python 3.14

Status: in progress. This is not a full causal/optimization catalog census; it is the requested import-risk and fallback check.

Probe:

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
python 3.14.0
econml: IMPORT_ERROR ModuleNotFoundError: No module named 'econml'
dowhy: IMPORT_ERROR ModuleNotFoundError: No module named 'dowhy'
cvxpy: IMPORT_ERROR ModuleNotFoundError: No module named 'cvxpy'
statsmodels: OK version=0.14.6
jax: OK version=0.9.1
pymoo: OK version=0.6.1.6
scipy: OK version=1.16.3
```

What the code does:

- DoWhy methods are optional in the causal registry and require both `dowhy` and `cvxpy`: `_registry_boot.py:413-425` wraps `dowhy_identify_estimate` and `dowhy_refute` in `_optional_method_types(... optional_deps=("dowhy", "cvxpy"))`.
- EconML-backed CATE/DML/meta/policy-learning methods are imported in one try block; if the missing module is `econml` or `shap`, registration is silently skipped (`foundry/methods/catalog/causal/_registry_boot.py:441-457`).
- `_econml_adapter.py` stores import failure in `ECONML_IMPORT_ERROR`, leaves `ECONML_AVAILABLE=False`, and `require_econml()` raises an ImportError telling the caller to install optional causal deps (`foundry/methods/catalog/causal/_econml_adapter.py:13-22`, `foundry/methods/catalog/causal/_econml_adapter.py:41-47`).
- `ci_backends.resolve_discovery_ci_backend(...)` supports `auto`, `numpy`, and `jax`. With JAX importable, generic auto returns `used="jax"` (`foundry/methods/catalog/causal/ci_backends.py:59-91`).
- The constraint-discovery wrapper is more conservative: `_resolve_constraint_ci_backend(...)` converts auto-selected JAX back to NumPy with fallback reason `auto_defaults_numpy_for_stability`; explicit `discovery_ci_backend="jax"` is needed to run the JAX path (`foundry/methods/catalog/causal/constraint_discovery.py:2460-2475`). The JAX path itself computes deterministic partial-correlation adjacency by looping variable pairs and calling `partial_corr(..., backend="jax")` (`foundry/methods/catalog/causal/constraint_discovery.py:2774-2845`), and `run_constraint_discovery` calls it only when `ci_backend.used == "jax"` (`foundry/methods/catalog/causal/constraint_discovery.py:2971-3026`).
- `parameter_transfer._resolve_runtime_backend(...)` prefers numpyro if present, otherwise JAX if importable, otherwise NumPy; on this runtime it should choose JAX for auto with reason `auto_selected_jax:numpyro_unavailable` unless numpyro is installed (`foundry/methods/catalog/causal/parameter_transfer.py:223-241`). Numpyro import was not probed in Pass 1.
- `ParallelTrendsCheck` has `runtime_stack=("statsmodels", "numpy")` and imports `statsmodels.api` inside `pure_step(...)` (`foundry/methods/catalog/causal/diagnostics.py:43-48`, `foundry/methods/catalog/causal/diagnostics.py:100-103`). Since statsmodels imports on Python 3.14, this diagnostic path is runnable at dependency level.
- `MultiObjectiveNSGA2Estimator` has `runtime_stack=("pymoo", "numpy")` and imports `pymoo` inside `pure_step(...)` (`foundry/methods/catalog/optimization/multiobjective.py:45-49`, `foundry/methods/catalog/optimization/multiobjective.py:110-115`). Since pymoo imports on Python 3.14, this optimization path is runnable at dependency level.
- `QuadraticProgramEstimator.pure_step(...)` tries `import cvxpy as cp`, but if CVXPY is missing it falls back to `_solve_with_scipy(...)` (`foundry/methods/catalog/optimization/convex.py:343-375`). The SciPy fallback returns an explicit error only if SciPy is also missing (`foundry/methods/catalog/optimization/convex.py:425-461`); SciPy imports on this runtime.
- Some robust convex estimators do not have that fallback: `RobustLinearProgramEstimator.pure_step(...)` imports CVXPY directly (`foundry/methods/catalog/optimization/convex.py:614-619`), and `SetBasedRobustLinearEstimator.pure_step(...)` also imports CVXPY directly (`foundry/methods/catalog/optimization/convex.py:784-789`). With CVXPY unavailable, these raise at import time if called.

What calls it:

- Not fully traced in Pass 1. The likely Stage-B bridge is `RunHierarchicalPolicySearchNode._evaluate_candidate_payload(...)`, which calls `CompileFoundryNode`, `ResolveParametersNode`, `RunCausalReadinessNode`, `RunSimulationNode`, and `build_policy_runtime_evaluation(...)` before producing candidate value (`scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:325-450`). Those bodies still need to be read before declaring reachability from GY.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Dependency verdict on Python 3.14: EconML, DoWhy, and CVXPY paths are `unavailable` in the active runtime; statsmodels, JAX, pymoo, and SciPy paths are available.
- Causal fallback verdict: `REAL` JAX/NumPy fallback exists for discovery CI, but some owners intentionally default auto to NumPy for stability. Statsmodels diagnostics are dependency-real.
- Optimization fallback verdict: `REAL` pymoo multiobjective path and SciPy-backed quadratic fallback are available; CVXPY-only robust convex methods are `implemented_but_runtime_blocked` on this interpreter until optional deps are installed.

Disposition hint:

- `USE_AS_IS` for registry-level optional dependency gating and explicit JAX/NumPy metadata. `REWORK_TO_FIT` for any GY value path that assumes DoWhy/EconML/CVXPY availability. The GY value path must either select dependency-available methods or surface blockers instead of silently implying those methods ran.

Open questions:

- Read `CompileFoundryNode` and `RunCausalReadinessNode` to see whether unavailable methods are filtered before execution or only fail at method call time.
- Read `outcome_prediction.py` calibration gate and `build_policy_runtime_evaluation(...)` before calling value computation real for the generation cycle.

### `runtime/quality/workspace/loop.py`: Honest Backbone Loop

Status: done for Pass 2 loop bodies.

What it does:

- Defines the active Slice-0 operation set as exactly `{BIND, ESTIMATE, VERIFY}` and the fixed `WORKSPACE_TRAJECTORY = (BIND, ESTIMATE, VERIFY)` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:110-113`).
- `OperationRegistry.active_operation_classes()` returns only executable registrations whose class is in that active set (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:242-255`). The registry still contains ACQUIRE/REFINE/LOWER/DISCOVER and recursive DECOMPOSE/COMPOSE entries, but only BIND/ESTIMATE/VERIFY are admitted to the seed path (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:714-834`).
- `build_workspace_operation_registry()` registers:
  - executable BIND from Data Forge catalog graph (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:717-729`);
  - executable ESTIMATE from a measurement-summary adapter with Foundry registry discovery evidence (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:730-741`, discovery at `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:491-514`);
  - executable VERIFY from PDC authority-derivation contracts (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:742-753`, discovery at `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:515-536`);
  - non-executable ACQUIRE with a fail-closed reason saying it may attach a costed terminal plan but cannot execute inside Slice-0 (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:767-782`);
  - non-executable REFINE/LOWER/DISCOVER stubs and executable but non-active DECOMPOSE/COMPOSE for recursive cases (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:754-833`).
- `select_search_terminal(...)` implements deterministic anytime-exit precedence: spec/verifier gap, tool failure, composition invalid, recursive blocked, search ceiling repair, human decision, acquisition required, budget exhausted, frontier stable, else positive terminal (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:407-459`).
- `WorkspaceLoop.run_fixture(...)` is a committed fixture harness, not a free loop: it rejects any planner other than `"seed_trajectory"`, rejects any operation outside active operations, then rejects any trajectory not exactly BIND -> ESTIMATE -> VERIFY (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1471-1497`).
- `run_fixture(...)` loads the manifest, builds a workspace contract, semantic benchmark run, optional acquisition plan, incompleteness record, terminal decision, artifact envelopes, authority boundary if terminal is `grounded_partial_admissible`, frontier snapshot, ledger, obligations, VOI audit, and budget ledger, then returns a `WorkspaceSearchExitContract` with `cycle_index=3` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1499-1664`).
- The returned `cycle_index=3` is not an iteration count from a dynamic revising loop. The ledger records individual invocations with indices `0`, `1`, `2`, and the contract/frontier use `cycle_index=3` to reflect the fixed BIND/ESTIMATE/VERIFY trajectory length (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1584-1600`, `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1646-1650`, ledger at `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2676-2728`).
- `_build_artifacts(...)` produces a `BaseDataset` envelope and an `Estimate` envelope. If a groundable fixture has expected catalog refs and terminal admits measurement, it calls `MeasurementRootProducer.produce_from_catalog(...)`; otherwise it builds a shadow/missing-acquisition payload. The estimate payload is a measurement summary over rows, not a design candidate (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1910-2020`; summary helper at `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:670-700`).
- `_assert_workspace_artifact_cut_lines(...)` explicitly forbids Slice-0 from emitting `grounded_admissible` or any `DesignCandidate` artifact (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1798-1815`).
- `_authority_boundary(...)` initially requests measurement-backed decision authority, then immediately downgrades via `with_partial_evidence_downgrade(...)` to `decision_grade_cap="descriptive_only"` and `may_not_use_for` including design candidates, grounded admissible, production decisions, and publication without limitation (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2131-2165`).
- `_authority_derivation_trace(...)` records the declared transform as decision-admissible but computed grade as `descriptive_only`, with unresolved blocker `slice0_estimate_port_only` and `transform_mismatch_disposition="downgraded"` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2167-2196`).
- `_ledger(...)` creates synthetic canonical iterations for each operation with `status="abstained"`, no counterexamples, `no_retry_without_new_grammar=True`, and note `"Slice-0 loop is BIND -> ESTIMATE -> VERIFY; no design candidate promotion."` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2665-2772`).

Acquisition handling:

- `_acquisition_plan_for_manifest(...)` returns `None` when the fixture has expected catalog refs; otherwise it creates a `RequiredDataGap` for the missing distribution and calls `AcquisitionPlanner().plan_from_required_data(...)` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2585-2603`).
- `_decision_inputs(...)` clears `required_source_classes_missing` when an acquisition plan exists and sets `acquisition_required=True`, so terminal selection can choose `ACQUISITION_REQUIRED` unless a higher-precedence search-ceiling/tool/spec/human terminal fires first (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2459-2483`).
- `_obligation_records(...)` emits an open acquisition obligation when the terminal is `ACQUISITION_REQUIRED`, with resolution option pointing to `slice0.acquire.costed_plan` and `slice0_execution="fail_closed"` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1864-1908`).
- `AcquisitionPlanner.plan_from_required_data(...)` computes a costed plan, canonical planner report, DataNeedSpec, `SearchTerminalState`, and VOI audit; it does not execute acquisition or satisfy evidence slots (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:528-755`). The module header explicitly says planner records are governance/closeout inputs and "do not satisfy domain evidence slots" (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:1-7`).

`run_intent(...)` Phase-2 path:

- `run_intent(...)` selects a playbook from intent keys, creates a Phase-2 workspace id, and has a special counterexample branch for `force_counterexample == "missing_bounds"` that runs `LexBoundsApplicabilityGate` and returns `SEARCH_CEILING_REPAIR_REQUIRED` without executing Scientist nodes (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1266-1302`).
- Otherwise it creates an `ExecutionContext`, Phase-2 `ExperimentState`, checks required inputs with `BlockedInputProducer`, then builds a playbook registry over builtin Scientist nodes (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1304-1336`).
- It executes only legacy aliases `run_causal_evaluation` and `run_normative_arbitration`; `plan_policy_request` and all other aliases are recorded as `surface_out_of_scope` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1338-1367`).
- `run_normative_arbitration` first installs synthetic/normative support inputs with fixed problem frame, distributional impacts, metrics, simulation result, and legal report (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1066-1264`). This is a Phase-2 support/replay scaffold, not independent policy generation.
- Each executable playbook step is wrapped by `ScientistNodeAdapter.from_node(...)` with authority transform `{kind: "hint_only", requested_decision_grade: "descriptive_only"}` and executed via `execute_candidate(...)` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1368-1411`; adapter creation at `policy-engine/src/polisyos/runtime/quality/workspace/scientist_node_adapters.py:81-141`).
- After `run_causal_evaluation`, `FoundryMethodOutputConsumer.consume_from_state(...)` requires both `causal_method_result_ref` and `causal_method_evidence_ref` in `state.artifacts_index`, builds a `MethodOutputConsumptionRecord`, stamps an `AuthorityBoundary` with `decision_grade="descriptive_only"`, and `may_not_use_for` design decision, production recommendation, and publication authority (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1412-1429`; consumer at `policy-engine/src/polisyos/runtime/quality/workspace/foundry_consumption.py:57-144`).
- `FoundryMethodOutputConsumer._input_provenance(...)` rejects untyped roots, classifies `"synthetic"`/`gy.synthetic*` refs as `synthetic_probe`, and only measurement-like artifact kinds as `measurement_rooted` (`policy-engine/src/polisyos/runtime/quality/workspace/foundry_consumption.py:280-305`).
- `run_intent(...)` returns `FRONTIER_STABLE` when no blockers appear, with reason `"Phase-2 playbook trajectory reached a stable candidate-only frontier."` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1430-1469`).

Playbook and adapter relationships:

- `select_playbook_for_intent(...)` treats user-supplied `workflow_id` as legacy shadow context only. It chooses `scientist_policy_verified` for policy question or verification, `scientist_causal_full` for causal variables/observational data, else `scientist_policy_design` (`policy-engine/src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:139-162`).
- Phase-2 playbooks project only selected aliases from Scientist workflows: policy design -> build literature prior / run causal evaluation / run normative arbitration; causal full -> build literature prior / reconcile causal graph / run causal evaluation / run normative arbitration; policy verified -> plan request / run causal evaluation / run normative arbitration (`policy-engine/src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:14-38`).
- `_step_from_invocation(...)` maps aliases to operation classes and creates a `ScientistNodeAdapter` with `hint_only` descriptive authority; `PlaybookTrajectory.authority_path_disposition` is always `"loop_only"` (`policy-engine/src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:226-286`, `policy-engine/src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:57-67`).
- `ScientistNodeAdapter.execute_candidate(...)` first checks required state paths, returns a blocker on missing inputs, otherwise calls `node.execute(ctx, state)`, wraps declared outputs in artifact envelopes, and records internal trace `"candidate_only": True` (`policy-engine/src/polisyos/runtime/quality/workspace/scientist_node_adapters.py:208-344`).

Probe evidence:

```text
$ PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" python3 - <<'PY'
...
{
  "active": ["BIND", "ESTIMATE", "VERIFY"],
  "operations": {
    "slice0.acquire.costed_plan": {
      "class": "ACQUIRE",
      "executable": false,
      "fail_closed": "GY-H/GY-E may attach a costed acquisition_required terminal plan, but ACQUIRE cannot execute inside the Slice-0 trajectory."
    },
    "slice0.refine.stub": {
      "class": "REFINE",
      "executable": false,
      "fail_closed": "GY-C2 owns REFINE after spine-rot repair."
    }
  }
}
{
  "fixture": "ua_msme_credit_worldbank_measurement",
  "terminal_kind": "grounded_partial_admissible",
  "cycle_index": 3,
  "authority_grade": "descriptive_only",
  "authority_may_not_use_for": ["design_candidate", "grounded_admissible", "production_decision", "publication_without_limitation"],
  "output_artifact_types": ["BaseDataset", "Estimate"],
  "promoted_types": ["Estimate"],
  "ledger_invocations": [["slice0.bind.catalog", 0, "completed"], ["slice0.estimate.measurement_summary", 1, "completed"], ["slice0.verify.authority", 2, "completed"]],
  "ledger_note": "Slice-0 loop is BIND -> ESTIMATE -> VERIFY; no design candidate promotion."
}
{
  "fixture": "tourism_local_development_ceiling_probe",
  "terminal_kind": "acquisition_required",
  "cycle_index": 3,
  "authority_grade": null,
  "costed_plan_missing_distribution": "local_tourism_site_traffic",
  "output_artifact_types": ["BaseDataset", "Estimate"],
  "promoted_types": [],
  "blocking_obligations": ["obligation-tourism-local-development-ceiling-probe-acquisition"]
}
```

Terminal precedence probe:

```text
spec_gap_over_all a_spec_gap
tool_failure_over_acquire tool_failure
ceiling_over_acquire search_ceiling_repair_required
human_over_acquire human_decision_required
acquire acquisition_required
budget budget_exhausted
stable frontier_stable
positive grounded_partial_admissible
```

`run_intent(...)` probe:

```text
{
  "intent": {"policy_question": "Should Ukraine expand credit guarantees?"},
  "playbook_id": "scientist_policy_verified",
  "executed_operation_classes": ["BIND", "ESTIMATE", "VERIFY"],
  "executed_legacy_aliases": ["run_causal_evaluation", "run_normative_arbitration"],
  "out_of_scope_aliases": ["plan_policy_request"],
  "terminal_kind": "frontier_stable",
  "authority_grade": "descriptive_only",
  "authority_evidence_kind": "measurement",
  "method_output_count": 1,
  "foundry_input_provenance": "measurement_rooted"
}
{
  "intent": {"causal_variables": ["credit_access", "firm_survival"]},
  "playbook_id": "scientist_causal_full",
  "default_operation_classes": ["BIND", "REFINE", "ESTIMATE", "VERIFY"],
  "executed_operation_classes": ["BIND", "ESTIMATE", "VERIFY"],
  "executed_legacy_aliases": ["run_causal_evaluation", "run_normative_arbitration"],
  "out_of_scope_aliases": ["build_literature_prior", "reconcile_causal_graph"],
  "terminal_kind": "frontier_stable",
  "authority_grade": "descriptive_only",
  "method_output_count": 1
}
{
  "intent": {"policy_question": "Bounds probe", "force_counterexample": "missing_bounds"},
  "executed_operation_classes": ["BIND", "ESTIMATE", "REFINE"],
  "blockers": ["Lex search bounds are missing or invalid; no default zero may be used."],
  "terminal_kind": "search_ceiling_repair_required",
  "method_output_count": 0
}
```

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Slice-0 `run_fixture`: `REAL` deterministic proof-packet harness for BIND -> ESTIMATE -> VERIFY, but not a real generation/revision cycle. It is fixture-driven, single-pass, and explicitly forbids design candidates.
- Slice-0 candidate frontier: `SHADOW/fixture frontier`, not a design frontier. It contains BaseDataset/Estimate artifacts, may "promote" an `Estimate`, and explicitly says no design candidate promotion.
- Slice-0 acquisition: `REAL plan-only terminal`, not execute-capable. It computes a costed plan and VOI audit, raises obligations, but ACQUIRE is non-executable in the registry and evidence remains unsatisfied.
- Phase-2 `run_intent`: `REAL adapter bridge` into selected Scientist nodes and Foundry output consumption, but bounded to candidate-only/descriptive authority. It is intent-driven, but still not a cycle controller that generates, evaluates, revises, and promotes a policy design.
- Foundry reachability from loop: `REAL` in Phase-2 through `run_causal_evaluation` node outputs and `FoundryMethodOutputConsumer`, with a descriptive-only authority boundary. Slice-0 ESTIMATE uses a local measurement summary, not Foundry method execution.

Disposition hint:

- `USE_AS_IS` for the honest backbone ledger, terminal precedence, acquisition-required terminal planning, no-design-candidate cut-line, and Foundry consumption authority downgrade.
- `REWORK_TO_FIT` if GY-N3 needs an actual cycle: build a controller on top of these contracts, but do not call `run_fixture` the generator. `run_intent` can supply a candidate-only ESTIMATE/VERIFY adapter path, but it does not own generation or revision.

Open questions:

- Read Stage-B nodes to distinguish the real value produced by `run_causal_evaluation` from the loop's descriptive consumption of it.
- Decide whether the Phase-2 synthetic/normative support artifacts in `_install_phase2_normative_inputs(...)` should stay only as replay scaffolding or be replaced by real candidate evidence in GY-N5/GY-N6.

### `pdc/_impl/layer2_design_search.py`: Layer-2 S2 Shadow Design Search

**What it does from code read**

- The file defines a typed S2 shadow-design artifact family and deterministic producer: `Layer2S2DesignSearchInput` accepts a case, intent/grammar refs, objective/construct refs, required `requested_posture="shadow"`, optional forced counterexample, same-candidate retry flag, and candidate source authority (`deterministic_producer` or `llm_candidate`) (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:246-267`).
- The discipline types are real and useful: `DesignGrammarExpansion` records grammar-derived families/parameter space/constraints (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:632-647`), `DesignCandidateV0` requires a grammar expansion and prevents an `llm_candidate` from being upgraded to A-verified status (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:649-682`), `ConstraintStoreSnapshot` carries hard/governance constraint ids plus typed entries (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:700-711`), `CounterexampleRecord` routes counterexamples to refinement/acquisition/governance/abstention/blocking (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:713-731`), `RefinementDecision` carries VOI, budget refs, stakes band, and optional governance class with validator enforcement for `human_decision` (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:733-761`), and `SearchLedger` records iterations, replay key, coverage, branch states, posture refs, no-retry flag, and incompleteness note (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:781-880`).
- `run_s2_shadow_design_loop(...)` is not a loop controller despite the name. It constructs exactly one boundary, one grammar expansion, one candidate, one constraint store, one counterexample, one refinement decision, one iteration status, one ledger, and one design record, then returns a `Layer2S2DesignSearchRun` whose `candidates`, `counterexamples`, and `refinement_decisions` lists each contain one element (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:933-1103`).
- The grammar expansion is deterministic and hardcoded: `_grammar_expansion(...)` always emits instrument families `credit_guarantee`, `interest_rate_buydown`, and `cash_grant`, parameter spaces for `coverage`, `risk_share`, and `delivery_channel`, and constraints `shadow_only`, `a_side_verification_required`, and `no_acquisition_authority` (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1441-1467`; constants at `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:132-136`).
- The candidate is hardcoded to a credit-guarantee design: `_candidate(...)` always returns candidate id/ref ending in `credit_guarantee`, `instrument_family="credit_guarantee"`, parameterization `{coverage: partial_portfolio, risk_share: first_loss, delivery_channel: bank_intermediated}`, `status="candidate_unverified"`, and source authority copied from input (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1470-1534`).
- The counterexample/refinement route is rule-driven from input flags and injected posture summaries, not produced by external A verification. `_counterexample(...)` defaults to `real_design_blocker`, maps `a_spec_gap` to governance, `substrate_gap` to acquisition, `budget_gap` to abstention, and `force_retry_same_candidate` to blocked (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1614-1650`). `_refinement_decision(...)` maps those classes/postures to `human_decision`, `acquire`, `abstain`, `block_candidate`, `decompose`, `reframe`, or default `refine`; only the default `refine` path receives `next_candidate_ref=.../candidate/refined-001`, but no second candidate is constructed (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1653-1752`).
- `_search_ledger(...)` always creates a single `SearchIteration` and sets `candidate_refs`, `counterexample_refs`, and `refinement_decision_refs` to one item each. It also records `acquisition_branch_state="bridge_missing"`, `counterexample_conversion_rate=1.0`, `grammar_diversity_minimum=3`, and `no_retry_without_new_grammar=input.force_retry_same_candidate` (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1777-1967`).
- `_design_record(...)` marks the candidate as shadow: base axis positions are `grammar_expanded_shadow_only` and `candidate_emitted_from_grammar_shadow_only`; `INTERVENTION.design_candidate` firewall status is `warn` with reason "Candidate is replay-visible but remains shadow-only and non-exhaustive"; the returned record has `projection_status="shadow"` and an envelope certified only for `shadow_design_search_replay`, `machine_replay_trace`, and `reviewer_search_trace`, with production/recommendation/publication/etc. in `not_certified_for` (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1970-2188`; `_MAY_NOT_USE_FOR` at `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:142-151`).
- `project_s2_design_search(...)` projects the trace and explicitly emits `"canonical_outcome_effect": "none_shadow_only"`, plus the same authority boundary; PUBLIC projections have guard assertions for regime/composition/blind-spot/delegation/value/resource disclosures and raw-field leaks (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1106-1247`, assertions at `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1278-1370`).
- Persistence is real but limited to CAS storage of the `DesignRecordV0` and `SearchLedger`; `persist_s2_design_search_run(...)` writes JSON artifacts of kinds `policyos.layer2_s2.design_record_v0` and `policyos.layer2_s2.search_ledger`, and `load_s2_search_ledger(...)` reads the ledger back (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:1373-1424`).

**What it calls / what calls it**

- The runner calls only local constructors and helper functions in this file: `_shadow_boundary`, `_grammar_expansion`, `_candidate`, `_constraint_store`, `_counterexample`, `_refinement_decision`, `_iteration_status`, S7/S8/S11 status overrides, `_search_ledger`, `_design_record`, `_cluster_interfaces`, and `_handoff_records` (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:952-1103`).
- In `src`, this surface is exported from `polisyos.pdc` and not called by the runtime workspace loop or Scientist workflows (`policy-engine/src/polisyos/pdc/__init__.py:91-94`, `policy-engine/src/polisyos/pdc/__init__.py:202-206`). Caller scan over `policy-engine/src` found only the module and `pdc/__init__.py` references to `run_s2_shadow_design_loop`.
- Live non-runtime callers are validation/corpus tooling and tests: `check_policy_design_case_layer2_s2_design_search.py` runs default, A-spec, substrate, and budget variants for validator evidence (`policy-engine/tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py:77-97`), and `run_universal_outcome_corpus.py` injects S4/S5/S6/S7/S8/S10/S11/S12/S13 posture artifacts into the same one-shot runner (`policy-engine/tools/quality/validation/run_universal_outcome_corpus.py:1588-1625`). Unit tests exercise many variants (`policy-engine/tests/unit/pdc/test_layer2_s2_design_search.py:827-2600`, caller scan).

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` and instantiated `Layer2S2DesignSearchInput` with minimal objective/construct refs.

```text
default
  status shadow_ready
  candidate_count 1 candidate pdc://layer2/s2/ua-msme-credit-probe/candidate/credit-guarantee credit_guarantee {'coverage': 'partial_portfolio', 'risk_share': 'first_loss', 'delivery_channel': 'bank_intermediated'} candidate_unverified deterministic_producer
  grammar_families ['credit_guarantee', 'interest_rate_buydown', 'cash_grant']
  counterexample real_design_blocker routed_to refinement_policy
  decision refine next pdc://layer2/s2/ua-msme-credit-probe/candidate/refined-001
  ledger_iterations 1 iteration_status refined_shadow no_retry_without_new_grammar False
  acquisition_branch_state bridge_missing
  projection_status shadow certified_for ['shadow_design_search_replay', 'machine_replay_trace', 'reviewer_search_trace']
  not_certified_contains_production True
a_spec_gap -> status governance_required, decision human_decision, next None
substrate_gap -> status acquisition_required, decision acquire, acquisition_branch_state bridge_missing
force_retry_same_candidate -> status blocked, decision block_candidate, iteration_status blocked_no_retry, no_retry_without_new_grammar True
llm_candidate_with_grammar -> same fixed credit_guarantee candidate, source_authority llm_candidate, status candidate_unverified
llm_candidate_without_grammar raises Layer2S2DesignSearchInputError llm_candidate requires grammar_expansion_ref and remains shadow-only
```

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Runner: `SHADOW` + `HARDCODED` + single-iteration replay packet. It is not dead because validators, corpus tooling, public exports, and tests call it, but it is not a reusable generative loop as shipped. The candidate frontier is one fixed credit-guarantee candidate plus a synthetic `next_candidate_ref`; no second candidate is generated or evaluated.
- Discipline: `REAL/REWORKABLE`. The typed grammar-before-candidate, counterexample, VOI/budget-aware refinement decision, governance handoff validation, no-retry flag, constraint-store, deterministic replay, projection, and persistence discipline is usable substrate for GY-N3.
- Promotion/authority: `SHADOW_ONLY`. The design record and projections block production/recommendation/publication authority and publish `"canonical_outcome_effect": "none_shadow_only"`.

Disposition hint:

- `REWORK_TO_FIT`. Keep the typed ledger/refinement/counterexample/constraint-store/projection discipline, replace the hardcoded candidate/one-shot body, and wire it to real A/value/promotion owners. Delete or quarantine only duplicated hardcoded candidate construction after a real generator exists.

Open questions:

- Which GY-N3 owner should own the real iterative state machine: extend this S2 discipline, or make the workspace loop consume these typed records?
- Does the Universal Outcome Corpus output get consumed by any authority-bearing promotion path, or is it also validation/corpus-only? Caller scan shows no runtime caller, but promotion files still need reading.

### `scientist/nodes/builtins/simulate/run_causal_evaluation.py`: Reachable Foundry Causal Value Executor

**What it does from code read**

- This node is the concrete Foundry-method execution owner reached by the Pass-2 workspace `run_intent` path. Its `NodeSpec` reads an `observational_data_ref`, `causal_method_fqn`, method params, and optional evidence settings; it writes a causal report, uncertainty envelope, method result/evidence refs, validity bundle, optional HTE/recommendation artifacts, and optional claim artifacts (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:79-118`).
- `_load_observational_data(...)` is typed by method FQN: it validates CAS/state payloads into `PanelObservationalData`, `RDDObservationalData`, `HTETrainingData`, or `GraphDiscoveryData` depending on method family (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:302-324`).
- `execute(...)` fail-closes when `observational_data_ref` is absent (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:366-381`), defaults to `causal.inference.synthetic_control` when no FQN is supplied (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:383-390`), then calls `ensure_causal_methods_registered()`, builds a `JobSpec`, and calls `run_job(... method_state=observational_data)` (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:392-415`).
- It treats Foundry job issues or missing/invalid report output as node failure (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:416-450`), then persists method result/evidence refs, causal validity, causal effect report, uncertainty envelope, optional HTE/recommendation outputs, and optional claim ledger/claims (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:464-852`).

**What it calls / what calls it**

- It calls `scientist.compute.runner.run_job(...)`, which looks up a method class in the registry and dispatches it through `MethodDispatcher` (`policy-engine/src/polisyos/scientist/compute/runner.py:224-266`). It also calls the causal catalog bootstrap before dispatch (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:392-415`).
- `runtime/quality/workspace/loop.py` executes this legacy alias in `run_intent(...)` and then consumes its state refs through `FoundryMethodOutputConsumer` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1338-1429`), so this is not merely a workflow DAG node: it is the value-producing method path reachable from the honest backbone's Phase-2 adapter.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` for causal-method execution when supplied observational data and a reachable method. It computes or fails through Foundry method classes and persists typed result/evidence/report artifacts.
- `NOT a full candidate value cycle` by itself: it computes causal/effect evidence, not generation, revision, or promotion. The workspace consumer downgrades consumed output to `descriptive_only`, so reachable value does not automatically become design authority.

Disposition hint:

- `USE_AS_IS` as the first GY-N5 value method bridge under available dependencies. Rework is needed around candidate-to-observational-data binding and authority promotion, not inside the basic method dispatch path.

Open questions:

- Which exact candidate artifact should own the `observational_data_ref` / method params handoff in GY-N5? Current Phase-2 fixtures install synthetic support for legacy aliases; the candidate binding owner is not yet canonical.

### Foundry Causal and Optimization Catalogs: Dependency Truth Under Python 3.14

**What it does from code read**

- The catalog bootstrap has explicit optional-dependency gating. `_optional_method_types(...)` skips methods when an optional dependency is missing (`policy-engine/src/polisyos/foundry/methods/catalog/causal/_registry_boot.py:206-238`). The causal registry then registers core causal methods and only conditionally registers DoWhy and EconML-backed methods (`policy-engine/src/polisyos/foundry/methods/catalog/causal/_registry_boot.py:241-458`).
- `SyntheticControlEstimator.pure_step(...)` is real numerical computation over `PanelObservationalData`: it uses donor weights from `_fit_scm_weights(...)`, which calls `scipy.optimize.minimize(...)`, computes post-treatment effects, confidence interval, p-value, diagnostics, and `CausalEffectReport` (`policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:40-96`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:344-470`).
- `StandardDifferenceInDifferences.pure_step(...)` computes ATT with NumPy least-squares HC1 logic, not EconML/DoWhy (`policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:116-128`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:175-254`).
- `ParallelTrendsCheck` declares `runtime_stack=("statsmodels", "numpy")` and its `pure_step(...)` imports statsmodels and runs an OLS pre-trend regression (`policy-engine/src/polisyos/foundry/methods/catalog/causal/diagnostics.py:47`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/diagnostics.py:100-128`).
- DoWhy-backed methods are unavailable on this runtime and degrade explicitly: `_run_dowhy(...)` catches `ModuleNotFoundError` and returns a failure report with `status_reason` instead of pretending to compute (`policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py:36-40`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py:202-223`).
- EconML-backed HTE methods are unavailable on this runtime and fail explicitly through `require_econml(...)` (`policy-engine/src/polisyos/foundry/methods/catalog/causal/_econml_adapter.py:13-47`); `ForestDRCATEEstimator.pure_step(...)` catches that import failure and returns a numerical-failure report (`policy-engine/src/polisyos/foundry/methods/catalog/causal/forest_dr.py:122-144`).
- Optimization is mixed. `QuadraticProgramEstimator` declares `("cvxpy", "numpy")` but catches missing `cvxpy` and falls back to `_solve_with_scipy(...)` (`policy-engine/src/polisyos/foundry/methods/catalog/optimization/convex.py:266`, `policy-engine/src/polisyos/foundry/methods/catalog/optimization/convex.py:343-520`). `MultiObjectiveNSGA2Estimator` declares `("pymoo", "numpy")` and its `pure_step(...)` imports pymoo and solves a constrained selection problem (`policy-engine/src/polisyos/foundry/methods/catalog/optimization/multiobjective.py:48`, `policy-engine/src/polisyos/foundry/methods/catalog/optimization/multiobjective.py:110-221`).

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` and directly invoked representative `pure_step(...)` methods with minimal typed state.

```text
deps {'econml': False, 'dowhy': False, 'cvxpy': False, 'statsmodels': True, 'jax': True, 'pymoo': True, 'scipy': True}
compute synthetic_control OK {'method': 'synthetic_control', 'status': 'success', 'point_estimate': 0.7965517314863092, 'confidence_interval': [0.5724137986147315, 0.9724137986147321], 'status_reason': None, 'p_value': 0.3333333333333333}
compute standard_did OK {'method': 'difference_in_differences', 'status': 'success', 'point_estimate': 0.7916666666666671, 'confidence_interval': [0.2830708938045364, 1.3002624395287978], 'status_reason': None, 'p_value': 0.0022821137039417275}
compute parallel_trends OK {'test_name': 'parallel_trends_check', 'passed': True, 'p_value': 1.0}
compute quadratic_program OK {'status': 'optimal', 'objective_value': 0.8999999950000006, 'backend': 'scipy.optimize.minimize', 'variables': {'x_0': 1.0, 'x_1': 9.43689570931383e-16}}
compute multiobjective_nsga2 OK {'status': 'optimal', 'objective_value': 2.7, 'constraints': {'budget': True}}
compute dowhy_identify OK {'method': 'dowhy_backdoor', 'status': 'numerical_failure', 'point_estimate': None, 'confidence_interval': None, 'status_reason': "DoWhy backend unavailable: No module named 'dowhy'", 'p_value': None}
compute forest_dr OK {'method': 'forest_dr', 'status': 'numerical_failure', 'point_estimate': None, 'confidence_interval': None, 'status_reason': 'ForestDR backend unavailable: EconML is required for HTE methods. Install optional deps: pip install policy-engine[causal]', 'p_value': None}
```

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` for the reachable causal/value subset: synthetic control, standard DiD, statsmodels diagnostics, SciPy fallback quadratic optimization, and pymoo NSGA-II compute nonconstant numerical outputs under Python 3.14.
- `BLOCKED/optional-unavailable` for DoWhy and EconML method families under the active Python 3.14 runtime. They fail explicitly rather than silently producing authority.
- `REUSE_WITH_FALLBACK` for CVXPY-labeled quadratic programming specifically, because the code has a SciPy fallback that the probe exercised. Do not generalize that to every CVXPY-backed optimizer without reading/probing each method.

Disposition hint:

- `USE_AS_IS` for method availability truth and reachable methods. `REWORK_TO_FIT` for GY-N5 task text: it must select the available statsmodels/NumPy/SciPy/pymoo subset or surface a method-unavailable blocker for DoWhy/EconML-only claims.

Open questions:

- Pass 3 should read any additional value method families selected by the rewritten GY-N5 acceptance tests; this pass only proves representative reachable and blocked paths.

### `runtime/quality/design_axes/outcome_prediction.py`: S10 Forecast Authority Gate, Not Forecast Producer

**What it does from code read**

- `ForecastSupport` is a typed S10 support record over already-supplied S5/S6/S8 refs, source/method lineage, uncertainty, calibration, and an `AuthorityBoundary`; validators require observable-calibrated support to carry observable/calibration refs and governed tiers to carry uncertainty intervals, forbid simulation-only support from upgrading beyond `simulation_only_advisory`, and require limitations for transported estimates (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:97-166`).
- `ForecastCalibrationRecord` validates observable-subset calibration math, evidence refs, time window ordering, and authority denials; it does not compute forecasts (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:169-224`).
- `WelfareComparisonRecord` enforces S8 value provenance and refuses hidden Pareto scalarization unless frontier and rejected nondominated alternatives are visible (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:269-314`).
- `build_forecast_support(...)` requires S5/S6/S8/design graph/prediction context inputs, derives a forecast tier from S5 origin/label, requires observable calibration refs for observable tiers, validates equilibrium blocking, requires source/method/sensitivity refs for validated local models, and applies system-effect constraints (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:430-449`, helpers at `policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:613-680`).
- `verify_prediction_authority_envelope(...)` builds an envelope from support and optional calibration. It denies production/recommendation/claim/closeout/S11 authority through merged `may_not_use_for` and marks `envelope_status="blocked"` when issue codes exist (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:471-545`).
- `_prediction_issue_codes(...)` flags simulation-only evidence laundering, equilibrium-contested single forecast, uncalibrated observable promotion, and missing required authority denials (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:683-698`). `summarize_forecast_support_integrity(...)` aggregates calibration counts and non-observable/simulation/equilibrium blocker counts (`policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:548-610`).

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` and built minimal S10 support/calibration records.

```text
simulation_support simulation_only_advisory simulation blocked ['s10_simulation_only_laundered_as_evidence'] True True
observable_support observable_calibrated blocked limit ['s10_uncalibrated_observable_promotion'] True
integrity 2 4 3 0.75 limit 1
equilibrium_single_point_error ValueError equilibrium contested system effect cannot emit single point forecast
```

The first attempted observable probe also failed when I used stale literals (`localized_validated_model`, `localized_effect`), proving the model enforces the current S5 literal set from `coupling_composition.py:78-93`. The second attempted probe failed until `forecast_authority_disposition_reason` was supplied, proving the builder does not synthesize the reason.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` authority/calibration gate. It classifies and blocks/limits forecast support from supplied artifacts.
- `NOT a forecast producer`: no function here estimates an effect, simulates outcomes, or computes candidate value. The actual numeric effect must come from Foundry causal/simulation/optimization or supplied metrics; this file verifies support posture around those outputs.

Disposition hint:

- `USE_AS_IS` for S10 forecast authority gating in GY-N5/GY-N6. The rewrite should not ask this owner to compute value; it should feed it method output, calibration evidence, uncertainty refs, and value provenance.

Open questions:

- Need promotion pass to prove whether S10 envelopes are consumed by governed promotion, or only available as readiness artifacts.

### `scientist/nodes/builtins/compile/compile_foundry.py`: Foundry Compile Bridge

**What it does from code read**

- `CompileFoundryNode` reads a Trinity bundle and optional method registry ref, then writes compile/link reports, execution plan, lowered program, program graph, typed IR, and provenance refs (`policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py:41-65`).
- `execute(...)` fails if `ctx.foundry` is missing, requires `inputs.trinity_bundle_ref` and kind `ir.trinity_bundle`, builds a `CompileRequest`, and calls `ctx.foundry.compile(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py:97-135`).
- It persists returned refs into the experiment state and fails if Foundry compile returned `ok=False` (`policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py:137-178`).

**What it calls / what calls it**

- It calls a Foundry port, not the method registry directly. `RunHierarchicalPolicySearchNode._evaluate_candidate_payload(...)` calls this node before cross-graph evidence, parameter resolution, causal readiness, simulation, and runtime evaluation (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:325-450`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL bridge` if `ctx.foundry` is configured and a Trinity bundle exists. It compiles a candidate into executable plan artifacts.
- `BLOCKED` without a Foundry port. It is not a value estimator and does not compute forecast/value itself.

Disposition hint:

- `USE_AS_IS` as the candidate-to-execution-plan bridge for the Scientist Stage-B path; GY needs a real candidate/Trinity owner upstream and a configured Foundry port in the execution context.

### `scientist/nodes/builtins/causal/run_causal_readiness.py`: Causal Readiness Producer

**What it does from code read**

- Its spec reads C4a bundles, graph refs, proxy/interference/transport/counterfactual query inputs, and writes causal readiness bundles and selected transport/strategic/proxy/counterfactual refs (`policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py:71-99`).
- `execute(...)` skips if no readiness inputs are present, loads a reconciled causal graph when referenced, coerces bundle inputs, then runs `ProxyIdentificationRunner`, `TransportabilityChecker`, `StrategicResponseRunner`, and `CounterfactualQueryRunner` to assemble readiness entries (`policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py:150-281`).
- It persists a `CausalReadinessBundle` and selected refs into state (`policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_readiness.py:283-341`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL readiness/gate artifact producer`, not a value estimator. It produces causal-readiness inputs/limitations that Stage-B or promotion can use, but it does not compute a policy effect.

Disposition hint:

- `USE_AS_IS` for grounding/readiness around value, with GY wiring needed so real candidate-generated graphs/bundles reach it.

### `scientist/nodes/builtins/simulate/run_simulation.py`: Foundry Execute / Simulation Bridge

**What it does from code read**

- The node reads an execution plan, input bindings, candidate schema, optional simulation method, strategic response, and causal params; it writes simulation result/metrics/proof bridge and strategic artifacts (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py:103-167`).
- `execute(...)` fails if no Foundry port exists, materializes policy override bundles, requires `exec_plan_ref` and `input_bindings_ref`, enforces `Phase4DynamicsGate`, builds an `ExecuteRequest`, and calls `ctx.foundry.execute(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py:194-320`).
- It loads simulation result payload/state snapshot if present, routes derived refs, fails on `result.ok=False`, materializes a simulation proof bridge, and optionally runs a strategic-response hook using `policy_runtime_support.load_simulation_metrics(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py:325-529`).

**What it calls / what calls it**

- It is called by the hierarchical-search Stage-B evaluator after compile/readiness/cross-graph/parameter resolution (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:325-450`).
- It is not executed by the Pass-2 workspace `run_intent(...)` adapter; that adapter executes `run_causal_evaluation` and `run_normative_arbitration` only (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1338-1367`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL bridge` to Foundry simulation when compile/execute artifacts and `ctx.foundry` are present.
- `implemented_but_not_orchestrated` from the honest workspace loop's Phase-2 path. It is present in the Scientist policy-design Stage-B path, but the default verified/mock candidate currently fails before Stage-B due missing Lex bounds.

Disposition hint:

- `REWORK_TO_FIT`: use it for GY-N5 where the policy-design DAG/hierarchical search can actually enter Stage B; do not claim the workspace loop already runs it.

### `scientist/nodes/builtins/decide/policy_runtime_support.py` and `scientist/policy_design/objectives.py`: Candidate Value Assembly and Promotion Input Support

**What it does from code read**

- `ProductionPolicyEvaluationBackend.evaluate(...)` builds evidence-driven simulation metrics, evaluates `ObjectiveStack`, and only sets `promotable_source=True` when fidelity is full and causal effect report, uncertainty report, governance report, plus metrics or causal report source are present (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:165-235`).
- `SyntheticPolicyEvaluationBackend.evaluate(...)` builds deterministic synthetic metrics and always returns `promotable_source=False` with `degradation_mode="research_only"` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:244-310`).
- `resolve_policy_evaluation(...)` loads metrics/evaluation refs and evaluates the objective stack when a parsed evaluation is not already present (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:331-360`). `build_policy_simulation_results(...)` returns policy value, employment, welfare, net social welfare, GDP/government-balance changes, ATE/bootstrap, objective channels, and provenance from an evaluation (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:461-530`).
- Artifact loaders read `Metrics`, `CausalEffectReport`, uncertainty/governance/cross-graph/distributional/ambiguity reports from state/CAS (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:610-644` and adjacent loaders).
- `_build_runtime_simulation_metrics(...)` is deterministic synthetic fallback from candidate shape/parameters/objectives and is not promotion-safe (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:1173-1224`).
- `_build_evidence_driven_simulation_metrics(...)` uses supplied simulation metrics, causal effect report point estimate or ATE, conservative zero fallback, distributional/governance/transport penalties, CI width from causal report/uncertainty, and a `source_components` trail (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:1227-1332`).
- `ObjectiveStack.evaluate(...)` deterministically scores supplied metrics into primary policy value/employment/welfare, secondary inequality/robustness/transportability/evidence/simplicity criteria, penalties, and hard-constraint outcomes (`policy-engine/src/polisyos/scientist/policy_design/objectives.py:241-430`). It is a scorer over evidence/metrics, not an estimator.
- `run_promotion_with_evidence(...)` assembles promotion inputs and enforces evidence completeness before invoking promotion coordination (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:935-1170`). Full promotion enforcement still needs its own Pass-2 section after the promotion files are read.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Production backend: `REAL` value assembly/scoring from existing causal/simulation/governance artifacts; authority-aware because promotability depends on evidence completeness.
- Synthetic backend: `SHADOW/HARDCODED-FALLBACK` for tests/research only, explicitly not promotable.
- Objective stack: `REAL deterministic scorer`, but not a causal forecast producer.

Disposition hint:

- `USE_AS_IS` for evidence-driven scoring and promotability checks. `REWORK_TO_FIT` around the synthetic fallback: keep for tests/fixtures, do not let it become GY authority.

### Stage-B Value Verdict Under Python 3.14

- The value path is **not globally blocked** by unavailable EconML/DoWhy/CVXPY. Real causal/value computation is available through synthetic control, DiD, statsmodels diagnostics, SciPy fallback quadratic optimization, pymoo NSGA-II, and likely JAX/NumPy-backed support paths. DoWhy/EconML-specific methods are blocked/unavailable and return explicit failure/no-backend reports.
- `outcome_prediction.py` is a calibration/authority gate over supplied forecast support; it must be reused as a gate, not treated as a forecast engine.
- The current honest workspace loop reaches `run_causal_evaluation` descriptively, not `compile_foundry`/`run_simulation`. The Scientist hierarchical Stage-B path contains compile/readiness/simulation/evaluation wiring, but the current mock-formalized candidate can fail before Stage B due missing bounds.
- GY-N5 should be rewritten as `reuse-with-available-method-subset`: bind candidate to observed/simulation data, execute reachable Foundry method(s), assemble evidence-driven runtime evaluation, then pass forecast support through S10 gates. It should explicitly block or skip DoWhy/EconML-only claims under this runtime.

### `pdc/_impl/layer2_readiness.py` and `pdc/_impl/gy_waist.py`: Two-Ring Waist / Authority Derivation Contracts

**What it does from code read**

- `AuthorityBoundary` is a purpose-scoped authority lattice: it records authoritative purposes, denied purposes, source authority, posture, rule refs, evidence kind, decision grade, evidence basis, and known limits (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:62-74`).
- Its validators enforce two load-bearing invariants: any `llm_*` source must remain `shadow`, and uncalibrated simulation cannot carry `advisory_admissible` or stronger authority (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:76-89`).
- `AuthorityBoundary.meet(...)` computes the weakest shared boundary by intersecting authoritative purposes, unioning denied purposes, meeting evidence kind/decision grade/source/posture, and merging evidence bases (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:91-114`, helper lattice functions at `policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:186-252`).
- `DesignRecordV0` refuses LLM-sourced non-shadow records and refuses production authority; `CanonicalDesignRecord` likewise refuses production posture/boundary (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:320-343`, `policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:346-383`).
- `GyWaistModel` owns Ring-2 write control: subclasses list `ring2_fields`, and `_reject_untrusted_ring2_writes(...)` rejects non-verifier/governance/a-side/system-verifier attempts to write those fields (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:141-165`).
- `assert_ring2_verifier_provenance(...)` is the consumption-time backstop: it revalidates even constructed/copied models with writer context and recursively rejects non-verifier-populated Ring-2 fields (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:91-129`).
- Ring-2 fields include `ArtifactEnvelope.authority_boundary` and `certified_operation_envelope`, `ArtifactEnvelopeVerification.latest_promotion_result`, `PortSpec.provided_authority`, and `SearchLedgerEvent.authority_delta` (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:269-314`, `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:431-448`).
- `AuthorityDerivationTrace` proves authority is computed, not copied from operation hints. Its validator rejects `transform_mismatch_disposition="upgraded"`, rejects "matched" transforms where requested evidence/grade exceeds computed evidence/grade, and rejects decision-admissible self-promotion past unresolved blockers (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:451-497`).
- `SearchExitContract` derives `evidence_kind`, `decision_grade`, and `evidence_ladder_rung` from the verifier-written `authority_boundary`, rejecting mismatched explicit fields (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:694-742`).
- `AgentDecisionRecord` is explicitly candidate-only and rejects `candidate_only=False` (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:627-650`). `SubDesignContract` requires authority to be exported on provided ports if a search exit has an authority boundary (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:778-808`). `CompositionCertificate` requires a receipt for composable verdicts (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:860-883`).

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"`.

```text
llm_governed_boundary_error ValidationError 1 validation error for AuthorityBoundary
uncalibrated_sim_error ValidationError 1 validation error for AuthorityBoundary
port_agent_write_error ValidationError 1 validation error for PortSpec
port_verifier_write decision_admissible
construct_boundary_error ValueError Ring-2 verifier provenance rejected: 1 validation error for ArtifactEnvelope
construct_boundary_verifier_ok True
```

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` two-ring authority enforcement. It is not a generator or promotion controller, but it is the waist that prevents Ring-1/agent/candidate records from writing verifier authority fields and forces derived authority to agree with the boundary.

Disposition hint:

- `USE_AS_IS` for GY-N6 waist invariants. Any in-cycle promotion should pass through these models instead of inventing a parallel authority shortcut.

Open questions:

- Which future GY controller should be responsible for calling `assert_ring2_verifier_provenance(...)` at every persist/promote/surface read? The contracts exist; orchestration coverage still needs audit in Pass 3.

### `runtime/quality/proving_ground/governed_promotion_gate.py`: G4 Shadow-To-Governed Promotion Gate

**What it does from code read**

- G4 is explicitly bounded to promotion state over persisted Layer-3 artifacts. It denies production, publication, approval, scorecard, closeout, source-data truth, claim authority, recommendation, legal/proof/effect authority without upstream gates, human override of A incompleteness, and useful-design credit before G5 (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1-6`, `policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:61-86`).
- It normalizes explicit promotion requests into `Layer3G4PromotionInput` only after `resolve_g4_source_design_record(...)` finds a replay ref, non-placeholder digest, and full payload status; unresolved/ref-only/manifest-only/missing digest all produce issue codes/blockers (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1329-1381`, `policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1418-1486`).
- `build_g4_grounded_contract_set(...)` accepts only grounded contract families `g1_source_contract`, `g2_forecast_support`, `g3_proof_record`, and `gl_legal_mandate`; it rejects search-ledger-only, readiness-summary-only, GL compatibility overclaims, unresolved required refs, fixture-scoped grounding, and rows whose `may_not_use_for` blocks governed promotion (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1500-1703`).
- `_required_families_for_input(...)` derives G1/G2/G3/GL requirements from declared claim families and scope flags (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1768-1791`). `_contract_support_issue_codes(...)` enforces adapter admission, conformance, search recall/freshness, upstream deny-list, G2 calibration/limitation, G3 proof/certificate resolution, GL legal authority/temporal competence/reissue/reference resolution, and limited-boundary overpromotion (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1922-1996`).
- `build_g4_a_completeness_ledger(...)` walks every claim/family requirement, records supporting refs, blockers, limitations, and appends `layer3_g4_a_completeness_failed` on any issue (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1999-2111`).
- `build_g4_human_decision_integrity_gate(...)` requires S7/P26 human-decision records for high-stakes/value-laden/accountability/out-of-routine scopes, rejects "human not required" bypasses without bounded rationale, validates full `HumanDecisionRequest`/`HumanDecisionRecord` payloads when provided, checks five-rights/responsibility integrity/active choice/scope match, and refuses human decisions that override A incompleteness (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:2114-2429`).
- `build_g4_weakest_boundary_composition(...)` collects ledger, contract, and policy-program composition blockers and calls `reduce_g4_promotion_state(...)`; blockers produce `promotion_blocked`, no blockers produce `governed_promoted` (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:2432-2504`).
- `reduce_g4_promotion_state(...)` itself is pure and fail-closed: it rejects missing input refs, inline/unhashed refs, invalid producer roots, non-pass/limited dependency statuses, and explicit blocker refs; only then emits `governed_promoted` with hashed input provenance (`policy-engine/src/polisyos/runtime/quality/proving_ground/status_decision_reducers.py:289-311`, `_input_issue_codes` at `policy-engine/src/polisyos/runtime/quality/proving_ground/status_decision_reducers.py:421-441`, output hash at `policy-engine/src/polisyos/runtime/quality/proving_ground/status_decision_reducers.py:444-487`).
- `build_g4_promotion_records(...)` writes final records from the reduced decision, preserving blockers/limitations/upstream refs and keeping downstream consumer gates reference-only (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`). Closeout/PDC/G5 consumer gates and public projections only carry refs, states, blockers, limitations, and deny-lists (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:2753-2971`).
- `validate_layer3_g4_bundle(...)` validates dependency readiness, request-level source/composition/context/self-promotion/naming/upstream-builder/G1/readiness-summary/GL/human-decision blockers, plus public projection and authority-leak checks (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:4293-4726`).
- `build_layer3_g4_bundle(...)` builds a repository bundle from persisted G4 runtime request payloads and dependency artifacts, then runs conformance and registry-ratchet generation (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:4729-4804`).

**What it calls / what calls it**

- G4 calls the required-reference resolver and G5/GX reducers, but it does not call the workspace loop, Scientist policy-design DAG, or S2 runner directly in the code read.
- Caller scan shows live usage by the G4 readiness validator (`policy-engine/tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py:154-156`), repo-quality/unit tests, and internal conformance fixtures. No `runtime/quality/workspace/loop.py` or Scientist workflow caller was found for `build_layer3_g4_bundle(...)` or `validate_layer3_g4_bundle(...)`.

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` and directly exercised the G4 builders.

```text
pass_chain pass () pass () pass () governed_promoted not_required ['governed_promoted'] [()]
missing_cal_chain pass pass fail ('layer3_g4_missing_g2_calibration_ref', 'layer3_g4_a_completeness_failed') promotion_blocked ['promotion_blocked'] [('layer3_g4_missing_g2_calibration_ref',)]
validate_llm fail ['layer3_g4_shadow_self_promotion']
```

An earlier probe using digest `sha256:` plus all `1`s produced `layer3_g4_source_design_record_digest_missing`, proving placeholder digests are rejected by `resolve_g4_source_design_record(...)`.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` promotion gate and validator over explicit/persisted inputs. It can emit a real `governed_promoted` state for declared G4 scope when source design record, upstream grounded contracts, adapter admission/conformance, A completeness, human-decision gate, and weakest-boundary reducer all pass.
- `implemented_but_not_orchestrated` for an in-cycle GY loop: no evidence yet that `run_fixture`, `run_intent`, S2, or the Scientist policy-design DAG calls this gate during candidate evaluation/revision.
- Authority is intentionally bounded: G4 promotion state is not production/publish/closeout/usefulness authority.

Disposition hint:

- `USE_AS_IS` for GY-N6 shadow-to-governed gating semantics. `REWORK_TO_FIT` for orchestration: the generation cycle needs an explicit promotion step that feeds this gate with real S2/S5/S10/G1/G2/G3/GL artifacts and then passes the resulting state through the two-ring waist.

Open questions:

- Pass 3 should verify the persisted request payload path (`_persisted_g4_runtime_request_payloads`) and whether current artifacts ever represent a real candidate from the GY cycle rather than validation/conformance fixtures.

### Scientist Policy Promotion: Direct Node Disabled, Evidence-Gated Support Path Exists

**What it does from code read**

- `RunPolicyPromotionNode.execute(...)` is no longer a live direct runtime promotion node: in policy mode it returns a failure telling callers to use `run_policy_blueprint_runtime`; outside policy mode it skips (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py:120-141`).
- The older helper `_run_promotion_with_evidence(...)` still requires `PromotionEvidenceBundle.assert_compatible_with_run(...)`, selection/hidden-holdout/adversarial/replay/governance refs, loaded governance report, causal/distributional/cross-graph/prior/latent/uncertainty inputs, then calls `PolicyPromotionCoordinator.coordinate_promotion(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py:144-251`).
- `PromotionEvidenceBundle.missing_required_refs(...)` requires selection, hidden holdout, adversarial meta evaluation, replay bundle, optional replay verification/calibration, and governance refs depending on flags (`policy-engine/src/polisyos/scientist/methods/search/promotion_evidence.py:20-65`). `assert_runtime_compatible(...)` binds those refs to current run/candidate, checks artifact kinds, split roles, stale refs, replay bundle kind, replay verification run/ref match, calibration report kind, governance manifest presence, and stress-test kind (`policy-engine/src/polisyos/scientist/methods/search/promotion_evidence.py:67-198`).
- The current support function `run_promotion_with_evidence(...)` in `policy_runtime_support.py` is stricter than the older direct-node helper: it verifies or persists replay verification, calls `assert_runtime_compatible(...)`, then requires hidden holdout, replay bundle, replay verification, governance, and calibration before building the judge input (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:935-995`).
- It loads selection/hidden-holdout/platform meta/governance/causal/distributional/cross-graph/prior/latent/uncertainty, extracts Phase-2 proof/bounds/data-readiness refs and evaluation provenance, then calls `PolicyPromotionCoordinator.build_input_bundle(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:997-1157`).
- `PolicyPromotionCoordinator.coordinate_promotion(...)` runs the judge stack, persists a judge verdict, evaluates and persists a decision-readiness contract, refuses promotion if the judge verdict is not `promote`, refuses if `evaluation_promotable_source` is false, and only then calls the champion registry's `consider_promotion(...)` (`policy-engine/src/polisyos/scientist/methods/search/judge_stack.py:1397-1679`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- Direct node: `DEAD/disabled for policy runtime` as a direct workflow node.
- Support path/coordinator: `REAL evidence-gated promotion machinery`, but separate from G4 PDC promotion-state semantics. It promotes a Scientist champion candidate after judge/readiness/evidence checks; it does not itself produce the G4 `governed_promoted` PDC state.

Disposition hint:

- `REWORK_TO_FIT`: keep evidence-bundle/runtime compatibility and judge/readiness checks, but clarify whether GY-N6 means G4 PDC promotion state, Scientist champion promotion, or both in sequence.

Open questions:

- Pass 3 should trace `run_policy_blueprint_runtime` and confirm how, if at all, it links Scientist champion promotion to the G4 governed promotion gate.

### `runtime/quality/proving_ground/bounded_request_agent.py`: G6 Bounded Arbitrary-Request Agent

**What it does from code read**

- G6 constants bound the surface to orchestration audit, G5 routing decision, and demand-pull-vs-abstention readings. The deny-list includes production, rollout, publication, approval, scorecard, closeout, public/policy recommendation, legal advice, claim/obligation/causal/proof/legal authority, direct G5 conversion authority, and G7 region widening (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1-6`, `policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:88-123`).
- `Layer3G6PolicyGrammarProjection` validates compiler-supplied routing facets and concept/jurisdiction spine refs; it must carry `authoritative_for=("layer3_g6_policy_grammar_routing_facets",)` and deny legal/claim/closeout authority (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:281-325`).
- `Layer3G6GrammarExpansionCandidate` is always `authority_state="candidate_unverified"` and carries `may_not_use_for=G6_MAY_NOT_USE_FOR` (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:351-360`).
- `run_layer3_g6_bounded_agent_loop(...)` validates the policy-grammar projection, builds an envelope/candidate/tool registry/tool-contract summary, creates or receives a client, and if a client exists runs the Scientist `run_tool_loop(...)` with a G6 system/user prompt and bounded tool registry (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1318-1368`).
- The running loop records only selected allowed G6 tool names, fixed selected evidence refs for G5 readiness/conversion, rejects `unbounded_web_search` and a legal-advice branch, builds prompt-tool and hypothesis ledgers, projects the tool-loop trace, and builds a search ledger with `completeness_status="partial_budget_cutoff"` (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1369-1462`).
- `_blocked_g6_agent_loop_result(...)` builds prompt-tool/hypothesis ledgers, a blocked trace with `layer3_g6_llm_client_unavailable`, a search ledger with rejected allowed tools, and an audit with no synthetic success (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:2382-2445`). In this runtime, `client=None` attempted to create a traced gateway client and then failed on unsupported model before reaching this branch; see probe note below.
- `build_g6_design_record_candidate_handoff(...)` creates a hypothesis-ledger-backed design-record candidate handoff, still `candidate_unverified`, for composed G6 -> G5 consumption (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1467-1513`).
- `build_g6_g5_invocation_plan(...)` bridges only to the pinned G5 case for `same_class_as_g5_pinned_case`; outside envelope returns abstention, non-pinned case attempts and denied requested authority from G5 produce issue codes, and the actual G5 bundle/consumer gate is read to populate conversion refs/outcomes (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1516-1608`).
- `build_layer3_g6_agent_run_record(...)` is deterministic/non-LLM: it builds the request envelope, candidate, grounding demand, tool summary, G5 invocation, selected/rejected tool names, prompt-tool/hypothesis ledgers, search ledger, orchestration audit, result/abstention projection, engineering readiness, grounded value closure, and replay fingerprint (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1645-1816`).
- G6 replay continuity/manifest use the shared NL replay helpers and fail if required refs are missing (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1819-1895`).

**What it calls / what calls it**

- G6 calls Scientist tool-loop abstractions, G5 conversion/proving-ground functions, hypothesis/prompt-tool ledgers, replay/orchestration continuity, candidate firewall, projection semantics, and required-ref resolution (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:19-57`).
- Caller scan found G6 used by readiness validation tools and tests, G7/health governance readers, citation-faithfulness tests, and the workspace `AgentEventBridge`; no call from `runtime/quality/workspace/loop.py`, Scientist policy-design DAG, S2 design search, or Stage-B evaluator was found.

**Probe evidence**

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` with a minimal `ua_msme_support` policy-grammar projection.

```text
loop pass same_class_as_g5_pinned_case pass partial_budget_cutoff ('layer3_g6_build_g5_bundle', 'layer3_g6_read_g5_conversion') candidate_unverified True
record pass blocked_by_current_g5_unchanged_blocker g5_unchanged_blocker pass () True pass
```

The same probe attempted `run_layer3_g6_bounded_agent_loop(..., client=None)`. In this runtime `create_traced_gateway_client(...)` returned a client and the first network-backed tool-loop request failed with:

```text
RuntimeError: Gateway request failed (400): {"error":{"message":"unsupported model \"layer3-g6-bounded-agent\"; supported models: Qwen/Qwen3-235B-A22B-Instruct-2507-FP8, MiniMaxAI/MiniMax-M2.7, moonshotai/Kimi-K2.6"}}
```

So the explicit no-client blocked branch exists in code, but `client=None` is not a guaranteed blocked local path when a gateway client can be constructed.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` bounded G6 routing/audit producer for arbitrary requests and pinned G5 bridge, with candidate-only outputs and authority deny-lists.
- `NOT wired into a GY generation cycle` in the code scanned. It does not drive GY-N3 candidate generation/revision and cannot promote candidates; it routes same-class requests to pinned G5 and records candidate/audit/projection artifacts.
- Contains deterministic/hardcoded routing structure: allowed tools are fixed, selected evidence refs are G5 readiness/conversion refs, rejected branches include unbounded web search/legal advice, and default record builder selects the G5 bundle tool only when G5 invocation passes.

Disposition hint:

- `REWORK_TO_FIT` only as a bounded arbitrary-request/router input to a later cycle. Do not use it as the GY-N3 cycle controller.

### `runtime/quality/workspace/agent_proposal_bridge.py`: Agent Proposal Bridge

**What it does from code read**

- `AgentEventBridge.run_tool_loop_proposal(...)` either fail-closes with `no_client_blocker(...)` when no client is supplied, or imports Scientist tool-loop machinery, runs the tool loop, extracts tool call names, and records a Ring-1 event (`policy-engine/src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:51-93`).
- `record_tool_loop(...)` delegates to G6 `build_gy_phase2_agent_event_records(...)`, returning `AgentDecisionRecord`, `OperationInvocationRecord`, `SearchLedgerEvent`, and `MethodPlan` (`policy-engine/src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:94-123`; record builder at `policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:3378-3455`).
- Those records are candidate-only: `MethodPlan.authority_transform.kind="agent_ring1_hint_only"` with `requested_decision_grade="candidate_only"`, `admission_state="candidate_only"`, and `AgentDecisionRecord.candidate_only=True` with rationale "verifier owns promotion" (`policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:3391-3419`).
- `persist_event_bundle(...)` persists all four records to CAS with `gy.agent.*` kinds and returns waist `ArtifactRef`s (`policy-engine/src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:125-161`).
- `no_client_blocker(...)` returns `ApplicabilityResult(status="repair_required")` plus `SearchBlockerRecord(producer_missing_label="producer_missing")`; it explicitly says synthetic audits are forbidden (`policy-engine/src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:163-208`).
- `normalize_agent_voi_scores(...)` clamps numeric supported action scores to [0, 1], rejects unsupported/non-numeric/non-finite inputs, and records that agent VOI scores are candidate-only before GY-H use (`policy-engine/src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:211-286`).

**Probe evidence**

```text
bridge True candidate_only {'kind': 'agent_ring1_hint_only', 'rule_ref': 'policyos.gy.phase2.agent.v1', 'requested_decision_grade': 'candidate_only'} 0
bridge_no_client False repair_required producer_missing No agent client was supplied; synthetic audits are forbidden.
voi {'a': 1.0, 'c': 0.5} [{'action_ref': 'a', 'reason': 'score_clipped_to_unit_interval', 'original_score': 1.2, 'normalized_score': 1.0}, {'action_ref': 'b', 'reason': 'unsupported_action', 'original_score': 'bad'}, {'action_ref': 'd', 'reason': 'unsupported_action', 'original_score': 'nan'}] ['Agent VOI scores are candidate-only and normalized before GY-H use.']
```

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL` Ring-1 agent proposal/audit bridge and no-client fail-closed blocker.
- `implemented_but_not_orchestrated` for the current honest loop: caller scan did not find it invoked by `loop.py`. It is a bridge available for a future agent-proposer integration, not currently part of BIND -> ESTIMATE -> VERIFY or Phase-2 `run_intent`.

Disposition hint:

- `USE_AS_IS` for candidate-only event recording if GY later admits an agent proposer. `REWORK_TO_FIT` for integration: a cycle controller must consume these `MethodPlan`s under verifier control and never treat them as authority.

### `scientist/agent/drafter_clients.py`, `_drafter_orchestrator.py`, `formalizer.py`, `critic.py`, `informed_critic.py`: Generator Organs

Status: Pass 3 done for generation-cycle relevant bodies.

**What they do from code read**

- `MockDrafterAgent.draft_policy(...)` is deterministic and domain-templated. It validates `ProblemFrame.frame_id`, increments a local counter, generates a draft id from `frame_id`, builds interventions from `_generate_interventions(...)`, and returns no `raw_llm_response` (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:93-133`). `_generate_interventions(...)` is hardcoded by `problem_frame.domain`: economic -> `tax_subsidy` plus `income_tax`, healthcare -> `healthcare_subsidy`, else `general_intervention` (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:135-190`). `refine_draft(...)` appends critique hints to the narrative and preserves interventions; it does not call a model (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:285-313`).
- `LLMDrafterAgent.draft_policy(...)` is a real LLM-backed generator organ: it builds a system prompt, serializes the `ProblemFrame`, prior drafts, data context, and web evidence, calls `self._llm.generate(..., response_format={"type": "json_object"})`, parses JSON, and constructs `DraftResult` from the model-provided narrative/interventions/rationale/references/confidence (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:328-420`). Its error path catches JSON/type/value failures and falls back to `MockDrafterAgent` (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:413-420`). Its `refine_draft(...)`, however, is deterministic hint-appending and preserves interventions, so it is not a model-backed revision organ (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:422-446`).
- `create_drafter_agent(...)` always creates an `LLMDrafterAgent` as the inner drafter, unless the caller provided no live LLM upstream; multipass mode is controlled by `POLISYOS_DRAFTER_MULTIPASS_MODE`, with `off` returning the single-pass LLM drafter and `active`/`shadow` wrapping it in `MultiPassLLMDrafter` (`policy-engine/src/polisyos/scientist/agent/drafter_factory.py:52-123`). The compatibility `drafter_node(...)` is explicitly no-op legacy (`policy-engine/src/polisyos/scientist/agent/drafter_factory.py:126-132`).
- `MultiPassLLMDrafter.draft_policy(...)` delegates pass 1 to the inner drafter, then can run deterministic checks, LLM critique passes, and an LLM consolidation pass; if the multipass pipeline errors it falls back to the inner single-pass drafter (`policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py:137-159`, `policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py:176-230`). Pass 1 calls `self._inner.draft_policy(...)` after optional constitution and RAG hints (`policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py:477-571`). Critique passes call `self._llm.generate(...)` and parse findings (`policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py:577-667`); consolidation also calls `self._llm.generate(...)` and parses a revised full draft (`policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py:673-756`).
- `MockFormalizerAgent.formalize(...)` does not call a model; it builds a `TrinityBundle` from the draft via `_build_trinity_bundle_from_draft(...)` (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1426-1444`). Its repair path inserts a hardcoded `tax_subsidy` repair when interventions are missing and fills `data_snapshot_ref` with `ZERO_ARTIFACT_REF` (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1445-1478`).
- `LLMFormalizerAgent.formalize(...)` is a real LLM-backed formalizer: it builds a Trinity prompt from draft narrative/interventions/rationale, calls `self._llm.generate(..., response_format={"type": "json_object"}, plugins=response-healing?)`, parses JSON, normalizes aliases, validates a `TrinityBundle`, and returns the normalized bundle (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1519-1636`). On repeated call/parse/schema failure it logs a degraded path and falls back to `MockFormalizerAgent` (`policy-engine/src/polisyos/scientist/agent/formalizer.py:1574-1664`).
- `MockCriticAgent.critique(...)` is deterministic: it validates structure, computes token-overlap alignment, completeness, optional numeric-rate warnings, then returns a `CritiqueReport` with `metadata["mock_generated"]=True` (`policy-engine/src/polisyos/scientist/agent/critic.py:147-227`, `policy-engine/src/polisyos/scientist/agent/critic.py:229-404`).
- `LLMCriticAgent.critique(...)` is a real LLM-backed critic: it serializes `ProblemFrame` and `TrinityBundle`, calls `self._llm.generate(..., response_format={"type": "json_object"})`, parses issues/scores/verdict/hint, normalizes stale contract issues, and returns a `CritiqueReport`; LLM call failure falls back to `MockCriticAgent`, while parse failure returns a parse-warning report rather than falling back (`policy-engine/src/polisyos/scientist/agent/critic.py:417-586`).
- `create_critic_agent(...)` selects `MockCriticAgent` only if `POLISYOS_CRITIC_MODE=mock` or no LLM client is supplied; otherwise it uses `LLMCriticAgent`, with optional `InformedCriticAgent` wrapper behind `POLISYOS_INFORMED_CRITIC_ENABLED` (`policy-engine/src/polisyos/scientist/agent/critic.py:665-704`).
- `InformedCriticAgent` is a deterministic wrapper around an inner critic. It adds pattern-memory, feasibility, budget, and norm pre-issues, then calls the inner critic and recomputes the verdict (`policy-engine/src/polisyos/scientist/agent/informed_critic.py:98-203`). It can call a feasibility probe to check selector attributes, matching counts, and budget impact (`policy-engine/src/polisyos/scientist/agent/informed_critic.py:240-356`).

**Blueprint runtime connection**

- `RunPolicyBlueprintRuntimeNode.execute(...)` is not a generator. It runs only in policy mode and only after `resolve_policy_runtime_request(...)` returns an existing `PolicyCandidateSchema` plus runtime evidence (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:314-337`; resolver at `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_request.py:57-101`).
- It builds a `ProductionPolicyEvaluationBackend` selection evaluation, persists evaluation/benchmark/evidence artifacts, constructs a `FunnelOrchestrator` with L0-L6 stages, and wires Level 6 to `_policy_promotion_runner(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:341-620`, `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:702-750`).
- `_PolicyRuntimeWorkflowEngine.run(...)` adapts the production runtime backend into medium/full fidelity funnel stages and carries provenance fields such as `policy_runtime_backend_kind`, `policy_runtime_promotable_source`, and degradation mode (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:246-289`).
- `_policy_promotion_runner(...)` rejects promotion without a promotion evidence bundle, Level-4 full evaluation, or promotable runtime provenance; otherwise it calls `run_promotion_with_evidence(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:1869-1918`, `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:2104-2144`).
- The Scientist policy-design workflow includes `run_policy_blueprint_runtime` after governance/causal/distributional/uncertainty and before policy translation/output bundle (`policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py:231-260`), and the builtins registry includes `RunPolicyBlueprintRuntimeNode()` (`policy-engine/src/polisyos/scientist/nodes/builtins/__init__.py:210-236`).

**Probe evidence**

Probe used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD/policy-engine:$PWD/policy-engine/src"` with a fake async client that records `generate(...)` calls and returns strict JSON.

```text
mock_drafter ['tax_subsidy', 'income_tax'] ['tax_subsidy', 'income_tax'] None
llm_drafter_calls 3 [{'type': 'json_object'}, {'type': 'json_object'}, {'type': 'json_object'}]
llm_drafter_varied llm_credit_guarantee credit_guarantee llm_cash_grant cash_grant
llm_drafter_bad_json_fallback True True tax_subsidy
llm_formalizer_calls 4 ['probe_llm_formalizer_content_used'] fallback_notes []
llm_critic_calls 1 critique_probe APPROVE [('budget_warn', 'feasibility', 'warning')] Add stress-tested fiscal guardrail
mock_critic True NEEDS_REVISION 1
```

Interpretation:

- LLM drafter is real and can return varied candidate organs from model JSON. The deterministic mock path remains hardcoded by domain and is used on bad JSON.
- LLM formalizer really consumes model JSON when valid. The bad JSON path retried until the fake client exhausted payloads, then fell back to deterministic formalization; four calls are expected because the second formalization attempt consumed one bad payload plus retry attempts.
- LLM critic really consumes model JSON. The supplied warning-only `REJECT` was normalized to `APPROVE` by `_normalized_critic_verdict(...)`, proving the critic output is not blindly authoritative (`policy-engine/src/polisyos/scientist/agent/critic.py:130-144`).

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL`: `LLMDrafterAgent`, `LLMFormalizerAgent`, `LLMCriticAgent`, multipass critique/consolidation hooks, and blueprint runtime's policy evaluation/funnel/promotion plumbing.
- `HARDCODED`: `MockDrafterAgent`, `MockFormalizerAgent` repairs, mock critic structural checks, and LLM drafter/critic deterministic fallback behavior.
- `implemented_but_not_orchestrated for GY generator`: real LLM organs exist, but Pass 1 proved plain policy text routes to verified-policy scripted generation by default; no canonical GY controller currently consumes these organs as NL -> DesignProblem -> diverse candidate set -> A-grounded cycle.

Disposition hint:

- `REWORK_TO_FIT` for GY-N2: reuse `LLMDrafterAgent` / `LLMFormalizerAgent` / `LLMCriticAgent` as the gateway-backed generator organs, but put them behind a canonical `DesignProblem` and authority boundary; do not reuse mock fallbacks as generation authority.
- `USE_AS_IS` for blueprint runtime as a post-candidate evaluation/funnel/promotion owner, not as generation.

Open questions:

- Pass 4 should decide the exact orchestration boundary: should LLM drafting happen before A-grounding with claims extracted afterward, or should retrieval/grounding constrain the drafter prompt before candidate creation?
- Pass 4 should decide whether blueprint runtime is in the GY promotion sequence or remains a separate Scientist evaluation/funnel surface. Pass 3 showed candidate value reuse works through direct Foundry/policy-runtime evaluation; it did not prove full blueprint runtime end-to-end on a GY-produced candidate.

### Bounded Stage-B Value Probe: Candidate -> Causal Method -> Policy Runtime Evaluation

Status: Pass 3 done for a minimal candidate/value path under Python 3.14 dependencies.

**What the code path does**

- `SyntheticControlMethod.pure_step(...)` is a real estimator. It validates one treated unit, at least two donors, a valid treatment time, fits donor weights through `_fit_scm_weights(...)`, computes treated-minus-counterfactual post effects, bootstraps confidence intervals when placebo count is small, and builds a `CausalEffectReport` (`policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:344-470`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:486-622`). It expects runner-injected params such as `__rng__` for bootstrap; a direct call without `__rng__` raised `KeyError: '__rng__'` at `policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:557`, which is evidence that the catalog runner normally supplies execution context.
- `_synthetic_control_output(...)` wraps the `CausalEffectReport`, its IR uncertainty envelope, warnings, determinism tier, weights, and counterfactual (`policy-engine/src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:209-228`; common wrapper at `policy-engine/src/polisyos/foundry/methods/catalog/causal/_common.py:136-151`).
- `ProductionPolicyEvaluationBackend.evaluate(...)` consumes a `PolicyCandidateSchema`, simulation metrics, causal effect report, uncertainty envelope, distributional/cross-graph/governance reports, and optional ambiguity certificate. It builds evidence-driven simulation metrics, evaluates them with `ObjectiveStack`, marks promotability only when full fidelity plus causal + uncertainty + governance + metrics/causal components are present, and returns a `PolicyRuntimeEvaluationArtifact` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:159-235`).
- `_build_evidence_driven_simulation_metrics(...)` uses the causal report point estimate as `policy_value`/`ate`, derives employment as `0.6 * point_estimate` when no distributional report exists, computes welfare from policy value/employment minus penalties, carries CI width from the causal report or uncertainty envelope, and records source components (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:1227-1332`).
- `build_policy_simulation_results(...)` surfaces `policy_value`, `ate`, bootstrap CI width/draw count/fidelity, objective channels, blocking reasons, backend kind, promotion source flag, degradation mode, and source components (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:461-530`).
- `ObjectiveStack.evaluate(...)` turns metrics/evidence into primary channels (`policy_value`, `employment`, `welfare`), secondary channels, penalties, hard constraints, feasibility, and metadata; statistical/transport constraints are driven by the search uncertainty envelope (`policy-engine/src/polisyos/scientist/policy_design/objectives.py:241-490`).

**Probe evidence**

Probe used a `MockDrafterAgent`/`MockFormalizerAgent` only to construct a minimal valid `PolicyCandidateSchema`, then computed a real SCM causal effect and fed it into `ProductionPolicyEvaluationBackend` with a bounded uncertainty envelope.

```text
deps {'econml': False, 'dowhy': False, 'cvxpy': False, 'statsmodels': True, 'jax': True, 'pymoo': True, 'scipy': True}
method_value synthetic_control success 3.0 (3.0, 3.0) bootstrap 0.333333
candidate stageb_probe_candidate tax_subsidy sha256:177f1d036fe
runtime_metrics {'policy_value': 3.0, 'employment': 1.8, 'welfare': 2.58, 'budget_penalty': 0.0, 'ate': 3.0, 'ci_width': 0.0}
evaluation True 3.0 2.58 {'policy_budget_constraint': <ConstraintStatus.FEASIBLE: 'feasible'>, 'compliance_constraint': <ConstraintStatus.FEASIBLE: 'feasible'>, 'equity_constraint': <ConstraintStatus.FEASIBLE: 'feasible'>, 'statistical_constraint': <ConstraintStatus.FEASIBLE: 'feasible'>, 'transport_constraint': <ConstraintStatus.FEASIBLE: 'feasible'>}
simulation_results {'policy_value': 3.000000031863655, 'ate': 3.000000031863655, 'bootstrap': {'ci_width': 0.1, 'draws': 500, 'fidelity': 'full'}, 'promotable_source': False, 'evaluation_degradation_mode': 'research_only', 'evaluation_source_components': ['causal_effect_report', 'uncertainty_envelope']}
provenance production full False research_only ('causal_effect_report', 'uncertainty_envelope') ()
```

Interpretation:

- A candidate-level value path is real under the active Python 3.14 dependencies: SCM computed an effect/CI/p-value, and the production backend converted it into policy value, welfare, objective channels, constraints, and simulation results.
- The result is not promotion-grade by itself. `promotable_source=False` and `degradation_mode="research_only"` because the probe intentionally omitted a governance report and the full evidence bundle required by `ProductionPolicyEvaluationBackend.evaluate(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:207-220`).
- DoWhy/EconML/CVXPY remain unavailable; statsmodels/JAX/pymoo/SciPy are available. Pass 2 already proved DoWhy/EconML methods fail with explicit unavailable-backend status and QP can fall back to SciPy.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL`: bounded candidate -> real causal method -> production policy runtime evaluation. This is stronger than Pass 2's method-level probe because it enters the candidate evaluation backend.
- `REWORK_TO_FIT`: the candidate in this probe came from mock drafting only to supply a valid object. GY-N5 should reuse the value backend and available method subset, but GY-N2/N3 must supply real generated and grounded candidates.
- `bridge_missing`: no scanned cycle currently wires the value output back to candidate revision or G4 promotion with complete grounded contracts.

Disposition hint:

- `USE_AS_IS` for the available-method value gate shape: synthetic control/DID/diagnostics/optimization fallback plus `ProductionPolicyEvaluationBackend` and `ObjectiveStack`.
- `REWORK_TO_FIT` for orchestration: feed real candidate/evidence/governance, preserve unavailable-method blockers, and make promotion-grade status explicit.

### Acquisition Execution Owners: Fabric Retrieval, Scholar Deep Search, OpenAlex/Data Forge, Control Workers

Status: Pass 3 done for the high-value acquisition-execution census.

**What the code path does**

- `RetrievalService.resolve(...)` is a real resolver over fastlane, optional catalog, and ExploreLane. It collects `FetchPlan`s from fastlane, catalog, or discovery, emits telemetry, and returns `ResolveOutcome` with selected plans and candidates (`policy-engine/src/polisyos/fabric/retrieval/service.py:230-385`). When unresolved needs remain and ExploreLane is enabled, it calls `self.discover(...)`, updates a local metadata index, and turns discovered `DiscoveryCandidate`s into executable `FetchPlan`s (`policy-engine/src/polisyos/fabric/retrieval/service.py:290-343`, `policy-engine/src/polisyos/fabric/retrieval/service.py:559-612`).
- `ExploreLaneDiscovery._discover_async(...)` executes bounded connector metadata discovery. It queries connector entries with `ConnectorCapability.CATALOG_BROWSE`, opens connector connections, iterates `connector.list_datasets(handle)`, optionally calls `connector.get_dataset_schema(...)`, scores descriptors against each `DataNeed`, and returns sorted `DiscoveryCandidate`s plus warnings and docs-fetched counts (`policy-engine/src/polisyos/fabric/retrieval/explore_lane.py:75-188`). This is real connector execution, not a fixture, though it depends on registered connectors/profiles.
- `FetchExecutor.execute(...)` is a real fetch execution path. It previews with `_fetch_preview`, optionally follows one fallback, then calls `_fetch` for full payload and creates a `DataContextMetric` from connector `FetchResult` row count, completeness, source lane, and sample rows (`policy-engine/src/polisyos/fabric/retrieval/executor.py:76-156`). `_fetch` gets the connector, resolves config, opens a connection, builds a typed `FetchRequest`, calls `connector.fetch(handle, request)`, records metrics, and releases the connection (`policy-engine/src/polisyos/fabric/retrieval/executor.py:204-260`). Persistence of large payloads is explicitly deferred to the ingestion pipeline even when `persist_payload=True` and `cas_root` exists (`policy-engine/src/polisyos/fabric/retrieval/executor.py:139-143`).
- `RetrievalService.execute_fetch_plans(...)` loops through plans, calls `self._executor.execute(...)`, accumulates successful `DataContextMetric`s into `DataContext`, and emits explore-lane promotion candidates when quality passes (`policy-engine/src/polisyos/fabric/retrieval/service.py:426-480`, `policy-engine/src/polisyos/fabric/retrieval/service.py:637-673`).
- Scholar deep search is also real acquisition/search execution. `ScholarDeepSearchService.deep_search(...)` builds or accepts a brief/query graph, loops query nodes, calls provider policy search, fetches and compresses result pages, builds source records and claim supports, and returns `WebEvidenceBundle` (`policy-engine/src/polisyos/scholar/search/service.py:214-478`). `ScholarDeepSearchService.persist_bundle(...)` writes the bundle as `scholar.web_evidence_bundle` to CAS (`policy-engine/src/polisyos/scholar/search/service.py:480-493`).
- `ProviderFailoverPolicy.search(...)` tries provider implementations in priority order and returns the first successful hit set or last error (`policy-engine/src/polisyos/scholar/search/providers.py:51-85`). `OpenAlexWorksProvider.search(...)` constructs the OpenAlex `/works` query, calls `_read_openalex_url_text`, reconstructs abstracts, normalizes works into `WebSearchHit`s, and applies constraints (`policy-engine/src/polisyos/scholar/search/providers.py:159-244`). This is network-backed execution, not a stub.
- `ScholarService.enrich_topic(...)` bootstraps missing seed sources by running `ScholarDeepSearchService.deep_search(...)`, persists the web evidence bundle when possible, turns usable sources into `SourceSpec`s, and then calls the Scholar enrichment orchestrator (`policy-engine/src/polisyos/scholar/api.py:34-104`). `ScholarService.submit(...)` delegates to `DeepResearchJobManager.submit(...)` for background deep-research jobs (`policy-engine/src/polisyos/scholar/api.py:140-164`).
- `DeepResearchJobManager.submit(...)` creates a job and starts `_run_job(...)` as an asyncio task (`policy-engine/src/polisyos/scholar/search/jobs.py:100-131`). `_run_job(...)` calls `self._service.deep_search(...)`, persists checkpoints during progress, persists a `scholar.academic_evidence` report, and returns/persists terminal status; on failure it still persists a partial bundle and evidence report (`policy-engine/src/polisyos/scholar/search/jobs.py:220-359`, `policy-engine/src/polisyos/scholar/search/jobs.py:361-400`).
- Data Forge/OpenAlex has a separate batch acquisition owner. `OpenAlexClient.list_works(...)` performs rate-limited aiohttp `/works` calls with retries/backoff and error handling (`policy-engine/src/polisyos/data_forge/domains/academic/openalex/client.py:64-134`). `harvest_all(...)` materializes already-selected OpenAlex works into raw snapshots and writes a stage manifest (`policy-engine/src/polisyos/data_forge/domains/academic/batch/harvester.py:50-120`). This is execution, but it is batch-pipeline execution, not workspace-loop acquisition execution.
- Runtime control workers do not provide an acquisition job kind. `ControlJobKind` is exactly `"workflow_run" | "natural_language_run" | "lex_pipeline"` (`policy-engine/src/polisyos/core/contracts/control.py:42-43`), and `RunLifecycleService._process_control_job(...)` dispatches only those three kinds; an unknown job kind raises (`policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py:1000-1114`). `natural_language_run` is explicitly completed as a legacy shadow with NL execution withheld (`policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py:1069-1103`).
- The workspace-loop API projection for `acquisition_required` says the next action is "Run an approved acquisition producer" but does not invoke one (`policy-engine/src/polisyos/runtime/http/services/control/workspace_loop_transition.py:419-460`). This reinforces Pass 2: the workspace loop terminates at acquisition, it does not close the loop.

**Probe evidence**

```text
fabric_execute_probe ok True 0.92
fabric_metric_probe sme_credit_gap 2 0.92 [{'year': 2024, 'sme_credit_gap': 12.5, 'request_page_size': None}, {'year': 2025, 'sme_credit_gap': 10.0, 'request_page_size': None}]
fabric_used_plan probe_plan_sme_gap False
```

The probe used a fake connector to avoid external I/O, but executed the production `FetchExecutor.execute(...)` body. It proves the Fabric path applies the preview gate and returns a real `DataContextMetric` from connector `FetchResult`, not an empty shell.

**Calls / called by**

- Fabric retrieval execution is called through retrieval services/API surfaces, not from `WorkspaceLoop._acquisition_plan_for_manifest(...)`. In this pass I found no direct caller that converts `AcquisitionPlanner.plan_from_required_data(...)` output into `DataResolveRequest`/`FetchPlan` execution.
- Scholar execution is called by `ScholarService.enrich_topic(...)` and `DeepResearchJobManager`, and can persist web/academic evidence, but it is not dispatched by `ControlWorker` and is not consumed by the workspace `ACQUISITION_REQUIRED` terminal.
- OpenAlex batch execution feeds Data Forge academic artifacts; it is not a synchronous "satisfy this missing distribution for this GY cycle" operation.

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL`: Fabric retrieval execution, Scholar deep search, Scholar background evidence jobs, OpenAlex provider/client, and Data Forge academic batch harvesting.
- `implemented_but_not_orchestrated`: none of these are wired to close the workspace loop's acquisition terminal.
- `PLAN_ONLY`: `runtime/quality/acquisition_planner.py` remains a costed gap/VOI terminal producer and explicitly does not satisfy evidence slots.

Disposition hint:

- `USE_AS_IS` for `runtime/quality/acquisition_planner.py` as gap/VOI/terminal planner, not execution.
- `REWORK_TO_FIT` for `fabric/retrieval/service.py`, `explore_lane.py`, and `executor.py` as executable metric/data acquisition substrate.
- `REWORK_TO_FIT` for `scholar/search/service.py`, `scholar/search/jobs.py`, `scholar/api.py`, and `scholar/search/providers.py` as bounded research/claim-evidence acquisition substrate.
- `REWORK_TO_FIT` for `data_forge/domains/academic/openalex/*` and academic batch as durable corpus/SKG population, not first-line synchronous cycle closure.
- `REWORK_TO_FIT` for runtime control dispatch if GY-N4 chooses durable acquisition jobs; current job kind set omits acquisition by construction.

Open questions for Pass 4:

- Which exact bridge artifact should close `ACQUISITION_REQUIRED`: `DataContext`, Scholar `WebEvidenceBundle` / `scholar.academic_evidence`, SKG claim refs, or a new small handoff envelope?
- Should acquisition execute inline in the workspace loop, as a durable control job, or as a Scholar/Fabric task with explicit re-entry?

### Grounding (A) Owners: Policy Grounding Matrix, Scholar Claim Support, SKG, Candidate Firewall, Span Entailment

Status: Pass 3 done for the cycle-relevant grounding connection.

**What the code path does**

- `build_policy_grounding_matrix_report(...)` is a real deterministic grounding report builder over final policy claims. It derives selected norm/data/method refs from Lex/Fabric/Foundry inputs, optionally normalizes a runtime claim registry, validates every claim with `_validate_claim(...)`, folds citation/source/causal validity reports, and returns status, normalized claims, issues, blocking count, and summary (`policy-engine/src/polisyos/scientist/validation/policy_grounding.py:1477-1688`).
- `_validate_claim(...)` checks claim family, major-claim grounding, family-required grounding, selected-ref membership, normative refs, numerical method-output agreement, optional claim-support semantics, and returns normalized claim grounding status plus issues (`policy-engine/src/polisyos/scientist/validation/policy_grounding.py:995-1292`). This is real validation, but it is validation over supplied refs and reports; it does not search for missing evidence itself.
- `normalize_policy_grounding_matrix(...)` recomputes grounding status from an existing report plus supplied evidence reports; it does not trust an existing status string (`policy-engine/src/polisyos/scientist/validation/policy_grounding.py:1691-1800`).
- The NL pipeline calls `build_policy_grounding_matrix_report(...)` after final policy claims, runtime claim registry, normative evidence, Fabric trace, Foundry method report, citation faithfulness, and source-quality reports exist, then persists/publishes `scientist.policy_grounding_matrix` (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7015-7124`). That is a real policy-output grounding gate, not an in-cycle candidate grounding search.
- Scholar deep search builds claim support links lexically. `_build_claim_supports(...)` ranks snippets by `lexical_support_score`, selects positive snippets, computes conflict score, assigns `supported` / `weakly_supported` / `contested` / `unsupported`, and stores requirement metadata in `ClaimSupportLink` (`policy-engine/src/polisyos/scholar/search/service.py:581-649`). This is real search-support summarization, but positive support here is lexical/support-link evidence, not by itself L2 authority.
- `normalize_scholar_academic_evidence_report(...)` fails Scholar evidence when citations lack runtime provenance, snippets are absent, freshness is stale/missing, conflicts are missing, or support requirements are unmet; status is `fail` if issues exist, `blocked` if literature deficit blockers exist, else `pass` (`policy-engine/src/polisyos/scholar/_impl/evidence.py:625-648`, `policy-engine/src/polisyos/scholar/_impl/evidence.py:651-690`, `policy-engine/src/polisyos/scholar/_impl/evidence.py:693-735`). This is a real evidence-quality gate.
- SKG read/search is real. `load_academic_skg_summary(...)` opens DuckDB read-only, lists tables, counts rows, and discovers latest version (`policy-engine/src/polisyos/data_forge/domains/academic/skg.py:38-74`, `policy-engine/src/polisyos/data_forge/domains/academic/skg.py:77-113`). `ScholarKnowledgeGraph.find_relevant_works(...)` performs text search and optional vector reranking; `get_parameter_prior(...)` computes weighted priors from simulation-ready or raw estimates; `find_causal_evidence(...)` queries exact or support-mode causal claims (`policy-engine/src/polisyos/data_forge/domains/academic/knowledge/search.py:76-239`). `SKGQuery.query_prior(...)` and `query_claims(...)` compute weighted priors and synthesized causal claim results from the store (`policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py:114-193`).
- SKG ingestion enforces span grounding before writing edge authority. `validate_causal_claim_span_grounding(...)` rejects missing/mismatched/unresolved spans, then calls span-claim entailment and returns `validated_supporting` only when the span supports the claim (`policy-engine/src/polisyos/ir/analytics/literature.py:899-971`). `skg_store` rejects claims whose grounding status is not `validated_supporting` before inserting SKG edges and carries `authority_tier`, `span_grounding_status`, and `grounding_ref` in quality signals (`policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:720-760`).
- `candidate_firewall.assert_l2_claim_authority_span_grounded(...)` is the strict authority boundary for web/OpenAlex/SKG-style L2 claim authority. It rejects raw web bundles/search hits; requires a `validated_span_grounding_ref`/grounding ref; requires a resolver-backed record; requires matching grounding ref, claim id/text, span text, `support_status` or `span_grounding_status == "validated_supporting"`, `authority_tier == "design_tier_l2"`, and `source_content_sha256`; then calls `_resolved_grounding_entails(...)` to run the span entailment judge (`policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:228-284`, `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:423-532`).
- `_resolved_grounding_entails(...)` imports `polisyos.scientist.validation.citation_faithfulness.evaluate_span_claim_entailment(...)`, builds a claim/evidence pair, and accepts only labels in `SPAN_ENTAILMENT_SUPPORT_LABELS` (`policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:539-593`). The entailment owner itself is fail-closed without a real production client: `evaluate_span_claim_entailment(...)` applies reject-only claim-support/lexical prefilters, creates the default span-support gateway client, returns `entailment_verifier_unavailable` if no production client exists, and only returns `supports` when the agent tool judgment is `entails` above threshold (`policy-engine/src/polisyos/scientist/validation/citation_faithfulness.py:297-385`, `policy-engine/src/polisyos/scientist/validation/citation_faithfulness.py:450-488`, `policy-engine/src/polisyos/scientist/validation/citation_faithfulness.py:537-704`, `policy-engine/src/polisyos/scientist/validation/citation_faithfulness.py:754-766`).
- GY Ring-1 agent records are explicitly candidate-only at the waist. `AgentDecisionRecord._enforce_candidate_firewall(...)` raises if `candidate_only` is not true (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:627-649`).
- Runtime production data path can populate `skg_db_path` and `skg_index_dir` from academic bundle manifests (`policy-engine/src/polisyos/runtime/http/services/control/production_data.py:233-258`), which makes SKG available to runtime surfaces, but this is configuration/defaulting, not a cycle call to ground a candidate.

**Probe evidence**

```text
raw_issues [{'code': 'web_bundle_l2_authority_blocked', ... 'message': 'Web bundles and raw search hits are candidate_unverified until a resolving, supporting span-grounding record validates them.'}]
no_resolver_issues [{'code': 'l2_claim_authority_grounding_unresolved', ... 'message': 'L2 claim authority requires a resolver-backed span grounding record.'}]
resolver_good claim-1
resolver_mismatch l2_claim_authority_grounding_unvalidated
```

The probe used the production `assert_l2_claim_authority_span_grounded(...)` / `l2_claim_authority_grounding_issues_for_payload(...)` bodies with a fake span-support client that returned the required tool-call judgment. It confirms the firewall is real and content-bound: raw web evidence fails, a validated-looking ref without resolver fails, resolver-backed matching span+claim passes, and claim-text mismatch fails.

**Calls / called by**

- NL policy-output quality calls the policy grounding matrix builder, then uses the grounding matrix in security assurance, decision artifact quality, semantic binding, provider quality, and progress reports (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7015-7124`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7238-7294`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7511-7567`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7593-7649`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:7651-7799`).
- Scholar/SKG acquisition can produce support/evidence/grounding records, and the candidate firewall can enforce their authority use.
- The GY workspace loop does not call the Scholar grounding search, SKG query, span-grounding validator, or candidate firewall as a candidate-grounding step. Pass 2 showed the workspace operation trajectory is BIND -> ESTIMATE -> VERIFY, with acquisition as terminal; Pass 3 found no bridge from a generated candidate into "ground this candidate's claims via Scholar/SKG/candidate_firewall, then revise/promote."

REAL vs SHADOW vs STUB vs HARDCODED vs DEAD:

- `REAL`: policy grounding matrix, Scholar evidence/support quality, SKG read/query, OpenAlex/SKG span-grounding ingestion gate, candidate firewall, and span entailment judge.
- `implemented_but_not_orchestrated`: the A-grounding machinery exists but is not in the GY generation cycle.
- `not enough for authority by itself`: Scholar lexical `ClaimSupportLink` and web bundles are candidate/support evidence; the firewall requires resolver-backed validated span grounding plus entailment before L2 authority.
- `gateway-dependent`: positive span entailment requires a production gateway client or explicit injected test client; without that, the entailment owner fails closed.

Verdict for the A grounds B hop:
- "Ground a candidate's claims" is reachable as a set of owners the cycle could call, but not reachable in-cycle today. The strongest existing enforcement is `candidate_firewall.assert_l2_claim_authority_span_grounded(...)` plus SKG span-grounding validation. The real gap is orchestration and bridge artifact: GY-N2/N3 need to call Scholar/SKG acquisition and the firewall before value/promotion, and carry the resulting validated refs into `PolicyCandidateSchema` / grounding matrix inputs.

Disposition hint:

- `USE_AS_IS`: `candidate_firewall` for authority boundary; `citation_faithfulness.evaluate_span_claim_entailment` for fail-closed span entailment; `policy_grounding` matrix for final policy-output validation.
- `REWORK_TO_FIT`: Scholar claim-support/web evidence and SKG query as grounding producers for generated candidates; they need a candidate-specific bridge and resolver-backed artifact.
- `REWORK_TO_FIT`: NL pipeline grounding matrix path as a consumer/gate after generated claims, not as the generator-cycle controller.

Open questions for Pass 4:

- What exact resolver should convert SKG/OpenAlex span refs into records consumable by `assert_l2_claim_authority_span_grounded(...)` during a GY cycle?
- Should candidate grounding happen before formalization, after formalization, or both: draft claim screening before expensive value, then final grounding matrix before promotion?

### DesignProblem Candidate Type Census: Runtime Intent, Scientist ProblemFrame, Verified PolicyRequestFrame, Trinity, PolicyCandidateSchema, S2 Input

Status: Pass 3 done for the canonical-problem assessment.

**What each type does**

- Runtime `PolicyIntentEnvelope` is a validated pre-routing intent capture, built by `build_policy_intent_envelope(...)`. It requires run/job/tenant identity, policy problem, desired outcome, proposed intervention, jurisdiction, target population, policy/data time, requested authority level, authoring provenance, and optional stakeholders/constraints/objectives/assumptions/evidence expectations. Validation maps requested authority to execution/validation/fallback profiles, computes requester preference, analysis independence, capture risk, and challenge-depth policy (`policy-engine/src/polisyos/runtime/quality/assurance_case.py:311-425`). It is persisted by the NL pipeline as `runtime.policy_intent_envelope` before building the Policy Design Case (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3128-3219`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3520-3563`).
- Scientist agent `ProblemFrame` is a lightweight immutable dataclass used by drafter/formalizer/critic protocols. Fields are `frame_id`, `domain`, `problem_statement`, actors, goals, constraints, success criteria, assumptions, context, and created timestamp (`policy-engine/src/polisyos/scientist/agent/protocols.py:74-97`). It is the input to `DrafterAgent.draft_policy(...)`, `DataNeedExtractorAgent.extract_data_needs(...)`, and PI agent `create_problem_frame(...)` (`policy-engine/src/polisyos/scientist/agent/protocols.py:237-318`). It has no authority profile, provenance spine, policy/data time split, acquisition obligations, or evidence-grounding contract by itself.
- Verified-policy `PolicyRequestFrame` is a persisted Pydantic contract for the `scientist_policy_verified` workflow. Fields are `request_id`, `policy_question`, jurisdiction, as-of, domain, target context, evaluation criteria, goals, constraints, notes (`policy-engine/src/polisyos/scientist/validation/policy_verified/models.py:25-41`). `build_policy_request_frame(...)` derives it from `ExperimentState.params` and optional research intent, with defaults like "UA" jurisdiction and a fallback generic policy question (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:78-131`). It is persisted/loaded by `persist_policy_request_frame(...)` / `load_policy_request_frame(...)` (`policy-engine/src/polisyos/scientist/validation/policy_verified/models.py:214-237`) and consumed by verified-policy planning/verification/drafting nodes (`policy-engine/src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py:72-73`, plus consumers listed by `rg` in planning/decide nodes).
- `PolicyRequestFrame` drives a scripted verified-policy path. `draft_policy_option_set(...)` always builds `verified_option_1` from the frame and verified claims, and optionally one `hypothesis_option_1` when unresolved critical gaps exist (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:457-515`). `formalize_policy_option_set(...)` turns the selected option into a `DraftResult` with a hardcoded `mechanism_type: "tax_subsidy"`, then calls `MockFormalizerAgent().formalize(...)` (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:518-558`). This is not a general DesignProblem generator.
- IR governance `ProblemFrame` is the rich Trinity "what" contract. It owns `problem_id`, formal `ProblemDomain`, objectives, KPIs, success criteria, hard/soft constraints, stakeholders, optional `NormativeFrame`, narrative, labels, and notes (`policy-engine/src/polisyos/ir/governance/problem_frame.py:296-373`). It is what `TrinityBundle.problem_frame` carries (`policy-engine/src/polisyos/ir/trinity/__init__.py:22-29`). It is formal and search/evaluation-friendly, but it is post-formalization; it does not capture raw NL provenance or requested authority by itself.
- There are two `TrinityBundle` concepts: the IR bundle embeds full `ProblemFrame`, `PolicySpec`, and `ModelSpec` objects (`policy-engine/src/polisyos/ir/trinity/__init__.py:22-29`), while `core.contracts.trinity.TrinityBundle` is a reference bundle with `ProblemFrameRef`, `PolicySpecRef`, and `ModelSpecRef` (`policy-engine/src/polisyos/core/contracts/trinity.py:72-99`). The embedded IR bundle is the one consumed by policy-design candidate/schema/search code.
- `PolicyCandidateSchema` is a Layer-B candidate wrapper around a `TrinityBundle`, not a problem type. It carries `candidate_id`, `trinity_bundle`, rollout/target population/parameter schedule/budget allocation/fallback variants/monitoring/evidence assumptions/transport assumptions/harm envelope/implementation notes/metadata (`policy-engine/src/polisyos/scientist/policy_design/schema.py:121-138`). Its validator checks internal candidate consistency: referenced interventions/parameters/constraints/metrics, rollout order, budget envelope, transport compatibility, and fallback variants preserving the same problem identity (`policy-engine/src/polisyos/scientist/policy_design/schema.py:139-267`). `from_trinity_bundle(...)` creates default rollout, parameter schedule, target population, and evidence assumptions from a Trinity bundle (`policy-engine/src/polisyos/scientist/policy_design/schema.py:293-339`).
- S2 `Layer2S2DesignSearchInput` is a shadow-search input, not a canonical problem. It carries case/intent/grammar/actor/domain/objective/construct/authority refs, `requested_posture="shadow"`, rule version, forced counterexample knobs, candidate-source authority, and omitted-grammar flag (`policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py:246-267`). It is explicitly tied to deterministic one-case S2 shadow design search.
- Workspace `run_intent(...)` takes a raw `dict[str, Any]`, not a typed DesignProblem. `WorkspaceIntentRunResult` carries terminal state, playbook trace, blockers, authority boundary, invocations, artifacts, method consumption, and production findings (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:297-315`). `run_intent(...)` selects a playbook from the dict, derives `workspace_id` from `policy_question`, treats `plan_policy_request` as out-of-scope, executes only bounded Foundry/governance-tail steps, and returns descriptive/candidate-only results (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1266-1395`).

**Probe evidence**

```text
intent_fields ['analysis_independence', 'challenge_depth_policy', 'desired_outcome', 'policy_problem', 'proposed_intervention', 'requested_execution_profile']
scientist_problem pf-probe economic ('increase lending',) {}
verified_request policy_request_probe Can UA adopt SME credit guarantees? UA ['increase lending']
shadow_input case-probe shadow deterministic_producer ('objective://increase-lending',)
trinity pf_probe policy_8620f13c3b ['tax_subsidy']
candidate candidate-probe policy_8620f13c3b_population 1 1 sha256:70b9b7ad02a2e
```

The probe confirms the surfaces are not interchangeable. Runtime intent carries authority/challenge semantics; Scientist `ProblemFrame` is light generator input; verified `PolicyRequestFrame` is a legal-request surface; S2 input is shadow/ref-only; Trinity/`PolicyCandidateSchema` are formal candidate layers. It also re-confirms the hardcoded mock path: a credit-guarantee draft became a `tax_subsidy` Trinity intervention via `MockFormalizerAgent`.

**Producers and consumers**

- Runtime intent producer: NL pipeline `_materialize_policy_intent_envelope(...)`; consumers: Policy Design Case profile, semantic/scorecard/quality surfaces (`policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3128-3219`, `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py:3520-3563`).
- Scientist agent `ProblemFrame` producer: PI agent or direct construction in agent circuit; consumers: drafter/data-need/formalizer/critic protocols and real/mock drafter organs (`policy-engine/src/polisyos/scientist/agent/protocols.py:237-318`; generator bodies read in Pass 3).
- Verified `PolicyRequestFrame` producer: `plan_policy_request` node via `build_policy_request_frame(...)`; consumers: legal candidate pack/source verification/source gap review/draft options/build report/formalize verified policy nodes (`policy-engine/src/polisyos/scientist/validation/policy_verified/service.py:78-131`; `rg` callers around `policy_request_frame_ref` in `scientist/nodes/builtins/*`).
- IR Trinity `ProblemFrame` producer: formalizer; consumers: `PolicyCandidateSchema`, hierarchical search, policy runtime, objectives/value backend.
- `PolicyCandidateSchema` producer: `PolicyCandidateSchema.from_trinity_bundle(...)`, hierarchical/search fixtures, blueprint/runtime paths; consumers: hierarchical search, policy runtime evaluation, promotion evidence.
- S2 input producer/consumer: PDC S2 shadow loop only; it is reference-level and shadow-posture by design.

Verdict:
- There is **no canonical DesignProblem today**. The closest reusable pieces are runtime `PolicyIntentEnvelope` for authority/provenance/time/request semantics, Scientist `ProblemFrame` for generator input, and IR governance `ProblemFrame` for formal evaluation/search semantics.
- GY-N1 should be `REWORK_TO_FIT` with a small canonical bridge type/envelope rather than adopting any one existing type as-is. The new/rewired DesignProblem must strangle the selector fork by carrying: raw NL/request provenance, requested authority/execution profile, jurisdiction/time split, objectives/constraints/stakeholders, evidence/acquisition expectations, grounding requirements, and a path to IR `ProblemFrame` once formalized.
- `PolicyCandidateSchema` should remain the candidate contract for Layer-B after generation/formalization; it should not become the problem type.
- Verified `PolicyRequestFrame` is useful for legal-request subflow but too narrow and too scripted for universal GY DesignProblem.
- S2 `Layer2S2DesignSearchInput` contributes discipline/refs but is shadow-specific and should not be promoted as canonical problem input.

Disposition hint:

- `PolicyIntentEnvelope`: `REWORK_TO_FIT` as the authority/provenance/time half of DesignProblem.
- Scientist `ProblemFrame`: `REWORK_TO_FIT` as generator-facing projection from DesignProblem.
- IR governance `ProblemFrame`: `USE_AS_IS` as formalized Trinity problem once candidate generation moves into formal layer.
- `PolicyRequestFrame`: `REWORK_TO_FIT` as a legal sub-projection, not universal input.
- `PolicyCandidateSchema`: `USE_AS_IS` as candidate/evaluation wrapper.
- `Layer2S2DesignSearchInput`: `REWORK_TO_FIT` for discipline/refs; keep shadow-specific input separate.

Open questions for Pass 4:

- Should the canonical DesignProblem be a new Pydantic public contract, or a runtime-quality bridge envelope that validates/projections into existing `PolicyIntentEnvelope`, Scientist `ProblemFrame`, and IR `ProblemFrame`?
- Which selector should be strangled first: NL plain policy text selecting `scientist_policy_verified`, or workspace `run_intent` accepting raw dicts?

### Remaining Governance / Value-Axis Owners and Foundry Method Selection

Status: Pass 3 done for cycle-relevant S6/S7/S8, scorecard aggregation, and method registry selection.

What the code does:

- `blind_spot_firewalls.py` is a real fail-closed S6 axis firewall producer, not a prose-only contract. `evaluate_measurability_adequacy(...)` validates construct rows, rejects proxy/value laundering when a pass is declared over invalid proxy/missing disclosure, and returns `pass` / `limit` / `block` records with authority boundaries (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:540-632`). `evaluate_aggregation_validity(...)` blocks scope drift / Simpson/ecological risk without proof (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:635-702`). `evaluate_capacity_feasibility(...)` raises when required capacity is absent/copied/unsupported without an obligation, then emits capacity-building obligations and a disposition (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:705-790`). `evaluate_mandate_legitimacy(...)` rejects LLM-origin mandate/objective authority without provenance and distinguishes blocked/limited/pass mandate rows (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:792-869`). `evaluate_strategic_response(...)` does not solve rich equilibrium; it gates response-model validity, emits post-intervention DGP updates when available, and blocks system-dynamics-required unresolved channels (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:872-984`). `build_s6_blind_spot_firewall_report(...)` aggregates the five axes, computes `blocked` / `limited` / `clear_fail_closed`, and materializes bridge consumer rows, S2-style constraint-store updates, C3 authority-dimension rows, blocking/limiting refs, regime reissue flag, and false-clear penalty (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:987-1090`).
- `mandate_bounded_delegation.py` is a real S7 decision-rights and responsibility-integrity producer. `build_governance_decision_class_registry(...)` constructs fixed governance decision classes and roles for `a_spec_gap`, `budget_use`, `acquisition`, `final_choice`, `value_authorization`, `mandate_boundary`, `data_access`, and `routine_in_envelope` (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:362-393`). `build_decision_rights_matrix(...)` and `build_delegation_contract(...)` bind those classes to required roles, mode, budget refs, mandate refs, and governed-pilot authority boundaries (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:396-475`). `build_human_decision_request(...)` derives whether critical decisions require a request, sets five-rights requirements, options, limitations, and disconfirming refs (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:478-555`). `record_human_decision(...)` raises on wrong role, disallowed action, delegated autonomy without mandate, or "oversight theater" missing evidence/accountability/five-rights checks; otherwise it returns a passed `HumanDecisionRecord` (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:558-631`). `evaluate_delegation_for_case(...)` is a corpus/probe evaluator that blocks high-stakes `ai_first`, blocks delegated autonomy without mandate, and computes a `DelegationIntegrityReport` (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:634-715`). `s7_delegation_integrity(...)` computes precision/recall/pass-rate and false-clear counts from probe rows (`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py:718-758`).
- `value_choice_provenance.py` is a real S8 value-authority firewall and provenance builder, not a value estimator. `build_authorized_value_schedule(...)` requires S6 mandate pass, authorized value source, and valid S7 value-authorization refs when present; it raises P20/P22/P26 errors otherwise (`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:310-370`, `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:653-692`). `build_shadow_scenario_value_schedule(...)` deliberately emits `shadow_scenario_only` with `ranked_recommendation_authority` denied (`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:373-406`). `build_pareto_archive(...)` blocks `ranked_with_authorized_values` without a non-shadow value schedule and maps foundry/frontier payload refs into a replayable archive (`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:419-479`). `build_value_choice_provenance_record(...)` rejects S7 decision refs as a substitute for S8 value authority and forces conflict rows into `contested_multi_principal` with arrow-disclosure requirements (`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:482-499`, `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:695-705`). `s8_value_provenance_integrity(...)` computes completeness and false-clear counts for LLM/corpus/mandate/Pareto/multi-principal/S7/shadow/arrow probes (`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py:566-608`).
- `scorecard.py` is the global quality aggregation gate, not a candidate generator or value estimator. `normalize_quality_evidence(...)` normalizes production data quality, normative evidence, Data Forge snapshot binding, Fabric retrieval, Foundry method report, Scholar evidence, policy grounding matrix, conflict, and privacy reports before scorecard use (`policy-engine/src/polisyos/runtime/quality/scorecard.py:1089-1163`). `build_quality_scorecard(...)` assembles a large ordered gate list from execution/materialization, LLM, calibration, authority contracts, reports, Data Forge, security/compliance, phase barriers, effective mode, Lex, semantic binding, hypothesis firewall, Scholar, assurance case, PDC profile, acquisition planner, cost, complexity, source-truth conflict, closeout, legacy migration, attestation, and status-envelope gates; then it computes blocking failures, quality status, performance status, warnings, soft-gate telemetry, approval readiness, stage scores, overall score, refs, and returns a scorecard payload (`policy-engine/src/polisyos/runtime/quality/scorecard.py:9955-10404`).
- Foundry method selection is registry-based and explicit/default-driven in the workspace, not an autonomous GY candidate-value chooser. `MethodRegistry.register(...)` and `register_lazy(...)` validate `MethodSignature` / `MethodMetadata`, record lifecycle/audit entries, and index methods (`policy-engine/src/polisyos/foundry/methods/selection/registry.py:491-626`). `MethodRegistry.get(...)` resolves exact FQN or versioned short/base names and lazy-loads entries (`policy-engine/src/polisyos/foundry/methods/selection/registry.py:680-729`, `policy-engine/src/polisyos/foundry/methods/selection/registry.py:781-799`). `query(...)` and `snapshot(...)` support deterministic discovery/inspection (`policy-engine/src/polisyos/foundry/methods/selection/registry.py:805-855`, `policy-engine/src/polisyos/foundry/methods/selection/registry.py:950-963`). `get_registry(...)` returns a context-local registry when present, otherwise the singleton (`policy-engine/src/polisyos/foundry/methods/selection/registry.py:1047-1057`). `ensure_all_methods_registered(...)` bootstraps builtins/entry-points/dev scan into the registry (`policy-engine/src/polisyos/foundry/methods/catalog/__init__.py:117-126`).
- Workspace `run_intent(...)` selects the causal method by `intent["causal_method_fqn"]` or the fixed default `causal.inference.synthetic_control@1.0.0`, writes it into `ExperimentState`, and uses fixed synthetic observational data/graph defaults when the intent omits them (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:1036-1064`). The live causal node then calls `ensure_causal_methods_registered()`, loads observational data, builds a `JobSpec(method_fqn=...)`, and calls `run_job(...)` (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:392-415`). The workspace also has `_foundry_registry_estimate_candidates(...)` to list estimate/measurement-like registry candidates for reporting/discovery, but the active loop does not use that list to choose a method (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:630-659`).

Probe evidence:

```text
probe_start governance_registry
causal_inference_count 5 ['causal.inference.dowhy_identify_estimate@1.0.0', 'causal.inference.dowhy_identify_estimate@2.0.0', 'causal.inference.regression_discontinuity@1.0.0', 'causal.inference.structural_time_series@1.0.0', 'causal.inference.synthetic_control@1.0.0']
synthetic_control_registered SyntheticControlMethod numpy ['causal', 'estimation', 'panel', 'quasi-experimental', 'synthetic-control']
optimization_count 18 ['optimization.auction.public_reserve_auction@1.0.0', 'optimization.bilevel.bilevel@1.0.0', 'optimization.bilevel.bilevel@1.1.0', 'optimization.combinatorial.knapsack@1.0.0', 'optimization.combinatorial.vehicle_routing@1.0.0', 'optimization.convex.quadratic_program@1.0.0']
s6_proxy_launder_block P18StreetlightMeasurabilityError P18 streetlight proxy/value laundering: proxy or unmeasured value construct requires value
s6_report clear_fail_closed 12 ['KNOWLEDGE.epistemic_regime', 'ACTOR.value_choice_provenance', 'INTERVENTION.targeting']
s7_request final_choice governance_board request_human_decision request_driven
s7_wrong_role_block P26ResponsibilityIntegrityError wrong_role_approval
s8_llm_value_block P20NormativeChoiceError P20 unauthorized value source: llm_candidate
s8_schedule_archive authorized ranked_with_authorized_values ['candidate-a']
```

Calls and callers:

- S6/S7/S8 are value/governance axis producers consumed by PDC/readiness/scorecard-style governance surfaces; S6 explicitly emits `BlindSpotConstraintStoreUpdate` rows that are "later mapped into the S2 constraint store" by contract, but no Pass 3 body shows the current GY workspace loop ingesting those updates into an executable revision cycle (`policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:485-501`, `policy-engine/src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:1026-1065`).
- Scorecard consumes many normalized reports but is downstream aggregation. It should not become GY-N3 controller or GY-N5 value producer.
- Foundry registry is reached from `run_causal_evaluation`, and the workspace loop reaches that node through the Phase-2 playbook. Method selection itself is explicit/default FQN, not generated from DesignProblem/candidate objective.

Verdict:

- `blind_spot_firewalls.py`: `REAL` governance/value-axis firewall and constraint-injection producer; `implemented_but_not_orchestrated` for an in-cycle revise loop.
- `mandate_bounded_delegation.py`: `REAL` human decision routing/responsibility-integrity owner; not a cycle controller.
- `value_choice_provenance.py`: `REAL` value-authority provenance gate; not a forecast/value estimator.
- `scorecard.py`: `REAL` global aggregation/closeout gate; not candidate generator/reviser/value producer.
- Foundry method registry: `REAL` registry/discovery/lookup mechanism. In the workspace value path, selection is `HARDCODED/EXPLICIT_DEFAULT` unless the caller supplies `causal_method_fqn`.

Disposition hint:

- `USE_AS_IS` for S6/S7/S8 as authority/gate producers and for scorecard as downstream closeout.
- `REWORK_TO_FIT` for GY-N3/N7: a real cycle must consume S6 constraint updates, S7 decision routes, S8 value authorization, and scorecard gates at the right lifecycle points; current owners emit correct artifacts but do not drive iteration.
- `REWORK_TO_FIT` for GY-N5 method selection: reuse registry and reachable methods, but add a DesignProblem/candidate-aware method-selection policy or explicit blocker. Do not rely on the current default `synthetic_control` as universal value method.

Open questions for Pass 4:

- Which exact cycle artifact should carry S6 constraint-store updates into the revision controller: S2-compatible constraint store, workspace blocker packet, or a new GY cycle ledger?
- Should GY-N5 method selection use existing `foundry/methods/selection/advisor.py`, a narrower rule table, or explicit method FQNs declared by the DesignProblem?
- How much of `build_quality_scorecard(...)` should be required before B->A promotion versus only at publication/closeout?

### Python 3.13 Isolated Dependency and Runtime Experiment

Status: Pass 4 done. The two venvs were created only under `/tmp`; no shell activation or install touched the supported Python 3.14 environment.

**Declared compatibility and experiment setup**

- The product itself requires Python `>=3.14,<3.15` (`policy-engine/pyproject.toml:5-17`), and the checked lock declares `==3.14.*` (`policy-engine/uv.lock:1-3`). A normal `uv` 3.13 sync is therefore unsupported before any causal dependency is considered. `uv venv --python 3.13` emitted the incompatibility warning, and the editable base/test install required pip's explicit `--ignore-requires-python` escape hatch.
- The dependency markers are narrower than the shorthand carried from Pass 3: EconML is admitted below 3.14 (`policy-engine/pyproject.toml:86-90`); the **pinned DoWhy compatibility pair** is admitted only below 3.13 and couples DoWhy 0.13 to `cvxpy<1.5` (`policy-engine/pyproject.toml:83-91`). Separately, the optimization extra requires modern `cvxpy>=1.8.1` on every supported interpreter (`policy-engine/pyproject.toml:80`), and `research` includes both causal-full and optimization-advanced (`policy-engine/pyproject.toml:147-158`). Thus “CVXPY is excluded on 3.13” was too broad: only the old DoWhy-compatible CVXPY line is excluded.
- A full `.[test,research]` install first failed with `OSError: [Errno 28] No space left on device` while downloading the research extra's transitive Torch. This did not install a partial environment. The bounded experiment then installed `.[test]` plus only statsmodels, EconML, and modern CVXPY. Because the 3.14 lock cannot resolve for 3.13, this necessarily produced a fresh dependency set (for example JAX 0.10.2); it is compatibility evidence, not reproducibility evidence.

**Install/import/compute results**

```text
python 3.13.3 numpy 2.4.6
jax_import 0.10.2 jax_op [3.0, 6.0]
statsmodels_import 0.14.6 params [1.0, 2.0] rsquared 1.0
cvxpy_import 1.9.2 status optimal x 2.0 value 0.0
econml_import 0.16.0 linear_dml_effect [2.006564, 1.999496, 2.016666, 2.0041, 2.008821]
dowhy_failed ModuleNotFoundError No module named 'dowhy'
```

- EconML 0.16 had a CPython-3.13 arm64 wheel, imported, and `LinearDML.fit(...)` recovered the planted treatment effect of 2.0. This is a real unlock on 3.13.
- Modern CVXPY 1.9.2 had a CPython-3.13 wheel, imported, and solved `min (x-2)^2, x>=0` to `x=2`, status `optimal`. It is already reachable through `optimization-advanced`; no interpreter downgrade is required for modern CVXPY.
- The project-pinned `dowhy>=0.13,<0.14` did not install on 3.13. Pip reported that DoWhy 0.13 requires Python `<3.13` and that no matching distribution exists. This confirms the project marker empirically.
- A separate throwaway 3.13 venv proved that the newer, currently unadopted DoWhy 0.14 **does** install with modern CVXPY and compute:

```text
dowhy_import 0.14
dowhy_identified EstimandType.NONPARAMETRIC_ATE backdoor True
dowhy_estimate 1.499828
```

  The code built a `CausalModel` with one observed common cause, identified a backdoor estimand, and recovered a planted effect of 1.5. Therefore Python 3.12 is the only way to obtain the **current pinned DoWhy 0.13 + `cvxpy<1.5` contract**, but it is not the only interpreter capable of DoWhy/CVXPY in general; adopting DoWhy 0.14 would be a separate dependency/API migration requiring its own verification.

**Regression result: supported code that breaks on 3.13**

- The 3.13 JAX and statsmodels smokes pass, and a non-Foundry core/agent subset passed 10 tests (`test_search_contract.py` plus `test_workspace_agent_proposal_bridge.py`).
- The workspace/value subset does not merely fail an optional method: it fails during collection. `ProcurementGraphState` uses jaxtyping annotations such as `Int[Array, n_edges]` and `QueueEventCalendarState` uses `Float[Array, n_events]` without quoted dimensions or `from __future__ import annotations` (`policy-engine/src/polisyos/foundry/contracts/state.py:11-28`, `policy-engine/src/polisyos/foundry/contracts/state.py:72-87`). Python 3.13 evaluates `n_edges` while constructing the class and raises; Python 3.14's deferred annotation semantics import the class successfully.

```text
3.13 collection: NameError: name 'n_edges' is not defined
path: foundry/contracts/state.py:19 while importing workspace/Foundry causal registry
3.13 Stage-B import: stage_b_blocked NameError name 'n_edges' is not defined
3.14 identical targeted subset: 45 passed (one JAX deprecation warning)
```

- The compared subset was `test_workspace_loop.py`, workspace Foundry-consumption integration tests, synthetic-control tests, and the core search-contract tests. This proves that the Pass-3 Stage-B path and honest workspace backbone currently depend on the 3.14 language baseline; obtaining EconML on 3.13 would break the very value/cycle surface it is meant to enrich unless the symbolic annotation class is repaired across Foundry and then reverified.

**Verdict and disposition**

- Recommendation for GY-N5: **stay on Python 3.14** and use the already-real statsmodels/JAX/SciPy/pymoo path. It is the declared, locked, and working baseline. Do not move the cycle to 3.13 merely to add EconML: the repository cannot sync normally there and the Foundry/workspace/Stage-B import path breaks.
- Python 3.13's potential benefit is EconML 0.16 plus, after a dependency migration, DoWhy 0.14; its cost is changing the product baseline/lock and repairing/retesting Python-3.14-dependent annotations. This is a future platform migration, not a GY-N5 fallback.
- Python 3.12 is required only if preserving the existing DoWhy 0.13/old-CVXPY compatibility contract. It moves still farther from the supported baseline and was not justified by this value path, which already computes on 3.14. `REWORK_TO_FIT` any dependency migration; `USE_AS_IS` the available 3.14 method subset.

Open question: if DoWhy is later load-bearing, evaluate a DoWhy 0.14 migration on 3.14 first. The successful 3.13 smoke proves package capability, not compatibility with PolicyOS method adapters.

### World Representation, Data Binding, and Joint Simulation

Status: Pass 4 done for the north-star world-model and joint-simulation question.

#### `foundry/agent_sim/world`: real synthetic benchmark DGP, not the production world model

- `SyntheticWorld` chooses one of four fixed materializers from `_TEMPLATE_REGISTRY`, materializes latent and observed tables plus a truth registry, and filters truth targets according to the supplied DGP specification (`policy-engine/src/polisyos/foundry/agent_sim/world/world.py:30-53`, `policy-engine/src/polisyos/foundry/agent_sim/world/world.py:94-138`). Its `sample(...)` method returns slices of the already-materialized observed or latent table; it is not learning a world from production data (`policy-engine/src/polisyos/foundry/agent_sim/world/world.py:140-218`).
- `SyntheticWorldDGP` explicitly parameterizes synthetic family, sample size, seed, treatment effect, confounding, missingness, measurement, sampling, and a small benchmark intervention specification (`policy-engine/src/polisyos/foundry/agent_sim/world/models.py:123-203`). `WorldArtifact` hashes and references observed data, latent data, truth, and replay configuration (`policy-engine/src/polisyos/foundry/agent_sim/world/world.py:262-327`). That is a substantive reproducible test-world contract, but its source is a template plus declared parameters, not Fabric/SKG observations.
- Caller search found product use only in Foundry validation/phase-zero closure and tests; no workspace, Scientist policy-design, or GY controller consumes `SyntheticWorld`. Verdict: **REAL synthetic benchmark/test world; SHADOW relative to the north-star production world model**. Disposition: `USE_AS_IS` for semantic evaluation and adversarial test generation; do not promote it to the production world owner.

Probe, using the supported 3.14 environment:

```text
synthetic_world sw.phase0.cross_sectional.calibrated.v1 cross_sectional 5 12 17
synthetic_columns ['base_weight', 'classification_probability', 'feature_0', 'feature_1', 'feature_2', 'feature_3', 'inclusion_probability', 'label', 'mediator', 'outcome']
synthetic_causal_targets ['causal.atc', 'causal.ate', 'causal.att', 'causal.cate', 'causal.ite', 'causal.mediation.direct_effect', 'causal.mediation.indirect_effect', 'causal.propensity']
synthetic_artifact 91 sw... replay_key synthetic-world://observed/... synthetic-world://truth/...
```

#### The production-facing world is split across four owners

- Fabric data does become executable state. `build_input_bindings(...)` loads a `DataSnapshot`, registry, and payload, validates prepared binding rules, builds or loads a base `GlobalState`, materializes source fields through transforms into registry slots, and persists the state snapshot, bindings, and report (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:69-236`). `_build_base_state(...)` infers entity sizes when no state snapshot exists; `_materialize_state(...)` fails missing required rules and warns/skips optional misses (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:541-661`). The execute path consumes this bound `GlobalState`; `data_snapshot_ref` remains lineage rather than being queried during simulation (`policy-engine/src/polisyos/foundry/execute/api.py:304-327`). This is a **REAL observed-data-to-state bridge**, not causal-structure discovery.
- The causal graph is a separate IR artifact. `SCMFitData` requires both a data matrix/column names and an already supplied `CausalGraphModel`; the fitter does not discover the graph (`policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py:498-577`). `HybridSCMFit.pure_step(...)` projects that graph to a DAG, tries DoWhy when available, falls back to NumPy, fits linear mechanisms for non-root nodes, and combines data fits with literature priors (`policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py:260-486`). On 3.14 this mechanism-fitting path is real through NumPy, but the graph skeleton and root-variable mechanisms remain upstream obligations.
- The executable representations are then `GlobalState` plus Foundry program graph for policy mechanisms, and `StructuralCausalModelSpec`/`NCMSpec` for causal counterfactual computation. There is no code-read owner that unifies Fabric/SKG facts, the inferred/curated causal graph, fitted mechanisms, policy slots, and deployment observations into one versioned, growing north-star world model.

Verdict: **PARTIAL, fragmented world-model substrate**. `GlobalState` binding, IR causal models, and synthetic evaluation worlds are real and reusable, but the north-star production world model has `producer_missing`/`bridge_missing` as a single lifecycle capability. Disposition: `REWORK_TO_FIT` by defining a canonical world-model envelope over these owners; do not build a second state engine.

#### Foundry program graph: real multi-mechanism execution on one state step

- Lowering iterates over every enabled Trinity intervention, resolves its runtime support and mechanism parameters, and emits one `LoweredMechanism` per intervention (`policy-engine/src/polisyos/foundry/compile/_lowering.py:156-287`). Graph construction creates mask/apply nodes for every lowered mechanism, adds slot dependencies, and joins writers through merge and constraint-check nodes (`policy-engine/src/polisyos/foundry/compile/_graph.py:20-105`). Topological ordering rejects cycles (`policy-engine/src/polisyos/foundry/compile/_graph.py:108-122`).
- The executor runs the graph against one visible `GlobalState`. Dependent nodes flush upstream patches before running; independent writers accumulate patch records that the merge node combines, after which constraints are checked (`policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py:114-470`). Mechanism nodes apply schedules and masks, instantiate the mechanism, emit patches, and may emit welfare reports (`policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py:842-984`).
- `execute(...)` runs the request's `current_step` once. `max_steps` bounds the request but is not an internal policy-horizon loop; the optional feedback/fixed-point path handles a program-level feedback request, not a general outer simulation horizon (`policy-engine/src/polisyos/foundry/execute/api.py:148-223`, `policy-engine/src/polisyos/foundry/execute/api.py:782-830`). Scientist's `RunSimulationNode` constructs one `ExecuteRequest` and calls Foundry once (`policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py:194-320`).

Probe: a real Trinity program with a 10% income tax and 5% subsidy compiled to two mechanisms and executed both against the same two-agent state:

```text
program_joint_compile True mechanisms ['tax_subsidy', 'income_tax']
program_joint_edges [('op.mask.subsidy','subsidy','depends_on'), ('op.mask.tax','tax','depends_on'), ('subsidy','op.merge_state','depends_on'), ('tax','op.merge_state','depends_on'), ('op.merge_state','op.check_constraints','depends_on')]
program_joint_metrics {'applied_nodes': 2, 'patch_ops': 2, ...}
program_joint_income [950.0, 950.0] balance 100.0
```

Verdict: **REAL joint mechanism application at one state step**, including writer merge and dependency ordering. It is not by itself a multi-period general-equilibrium simulation. Disposition: `USE_AS_IS` as the policy-mechanism execution substrate; `REWORK_TO_FIT` the missing horizon/controller and world-model adapter.

#### NCM and coupled simulation: real joint organs, not a GY whole-design path

- `NCMQueryData` accepts multiple intervention worlds, and each intervention is a mapping that may set several variables (`policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:101-145`). `_predict_from_abducted(...)` applies every key in one intervention mapping and then propagates structural equations in topological order; `_parallel_worlds(...)` reuses common exogenous noise across all intervention worlds (`policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:691-766`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:805-890`). Cyclic NCMs are explicitly unsupported rather than silently approximated.
- A probe supplied the nonlinear equation `Y = X1 * X2 + noise`. The engine recovered the non-additive joint term, proving it is not summing per-intervention effects:

```text
ncm_joint_worlds 4 32
ncm_joint_means [({'X1':0,'X2':0}, -0.160933), ({'X1':1,'X2':0}, -0.160933), ({'X1':0,'X2':1}, -0.160933), ({'X1':1,'X2':1}, 0.839067)]
ncm_joint_interaction 1.0
ncm_warnings []
```

- The adjacent GCM query path is narrower: `CausalQuery` has one `treatment_variable`, and the query executor applies an intervention only at that node (`policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:473-566`). Thus GCM fitting is reusable for value, but this query owner is single-treatment.
- `CoupledPolicySimulationEstimator` creates `GlobalState`, a queue runtime, `QueueDESKernel`, `UnemploymentClaimABMKernel`, and a `DefaultPolicyCoupler`, then advances the coupled system for `n_steps` (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:57-145`). This is real feedback for the hardcoded unemployment-claims/benefit domain. Its ABM proof wrapper is candidly stubbed: `_abm_result_stub(...)` fabricates stable refs and marks `phase4_abm_result_stub` (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/dynamics.py:33-40`). Verdict: **REAL domain-specific coupled dynamics with a STUB result/proof wrapper**, not a universal many-policy simulator.

Disposition: `USE_AS_IS` the NCM common-noise/joint-intervention engine and coupled kernels where their contracts fit; `REWORK_TO_FIT` adapters from policy intervention atoms and a real result artifact. Do not infer universal coverage from the unemployment example.

#### `CompositionCertificate` and GY-G recursion: gate interactions; do not simulate them

- `compose_subdesigns(...)` requires an observed coupling graph. Missing/unknown coupling fails closed with a discovery obligation (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:1255-1357`). Feedback returns `requires_system_dynamics` and explicitly requires a joint sub-workspace or fixpoint/equilibrium/simulation operation; it does not invoke one (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:1358-1399`). Shared-resource coupling returns `requires_capacity_aggregation`, whose resolution option is explicitly `surface_out_of_scope` (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:1401-1444`). Only the no-feedback/no-shared-capacity route reaches authority-flow and emergent-claim grounding (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:1446-1533`).
- The workspace recursive fixture path manufactures an observed coupling graph with `interaction_edges=()` for every case, runs fixed child fixtures, passes no parent claims, and emits a certificate (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:865-951`). `run_recursive_case(...)` therefore demonstrates typed recursive composition of declared-independent children; it neither discovers interactions nor runs joint dynamics.

Verdict: `CompositionCertificate` is a **REAL fail-closed interaction/authority gate**, not a pairwise effect calculator. GY-G is a **HARDCODED depth-2 independent-fixture demonstration**. Disposition: `USE_AS_IS` the classification, obligation, and certificate semantics; `REWORK_TO_FIT` the recursive fixture bridge and strangle it once a real cycle controller supplies observed coupling graphs and invokes the appropriate joint simulator.

#### Whole-picture verdict for north-star binding constraint 3

Joint simulation is **PARTIAL, not greenfield and not complete**:

1. Foundry can execute many compiled policy mechanisms against a shared state at one step.
2. The NCM method can compute genuinely nonlinear multi-variable `do()` worlds with shared exogenous noise.
3. A domain-specific DES/ABM owner can run feedback over time.
4. The composition owner correctly refuses to launder feedback/shared-resource systems through independent composition.

The missing capability is the bridge/controller that maps a generated set of policy atoms into one data-bound, versioned causal world; selects a compatible joint engine; runs individual, interaction, and whole-design horizons; carries uncertainty and coupling evidence back to the candidate; and re-enters revise/promote. This is `bridge_missing` plus `consumer_missing`, not “no simulator exists.”

Open questions for task design: whether the canonical joint engine should be Foundry program execution backed by NCM mechanisms, or whether NCM remains the counterfactual value engine beside a separate state-transition simulator; and how cyclic/general-equilibrium obligations are discharged when the acyclic NCM and topologically sorted program graph intentionally reject cycles.

### Intervention Atom Census: Trinity Action vs Causal `do()`

Status: Pass 4 done. The atom is **PARTIAL and split**, not absent.

#### Trinity `InterventionSpec`: executable policy-action nucleus

- `InterventionSpec` carries `kind` (mechanism registry key), target `SelectorExpr`, `ScheduleSpec`, parameter values, priority/enabled state, legal provision ref, target population/sector/region annotations, measurement expectations, identification mode, and strategic-response channels (`policy-engine/src/polisyos/ir/governance/policy_spec.py:73-108`). `PolicySpec` groups up to 100 interventions, explicit mechanism bindings, and tunable `ParameterSpec` rows (`policy-engine/src/polisyos/ir/governance/policy_spec.py:192-244`). `ParameterSpec.param_path` points into intervention parameters and carries bounds/tunability (`policy-engine/src/polisyos/ir/governance/policy_spec.py:161-189`).
- The target is a **population/entity selector**, not the state variable that the mechanism changes. The direct state footprint is resolved later: `link_trinity(...)` uses `intervention.kind` to fetch a `MechanismTypeSpec`, validates parameters/selectors, resolves mechanism read/write slots, and emits a `LinkedIntervention` with those slots and inclusive schedule bounds (`policy-engine/src/polisyos/ir/linker/_trinity_linker.py:89-178`). The default mechanism registry makes the semantics concrete: `tax_subsidy` reads `agents.income` and writes `agents.income` plus `government.balance`; `income_tax` reads `agents.reported_income` and writes the same two output slots (`policy-engine/src/polisyos/ir/kernel/mechanisms.py:81-117`).
- Lex does not invent a richer atom. `LexInterventionCompiler.compile(...)` validates knobs, copies a provision directive into `InterventionSpec`, and emits `ParameterSpec` rows (`policy-engine/src/polisyos/lex/interventions.py:169-231`). This is a real legal-provision-to-executable-intervention compiler, but no downstream causal path is added.
- `PolicyCandidateSchema` embeds the Trinity bundle and validates rollout, parameter schedule, budget, monitoring, fallback, and transport references against it (`policy-engine/src/polisyos/scientist/policy_design/schema.py:121-267`). A monitoring row may reference an intervention and metric, and `measurement_expectations` is an untyped dictionary, but neither expresses a verified direct-effect bundle or a causal path to intended outcomes (`policy-engine/src/polisyos/scientist/policy_design/schema.py:72-80`, `policy-engine/src/polisyos/scientist/policy_design/schema.py:230-240`).

Probe: Lex compilation plus strict Trinity linking produced real slot semantics, but inspection shows those semantics are not fields of the authored atom:

```text
policy_atom_fields ['enabled', 'identification_mode', 'intervention_id', 'kind', 'lex_provision_ref', 'measurement_expectations', 'notes', 'params', 'priority', 'schedule', 'strategic_response_expected', 'target', 'target_population_type', 'target_region_ids', 'target_sector_ids', 'transmission_channels']
policy_atom tax_subsidy {'kind':'predicate','field':'id','operator':'==','value':'all'} {'rate': Decimal('0.05')} {'outcome_metric':'household_consumption'}
linked_slots ['agents.income'] ['agents.income', 'government.balance'] 0 1
link_ok True [unused-registry warnings only]
```

Verdict: **REAL executable policy-action nucleus** with operator/mechanism, population target, timing, and parameters. Registry-derived read/write slots are a real direct state footprint. The direct-effect *function* remains in the mechanism implementation, and intended downstream effects remain elsewhere in `ProblemFrame` objectives/KPIs or free-form measurement expectations. The north-star tuple is therefore not a single content-bound artifact.

#### Proof-kernel interventions: typed `do()`, outcomes, and conservative composition

- `ir/analytics/interventions.py` has a genuine intervention type system: atomic node assignments, conditional and stochastic policies, modified-treatment policies, edge/path interventions, transport, interference, and composite expressions (`policy-engine/src/polisyos/ir/analytics/interventions.py:172-448`). `InterventionQuery` binds one such expression to typed outcome variables and query context (`policy-engine/src/polisyos/ir/analytics/interventions.py:134-169`, `policy-engine/src/polisyos/ir/analytics/interventions.py:452-460`).
- Composition is behavioral, not merely structural. `check_intervention_composition(...)` flattens composites, tracks changed targets and natural-value dependencies, drops idempotent duplicate node assignments, permits a typed policy replacement rule, and blocks conflicting assignments (`policy-engine/src/polisyos/ir/analytics/interventions.py:675-863`). `identification_plan_for_intervention(...)` selects ID/IDC/dynamic-g-formula/stochastic/MTP/edge/path/transport backends and emits side conditions rather than claiming every type identified (`policy-engine/src/polisyos/ir/analytics/interventions.py:866-1030`).
- The simpler persisted `CausalQuery` surface remains single-treatment: one `treatment_variable`, one outcome, and one perturbation spec (`policy-engine/src/polisyos/ir/analytics/causal_queries.py:41-106`). The richer proof-kernel type system is not consumed by Trinity lowering or `PolicyCandidateSchema`.

Probe:

```text
proof_node_plan id_algorithm identified
proof_duplicate well_typed; rule=DROP_DUPLICATE_NODE_ASSIGNMENT
proof_conflict blocked; reason='conflicting assignments for intervention target benefit_rate'; blocked_pair=[0,1]
```

Verdict: **REAL typed causal-intervention and composition discipline**, but `bridge_missing` from the policy action to the causal expression/query and then to the NCM/Stage-B request.

#### Universal policy grammar: useful facets, not the intervention atom

- The policy grammar derives 11 categorical facets including instrument, targeting, delivery, funding, authority, outcome channel, risk, method need, population, geography, and time (`policy-engine/src/polisyos/policy_grammar/_impl/facets.py:39-60`). Derivation is deterministic keyword/contract normalization: for example instrument type is selected by fixed token tests such as subsidy/service/credit/tax/regulation (`policy-engine/src/polisyos/policy_grammar/_impl/facets.py:199-217`), and normalization collects intervention kinds, population/region strings, parameter keys, and schedule hints (`policy-engine/src/polisyos/policy_grammar/_impl/normalizer.py:39-95`).
- The compiler emits a compilation-only `UniversalPolicyDesignCase`, blocks when concepts/facets are missing, and preserves a candidate-unverified authority envelope (`policy-engine/src/polisyos/policy_grammar/_impl/compiler.py:26-81`). Its consumer projects facets to obligation-graph snapshots and fails closed on unsupported authority (`policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:15-84`). It classifies an intervention family; it does not supply executable parameters, target slots, or causal effects.

Verdict: **REAL deterministic governance grammar, HARDCODED vocabulary derivation, not a generator and not the atom**. Disposition: `USE_AS_IS` for constraints/facets; do not make GY-N2 generate by enumerating its token table (`P10`/`P15`).

#### Disposition for GY-N2

- `REWORK_TO_FIT` the existing `InterventionSpec`/`LinkedIntervention` as the policy atom rather than building a competing lever type.
- `USE_AS_IS` the mechanism registry's state footprint and the proof-kernel intervention composition/identification contracts.
- Build the missing **binding artifact/bridge**, not a duplicate intervention hierarchy: intervention id + mechanism/operator + resolved target slots/direct mechanism ref + typed proof-kernel intervention expression + intended outcome/causal-path refs + provenance/authority. Its validator must prove the mechanism slots and causal variables resolve to the same world-model version and must fail closed when the causal downstream mapping is absent.
- Strangle free-form `measurement_expectations` as the only policy-to-outcome association once that binding exists. `PolicyCandidateSchema` should reference the binding per intervention and joint design, while LLM output remains candidate-only.

### Post-Deployment and Two-Contour Monitoring

Status: Pass 4 done. There are real monitoring and reissue organs, but no Bayesian deployed-policy effect updater and no unified two-contour controller.

#### DDM detectors: real model/data monitoring computations

- `evaluate_data_quality(...)` evaluates required/null-rate, type, numeric range, allowed-value, and freshness contracts over actual records and emits a typed `DataQualitySignal` with hard-failure and risk score (`policy-engine/src/polisyos/ddm/detectors/data_quality_monitor.py:39-87`, `policy-engine/src/polisyos/ddm/detectors/data_quality_monitor.py:90-163`).
- Delayed-label monitoring is substantive. `estimate_binary_classification_degradation(...)` uses calibrated probabilities as CBPE-style expected metric contributions, computes a mean/95% interval, and maps it to a metric budget (`policy-engine/src/polisyos/ddm/detectors/performance_estimator.py:48-103`, `policy-engine/src/polisyos/ddm/detectors/performance_estimator.py:154-176`). Once labels arrive, `monitor_realized_binary_performance(...)` computes accuracy/precision/recall/Brier/AUC and uncertainty; the regression branch computes MAE/RMSE and label delays (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:49-143`, `policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:146-258`). These are predictive-performance monitors, not causal treatment-effect estimators.
- `DriftAndDegradationMonitor.evaluate_window(...)` adapts calibrated shift events, maps shift/degradation/data-quality signals to readiness, builds root-cause and incident artifacts, and optionally emits a model-registry readiness record (`policy-engine/src/polisyos/ddm/integration/monitor.py:55-116`). The shift adapter preserves stationarity regime, calibration id, evidence kind, diagnostic-only flag, and maps severity to risk levels; uncalibrated input fails Pydantic validation (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:10-62`).

Probe on the supported interpreter:

```text
realized_effect_monitor 0.5 (0.17333333333333328, 0.8266666666666667) 1.0 realized_performance
data_quality True 1.0 ['age: null_rate 0.333 exceeds 0.000', 'age: 1 range errors']
readiness R0; primary_reason=hard_data_contract_failure; promotion_allowed=False
incident severity=rollback; rollback_or_fallback=True; page_owner=True
root_causes degradation_event_ids=[realized-...]; data_quality_violations=[null-rate, range]
```

Verdict: **REAL generic DDM computation and readiness/incident composition**. Caller search found these concrete detector entry points used directly by DDM tests and exports; it did not find a GY/workspace or S13 producer invoking them. The PDC bridge in `runtime/quality/ddm_monitoring.py` validates that all five DDM event groups exist, link affected claims/evidence lines, carry downstream status and runtime/CAS refs, and connect incidents to root-cause events (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:37-147`, `policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:242-359`). It consumes already-produced events; it does not run DDM. Capability state for policy monitoring: `implemented_but_not_orchestrated`/`producer_missing` at this bridge.

Disposition: `USE_AS_IS` detector/readiness/incident algorithms; `REWORK_TO_FIT` event adapters that bind model/data events to deployed policy claims, intervention ids, world-model version, and the GY lifecycle.

#### Multiple testing: real bounded diagnostic discipline, standalone

- `allocate_conservative_budget(...)` deduplicates test ids and applies a Bonferroni/union-bound split (`policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:76-93`). `OnlineFDRController.test(...)` spends half current alpha wealth subject to a floor, rejects by p-value, and rewards discoveries (`policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:38-73`). This is a small alpha-wealth implementation, not a named LORD/SAFFRON guarantee.
- Caller search found the controller in stationary-replay tests and package exports, not in the window monitor or a policy anomaly-discovery workflow (`policy-engine/tests/unit/ddm/test_stationary_replay.py:95-113`). Probe:

```text
fdr_plan bonferroni_union_bound {'region': 0.025, 'sector': 0.025}
fdr_decisions True alpha=0.0125 wealth=0.0375; False alpha=0.01875 wealth=0.01875; discoveries=1
```

Verdict: **REAL, STANDALONE diagnostic multiple-testing organ**. Reusable for the exploratory contour after its statistical guarantee and event/persistence semantics are made explicit; currently `bridge_missing` and `consumer_missing`.

#### Scientist decision feedback: live confirm/refute/reissue loop, not Bayesian effect learning

- Decision-packet enrichment builds and persists a monitoring contract from simulation results and backtest error (`policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py:1510-1544`). The ranges are deterministic heuristics: confirm margin is max(10% of baseline, MAE, 0.01); refute margin is max(20%, RMSE, twice confirm margin) (`policy-engine/src/polisyos/scientist/feedback/core.py:69-135`).
- `DecisionFeedbackService.evaluate_packet(...)` loads actuals through the decision packet's data snapshot, compares each observed metric against confirm/refute ranges, persists a report, and on refutation marks decision validity `REQUIRES_HUMAN_REVIEW`, persists comparison and reissue-plan artifacts, and updates feedback refs (`policy-engine/src/polisyos/scientist/feedback/core.py:204-355`, `policy-engine/src/polisyos/scientist/feedback/core.py:525-533`).
- `build_reissue_plan(...)` creates a Foundry `CalibrationConfig` for refuted metrics and may convert an already-present calibration report into a parameter-override bundle; it does not execute calibration itself (`policy-engine/src/polisyos/scientist/feedback/core.py:424-523`). Runtime exposes `POST /runs/{run_id}/feedback/evaluate` and a reissue path; `prepare_reissue(...)` creates a new experiment-state payload carrying the reissue plan, refuted metrics, and optional override bundle (`policy-engine/src/polisyos/runtime/http/routes/control.py:139-175`, `policy-engine/src/polisyos/runtime/http/services/feedback.py:209-270`). This is a **live post-deployment lifecycle**, not merely contracts.
- No body in this path estimates a treatment effect, updates a prior/posterior, or separates policy effect from secular change. It compares raw actual metric values to fixed ranges. The calibration config is future work for a reissued model run, not an online Bayesian causal update.

Verdict: **REAL confirm/refute/review/reissue contour with HARDCODED range policy; no Bayesian policy-effect update**. `USE_AS_IS` persistence, decision-validity trigger, and reissue bridge; `REWORK_TO_FIT` monitoring contract generation to consume candidate value uncertainty/estimands and post-deploy causal observations.

#### S13 post-deploy accountability: strong gate, not a detector or learner

- A deployable `DeploymentDossier` must carry monitoring design, owner/deadline, reissue/rollback paths, and monitorability floor (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:180-225`). `DivergenceRecord` requires attribution, owner/deadline, closure evidence, and prevents an implementation failure from refuting policy theory without an independent ref (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:228-298`).
- `LearningUpdateProposal` fails closed unless A-before-B passes, divergence is attributed, a deployment baseline and post-deploy signal refs exist, and non-note updates carry an assurance-case delta; high-stakes reissue/shrink requires governance/human-decision refs (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:316-390`). False-clear checks also block outcome learning without a counterfactual credibility ref (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:972-992`).
- `PostDeployMapeKTrace` is a typed list of monitor/analyze/plan/execute/knowledge refs; `build_post_deploy_mape_k_trace(...)` validates a supplied payload but does not perform those stages (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:301-313`, `policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:586-633`). Production caller search found downstream projection/export use but no owner constructing S13 artifacts from DDM or decision-feedback outputs.

Verdict: **REAL authority/attribution firewall, implemented but not orchestrated as the monitoring controller**. `USE_AS_IS` for north-star safety semantics; add bridges from DDM and decision feedback rather than duplicating S13.

#### North-star two-contour verdict

- Confirmatory contour: **PARTIAL/EXISTS**. A live decision-feedback service tracks predicted metrics against actuals and can force review/reissue, but it is range-based, not Bayesian or causal.
- Exploratory contour: **PARTIAL**. Calibrated shift/data-quality/performance detectors and FDR controls compute real diagnostics, but they are generic model-monitoring organs and are not orchestrated into policy anomaly discovery, persisted search frontier, or candidate generation.
- Fully greenfield piece: the controller/artifact that maintains a deployed policy estimand posterior (or honest non-Bayesian sequential estimate), separates confirmatory from exploratory alpha/authority, binds discoveries to the world model and evidence graph, and routes attributed learning back through GY revise/promote. This is a plausible post-GY-N7 workstream, not evidence that current GY generation already cycles after deployment.

### Required vs Available Data and World-State Binding

Status: Pass 4 done. There are two independent requirement systems; the richer one is not connected to the Foundry non-identification witness used by the workspace loop.

#### Foundry `RequiredDataSpec`: real ID failure witness, very narrow contract

- `RequiredDataSpec` is a frozen internal dataclass with only `missing_distributions`, `suggested_experiment`, and `alternative_identification` (`policy-engine/src/polisyos/foundry/methods/catalog/causal/_id_contracts.py:24-31`). `HedgeCertificate` optionally owns one, while `IdentificationResult.required_distributions` is a separate list (`policy-engine/src/polisyos/foundry/methods/catalog/causal/_id_contracts.py:33-75`). It has no claim id, scope, quality, rights, cost, world-model variable binding, or persistence/provenance fields.
- In the main ID algorithm, a full-graph hedge constructs experimental `DistributionRef` rows only for `hedge_root & treatment` and suggests randomizing the same intersection (`policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py:325-395`). General hedge/thicket construction similarly derives distributions from the hedge forest's treatment intersection (`policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py:1427-1463`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py:1527-1550`). A non-well-posed cyclic model instead emits an empty distribution set plus an explanatory alternative-identification string (`policy-engine/src/polisyos/foundry/methods/catalog/causal/cyclic_id.py:514-545`).

Probe: the canonical bow-arc `X -> Y`, `X <-> Y` is correctly non-identifiable, but its `hedge_root` is the non-treatment node, so `hedge_root & treatment` is empty:

```text
id_result hedge_found Hedge found ... P(['Y']|do(['X'])) is NOT identifiable.
required_data RequiredDataSpec(missing_distributions=(), suggested_experiment=None, alternative_identification=None)
```

This is a **REAL negative identification certificate with an incomplete acquisition witness**. The algorithm's status is trustworthy for this probe; the attached “what data would resolve it” payload is not sufficient.

#### GY `AcquisitionPlanner.plan_from_required_data`: lossy, hardcoded adapter

- The adapter reads `missing_distributions` by attribute, takes only element zero, and substitutes the literal `unknown_missing_distribution` when empty (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:528-551`). It computes cost, authority gain, and decision value from deterministic basis helpers/fixed gap tables, multiplies authority gain by decision value for VOI, and compares VOI/cost to a fixed `0.0001` threshold (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:552-577`, `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:758-780`).
- It then fabricates one data-family requirement, one `public_registry` VOI decision, and one Scientist `DataNeedSpec(metric=<string>, quality_min=0.7)` (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:578-643`). The costed rung-7 plan and `SearchTerminalState` stop at `ACQUISITION_REQUIRED`; hard budgets are recorded as disallowing continuation (`policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:644-748`).
- The bow-arc probe above therefore became:

```text
gy_adapter unknown_missing_distribution public_registry acquisition_required 0.2976
```

  That is a **HARDCODED false precision**: positive VOI and a concrete strategy were assigned despite no named distribution or experiment. A second probe proved multiple gaps are truncated:

```text
multi_required ('P(Y|do(X))', 'P(M|do(X))')
multi_adapter_only P(Y|do(X)) P(Y|do(X))
```

Verdict: `REWORK_TO_FIT`. Preserve all typed distribution refs, reject/repair empty unresolved witnesses, derive cost/VOI from actual eligible providers and decision sensitivity, and emit one-to-many requirements. Do not reuse the current first-item/string fallback as the GY-N4 bridge.

#### W7 `DataRequirementSpec` and Fabric matching: real richer required/available gap

- `DataRequirementSpec` is the stronger reusable contract: claim id/family/use; required source families; population/geography/time role; recency; lineage and transformation tolerance; quality/missingness minima; admissibility predicates; mandatory facets; concept/obligation/authority refs; producer/rule version and authority boundary (`policy-engine/src/polisyos/data_requirement/_impl/models.py:50-162`). `DataRequirementCompiler.compile_for_claim_ledger(...)` derives these rows from policy facets, obligation graph, claim ledger, and capability bindings; the legacy hardcoded family heuristic is disabled by default (`policy-engine/src/polisyos/data_requirement/compiler.py:83-119`, `policy-engine/src/polisyos/data_requirement/compiler.py:144-309`).
- `build_source_contract_requirement_bindings(...)` compares each required family with available Fabric candidates or capability bindings. Absence emits `blocked`; a matching source missing mandatory facets or failing source-contract validation emits `rejected`; only a matching, validation-passing source with all facets is `selected`; unrelated inventory remains context-only (`policy-engine/src/polisyos/fabric/catalog/data_requirement_adapter.py:15-117`, `policy-engine/src/polisyos/fabric/catalog/data_requirement_adapter.py:120-187`). Capability-backed rows preserve source assets, rights, quality, limitations, conflicts, and authority composition refs (`policy-engine/src/polisyos/fabric/catalog/data_requirement_adapter.py:190-316`).

Probe:

```text
available_none {'selected':0,'rejected':0,'blocked':1} blocked required_source_family_absent ['schema_ref','lineage_refs']
available_weak {'selected':0,'rejected':1,'blocked':0} rejected source_contract_facets_missing ['lineage_refs']
available_good {'selected':1,'rejected':0,'blocked':0} selected
```

Verdict: **REAL required-vs-available classification and admissibility boundary**. Disposition: `USE_AS_IS` the W7 contract/compiler and Fabric matcher. Missing bridge: convert mathematical `DistributionRef`/world-variable needs into one or more claim-bound W7 specs without discarding causal semantics.

#### Available data to world model: real final leg, no acquisition handoff

- As recorded in the world-model section, `build_input_bindings(...)` can turn an actual Fabric `DataSnapshot` plus explicit binding rules into a persisted `GlobalState` and binding report (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:69-236`, `policy-engine/src/polisyos/foundry/data_plane/bindings.py:541-661`). It does not consume `DataRequirementSpec`, a source-binding report, or `RequiredDataSpec`; callers must already supply the snapshot and slot mappings.
- S12 `allocate_value_of_information(...)` aggregates already-provided `ValueOfInformationEstimate` rows across canonical allocation sites; it does not estimate the expected decision value of acquiring data (`policy-engine/src/polisyos/runtime/quality/design_axes/resource_economics.py:487-521`). The S3 fixture acquisition loop uses fixed expected value/cost numbers `0.91/0.15` for every generated gap (`policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:459-486`). These are governance/allocation demonstrations, not the missing world-data VOI computation.

Whole-path verdict: required > available is honestly represented in W7/Fabric, and available snapshots can honestly populate Foundry state, but no owner connects:

```text
ID DistributionRef gap -> W7 requirement -> eligible provider/source -> executed acquisition
-> validated snapshot/source contract -> slot/causal-variable binding -> refit world -> rerun original workspace
```

The breaks are the `RequiredDataSpec -> DataRequirementSpec` semantic adapter, provider execution handoff, and world/loop re-entry receipt. Those are the load-bearing GY-N4 changes; the underlying matcher and state binder should be reused.

### Connector and Acquisition Execution Depth

Status: Pass 4 done. Execution exists in several bounded organs; no owner consumes the GY costed plan end to end.

#### Fabric direct/retrieval execution is real

- `fabric_get_data(...)` resolves an explicit or catalog-discovered connector, builds a typed `FetchRequest`, obtains/releases a registry connection, calls `connector.fetch(...)`, and returns the real `FetchResult` (`policy-engine/src/polisyos/fabric/api.py:90-156`, `policy-engine/src/polisyos/fabric/api.py:159-254`). This is a synchronous Scientist-facing fetch, not an ingestion/persistence workflow.
- `RetrievalService.resolve(...)` runs fast-lane, dataset-catalog, and optionally explore-lane discovery to produce `FetchPlan` rows; unresolved needs produce a warning rather than fabricated data (`policy-engine/src/polisyos/fabric/retrieval/service.py:230-385`). `execute_fetch_plans(...)` invokes `FetchExecutor` for each plan and returns `DataContextMetric` rows plus promotion candidates (`policy-engine/src/polisyos/fabric/retrieval/service.py:426-480`).
- `FetchExecutor` performs a preview fetch, gates on completeness, can follow a fallback, then performs the full connector fetch and returns row count/completeness/sample rows (`policy-engine/src/polisyos/fabric/retrieval/executor.py:70-156`, `policy-engine/src/polisyos/fabric/retrieval/executor.py:158-260`). Its `persist_payload` branch is intentionally a no-op; the body says large-payload persistence is deferred to ingestion (`policy-engine/src/polisyos/fabric/retrieval/executor.py:139-143`). Thus retrieval execution yields in-memory metric context, not a `DataSnapshot` or SKG delta.

Verdict: **REAL search/resolve/fetch path**. Disposition: `USE_AS_IS` discovery/preview/fallback/fetch; `REWORK_TO_FIT` promotion from a selected `DataRequirementSpec` and acquisition budget into a persisted ingestion manifest.

#### Fabric ingestion really executes fetch -> evidence -> `DataSnapshot`

- `run_connectors_ingestion(...)` normalizes a connector manifest, resolves injected/default registry/tracer/metrics/store providers, fetches every dataset, applies transform DAG, PII processing and quarantine, caches payloads, records fetch/version/quality metadata, persists provenance, and emits an `EvidenceBundle` (`policy-engine/src/polisyos/fabric/ingestion/ingestion.py:804-938`, `policy-engine/src/polisyos/fabric/ingestion/ingestion.py:951-1072`).
- `run_orchestrated_ingestion(...)` calls that canonical ingestion once and then builds a `DataSnapshot` from the evidence bundle without re-fetching (`policy-engine/src/polisyos/fabric/data_plane/orchestrator.py:511-570`). Snapshot construction selects the first evidence source as `data_ref`, persists a quality report, and writes a lineage-linked `fabric.data_snapshot` (`policy-engine/src/polisyos/fabric/data_plane/orchestrator.py:573-639`). Multi-dataset snapshot semantics are therefore limited: all sources stay in the evidence bundle, but only source zero is the primary data ref.
- Partitioned ingestion can run manifests through local async/Dask/Ray/Celery backends, persist partition cursor state, and return evidence/snapshot refs per partition (`policy-engine/src/polisyos/fabric/data_plane/orchestrator.py:360-508`). This is a real execution substrate, although distributed trust checks remain a separate concern.

Probe through a fake connector but the real ingestion, CAS, provenance/evidence, and snapshot bodies:

```text
connector_ingestion: fetching dataset 1/1 (probe:income)
fabric_execution 1 True True
snapshot data_ref=sha256:c2a2... evidence_ref=sha256:adc7... stats={'datasets_fetched':1,'source':'orchestrated_ingestion:pass4_probe'}
manifest_kinds fabric.evidence_bundle fabric.data_snapshot
```

Verdict: **REAL end-to-end connector execution to a world-bindable snapshot**. `USE_AS_IS`, with an N4 adapter supplying a governed manifest and preserving all selected source refs.

#### Scholar/OpenAlex -> SKG: real endpoints, missing live ingestion bridge

- `OpenAlexWorksProvider.search(...)` sends a real OpenAlex works query with filters, rate limiting and retry, reconstructs inverted-index abstracts, and returns normalized academic hits (`policy-engine/src/polisyos/scholar/search/providers.py:159-244`). `ScholarDeepSearchService.deep_search(...)` builds/resumes a query graph, enforces query/page/time budgets, executes provider searches, persists no-hit frontier records in its bundle, fetches pages, deduplicates by content hash, builds snippets/claim-support rows, and can persist the resulting `WebEvidenceBundle` (`policy-engine/src/polisyos/scholar/search/service.py:214-478`, `policy-engine/src/polisyos/scholar/search/service.py:480-528`).
- `ingest_openalex_span_grounded_claims(...)` is also real: it persists query trace/version, validates each `CausalClaim` against an `OpenAlexWorkText` span, rejects unsupported claims, canonizes variables, and writes article, edge, edge-evidence, and span-grounded-claim SKG rows (`policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:640-845`). The no-hit variant persists query/frontier/version rows (`policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:848-911`).
- The call graph is the break: production search service/provider modules never import these ingest functions, and repository callers of both OpenAlex ingest entry points are tests. Scholar returns generic web sources/snippets/support records; SKG ingest requires typed `OpenAlexWorkText`, extracted `CausalClaim` rows, and a query trace. No production owner performs that conversion and call.

Verdict: **REAL search plus REAL grounded SKG writer, but `bridge_missing`/`implemented_but_not_orchestrated` between them**. The GY-K artifacts demonstrate a route, not a live acquisition consumer. `REWORK_TO_FIT` by adding a producer-owned Scholar/OpenAlex extraction-ingest receipt; do not embed SKG writes inside the workspace loop.

#### Runtime workers cannot consume the acquisition plan today

- `TaskRunner` is only a local thread-pool wrapper around an arbitrary callback; it tracks pending/running/completed/failed but has no plan decoder, persistence, or acquisition handler (`policy-engine/src/polisyos/runtime/http/services/task_runner.py:21-100`).
- `ControlWorker` provides durable lease, heartbeat, and generic `JobHandler` dispatch (`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-233`). The actual control handler admits exactly `workflow_run`, `natural_language_run`, and `lex_pipeline`; every other kind raises (`policy-engine/src/polisyos/runtime/http/services/_control_contracts.py:21-33`, `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py:1000-1114`). There is no acquisition job kind.
- The workspace-control projection merely emits a blocking gate whose next action is “Run an approved acquisition producer”; it neither enqueues nor names an executable producer request (`policy-engine/src/polisyos/runtime/http/services/control/workspace_loop_transition.py:419-455`). Repository-wide caller search found `AcquisitionPlan.costed_plan` consumed only by workspace terminal/audit construction, not Fabric, Scholar, Data Forge, or the control worker.
- S3's `SubstrateAcquisitionLoop.run_to_closure(...)` does model the right state sequence, including rerun-consuming-index-delta closure, but `from_fixture(...)` explicitly never uses live network; `_discover_source(...)`, source validation, capability creation, and VOI values all read a JSON fixture (`policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:269-372`, `policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:459-486`, `policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:505-619`). Verdict: **HARDCODED fixture closure discipline**, reusable as a state-machine template, not an executor.

#### Exact GY-N4 bridge and re-entry gap

The costed GY plan currently says only `recommended_strategy=public_registry`, a stringified missing distribution, synthetic cost, and generic `DataNeedSpec`. It lacks provider/connector id, dataset/query, filters/time/scope, rights requirement, W7 requirement refs, binding rules, approval/budget receipt, and destination (Fabric snapshot vs Scholar/SKG).

N4 should `REWORK_TO_FIT` existing owners with one typed acquisition execution bridge:

1. Accept all W7 requirement gaps plus VOI/budget decision and original workspace/cycle refs.
2. Resolve eligible Fabric `FetchPlan`/connector manifests or Scholar query plans; require rights/source-contract validation before execution.
3. Enqueue a durable acquisition job using `ControlWorker` infrastructure.
4. Execute Fabric ingestion to `EvidenceBundle`/`DataSnapshot`, or Scholar extraction to a span-grounded SKG delta, through the existing owners.
5. Emit a content-bound receipt mapping each requirement/distribution to produced source, evidence, snapshot/SKG version, quality, cost, and failures.
6. Update the capability/world binding and re-enter the **same** workspace with incremented cycle index; closure must prove the rerun consumed the delta, as the S3 fixture state machine already requires.

Until all six are present, acquisition execution **exists in the repository but is absent from the generation cycle**.

### Authority Derivation and Effective Evidence Independence

Status: Pass 4 done. The authority and P14 organs are **REAL, fail-closed, and reusable**, but they are distributed consumers/gates rather than an orchestrated GY promotion stage.

#### Evidence kind and decision grade are separate authority axes

- `EvidenceKind` is a non-ranked kind lattice (`measurement`, `derivation`, `proxy`, `transport`, `bounds`, `simulation`, `elicitation`, `incomparable_meet`), while `DecisionGrade` is the separately ranked authority axis (`unsupported` through `decision_admissible`) (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:29-44`, decision-grade ranking at `policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:168-195`). A measurement does not become decision-admissible merely because it is measurement.
- `AuthorityBoundary` binds both axes to explicit allowed/denied purposes, source authority, posture, rule versions, evidence basis, and known limits (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:62-74`). LLM sources are forced to `shadow`, and simulation at advisory-or-stronger grade requires calibration refs (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:76-89`). `meet(...)` intersects allowed purposes, unions denials, takes the weaker decision grade/posture/source authority, and computes the evidence-kind meet (`policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:91-114`, `policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py:190-220`).
- Ring-2 models reject non-empty verifier-only fields unless validation context names a verifier/governance/A-side writer; the separate `assert_ring2_verifier_provenance(...)` reserializes and revalidates at persistence/promotion/read boundaries so `model_construct`/unchecked copies cannot bypass the rule (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:91-128`, `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:141-165`).
- `AuthorityDerivationTrace` compares requested transforms with independently computed evidence kind and decision grade. It forbids `upgraded`, rejects a `matched` result whose request exceeds the computation, and forbids decision-admissible output with unresolved blockers (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:451-497`; evidence coverage relation at `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:931-947`). `SearchExitContract` likewise derives its public evidence kind/grade/rung from the verifier-written boundary and rejects contradictory supplied projections (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:694-741`).
- The current workspace producer uses these rules honestly but narrowly: it starts from a requested measurement/decision-admissible boundary, calls `with_partial_evidence_downgrade(...)`, denies design-candidate/grounded-admissible/production/publication uses, caps grade at `descriptive_only`, and emits an `AuthorityDerivationTrace` with blocker `slice0_estimate_port_only` (`policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2140-2165`, `policy-engine/src/polisyos/runtime/quality/workspace/loop.py:2167-2196`). The HTTP transition persists each trace separately beside the search exit and ledger (`policy-engine/src/polisyos/runtime/http/services/control/workspace_loop_transition.py:138-166`).

Probe, Python 3.14:

```text
authority_matched_self_promotion REJECTED True
authority_downgrade descriptive_only downgraded
```

This constructs the same request (`measurement`, `decision_admissible`) against a computed `descriptive_only` result. Declaring it `matched` raises; declaring it `downgraded` succeeds. This proves the trace validator enforces the direction of authority rather than merely carrying labels.

#### P14 effective independence is computed and consumed

- `build_evidence_independence_map(...)` first validates evidence lines against predeclared portfolio designs, canonicalizes methods using passing Foundry consensus/equivalence reports, then clusters by claim, strand, method cluster, source lineage, corpus ancestry, author/institution pool, preprocessing, assumptions, identification strategy, and shared failure mode (`policy-engine/src/polisyos/runtime/quality/evidence_independence.py:19-45`, `policy-engine/src/polisyos/runtime/quality/evidence_independence.py:136-248`, `policy-engine/src/polisyos/runtime/quality/evidence_independence.py:455-567`). Every hard cluster contributes one effective line; raw count is explicitly diagnostic and support/counterevidence/context masses are reported separately (`policy-engine/src/polisyos/runtime/quality/evidence_independence.py:189-207`, `policy-engine/src/polisyos/runtime/quality/evidence_independence.py:790-882`).
- The richer `build_effective_independence_graph(...)` is also real: it derives evidence-line identities, hard-collapse edges/clusters, optional governed feature-flagged pairwise dependence, `quality * novelty` mass, scarcity limits, and a rule forbidding collapse of counterevidence into support (`policy-engine/src/polisyos/evidence/portfolio/effective_independence_graph.py:18-48`, `policy-engine/src/polisyos/evidence/portfolio/effective_independence_graph.py:87-198`). Runtime W4.B only exposes that graded graph when the feature flag and governed config are present (`policy-engine/src/polisyos/runtime/quality/evidence_independence.py:1020-1065`).
- The result reaches authority-bearing consumers. Serious-canary scorecards validate every map and fail when raw evidence counts appear without effective counts or evidence lines appear without a map (`policy-engine/src/polisyos/runtime/quality/scorecard.py:4964-5033`). Composition validates the map, requires it be bound to the exact claim/subdesign/producer roots/evidence lines/lineage, recomputes content hashes, resolves verifier provenance, and blocks missing, invalid, unbound, or zero-effective-evidence maps (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:2105-2199`, `policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:2282-2360`, blocking verdict at `policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:2509-2541`). G5 conversion also validates the map and emits failure issues for missing/invalid effective-independence evidence (`policy-engine/src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py:2831-2874`, `policy-engine/src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py:3848-3872`).

Probe, Python 3.14, two publications of one study plus one independent study:

```text
independence_counts 3 2
collapse_reasons ['same_study_reported_multiple_times', 'same_snapshot_preprocessing_identification']
support_mass 2.0
raw_count_authority diagnostic_only
```

The three records do not yield three authority-bearing support units. This is a computed P14 collapse, not a presence check.

#### Promotion depth and disposition

- G4 remains a bounded resolver over persisted G1/G2/G3/GL artifacts. Its declared authority is promotion-decision replay and governed promotion state only; it explicitly denies production, publication, approval, scorecard, closeout, recommendation, ungrounded causal/proof/legal authority, and overriding A-side incompleteness (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1-6`, `policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:61-86`). Its conformance negatives cover missing grounded contracts/calibration/proof/legal refs, weakest-boundary bypass, shadow self-promotion, human-decision bypass, and downstream authority leaks (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:114-157`).
- Verdict for GY-N6: **USE_AS_IS** for `AuthorityBoundary`, Ring-2 provenance, authority derivation, P14 independence, G4/G5 enforcement, and scorecard/composition consumers. **REWORK_TO_FIT** is only the orchestration/bridge: a real cycle must persist the generated candidate, A-grounding, value/calibration, counterexample/refinement, evidence-independence, and human/mandate artifacts, then invoke the existing gates and feed their downgrade/block/promote result back to the cycle. No gate should be replaced by an LLM/controller decision.
- Capability state for an in-cycle B->A promotion is therefore `implemented_but_not_orchestrated` / `bridge_missing`, not `producer_missing`. G4 itself reports its admission maturity as `implemented_but_not_orchestrated` in the generated readiness surface (`policy-engine/src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:2982`).

Open questions:

- The final GY controller must choose one persisted promotion sequence. The code supports workspace Ring-2 derivation, G4 governed promotion, and Scientist champion promotion as separate paths; investigation has not found a canonical bridge ordering all three.
- P14 is already sufficient for authority enforcement, but the generated candidate path must produce content-bound evidence-line/lineage records. Passing only an independence-map reference or count will fail composition by design.

### Foundry Method Advisor: Real Planner, Not Executor

Status: Pass 4 done; closes the remaining Pass-3 method-selection gap.

- `MethodAdvisorQuery` carries method criteria, observed-data characteristics, runtime/cost budgets, loss profile, cost policy, risk bound, and optional strict cross-method consensus (`policy-engine/src/polisyos/foundry/methods/selection/advisor.py:184-269`). `advise_methods(...)` overlays runtime truthfulness history, ranks catalog entries, optionally computes budget-filtered/Pareto candidates and certificates, and suppresses all recommendations when required consensus is absent/refuses (`policy-engine/src/polisyos/foundry/methods/selection/advisor.py:400-579`). The analyst surface always requires at least two-method consensus and applies cost annotation/Pareto policy (`policy-engine/src/polisyos/foundry/methods/selection/advisor.py:582-620`).
- Budget handling is substantive: no cost model, unknown cost, out-of-scope cost, and infeasible budget are distinct fail-closed statuses; feasible filtering and Pareto selection return bound-type/proof-obligation certificates rather than silently ignoring cost (`policy-engine/src/polisyos/foundry/methods/selection/advisor.py:823-1062`, certificate obligations at `policy-engine/src/polisyos/foundry/methods/selection/advisor.py:1698-1713`). Truthfulness is the primary lexicographic ranking dimension (`policy-engine/src/polisyos/foundry/methods/selection/advisor.py:391-397`).
- Caller scan found production-code calls only in Foundry phase-zero validation and the methods CLI, plus the helper's own wrappers (`policy-engine/src/polisyos/foundry/validation/phase0_closure.py:222`, `policy-engine/src/polisyos/foundry/methods/cli/__init__.py:347`). Workspace `run_intent(...)` does not invoke it. It packages catalog metadata and historical/runtime predictions; it does not execute a method or prove its result.

Probe:

```text
advisor_selected ['causal.pass4.approx@1.0.0']
advisor_status FILTERED ('causal.pass4.exact@1.0.0',)
advisor_strict_without_results [] not_enough_methods False
advisor_execution_count 0
```

The preferred exact method was filtered because its certified cost exceeded budget; strict mode emitted no recommendation without two comparable results. Verdict: **REAL selection/planning organ, implemented but not orchestrated into GY, non-authoritative without execution**. GY-N5 should `USE_AS_IS` its ranking/budget/consensus certificates, then pass selected FQNs through the existing registry/runner and consume actual method evidence. It must not treat an advisor score as candidate value or causal authority.

### Fabric World Store / Materialization / Query: Epistemic World Substrate

Status: Pass 5 done for the user-called-out correction. This reopens and revises the Pass-4 world-model verdict.

#### What it does

- `polisyos.fabric.world` is not a shim or legacy shell. The facade exports the store write path, validation, materialization, Kuzu graph export, and snapshot/branch helpers from one public package (`policy-engine/src/polisyos/fabric/world/__init__.py:5-41`, materialization exports at `policy-engine/src/polisyos/fabric/world/__init__.py:43-87`). The README's dependency statement is confirmed by callers: Fabric docs/claims, Lex, Scholar, Data Forge legal batch, storage adapters, and runtime temporal code import the facade or query path (caller scan included `policy-engine/src/polisyos/scholar/orchestrator/bundle.py:16-20`, `policy-engine/src/polisyos/fabric/claims/extraction.py:17-20`, `policy-engine/src/polisyos/lex/normpack/assemble_pack.py:35-41`, `policy-engine/src/polisyos/fabric/storage/duckdb_adapter.py:15`).
- The fact emitter turns typed world objects into IR fact-log rows. `emit_attr_fact(...)` rejects missing attribute values and can attach mutation metadata, valid time, trust, and legal envelopes (`policy-engine/src/polisyos/fabric/world/store/emit.py:43-89`). `emit_edge_fact(...)` rejects empty targets and serializes relation predicates through `world.rel.*` (`policy-engine/src/polisyos/fabric/world/store/emit.py:91-137`). Higher-level emitters map document metadata/fragments/claims/events into node and provenance-edge facts, including claim-citation derivation and event input/output provenance (`policy-engine/src/polisyos/fabric/world/store/emit.py:198-387`, `policy-engine/src/polisyos/fabric/world/store/emit.py:435-556`).
- Persistence is content-addressed and governed. `persist_doc_meta`, `persist_claim`, `persist_world_event`, etc. call `store.put_json(...)` with kind/schema and `resolve_artifact_governance(...)`; claims include citation/source inputs, and world events include evidence/provenance/world-object inputs (`policy-engine/src/polisyos/fabric/world/store/persist.py:42-64`, `policy-engine/src/polisyos/fabric/world/store/persist.py:123-158`, `policy-engine/src/polisyos/fabric/world/store/persist.py:230-265`). This is not just a table row write; the artifacts are CAS-manifested with inputs/governance through `FileSystemCAS` (`policy-engine/src/polisyos/core/artifacts/store.py:149-205`).
- The append-only mutation model is explicit. `WorldMutationKind` supports `assertion`, `correction`, `revocation`, `branch_assertion`, and `scenario_assertion`; `WorldObservedState` distinguishes observed vs simulated state (`policy-engine/src/polisyos/fabric/world/store/segments.py:39-54`). `WorldFactMutationMetadata.__post_init__` normalizes and validates required fields, while `_validate_world_mutation_metadata(...)` requires correction/revocation evidence and scenario lineage/branch/actor/reason, and forces scenario assertions to simulated state (`policy-engine/src/polisyos/fabric/world/store/segments.py:65-133`, `policy-engine/src/polisyos/fabric/world/store/segments.py:229-266`).
- Segments are a real append-only storage boundary. `write_world_fact_segment(...)` normalizes the segment name, deduplicates by `fact_id`, and writes under the `world/` lane; `append_world_segment_index(...)` appends the manifest to `_segments.jsonl` under a file lock and updates segment-count metrics when available; `load_world_fact_manifests(...)` reads and validates the index fail-closed (`policy-engine/src/polisyos/fabric/world/store/segments.py:320-410`). `gc_world_segments(...)` only deletes applied, unretained segments and rewrites the index (`policy-engine/src/polisyos/fabric/world/store/segments.py:430-499`).
- Validation is substantive. `validate_doc_meta_ids`, `validate_doc_fragment_ids`, `validate_claim_id`, `validate_world_event_id`, trust/quality/conflict validators recompute deterministic IDs; `validate_fact_is_world_abi(...)` enforces subject/predicate ID patterns, `world.rel.*` edge target/object rules, allowed world attributes, `NodeKind` values, and artifact-id syntax for artifact/properties refs (`policy-engine/src/polisyos/fabric/world/store/validate.py:54-120`, `policy-engine/src/polisyos/fabric/world/store/validate.py:123-164`).
- DuckDB materialization is real and incremental. `ensure_world_schema(...)` applies `duckdb_world.sql` and idempotent migrations (`policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:146-190`); the DDL defines `world.world_facts` with `valid_time` and `tx_time`, `world.world_nodes`, `world.world_edges`, events/docs/claims/conflicts/trust/quality projections, and bitemporal indexes (`policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql:33-100`, projection tables at `policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql:106-260`). `ensure_world_materialized(...)` applies only unapplied segment IDs and refuses hash mismatches (`policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:219-297`). `apply_world_segment(...)` verifies the Parquet hash, stages rows, inserts only new facts/edges, updates touched node envelopes by ranked latest facts, refreshes projections, and records a per-segment plan/stats row in one transaction (`policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:351-491`, plan recording at `policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:600-667`, `policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:741-780`).
- Projection refresh is content-bound to CAS artifacts rather than trusting node presence. `_load_doc_meta`, `_load_claim`, `_load_world_event`, etc. load bytes from CAS, validate deterministic IDs, and only then write typed projection rows (`policy-engine/src/polisyos/fabric/world/materialize/projections.py:210-314`). `update_projections(...)` computes the impacted projection plan from touched node kinds, loads artifact IDs from `world.world_nodes`, updates typed projection tables, and recomputes claim-citation/conflict-member projections from graph edges (`policy-engine/src/polisyos/fabric/world/materialize/projections.py:743-872`).
- Query is a governed, bitemporal read path. `WorldQueryRequest` carries table, columns, filters, access scope, classification, row policy, audit log, `as_of_tx_time`, `as_of_valid_time`, `snapshot_root`, `snapshot_id`, and `branch` (`policy-engine/src/polisyos/fabric/world/query.py:124-155`). `execute_world_query(...)` normalizes allowed columns/classifications, emits deny/allow audit events, resolves snapshot/branch if requested, compiles temporal clauses, parameterizes filters, enforces row/tenant policies, and masks columns (`policy-engine/src/polisyos/fabric/world/query.py:157-266`, snapshot backend at `policy-engine/src/polisyos/fabric/world/query.py:403-481`, temporal SQL at `policy-engine/src/polisyos/fabric/world/query.py:488-682`, audit at `policy-engine/src/polisyos/fabric/world/query.py:812-854`). Runtime `TemporalService.world_query_kwargs(...)` maps runtime valid/transaction time, branch, and snapshot fields directly into these query kwargs (`policy-engine/src/polisyos/runtime/http/services/temporal.py:364-384`).
- Snapshots and branches are real for DuckDB-native materializations. `create_world_snapshot(...)` requires a file-backed DuckDB database, copies the database file after `CHECKPOINT`, records transaction/valid cutoffs from `world.world_facts`, attaches governance, registers branch-head governance evidence, and persists metadata (`policy-engine/src/polisyos/fabric/world/store/snapshots.py:298-379`, branch upsert at `policy-engine/src/polisyos/fabric/world/store/snapshots.py:382-490`). `create_world_branch(...)` supports observed/scenario branches; scenario branches require `scenario_ref`, assumption lineage, and `valid_from`, mark observed state as simulated, and store a `scenario_contract` (`policy-engine/src/polisyos/fabric/world/store/snapshots.py:493-568`). `resolve_world_snapshot(...)` resolves exact snapshot, branch head, or point-in-time retained snapshot by tx/valid cutoffs (`policy-engine/src/polisyos/fabric/world/store/snapshots.py:595-657`). `merge_world_branch(...)` copies the target snapshot, merges known world tables by primary key under `fail_on_conflict` / `branch_wins` / `target_wins`, resolves or blocks `world.kind` conflicts, creates a new target snapshot, and appends merge governance evidence (`policy-engine/src/polisyos/fabric/world/store/snapshots.py:726-871`, conflict logic at `policy-engine/src/polisyos/fabric/world/store/snapshots.py:1287-1434`).
- Kuzu is present but narrower than DuckDB. The in-memory `WorldGraphSnapshot` and query helpers can traverse entity neighborhoods/source overlap/origin/conflict/policy-impact over a materialized node/edge snapshot (`policy-engine/src/polisyos/fabric/world/materialize/kuzu.py:132-180`, `policy-engine/src/polisyos/fabric/world/materialize/kuzu.py:269-399`). The live Kuzu export is explicitly rebuild-only; `materialize_world_kuzu_from_duckdb(...)` defaults `kuzu_enabled=False`, and the temporal parity marker says graph temporal scope is `partial` with edge times only, not full bitemporal fact projection (`policy-engine/src/polisyos/fabric/world/materialize/kuzu.py:27-56`, `policy-engine/src/polisyos/fabric/world/materialize/kuzu.py:542-568`, `policy-engine/src/polisyos/fabric/world/materialize/kuzu.py:607-627`).

#### Calls and callers

- What it calls: IR world IDs/predicates/fact-log types, CAS artifact store, Fabric governance/security/temporal helpers, `SimulationDB`, DuckDB, optional Kuzu, and runtime observability. It does **not** import Foundry mechanisms, SKG, or runtime workspace loops, consistent with architecture directionality.
- What calls it: Fabric docs and claims pipelines emit/persist facts; Scholar bundles write fact segments (`policy-engine/src/polisyos/scholar/orchestrator/bundle.py:196-201`); Lex/normpack/legal evaluation emit world nodes/events; Data Forge legal batch/corpus code uses `stable_world_provenance_v1`; Fabric storage adapters query `query_world_table`; runtime temporal code projects temporal scope into Fabric world queries. I did not find a GY workspace-loop caller that binds a generated policy candidate/value update back into `fabric/world`; that remains the bridge gap.

#### Probe evidence

Probe command used `JAX_PLATFORMS=cpu PYTHONPATH="$PWD:$PWD/src" uv run python` and public world-store APIs. The first attempt intentionally revealed an operational edge case: creating `SimulationDB` at a path named `world.duckdb` caused DuckDB to report `Ambiguous reference to catalog or schema "world"`, so the successful probe used `sim.duckdb`.

```text
segments 2 2 3 2 0 0
segment_ids ['pass5_base_1782324232', 'pass5_future_1782324232']
current [{'node_id': 'claim.pass5_world', 'kind': 'claim', 'label': 'Pass5 future label'}]
as_of_valid_2026 [{'node_id': 'claim.pass5_world', 'kind': 'claim', 'label': 'Pass5 base label'}]
as_of_valid_2028 [{'node_id': 'claim.pass5_world', 'kind': 'claim', 'label': 'Pass5 future label'}]
as_of_tx_2000_empty True
snapshot world_snapshot_20260624T180353Z_fba7c513 True main 2027-01-01T00:00:00Z
branch scenario_pass5 scenario simulated 1 True
resolved_branch True main
branch_query [{'node_id': 'claim.pass5_world', 'label': 'Pass5 future label'}]
adapters [('delta_table', False, False, False), ('duckdb_native_file_copy', True, True, True), ('iceberg_table', False, False, False)]
kuzu_contract rebuild False 1 0
kuzu_temporal partial ('world.world_edges',) ('world.world_facts_as_of_projection',)
```

Interpretation: the write -> index -> materialize -> query path inserted three facts from two segments; current materialized node state chose the later valid-time label; bitemporal `as_of_valid_time` filtered the future label out for 2026 and included it for 2028; an `as_of_tx_time` before the facts returned empty; a DuckDB snapshot file was created; a scenario branch was registered with simulated state and scenario contract; query-through-branch resolved the retained snapshot; only the DuckDB adapter is currently create/query/merge capable; Kuzu is rebuild-only and partially temporal.

#### Verdict and disposition

- Verdict: **REAL-and-CURRENT epistemic world substrate**, not legacy, not shadow, not greenfield. It is the append-only bitemporal/provenance/snapshot/branch materialization half of the north-star world model.
- Bounded truth: it is not the causal/mechanistic simulator by itself. It stores and materializes facts, evidence objects, graph edges, provenance, quality/trust/conflicts/events, snapshots, and branches. It does not contain Foundry `GlobalState`/NCM/GCM mechanisms, SKG causal priors, or DataSnapshot-to-mechanism bindings, and it has no `WorldModelRecord` lifecycle type tying those pieces together.
- Corrected north-star verdict: the world model is **UNIFY_EXISTING / REWORK_TO_FIT**, not producer-missing greenfield. It is `fabric/world` (epistemic facts, bitemporal validity, provenance, snapshots/branches) + Foundry `GlobalState`/GCM/NCM/program graph (mechanisms and simulatable state) + SKG/literature priors + Fabric/DataSnapshot -> Foundry binding. The missing owner is a content-bound lifecycle bridge (`WorldModelRecord`) and a controller that writes deployment/posterior updates into `fabric/world` and rebuilds/binds mechanisms for simulation.
- Disposition: `USE_AS_IS` for append-only fact/event storage, DuckDB materialization, bitemporal/snapshot/branch query, governance/audit, and Kuzu rebuild/fallback graph traversal. `REWORK_TO_FIT` for GY: add the lifecycle envelope and bridge into Foundry/SKG/binding; add world-update consumers for post-deploy learning. Do **not** build a parallel world store (P27/P30 risk).

Open questions for the sweep:

- Is there already a higher-level `WorldModelRecord` / model-state lifecycle owner outside `fabric/world`?
- Is there a hidden Bayesian/posterior updater that can emit new facts/edges into `fabric/world` after deployment?
- Can any existing Fabric/Foundry bridge already bind a Fabric snapshot/branch id to Foundry `GlobalState` and causal mechanisms, or is that the exact new bridge?

### Pass 5 Hidden Useful-Code Sweep: Subsystem Census

Status: Pass 5 done for the targeted hidden-code sweep. This was intentionally breadth-first to avoid repeating the `fabric/world` miss; only owners relevant to a missing/partial cycle need were then read deeply.

#### Sweep method and coverage

- Enumerated top-level packages under `src/polisyos`: `berl`, `calibration`, `common`, `core`, `corpus`, `data_forge`, `data_requirement`, `ddm`, `evidence`, `fabric`, `foundry`, `ir`, `legal_requirement`, `lex`, `method_requirement`, `obligation_graph`, `obligation_rules`, `participation_requirement`, `pdc`, `policy_grammar`, `runtime`, `schemas`, `scholar`, `scholar_requirement`, and `scientist`.
- README/docstring sweep focus, checked against the existing coverage tracker:
  - `fabric`: connector-backed acquisition, docs/claims, world materialization/query. Hidden relevant owner found and read deeply: `fabric/world`.
  - `foundry`: computation layer, Trinity-to-execution plans, runtime state binding, methods, calibration, uncertainty, agent simulation. Hidden relevant owners found/read: `data_plane/bindings.py`, `execute/api.py`, Bayesian posterior owners, transport, and joint simulation precision.
  - `scientist`: workflow execution, nodes, governance, decision artifacts. Hidden relevant owners found/read: VOI scheduler and learned search policy.
  - `data_forge`: offline acquisition/normalization/publishing/read APIs and provenance snapshots. Hidden relevant owners found/read: snapshot finalization/binding and artifact refs.
  - `ir`: canonical contracts for Trinity, governance, analytics, observation, model layer. Hidden relevant owners found/read: `ModelSpec`, typed intervention halves, and transportability.
  - `ddm`: monitoring/drift/calibration/FDR. Already partially read in Pass 4; Pass 5 sweep found Bayesian primitives elsewhere, not a deployed Bayesian effect updater here.
  - `berl`, `calibration`, `corpus`, `legal_requirement`, `method_requirement`, `obligation_graph`, `obligation_rules`, `participation_requirement`, `scholar_requirement`, `lex`, `policy_grammar`, `data_requirement`, `pdc`, `runtime`, `schemas`, `scholar`, `core`, `common`: scanned for the flagged missing needs. Relevant discovered additions were `method_requirement` transport compilation and existing contracts/artifact refs; the rest were either already covered, requirement/gate compilers, evaluation fixtures, or non-controller support for GY.

#### Hidden-owner verdicts surfaced by the sweep

- World model / lifecycle: `fabric/world` is real; `ir/model_layer/model_spec.py`, `data_forge/kernel/snapshot/finalize.py`, `runtime/quality/data_forge_binding.py`, and `foundry/data_plane/bindings.py` add real lifecycle pieces. Verdict changes from broad producer-missing to `UNIFY_EXISTING` plus one lifecycle envelope.
- Post-deployment Bayesian/effect-learning: Foundry has real Bayesian posterior and calibration primitives, but no deployed-policy Bayesian updater/controller found. Verdict changes from "Bayesian effect update fully greenfield" to "controller greenfield over reusable posterior/calibration primitives".
- Joint simulation/general-equilibrium: Foundry has real shared-state execution, NCM parallel worlds, and coupled DES/ABM; the coupled ABM proof wrapper is stubbed, not the entire coupled engine. Verdict changes from weak `PARTIAL` to precise `PARTIAL: engine real, proof/calibration receipt stubbed, universal horizon controller missing`.
- Acquisition receipt/re-entry: Data Forge snapshot bindings and runtime validators are real, but the GY durable acquisition receipt and same-workspace re-entry bridge remain missing.
- VOI / experiment selection: Scientist has a real predictive VOI scheduler and learned routing policies; this does not execute acquisition, but it is reusable for GY-N3/N7 cycle scheduling.
- DesignProblem unifier: no hidden canonical `DesignProblem` record was found. `IR ProblemFrame` and `ModelSpec` are stronger than Pass 3 initially weighted, but they do not unify raw NL provenance, acquisition expectations, candidate frontier, world lifecycle, and authority profile.
- Intervention/lever/operator unifier: no hidden single atom was found. Trinity `InterventionSpec`/linker and proof-kernel `do()` algebra remain the two halves to bind.
- Transport / external validity: hidden real owner found. IR transportability + Foundry transport engine + density-ratio diagnostics are reusable gates for `transported_limited` rather than just labels.
- Calibration / uncertainty / identification: hidden Foundry Bayesian/calibration and transportability owners deepen the value/governance stack under Python 3.14; no need to block GY-N5 on DoWhy/EconML/CVXPY.

### IR ModelSpec, Data Forge Snapshot Binding, and Foundry Input Bindings: World-Lifecycle Pieces

Status: Pass 5 done. These files answer the open question "is there already a model/world lifecycle owner outside `fabric/world`?"

#### What they do

- `ModelSpec` is a real Trinity `how` contract, not a placeholder. It carries `model_id`, `data_snapshot_ref`, optional `registry_bundle_ref`, `time_semantics`, agent configuration, assumptions, environment, fidelity, and calibration refs (`policy-engine/src/polisyos/ir/model_layer/model_spec.py:179-260`). The model validators enforce unique assumptions/agent/environment ids and reject population shares above 1.0 (`policy-engine/src/polisyos/ir/model_layer/model_spec.py:263-289`). Agent/environment subcontracts exist for population, initial state, dynamics, and scope (`policy-engine/src/polisyos/ir/model_layer/model_spec.py:90-176`).
- Trinity already knows `ModelSpec` as one of the three canonical refs. `ModelSpecRef` exists in the core Trinity contract (`policy-engine/src/polisyos/core/contracts/trinity.py:56-69`), and `TrinityBundle` validates `ProblemFrame`, `PolicySpec`, and `ModelSpec` together (`policy-engine/src/polisyos/ir/trinity/__init__.py:22-29`).
- Data Forge snapshot finalization writes a durable binding rather than just a release marker. `finalize_snapshot(...)` reads publish manifests, hashes artifacts, writes `snapshot_manifest.json`, and calls `_write_snapshot_binding(...)` (`policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py:41-96`). `_write_snapshot_binding(...)` computes snapshot/release ids, Merkle root/data hash, read API identity, quality gates, transform lineage, claim requirement bindings, runtime event refs, and provenance manifest refs (`policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py:135-301`, `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py:346-460`).
- `ArtifactRef` is snapshot-aware and requires `polisyos://...@snapshot` shape plus provenance/version/license/retention metadata; its `snapshot_id` property parses the logical ref (`policy-engine/src/polisyos/data_forge/kernel/artifacts.py:43-74`). `SnapshotResolver` is a small in-memory logical-URI resolver (`policy-engine/src/polisyos/data_forge/kernel/snapshot/time_travel.py:16-42`); it is useful but not the Fabric bitemporal world query.
- Foundry input binding is the real `DataSnapshot -> GlobalState` bridge. `build_input_bindings(...)` loads a `DataSnapshot` and registry bundle, prepares and validates rules, builds a `GlobalState`, materializes slots into state, persists a state snapshot, and returns `FoundryInputBindings` plus a report (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:69-236`). It can infer mapping rules from payload paths matching registry slots/state paths (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:481-525`), validates target slot ids (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:528-538`), builds base state/entity sizes (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:541-593`), and materializes values with transform/coerce support (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:612-660`).
- Foundry execution treats input bindings as the canonical data boundary: `execute(...)` accepts `request.input_bindings_ref`, and `_resolve_state_from_input_bindings(...)` is the path to runtime state (`policy-engine/src/polisyos/foundry/execute/api.py:98-112`, `policy-engine/src/polisyos/foundry/execute/api.py:304-320`).
- Runtime Data Forge binding validators are substantive gates. They normalize snapshot binding docs (`policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:781-882`), scorecard gates (`policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:885-930`), detect missing role/snapshot/read API/lineage/manifest/Merkle fields (`policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:1119-1188`), and build official snapshot authority answers/read API identity (`policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:1808-1844`, `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:2044-2095`).

#### Probe evidence

```text
modelspec_invalid ValidationError 1 validation error for ModelSpec
modelspec_valid wm_probe_ok hybrid False
df_missing fail ['data_forge_snapshot_binding_missing']
df_keys ['bindings', 'capability_reality_status', 'issues', 'observed_at', 'release_id', 'release_manifest_ref', 'runtime_authority_envelope', 'schema_version', 'snapshot_id', 'status', 'summary']
df_validish fail 4 48 legal@snap_pass5
df_issue_codes ['data_forge_snapshot_merkle_root_missing', 'data_forge_snapshot_runtime_event_ref_missing', 'data_forge_snapshot_manifest_ref_missing', 'data_forge_snapshot_corpus_id_missing', 'data_forge_snapshot_creation_time_missing', 'data_forge_snapshot_lineage_refs_missing']
df_gates [('fail', 'data_forge_snapshot_merkle_root_missing'), ('fail', 'data_forge_snapshot_runtime_event_ref_missing'), ('fail', 'data_forge_snapshot_manifest_ref_missing'), ('fail', 'data_forge_snapshot_corpus_id_missing'), ('fail', 'data_forge_snapshot_creation_time_missing'), ('fail', 'data_forge_snapshot_lineage_refs_missing')] count 48
```

#### Verdict and disposition

- Verdict: **REAL-and-CURRENT lifecycle pieces**, not a single lifecycle owner. `ModelSpec` is the simulation/model contract; Data Forge snapshot binding is the data/read-surface contract; Foundry input bindings are the data-to-`GlobalState` execution bridge; runtime binding validation is a real gate.
- Missing: no `WorldModelRecord` unifies Fabric world snapshot/branch/as-of time, SKG priors, Data Forge snapshot binding/read API, ModelSpec, Foundry input bindings, mechanism refs, policy slots, regional/time semantics, and deployment/posterior update lineage.
- Disposition: `USE_AS_IS` for each piece; `REWORK_TO_FIT` by adding one content-bound lifecycle envelope and controller handoff. This further revises the world-model verdict away from "producer missing": the missing capability is `bridge_missing` / `implemented_but_not_orchestrated`.

### Scientist VOI and Learned Search Scheduling

Status: Pass 5 done. This hidden owner matters for GY-N3/N7 scheduling and refinement budget, not for acquisition execution.

#### What it does

- `voi_scheduler.py` defines rich scheduling artifacts: `ParetoSnapshot`, `ComputeEconomicsDecision`, `SchedulingDecision`, `VOIObservation`, `PromotionObservation`, and `VOIModelSnapshot` (`policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:34-167`).
- `SimpleVOIScheduler.prioritize(...)` reads cheap candidate signals, frontier state, stage, and budget constraints; computes marginal/prioritized decisions; and applies explicit action gates for dominated candidates, exhausted budget, calibration reserve, timeout risk, and low ROI (`policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:169-212`, action logic at `policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:344-391`).
- `PredictiveVOIScheduler` stores VOI observations, promotion observations, and calibration records; can snapshot/restore state; reports model health; predicts objective/disagreement/duration/cost/timeout/promotion with ridge/fallback models; and falls back to conservative decisions when calibration is weak (`policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:448-647`, prediction at `policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:649-786`, fallback at `policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:788-792`). Feature extraction and cross-domain weighting are substantive (`policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:926-1036`), and VOI reports are persistable (`policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:1044-1289`).
- `advanced_policy.py` adds learned policies rather than only heuristics: an RBF surrogate trains on evaluations (`policy-engine/src/polisyos/scientist/methods/search/strategies/advanced_policy.py:380-418`), `LearnedVOIPolicy` computes ridge-linear learned VOI (`policy-engine/src/polisyos/scientist/methods/search/strategies/advanced_policy.py:425-473`), and learned routing/population scheduling exist (`policy-engine/src/polisyos/scientist/methods/search/strategies/advanced_policy.py:476-560`).

#### Probe evidence

```text
voi_decision advance 0.8506 predictive 0.6058
voi_stop stop_search
voi_challenge run_adversarial_challenge
```

The probe created candidate/search signals and observed that the scheduler computed a nonconstant advance decision, a stop condition, and an adversarial challenge trigger from changed inputs.

#### Verdict and disposition

- Verdict: **REAL VOI/search scheduling organ**, implemented but not orchestrated into GY. It is not the acquisition planner and does not execute data acquisition; it schedules candidate evaluation/search work.
- Disposition: `USE_AS_IS` for scoring, budget, calibration and persistable decision/report structures; `REWORK_TO_FIT` to feed it canonical candidate/value/acquisition signals and make it the GY-N3/N7 stopping/escalation policy. This collapses any "build a VOI scheduler from scratch" plan into rework/wire-existing.

### Foundry Bayesian, Posterior, and Calibration Primitives

Status: Pass 5 done. This rechecks whether post-deployment Bayesian update is completely greenfield or can reuse Foundry organs.

#### What they do

- `foundry/methods/catalog/bayesian/variational.py` implements a real NumPy mean-field variational inference estimator. The protocol includes posterior slots and uncertainty envelope outputs (`policy-engine/src/polisyos/foundry/methods/catalog/bayesian/variational.py:87-104`), and `pure_step(...)` computes closed-form CAVI posterior updates, ELBO diagnostics, truthfulness diagnostics versus reference posterior when present, prediction output, and credible intervals (`policy-engine/src/polisyos/foundry/methods/catalog/bayesian/variational.py:306-375`, `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/variational.py:383-493`).
- `PosteriorResult` is a typed posterior artifact with means/stds/intervals/diagnostics/warnings/prior-sensitivity/truthfulness (`policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py:1533-1565`). Validators infer truthfulness state from diagnostics and warnings (`policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py:1567-1614`), and `to_truthfulness_receipt(...)` builds a receipt (`policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py:1625-1647`).
- `BayesianVAREstimator` computes a real Bayesian VAR with NumPy/SciPy: ridge/Minnesota-prior posterior mean, standard errors, intervals, and uncertainty envelope (`policy-engine/src/polisyos/foundry/methods/catalog/econometrics/expansion.py:151-288`).
- `uncertainty_adapter.py` builds Hessian-normal approximations and summarizes Bayesian calibration posterior draws into envelopes and uncertainty decompositions (`policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py:48-126`, `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py:147-228`).
- DDM remains useful but not this owner: `ddm/integration/model_registry.py` gates monitoring registration (`policy-engine/src/polisyos/ddm/integration/model_registry.py:21-128`), threshold calibration exists (`policy-engine/src/polisyos/ddm/calibration/calibrate.py:260-330`), and online FDR exists (`policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:8-93`), but I found no deployed-policy Bayesian effect updater writing posterior effects back into the world model.

#### Probe evidence

```text
bayes_vi 1.0342 credible_interval APPROXIMATE_UNCALIBRATED
bayes_calib 1.1 (0.86, 1.34) bayesian
```

The probe fit the variational estimator and summarized posterior draws; both returned computed numeric estimates/envelopes under the Python 3.14 dependency set.

#### Verdict and disposition

- Verdict: **REAL Bayesian/posterior primitives**, not a deployed monitoring controller. Pass 4's "Bayesian effect updater greenfield" is refined: the updater/controller is greenfield, but its posterior/calibration primitives should be reused.
- Disposition: `USE_AS_IS` for posterior artifacts, VI/BVAR estimators, calibration envelopes, and truthfulness receipts. `BUILD-NEW` only for deployed-policy confirmatory updater + exploratory anomaly-to-hypothesis controller + Fabric world write-back.

### Transportability and External-Validity Stack

Status: Pass 5 done. This owner changes the status of `transported_limited` from a mostly label/gate concept to a real computational stack.

#### What it does

- IR transportability defines typed selection diagrams and sigma variables (`policy-engine/src/polisyos/ir/analytics/transportability.py:69-249`), plus `TransportFormula`, `TransportabilityStatus`, `TransportMode`, and `TransportabilityResult` with identified/partial/bounds/unsupported states and strict validators (`policy-engine/src/polisyos/ir/analytics/transportability.py:364-585`). `build_selection_diagram(...)` builds diagrams from context deltas, and results can be persisted (`policy-engine/src/polisyos/ir/analytics/transportability.py:594-675`).
- Foundry `solve_transportability(...)` tries direct/PAG/simplified/symbolic/bounds backends, applies privacy context, and returns unsupported only after backends are exhausted (`policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:39-161`). The symbolic backend attempts formal transportability identification and then frontdoor/rule2/c-component/rule3 fallbacks (`policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:342-434`). Bounds-only mode calls `transport_bounds` or a Manski-style fallback (`policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:437-470`), and direct/simplified results are explicit (`policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:473-541`, backend ordering at `policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:796-811`).
- The old `transport_check.py` path is a delegated shim rather than a second authority: it calls the canonical engine and emits proof bundle/negative certificate (`policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_check.py:65-180`).
- `DensityRatioEstimator` estimates source-to-target transport weights and diagnostics (`policy-engine/src/polisyos/foundry/methods/catalog/causal/density_ratio.py:724-889`).
- G2 causal forecast search already reaches SKG transport evidence: it queries SKG edges and transport-score rows with SKG snapshot/version traces (`policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py:1117-1235`).
- `method_requirement` compiles transportability requirements from claims: the requirement enum includes transportability (`policy-engine/src/polisyos/method_requirement/models.py:21-28`), specs carry requirement/status/proof fields (`policy-engine/src/polisyos/method_requirement/models.py:88-126`), and the compiler emits `TRANSPORT_CERTIFICATE`, `TARGET_POPULATION_LIMITS`, or `DO_NOT_TRANSPORT` based on claim/context tokens (`policy-engine/src/polisyos/method_requirement/compiler.py:93-108`, `policy-engine/src/polisyos/method_requirement/compiler.py:319-331`), alongside uncertainty/fairness/strategic/simulation requirements (`policy-engine/src/polisyos/method_requirement/compiler.py:334-440`).

#### Probe evidence

```text
density_ratio 4 0.3832 logistic_trick
transport_direct identified direct 1.0 simplified_legacy
transport_shifted identified transport_formula 0.95 True
```

The probe estimated density-ratio diagnostics, solved a direct same-context transport case, and solved a shifted-context case with a transport formula and confidence.

#### Verdict and disposition

- Verdict: **REAL transport/external-validity organ**, not a shadow label. It is not currently sequenced by the GY cycle, but it can enforce or qualify value transfer and promotion.
- Disposition: `USE_AS_IS` for selection diagrams, transport solver, density-ratio diagnostics, method requirements, and G2/SKG transport traces. `REWORK_TO_FIT` to feed `WorldModelRecord` source/target contexts and attach `transported_limited` receipts to value/promotion packets.

### Joint Simulation Precision Pass: Coupled DES/ABM, NCM, Shared State

Status: Pass 5 done. This resolves what "coupled ABM proof result is stubbed" means.

#### What it does

- `foundry/methods/catalog/simulation/coupled.py` runs a real coupled policy simulation: `_run_coupled_policy(...)` builds `GlobalState`, creates a queue runtime, executes `CoupledContractsExecutor`, advances a horizon, and returns queue trajectory/final state/summary/metrics (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:57-145`). `CoupledPolicySimulationEstimator.pure_step(...)` returns a real method result from that run (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:148-225`). Queue MLE and SMM estimators are also real (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:228-424`).
- The stub is specifically the attached ABM proof wrapper: `_run_coupled_policy(...)` sets `abm_result = _abm_result_stub(...)` (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:140-144`), and `_abm_result_stub(...)` creates deterministic fake artifact refs with notes `phase4_abm_result_stub` and `diagnostics_not_attached` before calling `build_abm_result_from_simulation(...)` (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/dynamics.py:33-40`). That is a proof/calibration receipt stub, not evidence that the coupled queue/horizon engine is fake.
- Foundry shared-state program execution is real and general: the graph executor runs ordered nodes, patches and merges records into visible shared state, applies constraints, and records node outputs (`policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py:114-260`).
- NCM can simulate nonlinear joint interventions over parallel worlds. `_predict_from_abducted`, `_counterfactual_world`, and `_parallel_worlds` propagate shared exogenous noise and interventions through the causal model (`policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:691-890`).

#### Verdict and disposition

- Verdict: **PARTIAL joint simulation**. Real engines exist for shared-state mechanism execution, NCM parallel worlds, and a domain-specific coupled DES/ABM horizon. The missing capability is a universal controller and proof/calibration receipt, not a complete simulator rewrite.
- Disposition: `USE_AS_IS` for shared-state executor, NCM, and coupled queue horizon where applicable. `REWORK_TO_FIT` by building a horizon controller over these engines and replacing `_abm_result_stub` with a content-bound simulation proof/calibration receipt. No hidden general-equilibrium owner was found.

### Three Hardest Seams: Field-Level Contracts

Status: Pass 5 done. These are not production code changes; they are the code-grounded contracts the rewritten GY tasks should target.

#### 1. InterventionAtomBinding

Existing halves read:

- Trinity executable action: `InterventionSpec` carries `intervention_id`, `kind`, `target`, `schedule`, `params`, `priority`, `enabled`, `lex_provision_ref`, population/sector/region, measurement expectations, identification mode, and strategic-response fields (`policy-engine/src/polisyos/ir/governance/policy_spec.py:73-108`).
- Trinity linker: `link_trinity(...)` validates selectors/mechanisms/params, resolves mechanism registry slots, and records read/write state slots in `LinkedIntervention` (`policy-engine/src/polisyos/ir/linker/_trinity_linker.py:28-178`).
- Proof-kernel causal side: `QueryTarget`/context and `VariableAssignment`/`NodeIntervention` express `do(X=x)` and richer conditional/stochastic/MTP/edge/path intervention forms (`policy-engine/src/polisyos/ir/analytics/interventions.py:134-289`); composition and identification plans validate intervention compatibility and backend obligations (`policy-engine/src/polisyos/ir/analytics/interventions.py:675-810`, `policy-engine/src/polisyos/ir/analytics/interventions.py:930-1035`).

Content-bound bridge fields:

- `atom_id`, `schema_version`, `problem_frame_ref`, `policy_spec_ref`, `intervention_id`.
- `operator_kind`: Trinity `kind` plus proof-kernel intervention type (`node`, `conditional`, `stochastic`, `MTP`, `edge`, `path`, `transport`).
- `target_selector`: Trinity `target` plus `target_population_type`, `target_sector_ids`, `target_region_ids`.
- `target_world_slots`: `LinkedIntervention.writes_slots`; `read_slots`: `LinkedIntervention.reads_slots`.
- `direct_effect_bundle`: Trinity `params`, `schedule`, `priority`, `mechanism_id`, mechanism config overrides, transform/coerce refs, and `lex_provision_ref`.
- `causal_do_expr`: proof-kernel `NodeIntervention.assignments` or richer expression payload, including `VariableAssignment.variable`, `value`, `value_expr`, and selection/context refs.
- `intended_downstream_estimand`: `QueryTarget` outcome variables, conditioning set, source/target populations, functional, and metric/unit.
- `causal_path_or_identification_plan_ref`: backend/status/conditions from `InterventionIdentificationPlan`.
- `world_model_record_ref`: Fabric snapshot/branch/time, ModelSpec, SKG, and Foundry state binding version.
- `measurement_expectations`: retained from Trinity but downgraded to supporting metadata once the causal estimand exists.
- `content_hash`, `producer_ref`, `provenance_refs`, and lifecycle `status` in `candidate_unverified | grounded | valued | promoted | blocked`.

Disposition: `BUILD-NEW` bridge artifact over existing halves; do not build a second intervention hierarchy.

#### 2. WorldModelRecord / Lifecycle Envelope

Existing interfaces:

- Fabric world exposes append-only facts/events/docs/claims/trust/quality/conflicts, provenance, bitemporal materialization, snapshot/branch, and query fields: `snapshot_root`, `snapshot_id`, `branch`, `as_of_tx_time`, `as_of_valid_time`, classification/row policy/audit (`policy-engine/src/polisyos/fabric/world/query.py:124-155`, `policy-engine/src/polisyos/fabric/world/query.py:157-266`).
- Data Forge exposes `snapshot_id`, `release_id`, read API identity, Merkle/data hash, quality gates, lineage, and requirement bindings through snapshot binding (`policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py:135-301`).
- `ModelSpec` exposes simulation contract: `model_id`, `data_snapshot_ref`, registry bundle, time semantics, agents, assumptions, environment, fidelity, calibration refs (`policy-engine/src/polisyos/ir/model_layer/model_spec.py:179-260`).
- Foundry input bindings expose the actual bound `GlobalState`, state snapshot, registry bundle, mapping rules, validation report, and `input_bindings_ref` execution boundary (`policy-engine/src/polisyos/foundry/data_plane/bindings.py:69-236`, `policy-engine/src/polisyos/foundry/execute/api.py:98-112`).
- SKG/G2 exposes causal priors and transport traces through SKG snapshot/version query traces (`policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py:1117-1235`).

Bridge fields:

- Identity/authority: `world_model_record_id`, `schema_version`, `authority_status`, `created_at`, `producer_ref`, `content_hash`.
- Scope: `region_or_jurisdiction`, `population_scope`, `policy_domain`, `valid_time_scope`, `tx_time_scope`, `resolution`, and `branch_mode` (`observed | scenario | deployment_update`).
- Fabric world ref: `snapshot_root`, `snapshot_id`, `branch`, `as_of_valid_time`, `as_of_tx_time`, `world_query_policy`, `provenance_manifest_ref`.
- Data Forge binding ref: `snapshot_id`, `release_id`, `read_api_identity`, `snapshot_ref`, `merkle_root`, `data_hash`, `claim_requirement_bindings`, `quality_gate_refs`, `lineage_refs`.
- Simulation model ref: `model_spec_ref` or embedded `ModelSpec` hash, `registry_bundle_ref`, `mechanism_refs`, `GCM/NCM/program_graph_refs`, assumptions and fidelity/calibration refs.
- Foundry binding ref: `input_bindings_ref`, `bound_state_snapshot_ref`, `mapping_rules_ref`, `state_slot_digest`.
- SKG/causal-prior ref: `skg_snapshot_ref`, `skg_version_id`, edge/prior refs, transport-score refs.
- Policy slot map: `slot_id`, `state_path`, unit, entity scope, temporal granularity, and relation to `InterventionAtomBinding.target_world_slots`.
- Deployment update refs: feedback/reissue/refute/incidents/posterior-update refs that can write back into Fabric world and trigger rebind/recalibration.
- Limitations: unavailable data, transport limits, calibration envelope status, unresolved conflicts, and admissibility blockers.

Disposition: `BUILD-NEW` one bridge type/lifecycle controller; `USE_AS_IS` all four underlying substrates. Dedicated world-model-lifecycle task is required before robust GY-N3/N5 because candidate value must name the exact world version it runs against.

#### 3. JointSimulationHorizonController

Existing engines and exact gap:

- Shared-state executor can run many mechanism nodes against one state and merge outputs (`policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py:114-260`).
- NCM can run multi-intervention counterfactual worlds with shared exogenous noise (`policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:691-890`).
- Coupled DES/ABM queue horizon is real, while its ABM proof receipt is stubbed (`policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:57-145`, `policy-engine/src/polisyos/foundry/methods/catalog/simulation/dynamics.py:33-40`).
- Coupling composition can classify/limit/require proof for shared-resource/feedback interactions, but it is a gate, not the runner (`policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py:1255-1533`).

Controller input contract:

- `world_model_record_ref`.
- `intervention_atoms: list[InterventionAtomBinding]`.
- baseline/comparator policy refs and selected outcomes/estimands.
- `horizon`: start/end/step, valid-vs-transaction time semantics, scenario branch policy.
- engine plan: `program_graph | ncm_parallel_worlds | coupled_des_abm | system_dynamics | method_registry_estimator`, with eligibility conditions.
- data/acquisition requirements, transport requirements, calibration requirements, budget/seed/replication policy.
- escalation rules: individual -> pairwise -> joint, feedback/shared-resource blocker handling, counterexample thresholds, acquisition-required terminal.

Controller output contract:

- Per-atom and joint trajectories, marginal effects, interaction terms, shared-resource/feedback classifications, and general-equilibrium limitations.
- Uncertainty/calibration receipts, transportability receipts, and simulation proof receipts replacing the current coupled ABM stub.
- Counterexamples/refinement decisions suitable for the S2 discipline and VOI scheduler.
- Acquisition requests/receipts for blocked world slots.
- Promotion-ready value packet with `WorldModelRecord`, atom bindings, grounding refs, method refs, and authority blockers.

Disposition: `REWORK_TO_FIT` over Foundry/shared-state/NCM/coupled engines plus `BUILD-NEW` thin horizon controller. Do not classify current state as pairwise-only, but do not claim a universal joint simulator exists.

### Live Operational Probes: Gateway and OpenAlex

Status: Pass 5 done. These probes check current credentials/external behavior; they do not replace the fake-client probes used for body-level control-flow proof.

#### LLM gateway

Relevant code anchors:

- Gateway config loads `.env`, defaults base URL to `https://proxy.gonka.gg/v1`, validates plausible `sk-` key shape, and creates traced/cached/sanitized clients (`policy-engine/src/polisyos/scientist/orchestration/llm/factory.py:85-146`, client construction at `policy-engine/src/polisyos/scientist/orchestration/llm/factory.py:149-248`).
- `GatewayLLMClient.generate(...)` posts OpenAI-compatible `/chat/completions`; `list_model_ids(...)` calls `/models` (`policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py:215-274`, `policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py:276-330`).
- `LLMDrafterAgent.draft_policy(...)` calls the LLM with JSON mode and parses `DraftResult`; fallback only occurs on JSON parse/type/value errors (`policy-engine/src/polisyos/scientist/agent/drafter_clients.py:337-420`).
- `LLMCriticAgent.critique(...)` calls the LLM with JSON mode and falls back only on call failure or parse/value issues (`policy-engine/src/polisyos/scientist/agent/critic.py:431-560`).

Probe output, key masked:

```text
gateway_config True https://proxy.gonka.gg/v1 sk-3d...be44
gateway_models 3 [] ['Qwen/Qwen3-235B-A22B-Instruct-2507-FP8', 'moonshotai/Kimi-K2.6', 'MiniMaxAI/MiniMax-M2.7']
drafter_error RuntimeError Gateway request failed (400): {"error":{"message":"unsupported model \"gpt-5-mini\"; supported models: Qwen/Qwen3-235B-A22B-Instruct-2507-FP8, MiniMaxAI/MiniMax-M2.7, moonshotai/Kimi-K2.6"}}
critic_result REJECT 4 0.0 0.0
critic_first_issue No interventions defined in policy_spec
gateway_call_observer []
```

Interpretation: the project profile `gpt-5-mini` exists in code, but this live gateway account does **not** support it today. The critic result here is fallback/degraded because the gateway call failed fast; it is useful as an operational failure record, not proof of model-backed critique.

Supported-model rerun:

```text
gateway_supported_client True Qwen/Qwen3-235B-A22B-Instruct-2507-FP8
drafter_supported_result draf7892_pass5_live 2 0.85 True
drafter_supported_interventions ["{'name': 'EITC Top-Up Credit', 'description': 'Provides an additional refundable tax credit to low-income workers who qualify for the existing EITC, paid upon annual tax filing.', ", "{'name': 'Small Employer Hiring Incentive', 'description': 'Provides a time-limited payroll tax reduction for small employers who formally hire and retain low-income workers for at"]
drafter_supported_narrative This policy proposal introduces a two-part intervention to increase take-home pay for low-income workers while maintaining administrative feasibility, minimizing fraud risk, and adhering to a strict budget cap. First, an
critic_supported_result REJECT 7 0.1 0.2
critic_supported_issue ProblemFrame defines no objectives, making it impossible to assess policy alignment or optimize interventions.
critic_supported_metadata_raw REJECT
gateway_supported_call_observer [{"completion_tokens": 798, "latency_ms": 32610, "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "prompt_tokens": 635, "provider": "gateway", "status": "success"}, {"completion_tokens": 863, "latency_ms": 29048, "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "prompt_tokens": 2372, "provider": "gateway", "status": "success"}]
```

Verdict: **real credentialed LLM gateway path works through real drafter and critic organs**, but the default documented `gpt-5-mini` profile is operationally unsupported by the current gateway account. GY-N2 can reuse the LLM organs, but the rewritten task must make model-profile selection/catalog validation an explicit preflight.

#### OpenAlex

Relevant code anchor: `OpenAlexClient` wraps live provider requests with rate limiting, retries, and typed `OpenAlexRequest`; `list_works(...)` calls the real OpenAlex API path (`policy-engine/src/polisyos/data_forge/domains/academic/openalex/client.py:17-29`, `policy-engine/src/polisyos/data_forge/domains/academic/openalex/client.py:32-134`).

Probe output:

```text
openalex_result 755 https://openalex.org/W2126854401 2001 838
openalex_title Welfare, the Earned Income Tax Credit, and the Labor Supply of Single Mothers
```

Verdict: **live OpenAlex provider path works**. This de-risks GY-N4's external acquisition execution, but does not create the missing acquisition receipt/re-entry bridge.

## Cross-Cutting Findings

### A. The Three Parallel Worlds Map

Pass 4 comprehensive refinement, after reading generation, loop, shadow search, value, world-model, acquisition, monitoring, and authority owners:

1. Runtime NL / agent-circuit front door.

- Real owner: `_execute_nl_pipeline(...)` accepts raw `nl_request`, publishes runtime-quality sidecar artifacts, can build a Scientist `ProblemFrame` and Trinity/final-claims bundle through the local agent circuit, then wraps the selected variant into `ExperimentState` for `scientist.api.run_experiment(...)` (`runtime/http/services/control/nl_pipeline.py:1131-1159`, `runtime/http/services/control/nl_pipeline.py:3128-3219`, `runtime/http/services/control/nl_pipeline.py:4448-4482`, `runtime/http/services/control/nl_pipeline.py:6389-6597`).
- Verdict: `REAL` front door and publication bridge, but not the generation-cycle controller. The mock PI/data-need/agent path is input-sensitive but templated/hardcoded in the bodies read (`scientist/agent/pi.py:82-133`, `scientist/agent/data_need_extractor.py:34-92`; mock probe in Pass 1).

2. Scientist policy workflow world.

- Real owners: workflow selection/build/execution in `scientist.api.run_experiment(...)`, `selection.py`, `builder.py`, `policy_design.py`; explicit `scientist_policy_design` runs a policy-design DAG, while plain policy params select `scientist_policy_verified` (`scientist/api.py:212-328`, `scientist/orchestration/workflows/selection.py:42-97`, `scientist/orchestration/workflows/builder.py:510-724`).
- It has the closest production-shaped evaluate/search surface: a Trinity-to-`PolicyCandidateSchema` bridge and hierarchical search can evaluate bounded candidates and fail closed on missing Lex bounds (`scientist/policy_design/schema.py:293-339`, `scientist/nodes/builtins/policy/run_hierarchical_policy_search.py:181-218`, `scientist/policy_design/search.py:1228-1308`; Pass 1 search probe).
- Verdict: `REAL` workflow/evaluation/search machinery, but the default/plain-policy candidate source is scripted/hardcoded: verified-policy service creates one verified option plus optional hypothesis option, and mock formalization emits a fixed tax-subsidy Trinity (`scientist/validation/policy_verified/service.py:457-558`, `scientist/agent/formalizer.py:1357-1414`). Pass 3 revised the generator picture: real LLM-backed organs exist (`LLMDrafterAgent.draft_policy`, `LLMFormalizerAgent.formalize`, `LLMCriticAgent.critique`, and multipass drafter/critic orchestration), but they are not currently selected as the GY cycle's canonical generator (`scientist/agent/drafter_clients.py:328-408`, `scientist/agent/formalizer.py:1519-1644`, `scientist/agent/critic.py:417-510`, `scientist/agent/_drafter_orchestrator.py:64-226`; Pass 3 generator probe). `run_policy_blueprint_runtime` is downstream runtime/evaluation/promotion plumbing, not a candidate generator (`scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:307-384`).

3. Honest GY workspace loop.

- Real owner: `runtime/quality/workspace/loop.py` defines the active Slice-0 operation set and trajectory as exactly `BIND -> ESTIMATE -> VERIFY` (`runtime/quality/workspace/loop.py:110-113`); `OperationRegistry.active_operation_classes()` only returns executable registrations in that active set (`runtime/quality/workspace/loop.py:242-255`).
- `run_fixture(...)` rejects non-`seed_trajectory` planner kinds, inactive operations, and any trajectory other than `BIND/ESTIMATE/VERIFY`; it returns `cycle_index=3`, artifacts, authority, ledger, obligations, VOI, and terminal state from that fixed path (`runtime/quality/workspace/loop.py:1471-1664`; fixture probes in the per-asset section).
- `run_intent(...)` is a Phase-2 adapter, not the same thing as the fixture loop: it selects a playbook, executes only `run_causal_evaluation` and `run_normative_arbitration`, marks `plan_policy_request` out of scope, consumes causal outputs through `FoundryMethodOutputConsumer`, and exits `FRONTIER_STABLE` with `descriptive_only` authority (`runtime/quality/workspace/loop.py:1266-1469`; intent probe in the per-asset section).
- Verdict: `REAL honest backbone` for measurement/evidence packets and Foundry-method consumption, but `single-pass` and `descriptive_only`. It does not generate, revise, or promote design candidates; `_assert_workspace_artifact_cut_lines(...)` forbids `DesignCandidate`/`grounded_admissible` artifacts (`runtime/quality/workspace/loop.py:1798-1815`), and `_authority_boundary(...)` downgrades to measurement/descriptive authority (`runtime/quality/workspace/loop.py:2131-2165`).

4. Layer-2 S2 shadow design search.

- Real owner: `run_s2_shadow_design_loop(...)` builds one boundary, one grammar expansion, one candidate, one constraint-store snapshot, one counterexample, one refinement decision, one search-ledger iteration, and one shadow design record (`pdc/_impl/layer2_design_search.py:933-1103`).
- The grammar/candidate are hardcoded: `_grammar_expansion(...)` fixes the family set around credit guarantee / interest buy-down / cash grant (`pdc/_impl/layer2_design_search.py:1441-1467`), and `_candidate(...)` emits a fixed `credit_guarantee` candidate with fixed parameterization (`pdc/_impl/layer2_design_search.py:1470-1534`).
- The refinement discipline is real and reusable: `DesignGrammarExpansion`, `DesignCandidateV0`, `ConstraintStoreSnapshot`, `CounterexampleRecord`, `RefinementDecision`, and `SearchLedger` carry explicit grammar, blocker, no-retry, and next-step semantics (`pdc/_impl/layer2_design_search.py:632-880`); probe variants showed `a_spec_gap -> governance_required`, `substrate_gap -> acquisition_required`, and same-candidate retry -> blocked.
- Verdict: `SHADOW + HARDCODED + single-iteration replay`, not a real generator/cycle. Not dead: caller scan found validation tools, corpus generation, and tests using it. The discipline is `REWORK_TO_FIT`; the fixed candidate/projector is shadow-only.

5. Promotion and bounded-agent side worlds.

- G4 governed promotion and the Ring-2 waist are real enforcement owners, but they are not called by the workspace loop, S2 loop, or Scientist policy-design path in the callers read. Ring-2 rejects LLM promotion and uncalibrated simulation authority (`pdc/_impl/gy_waist.py:91-129`, `pdc/_impl/layer2_readiness.py:62-114`); G4 validates complete G1/G2/G3/GL grounded contract sets and can produce `governed_promoted` only under explicit complete inputs (`runtime/quality/proving_ground/governed_promotion_gate.py:1500-1703`, `runtime/quality/proving_ground/governed_promotion_gate.py:1999-2111`, `runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`; promotion probe in per-asset section).
- G6 bounded agent and `AgentEventBridge` are real candidate-only routing/audit surfaces, but not a GY cycle controller. G6 routes the pinned same-class request to G5, produces candidate-unverified handoffs, and records partial-budget-cutoff search ledgers (`runtime/quality/proving_ground/bounded_request_agent.py:1318-1462`, `runtime/quality/proving_ground/bounded_request_agent.py:1516-1608`); `AgentEventBridge` records `agent_ring1_hint_only` candidate-only events and fail-closes with `producer_missing` if no client is supplied (`runtime/quality/workspace/agent_proposal_bridge.py:51-208`).

6. Shared execution organs outside all three worlds.

- Foundry program-graph execution and NCM intervention semantics can jointly propagate multiple mechanisms/interventions; Fabric ingestion can materialize a `DataSnapshot`; Scholar/OpenAlex and Data Forge/SKG can search and ground literature; DDM and decision-feedback owners can monitor deployed outcomes. These are real organs, but no one of the three candidate/control worlds constructs one production, data-bound, versioned world model and schedules all of them (`policy-engine/src/polisyos/foundry/compile/_graph.py:20-122`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:691-890`, `policy-engine/src/polisyos/fabric/data_plane/orchestrator.py:511-639`, `policy-engine/src/polisyos/scholar/search/service.py:214-528`, `policy-engine/src/polisyos/scientist/feedback/core.py:204-355`).
- The intervention is split across Trinity `InterventionSpec` and proof-kernel causal intervention expressions. The former is executable policy action metadata; the latter is typed `do()` algebra. There is no content-bound bridge making the policy atom's direct state-edit bundle and downstream causal path one artifact (`policy-engine/src/polisyos/ir/governance/policy_spec.py:73-108`, `policy-engine/src/polisyos/ir/analytics/interventions.py:134-184`).

Current definitive relation summary:

- No single owner currently implements NL -> design problem -> generate -> ground -> value -> revise -> promote as a cycle.
- The `scientist_policy_design` world is the closest live evaluate/search DAG. Its default/plain-policy input source is scripted, but Pass 3 found reusable real LLM generator organs beside it; the missing piece is orchestration and authority fencing, not raw model-calling capability.
- The workspace loop is the honest backbone for descriptive measurement/evidence packets and reachable Foundry-method consumption; it is single-pass and intentionally not a design generator or promotion surface.
- S2 is the shadow replay/design-search world: valuable refinement discipline, fixed one-shot credit-guarantee body, shadow-only authority.
- Fabric/Scholar/Data Forge/SKG/candidate-firewall owners provide real acquisition/grounding execution, but the workspace loop only plans acquisition and no scanned GY owner calls candidate claim grounding in-cycle.
- G4/Ring-2/S6/S7/S8/scorecard are the real promotion/governance/enforcement waist. G6/agent bridge is a real candidate-only proposer/audit surface. These are adjacent owners, not orchestrated phases inside the cycle.
- The world-model/value/acquisition/monitoring organs are likewise adjacent. Their existence reduces GY to bridge/controller work in many places, but it does not make the cycle real: the decisive missing artifact chain is candidate atom -> world binding -> grounded/value result -> refinement -> governed promotion -> deployment observation.
- Pass 5 final correction: the world binding should not be built as a new store. It should be a `WorldModelRecord` over real adjacent owners: `fabric/world` for bitemporal epistemic facts/snapshots/branches, Data Forge snapshot binding for read-surface lineage, IR `ModelSpec` for model contract, Foundry input bindings/GlobalState/mechanisms for simulation, and SKG for causal priors. None of the three cycle worlds currently owns that lifecycle envelope.

### B. The Would-Be Cycle Data Flow

Pass 4 end-to-end trace, with exact break/fork points:

1. NL -> runtime intent/front door.

- Real owner: `_execute_nl_pipeline(...)` receives text and context (`runtime/http/services/control/nl_pipeline.py:1131-1159`), then builds/validates a `PolicyIntentEnvelope` and sidecar runtime-quality artifacts (`runtime/http/services/control/nl_pipeline.py:3128-3219`, `runtime/quality/assurance_case.py:311-425`).
- Break A: this output is not a canonical `DesignProblem`. Pass 1 found separate `PolicyIntentEnvelope`, Scientist `ProblemFrame`, verified-policy `PolicyRequestFrame`, Trinity bundle, S2 input, and `PolicyCandidateSchema` surfaces.

2. Intent/problem -> workflow fork.

- The runtime front door wraps selected variant artifacts into `ExperimentState` and calls `run_experiment(...)` (`runtime/http/services/control/nl_pipeline.py:6389-6597`, `scientist/api.py:212-328`).
- Break B: selector fields fork the world. Plain policy params go to `scientist_policy_verified`, not `scientist_policy_design`; explicit workflow/profile/policy-mode selects design (`scientist/orchestration/workflows/selection.py:42-97`; selector probe). Workspace `run_intent(...)` has its own playbook selector and executes only two Scientist aliases (`runtime/quality/workspace/loop.py:1266-1469`).

3. Generate candidate.

- Existing Scientist verified-policy path builds `PolicyRequestFrame`, legal packs, a scripted option set, and mock-formalized Trinity (`scientist/validation/policy_verified/service.py:78-183`, `scientist/validation/policy_verified/service.py:457-558`, `scientist/agent/formalizer.py:1357-1414`).
- Real LLM-backed generator organs exist outside that scripted default: `LLMDrafterAgent.draft_policy(...)` calls the gateway and parses JSON draft output, `LLMFormalizerAgent.formalize(...)` calls the gateway and parses Trinity JSON, and `LLMCriticAgent.critique(...)` calls the gateway for critique; Pass 3 fake-client probe produced varied drafter options and a model-sourced critic recommendation (`scientist/agent/drafter_clients.py:328-408`, `scientist/agent/formalizer.py:1519-1644`, `scientist/agent/critic.py:417-510`).
- S2 shadow path builds one fixed `credit_guarantee` candidate (`pdc/_impl/layer2_design_search.py:1441-1534`).
- G6 can emit a `candidate_unverified` grammar expansion/handoff for pinned G5 routing, not a promoted policy candidate (`runtime/quality/proving_ground/bounded_request_agent.py:351-360`, `runtime/quality/proving_ground/bounded_request_agent.py:1467-1513`).
- Break C: the raw generator organs are real, but no scanned owner wires them into canonical NL -> DesignProblem -> diverse candidates -> A-grounded candidate packets. The currently selected/plain-policy path remains scripted/fixed; the real LLM organs are `implemented_but_not_orchestrated` for GY.

4. Grounding / A-side evidence.

- Workspace fixture path grounds measurement artifacts through fixed BIND/ESTIMATE/VERIFY and forbids design candidates/admissible promotion (`runtime/quality/workspace/loop.py:1471-1664`, `runtime/quality/workspace/loop.py:1798-1815`).
- S2 constructs a shadow boundary and explicitly marks records not usable for recommendation/production/publication (`pdc/_impl/layer2_design_search.py:1970-2188`).
- Pass 3 found real A-grounding execution owners outside the workspace loop: Fabric retrieval can execute fetch plans (`fabric/retrieval/service.py:230-444`, `fabric/retrieval/executor.py:76-176`), Scholar deep search can query providers/fetch/compress/support claims (`scholar/search/service.py:214-382`), OpenAlex/Data Forge can execute academic provider/ingest paths (`scholar/search/providers.py:159-276`, `data_forge/domains/academic/openalex/client.py:32-110`, `data_forge/domains/academic/batch/harvester.py:50-126`), SKG can query priors/claims (`data_forge/domains/academic/knowledge/skg_query.py:105-183`), and the L2 candidate firewall requires resolver-backed span grounding plus entailment (`runtime/quality/candidate_firewall.py:228-365`, `scientist/validation/citation_faithfulness.py:297-365`; grounding probe).
- G4 promotion requires grounded G1/G2/G3/GL contract families, not search-ledger-only or readiness-summary stand-ins (`runtime/quality/proving_ground/governed_promotion_gate.py:1500-1703`, `runtime/quality/proving_ground/governed_promotion_gate.py:1768-1791`).
- Break D: A-side grounding exists and can execute, but there is no orchestrated bridge from an NL-generated candidate into "ground this candidate's claims" via Scholar/SKG/candidate-firewall, then into the workspace proof packet and G4 grounded contracts. Acquisition is plan-only in the workspace but executable in adjacent Fabric/Scholar/Data Forge owners.

5. Value / outcome computation.

- Reachable current workspace value hook is Phase-2 `run_intent(...) -> run_causal_evaluation -> FoundryMethodOutputConsumer`, with descriptive authority only (`runtime/quality/workspace/loop.py:1338-1429`).
- `run_causal_evaluation.py` really executes Foundry methods through `run_job(...)` after loading typed observational data (`scientist/nodes/builtins/causal/run_causal_evaluation.py:392-415`) and persists method result/evidence/validity/uncertainty/claims artifacts (`scientist/nodes/builtins/causal/run_causal_evaluation.py:464-852`).
- Under Python 3.14, value is not globally blocked: synthetic control, DID, parallel trends, quadratic-program SciPy fallback, and pymoo multiobjective probes computed real results; DoWhy and EconML methods fail with explicit unavailable-backend status. `outcome_prediction.py` is a calibration/authority gate over forecast support, not the forecast producer (`runtime/quality/design_axes/outcome_prediction.py:430-545`).
- Pass 3 bounded candidate value probe pushed a candidate-shaped `PolicyCandidateSchema` plus a real synthetic-control effect report into `ProductionPolicyEvaluationBackend.evaluate(...)`; it computed `policy_value=3.0`, welfare/employment metrics, uncertainty envelope, feasible constraints, and `promotable_source=False` / `research_only` when governance evidence was absent (`scientist/nodes/builtins/decide/policy_runtime_support.py:165-360`, `scientist/nodes/builtins/decide/policy_runtime_support.py:461-530`; Stage-B probe).
- Break E: the real value methods and policy-runtime evaluator can compute candidate value under Python 3.14, but current workspace method selection is explicit/default `causal.inference.synthetic_control@1.0.0`, not DesignProblem-aware, and value output is not fed into a revise loop or G4 promotion (`runtime/quality/workspace/loop.py:1036-1064`).

6. Revise.

- S2's `RefinementDecision`/`SearchLedger` discipline records blocker-to-next-step semantics and no-retry-without-new-grammar, but `run_s2_shadow_design_loop(...)` constructs only one iteration and no second generated candidate (`pdc/_impl/layer2_design_search.py:733-880`, `pdc/_impl/layer2_design_search.py:933-1103`).
- Workspace `REFINE` is registered but non-executable in the active Slice-0 loop; active trajectory is only BIND/ESTIMATE/VERIFY (`runtime/quality/workspace/loop.py:110-113`, `runtime/quality/workspace/loop.py:714-834`).
- Scientist hierarchical search has a real iteration engine, but the default mock-formalized candidate probe fails before Stage B due missing Lex bounds (`scientist/policy_design/search.py:925-1040`, `scientist/policy_design/search.py:1228-1308`; Pass 1 probe).
- Break F: revision discipline exists, but no owner currently closes the loop from value/counterexample back to a newly generated candidate and re-grounded packet.

7. Promote.

- Ring-2 waist validators enforce verifier provenance and block LLM/self-upgrade authority (`pdc/_impl/gy_waist.py:91-129`, `pdc/_impl/gy_waist.py:451-497`).
- G4 governed gate can emit `governed_promoted` for complete explicit inputs and blocks missing calibration or shadow self-promotion (`runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`, `runtime/quality/proving_ground/governed_promotion_gate.py:4293-4804`; G4 probe).
- Scientist `RunPolicyPromotionNode.execute(...)` is disabled/fail-closed in policy mode, while support-level `run_promotion_with_evidence(...)` and `PolicyPromotionCoordinator` are real evidence-gated champion-promotion machinery (`scientist/nodes/builtins/decide/run_policy_promotion.py:120-141`, `scientist/nodes/builtins/decide/policy_runtime_support.py:935-1170`, `scientist/methods/search/judge_stack.py:1397-1679`).
- S6/S7/S8 add real governance gates before authority: S6 emits fail-closed axis firewall reports plus bridge/constraint updates, S7 routes/records human decisions with five-rights checks, and S8 blocks LLM/corpus/ad-hoc value authority while allowing authorized value schedules (`runtime/quality/design_axes/blind_spot_firewalls.py:987-1090`, `runtime/quality/design_axes/mandate_bounded_delegation.py:478-631`, `runtime/quality/design_axes/value_choice_provenance.py:310-370`; governance probe).
- Break G: promotion enforcement exists, but no scanned cycle calls it after candidate generation/value/revision. G4 PDC promotion, Scientist champion promotion, blueprint runtime promotion support, and S6/S7/S8/scorecard gates are parallel enforcement surfaces until a GY controller sequences them.

8. Deploy -> observe -> update the world model (north-star next horizon).

- `DecisionFeedbackService` records confirm/refute/review decisions, compares realized metrics against precomputed ranges, emits invalidation/reissue actions, and persists audit state; DDM computes data-quality, drift/performance, readiness, and rollback incidents; multiple-testing controllers compute bounded alpha decisions (`policy-engine/src/polisyos/scientist/feedback/core.py:204-355`, `policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:49-258`, `policy-engine/src/polisyos/ddm/integration/monitor.py:55-116`, `policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:38-93`).
- Break H: the confirmatory path is range/comparator based rather than a Bayesian causal posterior update, the exploratory detectors are not orchestrated into a low-authority anomaly-to-hypothesis path, and neither contour writes newly supported edges/required-data specs back into the world model. This is **PARTIAL next-horizon machinery**, not part of the current GY-N1..N7 closure.

Pass 4 exact bridge summary:

```text
NL
  -> PolicyIntentEnvelope                 [real; canonical DesignProblem missing]
  -> generator projection                [real organs; selector/default fork]
  -> intervention atom                   [split policy action vs causal do()]
  -> candidate claim grounding under A   [real organs; orchestration bridge missing]
  -> data-bound world + joint simulation [real partial organs; production builder missing]
  -> value + calibration/authority gate  [real on Python 3.14; not fed back]
  -> counterexample/refinement            [real discipline; executable retry missing]
  -> acquisition when blocked            [real execution; typed handoff/re-entry missing]
  -> governed B->A promotion              [real enforcement; sequence missing]
  -> deploy/observe/world update          [partial; unified two-contour controller missing]
```

Pass 5 refined bridge summary:

```text
NL
  -> canonical DesignProblem              [BUILD/bridge over existing projections]
  -> LLM candidate organs                 [real; live gateway works; profile preflight required]
  -> InterventionAtomBinding              [BUILD bridge: Trinity action slots + proof-kernel do()]
  -> A-grounded candidate packet          [real grounding organs; orchestrator missing]
  -> WorldModelRecord                     [BUILD bridge: Fabric world + Data Forge binding + ModelSpec + Foundry state + SKG]
  -> JointSimulationHorizonController     [BUILD controller over real Foundry engines; proof receipt stub to replace]
  -> value/calibration/transport gate     [real under Python 3.14; needs world/candidate adapter]
  -> VOI/refinement decision              [real scheduler + S2 discipline; executable retry missing]
  -> closed acquisition when blocked      [providers live; receipt/re-entry missing]
  -> governed B->A promotion              [real enforcement; one persisted sequence missing]
  -> deploy/observe/world update          [DDM/feedback + Bayesian primitives; deployed updater/controller missing]
```

### C. Reuse / Rework / Delete Candidates

Accumulating candidates after Pass 4:

USE_AS_IS:

- owner_id: `nl_pipeline_authority_publication`; owner_path: `src/polisyos/runtime/http/services/control/nl_pipeline.py:2914` - Runtime authority artifact publication helper path in `nl_pipeline.py` (`runtime/http/services/control/nl_pipeline.py:2914-3035`): real CAS/authority envelope/diagnostic publication surface.
- owner_id: `policy_intent_envelope`; owner_path: `src/polisyos/runtime/quality/assurance_case.py:311` - `PolicyIntentEnvelope` validation in `runtime/quality/assurance_case.py:311-425`: real front-door intent capture/normalization.
- owner_id: `experiment_state_artifact_ref_contracts`; owner_path: `src/polisyos/scientist/orchestration/engine/state.py:23` - `ExperimentState` and `ArtifactRef` strict boundary contracts (`scientist/orchestration/engine/state.py:23-55`, `core/artifacts/manifest.py:199-205`): useful typed bridge discipline.
- owner_id: `workflow_selector_builder_dispatch`; owner_path: `src/polisyos/scientist/api.py:212` - Workflow selector/builder dispatch (`scientist/api.py:212-328`, `workflows/selection.py:32-61`, `workflows/builder.py:510-724`): real routing/execution owner; GY should set it deliberately.
- owner_id: `hierarchical_search_bounds_frontier`; owner_path: `src/polisyos/scientist/policy_design/search.py:1228` - Hierarchical search bounds gate and frontier provenance (`scientist/policy_design/search.py:1228-1308`): correct fail-closed shape for P25/P32.
- owner_id: `optional_causal_method_dependency_gates`; owner_path: `src/polisyos/foundry/methods/catalog/causal/_registry_boot.py:413` - Dependency gating for optional causal methods (`foundry/methods/catalog/causal/_registry_boot.py:413-457`) and explicit CI backend metadata (`ci_backends.py:59-91`, `constraint_discovery.py:2460-2475`): reuse to surface method availability truthfully.
- owner_id: `workspace_honest_backbone_semantics`; owner_path: `src/polisyos/runtime/quality/workspace/loop.py:110` - Workspace terminal selection, active-operation registry, no-design artifact cut line, descriptive authority boundary, and acquisition-required terminal (`runtime/quality/workspace/loop.py:110-113`, `runtime/quality/workspace/loop.py:242-255`, `runtime/quality/workspace/loop.py:407-459`, `runtime/quality/workspace/loop.py:1798-1815`, `runtime/quality/workspace/loop.py:2131-2165`): correct honest backbone semantics.
- owner_id: `acquisition_planner_evidence_gap_surface`; owner_path: `src/polisyos/runtime/quality/acquisition_planner.py:528` - Acquisition planner as plan-only evidence-gap surfacer (`runtime/quality/acquisition_planner.py:1-7`, `runtime/quality/acquisition_planner.py:528-755`): reuse for `ACQUISITION_REQUIRED`, not as data execution.
- owner_id: `foundry_causal_evaluation_bridge`; owner_path: `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:392` - `run_causal_evaluation.py` Foundry method bridge and `FoundryMethodOutputConsumer` path (`scientist/nodes/builtins/causal/run_causal_evaluation.py:392-415`, `scientist/nodes/builtins/causal/run_causal_evaluation.py:464-852`, `runtime/quality/workspace/loop.py:1412-1429`): real reachable value/evidence computation under available methods.
- owner_id: `available_value_methods_subset`; owner_path: `src/polisyos/foundry/methods/catalog/causal/synthetic_control.py:40` - Available value methods: synthetic control SciPy optimizer, standard DID NumPy/statsmodels-style diagnostics, quadratic-program SciPy fallback, and pymoo multiobjective (`foundry/methods/catalog/causal/synthetic_control.py:40-96`, `foundry/methods/catalog/causal/synthetic_control.py:344-470`, `foundry/methods/catalog/causal/did.py:116-254`, `foundry/methods/catalog/causal/diagnostics.py:47-128`, `foundry/methods/catalog/optimization/convex.py:343-520`, `foundry/methods/catalog/optimization/multiobjective.py:110-221`).
- owner_id: `outcome_prediction_authority_gate`; owner_path: `src/polisyos/runtime/quality/design_axes/outcome_prediction.py:97` - `outcome_prediction.py` as the S10 calibration/authority gate, not a forecast producer (`runtime/quality/design_axes/outcome_prediction.py:97-224`, `runtime/quality/design_axes/outcome_prediction.py:430-545`).
- owner_id: `ring2_waist_g4_promotion_enforcement`; owner_path: `src/polisyos/pdc/_impl/gy_waist.py:91` - Ring-2 waist authority validators and G4 governed promotion reducer/validator (`pdc/_impl/gy_waist.py:91-129`, `pdc/_impl/gy_waist.py:451-497`, `runtime/quality/proving_ground/governed_promotion_gate.py:1999-2111`, `runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`, `runtime/quality/proving_ground/governed_promotion_gate.py:4293-4804`).
- owner_id: `agent_event_bridge_candidate_audit`; owner_path: `src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py:51` - `AgentEventBridge` record shape and no-client blocker as candidate-only Ring-1 audit plumbing (`runtime/quality/workspace/agent_proposal_bridge.py:51-208`), if a later proposer is explicitly admitted under verifier control.
- owner_id: `llm_generator_organs`; owner_path: `src/polisyos/scientist/agent/drafter_clients.py:328` - Real LLM generator organs (`LLMDrafterAgent`, `LLMFormalizerAgent`, `LLMCriticAgent`, `MultiPassLLMDrafter`): use as gateway-backed candidate/critique producers under a canonical DesignProblem, with their mock fallback outputs treated as fixture/shadow only (`scientist/agent/drafter_clients.py:328-408`, `scientist/agent/formalizer.py:1519-1644`, `scientist/agent/critic.py:417-510`, `scientist/agent/_drafter_orchestrator.py:64-226`).
- owner_id: `acquisition_grounding_producers`; owner_path: `src/polisyos/fabric/retrieval/service.py:230` - Fabric retrieval executor, Scholar deep search, OpenAlex provider/client, Data Forge academic batch harvester, SKG query/search, and candidate-firewall span-grounding checks as acquisition/grounding producers (`fabric/retrieval/service.py:230-444`, `fabric/retrieval/executor.py:76-176`, `scholar/search/service.py:214-382`, `scholar/search/providers.py:159-276`, `data_forge/domains/academic/openalex/client.py:32-110`, `data_forge/domains/academic/batch/harvester.py:50-126`, `data_forge/domains/academic/knowledge/skg_query.py:105-183`, `runtime/quality/candidate_firewall.py:228-365`).
- owner_id: `s6_s7_s8_scorecard_gates`; owner_path: `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py:987` - S6/S7/S8 governance axes and scorecard as authority and closeout gates: S6 blind-spot firewall/constraint producer, S7 responsibility-integrity/human-decision routing, S8 value-choice provenance gate, and quality scorecard aggregation (`runtime/quality/design_axes/blind_spot_firewalls.py:987-1090`, `runtime/quality/design_axes/mandate_bounded_delegation.py:478-631`, `runtime/quality/design_axes/value_choice_provenance.py:310-370`, `runtime/quality/scorecard.py:9955-10404`).
- owner_id: `foundry_method_registry`; owner_path: `src/polisyos/foundry/methods/selection/registry.py:491` - Foundry method registry for explicit/available method lookup and truthful availability surfacing (`foundry/methods/selection/registry.py:491-626`, `foundry/methods/selection/registry.py:680-729`, `foundry/methods/catalog/__init__.py:117-126`).
- owner_id: `fabric_world_substrate`; owner_path: `src/polisyos/fabric/world/store/segments.py:320` - `fabric/world` append-only fact/event store, DuckDB materialization, bitemporal/snapshot/branch query, governance/audit, and Kuzu rebuild graph traversal (`fabric/world/store/segments.py:320-410`, `fabric/world/materialize/duckdb.py:219-491`, `fabric/world/query.py:157-266`, `fabric/world/store/snapshots.py:298-379`, `fabric/world/materialize/kuzu.py:542-568`).
- owner_id: `world_lifecycle_piece_contracts`; owner_path: `src/polisyos/ir/model_layer/model_spec.py:179` - IR `ModelSpec`, Data Forge snapshot binding, runtime Data Forge binding validator, and Foundry input bindings as lifecycle pieces (`ir/model_layer/model_spec.py:179-260`, `data_forge/kernel/snapshot/finalize.py:135-301`, `runtime/quality/data_forge_binding.py:781-930`, `foundry/data_plane/bindings.py:69-236`).
- owner_id: `scientist_voi_scheduler`; owner_path: `src/polisyos/scientist/methods/search/voi_scheduler.py:169` - Scientist VOI scheduler and learned VOI/routing policies for search/evaluation budgets (`scientist/methods/search/voi_scheduler.py:169-212`, `scientist/methods/search/voi_scheduler.py:448-792`, `scientist/methods/search/strategies/advanced_policy.py:425-560`).
- owner_id: `bayesian_transport_primitives`; owner_path: `src/polisyos/foundry/methods/catalog/bayesian/variational.py:383` - Foundry Bayesian posterior/calibration primitives and transportability/external-validity stack under Python 3.14 (`foundry/methods/catalog/bayesian/variational.py:383-493`, `foundry/methods/catalog/bayesian/protocols.py:1533-1647`, `foundry/calibration/uncertainty_adapter.py:147-228`, `ir/analytics/transportability.py:364-585`, `foundry/methods/catalog/causal/transport_engine.py:39-161`, `foundry/methods/catalog/causal/density_ratio.py:724-889`).
- owner_id: `foundry_shared_state_joint_execution`; owner_path: `src/polisyos/foundry/compile/_lowering.py:156` - Foundry program graph, mechanism lowering/linking, `GlobalState` binding, and NCM intervention execution: real shared-state and joint causal-execution substrate (`foundry/compile/_lowering.py:156-287`, `foundry/compile/_graph.py:20-122`, `foundry/data_plane/bindings.py:69-236`, `foundry/methods/catalog/causal/ncm_engine.py:691-890`).
- owner_id: `trinity_and_causal_intervention_halves`; owner_path: `src/polisyos/ir/analytics/interventions.py:134` - IR causal intervention algebra and Trinity `InterventionSpec` as the two existing halves of the north-star atom (`ir/analytics/interventions.py:134-184`, `ir/governance/policy_spec.py:73-108`). Reuse both; authority must come from their new binding, not either half alone.
- owner_id: `w7_data_requirement_ingestion_chain`; owner_path: `src/polisyos/data_requirement/compiler.py:83` - W7 `DataRequirementSpec` compiler/Fabric matcher plus canonical Fabric ingestion/orchestration to `EvidenceBundle` and `DataSnapshot` (`data_requirement/_impl/models.py:50-162`, `data_requirement/compiler.py:83-309`, `fabric/catalog/data_requirement_adapter.py:15-187`, `fabric/ingestion/ingestion.py:804-1072`, `fabric/data_plane/orchestrator.py:511-639`).
- owner_id: `authority_independence_composition_enforcement`; owner_path: `src/polisyos/pdc/_impl/layer2_readiness.py:62` - Authority boundary/derivation, P14 independence map/effective graph, scorecard validation, and content-bound composition enforcement (`pdc/_impl/layer2_readiness.py:62-114`, `pdc/_impl/gy_waist.py:451-497`, `runtime/quality/evidence_independence.py:136-248`, `evidence/portfolio/effective_independence_graph.py:87-198`, `runtime/quality/design_axes/coupling_composition.py:2282-2360`).
- owner_id: `post_deploy_monitoring_organs`; owner_path: `src/polisyos/ddm/detectors/realized_performance_monitor.py:49` - DDM detector computations, `DecisionFeedbackService` persistence/reissue lifecycle, and S13 attribution/firewall enforcement as post-deploy organs (`ddm/detectors/realized_performance_monitor.py:49-258`, `scientist/feedback/core.py:204-533`, `runtime/quality/design_axes/post_deploy_accountability.py:316-390`).
- owner_id: `value_outer_set_foundation_contract`; owner_path: `src/polisyos/core/contracts/runtime.py:905` - `ValueOuterSet` is the GY-N-V foundation carrier for set-valued value and the typed home for S1 proxy household bounds; it extends the existing core runtime value-contract layer rather than living in PDC or Foundry.
REWORK_TO_FIT:

- owner_id: `nl_pipeline_generation_cycle_front_door`; owner_path: `src/polisyos/runtime/http/services/control/nl_pipeline.py:1131` - `nl_pipeline.py` as generation-cycle front door: preserve durable publication and handoff, but extract/bridge a canonical generation request instead of relying on sidecar intent plus agent circuit.
- owner_id: `mock_pi_data_need_path`; owner_path: `src/polisyos/scientist/agent/pi.py:82` - Mock PI/data-need path (`scientist/agent/pi.py:82-133`, `data_need_extractor.py:34-92`): usable for fixtures only; not authority or real design parsing.
- owner_id: `verified_policy_candidate_source`; owner_path: `src/polisyos/scientist/validation/policy_verified/service.py:457` - Verified-policy candidate source (`validation/policy_verified/service.py:457-558`, `agent/formalizer.py:1357-1414`): keep legal/request skeleton, replace scripted option/formalization if GY needs real candidate generation.
- owner_id: `trinity_candidate_search_bridge`; owner_path: `src/polisyos/scientist/policy_design/schema.py:293` - `PolicyCandidateSchema.from_trinity_bundle(...)` and `HierarchicalPolicySearchAdapter.build_candidate(...)`: useful bridge from Trinity/Lex into search, but must receive real candidate/bounds and not hardcoded tax-subsidy defaults.
- owner_id: `foundry_value_path_method_assumptions`; owner_path: `src/polisyos/foundry/methods/catalog/causal/_registry_boot.py:441` - Foundry value path assumptions: statsmodels/JAX/pymoo/SciPy are available, but EconML/DoWhy/CVXPY are not; any GY value path must select reachable methods or emit blockers.
- owner_id: `workspace_run_intent_cycle_adapter`; owner_path: `src/polisyos/runtime/quality/workspace/loop.py:1266` - Workspace `run_intent(...)`: reuse adapter/consumer surfaces, but it must become an orchestrated cycle if GY-N3 means generation/revision; current body is descriptive and executes only fixed aliases (`runtime/quality/workspace/loop.py:1266-1469`).
- owner_id: `s2_refinement_discipline`; owner_path: `src/polisyos/pdc/_impl/layer2_design_search.py:632` - S2 refinement discipline (`SearchIteration`, `RefinementDecision`, `CounterexampleRecord`, constraint store, no-retry flag): keep the discipline, replace hardcoded grammar/candidate and single-iteration body (`pdc/_impl/layer2_design_search.py:632-880`, `pdc/_impl/layer2_design_search.py:933-1103`, `pdc/_impl/layer2_design_search.py:1441-1534`).
- owner_id: `stage_b_foundry_nodes`; owner_path: `src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py:97` - Stage-B compile/readiness/simulation nodes: real bridge/gate owners but not reached by the current workspace loop and still need an actual `ctx.foundry`/valid candidate integration trace (`scientist/nodes/builtins/compile/compile_foundry.py:97-178`, `scientist/nodes/builtins/causal/run_causal_readiness.py:150-341`, `scientist/nodes/builtins/simulate/run_simulation.py:194-529`).
- owner_id: `policy_runtime_support_backend`; owner_path: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:165` - `policy_runtime_support.py` production backend and promotion support: keep evidence-driven metrics/promotion semantics, but do not let synthetic research-only backend stand in for authority (`scientist/nodes/builtins/decide/policy_runtime_support.py:165-360`, `scientist/nodes/builtins/decide/policy_runtime_support.py:461-530`, `scientist/nodes/builtins/decide/policy_runtime_support.py:935-1332`).
- owner_id: `g4_in_cycle_promotion_sequence`; owner_path: `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py:1500` - G4 governed promotion as in-cycle GY-N6: enforcement is real, but a cycle controller must provide complete G1/G2/G3/GL grounded inputs; current caller scan shows validator/tool/test usage, not workspace/Scientist orchestration.
- owner_id: `bounded_agent_proposal_bridge`; owner_path: `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1318` - G6 bounded agent and `agent_proposal_bridge.py`: useful candidate-only proposer/audit plumbing, but scoped to bounded G5 routing and Ring-1 hints; not a cycle controller (`runtime/quality/proving_ground/bounded_request_agent.py:1318-1608`, `runtime/quality/workspace/agent_proposal_bridge.py:51-286`).
- owner_id: `scientist_champion_vs_g4_promotion`; owner_path: `src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py:120` - Scientist champion promotion vs G4 PDC promotion: both are evidence-gated, but Pass 3 must decide whether GY-N6 needs one, the other, or a sequence (`scientist/nodes/builtins/decide/run_policy_promotion.py:120-251`, `scientist/methods/search/judge_stack.py:1397-1679`, `runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`).
- owner_id: `design_problem_projection_surfaces`; owner_path: `src/polisyos/ir/governance/problem_frame.py:296` - `PolicyIntentEnvelope` + Scientist `ProblemFrame` + IR governance `ProblemFrame` as canonical DesignProblem projections: no one current type carries the full NL/request authority/time/generation/formal-evaluation payload (`runtime/quality/assurance_case.py:311-425`, `scientist/agent/protocols.py:74-97`, `ir/governance/problem_frame.py:296-370`).
- owner_id: `acquisition_planner_execution_bridge`; owner_path: `src/polisyos/runtime/quality/acquisition_planner.py:528` - Acquisition planner plus execution owners: current workspace stops at `ACQUISITION_REQUIRED`; GY-N4 must bridge planner output into Fabric/Scholar/Data Forge execution and then re-enter grounding/revision (`runtime/quality/acquisition_planner.py:528-755`, `runtime/quality/workspace/loop.py:407-459`, `fabric/retrieval/service.py:230-444`, `scholar/search/service.py:214-382`).
- owner_id: `candidate_grounding_bridge`; owner_path: `src/polisyos/runtime/quality/candidate_firewall.py:228` - Candidate grounding: reuse SKG/candidate-firewall/span-entailment, but build the missing "ground this candidate's claims" orchestrator and artifact bridge (`runtime/quality/candidate_firewall.py:228-365`, `scientist/validation/policy_grounding.py:1477-1688`, `scientist/validation/citation_faithfulness.py:297-365`).
- owner_id: `workspace_method_selection_default`; owner_path: `src/polisyos/runtime/quality/workspace/loop.py:1036` - Method selection: current workspace default `causal.inference.synthetic_control@1.0.0` is honest but not universal; GY-N5 needs a candidate/problem-aware method policy over the registry or an explicit blocker (`runtime/quality/workspace/loop.py:1036-1064`, `foundry/methods/selection/registry.py:805-855`).
- owner_id: `scorecard_lifecycle_placement`; owner_path: `src/polisyos/runtime/quality/scorecard.py:9955` - Scorecard placement: use as downstream gate/closeout, but do not require the full scorecard for every internal revise iteration unless GY-N7 explicitly sets that lifecycle boundary (`runtime/quality/scorecard.py:9955-10404`).
- owner_id: `canonical_world_model_envelope`; owner_path: `src/polisyos/foundry/agent_sim/world/world.py:30` - Canonical world model: wrap existing `GlobalState`/program graph/IR causal graph/NCM/data-snapshot owners in one versioned, regional, data-bound lifecycle envelope. `SyntheticWorld` remains semantic-test input, not production state (`foundry/agent_sim/world/world.py:30-218`, `foundry/data_plane/bindings.py:69-236`).
- owner_id: `world_model_record_lifecycle_bridge`; owner_path: `src/polisyos/data_forge/kernel/snapshot/finalize.py:135` - Canonical world lifecycle: replace the previous generic "world model program" with a concrete `WorldModelRecord` bridge over Fabric world snapshot/branch, Data Forge snapshot binding, IR `ModelSpec`, Foundry input bindings/GlobalState/mechanisms, SKG priors, and deployment-update lineage. This is one-bridge/unify-existing, not a parallel store.
- owner_id: `joint_simulation_horizon_bridge`; owner_path: `src/polisyos/foundry/methods/catalog/simulation/coupled.py:57` - Joint simulation: retain Foundry's shared-state mechanism executor, NCM, coupling certificate, and real coupled DES/ABM horizon, but add a horizon/controller that applies a generated intervention set jointly and reports interactions/general-equilibrium/feedback; replace the ABM proof/calibration stub (`foundry/methods/catalog/simulation/coupled.py:57-145`, `foundry/methods/catalog/simulation/dynamics.py:33-40`).
- owner_id: `intervention_atom_binding_bridge`; owner_path: `src/polisyos/ir/governance/policy_spec.py:73` - Intervention atom bridge: bind one Trinity action/operator and registry-derived target/read-write footprint to typed causal `do()` expressions, direct-effect bundle, intended downstream estimand, and world-model resolution. The current split is `bridge_missing`, not a reason to invent another action model.
- owner_id: `llm_generation_model_preflight`; owner_path: `src/polisyos/scientist/orchestration/llm/gateway_client.py:276` - LLM generation preflight: wire `list_model_ids(...)` or equivalent profile validation before generation so unsupported code-profile models like the current `gpt-5-mini` account mismatch fail before a cycle starts (`scientist/orchestration/llm/gateway_client.py:276-330`).
- owner_id: `transport_value_receipts`; owner_path: `src/polisyos/ir/analytics/transportability.py:364` - Transport/value: attach transportability/density-ratio receipts and Bayesian posterior/calibration receipts to value packets; do not leave them as side diagnostics.
- owner_id: `core_quantity_value_uncertainty_seed`; owner_path: `src/polisyos/core/contracts/runtime.py:905` - Existing `QuantityValue`/`QuantityUncertainty` value-contract seed stays in the shared core layer, but set-valued GY value must be reworked through `ValueOuterSet` so Foundry and PDC consume one foundation carrier.
- owner_id: `required_data_spec_lossless_adapter`; owner_path: `src/polisyos/foundry/methods/catalog/causal/_id_contracts.py:24` - `RequiredDataSpec` adapter: replace first-item-only and `unknown_missing_distribution` fallback behavior with a lossless one-to-many `DistributionRef -> DataRequirementSpec` bridge and actual provider-sensitive VOI (`foundry/methods/catalog/causal/_id_contracts.py:24-75`, `runtime/quality/acquisition_planner.py:528-643`).
- owner_id: `acquisition_control_reentry`; owner_path: `src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:269` - Acquisition control: add a durable acquisition job/receipt and same-workspace re-entry over Fabric/Scholar/Data Forge; keep S3's consume-the-index-delta closure rule but replace its fixture discovery/VOI (`runtime/quality/design_axes/substrate_acquisition.py:269-372`, `runtime/quality/design_axes/substrate_acquisition.py:459-619`).
- owner_id: `two_contour_monitoring_bridge`; owner_path: `src/polisyos/scientist/feedback/core.py:204` - Two-contour monitoring: connect DDM/FDR low-authority anomalies to candidate hypotheses and connect predeclared estimands/uncertainty to causal/Bayesian confirmatory updates; preserve `DecisionFeedbackService` invalidation/reissue and S13 attribution gates.

DELETE / COMPATIBILITY-ONLY candidates:

- owner_id: `engine_langgraph_legacy_shadow`; owner_path: `src/polisyos/scientist/orchestration/workflows/engine_langgraph.py:73` - `workflows/engine_langgraph.py`: provisional `SHADOW/LEGACY`; `from_existing_workflow()` and factory without a supplied build function raise (`engine_langgraph.py:73-93`). Need caller search before final DELETE recommendation.
- owner_id: `s2_fixed_credit_guarantee_body`; owner_path: `src/polisyos/pdc/_impl/layer2_design_search.py:1441` - S2 fixed credit-guarantee candidate/projection body should be strangled once a real generator feeds the reusable refinement discipline (`pdc/_impl/layer2_design_search.py:1441-1534`, `pdc/_impl/layer2_design_search.py:1970-2188`).
- owner_id: `verified_policy_fixed_option_defaults`; owner_path: `src/polisyos/scientist/validation/policy_verified/service.py:457` - Verified-policy fixed option/formalization defaults are fixture/scaffold material, not the GY generator (`scientist/validation/policy_verified/service.py:457-558`, `scientist/agent/formalizer.py:1357-1414`).
- owner_id: `direct_policy_promotion_node_policy_mode`; owner_path: `src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py:120` - Direct `RunPolicyPromotionNode.execute(...)` in policy mode is disabled/fail-closed; keep only if Pass 3 finds a non-policy caller that still needs it (`scientist/nodes/builtins/decide/run_policy_promotion.py:120-141`).
- owner_id: `synthetic_policy_runtime_backend`; owner_path: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:244` - Synthetic policy-runtime backend is compatibility/research-only for authority purposes; production value/promotability must come from evidence-driven inputs (`scientist/nodes/builtins/decide/policy_runtime_support.py:244-310`).
- owner_id: `mock_generator_outputs`; owner_path: `src/polisyos/scientist/agent/drafter_clients.py:86` - Mock generator outputs (`MockDrafterAgent` fixed economic options, `MockFormalizerAgent` tax-subsidy fallback, `MockCriticAgent` structural checks) should be fixture-only, never GY generation authority (`scientist/agent/drafter_clients.py:86-161`, `scientist/agent/formalizer.py:1426-1517`, `scientist/agent/critic.py:147-407`).
- owner_id: `s2_fixed_candidate_as_generator`; owner_path: `src/polisyos/pdc/_impl/layer2_design_search.py:1470` - Any direct use of S2's fixed credit-guarantee candidate as a "generator" should be deleted/strangled after the real GY controller feeds S2-compatible refinement discipline.
- owner_id: `unknown_missing_distribution_adapter`; owner_path: `src/polisyos/runtime/quality/acquisition_planner.py:528` - `unknown_missing_distribution` fabrication and first-gap-only acquisition adaptation must be deleted once the lossless RequiredData bridge exists; the current positive VOI on a fabricated unknown is not acceptable authority.
- owner_id: `gy_g_s3_fixture_only_demonstrations`; owner_path: `src/polisyos/runtime/quality/workspace/loop.py:865` - GY-G's hardcoded depth-2 independent fixture recursion and S3's fixture-only source/VOI bodies should become compatibility tests after a real controller and acquisition receipt path exist, not remain production demonstrations.
- owner_id: `household_cell_ad_hoc_bounds_representation`; owner_path: `src/polisyos/foundry/contracts/state.py:317` - GY-S1's interim `HouseholdCellState` lower/upper/identification scalar representation is deleted and replaced by `core.contracts.runtime.ValueOuterSet`; no production reader should consume bare household bound scalars.

REWORK_TO_FIT:

- owner_id: `production_data_substrate_registry`; owner_path: `src/polisyos/runtime/quality/substrate_registry.py:158` - Production-data metadata substrate registry over existing L5 measurement/identification/schema-regime catalogs and L1 DCAT metadata; runtime consumers should resolve one content-addressed substrate version instead of fragmented catalog refs, while L5/L1 remain the coverage/trust authority.
- owner_id: `l6_intervention_substrate_lift`; owner_path: `src/polisyos/runtime/quality/intervention_substrate.py:292` - L6 agent-sim intervention substrate bridge over the real knob dictionary, Lex law-to-lever map, Foundry method registry routes, and S0 L6 artifact registration; it reuses InterventionAtomBinding/WorldModelRecord slot authority, LegalKnowledgeStore admissibility, and the Foundry registry instead of creating a parallel lever/method/legal hierarchy.

USE_AS_IS:

- owner_id: `scholar_kg_credal_lift_owner`; owner_path: `src/polisyos/data_forge/domains/academic/knowledge/skg_query.py:1745` - `SKGQuery` owns the L2 Scholar KG runtime lift: parameter estimates lower into the GY-N-V `ValueOuterSet`, SKG transport widens bounded value sets, contested edges lower to structural ambiguity, and candidate grounding resolves through the existing SKG version store.
- owner_id: `lex_kg_admissibility_lift_owner`; owner_path: `src/polisyos/lex/knowledge/store.py:890` - `LegalKnowledgeStore` owns the L3 Lex KG runtime lift: rule thresholds evaluate with operator/unit/scope semantics, missing bounds fail closed, amendment `effective_from` gates temporal competence, and threshold rows bind to normative facts/provisions.

REWORK_TO_FIT:

- owner_id: `generation_cycle_controller_scaffold`; owner_path: `src/polisyos/runtime/quality/generation_cycle.py:1` - Existing GY-N6 controller scaffold: rework in place as the canonical thin controller over N4 CGF dispositions, N5 horizon observations, S2 refinement discipline, and Scientist VOI scheduling; do not create a parallel controller.

## GY-N1..N7 -> Owners Mapping

This is the Pass 5 final owner/disposition synthesis for rewriting the GY-N1..N7 tasks. Pass 5 adds the hidden-sweep corrections: `fabric/world` + `ModelSpec` + Data Forge snapshot binding + Foundry input bindings make world-model work `UNIFY_EXISTING`; Scientist VOI scheduling is reusable for cycle control; Foundry Bayesian/transport primitives are real under Python 3.14; the coupled simulation engine is real while its ABM proof receipt is stubbed; the live gateway works with the currently supported Qwen model but not the hardcoded `gpt-5-mini` profile.

### GY-N1: NL -> Canonical DesignProblem

- Owners: `runtime/quality/assurance_case.py` `PolicyIntentEnvelope` for request/authority/provenance/time; Scientist `ProblemFrame` for generator-facing problem; IR governance `ProblemFrame` for formal Trinity problem; verified `PolicyRequestFrame` for legal/request subflow (`runtime/quality/assurance_case.py:311-425`, `scientist/agent/protocols.py:74-97`, `ir/governance/problem_frame.py:296-370`, `scientist/validation/policy_verified/models.py:25-40`).
- Disposition: `REWORK_TO_FIT`, with a small canonical bridge/envelope. `BUILD-NEW` only for the missing bridge contract if existing projections cannot be safely unified.
- Exact gap: no current type spans NL provenance, authority profile, jurisdiction/time semantics, objectives/constraints/stakeholders, evidence/acquisition needs, generator projection, and IR formal problem. Current front door emits `PolicyIntentEnvelope`; workspace accepts raw dict; verified-policy uses a narrower scripted `PolicyRequestFrame`.
- Pass 5 refinement: no hidden canonical `DesignProblem` was found in the subsystem sweep. IR `ModelSpec` strengthens the eventual world side of the problem envelope, but it is not a request/problem record (`policy-engine/src/polisyos/ir/model_layer/model_spec.py:179-260`).
- Strangle obligation: plain policy NL must stop silently forking into `scientist_policy_verified` as the universal generation path; `run_intent` must stop accepting untyped dicts for GY cycle entry.

### GY-N2: Generation Under A

- Owners: real LLM drafter/formalizer/critic/multipass drafter; Trinity `InterventionSpec`/`LinkedIntervention` and mechanism registry; proof-kernel intervention expressions; `PolicyCandidateSchema.from_trinity_bundle(...)`; Lex hierarchical-search adapter; candidate firewall/SKG/Scholar grounding owners (`scientist/agent/drafter_clients.py:328-408`, `scientist/agent/formalizer.py:1519-1644`, `scientist/agent/critic.py:417-510`, `ir/governance/policy_spec.py:73-108`, `ir/linker/_trinity_linker.py:89-178`, `ir/analytics/interventions.py:134-184`, `scientist/policy_design/schema.py:293-339`, `runtime/quality/candidate_firewall.py:228-365`).
- Disposition: `REWORK_TO_FIT`.
- Exact gap: real LLM organs can generate/critique, but current selected candidate sources are scripted/default/mock or shadow. The north-star atom is split: Trinity owns executable action/target/schedule/parameters and registry-derived state slots, while proof analytics owns typed `do()` expressions/outcomes. No content-bound artifact joins direct effects, causal path, intended downstream effect, and world-model version.
- Pass 5 refinement: the real credentialed gateway path works through the drafter and critic with the live-supported Qwen model; the hardcoded `gpt-5-mini` profile is not currently supported by the gateway catalog. GY-N2 needs model-catalog preflight as part of generation admission (`policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py:276-330`; live probe output in "Live Operational Probes").
- Strangle obligation: mock drafter/formalizer/critic and verified fixed tax-subsidy path are fixture/scaffold only; generated LLM output remains candidate-only until A-grounded. Strangle free-form `measurement_expectations` as the only action-to-outcome link once the atom binding exists.

### GY-N3: The Real Generation Cycle

- Owners: workspace loop as honest operation/ledger/terminal backbone; S2 refinement discipline; Scientist hierarchical search; Scientist VOI scheduler/learned search policies; Foundry shared-state program executor/NCM/coupled simulation; coupling composition gate; S6 constraint updates; bounded agent bridge only as candidate-only proposal/audit (`runtime/quality/workspace/loop.py:110-113`, `pdc/_impl/layer2_design_search.py:632-880`, `scientist/policy_design/search.py:925-1040`, `scientist/methods/search/voi_scheduler.py:169-212`, `scientist/methods/search/strategies/advanced_policy.py:425-560`, `foundry/execute/_internal/graph/__init__.py:114-260`, `foundry/methods/catalog/causal/ncm_engine.py:691-890`, `foundry/methods/catalog/simulation/coupled.py:57-145`, `runtime/quality/design_axes/coupling_composition.py:1255-1533`).
- Disposition: `REWORK_TO_FIT` plus likely `BUILD-NEW` thin controller because no owner currently executes generate -> ground -> value -> revise -> repeat.
- Exact gap: workspace is single-pass/descriptive, S2 is hardcoded one-iteration shadow, and Scientist search cannot repair back through a real generator/grounding loop. Joint execution exists, VOI scheduling exists, and the coupled DES/ABM engine is real, but no controller maps generated atom bindings into one `WorldModelRecord`, selects the required joint engine, runs a horizon, replaces the stubbed simulation proof receipt, and feeds interactions/counterexamples back.
- Strangle obligation: keep workspace terminal/authority honesty and S2 no-retry discipline, but replace the hardcoded candidate and add executable revision state that can re-enter generation only when grammar/evidence/value changed. Replace GY-G's declared-independent depth-2 fixture with observed coupling plus actual joint simulation where required.

### GY-N4: Closed Acquisition

- Owners: Foundry `RequiredDataSpec` witness and `AcquisitionPlanner`; W7 `DataRequirementSpec` compiler/Fabric source matcher; Fabric retrieval and ingestion to `DataSnapshot`; Data Forge snapshot binding and runtime binding validators; Scholar deep search/OpenAlex plus Data Forge span-grounded SKG writer; `ControlWorker` durable job substrate; S3 acquisition closure discipline (`foundry/methods/catalog/causal/_id_contracts.py:24-75`, `runtime/quality/acquisition_planner.py:528-755`, `data_requirement/compiler.py:83-309`, `fabric/catalog/data_requirement_adapter.py:15-187`, `fabric/data_plane/orchestrator.py:511-639`, `data_forge/kernel/snapshot/finalize.py:135-301`, `runtime/quality/data_forge_binding.py:781-930`, `scholar/search/service.py:214-528`, `data_forge/domains/academic/knowledge/skg_store.py:640-911`, `runtime/http/services/control_worker.py:84-233`).
- Disposition: `REWORK_TO_FIT`.
- Exact gap: workspace acquisition is plan-and-terminate; its adapter preserves only the first missing distribution and may replace an empty witness with `unknown_missing_distribution`, then assigns synthetic positive VOI. No typed request maps all gaps to eligible providers, no control job kind executes it, no receipt binds produced snapshot/SKG versions to requirements, and no rerun proves consumption.
- Pass 5 refinement: live OpenAlex works and Data Forge snapshot binding gates are real, so GY-N4 is a bridge/receipt/re-entry task, not an acquisition provider build.
- Strangle obligation: delete the lossy/unknown fallback; compile all gaps to claim-bound W7 specs, execute one existing provider path, persist a content-bound cost/quality/rights/binding receipt, and re-enter the same workspace/cycle index. Preserve S3's “rerun consumed index delta” closure rule, not its fixture source/VOI.

### GY-N5: Value as Gate

- Owners: Foundry method advisor for non-authoritative ranking/budget/consensus certificates; `run_causal_evaluation` + Foundry registry/methods for execution; `ProductionPolicyEvaluationBackend`; `outcome_prediction.py`; Foundry Bayesian/posterior/calibration primitives; IR/Foundry transportability and density-ratio stack; S8 value-choice provenance; scorecard/Foundry method report gates (`foundry/methods/selection/advisor.py:400-620`, `scientist/nodes/builtins/simulate/run_causal_evaluation.py:392-415`, `foundry/methods/selection/registry.py:491-729`, `scientist/nodes/builtins/decide/policy_runtime_support.py:165-360`, `runtime/quality/design_axes/outcome_prediction.py:430-545`, `foundry/methods/catalog/bayesian/variational.py:383-493`, `foundry/calibration/uncertainty_adapter.py:147-228`, `ir/analytics/transportability.py:364-585`, `foundry/methods/catalog/causal/transport_engine.py:39-161`).
- Disposition: `USE_AS_IS` for advisor planning, method computation, and gates under reachable methods; `REWORK_TO_FIT` only the DesignProblem/candidate-to-advisor projection, execution bridge, and authority sequencing.
- Exact gap: candidate value can compute under Python 3.14 with statsmodels/JAX/SciPy/pymoo plus Bayesian/transport primitives, but DoWhy/EconML/CVXPY project extras are unavailable there; workspace default method selection is not candidate/problem-aware; no `WorldModelRecord`/horizon adapter feeds joint effects into value; output remains descriptive/research-only without governance evidence.
- Strangle obligation: keep Python 3.14 for GY, select reachable methods explicitly, surface unavailable-method blockers truthfully, and feed effect/uncertainty/calibration plus joint-interaction counterexamples into revision before promotion. Do not move the product baseline to 3.13 solely for EconML: the isolated probe found Foundry annotation import breakage and no supported project install.

### GY-N6: B -> A Promotion

- Owners: Ring-2 waist / layer2 readiness / `AuthorityDerivationTrace`; P14 independence map/effective graph and content-binding consumer; G4 governed promotion gate; G5 conversion/status reducers; Scientist promotion support/coordinator; S6/S7/S8 governance gates (`pdc/_impl/gy_waist.py:91-165`, `pdc/_impl/gy_waist.py:451-497`, `runtime/quality/evidence_independence.py:136-248`, `evidence/portfolio/effective_independence_graph.py:87-198`, `runtime/quality/design_axes/coupling_composition.py:2282-2360`, `runtime/quality/proving_ground/governed_promotion_gate.py:1500-1703`, `runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`).
- Disposition: `USE_AS_IS` for enforcement; `REWORK_TO_FIT` for in-cycle sequencing.
- Exact gap: enforcement can promote complete grounded inputs, collapse dependent evidence, and block shadow/self/uncalibrated/unbound authority, but no generation cycle persists and sequences these inputs after value/revision. Scientist champion promotion and G4 PDC promotion remain parallel.
- Strangle obligation: choose one persisted promotion sequence, require resolve + content-bind + verifier provenance for producer roots, entailment/grounding, calibration, effective independence, admissibility, S6/S7/S8 value/mandate gates, and never allow LLM output or an evidence count to upgrade itself.

### GY-N7: Depth-N Universality

- Owners: S2 refinement discipline, workspace operation ledger/terminals and recursive composition contract, Foundry registry plus joint program/NCM engines, coupling composition certificate, S6/S7/S8 axes, scorecard/status envelope, hierarchical-search frontier semantics (`pdc/_impl/layer2_design_search.py:632-880`, `runtime/quality/workspace/loop.py:242-315`, `runtime/quality/workspace/loop.py:865-951`, `foundry/methods/selection/registry.py:805-963`, `foundry/methods/catalog/causal/ncm_engine.py:691-890`, `runtime/quality/design_axes/coupling_composition.py:1255-1533`).
- Disposition: `REWORK_TO_FIT` plus likely `BUILD-NEW` depth-N controller, because no existing owner generalizes the cycle over arbitrary depth/candidate families.
- Exact gap: current loops are fixed single-pass or one-shot shadow; recursion fabricates independent depth-2 children; no universal depth-N cycle budget, world-model resolution rule, joint-simulation escalation, stopping rule, acquisition re-entry, or promotion closure spans generation/value/governance.
- Pass 5 refinement: VOI scheduling, transport, Data Forge/Fabric world lifecycle pieces, and Bayesian primitives reduce the needed new surface to a controller plus bridge records; they do not remove the need for a depth-N universality controller.
- Strangle obligation: reuse existing ledgers/gates/coupling classifications and prove universality with generated intervention families, nonlinear interactions, feedback/shared-resource blockers, missing-data re-entry, and adversarial authority cases. Delete the fixed independent-child demonstration as a production claim once the controller exists.

## North-Star Organ Checklist

Checked against `policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md:24-155`.

| North-star organ | Status | Actual owner/evidence | Missing capability |
|---|---|---|---|
| World model | **PARTIAL / UNIFY_EXISTING** | Pass 5 correction: `fabric/world` is a real append-only epistemic fact/event/provenance store with DuckDB materialization, bitemporal query, snapshots, and branches; `ModelSpec` is the Trinity simulation-model contract; Data Forge snapshot binding and runtime binding validators are real; Foundry `DataSnapshot -> GlobalState` binding is real; IR causal graph plus GCM/NCM mechanisms are real; `SyntheticWorld` is only a reproducible benchmark (`fabric/world/store/segments.py:320-410`, `fabric/world/materialize/duckdb.py:219-491`, `fabric/world/query.py:157-266`, `fabric/world/store/snapshots.py:298-379`, `ir/model_layer/model_spec.py:179-260`, `data_forge/kernel/snapshot/finalize.py:135-301`, `runtime/quality/data_forge_binding.py:781-930`, `foundry/data_plane/bindings.py:69-236`, `foundry/methods/catalog/causal/gcm_fit.py:260-486`). | No lifecycle bridge unifies Fabric facts/snapshot/branch, Data Forge read-surface binding, SKG causal priors, ModelSpec, Foundry mechanisms/simulatable state, policy slots, regional/version/time semantics, and deployment/posterior updates. Missing state is `bridge_missing` / `implemented_but_not_orchestrated`, not broad `producer_missing`; do not build a parallel world store. |
| Joint simulation | **PARTIAL** | Foundry applies multiple mechanisms to shared state; NCM computes nonlinear multi-variable interventions with shared noise; coupled DES/ABM runs a real domain-specific feedback horizon; composition blocks unsupported feedback/shared-resource coupling (`foundry/execute/_internal/graph/__init__.py:114-260`, `foundry/methods/catalog/causal/ncm_engine.py:691-890`, `foundry/methods/catalog/simulation/coupled.py:57-145`, `runtime/quality/design_axes/coupling_composition.py:1255-1533`). | No universal generated-design -> data-bound world -> individual/pairwise/joint horizon controller and no general-equilibrium owner. The coupled ABM proof/calibration receipt is stubbed (`foundry/methods/catalog/simulation/dynamics.py:33-40`), but the coupled engine is real. `bridge_missing` + `consumer_missing`, not greenfield simulation. |
| Intervention atom | **PARTIAL** | Trinity `InterventionSpec` plus linker/registry provide operator, population selector, timing, parameters, and read/write state slots; proof analytics provides typed `do()` expressions, outcome query, composition, and identification (`ir/governance/policy_spec.py:73-108`, `ir/linker/_trinity_linker.py:89-178`, `ir/analytics/interventions.py:134-184`, `ir/analytics/interventions.py:675-1030`). | The halves are not one content-bound atom with target world slot, direct-effect bundle/mechanism, intended downstream effect/path, and world-model version. Build a bridge artifact, not a second lever hierarchy. |
| VOI acquisition / demand paging | **PARTIAL** | W7 requirements and Fabric matching honestly classify required vs available; Fabric/Scholar/OpenAlex can execute; Fabric ingestion emits a bindable snapshot; Data Forge snapshot binding gates snapshot authority; Scientist VOI scheduler computes real search/evaluation decisions; S3 demonstrates consume-the-delta closure (`data_requirement/compiler.py:83-309`, `fabric/catalog/data_requirement_adapter.py:15-187`, `fabric/data_plane/orchestrator.py:511-639`, `data_forge/kernel/snapshot/finalize.py:135-301`, `scientist/methods/search/voi_scheduler.py:169-212`, `runtime/quality/design_axes/substrate_acquisition.py:269-372`). | Foundry's narrow witness is lossy-adapted, current acquisition planner terminates instead of executing, no acquisition job/receipt binds every requirement to cost/quality/rights/output, and no same-workspace re-entry exists (`runtime/quality/acquisition_planner.py:528-748`). |
| Two-contour monitoring | **PARTIAL** | DDM computes drift/performance/readiness/incidents; multiple-testing controls a submitted hypothesis family; `DecisionFeedbackService` persists confirm/refute/review and reissue; S13 enforces A-before-B and attribution; Foundry has Bayesian posterior/calibration primitives that can be reused (`ddm/detectors/realized_performance_monitor.py:49-258`, `ddm/calibration/multiple_testing.py:38-93`, `scientist/feedback/core.py:204-533`, `runtime/quality/design_axes/post_deploy_accountability.py:316-390`, `foundry/methods/catalog/bayesian/protocols.py:1533-1647`, `foundry/calibration/uncertainty_adapter.py:147-228`). | No deployed-policy Bayesian effect updater/controller, no exploratory whole-variable anomaly controller, no anomaly -> candidate edge/required-data/experiment promotion, and no write-back to the world model. The updater/controller is **GREENFIELD over reusable Bayesian primitives**. |
| Safety-kernel firewall | **EXISTS** | Candidate firewall and span entailment reject ungrounded claims; Ring-2 and authority derivation reject self-promotion; G4/G5 require grounded/calibrated families; P14 collapses dependent evidence and content-binds lineage; S6/S7/S8 constrain blind spots, mandate, and value authority (`runtime/quality/candidate_firewall.py:228-365`, `scientist/validation/citation_faithfulness.py:297-365`, `pdc/_impl/gy_waist.py:91-165`, `runtime/quality/proving_ground/governed_promotion_gate.py:114-157`, `runtime/quality/design_axes/coupling_composition.py:2282-2360`). | Enforcement is real and should be reused as-is. The GY lifecycle bridge that invokes it after every generation/value/refinement and before promotion is missing; that is orchestration, not a missing kernel. |

Whole-check verdict after Pass 5: none of the six north-star organs is wholly greenfield. The safety kernel exists; the other five are partial assemblies. The genuinely new work is predominantly typed lifecycle bridges/controllers, plus the post-deployment Bayesian updater/controller and the `WorldModelRecord` lifecycle bridge. The world store itself is not greenfield.

## Pass 4 Completeness Sweep

High-value coverage closed:

- Every user-named Pass-4 owner is now `done` in the tracker: isolated interpreter/dependency experiment, world representation and joint execution, intervention atom, monitoring, required/available data, connector execution/re-entry, authority derivation, and evidence independence.
- The Pass-3 weak Foundry advisor owner is now closed: it is a real budget/truthfulness/consensus planner, not a method executor and not currently called by GY.
- The complete capability chain has an explicit reality label at every hop: front door `real/forked`; generator `real organs but un-orchestrated`; atom `partial/split`; grounding `real/unbridged`; world/joint execution `partial`; value `real under 3.14 subset`; revision `discipline real/controller absent`; acquisition `execution real/re-entry absent`; promotion `enforcement real/un-orchestrated`; monitoring `partial next horizon`.

Pass 5 closure status:

- Credentialed gateway/OpenAlex operational verification is now done. The live gateway account supports Qwen/MiniMax/Kimi, not the hardcoded `gpt-5-mini`; the Qwen-supported run produced a real drafter artifact and a real critic report through the existing agents. OpenAlex returned live work metadata for the EITC query.
- The fabric/world miss is corrected. World model work is now `UNIFY_EXISTING`: `fabric/world` + Data Forge snapshot binding + IR `ModelSpec` + Foundry input binding/GlobalState/mechanisms + SKG priors need one lifecycle envelope, not a parallel world store.
- The hidden-code sweep found reusable owners for VOI scheduling, Bayesian/posterior primitives, and transportability. It did not find a canonical DesignProblem, unified intervention atom, acquisition receipt/re-entry bridge, deployed Bayesian updater, or universal joint-simulation horizon controller.
- `run_policy_blueprint_runtime` still cannot be honestly driven on a GY-produced candidate because that input chain does not exist; this remains the diagnosed `bridge_missing`, not an unread runtime owner.
- The formal disposition ledger/validator and rewritten GY-N1..N7 tasks are the next GY-N0 deliverables; this notebook is now the code-grounded substrate for them.

## Revisions Log

- Pass 5: Was "world model missing a higher-level lifecycle owner" after the `fabric/world` correction -> now "several lifecycle pieces already exist: `ModelSpec` for simulation contract, Data Forge snapshot binding for read-surface/data lineage, runtime Data Forge binding validators, and Foundry input bindings for `DataSnapshot -> GlobalState`; the missing owner is the `WorldModelRecord` bridge, not a broad model-state producer" based on `policy-engine/src/polisyos/ir/model_layer/model_spec.py:179-260`, `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py:135-301`, `policy-engine/src/polisyos/runtime/quality/data_forge_binding.py:781-930`, `policy-engine/src/polisyos/foundry/data_plane/bindings.py:69-236`, and the Pass-5 Data Forge/ModelSpec probes.
- Pass 5: Was "VOI/acquisition planner is narrow/lossy and no richer VOI engine was known" -> now "the acquisition planner remains plan-only/lossy, but Scientist has a real predictive VOI/search scheduler and learned routing policies for candidate evaluation/search budgets" based on `policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:169-212`, `policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:448-792`, `policy-engine/src/polisyos/scientist/methods/search/strategies/advanced_policy.py:425-560`, and the VOI probe.
- Pass 5: Was "post-deployment Bayesian causal update is greenfield" -> now "the deployed updater/controller is greenfield, but Foundry Bayesian posterior/calibration primitives are real and reusable" based on `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/variational.py:383-493`, `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py:1533-1647`, `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py:147-228`, and the Bayesian probe.
- Pass 5: Was "transported_limited/external validity lightly covered as G2/gate semantics" -> now "IR transportability, Foundry transport solver, density-ratio diagnostics, and method-requirement compilation are real reusable external-validity owners" based on `policy-engine/src/polisyos/ir/analytics/transportability.py:364-585`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_engine.py:39-161`, `policy-engine/src/polisyos/foundry/methods/catalog/causal/density_ratio.py:724-889`, `policy-engine/src/polisyos/method_requirement/compiler.py:319-440`, and the transport probe.
- Pass 5: Was "coupled ABM proof result is stubbed" with possible ambiguity -> now "the coupled DES/ABM horizon engine is real; the stub is specifically the ABM proof/calibration receipt attached by `_abm_result_stub(...)`" based on `policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:57-145`, `policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:140-144`, and `policy-engine/src/polisyos/foundry/methods/catalog/simulation/dynamics.py:33-40`.
- Pass 5: Was "real LLM generator organs exist from fake-client probes; live credentials unverified" -> now "live gateway credentials work with catalog-supported Qwen/MiniMax/Kimi; `gpt-5-mini` is unsupported by the current account; Qwen produced a real drafter result and critic report through existing agents" based on `policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py:276-330`, `policy-engine/src/polisyos/scientist/agent/drafter_clients.py:337-420`, `policy-engine/src/polisyos/scientist/agent/critic.py:431-560`, and the Pass-5 live gateway probe.
- Pass 5: Was "OpenAlex live behavior not verified" -> now "OpenAlex provider returned a live EITC work result via the real client; acquisition execution is operationally reachable, while the GY receipt/re-entry bridge remains missing" based on `policy-engine/src/polisyos/data_forge/domains/academic/openalex/client.py:17-134` and the Pass-5 OpenAlex probe.
- Pass 4: Was "world model PARTIAL with producer/lifecycle missing; Fabric data binding + Foundry mechanisms real but no production world-store owner" -> now "world model is `UNIFY_EXISTING`: `fabric/world` is a real current bitemporal epistemic fact/provenance/snapshot/branch substrate, Foundry owns mechanisms/simulatable state, SKG owns literature priors, and the missing object is a `WorldModelRecord`/lifecycle bridge binding those four" based on `policy-engine/src/polisyos/fabric/world/store/segments.py:320-410`, `policy-engine/src/polisyos/fabric/world/materialize/duckdb.py:219-491`, `policy-engine/src/polisyos/fabric/world/query.py:157-266`, `policy-engine/src/polisyos/fabric/world/store/snapshots.py:298-379`, and the Pass-5 round-trip probe.
- Pass 1: Was "policy-design selection may occur from policy request refs" based on code-reading uncertainty -> now "policy request/trinity artifact refs alone selected `scientist_default` in probe; policy text params select `scientist_policy_verified`; policy-design requires explicit workflow/profile/policy_mode" based on `workflows/selection.py:64-97` and selector probe output.
- Pass 1: Was "hierarchical search parameterless/success path needs probe" -> now "default mock-formalized candidate fails closed before Stage B because Lex bounds are missing" based on probe raising through `lex/interventions.py:1024` and `scientist/policy_design/search.py:347`. Parameterless/success path still open with a deliberately non-tunable or bounded candidate.
- Pass 1: Was "statsmodels/jax fallback path not started" -> now "dependency-level fallback exists for statsmodels diagnostics, JAX/NumPy CI, pymoo multiobjective, and SciPy quadratic fallback; EconML/DoWhy/CVXPY unavailable on Python 3.14" based on import probe and code anchors in `_registry_boot.py`, `ci_backends.py`, `constraint_discovery.py`, `diagnostics.py`, `multiobjective.py`, and `convex.py`.
- Pass 1: Was "honest GY workspace loop unknown" -> now "`run_fixture(...)` is a real but fixed BIND -> ESTIMATE -> VERIFY harness, not a generation/revision cycle; `cycle_index=3` is the fixed trajectory count, not evidence of iterative search" based on `runtime/quality/workspace/loop.py:110-113`, `runtime/quality/workspace/loop.py:1471-1664`, and the fixture probes.
- Pass 1: Was "S2 shadow design search unknown" -> now "`run_s2_shadow_design_loop(...)` is a single-iteration shadow replay with a hardcoded `credit_guarantee` candidate, while its refinement discipline types are reusable" based on `pdc/_impl/layer2_design_search.py:632-880`, `pdc/_impl/layer2_design_search.py:933-1103`, `pdc/_impl/layer2_design_search.py:1441-1534`, and S2 probe variants.
- Pass 1: Was "value path may be blocked by unavailable causal/convex deps" -> now "GY-N5 should be rewritten as reuse-with-available-method-subset: synthetic control, DID, diagnostics, SciPy QP fallback, and pymoo multiobjective compute under Python 3.14; DoWhy/EconML fail explicitly; CVXPY is absent but not required for the probed QP path" based on the dependency/value probe and method anchors in the Stage-B sections.
- Pass 1: Was "outcome_prediction value owner unread" -> now "`outcome_prediction.py` is a calibration/authority gate over forecast support, not the forecast producer" based on `runtime/quality/design_axes/outcome_prediction.py:430-545` and the simulation/observable support probes.
- Pass 1: Was "promotion/authority enforcement unread" -> now "Ring-2 waist and G4 governed promotion enforce verifier provenance, bounded authority, contract-family completeness, and calibration; G4 can emit `governed_promoted` for complete explicit inputs but is not orchestrated by the scanned cycle owners" based on `pdc/_impl/gy_waist.py:91-129`, `runtime/quality/proving_ground/governed_promotion_gate.py:1500-1703`, `runtime/quality/proving_ground/governed_promotion_gate.py:2616-2750`, and promotion probes.
- Pass 1: Was "bounded request agent wiring unknown" -> now "G6 bounded agent and `AgentEventBridge` are real candidate-only routing/audit/proposal surfaces, scoped to G5/Ring-1 hints and not invoked by `loop.py` or the Scientist design DAG in caller scans" based on `runtime/quality/proving_ground/bounded_request_agent.py:1318-1608`, `runtime/quality/workspace/agent_proposal_bridge.py:51-208`, and bridge/G6 probes.
- Pass 2: Was "existing candidate generation is scripted/fixed" -> now "the selected/plain-policy generation path is scripted/fixed, but real LLM drafter/formalizer/critic organs exist and produced varied probe outputs; they are not orchestrated into GY" based on `scientist/agent/drafter_clients.py:328-408`, `scientist/agent/formalizer.py:1519-1644`, `scientist/agent/critic.py:417-510`, and the Pass 3 generator probe.
- Pass 2: Was "workspace acquisition is plan-only" -> now "workspace acquisition remains plan-only, but execution-capable acquisition/grounding owners exist in Fabric retrieval, Scholar deep search/OpenAlex, Data Forge academic batch, and SKG; the missing piece is the bridge/re-entry" based on `runtime/quality/acquisition_planner.py:528-755`, `fabric/retrieval/service.py:230-444`, `scholar/search/service.py:214-382`, `data_forge/domains/academic/openalex/client.py:32-110`, and the Fabric execution probe.
- Pass 2: Was "A-grounding exists in multiple separate forms, bridge open" -> now "candidate-level A-grounding machinery is concrete: candidate firewall requires resolver-backed span grounding plus entailment, SKG query/search exists, and policy grounding matrix gates final claims; none are called in the workspace/GY cycle" based on `runtime/quality/candidate_firewall.py:228-365`, `scientist/validation/citation_faithfulness.py:297-365`, `data_forge/domains/academic/knowledge/skg_query.py:105-183`, `scientist/validation/policy_grounding.py:1477-1688`, and the grounding probe.
- Pass 2: Was "value methods are real under available dependency subset" -> now "a candidate-shaped Stage-B value probe computed `policy_value=3.0` plus uncertainty/governance degradation through `ProductionPolicyEvaluationBackend`; value is reusable, but authority remains `research_only` without governance/provenance evidence" based on `scientist/nodes/builtins/decide/policy_runtime_support.py:165-360`, `scientist/nodes/builtins/decide/policy_runtime_support.py:461-530`, and the Stage-B probe.
- Pass 2: Was "S6/S7/S8/scorecard weakly covered" -> now "S6/S7/S8/scorecard are real authority/gate producers: S6 emits bridge and constraint updates, S7 blocks wrong-role/oversight-theater decisions, S8 blocks LLM value authority, scorecard aggregates normalized evidence into blocking gates; none are the cycle controller" based on `runtime/quality/design_axes/blind_spot_firewalls.py:987-1090`, `runtime/quality/design_axes/mandate_bounded_delegation.py:558-631`, `runtime/quality/design_axes/value_choice_provenance.py:310-370`, `runtime/quality/scorecard.py:9955-10404`, and the governance probe.
- Pass 1/2: Was "no canonical DesignProblem, exact candidates still diffuse" -> now "the competing problem/candidate surfaces have been mapped: `PolicyIntentEnvelope`, Scientist `ProblemFrame`, verified `PolicyRequestFrame`, IR `ProblemFrame`, S2 input, raw workspace intent dict, and `PolicyCandidateSchema`; none is sufficient alone" based on the DesignProblem census and probe.
- Pass 1/2: Was "Python 3.13 likely unlocks EconML only; DoWhy/CVXPY require 3.12" from project markers -> now "an isolated 3.13 environment installed/imported/smoked EconML 0.16, modern DoWhy 0.14, and modern CVXPY, but the project itself requires 3.14, pinned DoWhy 0.13 is unavailable, and Foundry/workspace collection breaks on evaluated jaxtyping dimension names" based on the Pass-4 isolated probes and `foundry/contracts/state.py:11-28`, `foundry/contracts/state.py:72-87`. Markers describe the supported project set, not every upstream wheel.
- Pass 3: Was "joint simulation/combinatorial wall weakly covered" -> now "joint execution is partial, not greenfield: shared-state multi-mechanism execution, nonlinear multi-variable NCM worlds, and domain-specific coupled feedback are real; no universal whole-design horizon/controller exists" based on `foundry/compile/_graph.py:20-122`, `foundry/execute/_internal/graph/__init__.py:114-470`, `foundry/methods/catalog/causal/ncm_engine.py:691-890`, and joint probes.
- Pass 3: Was "typed intervention atom unresolved/possibly absent" -> now "the atom is split between executable Trinity action/linker state slots and proof-kernel typed `do()` algebra; the missing owner is their content-bound bridge" based on `ir/governance/policy_spec.py:73-108`, `ir/linker/_trinity_linker.py:89-178`, `ir/analytics/interventions.py:134-184`, and atom probes.
- Pass 3: Was "post-deployment monitoring possibly greenfield" -> now "DDM/FDR/decision-feedback/S13 are real partial organs, but Bayesian effect update, exploratory anomaly orchestration, and world-model write-back are greenfield" based on the monitoring bodies and probes.
- Pass 3: Was "acquisition execution exists outside the loop" -> now "the exact closed path is known: W7 requirement -> Fabric/Scholar plan -> durable job -> ingestion/span-grounded SKG -> content-bound receipt -> world binding -> same-workspace rerun; the current Foundry adapter is additionally lossy and can assign positive VOI to `unknown_missing_distribution`" based on `acquisition_planner.py:528-748`, W7/Fabric matching probes, and real fake-connector ingestion probe.
- Pass 2: Was "authority/promotion enforcement reusable" -> now "P14 effective independence is also a real authority consumer: three raw lines collapsed to two effective units in probe, scorecard validates maps, and composition requires claim/root/lineage/content-hash/verifier binding" based on `evidence_independence.py:136-248`, `effective_independence_graph.py:87-198`, and `coupling_composition.py:2282-2360`.
- Pass 3: Was "Foundry advisor not deeply read" -> now "advisor is a real metadata/history/cost/consensus planner that can fail closed and certify budget selection, but it has no GY caller and executes zero methods" based on `foundry/methods/selection/advisor.py:400-620`, `foundry/methods/selection/advisor.py:823-1062`, caller scan, and probe.

## Pass 0 Summary

Created the investigation notebook before reading repository code.

## Pass 1 Running Notes

Started with required repo guidance. The pattern lens to carry into code reading is: do not accept a generation/search artifact as real unless producer, persisted artifact/event, orchestration bridge, consumer, visible surface, and semantic/negative verification are all shown; watch especially for `P25` search-frontier authority, `P27` parallel implementations, and `P30` plan-named owner drift.

## Pass 1 Summary + Next Start

Completed deeply in this pass:

- Runtime NL front door and typed outputs: `nl_pipeline.py`, `assurance_case.py`, `ProblemFrame`, PI/data-need agents, with a mock behavior probe.
- Scientist workflow routing and policy-design DAG skeleton: `run_experiment`, `selection.py`, `builder.py`, `policy_design.py`, simple/langgraph engines, with selector probes.
- Policy-design generation-adjacent node chain: request frame, legal candidate pack, draft option set, mock formalization, and Trinity-to-candidate bridge.
- Hierarchical search first pass: node bridge, Lex adapter, `PolicyCandidateSchema`, coordinator, bounds gate, and a default-candidate fail-closed probe.
- Dependency risk slice for value path: EconML/DoWhy/CVXPY absent on Python 3.14; statsmodels/JAX/pymoo/SciPy present; code fallback paths partly read.

Top reshaping findings:

- There is no single proven NL -> `DesignProblem` -> generator path yet. Runtime NL intent, Scientist `ProblemFrame`, verified-policy `PolicyRequestFrame`, Trinity, and `PolicyCandidateSchema` are separate typed surfaces with bridges/forks, not one continuous owner.
- `scientist_policy_design` is live but not the default for plain policy text. Plain policy params route to `scientist_policy_verified`; policy-design requires explicit selector fields.
- The existing verified-policy "candidate generation" is scripted: one verified option, optional hypothesis option, fixed tax-subsidy formalization, fixed objective/agent config/seed.
- Hierarchical search is materially real and fail-closed on missing bounds; with the current mock-formalized default candidate it raises before Stage-B value, so the default path is not a working generate-value-revise cycle.
- Foundry method availability must be part of GY value semantics: major causal/convex deps are unavailable on Python 3.14, while statsmodels/JAX/pymoo/SciPy provide narrower reachable paths.

Most important open questions:

- What exactly does `runtime/quality/workspace/loop.py` do for `run_fixture`, `run_intent`, `OperationRegistry`, BIND/ESTIMATE/VERIFY, and acquisition?
- Is `pdc/_impl/layer2_design_search.py` a hardcoded shadow loop, a reusable refinement discipline, or dead?
- Do `CompileFoundryNode`, `RunSimulationNode`, `build_policy_runtime_evaluation`, and `outcome_prediction.py` compute real value for search candidates under reachable dependencies?
- Where do governed promotion, authority derivation, and the two-ring waist enforce evidence/provenance rather than carrying candidate output forward?
- Is the bounded request agent wired into any loop, or only a proposal/shadow surface?

Next pass should start here:

1. `policy-engine/src/polisyos/runtime/quality/workspace/loop.py`: read `run_fixture`, `run_intent`, `select_search_terminal`, `OperationRegistry`, and BIND/ESTIMATE/VERIFY bodies. Probe a minimal fixture/intent if importable.
2. `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py`: read `run_s2_shadow_design_loop`, `_candidate`, `_grammar_expansion`, and refinement discipline types; probe whether candidates are hardcoded and whether iteration truly updates grammar.
3. Then return to Stage-B value owners: `runtime/quality/design_axes/outcome_prediction.py`, `scientist/nodes/builtins/compile/compile_foundry.py`, `scientist/nodes/builtins/causal/run_causal_readiness.py`, `scientist/nodes/builtins/simulate/run_simulation.py`, and `scientist/nodes/builtins/decide/policy_runtime_support.py`.

## Pass 2 Summary + Where Pass 3 Should Start

Completed deeply in this pass:

- Honest backbone loop: `runtime/quality/workspace/loop.py`, `runtime/quality/acquisition_planner.py`, `runtime/quality/workspace/foundry_consumption.py`, `scientist_node_adapters.py`, and `workflow_playbook_projection.py`.
- Shadow design search: full S2 loop, grammar/candidate/counterexample/refinement/ledger/projection/persistence path, caller scan, and behavior probes.
- Stage-B value owners under reachable dependencies: `outcome_prediction.py`, `run_causal_evaluation.py`, `compile_foundry.py`, `run_causal_readiness.py`, `run_simulation.py`, `policy_runtime_support.py`, `objectives.py`, and causal/optimization catalog slices.
- Promotion / two-ring waist: `layer2_readiness.py`, `gy_waist.py`, G4 governed promotion gate, G4 reducer, direct Scientist promotion node, Scientist evidence bundle, and promotion coordinator slices.
- Bounded agent wiring: G6 bounded request agent, G6 -> G5 route, and workspace `AgentEventBridge`.

Top reshaping findings:

- The workspace loop is the honest backbone but not the cycle: `run_fixture(...)` is fixed BIND -> ESTIMATE -> VERIFY with `cycle_index=3`, descriptive authority, no design-candidate promotion, and plan-only acquisition. `run_intent(...)` is a descriptive Phase-2 adapter that executes `run_causal_evaluation` / `run_normative_arbitration`, not a generator/reviser.
- S2 is not the real generator: it is a shadow, hardcoded, one-iteration credit-guarantee replay. The reusable part is the refinement discipline: grammar expansion contract, constraint store, counterexample record, refinement decision, no-retry flag, and ledger structure.
- Value is not globally blocked on Python 3.14. DoWhy/EconML/CVXPY are unavailable, but synthetic control, DID, parallel-trends diagnostics, SciPy QP fallback, and pymoo multiobjective computed real results. `outcome_prediction.py` gates/calibrates support; it does not compute the forecast.
- Promotion enforcement already exists but is outside the cycle: Ring-2 waist rejects authority upgrades without verifier provenance; G4 can promote only complete grounded contract sets and blocks missing calibration/shadow self-promotion. Scientist champion promotion is a separate evidence-gated path, and the direct node is disabled in policy mode.
- G6 bounded agent and `AgentEventBridge` are real candidate-only routing/audit surfaces, not a GY-N3 cycle controller.

Most important open questions:

- How, if at all, does `run_policy_blueprint_runtime` connect Scientist champion promotion, runtime support, and G4 PDC promotion?
- Can a deliberately valid bounded `PolicyCandidateSchema` reach Stage-B compile/readiness/simulation/value end to end with an actual `ctx.foundry`, or is the current working value path limited to `run_causal_evaluation` in workspace `run_intent(...)`?
- Is there any acquisition execution owner beyond `AcquisitionPlanner.plan_from_required_data(...)`, or is the generation-cycle surface intentionally plan-and-terminate until a later data-acquisition capability is wired?
- Which owner should become the canonical GY controller: a reworked workspace loop, Scientist policy-design workflow, or a new thin orchestrator that composes existing owners without duplicating them?
- How should G4 PDC promotion and Scientist champion promotion relate: one canonical promotion waist, sequential gates, or separate surfaces with explicit boundaries?

Pass 3 should start here:

1. Trace `run_policy_blueprint_runtime` and surrounding Scientist/runtime promotion owners to determine whether G4 and Scientist champion promotion are already bridged or parallel.
2. Build a minimal bounded candidate probe for the Scientist Stage-B path that reaches compile/readiness/simulation/value with available methods, or records the exact blocker.
3. Follow acquisition outward from the workspace terminal and planner to confirm whether any execution-capable acquisition producer exists.
4. Deepen the remaining generator-adjacent owners: `scientist/orchestration/llm/cycle.py`, `drafter_clients.py`, `formalizer.py`, `critic.py`, and retrieval, focusing only on whether they can produce non-hardcoded candidate artifacts under bounded authority.
5. Convert the refined map into the later GY-N0 disposition ledger once Pass 3 closes the promotion/value/acquisition open questions.

## Pass 3 Summary + Where Pass 4 Should Start

Completed deeply in this pass:

- Generator organs and blueprint runtime: real LLM drafter/formalizer/critic/multipass owners, mock fallback behavior, and blueprint runtime as downstream evaluation/funnel/promotion plumbing.
- Bounded Stage-B value probe: a candidate-shaped policy value path computed real causal effect/value/uncertainty under Python 3.14 with available statsmodels/JAX/SciPy/pymoo-compatible paths, while preserving research-only/promotable-source downgrade without governance evidence.
- Acquisition execution search: workspace remains plan-only, but Fabric retrieval, Scholar deep search/OpenAlex, Data Forge academic batch, and SKG are real execution/grounding owners outside the workspace loop.
- Grounding connection: candidate firewall, citation entailment, SKG query/search, and policy grounding matrix are real A-grounding enforcement pieces, but not invoked by the GY loop.
- DesignProblem candidate census: runtime `PolicyIntentEnvelope`, Scientist `ProblemFrame`, verified `PolicyRequestFrame`, IR `ProblemFrame`, raw workspace intent dict, S2 input, Trinity, and `PolicyCandidateSchema` were mapped as separate surfaces.
- Remaining governance/value owners: S6 blind-spot firewalls, S7 mandate-bounded delegation, S8 value-choice provenance, scorecard aggregation, and Foundry method registry/selection.
- Payoff synthesis: added `GY-N1..N7 -> Owners Mapping` with owner, disposition, exact gap, and strangle obligation for each workstream.

Top reshaping findings:

- Generator verdict: real gateway-backed generator organs exist, but the live/plain-policy path remains scripted/fixed and no GY controller uses those organs as NL -> DesignProblem -> grounded candidate frontier.
- Stage-B value verdict: GY-N5 is reuse-with-available-method-subset, not blocked. The probe computed `policy_value=3.0` with uncertainty and governance degradation; unavailable DoWhy/EconML/CVXPY should be blockers for those methods, not for value globally.
- Acquisition verdict: execution exists, but not where the workspace loop currently stops. GY-N4 is a bridge/re-entry task, not a from-scratch acquisition build.
- Grounding verdict: A-grounding is real and fail-closed, especially candidate-firewall span grounding and entailment, but it is not wired as the "A grounds B" hop of the cycle.
- DesignProblem verdict: no existing type should be adopted as-is; GY-N1 needs a canonical bridge over existing projections.
- Governance verdict: S6/S7/S8/scorecard are usable gates/constraints, not controllers. They should constrain and close the cycle, not replace the cycle.

Completeness sweep:

- Closed high-value Pass 3 gaps: generator organs, blueprint runtime role, candidate-level value probe, acquisition execution owners, A-grounding owners, DesignProblem competing types, S6/S7/S8, scorecard, Foundry method registry/default selection.
- Remaining deferrable gaps for Pass 4: exact production gateway behavior with real model clients was not run; OpenAlex/Scholar network execution was code-read and provider-probed only through local/fake paths; full blueprint runtime was not driven end-to-end on a GY-produced candidate; the `foundry/methods/selection/advisor.py` policy was not deeply read because active workspace selection uses explicit/default FQN; the final DesignProblem bridge contract is a design decision, not an investigation fact.

Pass 4 should start here:

1. Decide and specify the canonical GY controller boundary: reworked workspace loop, Scientist workflow extension, or new thin orchestrator composing existing owners.
2. Read `foundry/methods/selection/advisor.py` only if GY-N5 will use advisory method selection rather than explicit method FQNs.
3. Prototype or probe one fully bridged mini-cycle in investigation mode: DesignProblem projection -> LLM candidate -> candidate-firewall/SKG grounding -> Foundry value -> S2-style refinement decision -> G4/S6/S7/S8 promotion blockers.
4. Resolve promotion sequencing: G4 governed promotion only, Scientist champion promotion then G4, or separate surfaces with explicit authority boundaries.
5. Convert this notes document into the formal GY-N0 disposition ledger and rewrite GY-N1..N7 tasks from the `GY-N1..N7 -> Owners Mapping` section.

## Pass 4 Summary + Where Pass 5 Should Start

Completed deeply in this pass:

- Isolated Python 3.13 experiment: install/import/compute smokes for EconML, pinned and modern DoWhy, CVXPY, JAX, and statsmodels; targeted 3.13 vs 3.14 workspace/value/core regression comparison; throwaway environments only.
- North-star world model and joint simulation: synthetic benchmark world, Fabric-to-`GlobalState` binding, causal graph/mechanism fit, Foundry shared-state program execution, nonlinear NCM joint interventions, coupled DES/ABM, composition certificates, and GY-G recursive fixtures.
- Intervention atom: Trinity action/linker/mechanism slots, Lex lowering, proof-kernel typed interventions/composition/identification, and universal policy grammar.
- Post-deployment monitoring: DDM detectors/readiness/incidents, multiple-testing control, decision-feedback/reissue, and S13 attribution/authority firewall.
- Required vs available data and closed acquisition depth: Foundry ID witnesses, lossy GY planner adapter, W7 requirements/Fabric matching, real connector ingestion to snapshot, Scholar/OpenAlex/Data Forge/SKG path, worker dispatch gap, and same-workspace re-entry obligation.
- Authority depth: evidence-kind vs decision-grade, Ring-2 provenance, authority derivation, G4/G5, P14 effective-independence computation/content binding, scorecard/composition consumers, and behavior probes.
- Foundry method advisor: truthfulness/data/cost ranking, Pareto/budget certificates, strict consensus refusal, caller scan, and probe.

Top reshaping findings:

- Python target: stay on supported 3.14 for GY-N5. Python 3.13 adds EconML and can run modern DoWhy/CVXPY, but the project rejects 3.13 and Foundry/workspace collection breaks on evaluated jaxtyping dimensions. Python 3.12 is needed only for the current pinned DoWhy 0.13/old-CVXPY pair, not for value globally.
- Joint simulation: **PARTIAL, not pairwise-only and not complete**. Shared-state mechanism execution, nonlinear multi-`do()` NCM, and domain-specific feedback are real; the universal data-bound whole-design horizon/controller and general-equilibrium path are missing.
- Intervention atom: **PARTIAL and split**. Trinity owns executable action/state footprint; proof analytics owns typed causal intervention/outcome semantics. GY-N2 should build their content-bound bridge, not another intervention hierarchy.
- Monitoring: **PARTIAL next horizon**. DDM/FDR/decision-feedback/S13 are real; Bayesian causal effect update, anomaly-to-confirmatory promotion, and world-model write-back are absent.
- Acquisition: real execution exists from connectors to `DataSnapshot` and from OpenAlex claims to SKG, but the GY plan is lossy/hardcoded and no durable job/receipt/re-entry bridge consumes it.
- Promotion: authority derivation and P14 are real consumers, not labels. GY-N6 reuses them; only persisted in-cycle sequencing is missing.

Comprehensive GY ownership verdict:

- N1 `REWORK_TO_FIT`: bridge existing intent/problem projections into one canonical generation request.
- N2 `REWORK_TO_FIT`: orchestrate real LLM organs and bind Trinity action to causal `do()`/world semantics; strangle mock/fixed generators.
- N3 `REWORK_TO_FIT` plus a thin controller: compose workspace honesty, S2 refinement discipline, grounding, joint simulation, and revision.
- N4 `REWORK_TO_FIT`: lossless requirements, existing acquisition execution, content-bound receipt, and same-cycle re-entry.
- N5 `USE_AS_IS` computation/advisor/gates on 3.14; rework only problem-aware selection, execution bridge, and authority sequencing.
- N6 `USE_AS_IS` Ring-2/G4/G5/P14/S6/S7/S8 enforcement; rework only one canonical persisted promotion sequence.
- N7 `REWORK_TO_FIT` plus a depth-N controller: replace declared-independent fixtures with observed coupling, joint escalation, budgets, stopping, and adversarial universality proofs.

Pass 4 handoff items and Pass 5 disposition:

1. Convert this census into the disposition ledger/validator and rewrite GY-N1..N7 from the owner mapping: still the next GY-N0 deliverable, not part of this census pass.
2. Decide the canonical thin-controller and promotion sequence boundaries: still architecture decisions, now supported by the field-level seam contracts above.
3. Credentialed gateway/OpenAlex operational verification: completed in Pass 5. World-model lifecycle and Bayesian post-deployment update are now specified as concrete workstreams, not unresolved owner-discovery questions.

## Pass 5 Final Summary + Convergence Status

Completed deeply in this pass:

- Corrected the world-model verdict by reading and probing `fabric/world` store/materialization/query/snapshot/branch code end to end.
- Ran a targeted hidden-code sweep across all major `src/polisyos` subsystems and deeply investigated newly relevant owners: `ModelSpec`, Data Forge snapshot binding, Foundry input bindings, Scientist VOI scheduler, Foundry Bayesian/posterior primitives, transportability, and joint simulation precision.
- Specified the three hardest seams as field-level contracts: `InterventionAtomBinding`, `WorldModelRecord`, and `JointSimulationHorizonController`.
- Ran live operational probes: gateway model catalog + real drafter/critic calls through the supported Qwen model, and a live OpenAlex query.
- Updated the coverage tracker, per-asset sections, cross-cutting maps, reuse/rework/delete list, north-star organ checklist, GY-N1..N7 mapping, and revisions log.

Top final findings:

- `fabric/world` is a real current bitemporal epistemic world substrate. The north-star world model is not greenfield; it is `UNIFY_EXISTING` across `fabric/world`, Data Forge snapshot binding, IR `ModelSpec`, Foundry state/mechanisms, and SKG priors. The missing artifact is `WorldModelRecord`.
- The hidden sweep collapses several possible build-new plans into rework: VOI scheduling, Bayesian posterior/calibration, transportability, DataSnapshot-to-GlobalState binding, and world fact storage already exist.
- The genuinely build-new cores are narrow but load-bearing: canonical `DesignProblem` bridge, `InterventionAtomBinding`, `WorldModelRecord`, `JointSimulationHorizonController`, acquisition receipt/re-entry, and the post-deployment Bayesian/anomaly controller.
- Live generator operations work, but the configured/default `gpt-5-mini` profile is not supported by the current gateway account; GY-N2 needs model-catalog/profile preflight.
- Acquisition execution is operationally reachable via OpenAlex/Fabric/Data Forge, but the GY planner still needs a durable receipt and same-cycle re-entry.

Recommended next step:

- Create a dedicated world-model-lifecycle workstream before or at the front of GY-N3/N5. It should build `WorldModelRecord` as one bridge over existing owners, not a new store. Without it, generation/value/revision cannot name the world version, policy slots, transport context, or deployment update lineage they operate on.

Convergence status:

- The investigation has converged for GY-N0 owner discovery. Another sweep is unlikely to change the major build-vs-rework verdicts. Remaining work is synthesis into the disposition ledger/validator and rewritten GY-N1..N7 tasks, not more census.

## Known Debt: Layer 3 Lifecycle Payload Drift

Ticket: `GY-LIFECYCLE-DEBT-2026-06-27`

Owner: `team-runtime-quality`

Scope: `layer3_gy_composition_certificates.json`, `layer3_gy_phase2_*` proof payloads, and `layer3_gy_workflow_failure_authority_proofs.json`.

Evidence collected during the GY-N-V closing fix pass:

- Clean HEAD comparison used `git worktree add --detach /tmp/polisyos-gy-base HEAD` at `aad375dd`, then attempted the three lifecycle tests from `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py`. Clean HEAD exited with pytest code 4 because that lifecycle test module is absent from committed HEAD, so these red tests belong to accumulated uncommitted Layer 3 lifecycle work rather than the GY-N-V runtime refactor.
- Current working tree run of the three tests exits 1. The failures are committed-vs-live payload drift: composition differs in recomputed artifact hashes, phase2 proof payloads differ from live proof generation, and workflow-failure authority proof payloads differ from live proof generation.
- None of the GY-N-V touched files (`src/polisyos/core/contracts/value_outer_set.py`, `src/polisyos/foundry/contracts/state.py`, `src/polisyos/runtime/quality/data_state_substrate.py`, `src/polisyos/runtime/quality/substrate_registry.py`, `src/polisyos/ir/kernel/slots.py`, `src/polisyos/foundry/agent_sim/wiring/executors.py`, or the GY-N-V validators/tests) are source-of-truth inputs to the three remaining-red lifecycle validators.

Disposition: pre-existing and unrelated to GY-N-V. Do not regenerate those composition/phase2/workflow payloads inside GY-N-V. Close this debt in the lifecycle artifact workstream by either committing the recomputed payloads from the owning validators or removing scratch/untracked proof outputs from lifecycle gates.
