from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality import assurance_case as ac
from polisyos.runtime.quality.assurance_case import PolicyDesignCaseAuthorityError
from polisyos.runtime.quality.policy_design_jurisdiction_spine import (
    build_policy_design_jurisdiction_spine_boundary_record,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_quality_evidence,
    scorecard_for,
    sha,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_jurisdiction_spine_projects_lex_ir_and_cross_graph_surfaces() -> None:
    assert hasattr(ac, "build_policy_design_jurisdiction_spine")

    spine = ac.build_policy_design_jurisdiction_spine(
        spine_id="jurisdiction-spine-R_multi",
        jurisdiction_spine_ref=sha("6"),
        run_id="R_multi",
        job_id="job-multi",
        tenant_id="tenant-1",
        policy_intent_ref=sha("0"),
        lex_normative_report=_multi_jurisdiction_lex_report(),
        normative_arbitration_result={
            "provenance": {"legal_report_ref": sha("a")},
            "rights_audit": [
                {
                    "right_id": "right.equal_access",
                    "status": "satisfied",
                    "binding_ref": "norm.eu.state_aid",
                    "notes": ["EU state-aid rule checked before national rollout."],
                }
            ],
            "hard_constraint_audit": [
                {
                    "constraint_id": "constraint.local_budget",
                    "status": "satisfied",
                    "notes": ["Local implementation budget authority is bounded."],
                }
            ],
        },
        cross_graph_conflicts=[
            {
                "conflict_id": "conflict.local.delivery.overlap",
                "dimension": "legal_vs_dataset",
                "severity": "medium",
                "description": "Local delivery area differs from dataset region.",
                "blocking": False,
                "resolved_status": "resolved",
            }
        ],
        runtime_authority=_runtime_authority(),
    )

    assert spine["schema_version"] == ac.POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION
    assert spine["authority_level_taxonomy"] == [
        "supranational",
        "national",
        "regional",
        "local",
    ]
    by_level = {row["authority_level"]: row for row in spine["jurisdictions"]}
    assert by_level["supranational"]["jurisdiction_id"] == "EU"
    assert by_level["national"]["jurisdiction_id"] == "UA"
    assert by_level["regional"]["hierarchy"]["parent_jurisdiction_ids"] == ["UA"]
    assert by_level["local"]["delegation"]["delegated_from"] == ["UA-30"]
    assert by_level["supranational"]["pre_emption"]["preempts"] == ["UA"]
    assert spine["projection_sources"] == {
        "lex": ["policyos.lex.normative_applicability_report.v1"],
        "ir_normative_arbitration": ["ir.normative_arbitration_result"],
        "cross_graph_conflict": ["conflict.local.delivery.overlap"],
    }
    assert {surface["surface"] for surface in spine["conflict_surfaces"]} == {
        "ir.normative_arbitration",
        "scientist.cross_graph.conflict",
    }
    assert spine["status"] == "pass"
    assert spine["blockers"] == []


def test_jurisdiction_spine_unresolved_competence_blocks_serious_scorecard() -> None:
    assert hasattr(ac, "build_policy_design_jurisdiction_spine")

    lex_report = _multi_jurisdiction_lex_report()
    broken_norm = deepcopy(lex_report["applied_norms"][1])
    broken_norm.pop("competence")
    broken_norm.pop("competent_authority")
    broken_norm.pop("source_authority")
    lex_report["applied_norms"] = [broken_norm]

    spine = ac.build_policy_design_jurisdiction_spine(
        spine_id="jurisdiction-spine-R_blocked",
        jurisdiction_spine_ref=sha("7"),
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-1",
        policy_intent_ref=sha("0"),
        lex_normative_report=lex_report,
        runtime_authority=_runtime_authority(ref_char="7"),
    )
    evidence = complete_quality_evidence()
    evidence["policy_design_case"]["jurisdiction_spine"] = spine

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_jurisdiction_unresolved_competence_blocker" in blocking_codes(
        scorecard
    )


def test_jurisdiction_spine_arbitration_violation_emits_typed_blocker() -> None:
    spine = ac.build_policy_design_jurisdiction_spine(
        spine_id="jurisdiction-spine-R_arbitration_blocked",
        jurisdiction_spine_ref=sha("8"),
        run_id="R_arbitration_blocked",
        job_id="job-arbitration-blocked",
        tenant_id="tenant-1",
        policy_intent_ref=sha("0"),
        lex_normative_report=_multi_jurisdiction_lex_report(),
        normative_arbitration_result={
            "rights_audit": [
                {
                    "right_id": "right.equal_access",
                    "status": "violated",
                    "notes": ["Equal access check failed."],
                }
            ]
        },
        runtime_authority=_runtime_authority(ref_char="8"),
    )

    assert spine["status"] == "blocked"
    assert spine["unresolved_conflicts"][0]["code"] == (
        "policy_design_jurisdiction_unresolved_conflict_blocker"
    )
    assert {blocker["code"] for blocker in spine["blockers"]} == {
        "policy_design_jurisdiction_unresolved_conflict_blocker"
    }
    boundary = build_policy_design_jurisdiction_spine_boundary_record(spine)
    assert boundary["status"] == "blocked"
    assert boundary["producer_owner"] == "team-lex"
    assert boundary["reader_owner"] == "team-runtime-quality"
    assert boundary["record_family"] == "concept_and_jurisdiction_spine.v1"
    assert boundary["runtime_authority_envelope"]["provenance_kind"] == "runtime_blocker"
    assert {
        blocker["code"] for blocker in boundary["blockers"]
    } == {"policy_design_jurisdiction_unresolved_conflict_blocker"}

    hidden_blocker = deepcopy(spine)
    hidden_blocker["status"] = "pass"
    hidden_blocker["blockers"] = []
    hidden_boundary = build_policy_design_jurisdiction_spine_boundary_record(hidden_blocker)
    assert hidden_boundary["status"] == "failed"
    assert {
        issue["code"] for issue in hidden_boundary["issues"]
    } == {"policy_design_jurisdiction_spine_blocker_missing"}


