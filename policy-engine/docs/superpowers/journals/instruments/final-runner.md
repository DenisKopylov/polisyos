# Literal targeted replay runner

Working directory: `/Users/deniskopylov/polisyos/.worktrees/instrument-honesty/policy-engine`.
Each code block is one process invocation. Redirection preserves its status; do not append an echo or chain another command. These are replay commands, not all-green claims. The completion journal and raw receipt indexes give actual observed outcomes. Replays write separate `replay-*` logs so deciding evidence is retained.
This is a one-off receipt replay document, not a new production instrument or path-only executable. All product gates below use existing registered commands. Parameterized selectors intentionally execute every declared case. The dashboard full coverage command is the sole full-suite exception.

## invocation-final-tests

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/runtime/quality/test_production_invocation.py::test_cli_reports_test_only_verifier_and_persists_negative \
  tests/unit/runtime/quality/test_production_invocation.py::test_import_annotation_and_orphan_helper_do_not_supply_a_runnable_caller \
  tests/unit/runtime/quality/test_production_invocation.py::test_class_construction_does_not_invoke_its_verification_method \
  tests/unit/runtime/quality/test_production_invocation.py::test_removing_a_call_from_a_previously_reached_mechanism_is_a_regression \
  tests/unit/runtime/quality/test_production_invocation.py::test_named_deferral_is_explicit_and_never_a_static_path \
  tests/unit/runtime/quality/test_production_invocation.py::test_parameter_shadowing_does_not_turn_an_import_into_a_production_call \
  tests/unit/runtime/quality/test_production_invocation.py::test_recursion_and_literal_false_entry_do_not_establish_invocation \
  tests/unit/runtime/quality/test_production_invocation.py::test_executable_script_registration_is_a_root_but_test_script_is_not \
  tests/unit/runtime/quality/test_production_invocation.py::test_lexical_definitions_survive_entry_and_statement_containers \
  tests/unit/runtime/quality/test_production_invocation.py::test_registration_receivers_are_uncertain_without_hiding_a_direct_orphan \
  tests/unit/runtime/quality/test_production_invocation.py::test_test_registration_and_plain_annotations_do_not_exempt_orphans \
  tests/unit/runtime/quality/test_production_invocation.py::test_removed_direct_call_cannot_be_replaced_by_callback_registration \
  tests/unit/runtime/quality/test_production_invocation.py::test_dynamic_receiver_site_is_unmeasured_without_inventing_its_target \
  tests/unit/runtime/quality/test_production_invocation.py::test_cli_discloses_partial_coverage_and_unrun \
  tests/unit/runtime/quality/test_production_invocation.py::test_unified_cli_discovers_the_production_invocation_command \
  tests/unit/runtime/quality/test_production_invocation.py::test_deferred_expression_bodies_do_not_supply_direct_invocation_paths \
  tests/unit/runtime/quality/test_production_invocation.py::test_deferred_function_bodies_stop_direct_paths_with_lexical_yield_detection \
  tests/unit/runtime/quality/test_production_invocation.py::test_conditional_expressions_share_declaration_and_call_walk_domains \
  tests/unit/runtime/quality/test_production_invocation.py::test_internal_measurement_failure_is_unrun_without_admitting_a_stale_receipt >docs/superpowers/journals/instruments/root/raw/replay-invocation-final-tests.log 2>&1
```

## ci-scanners-final-tests

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_gate_builds_passing_json_report \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_gate_matches_parametrized_cases_for_required_names \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_gate_fails_on_missing_evidence_and_broad_handlers \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_copy_scan_uses_ast_and_reports_unresolved_calls \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_absent_or_malformed_source_is_unrun \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_broad_handler_scan_ignores_comments_and_includes_tuples \
  tests/repo_quality/tools/test_scientist_phase1_gate.py::test_scientist_phase1_qualified_handler_is_explicitly_unmeasured \
  tests/repo_quality/tools/test_fabric_exception_baseline.py::test_fabric_exception_baseline_missing_source_is_unrun \
  tests/repo_quality/tools/test_fabric_exception_baseline.py::test_fabric_exception_baseline_names_unmeasured_handler_syntax \
  tests/repo_quality/tools/test_fabric_exception_baseline.py::test_fabric_exception_baseline_unavailable_scanner_is_unrun >docs/superpowers/journals/instruments/root/raw/replay-ci-scanners-final-tests.log 2>&1
```

