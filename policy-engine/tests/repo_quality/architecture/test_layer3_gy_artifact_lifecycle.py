from __future__ import annotations

import contextlib
import json
import re
import tomllib
from copy import deepcopy
from pathlib import Path

import pytest

from tools.quality.validation import (
    check_layer3_artifact_surface_safety,
    check_layer3_gy_composition_artifacts,
    check_layer3_gy_data_state_substrate_contract,
    check_layer3_gy_design_problem_contract,
    check_layer3_gy_generated_public_lifecycle_audit,
    check_layer3_gy_intervention_atom_binding_contract,
    check_layer3_gy_knowledge_substrate_contract,
    check_layer3_gy_loop_artifacts,
    check_layer3_gy_phase2_artifacts,
    check_layer3_gy_value_outer_set_strangle_receipt,
    check_layer3_gy_world_model_record_contract,
    check_layer3_time_source_authority,
    check_layer3_workflow_failure_authority,
    check_production_data_substrate_registry_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_declaring_workflow(
    repo_root: Path,
    *,
    workflow_path: str,
    outputs: list[str],
    include_declared_outputs: bool = True,
) -> None:
    path = repo_root / workflow_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if include_declared_outputs:
        body = (
            "from __future__ import annotations\n\n"
            f"OUTPUTS = {outputs!r}\n\n"
            "def declared_outputs() -> list[str]:\n"
            "    return list(OUTPUTS)\n"
        )
    else:
        body = "from __future__ import annotations\n\n" f"OUTPUTS = {outputs!r}\n"
    path.write_text(body, encoding="utf-8")


def _assert_live_payloads_match_declared_outputs(
    producer: object,
    live_payloads: dict[str, dict[str, object]],
) -> None:
    assert set(live_payloads) == set(producer.declared_outputs())
    for payload in live_payloads.values():
        assert check_layer3_gy_generated_public_lifecycle_audit._contains_gy_provenance(
            payload
        )


def test_layer3_gy_generated_artifact_lifecycle_is_scan_based() -> None:
    report = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        REPO_ROOT
    )

    assert report["status"] == "pass"
    discovered = set(report["discovered_artifacts"])
    assert set(report["discovered_artifacts"]) == set(report["producer_declared_outputs"]) | set(
        report["source_committed_outputs"]
    )
    assert not set(report["producer_declared_outputs"]) & set(report["source_committed_outputs"])
    assert (
        "architecture/policy_design_case/layer3_gy_task0_audit/"
        "layer3_gy_generated_public_lifecycle_audit.json"
    ) in discovered
    assert "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json" in discovered
    assert report["orphan_count"] == 0
    assert report["phantom_output_count"] == 0
    assert report["duplicate_claim_count"] == 0
    assert report["registered_artifact_count"] == len(discovered)


def test_layer3_gy_design_problem_contract_recomputes_schema() -> None:
    report = check_layer3_gy_design_problem_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_design_problem_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_design_problem_contract.build_live_payload()


def test_layer3_gy_intervention_atom_binding_contract_recomputes_schema() -> None:
    report = check_layer3_gy_intervention_atom_binding_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_intervention_atom_binding_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_intervention_atom_binding_contract.build_live_payload()


def test_layer3_gy_world_model_record_contract_recomputes_schema() -> None:
    report = check_layer3_gy_world_model_record_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_world_model_record_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_world_model_record_contract.build_live_payload()


def test_production_data_substrate_registry_contract_recomputes_schema() -> None:
    report = check_production_data_substrate_registry_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/production_data_substrate_registry_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_production_data_substrate_registry_contract.build_live_payload()


def test_layer3_gy_data_state_substrate_contract_recomputes_schema() -> None:
    report = check_layer3_gy_data_state_substrate_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_data_state_substrate_contract.build_live_payload(
        REPO_ROOT
    )


def test_layer3_gy_value_outer_set_strangle_receipt_recomputes_schema() -> None:
    report = check_layer3_gy_value_outer_set_strangle_receipt.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_value_outer_set_strangle_receipt.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_value_outer_set_strangle_receipt.build_live_payload(
        REPO_ROOT
    )
    assert committed["strangle_receipt"]["remaining_callers"] == []


def test_layer3_gy_knowledge_substrate_contract_recomputes_schema() -> None:
    report = check_layer3_gy_knowledge_substrate_contract.validate(REPO_ROOT)
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_knowledge_substrate_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert report["status"] == "pass"
    assert committed == check_layer3_gy_knowledge_substrate_contract.build_live_payload(
        REPO_ROOT
    )


def test_layer3_gy_knowledge_substrate_contract_rejects_degenerate_l2_point(
    monkeypatch,
) -> None:
    from polisyos.core.contracts import DataTrust, ValueOuterSet
    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery

    def point_only_estimate(self, *, estimate_id, world_model_record_ref, epoch, **kwargs):
        trust_score = float(kwargs.get("trust_score_override") or 0.9)
        return ValueOuterSet.interval_box(
            coordinates=("contract_probe",),
            lower=(1.0,),
            upper=(1.0,),
            identification_mode="point_identified",
            assumptions=("contract_probe_degenerate_point",),
            assumption_status="declared",
            calibration_scope={
                "estimate_id": str(estimate_id),
                "lowering_status": "parameter_estimate_ci_interval",
            },
            data_trust=DataTrust(
                tier="probe",
                trust_cap=trust_score,
                trust_multiplier=trust_score,
                min_coverage=0.0,
                max_coverage=1.0,
                promotion_floor=0.2,
                authority_ref="contract://probe",
            ),
            world_model_record_ref=str(world_model_record_ref),
            epoch=str(epoch),
            representation_status="certified",
        )

    monkeypatch.setattr(SKGQuery, "parameter_estimate_value_outer_set", point_only_estimate)

    report = check_layer3_gy_knowledge_substrate_contract.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert any(
        issue.get("case_id") == "l2_estimate_ci_lowers_to_value_outer_set"
        for issue in report["issues"]
    )


def test_layer3_gy_knowledge_substrate_contract_rejects_presence_only_grounding(
    monkeypatch,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        GroundedCausalPriorResolution,
        SKGQuery,
    )

    def presence_only_grounding(
        self,
        *,
        cause,
        effect,
        estimand,
        scope_context_id,
        required_skg_version_id,
        min_relevance=0.55,
    ):
        return GroundedCausalPriorResolution(
            status="bound",
            cause=str(cause),
            effect=str(effect),
            estimand=str(estimand),
            scope_context_id=str(scope_context_id),
            skg_version_id=int(required_skg_version_id),
            skg_snapshot_ref="duckdb://presence-only#v1",
            edge_id="06fb46cd681818bc52d1cc01",
            relevance_score=1.0,
            content_bind_status="content_bound",
            validation_status="validated",
        )

    monkeypatch.setattr(SKGQuery, "resolve_grounded_causal_prior", presence_only_grounding)

    report = check_layer3_gy_knowledge_substrate_contract.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert any(
        issue.get("case_id")
        == "l2_skg_grounding_resolve_content_bind_validate_fail_closed"
        for issue in report["issues"]
    )


def test_production_data_substrate_registry_contract_exercises_trust_tier_bounds(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import substrate_registry

    def tier_name_presence_only(
        self,
        registration,
        *,
        expected_tier=None,
    ) -> None:
        tier = expected_tier or self.trust_tiers.get(registration.trust_tier.tier)
        if tier is None:
            raise substrate_registry.SubstrateRegistryError(
                "substrate_trust_tier_unresolved",
                f"unknown trust_tier {registration.trust_tier.tier}",
            )

    monkeypatch.setattr(
        substrate_registry.L5CatalogAuthority,
        "validate_trust_tier_bounds",
        tier_name_presence_only,
    )

    behavior_report = (
        check_production_data_substrate_registry_contract
        .substrate_registry_trust_tier_bounds_behavior_report
    )
    behavior = behavior_report(REPO_ROOT)
    report = check_production_data_substrate_registry_contract.validate(REPO_ROOT)

    assert behavior["status"] == "fail"
    assert {
        "substrate_trust_cap_inflated",
        "substrate_trust_multiplier_inflated",
    } <= {
        str(issue.get("expected_code"))
        for issue in behavior["issues"]
        if isinstance(issue, dict)
    }
    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "substrate_registry_honesty_behavior_failed"
        for issue in report["issues"]
    )


@pytest.mark.parametrize(
    ("removed_check", "expected_code"),
    [
        ("coverage", "substrate_coverage_inflated"),
        ("identification", "substrate_identification_mode_inflated"),
        ("coverage_and_identification", "substrate_coverage_inflated"),
        ("known_expected_tier", "substrate_trust_cap_inflated"),
        ("schema_regime", "substrate_schema_regime_unresolved"),
    ],
)
def test_production_data_substrate_registry_contract_exercises_known_family_honesty(
    monkeypatch,
    removed_check: str,
    expected_code: str,
) -> None:
    from polisyos.runtime.quality import substrate_registry

    def validate_with_removed_known_family_check(self, registration) -> None:
        family_id = registration.family_id
        self.validate_trust_tier_bounds(registration)
        if family_id in self.coverage_rules:
            if removed_check not in {"coverage", "coverage_and_identification"}:
                allowed_coverage = float(self.coverage_rules[family_id])
                if registration.coverage.coverage_score > allowed_coverage + 1e-9:
                    raise substrate_registry.SubstrateRegistryError(
                        "substrate_coverage_inflated",
                        f"{family_id}: {registration.coverage.coverage_score} > {allowed_coverage}",
                    )
            if removed_check not in {"identification", "coverage_and_identification"}:
                expected_identification = self.identification_modes.get(family_id)
                if (
                    expected_identification is not None
                    and registration.identification_mode != expected_identification
                ):
                    raise substrate_registry.SubstrateRegistryError(
                        "substrate_identification_mode_inflated",
                        f"{family_id}: {registration.identification_mode} != {expected_identification}",
                    )
            if removed_check != "known_expected_tier":
                expected_tier = self.expected_trust_tier(family_id)
                self.validate_trust_tier_bounds(registration, expected_tier=expected_tier)
        if removed_check != "schema_regime":
            if (
                registration.schema_regime.schema_regime_id not in self.schema_regimes
                and not registration.schema_regime.schema_regime_id.startswith("dcat:")
                and not registration.schema_regime.schema_regime_id.startswith("manifest:")
            ):
                raise substrate_registry.SubstrateRegistryError(
                    "substrate_schema_regime_unresolved",
                    registration.schema_regime.schema_regime_id,
                )

    monkeypatch.setattr(
        substrate_registry.L5CatalogAuthority,
        "validate_registration",
        validate_with_removed_known_family_check,
    )

    behavior = (
        check_production_data_substrate_registry_contract
        .substrate_registry_trust_tier_bounds_behavior_report(REPO_ROOT)
    )
    report = check_production_data_substrate_registry_contract.validate(REPO_ROOT)

    assert behavior["status"] == "fail"
    assert expected_code in {
        str(issue.get("expected_code"))
        for issue in behavior["issues"]
        if isinstance(issue, dict)
    }
    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "substrate_registry_honesty_behavior_failed"
        for issue in report["issues"]
    )


def test_production_data_substrate_registry_contract_rejects_unexercised_runtime_property(
    monkeypatch,
) -> None:
    original = (
        check_production_data_substrate_registry_contract
        ._substrate_registry_runtime_honesty_properties
    )

    def with_future_runtime_property(repo_root: Path) -> dict[str, str]:
        properties = dict(original(repo_root))
        properties["runtime_code:substrate_future_honesty"] = "substrate_future_honesty"
        return properties

    monkeypatch.setattr(
        check_production_data_substrate_registry_contract,
        "_substrate_registry_runtime_honesty_properties",
        with_future_runtime_property,
    )

    behavior = (
        check_production_data_substrate_registry_contract
        .substrate_registry_trust_tier_bounds_behavior_report(REPO_ROOT)
    )
    report = check_production_data_substrate_registry_contract.validate(REPO_ROOT)

    assert behavior["status"] == "fail"
    assert any(
        issue.get("code") == "substrate_registry_honesty_behavior_incomplete"
        for issue in behavior["issues"]
    )
    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "substrate_registry_honesty_behavior_incomplete"
        for issue in report["issues"]
    )


