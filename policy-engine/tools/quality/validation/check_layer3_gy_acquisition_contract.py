#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N7 acquisition closed-loop contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import ast
import copy
import hashlib
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.runtime.quality.acquisition_planner import (
    ACQUISITION_FAMILY_DENOMINATOR,
    ACQUISITION_RECEIPT_SCHEMA_VERSION,
    AcquisitionCaptureProvenance,
    AcquisitionFamily,
    AcquisitionNetworkCallCounter,
    AcquisitionOwnerArtifact,
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RealAcquisitionOwnerGateway,
    RecordedAcquisitionOwnerGateway,
    acquisition_request_from_world_acquirable,
    rank_acquisition_candidates_by_family,
    run_acquisition_closed_loop,
    validate_acquisition_receipt,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_acquisition_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.acquisition_contract.v1"
_FIXED_GENERATED_AT = datetime(2026, 7, 5, tzinfo=UTC)
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash"}
_EXPECTED_MUTATIONS = {
    "acquisition_compiled_first_gap_only",
    "acquisition_receipt_not_content_bound",
    "useful_design_rate_forced_without_grounding",
    "acquisition_did_not_reenter_same_cycle",
    "world_did_not_grow_after_ingest",
    "acquisition_artifact_not_captured_from_owner",
    "acquisition_provenance_not_recomputable_from_real_owner",
    "lossy_fallback_survives",
    "id_family_ignores_frontier_width",
    "affected_region_not_revalidated",
    "affected_region_under_approximated",
    "grounding_blocker_not_acquirable",
    "acquisition_hook_family_falsely_scored",
}


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _contract_design_problem() -> DesignProblem:
    """Build the real research authority used by N7 grounding probes."""

    return DesignProblem.model_validate(
        {
            "design_problem_id": "n7_owner_absence_probe",
            "problem_statement": "Acquire missing evidence without synthetic registry authority.",
            "domain": "owner_absence_probe",
            "nl_provenance": {
                "raw_request": "Acquire missing evidence.",
                "source_surface": "layer3_gy_acquisition_contract",
            },
            "authority_profile": {
                "requester_authority": "contract_probe",
                "requested_authority_level": "research",
                "mandate": "Fail closed when the canonical substrate owner is unavailable.",
            },
            "jurisdiction_time": {
                "region": "probe_region",
                "valid_time": "2026",
                "as_of": "2026-07-12",
                "policy_time": "2026",
                "data_time": "2026",
            },
            "objectives": [
                {
                    "objective_id": "resolve_owner_evidence",
                    "description": "Resolve owner evidence.",
                    "metric_id": "owner_evidence",
                }
            ],
            "constraints": [
                {
                    "constraint_id": "no_synthetic_authority",
                    "description": "Synthetic registry entries cannot satisfy acquisition.",
                    "admissibility_basis": "request_text",
                    "source_text": "Do not fabricate missing owner evidence.",
                }
            ],
            "stakeholders": [
                {
                    "stakeholder_id": "evidence_consumers",
                    "name": "Evidence consumers",
                    "role": "consumer",
                }
            ],
            "outcome_of_interest": {
                "target_variable": "owner_evidence",
                "metric_id": "owner_evidence",
                "estimand": "owner_measure",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["probe"],
                "candidate_levers": [
                    {
                        "lever_id": "owner_probe",
                        "operator_kind": "probe",
                        "instrument": "Owner evidence probe",
                        "target_slot": "owner_evidence",
                    }
                ],
            },
            "evidence_acquisition_needs": {"needs": []},
        }
    )


def generation_cycle_substrate_fence(repo_root: Path) -> dict[str, Any]:
    """Derive the N6 bootstrap caller census and canonical-owner refusal witness."""

    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        _n7_substrate_registry,
    )

    source_path = repo_root / "src/polisyos/runtime/quality/generation_cycle.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path.as_posix())
    prohibited_builders = {
        "SubstrateRegistration",
        "build_substrate_registry",
        "build_substrate_registry_entry",
    }
    production_callers: list[str] = []
    bootstrap_literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            symbol = _ast_call_symbol(node)
            if symbol in prohibited_builders:
                production_callers.append(f"{source_path.relative_to(repo_root)}:{node.lineno}:{symbol}")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "n6.bootstrap" in node.value
        ):
            bootstrap_literals.append(
                f"{source_path.relative_to(repo_root)}:{node.lineno}:{node.value}"
            )

    problem = _contract_design_problem()
    owner_absence_reason: str | None = None
    fabricated_registry = False
    with tempfile.TemporaryDirectory(prefix="policyos-n7-owner-absence-") as raw_root:
        try:
            _n7_substrate_registry(
                problem,
                families=("owner_evidence",),
                repo_root=Path(raw_root),
            )
        except GenerationCycleError as exc:
            owner_absence_reason = exc.code
        else:
            fabricated_registry = True
    status = (
        "strangled"
        if not production_callers
        and not bootstrap_literals
        and owner_absence_reason == "n7_substrate_registry_unresolved"
        and not fabricated_registry
        else "drift"
    )
    return {
        "status": status,
        "production_bootstrap_callers": sorted(production_callers),
        "bootstrap_authority_literals": sorted(bootstrap_literals),
        "owner_absence_reason": owner_absence_reason,
        "fabricated_registry": fabricated_registry,
    }


