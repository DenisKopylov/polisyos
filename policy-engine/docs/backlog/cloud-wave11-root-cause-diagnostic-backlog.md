# Cloud Wave 11 Root Cause Diagnostic Backlog

Status: active diagnostic backlog
Created: 2026-05-20
Run source: `policyos-prod-debug-20260520`, project `lex-1-494208`,
zone `europe-west1-b`

This document records the extra diagnostic pass after the 2026-05-20 cloud
Wave 11 live lane. The goal is to explain the new scorecard failures before
changing implementation code.

## Source Artifacts

- Matrix JSON:
  `_build/.tmp/production-quality/cloud_wave11/cloud_wave11_live_research_lane.json`
- Provider preflight:
  `_build/.tmp/production-quality/cloud_wave11/cloud_wave11_provider_preflight.json`
- Bundle inspection:
  `_build/.tmp/production-quality/cloud_wave11/cloud_wave11_evidence_bundle_inspection.json`
- Readiness:
  `_build/.tmp/production-quality/cloud_wave11/cloud_wave11_readiness.json`
- Local bundle mirror:
  `_build/.tmp/production-quality/cloud_wave11/bundle_full`
- GCS production-quality artifacts:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/`
- GCS evidence bundle:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_evidence/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T141708Z_b12144f479d34e03854f15ef81c7d5e6/`

## Checks Performed

### Artifact Pull

Pulled the cloud bundle's top-level JSON, quality evidence JSON, CAS manifest,
legacy migration sandbox, and curated production-data metadata from GCS.

```bash
gcloud storage cp \
  'gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_evidence/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T141708Z_b12144f479d34e03854f15ef81c7d5e6/quality_evidence/*.json' \
  _build/.tmp/production-quality/cloud_wave11/bundle_quality_evidence/

gcloud storage cp \
  'gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/curated/source_bindings.json' \
  _build/.tmp/production-quality/cloud_wave11/production_data_metadata/source_bindings.json

gcloud storage cp \
  'gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/curated/data_contracts.json' \
  _build/.tmp/production-quality/cloud_wave11/production_data_metadata/data_contracts.json
```

### Replay And Bundle Inspection

```bash
uv run python tools/ops_runners/runtime/replay_canary_bundle.py \
  --bundle _build/.tmp/production-quality/cloud_wave11/bundle_full \
  --json-output _build/.tmp/production-quality/cloud_wave11/replay_cloud_wave11_bundle.json

uv run python tools/quality/validation/inspect_evidence_bundles.py \
  --repo-root . \
  --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full \
  --json-output _build/.tmp/production-quality/cloud_wave11/inspect_cloud_wave11_bundle_direct.json
```

Result:

- Replay status: `match`.
- Replay production readiness: `pass`.
- Direct bundle inspection status: `fail` only because the bundle scorecard and
  bundle quality status are not passing.
- After the CAS manifest was pulled, the direct inspector no longer reported
  missing bundle components.

Interpretation: the bundle is replayable and structurally inspectable. The
remaining failure is the actual runtime scorecard, not artifact corruption.

## Scorecard Shape

Cloud live lane:

- selected: 1
- executed: 1
- passed: 0
- failed: 1
- blocked: 0
- skipped: 0
- failure envelope: `canary_scorecard_failed`
- quality status: `fail`
- approval state: `quality_failed`
- overall score: `0.297083`

Failed gate count:

- failed gates: 181
- total gates: 215

Top failed gate codes:

| Count | Code |
| ---: | --- |
| 45 | `semantic_fabric_source_facet_incomplete` |
| 38 | `policy_design_case_record_family_missing` |
| 15 | `semantic_fabric_derived_feature_binding_missing` |
| 6 each | `semantic_major_claim_scenario_requirement_refs_missing`, `semantic_major_claim_canonical_concept_refs_missing`, `semantic_major_claim_column_refs_missing`, `semantic_major_claim_argument_refs_missing`, `semantic_major_claim_warrant_refs_missing`, `semantic_major_claim_rebuttal_refs_missing`, `semantic_major_claim_counter_evidence_refs_missing`, `semantic_major_claim_limitation_refs_missing` |
| 2 each | `data_dictionary_missing`, `missing_recommendation_normative_anchor`, `selected_source_family_not_admissible`, `method_family_not_expected`, `major_claim_missing_grounding`, `major_recommendation_missing_required_section`, `policy_design_case_record_families_missing`, `policy_design_case_records_missing` |

Operator triage compressed the failures to 19 root-cause groups. The largest
collapse is semantic binding: 108 downstream failures under one semantic
closure root.

## Negative Controls

These are not the current root blockers:

- Provider credentials: provider preflight passed in cloud.
- Missing full production-data directory: cloud run used the 34G data directory
  with 6562 files.
- Bundle corruption: replay matched and bundle inspection sees required
  evidence surfaces.
- Public export authority minting: inspector preserves the failed scorecard and
  public export does not promote authority.
- Lex zero-retrieval: Lex returned 33 candidate norms and selected 33 global
  norms.

## Root Cause Finding 1 - Scenario Data Families Are Absent From Curated Contracts

Severity: critical
Owner candidate: Fabric / production-data contract index

Evidence:

- Scenario requires three data families:
  - `production_msme_panel`
  - `credit_program_registry`
  - `regional_displacement_indicators`
- Fabric selected only broad production-data families:
  - `academic`
  - `curated`
  - `datasets`
  - `lex`
  - `ukraine_simulation`
- Every scenario binding finding is blocked with
  `scenario_source_family_absent`.
- Every required scenario family has `candidate_ref=null`.
- Rejected candidate families are the same broad bundles, not scenario
  contracts.
- Curated metadata was present and checksumed, but it contains no scenario
  families:
  - `source_bindings.json`: 3 bindings, 0 occurrences of
    `production_msme_panel`, `credit_program_registry`,
    `regional_displacement_indicators`, `msme`, `credit`, or `displacement`.
  - `data_contracts.json`: 3 contracts, 0 occurrences of the same scenario
    terms.
- Current curated bindings are generic:
  - `us.macro.gdp_nominal`
  - `us.macro.unemployment_rate`
  - `agent.income.salary`

Working hypothesis:

The live lane has enough files, but not the scenario-admissible production-data
contract metadata. This is why Fabric cannot bind to scenario source families
even though the production-data manifest is present and the curated metadata
files exist.

Next diagnostic:

- Build a small contract-index report directly from the cloud
  `source_bindings.json` and `data_contracts.json` and assert the three
  scenario families are absent before the runtime source selector runs.
- Decide whether the fix belongs in data packaging, Data Forge export, or
  runtime contract-index mapping.

## Root Cause Finding 2 - Data Quality Is File-Available But Not Claim-Admissible

Severity: critical
Owner candidate: Data Forge / Fabric / runtime quality

Evidence:

- Entity counts:
  - `academic`: 10000
  - `datasets`: 10000
  - `lex`: 10000
  - `curated`: 0
  - `ukraine_simulation`: 0
- Data quality failures include:
  - `data_dictionary_missing`
  - `construct_validity_metric_missing`
  - `production_data_quality_missing`
  - `production_data_missingness_high`
  - `recency_timestamp_missing`
  - `production_data_outlier_ratio_high`
- All three major claims have `data_refs=[]`.
- All three claim diagnostics fail on construct-validity coverage.

Working hypothesis:

The data plane currently proves bundle presence, not policy-admissible evidence.
The live lane needs scenario-family contracts with dictionaries, schema refs,
field refs, units, geography/time coverage, quality, missingness, freshness,
lineage, transformation refs, and derived-feature bindings.

Next diagnostic:

- Inspect whether any source outside the curated metadata has the missing
  scenario semantics, or whether the production-data build never produced them.
- Add a local static check that fails when curated contracts do not mention the
  scenario families required by `scenario-public_golden`.

## Root Cause Finding 3 - Lex Retrieval Works, But Recommendation Anchoring Does Not

Severity: high
Owner candidate: Lex / policy semantics

Evidence:

- `normalized_query_terms` include Ukrainian legal terms such as
  `підприємство`, `кредит`, `грант`, and `воєнний стан`.
- Lex returned:
  - `candidate_norm_count=33`
  - `applied_norm_count=33`
  - `rejected_norm_count=0`