def test_layer3_gy_generated_artifact_gate_rejects_nested_unregistered_artifact() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_task0_audit/"
        / "layer3_gy_unregistered_probe.json"
    )
    try:
        probe.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": (
                "architecture/policy_design_case/layer3_gy_task0_audit/"
                "layer3_gy_unregistered_probe.json"
            ),
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generated_artifact_gate_rejects_unregistered_gx_report_artifact() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gx_reports/"
        / "tourism_local_development_ceiling_probe/audit_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gx_probe.v1"}\n',
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_unaccounted_output_root_file",
            "path": relative,
        } in result["issues"]
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generated_artifact_gate_rejects_unregistered_gx_data_home_artifact() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gx_data_home/cases/"
        / "audit_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gx_probe.v1"}\n',
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_unaccounted_output_root_file",
            "path": relative,
        } in result["issues"]
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generation_cycle_disposition_ledger_variant_must_be_registered() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/"
        / "layer3_gy_generation_cycle_disposition_ledger_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "policyos.policy_design_case.layer3_gy."
                        "generation_cycle_disposition_ledger.v1"
                    ),
                    "gy_lifecycle_marker": (
                        "policyos.policy_design_case.layer3_gy."
                        "generation_cycle_disposition_ledger.v1"
                    ),
                    "producer": "policyos.policy_design_case.layer3_gy_registration_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_intervention_atom_binding_contract_variant_must_be_registered() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/"
        / "layer3_gy_intervention_atom_binding_contract_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "policyos.policy_design_case.layer3_gy."
                        "intervention_atom_binding_contract.v1"
                    ),
                    "gy_lifecycle_marker": (
                        "policyos.policy_design_case.layer3_gy."
                        "intervention_atom_binding_contract.v1"
                    ),
                    "producer": "policyos.policy_design_case.layer3_gy_atom_registration_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_world_model_record_contract_variant_must_be_registered() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/"
        / "layer3_gy_world_model_record_contract_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "policyos.policy_design_case.layer3_gy."
                        "world_model_record_contract.v1"
                    ),
                    "gy_lifecycle_marker": (
                        "policyos.policy_design_case.layer3_gy."
                        "world_model_record_contract.v1"
                    ),
                    "producer": (
                        "policyos.policy_design_case.layer3_gy_world_record_registration_probe"
                    ),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_production_data_substrate_registry_contract_variant_must_be_registered() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/"
        / "production_data_substrate_registry_contract_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "policyos.policy_design_case.layer3_gy."
                        "production_data_substrate_registry_contract.v1"
                    ),
                    "gy_lifecycle_marker": (
                        "policyos.policy_design_case.layer3_gy."
                        "production_data_substrate_registry_contract.v1"
                    ),
                    "producer": "policyos.policy_design_case.substrate_registry_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_data_state_substrate_contract_variant_must_be_registered() -> None:
    probe = (
        REPO_ROOT
        / "architecture/policy_design_case/"
        / "layer3_gy_data_state_substrate_contract_unregistered_probe.json"
    )
    relative = probe.relative_to(REPO_ROOT).as_posix()
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "policyos.policy_design_case.layer3_gy."
                        "data_state_substrate_contract.v1"
                    ),
                    "gy_lifecycle_marker": (
                        "policyos.policy_design_case.layer3_gy."
                        "data_state_substrate_contract.v1"
                    ),
                    "producer": "policyos.policy_design_case.data_state_substrate_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": relative,
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generated_artifact_gate_rejects_provenance_artifact_without_name_prefix() -> None:
    probe = REPO_ROOT / "architecture/policy_design_case/gy_surface_probe.json"
    try:
        probe.write_text(
            json.dumps(
                {
                    "metadata": {
                        "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    },
                    "producer": "gy-m1-regression-probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "architecture/policy_design_case/gy_surface_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_marker_scan_rejects_public_surface_artifact_without_registry_entry() -> None:
    probe = REPO_ROOT / "architecture/public_surface/gy_public_surface_probe.json"
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "architecture/public_surface/gy_public_surface_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_marker_scan_rejects_generated_doc_artifact_without_registry_entry() -> None:
    probe = REPO_ROOT / "docs/reference/gy_generated_doc_probe.json"
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "generator": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "docs/reference/gy_generated_doc_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_marker_scan_rejects_fresh_architecture_directory_artifact() -> None:
    probe = REPO_ROOT / "architecture/gy_fresh_scope/gy_fresh_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "architecture/gy_fresh_scope/gy_fresh_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_layer3_gy_marker_scan_is_repo_scoped_for_package_json_artifacts() -> None:
    probe = REPO_ROOT / "packages/gy_package_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "packages/gy_package_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_marker_scan_is_repo_scoped_for_src_json_artifacts() -> None:
    probe = REPO_ROOT / "src/polisyos/runtime/quality/schemas/gy_schema_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "src/polisyos/runtime/quality/schemas/gy_schema_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            probe.parent.rmdir()


def test_layer3_gy_marker_scan_is_repo_scoped_for_fresh_top_level_json_artifacts() -> None:
    probe = REPO_ROOT / "gy_fresh_repo_scope/gy_fresh_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_marker_scan_probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "gy_fresh_repo_scope/gy_fresh_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_layer3_gy_marker_scan_excludes_owned_test_data() -> None:
    probe = REPO_ROOT / "tests/fixtures/gy_marker_test_data_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_gy_probe.v1",
                    "producer": "policyos.policy_design_case.layer3_gy_test_fixture",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "pass"
        assert "tests/fixtures/gy_marker_test_data_probe.json" not in set(
            result["discovered_artifacts"]
        )
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_marker_scan_reads_markdown_lifecycle_markers_repo_wide() -> None:
    probe = REPO_ROOT / "gy_fresh_repo_scope/gy_non_json_probe.md"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            "---\n"
            "gy_lifecycle_marker: policyos.policy_design_case.layer3_gy_probe.v1\n"
            "---\n"
            "\n"
            "# Probe\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "gy_fresh_repo_scope/gy_non_json_probe.md",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_layer3_gy_marker_scan_reads_toml_lifecycle_markers_repo_wide() -> None:
    probe = REPO_ROOT / "gy_fresh_repo_scope/gy_non_json_probe.toml"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            'gy_lifecycle_marker = "policyos.policy_design_case.layer3_gy_probe.v1"\n',
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "gy_fresh_repo_scope/gy_non_json_probe.toml",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_layer3_gy_contract_derived_output_root_rejects_unmarked_stray_file(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "architecture/public_surface").mkdir(parents=True)
    output_dir = repo_root / "architecture/gy_contract_probe"
    output_dir.mkdir(parents=True)
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        "[generated_artifacts]\nversion = 1\n",
        encoding="utf-8",
    )
    (repo_root / "architecture/public_surface/contract.toml").write_text(
        """
[public_surface]
version = 1

[[generated_artifact_family]]
id = "policy-design-case-layer3-gy-contract-probe"
owner = "team-runtime-quality"
regenerate = "uv run python tools/quality/validation/check_probe.py --write"
stale_output_behavior = "fail"
outputs = [
  "architecture/gy_contract_probe/registered_anchor.json",
]
""".lstrip(),
        encoding="utf-8",
    )
    stray = "architecture/gy_contract_probe/unmarked_stray.json"
    (repo_root / stray).write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.not_layer3_gy_probe.v1",
                "producer": "non-gy-stray",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_unaccounted_output_root_file",
        "path": stray,
    } in result["issues"]


def test_layer3_gy_universe_ignores_unmarked_artifact_outside_marker_and_contract_scopes(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "architecture/unowned_scope").mkdir(parents=True)
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        "[generated_artifacts]\nversion = 1\n",
        encoding="utf-8",
    )
    probe = "architecture/unowned_scope/plain_artifact.json"
    (repo_root / probe).write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_probe.v1",
                "producer": "non-gy-regression-probe",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "pass"
    assert probe not in set(result["discovered_artifacts"])


def test_layer3_gy_generated_artifact_gate_rejects_unaccounted_file_in_output_root() -> None:
    probe = REPO_ROOT / "architecture/policy_design_case/gy_omit_marker_probe.json"
    try:
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.not_layer3_gy_probe.v1",
                    "producer": "omit-marker-regression-probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_unaccounted_output_root_file",
            "path": "architecture/policy_design_case/gy_omit_marker_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generated_artifact_gate_ignores_non_gy_artifact_outside_gy_scopes() -> None:
    probe = REPO_ROOT / "architecture/non_gy_scope/non_gy_surface_probe.json"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            json.dumps(
                {
                    "schema_version": "policyos.policy_design_case.layer3_probe.v1",
                    "producer": "non-gy-regression-probe",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            REPO_ROOT
        )

        assert result["status"] == "pass"
        assert "architecture/non_gy_scope/non_gy_surface_probe.json" not in set(
            result["discovered_artifacts"]
        )
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_layer3_gy_generated_artifact_gate_rejects_phantom_outputs(tmp_path: Path) -> None:
    repo_root = tmp_path
    artifact_dir = repo_root / "architecture/policy_design_case"
    artifact_dir.mkdir(parents=True)
    workflow = "tools/quality/validation/check_probe_family.py"
    (artifact_dir / "layer3_gy_registered.json").write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    _write_declaring_workflow(
        repo_root,
        workflow_path=workflow,
        outputs=[
            "architecture/policy_design_case/layer3_gy_registered.json",
            "architecture/policy_design_case/layer3_gy_missing.json",
        ],
    )
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "gy-family"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = [
  "architecture/policy_design_case/layer3_gy_registered.json",
  "architecture/policy_design_case/layer3_gy_missing.json",
]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_registered_output_missing",
        "path": "architecture/policy_design_case/layer3_gy_missing.json",
        "family_id": "gy-family",
    } in result["issues"]


def test_layer3_gy_generated_artifact_gate_rejects_duplicate_family_claims(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    artifact_dir = repo_root / "architecture/policy_design_case"
    artifact_dir.mkdir(parents=True)
    workflow = "tools/quality/validation/check_probe_family.py"
    (artifact_dir / "layer3_gy_registered.json").write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    _write_declaring_workflow(
        repo_root,
        workflow_path=workflow,
        outputs=["architecture/policy_design_case/layer3_gy_registered.json"],
    )
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "gy-family-a"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = ["architecture/policy_design_case/layer3_gy_registered.json"]

[[family]]
id = "gy-family-b"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = ["architecture/policy_design_case/layer3_gy_registered.json"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_artifact_registered_multiple_families",
        "path": "architecture/policy_design_case/layer3_gy_registered.json",
        "family_ids": "gy-family-a,gy-family-b",
    } in result["issues"]


def test_layer3_gy_generated_family_requires_authoritative_declared_outputs(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    artifact_dir = repo_root / "architecture/policy_design_case"
    artifact_dir.mkdir(parents=True)
    workflow = "tools/quality/validation/check_probe_family.py"
    output = "architecture/policy_design_case/layer3_gy_registered.json"
    (repo_root / output).write_text(
        '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    _write_declaring_workflow(
        repo_root,
        workflow_path=workflow,
        outputs=[output],
        include_declared_outputs=False,
    )
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "gy-family"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = ["{output}"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_producer_declared_outputs_missing",
        "family_id": "gy-family",
        "workflow": workflow,
    } in result["issues"]


def test_layer3_gy_generated_family_rejects_unregistered_declared_output(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    artifact_dir = repo_root / "architecture/policy_design_case"
    artifact_dir.mkdir(parents=True)
    workflow = "tools/quality/validation/check_probe_family.py"
    registered = "architecture/policy_design_case/layer3_gy_registered.json"
    unregistered = "architecture/policy_design_case/gy_producer_extra.json"
    for output in (registered, unregistered):
        (repo_root / output).write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )
    _write_declaring_workflow(
        repo_root,
        workflow_path=workflow,
        outputs=[registered, unregistered],
    )
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "gy-family"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = ["{registered}"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_producer_output_not_registered",
        "path": unregistered,
        "family_id": "gy-family",
    } in result["issues"]


def test_layer3_gy_generated_family_rejects_declared_output_without_marker(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    artifact_dir = repo_root / "architecture/policy_design_case"
    artifact_dir.mkdir(parents=True)
    workflow = "tools/quality/validation/check_probe_family.py"
    output = "architecture/policy_design_case/gy_unmarked_declared.json"
    (repo_root / output).write_text(
        '{"schema_version":"policyos.policy_design_case.not_layer3_gy_probe.v1"}\n',
        encoding="utf-8",
    )
    _write_declaring_workflow(repo_root, workflow_path=workflow, outputs=[output])
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "gy-family"
gy_lifecycle_family = true
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
outputs = ["{output}"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_producer_output_provenance_missing",
        "family_id": "gy-family",
        "path": output,
    } in result["issues"]


def test_layer3_gy_generated_family_rejects_broad_lifecycle_schema_prefix(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    output = "architecture/policy_design_case/broad_prefix_declared.json"
    (repo_root / output).parent.mkdir(parents=True)
    (repo_root / output).write_text(
        '{"schema_version":"policyos.unrelated_schema.v1"}\n',
        encoding="utf-8",
    )
    workflow = "tools/quality/validation/check_probe_family.py"
    _write_declaring_workflow(repo_root, workflow_path=workflow, outputs=[output])
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "broad-prefix-family"
gy_lifecycle_family = true
lifecycle_schema_prefixes = ["policyos."]
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
regenerate_commands = ["python {workflow} --write"]
check_command = ["python", "{workflow}", "--check"]
outputs = ["{output}"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_family_lifecycle_schema_prefix_unbounded",
        "family_id": "broad-prefix-family",
        "prefix": "policyos.",
    } in result["issues"]
    assert {
        "code": "layer3_gy_producer_output_provenance_missing",
        "family_id": "broad-prefix-family",
        "path": output,
    } in result["issues"]


def test_layer3_gy_generated_family_rejects_policy_design_case_root_prefix(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    output = "architecture/policy_design_case/root_prefix_declared.json"
    (repo_root / output).parent.mkdir(parents=True)
    (repo_root / output).write_text(
        '{"schema_version":"policyos.policy_design_case.unrelated.v1"}\n',
        encoding="utf-8",
    )
    workflow = "tools/quality/validation/check_probe_family.py"
    _write_declaring_workflow(repo_root, workflow_path=workflow, outputs=[output])
    (repo_root / "architecture/generated_artifacts.toml").write_text(
        f"""
[[family]]
id = "root-prefix-family"
gy_lifecycle_family = true
lifecycle_schema_prefixes = ["policyos.policy_design_case."]
lifecycle = "generated_committed"
owner = "team-runtime-quality"
stale_output_behavior = "fail"
drift_gate = "automated"
workflow = "{workflow}"
regenerate_commands = ["python {workflow} --write"]
check_command = ["python", "{workflow}", "--check"]
outputs = ["{output}"]
""".lstrip(),
        encoding="utf-8",
    )

    result = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        repo_root
    )

    assert result["status"] == "fail"
    assert {
        "code": "layer3_gy_family_lifecycle_schema_prefix_unbounded",
        "family_id": "root-prefix-family",
        "prefix": "policyos.policy_design_case.",
    } in result["issues"]
    assert {
        "code": "layer3_gy_producer_output_provenance_missing",
        "family_id": "root-prefix-family",
        "path": output,
    } in result["issues"]


def test_layer3_gy_registered_artifact_families_have_lifecycle_metadata() -> None:
    payload = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    families = {family["id"]: family for family in payload["family"]}
    report = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        REPO_ROOT
    )

    assert report["status"] == "pass"
    assert "policy-design-case-layer3-gy-task0-audit-artifacts" in report["family_ids"]
    assert "policy-design-case-layer3-gy-loop-source-artifacts" in report["family_ids"]
    for family_id in report["family_ids"]:
        family = families[family_id]
        assert family["owner"] == "team-runtime-quality"
        assert family["lifecycle"] in {"generated_committed", "source_committed"}
        assert family["gy_lifecycle_family"] is True
        assert family["stale_output_behavior"] == "fail"
        assert family["drift_gate"] == "automated"
        assert family["outputs"]
        assert family["regenerate_commands"]
        assert "--check" in list(family["check_command"])
        for output in family["outputs"]:
            assert output in report["registered_outputs"]
            assert (REPO_ROOT / output).is_file()


def test_layer3_gy_n11_confidence_ledger_has_one_frozen_lifecycle_owner() -> None:
    family_id = "policy-design-case-layer3-gy-n11-confidence-ledger"
    output = "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
    catalog_path = (
        "production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb"
    )
    l5_path = (
        "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/"
        "runtime_calibration_internals/calibration/d2/measurement_registry.json"
    )
    payload = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    matching = [
        family
        for family in payload["family"]
        if family["id"] == family_id
    ]

    assert len(matching) == 1
    family = matching[0]
    assert family["lifecycle"] == "generated_committed"
    assert family["gy_lifecycle_family"] is True
    assert family["stale_output_behavior"] == "fail"
    assert family["drift_gate"] == "automated"
    assert family["outputs"] == [output]
    assert family["regenerate_commands"] == [
        "JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test "
        "python tools/quality/validation/check_layer3_gy_confidence_ledger.py --write "
        f"--catalog-path {catalog_path} --l5-path {l5_path}"
    ]
    assert family["workflow"] == (
        "tools/quality/validation/check_layer3_gy_confidence_ledger.py"
    )
    assert family["check_command"] == [
        "env",
        "JAX_PLATFORMS=cpu",
        "uv",
        "run",
        "--extra",
        "analytics",
        "--extra",
        "solvers",
        "--extra",
        "test",
        "python",
        "tools/quality/validation/check_layer3_gy_confidence_ledger.py",
        "--check",
        "--catalog-path",
        catalog_path,
        "--l5-path",
        l5_path,
    ]

    report = check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
        REPO_ROOT
    )
    n11_issues = [
        issue
        for issue in report["issues"]
        if issue.get("family_id") == family_id or issue.get("path") == output
    ]

    assert report["family_ids"].count(family_id) == 1
    assert report["registered_outputs"].count(output) == 1
    assert report["producer_declared_outputs"].count(output) == 1
    assert report["discovered_artifacts"].count(output) == 1
    assert report["registered_artifacts"].count(output) == 1
    assert n11_issues == []


def test_layer3_gy_loop_family_uses_honest_generated_and_source_classifications() -> None:
    payload = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    families = {family["id"]: family for family in payload["family"]}

    generated = families["policy-design-case-layer3-gy-loop-artifacts"]
    source = families["policy-design-case-layer3-gy-loop-source-artifacts"]

    assert generated["lifecycle"] == "generated_committed"
    assert generated["outputs"] == [
        "architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json",
        check_layer3_gy_loop_artifacts.GRADED_OUTCOME_PATH,
        check_layer3_gy_loop_artifacts.OUTCOME_RUN_PATH,
        check_layer3_gy_loop_artifacts.OUTCOME_REPLAY_PATH,
    ]
    assert "--write" in " ".join(generated["regenerate_commands"])
    assert source["lifecycle"] == "source_committed"
    assert source["outputs"] == [
        "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json",
        "architecture/policy_design_case/layer3_gy_semantic_benchmark.json",
    ]
    assert source["source_integrity_sha256"]
    assert "human-authored" in source["source_committed_rationale"]


def test_layer3_gy_loop_source_artifacts_fail_closed_on_integrity_drift() -> None:
    source_paths = (
        REPO_ROOT / "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json",
        REPO_ROOT / "architecture/policy_design_case/layer3_gy_semantic_benchmark.json",
    )
    originals = {path: path.read_text(encoding="utf-8") for path in source_paths}
    try:
        for path in source_paths:
            for restore_path, text in originals.items():
                restore_path.write_text(text, encoding="utf-8")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["__audit_corruption__"] = "source-integrity-drift"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = check_layer3_gy_loop_artifacts.validate(REPO_ROOT)

            assert result["status"] == "fail"
            assert any(
                issue.get("code") == "layer3_gy_source_output_integrity_drift"
                and issue.get("path") == path.relative_to(REPO_ROOT).as_posix()
                for issue in result["issues"]
            )
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")


def test_layer3_gy_loop_validator_recomputes_durable_worker_proofs() -> None:
    live_payloads = check_layer3_gy_loop_artifacts.build_live_loop_artifacts(REPO_ROOT)
    _assert_live_payloads_match_declared_outputs(
        check_layer3_gy_loop_artifacts,
        live_payloads,
    )
    committed = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json")
        .read_text(encoding="utf-8")
    )

    assert committed == live_payloads["architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json"]


def test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked(gy_l_complete_live_population) -> None:
    live_payloads, observations, _ = gy_l_complete_live_population
    outcome = live_payloads[check_layer3_gy_loop_artifacts.OUTCOME_RUN_PATH]
    replay = live_payloads[check_layer3_gy_loop_artifacts.OUTCOME_REPLAY_PATH][
        "replay_proof"
    ]
    proof = outcome["production_loop_run_proof"]
    contract = outcome["search_exit_contract"]

    assert outcome["trigger_kind"] == "http_control_route"
    assert outcome["http_receipts"]["launch"]["status_code"] == 200
    assert outcome["http_receipts"]["readback"]["status_code"] == 200
    assert proof["job_id"] == outcome["http_receipts"]["launch"]["job_id"]
    assert proof["worker_lease_id"]
    assert proof["_execute_workflow_invocation_id"]
    assert proof["workspace_loop_invocation_id"]
    assert proof["control_store_state_transitions"] == ["pending", "running", "completed"]
    assert proof["output_cas_refs"]
    assert proof["artifacts_index_refs"]
    assert "runs_readback" in proof["surface_reads_checked"]
    assert contract["terminal_state"]["kind"] == "a_spec_gap"
    assert contract["authority_boundary"] is None
    assert contract["evidence_kind"] is None
    assert contract["decision_grade"] == "unsupported"
    assert contract["evidence_ladder_rung"] == "none"
    production = [
        observation for observation in observations
        if observation._checked_snapshot()[0].catalog_mode == "production"
    ]
    (observation,) = production
    custody = observation._checked_custody()
    admission = custody["production_admission"]
    admission_ref = custody["recorded_production_evidence"]["admission_ref"]
    assert observation["proof"]["job_id"] == proof["job_id"]
    workspace = contract["workspace_contract"]
    ledger = contract["search_ledger"]
    assert workspace["refusal_source_admission_ref"] == admission_ref
    assert workspace["refusal_reason"] == admission["positive_admission_state"]
    assert ledger["source_admission_ref"] == admission_ref
    assert ledger["admission_decision_refs"] == [
        decision["decision_id"] for decision in admission["graded_decisions"]
    ]
    quality = contract["incompleteness_record"]["search_quality"]
    assert quality["recall_at_known_seeds"] is None
    assert quality["semantic_benchmark_run"]["population_state"] == "not_established"
    assert ledger["counterexample_conversion_rate"] is None
    assert outcome["useful_design_credit"] is False
    assert outcome["production_case_outcome"]["outcome_kind"] == outcome["terminal_outcome"]
    assert outcome["production_case_outcome"]["useful_design_credit"] is False
    assert outcome["production_case_outcome"]["final_run_hash"].startswith("sha256:")
    assert replay["replay_levels"] == ["A", "B", "C"]
    assert replay["input_hashes"]
    assert replay["output_hash"] == outcome["output_hash"]


def test_layer3_gy_outcome_validator_rejects_direct_helper_and_hand_authored_proof() -> None:
    outcome = json.loads((REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_RUN_PATH).read_text())
    replay = json.loads(
        (
            REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_REPLAY_PATH
        ).read_text()
    )

    helper = json.loads(json.dumps(outcome))
    helper["trigger_kind"] = "direct_workspace_loop_helper"
    helper_issues: list[dict[str, str]] = []
    check_layer3_gy_loop_artifacts.validate_outcome_run(
        helper,
        replay,
        helper_issues,
    )
    assert {"code": "layer3_gy_outcome_direct_helper_rejected"} in helper_issues

    authored = json.loads(json.dumps(outcome))
    authored["proof_source"] = "hand_authored"
    authored_issues: list[dict[str, str]] = []
    check_layer3_gy_loop_artifacts.validate_outcome_run(
        authored,
        replay,
        authored_issues,
    )
    assert {"code": "layer3_gy_outcome_hand_authored_proof_rejected"} in authored_issues

    shaped = json.loads(json.dumps(outcome))
    shaped["production_loop_run_proof"]["job_id"] = "hand-authored-shape"
    shaped_issues: list[dict[str, str]] = []
    check_layer3_gy_loop_artifacts.validate_outcome_run(
        shaped,
        replay,
        shaped_issues,
    )
    assert {"code": "layer3_gy_outcome_production_proof_content_drift"} in shaped_issues


def test_layer3_gy_outcome_replay_corrupt_field_detects_drift() -> None:
    outcome = json.loads((REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_RUN_PATH).read_text())
    replay = json.loads(
        (
            REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_REPLAY_PATH
        ).read_text()
    )
    outcome["search_exit_contract"]["terminal_state"]["reason"] = "corrupted"
    issues: list[dict[str, str]] = []

    check_layer3_gy_loop_artifacts.validate_outcome_run(outcome, replay, issues)

    assert {"code": "layer3_gy_outcome_replay_output_drift"} in issues


def test_layer3_gy_outcome_validator_rejects_gx_terminal_drift() -> None:
    outcome = json.loads((REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_RUN_PATH).read_text())
    replay = json.loads(
        (
            REPO_ROOT / check_layer3_gy_loop_artifacts.OUTCOME_REPLAY_PATH
        ).read_text()
    )
    outcome["production_case_outcome"]["outcome_kind"] = "grounded_partial_admissible"
    issues: list[dict[str, str]] = []

    check_layer3_gy_loop_artifacts.validate_outcome_run(outcome, replay, issues)

    assert {"code": "layer3_gy_outcome_gx_terminal_drift"} in issues


def test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report(
    gy_l_complete_live_population,
) -> None:
    """Use only the producer's real production observations, never fixture credit."""
    owner = check_layer3_gy_loop_artifacts
    live_payloads, observations, _ = gy_l_complete_live_population
    _assert_live_payloads_match_declared_outputs(owner, live_payloads)
    expected_population = [
        observation
        for observation in observations
        if observation._checked_snapshot()[0].catalog_mode == "production"
    ]
    # The exact real observation objects carry the current source/S1 readback.
    # An unrelated fixture cannot become a numerator by matching its shape.
    actual_report = owner._build_graded_outcome_report(expected_population)
    live_report = live_payloads[owner.GRADED_OUTCOME_PATH]
    committed = json.loads((REPO_ROOT / owner.GRADED_OUTCOME_PATH).read_text())
    assert committed == live_report == actual_report
    population = live_report["population"]
    assert population["member_count"] == len(expected_population)
    assert [row["population_position"] for row in population["members"]] == list(
        range(len(expected_population))
    )
    groups = (
        live_report["graded_outcomes"],
        live_report["honest_non_value_outcomes"],
        live_report["unmeasurable_outcomes"],
    )
    assert sum(len(rows) for rows in groups) == len(expected_population)
    expected_rate = (
        None
        if groups[2] or not expected_population
        else round(len(groups[0]) / len(expected_population), 4)
    )
    assert live_report["summary"]["useful_design_rate"] == expected_rate
    expected_pairs = {
        (row["proof"]["run_id"], row["proof"]["job_id"]) for row in expected_population
    }
    assert {
        (member["run_id"], member["job_id"]) for member in population["members"]
    } == expected_pairs


def test_layer3_gy_loop_graded_outcome_corrupt_field_self_check_fails_closed() -> None:
    report = check_layer3_gy_loop_artifacts.validate(
        REPO_ROOT,
        corrupt_field_drift_check=True,
    )

    assert report["status"] == "fail"
    assert {"code": "layer3_gy_graded_outcome_corrupt_field_drift_detected"} in report[
        "issues"
    ]


def test_layer3_gy_composition_validator_recomputes_certificates() -> None:
    live_payloads = check_layer3_gy_composition_artifacts.build_live_composition_artifacts(
        REPO_ROOT
    )
    _assert_live_payloads_match_declared_outputs(
        check_layer3_gy_composition_artifacts,
        live_payloads,
    )
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_composition_certificates.json"
        ).read_text(encoding="utf-8")
    )

    assert committed == live_payloads[
        "architecture/policy_design_case/layer3_gy_composition_certificates.json"
    ]
    assert any(
        run.get("terminal_state", {}).get("kind") == "grounded_partial_admissible"
        and run.get("composition_certificate", {}).get("verdict") == "composable"
        and run.get("composition_certificate", {}).get("composition_receipt_ref")
        for run in committed["recursive_runs"]
    )
    assert committed.get("composition_receipts")
    assert committed.get("independence_consistency_verifications")
    assert committed.get("p14_independence_verifications")


