#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N7 acquisition closed-loop contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
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
    AcquisitionFamily,
    AcquisitionOwnerArtifact,
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
    acquisition_request_from_world_acquirable,
    rank_acquisition_candidates_by_family,
    run_acquisition_closed_loop,
    validate_acquisition_receipt,
)

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


def build_live_payload(repo_root: Path) -> dict[str, Any]:
    """Recompute the frozen N7 receipt from recorded real-owner responses."""

    del repo_root
    positive = _positive_receipt()
    no_result = _no_result_receipt()
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
    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    if not path.is_file():
        issues.append({"code": "layer3_gy_acquisition_contract_missing", "path": OUTPUT_PATH})
    else:
        issues.extend(validate_payload(json.loads(path.read_text(encoding="utf-8")))["issues"])
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": 0,
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
    corrupted["positive_receipt"]["owner_artifacts"][0]["payload"]["grounding_results"][0][
        "grounded"
    ] = False
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
            "network_calls": 0,
        }
    return {
        "status": "pass",
        "issues": [{"code": "corrupt_field_drift_not_detected"}],
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": 0,
    }


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run the explicit rederive path over recorded owner responses."""

    started = time.monotonic()
    payload = build_live_payload(repo_root)
    report = validate_payload(payload)
    return {
        "status": report["status"],
        "issues": report["issues"],
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "network_calls": 0,
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


def _positive_receipt() -> AcquisitionReceipt:
    data_spec, second_spec = _compiled_specs()
    world = _world_snapshot()
    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            data_spec.requirement_id: AcquisitionOwnerArtifact.from_payload(
                owner_component="fabric.ingestion",
                requirement_ref=data_spec.requirement_id,
                artifact_ref="fabric://recorded/production-msme-panel",
                payload={
                    "world_slots": ["production_msme_panel"],
                    "grounding_results": [{"candidate_id": "design:credit", "grounded": True}],
                },
                cost_usd=11.25,
                quality={"completeness": 0.98},
                rights={"license": "recorded-open"},
                binding_refs=("claim-source-family",),
                journal_ref="journal://n7/production-msme-panel/001",
            ),
            second_spec.requirement_id: AcquisitionOwnerArtifact.from_payload(
                owner_component="data_forge.skg",
                requirement_ref=second_spec.requirement_id,
                artifact_ref="skg://recorded/tax-admin-panel",
                payload={
                    "world_slots": ["tax_admin_panel"],
                    "grounding_results": [{"candidate_id": "design:tax", "grounded": True}],
                },
                cost_usd=7.5,
                quality={"skg_confidence": 0.91},
                rights={"license": "recorded-open"},
                binding_refs=("claim-calibration-panel",),
                journal_ref="journal://n7/tax-admin-panel/001",
            ),
        }
    )
    return run_acquisition_closed_loop(
        run_id="run-n7-contract-positive",
        acquisition_request=_n6_request(cycle_index=3),
        data_requirement_specs=(data_spec, second_spec),
        world_snapshot=world,
        owner_gateway=gateway,
        useful_design_rate_before=0.0,
        generated_at=_FIXED_GENERATED_AT,
    )


def _no_result_receipt() -> AcquisitionReceipt:
    data_spec = _compiled_specs()[0]
    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            data_spec.requirement_id: AcquisitionOwnerArtifact.from_payload(
                owner_component="fabric.retrieval",
                requirement_ref=data_spec.requirement_id,
                artifact_ref="fabric://recorded/no-result",
                payload={"world_slots": [], "grounding_results": []},
                cost_usd=3.75,
                quality={"query_validated": True},
                rights={"license": "recorded-open"},
                binding_refs=(),
                journal_ref="journal://n7/no-result/001",
            )
        }
    )
    return run_acquisition_closed_loop(
        run_id="run-n7-contract-no-result",
        acquisition_request=_n6_request(cycle_index=4),
        data_requirement_specs=(data_spec,),
        world_snapshot=_world_snapshot(),
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
        world_snapshot=_world_snapshot(),
        owner_gateway=RecordedAcquisitionOwnerGateway(artifacts_by_requirement={}),
        useful_design_rate_before=0.0,
        generated_at=_FIXED_GENERATED_AT,
    )


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


def _world_snapshot() -> AcquisitionWorldSnapshot:
    return AcquisitionWorldSnapshot(
        world_ref="world://before/n7-contract",
        known_slots=("production_msme_panel",),
        dependency_index={
            "production_msme_panel": ("design:credit", "design:portfolio"),
            "tax_admin_panel": ("design:tax", "design:portfolio"),
        },
        design_revalidation_stages={
            "design:credit": ("identification", "calibration", "value_set", "grounding"),
            "design:portfolio": ("identification", "calibration", "value_set", "grounding"),
            "design:tax": ("identification", "calibration", "value_set", "grounding"),
        },
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
    payload["positive_receipt"]["owner_artifacts"][0]["payload"]["grounding_results"][0][
        "grounded"
    ] = False


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
        write(repo_root)
        report = {
            "status": "pass",
            "issues": [],
            "outputs": declared_outputs(),
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
            "network_calls": 0,
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
    raise SystemExit(main())
