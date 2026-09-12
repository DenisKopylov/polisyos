# Row 1 — complete source-owner census

**MP1-S01 — denominator.** At `307dabcb47bcc0e7659529344d0648cafb840a30`,
`tools/` and `architecture/` contain 1,269 tracked files. Independent Git index
and tree enumerations agree. Of these, 498 are executable-source files: 455
Python, 12 TypeScript, 4 MJS and 27 shell; the other 771 are configuration,
artifacts or documentation. All source reads succeeded; all 455 Python ASTs
parsed, and TypeScript compiler traversal covered the 16 TS/MJS files.

**MP1-S02 — adjudicated population, superseding the provisional 270 candidates.**
Every one of the 498 source files now has an explicit source/control-flow role
and witness. There are **319 diagnostic source owners and 179 exclusions**.
The unit is a source module owning at least one non-test diagnostic about
source, evidence or environment absence, including observed no violations.
A delegating alias adds no owner unless it performs its own analysis. A writer
whose missing-input error merely aborts writing is excluded. A module with both
writing and diagnostic modes is included for the identified diagnostic.
This definition includes supplied-evidence validators: their absence findings
are meaningful only within that supplied evidence, exactly the class at issue.

**MP1-S03 — input disclosure.** Of those 319 owners, **16** expose their bounded
input scope/identity in at least one diagnostic output mode, **290** disclose
only part of the basis, and **13** disclose none. “Yes” is qualified by the mode
and scope in the output witness below; it is not uniform success/failure/all-format
compliance with the new standing rule. Source adjudication does not certify an
executed read receipt or the adequacy of the instrument. For example, Phase0
JUnit JSON names its inputs while its text projection does not; release-canary
JSON is richer than its default stdout. Those are migration work, not exceptions.

**MP1-S04 — discovery provenance.** Ledger and Atlas are the two commissioning
owners inside this source denominator. **317/319** owners were surfaced by this
survey rather than the incident list. The third incident/reference owner,
`src/polisyos/runtime/quality/production_invocation.py@307dabcb4`, is outside the
bounded source roots; its tools wrapper delegates to it. Adding that explicitly
named reference gives 320 discussed owners, 3 incident owners and 317 survey-found
owners; do not silently change the 319-owner census denominator.

**MP1-S05 — independently checked evidence.** Two disjoint reviews cover indices
0–213 plus 464–497 (248 paths), and 214–463 (250 paths). Root reconciles their union
against all 498 source paths, checks every source SHA-256, and checks all Python
positive function/line witnesses against full synchronous/asynchronous AST node
bounds: no omitted index, duplicate index, hash mismatch or witness-bound error.
The original lexical queries ran case-insensitively; their counterexample was a
non-lexical diagnostic or differently capitalized type. Full source role review
and complete AST definition/call/exit inventories accompany those queries.

**Survey boundary:** `unresolved_by_construction: static source-owner adjudication
and bounded output witnesses do not establish runtime invocation, complete reads
inside delegated processes or external plugins, or uniform disclosure across all
output modes; these remain named migration obligations, never measured absence.`

The standing author/review rule is property-based, not a list of these 319 names.
Historical partial/undisclosed projections route to **MP-B1**, team-devx and the
owning source teams. New instruments and changed absence paths must expose actual
reads, selector and unresolved boundaries with a negative that removes that behavior.
The lane repairs the declared GY/Atlas seams and supplies that standing rule; this
census does not pretend a generic tracer has migrated every historical output.

## Complete source inventory

I = diagnostic owner; other labels give the excluded source role. Disclosure is
shown only for diagnostic owners. Each source is pinned independently by path@ref;
function:line is a navigation aid to its source-to-output witness in the raw review.

