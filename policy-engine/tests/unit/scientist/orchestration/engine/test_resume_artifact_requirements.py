"""Required external state is checked through native checkpoint and CAS consumers."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeOutcome,
    NodeOutputDisposition,
    NodeOutputRule,
    NodeSpec,
    OutputAwareNodeOutcome,
    OutputAwareNodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _metadata(name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(f"scientist.b71_{name}@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description="B71 native required-artifact consumer",
        capabilities=Capability.SCIENTIST_NODE,
    )


def _options(kind: str) -> PutOptions:
    return PutOptions(
        kind=kind,
        media_type="application/octet-stream",
        producer=ProducerInfo(component="scientist.b71_producer", version="1.0.0"),
    )


class _Producer:
    spec = OutputAwareNodeSpec(
        metadata=_metadata("producer"),
        state_writes=["inputs.required_ref"],
        produces=["required_input"],
        output_rules=(NodeOutputRule(output_key="required_input", availability="required"),),
    )

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        ref = ctx.store.put_bytes(b"B71 required producer bytes", _options("b71.required_input"))
        assert ctx.store.verify(ref).ok
        state.inputs["required_ref"] = ref
        return OutputAwareNodeOutcome(
            status="ok",
            state=state,
            artifacts=[ref],
            output_dispositions=(
                NodeOutputDisposition(
                    output_key="required_input", disposition="produced", artifact_ref=ref
                ),
            ),
        )

    def validate_cache_hit(
        self, ctx: ExecutionContext, state: ExperimentState, cached_outcome: NodeOutcome
    ) -> bool:
        del state
        ref = cached_outcome.state.inputs.get("required_ref")
        return ref is not None and ctx.store.verify(ref).ok


class _Reader:
    spec = NodeSpec(
        metadata=_metadata("reader"),
        state_reads=["inputs.required_ref"],
        state_writes=["reports_index.consumed"],
    )

    def __init__(self, *, stop: bool = False) -> None:
        self.stop = stop
        self.calls = 0
        self.effect_refs: list[ArtifactRef] = []
        self.read_refs: list[ArtifactRef] = []

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        if self.stop:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="b71.stop", message="Stop after native producer completion"),
            )
        # A durable consumer effect makes refusal before dispatch observable;
        # counting calls or inspecting a reference alone would not prove it.
        effect = ctx.store.put_bytes(b"B71 dependent consumer admitted", _options("b71.effect"))
        self.effect_refs.append(effect)
        ref = state.inputs["required_ref"]
        self.read_refs.append(ref)
        assert ctx.store.get_bytes(ref) == b"B71 required producer bytes"
        assert ctx.store.verify(ref).ok
        state.reports_index["consumed"] = effect
        return NodeOutcome(status="ok", state=state, artifacts=[effect])


def _registry(*, stop: bool = False) -> tuple[NodeRegistry, _Producer, _Reader]:
    registry = NodeRegistry()
    producer = _Producer()
    reader = _Reader(stop=stop)
    registry.register(producer)
    registry.register(reader)
    return registry, producer, reader


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="b71_required_artifact",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(alias="producer", node_id=_Producer.spec.metadata.component_id),
            NodeInvocation(
                alias="reader",
                node_id=_Reader.spec.metadata.component_id,
                depends_on=["producer"],
            ),
        ],
    )


def _native_checkpoint(tmp_path: Path) -> tuple[FileSystemCAS, str, ArtifactRef, ArtifactRef]:
    store = FileSystemCAS(tmp_path / "cas")
    run_id = "R_b71_required_artifact"
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("b71"))
    registry, producer, _reader = _registry(stop=True)
    hook = CASCheckpointHook(store=store, run_dir=Path(store.root) / "runs" / run_id)
    first = WorkflowExecutor(ctx, registry, checkpoint_hook=hook).execute(
        _workflow(),
        ExperimentState(run_id=run_id, inputs={"registry_bundle_ref": bundle.bundle_ref}),
    )
    assert first.report.status == "fail"
    assert producer.calls == 1
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint = resolved
    assert store.verify(head.checkpoint_ref).ok
    assert checkpoint.metadata.completed_nodes == ["producer"]
    assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"
    state = ExperimentState.model_validate(checkpoint.state)
    required = state.inputs["required_ref"]
    assert store.get_bytes(required) == b"B71 required producer bytes"
    assert store.verify(required).ok
    return store, run_id, bundle.bundle_ref, required


def test_native_resume_reads_available_required_artifact_without_producer_reexecution(tmp_path):
    store, run_id, bundle, required = _native_checkpoint(tmp_path)
    reopened = FileSystemCAS(store.root)
    registry, producer, reader = _registry()
    result = resume_from_checkpoint(
        reopened, run_id, workflow=_workflow(), registry=registry, registry_bundle_ref=bundle
    )
    assert result.report.status == "ok"
    assert [node.alias for node in result.report.nodes] == ["reader"]
    assert producer.calls == 0
    assert reader.read_refs == [required]
    assert len(reader.effect_refs) == 1
    assert reopened.verify(reader.effect_refs[0]).ok
    assert reopened.get_bytes(result.state.reports_index["consumed"]) == (
        b"B71 dependent consumer admitted"
    )


def test_missing_required_blob_refuses_resume_before_dependent_cas_effect(tmp_path):
    store, run_id, bundle, required = _native_checkpoint(tmp_path)
    store._paths(required.artifact_id)[0].unlink()
    reopened = FileSystemCAS(store.root)
    assert not reopened.verify(required).ok
    registry, producer, reader = _registry()
    with pytest.raises(CheckpointCorruptedError, match=r"inputs\.required_ref"):
        resume_from_checkpoint(
            reopened, run_id, workflow=_workflow(), registry=registry, registry_bundle_ref=bundle
        )
    assert producer.calls == reader.calls == 0
    assert reader.effect_refs == reader.read_refs == []


def test_allow_replay_repairs_required_blob_before_real_consumer_read(tmp_path):
    store, run_id, bundle, required = _native_checkpoint(tmp_path)
    store._paths(required.artifact_id)[0].unlink()
    reopened = FileSystemCAS(store.root)
    assert not reopened.verify(required).ok
    registry, producer, reader = _registry()
    result = resume_from_checkpoint(
        reopened,
        run_id,
        workflow=_workflow(),
        registry=registry,
        registry_bundle_ref=bundle,
        resume_strategy="allow_replay",
    )
    assert result.report.status == "ok"
    assert [node.alias for node in result.report.nodes] == ["producer", "reader"]
    assert producer.calls == 1
    assert reader.calls == 1
    assert reader.read_refs == [required]
    assert reopened.verify(required).ok
    assert reopened.get_bytes(required) == b"B71 required producer bytes"
    assert reopened.verify(reader.effect_refs[0]).ok