## ci-fabric-final-behavior

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/fabric/test_world_store.py::test_write_world_fact_segment_roundtrip \
  tests/unit/fabric/test_world_store.py::test_append_world_segment_index_uses_injected_observability_providers \
  tests/unit/fabric/test_world_store.py::test_invalid_world_segment_index_fails_closed \
  tests/unit/fabric/test_world_store.py::test_gc_world_segments_keeps_latest_and_unapplied \
  tests/unit/fabric/test_world_store.py::test_world_manifest_validator_assertion_is_not_translated \
  tests/unit/fabric/test_world_store.py::test_world_segment_metrics_never_publish_zero_for_unreadable_index \
  tests/unit/fabric/test_world_store.py::test_world_segment_gc_retains_invalid_time_but_propagates_assertions \
  tests/unit/fabric/test_world_time_travel.py::test_world_branch_merge_applies_branch_head_without_manual_rebuild \
  tests/unit/fabric/test_world_time_travel.py::test_world_branch_merge_fail_on_conflicting_world_kind \
  tests/unit/fabric/test_world_time_travel.py::test_world_branch_merge_target_wins_on_conflicting_world_kind \
  tests/unit/fabric/test_world_time_travel.py::test_world_branch_merge_uses_backend_transaction_and_rolls_back_programmer_error >docs/superpowers/journals/instruments/root/raw/replay-ci-fabric-final-behavior.log 2>&1
```

## tests/repo_quality/architecture/test_repository_structure_station_inputs.py

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_ignored_and_untracked_state_does_not_change_commit_verdict \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_default_refuses_committed_output_even_when_directory_is_ignored \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_missing_tracked_input_is_reported_instead_of_disappearing \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_untracked_policy_and_catalog_peer_cannot_change_gate_inputs \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_required_configuration_cannot_be_supplied_by_the_station \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_pyproject_reports_physical_measurement_and_semantic_omissions \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_missing_pyproject_is_unrun_even_when_report_only \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_registered_pyproject_command_prints_omissions_on_clean_input \
  tests/repo_quality/architecture/test_repository_structure_station_inputs.py::test_malformed_gate_policy_is_unrun_instead_of_a_traceback >docs/superpowers/journals/instruments/root/raw/replay-tests-repo_quality-architecture-test_repository_structure_station_inputs-py.log 2>&1
```

## tests/repo_quality/architecture/test_package_import_measurement.py

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/repo_quality/architecture/test_package_import_measurement.py::test_missing_local_mount_is_named_unmeasured \
  tests/repo_quality/architecture/test_package_import_measurement.py::test_missing_required_root_remains_a_finding \
  tests/repo_quality/architecture/test_package_import_measurement.py::test_ignored_python_is_excluded_with_a_named_tracked_denominator \
  tests/repo_quality/architecture/test_package_import_measurement.py::test_missing_contract_is_unrun_even_without_fail_closed \
  tests/repo_quality/architecture/test_package_import_measurement.py::test_unavailable_git_denominator_does_not_become_an_empty_scan >docs/superpowers/journals/instruments/root/raw/replay-tests-repo_quality-architecture-test_package_import_measurement-py.log 2>&1
