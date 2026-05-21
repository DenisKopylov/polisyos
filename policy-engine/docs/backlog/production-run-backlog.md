---
title: PolicyOS Production Run Backlog
status: active
owner: team-runtime
created: 2026-05-10
last_updated: 2026-05-12
scope:
  - runtime-api
  - control-plane
  - nl-pipeline
  - llm-gateway
  - fabric
  - foundry
  - scientist
  - dashboard
---

# PolicyOS Production Run Backlog

This backlog contains major production-readiness tasks discovered during
end-to-end testing. It is intentionally selective: if the fix is small and the
root cause is known, fix it in code instead of filing it here.

## Entry Template

```markdown
## PRB-000 - Short Title

- Status: Open | In Progress | Blocked | Done
- Severity: Critical | High | Medium
- Owning layer:
- Evidence:
- Production impact:
- Root-cause hypothesis:
- Durable fix path:
- Acceptance gates:
- Notes:
```

## PRB-001 - LLM Gateway Capability And Availability Preflight

- Status: Done
- Severity: Critical
- Owning layer: LLM gateway integration, control-plane launch policy
- Evidence: The real Gonka canary on 2026-05-10 reached the provider but failed
  before PolicyOS workflow execution. The provider first rejected JSON object
  mode as temporarily unavailable, then the fallback request failed with an
  upstream "no endpoints available" response. A later authenticated tiny
  completion preflight could not run because the visible `policy-engine/.env`
  did not contain `POLISYOS_LLM_GATEWAY_API_KEY`; fallback key names were either
  not proxy keys or were rejected by the proxy.
- Production impact: Real runs can fail before the first NL agent result. If
  this is discovered only inside a long job, operators waste time and the job
  failure arrives too late in the lifecycle.
- Root-cause hypothesis: Runtime launch currently treats model names as enough
  to start a production LLM lane, but provider capability and live endpoint
  availability are dynamic and need a preflight gate.
- Durable fix path: Add a preflight step before real LLM jobs that checks
  `/health`, `/v1/models`, `/api/models/capabilities`, pricing, JSON-mode
  support, and a tiny budget-capped completion for the selected model set.
  Cache the result with a short TTL and record it in the job evidence bundle.
- Acceptance gates:
  - Real LLM launch refuses models whose provider preflight is red unless the
    caller explicitly selects a degraded diagnostic mode.
  - Failed preflight becomes a short failed control job with an actionable
    provider/capability error.
  - Done: Credential preflight confirms the canonical env var is present and has the
    expected proxy-key shape before any long NL job starts.
  - Done: Runtime launch now runs mandatory provider preflight for serious
    real-LLM profiles and fails as a short actionable control job when red.
  - Done: Live preflight captures health, model catalog, capabilities, pricing,
    model presence, and a tiny completion before a long NL workflow starts.
  - Done: JSON-mode degradation is recorded as structured
    `response_format_mode=fallback_plain_json` evidence instead of only a log
    warning.
  - Done: Dashboard route-level smoke renders terminal provider failure
    envelopes from a rejected NL launch.
  - Remaining: Add a dedicated provider availability/status panel that makes
    model availability and last preflight timestamp more discoverable.
  - Partial: Env-backed gateway client creation now rejects malformed proxy-key
    values before constructing the real network client.
  - Partial: Provider verification now prefers the canonical
    `POLISYOS_LLM_GATEWAY_API_KEY` proxy key before legacy smoke-test key names.

## PRB-002 - Production Canary Evidence Bundle Automation

- Status: Done
- Severity: High
- Owning layer: ops runners, runtime observability, dashboard diagnostics
- Evidence: Current canary debugging depends on manually correlating launch
  command, job ID, run ID, server logs, provider responses, artifacts, and test
  output.
- Production impact: Manual evidence collection slows root-cause analysis and
  makes production incidents harder to compare across runs.
- Root-cause hypothesis: The system has most of the needed evidence surfaces,
  but no single canary bundle assembler that captures them in one reproducible
  directory or artifact.
- Durable fix path: Extend the real E2E runner to emit a sanitized evidence
  bundle containing command metadata, git revision, request body without
  secrets, job timeline, variant summaries, provider call events, artifact refs,
  run index records, selected logs, metrics snapshots, and dashboard trace refs.
  The assembler now writes optional `dashboard.json` with dashboard base URL and
  Playwright trace/screenshot/video/report references supplied explicitly or via
  `POLISYOS_DASHBOARD_*` environment variables.
- Acceptance gates:
  - Done: Cloud real E2E runner now writes a filesystem canary evidence
    bundle on success and failure.
  - Done: Bundle includes sanitized request/env/job/run/timeline/lineage,
    artifact refs, provider preflight, failure envelope, and performance
    summary when present.
  - Done: Bundle sanitizer recursively redacts API keys, bearer tokens, raw
    secrets, and `POLISYOS_LLM_GATEWAY_API_KEY` values.
  - Done: Local staging/production canary runner writes the same sanitized
    bundle after both success and failure.
  - Done: Local canary evidence falls back to run trace/checkpoint files when
    the runtime run-index API does not yet return run/timeline/lineage payloads.
  - Done: Sanitizer preserves non-secret token/cost accounting fields such as
    `token_usage`, `prompt_tokens`, `completion_tokens`, and `total_tokens`.
  - Done: Add dashboard trace/screenshot references to the bundle for
    operator-facing UI evidence.

## PRB-003 - Real External Data Materialization Lane

