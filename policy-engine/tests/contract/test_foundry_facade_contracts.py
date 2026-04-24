from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecPlanRef,
    ExecuteRequest,
    ExecuteResult,
    FoundryCompileConfig,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    FoundryValidationFlags,
    MetricsRef,
    ObservedRange,
    ObservedRangeBundle,
    ObservedRangeBundleRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
    WelfareBoundReport,
    WelfareBoundReportRef,
)


def _dummy_ref(kind: str, media_type: str = "application/json") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind=kind,
        media_type=media_type,
    )


def test_compile_request_canonical() -> None:
    req = CompileRequest(
        input_kind="trinity",
        policy_ref=_dummy_ref("ir.trinity_bundle"),
        registry_bundle_ref=_dummy_ref("core.registry_bundle"),
        compile_config=FoundryCompileConfig(),
        validation_flags=FoundryValidationFlags(),
    )
    to_canonical_bytes(req)


def test_compile_result_canonical() -> None:
    result = CompileResult(
        ok=True,
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("1" * 64)),
        compile_report_ref=_dummy_ref("compiler.compile_report"),
        derived_refs=[
            DerivedArtifact(role="program_graph", ref=_dummy_ref("foundry.program_graph"))
        ],
    )
    to_canonical_bytes(result)


def test_execute_request_canonical() -> None:
    req = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("3" * 64)
        ),
        registry_bundle_ref=_dummy_ref("core.registry_bundle"),
        exec_config=FoundryExecConfig(),
    )
    to_canonical_bytes(req)


def test_execute_request_with_observed_range_bundle_canonical() -> None:
    req = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("3" * 64)
        ),
        observed_range_bundle_ref=ObservedRangeBundleRef(
            artifact_id=ArtifactID.from_sha256_hex("5" * 64)
        ),
        welfare_bound_mode="both",
        welfare_bound_required=True,
    )
    to_canonical_bytes(req)


def test_execute_result_canonical() -> None:
    result = ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=ArtifactID.from_sha256_hex("4" * 64)),
        derived_refs=[DerivedArtifact(role="metrics", ref=_dummy_ref("foundry.metrics"))],
    )
    to_canonical_bytes(result)


def test_welfare_bound_sidecar_models_canonical() -> None:
    bundle = ObservedRangeBundle(
        ranges={
            "income_tax.eti_effective": ObservedRange(lower=0.1, upper=0.3),
        }
    )
    report = WelfareBoundReport(
        mechanism_type="income_tax",
        node_id="node_a",
        welfare_loss_lower=1.0,
        welfare_loss_upper=2.0,
        required_observables=("income_tax.eti_effective",),
        status="ok",
    )
    spec = CanonSpec(forbid_floats=False)
    to_canonical_bytes(bundle, spec=spec)
    to_canonical_bytes(report, spec=spec)


def test_simulation_result_with_welfare_bound_refs_canonical() -> None:
    result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        metrics_ref=MetricsRef(artifact_id=ArtifactID.from_sha256_hex("6" * 64)),
        state_snapshot_ref=StateSnapshotRef(artifact_id=ArtifactID.from_sha256_hex("7" * 64)),
        welfare_bound_refs={
            "node_a": WelfareBoundReportRef(artifact_id=ArtifactID.from_sha256_hex("8" * 64))
        },
    )
    to_canonical_bytes(result)
