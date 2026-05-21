from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.degradation import (
    DEGRADATION_LEDGER_REQUIRED_FIELDS,
    DEFAULT_MODE_AND_FALLBACK_POLICY_REGISTRY,
    DegradationLedgerContractError,
    ModeAndFallbackPolicyRegistryError,
    assert_serious_fallback_allowed,
    build_degradation_record,
    deserialize_degradation_record,
    degradation_gate_from_payloads,
    evaluate_degradation_policy,
    load_mode_and_fallback_policy_registry,
    serialize_degradation_record,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    scorecard_for,
    sha,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _fixture_payload(name: str) -> dict[str, Any]:
    path = REPO_ROOT / f"tests/fixtures/runtime_quality/degradation_ledgers/{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["payload"]


def test_degradation_ledger_records_include_phase_1_5_required_fields() -> None:
    payload = _fixture_payload("declared_allowed_fallback_pass")

    assert set(DEGRADATION_LEDGER_REQUIRED_FIELDS) <= set(payload)

    for field in DEGRADATION_LEDGER_REQUIRED_FIELDS:
        incomplete = deepcopy(payload)
        incomplete.pop(field)

        with pytest.raises(DegradationLedgerContractError) as error:
            deserialize_degradation_record(incomplete)

        assert error.value.code == "degradation_ledger_required_field_missing"
        assert error.value.field == field


def test_replay_manifest_degradation_ledger_summary_is_not_a_degradation_record() -> None:
    gate = degradation_gate_from_payloads(
        canary_kind="production",
        job_payload=None,
        run_payload=None,
        quality_evidence={
            "replay_manifest": {
                "schema_version": "policyos.replay_manifest.v1",
                "status": "pass",
                "degradation_ledger": {
                    "degradation_ledger_ref": sha("d"),
                    "blocking_record_count": 0,
                },
            }
        },
    )

    assert gate is None


def test_mode_and_fallback_policy_registry_loads_real_test_commands() -> None:
    registry = load_mode_and_fallback_policy_registry(
        DEFAULT_MODE_AND_FALLBACK_POLICY_REGISTRY,
        repo_root=REPO_ROOT,
    )

    assert registry.mode_policies
    assert registry.fallback_policies


def test_mode_and_fallback_policy_registry_rejects_missing_command_path(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "mode_and_fallback_policy.toml"
    registry.write_text(
        "\n".join(
            [
                "[[mode_policies]]",
                'policy_id = "serious_production_mode"',
                'profiles = ["production"]',
                'failure_code = "mode_policy_failure"',
                'next_diagnostic_command = "uv run pytest tests/unit/runtime/quality/test_missing_policy.py -q"',
                "",
                "[[fallback_policies]]",
                'policy_id = "serious_fallback_fail_closed"',
                'profiles = ["production"]',
                'failure_code = "degradation_fallback_not_allowed"',
                'next_diagnostic_command = "uv run pytest tests/unit/runtime/quality/test_degradation.py -q"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ModeAndFallbackPolicyRegistryError,
        match="diagnostic command path does not exist",
    ):
        load_mode_and_fallback_policy_registry(registry, repo_root=REPO_ROOT)


def test_declared_allowed_fallback_fixture_passes_serious_policy() -> None:
    record = deserialize_degradation_record(
        _fixture_payload("declared_allowed_fallback_pass")
    )

    decision = evaluate_degradation_policy(record, active_profile="production")

    assert decision.allowed is True
    assert decision.blocking is False
    assert decision.code is None
    assert record.provenance_refs == (
        "event://diagnostic/evt_hds_phase02_allowed_fallback_pass",
        "cas://sha256/9999999999999999999999999999999999999999999999999999999999999999",
    )
    assert record.typed_blocker is None
    assert deserialize_degradation_record(serialize_degradation_record(record)) == record


def test_generated_substitute_fixture_blocks_production_authority_closeout() -> None:
    record = deserialize_degradation_record(
        _fixture_payload("silent_generated_substitute_rejected")
    )

    decision = evaluate_degradation_policy(record, active_profile="production")

    assert decision.allowed is False
    assert decision.blocking is True
    assert decision.code == "degradation_generated_substitute_not_allowed"
    assert decision.typed_blocker is not None
    assert decision.typed_blocker["code"] == "degradation_generated_substitute_not_allowed"

    with pytest.raises(DegradationLedgerContractError) as error:
        assert_serious_fallback_allowed(record, active_profile="production")

    assert error.value.code == "degradation_generated_substitute_not_allowed"


@pytest.mark.parametrize(
    ("degradation_kind", "trigger", "expected_code"),
    [
        (
            "fallback_default",
            "implicit_runtime_default_used",
            "degradation_fallback_default_not_allowed",
        ),
        (
            "optional_report_generation",
            "runtime_quality_ref_marked_optional",
            "degradation_optional_report_generation_not_allowed",
        ),
        (
            "generated_substitute",
            "missing_runtime_report_generated_by_bundle",
            "degradation_generated_substitute_not_allowed",
        ),
        (
            "parser_healing",
            "llm_payload_schema_healed",
            "degradation_parser_healing_not_allowed",
        ),
        (
            "provider_quarantine",
            "provider_model_quarantined",
            "degradation_provider_quarantine_not_allowed",
        ),
        (
            "jax_missing_materialization_refs",
            "jax_unavailable_materialization_refs_synthesized",
            "degradation_jax_missing_materialization_refs_not_allowed",
        ),
        (
            "local_canary_fixture_payload",
            "local_fixture_payload_used",
            "degradation_local_canary_fixture_payload_not_allowed",
        ),
        (
            "deterministic_overlay",
            "deterministic_evidence_overlay_applied",
            "degradation_deterministic_overlay_not_allowed",
        ),
        (
            "dashboard_projection",
            "dashboard_quality_projection_used",
            "degradation_dashboard_projection_not_allowed",
        ),
    ],
)
def test_degradation_scenarios_fail_closed_for_serious_authority_evidence(
    degradation_kind: str,
    trigger: str,
    expected_code: str,
) -> None:
    record = build_degradation_record(
        component="polisyos.runtime.quality.tests",
        phase="quality_closeout",
        trigger=trigger,
        primary_path="cas://runtime/authority-evidence",
        fallback_path=f"fallback://{degradation_kind}",
        allowed_profiles=("dev_smoke",),
        actual_profile="production",
        produced_artifacts=(sha("a"),),
        affected_claims=("claim://policy/recommendation-1",),
        affected_gates=("readiness.minimum_closeout_gate",),
        severity="high",
        degradation_kind=degradation_kind,
        override_policy="not_overridable",
        downstream_impact="Would let fallback-derived evidence satisfy a serious gate.",
        provenance_refs=("event://diagnostic/fallback-test",),
        owner="team-runtime-ops",
    )

    decision = evaluate_degradation_policy(record, active_profile="production")

    assert decision.allowed is False
    assert decision.blocking is True
    assert decision.code == expected_code
    assert decision.typed_blocker is not None
    assert decision.typed_blocker["code"] == expected_code


def test_signed_non_production_lowering_exception_can_allow_serious_fallback() -> None:
    record = build_degradation_record(
        component="polisyos.lex.parser",
        phase="lex_parse",
        trigger="parser_recovered_trailing_json",
        primary_path="parser://strict-json",
        fallback_path="parser://lossless-healing",
        allowed_profiles=("dev_smoke",),
        actual_profile="production",
        produced_artifacts=(sha("b"),),
        affected_claims=("claim://normative_applicability/ua_energy_relief",),
        affected_gates=("runtime_quality.normative_applicability",),
        severity="medium",
        degradation_kind="parser_healing",
        override_policy="signed_non_production_lowering_exception",
        downstream_impact="Parser repair preserved every field and did not lower production evidence.",
        provenance_refs=("event://diagnostic/parser-healing",),
        owner="team-runtime-ops",
        signed_exception_ref="exception://signed/non-production-lowering/parser-healing-1",
    )

    decision = evaluate_degradation_policy(record, active_profile="production")

    assert decision.allowed is True
    assert decision.blocking is False
    assert decision.code is None
    assert record.typed_blocker is None


def test_scorecard_blocks_silent_fallback_without_degradation_ledger_for_serious_closeout() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "fallback_used": True,
                "fallback_reason": "llm_gateway_timeout",
                "degradation_ledger_ref": None,
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_unallowed_fallback" in blocking_codes(scorecard)