- Status: In Progress
- Severity: High
- Owning layer: Fabric retrieval, source contracts, Foundry input bindings
- Evidence: The deterministic lane proves retrieval/materialization logic with
  fixtures, but production readiness still needs a real external provider lane
  that persists immutable source payloads and bindings. On 2026-05-10, runtime
  discovery was fixed to load the recently added canonical curated contracts at
  `production_data/canonical/local_data_20260501/policy_engine_data/curated`.
  The NL runtime now also derives dataset, Lex legal KG, academic/SKG, benchmark,
  and Ukraine simulation bundle paths from `production_data_root`. On
  2026-05-12, the local production canary completed with real production data
  from `production_data/manifest.json`, persisted `data_snapshot_ref`,
  `input_bindings_ref`, `registry_bundle_ref`, and `quality_report_ref`, and
  recorded the manifest checksum plus selected bundle versions/readiness in the
  evidence bundle.
- Production impact: A run can complete syntactically while relying on weak or
  fixture-only evidence, reducing the quality and auditability of final policy
  outputs.
- Root-cause hypothesis: Runtime NL already passes data needs through retrieval
  and materialization, but the production canary lacks a mandatory small real
  source contract and acceptance proof.
- Durable fix path: Define one low-risk canonical real data source for the MSME
  canary, wire it through Fabric retrieval and Foundry input bindings, and make
  the production canary require a data snapshot or binding artifact.
- Acceptance gates:
  - Done: Canary run materializes a production-data payload into CAS.
  - Done: Scientist workflow receives artifact refs, not only natural-language
    notes.
  - Done: Run evidence context and lineage expose the source, snapshot,
    bindings, selected bundle versions, manifest checksum, and quality
    diagnostics.
  - Remaining: Add an optional separate lane that exercises one approved live
    external data provider after local production-data materialization is green.

## PRB-004 - Phase-Level Production SLOs And Bottleneck Budgeting

- Status: Done
- Severity: High
- Owning layer: runtime observability, control-plane jobs, CAS, dashboard
- Evidence: Hot-path tests exist, and the E2E plan identifies lease time, NL
  step duration, CAS put/get, retrieval/materialization, run index refresh,
  timeline/lineage build, and dashboard first meaningful render as bottlenecks.
  Production canaries still lack a single phase budget report.
- Production impact: Slow or unstable runs are hard to distinguish from broken
  runs, and regressions can hide until a full production workflow is attempted.
- Root-cause hypothesis: Timing data is emitted at several boundaries, but it
  is not normalized into one phase-level SLO artifact for each run.
- Durable fix path: Emit a run performance summary with phase durations, LLM
  latency, retrieval/materialization timing, explicit phase budgets, and
  over-budget status. Expose the summary through runtime agents API, evidence
  bundles, and dashboard. Broader cross-surface timing budgets for queue lease,
  CAS, run-index, timeline/lineage, and dashboard route render are tracked in
  PRB-023.
- Acceptance gates:
  - Done: NL run params now include `run_performance_summary` with variant
    status counts, LLM token/cost/latency totals, step timings, retrieval phase
    timings, phase budget rows, budget summary, and per-variant rows.
  - Done: Hot-path performance tests are green and measure run-index list,
    timeline build, run-index refresh, CAS round trip, cursor progress stream,
    incremental refresh, and lineage build.
  - Done: `/api/v1/runs/{run_id}/agents` exposes `performance_summary` from
    experiment state for dashboard and operator diagnostics.
  - Done: Canary evidence bundle includes `agents.json` and writes
    `performance.json` from the agents pipeline summary when present.
  - Done: Dashboard Agents tab preserves, normalizes, and highlights
    over-budget phases without requiring log inspection.

## PRB-005 - End-To-End Failure Surface Consistency

- Status: Done
- Severity: High
- Owning layer: control-plane jobs, runtime API, dashboard
- Evidence: The real Gonka canary exposed that all-model provider failures were
  previously surfaced as `mock_fallback_disallowed`, masking the gateway root
  cause. The backend variant summary fix now reports
  `no_model_variant_completed:<model>:<reason>`. On 2026-05-10, all-variant
  NL gateway failures also gained a terminal control-job progress envelope with
  `code`, `layer`, `phase`, `retryable`, message, and per-variant reasons.
- Production impact: Masked errors send operators to the wrong owning layer and
  increase mean time to resolution.
- Root-cause hypothesis: Failure details are captured inside variant steps and
  notes, but terminal job errors and dashboard views need a consistent error
  envelope across API, control job, timeline, and UI. The stable API envelope
  and Clerk recovery UI now have route-level smoke coverage for a rejected NL
  launch backed by terminal control-job failure details.
- Durable fix path: Standardize a terminal failure envelope with code, layer,
  provider/model, failing phase, actionable message, retryability, and evidence
  refs. Propagate it through job status, run timeline, and dashboard errors.
- Acceptance gates:
  - Done: NL all-variant gateway failure test covers backend terminal error.
  - Done: Runtime control-job progress includes the same structured envelope,
    and API/job-detail/dashboard rendering have route-level smoke coverage.
  - Done: `/api/v1/control/jobs/{job_id}` exposes top-level `failure` derived
    from progress/error_message while preserving `progress.failure`.
  - Done: Dashboard renders failure code, layer, phase, retryability,
    model/provider, next action, and evidence ref/path in the Clerk recovery
    surface.
  - Done: Route-level smoke includes a fixture-backed terminal failure journey
    that starts from a rejected NL launch.

## PRB-006 - Production Data Root Manifest And Discovery Contract

