---
title: Cloud Production Debug Ten-Check Backlog
status: active
owner: team-runtime
created: 2026-05-20
source_run: .polisyos/canary_evidence/local-prod-debug/live-research/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T080028Z_33b5bf0188564b2184f2d47a930b8bf0
source_probe: _build/.tmp/production-quality/cloud_prod_debug_live_full_data.json
scope:
  - gcp-production-debug
  - production_data
  - runtime-api
  - control-plane
  - llm-gateway
  - fabric
  - lex
  - foundry
  - scientist
  - quality-scorecard
---

# Cloud Production Debug Ten-Check Backlog

This backlog records the first GCP-backed production-debug sweep after the full
`production_data` tree was uploaded to the debug VM.

The run is intentionally diagnostic. It proves that the cloud debug environment
can execute the live research lane with full production data and fail closed
through the quality scorecard. It does not prove production promotion readiness.

## Source Run

- Account context: `repairkyiv4@gmail.com`
- GCP project: `lex-1-494208`
- VM: `policyos-prod-debug-20260520`
- Zone: `europe-west1-b`
- Machine: `e2-standard-8`
- Access posture: IAP-only SSH; no external IP observed.
- Control-plane store: Docker `postgres:16-alpine` bound to `127.0.0.1:5432`.
- Production data: `6562` files, approximately `34G`, synced to the VM.
- Execution lane:
  `profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only`
- Execution profile distinction: this is a production-debug lane using
  `research` plus embedded worker plus Postgres. Strict production still needs
  the cloud security chain and external worker topology before promotion.

## Evidence Artifacts

- Summary JSON:
  `_build/cloud-prod-debug-20260520/cloud_prod_debug_ten_checks_summary.json`
- Kimi provider preflight:
  `_build/cloud-prod-debug-20260520/cloud_prod_debug_provider_kimi.json`
- VM summary JSON:
  `_build/.tmp/production-quality/cloud_prod_debug_ten_checks_summary.json`
- VM full-data live probe:
  `_build/.tmp/production-quality/cloud_prod_debug_live_full_data.json`
- Evidence bundle:
  `.polisyos/canary_evidence/local-prod-debug/live-research/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T080028Z_33b5bf0188564b2184f2d47a930b8bf0`
