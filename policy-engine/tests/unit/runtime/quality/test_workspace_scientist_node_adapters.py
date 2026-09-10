from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import InputRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.pdc import OperationClass
from polisyos.runtime.quality import adapter_contracts
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
        ctx.calls.append("execute")
        next_state = state.model_copy(deep=True)
        next_state.artifacts_index["causal_report_ref"] = ctx.store.put_json(
            {"status": "candidate", "finding": "measured test output"},
            PutOptions(kind="ir.causal_report", media_type="application/json"),
        )
        return NodeOutcome(
            status="ok",
            state=next_state,
            artifacts=[next_state.artifacts_index["causal_report_ref"]],
        )


def _station(tmp_path, *, store_type=FileSystemCAS):
    store = store_type(tmp_path / "cas")
    state = ExperimentState(
        run_id="R_phase2_adapter",
        params={"causal_variables": ["x", "y"]},
        observational_data_ref=store.put_json(
            {"observations": [{"x": 1, "y": 2}]},
            PutOptions(kind="ir.observational_data", media_type="application/json"),
        ),
    )
    return SimpleNamespace(store=store, calls=[]), state


def _adapter(node=None):
    return ScientistNodeAdapter.from_node(
        node or _ProducingNode(_node().spec),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )


def _conformance(adapter, ctx, state, **kwargs):
    return scientist_node_adapters.validate_adapter_semantic_preservation(
        adapter,
        ctx=ctx,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-semantic",
        **kwargs,
    )


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


def test_legacy_node_adapter_semantic_preservation_requires_real_output(tmp_path) -> None:
    adapter = ScientistNodeAdapter.from_node(
        _ProducingNode(_node().spec),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )
    ctx, state = _station(tmp_path)

    result = scientist_node_adapters.validate_adapter_semantic_preservation(
        adapter,
        ctx=ctx,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-semantic",
    )

    assert result.passed is True
    assert "semantic_output_preservation" in result.checked


def test_conformance_returns_once_executed_payload_with_real_cas_custody(tmp_path) -> None:
    import hashlib
    import json

    ctx, state = _station(tmp_path)
    result = _conformance(_adapter(), ctx, state, cycle_index=7)

    assert result.passed, result.failures
    assert ctx.calls == ["execute"]
    assert result.execution is not None
    assert "execution" not in result.model_dump(mode="json")
    assert result.execution.invocation.cycle_index == 7
    assert result.workspace_id == "ws-phase2"
    assert result.invocation_id == "invoke-semantic"
    assert result.cycle_index == 7
    assert result.smoke_attempted is True
    assert result.conformance_ref is not None
    report_payload = json.loads(ctx.store.get_bytes(result.conformance_ref.artifact_id))
    assert report_payload["passed"] is True
    assert "conformance_ref" not in report_payload
    assert "execution" not in report_payload
    assert result.input_bindings
    assert result.applicability_binding is not None
    assert result.execution.invocation.applicability_result == (
        f"cas://{result.applicability_binding.artifact_ref.artifact_id}"
    )
    assert result.input_state_hash.startswith("sha256:")
    assert [item.path for item in result.output_bindings] == ["causal_report_ref"]
    binding = result.output_bindings[0]
    blob = ctx.store.get_bytes(binding.artifact_ref.artifact_id)
    assert binding.content_hash == "sha256:" + hashlib.sha256(blob).hexdigest()
    envelope = result.execution.artifact_envelopes[0]
    assert envelope.payload_ref == f"cas://{binding.artifact_ref.artifact_id}"
    assert envelope.ref.content_hash == binding.content_hash
    assert result.execution.invocation.output_artifacts == [envelope.ref]
    assert result.execution.ledger_event.output_artifacts == [envelope.ref]
    assert envelope.lifecycle_state == "shadow"
    assert envelope.authority_boundary is None
    payload = json.loads(blob)
    assert payload["authority_disposition"] == "candidate_only"
    assert payload["artifacts_index_value"] == result.execution.outcome.state.artifacts_index[
        "causal_report_ref"
    ].model_dump(mode="json")
    manifest = ctx.store.get_manifest(binding.artifact_ref.artifact_id)
    assert manifest.producer is not None
    assert manifest.artifact_schema is not None
    assert str(state.observational_data_ref.artifact_id) in {
        str(ref.artifact_id) for ref in manifest.inputs
    }