def test_layer3_gy_composition_corrupt_field_self_check_fails_closed() -> None:
    report = check_layer3_gy_composition_artifacts.validate(
        REPO_ROOT,
        corrupt_field_drift_check=True,
    )

    assert report["status"] == "fail"
    assert {"code": "layer3_gy_composition_corrupt_field_drift_detected"} in report["issues"]


def test_layer3_gy_generated_artifact_gate_rejects_unregistered_artifacts() -> None:
    probe = REPO_ROOT / "architecture/policy_design_case/layer3_gy_unregistered_probe.json"
    try:
        probe.write_text(
            '{"schema_version":"policyos.policy_design_case.layer3_gy_probe.v1"}\n',
            encoding="utf-8",
        )

        result = check_layer3_gy_loop_artifacts.validate(REPO_ROOT)

        assert result["status"] == "fail"
        assert {
            "code": "layer3_gy_artifact_not_registered",
            "path": "architecture/policy_design_case/layer3_gy_unregistered_probe.json",
        } in result["issues"]
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_ownership_regression_guardrails() -> None:
    gy_loop_source = (REPO_ROOT / "src/polisyos/runtime/quality/workspace/loop.py").read_text(
        encoding="utf-8"
    )
    gy_spine_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/workspace/spine_repair_gates.py"
    ).read_text(encoding="utf-8")
    adapter_contracts_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/adapter_contracts.py"
    ).read_text(encoding="utf-8")
    acquisition_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/acquisition_planner.py"
    ).read_text(encoding="utf-8")
    data_forge_binding_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/data_forge_binding.py"
    ).read_text(encoding="utf-8")
    semantic_binding_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/semantic_binding.py"
    ).read_text(encoding="utf-8")
    gy_waist_source = (REPO_ROOT / "src/polisyos/pdc/_impl/gy_waist.py").read_text(
        encoding="utf-8"
    )
    gy_adapters_source = (REPO_ROOT / "src/polisyos/runtime/quality/workspace/scientist_node_adapters.py").read_text(
        encoding="utf-8"
    )
    layer2_composition_source = (
        REPO_ROOT / "src/polisyos/runtime/quality/design_axes/coupling_composition.py"
    ).read_text(encoding="utf-8")
    policy_search_source = (
        REPO_ROOT / "src/polisyos/scientist/policy_design/search.py"
    ).read_text(encoding="utf-8")

    assert "_InMemoryWorkspaceCatalogGraph" not in gy_loop_source
    assert "2026-06-15T00:00:00Z" not in gy_loop_source
    assert "class WorkspaceSearchLedger(SearchLedger)" in gy_loop_source
    assert "class WorkspaceSearchLedger(BaseModel)" not in gy_loop_source
    assert "class AcquisitionPlanner" not in gy_loop_source
    assert "class FormalGate" not in gy_loop_source
    assert "class ConnectorAdmissionGate" not in gy_loop_source
    assert "class DataRequirementAdmissionGate" not in gy_loop_source
    assert "class SemanticAdequacyGate" not in gy_loop_source
    assert "class GySemanticBenchmark" not in gy_loop_source
    assert "class SemanticBenchmarkRun" not in gy_loop_source
    assert "class MeasurementRootProducer" not in gy_loop_source
    assert "plan_requirement_gap_acquisition(" not in gy_loop_source
    assert "plan_requirement_gap_acquisition(" in acquisition_source
    assert "class ConnectorAdmissionGate" in adapter_contracts_source
    assert "class DataRequirementAdmissionGate" in adapter_contracts_source
    assert "class MeasurementRootProducer" in data_forge_binding_source
    assert "class SemanticAdequacyGate" in semantic_binding_source
    assert "class GySemanticBenchmark" in semantic_binding_source
    assert "producer\": \"polisyos.runtime.quality.AcquisitionPlanner\"" not in gy_loop_source
    assert "derive_phase2_parameter_bounds(" in gy_spine_source
    assert "verify_phase2_governance_tail(" in gy_spine_source
    assert "polisyos.scientist.nodes.builtins.governance" not in gy_spine_source
    assert "math.isfinite" not in gy_spine_source
    assert "_REQUIRED_SIX_JUDGES" not in gy_spine_source
    assert "phase2.judge_stack.six_judges_present" not in gy_spine_source
    assert "require_explicit_parameter_bounds: bool = True" in policy_search_source
    assert "allow_legacy_shadow_inferred_bounds: bool = False" in policy_search_source
    assert "legacy-shadow/candidate-only" in policy_search_source
    assert "require_explicit_parameter_bounds: bool = False" not in policy_search_source
    assert "class SubDesignContract" in gy_waist_source
    assert "class CompositionCertificate" in gy_waist_source
    assert "class DesignInterfaceContract" in layer2_composition_source
    assert "class CompositionReceipt" in layer2_composition_source
    assert "def compose_subdesigns" in layer2_composition_source
    assert "def validate_adapter_preservation" not in gy_adapters_source
    assert "def validate_scientist_node_adapter_shape" in gy_adapters_source


