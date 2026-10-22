from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.artifacts.lineage import ArtifactLineageGraph
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel.constraints import ConstraintRegistry
from polisyos.ir.kernel.mechanisms import MechanismTypeRegistry, MechanismTypeSpec
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.metrics import DEFAULT_METRIC_REGISTRY
from polisyos.ir.kernel.selector_fields import DEFAULT_SELECTOR_FIELD_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.kernel.units import DEFAULT_UNITS_REGISTRY, MoneyUnit, UnitsRegistry
from polisyos.ir.linker import LinkedTrinityBundle
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.observation.causal_execution import BoundsEstimationEntry, CausalExecutionBundle
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.ir.passes import (
    ArtifactRefTypeCheckResult,
    CrossModelTypeCheckPass,
    PassContext,
    PassPipeline,
    PassResult,
    RegistryDependencyPass,
    SlotMechanismReachability,
    SlotMechanismReachabilityPass,
    TrinityLinkAnalysisPass,
    UnusedArtifactAnalysisPass,
    UnusedArtifactAnalysisResult,
)
from polisyos.ir.registry.refs import BoundsBundleRef
from polisyos.ir.registry.registry_fragments import (
    ComposePolicy,
    RegistryBundle,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
)
from polisyos.ir.trinity import TrinityBundle

if TYPE_CHECKING:
    from pathlib import Path


class _ManifestOnlyReader:
    def __init__(self, manifests: dict[str, object]) -> None:
        self._manifests = manifests

    def get_manifest(self, artifact_id: object) -> object:
        return self._manifests.get(str(artifact_id))


def _units_fragment(fragment_id: str) -> UnitsFragment:
    return UnitsFragment(
        meta=RegistryFragmentMeta(
            fragment_id=fragment_id,
            namespace="tests",
        ),
        payload=UnitsRegistry(units={"usd": MoneyUnit(currency="USD")}),
    )