- GCS evidence prefix:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/`
- GCS summary JSON:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/cloud_prod_debug_ten_checks_summary.json`
- GCS Kimi provider preflight:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/cloud_prod_debug_provider_kimi.json`

Important observation:

- With incomplete production data, the live lane failed earlier in provider or
  workflow setup.
- With full production data, the live lane completed and emitted a quality
  scorecard, but the scorecard failed closed:
  `overall_score=0.34375`, `quality_status=fail`,
  `approval_state=quality_failed`.

## Ten-Check Summary

| Check | Status | Evidence signal | Primary finding | Next backlog item |
| --- | --- | --- | --- | --- |
| 1. Scorecard owner map | Fail | `32` failed gates; failures in `ops`, `policy_output`, `scientist`, `materialization`, `llm`, `lex`, `fabric`, `foundry` | Failures are now owner-mapped, but many gates remain red. | `CPD-001` |
| 2. Evidence/readiness consistency | Pass with expected fail-closed result | Live lane completed; inspection found one failing serious bundle; readiness did not promote it. | Fail-closed behavior held. Keep as regression guard. | `CPD-002` |
| 3. Authority envelope audit | Fail | `10` `hds_unknown_provenance` gates, even though sampled artifacts have runtime refs and CAS refs. | Failing runtime-owned evidence is being collapsed into unknown provenance. | `CPD-003` |
| 4. Provider/model A/B | Fail for default model quality; preflight passes | Qwen and Kimi preflights passed; live Qwen ledger demoted default model for grounding failure. | Health is not enough; selected model quality fails the live evidence loop. | `CPD-004` |
| 5. Production data quality | Fail | `45` issues across dictionary, construct validity, recency, missing quality, outliers, missingness. | Full data is present but not yet fully quality-described. | `CPD-005` |
| 6. Lex normative retrieval | Fail | `6` issues; four major recommendations lack normative anchors. | Legal authority is not bound to the major recommendations. | `CPD-006` |
| 7. Fabric source admissibility | Fail | `65` issues; selected source family and field-level refs are not admissible enough. | Source selection lacks rights, dictionary, schema, field, unit, geography, time, quality, and lineage refs. | `CPD-007` |
| 8. Foundry method expectation | Fail | `6` issues; generic `foundry.execute` does not satisfy expected analytical method family. | Method selection is too generic for serious policy approval. | `CPD-008` |
| 9. Policy grounding and decision artifact | Fail | Grounding, decision quality, and semantic binding all failed. | Major claims and public recommendations lack required grounding and publication sections. | `CPD-009` |
| 10. Cloud hardening sanity | Pass for debug; not promotion-ready | IAP-only, no external IP, local Postgres, env mode `0600`, full data present. | Cloud debug posture is acceptable, but production security and worker topology are not done. | `CPD-010` |

## CPD-001 - Scorecard Owner Map Remediation

- Status: In progress - Wave 10 local controlled comparison implemented; cloud live rerun pending
- Severity: Critical
- Owning layer: runtime quality scorecard, all producer domains
- Evidence: Full-data live scorecard failed with `overall_score=0.34375`,
  `quality_status=fail`, `approval_state=quality_failed`, and `32` failed gates.
- Failed stages: `ops=11`, `policy_output=5`, `scientist=5`,
  `materialization=3`, `llm=2`, `lex=2`, `fabric=2`, `foundry=2`.
- Production impact: The system correctly blocks publication, but the remaining
  remediation surface is broad enough that owners need an explicit triage map.
- Root-cause hypothesis: Runtime-owned quality gates exist and fire, but
  multiple producer domains still emit incomplete or failing authority evidence.
- Durable fix path: Treat the owner map in the summary JSON as the assignment
  ledger. Each domain owner must either make the gate pass with runtime evidence
  or emit a typed blocker that the serious readiness gate can explain.
- Acceptance gates:
  - Every scorecard failure has a concrete owning layer and next action.
  - No failed gate remains only as a generic or unknown provenance failure.
  - The same live lane either passes scorecard gates or fails with only accepted
    typed blockers.

## CPD-002 - Evidence/Readiness Consistency Regression Guard

- Status: Watch
- Severity: High
- Owning layer: runtime quality readiness, evidence inspection
- Evidence: The full-data live lane completed, evidence inspection selected one
  serious bundle, and readiness did not silently promote it. Inspection summary:
  `fail_count=1`, `closeout_ready_count=0`.
- Production impact: This is the main safety property from the run: a completed
  live workflow with a failing scorecard stayed non-publishable.
- Root-cause hypothesis: Current readiness/inspection projection is aligned for
  this lane, but it needs to remain protected while domain fixes land.
- Durable fix path: Preserve this lane as a regression fixture and keep
  readiness/export tests asserting that a failed scorecard cannot become
  approval-ready through dashboard, API, or public export projections.
- Acceptance gates:
  - Re-running evidence inspection on this bundle preserves the failure
    envelope.
  - Public/dashboard/API exports cannot mint authority or readiness when the
    scorecard failed.
  - Future passing runs must show positive readiness because required evidence
    passes, not because failed evidence was ignored.

## CPD-003 - Authority Envelope Failure Classification

- Status: In progress - Wave 7 local regression implemented; cloud live rerun pending
- Severity: Critical
- Owning layer: honest diagnostics substrate, runtime quality validators
- Evidence: `10` gates reported `hds_unknown_provenance`. Sampled artifacts
  were runtime-emitted and carried `producer_authority`, runtime event refs, and
  CAS refs, but their `authority_validation_status` was `fail`.
- Production impact: Operators see an "unknown provenance" class even when the
  evidence has provenance but fails a domain authority check. That blurs root
  cause and makes remediation noisier.
- Root-cause hypothesis: The HDS validator is conflating missing provenance with
  present-but-failing runtime authority evidence.
- Durable fix path: Split diagnostics into at least two classes: missing or
  spoofed provenance, and runtime-owned authority evidence present but failing.
  Preserve the domain failure code when the envelope is present.
- Acceptance gates:
  - A failing runtime-owned artifact is reported with its domain code and
    authority failure reason, not only `hds_unknown_provenance`.
  - A truly missing/spoofed envelope still fails as provenance/authenticity
    failure.
  - Scorecard and operator summaries point to the first missing or failing
    producer without losing the domain-specific finding.
- Local remediation note, 2026-05-20:
  - `AuthorityFailureClassification` now separates missing provenance,
    spoofed/projection provenance, packaging-only projections, ref identity
    failures, and runtime-owned domain failures.
  - Runtime-owned CAS-backed artifacts with `producer_authority` and
    `validation_status=fail` keep their producer/domain failure code instead of
    being collapsed to `hds_unknown_provenance`.
  - Scorecard and approval readiness now include
    `policyos.operator_triage_ledger.v1` with `owner`, `root_cause_class`,
    `first_failing_artifact_ref`, and `next_action`; evidence-bundle inspection
    preserves this ledger for failed serious bundles.

## CPD-004 - Provider/Model Live Quality Selection

- Status: Open
- Severity: High
- Owning layer: LLM gateway integration, Scientist LLM selection
- Evidence: Qwen and Kimi provider preflights passed. The full-data live lane
  using `Qwen/Qwen3-235B-A22B-Instruct-2507-FP8` produced a provider quality
  ledger with default model action `demote` for `grounding_failure_rate`.
- Production impact: Provider health and tiny completion readiness are
  necessary but not sufficient. The default model can be operationally healthy
  and still fail quality selection for serious policy work.
- Root-cause hypothesis: The live model selector still treats preflight success
  too strongly compared with grounded-output quality observations.
- Durable fix path: Run the same full-data live lane with Kimi and any other
  candidate model under the same budget, compare provider quality ledgers, and
  update the default model policy or require a signed override for Qwen.
- Local remediation note, 2026-05-20:
  - Wave 10 adds a frozen controlled grounding task with one data ref, one norm
    ref, one method ref, and one claim ref.
  - Provider/model comparison for Qwen and Kimi now records schema failures,
    grounding failures, refusal/degradation behavior, latency, cost, and
    request fingerprints without retaining secrets.
  - Default model promotion is blocked until each candidate has at least three
    bounded controlled samples on the same frozen evidence refs.
- Acceptance gates:
  - Default production model is not demoted by the provider quality ledger.
  - Live observations include enough samples to distinguish transient output
    failure from model unsuitability.
  - Model fallback/degradation decisions are visible in scorecard, bundle, and
    operator surfaces.

## CPD-005 - Production Data Quality Contracts

- Status: Open
- Severity: Critical
- Owning layer: production data, Fabric materialization
- Evidence: `45` production-data issues: `data_dictionary_missing=10`,
  `construct_validity_metric_missing=10`, `recency_timestamp_missing=10`,
  `production_data_quality_missing=6`, `production_data_outlier_ratio_high=4`,
  `production_data_missingness_high=4`,
  `major_recommendation_data_quality_degrade_reason_missing=1`.
- Production impact: Full data is available, but selected bundles cannot yet
  prove schema, dictionary, freshness, construct validity, missingness, and
  data quality well enough for serious claims.
- Root-cause hypothesis: The full `production_data` upload solved file
  availability, but bundle metadata and metric-to-column contracts remain
  incomplete.
- Durable fix path: For every selected bundle, add dictionary paths, column
  roles, units, recency timestamps, schema refs, quality diagnostics, and
  construct validity bindings for requested metrics.
- Acceptance gates:
  - `production_data_quality.json` has no fail-severity findings for selected
    bundles.
  - Missingness/outlier findings are either remediated or carried as claim-bound
    limitations.
  - Major recommendations name explicit data-quality degrade reasons when data
    limitations remain.

## CPD-006 - Lex Normative Retrieval And Recommendation Anchors

- Status: Open
- Severity: Critical
- Owning layer: Lex legal authority
- Evidence: Lex emitted `no_relevant_norm_found`, `no_applicable_norms`, and
  missing normative anchors for:
  `rec_emergency_liquidity_grants`,
  `rec_war_responsive_loan_guarantee_program`,
  `rec_digital_voucher_system_for_logistics`,
  `rec_automated_eligibility_disbursement_engine`.
- Production impact: Major recommendations cannot claim legal/institutional
  authority without applicable norms or explicit no-anchor rationale.
- Root-cause hypothesis: The legal query and/or legal KG binding is too broad or
  too weak for the Ukraine MSME wartime-credit scenario.
- Durable fix path: Bind legal retrieval to jurisdiction, time, competence,
  policy instrument, beneficiary class, fiscal authority, and implementation
  agency terms. Preserve rejected norms and blockers as first-class evidence.
- Acceptance gates:
  - Every major recommendation has an applicable norm ref, rejected norm refs,
    or explicit no-anchor blocker.
  - Jurisdiction and competence spine close over legal, data, method, and claim
    evidence.
  - Legal authority failures remain publish-blocking until typed and accepted.

## CPD-007 - Fabric Source Admissibility And Field-Level Lineage

- Status: Open
- Severity: Critical
- Owning layer: Fabric source selection and data contracts
- Evidence: `65` Fabric source-selection issues. Repeated missing fields include
  source rights, dictionary refs, schema refs, field refs, unit refs, geography
  refs, time coverage refs, quality refs, missingness refs, lineage refs,
  transformation refs, and derived feature bindings.
- Production impact: The lane selects data sources, but they are not admissible
  enough to support major claims or downstream Foundry methods.
- Root-cause hypothesis: Source selection is using available bundles without a
  complete admissibility contract for the golden scenario.
- Durable fix path: Define admissible source families for the scenario and
  require every selected source to carry rights, schema, dictionary, field-level
  lineage, unit, geography, time, quality, missingness, and transformation refs.
- Acceptance gates:
  - Fabric retrieval trace has no selected-source admissibility failures.
  - Each selected field can be followed to bundle, source, schema, dictionary,
    quality, and lineage evidence.
  - Scenario contracts reject inadmissible source families before Foundry or
    Scientist tries to use them.

## CPD-008 - Foundry Method Expectation Binding

- Status: In progress - Wave 5 local regression implemented; cloud live rerun pending
- Severity: Critical
- Owning layer: Foundry methods
- Evidence: Foundry emitted `method_family_not_expected`,
  `generic_simulation_false_pass`, `method_assumptions_missing`,
  `method_uncertainty_missing`, `method_missingness_diagnostics_missing`, and
  `method_sensitivity_missing`.
- Production impact: A generic simulation cannot satisfy a serious causal or
  econometric method expectation for final policy claims.
- Root-cause hypothesis: Method selection falls back to a generic execution path
  instead of selecting or blocking on an appropriate analytical method family.
- Durable fix path: Make method selection explicit before execution. If the
  scenario expects causal/econometric evidence, reject generic simulation unless
  an operator accepts a typed method limitation.
- Remediation note: Wave 5 adds runtime `method_obligations`, rejects generic
  `foundry.execute` for distributional and implementation-feasibility
  obligations, and persists a pre-claim obligation report in serious Scientist
  workflow state before claim drafting.
- Acceptance gates:
  - Method report names selected method family, assumptions, uncertainty,
    missingness diagnostics, sensitivity, and data bindings.
  - Generic simulation cannot satisfy the golden scenario's analytical method
    contract by default.
  - Method blockers bind to downstream claim limitations and approval state.

## CPD-009 - Policy Grounding, Semantic Binding, And Decision Artifact Quality

- Status: In progress - Waves 6, 8, and 9 local regressions implemented; cloud live rerun pending
- Severity: Critical
- Owning layer: Scientist, final artifact compiler, runtime projection
- Evidence: Policy grounding failed with `major_claim_missing_grounding=4` and
  `source_quality_freshness_unknown=5`. Decision artifact quality failed with
  `major_recommendation_missing_required_section=44`,
  `claim_statement_missing_text=28`,
  `claim_compiler_runtime_registry_missing=4`,
  `claim_statement_missing_evidence_or_blocker=4`, plus publishable-artifact
  readiness and source-truth conflicts. Semantic binding status also failed.
- Production impact: The final public decision artifact is correctly blocked,
  because major claims do not yet carry enough data, method, norm, warrant,
  rebuttal, uncertainty, and registry evidence.
- Root-cause hypothesis: Upstream data/legal/method failures propagate into the
  final compiler, but the compiler also has independent gaps in required public
  sections and runtime registry binding.
- Durable fix path: Require every major recommendation to be compiled from a
  runtime claim registry entry with evidence refs or blockers, support summary,
  uncertainty, tradeoffs, distributional impact, implementation feasibility,
  monitoring, contestability, and publication-state effects.
- Remediation note: Wave 6 makes `semantic_binding_ledger.json` compatible with
  the live `runtime_report_status=blocked` shape and adds per-claim closure over
  scenario, Fabric columns, Lex norms, Foundry method outputs, Scientist claim
  refs, argument, warrant, rebuttal/counter-evidence, and limitations.
- Remediation note: Wave 8 makes policy grounding fail major grounded claims
  that lack portfolio, independence, synthesis, argument, warrant,
  rebuttal/counter-evidence, and accepted limitation/deficit refs. It also
  projects portfolio and synthesis records onto claim ref axes, requires
  serious decision artifacts to carry a runtime `claim_evidence_contract`, and
  verifies public-ready recommendation, legal, data, method, uncertainty,
  feasibility, monitoring, risk, and contestability sections are backed by
  runtime evidence refs or typed blockers.
- Remediation note: Wave 9 adds the concrete Policy Design Case record-family
  coverage contract. A top-level `policy_design_case.json` `status=pass` now
  fails Phase 28/29 and Pass 1B gates when `records` or `record_families` are
  absent. Each minimum SDD family must carry schema owner, producer owner,
  reader owner, readiness gate, runtime refs, and authority envelope; governance
  surfaces can be present, blocked, or out-of-scope only through typed
  authority policy. Wave 40 closeout now requires runtime record-family
  coverage in addition to the static SDD registry.
- Acceptance gates:
  - Major claims fail if they lack data, method, norm, portfolio, independence,
    synthesis, argument, warrant, rebuttal/counter-evidence, accepted deficits,
    or required BERL reliability.
  - Publishable artifacts cannot be marked ready while scorecard, grounding, or
    source-truth gates fail.
  - Decision artifact sections are generated from runtime evidence, not manual
    ledgers.

## CPD-010 - Cloud Debug Hardening To Production Topology

- Status: Open
- Severity: High
- Owning layer: platform/runtime operations
- Evidence: The debug VM passed the hardening sanity check for this phase:
  IAP-only access, no external IP, Postgres on localhost, `.env.prod-cloud`
  mode `0600`, and full production data present.
- Production impact: The current VM is good enough for realistic debugging, but
  it is not the final production topology.
- Root-cause hypothesis: We deliberately kept the environment MacBook-friendly
  and operator-controlled: embedded worker, debug VM, local Postgres container,
  and no public runtime ingress.
- Durable fix path: Promote the cloud setup through a separate infrastructure
  plan: external worker topology, strict production security collaborators,
  secret rotation, backup/restore drill, least-privilege service accounts,
  monitoring, budget controls, and teardown/rebuild runbooks.
- Acceptance gates:
  - Strict production bootstrap succeeds only with external workers,
    PostgreSQL-backed control-plane state, and production security chain.
  - Backup/restore and evidence replay drills pass from retained cloud
    artifacts.
  - No public/dashboard/API export can bypass approval and evidence gates.

## Recommended Execution Order

1. Fix `CPD-003` first so diagnostics distinguish missing provenance from
   present-but-failing authority evidence.
2. Fix `CPD-005`, `CPD-007`, and `CPD-006` together, because data contracts,
   source admissibility, and legal anchors define the evidence base.
3. Fix `CPD-008` before expecting final policy quality to pass.
4. Fix `CPD-009` once upstream data/legal/method evidence is claim-bindable.
5. Run `CPD-004` model A/B after the evidence base is less noisy, then choose
   or override the default production model.
6. Keep `CPD-002` as a regression guard throughout.
7. Treat `CPD-010` as the infrastructure promotion track, not as a blocker for
   local/cloud debugging.

## Additional Root-Cause Diagnostics - 2026-05-20

After the ten-check sweep, we ran a second diagnostic pass before changing code.
The goal was to find shared causes behind multiple red gates.

Additional artifacts:

- Local copied evidence bundle:
  `_build/cloud-prod-debug-20260520/evidence_bundle/`
- Bundle directory inspection:
  `_build/cloud-prod-debug-20260520/root_cause_bundle_dir_inspection.json`
- Replay refs:
  `_build/cloud-prod-debug-20260520/root_cause_replay_refs.json`
- Static Fabric source-contract report:
  `_build/cloud-prod-debug-20260520/root_cause_fabric_source_contracts.json`
- Static Fabric decision-data coverage report:
  `_build/cloud-prod-debug-20260520/root_cause_fabric_decision_data_coverage.json`
- Local production-data static probe:
  `_build/cloud-prod-debug-20260520/root_cause_local_prod_data_static.json`
- GCS copies:
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/root_cause_bundle_dir_inspection.json`,
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/root_cause_replay_refs.json`,
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/root_cause_fabric_source_contracts.json`,
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/root_cause_fabric_decision_data_coverage.json`,
  `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/root_cause_local_prod_data_static.json`

Checks run:

```bash
gcloud storage cp --recursive 'gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_evidence/live-research/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T080028Z_33b5bf0188564b2184f2d47a930b8bf0/*' _build/cloud-prod-debug-20260520/evidence_bundle/
uv run python tools/quality/validation/inspect_evidence_bundles.py --repo-root . --bundle-dir _build/cloud-prod-debug-20260520/evidence_bundle --json-output _build/cloud-prod-debug-20260520/root_cause_bundle_dir_inspection.json
uv run python tools/ops_runners/runtime/replay_canary_bundle.py --bundle _build/cloud-prod-debug-20260520/evidence_bundle --json-output _build/cloud-prod-debug-20260520/root_cause_replay_refs.json
uv run python tools/quality/validation/fabric_source_contracts.py --report
uv run python tools/quality/validation/fabric_decision_data_coverage.py --report
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks production-data-static --output _build/cloud-prod-debug-20260520/root_cause_local_prod_data_static.json
```

Results:

- Evidence bundle inspection failed only on expected closeout facts:
  `phase64_scorecard_not_pass` and `phase64_bundle_quality_status_not_pass`.
- Replay was stable: `production_readiness=pass`, `status=match`,
  `difference_count=0`. This means the copied bundle is reproducible enough for
  diagnosis; the red scorecard is not a replay drift artifact.
- Static Fabric source-contract coverage passed:
  `conformance_error_count=0`, `source_contract_count=20`,
  `scorecard_count=20`.
- Static Fabric decision-data coverage passed:
  `status=implemented`, `naked_decision_value_count=0`,
  `unknown_field_count=0`.
- Local production-data static probe warned, not failed as a process:
  selected bundle roles were `academic`, `curated`, `datasets`, `lex`, and
  `ukraine_simulation`; findings still included missing dictionaries, missing
  recency timestamps, and missing construct-validity binding for
  `msme_survival_rate`.

### Converged Root-Cause Hypotheses

The failures do not look like ten independent problems. They converge around
six shared causes.

1. Runtime scenario-evidence bridge gap.

   Evidence:

   - Golden scenario expects admissible data source families:
     `production_msme_panel`, `credit_program_registry`,
     `regional_displacement_indicators`.
   - Live Fabric selected broad production bundle families instead:
     `datasets`, `lex`, `curated`, `academic`, `ukraine_simulation`.
   - Every selected source had empty or missing `dictionary_ref`, `schema_ref`,
     `field_refs`, `unit_refs`, `geography_refs`, `time_coverage_refs`,
     `quality_refs`, `missingness_refs`, `lineage_refs`,
     `transformation_refs`, and `derived_feature_bindings`.
   - Static Fabric source contracts pass, so the architectural surface exists;
     the runtime lane is not binding those contracts to the scenario.

   Likely explains:

   - `CPD-005` production data quality failures.
   - `CPD-007` Fabric source admissibility failures.
   - Most of `CPD-009` missing grounding and required public sections.
   - Part of `CPD-008`, because Foundry receives generic data refs instead of a
     method-ready analytical panel.

   Next diagnostic before fixing:

   - Build a small matrix from scenario expected source families to available
     production-data bundles/contracts and mark each as `available`,
     `available_but_unbound`, or `absent`.

2. Lex query-normalization and legal-retrieval bridge gap.

   Evidence:

   - Live Lex report had `candidate_norm_count=0`,
     `retrieval_status=no_relevant_norm_found`, and no selected/rejected norms.
   - The query terms were mostly English policy text plus `UA`.
   - Direct DuckDB probe of the same Lex KG found Ukrainian legal material:
     `підприєм` matched `67126` high-confidence norms, `кредит` matched
     `30738`, `грант` matched `5223`, and `воєн` matched `15370`.
   - English terms were much weaker: `msme=0`, `small business=0`,
     `wartime=0`, while `credit=13` and `grant=7`.

   Likely explains:

   - `CPD-006` no relevant norm and missing recommendation anchors.
   - Jurisdiction/competence spine blockers.
   - Downstream `CPD-009` claim grounding gaps.

   Next diagnostic before fixing:

   - Run a Lex-only retrieval probe with bilingual/normalized Ukrainian terms
     generated from the same scenario and compare candidate counts and selected
     norm refs against the current live report.

3. Authority classification gap, not missing producer provenance.

   Evidence:

   - Producer artifacts such as `production_data_quality`,
     `normative_evidence`, `fabric_retrieval_trace`,
     `foundry_method_report`, `policy_grounding_matrix`,
     `decision_artifact_quality`, and `semantic_binding_ledger` all had
     `authority_envelope.authority_role=producer_authority`,
     `provenance_kind=runtime_emitted`, runtime event refs, and CAS refs.
   - The scorecard still emitted `hds_unknown_provenance` because
     `validation_status` was `fail` or `blocked`, and the scorecard maps
     present-but-failing runtime authority to the same code used for unknown
     provenance.
   - The bundle-level `evidence_provenance_manifest` correctly marks packaged
     files as `packaging_only` or `diagnostic_supporting`; that packaging role
     must not override the producer authority inside the artifact.

   Likely explains:

   - `CPD-003`.
   - Noise across many stages in `CPD-001`.

   Next diagnostic before fixing:

   - Add a negative/positive fixture pair: one artifact with no envelope should
     stay provenance failure; one runtime-emitted artifact with failing domain
     validation should surface its domain failure and an authority-validation
     failure, not `hds_unknown_provenance`.

4. Semantic binding closure gap.

   Evidence:

   - `semantic_binding_ledger.json` has `runtime_report_status=blocked`, but
     `SemanticBindingLedger` currently rejects that field as extra input during
     scorecard deserialization.
   - The ledger shows empty `canonical_concept_refs`, empty Fabric
     `column_refs`, empty Lex `selected_norm_refs`, empty Foundry
     `uncertainty_refs`, and empty Scientist required data/method/norm refs.
   - The same ledger contains many `spine-binding:*:unbound_concept:*` refs.

   Likely explains:

   - `semantic_binding_ledger_invalid`.
   - `policy_design_concept_unresolved`.
   - Most final claim grounding failures.

   Next diagnostic before fixing:

   - Validate the producer schema and reader schema for semantic binding against
     this exact live artifact, then trace which producer should fill
     canonical concept, data, method, norm, and claim refs.

5. Policy Design Case record-family gap.

   Evidence:

   - `policy_design_case.json` reports `status=pass`, but the artifact has no
     explicit `records` or `record_families` arrays and the scorecard still
     reports missing Phase 28/29/Pass 1B record families.
   - The artifact records concept and jurisdiction issues internally, but its
     top-level status is not enough for serious closeout.

   Likely explains:

   - The ops-stage record-family failures in `CPD-001`.
   - The remaining Pass 1B/Pass 2 closeout blockers even if domain evidence is
     repaired.

   Next diagnostic before fixing:

   - Compare the minimum SDD record-family coverage contract against the live
     `policy_design_case.json` and list exactly which family producer is
     absent, blocked, or incorrectly projected as pass.

   Local remediation note, 2026-05-20:

   - Wave 9 implements that comparison as
     `policyos.runtime.policy_design_case.record_family_coverage.v1`.
   - Static registry rows remain only the catalog of required families; runtime
     closeout now reads concrete `records` and `record_families`.
   - Wave 40 validation rejects SDD mapping artifacts that omit runtime
     record-family coverage.

6. Provider/model quality is likely downstream-contaminated until evidence
   binding is cleaner.

   Evidence:

   - Qwen and Kimi provider preflights both passed.
   - The default Qwen live observation was demoted for grounding failure with a
     sample count of one.
   - The same run had no legal anchors, no field-level data refs, generic
     Foundry method evidence, and missing semantic binding.

   Likely explains:

   - `CPD-004` should not be treated as a pure model-quality root cause yet.

   Next diagnostic before fixing:

   - Re-run a model A/B lane only after the Lex/Fabric/semantic bridge has at
     least one claim-bound path, or run a tiny controlled grounding task where
     the evidence refs are already known-good.

### Updated Remediation Ordering From Diagnostics

Do not start with final artifact text generation. The shared root causes point
to this safer order:

1. Diagnose and fix the scenario-evidence bridge so Fabric can map golden
   scenario requirements to available production-data contracts or typed absent
   blockers.
2. Diagnose and fix Lex query normalization against the Ukrainian legal KG.
3. Fix authority failure classification so future runs show true first causes.
4. Fix semantic binding producer/reader schema and ref propagation.
5. Re-run the live lane and only then judge model A/B quality.
6. Address Policy Design Case record-family gaps as the closeout layer after
   domain evidence is claim-bindable.

## Implementation Ledger

### Wave 0 - Root-Cause Regression Fixture

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Fixture:
  `tests/fixtures/production_quality/cloud_debug_20260520/root_cause_summary.json`
- Regression tests:
  `tests/repo_quality/tools/test_cloud_prod_debug_root_cause_regression.py`
- Runtime tooling:
  `tools/ops_runners/runtime/replay_canary_bundle.py --root-cause-fixture`
- Preserved root-cause axes:
  - scenario expected families:
    `production_msme_panel`, `credit_program_registry`,
    `regional_displacement_indicators`;
  - selected broad families:
    `datasets`, `lex`, `curated`, `academic`, `ukraine_simulation`;
  - Lex retrieval:
    `candidate_norm_count=0`, `retrieval_status=no_relevant_norm_found`,
    while direct Ukrainian term probes find legal material;
  - semantic binding:
    `runtime_report_status.extra_forbidden` plus empty claim-binding axes;
  - Policy Design Case:
    top-level `status=pass` with missing record-family closeout codes;
  - authority classification:
    `hds_unknown_provenance_count=10` on runtime-emitted failing authority
    artifacts.
- Verification:

```bash
uv run pytest tests/repo_quality/tools/test_cloud_prod_debug_root_cause_regression.py -q
uv run pytest tests/repo_quality/tools/test_replay_canary_bundle.py -q
uv run python tools/ops_runners/runtime/replay_canary_bundle.py --root-cause-fixture tests/fixtures/production_quality/cloud_debug_20260520/root_cause_summary.json --json-output _build/.tmp/production-quality/root_cause_fixture_replay.json
```

The fixture replay command is expected to exit `2` because it deliberately
renders the known failed cloud-debug run as a preserved failure envelope.

### Wave 1 - Scenario Evidence Contract

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Runtime contract:
  `src/polisyos/runtime/quality/scenario_evidence_contract.py`
- Golden scenario metadata:
  `tools/ops_runners/runtime/golden_quality_scenarios.json`
- Loader and canary propagation:
  `tools/ops_runners/runtime/quality_scenarios.py`,
  `tools/ops_runners/runtime/local_production_canary.py`
- Regression tests:
  `tests/unit/runtime/quality/test_scenario_evidence_contract.py`,
  `tests/unit/tools/test_quality_scenarios.py`
- Contract result:
  - scenario id:
    `ukraine_msme_wartime_credit_support`;
  - contract id:
    `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1`;
  - data obligations:
    `production_msme_panel`, `credit_program_registry`,
    `regional_displacement_indicators`;
  - legal obligations include:
    `wartime_business_support_authority`, `credit_eligibility_rule`,
    `budget_constraint`, `equity_and_access_obligation`;
  - method obligations include:
    `causal_effect_estimation`, `heterogeneity_by_region_or_firm_size`,
    `uncertainty_interval`, `sensitivity_or_transportability_diagnostic`;
  - claim obligations include:
    `blanket_uncapped_credit_support`,
    `recommendation_without_budget_guardrail`,
    `recommendation_without_displaced_or_frontline_access_analysis`.
- Negative control:
  `datasets` does not satisfy the `production_msme_panel` data requirement and
  produces `source_family_mismatch`.
- Verification:

```bash
uv run pytest tests/unit/tools/test_quality_scenarios.py tests/unit/runtime/quality/test_scenario_evidence_contract.py -q
uv run pytest tests/unit/tools/test_local_production_canary.py::test_build_canary_request_applies_quality_scenario_contract tests/unit/tools/test_canary_evidence.py::test_assemble_canary_evidence_writes_success_and_failure_context_without_secrets -q
```

This wave turns the scenario expectations into typed runtime obligations. It
does not yet make Fabric satisfy those obligations; that is Wave 3 after the
production data contract index in Wave 2.

### Wave 2 - Production Data Contract Index

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Runtime index:
  `src/polisyos/runtime/quality/production_data_contract_index.py`
- Runtime service integration:
  `src/polisyos/runtime/http/services/control/production_data.py`
- Local probe integration:
  `tools/quality/testing/local_prod_debug_probe.py --checks production-data-static`
- Regression tests:
  `tests/unit/runtime/quality/test_production_data_contract_index.py`,
  `tests/repo_quality/tools/test_local_prod_debug_probe.py`
- Contract result:
  - the index loads `manifest.json`, curated `data_contracts.json`, and
    curated `source_bindings.json`;
  - curated source bindings can satisfy a concrete scenario family such as
    `credit_program_registry` only when required source, dictionary, schema,
    field, unit, geography, time, quality, missingness, lineage,
    transformation, derived-feature, recency, construct-validity, and outlier
    facets are present;
  - missing dictionary/schema/lineage facets now produce a failed binding
    instead of passing on file availability;
  - recency, construct-validity, missingness, and outlier gaps are exported as
    claim-bound limitations or degrade reasons.
- Current local production-data finding:
  the real `production_data` root has `candidate_count > 0`, but the golden
  scenario source families are still absent as admissible candidates:
  `production_msme_panel=blocked`, `credit_program_registry=blocked`,
  `regional_displacement_indicators=blocked`. Rejected broad source families
  remain `academic`, `curated`, `datasets`, `lex`, and `ukraine_simulation`.
  This is the intended Wave 2 diagnostic: full file availability is no longer
  confused with scenario-admissible evidence.
- Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_production_data_contract_index.py tests/repo_quality/tools/test_local_prod_debug_probe.py -q
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks production-data-static --output _build/.tmp/production-quality/local_prod_debug_wave2_data_static.json
```