def test_layer3_gy_production_loop_run_proof_committed_and_authority_path_checked() -> None:
    payload = (
        REPO_ROOT / "architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json"
    ).read_text(encoding="utf-8")

    proofs = json.loads(payload)["proofs"]

    assert len(proofs) >= 2
    for proof in proofs:
        assert proof["endpoint"] == "/api/v1/control/runs"
        assert proof["legacy_path_disposition"] == "routed_to_workspace_loop"
        assert proof["output_search_exit_contract_ref"].startswith("sha256:")
        assert not re.fullmatch(
            r"sha256:([0-9a-f])\1{63}",
            proof["output_search_exit_contract_ref"],
        )
        for ref in proof["output_cas_refs"]:
            assert not re.fullmatch(r"sha256:([0-9a-f])\1{63}", ref)
        assert "runs_readback" in proof["surface_reads_checked"]
        assert proof["surface_readbacks"]
        readback = proof["surface_readbacks"][0]
        assert readback["surface"] == "/api/v1/control/runs"
        assert readback["observed_job_state"] == "completed"
        assert readback["observed_search_exit_contract_ref"] == proof[
            "output_search_exit_contract_ref"
        ]
        assert readback["matched_search_exit_contract_ref"] is True
        assert proof["control_store_state_transitions"] == ["pending", "running", "completed"]
        assert proof["worker_lease_id"].startswith("control-worker")
        if readback["observed_authority_result"] == "verifier_stamped":
            assert "authority_derivation_trace_ref" in proof["artifacts_index_refs"]
        if readback["observed_authority_result"] == "acquisition_required":
            assert "authority_derivation_trace_ref" not in proof["artifacts_index_refs"]


def _c1_live_admission_station(tmp_path: Path):
    from types import SimpleNamespace

    from polisyos.pdc import OperationClass, SearchTerminalKind
    from polisyos.runtime.quality.workspace import workflow_playbook_projection as owner
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
        _node,
        _ProducingNode,
        _station,
    )

    ctx, state = _station(tmp_path)
    node = _ProducingNode(_node().spec)
    nodes = SimpleNamespace(get=lambda node_id: node)
    candidate = owner._step_from_invocation(
        workflow_id="scientist_policy_design",
        invocation=SimpleNamespace(
            alias="run_causal_evaluation", node_id=node.spec.metadata.component_id,
        ),
        node_registry=nodes,
    )
    admission = owner.admit_playbook_step(
        candidate, node_registry=nodes, ctx=ctx, state=state,
        workspace_id="ws-c1-proof", invocation_id="invoke-c1-proof", cycle_index=1,
    )
    assert admission.step is not None, admission.conformance.failures
    execution = admission.conformance.execution
    assert execution is not None
    selected = owner.select_playbook_for_intent({"policy_question": "C1 conformance proof"})
    trajectory = owner.PlaybookTrajectory(
        playbook_id=selected.playbook_id, source_workflow_id=selected.playbook_id,
        default_operation_classes=[candidate.operation_class], steps=[candidate],
        authority_path_disposition="loop_only",
    )
    registry = owner.PlaybookRegistry(playbooks={selected.playbook_id: trajectory})
    stable = SimpleNamespace(
        adapter_admissions=[admission], operation_invocations=[execution.invocation],
        search_ledger_events=[execution.ledger_event], artifact_envelopes=execution.artifact_envelopes,
        terminal_state=SimpleNamespace(kind=SearchTerminalKind.FRONTIER_STABLE),
        phase2_playbook_trace=SimpleNamespace(out_of_scope_steps=[]),
    )
    deviation = SimpleNamespace(
        terminal_state=SimpleNamespace(kind=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED),
        phase2_playbook_trace=SimpleNamespace(deviation_operation=OperationClass.REFINE),
    )
    return ctx, stable, deviation, selected, registry