@pytest.mark.parametrize("ctx", [None, SimpleNamespace(), SimpleNamespace(store=None)])
def test_conformance_refuses_missing_cas_context(tmp_path, ctx) -> None:
    _, state = _station(tmp_path)
    result = _conformance(_adapter(_node()), ctx, state)
    assert result.passed is False
    assert "semantic_store_missing" in result.failures


class _ChangedPayloadStore(FileSystemCAS):
    def put_json(self, obj, opts, canon_spec=None):
        if isinstance(obj, dict) and obj.get("output_key") == "causal_report_ref":
            obj = deepcopy(obj)
            obj["outcome_status"] = "fabricated-success"
        return super().put_json(obj, opts, canon_spec)


def test_conformance_consults_preservation_on_valid_cas_with_changed_payload(tmp_path) -> None:
    ctx, state = _station(tmp_path, store_type=_ChangedPayloadStore)
    result = _conformance(_adapter(), ctx, state)
    assert result.passed is False
    assert "adapter_preservation_failed:causal_report_ref" in result.failures
    assert ctx.calls == ["execute"]


def test_conformance_rejects_declared_output_with_malformed_ref(tmp_path) -> None:
    class MalformedNode(_FakeNode):
        def execute(self, ctx, state):
            state = state.model_copy(deep=True)
            state.artifacts_index["causal_report_ref"] = {
                "artifact_id": "fake",
                "kind": "ir.causal_report",
            }
            return NodeOutcome(status="ok", state=state)

    ctx, state = _station(tmp_path)
    result = _conformance(_adapter(MalformedNode(_node().spec)), ctx, state)
    assert result.passed is False
    assert "output_state_invalid:ValidationError" in result.failures


def test_conformance_refuses_dangling_input_before_node_execution(tmp_path) -> None:
    ctx, state = _station(tmp_path)
    state.observational_data_ref = ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64),
        kind="ir.observational_data",
        media_type="application/json",
    )
    result = _conformance(_adapter(), ctx, state)
    assert result.passed is False
    assert ctx.calls == []
    assert any(item.startswith("input_reference_invalid:") for item in result.failures)


def test_conformance_refuses_dangling_output_ref_with_all_markers(tmp_path) -> None:
    class DanglingNode(_FakeNode):
        def execute(self, ctx, state):
            state.artifacts_index["causal_report_ref"] = ArtifactRef(
                artifact_id=ArtifactID.model_validate("sha256:" + "2" * 64),
                kind="ir.causal_report",
                media_type="application/json",
            )
            return NodeOutcome(
                status="ok", state=state, artifacts=[state.artifacts_index["causal_report_ref"]]
            )

    ctx, state = _station(tmp_path)
    result = _conformance(_adapter(DanglingNode(_node().spec)), ctx, state)
    assert result.passed is False
    assert any(
        item.startswith("output_reference_invalid:causal_report_ref") for item in result.failures
    )


def test_conformance_resolves_nested_reference_manifest_lineage_before_smoke(tmp_path) -> None:
    ctx, state = _station(tmp_path)
    ref = ctx.store.put_json(
        {"status": "candidate"},
        PutOptions(
            kind="test.child",
            media_type="application/json",
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate("sha256:" + "3" * 64),
                    role="unavailable-parent",
                )
            ],
        ),
    )
    state.params["nested"] = {"values": [ref.model_dump(mode="json")]}
    spec = _node().spec.model_copy(deep=True)
    spec.state_reads.append("params.nested")
    result = _conformance(_adapter(_ProducingNode(spec)), ctx, state)
    assert result.passed is False
    assert ctx.calls == []
    assert any(item.startswith("input_reference_invalid:params.nested") for item in result.failures)