### Wave 3 - Fabric Source Binding

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Fabric audit:
  `src/polisyos/fabric/catalog/source_selection_audit.py`
- Runtime propagation:
  `src/polisyos/runtime/http/services/control/nl_pipeline.py`,
  `src/polisyos/runtime/http/services/control/production_data.py`
- Validation CLI:
  `tools/quality/validation/fabric_source_contracts.py --repo-root . --report <path>`
- Regression tests:
  `tests/unit/fabric/test_source_selection_audit.py`,
  `tests/unit/runtime/http/test_nl_pipeline_materialization.py`
- Contract result:
  - selecting a generic `datasets` bundle while the scenario requires
    `production_msme_panel` now emits `source_family_mismatch`;
  - Fabric source-selection traces now carry `selected_contract_binding`,
    `selected_contract_bindings`, `rejected_contract_bindings`, and
    `source_family_blockers`;
  - satisfied production-data contract-index candidates can be selected as
    `production_data_contract` sources when they carry dictionary, schema,
    field, unit, geography, time, quality, missingness, lineage,
    transformation, freshness, and derived-feature facets;
  - `nl_pipeline.py` threads `scenario_evidence_contract_id`,
    `production_data_contract_binding_report`, and `scenario_binding_findings`
    through the persisted Fabric trace and production-data evidence context.