def test_c1_playbook_proof_binds_the_admission_the_consumer_used(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    ctx, stable, deviation, selected, registry = _c1_live_admission_station(tmp_path)
    payload = check_layer3_gy_phase2_artifacts.build_playbook_admission_proof(
        REPO_ROOT, stable=stable, deviation=deviation, selected=selected,
        registry=registry, store=ctx.store,
    )
    admission = stable.adapter_admissions[0]
    witness = payload["proofs"][0]["adapter_admissions"][0]
    raw = json.loads(capsys.readouterr().err.splitlines()[-1])["raw_run_admissions"][0]
    assert raw["conformance_ref"] == admission.conformance_ref.model_dump(mode="json")
    assert witness["candidate"] == admission.candidate.model_dump(mode="json")
    assert raw["conformance"] == admission.conformance.model_dump(mode="json")
    assert witness["conformance"]["input_state_hash"] == admission.conformance.input_state_hash
    assert witness["conformance_semantic_digest"].startswith("sha256:")
    assert witness["admission_state"] == "admitted"
    assert witness["operation_invocation_id"] == stable.operation_invocations[0].invocation_id
    assert payload["proofs"][0]["candidate_step_ids"] == [admission.candidate.step_id]
    assert ctx.calls == ["execute"]


def test_c1_playbook_proof_refuses_changed_receipt_with_markers_intact(tmp_path: Path) -> None:
    import pytest

    ctx, stable, deviation, selected, registry = _c1_live_admission_station(tmp_path)
    admission = stable.adapter_admissions[0]
    changed = admission.conformance.model_copy(update={"input_state_hash": "sha256:" + "0" * 64})
    stable.adapter_admissions = [admission.model_copy(update={"conformance": changed})]
    with pytest.raises(AssertionError, match="c1_conformance_receipt_payload_mismatch"):
        check_layer3_gy_phase2_artifacts.build_playbook_admission_proof(
            REPO_ROOT, stable=stable, deviation=deviation, selected=selected,
            registry=registry, store=ctx.store,
        )


def test_c1_proof_semantics_are_stable_across_fresh_cas_emission_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime

    from polisyos.core.artifacts import manifest

    packets = []
    raw_refs = []
    for hour in (1, 2):
        class EmissionClock(datetime):
            @classmethod
            def now(cls, tz=None, *, emission_hour=hour):
                return datetime(2026, 9, 8, emission_hour, tzinfo=tz)

        with monkeypatch.context() as patch:
            patch.setattr(manifest, "datetime", EmissionClock)
            ctx, stable, deviation, selected, registry = _c1_live_admission_station(
                tmp_path / str(hour),
            )
        raw_refs.append(stable.adapter_admissions[0].conformance_ref)
        packets.append(check_layer3_gy_phase2_artifacts.build_playbook_admission_proof(
            REPO_ROOT, stable=stable, deviation=deviation, selected=selected,
            registry=registry, store=ctx.store,
        ))
    assert raw_refs[0] != raw_refs[1], "The control must produce distinct raw custody receipts."
    assert packets[0] == packets[1], "Run-emission time is not a changed admission property."


@pytest.mark.parametrize(
    "source",
    [
        "def admit(adapter):\n    run = adapter.execute_candidate\n    return run()\n",
        "from polisyos.runtime.quality.workspace.workflow_playbook_projection import PlaybookStep\n"
        "def admit(**kwargs):\n    ctor = PlaybookStep\n    return ctor(**kwargs)\n",
    ],
)
def test_c1_strangle_finds_new_aliased_admission_bypass(tmp_path: Path, source: str) -> None:
    path = tmp_path / "src/new_owner.py"
    path.parent.mkdir()
    path.write_text(source, encoding="utf-8")
    receipt = check_layer3_gy_phase2_artifacts.recompute_playbook_admission_strangle(tmp_path)
    assert receipt["unexpected_callers"], "A new aliased production bypass escaped the fence."
    assert {row["path"] for row in receipt["unexpected_callers"]} == {"src/new_owner.py"}


def test_c3_binding_vocabulary_uses_every_real_method_and_signature() -> None:
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    report = check_layer3_gy_phase2_artifacts.recompute_foundry_binding_vocabulary()
    registry = MethodRegistry.get_instance()
    expected = {(row.fqn, row.abi_digest()) for row in registry.list_all()}
    observed = {(row["method_fqn"], row["signature_digest"]) for row in report["methods"]}
    with registry.snapshot_scope() as snapshot:
        independent = {(row.fqn, row.signature.abi_digest()) for row in snapshot.entries()}
    assert observed == expected == independent
    assert report["denominator"]["list_all"] == len(expected)
    assert {row["support_state"] for row in report["methods"]} <= {
        "recorded_panel_compatible",
        "other_typed_contract",
        "typed_input_without_contract_id",
        "no_concrete_input_contract_declared",
        "ambiguous",
    }
    assert report["coverage_claim"] == "full_vocabulary_classified_not_all_methods_executed"


def test_c3_binding_vocabulary_rejects_a_removed_method_identity() -> None:
    report = check_layer3_gy_phase2_artifacts.recompute_foundry_binding_vocabulary()
    assert report["methods"]
    removed = report["methods"].pop()
    issues = check_layer3_gy_phase2_artifacts.validate_foundry_binding_vocabulary(report)
    print(
        json.dumps(
            {"probe": "removed_method_identity_markers_retained", "issues": issues}, sort_keys=True
        )
    )
    assert {
        "code": "c3_method_vocabulary_identity_missing",
        "method_fqn": removed["method_fqn"],
        "signature_digest": removed["signature_digest"],
    } in issues


def test_layer3_gy_phase2_proof_artifacts_are_committed_and_semantic() -> None:
    live_payloads = check_layer3_gy_phase2_artifacts.build_live_proof_payloads(REPO_ROOT)
    _assert_live_payloads_match_declared_outputs(
        check_layer3_gy_phase2_artifacts,
        live_payloads,
    )
    for relative_path, live_payload in live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert committed == live_payload

    proof_root = REPO_ROOT / "architecture/policy_design_case"
    playbook = json.loads(
        (proof_root / "layer3_gy_phase2_playbook_run_proofs.json").read_text(
            encoding="utf-8"
        )
    )
    spine = json.loads(
        (proof_root / "layer3_gy_phase2_spine_repair_proofs.json").read_text(
            encoding="utf-8"
        )
    )
    foundry = json.loads(
        (proof_root / "layer3_gy_phase2_foundry_consumption_proofs.json").read_text(
            encoding="utf-8"
        )
    )
    agent = json.loads(
        (proof_root / "layer3_gy_phase2_agent_event_audit.json").read_text(
            encoding="utf-8"
        )
    )

    assert playbook["proofs"][0]["legacy_workflow_id_disposition"] == "legacy_shadow_context"
    assert playbook["proofs"][0]["authority_path_disposition"] == "loop_only"
    assert set(playbook["proofs"][0]["executed_legacy_aliases"]) >= {
        "run_causal_evaluation",
        "run_normative_arbitration",
    }
    assert all(
        step.get("disposition") == "surface_out_of_scope"
        for step in playbook["proofs"][0].get("out_of_scope_steps", [])
    )
    assert any(
        proof.get("none_to_zero_laundering_rejected") is True for proof in spine["proofs"]
    )
    assert any(
        proof.get("proof_id") == "phase2-causal-input-producers-resolve-default-path"
        and proof.get("default_path_resolved") is True
        and proof.get("unresolved_blockers") == []
        for proof in spine["proofs"]
    )
    measurement_foundry = next(
        proof
        for proof in foundry["proofs"]
        if proof["proof_id"] == "phase2-estimate-consumes-foundry-output-through-loop"
    )
    foundry_boundary = measurement_foundry["authority_boundary"]
    assert foundry_boundary["evidence_kind"] == "measurement"
    assert foundry_boundary["decision_grade"] == "descriptive_only"
    assert measurement_foundry["input_provenance"] == "measurement_rooted"
    assert measurement_foundry["measurement_root_refs"]
    assert measurement_foundry["consumed_method_output_refs"]
    synthetic_foundry = next(
        proof
        for proof in foundry["proofs"]
        if proof["proof_id"] == "phase2-estimate-synthetic-panel-stays-simulation"
    )
    assert synthetic_foundry["input_provenance"] == "synthetic_probe"
    assert synthetic_foundry["authority_boundary"]["evidence_kind"] == "simulation"
    assert synthetic_foundry["measurement_root_refs"] == []
    assert "F10" in synthetic_foundry["open_production_findings"]
    assert agent["audit"]["candidate_only_required"] is True
    assert agent["audit"]["knowledge_tool_registry_core_tool_count"] == 20
    assert agent["audit"]["tool_loop_execution"]["client_generate_calls"] == 2
    assert agent["audit"]["tool_loop_execution"]["tool_calls"] == ["search_datasets"]
    assert agent["audit"]["tool_loop_execution"]["persisted_event_ref_count"] == 4


def test_layer3_artifact_surface_safety_validator_recomputes_proofs() -> None:
    live_payloads = check_layer3_artifact_surface_safety.build_live_proof_payloads(
        REPO_ROOT
    )
    _assert_live_payloads_match_declared_outputs(
        check_layer3_artifact_surface_safety,
        live_payloads,
    )
    for relative_path, live_payload in live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert committed == live_payload


def test_layer3_time_source_authority_validator_recomputes_proofs() -> None:
    live_payloads = check_layer3_time_source_authority.build_live_proof_payloads(
        REPO_ROOT
    )
    _assert_live_payloads_match_declared_outputs(
        check_layer3_time_source_authority,
        live_payloads,
    )
    inventory = live_payloads[
        "architecture/policy_design_case/layer3_gy_authority_candidate_inventory.json"
    ]
    consistency = live_payloads[
        "architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json"
    ]
    assert inventory["row_count"] == 406
    assert inventory["reconciliation"]["gx_positive_status_count"] == 0
    assert consistency["audit_model"] == "TimeSourceConsistencyAuditProjection"
    assert {
        audit["mismatch_disposition"] for audit in consistency["audits"]
    } <= {
        "consistent",
        "inconsistent",
        "insufficient_evidence",
        "blocked_for_owner_review",
    }
    assert "consistent" in {
        audit["mismatch_disposition"] for audit in consistency["audits"]
    }
    assert all(
        row["disposition"] == "authority_admitted"
        for row in consistency["s12_ref_dereference"]["real_ref_results"]
    )
    for relative_path, live_payload in live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert committed == live_payload


def test_layer3_time_source_authority_validator_rejects_legacy_model_and_token() -> None:
    payload = deepcopy(
        check_layer3_time_source_authority.build_live_proof_payloads(REPO_ROOT)[
            "architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json"
        ]
    )
    payload["audit_model"] = "TimeSourceEnvelopeAudit"
    payload["audits"][0]["mismatch_disposition"] = "admitted"
    issues: list[dict[str, str]] = []

    check_layer3_time_source_authority._validate_time_source_audit(payload, issues)

    assert {issue["code"] for issue in issues} >= {
        "time_source_audit_model_mismatch",
        "time_source_disposition_unknown",
    }


@pytest.fixture(scope="module")
def workflow_failure_authority_live_payloads() -> dict[str, dict[str, object]]:
    return check_layer3_workflow_failure_authority.build_live_proof_payloads(
        REPO_ROOT
    )


def test_layer3_workflow_failure_authority_has_real_execution(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
) -> None:
    from collections import Counter

    from polisyos.scientist.orchestration.workflows.discovery import discovery_workflow_spec

    owner = check_layer3_workflow_failure_authority
    live_payloads = workflow_failure_authority_live_payloads
    _assert_live_payloads_match_declared_outputs(
        owner, live_payloads,
    )
    proof = live_payloads[owner.PROOF_PATH]
    issues: list[dict[str, str]] = []
    owner._validate_proof_payload(proof, issues)
    assert issues == []
    scenarios = {item["scenario"]: item for item in proof["proofs"]}
    assert scenarios["workflow_failure"]["terminal_job_state"] == "failed"
    candidate = scenarios["legacy_shadow_candidate"]
    assert candidate["authority_result"] == "candidate_only"
    execution = candidate["workflow_execution"]
    spec = discovery_workflow_spec()
    assert execution["workflow_spec"] == spec.model_dump(mode="json")
    assert execution["workflow_report"]["run_id"] == candidate["run_id"]
    assert Counter(
        (row["alias"], row["node_id"]) for row in execution["workflow_report"]["nodes"]
    ) == Counter((row.alias, str(row.node_id)) for row in spec.nodes)
    for scenario in scenarios.values():
        assert set(scenario["surface_reads_checked"]) >= {
            "control_worker_precompletion",
            "run",
            "artifact",
            "lineage",
            "export",
            "dashboard",
            "public_packet",
        }
        assert scenario["worker_claim"]["payload"]["run_id"] == scenario["run_id"]


def test_layer3_workflow_failure_authority_validator_recomputes_proofs(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
) -> None:
    owner = check_layer3_workflow_failure_authority
    for relative_path, live_payload in workflow_failure_authority_live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert owner.comparison_payload(committed) == owner.comparison_payload(live_payload)


def test_layer3_workflow_failure_authority_refuses_removed_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    monkeypatch.setattr(
        ControlPlaneService, "_run_legacy_scientist_workflow", lambda *args: None
    )
    with pytest.raises(ValueError, match="workflow_report_execution_not_established"):
        check_layer3_workflow_failure_authority._run_durable_authority_surface_proof(
            "legacy_shadow_candidate"
        )


def test_layer3_workflow_failure_authority_comparison_preserves_decisive_fields(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
) -> None:
    import hashlib

    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.scientist.orchestration.engine.executor import WorkflowReport

    owner = check_layer3_workflow_failure_authority
    original = workflow_failure_authority_live_payloads[owner.PROOF_PATH]
    expected = owner.comparison_payload(original)
    # Walk every real emitted node, retaining valid CAS content addresses after mutation.
    candidate = next(row for row in original["proofs"] if row["workflow_execution"] is not None)
    for index in range(len(candidate["workflow_execution"]["workflow_report"]["nodes"])):
        changed = deepcopy(original)
        proof = next(row for row in changed["proofs"] if row["workflow_execution"] is not None)
        execution = proof["workflow_execution"]
        execution["workflow_report"]["nodes"].pop(index)
        report = WorkflowReport.model_validate(execution["workflow_report"])
        execution["workflow_report_ref"] = "sha256:" + hashlib.sha256(
            to_canonical_bytes(report.model_dump(), spec=CanonSpec())
        ).hexdigest()
        with pytest.raises(ValueError, match="workflow_report_execution_mismatch"):
            owner.comparison_payload(changed)
    for proof_index, proof in enumerate(original["proofs"]):
        for readback_index, readback in enumerate(proof["surface_readbacks"]):
            paths = [("decision",)] if "decision" in readback else []
            paths.extend(("decisions", index, "decision") for index in range(len(readback.get("decisions", []))))
            for path in paths:
                changed = deepcopy(original)
                decision = changed["proofs"][proof_index]["surface_readbacks"][readback_index]
                for key in path:
                    decision = decision[key]
                decision["blocking"] = False
                decision["visible_downgrade"] = False
                assert owner.comparison_payload(changed) != expected


def test_layer3_workflow_failure_authority_history_partition_is_exact(
    tmp_path: Path,
) -> None:
    owner = check_layer3_workflow_failure_authority
    registry = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    current = next(row for row in registry["family"] if row["id"] == owner.FAMILY_ID)
    history = next(row for row in registry["family"] if row["id"] == owner.HISTORY_FAMILY_ID)
    assert current["outputs"] == [owner.PROOF_PATH]
    assert history["outputs"] == [owner.HISTORICAL_PROOF_PATH]
    assert history["source_integrity_sha256"] == {
        owner.HISTORICAL_PROOF_PATH: "sha256:" + owner.HISTORICAL_PROOF_SHA256
    }
    target = tmp_path / "architecture/generated_artifacts.toml"
    target.parent.mkdir(parents=True)
    text = (REPO_ROOT / "architecture/generated_artifacts.toml").read_text()
    target.write_text(text.replace(owner.HISTORICAL_PROOF_SHA256, "0" * 64))
    issues: list[dict[str, str]] = []
    owner._validate_generated_artifacts_registration(tmp_path, issues)
    assert {row["code"] for row in issues} == {
        "workflow_failure_authority_history_partition_invalid"
    }


@pytest.mark.parametrize("ref_field", ["request_artifact_ref", "progress_artifact_ref"])
def test_layer3_workflow_failure_authority_refuses_unbound_recorded_ref(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
    ref_field: str,
) -> None:
    owner = check_layer3_workflow_failure_authority
    changed = deepcopy(workflow_failure_authority_live_payloads[owner.PROOF_PATH])
    for proof in changed["proofs"]:
        original_ref = proof[ref_field]
        proof[ref_field] = "sha256:" + "0" * 64
        if ref_field == "progress_artifact_ref":
            for readback in proof["surface_readbacks"]:
                for key in ("read_method", "response_artifact_ref_or_route"):
                    if key in readback:
                        readback[key] = readback[key].replace(original_ref, proof[ref_field])
    with pytest.raises(ValueError, match=r"workflow_.*content_mismatch"):
        owner.comparison_payload(changed)


def test_layer3_workflow_failure_authority_refuses_absent_recorded_fields(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
) -> None:
    owner = check_layer3_workflow_failure_authority
    payload = workflow_failure_authority_live_payloads[owner.PROOF_PATH]
    candidate = next(row for row in payload["proofs"] if row["workflow_execution"] is not None)
    execution = deepcopy(candidate["workflow_execution"])
    assert execution["workflow_report"]["nodes"][0]["error"] is None
    del execution["workflow_report"]["nodes"][0]["error"]
    with pytest.raises(ValueError, match=r"workflow_.*shape"):
        owner._validated_execution(execution, run_id=candidate["run_id"])


def test_layer3_workflow_failure_authority_refuses_unrelated_http_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        TestClient,
        "request",
        lambda *args, **kwargs: httpx.Response(409, json={"code": "unrelated_conflict"}),
    )
    with pytest.raises(ValueError, match="workflow_http_authority_response_invalid"):
        check_layer3_workflow_failure_authority._run_durable_authority_surface_proof(
            "legacy_shadow_candidate"
        )