```

## tests/repo_quality/tools/test_instrument_input_scope.py

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_without_yaml_reports_unrun \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_invalid_publication_scope_is_unrun \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_clean_output_names_unmeasured_semantics \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_existing_unpublished_target_is_a_real_failure \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_partially_malformed_scope_is_unrun \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_docs_unsupported_link_forms_are_explicitly_unmeasured \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_directory_missing_contract_is_unrun \
  tests/repo_quality/tools/test_instrument_input_scope.py::test_directory_git_failure_is_not_an_empty_inventory >docs/superpowers/journals/instruments/root/raw/replay-tests-repo_quality-tools-test_instrument_input_scope-py.log 2>&1
```

## tests/repo_quality/tools/test_runtime_contract_measurement.py

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/repo_quality/tools/test_runtime_contract_measurement.py::test_skipped_client_check_is_named_in_clean_output \
  tests/repo_quality/tools/test_runtime_contract_measurement.py::test_missing_openapi_comparator_is_unrun \
  tests/repo_quality/tools/test_runtime_contract_measurement.py::test_failed_client_process_retains_prior_findings_as_partial >docs/superpowers/journals/instruments/root/raw/replay-tests-repo_quality-tools-test_runtime_contract_measurement-py.log 2>&1
```

## tests/unit/common/test_llm_json.py

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/common/test_llm_json.py::test_extract_llm_json_object_accepts_think_prefixed_json \
  tests/unit/common/test_llm_json.py::test_extract_llm_json_object_accepts_fenced_json \
  tests/unit/common/test_llm_json.py::test_extract_llm_json_object_rejects_invalid_response \
  tests/unit/common/test_llm_json.py::test_extract_llm_json_object_rejects_non_object \
  tests/unit/common/test_llm_json.py::test_extract_llm_json_keeps_generic_array_contract \
  tests/unit/common/test_llm_json.py::test_json_extraction_uses_the_canonical_serialization_owner >docs/superpowers/journals/instruments/root/raw/replay-tests-unit-common-test_llm_json-py.log 2>&1
```

## ci-owner-seams-red

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_consults_injected_registry_and_reopens_injected_store \
  tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_does_not_fall_back_when_injected_profile_is_absent \
  tests/unit/fabric/connectors/sources/test_http_connector_base.py::test_connection_config_redaction_preserves_arbitrary_credential_keys_without_values \
  tests/unit/fabric/connectors/sources/test_http_connector_base.py::test_connection_config_rejects_unavailable_scanner_shape >docs/superpowers/journals/instruments/root/raw/replay-ci-owner-seams-red.log 2>&1
```

## ci-owner-seams-green-first

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/runtime/http/test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation \
  tests/unit/runtime/http/test_architecture_boundaries.py::test_runtime_control_paths_do_not_resolve_registry_singletons_inline \
  tests/unit/runtime/http/test_api_maturity.py::test_runtime_container_accepts_typed_test_overrides \
  tests/unit/runtime/http/test_api_maturity.py::test_runtime_security_middlewares_receive_injected_metrics_provider \
  tests/unit/fabric/connectors/sources/test_http_connector_base.py::test_connection_config_redaction_uses_shared_secret_pii_scanner \
  tests/unit/fabric/connectors/test_protocol_compliance.py::TestConnectionConfig::test_redacted_hides_credentials >docs/superpowers/journals/instruments/root/raw/replay-ci-owner-seams-green-first.log 2>&1
```

## ci-owner-boundary-review

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_rejects_an_injected_store_with_different_artifact_backing \
  tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_uses_orchestration_and_returns_reopenable_one_call_evidence \
  tests/unit/runtime/quality/test_live_acquisition_executor.py::test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport >docs/superpowers/journals/instruments/root/raw/replay-ci-owner-boundary-review.log 2>&1
```

## ci-factory-custody-red

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/core/artifacts/backends/test_config.py::TestBuildArtifactStore::test_filesystem_backend_preserves_tenant_and_cell_custody \
  tests/unit/core/artifacts/backends/test_config.py::TestBuildArtifactStore::test_non_filesystem_backend_rejects_explicit_ownership_scope >docs/superpowers/journals/instruments/root/raw/replay-ci-factory-custody-red.log 2>&1
```

