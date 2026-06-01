#!/usr/bin/env python3
"""Validate the Layer 2 S0 readiness bundle."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

DEFAULT_READINESS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_readiness_manifest.json"
)
DEFAULT_MINIMAL_SEED_PATH = Path(
    "architecture/policy_design_case/layer2_minimal_seed_manifest.json"
)
DEFAULT_DEPENDENCY_DAG_PATH = Path("architecture/policy_design_case/layer2_dependency_dag.json")
DEFAULT_SLICE_CELL_MATRIX_PATH = Path(
    "architecture/policy_design_case/layer2_slice_cell_matrix.toml"
)
DEFAULT_FLOOR_GOVERNANCE_PATH = Path(
    "architecture/policy_design_case/layer2_floor_governance.toml"
)
DEFAULT_ARTIFACT_TRACEABILITY_PATH = Path(
    "architecture/policy_design_case/layer2_artifact_traceability.toml"
)
DEFAULT_CORPUS_PARTITION_PATH = Path(
    "architecture/policy_design_case/layer2_corpus_partition.json"
)
DEFAULT_FIRST_PROVING_CASE_PATH = Path(
    "architecture/policy_design_case/layer2_first_proving_case.json"
)
DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"
)
DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json"
)
DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json"
)
DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json"
)
DEFAULT_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")

REQUIRED_SLICES = {f"S{number}" for number in range(15)}
REQUIRED_UA_MSME_CONSTRUCTS = {
    "credit_program_enrollment",
    "firm_survival",
    "regional_displacement_pressure",
    "credit_access",
    "fiscal_burden_per_beneficiary",
}
REQUIRED_ARTIFACT_NAMES = {
    "MinimalSeedManifest",
    "ValueOfInformationEstimate",
    "GovernanceDecisionClass",
    "AxisPositionDeclaration",
    "AxisFirewallStatus",
    "CertifiedOperationEnvelope",
    "DesignRecord",
    "ClusterInterfaceContract",
    "ClusterHandoffRecord",
    "ConstructOntologyDelta",
    "CapabilityBindingResult",
    "CommitmentProfileRecord",
    "ClusterAuthorityDimensionRecord",
    "ForecastCalibrationRecord",
    "ProofCarryingAnalyticsRecord",
    "CertifiedEnvelopeDelta",
}
MATURITY_QUALIFIERS = {"fail_closed", "predictive"}
S5_CLOSED_CELLS = {
    "SYSTEM.connectivity_modularity",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.scale_composition",
}
S5_COUPLING_REGIMES = {
    "modular",
    "near_decomposable",
    "hierarchically_coupled",
    "entangled",
}
S5_REQUIRED_ARTIFACTS = {
    "CompositionReceipt",
    "ComputationalTractabilityBudget",
    "CouplingGraph",
    "CouplingRegimeClassification",
    "DecompositionResult",
    "DesignInterfaceContract",
    "RecursiveDesignGraph",
    "SystemDynamicsRequirement",
}
S5_REQUIRED_NESTED_RECORDS = {
    "BoundaryCouplingClassification",
    "CompositionLawCheck",
    "ForecastSupportScope",
    "ModuleDiscoveryResult",
}
S5_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "equilibrium_prediction_authority",
    "whole_design_authority_without_coupling_graph",
    "whole_design_authority_from_syntactic_decomposition",
    "whole_design_authority_from_user_supplied_module_split",
    "false_modular_decomposition",
    "weakened_authority_from_tractability_cutoff",
}
S6_CLOSED_CELLS = {
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
}
S6_REQUIRED_ARTIFACTS = {
    "MeasurabilityAdequacyRecord",
    "AggregationValidityRecord",
    "CapacityFeasibilityRecord",
    "MandateLegitimacyRecord",
    "StrategicResponseRecord",
    "ClusterAuthorityDimensionRecord",
}
S6_REQUIRED_FIREWALLS = {"P18", "P19", "P21", "P22", "P24"}
S6_REQUIRED_BRIDGE_CONSUMERS = {
    "KNOWLEDGE.epistemic_regime",
    "ACTOR.value_choice_provenance",
    "INTERVENTION.targeting",
    "INTERVENTION.feasibility",
    "DESIGNER_ITSELF.envelope_membership",
    "PUBLIC.legitimacy_disclosure",
    "INTERVENTION.design_candidate",
    "SYSTEM.post_intervention_dgp",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.robustness",
}
S6_C3_AUTHORITY_DIMENSIONS = {
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
}
S6_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "delegation_authority",
    "value_choice_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "rich_response_model_authority",
    "capacity_transfer_authority",
    "mandate_authority_from_llm",
    "proxy_construct_equivalence_without_disclosure",
    "aggregation_scope_transfer_without_validity",
    "post_policy_effect_claim_without_response_model",
}


def load_layer2_readiness_payloads(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Load all governed S0 readiness payloads."""

    root = Path(repo_root)
    return {
        "readiness_manifest": _load_json(root / DEFAULT_READINESS_MANIFEST_PATH),
        "minimal_seed": _load_json(root / DEFAULT_MINIMAL_SEED_PATH),
        "dependency_dag": _load_json(root / DEFAULT_DEPENDENCY_DAG_PATH),
        "slice_cell_matrix": _load_toml(root / DEFAULT_SLICE_CELL_MATRIX_PATH),
        "floor_governance": _load_toml(root / DEFAULT_FLOOR_GOVERNANCE_PATH),
        "artifact_traceability": _load_toml(root / DEFAULT_ARTIFACT_TRACEABILITY_PATH),
        "corpus_partition": _load_json(root / DEFAULT_CORPUS_PARTITION_PATH),
        "first_proving_case": _load_json(root / DEFAULT_FIRST_PROVING_CASE_PATH),
        "s3_substrate_acquisition": _load_optional_json(
            root / DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH
        ),
        "s4_epistemic_regime": _load_optional_json(
            root / DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH
        ),
        "s5_coupling_composition": _load_optional_json(
            root / DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH
        ),
        "s6_blind_spot_firewalls": _load_optional_json(
            root / DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH
        ),
        "inventory": _load_json(root / DEFAULT_INVENTORY_PATH),
        "cluster_map": cluster_map.load_cluster_ownership_map(root),
    }