| Source | Role | Input disclosure | Absence witness |
| --- | --- | --- | --- |
| `architecture/atlas_surfaces/capture_c13_execution_environment.mjs@307dabcb4` | writer | — | `—` |
| `architecture/atlas_surfaces/check_atlas_enforcement.py@307dabcb4` | I | partial | `validate_slice_scope_obligations:3300` |
| `architecture/atlas_surfaces/check_frontend_disposition_register.py@307dabcb4` | I | partial | `validate_register:19753` |
| `architecture/atlas_surfaces/check_status_retirement_inventory.py@307dabcb4` | I | partial | `_validate_live_scan:573` |
| `architecture/atlas_surfaces/decision_time_semantics_scan.mjs@307dabcb4` | I | partial | `<module>:365` |
| `architecture/atlas_surfaces/generated_client_receipt_census.py@307dabcb4` | I | partial | `build_report:907` |
| `architecture/atlas_surfaces/status_retirement_scan.mjs@307dabcb4` | I | partial | `<module>:6235` |
| `architecture/atlas_surfaces/test_atlas_enforcement.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_decision_time_semantics_scan.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_ds18_execution_outcome_consumer.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_ds18_time_semantics_lineage.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_frontend_baseline_debt_manifest.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_frontend_disposition_register.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_generated_client_receipt_census.py@307dabcb4` | test | — | `—` |
| `architecture/atlas_surfaces/test_status_retirement_inventory.py@307dabcb4` | test | — | `—` |
| `tools/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/archive/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/archive/migrate_to_trinity.py@307dabcb4` | writer | — | `—` |
| `tools/check_response_corpus.py@307dabcb4` | I | partial | `check_operation_coverage:73` |
| `tools/ci/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ci/check_action_freshness.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/check_fabric_schema_registry.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/check_foundry_domain_coverage.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/check_phase7_ratchet.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/check_policyos_production_quality_best_in_class.py@307dabcb4` | I | partial | `build_readiness_payload:2734` |
| `tools/ci/check_scientist_benchmark_authority.py@307dabcb4` | I | partial | `_build_payload:190` |
| `tools/ci/check_scientist_best_in_class_phase1_0.py@307dabcb4` | I | partial | `_build_payload:148` |
| `tools/ci/check_scientist_best_in_class_phase1_1.py@307dabcb4` | I | partial | `_build_payload:118` |
| `tools/ci/check_scientist_best_in_class_phase1_2.py@307dabcb4` | I | partial | `_build_payload:129` |
| `tools/ci/check_scientist_best_in_class_phase1_3.py@307dabcb4` | I | partial | `_build_payload:143` |
| `tools/ci/check_scientist_best_in_class_phase1_4.py@307dabcb4` | I | partial | `_build_payload:142` |
| `tools/ci/check_scientist_best_in_class_phase1_6.py@307dabcb4` | I | partial | `_build_payload:167` |
| `tools/ci/check_scientist_best_in_class_phase2_0.py@307dabcb4` | I | partial | `_build_payload:345` |
| `tools/ci/check_scientist_best_in_class_phase2_1.py@307dabcb4` | I | partial | `_build_payload:259` |
| `tools/ci/check_scientist_best_in_class_phase2_2.py@307dabcb4` | I | partial | `_build_payload:285` |
| `tools/ci/check_scientist_best_in_class_phase2_3.py@307dabcb4` | I | partial | `_build_payload:270` |
| `tools/ci/check_scientist_best_in_class_phase2_4.py@307dabcb4` | I | partial | `_build_payload:302` |
| `tools/ci/check_scientist_best_in_class_phase2_5.py@307dabcb4` | I | partial | `_build_payload:398` |
| `tools/ci/check_scientist_best_in_class_phase2_6.py@307dabcb4` | I | partial | `_build_payload:395` |
| `tools/ci/check_scientist_best_in_class_phase2_7.py@307dabcb4` | I | partial | `_build_payload:406` |
| `tools/ci/check_scientist_best_in_class_wave1.py@307dabcb4` | I | partial | `_build_payload:418` |
| `tools/ci/check_scientist_best_in_class_wave2.py@307dabcb4` | I | partial | `_build_payload:832` |
| `tools/ci/check_scientist_phase0_gate.py@307dabcb4` | I | yes | `_build_payload:87` |
| `tools/ci/check_scientist_phase1_gate.py@307dabcb4` | I | partial | `_build_payload:219` |
| `tools/ci/check_scientist_phase2_gate.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/check_scientist_phase2_ratchet.py@307dabcb4` | I | partial | `main:150` |
| `tools/ci/check_scientist_reliability.py@307dabcb4` | I | partial | `_load_passed_test_cases:60` |
| `tools/ci/check_workflow_policy.py@307dabcb4` | delegate | — | `—` |
| `tools/ci/install_actionlint.sh@307dabcb4` | delegate | — | `—` |
| `tools/ci/install_supply_chain_tools.sh@307dabcb4` | delegate | — | `—` |
| `tools/cli.py@307dabcb4` | delegate | — | `—` |
| `tools/design/_a11yColor.ts@307dabcb4` | helper | — | `—` |
| `tools/design/adr_lint.py@307dabcb4` | I | no | `main:42` |
| `tools/design/check-atlas-v4-token-drift.ts@307dabcb4` | I | no | `assertRequiredArtifactsExist:199` |
| `tools/design/check-bureaucratic-review.ts@307dabcb4` | I | no | `main:25` |
| `tools/design/check-categorical-palettes.ts@307dabcb4` | I | no | `assertPalette:92` |
| `tools/design/check-color-blind.ts@307dabcb4` | I | no | `main:33` |
| `tools/design/check-composition-rules.ts@307dabcb4` | I | no | `assertNoForbiddenCompositionTokens:59` |
| `tools/design/check-contrast.ts@307dabcb4` | I | no | `main:295` |
| `tools/design/check-motion-tokens.ts@307dabcb4` | I | no | `main:23` |
| `tools/design/check-print-snapshots.ts@307dabcb4` | I | no | `main:44` |
| `tools/design/check-reduced-motion.ts@307dabcb4` | I | no | `main:28` |
| `tools/design/migrate-numbers-to-quantity.ts@307dabcb4` | writer | — | `—` |
| `tools/design/report-quantity-coverage.ts@307dabcb4` | I | partial | `main:115` |
| `tools/devx/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/architecture/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/architecture/guardrails.py@307dabcb4` | I | partial | `run_check:2073` |
| `tools/devx/architecture/scaffold.py@307dabcb4` | writer | — | `—` |
| `tools/devx/connectors/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/connectors/check_contracts.py@307dabcb4` | I | partial | `main:156` |
| `tools/devx/connectors/scaffold.py@307dabcb4` | writer | — | `—` |
| `tools/devx/foundry/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/foundry/generate_stubs.py@307dabcb4` | writer | — | `—` |
| `tools/devx/foundry/sync_dependency_profile.py@307dabcb4` | I | partial | `_run_diagnose:246` |
| `tools/devx/foundry/update_signature_baseline.py@307dabcb4` | I | partial | `main:50` |
| `tools/devx/install_repo_hooks.mjs@307dabcb4` | writer | — | `—` |
| `tools/devx/refactor/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/refactor/move_module.py@307dabcb4` | writer | — | `—` |
| `tools/devx/workspace/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/devx/workspace/_common.py@307dabcb4` | I | partial | `surface_status:218` |
| `tools/devx/workspace/_repo_hygiene.py@307dabcb4` | helper | — | `—` |
| `tools/devx/workspace/acceptance_audit.py@307dabcb4` | I | partial | `run_audit:747` |
| `tools/devx/workspace/benchmark_surfaces.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/bootstrap.py@307dabcb4` | writer | — | `—` |
| `tools/devx/workspace/ci_parity.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/clean_local_reports.py@307dabcb4` | operation | — | `—` |
| `tools/devx/workspace/core_runtime_basedpyright.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/core_runtime_closeout.py@307dabcb4` | I | partial | `run_closeout:394` |
| `tools/devx/workspace/core_runtime_long_soak.py@307dabcb4` | I | partial | `run_long_soak:600` |
| `tools/devx/workspace/core_runtime_mypy.py@307dabcb4` | I | partial | `_iter_python_files:60` |
| `tools/devx/workspace/docs_style.py@307dabcb4` | I | partial | `main:28` |
| `tools/devx/workspace/doctor.py@307dabcb4` | I | partial | `_check_lockfiles:148` |
| `tools/devx/workspace/format_check.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/lint_fast.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/lint_full.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/python_base_basedpyright.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/python_base_mypy.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/release_build_cache_lifecycle.py@307dabcb4` | I | partial | `build_report:142` |
| `tools/devx/workspace/remote_acceptance.py@307dabcb4` | operation | — | `—` |
| `tools/devx/workspace/repository_sota_closeout.py@307dabcb4` | I | no | `main:177` |
| `tools/devx/workspace/runtime_surface.py@307dabcb4` | delegate | — | `—` |
| `tools/devx/workspace/tool_configs.py@307dabcb4` | I | partial | `check_drift:192` |
| `tools/devx/workspace/verify.py@307dabcb4` | delegate | — | `—` |
| `tools/lib/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/lib/cache.py@307dabcb4` | helper | — | `—` |
| `tools/lib/compat.py@307dabcb4` | helper | — | `—` |
| `tools/lib/document_references.py@307dabcb4` | helper | — | `—` |
| `tools/lib/fs.py@307dabcb4` | helper | — | `—` |
| `tools/lib/http.py@307dabcb4` | helper | — | `—` |
| `tools/lib/imports.py@307dabcb4` | helper | — | `—` |
| `tools/lib/output.py@307dabcb4` | helper | — | `—` |
| `tools/lib/preflight.py@307dabcb4` | I | partial | `run_preflight:38` |
| `tools/lib/runner.py@307dabcb4` | helper | — | `—` |
| `tools/lib/sql.py@307dabcb4` | helper | — | `—` |
| `tools/lib/timing.py@307dabcb4` | I | partial | `summarize_timing_budget_lanes:941` |
| `tools/ops_runners/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/calibration/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/calibration/compare_shards.py@307dabcb4` | I | partial | `analyze_shard:69` |
| `tools/ops_runners/cloud/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/cloud/build_priority_manifests.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/cloud/build_queue3_waves.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/cloud/canonical_auto_approve.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/cloud/check_progress.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/check_progress.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/deploy/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/cloud/deploy/deploy_to_server.sh@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/cloud/deploy/setup_server.sh@307dabcb4` | I | partial | `<module>:58` |
| `tools/ops_runners/cloud/deploy_to_server.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/deploy_to_server.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/gcp_preflight.py@307dabcb4` | I | partial | `main:57` |
| `tools/ops_runners/cloud/merge_shards.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/cloud/pipeline/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/cloud/pipeline/run_datasets_validation.sh@307dabcb4` | I | partial | `<module>:154` |
| `tools/ops_runners/cloud/pipeline/run_diagnostic.sh@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/cloud/pipeline/run_pipeline.sh@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/cloud/pipeline/run_remaining_stages.sh@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/cloud/preflight/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/cloud/prepare_shards.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/prepare_shards.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_datasets_validation.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_datasets_validation.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_diagnostic.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_diagnostic.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_lex_from_manifest.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/cloud/run_pipeline.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_pipeline.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_remaining_stages.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/run_remaining_stages.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/setup_server.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/setup_server.sh@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/cloud/shards/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/cloud/shards/check_progress.sh@307dabcb4` | I | partial | `<module>:31` |
| `tools/ops_runners/cloud/shards/prepare_shards.sh@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/data/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/data/build_academic_gold_candidates.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/data/build_expert_review_bundle.py@307dabcb4` | I | partial | `_validation_summary:149` |
| `tools/ops_runners/data/generate_wvs_registry.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/data/record_fixtures.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/deploy/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/experiments/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/experiments/run_msme_deadline_suite.py@307dabcb4` | I | partial | `preflight:1722` |
| `tools/ops_runners/experiments/run_msme_discovery_addendum_20260501.py@307dabcb4` | I | partial | `main:1140` |
| `tools/ops_runners/experiments/run_msme_e2e_showcase.py@307dabcb4` | I | yes | `preflight:1345` |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite.py@307dabcb4` | I | partial | `stage_04_evidence_retrieval:576` |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite_v2.py@307dabcb4` | I | partial | `stage_12_final_dossier:1767` |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py@307dabcb4` | I | partial | `stage_09_fairness_recourse_governance:703` |
| `tools/ops_runners/experiments/run_msme_final_v3_cloud_rerun.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py@307dabcb4` | I | partial | `preflight:1811` |
| `tools/ops_runners/experiments/run_policyos_real_e2e_cloud.py@307dabcb4` | operation | — | `—` |
| `tools/ops_runners/migrations/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/migrations/contracts.py@307dabcb4` | helper | — | `—` |
| `tools/ops_runners/migrations/migrate.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/migrations/migrate_duckdb_to_pg.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/release/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/release/build_release_notes.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/release/check_compatibility_release_gates.py@307dabcb4` | I | partial | `build_report:41` |
| `tools/ops_runners/release/check_operability_release_gates.py@307dabcb4` | I | partial | `build_report:86` |
| `tools/ops_runners/release/check_release_artifact_sizes.py@307dabcb4` | I | partial | `evaluate_artifacts:31` |
| `tools/ops_runners/release/check_release_version.py@307dabcb4` | I | partial | `main:35` |
| `tools/ops_runners/release/evaluate_vuln_report.py@307dabcb4` | I | no | `evaluate:65` |
| `tools/ops_runners/release/run_release_canary.py@307dabcb4` | I | yes | `_probe:48` |
| `tools/ops_runners/release/stage_release_snapshot.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/reports/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/reports/dead_overrides.py@307dabcb4` | I | partial | `build_report:87` |
| `tools/ops_runners/runtime/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/runtime/archive_legacy_runs.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/runtime/backfill_decision_validity.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/runtime/canary_evidence.py@307dabcb4` | I | partial | `_provenance_entry_for_file:738` |
| `tools/ops_runners/runtime/canary_matrix.py@307dabcb4` | I | no | `_missing_or_deferred_gaps:183` |
| `tools/ops_runners/runtime/check_runtime_api_contract.py@307dabcb4` | I | partial | `_check_runtime_client_drift:88` |
| `tools/ops_runners/runtime/export_runtime_openapi.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/runtime/generate_runtime_client.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/runtime/inventory_legacy_runs.py@307dabcb4` | I | partial | `collect_inventory:65` |
| `tools/ops_runners/runtime/local_production_canary.py@307dabcb4` | I | partial | `main:2493` |
| `tools/ops_runners/runtime/provider_quality_ledger.py@307dabcb4` | I | partial | `_observation_from_variant:239` |
| `tools/ops_runners/runtime/quality_benchmark_authority.py@307dabcb4` | I | partial | `_validate_pack_evidence:386` |
| `tools/ops_runners/runtime/quality_scenarios.py@307dabcb4` | I | partial | `validate_quality_scenario_contract:151` |
| `tools/ops_runners/runtime/replay_canary_bundle.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/runtime/run_canary_matrix.py@307dabcb4` | I | partial | `_completed_result:363` |
| `tools/ops_runners/runtime/runtime_state_cleanup.py@307dabcb4` | I | partial | `_summarize_slot:141` |
| `tools/ops_runners/runtime_cli.py@307dabcb4` | I | partial | `_summary_metric_validation_payload:744` |
| `tools/ops_runners/ukraine_data/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/ops_runners/ukraine_data/build_edr_identity_seed_candidates.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/ukraine_data/build_p1_source_bindings.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/ukraine_data/build_spending_contracts_procurement_proxy.py@307dabcb4` | delegate | — | `—` |
| `tools/ops_runners/ukraine_data/fetch_p0_sources.py@307dabcb4` | I | partial | `main:283` |
| `tools/ops_runners/ukraine_data/fetch_p1_p2_public_sources.py@307dabcb4` | I | partial | `_download_ckan_source:526` |
| `tools/ops_runners/ukraine_data/harvest_prozorro_contract_details.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/ukraine_data/harvest_prozorro_contract_feed.py@307dabcb4` | writer | — | `—` |
| `tools/ops_runners/ukraine_data/harvest_spending_contracts_by_disposer.py@307dabcb4` | I | partial | `_harvest_disposer:543` |
| `tools/ops_runners/ukraine_data/harvest_spending_daily.py@307dabcb4` | I | partial | `_fetch_day:87` |
| `tools/ops_runners/ukraine_data/pre_shard_lex_corpus.py@307dabcb4` | writer | — | `—` |
| `tools/quality/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/ci/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/ci/check_action_freshness.py@307dabcb4` | I | partial | `evaluate:147` |
| `tools/quality/ci/check_fabric_schema_registry.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/ci/check_foundry_domain_coverage.py@307dabcb4` | I | partial | `evaluate_foundry_domain_coverage:150` |
| `tools/quality/ci/check_phase7_ratchet.py@307dabcb4` | I | partial | `evaluate_phase7_ratchet:127` |
| `tools/quality/ci/check_workflow_policy.py@307dabcb4` | I | partial | `_check_pinned_actions:99` |
| `tools/quality/ci/install_actionlint.sh@307dabcb4` | writer | — | `—` |
| `tools/quality/ci/install_supply_chain_tools.sh@307dabcb4` | writer | — | `—` |
| `tools/quality/diagnostics/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/diagnostics/abi_diff.py@307dabcb4` | I | partial | `_verify_version_bumps:713` |
| `tools/quality/diagnostics/capture_env.py@307dabcb4` | I | partial | `cmd_compare:124` |
| `tools/quality/diagnostics/check_perf_regression.py@307dabcb4` | I | partial | `_structured_result:244` |
| `tools/quality/diagnostics/check_scientist_node_version_bump.py@307dabcb4` | I | partial | `main:115` |
| `tools/quality/diagnostics/check_setup.py@307dabcb4` | I | partial | `main:63` |
| `tools/quality/diagnostics/check_state_reads.py@307dabcb4` | I | partial | `main:171` |
| `tools/quality/diagnostics/check_udf_perf.py@307dabcb4` | I | partial | `main:153` |
| `tools/quality/diagnostics/gen_schema.py@307dabcb4` | I | partial | `_assert_file_equals:307` |
| `tools/quality/diagnostics/generate_ir_reference_catalog.py@307dabcb4` | I | partial | `generate_reference_docs:65` |
| `tools/quality/diagnostics/generate_ir_schema.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/diagnostics/scan_fabric.py@307dabcb4` | writer | — | `—` |
| `tools/quality/diagnostics/verify_scm_v3.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/diagnostics/verify_scm_v3_fullspec.py@307dabcb4` | I | partial | `_row_status:242` |
| `tools/quality/diagnostics/visualize_provenance.py@307dabcb4` | I | partial | `verify_prov_json:111` |
| `tools/quality/lint/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/lint/check_scholar_imports.py@307dabcb4` | I | partial | `check:73` |
| `tools/quality/lint/collect_arch_metrics.py@307dabcb4` | I | partial | `_count_missing_sources:110` |
| `tools/quality/lint/compare_baseline.py@307dabcb4` | I | partial | `_validate_exceptions:81` |
| `tools/quality/lint/lint_connector_hardening.py@307dabcb4` | I | partial | `main:142` |
| `tools/quality/lint/lint_connectors.py@307dabcb4` | I | partial | `scan:103` |
| `tools/quality/lint/lint_foundry.py@307dabcb4` | I | partial | `_structured_result:288` |
| `tools/quality/lint/lint_foundry_data_plane.py@307dabcb4` | I | partial | `_check_workflow_has_p8_nodes:95` |
| `tools/quality/lint/lint_imports.py@307dabcb4` | I | partial | `_structured_result:1014` |
| `tools/quality/lint/lint_legacy_cutover.py@307dabcb4` | I | partial | `_check_entrypoint_groups:79` |
| `tools/quality/lint/rules/__init__.py@307dabcb4` | registry | — | `—` |
| `tools/quality/lint/rules/foundry.py@307dabcb4` | I | partial | `_check_banned_imports:17` |
| `tools/quality/testing/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/testing/build_review_package.py@307dabcb4` | writer | — | `—` |
| `tools/quality/testing/check_fabric_exception_baseline.py@307dabcb4` | I | yes | `main:42` |
| `tools/quality/testing/check_playwright_quarantines.py@307dabcb4` | I | partial | `_validate_registry:154` |
| `tools/quality/testing/local_integration_stack.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/testing/local_prod_debug_probe.py@307dabcb4` | I | partial | `run_production_data_static_check:1196` |
| `tools/quality/testing/mutation.py@307dabcb4` | I | partial | `_admit:271` |
| `tools/quality/testing/pytest_workload_receipt.py@307dabcb4` | writer | — | `—` |
| `tools/quality/testing/repeat_pytest.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/testing/report_test_economics.py@307dabcb4` | I | partial | `_render_summary:233` |
| `tools/quality/testing/report_test_ratchets.py@307dabcb4` | I | partial | `_property_status:141` |
| `tools/quality/testing/review_freeze.py@307dabcb4` | I | partial | `validate_ledger:3018` |
| `tools/quality/testing/run_timed_suite.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/testing/runtime_resilience_matrix.py@307dabcb4` | I | partial | `_operator_findings:1103` |
| `tools/quality/validation/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/quality/validation/architecture_report_only_contracts.py@307dabcb4` | I | partial | `_dynamic_imports_summary:1806` |
| `tools/quality/validation/build_honest_diagnostics_coverage.py@307dabcb4` | I | partial | `build_coverage_payload:352` |
| `tools/quality/validation/build_policy_design_case_coverage.py@307dabcb4` | I | partial | `_target_failures:692` |
| `tools/quality/validation/build_policy_design_case_pass2_diagnostics.py@307dabcb4` | I | partial | `_verdict_for_pdd:1860` |
| `tools/quality/validation/build_policy_design_case_pass2_disposition.py@307dabcb4` | I | partial | `_classification_for:801` |
| `tools/quality/validation/build_policy_design_case_wave35a.py@307dabcb4` | I | partial | `_build_hardcoded_language_audit:493` |
| `tools/quality/validation/build_policy_design_case_wave35b.py@307dabcb4` | I | partial | `_build_disposition_update:993` |
| `tools/quality/validation/build_policy_design_case_wave35c.py@307dabcb4` | I | partial | `_refresh_disposition_summary:1342` |
| `tools/quality/validation/build_policy_design_case_wave35d.py@307dabcb4` | I | partial | `_refresh_disposition_summary:1428` |
| `tools/quality/validation/build_policy_design_case_wave35e.py@307dabcb4` | I | partial | `_refresh_disposition_summary:1563` |
| `tools/quality/validation/build_policy_design_case_wave35f_integrity.py@307dabcb4` | I | partial | `_build_integrity_report:750` |
| `tools/quality/validation/build_policy_design_case_wave35g_backfill.py@307dabcb4` | I | partial | `_build_integrity_report:763` |
| `tools/quality/validation/build_policy_design_case_wave35g_institutional_provenance.py@307dabcb4` | I | partial | `validate_institutional_provenance_boundary_ledger:180` |
| `tools/quality/validation/build_policy_design_case_wave35g_memory_authority.py@307dabcb4` | I | partial | `_contamination_checks:349` |
| `tools/quality/validation/build_policy_design_case_wave35h_provenance.py@307dabcb4` | I | partial | `_build_integrity_report:544` |
| `tools/quality/validation/build_policy_design_case_wave36_closeout.py@307dabcb4` | I | partial | `_disposition_entry:328` |
| `tools/quality/validation/build_policy_design_case_wave40_readiness.py@307dabcb4` | I | partial | `_sdd_record_family_mapping:546` |
| `tools/quality/validation/build_policy_evidence_capability_index.py@307dabcb4` | writer | — | `—` |
| `tools/quality/validation/build_wave5_honest_diagnostics_evidence.py@307dabcb4` | I | partial | `_replay_case:231` |
| `tools/quality/validation/capture_layer3_gy_design_generation_replay.py@307dabcb4` | I | partial | `_diagnostic_from_result:288` |
| `tools/quality/validation/check_can_i_closeout.py@307dabcb4` | I | partial | `main:66` |
| `tools/quality/validation/check_canonical_vocabulary_crosswalk.py@307dabcb4` | I | partial | `validate:749` |
| `tools/quality/validation/check_ci_ratchets.py@307dabcb4` | I | partial | `_scan_except_exception_pass:164` |
| `tools/quality/validation/check_compilation_truthfulness.py@307dabcb4` | I | partial | `validate_compilation_truthfulness_report:142` |
| `tools/quality/validation/check_critic_ensemble_diversity.py@307dabcb4` | I | partial | `_evaluate_case:383` |
| `tools/quality/validation/check_debt_ledger.py@307dabcb4` | I | partial | `audit_repository:1314` |
| `tools/quality/validation/check_docs_accuracy.py@307dabcb4` | I | partial | `scan_file:456` |
| `tools/quality/validation/check_docs_freshness_baseline.py@307dabcb4` | I | partial | `check_baseline:57` |
| `tools/quality/validation/check_docs_gate.py@307dabcb4` | I | partial | `main:656` |
| `tools/quality/validation/check_docs_lifecycle.py@307dabcb4` | I | partial | `_compatibility_adr_finding:237` |
| `tools/quality/validation/check_docstring_quality.py@307dabcb4` | I | partial | `check_docstrings:699` |
| `tools/quality/validation/check_domain_coverage_breadth.py@307dabcb4` | I | partial | `validate_domain_coverage_breadth_report:170` |
| `tools/quality/validation/check_evidence_spine_connectivity.py@307dabcb4` | I | partial | `main:74` |
| `tools/quality/validation/check_evidence_spine_handoffs.py@307dabcb4` | I | partial | `inspect_bundle:26` |
| `tools/quality/validation/check_expert_adjudication_labels.py@307dabcb4` | I | partial | `validate_expert_adjudication_labels:103` |
| `tools/quality/validation/check_extension_examples.py@307dabcb4` | I | partial | `validate_pyproject:162` |
| `tools/quality/validation/check_grounding_active_controller_contract.py@307dabcb4` | I | partial | `validate:427` |
| `tools/quality/validation/check_grounding_admission_contract.py@307dabcb4` | I | partial | `_core_issues:679` |
| `tools/quality/validation/check_grounding_benchmark_contract.py@307dabcb4` | I | partial | `validate:169` |
| `tools/quality/validation/check_grounding_bind_contract.py@307dabcb4` | I | partial | `validate:303` |
| `tools/quality/validation/check_grounding_credal_reference_contract.py@307dabcb4` | I | partial | `validate:366` |
| `tools/quality/validation/check_grounding_phrasing_defense_contract.py@307dabcb4` | I | partial | `validate_payload:254` |
| `tools/quality/validation/check_grounding_refusal_sensitivity.py@307dabcb4` | I | partial | `main:167` |
| `tools/quality/validation/check_grounding_relation_contract.py@307dabcb4` | I | partial | `validate:262` |
| `tools/quality/validation/check_gy_acquisition_assurance.py@307dabcb4` | I | partial | `validate_corpus:62` |
| `tools/quality/validation/check_honest_diagnostics_proof_harness.py@307dabcb4` | I | partial | `_missing:699` |
| `tools/quality/validation/check_import_policy_projection.py@307dabcb4` | I | partial | `build_report:147` |
| `tools/quality/validation/check_layer3_artifact_surface_safety.py@307dabcb4` | I | partial | `validate:55` |
| `tools/quality/validation/check_layer3_gy_acquisition_contract.py@307dabcb4` | I | partial | `validate:355` |
| `tools/quality/validation/check_layer3_gy_acquisition_executor.py@307dabcb4` | I | partial | `_check_payloads:1532` |
| `tools/quality/validation/check_layer3_gy_agent_workflow_event_backing_audit.py@307dabcb4` | I | partial | `validate:126` |
| `tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py@307dabcb4` | I | partial | `validate:54` |
| `tools/quality/validation/check_layer3_gy_catalog_fetch_audit.py@307dabcb4` | I | partial | `validate:287` |
| `tools/quality/validation/check_layer3_gy_composition_artifacts.py@307dabcb4` | I | partial | `validate:243` |
| `tools/quality/validation/check_layer3_gy_confidence_ledger.py@307dabcb4` | I | partial | `_check_exact:3554` |
| `tools/quality/validation/check_layer3_gy_connector_family_truth_audit.py@307dabcb4` | I | partial | `validate:338` |
| `tools/quality/validation/check_layer3_gy_data_requirement_compiler_audit.py@307dabcb4` | I | partial | `validate:255` |
| `tools/quality/validation/check_layer3_gy_data_state_substrate_contract.py@307dabcb4` | I | partial | `validate:552` |
| `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py@307dabcb4` | I | partial | `validate_payload:6418` |
| `tools/quality/validation/check_layer3_gy_design_generation_contract.py@307dabcb4` | I | partial | `validate:1617` |
| `tools/quality/validation/check_layer3_gy_design_problem_contract.py@307dabcb4` | I | partial | `validate:66` |
| `tools/quality/validation/check_layer3_gy_engine_census.py@307dabcb4` | I | yes | `validate:205` |
| `tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py@307dabcb4` | I | partial | `validate_payload:1172` |
| `tools/quality/validation/check_layer3_gy_foundry_breadth_audit.py@307dabcb4` | I | partial | `validate:104` |
| `tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py@307dabcb4` | I | partial | `validate_gy_lifecycle_registry:166` |
| `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py@307dabcb4` | I | partial | `validate:676` |
| `tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py@307dabcb4` | I | partial | `_validate_owner:249` |
| `tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py@307dabcb4` | I | partial | `validate:170` |
| `tools/quality/validation/check_layer3_gy_intervention_substrate_contract.py@307dabcb4` | I | partial | `validate:255` |
| `tools/quality/validation/check_layer3_gy_joint_simulation_horizon_contract.py@307dabcb4` | I | partial | `check:331` |
| `tools/quality/validation/check_layer3_gy_knowledge_substrate_contract.py@307dabcb4` | I | partial | `validate:569` |
| `tools/quality/validation/check_layer3_gy_lex_frontier_root_cause_audit.py@307dabcb4` | I | partial | `validate:257` |
| `tools/quality/validation/check_layer3_gy_loop_artifacts.py@307dabcb4` | I | partial | `validate:98` |
| `tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py@307dabcb4` | I | partial | `_validate:229` |
| `tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py@307dabcb4` | I | partial | `_inspection_report:453` |
| `tools/quality/validation/check_layer3_gy_n13b_acquisition_contract.py@307dabcb4` | I | partial | `_check_exact:830` |
| `tools/quality/validation/check_layer3_gy_openalex_artifacts.py@307dabcb4` | I | partial | `validate:207` |
| `tools/quality/validation/check_layer3_gy_p0_coverage_audit.py@307dabcb4` | I | partial | `validate:69` |
| `tools/quality/validation/check_layer3_gy_p1_substrate_authority_audit.py@307dabcb4` | I | partial | `validate:236` |
| `tools/quality/validation/check_layer3_gy_p2_semantic_evidence_quality_audit.py@307dabcb4` | I | partial | `validate:120` |
| `tools/quality/validation/check_layer3_gy_phase2_artifacts.py@307dabcb4` | I | partial | `validate:168` |
| `tools/quality/validation/check_layer3_gy_promotion_contract.py@307dabcb4` | I | partial | `validate:518` |
| `tools/quality/validation/check_layer3_gy_runtime_surface_audit.py@307dabcb4` | I | partial | `validate:183` |
| `tools/quality/validation/check_layer3_gy_second_domain_pack.py@307dabcb4` | I | partial | `_validate_gap_witnesses:5920` |
| `tools/quality/validation/check_layer3_gy_source_contract_admissibility_audit.py@307dabcb4` | I | partial | `validate:368` |
| `tools/quality/validation/check_layer3_gy_substrate_package_capability_inventory.py@307dabcb4` | I | partial | `validate:407` |
| `tools/quality/validation/check_layer3_gy_value_gate_contract.py@307dabcb4` | I | partial | `check_result:5724` |
| `tools/quality/validation/check_layer3_gy_value_outer_set_strangle_receipt.py@307dabcb4` | I | partial | `validate:174` |
| `tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py@307dabcb4` | I | partial | `validate:117` |
| `tools/quality/validation/check_layer3_gy_world_model_record_contract.py@307dabcb4` | I | partial | `validate:101` |
| `tools/quality/validation/check_layer3_time_source_authority.py@307dabcb4` | I | partial | `validate:79` |
| `tools/quality/validation/check_layer3_workflow_failure_authority.py@307dabcb4` | I | partial | `_read_workflow_execution:382` |
| `tools/quality/validation/check_multilingual_locale_census.py@307dabcb4` | I | yes | `measure_catalogues:107` |
| `tools/quality/validation/check_package_import_gates.py@307dabcb4` | I | partial | `_check_summary_blockers:363` |
| `tools/quality/validation/check_policy_design_case_capability_ratchet.py@307dabcb4` | I | partial | `validate_repo_reference:3662` |
| `tools/quality/validation/check_policy_design_case_cluster_ownership_map.py@307dabcb4` | I | partial | `_validate_open_cell_closures:657` |
| `tools/quality/validation/check_policy_design_case_drift.py@307dabcb4` | I | partial | `_capability_map_violations:251` |
| `tools/quality/validation/check_policy_design_case_formal_invariants.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/check_policy_design_case_layer2_readiness.py@307dabcb4` | I | partial | `_validate_minimal_seed:1431` |
| `tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py@307dabcb4` | I | partial | `_validate_missing_owner_negative_control:320` |
| `tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py@307dabcb4` | I | partial | `validate_s2_design_search:108` |
| `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py@307dabcb4` | I | partial | `validate_layer3_g0_readiness:160` |
| `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py@307dabcb4` | I | partial | `_validate_persisted_artifacts:176` |
| `tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:345` |
| `tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:353` |
| `tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:271` |
| `tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:312` |
| `tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:620` |
| `tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:510` |
| `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:347` |
| `tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py@307dabcb4` | I | partial | `_validate_written_artifact_set:354` |
| `tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py@307dabcb4` | I | partial | `build_measurement_replay_report:1063` |
| `tools/quality/validation/check_policy_design_case_pass1b_hardening.py@307dabcb4` | I | partial | `build_pass1b_hardening_payload:380` |
| `tools/quality/validation/check_policy_design_case_pass2_disposition.py@307dabcb4` | I | partial | `_validate_ledger:179` |
| `tools/quality/validation/check_policy_design_case_reuse_map.py@307dabcb4` | I | partial | `validate_reuse_map_payload:184` |
| `tools/quality/validation/check_policy_design_case_walking_skeleton.py@307dabcb4` | I | partial | `_ref_path:287` |
| `tools/quality/validation/check_policy_design_case_wave34_pass2.py@307dabcb4` | I | partial | `_validate_phase_index:162` |
| `tools/quality/validation/check_policy_design_case_wave35f_integrity.py@307dabcb4` | I | partial | `_validate_gap_ledger:215` |
| `tools/quality/validation/check_policy_design_case_wave35g_backfill.py@307dabcb4` | I | partial | `_validate_projection:120` |
| `tools/quality/validation/check_policy_design_case_wave35h_provenance.py@307dabcb4` | I | partial | `_validate_integrity_report:278` |
| `tools/quality/validation/check_policy_design_case_wave36_closeout.py@307dabcb4` | I | partial | `_validate_entry_criteria:97` |
| `tools/quality/validation/check_policy_design_case_wave40_readiness.py@307dabcb4` | I | partial | `_validate_readiness:112` |
| `tools/quality/validation/check_policy_design_formal_invariants.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/check_production_data_scenario_contracts.py@307dabcb4` | I | partial | `build_report:67` |
| `tools/quality/validation/check_production_data_substrate_registry_contract.py@307dabcb4` | I | partial | `validate:499` |
| `tools/quality/validation/check_production_invariant_registry.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/check_production_invocation.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/check_runtime_quality_schema_compatibility.py@307dabcb4` | I | yes | `_parse_first_jsonl_row:360` |
| `tools/quality/validation/check_substrate_drift.py@307dabcb4` | I | partial | `build_substrate_drift_payload:218` |
| `tools/quality/validation/check_trust_claim_posture.py@307dabcb4` | I | partial | `validate_register_against_live_sources:1420` |
| `tools/quality/validation/check_universal_corpus_annotations.py@307dabcb4` | I | partial | `build_report:40` |
| `tools/quality/validation/check_wave4_operational_closeout.py@307dabcb4` | I | partial | `_decision_log_findings:629` |
| `tools/quality/validation/checkout_guard.py@307dabcb4` | I | partial | `assert_current_checkout:33` |
| `tools/quality/validation/compare_honest_diagnostics_rebaseline.py@307dabcb4` | I | partial | `compare_rebaseline:46` |
| `tools/quality/validation/compare_policy_design_case_rebaseline.py@307dabcb4` | I | yes | `compare_rebaseline:61` |
| `tools/quality/validation/control_plane_supply_chain_contracts.py@307dabcb4` | I | partial | `_check_owner_mappings:342` |
| `tools/quality/validation/decomposition_preflight.py@307dabcb4` | I | partial | `validate_dynamic_imports:1080` |
| `tools/quality/validation/directory_health.py@307dabcb4` | I | partial | `build_report:96` |
| `tools/quality/validation/directory_hygiene_assets.py@307dabcb4` | I | partial | `_validate_contract:361` |
| `tools/quality/validation/empty_namespace_gate.py@307dabcb4` | I | partial | `_deep_import_findings:219` |
| `tools/quality/validation/execute_gy_n12_artifact_transition.py@307dabcb4` | I | yes | `build_measurement:548` |
| `tools/quality/validation/export_policy_evidence_capability_dcat.py@307dabcb4` | I | partial | `validate_dcat_export:80` |
| `tools/quality/validation/export_policy_evidence_capability_prov.py@307dabcb4` | I | partial | `validate_prov_turtle:103` |
| `tools/quality/validation/fabric_best_in_class_inventory.py@307dabcb4` | I | partial | `_status_if:318` |
| `tools/quality/validation/fabric_decision_data_coverage.py@307dabcb4` | I | partial | `build_report:147` |
| `tools/quality/validation/fabric_discovery_intelligence.py@307dabcb4` | I | partial | `validate_report:342` |
| `tools/quality/validation/fabric_processing_guarantees.py@307dabcb4` | I | partial | `validate_report:82` |
| `tools/quality/validation/fabric_product_integration.py@307dabcb4` | I | partial | `validate_report:462` |
| `tools/quality/validation/fabric_schema_governance.py@307dabcb4` | I | partial | `main:234` |
| `tools/quality/validation/fabric_source_contracts.py@307dabcb4` | I | partial | `validate_report:716` |
| `tools/quality/validation/fabric_wave2_strict_closure.py@307dabcb4` | I | partial | `validate_report:160` |
| `tools/quality/validation/generate_adr_index.py@307dabcb4` | I | partial | `main:736` |
| `tools/quality/validation/generate_foundry_phase2_evidence.py@307dabcb4` | writer | — | `—` |
| `tools/quality/validation/generate_policy_evidence_capability_cards.py@307dabcb4` | I | partial | `_acquisition_lines:191` |
| `tools/quality/validation/gy_acquisition_assurance_oracle.py@307dabcb4` | I | partial | `_compare:102` |
| `tools/quality/validation/gy_evidence_canon.py@307dabcb4` | utility | — | `—` |
| `tools/quality/validation/inspect_evidence_bundles.py@307dabcb4` | I | partial | `_inspect_target:367` |
| `tools/quality/validation/inspect_policy_evidence_capability_index.py@307dabcb4` | I | partial | `build_capability_index_inspection_report:95` |
| `tools/quality/validation/inventory_legacy_quality_evidence.py@307dabcb4` | I | yes | `_parse_first_jsonl_row:724` |
| `tools/quality/validation/layer3_gy_acquisition_executor.py@307dabcb4` | I | yes | `classify_worldbank_data_response:701` |
| `tools/quality/validation/layer3_gy_confidence_ledger_contract.py@307dabcb4` | I | partial | `_require_n13b_projection_coherence:679` |
| `tools/quality/validation/layer3_gy_n13a_acquisition_census.py@307dabcb4` | I | partial | `measure_reverse_demand:3234` |
| `tools/quality/validation/layer3_gy_n13b_acceptance.py@307dabcb4` | I | yes | `derive_acceptance_input_selection:1045` |
| `tools/quality/validation/layer3_gy_n13b_acquisition_contract.py@307dabcb4` | I | yes | `derive_local_lift_refusal:245` |
| `tools/quality/validation/layer3_gy_n13b_derivation_universality.py@307dabcb4` | I | yes | `_prove_unregistered_basis_refusal:929` |
| `tools/quality/validation/layer3_gy_n13b_reentry.py@307dabcb4` | I | partial | `derive_reentry_disposition:199` |
| `tools/quality/validation/locale_census_independent.py@307dabcb4` | I | partial | `read_locale_catalogues:136` |
| `tools/quality/validation/name_collision_gate.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/pass2_wave34_common.py@307dabcb4` | formatter | — | `—` |
| `tools/quality/validation/production_quality_evidence_inventory.py@307dabcb4` | I | partial | `check_artifacts:1408` |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py@307dabcb4` | I | partial | `main:521` |
| `tools/quality/validation/repository_best_in_class_phase0_7_inventory.py@307dabcb4` | I | partial | `_collect_adr_metadata:443` |
| `tools/quality/validation/repository_last_mile_inventory.py@307dabcb4` | I | partial | `check_artifacts:1546` |
| `tools/quality/validation/repository_last_mile_shim_callers.py@307dabcb4` | I | partial | `collect_shim_callers:403` |
| `tools/quality/validation/repository_structure_phase0.py@307dabcb4` | I | partial | `gate_pyproject_size:749` |
| `tools/quality/validation/repository_verification_inventory.py@307dabcb4` | I | partial | `_mirror_package:427` |
| `tools/quality/validation/run_benchmark_contours.sh@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/run_causal_phase_validation.sh@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/run_compilation_truthfulness_audit.py@307dabcb4` | I | partial | `_typed_compilation_blockers:392` |
| `tools/quality/validation/run_domain_coverage_critic_diversity_audit.py@307dabcb4` | I | partial | `_typed_domain_coverage_blockers:764` |
| `tools/quality/validation/run_fabric_best_in_class_inventory.sh@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/run_foundry_phase0_validation.sh@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/run_foundry_phase2_validation.sh@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/run_grounding_closeout_sweep.py@307dabcb4` | I | partial | `_run_byte_identity_check:230` |
| `tools/quality/validation/run_layer2_s14_universality_battery.py@307dabcb4` | I | partial | `_preflight_issues:419` |
| `tools/quality/validation/run_policy_design_case_bundle_replay_inspection.py@307dabcb4` | I | partial | `_component_blockers:541` |
| `tools/quality/validation/run_policy_design_case_cloud_one_lane_revalidation.py@307dabcb4` | I | partial | `_lane_blockers:323` |
| `tools/quality/validation/run_policy_design_case_local_validation_ladder.py@307dabcb4` | I | partial | `build_domain_coverage_metrics:740` |
| `tools/quality/validation/run_policy_design_case_pass2_phase34_3.py@307dabcb4` | I | partial | `_diagnose_pdd_044:535` |
| `tools/quality/validation/run_policy_design_case_pass2_phase34_4.py@307dabcb4` | I | partial | `_diagnose_pdd_100:121` |
| `tools/quality/validation/run_policy_design_case_pass2_phase34_5.py@307dabcb4` | I | partial | `_diagnose_pdd_046:136` |
| `tools/quality/validation/run_policy_design_case_pass2_phase34_6.py@307dabcb4` | I | partial | `_diagnose_pdd_034:135` |
| `tools/quality/validation/run_policy_design_case_rollout_decision.py@307dabcb4` | I | partial | `_required_phase_blockers:420` |
| `tools/quality/validation/run_universal_compilation_integration_realism_check.py@307dabcb4` | I | partial | `_argument_graph_observed:373` |
| `tools/quality/validation/run_universal_outcome_corpus.py@307dabcb4` | I | partial | `_summary:9199` |
| `tools/quality/validation/shared_grounding_world_cache.py@307dabcb4` | I | yes | `owner_change_probe:181` |
| `tools/quality/validation/trust_claim_posture_sources.py@307dabcb4` | I | partial | `_validate_producer_metadata_bindings:455` |
| `tools/quality/validation/universality_preflight.py@307dabcb4` | I | yes | `assert_repository_interpreter:53` |
| `tools/quality/validation/validate_foundry_phase0_closure.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/validate_foundry_phase2_closure.py@307dabcb4` | delegate | — | `—` |
| `tools/quality/validation/validate_phase_closure.py@307dabcb4` | delegate | — | `—` |
| `tools/registry.py@307dabcb4` | helper | — | `—` |
| `tools/research/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/benchmarks/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/benchmarks/bench_domain.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/bench_simulation.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/benchmark_lex_llm_steady_state.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/benchmark_lex_llm_sweep.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/build_release_summary.py@307dabcb4` | I | partial | `build_release_summary:138` |
| `tools/research/benchmarks/harness.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/jax/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/benchmarks/jax/bench_domain.py@307dabcb4` | I | partial | `run_benchmarks:117` |
| `tools/research/benchmarks/jax/bench_simulation.py@307dabcb4` | measurement_only | — | `—` |
| `tools/research/benchmarks/lex/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/benchmarks/lex/benchmark_lex_llm_steady_state.py@307dabcb4` | I | partial | `_summarize_rows:239` |
| `tools/research/benchmarks/lex/benchmark_lex_llm_sweep.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/metrics.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/prepare_real_benchmark_data.py@307dabcb4` | writer | — | `—` |
| `tools/research/benchmarks/run_all.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/run_all_benchmarks.sh@307dabcb4` | I | partial | `_run_benchmark:154` |
| `tools/research/benchmarks/run_local_sota_profile.py@307dabcb4` | delegate | — | `—` |
| `tools/research/benchmarks/run_local_sota_profile.sh@307dabcb4` | I | partial | `<embedded Python>:118` |
| `tools/research/benchmarks/run_parallel.py@307dabcb4` | I | partial | `_suite_status_from_artifacts:135` |
| `tools/research/benchmarks/suite_registry.py@307dabcb4` | delegate | — | `—` |
| `tools/research/demos/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/demos/run_export_demo.py@307dabcb4` | stub | — | `—` |
| `tools/research/demos/run_foundry_ws9_frontier_demo.py@307dabcb4` | delegate | — | `—` |
| `tools/research/demos/run_laffer_demo.py@307dabcb4` | I | partial | `main:135` |
| `tools/research/demos/run_mechanism_design.py@307dabcb4` | I | partial | `main:266` |
| `tools/research/demos/run_udf_hybrid_demo.py@307dabcb4` | I | partial | `main:20` |
| `tools/research/demos/run_udf_query_demo.py@307dabcb4` | I | partial | `main:17` |
| `tools/research/experiments/__init__.py@307dabcb4` | namespace | — | `—` |
| `tools/research/experiments/filter_topics.py@307dabcb4` | writer | — | `—` |
| `tools/research/experiments/organize_relevant_topics.py@307dabcb4` | writer | — | `—` |
| `tools/response_transition_oracle.py@307dabcb4` | I | partial | `expectation:45` |