- Status: Done
- Severity: High
- Owning layer: data-forge, Fabric config, runtime data discovery
- Evidence: `production_data` now contains canonical curated contracts, dataset
  catalog snapshots, academic runtime evidence, Lex bundles, and Ukraine
  simulation assets. Several subdirectories contain manifests. On 2026-05-10,
  a root `production_data/manifest.json` was added with logical bundle roles,
  readiness, preferred runtime paths, and selected artifact checksums. Runtime
  curated discovery and NL/Scientist context defaults now read this manifest
  before falling back to legacy path heuristics.
- Production impact: Production runs become sensitive to local directory
  layout drift. A newly promoted data bundle can exist on disk while runtime
  continues using an older or empty default path.
- Root-cause hypothesis: Production data was promoted recently as a local
  snapshot, but there is no root-level machine-readable contract that declares
  current curated, datasets, academic, Lex, and simulation bundle locations.
- Durable fix path: Add a root production-data manifest with stable logical
  roles, version IDs, artifact checksums, readiness status, and preferred
  runtime paths. Teach runtime/Fabric discovery to read the manifest before
  falling back to legacy path heuristics.
- Acceptance gates:
  - Done: Runtime capabilities report the selected production data root,
    manifest checksum, and logical bundle paths/readiness under
    `constraints.production_data`.
  - Done: A regression test proves a newly versioned production data bundle can
    be discovered without code changes.
  - Done: Scientist context params include the root manifest checksum and
    selected data bundle versions/readiness as
    `production_data_evidence_context`.
  - Done: Canary evidence bundle writes `production_data_evidence.json` with
    the selected context and materialization refs for audit/debugging.

## PRB-007 - Serious Scientist Workflow Transportability Contract Closure

- Status: Done
- Severity: Critical
- Owning layer: Scientist causal workflow, transportability node, decision
  packet contract
- Evidence: Real Gonka canary `R_4e683c62a4dafacc` on 2026-05-10 reached
  Scientist and passed the earlier `link_trinity` blocker, but failed in
  `build_decision_packet` with `node.invalid_state` because the research
  profile requires `transportability_result_ref`. The workflow report shows
  `run_transportability` was skipped and no transportability artifact was
  produced. Follow-up real Gonka canary `R_0b09128ac7de15d3` confirmed the
  closure: `run_transportability` now persists typed
  `ir.transportability_result` and `ir.causal_capability_contract` artifacts
  for serious-profile missing-prerequisite cases instead of silently skipping.
- Production impact: A long production run can spend model/data/workflow time
  only to fail at the final decision-packet boundary. Operators get the missing
  contract late instead of an earlier, owned transportability decision.
- Root-cause hypothesis: The serious decision-packet contract requires
  transportability evidence, while the causal workflow still permits paths where
  no causal report or graph is available and `run_transportability` returns
  `skip` without an explicit insufficient/not-applicable artifact.
- Durable fix path: Decide the production contract semantics: either fail fast
  before decision-packet assembly when transportability prerequisites are
  missing, or make `run_transportability` persist a typed
  insufficient/not-applicable result artifact that satisfies traceability while
  clearly blocking automatic approval.
- Acceptance gates:
  - Done: Research/governed workflows no longer leave
    `transportability_result_ref` implicit when prerequisites are missing.
  - Done: Regression tests cover missing causal report/graph with serious
    profile.
  - Done: The persisted artifact identifies `run_transportability` as owner and
    records the missing prerequisite in `unsupported_reason`.
  - Done: Real canary includes a typed blocking transportability artifact.

## PRB-008 - Schema-Aware LLM Formalizer Healing

- Status: Done
- Severity: High
- Owning layer: NL formalizer, agent prompts, response healing, IR schema
- Evidence: Real Gonka canary `R_4e683c62a4dafacc` produced invalid Trinity
  fields such as `model_spec.agent_config.interaction_topology=well_mixed` and
  `model_spec.fidelity_level=medium`. The formalizer recovered through
  deterministic fallback, but the LLM-native output did not satisfy the schema.
  On 2026-05-10, the LLM formalizer gained pre-validation alias repair for
  common model-spec enums, with audit notes in `model_spec.notes`. On
  2026-05-12, strict schema-healing mode was added so repairable schema drift
  fails with a structured `llm_formalizer_schema_validation_failed` envelope
  instead of falling through to deterministic fallback, and NL model-variant
  failure reporting now preserves that owning layer in control progress.
- Production impact: Silent deterministic fallback reduces transparency and may
  hide drift between model behavior and PolicyOS IR contracts. In stricter
  production settings, this can become a terminal validation failure.
- Root-cause hypothesis: The formalizer prompt and healing loop do not provide
  enough enum-level schema constraints or canonical repair hints for common
  model outputs.
- Durable fix path: Add schema-aware repair maps and prompt constraints for
  enum fields, record each healed field in the run evidence bundle, and make
  strict production mode configurable between fail-fast and audited healing.
- Acceptance gates:
  - Done: Tests cover `well_mixed -> random` and `medium -> hybrid` as the
    chosen canonical mappings.
  - Done: Healed fields are visible in normalized Trinity model notes and in
    run-level variant telemetry as `schema_healing` plus
    `schema_healing_count`.
  - Done: Strict mode can fail with a structured schema error instead of silently
    falling back.

## PRB-009 - Evidence Parameter Payload Normalization