def _rebind_recorded_f1_progress(proof: dict[str, object]) -> None:
    import hashlib

    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    old_ref = proof["progress_artifact_ref"]
    raw = to_canonical_bytes(
        from_canonical_bytes(json.dumps(proof["progress_payload"]).encode()),
        spec=CanonSpec(forbid_floats=False),
    )
    proof["progress_artifact_ref"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    for readback in proof["surface_readbacks"]:
        for key in ("read_method", "response_artifact_ref_or_route"):
            if key in readback:
                readback[key] = readback[key].replace(old_ref, proof["progress_artifact_ref"])


@pytest.mark.parametrize(
    ("record_field", "decisive_field", "replacement"),
    [
        ("failure", "message", "forged failure content"),
        ("authority_boundary", "known_limits", ["forged limit"]),
        ("authority_surface_packet", "authority_result", "grounded_admissible"),
        ("production_loop_run_proof", "artifacts_index_refs", []),
    ],
)
def test_layer3_workflow_failure_authority_refuses_detached_progress_record(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
    record_field: str,
    decisive_field: str,
    replacement: object,
) -> None:
    owner = check_layer3_workflow_failure_authority
    payload = deepcopy(workflow_failure_authority_live_payloads[owner.PROOF_PATH])
    proof = next(row for row in payload["proofs"] if row["scenario"] == "workflow_failure")
    # Preserve every inner reference and marker; only the enclosing actual bytes
    # and routes are readdressed, so the existing outer custody check still passes.
    proof["progress_payload"][record_field][decisive_field] = replacement
    _rebind_recorded_f1_progress(proof)
    with pytest.raises(ValueError, match=r"workflow_.*content_mismatch"):
        owner.comparison_payload(payload)


def test_layer3_workflow_failure_authority_refuses_unclaimed_progress_output(
    workflow_failure_authority_live_payloads: dict[str, dict[str, object]],
) -> None:
    import hashlib

    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    owner = check_layer3_workflow_failure_authority
    payload = deepcopy(workflow_failure_authority_live_payloads[owner.PROOF_PATH])
    proof = next(row for row in payload["proofs"] if row["scenario"] == "workflow_failure")
    progress = proof["progress_payload"]
    loop = progress["production_loop_run_proof"]
    loop["output_cas_refs"].append("sha256:" + "0" * 64)
    old_ref = progress["production_loop_run_proof_ref"]
    raw = to_canonical_bytes(
        from_canonical_bytes(json.dumps(loop).encode()), spec=CanonSpec(forbid_floats=False)
    )
    new_ref = "sha256:" + hashlib.sha256(raw).hexdigest()
    for target in (progress, progress["artifacts_index"], progress["quality_scorecard"]["evidence_refs"]):
        assert target["production_loop_run_proof_ref"] == old_ref
        target["production_loop_run_proof_ref"] = new_ref
    _rebind_recorded_f1_progress(proof)
    with pytest.raises(ValueError, match="workflow_progress_output_population_mismatch"):
        owner.comparison_payload(payload)


def test_layer3_gy_lex_bounds_strangle_receipt_is_committed_and_fenced() -> None:
    receipt = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_phase2_lex_bounds_strangle_receipt.json"
        ).read_text(encoding="utf-8")
    )["strangle_receipt"]

    assert receipt["pattern_id"] == "P28"
    assert receipt["predecessor_ref"] == "scientist.policy_design.search._derive_bounds"
    assert receipt["replacement_ref"] == "scientist.policy_design.search.derive_phase2_parameter_bounds"
    assert receipt["default_flipped"] is True
    assert receipt["src_false_assignments"] == []
    assert receipt["fence_status"] == "fenced_compatibility_only"
    assert receipt["deletion_status"] == "pending_compatibility_tests_only"
    assert receipt["compatibility_allowlist"] == [
        "tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py"
    ]
    assert receipt["unexpected_compatibility_assignments"] == []
    assert all(
        item.split(":", maxsplit=1)[0] in receipt["compatibility_allowlist"]
        for item in receipt["compatibility_test_assignments"]
    )


def test_layer3_gy_legacy_inferred_bounds_are_fenced_out_of_src() -> None:
    offenders: list[str] = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"^\s*require_explicit_parameter_bounds\s*=\s*False\b", source, re.M):
            offenders.append(str(path.relative_to(REPO_ROOT)))
        if re.search(
            r"^\s*allow_legacy_shadow_inferred_bounds\s*=\s*True\b",
            source,
            re.M,
        ):
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


@pytest.fixture(scope="module")
def gy_l_complete_live_population():
    """Execute the actual canonical producer once for this bounded test wave."""
    from contextlib import ExitStack
    from copy import deepcopy
    from unittest.mock import patch

    owner = check_layer3_gy_loop_artifacts
    actual_run = owner._run_durable_workspace_loop_observation
    actual_verify = getattr(owner, "_verify_live_loop_observation", None)
    observations = []
    byte_comparison_controls = []

    def capture(**kwargs):
        observed = actual_run(**kwargs)
        observations.append(observed)
        return observed

    def verify_with_actual_cas_control(observation, **kwargs):
        # The actual durable store and HTTP view are changed together, while
        # the authentic immutable CAS contract and all proof markers remain.
        # Only the readback-to-payload comparison can distinguish this input.
        service = kwargs["service"]
        job_id = observation["proof"]["job_id"]
        job = service._control_store.get_job(job_id)
        original_progress = deepcopy(job.progress)
        changed = deepcopy(observation)
        changed["search_exit_contract"]["terminal_state"]["reason"] = "changed_cas_payload_control"
        changed_progress = deepcopy(original_progress)
        changed_progress["search_exit_contract"] = changed["search_exit_contract"]
        service._control_store.upsert_progress(job_id=job_id, progress=changed_progress)
        try:
            with pytest.raises(ValueError, match="observation_cas_payload_drift"):
                actual_verify(changed, **kwargs)
            byte_comparison_controls.append(kwargs["request"].identity())
        finally:
            service._control_store.upsert_progress(job_id=job_id, progress=original_progress)
        verified = actual_verify(observation, **kwargs)
        if "exit_capture" in kwargs:
            # Test-only access to the actual invocation's private typed witness;
            # this attribute is outside the outward JSON observation.
            verified._gy_l_exit_capture = kwargs["exit_capture"]
        return verified

    with ExitStack() as stack:
        stack.enter_context(patch.object(owner, "_run_durable_workspace_loop_observation", capture))
        if callable(actual_verify):
            stack.enter_context(
                patch.object(owner, "_verify_live_loop_observation", verify_with_actual_cas_control)
            )
        family = owner.build_live_loop_artifacts(REPO_ROOT)
    return family, observations, byte_comparison_controls


def _gy_l_pre_gx_issues(payloads):
    """Exercise the existing old consumer before the new companion is installed."""
    owner = check_layer3_gy_loop_artifacts
    issues = []
    validator = getattr(owner, "validate_pre_gx_output_family", None)
    if callable(validator):
        validator(payloads, issues)
    else:
        # This is a red-first harness branch, not a production bypass. It calls
        # the existing pre-GX member checks and exposes their missing full basis.
        for index, proof in enumerate(payloads[owner.PROOFS_PATH]["proofs"]):
            owner._validate_production_loop_proof(index, proof, issues)
        owner._validate_graded_outcome_report(payloads[owner.GRADED_OUTCOME_PATH], issues)
        owner.validate_outcome_run(
            payloads[owner.OUTCOME_RUN_PATH], payloads[owner.OUTCOME_REPLAY_PATH], issues
        )
    return issues


