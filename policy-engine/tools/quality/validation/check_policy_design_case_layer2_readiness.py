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