## ci-factory-custody-green

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/core/artifacts/backends/test_config.py::TestBuildArtifactStore::test_filesystem_backend_receives_injected_providers >docs/superpowers/journals/instruments/root/raw/replay-ci-factory-custody-green.log 2>&1
```

## ci-cas-importers-final

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  tests/unit/runtime/http/test_public_decision_verification_configuration.py::test_configured_keys_issue_and_reverify_persisted_report \
  tests/unit/runtime/quality/test_acquisition_epoch_admission.py::test_cli_consumes_actual_persisted_policy_refusal \
  tests/unit/runtime/quality/test_acquisition_planner.py::test_real_owner_gateway_records_local_skg_response_without_network \
  tests/unit/runtime/quality/test_adaptation_transition.py::test_unsigned_request_fails_safe_and_names_role \
  tests/unit/runtime/quality/test_confidence_ledger.py::test_canonical_authority_reopen_continues_one_budget_head \
  tests/unit/runtime/quality/test_epoch_custody_audit.py::test_cli_persists_both_unappointed_roles \
  tests/unit/runtime/quality/test_generation_cycle.py::test_controller_runs_counterexample_driven_revision_over_two_real_cycles \
  tests/unit/runtime/quality/test_grounding_calibration.py::test_actual_proof_world_pin_replays_original_bytes_time_and_structural_reference \
  tests/unit/runtime/quality/test_grounding_risk.py::test_restart_and_missing_head_cannot_reset_spend \
  tests/unit/runtime/quality/test_intervention_substrate.py::test_law_bound_lever_traces_real_l3_threshold_and_blocks_violating_value \
  tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_ring1_event_bundle_to_cas \
  tests/unit/runtime/quality/test_workspace_foundry_consumption.py::test_foundry_consumer_replays_actual_method_owner_and_preserves_raw_byte_custody \
  tests/unit/runtime/quality/test_workspace_foundry_consumption.py::test_actual_phase2_loop_records_constraint_refusal_before_earlier_source_block >docs/superpowers/journals/instruments/root/raw/replay-ci-cas-importers-final.log 2>&1
```

## common-json-importers

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/unit/runtime/quality/test_design_generation.py::test_drafter_shared_parser_accepts_recorded_think_prefixed_json \
  tests/unit/runtime/quality/test_design_generation.py::test_drafter_uses_mock_fallback_only_when_no_json_object_exists \
  tests/unit/scientist/agent/test_drafter_parsing.py::TestParseCritiquePayload::test_invalid_json \
  tests/unit/scientist/agent/test_drafter_parsing.py::TestParseCritiquePayload::test_think_prefixed_json \
  tests/unit/scientist/agent/test_drafter_parsing.py::TestParseConsolidatedDraft::test_think_prefixed_json_preserves_raw_response >docs/superpowers/journals/instruments/root/raw/replay-common-json-importers.log 2>&1
```

## tracked-root-existing-negative

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase7_undocumented_top_level_namespace_root_fails >docs/superpowers/journals/instruments/root/raw/replay-tracked-root-existing-negative.log 2>&1
```

## generated-docs

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/repo_quality/tools/test_tool_config_split.py::test_phase5_5_tool_config_split_generated_files_are_current \
  tests/repo_quality/tools/test_tool_config_split.py::test_phase5_5_dead_override_report_reads_generated_configs \
  tests/repo_quality/tools/test_docs_gate.py::test_docs_accuracy_follows_mkdocs_inherit_for_published_nav \
  tests/repo_quality/tools/test_docs_gate.py::test_docs_accuracy_treats_not_in_nav_as_publishable \
  tests/repo_quality/tools/test_docs_gate.py::test_docs_accuracy_rejects_planning_docs_in_nav \
  tests/repo_quality/tools/test_docs_gate.py::test_docs_command_check_fails_on_drift >docs/superpowers/journals/instruments/root/raw/replay-generated-docs.log 2>&1