def test_gy_l_complete_canonical_population_is_store_verified(gy_l_complete_live_population):
    import ast
    import hashlib
    import inspect

    owner = check_layer3_gy_loop_artifacts
    family, observations, byte_comparison_controls = gy_l_complete_live_population
    assert callable(getattr(owner, "validate_pre_gx_output_family", None))
    requests = owner.canonical_loop_requests()
    # Independent declarations are reconstructed from the entire canonical
    # declaration function, not a sampled request or a separate fixture list.
    source = ast.parse(inspect.getsource(owner.canonical_loop_requests))
    declared = []
    for node in ast.walk(source):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "CanonicalLoopRequest":
                declared.append(
                    {keyword.arg: ast.literal_eval(keyword.value) for keyword in node.keywords}
                )
    identities = [request.identity() for request in requests]
    independently_derived = [
        "sha256:"
        + hashlib.sha256(
            (
                json.dumps(row, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
            ).encode()
        ).hexdigest()
        for row in declared
    ]
    assert identities == independently_derived
    assert len(identities) == len(set(identities))
    assert len(observations) == len(requests)
    assert [row._checked_snapshot()[0].identity() for row in observations] == identities
    assert byte_comparison_controls == identities
    assert set(family) == set(owner.declared_outputs())
    assert len(family) == len(owner.declared_outputs())
    assert _gy_l_pre_gx_issues(family) == []
    report = family[owner.GRADED_OUTCOME_PATH]
    report_members = report["graded_outcomes"] + report["honest_non_value_outcomes"]
    expected_production_jobs = {
        observation["proof"]["job_id"]
        for request, observation in zip(requests, observations, strict=True)
        if request.catalog_mode == "production"
    }
    assert {row["job_id"] for row in report_members} == expected_production_jobs
    assert len(report_members) == len(expected_production_jobs)


def test_gy_l_pre_gx_refuses_duplicate_real_proof(gy_l_complete_live_population):
    from copy import deepcopy

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    original = deepcopy(family[owner.PROOFS_PATH])
    try:
        # Same authentic proof, byte hashes and provenance markers: only the
        # full population property is removed.
        family[owner.PROOFS_PATH]["proofs"].append(deepcopy(original["proofs"][0]))
        assert any(
            issue["code"] == "layer3_gy_pre_gx_family_custody_failed"
            for issue in _gy_l_pre_gx_issues(family)
        )
    finally:
        family[owner.PROOFS_PATH] = original


def test_gy_l_pre_gx_refuses_every_removed_or_changed_family_member(gy_l_complete_live_population):
    from copy import deepcopy

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    assert set(family) == set(owner.declared_outputs())
    for path in owner.declared_outputs():
        original = deepcopy(family[path])
        for variant in (None, {}, {**original, "owner": "unchanged_markers_changed_member"}):
            try:
                family[path] = variant
                issues = _gy_l_pre_gx_issues(family)
                assert any(
                    issue["code"] == "layer3_gy_pre_gx_family_custody_failed" for issue in issues
                ), (path, variant, issues)
            finally:
                family[path] = deepcopy(original)
        try:
            del family[path]
            assert any(
                issue["code"] == "layer3_gy_pre_gx_family_custody_failed"
                for issue in _gy_l_pre_gx_issues(family)
            ), path
        finally:
            family[path] = original


def test_gy_l_pre_gx_refuses_removed_real_report_member(gy_l_complete_live_population):
    from copy import deepcopy

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    original = deepcopy(family[owner.GRADED_OUTCOME_PATH])
    for field in ("graded_outcomes", "honest_non_value_outcomes"):
        for index in range(len(original[field])):
            try:
                del family[owner.GRADED_OUTCOME_PATH][field][index]
                assert any(
                    issue["code"] == "layer3_gy_pre_gx_family_custody_failed"
                    for issue in _gy_l_pre_gx_issues(family)
                ), (field, index)
            finally:
                family[owner.GRADED_OUTCOME_PATH] = deepcopy(original)


def test_gy_l_deserialization_and_removed_verification_cannot_mint_admission(
    gy_l_complete_live_population,
):
    owner = check_layer3_gy_loop_artifacts
    family, observations, _ = gy_l_complete_live_population
    clone = json.loads(json.dumps(family))
    assert any(
        issue["code"] == "layer3_gy_pre_gx_family_custody_failed"
        for issue in _gy_l_pre_gx_issues(clone)
    )
    for index, observed in enumerate(observations):
        changed = list(observations)
        changed[index] = json.loads(json.dumps(observed))
        with pytest.raises(ValueError, match="live_loop_observation_not_store_verified"):
            owner._assemble_live_loop_family(changed)
        missing = [value for position, value in enumerate(observations) if position != index]
        with pytest.raises(ValueError, match="live_loop_population_identity_set_drift"):
            owner._assemble_live_loop_family(missing)
        with pytest.raises(ValueError, match="live_loop_population_duplicate_identity"):
            owner._assemble_live_loop_family([*observations, observed])
    with pytest.raises(ValueError, match="live_loop_population_identity_set_drift"):
        owner._assemble_live_loop_family([])


def test_gy_l_canonical_serializer_retains_actual_unicode_bytes():
    owner = check_layer3_gy_loop_artifacts
    payload = {"scope": "Україна", "missing_is_not_null": None, "empty": []}
    expected = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert owner.serialize_loop_artifact(payload) == expected
    assert json.loads(expected) == payload
    with pytest.raises(ValueError):
        owner.serialize_loop_artifact({"unreadable": float("nan")})


def test_gy_l_accepted_input_uses_only_the_frozen_family(gy_l_complete_live_population):
    from copy import deepcopy
    from unittest.mock import patch

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    original = deepcopy(family[owner.PROOFS_PATH])
    actual_check = owner._VerifiedLoopFamily._checked_snapshot

    def mutate_after_check(self):
        frozen = actual_check(self)
        self[owner.PROOFS_PATH]["owner"] = "changed_after_admission"
        return frozen

    try:
        with patch.object(owner._VerifiedLoopFamily, "_checked_snapshot", mutate_after_check):
            accepted = owner.freeze_pre_gx_output_family(family)
        assert accepted[owner.PROOFS_PATH] == original
        assert family[owner.PROOFS_PATH] != original
    finally:
        family[owner.PROOFS_PATH] = original


def _gy_l_recorded_terminal_pair(gy_l_complete_live_population):
    """Use matching current-epoch bytes from the actual emitted family."""
    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    return (
        json.loads(owner.serialize_loop_artifact(family[owner.OUTCOME_RUN_PATH])),
        json.loads(owner.serialize_loop_artifact(family[owner.OUTCOME_REPLAY_PATH])),
    )


@pytest.mark.parametrize("status", ["fail", "expected_red", "not_measured", None, "absent"])
def test_gy_l_current_admission_requires_actual_gx_pass(status, gy_l_complete_live_population):
    owner = check_layer3_gy_loop_artifacts
    outcome, replay = _gy_l_recorded_terminal_pair(gy_l_complete_live_population)
    if status == "absent":
        outcome.pop("gx_validator_status", None)
    else:
        outcome["gx_validator_status"] = status
    issues = []
    owner.validate_outcome_run(outcome, replay, issues)
    assert any(item["code"] == "layer3_gy_outcome_gx_not_passed" for item in issues), issues


def test_gy_l_asserted_pass_without_current_execution_is_refused(gy_l_complete_live_population):
    owner = check_layer3_gy_loop_artifacts
    outcome, replay = _gy_l_recorded_terminal_pair(gy_l_complete_live_population)
    outcome["gx_validator_status"] = "pass"
    # A valid-looking pass marker cannot certify its own execution.
    outcome["gx_validation"] = {
        "schema_version": "policyos.layer3.gy.post_output_gx_verification.v1",
        "proof_source": "complete_gx_owner_on_fresh_output_family",
        "status": "pass",
        "finding_identities": [],
    }
    issues = []
    owner.validate_outcome_run(outcome, replay, issues)
    assert any(
        item["code"] == "layer3_gy_outcome_gx_execution_custody_failed" for item in issues
    ), issues


def test_gy_l_actual_post_gx_admission_binds_the_entire_emitted_family(
    gy_l_complete_live_population,
):
    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    outcome = family[owner.OUTCOME_RUN_PATH]
    basis = owner.freeze_pre_gx_output_family(family)
    verification = outcome["gx_validation"]
    assert verification is not None
    assert set(verification["input_artifact_hashes"]) == set(owner.declared_outputs())
    import hashlib

    assert verification["input_artifact_hashes"] == {
        path: "sha256:" + hashlib.sha256(owner.serialize_loop_artifact(value)).hexdigest()
        for path, value in sorted(basis.items())
    }
    assert outcome["gx_validator_status"] == verification["status"]
    issues = []
    owner.validate_outcome_run(outcome, family[owner.OUTCOME_REPLAY_PATH], issues)
    assert not any(row["code"] == "layer3_gy_outcome_gx_execution_custody_failed" for row in issues)
    if verification["status"] == "pass":
        assert verification["finding_identities"] == []
        assert issues == []
    else:
        # Engineering custody may work while L's actual GX-pass conjunct remains unmet.
        assert verification["status"] in {"expected_red", "fail"}
        assert any(row["code"] == "layer3_gy_outcome_gx_not_passed" for row in issues)


def test_gy_l_serialized_pass_and_changed_final_family_cannot_reuse_admission(
    gy_l_complete_live_population,
):
    from copy import deepcopy

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    pristine = deepcopy(dict(family))
    cloned = json.loads(owner.serialize_loop_artifact(family))
    cloned[owner.OUTCOME_RUN_PATH]["gx_validator_status"] = "pass"
    issues = []
    owner.validate_outcome_run(
        cloned[owner.OUTCOME_RUN_PATH], cloned[owner.OUTCOME_REPLAY_PATH], issues
    )
    assert any(row["code"] == "layer3_gy_outcome_gx_execution_custody_failed" for row in issues)
    for path in owner.declared_outputs():
        try:
            family[path]["changed_after_gx"] = True
            with pytest.raises(ValueError, match="post_gx_final_family_changed_after_verification"):
                owner._freeze_final_loop_family(family)
        finally:
            # Restore the same admitted outcome object and its exact full bytes.
            family[path].clear()
            family[path].update(deepcopy(pristine[path]))
    assert owner._freeze_final_loop_family(family) == pristine


def test_gy_l_current_output_drift_identity_sets_are_independent(gy_l_complete_live_population):
    from copy import deepcopy
    from itertools import combinations

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    fresh = owner._freeze_final_loop_family(family)
    declared = owner.declared_outputs()
    assert set(fresh) == set(declared)
    # Enumerate every pair of current family members; a new earlier drift must
    # never erase an already observed later finding.
    for first, second in combinations(declared, 2):
        single = deepcopy(fresh)
        single[second]["independent_drift"] = True
        baseline = []
        owner._compare_current_loop_outputs(single, fresh, baseline)
        combined = deepcopy(single)
        combined[first]["independent_drift"] = True
        augmented = []
        owner._compare_current_loop_outputs(combined, fresh, augmented)

        def identity(rows):
            return {json.dumps(row, sort_keys=True) for row in rows}

        assert identity(baseline) < identity(augmented)
        assert {row["path"] for row in augmented} == {first, second}
    for path in declared:
        for variant in (None, {}, [], False):
            changed = deepcopy(fresh)
            changed[path] = variant
            issues = []
            owner._compare_current_loop_outputs(changed, fresh, issues)
            assert any(row["path"] == path for row in issues), (path, variant)
        changed = deepcopy(fresh)
        del changed[path]
        issues = []
        owner._compare_current_loop_outputs(changed, fresh, issues)
        assert any(row["path"] == path for row in issues)


def test_gy_l_full_gx_notices_unproven_positive_only_in_new_output(gy_l_complete_live_population):
    from unittest.mock import patch

    owner = check_layer3_gy_loop_artifacts
    family, observations, _ = gy_l_complete_live_population
    baseline = set(family[owner.OUTCOME_RUN_PATH]["gx_validation"]["finding_identities"])
    actual_projection = owner._build_outcome_run

    def changed_projection(observation):
        result = actual_projection(observation)
        result["post_gx_only_control"] = {
            "status": "pass",
            "producer_ref": "controlled_missing_reducer",
        }
        return result

    with patch.object(owner, "_build_outcome_run", changed_projection):
        changed = owner._assemble_live_loop_family(observations)
    execution = owner._run_full_gx_on_new_artifacts(REPO_ROOT, changed)
    result = execution._checked_snapshot(changed)
    # Retain the complete changed report before any assertion can truncate it.
    checked = owner._attach_post_gx_result(changed, execution)
    assert result["verification"] is not None, result
    identities = set(result["verification"]["finding_identities"])
    added = [json.loads(value) for value in sorted(identities - baseline)]
    lost = [json.loads(value) for value in sorted(baseline - identities)]
    print(
        json.dumps(
            {"baseline_identity_count": len(baseline), "lost": lost, "added": added},
            sort_keys=True,
        )
    )
    # GX emits both leaf findings and reducer summaries. One new positive
    # replaces summary payloads by incrementing their record counts; that is
    # not a disappeared leaf. Retain and reconcile those full deltas explicitly.
    aggregate_fields = {
        "layer3_gx_reducer_provenance_missing": "missing_record_count",
        "layer3_gx_reducer_producer_root_chain_invalid": "invalid_record_count",
    }
    replacements = []
    for previous in lost:
        count_field = aggregate_fields.get(previous["code"])
        assert count_field is not None and type(previous.get(count_field)) is int, lost
        remainder = {key: value for key, value in previous.items() if key != count_field}
        matches = [
            row for row in added
            if {key: value for key, value in row.items() if key != count_field} == remainder
        ]
        assert len(matches) == 1, (previous, matches)
        current = matches[0]
        assert type(current[count_field]) is int
        assert current[count_field] == previous[count_field] + 1
        replacements.append((previous, current))
    assert len(replacements) == len(aggregate_fields)
    assert {row[0]["code"] for row in replacements} == set(aggregate_fields)
    # Compare complete individual issue objects, not just a total or status.
    retained = baseline - {json.dumps(row[0], sort_keys=True, separators=(",", ":"))
                           for row in replacements}
    assert retained <= identities
    control_path = owner.OUTCOME_RUN_PATH + "$/post_gx_only_control"
    for code in ("layer3_gx_reducer_provenance_missing", "layer3_gx_producer_root_invalid"):
        leaves = [row for row in added if row["code"] == code and row["path"] == control_path]
        assert len(leaves) == 1, (code, leaves)
        if code == "layer3_gx_reducer_provenance_missing":
            assert leaves[0]["field"] == "status" and leaves[0]["value"] == "pass"
    assert any(
        row["code"] == "layer3_gx_recompute_provenance_missing"
        and row["path"] == control_path
        for row in added
    ), added
    issues = []
    owner.validate_outcome_run(checked[owner.OUTCOME_RUN_PATH], checked[owner.OUTCOME_REPLAY_PATH], issues)
    assert any(row["code"] == "layer3_gy_outcome_gx_not_passed" for row in issues)


def test_gy_l_removed_post_output_execution_keeps_markers_but_turns_gate_red():
    from unittest.mock import patch

    owner = check_layer3_gy_loop_artifacts
    claimed = {
        "verification": {
            "schema_version": "policyos.layer3.gy.post_output_gx_verification.v1",
            "proof_source": "complete_gx_owner_on_fresh_output_family",
            "status": "pass",
            "finding_identities": [],
        }
    }
    # Remove the actual verifier call only. The canonical request population,
    # durable owner and all claimed pass/provenance fields still execute/remain.
    with patch.object(owner, "_run_full_gx_on_new_artifacts", return_value=claimed):
        report = owner.validate(REPO_ROOT)
    assert report["status"] == "fail"
    assert any(
        row["code"] == "layer3_gy_live_recomputation_failed"
        and "post_gx_result_not_actual_owner_execution" in row["reason"]
        for row in report["issues"]
    ), report


def test_gy_l_actual_current_reader_does_not_erase_an_existing_drift(gy_l_complete_live_population):
    from copy import deepcopy
    from unittest.mock import patch

    owner = check_layer3_gy_loop_artifacts
    family, _, _ = gy_l_complete_live_population
    original_reader = Path.read_text
    # This uses the complete real producer result once; only the actual current
    # artifact read seam varies. Lifecycle and every ordinary owner check remain.
    expected = json.loads(json.dumps(family))
    late = deepcopy(expected)
    late[owner.OUTCOME_REPLAY_PATH]["independent_reader_control"] = True
    both = deepcopy(late)
    both[owner.PROOFS_PATH]["independent_reader_control"] = True

    def full_check(payloads):
        def read(path, *args, **kwargs):
            if path.is_relative_to(REPO_ROOT):
                relative = path.relative_to(REPO_ROOT).as_posix()
                if relative in payloads:
                    return json.dumps(payloads[relative], sort_keys=True, indent=2) + "\n"
            return original_reader(path, *args, **kwargs)

        with (
            patch.object(owner, "build_live_loop_artifacts", return_value=family),
            patch.object(Path, "read_text", read),
        ):
            return owner.validate(REPO_ROOT)

    baseline = full_check(late)
    changed = full_check(both)
    before = {json.dumps(row, sort_keys=True) for row in baseline["issues"]}
    after = {json.dumps(row, sort_keys=True) for row in changed["issues"]}
    assert {
        "code": "layer3_gy_outcome_replay_drift",
        "path": owner.OUTCOME_REPLAY_PATH,
    } in baseline["issues"]
    assert before <= after, {"lost": sorted(before - after), "added": sorted(after - before)}
    assert {"code": "layer3_gy_production_proof_drift", "path": owner.PROOFS_PATH} in changed[
        "issues"
    ]


@pytest.mark.parametrize("relative_path", ["other-owner.json", "nested/new-input.json"])
def test_gy_l_actual_read_guard_rejects_invalid_json_outside_scan_list(tmp_path, relative_path):
    from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"schema_version":"preserved-owner-marker",')
    guard = owner._GXReadOnlyPythonGuard(tmp_path)
    guard.recording = True
    with pytest.raises(ValueError, match="gx_actual_json_read_refused"):
        guard("open", (str(path), "r", 0))


@pytest.mark.parametrize("body", [b"{", b"null", b"[]", b"false"])
def test_gy_l_actual_mapping_reader_refuses_present_unusable_basis(tmp_path, body):
    from tools.quality.validation import check_layer3_gy_loop_artifacts as owner
    from tools.quality.validation import check_policy_design_case_layer3_gx_hardening as gx

    path = tmp_path / "actual-mapping-reader.json"
    path.write_bytes(body)
    guard_factory = getattr(owner, "_GXReadOnlyPythonGuard", None)
    guard = guard_factory(tmp_path) if guard_factory else None
    # The old instrument has no wrapper: call the real existing reader so its
    # authored empty/default result is the substantive red, not a missing API.
    boundary = getattr(owner, "_gx_json_read_boundary", None)
    scope = boundary(gx, guard) if boundary and guard is not None else contextlib.nullcontext()
    with scope, pytest.raises(ValueError, match="gx_actual_json_read_refused"):
        gx._read_json(path, default={})


def test_gy_l_actual_read_states_distinguish_absence_and_track_complete_changes(tmp_path):
    from tools.quality.validation import check_layer3_gy_loop_artifacts as owner
    from tools.quality.validation import check_policy_design_case_layer3_gx_hardening as gx

    guard = owner._GXReadOnlyPythonGuard(tmp_path)
    present = tmp_path / "mapping.json"
    absent = tmp_path / "absent.json"
    present.write_text('{"untouched":null}', encoding="utf-8")
    with owner._gx_json_read_boundary(gx, guard):
        assert gx._read_json(present, default={}) == {"untouched": None}
        assert gx._read_json(absent, default={}) == {}
    guard.recheck_json_reads()
    assert guard.json_reads[str(absent.absolute())] == {
        "state": "absent",
        "sha256": None,
        "json_type": None,
    }
    assert guard.json_reads[str(present.absolute())]["json_type"] == "object"
    absent.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="read_state_changed"):
        guard.recheck_json_reads()


