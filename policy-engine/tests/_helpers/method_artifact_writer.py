"""Exercise the real sidecar kernel; do not attest method execution or readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.artifacts.signing import SigningConfig
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MethodExecutionOccurrence,
    MethodMetricBindingSetRef,
    ProgramGraphRef,
)
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.execute._internal.graph import (
    _capture_method_artifacts,
    _planned_method_dispatch,
)
from polisyos.foundry.execute._internal.models import MethodExecutionCapture
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import ComputeBackend


def local_store(root: Path) -> FileSystemCAS:
    """Caller disables optional telemetry before constructing this real backend."""
    return FileSystemCAS(
        root, signing_config=SigningConfig(enabled=False), ownership_enforced=False
    )


def capture_fixture(
    store: FileSystemCAS,
    codec: Literal["legacy", "bounded_v3"] = "bounded_v3",
) -> tuple[MethodExecutionCapture, MethodExecutionOccurrence]:
    refs = []
    for model, kind in (
        (ProgramGraphRef, "foundry.program_graph"),
        (ExecPlanRef, "foundry.exec_plan"),
        (MethodMetricBindingSetRef, "foundry.method_metric_binding_set"),
    ):
        ref = store.put_json(
            {"fixture": kind},
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )
        refs.append(model.model_validate(ref.model_dump(mode="python")))
    capture = MethodExecutionCapture(
        program_graph_ref=refs[0],
        exec_plan_ref=refs[1],
        method_metric_binding_set_ref=refs[2],
        artifact_output_codec=codec,
    )
    occurrence = MethodExecutionOccurrence(
        occurrence_id="inv:0:node",
        invocation_id="inv",
        plan_index=0,
        node_id="node",
        node_kind="method",
        status="planned",
        method_fqn="fixture.sidecar_kernel",
        dispatch=_planned_method_dispatch(
            node=None,
            method_class=None,
            method_identity={},
            metric_input_capture_required=False,
        ),
    )
    return capture, occurrence


def produce(
    store: FileSystemCAS,
    capture: MethodExecutionCapture,
    occurrence: MethodExecutionOccurrence,
    artifacts: dict[str, Any],
) -> Any:
    result = MethodResult(
        output={},
        timing=MethodTiming(wall_time_ms=0.0),
        reproducibility=ReproducibilityInfo(
            backend=ComputeBackend.NUMPY,
            determinism_tier=DeterminismTier.STRICT_CPU,
        ),
        artifacts=artifacts,
    )
    return _capture_method_artifacts(
        store, capture=capture, occurrence=occurrence, method_result=result
    )


def cas_content(root: Path) -> dict[str, bytes]:
    """Snapshot durable content, excluding transaction lock bookkeeping."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and (path.suffix in {".blob", ".json", ".sig"} or "intent" in path.name)
    }


def selected_ref(rows: Any) -> ArtifactRef:
    assert rows[1:] == ("captured", None, 1, 32)
    assert len(rows[0]) == 1 and rows[0][0].status == "captured"
    ref = rows[0][0].artifact_ref
    assert isinstance(ref, ArtifactRef)
    return ref


def raw_identity(value: Any) -> Any:
    """Independent exact JSON value/type oracle, including signed float identity."""
    if type(value) is dict:
        return (dict, tuple((key, raw_identity(item)) for key, item in sorted(value.items())))
    if type(value) is list:
        return (list, tuple(raw_identity(item) for item in value))
    if type(value) is float:
        return (float, value.hex())
    return (type(value), value)