def test_jurisdiction_spine_rejects_static_inventory_as_authority() -> None:
    assert hasattr(ac, "validate_policy_design_jurisdiction_spine")

    spine = _valid_spine()
    spine["runtime_authority_envelope"] = {
        **spine["runtime_authority_envelope"],
        "authority_role": "not_authoritative",
        "provenance_kind": "static_inventory",
        "cas_ref": None,
        "static_inventory_ref": "repo://architecture/name_registry.toml#jurisdiction",
    }

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_jurisdiction_spine_static_inventory_not_authority",
    ):
        ac.validate_policy_design_jurisdiction_spine(spine)


def test_jurisdiction_spine_fixtures_include_multijurisdiction_and_blocker_examples() -> None:
    fixture_dir = (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "policy_design_case"
        / "concept_jurisdiction_spine"
    )

    assert (fixture_dir / "jurisdiction_spine_multi_jurisdiction_pass.json").is_file()
    assert (
        fixture_dir / "jurisdiction_spine_unresolved_competence_rejected.json"
    ).is_file()


def test_jurisdiction_spine_json_schema_lists_phase_8_2_fields() -> None:
    schema_path = (
        REPO_ROOT
        / "schemas"
        / "runtime_quality"
        / "policy_design_jurisdiction_spine_v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema == ac.policy_design_jurisdiction_spine_json_schema()
    assert {
        "authority_level_taxonomy",
        "jurisdictions",
        "conflict_surfaces",
        "unresolved_conflicts",
        "blockers",
    } <= set(schema["required"])


def _valid_spine() -> dict[str, object]:
    return ac.build_policy_design_jurisdiction_spine(
        spine_id="jurisdiction-spine-R_valid",
        jurisdiction_spine_ref=sha("6"),
        run_id="R_valid",
        job_id="job-valid",
        tenant_id="tenant-1",
        policy_intent_ref=sha("0"),
        lex_normative_report=_multi_jurisdiction_lex_report(),
        runtime_authority=_runtime_authority(),
    )


def _multi_jurisdiction_lex_report() -> dict[str, object]:
    return {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "normative_applicability_report_ref": sha("a"),
        "target_context": {
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-17",
        },
        "applied_norms": [
            {
                "norm_id": "norm.eu.state_aid",
                "jurisdiction": "EU",
                "authority_level": "supranational",
                "source_authority": "European Commission",
                "competence": "state_aid_control",
                "competent_authority": "European Commission",
                "effective_from": "2024-01-01",
                "hierarchy_parent_jurisdiction_ids": [],
                "preempts": ["UA"],
                "preemption_rule_refs": ["norm.eu.state_aid:preemption"],
            },
            {
                "norm_id": "norm.ua.credit_eligibility",
                "jurisdiction": "UA",
                "authority_level": "national",
                "source_authority": "Verkhovna Rada",
                "competence": "national_wartime_economic_support",
                "competent_authority": "Ministry of Economy",
                "effective_from": "2024-02-01",
                "delegated_to": ["UA-30"],
            },
            {
                "norm_id": "norm.ua_30.delivery",
                "jurisdiction": "UA-30",
                "authority_level": "regional",
                "source_authority": "Kyiv Regional Military Administration",
                "competence": "regional_delivery_coordination",
                "competent_authority": "Kyiv Regional Military Administration",
                "effective_from": "2024-05-01",
                "hierarchy_parent_jurisdiction_ids": ["UA"],
                "delegated_from": ["UA"],
                "delegated_to": ["UA-30-KYIV"],
            },
            {
                "norm_id": "norm.ua_30_kyiv.office",
                "jurisdiction": "UA-30-KYIV",
                "authority_level": "local",
                "source_authority": "Kyiv City Council",
                "competence": "local_business_support_intake",
                "competent_authority": "Kyiv City Council",
                "effective_from": "2024-06-01",
                "hierarchy_parent_jurisdiction_ids": ["UA-30"],
                "delegated_from": ["UA-30"],
            },
        ],
    }


def _runtime_authority(*, ref_char: str = "6") -> dict[str, str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": sha(ref_char),
        "runtime_event_ref": sha("e"),
        "same_input_closure_ref": sha("3"),
        "effective_mode_ref": sha("4"),
        "schema_compatibility_ref": sha("5"),
    }