- Status: Done
- Severity: High
- Owning layer: Scientist evidence extraction, parameter resolution, IR schemas
- Evidence: The same real canary emitted repeated
  `EvidenceParameter.model_validate fallback` diagnostics because extracted
  parameter payloads had fields like `ci_low`, `ci_high`, `context_snippet`,
  `pattern_name`, `confidence`, and `variable_hint`, while the target
  `EvidenceParameter` schema requires different canonical fields such as
  `name`. On 2026-05-10, the academic article extraction boundary gained
  normalization for `variable_hint`, `ci_low`/`ci_high`, `context_snippet`,
  `pattern_name`, and numeric extraction confidence. Real and simulated
  production canaries on 2026-05-12 still emitted repeated
  `EvidenceParameter.model_validate fallback` diagnostics. Later on
  2026-05-12, the SKG query boundary gained a pre-validation normalizer for
  production-shaped payloads and the simulated production-data canary completed
  without `EvidenceParameter.model_validate fallback` log lines. Later on
  2026-05-12, parameter candidates gained `normalization_diagnostics`, and the
  academic benchmark/runtime-demand report now preserves those diagnostics in
  parameter candidate artifacts.
- Production impact: Parameter evidence can be partially salvaged but loses
  typed fidelity, which weakens reproducibility, auditability, and downstream
  parameter resolution quality.
- Root-cause hypothesis: Extraction payloads and canonical EvidenceParameter IR
  evolved separately; fallback conversion exists, but there is no explicit
  normalization contract at the boundary.
- Durable fix path: Define a versioned raw-to-canonical evidence-parameter
  mapper with diagnostics, provenance retention, and tests for representative
  production extraction payloads.
- Acceptance gates:
  - Done: Representative production-shaped extraction payloads now validate
    without being dropped.
  - Done: Raw fields are mapped into canonical fields or retained in
    `transfer_conditions`/`heterogeneity_note`, with normalization diagnostics
    retained for downstream evidence reports.
  - Done: Extraction warnings now expose field-level normalization
    diagnostics for mapped/dropped empirical parameter payloads.
  - Done: Parameter resolution artifacts expose normalization diagnostics.

## PRB-012 - Scientist Workflow Heartbeat And Subphase Progress

- Status: Done
- Severity: High
- Owning layer: Scientist workflow executor, control-plane progress, runtime API
- Evidence: Real and simulated production canaries on 2026-05-12 could spend
  several minutes with the control job stuck at `scientist_workflow_started`
  while CAS run traces were actively growing. The workflow eventually
  completed, but operators had to inspect local trace files to prove liveness.
  Later on 2026-05-12, runtime control added a Scientist trace progress bridge;
  the simulated production-data canary completed with
  `scientist_workflow.event_count=98` in `/api/v1/control/jobs/{job_id}`
  evidence.
- Production impact: Long healthy runs can look hung, timeout triage is harder,
  and dashboard users cannot identify the current Scientist node, slow phase,
  or latest artifact without log/CAS access.
- Root-cause hypothesis: Runtime control progress is updated before and after
  `run_experiment`, while Scientist emits detailed trace events only to the run
  store. There is no bridge that turns workflow node events into control-job
  heartbeats.
- Durable fix path: Add a progress sink or event bridge from Scientist executor
  node events to control job progress. Emit current node, node status, elapsed
  time, last artifact refs, warning count, and slow-phase budget status without
  changing public run contracts.
- Acceptance gates:
  - Done: Control job progress advances at least once per Scientist node or fixed
    heartbeat interval during long workflows.
  - Done: Dashboard Clerk/control-job surface shows active Scientist workflow
    progress from `progress.scientist_workflow`, including current node, event,
    phase, event count, latest artifact ref, and update timestamp.
  - Done: Canary evidence bundle captures heartbeat/subphase history.

## PRB-013 - ArtifactID Serialization Contract Cleanup

- Status: Resolved
- Severity: Medium
- Owning layer: IR refs, Pydantic serialization, runtime evidence surfaces
- Evidence: Real and simulated canaries on 2026-05-12 repeatedly emitted
  `PydanticSerializationUnexpectedValue(Expected ArtifactID...)` warnings when
  serializing artifact refs for workflow/evidence payloads. Later on
  2026-05-12, core artifact refs gained stable cross-wrapper
  validation/serialization in both Python and JSON dump modes; the simulated
  production-data canary completed under `PYTHONWARNINGS=error::UserWarning`
  with no `PydanticSerializationUnexpectedValue` lines.
- Production impact: The run can complete, but noisy serializer warnings make
  canary logs harder to scan and may hide real serialization regressions. A
  future stricter serializer setting could turn this into a failed evidence
  write.
- Root-cause hypothesis: Some payload fields are typed as `ArtifactID` but are
  populated with nested `ArtifactID` wrapper instances or mixed string/wrapper
  shapes at serialization boundaries.
- Durable fix path: Normalize artifact refs at IR/API boundaries so every
  public JSON payload contains canonical sha256 strings and every internal
  model receives exactly one `ArtifactID` wrapper layer.
- Acceptance gates:
  - Done: Production canary logs no longer emit ArtifactID serializer warnings.
  - Done: Tests cover nested ArtifactID, string artifact IDs, and public output
    for run reports, timeline, lineage, and evidence bundles.

## PRB-010 - Production Metric Taxonomy And LLM Canonicalization

- Status: In Progress
- Severity: High
- Owning layer: IR metric registry, NL agents, Trinity linker, production data
  discovery
- Evidence: Real Gonka canary `R_806855aea5b2d483` failed `link_trinity`
  because the LLM generated the plausible KPI `msme_loan_volume`, but the core
  metric registry did not contain that ID. A direct registry fix added the KPI,
  but this does not solve future production KPI drift. Follow-up real canary
  `R_0b09128ac7de15d3` then failed `link_trinity` on additional plausible
  production metrics: `ate_estimate`, `causal_pathway_count`, and
  `model_transport_score`. Those IDs are now covered by a targeted registry
  regression test, but the durable taxonomy/canonicalization gap remains.
- Production impact: Production runs can fail late whenever the model invents a
  sensible but unregistered metric, and adding one metric at a time does not
  scale to real policy domains.
