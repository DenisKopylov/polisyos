#!/usr/bin/env python3
"""Validate the CGF grounding credal-reference contract artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from polisyos.pdc import gy_content_hash

OUTPUT_PATH = "architecture/policy_design_case/grounding_credal_reference_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_credal_reference_contract.v1"
EXPECTED_MUTATIONS = {
    "contested_collapsed_to_scalar",
    "unstatusable_default_confirmed",
    "contested_essential_all_confirmed",
    "reference_repair_no_stale",
    "free_grow_edge_requires_hand_table",
}
REFERENCE_STATUSES = {
    "confirmed",
    "contested",
    "incomplete",
    "deprecated",
    "out_of_scope",
}


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configure_validation_jax_platform() -> None:
    """Keep local validator WMR builds reproducible without changing runtime code."""

    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")


def _scope_with_counts(
    scope: dict[str, Any],
    denominator_status: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    counted_scope = _copy(scope)
    for edge_class in counted_scope.get("included_edge_classes", []):
        modality = str(edge_class.get("modality") or "")
        counts = denominator_status.get(modality, {})
        edge_class["n_total"] = counts.get("n_total", 0)
        edge_class["n_statused"] = counts.get("n_statused", 0)
        edge_class["status_counts"] = counts.get("status_counts", {})
    return counted_scope


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the CGF credal-reference contract from live owners/data."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        all_essential_confirmed,
        bind_grounding_certificate_reference,
        build_credal_reference,
        build_grounding_backend_availability,
        derive_variable_alignment_edge,
        edge_payload_sample,
        essential_edge_scope_definition,
        reference_certificate_staleness,
        reference_lift,
        replace_reference_edge,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    backend = build_grounding_backend_availability()
    counts = reference.denominator_counts()
    total_edges = sum(modality_counts["total"] for modality_counts in counts.values())
    denominator_status = {
        modality: {
            "n_total": modality_counts["total"],
            "n_statused": sum(
                count
                for status, count in modality_counts.items()
                if status in REFERENCE_STATUSES
            ),
            "status_counts": {
                status: count
                for status, count in modality_counts.items()
                if status in REFERENCE_STATUSES
            },
        }
        for modality, modality_counts in counts.items()
    }
    contested_edge = _first_edge(
        reference,
        modality_prefix="L2_",
        status="contested",
        preferred_modality="L2_CONTESTED_EDGE",
    )
    deprecated_l3_edge = _first_edge(
        reference,
        modality_prefix="L3_",
        status="deprecated",
        preferred_modality="L3_RULE_THRESHOLD",
    )
    if contested_edge is None:
        raise RuntimeError("real_contested_l2_edge_missing")
    if deprecated_l3_edge is None:
        raise RuntimeError("real_deprecated_l3_edge_missing")
    contested_edges = [
        edge for edge in reference.essential_edges.values() if edge.status == "contested"
    ]
    contested_set_valued_failures = [
        _edge_key_text(edge.key) for edge in contested_edges if not edge.is_set_valued
    ]

    contested_scope = [contested_edge.key]
    contested_lift = reference_lift(reference, contested_scope)
    contested_lift_payload = contested_lift[_edge_key_text(contested_edge.key)]

    fake_key = ("L2_CAUSAL_EDGE", "cg0_fake_novel_edge_not_in_reference")
    fake_lift = reference_lift(reference, [fake_key])
    fake_lift_payload = fake_lift[_edge_key_text(fake_key)]

    free_grow_edge = derive_variable_alignment_edge(
        {
            "approved": True,
            "canonical_name": "cg0.free_grow_reference_probe",
            "confidence": 0.91,
            "method": "contract_free_grow_probe",
            "synonym": "cg0 novel alignment synonym",
        }
    )
    certificate = bind_grounding_certificate_reference(
        reference,
        certificate_id="cg0-reference-repair-stale-probe",
        edge_scope=contested_scope,
    )
    repaired_edge = CredalReferenceEdge(
        modality=contested_edge.modality,
        edge_id=contested_edge.edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"repaired_from": contested_edge.edge_id},
                "reference_repair_confirmed_probe",
            ),
        ),
        provenance={
            **dict(contested_edge.provenance),
            "repair_probe": "contract_reference_repair",
        },
        unit=contested_edge.unit,
        scale=contested_edge.scale,
    )
    repaired_reference = replace_reference_edge(reference, repaired_edge)
    staleness = reference_certificate_staleness(certificate, repaired_reference)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_credal_reference",
        "owner": (
            "polisyos.runtime.quality.credal_reference view over existing "
            "L2/L3/L6/WMR owners"
        ),
        "source_modules": [
            "src/polisyos/runtime/quality/credal_reference.py",
            "src/polisyos/runtime/quality/substrate_registry.py",
            "src/polisyos/runtime/quality/intervention_substrate.py",
            "src/polisyos/runtime/quality/world_model_record.py",
            "src/polisyos/runtime/quality/data_state_substrate.py",
            "src/polisyos/lex/knowledge/store.py",
        ],
        "reuse_existing_owners": [
            "L2 Scholar Knowledge Graph DuckDB tables",
            "L3 LegalKnowledgeStore / lex DuckDB tables",
            "L6 intervention substrate bundle and owner validation",
            "WorldModelRecord.policy_slot_map",
            "SubstrateRegistry content-addressed owner paths",
            "GY-N12-style epoch/hash staling through scoped edge hashes",
        ],
        "no_second_reference_store": True,
        "essential_edge_scope": _scope_with_counts(
            essential_edge_scope_definition(),
            denominator_status,
        ),
        "reference": {
            "schema_version": reference.schema_version,
            "as_of": reference.as_of,
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "component_versions": dict(sorted(reference.component_versions.items())),
            "total_essential_edges": total_edges,
            "denominator_status": denominator_status,
            "sample_edges": edge_payload_sample(reference, limit_per_status=2),
        },
        "capability_reality": {
            "typed_contract_artifact": (
                "CredalReference + CredalReferenceEdge + "
                "GroundingBackendAvailability"
            ),
            "producer": "build_credal_reference over L2/L3/L6/WMR owners",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "reference_lift(edge_scope) + all_essential_confirmed(edge_scope) "
                "for CG1/CG2 relation binding"
            ),
            "consumer": "CGF relation lifting and GroundingCertificate epoch binding",
            "verification": (
                "this recomputing validator plus focused tests/mutation probes"
            ),
            "surface": "generated Policy Design Case CGF contract artifact",
            "semantic_test": (
                "contested set-valued lift, fake-edge fail-closed, free-grow "
                "status derivation, reference-repair staling, backend gate"
            ),
        },
        "pattern_pass": {
            "relevant_ids": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P07",
                "P08",
                "P10",
                "P12",
                "P15",
                "P27",
                "P29",
                "P30",
                "P31",
                "P32",
                "P33",
                "P34",
            ],
            "target_correct_pattern": (
                "owner-first credal view; statuses derived generically from owner "
                "signals; set-valued ambiguity preserved through scoped lift"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": (
                "full-denominator status coverage, mutation-red set-valued "
                "discipline, and epoch staling"
            ),
        },
        "probes": {
            "contested_l2_set_valued": {
                "edge_key": _edge_key_text(contested_edge.key),
                "status": contested_edge.status,
                "is_set_valued": contested_lift_payload["is_set_valued"],
                "all_essential_confirmed": all_essential_confirmed(
                    reference,
                    contested_scope,
                ),
                "completion_kinds": [
                    completion["completion_kind"]
                    for completion in contested_lift_payload[
                        "admissible_completions"
                    ]
                ],
                "lift": contested_lift_payload,
            },
            "all_contested_edges_set_valued": {
                "n_contested": len(contested_edges),
                "n_failures": len(contested_set_valued_failures),
                "failure_examples": contested_set_valued_failures[:10],
            },
            "fake_novel_fail_closed": {
                "edge_key": _edge_key_text(fake_key),
                "status": fake_lift_payload["status"],
                "is_set_valued": fake_lift_payload["is_set_valued"],
                "all_essential_confirmed": all_essential_confirmed(
                    reference,
                    [fake_key],
                ),
                "lift": fake_lift_payload,
            },
            "free_grow_status_derivation": {
                "edge_key": _edge_key_text(free_grow_edge.key),
                "edge_known_to_code": False,
                "status": free_grow_edge.status,
                "admissible_completions": [
                    completion.to_payload()
                    for completion in free_grow_edge.admissible_completions
                ],
                "provenance": dict(free_grow_edge.provenance),
            },
            "real_l3_superseded_threshold_deprecated": {
                "edge_key": _edge_key_text(deprecated_l3_edge.key),
                "status": deprecated_l3_edge.status,
                "provenance": dict(deprecated_l3_edge.provenance),
                "admissible_completions": [
                    completion.to_payload()
                    for completion in deprecated_l3_edge.admissible_completions
                ],
            },
            "reference_repair_stales_certificate": {
                "certificate_id": certificate.certificate_id,
                "old_reference_epoch": certificate.reference_epoch,
                "new_reference_epoch": repaired_reference.reference_epoch,
                "status": staleness.status,
                "reasons": list(staleness.reasons),
                "stale_edge_keys": list(staleness.stale_edge_keys),
            },
        },
        "grounding_backend_availability": backend.to_payload(),
        "status_derivation": {
            "derived_from_owner_signals": True,
            "hand_assigned_edge_status_table": False,
            "fail_closed_default": "incomplete",
            "nonexistent_query_default": "out_of_scope",
        },
        "set_valued_contract": {
            "contested_edges_raise_ambiguity": True,
            "scalar_confidence_penalty_allowed": False,
            "lift_scope": "symbolic_edge_scope_only",
            "full_product_materialized": False,
        },
        "stale_conditions": [
            "reference_epoch_changed",
            "reference_hash_changed",
            "scoped_edge_hash_changed",
            "L2 alignment/contested-edge/canonical-variable repair",
            "L3 threshold or amendment temporal/version change",
            "L6 bundle or owner-validation binding change",
            "WorldModelRecord policy-slot map/content hash change",
        ],
        "behavioral_mutations": [],
    }
    payload["behavioral_mutations"] = _mutation_reports(payload)
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a recomputed or committed CGF credal-reference payload."""

    issues = _core_issues(payload, require_mutations=True)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(
    repo_root: Path | None = None,
    *,
    live_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate committed artifact drift and live CGF reference behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    output_path = repo_root / OUTPUT_PATH
    live = live_payload or build_live_payload(repo_root)
    issues = _core_issues(live, require_mutations=True)
    if not output_path.is_file():
        issues.append(
            {"code": "grounding_credal_reference_contract_missing", "path": OUTPUT_PATH}
        )
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "grounding_credal_reference_contract_invalid_json",
                    "error": str(exc),
                    "path": OUTPUT_PATH,
                }
            )
    if committed is not None and committed != live:
        issues.append(
            {"code": "grounding_credal_reference_contract_drift", "path": OUTPUT_PATH}
        )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "reference_epoch": live["reference"]["reference_epoch"],
        "reference_hash": live["reference"]["reference_hash"],
        "total_essential_edges": live["reference"]["total_essential_edges"],
        "denominator_status": live["reference"]["denominator_status"],
        "set_valued_evidence": live["probes"]["contested_l2_set_valued"],
        "backend_availability": live["grounding_backend_availability"],
    }