def test_conformance_refuses_contract_that_hides_declared_output(tmp_path) -> None:
    ctx, state = _station(tmp_path)
    adapter = _adapter().model_copy(update={"produced_outputs": []})
    result = _conformance(adapter, ctx, state)
    assert result.passed is False
    assert "adapter_node_contract_mismatch" in result.failures
    assert ctx.calls == []


def test_conformance_refuses_node_spec_changed_by_smoke(tmp_path) -> None:
    class ChangingSpecNode(_ProducingNode):
        def execute(self, ctx, state):
            outcome = super().execute(ctx, state)
            self.spec.produces.append("new_undeclared_output")
            return outcome

    ctx, state = _station(tmp_path)
    result = _conformance(_adapter(ChangingSpecNode(_node().spec)), ctx, state)
    assert result.passed is False
    assert "node_spec_changed_during_smoke" in result.failures
    assert ctx.calls == ["execute"]


def test_conformance_report_write_failure_prevents_admission(tmp_path) -> None:
    class FailingReportStore(FileSystemCAS):
        def put_json(self, obj, opts, canon_spec=None):
            if opts.kind == "gy.adapter_conformance":
                raise OSError("report unavailable")
            return super().put_json(obj, opts, canon_spec)

    ctx, state = _station(tmp_path, store_type=FailingReportStore)
    result = _conformance(_adapter(), ctx, state)
    assert result.passed is False
    assert result.conformance_ref is None
    assert "conformance_persistence_failed:OSError" in result.failures


@pytest.mark.parametrize("side", ["input", "output"])
@pytest.mark.parametrize(
    "variant",
    [name for name, field in ArtifactRef.model_fields.items() if field.is_required()] + ["scalar"],
)
def test_typed_reference_cannot_disappear_by_losing_a_required_field(tmp_path, side, variant):
    ctx, state = _station(tmp_path)
    value = state.observational_data_ref.model_dump(mode="json")
    if variant == "scalar":
        value = "causal_report_ref"
    else:
        del value[variant]

    class InvalidOutput(_FakeNode):
        def execute(self, ctx, state):
            ctx.calls.append("execute")
            state.artifacts_index["causal_report_ref"] = value
            return NodeOutcome(status="ok", state=state)

    if side == "input":
        state.observational_data_ref = value
        node = _ProducingNode(_node().spec)
    else:
        node = InvalidOutput(_node().spec)
    result = _conformance(_adapter(node), ctx, state)
    assert result.passed is False
    assert any(item.startswith(f"{side}_state_invalid:") for item in result.failures)
    assert ctx.calls == ([] if side == "input" else ["execute"])


def test_typed_state_revalidation_preserves_declared_subclass_fields(tmp_path) -> None:
    class ExtendedState(ExperimentState):
        extension_value: int

    ctx, state = _station(tmp_path)
    extended = ExtendedState.model_validate(
        {**state.model_dump(mode="python"), "extension_value": 17}
    )
    result = _conformance(_adapter(), ctx, extended)
    assert result.passed, result.failures
    assert isinstance(result.execution.outcome.state, ExtendedState)
    assert result.execution.outcome.state.extension_value == 17


def test_failed_mutating_smoke_cannot_change_caller_state(tmp_path) -> None:
    class MutatingNonproducer(_FakeNode):
        def execute(self, ctx, state):
            state.params["causal_variables"].append("mutated")
            return NodeOutcome(status="ok", state=state)

    ctx, state = _station(tmp_path)
    before = state.model_dump(mode="json")
    result = _conformance(_adapter(MutatingNonproducer(_node().spec)), ctx, state)
    assert result.passed is False
    assert "output_not_preserved:causal_report_ref" in result.failures
    assert state.model_dump(mode="json") == before
    assert result.execution.outcome.state.params["causal_variables"][-1] == "mutated"