- Global `selected_norm_refs` contains 33 refs.
- Per-recommendation coverage still fails:
  - `rec_adaptive_tax_relief_for_wartime_msmes`: `selected_norm_refs=[]`
  - `rec_emergency_wage_subsidy_program`: `selected_norm_refs=[]`
  - `rec_real_time_msme_monitoring_dashboard`: `selected_norm_refs=[]`
- All three fail with `missing_recommendation_normative_anchor`.

Working hypothesis:

Wave 4 fixed retrieval reachability but not the claim-to-norm join. The runtime
can retrieve Ukrainian norms globally, yet cannot select or reject norms for
specific recommendations and legal requirement families.

Next diagnostic:

- For each major recommendation, score candidate norms against the legal
  requirement facets: competence, temporal validity, policy instrument,
  beneficiary class, fiscal authority, and implementation agency.
- Emit selected and rejected norm refs per recommendation, not only global
  selected refs.

## Root Cause Finding 4 - Foundry Still Selects Generic Simulation

Severity: high
Owner candidate: Foundry / workflow builder

Evidence:

- Scenario expected method families:
  - `causal_effect_estimation`
  - `heterogeneity_by_region_or_firm_size`
  - `uncertainty_interval`
  - `sensitivity_or_transportability_diagnostic`
- Candidate method families: `simulation`
- Selected method: `foundry.execute`
- `method_obligations=[]`
- Missing method facets:
  - assumptions
  - uncertainty
  - sensitivity
  - missingness diagnostics
  - analytical proof surface
- Validity surface `certificate_proof` is required but missing.

Working hypothesis:

The live workflow still routes through the generic execution surface instead of
pinning a scenario method plan before claim drafting. The method report is now
correctly failing instead of false-passing.

Next diagnostic:

- Trace where the scenario method obligations disappear between
  `golden_scenario_contract.json`, workflow builder, and
  `foundry_method_report.json`.
- Verify whether the builder requests method obligations before final claim
  drafting in the live lane, not only in unit fixtures.

## Root Cause Finding 5 - Final Claims Are Not Compiled From The Evidence Graph

Severity: critical
Owner candidate: Scientist / decision artifact compiler

Evidence:

- Policy grounding matrix has 3 claims and 3 major claims.
- Summary sees global evidence availability:
  - `applied_norm_ref_count=33`
  - `selected_data_ref_count=10`
  - `selected_method_ref_count=1`
- Each major claim still has empty refs:
  - `data_refs=[]`
  - `method_refs=[]`
  - `norm_refs=[]`
  - `portfolio_refs=[]`
  - `argument_refs=[]`
  - `warrant_refs=[]`
  - `rebuttal_or_counter_evidence_refs=[]`
  - `limitation_refs=[]`
- Decision artifact has 130 issues.
- Each major recommendation misses all 11 required public sections:
  - `support_summary`
  - `uncertainty`
  - `policy_tradeoffs`
  - `distributional_impact`
  - `implementation_feasibility`
  - `budget_implication`
  - `stakeholder_impact`
  - `implementation_risks`
  - `residual_uncertainty`
  - `monitoring_plan`
  - `withdrawal_reissue_triggers`

Working hypothesis:

The final policy output is still primarily generated as recommendations, while
evidence refs are reported beside it rather than compiled into each major
recommendation. Downstream quality reports correctly detect this, but the claim
compiler does not yet make evidence graph closure a generation input.

Next diagnostic:

- Compare the final policy claim IDs with scenario claim requirement IDs and
  record whether the mapping is missing, lossy, or intentionally adversarial.
- Trace whether `policy_grounding_matrix` consumes Fabric/Lex/Foundry outputs
  before or after final recommendations are produced.

## Root Cause Finding 6 - Semantic Ledger Top-Level Status Is Too Weak

Severity: high
Owner candidate: runtime quality / semantic binding

Evidence:

- `semantic_binding_ledger.json` top-level `status=pass`.
- `runtime_report_status=null`.
- Scorecard still emits 108 semantic binding failures.
- Fabric semantic entry has:
  - `canonical_concept_refs=[]`
  - 15 column bindings with empty `column_refs`
  - unbound candidate spine refs
- Claim evidence paths for all three major claims miss:
  - `scenario_requirement_refs`
  - `canonical_concept_refs`
  - `column_refs`
  - `argument_refs`
  - `warrant_refs`
  - `rebuttal_refs`
  - `counter_evidence_refs`
  - `limitation_refs`

Working hypothesis:

The semantic ledger producer still treats "ledger exists and parses" as pass,
while the scorecard performs stricter closure checks later. This leaves a
truth-preservation gap between producer status and reader status.

Next diagnostic:

- Move the same closure evaluator used by scorecard into the semantic ledger
  producer path, or make top-level status explicitly `blocked` when the ledger
  is structurally readable but closure-incomplete.

## Root Cause Finding 7 - Policy Design Case Live Path Is Profile-Only

Severity: high
Owner candidate: runtime quality / Policy Design Case compiler

Evidence:

- `policy_design_case.json` top-level `status=pass`.
- `records` is absent.
- `record_families` is absent.
- Scorecard emits 50 PDC failures:
  - 38 `policy_design_case_record_family_missing`
  - 2 `policy_design_case_record_families_missing`
  - 2 `policy_design_case_records_missing`
  - missing substrate residual verification, self-FMEA, partial-state
    consistency, maturity profile, dormant capability inventory,
    skip-causality ledger, freshness/policy-time semantics, and Pass 1B
    hardening records.

Working hypothesis:

The cloud live path is still emitting the older profile/case skeleton. The
record-family compiler exists in tests/static tooling but is not wired into the
runtime evidence bundle for the live lane.

Next diagnostic:

- Trace the runtime producer that emits `policy_design_case_ref` and confirm
  whether it ever calls the minimum record-family registry/compiler.
- Add a live-bundle fixture where `status=pass` with no records must fail at
  producer time, not only scorecard time.

## Root Cause Finding 8 - Continuous Governance Reports Reuse The Wrong Authority Envelope

Severity: medium-high
Owner candidate: runtime quality / lifecycle governance

Evidence:

- Each continuous governance report top-level `status=pass`.
- Each report says `decision_status=no_published_decision_mutation_required`.
- Each report's `authority_envelope.validation_status=fail`.
- Each report's authority envelope says:
  - `artifact_kind=runtime.production_data_quality_report`
  - `schema_name=polisyos.runtime.ProductionDataQualityReport`
  - `phase=production_data_quality`
- Scorecard emits:
  - `continuous_governance_stale_validation_failed`
  - `continuous_governance_reissue_validation_failed`
  - `continuous_governance_supersede_validation_failed`
  - `continuous_governance_withdraw_validation_failed`

Working hypothesis:

The lifecycle reports are probably using a copied production-data quality
authority envelope helper or inherited validation status. This causes a
pass/fail contradiction: report semantics say no mutation is required, while
producer authority says the artifact failed domain validation.

Next diagnostic:

- Check the producer for the four continuous governance reports and verify the
  authority envelope fields are report-specific.
- Decide whether `no_published_decision_mutation_required` should produce
  `validation_status=pass` or a typed `not_applicable` status.

## Root Cause Finding 9 - Provider Quality Demotion Is Confounded By Evidence Closure Failure

Severity: medium
Owner candidate: provider quality / scorecard policy

Evidence:

- Provider preflight passed.
- `provider_model_quality_ledger.json` top-level `status=pass`, but its
  summary status is `fail`.
- Entry metrics:
  - `sample_count=1`
  - `quarantined_live_sample_count=1`
  - `grounding_failure_rate=1.0`
  - `schema_failure_rate=0.0`
  - `provider_error_rate=0.0`
  - `latency_ms_avg=143458.0`
  - action: `demote`
- The sample is from `runtime_nl_pipeline`, which is already known to lack
  Fabric, Lex, Foundry, and claim grounding closure.

Working hypothesis:

The model demotion is probably true as a live-lane observation but not yet a
fair default-model decision. It is based on one quarantined live sample whose
grounding failure is confounded by missing evidence binding upstream.

Next diagnostic:

- Require the controlled evidence-bound provider task from Wave 10 before any
  default model promotion or demotion.