- Verification:

```bash
uv run pytest tests/unit/fabric/test_source_selection_audit.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
uv run python tools/quality/validation/fabric_source_contracts.py --repo-root . --report _build/.tmp/production-quality/fabric_source_contracts.json
```

### Wave 4 - Lex Bilingual Legal Retrieval

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Query normalization:
  `src/polisyos/lex/normpack/query_normalization.py`
- Lex applicability integration:
  `src/polisyos/lex/normpack/applicability_report.py`,
  `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Regression tests:
  `tests/unit/lex/test_query_normalization.py`,
  `tests/unit/lex/test_normative_applicability_report.py`
- Contract result:
  - the Ukraine MSME golden scenario expands English MSME, credit, grant,
    wartime, and eligibility terms into Ukrainian retrieval stems including
    `підприєм`, `кредит`, `грант`, and `воєн`;
  - zero-candidate Lex reports now require a query-normalization report with
    original terms, normalized terms, KG path, language coverage, and a typed
    no-norm blocker code;
  - legal requirements now carry competence, temporal validity, policy
    instrument, beneficiary class, fiscal authority, and implementation agency
    facets so generic Ukrainian text matches cannot mint recommendation
    authority;
  - normative applicability coverage now records candidate, selected, and
    rejected norm refs for each major recommendation;
  - runtime NL Lex context now receives production-data defaults, including the
    `legal_kg_db_path`, and optional KG lookup degrades safely when a local
    fixture path is not a valid DuckDB database.
- Verification:

```bash
uv run pytest tests/unit/lex/test_query_normalization.py tests/unit/lex/test_normative_applicability_report.py -q
uv run pytest tests/unit/runtime/quality/test_scenario_evidence_contract.py -q
uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