```

## types-producer

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_shared_client_generation_is_package_owned_and_version_pinned \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_client_package_entrypoints_generate_only_in_scratch \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_openapi_typescript_output_matches_committed_shared_types >docs/superpowers/journals/instruments/root/raw/replay-types-producer.log 2>&1
```

## canary-orchestration

```sh
.venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/repo_quality/tools/test_canary_matrix.py::test_local_canary_runner_accepts_profile_specific_matrix_args \
  tests/repo_quality/tools/test_canary_matrix.py::test_real_canary_matrix_runs_deterministic_subset_and_writes_lane_summaries \
  tests/repo_quality/tools/test_canary_matrix.py::test_real_canary_matrix_fails_lane_when_scorecard_fails \
  tests/repo_quality/tools/test_canary_matrix.py::test_live_provider_lane_requires_credentials_and_explicit_flag >docs/superpowers/journals/instruments/root/raw/replay-canary-orchestration.log 2>&1
```

## mutation-protocol

```sh
.tmp/instrument-mutation-venv/bin/python \
  -m \
  pytest \
  -q \
  -s \
  tests/repo_quality/tools/test_mutation.py::test_declared_native_station_is_unrun_before_subprocess \
  tests/repo_quality/tools/test_mutation.py::test_controlled_protocol_admission_consumes_outcomes_and_rejects_corruption \
  tests/repo_quality/tools/test_mutation.py::test_missing_declared_source_never_becomes_empty_success \
  tests/repo_quality/tools/test_phase4_consolidation.py::test_mutation_tool_scientist_all_aggregates_failures >docs/superpowers/journals/instruments/root/raw/replay-mutation-protocol.log 2>&1
```

## Registered instruments and retained removal probe

Run the invocation recomputation after generation and with unchanged tracked Python inputs. Interpret its exit 1/3 as findings, not receipt mismatch; exit 2 signals UNRUN or drift. The retained removal probe calls the real test, retaining subprocess success while skipping normalization. It is ignored local evidence rather than another registered product tool.

### invocation-generate

```sh
.venv/bin/polisyos-tools validation check-production-invocation --repo-root . --base cc74d6581 --receipt docs/superpowers/journals/instruments/invocation/raw/replay-production-invocation-final.json >docs/superpowers/journals/instruments/root/raw/replay-invocation-generate.log 2>&1
```

### invocation-recompute

```sh
.venv/bin/polisyos-tools validation check-production-invocation --repo-root . --base cc74d6581 --receipt docs/superpowers/journals/instruments/invocation/raw/replay-production-invocation-final-rechecked.json --check docs/superpowers/journals/instruments/invocation/raw/replay-production-invocation-final.json >docs/superpowers/journals/instruments/root/raw/replay-invocation-recompute.log 2>&1
```

### scientist-final-command

```sh
.venv/bin/polisyos-tools ci check-scientist-phase1-gate --repo-root . --benchmark-json docs/superpowers/journals/instruments/invocation/raw/ci-scientist-original/scientist-phase1-benchmarks.json --junit-xml docs/superpowers/journals/instruments/invocation/raw/ci-scientist-original/scientist-phase1.xml --output docs/superpowers/journals/instruments/invocation/raw/replay-ci-scientist-final.json --require-passing >docs/superpowers/journals/instruments/root/raw/replay-scientist-final-command.log 2>&1
```

### fabric-final-command

```sh
.venv/bin/polisyos-tools testing check-fabric-exception-baseline >docs/superpowers/journals/instruments/root/raw/replay-fabric-final-command.log 2>&1
```

### package-import

```sh
.venv/bin/polisyos-tools validation check-package-import-gates --fail-closed >docs/superpowers/journals/instruments/root/raw/replay-package-import.log 2>&1
```