def test_gy_l_full_gx_refuses_invalid_actual_mapping_input(gy_l_complete_live_population):
    from unittest.mock import patch

    from tools.quality.validation import check_layer3_gy_loop_artifacts as owner
    from tools.quality.validation import check_policy_design_case_layer3_gx_hardening as gx

    family, _, _ = gy_l_complete_live_population
    original = owner._gx_make_overlay

    def invalid_actual_read(root, view, inputs, native):
        original(root, view, inputs, native)
        path = view / gx.BASELINE_NOTE_PATH
        # Detach only our view pointer; never write through it into the source.
        assert path.is_symlink()
        path.unlink()
        path.write_bytes(b"{")

    with patch.object(owner, "_gx_make_overlay", side_effect=invalid_actual_read):
        execution = owner._run_full_gx_on_new_artifacts(REPO_ROOT, family)
    result = execution._checked_snapshot(family)
    assert result["verification"] is None, result
    assert result["child_returncode"] != 0
    assert "gx_actual_json_read_refused" in result["child_stdout"], result
    print(json.dumps(result, sort_keys=True))


def test_gy_l_current_writer_checks_immutable_history_before_live_production(monkeypatch):
    owner = check_layer3_gy_loop_artifacts
    historical = getattr(owner, "HISTORICAL_OUTCOME_RUN_PATH", owner.OUTCOME_RUN_PATH)
    raw_read = Path.read_bytes

    def changed_history(path):
        raw = raw_read(path)
        return raw + b" " if path.resolve() == (REPO_ROOT / historical).resolve() else raw

    def unexpected_producer(*args, **kwargs):
        raise AssertionError("current writer reached producer with changed immutable history")

    monkeypatch.setattr(Path, "read_bytes", changed_history)
    monkeypatch.setattr(owner, "build_live_loop_artifacts", unexpected_producer)
    report = owner.validate(REPO_ROOT, write=True)
    assert report["status"] == "fail"
    assert {"code": "layer3_gy_loop_epoch_history_changed", "path": historical} in report["issues"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_history",
        "duplicate_history",
        "null_outputs",
        "duplicate_output",
        "swapped_epochs",
        "third_owner",
        "wrong_hash",
        "wrong_lifecycle",
    ],
)
def test_gy_l_current_history_partition_refuses_each_actual_registry_mutation(mutation):
    from copy import deepcopy

    owner = check_layer3_gy_loop_artifacts
    generated = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    current = next(row for row in generated["family"] if row["id"] == owner.FAMILY_ID)
    history = next(row for row in generated["family"] if row["id"] == owner.HISTORY_FAMILY_ID)
    baseline = []
    owner._validate_loop_epoch_partition(REPO_ROOT, generated, baseline)
    assert baseline == []
    if mutation == "missing_history":
        generated["family"].remove(history)
    elif mutation == "duplicate_history":
        generated["family"].append(deepcopy(history))
    elif mutation == "null_outputs":
        history["outputs"] = None
    elif mutation == "duplicate_output":
        history["outputs"].append(owner.HISTORICAL_OUTCOME_RUN_PATH)
    elif mutation == "swapped_epochs":
        current["outputs"] = [
            owner.HISTORICAL_OUTCOME_RUN_PATH if path == owner.OUTCOME_RUN_PATH else path
            for path in current["outputs"]
        ]
        history["outputs"] = [owner.OUTCOME_RUN_PATH]
    elif mutation == "third_owner":
        generated["family"].append({"id": "third-owner", "outputs": [owner.OUTCOME_RUN_PATH]})
    elif mutation == "wrong_hash":
        history["source_integrity_sha256"][owner.HISTORICAL_OUTCOME_RUN_PATH] = "sha256:" + "0" * 64
    elif mutation == "wrong_lifecycle":
        history["lifecycle"] = "generated_committed"
    issues = []
    owner._validate_loop_epoch_partition(REPO_ROOT, generated, issues)
    assert issues, mutation


def test_gy_l_p28_restored_aliased_pre_post_gx_is_fenced(monkeypatch):
    owner = check_layer3_gy_loop_artifacts
    path = REPO_ROOT / "tools/quality/validation/check_layer3_gy_loop_artifacts.py"
    raw_read = Path.read_bytes
    source = raw_read(path)
    marker = b"    request = CanonicalLoopRequest(fixture_id=fixture_id, catalog_mode=catalog_mode)"
    assert source.count(marker) == 1
    changed = source.replace(
        marker,
        b"    from tools.quality.validation.check_policy_design_case_layer3_gx_hardening import validate_layer3_gx_hardening as restored\n"
        b"    restored(repo_root, case='ua-msme', write=False)\n" + marker,
    )
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda member: changed if member.resolve() == path.resolve() else raw_read(member),
    )
    with pytest.raises(ValueError, match="layer3_gy_pre_output_gx_reachable"):
        owner._LoopGXStrangleMeasurement(REPO_ROOT)


def test_gy_l_p28_snapshot_cannot_survive_an_added_source_caller(monkeypatch):
    owner = check_layer3_gy_loop_artifacts
    measurement = owner._LoopGXStrangleMeasurement(REPO_ROOT)
    first = measurement.checked_snapshot()
    assert first["disposition"] == "fenced_default_flipped"
    path = REPO_ROOT / "tools/quality/validation/check_layer3_gy_loop_artifacts.py"
    raw_read = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda member: raw_read(member) + b"\n# source delta\n"
        if member.resolve() == path.resolve()
        else raw_read(member),
    )
    with pytest.raises(ValueError, match="loop_gx_strangle_source_bytes_changed"):
        measurement.checked_snapshot()


def test_gy_l_typed_readback_requires_actual_contract_and_verifier_returns(
    gy_l_complete_live_population, monkeypatch,
):
    owner = check_layer3_gy_loop_artifacts
    _, observations, _ = gy_l_complete_live_population
    controls = []
    for observation in observations:
        capture = observation._gy_l_exit_capture
        raw = observation["search_exit_contract"]
        job_id = observation["proof"]["job_id"]
        capture.verify(raw, job_id)._require_contract(raw)
        with monkeypatch.context() as control:
            control.setattr(capture, "_LiveLoopExitCapture__contract", None)
            with pytest.raises(ValueError, match="actual_contract_execution_unobserved"):
                capture.verify(raw, job_id)
        controls.append({"job_id": job_id, "removed_contract_return_refused": True})
        actual = capture._LiveLoopExitCapture__contract[0]
        if owner._nonempty_ring2_models(actual):
            with monkeypatch.context() as control:
                control.setattr(capture, "_LiveLoopExitCapture__envelopes", [])
                with pytest.raises(ValueError, match="ring2_verifier_object_unobserved"):
                    capture.verify(raw, job_id)
            controls[-1]["removed_verifier_returns_refused"] = True
        capture.verify(raw, job_id)._require_contract(raw)
    assert [row["job_id"] for row in controls] == [row["proof"]["job_id"] for row in observations]
    print(json.dumps({"actual_typed_readback_controls": controls}, sort_keys=True))


def test_gy_l_typed_readback_refuses_mutated_actual_runtime_object(
    gy_l_complete_live_population,
):
    _, observations, _ = gy_l_complete_live_population
    controls = []
    for observation in observations:
        capture = observation._gy_l_exit_capture
        actual = capture._LiveLoopExitCapture__contract[0]
        original = actual.terminal_state
        try:
            object.__setattr__(
                actual, "terminal_state", original.model_copy(update={"reason": "typed_readback_control"})
            )
            with pytest.raises(ValueError, match="live_loop_verified_exit_changed"):
                observation._checked_snapshot()
            with pytest.raises(ValueError, match="actual_contract_execution_drift"):
                capture.verify(observation["search_exit_contract"], observation["proof"]["job_id"])
        finally:
            object.__setattr__(actual, "terminal_state", original)
        observation._checked_snapshot()
        controls.append(observation["proof"]["job_id"])
    print(json.dumps({"mutated_actual_contract_refused": controls}, sort_keys=True))


def test_gy_l_observed_parent_cannot_launder_unobserved_nested_ring2(
    gy_l_complete_live_population,
):
    from types import SimpleNamespace

    owner = check_layer3_gy_loop_artifacts
    _, observations, _ = gy_l_complete_live_population
    controls = []
    for observation in observations:
        capture = observation._gy_l_exit_capture
        actual, _, job_id = capture._LiveLoopExitCapture__contract
        for envelope, _ in capture._LiveLoopExitCapture__envelopes:
            if not any(item is envelope for item in actual.artifact_envelopes):
                continue
            # Walk every protected field of this real nested verifier DTO. The
            # outer object and its snapshot are coherent; the child was never
            # supplied by the actual verifier and must not gain its standing.
            for field in type(envelope.verification).ring2_fields:
                changed = envelope.model_copy(update={
                    "verification": envelope.verification.model_copy(update={
                        field: "sha256:" + "0" * 64,
                    }),
                })
                contract = actual.model_copy(update={
                    "artifact_envelopes": [
                        changed if item is envelope else item for item in actual.artifact_envelopes
                    ],
                })
                candidate = owner._LiveLoopExitCapture(capture.store)
                for original, _ in capture._LiveLoopExitCapture__envelopes:
                    candidate.observe_envelope(
                        SimpleNamespace(_artifact_store=capture.store),
                        changed if original is envelope else original,
                    )
                candidate.observe_contract(contract, job_id)
                with pytest.raises(ValueError, match="ring2_verifier_object_unobserved"):
                    candidate.verify(contract.model_dump(mode="json"), job_id)
                controls.append({"job_id": job_id, "artifact_id": envelope.ref.artifact_id,
                                 "field": field})
    assert controls, "canonical live population exposed no nested protected-field control"
    print(json.dumps({"unobserved_nested_ring2_refused": controls}, sort_keys=True))


@pytest.mark.parametrize(
    "historical_path",
    [
        "architecture/policy_design_case/layer3_gy_outcome_run.json",
        "architecture/policy_design_case/layer3_gy_outcome_run_v2.json",
        "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json",
        "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json",
    ],
)
def test_gy_j_history_guards_every_completed_predecessor_epoch(monkeypatch, historical_path):
    owner = check_layer3_gy_loop_artifacts
    generated = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())
    baseline = []
    owner._validate_loop_epoch_partition(REPO_ROOT, generated, baseline)
    assert baseline == []
    raw_read = Path.read_bytes

    def changed_bytes(path):
        raw = raw_read(path)
        return raw + b" " if path.resolve() == (REPO_ROOT / historical_path).resolve() else raw

    monkeypatch.setattr(Path, "read_bytes", changed_bytes)
    issues = []
    owner._validate_loop_epoch_partition(REPO_ROOT, generated, issues)
    assert {"code": "layer3_gy_loop_epoch_history_changed", "path": historical_path} in issues
