"""Behavioral compiler artifacts and Scientist consumer compatibility checks."""

from __future__ import annotations

import logging
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

import polisyos.foundry as foundry
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.foundry import FoundryCompileConfig, ProgramGraph
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.compile.randomization import TreasuryPlan
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.kernel.slots import SlotLayout
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _context_and_state(root: Path) -> tuple[ExecutionContext, ExperimentState]:
    store = FileSystemCAS(root)
    registry = build_default_registry_bundle(store)
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="compile_contract", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="compile_contract",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target={"kind": "predicate", "field": "id", "operator": "==", "value": "all"},
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="compile_contract",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )
    run = RunContext.start(
        store=store, registry_bundle=registry.bundle_ref, run_id="compile_contract"
    )
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(__name__),
        foundry=foundry,
    )
    return context, ExperimentState(
        run_id="compile_contract",
        inputs={"trinity_bundle_ref": policy_ref, "registry_bundle_ref": registry.bundle_ref},
    )


def _assert_persisted_contracts(store: FileSystemCAS, state: ExperimentState) -> None:
    report_ref = state.reports_index["compile_report_ref"]
    report = CompileReport.model_validate(from_canonical_bytes(store.get_bytes(report_ref)))
    assert report.ok
    treasury_ref = state.artifacts_index["treasury_plan_ref"]
    layout_ref = state.artifacts_index["slot_layout_ref"]
    program_ref = state.artifacts_index["program_graph_ref"]
    assert report.treasury_plan_ref == treasury_ref
    assert report.slot_layout_ref == layout_ref

    graph = ProgramGraph.model_validate(from_canonical_bytes(store.get_bytes(program_ref)))
    treasury = TreasuryPlan.model_validate(from_canonical_bytes(store.get_bytes(treasury_ref)))
    # The compiler historically uses root_seed=0. This does not establish a runtime salt consumer.
    assert treasury.root_seed == 0
    assert treasury.node_salts == {
        node.node_id: int(sha256(f"node:{node.node_id}".encode()).hexdigest()[:16], 16)
        for node in graph.nodes
    }
    assert treasury.stream_salts == {"default": int(sha256(b"stream:default").hexdigest()[:16], 16)}
    layout = SlotLayout.model_validate(from_canonical_bytes(store.get_bytes(layout_ref)))
    assert layout.layout["agents.income"] == "agents.income"
    assert layout.layout["government.balance"] == "government_balance"

    for ref in (treasury_ref, layout_ref):
        manifest = store.get_manifest(ref)
        assert any(
            item.role == "program_graph" and item.artifact_id == program_ref.artifact_id
            for item in manifest.inputs
        )
    report_inputs = store.get_manifest(report_ref).inputs
    for role, ref in (("treasury_plan", treasury_ref), ("slot_layout", layout_ref)):
        assert any(
            item.role == role and item.artifact_id == ref.artifact_id for item in report_inputs
        )


def test_native_compile_artifacts_survive_scientist_consumer_and_cas_reopen(tmp_path: Path) -> None:
    """The real compiler output reaches Scientist state and persisted readback."""
    context, initial = _context_and_state(tmp_path / "cas")
    node = CompileFoundryNode(compile_config=FoundryCompileConfig(random_seed=17))
    first = node.execute(context, initial)
    repeated = node.execute(context, initial)

    assert first.status == repeated.status == "ok"
    assert initial.artifacts_index == initial.reports_index == {}
    reopened = FileSystemCAS(tmp_path / "cas")
    _assert_persisted_contracts(reopened, first.state)
    for key in ("treasury_plan_ref", "slot_layout_ref", "program_graph_ref", "exec_plan_ref"):
        assert first.state.artifacts_index[key] == repeated.state.artifacts_index[key]


@pytest.mark.parametrize("artifact", ["treasury", "layout"])
def test_compiler_artifact_contract_rejects_same_shape_missing_property(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    """A compiler PASS with a valid DTO still fails the content-level discriminator."""
    from polisyos.foundry.compile import trinity_compiler

    context, initial = _context_and_state(tmp_path / "cas")
    if artifact == "treasury":
        monkeypatch.setattr(trinity_compiler, "build_treasury_plan", lambda _graph: TreasuryPlan())
    else:
        monkeypatch.setattr(trinity_compiler, "build_slot_layout", lambda _registry: SlotLayout())
    outcome = CompileFoundryNode().execute(context, initial)
    assert outcome.status == "ok"
    assert outcome.state.artifacts_index["treasury_plan_ref"].kind == "foundry.treasury_plan"
    assert outcome.state.artifacts_index["slot_layout_ref"].kind == "foundry.slot_layout"
    with pytest.raises((AssertionError, KeyError)):
        _assert_persisted_contracts(FileSystemCAS(tmp_path / "cas"), outcome.state)


def test_compile_consumer_retains_persisted_failure_for_malformed_trinity(tmp_path: Path) -> None:
    """A supplied invalid artifact cannot produce successful compile-derived state."""
    context, initial = _context_and_state(tmp_path / "cas")
    malformed_ref: ArtifactRef = context.store.put_json(
        {"schema_version": "0.1", "policy_spec": {}},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
    )
    initial.inputs["trinity_bundle_ref"] = malformed_ref
    outcome = CompileFoundryNode().execute(context, initial)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "foundry.compile_failed"
    assert outcome.state.artifacts_index == {}
    report = CompileReport.model_validate(
        from_canonical_bytes(
            context.store.get_bytes(outcome.state.reports_index["compile_report_ref"])
        )
    )
    assert report.ok is False
    assert report.policy_ref == malformed_ref
    assert any("ValidationError" in note for note in report.notes)
