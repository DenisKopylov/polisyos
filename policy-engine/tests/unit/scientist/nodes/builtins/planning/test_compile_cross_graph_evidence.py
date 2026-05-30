from __future__ import annotations

from unittest.mock import patch

import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.ir.analytics.cross_graph import load_cross_graph_evidence_profile
from polisyos.ir.analytics.literature import (
    EnvironmentAuditReport,
    LiteratureCausalPrior,
    persist_literature_causal_prior,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.discovery.priors import (
    GraphPriorBundle,
    PriorEdge,
    persist_graph_prior_bundle,
)
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
    CompileCrossGraphEvidenceNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem1",
            domain="social",
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    value=1,
                    slot_id="budget",
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="policy1"),
        model_spec=ModelSpec(
            model_id="model1",
            data_snapshot_ref="sha256:" + ("0" * 64),
        ),
    )


def test_compilation_without_trinity(execution_context, minimal_state):
    """With enabled config but no Trinity bundle, produces a policy_request_only profile."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in outcome.state.artifacts_index
    summary = outcome.state.params.get("cross_graph_evidence_summary")
    assert summary is not None
    assert outcome.state.params.get("cross_graph_benchmark_summary") is not None


def test_compilation_skips_when_not_expected(execution_context, minimal_state):
    """When config is disabled, compilation is skipped."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": False},
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert outcome.state.params.get("cross_graph_evidence_expected") is False


def test_compilation_skips_fast_governance(execution_context, minimal_state):
    """FAST governance profile skips cross-graph evidence."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
                "governance_profile": "fast",
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert outcome.state.params.get("cross_graph_evidence_expected") is False


def test_compilation_enriches_profile_from_graph_prior_bundle(
    execution_context, minimal_state, cas_store
):
    graph_prior_bundle = GraphPriorBundle(
        high_confidence_edges=[
            PriorEdge(
                edge_key="X->Y",
                src="X",
                dst="Y",
                presence_confidence=0.8,
                orientation_confidence=0.7,
                provenance_refs=["paper:1"],
            )
        ],
        required_edges=[
            PriorEdge(
                edge_key="A->B",
                src="A",
                dst="B",
                presence_confidence=0.9,
                orientation_confidence=0.85,
                provenance_refs=["paper:2"],
            )
        ],
    )
    bundle_ref = persist_graph_prior_bundle(cas_store, graph_prior_bundle)
    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_GRAPH_PRIOR_BUNDLE_REF: bundle_ref,
            },
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            },
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(cas_store, profile_ref)
    assert any(need.need.cause == "A" and need.need.effect == "B" for need in profile.needs)
    assert any(need.need.cause == "X" and need.need.effect == "Y" for need in profile.needs)
    assert "graph_prior_bundle_enriched" in profile.notes


def test_compilation_records_degraded_source_statuses_when_sources_missing(
    execution_context,
    minimal_state,
    cas_store,
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "academic_db_path": "/tmp/missing-academic.duckdb",
                    "datasets_db_path": "/tmp/missing-datasets.duckdb",
                    "legal_db_path": "/tmp/missing-legal.duckdb",
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(cas_store, profile_ref)
    assert profile.source_statuses["academic"].status.value == "missing_path"
    assert profile.source_statuses["datasets"].status.value == "missing_path"
    assert profile.source_statuses["legal"].status.value == "missing_path"
    assert profile.source_statuses["benchmark"].status.value == "missing_config"
    assert profile.benchmark_summary["status"] == "degraded"


def test_compilation_writes_backlog_for_unresolved_needs(
    execution_context,
    minimal_state,
    tmp_path,
):
    backlog_path = tmp_path / "cross-graph-backlog.json"
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "backlog_output_path": str(backlog_path),
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert backlog_path.exists()


def test_compilation_appends_academic_demand_backlog_when_configured(
    execution_context,
    minimal_state,
    tmp_path,
):
    backlog_path = tmp_path / "cross-graph-backlog.json"
    academic_backlog_path = tmp_path / "academic-demand-backlog.jsonl"
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "backlog_output_path": str(backlog_path),
                    "academic_demand_backlog_path": str(academic_backlog_path),
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert backlog_path.exists()
    assert academic_backlog_path.exists()


def test_compilation_persists_degraded_profile_for_invalid_config(
    execution_context,
    minimal_state,
    cas_store,
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "unknown_field": "boom",
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(cas_store, profile_ref)
    assert profile.summary.status == "degraded"
    assert profile.diagnostics[0].code == "cross_graph.invalid_config"
    assert profile.benchmark_summary["reason"] == "invalid_config"


def test_compilation_passes_literature_prior_context_into_compiler(
    execution_context,
    minimal_state,
    cas_store,
    monkeypatch,
):
    trinity_ref = cas_store.put_json(
        _bundle(),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.trinity_bundle", version="1.0"),
        ),
    )
    prior_ref = persist_literature_causal_prior(
        cas_store,
        LiteratureCausalPrior(
            environment_audit=EnvironmentAuditReport(
                status="warning",
                n_environments=2,
                ks_passed=False,
                ks_rejected_variables=[0],
            ),
            metadata={"build_status": "ok"},
        ),
    )
    captured: dict[str, object] = {}

    def _fake_compile(self, bundle, **kwargs):
        del self, bundle
        captured.update(kwargs)
        from polisyos.ir.analytics.cross_graph import (
            CrossGraphEvidenceProfile,
            CrossGraphEvidenceSummary,
        )

        return CrossGraphEvidenceProfile(
            summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
            notes=["compiled"],
        )

    monkeypatch.setattr(
        "polisyos.scientist.cross_graph.compiler.CrossGraphEvidenceCompiler.compile",
        _fake_compile,
    )

    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            },
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_LITERATURE_PRIOR_REF: prior_ref,
            },
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            },
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert captured["literature_prior"] is not None
    assert captured["literature_prior_ref"] == str(prior_ref.artifact_id)


def test_compilation_target_context_assertion_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
                "target_context": {"country": "US", "year": 2025},
            }
        }
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("target-context-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence.ContextProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="target-context-broken"):
        CompileCrossGraphEvidenceNode().execute(execution_context, state)


def test_compilation_uses_branch_state_for_declared_outputs(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            }
        }
    )
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence.branch_state",
        _spy_branch,
    ):
        outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.cross_graph_evidence_profile_ref",
        "params.cross_graph_evidence_expected",
        "params.cross_graph_evidence_summary",
        "params.cross_graph_benchmark_summary",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF not in state.artifacts_index
    assert outcome.state.params["cross_graph_evidence_expected"] is True
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in outcome.state.artifacts_index
