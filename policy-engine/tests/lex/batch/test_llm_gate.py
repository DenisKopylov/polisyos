from __future__ import annotations

from polisyos.lex.batch.llm_gate import (
    GateRuntime,
    build_gate_features,
    decide_route,
)


def test_gate_routes_auto_on_high_deterministic_confidence() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Коротка норма без неоднозначності.",
        deterministic_confidence=0.95,
        reference_count=0,
        fallback_chunk=False,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        deterministic_confidence=0.95,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:1",
    )
    assert decision.route == "auto"


def test_gate_respects_budget_cap() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.1,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Складна норма з цифрами 20% і численними посиланнями.",
        deterministic_confidence=0.2,
        reference_count=4,
        fallback_chunk=True,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.5,
        deterministic_confidence=0.2,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:2",
    )
    assert decision.route == "deferred"
    assert "budget_cap" in decision.reason_codes


def test_gate_circuit_breaker_triggers_after_two_failures() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
        circuit_breaker_enabled=True,
    )
    assert runtime.register_audit_miss_rate(5.0) is False
    assert runtime.register_audit_miss_rate(6.0) is True
    assert runtime.safe_pass_active is True
    assert runtime.circuit_breaker_hits == 1