### directory

```sh
.venv/bin/polisyos-tools validation directory-health --fail-on-regression --fail-on-findings >docs/superpowers/journals/instruments/root/raw/replay-directory.log 2>&1
```

### architecture

```sh
.venv/bin/polisyos-tools architecture guardrails check >docs/superpowers/journals/instruments/root/raw/replay-architecture.log 2>&1
```

### docs-accuracy

```sh
.venv/bin/polisyos-tools validation check-docs-accuracy >docs/superpowers/journals/instruments/root/raw/replay-docs-accuracy.log 2>&1
```

### tools-reference

```sh
.venv/bin/polisyos-tools docs --check --output docs/reference/tools.md >docs/superpowers/journals/instruments/root/raw/replay-tools-reference.log 2>&1
```

### tool-configs

```sh
.venv/bin/polisyos-tools workspace tool-configs --check >docs/superpowers/journals/instruments/root/raw/replay-tool-configs.log 2>&1
```

### runtime-contract

```sh
.venv/bin/polisyos-tools runtime check-runtime-api-contract --max-diff-lines 100000 >docs/superpowers/journals/instruments/root/raw/replay-runtime-contract.log 2>&1
```

### runtime-unrun-negative

```sh
.venv/bin/polisyos-tools runtime check-runtime-api-contract --openapi docs/superpowers/journals/instruments/root/raw/absent-comparison.openapi.json >docs/superpowers/journals/instruments/root/raw/replay-runtime-unrun-negative.log 2>&1
```

### types-normalizer-removal

```sh
env PYTHONPATH=src:. .venv/bin/python docs/superpowers/journals/instruments/root/raw/types-normalizer-removal-probe.py >docs/superpowers/journals/instruments/root/raw/replay-types-normalizer-removal.log 2>&1
```

## Dashboard full coverage exception

Working directory: `policy-engine/apps/runtime-dashboard` within this worktree.
No per-directory Python suite or backend/CI-parity command is authorized.
The full suite uses the unchanged coverage include/exclude set and statement
floor. Its verbose raw output names every executed test, including the three
original CI files: `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts`,
`src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts`, and
`src/shared/lib/domain/workflow.test.ts`.

```sh
corepack pnpm exec vitest run --coverage --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=verbose >../../docs/superpowers/journals/instruments/coverage/raw/replay-full-vitest-coverage.log 2>&1
```

## Exact changed-Python lint denominator

```sh
.venv/bin/python -m ruff check src/polisyos/common/serialization.py src/polisyos/core/artifacts/backends/config.py src/polisyos/fabric/connectors/base.py src/polisyos/fabric/world/store/segments.py src/polisyos/fabric/world/store/snapshots.py src/polisyos/runtime/http/services/public_decision_verification_configuration.py src/polisyos/runtime/quality/acquisition_epoch_admission.py src/polisyos/runtime/quality/acquisition_executor.py src/polisyos/runtime/quality/acquisition_planner.py src/polisyos/runtime/quality/adaptation_transition.py src/polisyos/runtime/quality/confidence_ledger.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/epoch_custody_audit.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/grounding_calibration.py src/polisyos/runtime/quality/grounding_risk.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/production_invocation.py src/polisyos/runtime/quality/workspace/agent_proposal_bridge.py src/polisyos/runtime/quality/workspace/foundry_consumption.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/scientist/agent/_drafter_parsing.py src/polisyos/scientist/agent/code_verifier.py src/polisyos/scientist/agent/critic.py src/polisyos/scientist/agent/data_need_extractor.py src/polisyos/scientist/agent/drafter_clients.py src/polisyos/scientist/agent/formalizer.py src/polisyos/scientist/agent/pi.py src/polisyos/scientist/methods/discovery/workers/__init__.py src/polisyos/scientist/policy_design/adversary.py src/polisyos/scientist/policy_design/translator.py src/polisyos/scientist/validation/citation_faithfulness.py src/polisyos/scientist/validation/policy_verified/service.py tests/repo_quality/architecture/test_package_import_measurement.py tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py tests/repo_quality/architecture/test_repository_structure_station_inputs.py tests/repo_quality/tools/test_fabric_exception_baseline.py tests/repo_quality/tools/test_instrument_input_scope.py tests/repo_quality/tools/test_runtime_contract_measurement.py tests/repo_quality/tools/test_scientist_phase1_gate.py tests/unit/common/test_llm_json.py tests/unit/core/artifacts/backends/test_config.py tests/unit/fabric/connectors/sources/test_http_connector_base.py tests/unit/fabric/connectors/test_protocol_compliance.py tests/unit/fabric/test_world_store.py tests/unit/fabric/test_world_time_travel.py tests/unit/runtime/http/test_api_maturity.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/quality/test_live_acquisition_executor.py tests/unit/runtime/quality/test_production_invocation.py tools/ci/check_scientist_phase1_gate.py tools/ops_runners/runtime/check_runtime_api_contract.py tools/quality/testing/check_fabric_exception_baseline.py tools/quality/validation/check_docs_accuracy.py tools/quality/validation/check_package_import_gates.py tools/quality/validation/check_production_invocation.py tools/quality/validation/directory_health.py tools/quality/validation/repository_structure_phase0.py >docs/superpowers/journals/instruments/root/raw/replay-changed-python-ruff.log 2>&1
```