def write(repo_root: Path, *, payload: dict[str, Any] | None = None) -> None:
    """Write the live CGF credal-reference contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(
        json.dumps(live, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove corrupt decisive fields turn the contract red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    corrupted["reference"]["reference_hash"] = "sha256:corrupt"
    corrupted["probes"]["contested_l2_set_valued"]["is_set_valued"] = False
    corrupted["probes"]["contested_l2_set_valued"]["all_essential_confirmed"] = True
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "corrupt_field_drift_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
    }


def _core_issues(
    payload: dict[str, Any],
    *,
    require_mutations: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_credal_reference_schema_version_mismatch"})
    if payload.get("no_second_reference_store") is not True:
        issues.append({"code": "grounding_credal_reference_second_store_declared"})
    scope = payload.get("essential_edge_scope", {})
    if not scope.get("criterion"):
        issues.append({"code": "grounding_credal_reference_scope_criterion_missing"})
    included_scope = scope.get("included_edge_classes", [])
    excluded_scope = scope.get("excluded_edge_classes", [])
    if not included_scope:
        issues.append({"code": "grounding_credal_reference_scope_inclusions_missing"})
    if not excluded_scope:
        issues.append({"code": "grounding_credal_reference_scope_exclusions_missing"})
    reference = payload.get("reference", {})
    if not str(reference.get("reference_hash", "")).startswith("sha256:"):
        issues.append({"code": "grounding_credal_reference_hash_missing"})
    if not str(reference.get("reference_epoch", "")).startswith("kref:"):
        issues.append({"code": "grounding_credal_reference_epoch_missing"})
    denominator = reference.get("denominator_status", {})
    if not denominator:
        issues.append({"code": "grounding_credal_reference_denominator_missing"})
    for modality, counts in denominator.items():
        if counts.get("n_total") != counts.get("n_statused"):
            issues.append(
                {
                    "code": "grounding_credal_reference_denominator_not_full",
                    "modality": modality,
                }
            )
        if counts.get("n_total", 0) <= 0:
            issues.append(
                {
                    "code": "grounding_credal_reference_modality_empty",
                    "modality": modality,
                }
            )
    if sum(counts.get("n_total", 0) for counts in denominator.values()) != reference.get(
        "total_essential_edges"
    ):
        issues.append({"code": "grounding_credal_reference_total_count_mismatch"})
    for edge_class in included_scope:
        modality = str(edge_class.get("modality") or "")
        if not modality:
            issues.append({"code": "grounding_credal_reference_scope_modality_missing"})
            continue
        counts = denominator.get(modality)
        if not counts:
            issues.append(
                {
                    "code": "grounding_credal_reference_scope_modality_not_counted",
                    "modality": modality,
                }
            )
            continue
        if edge_class.get("n_total") != counts.get("n_total"):
            issues.append(
                {
                    "code": "grounding_credal_reference_scope_count_mismatch",
                    "modality": modality,
                }
            )
        if counts.get("n_total", 0) <= 0:
            issues.append(
                {
                    "code": "grounding_credal_reference_scope_modality_empty",
                    "modality": modality,
                }
            )
    for edge_class in excluded_scope:
        if not edge_class.get("owner_table") or not edge_class.get("reason"):
            issues.append({"code": "grounding_credal_reference_exclusion_reason_missing"})
        if edge_class.get("criterion_decision") != "excluded":
            issues.append({"code": "grounding_credal_reference_exclusion_decision_missing"})

    probes = payload.get("probes", {})
    contested = probes.get("contested_l2_set_valued", {})
    if contested.get("status") != "contested":
        issues.append({"code": "contested_l2_probe_not_contested"})
    if contested.get("is_set_valued") is not True:
        issues.append({"code": "contested_l2_probe_not_set_valued"})
    if contested.get("all_essential_confirmed") is not False:
        issues.append({"code": "contested_l2_probe_does_not_block_confirmation"})
    if len(contested.get("completion_kinds", [])) < 2:
        issues.append({"code": "contested_l2_probe_completion_set_collapsed"})
    if _contains_key(contested, "scalar_confidence"):
        issues.append({"code": "contested_l2_probe_scalar_confidence_laundered"})
    contested_summary = probes.get("all_contested_edges_set_valued", {})
    if contested_summary.get("n_contested", 0) <= 0:
        issues.append({"code": "all_contested_edges_probe_empty"})
    if contested_summary.get("n_failures") != 0:
        issues.append(
            {
                "code": "all_contested_edges_set_valued_failure",
                "failure_examples": contested_summary.get("failure_examples", []),
            }
        )

    fake = probes.get("fake_novel_fail_closed", {})
    if fake.get("status") != "out_of_scope":
        issues.append({"code": "fake_reference_edge_did_not_fail_closed"})
    if fake.get("all_essential_confirmed") is not False:
        issues.append({"code": "fake_reference_edge_confirmed"})

    free_grow = probes.get("free_grow_status_derivation", {})
    if free_grow.get("edge_known_to_code") is not False:
        issues.append({"code": "free_grow_probe_known_to_code"})
    if free_grow.get("status") not in REFERENCE_STATUSES:
        issues.append({"code": "free_grow_edge_not_statused"})
    if free_grow.get("status") != "confirmed":
        issues.append({"code": "free_grow_high_trust_edge_not_confirmed"})

    deprecated = probes.get("real_l3_superseded_threshold_deprecated", {})
    if not str(deprecated.get("edge_key", "")).startswith("L3_RULE_THRESHOLD::"):
        issues.append({"code": "real_l3_deprecated_probe_not_threshold"})
    if deprecated.get("status") != "deprecated":
        issues.append({"code": "real_l3_superseded_threshold_not_deprecated"})

    staling = probes.get("reference_repair_stales_certificate", {})
    if staling.get("status") != "stale":
        issues.append({"code": "reference_repair_did_not_stale_certificate"})
    if "scoped_edge_hash_changed" not in staling.get("reasons", []):
        issues.append({"code": "reference_repair_missing_scoped_edge_stale_reason"})

    backend = payload.get("grounding_backend_availability", {})
    backend_hash = backend.get("content_hash")
    backend_without_hash = {key: value for key, value in backend.items() if key != "content_hash"}
    if backend_hash != gy_content_hash(backend_without_hash):
        issues.append({"code": "grounding_backend_availability_hash_mismatch"})
    if backend.get("required_backend_status") != "available":
        issues.append({"code": "grounding_backend_required_cp_sat_unavailable"})
    solver = backend.get("solver", {})
    if solver.get("name") != "ortools_cp_sat" or solver.get("available") is not True:
        issues.append({"code": "grounding_backend_cp_sat_not_pinned"})
    if solver.get("unsat_core") != "assumptions":
        issues.append({"code": "grounding_backend_cp_sat_unsat_core_missing"})
    if backend.get("dense", {}).get("status") != "deferred":
        issues.append({"code": "grounding_backend_dense_not_deferred"})

    status_derivation = payload.get("status_derivation", {})
    if status_derivation.get("hand_assigned_edge_status_table") is not False:
        issues.append({"code": "grounding_reference_status_hand_table_declared"})
    if status_derivation.get("fail_closed_default") != "incomplete":
        issues.append({"code": "grounding_reference_fail_closed_default_missing"})

    set_valued = payload.get("set_valued_contract", {})
    if set_valued.get("scalar_confidence_penalty_allowed") is not False:
        issues.append({"code": "grounding_reference_scalar_penalty_allowed"})
    if set_valued.get("full_product_materialized") is not False:
        issues.append({"code": "grounding_reference_full_product_materialized"})

    if require_mutations:
        mutations = {
            str(mutation.get("mutation_id")): str(mutation.get("status"))
            for mutation in payload.get("behavioral_mutations", [])
        }
        missing = sorted(EXPECTED_MUTATIONS.difference(mutations))
        if missing:
            issues.append(
                {
                    "code": "grounding_credal_reference_required_mutation_missing",
                    "missing_mutations": missing,
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] != "red"
        )
        if not_red:
            issues.append(
                {
                    "code": "grounding_credal_reference_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _mutation_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = {
        "contested_collapsed_to_scalar": _mutate_contested_collapsed_to_scalar,
        "unstatusable_default_confirmed": _mutate_unstatusable_default_confirmed,
        "contested_essential_all_confirmed": _mutate_contested_all_confirmed,
        "reference_repair_no_stale": _mutate_reference_repair_no_stale,
        "free_grow_edge_requires_hand_table": _mutate_free_grow_missing_status,
    }
    reports: list[dict[str, Any]] = []
    for mutation_id, mutator in mutations.items():
        mutated = _copy(payload)
        mutator(mutated)
        issues = _core_issues(mutated, require_mutations=False)
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if issues else "green",
                "issue_codes": [issue["code"] for issue in issues],
            }
        )
    return reports


def _mutate_contested_collapsed_to_scalar(payload: dict[str, Any]) -> None:
    probe = payload["probes"]["contested_l2_set_valued"]
    scalar_completion = {
        "completion_kind": "fixed",
        "reason": "scalar_penalty_not_credal",
        "value": {"scalar_confidence": 0.72},
    }
    probe["is_set_valued"] = False
    probe["completion_kinds"] = ["fixed"]
    probe["lift"]["is_set_valued"] = False
    probe["lift"]["admissible_completions"] = [scalar_completion]


def _mutate_unstatusable_default_confirmed(payload: dict[str, Any]) -> None:
    probe = payload["probes"]["fake_novel_fail_closed"]
    probe["status"] = "confirmed"
    probe["all_essential_confirmed"] = True
    probe["lift"]["status"] = "confirmed"
    probe["lift"]["admissible_completions"] = [
        {
            "completion_kind": "fixed",
            "reason": "default_confirmed",
            "value": {"edge_key": probe["edge_key"]},
        }
    ]


def _mutate_contested_all_confirmed(payload: dict[str, Any]) -> None:
    payload["probes"]["contested_l2_set_valued"]["all_essential_confirmed"] = True


def _mutate_reference_repair_no_stale(payload: dict[str, Any]) -> None:
    probe = payload["probes"]["reference_repair_stales_certificate"]
    probe["status"] = "current"
    probe["reasons"] = []
    probe["stale_edge_keys"] = []


def _mutate_free_grow_missing_status(payload: dict[str, Any]) -> None:
    payload["probes"]["free_grow_status_derivation"]["status"] = "missing"


def _first_edge(
    reference: Any,
    *,
    modality_prefix: str,
    status: str,
    preferred_modality: str,
) -> Any:
    preferred = [
        edge
        for edge in reference.essential_edges.values()
        if edge.modality == preferred_modality and edge.status == status
    ]
    if preferred:
        return sorted(preferred, key=lambda item: item.key)[0]
    candidates = [
        edge
        for edge in reference.essential_edges.values()
        if edge.modality.startswith(modality_prefix) and edge.status == status
    ]
    return sorted(candidates, key=lambda item: item.key)[0] if candidates else None


def _contains_key(value: Any, key_name: str) -> bool:
    if isinstance(value, dict):
        return key_name in value or any(
            _contains_key(child, key_name) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(child, key_name) for child in value)
    return False


def _edge_key_text(key: tuple[str, str]) -> str:
    return f"{key[0]}::{key[1]}"


def _copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CGF grounding credal-reference contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)

    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    else:
        live_payload = build_live_payload(repo_root) if args.write else None
        if args.write:
            write(repo_root, payload=live_payload)
        report = validate(repo_root, live_payload=live_payload)

    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    else:
        print("grounding credal reference contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