## The 16 bounded disclosure witnesses

- `tools/ci/check_scientist_phase0_gate.py@307dabcb4`: JSON includes junit_sources, complete required_cases, category_results and missing-case notes for this bounded evidence selector.
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py@307dabcb4`: Bounded preflight report lists paths with exists/is_dir/bytes, imports with ok/error, GCS probe and LLM availability; yes is limited to this preflight witness.
- `tools/ops_runners/release/run_release_canary.py@307dabcb4`: Each probe output includes path, payload, expected and missing maps for the complete bounded PROBES set; transport exceptions are handled by main.
- `tools/quality/testing/check_fabric_exception_baseline.py@307dabcb4`: MEASUREMENT_SCOPE gives source root, all-file-type/rg-visible boundary and omitted semantics before count/digest outcome.
- `tools/quality/validation/check_layer3_gy_engine_census.py@307dabcb4`: JSON names sole census input, row_count and distributions; diagnostics refer to its exact rows. Text mode omits input path.
- `tools/quality/validation/check_multilingual_locale_census.py@307dabcb4`: Explicit path/file-type/file denominator,catalogue rows,implementation hashes and bounded interpretation emitted.
- `tools/quality/validation/check_runtime_quality_schema_compatibility.py@307dabcb4`: Report names repo_root,source_roots,readers and every discovered file/reader row with read_status/parse_error.
- `tools/quality/validation/compare_policy_design_case_rebaseline.py@307dabcb4`: Report current/previous coverage refs and per-metric comparison categories expose the bounded comparison inputs.
- `tools/quality/validation/execute_gy_n12_artifact_transition.py@307dabcb4`: Measurement carries source freeze,changed/deployment intersection,tool,target/protected path states and denominator hashes; measure mode is diagnostic despite transition-writing modes.
- `tools/quality/validation/inventory_legacy_quality_evidence.py@307dabcb4`: Inventory includes rules/source roots and all discovered entries with path,read_status,classification,reasons plus content-safety bounds.
- `tools/quality/validation/layer3_gy_acquisition_executor.py@307dabcb4`: Typed classification binds body_sha256 and byte_count to disposition,row_count,api_message_count; metadata output adds exact indicator and coverage disclosure.
- `tools/quality/validation/layer3_gy_n13b_acceptance.py@307dabcb4`: Typed selection carries baseline/census/registry identities,complete disposition denominators,rejections and selected/absent inputs.
- `tools/quality/validation/layer3_gy_n13b_acquisition_contract.py@307dabcb4`: Result binds census-backlog projection hash,provision ID,trust anchor,all rows and denominator/admissible counts.
- `tools/quality/validation/layer3_gy_n13b_derivation_universality.py@307dabcb4`: Receipt includes registry/catalog hashes,country/full series denominator,family proofs and exact refusal code/reason.
- `tools/quality/validation/shared_grounding_world_cache.py@307dabcb4`: Probe result explicitly identifies original/changed keys,miss boolean,stale rejection and pass/fail.
- `tools/quality/validation/universality_preflight.py@307dabcb4`: Interpreter error explicitly names observed,exec,expected,base prefixes and executable; success preflight returns package path/backend availability record.

## Replays and retained evidence

These are commissioned research replayers, not new production commands. The
non-test consumer is this lane's research/architecture handback; the journal
invokes them from product root. They remain in gitignored raw scratch because
this is a pinned one-off census, not an installed semantic-verification service.

`python3 docs/superpowers/journals/measurement-plane/row1/raw/review.py init`
reconciles source membership at the base (run on that pinned tree, before source
edits); `complete_structure.py` and `typescript_structure.cjs` retain full ASTs.
`adjudicate_a.py` and `compile_adjudication_b.py` record the reviewed decisions;
`validate_adjudication_a.py` and root's merged validation check identities and
witness positions. Authored role decisions are review, not a semantic oracle.
The complete per-emitter data-flow/output facts remain in the two adjudications.

Raw evidence SHA-256 identities:

- `docs/superpowers/journals/measurement-plane/row1/raw/population.json@99c02ec86ae3f29bc6bf9da8aef71450cc546f9bbe84a64a612f37c5995bfea9`
- `docs/superpowers/journals/measurement-plane/row1/raw/denominator.json@8bc76ab6459b319b73d8da0deabffa18fba40ca596e283f5fc3b00c84e5ba475`
- `docs/superpowers/journals/measurement-plane/row1/raw/complete_structure.py@4f61cbca6aa705c021e0ca30487a26c26adbb602e6f7c7cfb913785dde0da94d`
- `docs/superpowers/journals/measurement-plane/row1/raw/complete_structure.json@4c502e793b5bb5eaca334ea074f0219d5c43a35e3c27a7e2f8085ec749d9760e`
- `docs/superpowers/journals/measurement-plane/row1/raw/typescript_structure.cjs@64b34a21581d244cd64a4d8db48dab6cc3e099f6310b7cc380131509e6e0bc81`
- `docs/superpowers/journals/measurement-plane/row1/raw/typescript_structure.json@e24d26ac0233f48d58f2ec5740f7880bb3124b1fe20ed827f3c6c6833d58a2d4`
- `docs/superpowers/journals/measurement-plane/row1/raw/adjudication-a.json@5db13aee7ed02c6a53b8644914de9740ada91cf786def412d3fc060b31615d72`
- `docs/superpowers/journals/measurement-plane/row1/raw/adjudication-b.json@c4e2f34b5d737d3cd90a72ad17e83a6ad892621d56b33308dc932d3f3242e9df`
- `docs/superpowers/journals/measurement-plane/row1/raw/adjudication-merged.json@c99ddc01e1f9eae3fa250223194357ea15e4dd84563d16bec55793075c1c28ca`
- `docs/superpowers/journals/measurement-plane/row1/raw/adjudication-validation.json@d505e9353f69d774e89f8e5d9bfb278a3d58da79da20e3ea0095bdedbd103440`
- `docs/superpowers/journals/measurement-plane/row1/raw/atlas-plan-admission-baseline.json@796f90c67ccaa9e37e7624feb726c93a635d4ca210c678546edeebe6c8a18539`