- Root-cause hypothesis: The default metric registry is too small for
  production policy domains, and NL agents do not yet canonicalize objectives
  against a versioned metric taxonomy before Trinity linking.
- Durable fix path: Build a production metric taxonomy from `production_data`
  catalog maps, benchmark metrics, Lex references, and domain KPI lists. Add a
  canonicalization step that maps aliases or rejects unknown metrics before
  Scientist workflow execution.
- Acceptance gates:
  - Canary objective metrics are resolved before `link_trinity`.
  - Partial: The LLM formalizer now canonicalizes common production KPI aliases
    such as `msme_credit_volume -> msme_loan_volume` and records schema-healing
    notes on the `ProblemFrame`.
  - Unknown metrics fail in a short, actionable NL validation step with
    suggestions.
  - Done: Canary evidence bundle captures default metric taxonomy schema
    version, metric count, canonicalizer identity, and registry fingerprint.

## PRB-011 - Tenant-Scoped CAS Isolation For Content-Addressed Stores

- Status: Partially Resolved
- Severity: High
- Owning layer: core artifact store, tenant isolation, Scientist workflow store
  composition, runtime run index
- Evidence: During the simulated HTTP E2E smoke on 2026-05-10, propagating
  tenant scope into the embedded control worker correctly made Scientist runs
  tenant-aware, but the workflow store selector wrapped a content-addressed
  `FileSystemCAS` with the string-prefix `NamespacedArtifactStore`. That broke
  sha256 artifact lookups (`AttributeError: 'str' object has no attribute
  'hex'`) when workflow nodes read pre-workflow NL artifacts. The immediate
  E2E blocker was fixed by not applying string namespace prefixes to
  content-addressed filesystem CAS stores; the successful follow-up smoke
  `R_e664e3f8c495521c` completed and exposed tenant/cell via run manifest,
  run index, timeline, and artifact access checks.
- Production impact: Current production safety relies on run-manifest and
  run-index tenant metadata for API authorization, not on physically separated
  CAS object namespaces. That is acceptable for the current single-node debug
  lane, but not sufficient as the durable isolation model for governed or
  production multi-tenant deployments.
- Root-cause hypothesis: The old namespace wrapper was designed for arbitrary
  string-key stores, while the production CAS contract is content-addressed and
  requires stable sha256 IDs. Prefixing IDs corrupts the storage contract; a
  tenant-aware content-addressed store needs a separate ownership/index layer
  or tenant-local roots, not ID mutation.
- Durable fix path: Design and implement a tenant-aware CAS ownership model for
  content-addressed backends: either tenant-local CAS roots with deterministic
  promotion/copy semantics, or a shared immutable blob store plus a signed
  artifact ownership index. Integrate it with run index refresh, artifact
  authorization, lineage, garbage collection, and evidence bundles.
- Acceptance gates:
  - Governed/production runtime can enforce artifact ownership without relying
    only on run manifest traversal.
  - Content-addressed artifact IDs remain canonical sha256 IDs across tenants.
  - Cross-tenant artifact read/write/property tests cover FileSystemCAS and the
    production backend.
  - Canary evidence bundle includes the artifact ownership index or tenant CAS
    root used for the run.

## PRB-014 - Production Policy Quality Evidence Bundle

- Status: Partially Resolved
- Severity: Critical
- Owning layer: ops runners, runtime control evidence, Scientist reports,
  dashboard/API evidence surfaces
- Evidence: Current production/staging canaries prove execution completion and
  materialization refs, but they do not yet prove that final policy artifacts
  are normatively grounded, data-grounded, method-grounded, and conflict-checked.
  On 2026-05-12, the canary evidence assembler gained a first-class
  `quality_evidence/quality_scorecard.json`, separate `execution_status` and
  `quality_status`, and optional sanitized quality subreport files for
  normative evidence, Fabric retrieval traces, Foundry method reports, policy
  grounding matrices, and conflict checks.
- Production impact: A run can be technically completed while producing a weak
  or poorly supported policy artifact. Operators still have to manually inspect
  Lex refs, Fabric source choices, Foundry diagnostics, workflow reports, and
  final policy text to judge quality.
- Root-cause hypothesis: The evidence bundle was designed first for operational
  debugging. It does not yet have a first-class quality evidence schema that
  connects final policy claims to normative facts, data snapshots, method
  outputs, and conflict checks.
- Durable fix path: Add a `quality_evidence/` section to canary evidence
  bundles with stable subreports: normative evidence, Fabric retrieval trace,
  Foundry method report, policy grounding matrix, conflict check, and quality
  scorecard.
- Acceptance gates:
  - Done: Every production/staging canary writes
    `quality_evidence/quality_scorecard.json`.
  - Done: The bundle records quality status separately from execution status.
  - Done: Missing normative/data/method/conflict evidence produces
    `quality_status=fail` even when `execution_status=completed`.
  - Done: Sanitization rules apply to all quality evidence files.
  - Partial: Real Lex/Fabric/Foundry/conflict subreports are supported by the
    bundle contract but still need to be produced by their owning PRBs.

## PRB-015 - Golden Quality Scenarios And Expected Evidence Contracts

- Status: Resolved
- Severity: Critical
- Owning layer: quality test fixtures, production-data canary runner, docs,
  regression suites
- Evidence: Current canaries now load checked-in golden scenario contracts from
  `tools/ops_runners/runtime/golden_quality_scenarios.json`. The default
  Ukraine MSME scenario remains the primary canary lane, and four additional
  scenarios cover employment subsidy equity risk, tax relief budget constraints,
  digital training regional equity, and agricultural subsidy-rule conflict.
