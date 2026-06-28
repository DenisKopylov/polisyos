from __future__ import annotations

# ruff: noqa: S101
import copy
import importlib
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
S14_FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer2/s14"
SEALED_BATTERY_ROOT = (
    REPO_ROOT
    / "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
    "layer2-sealed-universality-battery"
)
S14_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s14_universality_assurance.v1"
S14_RULE_VERSION_REF = "policyos.layer2.s14.universality_assurance.v1"
S14_FLOOR_ID = "s14_universality"
S14_FALSE_CLEAR_FIELDS = (
    "bare_universal_claim_without_battery",
    "sealed_battery_dev_access",
    "aggregate_universal_number_laundering",
    "untested_axis_combination_in_envelope",
    "bespoke_cost_hidden_as_generality",
    "skeptic_defeater_ignored",
    "faithfulness_claim_without_s9",
    "battery_result_as_production_authority",
    "gold_label_leak_into_dev_signal",
    "freeze_hash_mismatch_accepted",
    "d4_breadth_floor_missing",
    "expert_oracle_bootstrap_missing",
    "weak_gold_floor_laundering",
    "shadow_candidate_oracle_laundering",
    "grounded_authority_refs_missing",
    "status_composition_laundering",
    "envelope_revision_freeze_laundering",
    "baseline_comparison_missing",
)
S14_SKEPTIC_DEFEATER_IDS = (
    "bespoke_disguise_defeater",
    "confident_theater_defeater",
    "failure_boundary_defeater",
    "single_axis_universality_defeater",
    "frozen_once_defeater",
    "first_call_defeater",
)
S14_SKEPTIC_ATTACKS = {
    "bespoke_disguise_defeater": "This is bespoke in disguise.",
    "confident_theater_defeater": "It is confident theater.",
    "failure_boundary_defeater": "It does not know where it fails.",
    "single_axis_universality_defeater": "It is universal only on one axis.",
    "frozen_once_defeater": "It works once, then freezes.",
    "first_call_defeater": "Why call it first?",
}
D4_TRACKS = (
    "grounding",
    "construct_demand",
    "acquisition_loop",
    "epistemic_regime",
    "coupling_modularity",
    "axis_declaration",
    "cluster_ownership",
    "scale_composition",
    "design_quality",
    "search_control",
    "delegation",
    "projection_lowering",
    "bootstrap_resource",
    "system_dynamics_backtest",
    "post_deploy_accountability",
    "prediction_backtest",
    "adversarial",
    "odd_abstention",
    "universality_battery",
)


