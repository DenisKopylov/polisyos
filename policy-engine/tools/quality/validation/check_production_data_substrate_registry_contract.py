#!/usr/bin/env python3
"""Validate the production-data substrate registry contract artifact."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/production_data_substrate_registry_contract.json"
SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.production_data_substrate_registry_contract.v1"
)
TRUST_TIER_BOUND_CASE_TIER_IDS = (
    "administrative_noisy",
    "authoritative_high_coverage",
    "authoritative_partial_coverage",
    "derived_proxy",
    "weak_anchor",
)


def _substrate_registry_runtime_honesty_properties(repo_root: Path) -> dict[str, str]:
    """Return S0 honesty properties enforced by the runtime, keyed by property id."""

    module_path = repo_root / "src/polisyos/runtime/quality/substrate_registry.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    target_functions = {"validate_registration", "validate_trust_tier_bounds"}
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in target_functions
    }
    properties: dict[str, str] = {}

    def _direct_error_codes(function_name: str) -> set[str]:
        codes: set[str] = set()
        function = functions.get(function_name)
        if function is None:
            return codes
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "SubstrateRegistryError"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                codes.add(node.args[0].value)
        return codes

    trust_bound_codes = _direct_error_codes("validate_trust_tier_bounds")
    if "substrate_trust_tier_unresolved" in trust_bound_codes:
        properties["generic_trust_tier_unresolved"] = "substrate_trust_tier_unresolved"
    if "substrate_trust_cap_inflated" in trust_bound_codes:
        properties["generic_trust_cap"] = "substrate_trust_cap_inflated"
    if "substrate_trust_multiplier_inflated" in trust_bound_codes:
        properties["generic_trust_multiplier"] = "substrate_trust_multiplier_inflated"

    validate_registration = functions.get("validate_registration")
    if validate_registration is not None:
        for node in ast.walk(validate_registration):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "validate_trust_tier_bounds"
            ):
                continue
            if any(keyword.arg == "expected_tier" for keyword in node.keywords):
                if "substrate_trust_cap_inflated" in trust_bound_codes:
                    properties["known_family_expected_tier_cap"] = (
                        "substrate_trust_cap_inflated"
                    )
                if "substrate_trust_multiplier_inflated" in trust_bound_codes:
                    properties["known_family_expected_tier_multiplier"] = (
                        "substrate_trust_multiplier_inflated"
                    )

    direct_code_property_ids = {
        "substrate_coverage_inflated": "known_family_coverage",
        "substrate_identification_mode_inflated": "known_family_identification",
        "substrate_schema_regime_unresolved": "schema_regime",
    }
    for code in sorted(_direct_error_codes("validate_registration")):
        if code in trust_bound_codes:
            continue
        properties[direct_code_property_ids.get(code, f"runtime_code:{code}")] = code
    return properties


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def substrate_registry_trust_tier_bounds_behavior_report(repo_root: Path) -> dict[str, Any]:
    """Exercise the live S0 runtime against L5 registry-honesty rules."""

    from polisyos.runtime.quality.substrate_registry import (
        SubstrateCoverage,
        SubstrateLayer,
        SubstrateRegistration,
        SubstrateRegistryError,
        SubstrateSchemaRegime,
        SubstrateTrustTier,
        build_substrate_registry_from_existing_catalogs,
        default_substrate_catalog_paths,
        load_l5_catalog_authority,
        register_substrate_entry,
    )

    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(repo_root))
    registry = build_substrate_registry_from_existing_catalogs(repo_root)
    schema_regime = l5.latest_schema_regime()
    required_runtime_properties = _substrate_registry_runtime_honesty_properties(repo_root)
    issues: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    def _registration(
        *,
        case_id: str,
        tier: SubstrateTrustTier,
        source_id: str | None = None,
        family_id: str | None = None,
        layer: SubstrateLayer = SubstrateLayer.L4,
        coverage: SubstrateCoverage | None = None,
        identification_mode: str = "bounds_only",
        registration_schema_regime: SubstrateSchemaRegime | None = None,
        authority_refs: tuple[str, ...] | None = None,
    ) -> SubstrateRegistration:
        return SubstrateRegistration(
            source_id=source_id or f"contract-behavior:{case_id}",
            family_id=family_id or f"contract_behavior_{case_id.replace(':', '_')}",
            layer=layer,
            coverage=coverage
            or SubstrateCoverage(
                coverage_score=0.21,
                coverage_kind="contract_behavior.coverage",
                coverage_rule_ref=f"contract://production-data-substrate/{case_id}#coverage",
                dataset_count=1,
                metric_binding_count=1,
            ),
            trust_tier=tier,
            identification_mode=identification_mode,
            schema_regime=registration_schema_regime or schema_regime,
            data_version=f"{case_id}:v1",
            snapshot_id=f"{case_id}:snapshot:v1",
            source_snapshot_id=f"{case_id}:source_snapshot:v1",
            provenance_refs=(f"contract://production-data-substrate/{case_id}",),
            authority_refs=authority_refs or (l5.measurement_registry_ref,),
        )

    def _attempt(
        *,
        case_id: str,
        tier_id: str,
        tier: SubstrateTrustTier,
        expected_status: str,
        expected_code: str | None = None,
        subproperty: str,
        runtime_property: str | None = None,
        registration: SubstrateRegistration | None = None,
    ) -> None:
        actual_status = "accepted"
        actual_code: str | None = None
        try:
            register_substrate_entry(
                registry,
                registration or _registration(case_id=case_id, tier=tier),
                l5_authority=l5,
            )
        except SubstrateRegistryError as exc:
            actual_status = "rejected"
            actual_code = exc.code
        except Exception as exc:
            actual_status = "error"
            actual_code = type(exc).__name__
        case = {
            "case_id": case_id,
            "tier": tier_id,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "expected_code": expected_code,
            "actual_code": actual_code,
            "subproperty": subproperty,
            "runtime_property": runtime_property,
        }
        cases.append(case)
        if actual_status != expected_status or actual_code != expected_code:
            issues.append(
                {
                    "code": "substrate_registry_honesty_behavior_failed",
                    **case,
                }
            )

    known_family_id = "household_distribution"
    known_tier = l5.expected_trust_tier(known_family_id)
    known_coverage_score = float(l5.coverage_rules[known_family_id])
    known_identification_mode = l5.identification_modes[known_family_id]
    known_refs = (
        l5.measurement_registry_ref,
        l5.identification_mode_registry_ref,
        l5.schema_regime_registry_ref,
    )

    def _known_family_registration(
        *,
        case_id: str,
        coverage_score: float = known_coverage_score,
        identification_mode: str = known_identification_mode,
        tier: SubstrateTrustTier = known_tier,
    ) -> SubstrateRegistration:
        return _registration(
            case_id=case_id,
            tier=tier,
            source_id=f"contract-behavior:known-family:{case_id}",
            family_id=known_family_id,
            layer=SubstrateLayer.L5,
            coverage=SubstrateCoverage(
                coverage_score=coverage_score,
                coverage_kind="l5_measurement_registry.coverage_rule",
                coverage_rule_ref=f"{l5.measurement_registry_ref}#/coverage_rules/{known_family_id}",
                dataset_count=1,
                metric_binding_count=1,
            ),
            identification_mode=identification_mode,
            authority_refs=known_refs,
        )

    _attempt(
        case_id=f"{known_family_id}:honest",
        tier_id=known_tier.tier,
        tier=known_tier,
        expected_status="accepted",
        subproperty="known_family_honest",
        registration=_known_family_registration(case_id=f"{known_family_id}:honest"),
    )
    _attempt(
        case_id=f"{known_family_id}:coverage_above_l5",
        tier_id=known_tier.tier,
        tier=known_tier,
        expected_status="rejected",
        expected_code="substrate_coverage_inflated",
        subproperty="known_family_coverage",
        runtime_property="known_family_coverage",
        registration=_known_family_registration(
            case_id=f"{known_family_id}:coverage_above_l5",
            coverage_score=min(1.0, known_coverage_score + 0.01),
        ),
    )
    _attempt(
        case_id=f"{known_family_id}:identification_above_l5",
        tier_id=known_tier.tier,
        tier=known_tier,
        expected_status="rejected",
        expected_code="substrate_identification_mode_inflated",
        subproperty="known_family_identification",
        runtime_property="known_family_identification",
        registration=_known_family_registration(
            case_id=f"{known_family_id}:identification_above_l5",
            identification_mode="point_identified",
        ),
    )
    expected_tier_probe_tier = l5.trust_tiers["authoritative_high_coverage"]
    _attempt(
        case_id=f"{known_family_id}:expected_tier_cap_above_l5",
        tier_id=expected_tier_probe_tier.tier,
        tier=expected_tier_probe_tier,
        expected_status="rejected",
        expected_code="substrate_trust_cap_inflated",
        subproperty="known_family_expected_tier_cap",
        runtime_property="known_family_expected_tier_cap",
        registration=_known_family_registration(
            case_id=f"{known_family_id}:expected_tier_cap_above_l5",
            tier=expected_tier_probe_tier,
        ),
    )
    _attempt(
        case_id=f"{known_family_id}:expected_tier_multiplier_above_l5",
        tier_id=expected_tier_probe_tier.tier,
        tier=expected_tier_probe_tier,
        expected_status="rejected",
        expected_code="substrate_trust_multiplier_inflated",
        subproperty="known_family_expected_tier_multiplier",
        runtime_property="known_family_expected_tier_multiplier",
        registration=_known_family_registration(
            case_id=f"{known_family_id}:expected_tier_multiplier_above_l5",
            tier=expected_tier_probe_tier.model_copy(
                update={"trust_cap": known_tier.trust_cap}
            ),
        ),
    )
    for tier_id in TRUST_TIER_BOUND_CASE_TIER_IDS:
        tier = l5.trust_tiers.get(tier_id)
        if tier is None:
            issues.append(
                {"code": "substrate_trust_tier_bounds_probe_missing_l5_tier", "tier": tier_id}
            )
            continue
        _attempt(
            case_id=f"{tier_id}:trust_cap_above_l5",
            tier_id=tier_id,
            tier=tier.model_copy(update={"trust_cap": tier.trust_cap + 0.001}),
            expected_status="rejected",
            expected_code="substrate_trust_cap_inflated",
            subproperty="trust_cap",
            runtime_property="generic_trust_cap",
        )
        _attempt(
            case_id=f"{tier_id}:trust_multiplier_above_l5",
            tier_id=tier_id,
            tier=tier.model_copy(update={"trust_multiplier": tier.trust_multiplier + 0.001}),
            expected_status="rejected",
            expected_code="substrate_trust_multiplier_inflated",
            subproperty="trust_multiplier",
            runtime_property="generic_trust_multiplier",
        )
        _attempt(
            case_id=f"{tier_id}:boundary",
            tier_id=tier_id,
            tier=tier,
            expected_status="accepted",
            subproperty="trust_tier_boundary",
        )
        _attempt(
            case_id=f"{tier_id}:honest_lower",
            tier_id=tier_id,
            tier=tier.model_copy(
                update={
                    "trust_cap": max(0.0, tier.trust_cap - 0.01),
                    "trust_multiplier": max(0.0, tier.trust_multiplier - 0.01),
                }
            ),
            expected_status="accepted",
            subproperty="trust_tier_honest_lower",
        )
    _attempt(
        case_id="unknown_tier_name",
        tier_id="contract_unregistered_tier",
        tier=SubstrateTrustTier(
            tier="contract_unregistered_tier",
            trust_cap=0.1,
            trust_multiplier=0.1,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref="contract://production-data-substrate/unregistered-tier",
        ),
        expected_status="rejected",
        expected_code="substrate_trust_tier_unresolved",
        subproperty="unknown_tier",
        runtime_property="generic_trust_tier_unresolved",
    )
    _attempt(
        case_id="schema_regime_unregistered",
        tier_id="weak_anchor",
        tier=l5.trust_tiers["weak_anchor"],
        expected_status="rejected",
        expected_code="substrate_schema_regime_unresolved",
        subproperty="schema_regime",
        runtime_property="schema_regime",
        registration=_registration(
            case_id="schema_regime_unregistered",
            tier=l5.trust_tiers["weak_anchor"],
            registration_schema_regime=schema_regime.model_copy(
                update={
                    "schema_regime_id": "contract_unregistered_schema_regime",
                    "authority_ref": (
                        "contract://production-data-substrate/unregistered-schema-regime"
                    ),
                }
            ),
        ),
    )
    exercised_runtime_properties = {
        str(case["runtime_property"])
        for case in cases
        if case.get("expected_status") == "rejected" and case.get("runtime_property")
    }
    required_property_ids = set(required_runtime_properties)
    if exercised_runtime_properties != required_property_ids:
        issues.append(
            {
                "code": "substrate_registry_honesty_behavior_incomplete",
                "missing_runtime_properties": sorted(
                    required_property_ids - exercised_runtime_properties
                ),
                "extra_behavior_properties": sorted(
                    exercised_runtime_properties - required_property_ids
                ),
                "required_runtime_properties": required_runtime_properties,
            }
        )
    return {
        "status": "pass" if not issues else "fail",
        "tier_count": len(TRUST_TIER_BOUND_CASE_TIER_IDS),
        "case_count": len(cases),
        "cases": cases,
        "issues": issues,
        "runtime_honesty_properties": required_runtime_properties,
        "subproperties": sorted({case["subproperty"] for case in cases}),
    }


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the S0 registry contract from the live model."""

    from polisyos.runtime.quality.substrate_registry import (
        SUBSTRATE_REGISTRY_ARTIFACT_KIND,
        SUBSTRATE_REGISTRY_SCHEMA_VERSION,
        SubstrateRegistry,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    registry_honesty = substrate_registry_trust_tier_bounds_behavior_report(repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.production_data_substrate_registry",
        "substrate_registry_schema_version": SUBSTRATE_REGISTRY_SCHEMA_VERSION,
        "artifact_kind": SUBSTRATE_REGISTRY_ARTIFACT_KIND,
        "owner": "polisyos.runtime.quality.substrate_registry.SubstrateRegistry",
        "source_module": "src/polisyos/runtime/quality/substrate_registry.py",
        "lifted_authority_catalogs": [
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/identification_mode_registry.json",
            "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/schema_regime_registry.json",
            "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb#ds_datasets",
            "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb#ds_metric_bindings",
        ],
        "producer": "build_substrate_registry_from_existing_catalogs",
        "free_grow_interface": "register_substrate_entry",
        "consumers": [
            "polisyos.runtime.quality.world_model_record.build_world_model_record",
        ],
        "content_binding_checks": [
            "entry_content_hash_mismatch",
            "substrate_registry_content_hash_mismatch",
            "substrate_registry_duplicate_entry",
            "substrate_coverage_inflated",
            "substrate_trust_cap_inflated",
            "substrate_trust_multiplier_inflated",
            "substrate_identification_mode_inflated",
            "substrate_entry_unresolved",
        ],
        "behavioral_checks": {
            "registry_honesty": {
                "status": registry_honesty["status"],
                "tier_count": registry_honesty["tier_count"],
                "case_count": registry_honesty["case_count"],
                "subproperties": registry_honesty["subproperties"],
                "runtime_honesty_properties": registry_honesty["runtime_honesty_properties"],
                "case_ids": [case["case_id"] for case in registry_honesty["cases"]],
            }
        },
        "no_parallel_authority_rule": (
            "Coverage, trust tier, identification mode, and schema regime are lifted "
            "from L5 D2 registries and L1 DCAT metadata; registrations exceeding L5 "
            "caps fail closed."
        ),
        "plan_named_owner_files_forbidden": "gy_s0_*",
        "json_schema": SubstrateRegistry.model_json_schema(),
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed contract artifact against live code."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    behavior = substrate_registry_trust_tier_bounds_behavior_report(repo_root)
    issues.extend(behavior["issues"])
    live = build_live_payload(repo_root)
    if not path.is_file():
        issues.append({"code": "production_data_substrate_registry_contract_missing"})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "production_data_substrate_registry_contract_invalid_json",
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "production_data_substrate_registry_contract_drift"})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live production-data substrate registry contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(repo_root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the S0 substrate registry contract validator."""

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
    raise SystemExit(main())