- Keep live-lane provider observations quarantined until the evidence graph is
  complete enough to isolate model quality from upstream binding failures.

## Root Cause Finding 10 - Prompt/Tool Ledger Fails On Final Evaluator Validation

Severity: medium
Owner candidate: runtime ops / prompt-tool authority

Evidence:

- Prompt/tool ledger summary:
  - `status=fail`
  - `step_count=10`
  - `tool_count=0`
  - `authority_scopes=["approval", "claims", "evidence", "scorecard"]`
- Nine steps have passing validation refs.
- The failing step is:
  `qwen_qwen3_235b_a22b_instruct_2507_fp8_1:evaluator:score_iteration:10`.
- The failed validator is `evaluator.score_iteration.status`.
- All tool allowlists and tool call refs are empty.

Working hypothesis:

The ledger is correctly catching that the final evaluator step failed, but it
does not expose a human-readable failure reason beyond the validation ref. Tool
count zero may also mean serious evidence handoffs are occurring without a
tool-authority surface.

Next diagnostic:

- Resolve `sha256:451fe5ef2d617ee18e4bc470aa49e8be9b0eec9d3a958d4e79ff3273e79e9e98`
  in the run CAS and attach the evaluator failure reason to the ledger.
- Decide whether no-tool serious runs are allowed, blocked, or explicitly
  marked not-applicable.

## Root Cause Finding 11 - Formalizer Fallback Indicates Schema Prompt Mismatch

Severity: medium
Owner candidate: Scientist formalizer / Trinity schema

Evidence from matrix failure envelope stderr:

```text
FormalizerFallback: 1 validation error for TrinityBundle
model_spec.assumptions.0.assumption_type
Input should be 'behavioral', 'structural', 'parametric', 'distributional',
'temporal' or 'boundary' [input_value='data']
```

Working hypothesis:

The LLM/formalizer generated `assumption_type="data"`, but the Trinity schema
enum does not allow it. The runtime fell back deterministically. This may be a
secondary source of generic or incomplete method/evidence structure.

Next diagnostic:

- Add a provider-output sanitizer or schema-aware prompt constraint that maps
  data assumptions into one of the allowed enum values, or add a typed enum
  value only if the domain model truly needs it.
- Check whether the fallback bundle is what removed claim/evidence detail.

## Root Cause Finding 12 - Control Plane Progress Update Timed Out Once

Severity: low-medium
Owner candidate: runtime control plane

Evidence from matrix failure envelope stderr:

```text
Failed to update NL progress for job ... phase scientist_workflow_running:
control_plane_store timed out
```

Working hypothesis:

This did not block bundle creation or scorecard evaluation, but it is a real
durability/resilience signal. It may become important under heavier cloud runs.

Next diagnostic:

- Query control-plane progress/outbox rows for the cloud job if the VM is
  restarted.
- Add a bounded cloud Postgres resource profile around progress updates during
  the live lane.

## Root Cause Graph

Current best root-cause ordering:

1. Scenario data families are absent from production-data contract metadata.
2. Fabric therefore cannot select claim-admissible source bindings.
3. Data quality can only report broad bundle availability and generic quality
   problems, not scenario-bound limitations.
4. Foundry receives generic inputs and selects `foundry.execute`.
5. Lex retrieves norms globally but cannot anchor them to recommendations.
6. Scientist recommendations are emitted without per-claim data, method, norm,
   argument, warrant, counter-evidence, and limitation refs.
7. Semantic binding and Policy Design Case artifacts are readable, but their
   top-level statuses do not reflect closure failures.
8. Public export and readiness correctly preserve the failure instead of
   minting authority.

## Implementation Vs Wiring Diagnosis

Question: are the failures caused by missing best-in-class logic, or by
existing modules not being connected to the live lane?

Short answer: this is mostly not an empty-code problem. The repository already
contains substantial contract, validator, and scorecard logic for the Wave 1-11
architecture. The cloud failures are primarily at the producer/wiring/data
contract boundary: the live lane either feeds the modules broad bundle metadata
instead of scenario-admissible contracts, loses scenario context before specific
producers consume it, or emits older profile-only artifacts whose reader gates
are already stricter.

| Area | Diagnosis | Evidence |
| --- | --- | --- |
| Scenario data/Fabric | Existing logic is connected, but data contracts are not scenario-admissible. | `ProductionDataContractIndex` loads `manifest.json`, curated `data_contracts.json`, and `source_bindings.json`, then binds by exact `expected_family`. Fabric consumes that report and emits `source_family_mismatch`. The local/cloud curated metadata has only 3 generic metric contracts and no `production_msme_panel`, `credit_program_registry`, or `regional_displacement_indicators`. |
| Data quality | Existing checks are real, but they can only score broad bundles because the scenario source bindings are absent. | The quality report flags dictionary, construct-validity, recency, missingness, and outlier problems. No selected data candidate becomes claim-bound evidence. |
| Lex | Retrieval logic exists; per-claim legal anchoring is under-connected. | Query normalization expands to Ukrainian terms and Lex selects 33 norms globally, but `_recommendation_coverage` only passes when final claims already carry applicable norm refs or an explicit no-anchor rationale. The live recommendations have none. |
| Scenario contract propagation | Mixed wiring gap. | `request.sanitized.json` contains `context.scenario_evidence_contract` with 18 requirements, but `normative_evidence.legal_requirements=[]` and the top-level Fabric trace has `scenario_evidence_contract_id=null` while its nested contract report has the id. This points to inconsistent context propagation across producers. |
| Foundry | Validation logic exists; live method selection is still generic and selected-method filtering is incomplete on the normalized path. | Method-quality code knows generic `foundry.execute` is not admissible for serious expectations, but the live report still has `selected_method_count=1`, selected `foundry.execute`, `rejected_method_count=0`, and `method_obligations=[]`. |
| Policy grounding / decision artifact | Validators exist; the final claim compiler is not evidence-graph-first. | `policy_grounding_matrix` can see global evidence counts, but every major claim has empty `data_refs`, `method_refs`, `norm_refs`, portfolio, argument, warrant, rebuttal/counter-evidence, and limitation refs. |
| Semantic binding | Closure evaluator exists; producer status is too weak. | `semantic_binding_ledger.json` parses and says `status=pass`, but the scorecard's semantic evaluator emits 108 closure failures from the same ledger. |
| Policy Design Case | Registry and coverage validators exist; runtime producer emits an older profile-only case. | `build_policy_design_case_profile` emits profile fields and the live path then forces `status=pass`; the artifact has no `records` or `record_families`, while the record-family coverage validator and scorecard correctly fail it. |
| Continuous governance | Definite wiring/metadata bug. | The no-op lifecycle reports reuse an authority envelope shaped like `runtime.production_data_quality_report` with production-data schema/phase, so report semantics and authority metadata contradict each other. |
| Provider quality | Logic exists, but the demotion decision is confounded by upstream evidence closure failure. | The provider preflight passed. The model ledger demotes on one quarantined live sample with grounding failures from a lane already missing Fabric/Lex/Foundry/claim closure. |

Architectural implication: the next fix should not be a superficial scorecard
threshold change. The best-in-class improvement is to make the scenario evidence
contract the single runtime spine for Data/Fabric, Lex, Foundry, claim
compilation, Semantic Binding, and Policy Design Case records. Producers should
emit typed blockers when their contract slice is unavailable; they should not
emit `pass` on profile-only or globally-selected evidence.

## Deep-Dive Pass 2 - First Broken Boundary By Subsystem

This pass traced the same cloud bundle from request context through producers
and reader gates. The goal was to classify every major failure as one of:
missing production data, disconnected existing module, incomplete domain logic,
or metadata/authority bug.

### Scenario Contract Propagation

Observed evidence:

- `request.sanitized.json#/context/scenario_evidence_contract` is present and
  has 18 requirements.
- `quality_evidence/golden_scenario_contract.json#/scenario_evidence_contract`
  is present.
- Fabric's nested
  `production_data_contract_binding_report.scenario_contract_id` is
  `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1`.
- Fabric's top-level `scenario_evidence_contract_id` is `null`.
- Lex's `query_normalization_report.legal_requirements` has 4 legal
  requirements, but top-level `normative_evidence.legal_requirements` is empty.
