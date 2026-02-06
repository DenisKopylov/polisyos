from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecuteRequest,
    ExecuteResult,
    ExecPlanRef,
    FoundryCompileConfig,
    FoundryExecConfig,
    FoundryValidationFlags,
    SimulationResultRef,
    StateSnapshotRef,
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
        state_snapshot_ref=StateSnapshotRef(artifact_id=ArtifactID.from_sha256_hex("3" * 64)),
        registry_bundle_ref=_dummy_ref("core.registry_bundle"),
        exec_config=FoundryExecConfig(),
    )
    to_canonical_bytes(req)


def test_execute_result_canonical() -> None:
    result = ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(
            artifact_id=ArtifactID.from_sha256_hex("4" * 64)
        ),
        derived_refs=[DerivedArtifact(role="metrics", ref=_dummy_ref("foundry.metrics"))],
    )
    to_canonical_bytes(result)
