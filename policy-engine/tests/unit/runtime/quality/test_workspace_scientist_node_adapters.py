from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.pdc import OperationClass
from polisyos.runtime.quality.workspace import scientist_node_adapters
from polisyos.runtime.quality.workspace.scientist_node_adapters import ScientistNodeAdapter
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState


@dataclass(frozen=True)
class _FakeNode:
    _spec: NodeSpec

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)


@dataclass(frozen=True)
class _ProducingNode(_FakeNode):
    def execute(self, ctx, state: ExperimentState) -> NodeOutcome:
        next_state = state.model_copy(deep=True)
        next_state.artifacts_index["causal_report_ref"] = ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "2" * 64),
            kind="ir.causal_report",
            media_type="application/json",
        )
        return NodeOutcome(status="ok", state=next_state)


def _node() -> _FakeNode:
    return _FakeNode(
        NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_phase2_fake@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Phase 2 Fake",
                description="Fake node for adapter tests.",
                tags=["phase2"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["run_id", "params.causal_variables", "observational_data_ref"],
            state_writes=["artifacts_index.causal_report_ref"],
            produces=["causal_report_ref"],
        )
    )


def test_legacy_node_adapter_maps_node_spec_to_operation_contract() -> None:
    adapter = ScientistNodeAdapter.from_node(
        _node(),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )

    contract = adapter.contract
    assert contract.operation_id == "phase2.estimate.fake"
    assert contract.operation_class == OperationClass.ESTIMATE
    assert {port.port_id for port in contract.consumes} >= {
        "port-run-id",
        "port-params-causal-variables",
        "port-observational-data-ref",
    }
    assert contract.produces[0].port_id == "port-causal-report-ref"
    assert contract.authority_transform["kind"] == "weakens"
    assert hasattr(scientist_node_adapters, "validate_scientist_node_adapter_shape")
    assert scientist_node_adapters.validate_scientist_node_adapter_shape(adapter).passed is True


def test_legacy_node_adapter_formal_gate_emits_search_blocker_for_missing_port() -> None:
    adapter = ScientistNodeAdapter.from_node(
        _node(),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )

    evaluation = adapter.evaluate_applicability(
        workspace_id="ws-phase2",
        invocation_id="invoke-fake",
        state_facts={"run_id": "R1", "params.causal_variables": ["x", "y"]},
        result_id="applicability-fake",
    )

    assert evaluation.applicability.status == "repair_required"
    assert evaluation.blocker is not None
    assert evaluation.blocker.missing_input == "observational_data_ref"
    assert evaluation.blocker.operation_class == OperationClass.ESTIMATE


def test_legacy_node_adapter_executes_node_as_candidate_event() -> None:
    adapter = ScientistNodeAdapter.from_node(
        _node(),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )
    state = ExperimentState(
        run_id="R_phase2_adapter",
        params={"causal_variables": ["x", "y"]},
        observational_data_ref=ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64),
            kind="ir.observational_data",
            media_type="application/json",
        ),
    )

    execution = adapter.execute_candidate(
        ctx=None,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-fake",
        cycle_index=0,
    )

    assert execution.outcome.status == "ok"
    assert execution.invocation.status == "completed"
    assert execution.invocation.operation_id == "phase2.estimate.fake"
    assert execution.ledger_event.operation_invocation_ref == "invoke-fake"
    assert execution.artifact_envelopes
    assert all(envelope.lifecycle_state == "shadow" for envelope in execution.artifact_envelopes)
    assert all(envelope.authority_boundary is None for envelope in execution.artifact_envelopes)


def test_legacy_node_adapter_semantic_preservation_requires_real_output() -> None:
    adapter = ScientistNodeAdapter.from_node(
        _ProducingNode(_node().spec),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )
    state = ExperimentState(
        run_id="R_phase2_adapter",
        params={"causal_variables": ["x", "y"]},
        observational_data_ref=ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64),
            kind="ir.observational_data",
            media_type="application/json",
        ),
    )

    result = scientist_node_adapters.validate_adapter_semantic_preservation(
        adapter,
        ctx=None,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-semantic",
    )

    assert result.passed is True
    assert "semantic_output_preservation" in result.checked


def test_legacy_node_adapter_shape_only_counterexample_fails_semantic_preservation() -> None:
    adapter = ScientistNodeAdapter.from_node(
        _node(),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )
    state = ExperimentState(
        run_id="R_phase2_adapter",
        params={"causal_variables": ["x", "y"]},
        observational_data_ref=ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64),
            kind="ir.observational_data",
            media_type="application/json",
        ),
    )

    result = scientist_node_adapters.validate_adapter_semantic_preservation(
        adapter,
        ctx=None,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-semantic-counterexample",
    )

    assert result.passed is False
    assert "output_not_preserved:causal_report_ref" in result.failures
