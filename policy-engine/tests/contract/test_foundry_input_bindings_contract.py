from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryInputBindingReportRef,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundryInputBindingTransform,
    StateSnapshotRef,
)
from polisyos.core.contracts.semantic_input_binding import (
    RESOLVED_INPUT_BINDING_MANIFEST_ROLE,
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    ResolvedMeasurementInput,
    load_resolved_input_binding_manifest,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrenceRef,
    SelectedVariableBindingRef,
)
from polisyos.foundry.data_plane.bindings import (
    load_input_bindings,
    reconcile_semantic_input_bindings,
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
        bound_state_snapshot_ref=StateSnapshotRef(artifact_id=ArtifactID.from_sha256_hex("3" * 64)),
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


def _selected_ref(kind: str, suffix: str) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef(
        artifact_id=ArtifactID.from_sha256_hex(suffix * 64),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{'9' * 64}",
    )


def _binding_fields() -> dict[str, object]:
    return {
        "data_snapshot_ref": _selected_ref("fabric.data_snapshot", "1").model_dump(),
        "registry_bundle_ref": _selected_ref("core.registry_bundle", "2").model_dump(),
        "bound_state_snapshot_ref": StateSnapshotRef.model_validate(
            _selected_ref("foundry.state_snapshot", "3").model_dump()
        ),
    }


@pytest.mark.parametrize(
    ("version", "legacy_digest"),
    [
        ("1.0", "0803a581ec08935a25950a0b249c13001f9f94273c6bc39a096982fd9be83568"),
        ("1.1", "7c45aa55449bbfe11743c12a55a5275c3c0ae03a751c8a5b4d08f8f73a28ae7a"),
    ],
)
def test_legacy_binding_versions_keep_exact_payload_bytes(
    tmp_path: Path, version: str, legacy_digest: str
) -> None:
    fields = _binding_fields()
    fields["schema_version"] = version
    if version == "1.1":
        fields["registered_sql_admission_ref"] = _selected_ref(
            RegisteredSQLAdmissionBinding.ARTIFACT_KIND, "4"
        ).model_dump()
    bindings = FoundryInputBindings.model_validate(fields)
    assert hashlib.sha256(to_canonical_bytes(bindings)).hexdigest() == legacy_digest

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        bindings,
        PutOptions(
            kind=bindings.ARTIFACT_KIND,
            media_type=bindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=bindings.ARTIFACT_SCHEMA_NAME, version=version),
        ),
        return_selected_profile=True,
    )
    assert ref.artifact_id.hex == legacy_digest
    assert to_canonical_bytes(load_input_bindings(store, ref)) == to_canonical_bytes(bindings)


@pytest.mark.parametrize("version", ["1.0", "1.1", "1.2", "1.3"])
@pytest.mark.parametrize("has_sql", [False, True])
@pytest.mark.parametrize("has_semantic", [False, True])
def test_foundry_binding_has_explicit_semantic_sql_version_matrix(
    version: str, has_sql: bool, has_semantic: bool
) -> None:
    fields = _binding_fields()
    fields["schema_version"] = version
    if has_sql:
        fields["registered_sql_admission_ref"] = _selected_ref(
            RegisteredSQLAdmissionBinding.ARTIFACT_KIND, "4"
        ).model_dump()
    if has_semantic:
        fields["resolved_binding_manifest_ref"] = ResolvedInputBindingManifestRef.model_validate(
            _selected_ref(ResolvedInputBindingManifest.ARTIFACT_KIND, "5").model_dump()
        )
    if (has_sql, has_semantic) != (version in {"1.1", "1.3"}, version in {"1.2", "1.3"}):
        with pytest.raises(ValidationError, match="foundry_input_bindings_"):
            FoundryInputBindings.model_validate(fields)
        return
    loaded = FoundryInputBindings.model_validate(fields)
    assert ("resolved_binding_manifest_ref" in loaded.model_dump()) is has_semantic
    assert ("registered_sql_admission_ref" in loaded.model_dump()) is has_sql


def _manifest() -> ResolvedInputBindingManifest:
    return ResolvedInputBindingManifest(
        data_snapshot_ref=_selected_ref("fabric.data_snapshot", "1"),
        model_input_obligation_set_ref=_selected_ref(
            "runtime.quality.model_input_obligation_set", "8"
        ),
        measurements=(
            ResolvedMeasurementInput(
                binding_id="stock",
                model_input_obligation_ref=_selected_ref(
                    "runtime.quality.model_input_obligation", "5"
                ),
                selected_occurrence_ref=ScopedMeasurementOccurrenceRef.model_validate(
                    _selected_ref("catalog.scoped_measurement_occurrence", "6").model_dump()
                ),
                correspondence_ref=ScopedCorrespondenceBasisRef.model_validate(
                    _selected_ref("catalog.scoped_correspondence_basis", "7").model_dump()
                ),
                source_path="measurement.value",
            ),
        ),
        retained_binding_ids=("income",),
    )