def validate_layer2_readiness(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S0 readiness from files in the repository."""

    root = Path(repo_root)
    missing = [
        path.as_posix()
        for path in (
            DEFAULT_READINESS_MANIFEST_PATH,
            DEFAULT_MINIMAL_SEED_PATH,
            DEFAULT_DEPENDENCY_DAG_PATH,
            DEFAULT_SLICE_CELL_MATRIX_PATH,
            DEFAULT_FLOOR_GOVERNANCE_PATH,
            DEFAULT_ARTIFACT_TRACEABILITY_PATH,
            DEFAULT_CORPUS_PARTITION_PATH,
            DEFAULT_FIRST_PROVING_CASE_PATH,
        )
        if not (root / path).exists()
    ]
    if missing:
        return _result(
            [
                {
                    "code": "layer2_readiness_artifact_missing",
                    "message": "Missing S0 readiness artifacts: " + ", ".join(missing),
                }
            ],
            summary={},
        )
    return validate_layer2_readiness_payloads(load_layer2_readiness_payloads(root))


def validate_layer2_readiness_payloads(payloads: dict[str, Any]) -> dict[str, Any]:
    """Validate already-loaded S0 readiness payloads."""

    issues: list[dict[str, str]] = []
    cluster_payload = payloads["cluster_map"]
    current_open_cells = _open_cell_refs(cluster_payload)
    ratchet_states = set(cluster_payload.get("ratchet_state_vocabulary", []))

    matrix = payloads["slice_cell_matrix"]
    open_cell_count_baseline = int(matrix["open_cell_count_baseline"])
    assignments = list(matrix.get("assignment", []))
    assigned_cells = {str(entry.get("cell_ref", "")) for entry in assignments}
    if len(assigned_cells) != open_cell_count_baseline:
        issues.append(
            _issue(
                "layer2_slice_cell_matrix_baseline_count_mismatch",
                "Slice-cell matrix must preserve the S0 baseline open-cell assignments.",
            )
        )
    if not current_open_cells <= assigned_cells:
        issues.append(
            _issue(
                "layer2_slice_cell_matrix_current_open_cell_not_assigned",
                "Every current open cell must remain assigned in the S0 slice-cell baseline.",
            )
        )

    for entry in assignments:
        target_state = str(entry.get("target_state", ""))
        if target_state not in ratchet_states:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_ratchet_state",
                    f"Unknown ratchet target_state={target_state}.",
                )
            )
        if target_state in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_maturity_used_as_state",
                    f"Maturity qualifier used as ratchet state: {target_state}.",
                )
            )
        maturity = entry.get("maturity")
        if maturity is not None and str(maturity) not in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_maturity",
                    f"Unknown maturity qualifier: {maturity}.",
                )
            )

    s0_cells_closed = list(matrix.get("s0_cells_closed", []))
    if s0_cells_closed:
        issues.append(
            _issue(
                "layer2_s0_must_not_close_cells",
                "S0 readiness cannot close cluster cells.",
            )
        )

    dag_nodes = set(payloads["dependency_dag"].get("nodes", {}))
    if dag_nodes != REQUIRED_SLICES:
        issues.append(
            _issue(
                "layer2_dependency_dag_slice_set_invalid",
                "Dependency DAG must declare S0 through S14 exactly.",
            )
        )
    if "S0" not in payloads["dependency_dag"]["nodes"]["S2"].get("prerequisites", []):
        issues.append(
            _issue(
                "layer2_dependency_dag_s2_missing_s0",
                "S2 must depend on S0.",
            )
        )

    _validate_minimal_seed(payloads["minimal_seed"], issues)
    _validate_floors(payloads["floor_governance"], issues)
    _validate_artifact_traceability(payloads["artifact_traceability"], issues)
    _validate_corpus_partition(payloads["corpus_partition"], issues)
    _validate_first_proving_case(payloads["first_proving_case"], issues)
    _validate_readiness_manifest(payloads["readiness_manifest"], issues)
    _validate_s3_substrate_acquisition(
        s3=payloads.get("s3_substrate_acquisition"),
        floor_governance=payloads["floor_governance"],
        first_proving_case=payloads["first_proving_case"],
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s4_epistemic_regime(
        s4=payloads.get("s4_epistemic_regime"),
        floor_governance=payloads["floor_governance"],
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s5_coupling_composition(
        s5=payloads.get("s5_coupling_composition"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s6_blind_spot_firewalls(
        s6=payloads.get("s6_blind_spot_firewalls"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    closed_since_s0 = sorted(assigned_cells - current_open_cells)
    s3 = payloads.get("s3_substrate_acquisition")
    s3_summary = (
        {
            "s3_acquisition_branch_state": s3.get("acquisition_branch_state"),
            "s3_expected_current_open_cell_count": s3.get(
                "expected_current_open_cell_count"
            ),
        }
        if isinstance(s3, dict) and s3
        else {}
    )
    s4 = payloads.get("s4_epistemic_regime")
    s4_summary = (
        {
            "s4_w12_overblocking_hypothesis": s4.get(
                "w12_overblocking_hypothesis"
            ),
            "s4_regime_accuracy": s4.get("regime_accuracy"),
            "s4_expected_current_open_cell_count": s4.get(
                "expected_current_open_cell_count"
            ),
        }
        if isinstance(s4, dict) and s4
        else {}
    )
    s5 = payloads.get("s5_coupling_composition")
    s5_summary = (
        {
            "s5_coupling_accuracy": s5.get("coupling_accuracy"),
            "s5_penalized_score": s5.get("penalized_score"),
            "s5_expected_current_open_cell_count": s5.get(
                "expected_current_open_cell_count"
            ),
            "s5_false_modular_count": s5.get("false_modular_count"),
            "s5_false_entangled_count": s5.get("false_entangled_count"),
            "s5_coupling_regime_counts": s5.get("coupling_regime_counts"),
            "s5_boundary_regime_counts": s5.get("boundary_regime_counts"),
            "s5_system_effect_support_labels": s5.get(
                "system_effect_support_labels"
            ),
        }
        if isinstance(s5, dict) and s5
        else {}
    )
    s6 = payloads.get("s6_blind_spot_firewalls")
    s6_summary = (
        {
            "s6_maturity": s6.get("maturity"),
            "s6_case_count": s6.get("case_count"),
            "s6_axis_coverage_count": s6.get("axis_coverage_count"),
            "s6_bridge_consumer_coverage": s6.get("bridge_consumer_coverage"),
            "s6_c3_authority_dimension_coverage": s6.get(
                "c3_authority_dimension_coverage"
            ),
            "s6_fail_closed_coverage": s6.get(
                "per_axis_fail_closed_negative_control_pass_rate"
            ),
            "s6_false_clear_count": s6.get("false_clear_count"),
            "s6_expected_current_open_cell_count": s6.get(
                "expected_current_open_cell_count"
            ),
        }
        if isinstance(s6, dict) and s6
        else {}
    )

    return _result(
        issues,
        summary={
            "open_cell_count": len(current_open_cells),
            "open_cell_count_baseline": open_cell_count_baseline,
            "current_open_cell_count": len(current_open_cells),
            "assigned_open_cell_count": len(assigned_cells),
            "cells_closed_since_s0": closed_since_s0,
            "s0_cells_closed": s0_cells_closed,
            "readiness_artifact_count": len(payloads["readiness_manifest"].get("artifacts", [])),
            "inventory_artifact_count": _inventory_layer2_artifact_count(payloads["inventory"]),
            **s3_summary,
            **s4_summary,
            **s5_summary,
            **s6_summary,
        },
    )


def _open_cell_refs(payload: dict[str, Any]) -> set[str]:
    return {
        f"{cluster}.{axis}"
        for cluster, axes in payload.get("open_cell_closure", {}).items()
        for axis in axes
    }


def _inventory_layer2_artifact_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for artifact in payload.get("artifacts", [])
        if str(artifact.get("id", "")).startswith("layer2_")
    )


def _validate_minimal_seed(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not {"P15", "P25"} <= set(payload.get("launch_firewalls", [])):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_launch_firewall",
                "Minimal seed manifest must include P15 and P25 launch firewalls.",
            )
        )
    required_budgets = {
        "compute",
        "acquisition",
        "expert_time",
        "human_attention",
        "legal_access",
    }
    if not required_budgets <= set(payload.get("budgets", {})):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_budget",
                "Minimal seed manifest must declare all launch budgets.",
            )
        )


def _validate_floors(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    floors = payload.get("floor", [])
    floor_slices = {str(floor.get("slice", "")) for floor in floors}
    required_floor_slices = {f"S{number}" for number in range(2, 15)}
    if not required_floor_slices <= floor_slices:
        issues.append(
            _issue(
                "layer2_floor_governance_missing_slice_floor",
                "Floor governance must cover S2 through S14.",
            )
        )
    for floor in floors:
        for field in ("metric", "floor_owner", "floor_artifact", "revision_rule"):
            if not floor.get(field):
                issues.append(
                    _issue(
                        "layer2_floor_governance_field_missing",
                        f"Floor {floor.get('floor_id')} omits {field}.",
                    )
                )


def _validate_artifact_traceability(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    names = {str(row.get("name", "")) for row in payload.get("artifact", [])}
    missing = REQUIRED_ARTIFACT_NAMES - names
    if missing:
        issues.append(
            _issue(
                "layer2_artifact_traceability_missing_required_artifact",
                "Artifact traceability omits: " + ", ".join(sorted(missing)),
            )
        )


def _validate_corpus_partition(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    dev = payload.get("dev_regression_corpus", {})
    sealed = payload.get("sealed_universality_battery", {})
    if dev.get("path") == sealed.get("path") or sealed.get("extensible") is not False:
        issues.append(
            _issue(
                "layer2_corpus_partition_not_sealed",
                "Sealed universality battery must be distinct and non-extensible.",
            )
        )
    if not str(sealed.get("freeze_hash", "")).startswith("sha256:"):
        issues.append(
            _issue(
                "layer2_corpus_partition_freeze_hash_missing",
                "Sealed universality battery must carry a freeze hash.",
            )
        )


def _validate_first_proving_case(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    constructs = set(payload.get("constructs", []))
    missing = REQUIRED_UA_MSME_CONSTRUCTS - constructs
    if missing:
        issues.append(
            _issue(
                "layer2_first_proving_case_missing_construct",
                "First proving case omits constructs: " + ", ".join(sorted(missing)),
            )
        )


def _validate_readiness_manifest(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if payload.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_readiness_manifest_closes_cells",
                "S0 readiness manifest must not claim closed cells.",
            )
        )
    if int(payload.get("open_cell_count_baseline", -1)) != 17:
        issues.append(
            _issue(
                "layer2_readiness_manifest_open_cell_count_invalid",
                "S0 readiness manifest must preserve open_cell_count_baseline=17.",
            )
        )
    if len(payload.get("readiness_items", [])) != 11:
        issues.append(
            _issue(
                "layer2_readiness_manifest_item_count_invalid",
                "S0 readiness manifest must carry the 11 roadmap readiness items.",
            )
        )


def _validate_s3_substrate_acquisition(
    *,
    s3: object,
    floor_governance: dict[str, Any],
    first_proving_case: dict[str, Any],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s3, dict) or not s3:
        return
    if s3.get("acquisition_branch_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s3_acquisition_branch_not_implemented",
                "S3 must close the acquisition branch (bridge_missing -> implemented).",
            )
        )
    if s3.get("cells_closed"):
        issues.append(
            _issue(
                "layer2_s3_must_not_close_cluster_cell",
                "S3 advances layers only; it closes no cluster cell.",
            )
        )
    if s3.get("expected_current_open_cell_count") != 15:
        issues.append(
            _issue(
                "layer2_s3_open_cell_count_drift",
                "S3 must keep current open_cell_count at 15.",
            )
        )
    deny = set(s3.get("may_not_use_for", []))
    required_deny = {
        "production_claim_authority",
        "scenario_family_authority",
        "claim_authority_from_proxy_or_simulation",
    }
    if not required_deny <= deny:
        issues.append(
            _issue(
                "layer2_s3_authority_boundary_incomplete",
                (
                    "S3 may_not_use_for must block production/scenario-family/proxy "
                    "authority."
                ),
            )
        )
    if set(s3.get("pinned_constructs", [])) != set(
        first_proving_case.get("constructs", [])
    ):
        issues.append(
            _issue(
                "layer2_s3_pinned_constructs_drift",
                "S3 pinned constructs must match the first proving case constructs.",
            )
        )
    grounded = set(s3.get("constructs_grounded_in_s3", []))
    staged = set(s3.get("constructs_staged_followup", []))
    pinned = set(s3.get("pinned_constructs", []))
    if not grounded or not grounded.isdisjoint(staged) or grounded | staged != pinned:
        issues.append(
            _issue(
                "layer2_s3_construct_partition_invalid",
                "S3 grounded and staged constructs must be disjoint and cover pinned constructs.",
            )
        )
    if "s3_acquisition_closure" not in set(s3.get("floors", [])):
        issues.append(
            _issue(
                "layer2_s3_floor_missing",
                "S3 manifest must reference the s3_acquisition_closure floor.",
            )
        )
    floor = _floor_by_id(floor_governance, "s3_acquisition_closure")
    if floor.get("metric") != "acquisition_loop_closure_rate":
        issues.append(
            _issue(
                "layer2_s3_floor_metric_invalid",
                "S3 acquisition closure floor must use acquisition_loop_closure_rate.",
            )
        )
    if floor.get("floor_owner") != "team-integration-spine":
        issues.append(
            _issue(
                "layer2_s3_floor_owner_invalid",
                "S3 acquisition closure floor owner must be team-integration-spine.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s3_manifest_missing_from_inventory",
                "S3 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s4_epistemic_regime(
    *,
    s4: object,
    floor_governance: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s4, dict) or not s4:
        return
    expected_closed = {
        "KNOWLEDGE.epistemic_regime",
        "INTERVENTION.reversibility_lifecycle_stakes",
    }
    if set(s4.get("cells_closed", [])) != expected_closed:
        issues.append(
            _issue(
                "layer2_s4_cells_closed_invalid",
                "S4 must close exactly the epistemic_regime and reversibility cells.",
            )
        )
    if s4.get("expected_current_open_cell_count") != 13:
        issues.append(
            _issue(
                "layer2_s4_open_cell_count_drift",
                "S4 manifest must record expected_current_open_cell_count=13.",
            )
        )
    if expected_closed & current_open_cells:
        issues.append(
            _issue(
                "layer2_s4_cluster_map_not_closed",
                "S4 cells must be removed from open_cell_closure.",
            )
        )
    if not expected_closed <= assigned_cells:
        issues.append(
            _issue(
                "layer2_s4_cells_not_assigned",
                "S4 closed cells must be in the frozen slice-cell baseline.",
            )
        )
    deny = set(s4.get("may_not_use_for", []))
    required_deny = {
        "risk_regime_authority_without_risk_evidence",
        "b_side_regime_selection",
        "outcome_claim_from_ignorance",
        "low_stakes_floor_on_catastrophic_irreversible",
    }
    if not required_deny <= deny:
        issues.append(
            _issue(
                "layer2_s4_authority_boundary_incomplete",
                (
                    "S4 may_not_use_for must block false-risk, regime-shopping, "
                    "ignorance-outcome, and P23."
                ),
            )
        )
    if not _floor_by_id(floor_governance, "s4_regime_accuracy"):
        issues.append(
            _issue(
                "layer2_s4_regime_floor_missing",
                "s4_regime_accuracy floor must be registered.",
            )
        )
    if s4.get("w12_overblocking_hypothesis") not in {"confirmed", "revised"}:
        issues.append(
            _issue(
                "layer2_s4_w12_hypothesis_not_recorded",
                "S4 must record the W12 hypothesis as confirmed or revised.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s4_manifest_missing_from_inventory",
                "S4 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s5_coupling_composition(
    *,
    s5: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s5, dict) or not s5:
        return
    if set(s5.get("cells_closed", [])) != S5_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s5_cells_closed_invalid",
                "S5 must close exactly connectivity, dynamics feedback, and composition cells.",
            )
        )
    if s5.get("open_cell_count_baseline") != 17:
        issues.append(
            _issue(
                "layer2_s5_open_cell_count_baseline_invalid",
                "S5 must preserve open_cell_count_baseline=17.",
            )
        )
    if s5.get("expected_current_open_cell_count") != 10:
        issues.append(
            _issue(
                "layer2_s5_open_cell_count_drift",
                "S5 manifest must record expected_current_open_cell_count=10.",
            )
        )
    if S5_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s5_cluster_map_not_closed",
                "S5 cells must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) > int(s5.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s5_cluster_open_cell_count_mismatch",
                "S5 manifest expected open-cell count must not be exceeded by the cluster map.",
            )
        )
    if not assigned_cells >= S5_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s5_cells_not_assigned",
                "S5 closed cells must be in the frozen slice-cell baseline.",
            )
        )
    if "s5_coupling_accuracy" not in set(s5.get("floors", [])):
        issues.append(
            _issue(
                "layer2_s5_floor_missing",
                "S5 manifest must reference the s5_coupling_accuracy floor.",
            )
        )
    if not _floor_by_id(floor_governance, "s5_coupling_accuracy"):
        issues.append(
            _issue(
                "layer2_s5_floor_governance_missing",
                "s5_coupling_accuracy floor must be registered.",
            )
        )
    if not _number_at_least(s5.get("coupling_accuracy"), 0.9):
        issues.append(
            _issue(
                "layer2_s5_coupling_accuracy_below_floor",
                "S5 coupling accuracy must meet the seeded corpus floor.",
            )
        )
    if not _number_at_least(s5.get("penalized_score"), 0.9):
        issues.append(
            _issue(
                "layer2_s5_penalized_score_below_floor",
                "S5 penalized score must meet the false-modular penalty floor.",
            )
        )
    if s5.get("false_modular_count") != 0:
        issues.append(
            _issue(
                "layer2_s5_false_modular_present",
                "S5 false_modular_count must remain zero.",
            )
        )
    if not _non_negative_int(s5.get("false_entangled_count")):
        issues.append(
            _issue(
                "layer2_s5_false_entangled_count_invalid",
                "S5 false_entangled_count must be present and non-negative.",
            )
        )
    if s5.get("proving_ground_case_count") != 13:
        issues.append(
            _issue(
                "layer2_s5_case_count_invalid",
                "S5 proving ground must cover all 13 universal corpus cases.",
            )
        )
    for field, code in (
        ("coupling_regime_counts", "layer2_s5_coupling_regime_counts_incomplete"),
        ("boundary_regime_counts", "layer2_s5_boundary_regime_counts_incomplete"),
    ):
        counts = s5.get(field)
        if not isinstance(counts, dict) or not set(counts) >= S5_COUPLING_REGIMES:
            issues.append(
                _issue(
                    code,
                    f"S5 {field} must cover all four D2.6 coupling regimes.",
                )
            )
    labels = s5.get("system_effect_support_labels")
    if not isinstance(labels, list) or "simulation_only_system_effect" not in labels:
        issues.append(
            _issue(
                "layer2_s5_system_effect_support_labels_incomplete",
                "S5 support labels must expose simulation-only system-effect scope.",
            )
        )
    required_artifacts = set(s5.get("required_artifacts", []))
    trace_s5_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S5"
    }
    if required_artifacts != S5_REQUIRED_ARTIFACTS or required_artifacts != trace_s5_artifacts:
        issues.append(
            _issue(
                "layer2_s5_required_artifacts_missing",
                "S5 required_artifacts must match layer2_artifact_traceability S5 rows.",
            )
        )
    nested_records = set(s5.get("nested_records", []))
    if not nested_records >= S5_REQUIRED_NESTED_RECORDS:
        issues.append(
            _issue(
                "layer2_s5_nested_records_missing",
                "S5 nested_records must include boundary, discovery, forecast, and law checks.",
            )
        )
    negative_controls = set(s5.get("negative_controls", []))
    required_controls = {
        "tests/fixtures/layer2/s5/false_modular_probe.json",
        "tests/fixtures/layer2/s5/syntactic_decomposition_probe.json",
        "tests/fixtures/layer2/s5/boundary_spoof_probe.json",
    }
    if not negative_controls >= required_controls:
        issues.append(
            _issue(
                "layer2_s5_negative_control_missing",
                "S5 negative_controls must include false-modular, syntactic, and boundary-spoof probes.",
            )
        )
    if not set(s5.get("may_not_use_for", [])) >= S5_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s5_authority_deny_list_incomplete",
                "S5 may_not_use_for must block production, prediction, and P17 authority laundering.",
            )
        )
    if s5.get("authority_boundary") != (
        "shadow_governed_composition_gate_only_no_production_or_prediction_authority"
    ):
        issues.append(
            _issue(
                "layer2_s5_authority_boundary_incomplete",
                "S5 authority_boundary must stay shadow-governed and non-production.",
            )
        )
    if "P17" not in set(s5.get("relevant_patterns", [])):
        issues.append(
            _issue(
                "layer2_s5_relevant_patterns_missing_p17",
                "S5 manifest must cite P17 decomposition laundering.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s5_manifest_missing_from_inventory",
                "S5 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s6_blind_spot_firewalls(
    *,
    s6: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s6, dict) or not s6:
        issues.append(
            _issue(
                "layer2_s6_manifest_missing",
                "S6 blind-spot firewalls manifest must be present.",
            )
        )
        return
    if s6.get("schema_version") != (
        "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s6_schema_version_invalid",
                "S6 manifest schema_version is invalid.",
            )
        )
    if s6.get("status") != "active" or s6.get("maturity") != "fail_closed":
        issues.append(
            _issue(
                "layer2_s6_status_or_maturity_invalid",
                "S6 manifest must be active with maturity=fail_closed.",
            )
        )
    if set(s6.get("cells_closed", [])) != S6_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s6_cells_closed_invalid",
                "S6 must close exactly the five blind-spot cells.",
            )
        )
    if s6.get("expected_current_open_cell_count") != 5:
        issues.append(
            _issue(
                "layer2_s6_open_cell_count_drift",
                "S6 manifest must record expected_current_open_cell_count=5.",
            )
        )
    if S6_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s6_cluster_map_not_closed",
                "S6 cells must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) != int(s6.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s6_cluster_open_cell_count_mismatch",
                "S6 manifest expected open-cell count must match the cluster map.",
            )
        )
    if not assigned_cells >= S6_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s6_cells_not_assigned",
                "S6 closed cells must be in the frozen slice-cell baseline.",
            )
        )

    trace_s6_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S6"
    }
    if set(s6.get("required_artifacts", [])) != S6_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s6_required_artifacts_missing",
                "S6 required_artifacts must list the six blind-spot artifacts.",
            )
        )
    if not trace_s6_artifacts >= S6_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s6_traceability_missing",
                "S6 artifacts must be traceable in layer2_artifact_traceability.",
            )
        )
    if set(s6.get("required_firewalls", [])) != S6_REQUIRED_FIREWALLS:
        issues.append(
            _issue(
                "layer2_s6_firewalls_invalid",
                "S6 must require P18, P19, P21, P22, and P24 firewalls.",
            )
        )
    if set(s6.get("c3_authority_dimensions", [])) != S6_C3_AUTHORITY_DIMENSIONS:
        issues.append(
            _issue(
                "layer2_s6_c3_dimensions_invalid",
                "S6 C3 authority dimensions must include strategic_robustness and response_model_validity.",
            )
        )
    if set(s6.get("required_bridge_consumers", [])) != S6_REQUIRED_BRIDGE_CONSUMERS:
        issues.append(
            _issue(
                "layer2_s6_bridge_consumers_invalid",
                "S6 required_bridge_consumers must cover all five blind-spot cells.",
            )
        )
    cluster_bridge_consumers = _s6_bridge_consumers_from_cluster_map(cluster_map_payload)
    if not cluster_bridge_consumers >= S6_REQUIRED_BRIDGE_CONSUMERS:
        issues.append(
            _issue(
                "layer2_s6_cluster_bridge_consumers_missing",
                "Cluster map must expose every S6 required bridge consumer.",
            )
        )

    floor = _floor_by_id(floor_governance, "s6_fail_closed_coverage")
    if not floor or floor.get("revision_rule") != "all_five_blind_spot_axes_required":
        issues.append(
            _issue(
                "layer2_s6_floor_governance_invalid",
                "s6_fail_closed_coverage floor must require all five blind-spot axes.",
            )
        )
    if s6.get("floor_id") != "s6_fail_closed_coverage":
        issues.append(
            _issue(
                "layer2_s6_floor_missing",
                "S6 manifest must reference s6_fail_closed_coverage.",
            )
        )
    if s6.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s6_case_count_invalid",
                "S6 manifest must record all 13 universal corpus cases.",
            )
        )
    if s6.get("axis_coverage_count") != 5 or s6.get("all_five_axes_covered") is not True:
        issues.append(
            _issue(
                "layer2_s6_axis_coverage_invalid",
                "S6 manifest must record coverage for all five blind-spot axes.",
            )
        )
    if not _number_at_least(
        s6.get("per_axis_fail_closed_negative_control_pass_rate"),
        1.0,
    ):
        issues.append(
            _issue(
                "layer2_s6_fail_closed_coverage_below_floor",
                "S6 fail-closed coverage must be at least 1.0.",
            )
        )
    if s6.get("false_clear_count") != 0:
        issues.append(
            _issue(
                "layer2_s6_false_clear_count_nonzero",
                "S6 false_clear_count must stay zero.",
            )
        )
    bridge_coverage = s6.get("bridge_consumer_coverage")
    if not _coverage_has_all_true(bridge_coverage, S6_REQUIRED_BRIDGE_CONSUMERS):
        issues.append(
            _issue(
                "layer2_s6_bridge_consumer_coverage_incomplete",
                "S6 bridge_consumer_coverage must mark every required consumer true.",
            )
        )
    c3_coverage = s6.get("c3_authority_dimension_coverage")
    if not _coverage_has_all_true(c3_coverage, S6_C3_AUTHORITY_DIMENSIONS):
        issues.append(
            _issue(
                "layer2_s6_c3_authority_dimension_coverage_incomplete",
                "S6 c3_authority_dimension_coverage must mark every C3 dimension true.",
            )
        )
    if not set(s6.get("may_not_use_for", [])) >= S6_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s6_authority_deny_list_incomplete",
                "S6 may_not_use_for must block prediction, production, value, capacity, and mandate laundering.",
            )
        )

    inventory_artifact = _inventory_artifact_by_id(
        inventory,
        "layer2_s6_blind_spot_firewalls_manifest",
    )
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s6_manifest_missing_from_inventory",
                "S6 manifest must be registered in the Policy Design Case inventory.",
            )
        )
    else:
        if inventory_artifact.get("path") != DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH.as_posix():
            issues.append(
                _issue(
                    "layer2_s6_inventory_path_invalid",
                    "S6 inventory path must point at the governed manifest.",
                )
            )
        if inventory_artifact.get("maturity") != "fail_closed":
            issues.append(
                _issue(
                    "layer2_s6_inventory_maturity_invalid",
                    "S6 inventory entry must carry maturity=fail_closed.",
                )
            )


def _s6_bridge_consumers_from_cluster_map(payload: dict[str, Any]) -> set[str]:
    consumers: set[str] = set()
    for cell_ref in S6_CLOSED_CELLS:
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cell = payload.get("cell", {}).get(cluster, {}).get(axis, {})
        if isinstance(cell, dict):
            consumers.update(str(ref) for ref in cell.get("publishes", []) if ref)
    return consumers


def _coverage_has_all_true(value: object, required: set[str]) -> bool:
    return isinstance(value, dict) and all(value.get(key) is True for key in required)


def _inventory_artifact_by_id(payload: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    for artifact in payload.get("artifacts", []):
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    return {}


def _number_at_least(value: object, minimum: float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value >= minimum


def _non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _floor_by_id(payload: dict[str, Any], floor_id: str) -> dict[str, Any]:
    for floor in payload.get("floor", []):
        if isinstance(floor, dict) and floor.get("floor_id") == floor_id:
            return floor
    return {}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _result(issues: list[dict[str, str]], *, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Layer 2 readiness validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json-output", default="")
    args = parser.parse_args(argv)

    result = validate_layer2_readiness(args.repo_root)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