- Job/run progress surfaces do not retain the scenario contract as a first-class
  runtime ref.

Diagnosis:

The scenario contract is not absent; it is partially propagated. It reaches the
request, golden scenario artifact, Fabric's nested contract-index binding, and
Lex query normalization. It is then lost or inconsistently projected at producer
normalization/report boundaries. This is a wiring and persistence contract
problem, not a missing concept.

Best-in-class fix shape:

- Treat the scenario contract as a required runtime artifact/ref, not just
  request context.
- Require every producer report that consumes it to carry
  `scenario_evidence_contract_id`, the relevant requirement ids, and selected or
  blocked requirement-level bindings.
- Fail producer normalization if it drops requirement ids while preserving
  derivative fields.

### Data And Fabric Boundary

First broken boundary:

`production_data` curated metadata cannot express the Ukrainian MSME scenario
families. `production_data/manifest.json` has 5 broad bundles, while curated
`source_bindings.json` and `data_contracts.json` have only 3 generic metric
rows:

- `us.macro.gdp_nominal`
- `us.macro.unemployment_rate`
- `agent.income.salary`

There are no curated hits for:

- `production_msme_panel`
- `credit_program_registry`
- `regional_displacement_indicators`

The contract-index logic itself is present. `ProductionDataContractIndex.load`
loads `manifest.json`, `curated/data_contracts.json`, and
`curated/source_bindings.json`; `bind_requirement` performs an exact
`expected_family` match and emits `scenario_source_family_absent` when no
candidate exists. Fabric then projects those findings into
`source_family_mismatch` blockers.

Classification:

- Root type: missing production data contract metadata.
- Existing module state: contract index and Fabric source-family gate are
  already connected enough to fail correctly.
- Not enough to fix: selecting the broad `datasets` bundle or weakening Fabric
  matching.

Required repair:

Add scenario-admissible curated source contracts with field dictionary, schema,
field refs, units, geography/time coverage, freshness, lineage, transformations,
quality, missingness, outlier, construct-validity, and claim-bindability refs.
Only then should Fabric select them. Until then, Fabric should continue to block.

### Lex Boundary

First broken boundary:

Lex retrieval is no longer a zero-candidate problem. The live report has 33
`candidate_norm_refs` and 33 `selected_norm_refs`, and query normalization
expands to Ukrainian terms such as `підприємство`, `кредит`, `грант`, and
wartime variants. But each major recommendation still has:

- `status=fail`
- `reason_code=missing_normative_anchor`
- empty `norm_refs`
- empty `selected_norm_refs`
- empty `rejected_norm_refs`

Additional split-brain:

- Nested query normalization has 4 legal requirements.
- Top-level normative report has 0 legal requirements.
- `normalize_normative_applicability_report` rebuilds from
  `report["scenario_evidence_contract"]`; the persisted live report does not
  carry that field, so top-level legal requirements are dropped even though
  query normalization saw them.

Classification:

- Root type 1: report-normalization wiring bug.
- Root type 2: incomplete per-recommendation legal anchoring logic.
- Existing module state: bilingual query expansion and candidate retrieval are
  developed; per-claim selected/rejected norm attribution is not yet a real
  scenario-aware selector.

Required repair:

Persist the scenario contract or legal-requirement projection into the
normative report before normalization. Then implement per-recommendation
candidate scoring/rejection against competence, temporal validity, instrument,
beneficiary class, fiscal authority, and implementation agency facets. A global
selected norm list must not satisfy a recommendation anchor by itself.

### Foundry Boundary

First broken boundary:

The live method report has the right serious expectations:

- `causal_effect_estimation`
- `heterogeneity_by_region_or_firm_size`
- `sensitivity_or_transportability_diagnostic`
- `uncertainty_interval`

But it still reports one selected method, `foundry.execute`, with zero rejected
methods and zero method obligations. The report correctly emits issues such as
`method_family_not_expected`, `generic_simulation_false_pass`,
`method_assumptions_missing`, `method_uncertainty_missing`,
`method_missingness_diagnostics_missing`, and `method_sensitivity_missing`.

Classification:

- Root type 1: selection-state normalization gap.
- Root type 2: scenario method obligations are incomplete for the actual
  serious method families.
- Existing module state: validator logic knows generic `foundry.execute` is not
  admissible; live normalization does not demote it into rejected candidates, and
  the obligation map does not cover the scenario expectations.

Required repair:

Normalize selected/rejected methods after applying serious expectations, so
`foundry.execute` cannot remain selected when it fails the scenario method
contract. Expand method obligations beyond distributional and implementation
feasibility to include causal, heterogeneity, uncertainty, and sensitivity
families before Scientist claim drafting.

### Claim Compiler And Decision Artifact Boundary

First broken boundary:

Final recommendations are extracted, but they are not minted through a runtime
claim registry before policy grounding and publishable decision compilation.
`policy_grounding_matrix.json` shows all 3 major recommendations with empty
`data_refs`, `method_refs`, and `norm_refs`. The decision artifact quality gate
then correctly fails with:

- `claim_compiler_runtime_registry_missing`
- `claim_statement_missing_evidence_or_blocker`
- `decision_artifact_claim_evidence_contract_blocked`
- `decision_artifact_public_section_unbound`
- required public section failures such as `support_summary`

The publishable compiler already has strict logic. It requires a claim registry,
runtime authority, producer refs, portfolio refs, independence refs,
specification curves, disconfirming refs, synthesis refs, tradeoff refs,
uncertainty refs, numerical semantics refs, and monitoring refs.

Classification:

- Root type: existing compiler is not connected early enough in the live
  workflow.
- Existing module state: fail-closed decision artifact and claim-contract logic
  exist; runtime does not yet create the producer-owned claim registry that
  should feed them.

Required repair:

Introduce a runtime claim registry stage after Fabric/Lex/Foundry/Scientist
evidence is available and before policy grounding/public artifact compilation.
The registry should either select all required producer refs for a major claim
or emit typed blockers/accepted deficits that downstream reports can project.

### Semantic Binding Boundary

First broken boundary:

The semantic binding ledger is structurally readable but its producer status is
too weak. Top-level `semantic_binding_ledger.json` reports `status=pass`, while
the scorecard emits closure failures for the same artifact:

- 45 `semantic_fabric_source_facet_incomplete`
- 15 `semantic_fabric_derived_feature_binding_missing`
- 6 each for missing scenario requirement refs, canonical concept refs, column
  refs, argument refs, warrant refs, rebuttal refs, counter-evidence refs, and
  limitation refs.

The missing claim evidence paths are visible under
`final_compiler[0].claim_evidence_paths`; they contain selected broad source
refs, 33 global norm refs, and `foundry.execute`, but no scenario requirement,
canonical concept, column, argument, warrant, rebuttal/counter-evidence, or
limitation refs.

Classification:

- Root type: producer status aggregation gap.
- Existing module state: strict closure evaluator exists and the scorecard uses
  it; the producer does not set `status=failed/blocked` from that evaluator.

Required repair:

Make the semantic ledger builder run the same closure evaluation that the
scorecard uses, and write `runtime_report_status` plus issue summaries into the
ledger. A readable ledger with closure-incomplete major claims must not be
top-level `pass`.

### Policy Design Case Boundary

First broken boundary:

`policy_design_case.json` is an older assurance profile, not a minimum
record-family case. It has:

- `status=pass`
- no `records`
- no `record_families`
- no `summary`
- profile fields such as `case_registry_entry`, `capability_ledger`,
  `intent_envelope`, `jurisdiction_spine`, and `nodes`

The runtime path builds this via `build_policy_design_case_profile` and then
forces `profile_payload["status"] = "pass"`. The stricter PDC registry,
coverage, maturity, and Pass 1B validators already exist separately and the
scorecard correctly reports missing family failures.

Classification:

- Root type: missing runtime PDC record-family compiler/integration.
- Existing module state: registry and validators exist; live producer still
  emits a profile-only artifact.

Required repair:

Replace or enrich the profile producer with a record-family compiler that emits
every minimum family as present, blocked, or out of scope by typed authority
policy. The compiler must attach schema owner, producer owner, reader owner,
readiness gate, runtime refs, authority envelope, and maturity/pass1b bindings.
Never force `status=pass` after building a profile-only case.