- Production impact: Quality regressions can hide behind one scenario that has
  favorable data and norms. Real production runs need repeatable, diverse
  scenario contracts.
- Root-cause hypothesis: Resolved. The canary runner previously embedded one
  hardcoded request, so expected quality evidence was not versioned or
  selectable by scenario id.
- Durable fix path: Implemented a golden quality scenario catalog plus
  `tools/ops_runners/runtime/quality_scenarios.py` validation. The local
  production canary runner now accepts `--quality-scenario` and
  `--quality-scenarios-file`, injects the expected evidence contract into the NL
  request context, and writes the contract into the canary evidence bundle as
  `quality_evidence/golden_scenario_contract.json`.
- Verification: The simulated local production canary completed with scenario
  `ukraine_msme_wartime_credit_support` and wrote bundle
  `.polisyos/canary_evidence/prb015_smoke/20260512T110834Z_fe0f7d206ac2458687dc7a1d2be9a8bf`.
  Execution status was `completed`; quality status remained `fail` because the
  next owning PRBs still need to produce Lex, Fabric, Foundry, grounding, and
  conflict subreports.
- Acceptance gates:
  - Done: Each scenario has a checked-in expected evidence contract.
  - Done: Each scenario declares required normative fact classes, admissible data
    source families, Foundry method expectations, and conflict checks.
  - Done: Quality canary runner can execute one scenario by id.
  - Done: Golden scenario failures surface layer, missing evidence type, and next
    action.

## PRB-016 - Lex Normative Applicability Quality Gates

- Status: Partially Resolved
- Severity: Critical
- Owning layer: Lex, normative retrieval, Scientist policy design, quality gates
- Evidence: Canaries now have a stable Lex applicability report contract and
  scorecard validation path. A raw `status=pass` normative report is normalized
  before scoring, so wrong jurisdiction, expired/not-yet-effective norms,
  superseded norms, missing authority metadata, and unanchored major
  recommendations cannot silently pass quality evidence.
- Production impact: The final policy may cite irrelevant, expired, lower-level,
  or non-applicable normative facts. This weakens legal defensibility and
  operator trust.
- Root-cause hypothesis: Partially resolved. Norm retrieval and policy
  generation now have a strict report validator, but the runtime pipeline still
  needs to produce the report from real Lex retrieval instead of only accepting
  it as quality evidence input.
- Durable fix path: Implemented
  `polisyos.lex.normpack.applicability_report` with
  `build_normative_applicability_report` and
  `normalize_normative_applicability_report`. The canary evidence assembler
  normalizes `quality_evidence/normative_evidence.json` before scorecard
  evaluation and includes issue codes in the operator-facing gate message. Next
  owning step: wire Lex retrieval/runtime to persist a
  `normative_applicability_report_ref` for real canary runs.
- Acceptance gates:
  - Done: Governed/production policy runs fail quality if no applicability report
    exists.
  - Done: Expired or superseded norms require explicit warning and cannot
    silently ground final recommendations.
  - Done: Every major recommendation has at least one applicable norm ref or an
    explicit rationale for why no normative anchor is required.
  - Done: Tests cover wrong jurisdiction, expired norm, missing authority
    metadata, and applicable norm success.
  - Partial: Real runtime still needs to emit and persist the applicability
    report ref from Lex retrieval.

## PRB-017 - Fabric Source Selection And Data Relevance Audit

- Status: Partially Resolved
- Severity: Critical
- Owning layer: Fabric retrieval/materialization, production data registry,
  runtime quality evidence
- Evidence: Canaries now have a Fabric source-selection trace contract and
  scorecard validation path. `fabric_retrieval_trace.json` is normalized before
  quality scoring, using the golden scenario's
  `admissible_data_source_families` as the expected source-family contract.
- Production impact: Policy conclusions can be grounded in technically valid
  but semantically weak or wrong data. Silent source misselection is more
  dangerous than a failed run.
- Root-cause hypothesis: Partially resolved. Fabric materialization provenance
  still needs to emit the trace automatically, but the operator-facing
  source-selection audit contract now exists and fails closed when evidence is
  incomplete or semantically wrong.
- Durable fix path: Implemented
  `polisyos.fabric.catalog.source_selection_audit` with
  `build_fabric_source_selection_trace` and `normalize_fabric_retrieval_trace`.
  The canary evidence assembler now normalizes `fabric_retrieval_trace` before
  scorecard evaluation and fails production/research/governed quality when
  selected sources are fixture/mock evidence, outside admissible source
  families, missing diagnostics, or when rejected sources lack reason codes.
  Next owning step: wire runtime Fabric retrieval/materialization to persist the
  trace from real source candidates and selections.
- Acceptance gates:
  - Partial: Every production/golden scenario can record selected and rejected
    data sources through the trace contract; runtime still needs automatic
    trace emission.
  - Done: Each selected source has freshness, coverage, schema compatibility, and
    relevance diagnostics.
  - Done: Each rejected source has a reason code.
  - Done: Fixture/mock fallback in research/governed/production produces
    `quality_status=fail`.

## PRB-018 - Foundry Method Validity And Diagnostics Gates

- Status: Partially Resolved
- Severity: Critical
- Owning layer: Foundry method catalog, Scientist method selection, workflow
  reports, quality scorecard
- Evidence: Canaries now have a Foundry method-quality report contract and
  scorecard validation path. `foundry_method_report.json` is normalized before
  quality scoring, using the golden scenario's `foundry_method_expectations` as
  the expected method-family contract.
- Production impact: A policy can be based on an inappropriate method or a point
  estimate without sufficient diagnostics. This creates false confidence in
  final recommendations.