def _s14() -> Any:
    return importlib.import_module("polisyos.runtime.quality.design_axes.universality_assurance")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((S14_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _negative_probe(false_clear_field: str) -> dict[str, Any]:
    path = S14_FIXTURE_DIR / "negative_controls" / f"{false_clear_field}_probe.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _cluster_axis_refs() -> list[str]:
    payload = tomllib.loads(
        (REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml")
        .read_text(encoding="utf-8")
    )
    return [
        f"{cluster}.{axis}"
        for cluster, axes in payload["cell"].items()
        for axis, cell in axes.items()
        if isinstance(cell, dict)
    ]


def _authority_boundary(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "authoritative_for": [
            "s14_universality_claim_gate",
            "sealed_battery_integrity",
            "per_axis_universality_scorecard",
            "mechanism_generality_assessment",
            "skeptic_defeater_evaluation",
            "d4_corpus_track_coverage",
            "expert_oracle_bootstrap",
            "universality_breadth_floor",
            "baseline_comparison",
            "grounded_authority_coverage",
            "evaluation_status_composition",
            "envelope_revision_dynamics",
            "declared_operation_envelope",
        ],
        "may_not_use_for": [
            "production_rollout_authority",
            "production_recommendation",
            "recommendation_authority",
            "publication_authority",
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "preference_learning",
            "automated_value_learning",
            "sealed_battery_training",
            "development_fixture_access",
            "aggregate_universal_score",
            "untested_axis_envelope_expansion",
            "gold_label_authority",
            "weak_gold_promotion_floor",
            "shadow_candidate_oracle",
            "baseline_free_universal_claim",
            "grounded_authority_without_a_firewalls",
        ],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": [S14_RULE_VERSION_REF],
    }
    payload.update(overrides)
    return payload


def _track_coverage_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_d4_corpus_track_coverage.json")
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-d4-corpus-track-coverage",
        "record_ref": "pdc://layer2/s14/d4-corpus-track-coverage",
        "coverage_status": fixture["coverage_status"],
        "track_rows": fixture["track_rows"],
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "4" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _oracle_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_expert_oracle_bootstrap.json")
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-expert-oracle-bootstrap",
        "record_ref": "pdc://layer2/s14/expert-oracle-bootstrap",
        "bootstrap_status": fixture["bootstrap_status"],
        "oracle_layers": fixture["oracle_layers"],
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "5" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _breadth_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_universality_breadth_floor_config.json")
    payload: dict[str, object] = {
        **fixture,
        "schema_version": S14_SCHEMA_VERSION,
        "config_id": "s14-breadth-floor",
        "config_ref": "pdc://layer2/s14/breadth-floor-config",
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "6" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _baseline_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_universality_baseline_comparison.json")
    payload: dict[str, object] = {
        **fixture,
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-baseline-comparison",
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "7" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _grounded_authority_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_grounded_authority_refs.json")
    payload: dict[str, object] = {
        **fixture,
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-grounded-authority-coverage",
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "8" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _status_composition_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_evaluation_status_composition_cases.json")
    payload: dict[str, object] = {
        **fixture,
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-status-composition",
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "a" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _envelope_dynamics_payload(**overrides: object) -> dict[str, object]:
    fixture = _fixture("s14_envelope_revision_dynamics.json")
    payload: dict[str, object] = {
        **fixture,
        "schema_version": S14_SCHEMA_VERSION,
        "record_id": "s14-envelope-revision-dynamics",
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "b" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _battery_run_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "run_id": "s14-sealed-run-001",
        "battery_id": "layer2-sealed-universality-battery",
        "battery_root": str(SEALED_BATTERY_ROOT.relative_to(REPO_ROOT)),
        "partition_path": (
            "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
            "layer2-sealed-universality-battery"
        ),
        "owner": "governance-board",
        "access_mode": "ci_gate_only",
        "run_mode": "sealed_ci",
        "explicit_access_granted": True,
        "sealed_battery_access_attempted": True,
        "sealed_battery_status": "accessed_by_sealed_runner",
        "freeze_hash": "sha256:" + "c" * 64,
        "computed_freeze_hash": "sha256:" + "c" * 64,
        "sealed_battery_integrity_status": "pass",
        "case_count": 6,
        "hard_corner_case_ids": list(_sealed_manifest()["hard_corner_case_ids"]),
        "fixture_manifest_digest": "sha256:" + "d" * 64,
        "freeze_time": "2026-06-03T00:00:00+00:00",
        "access_time": "2026-06-03T00:01:00+00:00",
        "run_time": "2026-06-03T00:02:00+00:00",
        "scoring_time": "2026-06-03T00:03:00+00:00",
        "assurance_time": "2026-06-03T00:04:00+00:00",
        "projection_time": "2026-06-03T00:05:00+00:00",
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _sealed_manifest() -> dict[str, Any]:
    return json.loads((SEALED_BATTERY_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _axis_rows() -> list[dict[str, object]]:
    rows = []
    for index, axis_ref in enumerate(_cluster_axis_refs()):
        not_tested = index in {3, 12}
        rows.append(
            {
                "axis_ref": axis_ref,
                "declared_posture": "not_tested" if not_tested else "in_envelope",
                "battery_status": "not_tested" if not_tested else "pass",
                "threshold_ref": f"repo://architecture/policy_design_case/layer2_floor_governance.toml#s14/{axis_ref}",
                "floor_passed": not not_tested,
                "hard_corner_case_refs": [
                    "sealed://s14/capacity-constrained-refugee-services"
                ],
                "mechanism_refs": [f"mechanism://s14/{axis_ref}"],
                "limitation_refs": [f"limitation://s14/{axis_ref}"] if not_tested else [],
                "failure_refs": [],
                "evidence_refs": [f"evidence://s14/{axis_ref}"],
            }
        )
    return rows


def _scorecard_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "scorecard_id": "s14-axis-scorecard",
        "scorecard_ref": "pdc://layer2/s14/axis-scorecard",
        "capability_reality_report_ref": "pdc://layer2/capability-reality/report",
        "axis_rows": _axis_rows(),
        "axis_scorecard_row_count": 27,
        "out_of_envelope_axis_refs": ["SYSTEM.dynamics_feedback"],
        "not_tested_axis_refs": ["SYSTEM.dynamics_feedback", "KNOWLEDGE.calibration"],
        "aggregate_universal_score": None,
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "e" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _mechanism_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "report_id": "s14-mechanism-generality",
        "report_ref": "pdc://layer2/s14/mechanism-generality",
        "mechanism_reuse_rate": 0.82,
        "growth_thermometer_ref": "pdc://layer2/s12/ua-msme/growth-thermometer",
        "s12_held_out_status": "pending_s14",
        "marginal_bespoke_cost_status": "pass",
        "sublinear_marginal_bespoke_cost": True,
        "reused_mechanism_refs": ["mechanism://s12/reuse/legal-access"],
        "bespoke_patch_refs": [],
        "bespoke_patch_limitations": [],
        "held_out_case_refs": ["sealed://s14/capacity-constrained-refugee-services"],
        "dev_case_refs": ["ua-msme-affordable-loans-2022"],
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "f" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _skeptic_records(**overrides: object) -> list[dict[str, object]]:
    records = []
    for defeater_id, attack in S14_SKEPTIC_ATTACKS.items():
        record = {
            "schema_version": S14_SCHEMA_VERSION,
            "defeater_id": defeater_id,
            "attack_id": attack,
            "attack_family": "architecture_skeptic_attack",
            "status": "pass",
            "projected_from_cae_defeater_ref": f"cae-defeater://s14/{defeater_id}",
            "evidence_refs": [f"evidence://s14/{defeater_id}"],
            "axis_refs": ["DESIGNER_ITSELF.evaluation_corpus"],
            "hard_corner_case_refs": ["sealed://s14/capacity-constrained-refugee-services"],
            "baseline_refs": ["benchmark://s14/bespoke-tools/mechanism-boundary-authority"],
            "envelope_revision_refs": ["pdc://layer2/s13/ua-msme/envelope-revision"],
            "grounded_authority_refs": ["pdc://layer2/s14/grounded-authority-coverage"],
            "residual_limitation_refs": [],
            "replay_digest": "sha256:" + "1" * 64,
            "rule_version_ref": S14_RULE_VERSION_REF,
        }
        record.update(overrides)
        records.append(record)
    return records


def _assurance_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "assurance_case_id": "s14-universality-assurance-case",
        "assurance_case_ref": "pdc://layer2/s14/universality-assurance-case",
        "cae_claim_ref": "cae://s14/universality-claim",
        "cae_subclaim_refs": ["cae://s14/subclaim/d4", "cae://s14/subclaim/scorecard"],
        "cae_evidence_refs": ["cae-evidence://s14/scorecard"],
        "cae_defeater_refs": [row["projected_from_cae_defeater_ref"] for row in _skeptic_records()],
        "non_overridable_blockers": [],
        "confidence_limits": {"lower_bound": 0.74, "upper_bound": 0.88},
        "d4_corpus_track_coverage_ref": "pdc://layer2/s14/d4-corpus-track-coverage",
        "expert_oracle_bootstrap_ref": "pdc://layer2/s14/expert-oracle-bootstrap",
        "breadth_floor_config_ref": "pdc://layer2/s14/breadth-floor-config",
        "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        "axis_scorecard_ref": "pdc://layer2/s14/axis-scorecard",
        "mechanism_generality_report_ref": "pdc://layer2/s14/mechanism-generality",
        "grounded_authority_coverage_ref": "pdc://layer2/s14/grounded-authority-coverage",
        "baseline_comparison_ref": "pdc://layer2/s14/baseline-comparison",
        "envelope_revision_dynamics_ref": "pdc://layer2/s14/envelope-revision-dynamics",
        "s9_projection_faithfulness_refs": ["pdc://layer2/s9/faithfulness/public-universal-claim"],
        "projection_refs": ["projection://s14/public"],
        "status_composition_ref": "pdc://layer2/s14/evaluation-status-composition",
        "skeptic_defeater_refs": [f"pdc://layer2/s14/defeater/{row['defeater_id']}" for row in _skeptic_records()],
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "2" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _gate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "gate_id": "s14-universality-claim-gate",
        "gate_ref": "pdc://layer2/s14/universality-claim-gate",
        "claim_text": "PolicyOS is universal over the declared envelope.",
        "requested_scope_refs": ["scope://s14/declared-envelope"],
        "declared_operation_envelope_ref": "pdc://layer2/s14/declared-envelope",
        "disposition": "universal_claim_limited",
        "s14_universality_assurance_refs": [
            "pdc://layer2/s14/universality-assurance-case",
            "pdc://layer2/s14/axis-scorecard",
            "pdc://layer2/s14/sealed-battery-run",
        ],
        "scorecard_ref": "pdc://layer2/s14/axis-scorecard",
        "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        "assurance_case_ref": "pdc://layer2/s14/universality-assurance-case",
        "limitation_refs": ["limitation://s14/not-all-axes-tested"],
        "out_of_envelope_axis_refs": ["SYSTEM.dynamics_feedback"],
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "3" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _summary_payload(**overrides: object) -> dict[str, object]:
    false_clear_counts = dict.fromkeys(S14_FALSE_CLEAR_FIELDS, 0)
    payload: dict[str, object] = {
        "schema_version": S14_SCHEMA_VERSION,
        "summary_id": "s14-universality-assurance-summary",
        "slice": "S14",
        "cells_closed": [],
        "layer_cells_advanced": ["DESIGNER_ITSELF.evaluation_corpus"],
        "current_open_cell_count": 0,
        "inventory_artifact_count": 22,
        "required_traceability_artifact_count": 6,
        "supporting_record_count": 7,
        "d4_corpus_track_count": 19,
        "expert_oracle_layer_count": 4,
        "sealed_battery_case_count": 6,
        "axis_scorecard_row_count": 27,
        "skeptic_defeater_count": 6,
        "skeptic_defeater_pass_rate": 1.0,
        "mechanism_generality_status": "pass",
        "sublinear_marginal_bespoke_cost_status": "pass",
        "sealed_battery_integrity_status": "pass",
        "universal_claim_disposition": "universal_claim_limited",
        "bare_universal_claim_block_count": 1,
        "untested_axis_out_of_envelope_count": 2,
        "aggregate_universal_number_block_count": 1,
        "false_clear_counts": false_clear_counts,
        **{f"{field}_false_clear_count": 0 for field in S14_FALSE_CLEAR_FIELDS},
        "authority_boundary": _authority_boundary(),
        "replay_digest": "sha256:" + "9" * 64,
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _contract_payloads() -> dict[str, dict[str, object]]:
    first_row = _axis_rows()[0]
    first_defeater = _skeptic_records()[0]
    return {
        "D4CorpusTrackCoverage": _track_coverage_payload(),
        "ExpertOracleBootstrapRecord": _oracle_payload(),
        "UniversalityBreadthFloorConfig": _breadth_payload(),
        "UniversalityBaselineComparison": _baseline_payload(),
        "GroundedAuthorityCoverageRecord": _grounded_authority_payload(),
        "EvaluationStatusCompositionRecord": _status_composition_payload(),
        "EnvelopeRevisionDynamicsRecord": _envelope_dynamics_payload(),
        "SealedUniversalityBatteryRun": _battery_run_payload(),
        "UniversalityAxisScoreRow": first_row,
        "UniversalityAxisScorecard": _scorecard_payload(),
        "MechanismGeneralityReport": _mechanism_payload(),
        "SkepticDefeaterRecord": first_defeater,
        "UniversalityClaimAssuranceCase": _assurance_payload(),
        "UniversalityClaimGateRecord": _gate_payload(),
        "UniversalityAssuranceSummary": _summary_payload(),
    }


def _issue_codes(result: Any) -> set[str]:
    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    issues = payload.get("issues", []) if isinstance(payload, dict) else []
    return {str(issue.get("code")) for issue in issues if isinstance(issue, dict)}


def test_s14_contracts_are_strict_replayable_and_exported() -> None:
    s14 = _s14()
    exported = importlib.import_module("polisyos.runtime.quality")

    assert s14.LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION == S14_SCHEMA_VERSION
    assert s14.LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION == S14_RULE_VERSION_REF
    assert s14.S14_UNIVERSALITY_FLOOR_ID == S14_FLOOR_ID
    assert tuple(s14.S14_FALSE_CLEAR_FIELDS) == S14_FALSE_CLEAR_FIELDS
    assert tuple(s14.S14_SKEPTIC_DEFEATER_IDS) == S14_SKEPTIC_DEFEATER_IDS

    for model_name, payload in _contract_payloads().items():
        model = getattr(s14, model_name)
        assert getattr(exported, model_name) is model
        assert model.model_config.get("extra") == "forbid", model_name
        validated = model.model_validate(payload)
        assert validated.model_dump(mode="json")
        with pytest.raises(ValidationError):
            model.model_validate({**payload, "unexpected_contract_field": "blocked"})


def test_sealed_battery_integrity_requires_partition_path_freeze_hash_and_owner() -> None:
    s14 = _s14()
    partition = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer2_corpus_partition.json")
        .read_text(encoding="utf-8")
    )["sealed_universality_battery"]

    assert partition["path"].endswith("layer2-sealed-universality-battery")
    assert partition["access"] == "ci_gate_only"
    assert partition["owner"] == "governance-board"
    assert partition["freeze_hash"].startswith("sha256:")

    run = s14.verify_sealed_battery_integrity(
        battery_root=SEALED_BATTERY_ROOT,
        partition=partition,
        allow_sealed_battery=True,
    )

    assert run.sealed_battery_integrity_status == "pass"
    assert run.partition_path == partition["path"]
    assert run.owner == "governance-board"
    assert run.freeze_hash == run.computed_freeze_hash


def test_sealed_battery_access_requires_explicit_ci_gate() -> None:
    s14 = _s14()

    denied = s14.verify_sealed_battery_integrity(
        battery_root=SEALED_BATTERY_ROOT,
        partition={
            "path": str(SEALED_BATTERY_ROOT.relative_to(REPO_ROOT)),
            "access": "ci_gate_only",
            "freeze_hash": "sha256:" + "c" * 64,
            "owner": "governance-board",
        },
        allow_sealed_battery=False,
    )

    assert denied.sealed_battery_integrity_status == "blocked"
    assert "sealed_battery_access_requires_explicit_allow" in _issue_codes(denied)


def test_dev_shadow_mode_cannot_read_hidden_sealed_battery() -> None:
    s14 = _s14()

    dev_run = s14.SealedUniversalityBatteryRun.model_validate(
        _battery_run_payload(
            run_mode="dev_shadow_no_hidden_access",
            explicit_access_granted=False,
            sealed_battery_access_attempted=False,
            sealed_battery_status="not_accessed_in_dev",
            access_time=None,
        )
    )

    assert dev_run.sealed_battery_access_attempted is False
    assert dev_run.sealed_battery_status == "not_accessed_in_dev"
    with pytest.raises(ValidationError):
        s14.SealedUniversalityBatteryRun.model_validate(
            _battery_run_payload(
                run_mode="dev_shadow_no_hidden_access",
                explicit_access_granted=False,
                sealed_battery_access_attempted=True,
                hidden_case_payloads=[{"case_id": "sealed"}],
            )
        )


def test_axis_scorecard_defaults_untested_axis_combinations_out_of_envelope() -> None:
    s14 = _s14()

    record = s14.gate_universality_claim(
        claim_text="PolicyOS is universal on all axes.",
        requested_scope_refs=["SYSTEM.dynamics_feedback", "KNOWLEDGE.calibration"],
        scorecard=s14.UniversalityAxisScorecard.model_validate(_scorecard_payload()),
        assurance_case=s14.UniversalityClaimAssuranceCase.model_validate(_assurance_payload()),
    )

    assert record.disposition == "universal_claim_blocked"
    assert set(record.out_of_envelope_axis_refs) >= {
        "SYSTEM.dynamics_feedback",
        "KNOWLEDGE.calibration",
    }


def test_per_axis_scorecard_covers_all_cluster_cells_without_aggregate_universal_number() -> None:
    s14 = _s14()

    scorecard = s14.UniversalityAxisScorecard.model_validate(_scorecard_payload())

    assert len(scorecard.axis_rows) == len(_cluster_axis_refs()) == 27
    assert {row.axis_ref for row in scorecard.axis_rows} == set(_cluster_axis_refs())
    assert scorecard.aggregate_universal_score is None
    with pytest.raises(ValidationError):
        s14.UniversalityAxisScorecard.model_validate(
            _scorecard_payload(aggregate_universal_score=0.91)
        )


def test_per_axis_scorecard_derives_rows_from_capability_reality_report() -> None:
    s14 = _s14()

    scorecard = s14.build_universality_axis_scorecard(
        cluster_map_path=REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml",
        capability_reality_report_ref="pdc://layer2/capability-reality/report",
        battery_status_by_axis=dict.fromkeys(_cluster_axis_refs(), "pass"),
    )

    assert scorecard.capability_reality_report_ref == "pdc://layer2/capability-reality/report"
    assert len(scorecard.axis_rows) == 27


def test_mechanism_generality_requires_sublinear_marginal_bespoke_cost() -> None:
    s14 = _s14()

    passing = s14.MechanismGeneralityReport.model_validate(_mechanism_payload())
    assert passing.marginal_bespoke_cost_status == "pass"
    assert passing.sublinear_marginal_bespoke_cost is True

    with pytest.raises(ValidationError):
        s14.MechanismGeneralityReport.model_validate(
            _mechanism_payload(
                marginal_bespoke_cost_status="pass",
                sublinear_marginal_bespoke_cost=False,
                bespoke_patch_refs=["one-off-template://s14/custom"],
            )
        )


def test_mechanism_generality_reuses_s12_growth_thermometer_pending_s14_ref() -> None:
    s14 = _s14()

    report = s14.build_s14_mechanism_generality_from_growth_thermometer(
        growth_thermometer={
            "thermometer_ref": "pdc://layer2/s12/ua-msme/growth-thermometer",
            "reuse_rate": 0.82,
            "reuse_rate_trend": "improving",
            "reused_primitive_refs": ["primitive://s12/legal-access"],
            "one_off_growth_refs": [],
            "frozen_primitive_set_ref": "repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json",
            "held_out_status": "pending_s14",
        },
        held_out_case_refs=["sealed://s14/capacity-constrained-refugee-services"],
    )

    assert report.growth_thermometer_ref == "pdc://layer2/s12/ua-msme/growth-thermometer"
    assert report.s12_held_out_status == "pending_s14"
    assert report.mechanism_reuse_rate == 0.82


def test_d4_corpus_track_coverage_requires_all_19_architecture_tracks() -> None:
    s14 = _s14()

    coverage = s14.D4CorpusTrackCoverage.model_validate(_track_coverage_payload())

    assert {row.track_id for row in coverage.track_rows} == set(D4_TRACKS)
    assert all(row.minimum_label_refs for row in coverage.track_rows)
    with pytest.raises(ValidationError):
        s14.D4CorpusTrackCoverage.model_validate(
            _track_coverage_payload(track_rows=_track_coverage_payload()["track_rows"][:-1])
        )


def test_expert_oracle_bootstrap_keeps_weak_gold_and_shadow_candidates_seed_only() -> None:
    s14 = _s14()

    oracle = s14.ExpertOracleBootstrapRecord.model_validate(_oracle_payload())
    layers = {row.layer_id: row for row in oracle.oracle_layers}

    assert set(layers) == {
        "weak_gold",
        "expert_gold_seed",
        "causal_support_seed",
        "shadow_candidate_pool",
    }
    assert layers["weak_gold"].authority == "seed_only"
    assert layers["shadow_candidate_pool"].authority == "seed_only"
    assert "promotion_floor" in layers["weak_gold"].forbidden_uses
    assert "oracle_truth" in layers["shadow_candidate_pool"].forbidden_uses


def test_breadth_floor_config_names_domain_jurisdiction_scale_regime_coupling_targets() -> None:
    s14 = _s14()

    config = s14.UniversalityBreadthFloorConfig.model_validate(_breadth_payload())

    assert config.floor_id == S14_FLOOR_ID
    assert config.domain_target
    assert config.jurisdiction_context_target
    assert config.scale_class_target
    assert config.epistemic_regime_target
    assert config.coupling_regime_target
    assert config.lifecycle_target
    assert config.state_capacity_target
    assert config.authority_posture_target
    assert config.instrument_family_target
    assert config.system_dynamics_target
    assert config.excluded_domain_refs


def test_grounded_authority_requires_a_firewall_claim_value_mandate_capacity_refs() -> None:
    s14 = _s14()

    coverage = s14.GroundedAuthorityCoverageRecord.model_validate(
        _grounded_authority_payload()
    )

    assert coverage.coverage_status == "pass"
    assert coverage.a_firewall_refs
    assert coverage.claim_evidence_binding_refs
    assert coverage.value_choice_provenance_refs
    assert coverage.mandate_legitimacy_refs
    assert coverage.capacity_check_refs
    assert coverage.regime_refs
    assert coverage.coupling_refs
    assert coverage.projection_faithfulness_refs
    with pytest.raises(ValidationError):
        s14.GroundedAuthorityCoverageRecord.model_validate(
            _grounded_authority_payload(a_firewall_refs=[])
        )


def test_evaluation_status_composition_blocks_seed_and_gap_laundering() -> None:
    s14 = _s14()

    composition = s14.EvaluationStatusCompositionRecord.model_validate(
        _status_composition_payload()
    )
    effects = {row.d4_label: row.effect for row in composition.status_cases}

    assert effects["weak_gold"] == "seed_only"
    assert effects["shadow_candidate_pool"] == "seed_only"
    assert effects["a_spec_gap"] == "blocks_claim"
    assert effects["search_incomplete"] == "limits_claim"
    assert effects["bespoke_growth_detected"] == "blocks_claim"


def test_evaluation_status_composition_maps_d4_labels_to_existing_closeout_lattice() -> None:
    s14 = _s14()

    composition = s14.EvaluationStatusCompositionRecord.model_validate(
        _status_composition_payload()
    )
    lattice_targets = {
        row.d4_label: row.existing_lattice_target for row in composition.status_cases
    }

    assert lattice_targets["outside_certified_envelope"] == "blocked"
    assert lattice_targets["projection_only"] == "publish_with_limitation"
    assert lattice_targets["envelope_shrunk"] == "public_revalidation"
    assert "new_s14_authority_tier" not in set(lattice_targets.values())


def test_skeptic_defeaters_match_architecture_six_attacks_exactly() -> None:
    s14 = _s14()

    records = [s14.SkepticDefeaterRecord.model_validate(row) for row in _skeptic_records()]

    assert tuple(row.defeater_id for row in records) == S14_SKEPTIC_DEFEATER_IDS
    assert {row.defeater_id: row.attack_id for row in records} == S14_SKEPTIC_ATTACKS
    assert "held_out_integrity_firewall" not in {row.defeater_id for row in records}


def test_skeptic_defeaters_require_all_six_attacks_to_pass() -> None:
    s14 = _s14()
    failing_records = _skeptic_records()
    failing_records[1]["status"] = "limited"

    gate = s14.gate_universality_claim(
        claim_text="PolicyOS is universal over the declared envelope.",
        requested_scope_refs=["scope://s14/declared-envelope"],
        scorecard=s14.UniversalityAxisScorecard.model_validate(_scorecard_payload()),
        assurance_case=s14.UniversalityClaimAssuranceCase.model_validate(_assurance_payload()),
        skeptic_defeaters=[
            s14.SkepticDefeaterRecord.model_validate(row) for row in failing_records
        ],
    )

    assert gate.disposition == "universal_claim_blocked"
    assert "skeptic_defeater_ignored" in _issue_codes(gate)


def test_skeptic_defeaters_are_projected_from_assurance_case_defeaters() -> None:
    s14 = _s14()

    records = s14.project_cae_defeaters_to_s14_skeptic_records(
        cae_defeaters=[
            {
                "defeater_id": defeater_id,
                "defeater_ref": f"cae-defeater://s14/{defeater_id}",
                "status": "resolved",
                "evidence_refs": [f"evidence://s14/{defeater_id}"],
            }
            for defeater_id in S14_SKEPTIC_DEFEATER_IDS
        ],
        attack_mapping=S14_SKEPTIC_ATTACKS,
    )

    assert {record.defeater_id for record in records} == set(S14_SKEPTIC_DEFEATER_IDS)
    assert all(record.projected_from_cae_defeater_ref for record in records)


def test_frozen_once_defeater_requires_expand_and_shrink_revision_evidence() -> None:
    s14 = _s14()

    dynamics = s14.EnvelopeRevisionDynamicsRecord.model_validate(
        _envelope_dynamics_payload()
    )

    assert dynamics.s12_expansion_evidence_refs
    assert dynamics.s13_shrink_or_split_refs
    assert dynamics.frozen_once_defeater_status == "pass"
    with pytest.raises(ValidationError):
        s14.EnvelopeRevisionDynamicsRecord.model_validate(
            _envelope_dynamics_payload(s13_shrink_or_split_refs=[])
        )


def test_envelope_revision_dynamics_reuses_s12_growth_ledger_and_s13_revisions() -> None:
    s14 = _s14()

    dynamics = s14.build_envelope_revision_dynamics_record(
        s12_growth_ledger_refs=["pdc://layer2/s12/ua-msme/envelope-growth-ledger"],
        s13_envelope_revision_refs=["pdc://layer2/s13/ua-msme/envelope-revision/shrink"],
        s13_certified_delta_refs=["pdc://layer2/s13/ua-msme/certified-envelope-delta"],
    )

    assert dynamics.s12_expansion_evidence_refs
    assert dynamics.s13_shrink_or_split_refs
    assert dynamics.certified_envelope_delta_refs


def test_first_call_defeater_requires_baseline_comparison() -> None:
    s14 = _s14()

    baseline = s14.UniversalityBaselineComparison.model_validate(_baseline_payload())
    families = {row.baseline_family for row in baseline.baseline_rows}

    assert families == {"bespoke_tool", "raw_llm", "expert_panel"}
    gate = s14.gate_universality_claim(
        claim_text="PolicyOS is universal over the declared envelope.",
        requested_scope_refs=["scope://s14/declared-envelope"],
        scorecard=s14.UniversalityAxisScorecard.model_validate(_scorecard_payload()),
        assurance_case=s14.UniversalityClaimAssuranceCase.model_validate(
            _assurance_payload(baseline_comparison_ref=None)
        ),
    )
    assert gate.disposition == "universal_claim_blocked"
    assert "baseline_comparison_missing" in _issue_codes(gate)


def test_universality_claim_requires_scorecard_battery_and_assurance_refs() -> None:
    s14 = _s14()

    gate = s14.UniversalityClaimGateRecord.model_validate(_gate_payload())

    assert gate.scorecard_ref
    assert gate.sealed_battery_run_ref
    assert gate.assurance_case_ref
    assert gate.s14_universality_assurance_refs
    with pytest.raises(ValidationError):
        s14.UniversalityClaimGateRecord.model_validate(
            _gate_payload(scorecard_ref=None, sealed_battery_run_ref=None)
        )


def test_universality_claim_assurance_case_reuses_runtime_assurance_case_builder() -> None:
    assurance_case = importlib.import_module("polisyos.runtime.quality.assurance_case")
    s14 = _s14()

    assert hasattr(assurance_case, "build_universality_assurance_case")
    case = s14.build_universality_claim_assurance_case(
        cae_scorecard={
            "quality_status": "pass",
            "blocking_quality_failures": [],
            "warnings": [],
            "evidence_refs": ["pdc://layer2/s14/axis-scorecard"],
        },
        scorecard=s14.UniversalityAxisScorecard.model_validate(_scorecard_payload()),
        skeptic_defeaters=[
            s14.SkepticDefeaterRecord.model_validate(row) for row in _skeptic_records()
        ],
    )

    assert case.cae_claim_ref
    assert case.cae_evidence_refs
    assert case.cae_defeater_refs


def test_bare_universal_claim_without_s14_refs_is_blocked() -> None:
    s14 = _s14()

    result = s14.gate_universality_claim(
        claim_text="PolicyOS is a universal policy designer.",
        requested_scope_refs=[],
        scorecard=None,
        assurance_case=None,
    )

    assert result.disposition == "universal_claim_blocked"
    assert "bare_universal_claim_without_battery" in _issue_codes(result)


def test_universality_gate_allows_limited_claim_with_declared_envelope_only() -> None:
    s14 = _s14()

    gate = s14.gate_universality_claim(
        claim_text="PolicyOS is universal over the declared envelope.",
        requested_scope_refs=["scope://s14/declared-envelope"],
        scorecard=s14.UniversalityAxisScorecard.model_validate(_scorecard_payload()),
        assurance_case=s14.UniversalityClaimAssuranceCase.model_validate(_assurance_payload()),
        visible_limitation_refs=["limitation://s14/not-all-axes-tested"],
    )

    assert gate.disposition == "universal_claim_limited"
    assert gate.declared_operation_envelope_ref
    assert gate.limitation_refs


def test_universality_assurance_cannot_mint_production_or_recommendation_authority() -> None:
    s14 = _s14()

    result = s14.verify_universality_claim_authority(
        _gate_payload(
            authority_boundary=_authority_boundary(
                authoritative_for=[
                    "s14_universality_claim_gate",
                    "production_rollout_authority",
                    "recommendation_authority",
                ]
            )
        )
    )

    assert result["status"] == "fail"
    assert "battery_result_as_production_authority" in {
        issue["code"] for issue in result["issues"]
    }


def test_universality_authority_verifier_does_not_echo_probe_false_clear_field() -> None:
    s14 = _s14()

    result = s14.verify_universality_claim_authority(
        {
            "false_clear_field": "baseline_comparison_missing",
            "baseline_comparison_ref": "pdc://layer2/s14/baseline-comparison",
            "universality_baseline_comparison_ref": (
                "pdc://layer2/s14/baseline-comparison"
            ),
            "s14_universality_assurance_refs": [
                "pdc://layer2/s14/universality-assurance-case"
            ],
        }
    )

    assert result["status"] == "pass"
    assert result["issues"] == []
    assert result["false_clear_counts"]["baseline_comparison_missing"] == 0


def test_gold_labels_cannot_appear_in_dev_signals_or_public_export() -> None:
    s14 = _s14()
    dev_signals = _fixture("s14_universality_dev_signals.json")
    forbidden = {
        "expected_",
        "gold_",
        "answer_key",
        "hidden_case_payload",
        "sealed_fixture_contents",
    }

    serialized = json.dumps(dev_signals)
    assert all(token not in serialized for token in forbidden)
    result = s14.verify_universality_claim_authority(
        _negative_probe("gold_label_leak_into_dev_signal")
    )
    assert result["status"] == "fail"
    assert "gold_label_leak_into_dev_signal" in {issue["code"] for issue in result["issues"]}


def test_freeze_hash_mismatch_fails_closed() -> None:
    s14 = _s14()

    result = s14.verify_sealed_battery_integrity(
        battery_root=SEALED_BATTERY_ROOT,
        partition={
            "path": str(SEALED_BATTERY_ROOT.relative_to(REPO_ROOT)),
            "access": "ci_gate_only",
            "freeze_hash": "sha256:" + "1" * 64,
            "owner": "governance-board",
        },
        allow_sealed_battery=True,
    )

    assert result.sealed_battery_integrity_status == "blocked"
    assert "freeze_hash_mismatch_accepted" in _issue_codes(result)


def test_s14_summary_requires_exact_false_clear_keys() -> None:
    s14 = _s14()

    summary = s14.UniversalityAssuranceSummary.model_validate(_summary_payload())

    assert tuple(summary.false_clear_counts) == S14_FALSE_CLEAR_FIELDS
    for false_clear_field in S14_FALSE_CLEAR_FIELDS:
        assert getattr(summary, f"{false_clear_field}_false_clear_count") == 0

    broken = copy.deepcopy(_summary_payload())
    broken["false_clear_counts"].pop("baseline_comparison_missing")
    with pytest.raises(ValidationError):
        s14.UniversalityAssuranceSummary.model_validate(broken)
