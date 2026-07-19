#!/usr/bin/env python3
"""Write, rederive, and verify the frozen GY-N13b acquisition contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.fabric.data_plane import canonical_json_bytes
from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
    DEFAULT_GENERATED_ARTIFACTS,
    DEFAULT_N13B_CONTRACT,
    DEFAULT_N13B_LIFECYCLE_MANIFEST,
    N13bAcquisitionExecutorContract,
    N13bContractError,
    derive_n13b_acquisition_executor_contract,
    derive_n13b_generated_registry_update,
)
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_DERIVATION_FAMILY_REGISTRY,
    DEFAULT_UNIVERSALITY_RECEIPT,
    build_derivation_universality_receipt,
    derivation_universality_bytes,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
SOURCE_MODULE_PATH = Path("tools/quality/validation/layer3_gy_n13b_acquisition_contract.py")
TEST_MODULE_PATH = Path("tests/repo_quality/tools/test_layer3_gy_n13b_acquisition_contract.py")
OVERLAY_SOURCE_PATH = Path("src/polisyos/data_forge/domains/catalog/knowledge/overlay.py")
ACQUISITION_AUTHORITY_SOURCE_PATH = Path(
    "src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py"
)
EVIDENCE_JOURNAL_SOURCE_PATH = Path("src/polisyos/fabric/data_plane/evidence_journal.py")
DERIVATION_SOURCE_PATH = Path("src/polisyos/runtime/quality/derived_observations.py")
OVERLAY_TEST_PATH = Path("tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py")
ACQUISITION_AUTHORITY_TEST_PATH = Path(
    "tests/unit/data_forge/domains/catalog/knowledge/test_acquisition_authority.py"
)
DERIVATION_TEST_PATH = Path("tests/unit/runtime/quality/test_derived_observations.py")
EVIDENCE_JOURNAL_TEST_PATH = Path("tests/unit/fabric/data_plane/test_live_attempt_terminal.py")


@dataclass(frozen=True)
class _SourceFlipCase:
    mutation_id: str
    source_path: Path
    replacements: tuple[tuple[str, str], ...]
    probe_nodeid: str
    expected_red_signal: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--rederive", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--l5-path", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=POLICY_ENGINE_ROOT / DEFAULT_N13B_CONTRACT,
    )
    parser.add_argument(
        "--lifecycle-output",
        type=Path,
        default=POLICY_ENGINE_ROOT / DEFAULT_N13B_LIFECYCLE_MANIFEST,
    )
    parser.add_argument(
        "--derivation-registry",
        type=Path,
        default=DEFAULT_DERIVATION_FAMILY_REGISTRY,
    )
    parser.add_argument(
        "--universality-output",
        type=Path,
        default=POLICY_ENGINE_ROOT / DEFAULT_UNIVERSALITY_RECEIPT,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.derivation_registry, args.universality_output = _canonical_derivation_paths(
        registry_path=args.derivation_registry,
        universality_output=args.universality_output,
    )
    baseline_before = _file_sha256(args.catalog_path)
    l5_sha = _file_sha256(args.l5_path)
    if args.source_flip_mutations:
        report = run_source_flip_mutations(POLICY_ENGINE_ROOT)
        _require_baseline_unchanged(args.catalog_path, baseline_before)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "pass" else 1

    first_universality = build_derivation_universality_receipt(
        catalog_path=args.catalog_path,
        registry_path=args.derivation_registry,
    )
    second_universality = build_derivation_universality_receipt(
        catalog_path=args.catalog_path,
        registry_path=args.derivation_registry,
    )
    first_universality_bytes = derivation_universality_bytes(first_universality)
    second_universality_bytes = derivation_universality_bytes(second_universality)
    if first_universality_bytes != second_universality_bytes:
        raise N13bContractError("n13b_universality_writer_not_byte_stable")
    if not args.write:
        _check_exact(
            args.universality_output,
            first_universality_bytes,
            "n13b_derivation_universality_drift",
        )

    registry_update = derive_n13b_generated_registry_update(POLICY_ENGINE_ROOT)
    generated_artifacts_path = POLICY_ENGINE_ROOT / DEFAULT_GENERATED_ARTIFACTS
    if not args.write:
        _check_exact(
            generated_artifacts_path,
            registry_update.registry_bytes,
            "n13b_generated_cas_registry_drift",
        )

    first = derive_n13b_acquisition_executor_contract(
        repo_root=POLICY_ENGINE_ROOT,
        baseline_sha256=baseline_before,
        l5_sha256=l5_sha,
        universality_receipt=first_universality,
        generated_artifacts_bytes=registry_update.registry_bytes,
    )
    second = derive_n13b_acquisition_executor_contract(
        repo_root=POLICY_ENGINE_ROOT,
        baseline_sha256=baseline_before,
        l5_sha256=l5_sha,
        universality_receipt=second_universality,
        generated_artifacts_bytes=registry_update.registry_bytes,
    )
    first_contract = canonical_json_bytes(first.model_dump(mode="json"))
    second_contract = canonical_json_bytes(second.model_dump(mode="json"))
    first_lifecycle = canonical_json_bytes(first.lifecycle.model_dump(mode="json"))
    second_lifecycle = canonical_json_bytes(second.lifecycle.model_dump(mode="json"))
    if first_contract != second_contract or first_lifecycle != second_lifecycle:
        raise N13bContractError("n13b_writer_not_byte_stable")
    _require_baseline_unchanged(args.catalog_path, baseline_before)

    if args.write:
        _write_transaction(
            (
                (generated_artifacts_path, registry_update.registry_bytes),
                (args.universality_output, first_universality_bytes),
                (args.lifecycle_output, first_lifecycle),
                (args.output, first_contract),
            ),
            remove_paths=tuple(
                POLICY_ENGINE_ROOT / path for path in registry_update.obsolete_cas_output_paths
            ),
        )
        status = "written"
    elif args.check:
        _check_exact(args.lifecycle_output, first_lifecycle, "n13b_lifecycle_manifest_drift")
        _check_exact(args.output, first_contract, "n13b_acquisition_contract_drift")
        status = "ok"
    elif args.corrupt_field_drift_check:
        _check_exact(args.lifecycle_output, first_lifecycle, "n13b_lifecycle_manifest_drift")
        _check_exact(args.output, first_contract, "n13b_acquisition_contract_drift")
        report = run_corrupt_field_drift(first)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
    else:
        status = "rederived"

    report = _summary(first, status=status)
    report["byte_stable_passes"] = 2
    report["derivation_family_count"] = first_universality.family_count
    report["derivation_universality_sha256"] = first_universality.receipt_sha256
    report["baseline_before_sha256"] = baseline_before
    report["baseline_after_sha256"] = _file_sha256(args.catalog_path)
    print(json.dumps(report, sort_keys=True))
    return 0


def _summary(
    contract: N13bAcquisitionExecutorContract,
    *,
    status: str,
) -> dict[str, object]:
    return {
        "status": status,
        "contract_sha256": contract.contract_sha256,
        "lifecycle_manifest_sha256": contract.lifecycle.manifest_sha256,
        "registered_output_count": contract.lifecycle.registered_output_count,
        "local_lift_denominator_count": contract.local_lift.residual_denominator_count,
        "local_lift_admissible_count": contract.local_lift.admissible_count,
        "d2_connector_gap_count": contract.d2_source_growth.connector_gap_count,
        "live_attempt_count": contract.journal.terminal_count,
        "raw_response_count": contract.journal.raw_response_count,
        "resumption_spent_call_count": contract.resumption_budget.spent_call_count,
        "resumption_remaining_call_count": contract.resumption_budget.remaining_call_count,
        "derivation_recipe_id": contract.derivation.recipe_id,
        "derivation_consumer_count": contract.derivation.consumer_count,
        "second_materialization_cache_hit": (contract.derivation.second_materialization_cache_hit),
        "derivation_family_count": contract.derivation_universality.family_count,
        "derivation_universality_sha256": (contract.derivation_universality.source_receipt_sha256),
        "availability_count_before": contract.world_growth.availability_count_before,
        "availability_count_after": contract.world_growth.availability_count_after,
        "availability_count_delta": contract.world_growth.availability_count_delta,
        "overlay_epoch_count": contract.world_growth.overlay_epoch_count,
        "admitted_observation_count": contract.world_growth.admitted_observation_count,
        "world_growth_status": contract.world_growth.status,
        "world_growth_event_count": contract.world_growth.event_count,
        "reentry_disposition": contract.reentry.reentry_disposition,
        "demonstration_status": contract.demonstration_status,
        "capstone_laundered_route_count": contract.capstone_routes.laundered_route_count,
        "open_residuals": list(contract.residual_closure.open_residuals),
    }


def run_corrupt_field_drift(
    contract: N13bAcquisitionExecutorContract,
) -> dict[str, object]:
    """Mutate nested decisive fields and require strict contract reconstruction to RED."""

    cases: tuple[tuple[str, tuple[str | int, ...], object], ...] = (
        ("world_growth_status_relabel", ("world_growth", "status"), "grew"),
        (
            "terminal_relabel",
            ("journal", "attempts", 0, "failure_code"),
            "alive_conformant",
        ),
        (
            "journal_raw_persistence_forged",
            ("journal", "attempts", 0, "raw_cas_persisted"),
            False,
        ),
        (
            "derivation_recipe_parameter_tamper",
            ("derivation", "recipe_projection", "parameters", 0, "value"),
            "1900",
        ),
        (
            "derivation_recipe_input_tamper",
            (
                "derivation",
                "recipe_projection",
                "inputs",
                0,
                "artifact",
                "artifact_id",
            ),
            "sha256:" + "0" * 64,
        ),
        (
            "derived_as_observed",
            ("derivation", "observation_class"),
            "observed",
        ),
        (
            "capstone_route_laundering",
            ("capstone_routes", "routes", 0, "route_class"),
            "live_fetchable",
        ),
        (
            "lifecycle_registration_removed",
            ("lifecycle", "canonical_provision_registered"),
            False,
        ),
        (
            "source_owner_hash_tamper",
            ("source_owners", 0, "file_sha256"),
            "sha256:" + "0" * 64,
        ),
        (
            "local_lift_terminal_relabel",
            ("local_lift", "disposition"),
            "local_lift_admissible",
        ),
        (
            "d2_connector_backlog_reordered",
            ("d2_source_growth", "rows", 0, "rank"),
            2,
        ),
        (
            "universality_family_proof_tamper",
            (
                "derivation_universality",
                "families",
                0,
                "family_proof_sha256",
            ),
            "sha256:" + "0" * 64,
        ),
        (
            "universality_family_version_tamper",
            ("derivation_universality", "families", 0, "method_version"),
            "forged-version",
        ),
    )
    results: list[dict[str, object]] = []
    for mutation_id, path, value in cases:
        payload = copy.deepcopy(contract.model_dump(mode="json"))
        _set_nested(payload, path, value)
        red = False
        error_type: str | None = None
        try:
            N13bAcquisitionExecutorContract.model_validate(payload)
        except (ValidationError, ValueError) as exc:
            red = True
            error_type = type(exc).__name__
        results.append(
            {
                "mutation_id": mutation_id,
                "result": "RED" if red else "GREEN_MUTATION_SURVIVED",
                "error_type": error_type,
            }
        )
    all_red = all(row["result"] == "RED" for row in results)
    return {
        "status": "pass" if all_red else "fail",
        "issues": [] if all_red else [{"code": "corrupt_field_drift_survived"}],
        "results": results,
    }


def _set_nested(payload: object, path: tuple[str | int, ...], value: object) -> None:
    current: Any = payload
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    contract_test = f"{TEST_MODULE_PATH}::"
    overlay_test = f"{OVERLAY_TEST_PATH}::"
    authority_test = f"{ACQUISITION_AUTHORITY_TEST_PATH}::"
    derivation_test = f"{DERIVATION_TEST_PATH}::"
    journal_test = f"{EVIDENCE_JOURNAL_TEST_PATH}::"
    return (
        _SourceFlipCase(
            mutation_id="baseline_mutation_fence_removed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    "        if current != self._baseline_identity:\n"
                    "            raise BaselineMutationError(\n",
                    "        if False and current != self._baseline_identity:\n"
                    "            raise BaselineMutationError(\n",
                ),
            ),
            probe_nodeid=(
                overlay_test + "test_overlay_baseline_hash_fence_detects_any_epoch_zero_mutation"
            ),
            expected_red_signal=(
                "test_overlay_baseline_hash_fence_detects_any_epoch_zero_mutation"
            ),
        ),
        _SourceFlipCase(
            mutation_id="passport_owner_validation_bypassed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    "        source_body = _validate_passport_owner_evidence(\n"
                    "            passport,\n"
                    "            artifact_store=artifact_store,\n"
                    "            authority=authority,\n"
                    "        )\n",
                    "        source_body = artifact_store.get_bytes(\n"
                    "            ArtifactID.model_validate(str(passport.raw_artifact_id))\n"
                    "        )\n",
                ),
            ),
            probe_nodeid=(
                overlay_test
                + "test_overlay_revalidates_raw_and_cas_evidence_instead_of_trusting_passport_flags"
            ),
            expected_red_signal=(
                "test_overlay_revalidates_raw_and_cas_evidence_instead_of_trusting_passport_flags"
            ),
        ),
        _SourceFlipCase(
            mutation_id="epoch_stamp_guard_removed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    "        if epoch_id <= 0:\n"
                    '            raise OverlayAdmissionError("epoch_stamp_required")\n',
                    "        if False and epoch_id <= 0:\n"
                    '            raise OverlayAdmissionError("epoch_stamp_required")\n',
                ),
            ),
            probe_nodeid=(
                overlay_test + "test_overlay_refuses_quarantine_derived_model_and_epochless_rows"
            ),
            expected_red_signal=(
                "test_overlay_refuses_quarantine_derived_model_and_epochless_rows"
            ),
        ),
        _SourceFlipCase(
            mutation_id="canonical_value_raw_binding_removed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    "            canonical_value = values[0]\n",
                    "            canonical_value = 0.99\n",
                ),
            ),
            probe_nodeid=(
                overlay_test + "test_overlay_refuses_canonical_values_not_derived_from_raw_evidence"
            ),
            expected_red_signal=(
                "test_overlay_refuses_canonical_values_not_derived_from_raw_evidence"
            ),
        ),
        _SourceFlipCase(
            mutation_id="fabricated_fetch_raw_cas_guard_removed",
            source_path=ACQUISITION_AUTHORITY_SOURCE_PATH,
            replacements=(
                (
                    "            if raw_cas != raw_body:\n"
                    '                raise AcquisitionAuthorityError("live_raw_journal_cas_mismatch")\n',
                    "            if False and raw_cas != raw_body:\n"
                    '                raise AcquisitionAuthorityError("live_raw_journal_cas_mismatch")\n',
                ),
            ),
            probe_nodeid=(authority_test + "test_live_execution_rejects_recomputed_wrong_raw_cas"),
            expected_red_signal="test_live_execution_rejects_recomputed_wrong_raw_cas",
        ),
        _SourceFlipCase(
            mutation_id="forged_source_watermark_guard_removed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    "    if str(passport.source_watermark) != raw_body_sha:\n"
                    '        raise OverlayAdmissionError("source_watermark_content_drift")\n',
                    "    if False and str(passport.source_watermark) != raw_body_sha:\n"
                    '        raise OverlayAdmissionError("source_watermark_content_drift")\n',
                ),
            ),
            probe_nodeid=(
                overlay_test + "test_overlay_rejects_forged_source_watermark_after_passport_rebind"
            ),
            expected_red_signal=(
                "test_overlay_rejects_forged_source_watermark_after_passport_rebind"
            ),
        ),
        _SourceFlipCase(
            mutation_id="quarantine_to_l1_status_fence_removed",
            source_path=OVERLAY_SOURCE_PATH,
            replacements=(
                (
                    '        if status not in {"admitted", "admitted_degraded"}:\n'
                    '            raise OverlayAdmissionError("passport_not_admitted", status)\n',
                    '        if False and status not in {"admitted", "admitted_degraded"}:\n'
                    '            raise OverlayAdmissionError("passport_not_admitted", status)\n',
                ),
            ),
            probe_nodeid=(
                overlay_test
                + "test_overlay_refuses_quarantined_status_with_complete_owner_evidence"
            ),
            expected_red_signal=(
                "test_overlay_refuses_quarantined_status_with_complete_owner_evidence"
            ),
        ),
        _SourceFlipCase(
            mutation_id="journal_tamper_identity_guard_removed",
            source_path=EVIDENCE_JOURNAL_SOURCE_PATH,
            replacements=(
                (
                    "    if terminal_sha != expected_sha:\n"
                    '        raise EvidenceJournalError("live_terminal_identity_drift", attempt_id)\n',
                    "    if False and terminal_sha != expected_sha:\n"
                    '        raise EvidenceJournalError("live_terminal_identity_drift", attempt_id)\n',
                ),
            ),
            probe_nodeid=(
                journal_test + "test_journal_reopen_rejects_incomplete_or_tampered_history"
            ),
            expected_red_signal=("test_journal_reopen_rejects_incomplete_or_tampered_history"),
        ),
        _SourceFlipCase(
            mutation_id="terminal_relabel_guards_removed",
            source_path=EVIDENCE_JOURNAL_SOURCE_PATH,
            replacements=(
                (
                    "    if outcome_code != expected_outcome:\n"
                    '        raise EvidenceJournalError("live_terminal_outcome_drift", attempt_id)\n',
                    "    if False and outcome_code != expected_outcome:\n"
                    '        raise EvidenceJournalError("live_terminal_outcome_drift", attempt_id)\n',
                ),
                (
                    "    if terminal_sha != expected_sha:\n"
                    '        raise EvidenceJournalError("live_terminal_identity_drift", attempt_id)\n',
                    "    if False and terminal_sha != expected_sha:\n"
                    '        raise EvidenceJournalError("live_terminal_identity_drift", attempt_id)\n',
                ),
            ),
            probe_nodeid=(journal_test + "test_terminal_resolution_rejects_a_fabricated_outcome"),
            expected_red_signal=("test_terminal_resolution_rejects_a_fabricated_outcome"),
        ),
        _SourceFlipCase(
            mutation_id="derivation_recipe_parameter_binding_removed",
            source_path=DERIVATION_SOURCE_PATH,
            replacements=(
                (
                    "        if self.assumptions != expected_assumptions:\n"
                    '            raise ValueError("recipe assumptions differ from family rules")\n',
                    "        if False and self.assumptions != expected_assumptions:\n"
                    '            raise ValueError("recipe assumptions differ from family rules")\n',
                ),
                (
                    "        _validate_output_parameter_bindings(\n"
                    "            self.family,\n"
                    "            self.parameters,\n"
                    "            self.output_basis,\n"
                    "        )\n",
                    "        if False:\n"
                    "            _validate_output_parameter_bindings(\n"
                    "                self.family,\n"
                    "                self.parameters,\n"
                    "                self.output_basis,\n"
                    "            )\n",
                ),
                (
                    '        if self.recipe_id != _identity("derivation-recipe", self.identity_payload()):\n'
                    '            raise ValueError("derivation recipe identity must be recomputed")\n',
                    '        if False and self.recipe_id != _identity("derivation-recipe", self.identity_payload()):\n'
                    '            raise ValueError("derivation recipe identity must be recomputed")\n',
                ),
            ),
            probe_nodeid=(derivation_test + "test_recipe_parameter_tamper_is_rejected"),
            expected_red_signal=("test_recipe_parameter_tamper_is_rejected"),
        ),
        _SourceFlipCase(
            mutation_id="derivation_recipe_input_hash_binding_removed",
            source_path=DERIVATION_SOURCE_PATH,
            replacements=(
                (
                    '        if self.recipe_id != _identity("derivation-recipe", self.identity_payload()):\n'
                    '            raise ValueError("derivation recipe identity must be recomputed")\n',
                    '        if False and self.recipe_id != _identity("derivation-recipe", self.identity_payload()):\n'
                    '            raise ValueError("derivation recipe identity must be recomputed")\n',
                ),
            ),
            probe_nodeid=(derivation_test + "test_layer_invariants_are_family_parameterized"),
            expected_red_signal=("test_layer_invariants_are_family_parameterized"),
        ),
        _SourceFlipCase(
            mutation_id="derived_as_observed_type_fence_removed",
            source_path=DERIVATION_SOURCE_PATH,
            replacements=(
                (
                    "    source_artifact_ids: tuple[artifacts.ArtifactID, ...] = Field(min_length=1)\n"
                    '    observation_class: Literal["derived"]\n',
                    "    source_artifact_ids: tuple[artifacts.ArtifactID, ...] = Field(min_length=1)\n"
                    "    observation_class: str\n",
                ),
            ),
            probe_nodeid=(derivation_test + "test_layer_invariants_are_family_parameterized"),
            expected_red_signal=("test_layer_invariants_are_family_parameterized"),
        ),
        _SourceFlipCase(
            mutation_id="derived_authority_monotonicity_removed",
            source_path=DERIVATION_SOURCE_PATH,
            replacements=(
                (
                    "        if self.effective_authority != min(\n"
                    "            item.effective_score for item in self.input_authorities\n"
                    "        ):\n"
                    '            raise ValueError("derived authority must equal the weakest input")\n',
                    "        if False and self.effective_authority != min(\n"
                    "            item.effective_score for item in self.input_authorities\n"
                    "        ):\n"
                    '            raise ValueError("derived authority must equal the weakest input")\n',
                ),
            ),
            probe_nodeid=(derivation_test + "test_layer_invariants_are_family_parameterized"),
            expected_red_signal=("test_layer_invariants_are_family_parameterized"),
        ),
        _SourceFlipCase(
            mutation_id="data_registered_novel_family_resolution_removed",
            source_path=DERIVATION_SOURCE_PATH,
            replacements=(
                (
                    "            and _output_basis_matches_family(family, output_basis)\n",
                    '            and family.family_id == "__enumerated_first_family__"\n'
                    "            and _output_basis_matches_family(family, output_basis)\n",
                ),
            ),
            probe_nodeid=(
                derivation_test
                + "test_novel_family_is_typed_refused_then_accepted_by_registry_data_only"
            ),
            expected_red_signal=(
                "test_novel_family_is_typed_refused_then_accepted_by_registry_data_only"
            ),
        ),
        _SourceFlipCase(
            mutation_id="local_rights_trust_root_fence_removed",
            source_path=ACQUISITION_AUTHORITY_SOURCE_PATH,
            replacements=(
                (
                    "    if expected_file_sha256 is not None and actual != expected_file_sha256:\n"
                    '        raise AcquisitionAuthorityError("local_rights_trust_registry_content_drift")\n',
                    "    if False and expected_file_sha256 is not None and actual != expected_file_sha256:\n"
                    '        raise AcquisitionAuthorityError("local_rights_trust_registry_content_drift")\n',
                ),
            ),
            probe_nodeid=(
                "tests/unit/runtime/quality/test_acquisition_executor.py::"
                "test_coordinated_rights_and_acquisition_rebaseline_cannot_replace_trust_anchor"
            ),
            expected_red_signal=(
                "test_coordinated_rights_and_acquisition_rebaseline_cannot_replace_trust_anchor"
            ),
        ),
        _SourceFlipCase(
            mutation_id="capstone_route_laundering_guard_removed",
            source_path=SOURCE_MODULE_PATH,
            replacements=(
                (
                    "        if self.route_class != expected:\n"
                    '            raise ValueError("capstone route class must be recomputed from decisive evidence")\n',
                    "        if False and self.route_class != expected:\n"
                    '            raise ValueError("capstone route class must be recomputed from decisive evidence")\n',
                ),
                (
                    "        if self.projection_sha256 != content_sha256(self.identity_payload()):\n"
                    '            raise ValueError("capstone route projection identity drift")\n',
                    "        if False and self.projection_sha256 != content_sha256(self.identity_payload()):\n"
                    '            raise ValueError("capstone route projection identity drift")\n',
                ),
                (
                    "        if self.laundered_route_count != laundered:\n"
                    '            raise ValueError("capstone route laundering count must be recomputed")\n',
                    "        if False and self.laundered_route_count != laundered:\n"
                    '            raise ValueError("capstone route laundering count must be recomputed")\n',
                ),
                (
                    "        if self.projection_sha256 != content_sha256(self.identity_payload()):\n"
                    '            raise ValueError("capstone preservation identity drift")\n',
                    "        if False and self.projection_sha256 != content_sha256(self.identity_payload()):\n"
                    '            raise ValueError("capstone preservation identity drift")\n',
                ),
            ),
            probe_nodeid=(
                contract_test + "test_capstone_route_projection_rejects_label_laundering"
            ),
            expected_red_signal="test_capstone_route_projection_rejects_label_laundering",
        ),
        _SourceFlipCase(
            mutation_id="lifecycle_registration_forgery_guard_removed",
            source_path=SOURCE_MODULE_PATH,
            replacements=(
                (
                    '        "universality_receipt_registered": (\n'
                    "            DEFAULT_UNIVERSALITY_RECEIPT.as_posix() in registration_paths\n"
                    "        ),\n",
                    '        "universality_receipt_registered": True,\n',
                ),
            ),
            probe_nodeid=(
                contract_test + "test_lifecycle_missing_universality_cannot_be_forged_closed"
            ),
            expected_red_signal=("test_lifecycle_missing_universality_cannot_be_forged_closed"),
        ),
    )


def run_source_flip_mutations(repo_root: Path) -> dict[str, object]:
    """Mutate decisive source properties serially and restore exact bytes."""

    results = [_run_source_flip(repo_root, case) for case in _source_flip_cases()]
    all_red = all(row["result"] == "RED" for row in results)
    return {
        "status": "pass" if all_red else "fail",
        "issues": [] if all_red else [{"code": "source_flip_mutation_survived"}],
        "results": results,
    }


def _run_source_flip(repo_root: Path, case: _SourceFlipCase) -> dict[str, object]:
    source_path = repo_root / case.source_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    source = original.decode("utf-8")
    for old, _new in case.replacements:
        if source.count(old) != 1:
            return {
                "mutation_id": case.mutation_id,
                "result": "HARNESS_ERROR",
                "proof": {"source_guard_count": source.count(old)},
            }
    baseline = _run_flip_probe(repo_root, case.probe_nodeid)
    if baseline.returncode != 0:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_flip_probe_not_green_before_mutation",
                "exit_code": baseline.returncode,
                "stdout_tail": "\n".join(baseline.stdout.splitlines()[-12:]),
                "stderr_tail": "\n".join(baseline.stderr.splitlines()[-12:]),
            },
        }
    mutated = source
    for old, new in case.replacements:
        mutated = mutated.replace(old, new, 1)
    completed: subprocess.CompletedProcess[str] | None = None
    error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(mutated, encoding="utf-8")
        completed = _run_flip_probe(repo_root, case.probe_nodeid)
    except Exception as exc:  # pragma: no cover - reported as harness evidence.
        error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    restored_probe = _run_flip_probe(repo_root, case.probe_nodeid)
    if restored_probe.returncode != 0:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_flip_probe_not_green_after_restore",
                "exit_code": restored_probe.returncode,
                "stdout_tail": "\n".join(restored_probe.stdout.splitlines()[-12:]),
                "stderr_tail": "\n".join(restored_probe.stderr.splitlines()[-12:]),
            },
        }
    if error is not None or completed is None:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": error or "source_flip_probe_not_run",
        }
    output = f"{completed.stdout}\n{completed.stderr}"
    targeted_failure = f"FAILED {case.probe_nodeid}" in output
    red = completed.returncode != 0 and targeted_failure
    return {
        "mutation_id": case.mutation_id,
        "result": "RED" if red else "GREEN_MUTATION_SURVIVED",
        "proof": {
            "exit_code": completed.returncode,
            "baseline_exit_code": baseline.returncode,
            "restored_exit_code": restored_probe.returncode,
            "expected_red_signal": case.expected_red_signal,
            "targeted_failure_observed": targeted_failure,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-12:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-12:]),
        },
    }


def _run_flip_probe(
    repo_root: Path,
    nodeid: str,
) -> subprocess.CompletedProcess[str]:
    """Run one fresh-process semantic probe without reusing bytecode or scratch."""

    with tempfile.TemporaryDirectory(prefix="polisyos-n13b-flip-pycache-") as cache_root:
        return subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "pytest",
                nodeid,
                "-q",
                "-p",
                "no:cacheprovider",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": cache_root,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )


def _check_exact(path: Path, expected: bytes, code: str) -> None:
    try:
        actual = Path(path).read_bytes()
    except OSError as exc:
        raise N13bContractError(code, str(path)) from exc
    if actual != expected:
        raise N13bContractError(code, str(path))


def _canonical_derivation_paths(
    *,
    registry_path: Path,
    universality_output: Path,
) -> tuple[Path, Path]:
    """Resolve and require the sole registry/receipt pair frozen by this owner."""

    expected_registry = (POLICY_ENGINE_ROOT / DEFAULT_DERIVATION_FAMILY_REGISTRY).resolve()
    expected_output = (POLICY_ENGINE_ROOT / DEFAULT_UNIVERSALITY_RECEIPT).resolve()
    actual_registry = (
        registry_path.resolve()
        if registry_path.is_absolute()
        else (POLICY_ENGINE_ROOT / registry_path).resolve()
    )
    actual_output = (
        universality_output.resolve()
        if universality_output.is_absolute()
        else (POLICY_ENGINE_ROOT / universality_output).resolve()
    )
    if actual_registry != expected_registry or actual_output != expected_output:
        raise N13bContractError(
            "n13b_noncanonical_derivation_owner_paths",
            f"registry={actual_registry}/receipt={actual_output}",
        )
    return actual_registry, actual_output


def _write_replace(path: Path, payload: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def _write_transaction(
    outputs: Sequence[tuple[Path, bytes]],
    *,
    remove_paths: Sequence[Path] = (),
    _replace: Any = os.replace,
    _unlink: Any = Path.unlink,
) -> None:
    """Replace and remove one output set, rolling back exact prior bytes on failure."""

    targets = tuple((Path(path), payload) for path, payload in outputs)
    removals = tuple(Path(path) for path in remove_paths)
    paths = tuple(path.resolve() for path, _payload in targets)
    removal_paths = tuple(path.resolve() for path in removals)
    if (
        len(paths) != len(set(paths))
        or len(removal_paths) != len(set(removal_paths))
        or set(paths) & set(removal_paths)
    ):
        raise N13bContractError("n13b_write_transaction_duplicate_target")
    originals: dict[Path, bytes | None] = {}
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []
    removed: list[Path] = []
    try:
        for target, payload in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            originals[target] = target.read_bytes() if target.exists() else None
            temporary = target.with_name(f".{target.name}.transaction.tmp")
            with temporary.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            staged[target] = temporary
        for target in removals:
            originals[target] = target.read_bytes() if target.exists() else None
        for target, _payload in targets:
            _replace(staged[target], target)
            replaced.append(target)
        for target in removals:
            if originals[target] is not None:
                _unlink(target)
                removed.append(target)
    except Exception as exc:
        for target in reversed(removed):
            original = originals[target]
            if original is not None:
                _write_replace(target, original)
        for target in reversed(replaced):
            original = originals[target]
            if original is None:
                target.unlink(missing_ok=True)
            else:
                _write_replace(target, original)
        raise N13bContractError("n13b_write_transaction_failed", str(exc)) from exc
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _require_baseline_unchanged(path: Path, before: str) -> None:
    after = _file_sha256(path)
    if after != before:
        raise N13bContractError("baseline_mutation_detected", f"{before} != {after}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
