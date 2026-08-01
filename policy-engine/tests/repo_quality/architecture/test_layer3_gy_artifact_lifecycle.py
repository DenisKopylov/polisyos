from __future__ import annotations

import contextlib
import json
import re
import tomllib
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
        "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json",
        "architecture/policy_design_case/layer3_gy_outcome_run.json",
        "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json",
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


def test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked() -> None:
    live_payloads = check_layer3_gy_loop_artifacts.build_live_loop_artifacts(REPO_ROOT)
    outcome = live_payloads["architecture/policy_design_case/layer3_gy_outcome_run.json"]
    replay = live_payloads[
        "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
    ]["replay_proof"]
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
    assert contract["terminal_state"]["kind"] == "search_ceiling_repair_required"
    assert contract["evidence_kind"] is None
    assert contract["decision_grade"] == "unsupported"
    assert contract["evidence_ladder_rung"] == "none"
    assert contract["incompleteness_record"]["search_quality"]["known_seeds_missed"]
    assert outcome["useful_design_credit"] is False
    assert outcome["gx_case_outcome"]["outcome_kind"] == outcome["terminal_outcome"]
    assert outcome["gx_case_outcome"]["useful_design_credit"] is False
    assert outcome["gx_case_outcome"]["final_run_hash"].startswith("sha256:")
    assert replay["replay_levels"] == ["A", "B", "C"]
    assert replay["input_hashes"]
    assert replay["output_hash"] == outcome["output_hash"]


def test_layer3_gy_outcome_validator_rejects_direct_helper_and_hand_authored_proof() -> None:
    outcome = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_outcome_run.json").read_text()
    )
    replay = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
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
    outcome = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_outcome_run.json").read_text()
    )
    replay = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
        ).read_text()
    )
    outcome["search_exit_contract"]["terminal_state"]["reason"] = "corrupted"
    issues: list[dict[str, str]] = []

    check_layer3_gy_loop_artifacts.validate_outcome_run(outcome, replay, issues)

    assert {"code": "layer3_gy_outcome_replay_output_drift"} in issues


def test_layer3_gy_outcome_validator_rejects_gx_terminal_drift() -> None:
    outcome = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_outcome_run.json").read_text()
    )
    replay = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
        ).read_text()
    )
    outcome["gx_case_outcome"]["outcome_kind"] = "grounded_partial_admissible"
    issues: list[dict[str, str]] = []

    check_layer3_gy_loop_artifacts.validate_outcome_run(outcome, replay, issues)

    assert {"code": "layer3_gy_outcome_gx_terminal_drift"} in issues


def test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report() -> None:
    live_payloads = check_layer3_gy_loop_artifacts.build_live_loop_artifacts(REPO_ROOT)
    _assert_live_payloads_match_declared_outputs(
        check_layer3_gy_loop_artifacts,
        live_payloads,
    )
    committed = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json"
        ).read_text(encoding="utf-8")
    )
    live_report = live_payloads[
        "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json"
    ]

    assert committed == live_report
    assert committed["summary"]["grounded_partial_admissible_count"] == 0
    assert committed["summary"]["capped_decision_grade_count"] == committed["summary"][
        "grounded_partial_admissible_count"
    ]
    assert committed["summary"]["floor_relaxation_used_count"] == 0
    assert committed["summary"]["useful_design_rate"] == 0.0
    assert committed["graded_outcomes"] == []
    assert committed["honest_non_value_outcomes"][0]["terminal_state"] == (
        "search_ceiling_repair_required"
    )


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
    assert inventory["row_count"] == 406
    assert inventory["reconciliation"]["gx_positive_status_count"] == 0
    for relative_path, live_payload in live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert committed == live_payload


def test_layer3_workflow_failure_authority_validator_recomputes_proofs() -> None:
    live_payloads = check_layer3_workflow_failure_authority.build_live_proof_payloads(
        REPO_ROOT
    )
    _assert_live_payloads_match_declared_outputs(
        check_layer3_workflow_failure_authority,
        live_payloads,
    )
    proof = live_payloads[
        "architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs.json"
    ]
    scenarios = {item["scenario"]: item for item in proof["proofs"]}
    assert scenarios["workflow_failure"]["terminal_job_state"] == "failed"
    assert scenarios["legacy_shadow_candidate"]["authority_result"] == "candidate_only"
    for scenario in scenarios.values():
        assert set(scenario["surface_reads_checked"]) >= {
            "run",
            "artifact",
            "lineage",
            "export",
            "dashboard",
            "public_packet",
        }
    for relative_path, live_payload in live_payloads.items():
        committed = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert committed == live_payload


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