- Root-cause hypothesis: Partially resolved. Method execution and method quality
  now have a separate validator, but the runtime pipeline still needs to emit
  the method-quality report automatically from real Foundry/Scientist workflow
  outputs.
- Durable fix path: Implemented
  `polisyos.foundry.validation.method_quality` with
  `build_foundry_method_report` and `normalize_foundry_method_report`. The
  canary evidence assembler now normalizes `foundry_method_report` before
  scorecard evaluation and fails production/research/governed quality when a
  method lacks input refs, assumptions, uncertainty, missingness diagnostics,
  sensitivity evidence, expected method-family match, or explicit degrade/fail
  behavior for insufficient data. Next owning step: wire Scientist/Foundry
  workflow reports to persist the method-quality report from real method
  executions.
- Acceptance gates:
  - Done: No production policy recommendation can be grounded only in a point
    estimate without uncertainty or diagnostics.
  - Done: Insufficient data causes explicit method degrade/fail status, not
    silent success.
  - Partial: Synthetic known-answer tests for representative methods remain a
    separate owning lane.
  - Done: Method assumptions are visible in quality evidence; workflow report
    emission still needs runtime wiring.

## PRB-019 - Policy Grounding Matrix And LLM Faithfulness Checks

- Status: Partially Resolved
- Severity: Critical
- Owning layer: Scientist final artifact generation, LLM agents, quality
  checker, CAS evidence
- Evidence: Current final policy artifacts can be generated after successful
  materialization and Foundry execution. The evidence bundle now recomputes a
  strict matrix that maps structured material policy claims to supporting Lex
  refs, Fabric data refs, and Foundry method outputs; remaining runtime work is
  to emit this matrix automatically from real final artifacts.
- Production impact: LLMs can produce fluent recommendations that are only
  loosely related to the verified evidence, invent unsupported metrics, soften
  uncertainty, or omit conflicts.
- Root-cause hypothesis: Final policy generation has evidence context, but lacks
  an automated faithfulness checker that decomposes final artifacts into claims
  and requires evidence refs for each material claim. The structured checker is
  now in place; free-text claim extraction and runtime matrix emission remain.
- Durable fix path: Implemented
  `polisyos.scientist.validation.policy_grounding` with
  `build_policy_grounding_matrix_report` and
  `normalize_policy_grounding_matrix`. The canary evidence assembler now
  normalizes `policy_grounding_matrix` after Lex/Fabric/Foundry reports and
  fails quality when raw `status=pass` contains unsupported recommendations,
  numeric claims that do not match Foundry outputs, or normative refs absent
  from applied Lex evidence. Next owning step: wire Scientist final artifact
  generation to persist structured claims and grounding refs automatically.
- Acceptance gates:
  - Done: Every major structured recommendation has data/method/norm grounding
    refs or a documented no-grounding rationale.
  - Done: Structured numerical claims match Foundry outputs within configured
    tolerance.
  - Done: Structured normative claims match Lex applicability evidence.
  - Done: Unsupported structured LLM claims produce `quality_status=fail` with
    claim text, missing evidence type, and next action.
  - Partial: Real final-artifact claim extraction and automatic matrix
    emission from Scientist/LLM agents remain to be wired.

## PRB-020 - Normative Conflict Detection And Policy Corpus Compatibility

- Status: Partially Resolved
- Severity: Critical
- Owning layer: Lex, governance rules, Scientist policy validation, quality
  scorecard
- Evidence: Current canaries do not yet require a conflict check showing whether
  the proposed policy conflicts with existing norms. The evidence bundle now
  normalizes `conflict_check.json` and refuses raw pass status when structured
  conflicts or corpus constraints identify a direct prohibition, eligibility
  mismatch, budget-rule mismatch, or equity/access conflict. Remaining runtime
  work is to emit the check automatically from the real Lex corpus and final
  policy claims.
- Production impact: A generated policy can be data-supported and norm-cited
  while still conflicting with the existing corpus. That is a production safety
  failure, not just a quality warning.
- Root-cause hypothesis: Norm retrieval and final policy generation are not yet
  followed by a mandatory corpus compatibility step that compares the proposed
  intervention against existing constraints. The structured report validator is
  now in place; automatic corpus extraction and runtime persistence remain.
- Durable fix path: Implemented `polisyos.lex.normpack.conflict_check` with
  `build_policy_conflict_check_report` and
  `normalize_policy_conflict_check_report`. The canary evidence assembler now
  normalizes `conflict_check` before scorecard evaluation, exposes conflict
  codes through `issues[]`, blocks direct/high-severity conflicts, and classifies
  medium/low indirect conflicts as warning quality. Next owning step: wire
  Lex/Scientist final policy generation to persist `policy_claims`,
  `corpus_constraints`, and detected conflicts from production norm corpus.
- Acceptance gates:
  - Done: Governed/production evidence bundles require `conflict_check.json`;
    missing conflict evidence fails quality.
  - Done: Direct structured conflicts block `quality_status=pass`.
  - Done: Indirect structured conflicts produce warnings or fails based on
    severity.
  - Done: Tests cover no-conflict, direct prohibition conflict, eligibility
    mismatch, budget-rule mismatch, and equity/access conflict.
  - Partial: Real production corpus compatibility extraction and persistence
    remain to be wired into runtime/Scientist workflows.

## PRB-021 - Quality Status And Operator Scorecard

- Status: Done
- Severity: High
- Owning layer: runtime API, control jobs, evidence bundle, dashboard
- Evidence: Jobs now expose additive top-level `execution_status`,
  `quality_status`, `quality_gates[]`, and `blocking_quality_failures[]` in
  `ControlJobResponse`. Completed jobs without quality evidence fail quality by
  default, and dashboard job status rendering shows quality failures separately
  from operational failure envelopes.