### Wave 9 - Policy Design Case Record Families

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Runtime contract:
  `src/polisyos/runtime/quality/policy_design_case.py`
- Phase gates:
  `src/polisyos/runtime/quality/pass1b_hardening.py`,
  `src/polisyos/runtime/quality/case_maturity.py`,
  `src/polisyos/runtime/quality/case_integrity.py`
- Wave 40 closeout:
  `tools/quality/validation/build_policy_design_case_wave40_readiness.py`,
  `tools/quality/validation/check_policy_design_case_wave40_readiness.py`
- Regression tests:
  `tests/unit/runtime/quality/test_policy_design_case_record_registry.py`,
  `tests/unit/runtime/quality/test_policy_design_case_pass1b_hardening.py`,
  `tests/unit/runtime/quality/test_case_maturity.py`,
  `tests/repo_quality/tools/test_policy_design_case_wave40.py`
- Contract result:
  - `policy_design_case.json` cannot pass serious closeout with only
    `status=pass`; missing `records` or `record_families` emits typed missing
    family codes.
  - Every minimum SDD family must have schema owner, producer owner, reader
    owner, readiness gate, runtime refs, and an authority envelope.
  - Governance surfaces for structured judgement, consultation,
    implementation monitoring, DDM, human oversight, self-FMEA, maturity,
    audit, benchmarking, proportionality, and formal invariants must be
    present, blocked, or out-of-scope through typed authority policy.
  - Wave 40 SDD mapping requires runtime record-family coverage in addition to
    the static registry.
- Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/unit/runtime/quality/test_policy_design_case_pass1b_hardening.py tests/unit/runtime/quality/test_case_maturity.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_wave40.py -q
```

### Wave 10 - Provider Quality After Evidence Closure

- Status: Complete
- Completed: 2026-05-20
- Plan: `docs/plans/active/POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md`
- Runtime contract:
  `src/polisyos/scientist/orchestration/llm/provider_quality.py`
- CLI ledger integration:
  `tools/ops_runners/runtime/provider_quality_ledger.py`
- Local probe integration:
  `tools/quality/testing/local_prod_debug_probe.py --checks provider-quality-controlled`
- Regression tests:
  `tests/unit/scientist/orchestration/llm/test_provider_quality.py`,
  `tests/repo_quality/tools/test_provider_quality_ledger.py`,
  `tests/repo_quality/tools/test_local_prod_debug_probe.py`
- Contract result:
  - controlled provider quality now uses frozen data, norm, method, and claim
    refs instead of judging model quality from an incomplete live evidence
    chain;
  - Qwen and Kimi comparisons retain sample count, schema failure rate,
    grounding failure rate, refusal rate, degradation rate, latency, cost, and
    request fingerprints without secrets;
  - default model promotion is blocked until the selected model and comparison
    candidates have at least three bounded controlled samples;
  - the local probe records the selected-model handoff for the live research
    lane; operator-approved cloud live execution remains Wave 11.
  - local live-lane follow-up records the selected model decision before the
    operator spends live provider budget.
- Verification:

```bash
uv run pytest tests/unit/scientist/orchestration/llm/test_provider_quality.py tests/repo_quality/tools/test_provider_quality_ledger.py tests/repo_quality/tools/test_local_prod_debug_probe.py -q
```

### Wave 11 - Cloud Live Re-Run And Export Truthfulness

- Status: Complete locally and re-run in the cloud; cloud lane still fails the
  runtime scorecard with typed domain blockers.
- Completed: 2026-05-20
- Matrix runner:
  `tools/ops_runners/runtime/run_canary_matrix.py --deterministic --only-lane ...`
- Evidence bundle inspector:
  `tools/quality/validation/inspect_evidence_bundles.py`
- Readiness gate:
  `tools/ci/check_policyos_production_quality_best_in_class.py`
- Public export truth source:
  `tools/ops_runners/runtime/canary_evidence.py`
- Local contract result:
  - `--only-lane` supports the exact cloud debug lane while preserving explicit
    live-provider credential gating;
  - the local rerun selected one live research lane and blocked it with typed
    `live_provider_not_enabled`, not unknown provenance;
  - bundle inspection preserves the matrix failure as
    `phase64_matrix_lane_not_passed`;
  - readiness preserves the same failure as `hds_matrix_lane_not_passed` with
    owner, root-cause class, failure envelope code, and next action;
  - public export bundles carry `runtime_truth_preservation` and inspector
    checks prevent scorecard-status promotion or authority reuse.
- Local evidence:
  - `_build/.tmp/production-quality/final_live_research_lane.json`
  - `_build/.tmp/production-quality/final_evidence_bundle_inspection.json`
  - `_build/.tmp/production-quality/final_readiness.json`
- Cloud validation after code sync:
  - VM: `policyos-prod-debug-20260520`, project `lex-1-494208`, zone
    `europe-west1-b`, account `repairkyiv4@gmail.com`.
  - Code sync: refreshed `src`, `tools`, `tests`, `docs`, `schemas`,
    `architecture`, `packages`, `pyproject.toml`, and `uv.lock`; excluded
    `.env*`, `_build`, `production_data`, virtualenvs, node modules, and
    caches.
  - Data/env check: `.env.prod-cloud` remained mode `600`;
    `production_data/manifest.json` present; `production_data` contains 6562
    files and about 34G.
  - Provider preflight:
    `_build/.tmp/production-quality/cloud_wave11_provider_preflight.json`:
    `pass` with `1 passed / 0 warned / 0 failed / 0 skipped`.
  - Live lane:
    `_build/.tmp/production-quality/cloud_wave11_live_research_lane.json`:
    `1 selected / 1 executed / 0 passed / 1 failed / 0 blocked / 0 skipped`.
  - Bundle:
    `.polisyos/canary_evidence/profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only/20260520T141708Z_b12144f479d34e03854f15ef81c7d5e6`.
  - Bundle inspection:
    `_build/.tmp/production-quality/cloud_wave11_evidence_bundle_inspection.json`:
    `fail`, one finding `phase64_matrix_lane_not_passed`, preserving
    `canary_scorecard_failed`.
  - Readiness:
    `_build/.tmp/production-quality/cloud_wave11_readiness.json`: `fail`.
    Static PQL findings in the bundle are all `pass`, but the minimum closeout
    gate keeps `hds_matrix_lane_not_passed` because the selected serious lane
    failed its runtime scorecard.
  - GCS evidence:
    `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/`
    and
    `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_evidence/`.
- Cloud runtime scorecard blockers:
  - `provider_model_quality_default_model_demoted`;
  - `prompt_tool_parser_authority_ledger_not_passing`;
  - `data_dictionary_missing`;
  - `missing_recommendation_normative_anchor`;
  - `selected_source_family_not_admissible`;
  - `method_family_not_expected`;
  - `major_claim_missing_grounding`;
  - `major_recommendation_missing_required_section`;
  - `continuous_governance_stale_validation_failed`;
  - `continuous_governance_reissue_validation_failed`;
  - `continuous_governance_supersede_validation_failed`;
  - `continuous_governance_withdraw_validation_failed`;
  - `data_forge_snapshot_binding_missing`;
  - repeated `semantic_fabric_source_facet_incomplete` for field, unit,
    geography, time coverage, quality, missingness, freshness, lineage, and
    transformation refs.
- Cloud root-cause notes:
  - Provider access is no longer the blocker; the provider preflight passed.
  - Lex retrieval improved materially: `normative_evidence.json` had
    `candidate_norm_count=33` and `applied_norm_count=33`, but all three major
    recommendations still lacked usable normative anchors.
  - Fabric still cannot satisfy the scenario families
    `production_msme_panel`, `credit_program_registry`, and
    `regional_displacement_indicators`; the report emits
    `source_family_mismatch` and blocked scenario binding findings.
  - Production data quality is still below admissibility: missing dictionaries,
    construct-validity metrics, recency timestamps, high missingness/outlier
    warnings, and missing observed rows for some bundles are exported as typed
    issues.
  - Foundry still emits method-family failures for the serious scenario rather
    than an admissible named method chain.
  - The semantic ledger top-level status was `pass`, while the scorecard
    correctly failed semantic Fabric source facets; this is a remaining
    aggregation/closure gap to investigate.
  - `policy_design_case.json` top-level status was `pass`, while nested
    jurisdiction and case nodes remained `blocked`; this top-level summary
    needs another truth-preservation check.
  - Public export did not mint authority: it carried failed/blocked projections
    and `runtime_truth_preservation` instead of promoting the failed scorecard.
  - Secondary operational anomalies in the lane stderr: a deterministic
    formalizer fallback caused by `TrinityBundle.model_spec.assumptions[0]`
    using unsupported `assumption_type="data"`, and a transient
    `control_plane_store timed out` while updating NL progress.
- Verification:

```bash
uv run pytest tests/repo_quality/tools/test_canary_matrix.py tests/repo_quality/tools/test_replay_canary_bundle.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_evidence_bundle_inspection.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
```

## Recheck Commands

```bash
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks quick --output _build/.tmp/production-quality/local_prod_debug_quick.json
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks provider-quality-controlled --allow-live-provider --output _build/.tmp/production-quality/local_prod_debug_provider_quality_controlled.json
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks provider-preflight,live-research-lane,evidence-inspection --allow-live-provider --output _build/.tmp/production-quality/local_prod_debug_live.json
uv run python tools/quality/validation/inspect_evidence_bundles.py --repo-root . --matrix-run-json _build/.tmp/production-quality/cloud_prod_debug_live_full_data.json --json-output _build/.tmp/production-quality/cloud_prod_debug_bundle_inspection.json
uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --matrix-run-json _build/.tmp/production-quality/cloud_prod_debug_live_full_data.json --output _build/.tmp/production-quality/cloud_prod_debug_readiness.json --output-format json
```

## Promotion Rule

Do not use this cloud-debug run as production approval evidence until:

- the full-data live lane has a passing scorecard or only accepted typed
  blockers;
- authority envelope failures are classified by real root cause;
- legal, Fabric, Foundry, and final-claim evidence are claim-bindable;
- strict production bootstrap runs with external worker topology and security
  collaborators;
- public/dashboard/API exports are rechecked against the same evidence bundle.
