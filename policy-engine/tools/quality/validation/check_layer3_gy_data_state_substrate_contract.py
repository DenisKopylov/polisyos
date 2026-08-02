#!/usr/bin/env python3
"""Validate the Layer 3 GY data-state substrate lift contract artifact."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.data_state_substrate_contract.v1"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def data_state_substrate_honesty_behavior_report(repo_root: Path) -> dict[str, Any]:
    """Exercise the live S1 bridge against L1 availability and L5 honesty rules."""

    from polisyos.runtime.quality.data_state_substrate import (
        DataStateSubstrateError,
        build_l5_family_binding_profile,
        l1_dcat_variable_availability,
        materialize_l4_data_state_snapshot,
    )
    from polisyos.runtime.quality.substrate_registry import (
        default_substrate_catalog_paths,
        load_l5_catalog_authority,
    )

    issues: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    def _record_case(
        *,
        case_id: str,
        expected_status: str,
        actual_status: str,
        detail: dict[str, Any],
    ) -> None:
        case = {
            "case_id": case_id,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "detail": detail,
        }
        cases.append(case)
        if actual_status != expected_status:
            issues.append({"code": "data_state_substrate_behavior_failed", **case})

    available = l1_dcat_variable_availability(repo_root, "avg_income")
    _record_case(
        case_id="l1_avg_income_available",
        expected_status="available",
        actual_status=available.status,
        detail=available.model_dump(mode="json"),
    )

    unavailable = l1_dcat_variable_availability(
        repo_root,
        "not_a_real_policyos_metric_for_s1",
    )
    _record_case(
        case_id="l1_missing_metric_unavailable",
        expected_status="unavailable",
        actual_status=unavailable.status,
        detail=unavailable.model_dump(mode="json"),
    )

    profile = build_l5_family_binding_profile(
        repo_root,
        families=("budget_flows", "household_distribution"),
        period_start="2021-12",
        period_end="2022-03",
    )
    budget = profile.family_authority("budget_flows")
    household = profile.family_authority("household_distribution")
    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(repo_root))
    expected_household_tier = l5.expected_trust_tier("household_distribution")
    budget_status = (
        "honest"
        if (
            budget.identification_mode == "point_identified"
            and budget.value_authority == "point"
            and budget.trust_tier == "authoritative_high_coverage"
            and budget.trust_cap == 1.0
        )
        else "inflated_or_downgraded"
    )
    _record_case(
        case_id="l5_point_identified_budget_full_trust",
        expected_status="honest",
        actual_status=budget_status,
        detail=budget.model_dump(mode="json"),
    )

    household_status = (
        "honest"
        if (
            household.identification_mode == "proxy_identified"
            and household.value_authority == "proxy_bounds"
            and household.trust_tier == expected_household_tier.tier
            and household.trust_cap == expected_household_tier.trust_cap
        )
        else "inflated_or_downgraded"
    )
    _record_case(
        case_id="l5_proxy_identified_household_bounds",
        expected_status="honest",
        actual_status=household_status,
        detail=household.model_dump(mode="json"),
    )

    behavioral_status, behavioral_detail = _household_proxy_behavioral_detail(
        repo_root,
        materialize_l4_data_state_snapshot=materialize_l4_data_state_snapshot,
    )
    _record_case(
        case_id="l5_proxy_behavioral_bounds_toggle_changes_state",
        expected_status="bounded_and_state_changes",
        actual_status=behavioral_status,
        detail=behavioral_detail,
    )

    regime_status = (
        "flagged"
        if (
            profile.schema_regime_status == "spans_changepoint_flagged"
            and profile.changepoint_period == "2022-02"
            and profile.boundary_buffer_periods >= 1
            and profile.regime_ids == ("ukraine_schema_v1", "ukraine_schema_v2")
        )
        else "silently_mixed"
    )
    _record_case(
        case_id="l5_prewar_wartime_span_flagged",
        expected_status="flagged",
        actual_status=regime_status,
        detail={
            "schema_regime_status": profile.schema_regime_status,
            "regime_ids": list(profile.regime_ids),
            "changepoint_period": profile.changepoint_period,
            "boundary_buffer_periods": profile.boundary_buffer_periods,
        },
    )

    try:
        build_l5_family_binding_profile(
            repo_root,
            families=("family_not_registered_for_s1_contract",),
            period_start="2021-12",
            period_end="2022-03",
        )
    except DataStateSubstrateError as exc:
        actual_status = exc.code
    else:
        actual_status = "accepted"
    _record_case(
        case_id="l5_unidentified_family_fails_closed",
        expected_status="l5_family_unidentified",
        actual_status=actual_status,
        detail={"family_id": "family_not_registered_for_s1_contract"},
    )

    return {
        "status": "pass" if not issues else "fail",
        "case_count": len(cases),
        "cases": cases,
        "issues": issues,
    }


def _household_proxy_behavioral_detail(
    repo_root: Path,
    *,
    materialize_l4_data_state_snapshot: Any,
) -> tuple[str, dict[str, Any]]:
    import numpy as np

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts import ValueOuterSet
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.foundry.execute.executor import load_state_snapshot

    def _bound_household_state(root: Path, workspace: Path, store: FileSystemCAS) -> Any:
        materialized = materialize_l4_data_state_snapshot(
            store,
            repo_root=root,
            workspace_dir=workspace,
            agent_limit=8,
            required_l1_variables=("avg_income",),
        )
        registry_bundle = build_default_registry_bundle(store)
        bindings = build_input_bindings(
            store,
            data_snapshot_ref=materialized.data_snapshot_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
            rules=None,
        )
        state = load_state_snapshot(store, snapshot_ref=bindings.bound_state_snapshot_ref)
        if state.household_cells is None:
            raise RuntimeError("household_cells_missing")
        return state.household_cells

    with tempfile.TemporaryDirectory(prefix="gy-s1-l5-toggle-") as tmp:
        tmp_path = Path(tmp)
        store = FileSystemCAS(tmp_path / "cas")
        proxy_households = _bound_household_state(
            repo_root,
            tmp_path / "proxy-workspace",
            store,
        )
        point_repo = _repo_with_household_identification_mode(
            repo_root,
            tmp_path,
            selected_mode="point_identified",
        )
        point_households = _bound_household_state(
            point_repo,
            tmp_path / "point-workspace",
            store,
        )

        proxy_set = proxy_households.value_outer_set
        point_set = point_households.value_outer_set
        if proxy_set is None or point_set is None:
            return "presence_not_gate", {"agent_limit": 8, "value_outer_set_missing": True}

        proxy_width = np.asarray(proxy_set.width, dtype=float)
        point_width = np.asarray(point_set.width, dtype=float)
        proxy_wide = bool(np.any(proxy_width > 0.0))
        point_tight = bool(np.allclose(point_width, 0.0))
        proxy_mode_ok = proxy_set.identification_status == "proxy"
        point_mode_ok = point_set.identification_status == "point"
        household_state_same = proxy_set == point_set
        degenerate_rejected = _degenerate_proxy_payload_rejected(proxy_set)
        non_certified_decision = ValueOuterSet.model_validate(
            {
                **proxy_set.model_dump(mode="json", exclude={"width"}),
                "representation_status": "search_only",
            }
        ).promotion_decision()
        zero_trust_decision = ValueOuterSet.model_validate(
            {
                **proxy_set.model_dump(mode="json", exclude={"width"}),
                "data_trust": {
                    "tier": "synthetic_zero_trust",
                    "trust_cap": 0.0,
                    "trust_multiplier": 1.0,
                    "min_coverage": 0.0,
                    "max_coverage": 1.0,
                    "promotion_floor": 0.5,
                    "authority_ref": "contract://l5/trust_tiers/synthetic_zero_trust",
                },
            }
        ).promotion_decision()
        weak_trust_decision = ValueOuterSet.model_validate(
            {
                **proxy_set.model_dump(mode="json", exclude={"width"}),
                "data_trust": {
                    "tier": "synthetic_weak_trust",
                    "trust_cap": 0.25,
                    "trust_multiplier": 0.6,
                    "min_coverage": 0.0,
                    "max_coverage": 1.0,
                    "promotion_floor": 0.5,
                    "authority_ref": "contract://l5/trust_tiers/synthetic_weak_trust",
                },
            }
        ).promotion_decision()
        strong_trust_decision = ValueOuterSet.model_validate(
            {
                **point_set.model_dump(mode="json", exclude={"width"}),
                "data_trust": {
                    "tier": "synthetic_authoritative_high",
                    "trust_cap": 1.0,
                    "trust_multiplier": 1.0,
                    "min_coverage": 0.9,
                    "max_coverage": 1.0,
                    "promotion_floor": 0.5,
                    "authority_ref": (
                        "contract://l5/trust_tiers/synthetic_authoritative_high"
                    ),
                },
            }
        ).promotion_decision()
        non_certified_blocked = (
            not non_certified_decision.promotable
            and "representation_not_certified" in non_certified_decision.reasons
        )
        zero_trust_blocked = (
            not zero_trust_decision.promotable
            and "data_trust_zero" in zero_trust_decision.reasons
        )
        weak_trust_blocked = (
            not weak_trust_decision.promotable
            and "data_trust_below_promotion_floor" in weak_trust_decision.reasons
        )
        compare_timeout_unknown = proxy_set.compare(point_set, force_timeout=True) == "unknown"
        proxy_decision = proxy_set.promotion_decision()
        point_decision = point_set.promotion_decision()
        promotion_grade_rank = {"blocked": 0, "low": 1, "medium": 2, "high": 3}
        proxy_promotable = proxy_decision.promotable
        point_promotable = point_decision.promotable
        strong_trust_grade_above_proxy = (
            promotion_grade_rank[strong_trust_decision.capped_decision_grade]
            > promotion_grade_rank[proxy_decision.capped_decision_grade]
        )
        status = (
            "bounded_and_state_changes"
            if proxy_wide
            and point_tight
            and proxy_mode_ok
            and point_mode_ok
            and not household_state_same
            and degenerate_rejected
            and non_certified_blocked
            and zero_trust_blocked
            and weak_trust_blocked
            and compare_timeout_unknown
            and proxy_promotable
            and point_promotable
            and strong_trust_decision.promotable
            and strong_trust_grade_above_proxy
            else "presence_not_gate"
        )
        return status, {
            "agent_limit": 8,
            "proxy_wide": proxy_wide,
            "point_tight": point_tight,
            "proxy_mode_ok": proxy_mode_ok,
            "point_mode_ok": point_mode_ok,
            "household_state_same": household_state_same,
            "degenerate_proxy_payload_rejected": degenerate_rejected,
            "non_certified_blocked": non_certified_blocked,
            "zero_trust_blocked": zero_trust_blocked,
            "weak_trust_blocked": weak_trust_blocked,
            "compare_timeout_unknown": compare_timeout_unknown,
            "proxy_promotable": proxy_promotable,
            "point_promotable": point_promotable,
            "proxy_promotion_grade": proxy_decision.capped_decision_grade,
            "point_promotion_grade": point_decision.capped_decision_grade,
            "strong_trust_promotion_grade": strong_trust_decision.capped_decision_grade,
            "strong_trust_grade_above_proxy": strong_trust_grade_above_proxy,
            "zero_trust_reasons": list(zero_trust_decision.reasons),
            "weak_trust_reasons": list(weak_trust_decision.reasons),
            "proxy_width_sum": round(float(np.sum(proxy_width)), 6),
            "point_width_sum": round(float(np.sum(point_width)), 6),
        }


def _degenerate_proxy_payload_rejected(proxy_set: Any) -> bool:
    from polisyos.core.contracts import ValueOuterSet

    midpoint = tuple(
        (float(lower) + float(upper)) / 2.0
        for lower, upper in zip(proxy_set.lower, proxy_set.upper, strict=True)
    )
    try:
        ValueOuterSet.model_validate(
            {
                **proxy_set.model_dump(mode="json", exclude={"width"}),
                "lower": midpoint,
                "upper": midpoint,
            }
        )
    except ValueError:
        return True
    return False


def _repo_with_household_identification_mode(
    repo_root: Path,
    tmp_path: Path,
    *,
    selected_mode: str,
) -> Path:
    canonical = (
        Path("production_data/canonical/local_data_20260501/")
        / "ukraine_server_support_20260410"
    )
    l5_d2 = canonical / "runtime_calibration_internals/calibration/d2"
    l5_d3 = canonical / "runtime_calibration_internals/calibration/d3"
    normalized = canonical / "normalized_corpus"
    l1_dcat = Path("production_data/datasets_full_phase3full_20260327_183054")
    temp_root = tmp_path / f"repo-l5-{selected_mode}"
    production_root = temp_root / "production_data"
    production_root.mkdir(parents=True, exist_ok=True)

    manifest_src = repo_root / "production_data/manifest.json"
    if manifest_src.exists():
        os.symlink(manifest_src, production_root / "manifest.json")
    _symlink_dir(repo_root / l1_dcat, temp_root / l1_dcat)
    _symlink_dir(repo_root / normalized, temp_root / normalized)
    _symlink_dir(repo_root / l5_d3, temp_root / l5_d3)

    d2_dst = temp_root / l5_d2
    shutil.copytree(repo_root / l5_d2, d2_dst)
    identification_path = d2_dst / "identification_mode_registry.json"
    identification = json.loads(identification_path.read_text(encoding="utf-8"))
    household = dict(identification["household_distribution"])
    household["selected_mode"] = selected_mode
    household["primary_mode"] = selected_mode
    household["fallback_triggered"] = False
    household["reason"] = "s1_contract_behavioral_toggle_probe"
    identification["household_distribution"] = household
    identification_path.write_text(
        json.dumps(identification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return temp_root


def _symlink_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(src, dst, target_is_directory=True)


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the data-state substrate lift contract from the live module."""

    from polisyos.core.contracts import DataTrust, ValueOuterSet, ValuePromotionDecision
    from polisyos.runtime.quality.data_state_substrate import (
        DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
        L1VariableAvailability,
        L5FamilyAuthority,
        L5FamilyBindingProfile,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    behavior = data_state_substrate_honesty_behavior_report(repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.data_state_substrate_lift",
        "data_state_substrate_schema_version": DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
        "artifact_kind": "fabric.production_data_state_payload",
        "owner": "polisyos.runtime.quality.data_state_substrate",
        "source_module": "src/polisyos/runtime/quality/data_state_substrate.py",
        "materializer": "materialize_l4_data_state_snapshot",
        "producer": "build_production_data_state_world_model_record",
        "reuse_existing_owners": [
            "data_forge.kernel.snapshot.finalize_snapshot",
            "foundry.data_plane.bindings.build_input_bindings",
            "runtime.quality.substrate_registry.build_substrate_registry_from_existing_catalogs",
            "runtime.quality.substrate_registry.persist_substrate_registry",
            "runtime.quality.world_model_record.build_world_model_record",
            "runtime.quality.world_model_record.consume_world_model_record_for_simulation",
        ],
        "lifted_authority_catalogs": [
            "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb#ds_datasets",
            "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb#ds_observations",
            "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb#ds_metric_bindings",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/identification_mode_registry.json",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/schema_regime_registry.json",
        ],
        "lifted_l4_corpus": [
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/normalized_corpus/agent_registry_full.parquet",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/normalized_corpus/firm_fundamentals_annual.parquet",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/normalized_corpus/budget_flows_monthly_sparse.parquet",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d3/corrected_firm_panels.parquet",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d3/calibrated_household_cells.parquet",
        ],
        "consumers": [
            "polisyos.foundry.data_plane.bindings.build_input_bindings",
            "polisyos.runtime.quality.world_model_record.build_world_model_record",
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation",
        ],
        "content_binding_checks": [
            "l1_variable_unavailable",
            "l5_family_unidentified",
            "production_data_state_empty",
            "production_data_path_missing",
            "schema_regime_period_order_invalid",
            "schema_regime_period_invalid",
            "l5_schema_regime_missing",
            "skg_prior_ref_unresolved",
            "fabric_world_empty",
            "fabric_world_not_queryable",
            "substrate_entry_unresolved",
        ],
        "honesty_rules": [
            "L1 DCAT is the coverage/availability authority for required variables.",
            "L5 trust tiers cap value trust and are not upgraded by S1.",
            "ValueOuterSet promotion value requires certified representation and L5 DataTrust above the promotion floor.",
            "Proxy-identified L5 families materialize bounded state, never point effects.",
            "Schema-regime spans across the 2022-02 changepoint are flagged.",
            "SyntheticWorld is benchmark-only and not accepted as the production world.",
        ],
        "patterns_closed": ["P01", "P10", "P14", "P27", "P29", "P30"],
        "behavioral_checks": {
            "l1_l5_honesty": {
                "status": behavior["status"],
                "case_count": behavior["case_count"],
                "case_ids": [case["case_id"] for case in behavior["cases"]],
            }
        },
        "json_schemas": {
            "l1_variable_availability": L1VariableAvailability.model_json_schema(),
            "l5_family_authority": L5FamilyAuthority.model_json_schema(),
            "l5_family_binding_profile": L5FamilyBindingProfile.model_json_schema(),
            "data_trust": DataTrust.model_json_schema(),
            "value_outer_set": ValueOuterSet.model_json_schema(),
            "value_promotion_decision": ValuePromotionDecision.model_json_schema(),
        },
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed contract artifact against live code and behavior."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    behavior = data_state_substrate_honesty_behavior_report(repo_root)
    issues.extend(behavior["issues"])
    live = build_live_payload(repo_root)
    if not path.is_file():
        issues.append({"code": "data_state_substrate_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "data_state_substrate_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "data_state_substrate_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live data-state substrate lift contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(repo_root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the data-state substrate lift contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    if args.write:
        write(repo_root)
    report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