- Production impact: Operators may treat a completed job as a successful policy
  run even when evidence grounding, applicability, method validity, or conflict
  checks failed.
- Root-cause hypothesis: Runtime completion was designed as an operational
  status. Quality needs a separate state machine and scorecard that can pass,
  warn, or fail independently of job execution. The public API projection,
  compact dashboard rendering, and route-mocked dashboard journey are now in
  place; runtime persistence can continue through the per-layer quality gates
  without changing the operator contract.
- Durable fix path: Implemented additive quality fields in
  `ControlJobResponse`, derived from `progress.quality_scorecard`,
  `progress.quality`, or top-level progress quality fields. Missing quality
  evidence on completed jobs is converted into a blocking
  `quality_evidence_present` gate. Regenerated Runtime OpenAPI/dashboard types
  and runtime API client; updated dashboard control job status rendering to show
  quality status, primary gate, layer, next action, and evidence ref.
- Acceptance gates:
  - Done: Completed execution with missing quality evidence returns
    `quality_status=fail`.
  - Done: Dashboard and API show quality status separately from job state.
  - Done: Quality scorecard names each gate, status, owning layer, evidence
    ref, and next action.
  - Done: Existing execution-only clients remain backward compatible because
    the API change is additive.
  - Done: Full route-mocked dashboard journey covers a quality-failed completed
    production canary with no operational failure envelope.

## PRB-022 - Quality Failure Injection Suite

- Status: Done
- Severity: High
- Owning layer: quality tests, fixture builders, runtime control, dashboard/API
- Evidence: Canary evidence now has deterministic negative fixtures for expired
  norms, wrong Fabric source selection, Foundry point estimates without
  uncertainty, unsupported policy claims, direct normative conflicts, production
  data schema drift, and multi-model policy disagreement. Quality gates and
  blocking quality failures now carry stable `code`, `layer`, `phase`,
  `evidence_ref`, and `next_action` through the filesystem bundle, Runtime API,
  generated dashboard types, and compact dashboard status panel.
- Production impact: The most dangerous failures are plausible completed runs
  with bad evidence, wrong sources, bad methods, unsupported LLM claims, or
  unhandled normative conflicts.
- Root-cause hypothesis: Quality failure classes were not encoded as
  deterministic tests, so they relied on manual review after canary completion.
  The injection suite is now encoded at the evidence/scorecard layer and a
  route-level dashboard journey exercises a completed production canary with
  failed quality.
- Durable fix path: Added deterministic quality negative scenarios for expired
  norms, wrong Fabric source selection, Foundry missing uncertainty, unsupported
  policy claims, normative conflicts, production data schema drift, and
  multi-model policy disagreement. Fabric diagnostics now preserve explicit
  schema-drift issue codes, policy grounding detects materially different major
  recommendation actions across model variants, and quality failure envelopes
  preserve code/phase in API and dashboard rendering.
- Acceptance gates:
  - Done: Each negative scenario fails with a stable quality failure envelope.
  - Done: Failure envelope includes `code`, `layer`, `phase`, `evidence_ref`, and
    `next_action`.
  - Done: Dashboard/API can render quality failure envelopes.
  - Done: Positive golden scenarios still pass after negative fixtures are added.
  - Done: Add a dedicated route-mocked dashboard journey for a completed job
    with `quality_status=fail` and no operational failure.

## PRB-023 - Cross-Surface Canary Performance Budget Evidence

- Status: Open
- Severity: Medium
- Owning layer: control-plane jobs, CAS, runtime API, canary runners,
  dashboard e2e
- Evidence: PRB-004 now closes run-internal phase SLOs and operator visibility,
  but the production canary still does not produce one normalized budget report
  for control job queue/lease time, CAS put/get timing, run-index refresh/list,
  timeline/lineage build, and dashboard first meaningful route render.
- Production impact: A canary can prove NL phase budgets while still hiding
  slow control-plane scheduling, slow evidence collection, or frontend route
  regressions that affect production operator experience.
- Root-cause hypothesis: These timings already exist as performance tests or
  local measurements, but they are not gathered during each canary and compared
  to explicit production/staging budgets.
- Durable fix path: Add a `canary_performance_budget.json` companion report
  that merges control job timestamps, bundle collection timings, CAS round-trip
  samples, run-index/timeline/lineage API timings, and dashboard smoke route
  timings. Include the report in evidence bundles and fail only when a budget is
  marked production-blocking.
- Acceptance gates:
  - Queue wait and job lease/execution timings are measured per canary.
  - CAS put/get, run-index refresh/list, timeline, and lineage API timings are
    sampled during evidence collection.
  - Dashboard smoke emits first meaningful route render timing into the bundle.
  - Report has per-phase budget, observed duration, status, retryability, and
    owning layer.
  - Production canary can distinguish operational failure from performance
    budget warning/failure.

## Recommended Quality Track Order

1. PRB-014 - Production Policy Quality Evidence Bundle.
2. PRB-015 - Golden Quality Scenarios And Expected Evidence Contracts.
3. PRB-019 - Policy Grounding Matrix And LLM Faithfulness Checks.
4. PRB-016 - Lex Normative Applicability Quality Gates.
5. PRB-017 - Fabric Source Selection And Data Relevance Audit.
6. PRB-018 - Foundry Method Validity And Diagnostics Gates.
7. PRB-020 - Normative Conflict Detection And Policy Corpus Compatibility.
8. PRB-021 - Quality Status And Operator Scorecard.
9. PRB-022 - Quality Failure Injection Suite.