## Pyproject physical-volume gate

Working directory: product root. This remains a measured rejection against the
unchanged 300-line budget; UNRUN is reserved for unavailable structural inputs.

```sh
.venv/bin/polisyos-tools validation repository-structure-phase0 gate --gate pyproject_size --mode fail-closed >docs/superpowers/journals/instruments/root/raw/replay-pyproject-volume.log 2>&1
```

## Dashboard report admission

Working directory: `policy-engine/apps/runtime-dashboard`. Run after full coverage;
missing/inconsistent reports must produce UNRUN, not a below-floor verdict.

```sh
node ./scripts/check-coverage-ratchet.mjs >../../docs/superpowers/journals/instruments/coverage/raw/replay-coverage-ratchet.log 2>&1
```

## Dashboard focused behavioral nodes

Working directory: `policy-engine/apps/runtime-dashboard`. The complete literal TypeScript AST-selected set is listed below; the command runs these four files, including every named case.

- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > passes a complete reconciled report while naming unmeasured properties
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > fails a complete measured shortfall without calling it unrun
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > reports a missing summary as unrun with no complete verdict
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects a green self-consistent subset that omitted an included source file
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects malformed JSON without leaking an uncaught parser exception
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects a forged percentage even when it exceeds the floor
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects aggregate counts that do not reconcile with the file records
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects an aliased duplicate record instead of double-counting its source
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > reports a missing metric as unmeasured rather than a coverage shortfall
- `scripts/check-coverage-ratchet.test.ts` — coverage ratchet measurement verdict > rejects invalid tolerance instead of silently passing a measured shortfall
- `src/app/layout/GlobalShortcuts.test.tsx` — GlobalShortcuts component contract > navigates through registered keyboard actions and removes them on unmount
- `src/app/layout/GlobalShortcuts.test.tsx` — GlobalShortcuts component contract > shows discoverable shortcut help while preserving ordinary typing
- `src/app/layout/GlobalShortcuts.test.tsx` — GlobalShortcuts component contract > persists sidebar and density actions and applies theme changes
- `src/app/layout/GlobalShortcuts.test.tsx` — GlobalShortcuts component contract > moves focus within the active list without wrapping or stealing input keys
- `src/features/runs/components/ReproduceRunButton.test.tsx` — ReproduceRunButton component contract > requires confirmation and permits cancellation without starting a run
- `src/features/runs/components/ReproduceRunButton.test.tsx` — ReproduceRunButton component contract > submits the source parameters once and shows the returned run after completion
- `src/features/runs/components/ReproduceRunButton.test.tsx` — ReproduceRunButton component contract > exposes a failed reproduction and allows dismissal before retry
- `src/features/runs/components/ReproduceRunButton.test.tsx` — ReproduceRunButton component contract > does not offer confirmation while reproduction is disabled
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > keeps scenario and temporal selection in both the real request and cache identity
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > does not request unknown runs or explicitly disabled scenario lists
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > returns an admitted scenario list without inventing an absent temporal selection
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > preserves an unavailable scenario response as an error rather than empty support
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > rejects malformed successful scenario data instead of admitting it to consumers
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > binds capability requests to the selected scenario and temporal scope
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > keeps unknown or disabled capability queries idle
- `src/api/hooks/useScenarioCapabilities.test.tsx` — scenario query admission > keeps unavailable capabilities distinguishable from an empty supported result