def test_resolved_manifest_ref_selects_exact_payload_and_complete_lineage(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    value = _manifest()
    ref = persist_resolved_input_binding_manifest(store, value)
    assert load_resolved_input_binding_manifest(store, ref) == value
    missing_proof = store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=value.ARTIFACT_SCHEMA_NAME, version=value.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[
                edge for edge in value.lineage_inputs() if not edge.role.endswith(".correspondence")
            ],
        ),
        return_selected_profile=True,
    )
    assert missing_proof.artifact_id == ref.artifact_id
    assert missing_proof.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(ValueError, match=r"^resolved_input_binding_manifest_lineage_mismatch$"):
        load_resolved_input_binding_manifest(
            store, ResolvedInputBindingManifestRef.model_validate(missing_proof.model_dump())
        )


@pytest.mark.parametrize("version", ["1.2", "1.3"])
def test_semantic_binding_requires_exact_manifest_role_and_wire_version(
    tmp_path: Path, version: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest_ref = persist_resolved_input_binding_manifest(store, _manifest())
    fields = _binding_fields() | {
        "schema_version": version,
        "resolved_binding_manifest_ref": manifest_ref,
    }
    if version == "1.3":
        fields["registered_sql_admission_ref"] = _selected_ref(
            RegisteredSQLAdmissionBinding.ARTIFACT_KIND, "4"
        ).model_dump()
    bindings = FoundryInputBindings.model_validate(fields)
    edge = input_ref_from_artifact_ref(manifest_ref, role=RESOLVED_INPUT_BINDING_MANIFEST_ROLE)

    def persist(*, schema_version: str, correct_edge: bool) -> ArtifactRef:
        return store.put_json(
            bindings,
            PutOptions(
                kind=bindings.ARTIFACT_KIND,
                media_type=bindings.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=bindings.ARTIFACT_SCHEMA_NAME, version=schema_version),
                inputs=[
                    input_ref_from_artifact_ref(
                        bindings.data_snapshot_ref, role="input.data_snapshot_ref"
                    ),
                    input_ref_from_artifact_ref(
                        bindings.registry_bundle_ref, role="input.registry_bundle_ref"
                    ),
                    input_ref_from_artifact_ref(
                        bindings.bound_state_snapshot_ref, role="artifact.bound_state_snapshot_ref"
                    ),
                    *(
                        [
                            input_ref_from_artifact_ref(
                                bindings.registered_sql_admission_ref,
                                role="input.registered_sql_admission_ref",
                            )
                        ]
                        if bindings.registered_sql_admission_ref is not None
                        else []
                    ),
                    edge
                    if correct_edge
                    else edge.model_copy(
                        update={
                            "manifest_profile_sha256": f"sha256:{'8' * 64}",
                        }
                    ),
                ],
            ),
            return_selected_profile=True,
        )

    positive = persist(schema_version=version, correct_edge=True)
    assert to_canonical_bytes(load_input_bindings(store, positive)) == to_canonical_bytes(bindings)
    wrong_edge = persist(schema_version=version, correct_edge=False)
    assert wrong_edge.artifact_id == positive.artifact_id
    with pytest.raises(
        ValueError, match=r"^foundry_input_bindings_semantic_manifest_edge_mismatch$"
    ):
        load_input_bindings(store, wrong_edge)
    with pytest.raises(ValueError, match="canon_profile_typed_artifact_schema_version_mismatch"):
        load_input_bindings(store, persist(schema_version="1.0", correct_edge=True))


def test_semantic_registered_sql_replay_stays_not_established(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest_ref = persist_resolved_input_binding_manifest(store, _manifest())
    bindings = FoundryInputBindings.model_validate(
        _binding_fields()
        | {
            "schema_version": "1.3",
            "registered_sql_admission_ref": _selected_ref(
                RegisteredSQLAdmissionBinding.ARTIFACT_KIND, "4"
            ),
            "resolved_binding_manifest_ref": manifest_ref,
        }
    )
    existing_files = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}

    with pytest.raises(
        ValueError, match=r"^foundry_input_bindings_semantic_sql_replay_not_established$"
    ):
        reconcile_semantic_input_bindings(store, bindings)

    remaining_files = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    assert remaining_files == existing_files