def test_conformance_preservation_failure_cannot_be_replaced_by_declarations(
    tmp_path, monkeypatch
) -> None:
    ctx, state = _station(tmp_path)
    calls = []
    original = adapter_contracts.validate_adapter_preservation

    def reject(**kwargs):
        calls.append(kwargs)
        report = original(**kwargs)
        return replace(report, status="blocked")

    monkeypatch.setattr(adapter_contracts, "validate_adapter_preservation", reject)
    result = _conformance(_adapter(), ctx, state)
    assert result.passed is False
    assert "adapter_preservation_failed:causal_report_ref" in result.failures
    assert calls


def test_legacy_node_adapter_shape_only_counterexample_fails_semantic_preservation(
    tmp_path,
) -> None:
    adapter = ScientistNodeAdapter.from_node(
        _node(),
        operation_id="phase2.estimate.fake",
        operation_class=OperationClass.ESTIMATE,
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
    )
    ctx, state = _station(tmp_path)

    result = scientist_node_adapters.validate_adapter_semantic_preservation(
        adapter,
        ctx=ctx,
        state=state,
        workspace_id="ws-phase2",
        invocation_id="invoke-semantic-counterexample",
    )

    assert result.passed is False
    assert "output_not_preserved:causal_report_ref" in result.failures


# Conditional node fixture: actual source-content readback, candidate authority only.
def _conditional_output_station(tmp_path, *, source_value=False):
    from hashlib import sha256

    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
    from polisyos.scientist.orchestration.engine import (
        NodeOutputDisposition,
        NodeOutputRefusal,
        NodeOutputRule,
        OutputAwareNodeOutcome,
        OutputAwareNodeSpec,
    )

    ctx, state = _station(tmp_path)
    source_ref = ctx.store.put_json(
        {"produce": source_value},
        PutOptions(kind="test.output_source", media_type="application/json"),
    )
    state.inputs["conditional_source_ref"] = source_ref
    base = _node().spec.model_dump(mode="python")
    base["state_reads"] = [*base["state_reads"], "inputs.conditional_source_ref"]
    spec = OutputAwareNodeSpec(
        **base,
        output_rules=(
            NodeOutputRule(
                output_key="causal_report_ref",
                availability="owner_verified_refusal",
                verifier_rule_ref="test.actual_source_projection.v1",
            ),
        ),
    )

    def digest(value):
        return (
            "sha256:"
            + sha256(
                to_canonical_bytes(value.model_dump(mode="json"), CanonSpec(forbid_floats=False))
            ).hexdigest()
        )

    def offered_refusal(input_state):
        return NodeOutputRefusal(
            node_id=str(spec.metadata.component_id),
            output_key="causal_report_ref",
            verifier_rule_ref="test.actual_source_projection.v1",
            reason_code="source_does_not_request_output",
            premise_presence="value",
            input_state_hash=digest(input_state),
            node_spec_hash=digest(spec),
            source_refs=(source_ref,),
            premise={"produce": False},
        )

    class ConditionalNode(_FakeNode):
        def execute(self, ctx, state):
            # Intentionally offers the same marker-rich refusal for both source
            # values. Only the independently consulted readback distinguishes it.
            ctx.calls.append("execute")
            refusal = offered_refusal(state)
            ref = ctx.store.put_json(
                refusal.model_dump(mode="json"),
                PutOptions(kind="scientist.node_output_refusal", media_type="application/json"),
            )
            next_state = state.model_copy(deep=True)
            next_state.artifacts_index.pop("causal_report_ref", None)
            if getattr(ctx, "poison_positive_slot", False):
                next_state.artifacts_index["causal_report_ref"] = ref
            rows = (
                ()
                if getattr(ctx, "drop_disposition", False)
                else (
                    NodeOutputDisposition(
                        output_key="causal_report_ref", disposition="refused", artifact_ref=ref
                    ),
                )
            )
            return OutputAwareNodeOutcome(
                status="ok",
                state=next_state,
                artifacts=[ref],
                output_dispositions=rows,
            )

        def verify_output_dispositions(self, *, ctx, input_state, outcome):
            source = from_canonical_bytes(
                ctx.store.get_bytes(
                    ArtifactRef.model_validate(
                        input_state.inputs["conditional_source_ref"]
                    ).artifact_id
                )
            )
            if not isinstance(source, dict) or source.get("produce") is not False:
                raise ValueError("source_requires_output_or_is_unreadable")
            for row in outcome.output_dispositions:
                actual = NodeOutputRefusal.model_validate(
                    from_canonical_bytes(ctx.store.get_bytes(row.artifact_ref.artifact_id))
                )
                if actual != offered_refusal(input_state):
                    raise ValueError("refusal_content_not_recomputed")

    return ctx, state, ConditionalNode(spec)


