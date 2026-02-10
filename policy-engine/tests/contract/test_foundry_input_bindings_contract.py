from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    ExecPlanRef,
    FoundryInputBindingRule,
    FoundryInputBindingTransform,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundryInputBindingReportRef,
    StateSnapshotRef,
)


def _ref(kind: str, suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(suffix * 64),
        kind=kind,
        media_type="application/json",
    )


def test_foundry_input_bindings_contract_is_canonical() -> None:
    bindings = FoundryInputBindings(
        data_snapshot_ref=_ref("fabric.data_snapshot", "1"),
        registry_bundle_ref=_ref("core.registry_bundle", "2"),
        rules=[
            FoundryInputBindingRule(
                binding_id="bind_agents_income",
                source_path="agents.income",
                target_slot_id="agents.income",
                transforms=[
                    FoundryInputBindingTransform(op="to_decimal"),
                    FoundryInputBindingTransform(op="round", params={"digits": 6}),
                ],
            )
        ],
        bound_state_snapshot_ref=StateSnapshotRef(
            artifact_id=ArtifactID.from_sha256_hex("3" * 64)
        ),
        quality_report_ref=_ref("fabric.quality_report", "4"),
    )
    to_canonical_bytes(bindings)


def test_execute_request_supports_input_bindings_ref() -> None:
    request = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("5" * 64)),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("6" * 64)
        ),
        registry_bundle_ref=_ref("core.registry_bundle", "7"),
    )
    to_canonical_bytes(request)


def test_data_snapshot_supports_quality_and_binding_links() -> None:
    snapshot = DataSnapshot(
        data_ref=StateSnapshotRef(artifact_id=ArtifactID.from_sha256_hex("8" * 64)),
        quality_report_ref=_ref("fabric.quality_report", "9"),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("a" * 64)
        ),
    )
    to_canonical_bytes(snapshot)


def test_input_binding_report_ref_is_typed() -> None:
    ref = FoundryInputBindingReportRef(artifact_id=ArtifactID.from_sha256_hex("b" * 64))
    assert ref.kind == "foundry.input_binding_report"