### Continuous Governance Boundary

First broken boundary:

No-op lifecycle reports (`stale`, `reissue`, `supersede`, `withdraw`) have
`status=pass` and `decision_status=no_published_decision_mutation_required`, but
their authority envelopes are copied from `runtime.production_data_quality_report`
with:

- `schema_name=polisyos.runtime.ProductionDataQualityReport`
- `phase=production_data_quality`
- `validation_status=fail`
- `artifact_kind=runtime.production_data_quality_report`

The closeout code constructs continuous governance reports from a generic
authority record. `_authority_record_for_ref` falls back to
`base_authority_envelope` when a report has no own envelope, and
`_continuous_governance_report` copies that authority record verbatim. That
makes lifecycle semantics and authority metadata contradict each other.

Classification:

- Root type: metadata/authority envelope construction bug.
- Existing module state: lifecycle reports exist, but their envelopes are not
  report-specific.

Required repair:

Mint lifecycle-specific authority envelopes and schemas for continuous
governance reports. A no-op lifecycle report can pass only with its own
`artifact_kind`, `schema_name`, `phase`, `validation_status`, and runtime event,
not with borrowed production-data metadata.

### Provider Quality Boundary

First broken boundary:

Provider preflight passed, but the model quality ledger demotes on a quarantined
live sample whose grounding failure is caused by upstream evidence closure. This
is a confounded model-quality signal, not a clean provider failure.

Classification:

- Root type: evaluation policy/gating issue.
- Existing module state: controlled provider-quality task exists; default
  promotion/demotion should rely on controlled evidence-bound samples until the
  live evidence graph closes.

Required repair:

Separate provider health, controlled evidence-bound model quality, and live-lane
system quality. Live-lane failures caused by Fabric/Lex/Foundry/PDC closure
should be attached as system blockers, not used as default-model demotion
evidence.

### Consolidated Root-Cause Classification

| Subsystem | First broken boundary | Classification | Fix priority |
| --- | --- | --- | --- |
| Production data | Curated metadata lacks scenario source families and facets. | Missing data contract metadata. | P0 |
| Fabric | Correctly blocks broad source families; top trace drops contract id. | Mostly working module plus trace metadata gap. | P0 |
| Lex | Query normalization sees legal requirements; normalized report drops them; recommendation anchors remain empty. | Wiring bug plus incomplete per-claim anchoring. | P0 |
| Foundry | Generic `foundry.execute` remains selected despite serious method failures; obligations are incomplete. | Selection normalization plus incomplete obligation model. | P0 |
| Claims | No runtime claim registry feeds grounding/compiler. | Existing compiler not connected early enough. | P0 |
| Semantic binding | Reader detects closure failures; producer status still says pass. | Producer status aggregation gap. | P0 |
| Policy Design Case | Runtime emits profile-only case, no record families. | Missing runtime record-family compiler/integration. | P0 |
| Continuous governance | Lifecycle reports borrow production-data failure envelope. | Authority metadata construction bug. | P1 |
| Provider quality | Demotion uses confounded live evidence failure. | Evaluation policy/gating issue. | P1 |

Deep diagnosis conclusion:

The new cloud problems are not mostly caused by an absence of developed logic in
the repository. The best-in-class contracts and readers are substantially
present. The live production path is still earlier-generation: it selects broad
bundles, global norms, generic methods, and profile-only PDC artifacts, while
newer readers expect scenario-bound producer evidence. The repair should
therefore focus on runtime producer compilation and contract propagation, not on
weakening scorecards or adding post-hoc narrative explanations.

### Regression Coverage Implications

Existing tests already prove many pieces in isolation:

- `test_nl_pipeline_materialization.py` has a synthetic production-data fixture
  where `production_msme_panel` is present with full contract facets; that path
  satisfies `selected_contract_binding` and carries the scenario contract id.
- `test_source_selection_audit.py` checks that broad source families cannot
  satisfy `production_msme_panel`, and that a fully-faceted contract candidate
  can pass.
- `test_production_data_contract_index.py` checks source-family mapping,
  missing dictionary/schema/lineage facets, and quality facets such as recency,
  construct validity, missingness, and outliers.
- `test_normative_applicability_report.py` checks that major recommendations
  require a normative anchor or explicit rationale, but the live path still has
  no auto-anchor from globally selected candidate norms.
- `test_method_quality.py` proves generic `foundry.execute` is rejected when
  the report is built from execution outputs, but the live normalized report
  still preserves it as selected because it enters the report through the
  selected-method path.
- `test_canary_matrix.py` has a deterministic scenario helper where
  `policy_design_case.claim_registry` exists and selects producer refs, but the
  cloud live path did not produce that claim registry.
- `test_policy_design_case_record_registry.py`, `test_case_maturity.py`, and
  `test_policy_design_case_pass1b_hardening.py` already reject profile-only
  PDC cases with no `records` or `record_families`.
- `test_canary_evidence_authority.py` protects against bundle/generated refs
  minting runtime authority, but the continuous-governance envelope bug is more
  specific: it borrows a real but wrong production-data envelope.

Coverage gaps to add before repair:

1. A cloud-metadata fixture proving current `production_data` curated contracts
   lack the three scenario source families and therefore must block before
   Fabric selection.
2. A Lex normalization regression where a persisted report has
   `query_normalization_report.legal_requirements` but no top-level
   `scenario_evidence_contract`; normalization must not erase legal
   requirements.
3. A Foundry normalization regression where an already-selected
   `foundry.execute` method is demoted to rejected when serious scenario method
   expectations are supplied.
4. An NL live-path test that requires a runtime claim registry before policy
   grounding, not only in deterministic helper evidence.
5. A semantic-binding producer-status test: if
   `final_compiler[0].claim_evidence_paths` lacks required axes, the ledger
   itself must be `failed` or `blocked`.
6. A PDC live-path test that forbids `profile_payload["status"] = "pass"` when
   no minimum record families are emitted.
7. A continuous-governance authority test that requires lifecycle reports to
   mint lifecycle-specific envelopes instead of inheriting the first available
   closeout envelope.

## External Research Pass - Connectivity Failures In Large Systems

This pass compared the PolicyOS cloud findings with primary sources from
distributed tracing, contract testing, data lineage, SRE troubleshooting, and
distributed-system failure analysis.

### Research Signals

1. Context propagation is a first-class system invariant, not optional metadata.
   OpenTelemetry describes context as the mechanism that lets traces, metrics,
   and logs correlate across process and service boundaries, and W3C Trace
   Context standardizes the cross-service carrier. This maps directly to our
   `scenario_evidence_contract`: it must be a propagated runtime carrier across
   Data/Fabric, Lex, Foundry, Scientist, Semantic Binding, PDC, and closeout
   readers. If it is only request-local metadata, producers can silently fork
   interpretations.

2. Async and batch boundaries are where traces most often break. OpenTelemetry's
   messaging conventions call out that producer and consumer traces cannot be
   directly correlated unless message creation context is attached to the
   message and propagated through all intermediaries. Our equivalent boundary is
   the transition from NL request/context into control-plane job progress,
   Scientist variant state, CAS evidence bundle, canary evidence assembly, and
   reader normalization. The cloud run shows exactly this class of break:
   Fabric's nested report has the scenario contract id, but the top-level trace
   drops it; Lex query normalization sees legal requirements, but normalized
   evidence loses them.

3. Consumer-provider compatibility should be a versioned matrix. Pact's
   `can-i-deploy` pattern records consumer contracts, provider verification
   results, deployed versions, and asks whether a specific version can safely
   enter an environment. Our current Wave 1-11 tests prove many modules in
   isolation, but the cloud live path combines producer/report/readiness versions
   that are not yet verified as an environment matrix. We need a PolicyOS
   equivalent: `can-i-closeout` over scenario contract version, producer report
   schema version, reader gate version, and authority-profile version.

4. Data lineage models separate static dataset metadata from per-run input/output
   facts. OpenLineage distinguishes Job, Run, and Dataset, with facets for schema,
   column lineage, quality metrics, quality assertions, ownership, and run
   lifecycle. Our production data contract index is conceptually aligned, but the
   current curated metadata only has generic metric contracts. Scenario source
   families need dataset-level facets and run-level input/output facets, not just
   bundle availability.

