"""Packet projections cannot turn an unverified option/program join into authority."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    _populate_optional_report_projections,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_OUTPUT_BUNDLE_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified import (
    VerifiedPolicyReport,
    load_verified_policy_report,
    persist_verified_policy_report,
)


def test_current_legacy_report_keeps_human_gate_and_discloses_unproved_join(
    tmp_path, monkeypatch
) -> None:
    import polisyos.scientist.validation.policy_verified.currentness as currentness

    store = FileSystemCAS(tmp_path / "cas")
    selected = persist_verified_policy_report(
        store,
        VerifiedPolicyReport(
            request_id="synthetic",
            executive_summary="Historical candidate summary",
            missing_evidence=["Independent earlier limitation"],
            needs_expert_review=False,
        ),
    )
    report = load_verified_policy_report(store, selected)
    monkeypatch.setattr(
        currentness,
        "resolve_current_verified_policy_report",
        lambda _ctx, _state, ref: SimpleNamespace(is_current=ref == selected, report=report),
    )
    state = ExperimentState(
        run_id="synthetic-option-program-packet",
        verified_policy_report_ref=selected,
        params={"option_program_correspondence": {"status": "verified"}},
    )
    packet: dict[str, object] = {}
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    _populate_optional_report_projections(ctx, state, packet)
    answer = packet["policy_answer"]
    assert isinstance(answer, dict)
    assert answer["needs_expert_review"] is False
    assert answer["missing_evidence"] == [
        "Independent earlier limitation",
        "The selected policy option has not been matched to the final program.",
    ]
    assert answer["option_program_correspondence"] == {
        "status": "not_established",
        "reason_code": "option_program_correspondence_not_established",
    }
    assert load_verified_policy_report(store, selected) == report


def test_packet_bundle_discloses_unproved_join_even_if_caller_claims_verified(
    tmp_path, monkeypatch
) -> None:
    import polisyos.scientist.policy_design.output as output_owner

    store = FileSystemCAS(tmp_path / "cas")
    selected = store.put_json(
        {"synthetic": True},
        PutOptions(kind="scientist.policy_artifact_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    ref = SimpleNamespace(artifact_id="synthetic-ref")
    bundle = SimpleNamespace(
        policy_brief_ref=ref,
        champion_policy_dossier_ref=ref,
        decision_readiness_contract_ref=None,
        phase3_gate=SimpleNamespace(model_dump=lambda **_kwargs: {"status": "pass"}),
    )
    monkeypatch.setattr(output_owner, "load_policy_artifact_bundle", lambda *_args: bundle)
    state = ExperimentState(
        run_id="synthetic-option-program-bundle",
        artifacts_index={ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: selected},
        params={"option_program_correspondence": {"status": "verified"}},
    )
    packet: dict[str, object] = {}
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    _populate_optional_report_projections(ctx, state, packet)
    projected = packet["policy_output_bundle"]
    assert isinstance(projected, dict)
    assert projected["phase3_gate"] == {"status": "pass"}
    assert projected["option_program_correspondence"] == {
        "status": "not_established",
        "reason_code": "option_program_correspondence_not_established",
    }