def _base_bundle(kind: str) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_phase2", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_phase2",
            interventions=[
                InterventionSpec(
                    intervention_id="intervention_phase2",
                    kind=kind,
                    target=SelectorPredicate(field="id", operator="==", value="all"),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_phase2",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )


def _registry_request(*, mechanism_writes: list[str]) -> RegistryComposeRequest:
    registries = RegistryBundle(
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        mechanisms=MechanismTypeRegistry(
            mechanisms={
                "custom": MechanismTypeSpec(
                    mechanism_id="custom",
                    writes_slots=mechanism_writes,
                ),
                "queue": MechanismTypeSpec(mechanism_id="queue"),
            }
        ),
        slots=DEFAULT_SLOT_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )
    return RegistryComposeRequest(
        fragments=[_units_fragment("units.phase2")],
        base_registries=registries,
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )


class CountingLinkPass(TrinityLinkAnalysisPass):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def run(self, context: PassContext) -> PassResult:
        self.calls += 1
        return super().run(context)


def test_pipeline_caches_link_analysis_and_invalidates_on_registry_change() -> None:
    link_pass = CountingLinkPass()
    pipeline = PassPipeline(
        [
            RegistryDependencyPass(),
            link_pass,
        ]
    )
    context = (
        PassContext()
        .with_surface(
            "registry_compose_request",
            _registry_request(mechanism_writes=["global.tax_rate"]),
        )
        .with_surface("trinity_bundle", _base_bundle("custom"))
    )

    first = pipeline.run(context)
    second = pipeline.run(context)

    assert link_pass.calls == 1
    assert first.require("link_report") == second.require("link_report")

    changed_context = context.with_surface(
        "registry_compose_request",
        _registry_request(mechanism_writes=["agents.income"]),
    )
    third = pipeline.run(changed_context)

    assert link_pass.calls == 2
    linked_bundle = third.require_as("linked_trinity_bundle", LinkedTrinityBundle)
    assert linked_bundle.bindings.used_slots_write == ["agents.income"]


def test_slot_mechanism_reachability_flags_orphan_mechanisms() -> None:
    pipeline = PassPipeline(
        [
            RegistryDependencyPass(),
            TrinityLinkAnalysisPass(),
            SlotMechanismReachabilityPass(),
        ]
    )
    context = (
        PassContext()
        .with_surface(
            "registry_compose_request",
            _registry_request(mechanism_writes=["global.tax_rate"]),
        )
        .with_surface("trinity_bundle", _base_bundle("queue"))
    )

    result = pipeline.run(context)
    reachability = result.require_as(
        "slot_mechanism_reachability",
        SlotMechanismReachability,
    )

    assert reachability.orphan_mechanisms == ["queue"]
    assert any(diagnostic.code == "orphan_mechanism" for diagnostic in result.diagnostics)


def test_pass_context_require_as_rejects_untyped_surface_values() -> None:
    context = PassContext().with_surface("link_report", {"ok": True})

    with pytest.raises(TypeError, match="PassContext value 'link_report'"):
        context.require_as("link_report", LinkedTrinityBundle)


def test_slot_mechanism_reachability_rejects_non_linked_bundle() -> None:
    context = PassContext().with_surface(
        "linked_trinity_bundle",
        {"bindings": {}},
    )

    with pytest.raises(TypeError, match="LinkedTrinityBundle"):
        SlotMechanismReachabilityPass().run(context)


def test_cross_model_type_check_and_unused_artifact_analysis_cover_execution_outputs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    upstream_ref = put_json_artifact(
        _ensure_ir_artifact_store(store),
        {"rows": 1},
        kind="test.upstream",
        schema_name="test.upstream",
        schema_version="1.0",
    )
    used_ref = put_json_artifact(
        _ensure_ir_artifact_store(store),
        {"rows": 2},
        kind="ir.bounds_bundle",
        schema_name="ir.bounds_bundle",
        schema_version="1.0",
        inputs=[{"artifact_id": upstream_ref["artifact_id"], "role": "upstream"}],
    )
    unused_ref = put_json_artifact(
        _ensure_ir_artifact_store(store),
        {"rows": 3},
        kind="ir.bounds_bundle",
        schema_name="ir.bounds_bundle",
        schema_version="1.0",
    )
    execution_bundle = CausalExecutionBundle(
        bounds_results=[
            BoundsEstimationEntry(
                task_id="task.bounds",
                family=ObservationFamily.LABOR_MARKET,
                status="ok",
                interval=(0.1, 0.5),
                informative=True,
                bounds_bundle_ref=BoundsBundleRef.model_validate(used_ref),
            )
        ]
    )
    bad_execution_bundle = CausalExecutionBundle(
        bounds_results=[
            BoundsEstimationEntry(
                task_id="task.missing",
                family=ObservationFamily.LABOR_MARKET,
                status="blocked",
                bounds_bundle_ref=BoundsBundleRef(
                    artifact_id="sha256:" + "f" * 64,
                ),
            )
        ]
    )

    pipeline = PassPipeline(
        [
            CrossModelTypeCheckPass(),
            UnusedArtifactAnalysisPass(),
        ]
    )
    context = (
        PassContext()
        .with_surface("artifact_store", ensure_ir_artifact_store(store))
        .with_surface(
            "artifact_ids",
            [
                used_ref["artifact_id"],
                upstream_ref["artifact_id"],
                unused_ref["artifact_id"],
            ],
        )
        .with_surface("artifact_task_bindings", execution_bundle.artifact_task_bindings())
        .with_surface("causal_execution_bundle", execution_bundle)
    )
    result = pipeline.run(context)

    cross_model_result = result.require_as(
        "cross_model_type_check",
        ArtifactRefTypeCheckResult,
    )
    lineage_graph = result.require_as("artifact_lineage_graph", ArtifactLineageGraph)
    unused_result = result.require_as(
        "unused_artifact_analysis",
        UnusedArtifactAnalysisResult,
    )
    assert cross_model_result.missing_ref_count == 0
    assert lineage_graph.produced_by(used_ref["artifact_id"]) == ("task.bounds",)
    assert lineage_graph.derived_from(used_ref["artifact_id"]) == (upstream_ref["artifact_id"],)
    assert unused_result.unused_artifact_ids == [unused_ref["artifact_id"]]

    ir_store = ensure_ir_artifact_store(store)
    manifest_only_reader = _ManifestOnlyReader(
        {
            str(ref["artifact_id"]): ir_store.get_manifest(ref["artifact_id"])
            for ref in (upstream_ref, used_ref, unused_ref)
        }
    )
    assert not hasattr(manifest_only_reader, "put_json")
    assert not hasattr(manifest_only_reader, "iter_artifact_ids")
    reader_result = PassPipeline([UnusedArtifactAnalysisPass()]).run(
        context.with_surface("artifact_store", manifest_only_reader).with_surface(
            "root_artifact_ids",
            [unused_ref["artifact_id"]],
        )
    )
    reader_lineage = reader_result.require_as("artifact_lineage_graph", ArtifactLineageGraph)
    reader_unused = reader_result.require_as(
        "unused_artifact_analysis",
        UnusedArtifactAnalysisResult,
    )
    assert reader_lineage.derived_from(used_ref["artifact_id"]) == (upstream_ref["artifact_id"],)
    assert reader_unused.used_artifact_ids == [str(unused_ref["artifact_id"])]
    assert reader_unused.unused_artifact_ids == sorted(
        {str(upstream_ref["artifact_id"]), str(used_ref["artifact_id"])}
    )

    with pytest.raises(
        TypeError,
        match="must be ArtifactLineageGraph; received ArtifactRefTypeCheckResult",
    ):
        result.require_as("cross_model_type_check", ArtifactLineageGraph)
    explicit_root_result = pipeline.run(
        context.with_surface("root_artifact_ids", (unused_ref["artifact_id"],))
    )
    explicit_root_analysis = explicit_root_result.require_as(
        "unused_artifact_analysis",
        UnusedArtifactAnalysisResult,
    )
    assert explicit_root_analysis.root_artifact_ids == [str(unused_ref["artifact_id"])]
    assert explicit_root_analysis.used_artifact_ids == [str(unused_ref["artifact_id"])]
    assert explicit_root_analysis.unused_artifact_ids == sorted(
        {str(upstream_ref["artifact_id"]), str(used_ref["artifact_id"])}
    )

    empty_root_sets: tuple[list[str] | tuple[object, ...], ...] = ([], ())
    for empty_roots in empty_root_sets:
        empty_root_result = pipeline.run(context.with_surface("root_artifact_ids", empty_roots))
        empty_root_analysis = empty_root_result.require_as(
            "unused_artifact_analysis",
            UnusedArtifactAnalysisResult,
        )
        assert empty_root_analysis.root_artifact_ids == [str(used_ref["artifact_id"])]
        assert empty_root_analysis.used_artifact_ids == sorted(
            {
                str(upstream_ref["artifact_id"]),
                str(used_ref["artifact_id"]),
            }
        )
        assert empty_root_analysis.unused_artifact_ids == [str(unused_ref["artifact_id"])]

    empty_generator_result = pipeline.run(context.with_surface("root_artifact_ids", iter(())))
    empty_generator_analysis = empty_generator_result.require_as(
        "unused_artifact_analysis",
        UnusedArtifactAnalysisResult,
    )
    assert empty_generator_analysis.root_artifact_ids == []
    assert empty_generator_analysis.used_artifact_ids == []
    assert empty_generator_analysis.unused_artifact_ids == sorted(
        {
            str(upstream_ref["artifact_id"]),
            str(used_ref["artifact_id"]),
            str(unused_ref["artifact_id"]),
        }
    )

    bad_result = pipeline.run(
        PassContext()
        .with_surface("artifact_store", ensure_ir_artifact_store(store))
        .with_surface("causal_execution_bundle", bad_execution_bundle)
    )
    bad_cross_model_result = bad_result.require_as(
        "cross_model_type_check",
        ArtifactRefTypeCheckResult,
    )
    assert bad_cross_model_result.missing_ref_count == 1
    assert any(diagnostic.code == "artifact_ref_missing" for diagnostic in bad_result.diagnostics)

    unused_pass = UnusedArtifactAnalysisPass()
    with pytest.raises(TypeError, match="artifact_ids must be an iterable"):
        unused_pass.run(context.with_surface("artifact_ids", 42))
    with pytest.raises(TypeError, match="root_artifact_ids must be an iterable"):
        unused_pass.run(context.with_surface("root_artifact_ids", str(unused_ref["artifact_id"])))
    for malformed_roots in (0, False, ""):
        with pytest.raises(TypeError, match="root_artifact_ids must be an iterable"):
            unused_pass.run(context.with_surface("root_artifact_ids", malformed_roots))
    with pytest.raises(
        TypeError,
        match="must provide a callable get_manifest method",
    ):
        unused_pass.run(PassContext().with_surface("artifact_store", object()))
    noncallable_reader = type("_NonCallableManifestReader", (), {"get_manifest": 0})()
    with pytest.raises(
        TypeError,
        match="must provide a callable get_manifest method",
    ):
        unused_pass.run(context.with_surface("artifact_store", noncallable_reader))