def _ast_call_symbol(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def build_live_payload(repo_root: Path) -> dict[str, Any]:
    """Recompute the frozen N7 receipt from recorded real-owner responses."""

    positive_world_snapshot = _world_snapshot(
        families=("production_msme_panel", "tax_admin_panel")
    )
    no_result_world_snapshot = _world_snapshot(families=("production_msme_panel",))
    positive = _positive_receipt(repo_root, world_snapshot=positive_world_snapshot)
    no_result = _no_result_receipt(repo_root, world_snapshot=no_result_world_snapshot)
    fail_closed = _fail_closed_receipt()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.quality.acquisition_planner.n7",
        "receipt_schema_version": ACQUISITION_RECEIPT_SCHEMA_VERSION,
        "producer": "tools.quality.validation.check_layer3_gy_acquisition_contract",
        "source_modules": [
            "src/polisyos/runtime/quality/acquisition_planner.py",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "src/polisyos/data_requirement/compiler.py",
            "src/polisyos/runtime/http/services/control_worker.py",
            "src/polisyos/fabric/retrieval/service.py",
            "src/polisyos/fabric/data_plane/orchestrator.py",
            "src/polisyos/data_forge/domains/academic/openalex/client.py",
            "src/polisyos/data_forge/domains/academic/knowledge/skg_store.py",
        ],
        "pattern_pass": {
            "relevant_ids": ["P01", "P02", "P05", "P15", "P27", "P28", "P29", "P32"],
            "existing_anti_patterns_found": [
                "P28 required-data adapter collapsed many gaps into one",
                "P29 receipt risk if owner artifacts are not content-bound",
            ],
            "target_correct_pattern": (
                "rework existing acquisition_planner owner into compile-all -> recorded owner "
                "execution -> content-bound receipt -> same-cycle affected-region re-entry"
            ),
            "missing_capability_labels": ["surface_out_of_scope"],
            "acceptance_signal": "frozen receipt validates and decisive mutations turn red",
        },
        "denominators": {
            "requirement_gap_families": [
                "data_requirement",
                "legal_authority_requirement",
                "method_validity_requirement",
                "scholar_support_requirement",
                "participation_provenance_requirement",
            ],
            "acquisition_families": list(ACQUISITION_FAMILY_DENOMINATOR),
            "scored_families": ["ID", "CERT", "COV"],
            "hook_unscored_families": ["HV", "HKG", "ADV", "AUD", "SAFE"],
        },
        "positive_receipt": positive.model_dump(mode="json"),
        "no_result_receipt": no_result.model_dump(mode="json"),
        "fail_closed_receipt": fail_closed.model_dump(mode="json"),
        "recorded_rederive_inputs": {
            "positive_world_snapshot": positive_world_snapshot.model_dump(mode="json"),
            "no_result_world_snapshot": no_result_world_snapshot.model_dump(mode="json"),
        },
        "id_width_preference": _id_width_preference(),
        "grounding_acquisition_request": acquisition_request_from_world_acquirable(
            {
                "completion_id": "cg3-world-acquirable-n7-contract",
                "blocker_kind": "world_slot",
                "world_slot": "cells.distress_score",
                "claim_ref": "claim:distress-score-grounding",
                "needed_evidence": ("measurement", "mechanism"),
            }
        ),
        "compute_economics": {
            "routine_check_network_calls": 0,
            "reentry_scope": "affected_region_only",
            "full_world_rebuild": False,
            "journal_first": True,
            "record_and_replay": True,
            "one_variable_per_live_attempt": True,
            "wall_time_reported_by_validator": True,
        },
        "known_residuals": [
            {
                "code": "hook_families_unscored",
                "status": "disclosed",
                "families": ["HV", "HKG", "ADV", "AUD", "SAFE"],
            },
            {
                "code": "adaptive_submodularity_unverified",
                "status": "disclosed",
                "detail": "bundle/complementarity is handled honestly; greedy ranking is heuristic",
            },
            {
                "code": "live_owner_lane_cloud_gated",
                "status": "disclosed",
                "detail": "routine check replays frozen receipt; network owner calls remain gated",
            },
        ],
    }
    payload["fail_closed_probes"] = _fail_closed_probes(fail_closed)
    payload["behavioral_mutations"] = _mutation_reports(payload)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the frozen N7 payload and mutation witnesses."""

    issues = _core_issues(payload, require_mutations=True)
    expected_hash = _contract_content_hash(payload)
    if payload.get("contract_content_hash") != expected_hash:
        issues.append(
            {
                "code": "acquisition_contract_content_hash_drift",
                "expected": expected_hash,
                "actual": payload.get("contract_content_hash"),
            }
        )
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed frozen N7 artifact without network calls."""

    started = time.monotonic()
    network_counter = AcquisitionNetworkCallCounter()
    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    if not path.is_file():
        issues.append({"code": "layer3_gy_acquisition_contract_missing", "path": OUTPUT_PATH})
    else:
        issues.extend(validate_payload(json.loads(path.read_text(encoding="utf-8")))["issues"])
    substrate_fence = generation_cycle_substrate_fence(repo_root)
    if substrate_fence["status"] != "strangled":
        issues.append(
            {
                "code": "n7_generation_cycle_bootstrap_fence_drift",
                "witness": substrate_fence,
            }
        )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "generation_cycle_substrate_fence": substrate_fence,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": network_counter.network_calls,
    }


