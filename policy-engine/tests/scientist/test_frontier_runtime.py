from __future__ import annotations

from polisyos.scientist.frontier_runtime import (
    FrontierCapabilityStatus,
    FrontierRuntimeConfig,
    build_frontier_runtime_report,
)


def test_frontier_runtime_report_marks_disabled_capabilities_disabled() -> None:
    report = build_frontier_runtime_report(FrontierRuntimeConfig())

    assert report.default_enable_eligible is False
    assert report.requested_capabilities == []
    assert {item.status for item in report.capabilities} == {FrontierCapabilityStatus.DISABLED}


def test_frontier_runtime_report_requires_validation_and_benchmark_refs() -> None:
    report = build_frontier_runtime_report(
        FrontierRuntimeConfig(
            enable_proximal_causal=True,
            enable_adversarial_scenario_discovery=True,
        )
    )

    assert report.default_enable_eligible is False
    assert "missing_offline_validation_ref" in report.default_enable_blockers
    assert "missing_benchmark_pack_ref" in report.default_enable_blockers
    proximal = next(
        item for item in report.capabilities if item.capability_id == "proximal_causal"
    )
    assert proximal.status == FrontierCapabilityStatus.OFFLINE_GATED


def test_frontier_runtime_report_marks_wired_capabilities_available_offline() -> None:
    report = build_frontier_runtime_report(
        FrontierRuntimeConfig(
            enable_proximal_causal=True,
            enable_adversarial_scenario_discovery=True,
            offline_validation_ref="sha256:" + "a" * 64,
            benchmark_pack_ref="sha256:" + "b" * 64,
            default_enable_requested=True,
            allow_baseline_replacement=True,
        )
    )

    proximal = next(
        item for item in report.capabilities if item.capability_id == "proximal_causal"
    )
    adversarial = next(
        item
        for item in report.capabilities
        if item.capability_id == "adversarial_scenario_discovery"
    )
    assert proximal.status == FrontierCapabilityStatus.AVAILABLE_OFFLINE
    assert adversarial.status == FrontierCapabilityStatus.AVAILABLE_OFFLINE
    assert report.default_enable_eligible is True


def test_frontier_runtime_report_keeps_unwired_methods_experimental() -> None:
    report = build_frontier_runtime_report(
        FrontierRuntimeConfig(
            enable_neural_dag_learners=True,
            offline_validation_ref="sha256:" + "a" * 64,
            benchmark_pack_ref="sha256:" + "b" * 64,
        )
    )

    neural = next(
        item for item in report.capabilities if item.capability_id == "neural_dag_learners"
    )
    assert neural.status == FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED
    assert report.default_enable_eligible is False
