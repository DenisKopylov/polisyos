from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import put_json_artifact
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
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.observation.causal_execution import BoundsEstimationEntry, CausalExecutionBundle
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.ir.passes import (
    CrossModelTypeCheckPass,
    PassContext,
    PassPipeline,
    RegistryDependencyPass,
    SlotMechanismReachabilityPass,
    TrinityLinkAnalysisPass,
    UnusedArtifactAnalysisPass,
)
from polisyos.ir.refs import BoundsBundleRef
from polisyos.ir.registry_fragments import (
    ComposePolicy,
    RegistryBundle,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
)
from polisyos.ir.trinity import TrinityBundle

if TYPE_CHECKING:
    from pathlib import Path


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

    def run(self, context: PassContext):  # type: ignore[override]
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
    assert third.require("linked_trinity_bundle").bindings.used_slots_write == ["agents.income"]


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
    reachability = result.require("slot_mechanism_reachability")

    assert reachability.orphan_mechanisms == ["queue"]
    assert any(diagnostic.code == "orphan_mechanism" for diagnostic in result.diagnostics)


def test_cross_model_type_check_and_unused_artifact_analysis_cover_execution_outputs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    upstream_ref = put_json_artifact(
        store,
        {"rows": 1},
        kind="test.upstream",
        schema_name="test.upstream",
        schema_version="1.0",
    )
    used_ref = put_json_artifact(
        store,
        {"rows": 2},
        kind="ir.bounds_bundle",
        schema_name="ir.bounds_bundle",
        schema_version="1.0",
        inputs=[{"artifact_id": upstream_ref["artifact_id"], "role": "upstream"}],
    )
    unused_ref = put_json_artifact(
        store,
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
        .with_surface("artifact_store", store)
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

    assert result.require("cross_model_type_check").missing_ref_count == 0
    assert result.require("artifact_lineage_graph").produced_by(used_ref["artifact_id"]) == (
        "task.bounds",
    )
    assert result.require("artifact_lineage_graph").derived_from(used_ref["artifact_id"]) == (
        upstream_ref["artifact_id"],
    )
    assert result.require("unused_artifact_analysis").unused_artifact_ids == [
        unused_ref["artifact_id"]
    ]

    bad_result = pipeline.run(
        PassContext()
        .with_surface("artifact_store", store)
        .with_surface("causal_execution_bundle", bad_execution_bundle)
    )
    assert bad_result.require("cross_model_type_check").missing_ref_count == 1
    assert any(diagnostic.code == "artifact_ref_missing" for diagnostic in bad_result.diagnostics)