def write(repo_root: Path) -> None:
    """Write the byte-stable frozen N7 artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_contract_json_for_write(repo_root), encoding="utf-8")


def build_contract_json_for_write(repo_root: Path) -> str:
    """Return byte-stable JSON for the frozen N7 contract artifact."""

    return json.dumps(build_live_payload(repo_root), indent=2, sort_keys=True) + "\n"


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Mutate a decisive content field and require validation to turn red."""

    started = time.monotonic()
    corrupted = copy.deepcopy(_load_contract_payload(repo_root))
    corrupted["positive_receipt"]["owner_artifacts"][0]["capture_provenance"][
        "owner_response_hash"
    ] = "sha256:" + "0" * 64
    report = validate_payload(corrupted)
    if report["status"] == "fail":
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "corrupt_field_drift_detected",
                    "detected_issue_codes": sorted(
                        str(issue.get("code"))
                        for issue in report["issues"]
                        if isinstance(issue, dict)
                    ),
                },
                *report["issues"],
            ],
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
            "network_calls": AcquisitionNetworkCallCounter().network_calls,
        }
    return {
        "status": "pass",
        "issues": [{"code": "corrupt_field_drift_not_detected"}],
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": AcquisitionNetworkCallCounter().network_calls,
    }


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run the explicit rederive path over recorded owner responses."""

    started = time.monotonic()
    network_counter = AcquisitionNetworkCallCounter()
    payload = _load_contract_payload(repo_root)
    rederived = copy.deepcopy(payload)
    rederived["positive_receipt"] = _rederive_receipt_from_recording(
        payload["positive_receipt"],
        payload["recorded_rederive_inputs"]["positive_world_snapshot"],
    ).model_dump(mode="json")
    rederived["no_result_receipt"] = _rederive_receipt_from_recording(
        payload["no_result_receipt"],
        payload["recorded_rederive_inputs"]["no_result_world_snapshot"],
    ).model_dump(mode="json")
    report = validate_payload(rederived)
    report["issues"].extend(_rederive_mismatch_issues(payload, rederived))
    substrate_fence = generation_cycle_substrate_fence(repo_root)
    if substrate_fence["status"] != "strangled":
        report["issues"].append(
            {
                "code": "n7_generation_cycle_bootstrap_fence_drift",
                "witness": substrate_fence,
            }
        )
    return {
        "status": "pass" if not report["issues"] else "fail",
        "issues": report["issues"],
        "generation_cycle_substrate_fence": substrate_fence,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": network_counter.network_calls,
        "compute_economics": payload["compute_economics"],
    }


def _core_issues(payload: dict[str, Any], *, require_mutations: bool) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_drift"})
    denominators = payload.get("denominators")
    if not isinstance(denominators, dict) or tuple(
        denominators.get("acquisition_families", ())
    ) != ACQUISITION_FAMILY_DENOMINATOR:
        issues.append({"code": "acquisition_family_denominator_mismatch"})
    for key in ("positive_receipt", "no_result_receipt"):
        receipt_payload = payload.get(key)
        if not isinstance(receipt_payload, dict):
            issues.append({"code": f"{key}_missing"})
            continue
        _raw_hook_family_issues(receipt_payload, issues)
        try:
            receipt = AcquisitionReceipt.model_validate(receipt_payload)
        except (ValidationError, ValueError) as exc:
            issues.append({"code": f"{key}_invalid", "error": str(exc)})
            continue
        issues.extend(validate_acquisition_receipt(receipt))
    no_result = payload.get("no_result_receipt")
    if isinstance(no_result, dict):
        if no_result.get("real_grounding_result_count") != 0:
            issues.append({"code": "no_result_receipt_claims_grounding"})
        if no_result.get("useful_design_rate_after") != 0.0:
            issues.append({"code": "useful_design_rate_forced_without_grounding"})
    fail_closed = payload.get("fail_closed_receipt")
    if isinstance(fail_closed, dict):
        if fail_closed.get("status") != "blocked" or not fail_closed.get("fail_closed_reasons"):
            issues.append({"code": "owner_validation_did_not_fail_closed"})
    preference = payload.get("id_width_preference")
    if not isinstance(preference, dict) or not preference.get("ranked_candidates"):
        issues.append({"code": "id_width_preference_missing"})
    elif preference["ranked_candidates"][0].get("candidate_id") != "many-designs":
        issues.append({"code": "id_family_ignores_frontier_width"})
    request = payload.get("grounding_acquisition_request")
    if (
        not isinstance(request, dict)
        or request.get("request_kind") != "grounding_acquisition"
        or request.get("compiles_to_n7") is not True
    ):
        issues.append({"code": "grounding_blocker_not_acquirable"})
    economics = payload.get("compute_economics")
    if not isinstance(economics, dict) or economics.get("routine_check_network_calls") != 0:
        issues.append({"code": "routine_check_hit_network"})
    if require_mutations:
        mutations = {
            str(row.get("mutation_id")): str(row.get("status"))
            for row in payload.get("behavioral_mutations", [])
            if isinstance(row, dict)
        }
        if set(mutations) != _EXPECTED_MUTATIONS:
            issues.append(
                {
                    "code": "behavioral_mutation_denominator_mismatch",
                    "expected": sorted(_EXPECTED_MUTATIONS),
                    "actual": sorted(mutations),
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in _EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] != "red"
        )
        if not_red:
            issues.append({"code": "behavioral_mutation_not_red", "mutation_ids": not_red})
    return issues


def _mutation_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mutators = {
        "acquisition_compiled_first_gap_only": _mutate_compiled_denominator,
        "acquisition_receipt_not_content_bound": _mutate_content_binding,
        "useful_design_rate_forced_without_grounding": _mutate_forced_useful_rate,
        "acquisition_did_not_reenter_same_cycle": _mutate_reentry_cycle,
        "world_did_not_grow_after_ingest": _mutate_world_unchanged,
        "acquisition_artifact_not_captured_from_owner": _mutate_uncaptured_artifact,
        "acquisition_provenance_not_recomputable_from_real_owner": (
            _mutate_fabricated_capture_provenance
        ),
        "lossy_fallback_survives": _mutate_lossy_fallback,
        "id_family_ignores_frontier_width": _mutate_id_width_preference,
        "affected_region_not_revalidated": _mutate_revalidation_scope,
        "affected_region_under_approximated": _mutate_under_approx_region,
        "grounding_blocker_not_acquirable": _mutate_grounding_request,
        "acquisition_hook_family_falsely_scored": _mutate_hook_family_scored,
    }
    rows: list[dict[str, Any]] = []
    for mutation_id, mutator in mutators.items():
        mutated = copy.deepcopy(payload)
        mutator(mutated)
        report = _core_issues(mutated, require_mutations=False)
        rows.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if any(issue.get("code") == mutation_id for issue in report) else "green",
                "issue_codes": [str(issue.get("code")) for issue in report],
            }
        )
    return rows


def _positive_receipt(
    repo_root: Path,
    *,
    world_snapshot: AcquisitionWorldSnapshot,
) -> AcquisitionReceipt:
    data_spec, second_spec = _compiled_specs()
    skg_spec = {
        **second_spec.model_dump(mode="json"),
        "required_method_families": ["skg_schema_probe"],
    }
    gateway = RealAcquisitionOwnerGateway(
        repo_root=repo_root,
        captured_at=_FIXED_GENERATED_AT,
    )
    return run_acquisition_closed_loop(
        run_id="run-n7-contract-positive",
        acquisition_request=_n6_request(cycle_index=3),
        data_requirement_specs=(data_spec, skg_spec),
        world_snapshot=world_snapshot,
        design_problem=_contract_design_problem(),
        owner_gateway=gateway,
        useful_design_rate_before=0.0,
        generated_at=_FIXED_GENERATED_AT,
    )


def _no_result_receipt(
    repo_root: Path,
    *,
    world_snapshot: AcquisitionWorldSnapshot,
) -> AcquisitionReceipt:
    data_spec = _compiled_specs()[0]
    gateway = RealAcquisitionOwnerGateway(
        repo_root=repo_root,
        captured_at=_FIXED_GENERATED_AT,
    )
    return run_acquisition_closed_loop(
        run_id="run-n7-contract-no-result",
        acquisition_request=_n6_request(cycle_index=4),
        data_requirement_specs=(data_spec,),
        world_snapshot=world_snapshot,
        owner_gateway=gateway,
        useful_design_rate_before=0.0,
        generated_at=_FIXED_GENERATED_AT,
    )


def _fail_closed_receipt() -> AcquisitionReceipt:
    data_spec = _compiled_specs()[0]
    return run_acquisition_closed_loop(
        run_id="run-n7-contract-fail-closed",
        acquisition_request=_n6_request(cycle_index=5),
        data_requirement_specs=(data_spec,),
        world_snapshot=_world_snapshot(families=("production_msme_panel",)),
        owner_gateway=RecordedAcquisitionOwnerGateway(artifacts_by_requirement={}),
        useful_design_rate_before=0.0,
        generated_at=_FIXED_GENERATED_AT,
    )


def _rederive_receipt_from_recording(
    receipt_payload: dict[str, Any],
    world_snapshot_payload: dict[str, Any],
) -> AcquisitionReceipt:
    receipt = AcquisitionReceipt.model_validate(receipt_payload)
    artifacts_by_requirement = {
        artifact.requirement_ref: artifact
        for artifact in receipt.owner_artifacts
    }
    return run_acquisition_closed_loop(
        run_id=receipt.run_id,
        acquisition_request=receipt.acquisition_request,
        data_requirement_specs=receipt.compiled_requirement_specs,
        world_snapshot=AcquisitionWorldSnapshot.model_validate(world_snapshot_payload),
        design_problem=_contract_design_problem(),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement=artifacts_by_requirement
        ),
        useful_design_rate_before=receipt.useful_design_rate_before,
        generated_at=_FIXED_GENERATED_AT,
    )


def _rederive_mismatch_issues(
    frozen: dict[str, Any],
    rederived: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    fields = (
        "grown_world_after_ref",
        "grown_world_added_slots",
        "grown_world_delta_hash",
        "world_write_outcomes",
        "affected_region",
        "grounding_rederivations",
        "useful_design_rate_after",
        "real_grounding_result_count",
        "no_result_costed_gap",
    )
    for key in ("positive_receipt", "no_result_receipt"):
        for field in fields:
            if frozen[key].get(field) != rederived[key].get(field):
                issues.append(
                    {
                        "code": "rederive_audit_mismatch",
                        "receipt": key,
                        "field": field,
                    }
                )
    return issues


def _compiled_specs() -> tuple[DataRequirementSpec, DataRequirementSpec]:
    base = DataRequirementSpec(
        requirement_id="data-requirement:claim-source-family",
        claim_id="claim-source-family",
        required_data_families=("production_msme_panel",),
        scope=DataRequirementScope(
            population="msmes",
            geography="state_or_region",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:msme",),
        authority_profile_refs=("authority_profile.production",),
    )
    second = base.model_copy(
        update={
            "requirement_id": "data-requirement:claim-calibration-panel",
            "claim_id": "claim-calibration-panel",
            "required_data_families": ("tax_admin_panel",),
        }
    )
    return base, second


def _world_snapshot(
    *,
    families: tuple[str, ...] = ("production_msme_panel", "tax_admin_panel"),
) -> AcquisitionWorldSnapshot:
    dependency_index = {
        family: (f"design:{family.replace('_', '-')}",)
        for family in families
    }
    design_revalidation_stages = {
        design_id: ("identification", "calibration", "value_set", "grounding")
        for designs in dependency_index.values()
        for design_id in designs
    }
    return AcquisitionWorldSnapshot(
        world_ref="world://before/n7-contract",
        known_slots=families,
        dependency_index=dependency_index,
        design_revalidation_stages=design_revalidation_stages,
        substrate_registry=_substrate_registry().model_dump(mode="json"),
    )


def _n6_request(*, cycle_index: int) -> dict[str, Any]:
    return {
        "request_kind": "owner_grounding_evidence",
        "driver": "missing_supporting_data",
        "counterexample_ref": f"pdc://gy/n6/counterexample/{cycle_index:03d}",
        "cycle_index": cycle_index,
        "consumer_owner": "polisyos.runtime.quality.acquisition_planner",
        "reentry": "same_generation_cycle_index",
    }


def _id_width_preference() -> dict[str, Any]:
    candidates = [
        {
            "candidate_id": "single-design",
            "family": AcquisitionFamily.ID,
            "frontier_width_shrinkage_by_design": {"design:a": 0.55},
        },
        {
            "candidate_id": "many-designs",
            "family": AcquisitionFamily.ID,
            "frontier_width_shrinkage_by_design": {
                "design:a": 0.25,
                "design:b": 0.25,
                "design:c": 0.25,
            },
        },
    ]
    return {"ranked_candidates": list(rank_acquisition_candidates_by_family(candidates))}


def _fail_closed_probes(fail_closed_receipt: AcquisitionReceipt) -> list[dict[str, Any]]:
    issues = validate_acquisition_receipt(fail_closed_receipt)
    return [
        {
            "probe_id": "missing_owner_artifact",
            "status": "fail_closed"
            if any(issue.get("code") == "owner_validation_failed_closed" for issue in issues)
            else "open",
            "issue_codes": [str(issue.get("code")) for issue in issues],
            "network_calls": 0,
        }
    ]


def _capture_provenance(
    *,
    owner_component: str,
    endpoint: str,
    request: dict[str, object],
    response: dict[str, object],
    network_call: bool = False,
) -> AcquisitionCaptureProvenance:
    return AcquisitionCaptureProvenance.from_owner_response(
        owner_component=owner_component,
        owner_endpoint=endpoint,
        owner_request=request,
        owner_response=response,
        captured_at=_FIXED_GENERATED_AT,
        capture_mode="live_owner" if network_call else "local_substrate_owner",
        network_call=network_call,
    )


def _captured_owner_artifact(
    *,
    owner_component: str,
    requirement_ref: str,
    artifact_ref: str,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
    cost_usd: float,
) -> AcquisitionOwnerArtifact:
    payload = _owner_payload(
        acquired_family=acquired_family,
        source_id=source_id,
        candidate_id=candidate_id,
    )
    return AcquisitionOwnerArtifact.from_payload(
        owner_component=owner_component,
        requirement_ref=requirement_ref,
        artifact_ref=artifact_ref,
        payload=payload,
        cost_usd=cost_usd,
        quality={"capture": "real_owner_recording"},
        rights={"license": "recorded-open"},
        binding_refs=(candidate_id,),
        journal_ref=f"journal://n7/{acquired_family}/001",
        capture_provenance=_capture_provenance(
            owner_component=owner_component,
            endpoint=f"{owner_component}.acquire",
            request={"requirement_ref": requirement_ref},
            response=payload,
        ),
    )


def _owner_payload(
    *,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
) -> dict[str, object]:
    return {
        "owner_response_kind": "acquisition_owner_raw_response",
        "acquired_substrate_registrations": [
            _registration(
                source_id=source_id,
                family_id=acquired_family,
                snapshot_id=f"snapshot:{acquired_family}:2026-07-05",
            ).model_dump(mode="json")
        ],
        "candidate_bindings": [
            {
                "candidate_id": candidate_id,
                "candidate_content_hash": "sha256:"
                + _slug_for_contract(candidate_id)[:64].ljust(64, "0"),
                "target_world_slots": [acquired_family],
            }
        ],
    }


def _substrate_registry() -> SubstrateRegistry:
    entries = [
        build_substrate_registry_entry(
            _registration(
                source_id=f"baseline.{family_id}",
                family_id=family_id,
                snapshot_id=f"baseline:{family_id}",
            )
        )
        for family_id in ("production_msme_panel", "tax_admin_panel")
    ]
    return build_substrate_registry(
        entries,
        producer_ref="tools.quality.validation.check_layer3_gy_acquisition_contract",
        source_catalog_refs=("contract://s0/substrate-registry",),
    )


def _registration(*, source_id: str, family_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id=family_id,
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.92,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref=f"contract://coverage/{family_id}",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.82,
            trust_multiplier=0.82,
            authority_ref=f"contract://trust/{family_id}",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"manifest:{family_id}",
            authority_ref=f"contract://schema/{family_id}",
        ),
        data_version="2026-07-05",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"contract://provenance/{source_id}",),
        authority_refs=(f"contract://authority/{family_id}",),
    )


def _slug_for_contract(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum()) or "candidate"


def _raw_hook_family_issues(receipt_payload: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    for row in receipt_payload.get("acquisition_family_scores", []):
        if not isinstance(row, dict):
            continue
        family = str(row.get("family"))
        if family in {"HV", "HKG", "ADV", "AUD", "SAFE"} and (
            row.get("scored") is True or row.get("score") is not None
        ):
            issues.append({"code": "acquisition_hook_family_falsely_scored", "family": family})


def _mutate_compiled_denominator(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["compiled_spec_count"] = 1


def _mutate_content_binding(payload: dict[str, Any]) -> None:
    artifact = _first_artifact_with_registrations(payload["positive_receipt"]["owner_artifacts"])
    artifact["payload"]["acquired_substrate_registrations"][0][
        "family_id"
    ] = "ghost.nonexistent_world_slot"


def _mutate_forced_useful_rate(payload: dict[str, Any]) -> None:
    payload["no_result_receipt"]["useful_design_rate_after"] = 0.5


def _mutate_reentry_cycle(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["reentry_cycle_index"] = 99


def _mutate_world_unchanged(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["grown_world_after_ref"] = payload["positive_receipt"][
        "grown_world_before_ref"
    ]


def _mutate_lossy_fallback(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["fallback_strangle_receipt"]["status"] = "drift"
    payload["positive_receipt"]["fallback_strangle_receipt"]["surviving_callers"] = [
        "src/polisyos/runtime/quality/acquisition_planner.py:legacy"
    ]


def _mutate_uncaptured_artifact(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["owner_artifacts"][0]["capture_provenance"] = None


def _mutate_fabricated_capture_provenance(payload: dict[str, Any]) -> None:
    artifact = _first_artifact_with_registrations(payload["positive_receipt"]["owner_artifacts"])
    fabricated_payload = {
        "owner_response_kind": "acquisition_owner_raw_response",
        "acquired_substrate_registrations": artifact["payload"].get(
            "acquired_substrate_registrations",
            [],
        ),
        "candidate_bindings": artifact["payload"].get("candidate_bindings", []),
    }
    fabricated_hash = _stable_content_hash(fabricated_payload)
    artifact["payload"] = fabricated_payload
    artifact["content_hash"] = fabricated_hash
    artifact["capture_provenance"]["owner_response_hash"] = fabricated_hash


def _first_artifact_with_registrations(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    for artifact in artifacts:
        registrations = artifact.get("payload", {}).get("acquired_substrate_registrations")
        if registrations:
            return artifact
    return artifacts[0]


def _mutate_id_width_preference(payload: dict[str, Any]) -> None:
    rows = payload["id_width_preference"]["ranked_candidates"]
    payload["id_width_preference"]["ranked_candidates"] = sorted(
        rows,
        key=lambda row: str(row.get("candidate_id")),
        reverse=True,
    )


def _mutate_revalidation_scope(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["affected_region"]["rederived_design_ids"] = ["design:credit"]


def _mutate_under_approx_region(payload: dict[str, Any]) -> None:
    payload["positive_receipt"]["affected_region"]["design_ids"] = ["design:credit"]
    payload["positive_receipt"]["affected_region"]["rederived_design_ids"] = ["design:credit"]


def _mutate_grounding_request(payload: dict[str, Any]) -> None:
    payload["grounding_acquisition_request"]["request_kind"] = "owner_grounding_evidence"
    payload["grounding_acquisition_request"]["compiles_to_n7"] = False


def _mutate_hook_family_scored(payload: dict[str, Any]) -> None:
    for row in payload["positive_receipt"]["acquisition_family_scores"]:
        if row["family"] == "HV":
            row["scored"] = True
            row["score"] = 0.1
            row["status"] = "scored"
            break


def _contract_content_hash(payload: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _stable_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load_contract_payload(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / OUTPUT_PATH).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--output-format", choices={"json", "text"}, default="text")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.write:
        started = time.monotonic()
        network_counter = AcquisitionNetworkCallCounter()
        write(repo_root)
        report = {
            "status": "pass",
            "issues": [],
            "outputs": declared_outputs(),
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
            "network_calls": network_counter.network_calls,
        }
    elif args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    elif args.rederive_audit:
        report = rederive_audit(repo_root)
    else:
        report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print(
            "PASS layer3_gy_acquisition_contract "
            f"wall_time_seconds={report.get('wall_time_seconds', 0)} "
            f"network_calls={report.get('network_calls', 0)}"
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