5. Data quality assertions should attach to the dataset or column they validate.
   OpenLineage's data-quality assertion facet records what was tested, whether it
   passed, and the target column. This is the missing distinction in our current
   data plane: `production_data` can say a broad bundle exists, but cannot yet
   bind dictionary, schema, freshness, missingness, outlier, construct-validity,
   and lineage findings to scenario fields and claims.

6. SRE troubleshooting recommends examining component boundaries and the data
   flowing between them. Google's SRE material explicitly emphasizes comparing
   expected behavior, actual behavior, telemetry/logs, known transformations, and
   black-box probes at each step. Our manual deep dive followed that method. The
   next improvement is to automate it as a boundary-probe fixture: inject a known
   scenario contract and assert each producer's output retains the same contract
   id, requirement ids, selected or blocked candidate refs, and status semantics.

7. Large-system failures often come from bad handling of non-fatal errors.
   Yuan et al.'s OSDI 2014 study found that catastrophic failures in
   distributed data-intensive systems were often caused by incorrect handling of
   explicit non-fatal errors, and many could be exposed by simple testing of
   error-handling paths. In our system, analogous "non-fatal" states are
   `blocked`, `failed`, `missing`, `profile_only`, `source_family_absent`,
   `generic_method_not_admissible`, and `missing_normative_anchor`. The cloud
   failure shows several places where these states are detected by readers but
   not reflected by producer top-level status or authority envelopes.

### Common Mistakes To Guard Against

| Mistake | External pattern | PolicyOS manifestation | Guardrail |
| --- | --- | --- | --- |
| Treating context as local request metadata | Lost distributed trace context | Scenario contract appears in request but disappears or becomes inconsistent in producer reports | Required propagated `scenario_contract_ref` and `requirement_refs` on every producer/reader artifact |
| Testing modules but not deployed combinations | Consumer/provider matrix drift | Unit tests pass synthetic fixtures, while cloud live path lacks claim registry and PDC records | `can-i-closeout` compatibility matrix for scenario, producer, reader, and authority versions |
| Confusing bundle availability with data admissibility | Dataset facet vs run/input/output facet confusion | Broad `datasets` selected while `production_msme_panel` contract is absent | Field-level source family contracts plus dataset/run lineage facets |
| Reporting global candidates as claim anchors | Missing consumer-specific contract verification | 33 Lex norms selected globally, but per-recommendation selected refs are empty | Per-claim selected/rejected legal candidate ledger |
| Letting generic execution satisfy named method obligations | Weak provider behavior contract | `foundry.execute` remains selected despite causal/uncertainty/sensitivity expectations | Demote generic methods during normalization under serious scenario contracts |
| Producer `pass` with reader-only failures | Bad handling of explicit non-fatal states | Semantic ledger and PDC profile say pass while reader gates fail closure | Producers must run their own closure evaluator and emit blocked/failed status |
| Borrowing authority metadata from nearby artifacts | Trace/provenance carrier confusion | Continuous governance reports inherit production-data envelope | Lifecycle-specific authority envelopes minted per report |
| Using live system failure as model-quality evidence | Confounded black-box symptom | Provider demotion caused by upstream evidence closure failure | Separate provider health, controlled model quality, and live system quality |
| Missing async parent/child links | Queue/message trace split | Job progress, CAS bundle, and canary assembly do not expose one causal graph | Span-link-like `parent_runtime_ref` and `input_ref/output_ref` graph for every async handoff |
| Putting sensitive or authoritative data in loose baggage | Unsafe context propagation | Risk of public/dashboard/API exports minting authority or leaking internals | Redacted context carriers; authority only from runtime-owned envelopes |

### Research-Driven Diagnostic Additions

1. Add a `scenario_contract_propagation_graph` artifact to every live bundle.
   It should list each component, consumed contract ref, emitted contract ref,
   requirement ids consumed, requirement ids emitted, and whether the component
   selected, rejected, or blocked each requirement.

2. Add `can-i-closeout` compatibility checks modeled after a contract matrix:
   `scenario_contract_version x producer_report_schema_version x reader_gate_version
   x authority_profile_version`. Closeout should fail if the exact deployed
   combination has not been verified.

3. Add boundary probes for every serious producer:
   `request -> Fabric`, `request -> Lex`, `request -> Foundry`,
   `producer evidence -> claim registry`, `claim registry -> semantic ledger`,
   `semantic ledger -> PDC records`, and `PDC records -> public export`.

4. Add OpenLineage-like data facets to production-data contracts:
   dataset identity, source family, schema, column lineage, quality assertions,
   freshness/nominal time, input subset, output subset, producer version, and
   owner. Scenario admissibility should read these facets, not bundle labels.

5. Add error-state coverage tests for every producer status:
   `missing`, `blocked`, `failed`, `degraded`, `profile_only`,
   `generic_not_admissible`, and `wrong_authority_envelope`. Each state must
   propagate to scorecard/readiness without being normalized to `pass`.

6. Add an async handoff ledger that behaves like span links: job progress,
   workflow state, CAS writes, canary bundle assembly, replay, inspection, and
   readiness should all expose parent/input/output refs. This will make future
   cloud failures diagnosable without manually searching JSON.

7. Add a "no borrowed envelope" invariant: every report's authority envelope
   `artifact_kind`, `schema_name`, `phase`, and `validation_status` must match
   the report being emitted unless a typed projection boundary explicitly says
   the report is a non-authoritative projection.

External sources:

