"""List or explicitly run the GY lane's bounded verification commands.

Run from policy-engine: .venv/bin/python <this-file> [--group GROUP ...] --run.
Without --run this only lists commands, literal test nodes and wrapper substitutions.
Each command is a separate process, with complete output and an exact-status receipt
under root/raw/<unique-run> beside this file. No shell, discovery, sync or broad suite.

Timeouts retain headroom over measured local runs: VC1 145s, CR5 38s, and
multi-minute AS1 replays and CR2/CR3 final tests 51s/corpus 42s; 900s tests
and 1800s corpus/architecture gates retain headroom without a short default.
The runner classifies subprocess evidence; it does not appoint an evaluator or
replace the substantive assertions in the selected tests and recomputing gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
JOURNAL = Path("docs/superpowers/journals/gy-lattice")
PYTHON = str(ROOT / ".venv/bin/python")
CR5_HELPER = str(JOURNAL / "cr5/verify.py")
CROSSWALK = Path("docs/reference/canonical-vocabulary-crosswalk.v1.json")

# Literal, reviewed selectors are intentionally fixed: no pytest discovery.

VC1_NODES = (
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_canonical_movement_admits_every_member_and_refuses_unknowns"
    ),
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_second_arbitrarily_named_movement_vocabulary_is_refused"
    ),
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_removing_registry_independence_cannot_hide_a_new_namespace"
    ),
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_blocking_loss_refuses_for_each_dimension_and_display_loss_preserves_identity"
    ),
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_no_status_addition_and_no_source_identity_or_owner_substitution"
    ),
    (
        "tests/unit/runtime/quality/test_vocabulary_crosswalk.py::"
        "test_factor_axes_are_not_lifecycle_statuses"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_reference_is_total_and_recomputed_from_all_declared_owners"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_missing_extra_and_corrupt_semantic_rows_fail"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_removing_anti_fork_property_keep_markers_is_detected"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_removing_loss_refusal_keep_marker_contract_is_detected"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_changed_source_denominator_and_unreadable_source_are_not_zero"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_institutional_reconciliation_preserves_candidate_and_unallocated_boundaries"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_actual_production_caller_refuses_a_second_namespace_and_removal_is_red"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_independent_source_parser_keeps_digit_bearing_lifecycle_members"
    ),
    (
        "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py::"
        "test_qualified_reason_identity_keeps_digits_and_complete_namespace"
    ),
)

AS1_UNIT_NODES = (
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_assurance_executes_frozen_corpus_and_persisted_consumer"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_terminal_requires_substantive_bound_complete_owner_basis"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_event_cannot_close_without_recomputed_targeted_current_evidence"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_duplicate_event_has_one_persisted_acquisition_effect"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_remove_boundary_property_keep_terminal_markers_refuses"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_ordinary_data_control_observes_admitted_availability_change"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_rule_change_revalidates_current_use_and_preserves_old_receipt"
    ),
    (
        "tests/unit/fabric/test_acquisition_assurance.py::"
        "test_persisted_consumer_rejects_self_stamped_closure"
    ),
)

AS1_CHECKER_NODES = (
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_complete_corpus_reconciles_two_parser_stacks"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_independent_oracle_grades_real_persisted_consumers"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_each_named_mutant_fails_on_its_own_witness"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_removing_oracle_independence_refuses"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_corrupt_immutable_input_refuses_before_grade"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_oracle_does_not_import_subject_decoder_or_comparison"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_oracle_seal_is_not_derived_from_selected_file"
    ),
    (
        "tests/repo_quality/tools/test_gy_acquisition_assurance.py::"
        "test_cli_creates_ignored_scratch_from_absent_directory"
    ),
)

ORACLE_NODES = (
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_oracle_exists_as_an_independent_executable"
    ),
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_isolated_oracle_rejects_changed_semantic_observation"
    ),
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_shared_subject_dependency_is_denied_before_grading"
    ),
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_removing_process_read_boundary_turns_oracle_red"
    ),
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_nonisolated_process_is_not_accepted_as_independent"
    ),
    (
        "tests/repo_quality/tools/test_acquisition_oracle_isolation.py::"
        "test_observed_case_denominator_is_reconciled_completely"
    ),
)

CR2_NODES = (
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_every_forbidden_product_and_pairwise_three_way_mutation_is_refused"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_real_intake_refuses_forbidden_state_without_persisting_it_as_current"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_late_event_appends_correction_and_duplicate_preserves_prior_bytes"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_head_gap_claim_and_conflicting_duplicate_forks_refuse"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_concurrent_head_writers_publish_one_exact_slot"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_withdrawal_preserves_external_state_but_never_claim_dependent_permission"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_projection_preserves_cr1_status_and_forged_authority_refuses"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_direct_cr1_injection_cannot_forge_chain_or_affected_claim"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_operation_synonym_cannot_reopen_protected_exposure"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_removing_product_semantics_keeps_markers_and_turns_battery_red"
    ),
    (
        "tests/unit/runtime/quality/test_constrained_response.py::"
        "test_direct_cr1_forbidden_genesis_is_refused_by_shared_history_validation"
    ),
)

CR3_NODES = (
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_twenty_packets_all_counters_and_high_harm_containment"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_proxy_pairs_have_distinct_context_reasons"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_independence_removal_and_decoder_poison_are_detected"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_every_guardrail_mutant_has_its_own_red_counter"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_corrupt_oracle_is_refused_and_valid_seal_wrong_content_fails"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_each_proxy_divergence_removal_is_local"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_valid_shape_decoder_wrongness_diverges_from_independent_oracle"
    ),
    (
        "tests/unit/runtime/quality/test_response_corpus_evaluator.py::"
        "test_operation_coverage_rejects_effect_removal_with_labels_intact"
    ),
)

CR1_IMPORTER_NODES = (
    (
        "tests/unit/runtime/quality/test_adaptation_transition.py::"
        "test_unsigned_request_fails_safe_and_names_role"
    ),
    (
        "tests/unit/runtime/quality/test_adaptation_transition.py::"
        "test_actual_sigkill_and_duplicate_preserve_single_custody_publication"
    ),
)

CR5_NODES = (
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_signed_observations_drive_runtime_and_direct_materialization"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_empty_deployment_appointment_cannot_publish"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_valid_champion_does_not_authorize_fabricated_run_result"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_appointment_cannot_name_its_producer_as_evaluator"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_graph_rejects_raw_or_unminted_verified_rows_before_writing"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_verified_rows_recheck_current_champion_at_graph_use"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_retained_promotion_basis_requires_actual_incumbent_observations"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_legacy_pointer_has_no_inferred_genesis_and_manual_replacement_is_refused"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_claim_transition_rejects_alternate_policy_without_changing_basis"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_every_current_input_field_is_required_and_content_bound"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py::"
        "test_verified_receipt_drives_graph_and_conflict_consumers"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py::"
        "test_constant_receipt_rejects_false_to_true_projection_flip_in_both_consumers"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py::"
        "test_invalid_replacement_receipt_cannot_erase_existing_admitted_pointer"
    ),
    (
        "tests/integration/data_forge/domains/academic/batch/test_claim_adjudication_pipeline.py::"
        "test_rich_producer_subject_survives_admission_and_both_consumers"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_raw_input_excludes_producer_publish_authority_and_freezes_bytes"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_missing_champion_blocks_without_emitting_result"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_promoted_champion_executes_and_publishes_strong_fulltext"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_model_positive_cannot_publish_abstract_only_claim"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_evaluation_candidate_mismatch_blocks_admission"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_required_guardrail_false_blocks_admission"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_tampered_raw_blob_is_rejected_before_execution"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_execution_result_cannot_be_presented_as_validity_evidence"
    ),
    (
        "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::"
        "test_scientist_cli_route_executes_real_transport_and_materializes_receipt"
    ),
)

CR5_AUTHENTICATION_FAILURES = (
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes[signature-scientist]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes[signature-data_forge]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes[unappointed_signer-scientist]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes[unappointed_signer-data_forge]"
    ),
)

CR5_OBSERVATION_FAILURES = (
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_valid_champion_does_not_authorize_fabricated_run_result[scientist]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py::"
        "test_valid_champion_does_not_authorize_fabricated_run_result[data_forge]"
    ),
)

CR5_CURRENT_SUBJECT_FAILURES = (
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[cause_variable-graph]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[cause_variable-conflict]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[direction-graph]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[direction-conflict]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[scope_conditions-graph]"
    ),
    (
        "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py::"
        "test_full_subject_reaches_both_consumers_without_borrowed_grades[scope_conditions-conflict]"
    ),
)

# These three nodes only wrap the separately listed CLI gates. They are exposed
# above, and omitted from as1-checker so a full run does not repeat the corpus.
AS1_WRAPPER_SUBSTITUTIONS = {
    AS1_CHECKER_NODES[1]: ("as1-check",),
    AS1_CHECKER_NODES[2]: ("as1-mutants",),
    AS1_CHECKER_NODES[3]: ("as1-decoder", "as1-loader", "as1-comparator", "as1-unconfined"),
}
AS1_MUTANT_WITNESSES = (
    ("mutant.row_count_auto_closes_relation_estimand_mandate", "row_inflation_false_close"),
    ("mutant.form_or_signature_auto_admits", "form_without_proof_admitted"),
    ("mutant.route_or_artifact_auto_closes_without_owner_reentry", "owner_reentry_bypassed"),
    ("mutant.exact_membership_used_for_hierarchy_or_subset", "subset_use_refused"),
    ("mutant.timeout_or_silence_emits_terminal", "unproved_terminal"),
    ("mutant.surface_composes_authority", "candidate_authority_escape"),
    ("mutant.remove_property_keep_markers", "missing_object_nonclosure_removed"),
)
RUFF_PATHS = (
    "src/polisyos/runtime/quality/vocabulary_crosswalk.py",
    "tools/quality/validation/check_canonical_vocabulary_crosswalk.py",
    "tests/unit/runtime/quality/test_vocabulary_crosswalk.py",
    "tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py",
    "src/polisyos/fabric/evidence/acquisition_assurance.py",
    "tools/quality/validation/check_gy_acquisition_assurance.py",
    "tests/unit/fabric/test_acquisition_assurance.py",
    "tests/repo_quality/tools/test_gy_acquisition_assurance.py",
    "tools/quality/validation/gy_acquisition_assurance_oracle.py",
    "tests/repo_quality/tools/test_acquisition_oracle_isolation.py",
    "src/polisyos/runtime/quality/constrained_response.py",
    "src/polisyos/runtime/quality/response_corpus_evaluator.py",
    "tools/response_transition_oracle.py",
    "tools/check_response_corpus.py",
    "tests/unit/runtime/quality/test_constrained_response.py",
    "tests/unit/runtime/quality/test_response_corpus_evaluator.py",
    "docs/superpowers/journals/gy-lattice/cr5/verify.py",
    "docs/superpowers/journals/gy-lattice/check_delivery.py",
    "docs/superpowers/journals/gy-lattice/run_targeted_verification.py",
)


@dataclass(frozen=True)
class Gate:
    """One command with its observed-outcome contract and bounded input selection."""

    group: str
    argv: tuple[str, ...]
    kind: str = "pytest"
    expected_exit: int = 0
    timeout_seconds: int = 900
    nodeids: tuple[str, ...] = ()
    reason: str = ""


def gates(run_root: Path) -> tuple[Gate, ...]:
    """Build only the explicit, reviewed commands; do not discover tests or import owners."""
    pytest = (PYTHON, "-m", "pytest", "-o", "addopts=", "-q", "-s")
    vc1 = (PYTHON, "-m", "tools.quality.validation.check_canonical_vocabulary_crosswalk")
    as1 = (PYTHON, "-m", "tools.quality.validation.check_gy_acquisition_assurance")
    cr3 = (PYTHON, "-m", "tools.check_response_corpus", "--check")
    test_groups = (
        ("vc1", VC1_NODES),
        ("as1-unit", AS1_UNIT_NODES),
        ("as1-checker", tuple(n for n in AS1_CHECKER_NODES if n not in AS1_WRAPPER_SUBSTITUTIONS)),
        ("oracle", ORACLE_NODES),
        ("cr2", CR2_NODES),
        ("cr3", CR3_NODES),
        ("cr1-importers", CR1_IMPORTER_NODES),
    )
    selected = [
        Gate(name, (*pytest, *nodes), timeout_seconds=1800 if name == "cr3" else 900,
             nodeids=nodes)
        for name, nodes in test_groups
    ]
    selected.extend((
        Gate("vc1-check", (*vc1, "--check"), kind="vc1"),
        Gate("vc1-corrupt", (*vc1, "--check", "--artifact",
                             str(run_root / "corrupt-crosswalk.json")),
             kind="vc1-corrupt", expected_exit=1, reason="reference_drift"),
        Gate("as1-check", (*as1, "--check"), kind="as1"),
        Gate("as1-mutants", (*as1, "--mutation-battery"), kind="as1-mutants",
             timeout_seconds=1800),
    ))
    for challenge in ("decoder", "loader", "comparator", "unconfined"):
        reason = ("oracle_isolation_not_enforced:subject_read" if challenge == "unconfined"
                  else "oracle_shared_dependency_refused:" + challenge)
        selected.append(Gate(
            "as1-" + challenge, (*as1, "--check", "--challenge", challenge),
            kind="isolation", expected_exit=2, reason=reason,
        ))
    selected.extend((
        Gate("cr3-check", (*cr3, "--root", str(run_root / "corpus-replay")),
             kind="cr3", timeout_seconds=1800),
        Gate("cr3-corrupt", (*cr3, "--root", str(run_root / "corrupt-oracle"),
                             "--corrupt-oracle"), kind="cr3-corrupt", expected_exit=1),
        Gate("cr5", (PYTHON, CR5_HELPER, "baseline"), kind="cr5", nodeids=CR5_NODES),
        Gate("cr5-authentication", (PYTHON, CR5_HELPER, "authentication"),
             kind="pytest-removal", expected_exit=1, nodeids=CR5_AUTHENTICATION_FAILURES,
             reason="authentication\tClaimAdjudicationVerifier._authenticate"),
        Gate("cr5-observation", (PYTHON, CR5_HELPER, "observation"),
             kind="pytest-removal", expected_exit=1, nodeids=CR5_OBSERVATION_FAILURES,
             reason="observation\tClaimAdjudicationVerifier.verify_batch"),
        Gate("cr5-current-subject", (PYTHON, CR5_HELPER, "current_subject"),
             kind="pytest-removal", expected_exit=1, nodeids=CR5_CURRENT_SUBJECT_FAILURES,
             reason="current_subject\tVerifiedClaimAdjudicationRows.for_current_subject"),
        Gate("cr5-unfavorable", (PYTHON, CR5_HELPER, "unfavorable"), kind="unfavorable"),
        Gate("delivery", (PYTHON, str(JOURNAL / "check_delivery.py")), kind="delivery"),
        Gate("ruff", (PYTHON, "-m", "ruff", "check", *RUFF_PATHS), kind="ruff"),
        Gate("architecture", (PYTHON, "-m", "tools.cli", "architecture", "guardrails", "check"),
             kind="architecture", timeout_seconds=1800),
    ))
    return tuple(selected)


def classify(gate: Gate, exit_code: int | None, output: str) -> str:
    """Require the declared result, refusing crashes and unrelated negative statuses."""
    if gate.kind == "architecture":
        freshness_unrun = (
            "Required freshness environment preparation failed",
            "Required freshness validation skipped",
            "freshness stage skipped",
            "libpython3.14.dylib",
            "SIGABRT",
        )
        unrun = any(marker.lower() in output.lower() for marker in freshness_unrun)
        creep = "New deep-import creep detected:" in output
        if creep and unrun:
            return "failed_architecture_review_required_and_unrun_freshness_no_sync"
        if unrun:
            return "unrun_freshness"
        if creep:
            return "failed_architecture_review_required_no_sync"
    if exit_code is None:
        return "unrun_timeout_or_launch_error"
    if exit_code < 0:
        return "failed_signal"
    if exit_code != gate.expected_exit:
        return "failed_unexpected_exit"
    crash_markers = ("Traceback (most recent call last):", "INTERNALERROR>",
                     "ERROR collecting", "Fatal Python error:")
    if any(marker in output for marker in crash_markers):
        return "failed_runtime_or_collection_error"
    lines = output.splitlines()
    if gate.group.startswith("cr5"):
        try:
            denominators = [json.loads(line.split("\t", 1)[1]) for line in lines
                            if line.startswith("EXPLICIT_NODE_DENOMINATOR\t")]
        except ValueError:
            return "failed_cr5_unreadable_node_denominator"
        if denominators != [list(CR5_NODES), list(CR5_NODES)]:
            return "failed_cr5_node_denominator_changed"
    if gate.kind == "pytest-removal":
        failed = re.findall(r"^FAILED (\S+)", output, flags=re.MULTILINE)
        expected = set(gate.nodeids)
        # Independent line parser also rejects duplicate or truncated failure identities.
        parsed = [line.split()[1] for line in lines if line.startswith("FAILED ")]
        if (failed != parsed or len(failed) != len(expected) or set(failed) != expected
                or "REMOVED_PROPERTY\t" + gate.reason not in lines
                or not re.search(rf"\b{len(expected)} failed\b", output)):
            return "failed_wrong_removal_witness"
        return "expected_negative_verified"
    if gate.kind == "isolation":
        errors = [line for line in lines if line.startswith("ORACLE_ERROR\t")]
        return ("expected_negative_verified" if errors == ["ORACLE_ERROR\t" + gate.reason]
                else "failed_wrong_isolation_reason")
    if gate.kind == "as1-mutants":
        killed = [tuple(line.split("\t")[1:]) for line in lines
                  if line.startswith("MUTANT_KILLED\t")]
        return ("passed" if tuple(killed) == AS1_MUTANT_WITNESSES
                and "MUTANT_NOT_KILLED" not in output else "failed_mutant_witness_set")
    if gate.kind == "as1":
        return "passed" if "ORACLE_PASS\t63" in lines else "failed_oracle_result"
    if gate.kind == "unfavorable":
        return ("passed" if any(line.startswith(
            "UNFAVORABLE_ADMITTED\tgraph=0\tconflict=0\treceipt=") for line in lines)
                else "failed_unfavorable_consumer_result")
    if gate.kind in ("pytest", "cr5"):
        return ("passed" if re.search(r"\b[1-9]\d* passed\b", output)
                else "failed_no_passing_test_result")
    if gate.kind == "ruff":
        return "passed" if "All checks passed!" in output else "failed_ruff_result"
    if gate.kind == "architecture":
        return ("passed" if "Architecture guardrail check passed." in output
                else "failed_architecture_result")
    try:
        report = json.loads(output)
    except ValueError:
        return "failed_unreadable_gate_report"
    if not isinstance(report, dict):
        return "failed_unreadable_gate_report"
    if gate.kind == "vc1-corrupt":
        valid = report.get("result") == "fail" and report.get("failures") == ["reference_drift"]
    elif gate.kind == "cr3-corrupt":
        valid = report.get("corruption_refusals") == [
            "oracle_seal_mismatch", "oracle_recompute_mismatch",
        ]
    elif gate.kind == "vc1":
        valid = report.get("result") == "pass" and report.get("failures") == []
    elif gate.kind == "cr3":
        counters = report.get("guardrail_counters", {})
        valid = (report.get("packet_count") == 20 and len(counters) == 12
                 and all(value == 0 for value in counters.values())
                 and report.get("issues") == []
                 and report.get("high_harm_declared", 0) > 0
                 and report.get("high_harm_declared") == report.get("high_harm_preserved"))
    else:
        valid = report.get("result") == "pass"
    if not valid:
        return "failed_wrong_gate_result"
    return "expected_negative_verified" if gate.expected_exit else "passed"


def prepare(gate: Gate, run_root: Path) -> dict[str, str] | None:
    """Create the one semantic-drift input in ignored scratch, preserving tracked bytes."""
    if gate.kind != "vc1-corrupt":
        return None
    data = (ROOT / CROSSWALK).read_bytes()
    artifact = json.loads(data)
    if artifact["entries"][0]["losses"]["source_identity"] != "blocking":
        raise ValueError("corruption_source_precondition_changed")
    artifact["entries"][0]["losses"]["source_identity"] = "tolerable"
    target = run_root / "corrupt-crosswalk.json"
    target.write_text(json.dumps(artifact, indent=2) + "\n")
    return {
        "source": f"{CROSSWALK}@{hashlib.sha256(data).hexdigest()}",
        "mutation": "entries[0].losses.source_identity: blocking -> tolerable",
        "artifact": f"{target.relative_to(ROOT)}@{hashlib.sha256(target.read_bytes()).hexdigest()}",
    }


def execute(gate: Gate, run_root: Path, environment: dict[str, str]) -> dict[str, object]:
    """Run a sole gate process and preserve output, status, duration and log identity."""
    output_path = run_root / (gate.group + ".txt")
    started = time.monotonic()
    exit_code = None
    instrumentation_error = None
    preparation = None
    try:
        preparation = prepare(gate, run_root)
        with output_path.open("wb") as output:
            process = subprocess.Popen(  # noqa: S603 - fixed gate argv, shell is never enabled
                gate.argv, cwd=ROOT, env=environment, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            try:
                exit_code = process.wait(timeout=gate.timeout_seconds)
            except subprocess.TimeoutExpired:
                # Kill this gate's process group, including compiler/test descendants.
                os.killpg(process.pid, signal.SIGKILL)
                exit_code = process.wait()
                instrumentation_error = "timeout"
    except (OSError, ValueError) as error:
        instrumentation_error = f"{type(error).__name__}:{error}"
        if not output_path.exists():
            output_path.write_text(instrumentation_error + "\n")
    elapsed = time.monotonic() - started
    data = output_path.read_bytes()
    classification = ("unrun_timeout_or_launch_error" if instrumentation_error
                      else classify(gate, exit_code, data.decode(errors="replace")))
    return {
        "group": gate.group, "argv": gate.argv, "cwd": str(ROOT),
        "environment": {"PYTHONPATH": environment["PYTHONPATH"]},
        "expected_exit_code": gate.expected_exit, "exit_code": exit_code,
        "timeout_seconds": gate.timeout_seconds, "wall_seconds": round(elapsed, 3),
        "classification": classification, "instrumentation_error": instrumentation_error,
        "nodeids": gate.nodeids, "preparation": preparation,
        "output": f"{output_path.relative_to(ROOT)}@{hashlib.sha256(data).hexdigest()}",
    }


def main() -> int:
    """Default to a read-only inventory; run selected gates only with explicit --run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=[g.group for g in gates(Path("<run-root>"))],
                        action="append", help="Repeat to select groups; default selects all.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="List only (the default).")
    mode.add_argument("--run", action="store_true", help="Execute selected groups sequentially.")
    args = parser.parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    run_root = ROOT / JOURNAL / "root/raw" / (run_id if args.run else "<run-id>")
    selected = [gate for gate in gates(run_root) if args.group is None or gate.group in args.group]
    if not args.run:
        sys.stdout.write(json.dumps({
            "mode": "list_only", "cwd": str(ROOT), "environment": {"PYTHONPATH": ".:src"},
            "commands": [{"group": gate.group, "argv": gate.argv,
                          "timeout_seconds": gate.timeout_seconds,
                          "expected_exit_code": gate.expected_exit, "nodeids": gate.nodeids,
                          "required_reason": gate.reason} for gate in selected],
            "as1_wrapper_substitutions": AS1_WRAPPER_SUBSTITUTIONS,
            "all_as1_checker_nodeids": AS1_CHECKER_NODES,
            "all_cr5_nodeids": CR5_NODES,
        }, indent=2) + "\n")
        return 0
    run_root.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, PYTHONPATH=".:src", PYTHONUNBUFFERED="1", NO_COLOR="1")
    results = []
    receipt_path = run_root / "receipt.json"
    for gate in selected:
        sys.stdout.write("RUN\t" + gate.group + "\n")
        sys.stdout.flush()
        result = execute(gate, run_root, environment)
        results.append(result)
        receipt_path.write_text(json.dumps({
            "schema_version": "gy-lattice.targeted-run.v1", "run_id": run_id,
            "runner": f"{Path(__file__).relative_to(ROOT)}@"
                      + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "gates": results,
        }, indent=2) + "\n")
        sys.stdout.write(f"RESULT\t{gate.group}\t{result['classification']}\t"
                         f"exit={result['exit_code']}\twall={result['wall_seconds']}\n")
        sys.stdout.flush()
        if result["classification"] not in ("passed", "expected_negative_verified"):
            break
    sys.stdout.write(f"RECEIPT\t{receipt_path.relative_to(ROOT)}@"
                     + hashlib.sha256(receipt_path.read_bytes()).hexdigest() + "\n")
    return int(len(results) != len(selected) or any(
        result["classification"] not in ("passed", "expected_negative_verified")
        for result in results
    ))


if __name__ == "__main__":
    raise SystemExit(main())