def test_conditional_output_adapter_preserves_verified_refusal_as_separate_artifact(tmp_path):
    ctx, state, node = _conditional_output_station(tmp_path)
    result = _conformance(_adapter(node), ctx, state)
    assert result.passed, result.failures
    assert ctx.calls == ["execute"]
    assert "causal_report_ref" not in result.execution.outcome.state.artifacts_index
    assert result.execution.outcome.output_dispositions[0].disposition == "refused"
    assert result.source_output_bindings
    assert result.output_bindings
    assert all(item.authority_boundary is None for item in result.execution.artifact_envelopes)


@pytest.mark.parametrize("source_value", [True, None, "false", {}, []])
def test_conditional_output_adapter_consults_actual_source_premise(tmp_path, source_value):
    ctx, state, node = _conditional_output_station(tmp_path, source_value=source_value)
    result = _conformance(_adapter(node), ctx, state)
    assert result.passed is False
    assert any("source_requires_output_or_is_unreadable" in failure for failure in result.failures)


@pytest.mark.parametrize("mutation", ["poison_positive_slot", "drop_disposition"])
def test_conditional_output_adapter_requires_complete_separate_dispositions(tmp_path, mutation):
    ctx, state, node = _conditional_output_station(tmp_path)
    setattr(ctx, mutation, True)
    result = _conformance(_adapter(node), ctx, state)
    assert result.passed is False
    expected = {
        "poison_positive_slot": "refused_output_positive_slot_present:causal_report_ref",
        "drop_disposition": "output_disposition_population_mismatch",
    }
    assert expected[mutation] in result.failures


def test_output_contract_extension_preserves_ordinary_nodes_and_requires_new_slots():
    from polisyos.scientist.orchestration.engine import NodeOutputRule, OutputAwareNodeSpec

    ordinary = _node().spec
    assert set(ordinary.model_dump()) == {"metadata", "state_reads", "state_writes", "produces"}
    assert NodeOutputRule(output_key="new_artifact_ref").availability == "required"
    payload = ordinary.model_dump(mode="python")
    payload["produces"] = [*payload["produces"], "new_artifact_ref"]
    with pytest.raises(ValueError, match="output_contract_population_mismatch"):
        OutputAwareNodeSpec(
            **payload, output_rules=(NodeOutputRule(output_key="causal_report_ref"),)
        )


def test_output_adapter_turns_malformed_dynamic_ref_into_typed_conformance_failure(tmp_path):
    class MalformedOutput(_FakeNode):
        def execute(self, ctx, state):
            changed = state.model_copy(deep=True)
            changed.artifacts_index["causal_report_ref"] = {"artifact_id": "not-a-valid-address"}
            return NodeOutcome(status="ok", state=changed)

    ctx, state = _station(tmp_path)
    result = _conformance(_adapter(MalformedOutput(_node().spec)), ctx, state)
    assert result.passed is False
    # Typed state validation is earlier than the generic output-ref walker.
    assert "output_state_invalid:ValidationError" in result.failures


def test_output_adapter_revalidates_mutated_complete_rule_schema(tmp_path):
    ctx, state, node = _conditional_output_station(tmp_path)
    original = type(node).execute

    def change_rule(self, ctx, state):
        outcome = original(self, ctx, state)
        object.__setattr__(self.spec.output_rules[0], "availability", "unverified_default")
        return outcome

    type(node).execute = change_rule
    result = _conformance(_adapter(node), ctx, state)
    assert result.passed is False
    assert any(failure.startswith("output_contract_invalid:") for failure in result.failures)