- [OpenTelemetry context propagation](https://opentelemetry.io/docs/concepts/context-propagation/)
- [OpenTelemetry messaging spans and message creation context](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [Pact can-i-deploy and verification matrix](https://docs.pact.io/pact_broker/can_i_deploy)
- [OpenLineage core specification](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md)
- [OpenLineage data quality assertions facet](https://openlineage.io/docs/next/spec/facets/dataset-facets/data_quality_assertions/)
- [Google SRE effective troubleshooting](https://sre.google/sre-book/effective-troubleshooting/)
- [Yuan et al., Simple Testing Can Prevent Most Critical Failures, OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf)
- [Google Dapper distributed tracing paper](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)

## Final Connectivity Diagnostic Pass - Before Remediation Planning

This pass reframes the cloud findings as evidence-spine connectivity failures,
not isolated component incidents. The question is not merely "which gate
failed?", but where runtime meaning changes shape: scenario contract to source
contract, source contract to claim input, legal candidate to recommendation
anchor, method candidate to analytical obligation, claim refs to semantic
closure, and semantic closure to Policy Design Case records.

### Connectivity Invariant Tested

A serious production lane should preserve one continuous evidence spine:

1. `scenario_evidence_contract` is created once and propagated as a runtime
   carrier.
2. Every producer consumes explicit requirement ids and emits selected,
   rejected, or blocked bindings for its slice.
3. Every major claim is compiled from producer-owned data, legal, method,
   argument, warrant, rebuttal/counter-evidence, limitation, and deficit refs.
4. Producer top-level status matches the strictest closure status known by its
   own reader contract.
5. Authority envelopes are minted by the report owner and match the report
   kind, schema, phase, and validation semantics.
6. Closeout verifies the deployed combination of scenario contract, producer
   report schema, reader gate, and authority profile.

The current cloud bundle violates this invariant in several consistent ways.

### Pattern 1 - Context Exists, But Becomes Local Metadata

Evidence:

- `request.sanitized.json` and `golden_scenario_contract.json` both carry
  `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1` with 18
  requirements.
- `bundle.json#/command` also carries the same scenario contract id.
- `fabric_retrieval_trace.json#/production_data_contract_binding_report` has
  the scenario contract id, but top-level
  `fabric_retrieval_trace.json#/scenario_evidence_contract_id` is `null`.
- `normative_evidence.json#/query_normalization_report/legal_requirements` has
  4 legal requirements, while top-level
  `normative_evidence.json#/legal_requirements` has 0.
- Current local `nl_pipeline.py` has code intended to set the Fabric top-level
  scenario id, so the cloud artifact mismatch is itself evidence that the live
  path lacks a compatibility guarantee for code version, report projection, or
  context handoff.

Connectivity diagnosis:

The scenario contract is not missing. It is not yet a mandatory carrier at
producer boundaries. Producers can see it internally, then emit a normalized
report that loses the contract id or requirement projection.

Planning implication:

The remediation plan should introduce a required propagation graph and fail
producer normalization if a producer consumed a scenario contract but dropped
the contract id or requirement ids in its emitted report.

### Pattern 2 - Data Availability Is Confused With Scenario Admissibility

Evidence:

- The cloud data directory was available and large enough for a real run.
- Curated `source_bindings.json` has only 3 bindings:
  `us.macro.gdp_nominal`, `us.macro.unemployment_rate`, and
  `agent.income.salary`.
- Curated `data_contracts.json` has the same 3 generic metric contracts.
- There are no curated contracts for `production_msme_panel`,
  `credit_program_registry`, or `regional_displacement_indicators`.
- Fabric emits 3 blocked scenario binding findings, all with `candidate_ref=null`.
- Fabric still has 5 broad selected sources in the trace, but
  `selected_contract_binding=null` and `selected_contract_bindings=[]`.

Connectivity diagnosis:

The production-data layer proves file and bundle presence, but not
scenario-admissible source identity, field facets, lineage, or claim
bindability. Fabric is correctly blocking broad bundles; the missing part is
the data contract package and the earlier fail-fast guard before source
selection.

Planning implication:

The first data repair must be contract packaging, not selector relaxation:
scenario-family source bindings with dictionary, schema, field refs, units,
geography/time coverage, freshness, lineage, transformations, quality,
missingness, outlier, construct-validity, and claim-bindability.

### Pattern 3 - Global Evidence Pools Are Treated As If They Were Claim Anchors

Evidence:

- Lex retrieved 33 candidate norm refs and selected 33 global norm refs.
- Each recommendation coverage row still fails with
  `missing_normative_anchor` and has 0 selected/rejected norm refs.
- Semantic claim evidence paths copy 33 `selected_norm_refs` onto each major
  claim, but still have 0 `scenario_requirement_refs`, 0
  `canonical_concept_refs`, 0 `column_refs`, 0 `argument_refs`, 0
  `warrant_refs`, 0 `rebuttal_refs`, 0 `counter_evidence_refs`, and 0
  `limitation_refs`.

Connectivity diagnosis:

The system can retrieve and store pools of potentially relevant evidence, but
does not consistently perform the second step: claim-specific selection,
rejection, and rationale. A global evidence pool is not an admissible claim
anchor.

Planning implication:

The remediation plan needs an explicit claim registry boundary. It should take
Fabric, Lex, Foundry, and Scientist outputs and compile per-claim selected,
rejected, blocked, and deficit refs before semantic binding and decision
artifact generation.

### Pattern 4 - Invalid Candidates Remain In Selected State

Evidence:

- Foundry expected method expectations:
  `causal_effect_estimation`,
  `heterogeneity_by_region_or_firm_size`,
  `sensitivity_or_transportability_diagnostic`, and `uncertainty_interval`.
- The only selected and candidate method is `method_id=foundry.execute` with
  `method_family=simulation`.
- `method_obligations=[]` and `rejected_methods=[]`.
- The same report correctly emits `method_family_not_expected`,
  `generic_simulation_false_pass`, missing assumptions, missing uncertainty,
  missing missingness diagnostics, and missing sensitivity issues.

Connectivity diagnosis:

Validation knows the candidate is not admissible, but selection-state
normalization does not demote the candidate from selected to rejected or blocked.
This is a state-machine problem: issue generation and selected-candidate state
are not governed by one contract.

Planning implication:

The method report builder should apply serious scenario expectations before
finalizing `selected_methods`, and the workflow builder should request named
method obligations before claim drafting.

### Pattern 5 - Producers Say `pass` When Readers Know Closure Failed

Evidence:

- `semantic_binding_ledger.json` has top-level `status=pass` and
  `runtime_report_status=null`.
- The scorecard emits 108 semantic binding failures from that same ledger.
- `policy_design_case.json` has top-level `status=pass`, but no `records`, no
  `record_families`, and no `summary`.
- `nl_pipeline.py` still contains a live path that builds a profile via
  `build_policy_design_case_profile` and then forces `profile_payload["status"] = "pass"`.

Connectivity diagnosis:

Several producers still treat "artifact exists and parses" as a pass, while
reader gates evaluate stronger closure contracts. This creates a truth
preservation gap: the system eventually fails correctly, but the artifact that
should own the failure does not expose the failure as its status.

Planning implication:

Closure evaluation must move upstream into producers. Semantic Binding and
Policy Design Case should emit `failed`, `blocked`, or `profile_only` at
producer time, with the same issue codes that downstream scorecard/readiness
will consume.

### Pattern 6 - Authority Envelopes Can Be Borrowed Across Report Kinds

Evidence:

- Each continuous governance no-op report says `status=pass` and
  `decision_status=no_published_decision_mutation_required`.
- Each report's authority envelope says:
  `artifact_kind=runtime.production_data_quality_report`,
  `schema_name=polisyos.runtime.ProductionDataQualityReport`,
  `phase=production_data_quality`, and `validation_status=fail`.
- `canary_evidence.py` has a fallback path where `_authority_record_for_ref`
  can copy `base_authority_envelope`, and `_continuous_governance_report`
  copies the supplied authority record into lifecycle reports.

Connectivity diagnosis:

The provenance system prevents missing authority, but it can still attach real
authority from the wrong report. That is a more subtle connectivity failure:
the authority carrier is present, yet semantically mismatched.

Planning implication:

Add a no-borrowed-envelope invariant. Every authority envelope must match the
report's artifact kind, schema, phase, validation status, and runtime event
unless the artifact is explicitly marked as a non-authoritative projection.

### Pattern 7 - Deployed Combination Compatibility Is Not Verified

Evidence:

- The bundle command carries the scenario contract id, but individual producer
  reports expose mixed behavior: some have runtime-report status, some do not;
  some propagate requirements internally but drop them at top level.
- `bundle.json#/git_sha` is `None`, so the exact producer/report/reader version
  combination is not reconstructable from the bundle alone.
- Unit fixtures exercise newer contracts, while the cloud live path still emits
  older profile-only or globally-selected evidence shapes in several places.

Connectivity diagnosis:

The repo has many correct local contracts, but closeout does not yet verify the
exact deployed combination of scenario contract version, producer report schema,
reader gate version, authority profile version, and code revision.

Planning implication:

Introduce `can-i-closeout`: a compatibility matrix that must be green for the
exact deployed bundle before readiness can be treated as closeout evidence.

### Pattern 8 - Secondary Signals Are Confounded By Upstream Connectivity

Evidence:

- Provider preflight passed.
- Provider model quality demoted the model from a single quarantined live
  observation whose grounding failure came from a lane already missing data,
  legal, method, claim, semantic, and PDC closure.
- Prompt/tool ledger has `summary.status=fail`, `tool_count=0`, and a final
  evaluator status failure, but it does not yet explain the serious handoff
  failure in operator language.
- One control-plane progress update timed out, but bundle creation and
  scorecard evaluation completed.

Connectivity diagnosis:

These are real signals, but they should not be interpreted as primary causes.
They are downstream observations emitted after the evidence spine has already
lost admissible source contracts and claim-bound refs.

Planning implication:

Keep provider/model decisions, prompt-tool authority, and control-plane
resilience diagnostics separated from root evidence-closure blockers until the
producer spine is complete enough to isolate them.

### Final Root Model

The deepest issue is not that PolicyOS lacks all best-in-class logic. The code
base now contains many strict contracts, validators, and reader gates. The cloud
lane is failing because the live producer path does not yet preserve one
authoritative evidence spine across subsystem boundaries.

The recurring failure modes are:

- context created but not propagated as a required runtime carrier;
- scenario evidence obligations present but not converted into producer-owned
  selected/rejected/blocked bindings;
- global evidence pools copied forward instead of claim-bound anchors;
- selected-candidate state not reconciled with validation failures;
- producer status weaker than downstream reader closure;
- authority envelope present but semantically attached to the wrong report;
- no closeout compatibility matrix for the exact deployed combination.

This means the remediation plan should be organized around the spine, not the
symptoms: scenario contract propagation, scenario data contract packaging,
producer selection/blocking contracts, claim registry compilation, producer-side
closure status, Policy Design Case record-family compilation, authority envelope
ownership, and `can-i-closeout` compatibility.

## Wave 0 Regression Fixture - Evidence Spine Connectivity

Status: implemented

Wave 0 of
`docs/plans/active/POLICYOS_EVIDENCE_SPINE_CONNECTIVITY_REMEDIATION_PLAN.md`
freezes the 2026-05-20 cloud connectivity failure as a compact regression
fixture:

- Fixture:
  `tests/fixtures/production_quality/cloud_debug_20260520/evidence_spine_connectivity_fixture.json`
- Test:
  `tests/repo_quality/tools/test_evidence_spine_connectivity_regression.py`
- Verification:
  `uv run pytest tests/repo_quality/tools/test_evidence_spine_connectivity_regression.py -q`

The fixture preserves the exact facts needed for future repairs:

- request and bundle carry
  `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1` with 18
  requirements;
- Fabric nested contract binding carries that id while the top-level Fabric
  trace drops it;
- Lex query normalization has 4 legal requirements while the top-level report
  has 0;
- curated production-data contracts contain only `us.macro.gdp_nominal`,
  `us.macro.unemployment_rate`, and `agent.income.salary`;
- `production_msme_panel`, `credit_program_registry`, and
  `regional_displacement_indicators` remain absent;
- semantic binding and Policy Design Case top-level `pass` states coexist with
  reader-visible closure failures;
- continuous governance carries a borrowed
  `runtime.production_data_quality_report` authority envelope.

The test intentionally fails if a future compact fixture erases any of these
four guardrails:

- dropped scenario contract id;
- global evidence pool replacing per-claim anchors;
- producer `pass` while reader closure fails;
- borrowed authority envelope.

## Proposed Next Work Items

1. Use the Wave 0 evidence-spine fixture to drive the next production-data
   regression: curated metadata must prove the three scenario families are
   present before Fabric selection.
2. Add a production-data contract packaging task that creates source bindings
   for `production_msme_panel`, `credit_program_registry`, and
   `regional_displacement_indicators` with full facets.
3. Add a runtime check that fails before Fabric selection if scenario families
   are not present in the contract index.
4. Add a Lex recommendation-anchor diagnostic that records why each candidate
   norm was selected or rejected per claim.
5. Add a Foundry workflow trace showing whether method obligations enter the
   builder before claim drafting.
6. Tighten semantic ledger and Policy Design Case producer statuses so
   top-level `pass` cannot coexist with closure-incomplete content.
7. Fix continuous governance authority envelopes to use lifecycle schemas and
   validation semantics.
8. Keep provider demotion decisions controlled-task-only until upstream
   evidence closure is complete.

## Recheck Commands

```bash
uv run python tools/quality/validation/inspect_evidence_bundles.py \
  --repo-root . \
  --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full \
  --json-output _build/.tmp/production-quality/cloud_wave11/inspect_cloud_wave11_bundle_direct.json

uv run python tools/ops_runners/runtime/replay_canary_bundle.py \
  --bundle _build/.tmp/production-quality/cloud_wave11/bundle_full \
  --json-output _build/.tmp/production-quality/cloud_wave11/replay_cloud_wave11_bundle.json
```

## 2026-05-21 Cloud Sync And Wave 12 Revalidation

Status: completed, closeout still blocked by typed findings

Cloud target:

- project: `lex-1-494208`
- VM: `policyos-prod-debug-20260520`
- zone: `europe-west1-b`
- workspace: `/workspace/polisyos/policy-engine`

Code sync evidence:

- Local source tarball uploaded to the VM and extracted into
  `/tmp/policy-engine-source-sync`.
- `rsync -a --delete` synchronized the source tree while preserving local
  cloud secrets, production data, build artifacts, CAS bundles, virtualenvs,
  and caches.
- Post-sync SHA-256 manifest comparison:
  - local files: `10635`
  - cloud files: `10635`
  - missing on cloud: `0`
  - extra on cloud: `0`
  - hash mismatches: `0`
- Local evidence:
  `_build/.tmp/production-quality/cloud_wave12_sync/manifest_diff_summary.after_sync.json`

Cloud quick probe:

- Command:
  `tools/quality/testing/local_prod_debug_probe.py --checks quick,production-data-static,docs-repro`
- Output copied locally:
  `_build/.tmp/production-quality/cloud_wave12/cloud_prod_debug_spine_quick_20260521_after_sync.json`
- Result: `6 passed`, `1 failed`.
- Passed:
  `bootstrap`, `postgres-lifecycle`, `stale-recovery`,
  `production-dry-run`, `postgres-resource`, `docs-repro`.
- Failed:
  `production-data-static`.
- Primary data blocker remains scenario-data admissibility: curated production
  contracts still do not provide the required scenario families
  `production_msme_panel`, `credit_program_registry`, and
  `regional_displacement_indicators`; the static probe also preserves the
  lower-level dictionary, freshness, missingness, outlier, construct-validity,
  and empty-curated-bundle findings.

Cloud live lane:

- Lane:
  `profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only`
- Matrix output copied locally:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/final_live_research_lane.json`
- Bundle path:
  `.polisyos/canary_evidence/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260521T092911Z_62b6b403cadd40a18aa25b9cad84998d`
- Result: failed with a preserved runtime failure envelope.
- Primary live failure:
  `no_model_variant_completed` at `llm_gateway`.
- Provider/model detail:
  `Qwen/Qwen3-235B-A22B-Instruct-2507-FP8` failed the gateway call to
  `https://proxy.gonka.gg/v1/chat/completions`.
- Missing late-run evidence in the failed lane remains explicit:
  `lineage.json`, `run.json`, `timeline.json`,
  `quality_evidence/conflict_check.json`,
  `quality_evidence/foundry_method_report.json`,
  `quality_evidence/normative_evidence.json`, and
  `quality_evidence/policy_grounding_matrix.json`.

Inspection and readiness outputs:

- Bundle inspection:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/final_evidence_bundle_inspection.json`
  - status: `fail`
  - finding: `phase64_matrix_lane_not_passed`
  - root cause class: `runtime_lane_failure`
- Readiness:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/final_readiness.json`
  - status: `fail`
  - primary matrix failure: `hds_matrix_lane_not_passed`
  - provider evidence attachments: `0`
  - required serious profile ref failures: `0`
- Evidence spine connectivity:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/evidence_spine_connectivity.json`
  - status: `pass`
  - findings: `0`
- Evidence spine handoffs:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/evidence_spine_handoffs.json`
  - status: `pass`
  - handoffs: `9`
  - findings: `0`
- Can-I-Closeout:
  `_build/.tmp/production-quality/cloud_wave12/after_sync/can_i_closeout.json`
  - status: `fail`
  - issue count: `3`
  - verified producer/reader pairs: `15` of `16`
  - blockers:
    `closeout_git_sha_missing`, `closeout_code_revision_missing`,
    `closeout_reader_schema_pair_unverified` for
    `policyos.security_assurance_report.v1` against
    `security_assurance_report_passed`.

Additional environment finding:

- First docs-gate run failed because stale macOS AppleDouble and `.DS_Store`
  files were present in the cloud workspace and confused ADR indexing.
- Deleted only `._*` and `.DS_Store` metadata files on the VM.
- Re-ran:
  `uv run --extra test pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q`
- Result: `29 passed`.

Diagnostic interpretation:

The repaired code is now synchronized to the VM and the Wave 12 infrastructure
checks prove that the evidence-spine carrier and handoff ledgers survive bundle
assembly. The remaining blockers are no longer hidden connectivity drift:

- source-data admissibility is still blocked before Fabric because scenario
  production-data contracts are absent from curated metadata;
- the one-lane live run is blocked at the LLM gateway before producing final
  claim/legal/method artifacts;
- closeout is correctly denied because the cloud bundle cannot prove deployed
  code revision metadata and one active producer/reader schema pair;
- PDC benchmarking, portfolio predeclaration, and run-cost proportionality
  readiness components still require the Wave 0 coverage baseline artifact in
  the cloud build directory.

Next diagnostics should separate these four classes instead of treating them as
one failure: data packaging, live provider/gateway availability, closeout
revision stamping, and coverage-baseline materialization.