```sh
corepack pnpm exec vitest run scripts/check-coverage-ratchet.test.ts src/app/layout/GlobalShortcuts.test.tsx src/features/runs/components/ReproduceRunButton.test.tsx src/api/hooks/useScenarioCapabilities.test.tsx --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=verbose >../../docs/superpowers/journals/instruments/coverage/raw/replay-focused-behavior.log 2>&1
```

## Grounding restart under declared solver provisioning

Working directory: product root. This separate frozen environment includes the `solvers` extra; import availability is a prerequisite, not an admission or restart verdict.

```sh
.tmp/instrument-solvers-venv/bin/python -m pytest tests/unit/runtime/quality/test_grounding_risk.py::test_restart_and_missing_head_cannot_reset_spend -vv >docs/superpowers/journals/instruments/coverage/raw/replay-grounding-risk-provisioned.log 2>&1
```

## Copied generated-config corruption

This retained one-off probe derives its full file set from the canonical producer, corrupts isolated copies, and invokes the existing byte-drift consumer. It never alters governed files.

```sh
env PYTHONPATH=src:. .venv/bin/python docs/superpowers/journals/instruments/root/raw/tool-config-corruption-probe.py >docs/superpowers/journals/instruments/root/raw/replay-tool-config-corruption.log 2>&1
```

## Canonical generated surfaces

Run writes into ignored replay scratch; the committed-source checks independently decide freshness. These commands consume declared generated-artifact inputs. Register prose is compiler input, not evidence about current runtime behavior.

```sh
.venv/bin/polisyos-tools runtime export-runtime-openapi --output docs/superpowers/journals/instruments/root/raw/replay-runtime_api_v1.openapi.json >docs/superpowers/journals/instruments/root/raw/replay-openapi-export.log 2>&1
```

```sh
.venv/bin/polisyos-tools validation check-trust-claim-posture --repo-root . --write --output-root docs/superpowers/journals/instruments/root/raw/replay-trust-regenerated --json >docs/superpowers/journals/instruments/root/raw/replay-trust-regeneration.log 2>&1
```

```sh
.venv/bin/polisyos-tools validation check-trust-claim-posture --repo-root . --check --json >docs/superpowers/journals/instruments/root/raw/replay-trust-check.log 2>&1
```

```sh
.venv/bin/polisyos-tools validation check-trust-claim-posture --repo-root . --corrupt-field-drift-check --json >docs/superpowers/journals/instruments/root/raw/replay-trust-corrupt-field.log 2>&1
```

## Current-slice documentation impact predicates

This one-off probe executes the existing planner against the complete committed slice delta. It explicitly emits every unrun child command; it does not replace the full docs workflow or establish historical range closure.

```sh
env PYTHONPATH=src:. .venv/bin/python docs/superpowers/journals/instruments/root/raw/docs-impact-probe.py >docs/superpowers/journals/instruments/root/raw/replay-docs-impact-plan.log 2>&1
```
