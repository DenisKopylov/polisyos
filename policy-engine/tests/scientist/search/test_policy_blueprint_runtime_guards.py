from __future__ import annotations

import hashlib
import logging
from types import SimpleNamespace

import polisyos.scientist.nodes.builtins.c6c_runtime_support as c6c_runtime_support
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    load_performative_shift_summary,
    load_strategic_payoff_table,
    load_strategic_response_bundle,
    load_strategic_scm,
    persist_strategic_payoff_table,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.doe.stress_report import (
    StressTestReport,
    Vulnerability,
    VulnerabilityType,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.evidence_sources import EvidenceSourcesConfig
from polisyos.scientist.kernel.budgets import ComputeBudget
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _SPEC,
    _merge_stress_test_reports,
    _persist_runtime_strategic_artifacts,
    _resolve_policy_runtime_source_statuses,
    _resolve_replay_bundle_ref,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_REPORT_REF


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
        ),
        kind="scientist.test",
        media_type="application/json",
    )


def _artifact_ref_model(seed: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": str(_ref(seed).artifact_id),
            "kind": kind,
            "media_type": "application/json",
        }
    )


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / run_id)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _runtime_payoff_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("low", "high"),
        "follower": ("stay", "switch"),
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }


def _runtime_contract(
    *,
    utility_refs: dict[str, ArtifactRefModel] | None = None,
    macro_utility_refs: dict[str, ArtifactRefModel] | None = None,
) -> StrategicSCM:
    return StrategicSCM(
        base_graph_ref=_artifact_ref_model("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs=utility_refs
        or {
            "leader": _artifact_ref_model("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref_model("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        macro_utility_refs=macro_utility_refs,
        policy_rule_ref=_artifact_ref_model("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )


def test_replay_resolution_does_not_fallback_to_checkpoint_ref() -> None:
    state = ExperimentState(
        run_id="run-a",
        last_checkpoint_ref=_ref("a"),
    )

    assert _resolve_replay_bundle_ref(state, None) is None


def test_replay_resolution_prefers_replayable_audit_bundle() -> None:
    replay_ref = _ref("b")
    state = ExperimentState(
        run_id="run-a",
        artifacts_index={"replayable_audit_bundle_ref": replay_ref},
        last_checkpoint_ref=_ref("c"),
    )

    assert _resolve_replay_bundle_ref(state, None) == replay_ref


def test_runtime_source_statuses_fall_back_to_nested_evidence_sources() -> None:
    statuses = _resolve_policy_runtime_source_statuses(
        cross_graph_profile=None,
        evidence_sources=EvidenceSourcesConfig(legal_db_path="/tmp/missing-legal.duckdb"),
    )

    assert statuses["legal"] == "missing_path"
    assert statuses["academic"] == "missing_config"
    assert statuses["benchmark"] == "missing_config"


def test_runtime_source_statuses_prefer_cross_graph_profile_when_available() -> None:
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=0),
        source_statuses={
            "legal": EvidenceSourceStatus(
                source=EvidenceSourceKind.LEGAL,
                configured=True,
                status=EvidenceSourceState.AVAILABLE,
            )
        },
    )

    statuses = _resolve_policy_runtime_source_statuses(
        cross_graph_profile=profile,
        evidence_sources=EvidenceSourcesConfig(legal_db_path="/tmp/missing-legal.duckdb"),
    )

    assert statuses["legal"] == "available"


def test_merge_stress_reports_replaces_phase_d4_suite_findings_by_suite_id() -> None:
    base_report = StressTestReport(
        report_id="stress-base",
        total_scenarios_evaluated=5,
        vulnerabilities=[
            Vulnerability(
                vulnerability_id="baseline:constraint",
                vulnerability_type=VulnerabilityType.CONSTRAINT_VIOLATION,
                severity="medium",
                description="baseline finding",
            ),
            Vulnerability(
                vulnerability_id="strategic_gaming_v1:stale_case",
                vulnerability_type=VulnerabilityType.COMBINATORIAL,
                severity="high",
                description="stale strategic finding",
            ),
        ],
        metadata={
            "phase_d4_suite_ids": ["strategic_gaming_v1"],
            "phase_d4_suite_scenario_counts": {"strategic_gaming_v1": 2},
            "base_total_scenarios_evaluated": 3,
        },
    )
    supplemental = StressTestReport(
        report_id="stress-strategic-refresh",
        total_scenarios_evaluated=4,
        vulnerabilities=[
            Vulnerability(
                vulnerability_id="strategic_gaming_v1:fresh_case",
                vulnerability_type=VulnerabilityType.COMBINATORIAL,
                severity="critical",
                description="fresh strategic finding",
            )
        ],
        metadata={"challenge_suite_id": "strategic_gaming_v1"},
    )

    merged = _merge_stress_test_reports(base_report, [supplemental])

    assert merged.total_scenarios_evaluated == 7
    assert merged.metadata["phase_d4_suite_ids"] == ["strategic_gaming_v1"]
    assert merged.metadata["phase_d4_suite_scenario_counts"] == {"strategic_gaming_v1": 4}
    vulnerability_ids = [item.vulnerability_id for item in merged.vulnerabilities]
    assert "baseline:constraint" in vulnerability_ids
    assert "strategic_gaming_v1:fresh_case" in vulnerability_ids
    assert "strategic_gaming_v1:stale_case" not in vulnerability_ids


def test_merge_stress_reports_can_clear_stale_phase_d4_findings_after_pass() -> None:
    base_report = StressTestReport(
        report_id="stress-base",
        total_scenarios_evaluated=5,
        vulnerabilities=[
            Vulnerability(
                vulnerability_id="strategic_gaming_v1:stale_case",
                vulnerability_type=VulnerabilityType.COMBINATORIAL,
                severity="high",
                description="stale strategic finding",
            )
        ],
        metadata={
            "phase_d4_suite_ids": ["strategic_gaming_v1"],
            "phase_d4_suite_scenario_counts": {"strategic_gaming_v1": 2},
            "base_total_scenarios_evaluated": 3,
        },
    )

    merged = _merge_stress_test_reports(
        base_report,
        [],
        replacement_suite_ids=["strategic_gaming_v1"],
    )

    assert merged.total_scenarios_evaluated == 3
    assert merged.vulnerabilities == []
    assert merged.metadata["phase_d4_suite_ids"] == []
    assert merged.metadata["phase_d4_suite_scenario_counts"] == {}


def test_runtime_spec_declares_strategic_phase_d_reads_and_writes() -> None:
    assert "params.strategic_scm" in _SPEC.state_reads
    assert "params.strategic_payoff_tables" in _SPEC.state_reads
    assert "params.macro_strategic_payoff_tables" in _SPEC.state_reads
    assert "params.performative_loop_spec" in _SPEC.state_reads
    assert "params.strategic_response" in _SPEC.state_writes


def test_runtime_strategic_helper_persists_normalized_contract_and_real_causal_component(
    tmp_path,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_ok")
    tables = _runtime_payoff_tables()
    leader_ref = persist_strategic_payoff_table(ctx.store, tables["leader"])
    follower_ref = persist_strategic_payoff_table(ctx.store, tables["follower"])
    contract = _runtime_contract(
        utility_refs={
            "leader": leader_ref,
            "follower": follower_ref,
        }
    )
    causal_report_ref = _ref("c")
    state = ExperimentState(
        run_id="runtime_strategic_ok",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
            "performative_loop_spec": {
                "analysis_scope": "iterated_loop",
                "proof_family": "rrm_parametric",
                "beta": 2.0,
                "gamma": 4.0,
                "epsilon": 1.0,
            },
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: causal_report_ref},
    )

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_scm_ref is not None
    assert output.strategic_response_bundle_ref is not None
    assert output.strategic_response_summary is not None
    normalized_contract = load_strategic_scm(ctx.store, output.strategic_scm_ref)
    assert normalized_contract.utility_refs["leader"] == leader_ref
    assert load_strategic_payoff_table(ctx.store, normalized_contract.utility_refs["leader"]) == tables["leader"]
    assert output.strategic_response_summary["causal_component_ref"]["artifact_id"] == str(
        causal_report_ref.artifact_id
    )
    assert output.strategic_response_summary["performative_loop"]["stability_status"] == (
        "certified_convergent"
    )
    bundle = load_strategic_response_bundle(ctx.store, output.strategic_response_bundle_ref)
    assert bundle.performative_shift_ref is not None
    shift_summary = load_performative_shift_summary(ctx.store, bundle.performative_shift_ref)
    assert shift_summary.analysis_scope.value == "iterated_loop"


def test_runtime_strategic_helper_blocks_when_causal_report_is_missing(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_no_causal")
    tables = _runtime_payoff_tables()
    leader_ref = persist_strategic_payoff_table(ctx.store, tables["leader"])
    follower_ref = persist_strategic_payoff_table(ctx.store, tables["follower"])
    contract = _runtime_contract(
        utility_refs={
            "leader": leader_ref,
            "follower": follower_ref,
        }
    )
    state = ExperimentState(
        run_id="runtime_strategic_no_causal",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
        },
    )

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_scm_ref is not None
    assert output.strategic_response_bundle_ref is None
    assert output.strategic_response_summary is not None
    assert output.strategic_response_summary["blocked_reason"] == (
        "missing_causal_report_for_strategic_decomposition"
    )


def test_runtime_strategic_helper_blocks_on_unreadable_contract_payoff_refs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_unreadable")
    contract = _runtime_contract()
    tables = _runtime_payoff_tables()
    state = ExperimentState(
        run_id="runtime_strategic_unreadable",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: _ref("c")},
    )

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_scm_ref is not None
    assert output.strategic_response_bundle_ref is None
    assert output.strategic_response_summary is not None
    assert output.strategic_response_summary["blocked_reason"] == (
        "strategic_contract_payoff_ref_unreadable"
    )
    stored_contract = load_strategic_scm(ctx.store, output.strategic_scm_ref)
    assert stored_contract.utility_refs == contract.utility_refs


def test_runtime_strategic_helper_blocks_on_contract_payoff_mismatch(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_mismatch")
    tables = _runtime_payoff_tables()
    mismatched_leader = tables["leader"].model_copy(
        update={
            "payoffs": {
                **tables["leader"].payoffs,
                "leader=high|follower=switch": 30.0,
            }
        }
    )
    leader_ref = persist_strategic_payoff_table(ctx.store, mismatched_leader)
    follower_ref = persist_strategic_payoff_table(ctx.store, tables["follower"])
    contract = _runtime_contract(
        utility_refs={
            "leader": leader_ref,
            "follower": follower_ref,
        }
    )
    state = ExperimentState(
        run_id="runtime_strategic_mismatch",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: _ref("c")},
    )

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_scm_ref is not None
    assert output.strategic_response_bundle_ref is None
    assert output.strategic_response_summary is not None
    assert output.strategic_response_summary["blocked_reason"] == (
        "strategic_contract_payoff_ref_mismatch"
    )


def test_runtime_strategic_helper_invalid_input_records_degraded_path(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_invalid")
    state = ExperimentState(
        run_id="runtime_strategic_invalid",
        params={
            "strategic_scm": {"not": "a strategic contract"},
            "strategic_payoff_tables": {},
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: _ref("c")},
    )

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_response_summary is not None
    assert output.strategic_response_summary["blocked_reason"] == "strategic_runtime_invalid_input"
    degraded = output.strategic_response_summary["degraded_path"]
    assert degraded["component"] == "scientist.decision_runtime"
    assert degraded["reason"] == "strategic_runtime_invalid_input"


def test_runtime_strategic_helper_persistence_failure_records_degraded_path(
    tmp_path,
    monkeypatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="runtime_strategic_persistence_failure")
    tables = _runtime_payoff_tables()
    leader_ref = persist_strategic_payoff_table(ctx.store, tables["leader"])
    follower_ref = persist_strategic_payoff_table(ctx.store, tables["follower"])
    contract = _runtime_contract(
        utility_refs={
            "leader": leader_ref,
            "follower": follower_ref,
        }
    )
    state = ExperimentState(
        run_id="runtime_strategic_persistence_failure",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: _ref("c")},
    )

    def _explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(c6c_runtime_support, "persist_strategic_scm", _explode)

    output = _persist_runtime_strategic_artifacts(
        ctx,
        state,
        candidate_ref=_ref("a"),
        selection_vector_ref=_ref("b"),
        selection_artifact=SimpleNamespace(simulation_results={"policy_value": 2.0}),
        artifacts_index=dict(state.artifacts_index),
    )

    assert output.strategic_response_summary is not None
    assert output.strategic_response_summary["blocked_reason"] == (
        "strategic_runtime_persistence_failed"
    )
    degraded = output.strategic_response_summary["degraded_path"]
    assert degraded["component"] == "scientist.decision_runtime"
    assert degraded["reason"] == "strategic_runtime_persistence_failed"
