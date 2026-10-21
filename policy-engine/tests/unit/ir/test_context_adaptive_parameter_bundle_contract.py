from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactRef,
    ArtifactWriteOptions,
    ProducerInfo,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import InputRef as CoreInputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshotChunk,
    RetainedSKGSnapshotV11,
    RetainedSKGSourceBinding,
    retained_skg_source_binding,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundle,
    ContextAdaptiveParameterBundleV11,
    ContextAdaptiveParameterBundleV12,
    ParameterApplicability,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle_v1_1,
    persist_context_adaptive_parameter_bundle_v1_2,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.artifacts import ArtifactID, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel, ContextAdaptiveParameterBundleRef


def test_context_adaptive_parameter_bundle_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    target_context = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        publication_year=2022,
    )
    parameter = EvidenceParameter(name="fiscal_multiplier", value=1.2)
    applicability = ParameterApplicability(
        parameter_id="fiscal_multiplier",
        target_context_id="UA",
        transport_status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_confidence=0.6,
        context_distance=0.4,
        is_applicable=True,
        adjustment_required=True,
        uncertainty_multiplier=1.8,
        recommended_value=1.2,
    )
    bundle = ContextAdaptiveParameterBundle(
        target_context=target_context,
        simulation_domain="fiscal",
        parameters={"fiscal_multiplier": parameter},
        applicability={"fiscal_multiplier": applicability},
        unsupported_parameters=["tax_elasticity"],
        skg_snapshot_ref="duckdb://mock#v1",
        skg_version_id=1,
        selection_timestamp="2026-03-02T12:00:00+00:00",
    )

    ref = persist_context_adaptive_parameter_bundle(_ensure_ir_artifact_store(store), bundle)
    loaded = load_context_adaptive_parameter_bundle(_ensure_ir_artifact_store(store), ref)

    assert isinstance(ref, ContextAdaptiveParameterBundleRef)
    assert ref.kind == "ir.context_adaptive_parameter_bundle"
    assert loaded == bundle
    assert _ensure_ir_artifact_store(store).get_manifest(ref).artifact_schema.version == "1.0"


def _graph_input() -> InputRef:
    return InputRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        role="causal_graph",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )


def _bundle_v1_1() -> ContextAdaptiveParameterBundleV11:
    return ContextAdaptiveParameterBundleV11(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
    )


def _profiled_source_input(
    store: FileSystemCAS,
    *,
    kind: str = "scientist.skg_source_snapshot",
    media_type: str = "application/json",
    schema_name: str | None = None,
    schema_version: str = "1.0",
) -> CoreInputRef:
    ref = store.put_bytes(
        b"{}",
        ArtifactWriteOptions(
            kind=kind,
            media_type=media_type,
            schema=SchemaInfo(name=schema_name or kind, version=schema_version),
            producer=ProducerInfo(component="tests.ir.parameters", version="1.0"),
        ),
    )
    selected = profile_bound_ref(store, ref)
    return input_ref_from_artifact_ref(selected, role="skg_source_snapshot")


def test_context_adaptive_parameter_bundle_v1_1_resolves_the_exact_skg_source_view(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)

    def put_source_view(kind: str):
        ref = store.put_bytes(
            b"{}",
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=kind, version="1.0"),
                producer=ProducerInfo(component="tests.ir.parameters", version="1.0"),
            ),
            return_selected_profile=True,
        )
        return ref, input_ref_from_artifact_ref(ref, role="skg_source_snapshot")

    sibling_ref, sibling = put_source_view("other.snapshot")
    selected_source_ref, selected = put_source_view("scientist.skg_source_snapshot")

    assert selected.artifact_id == sibling.artifact_id
    assert selected.manifest_profile_sha256 is not None
    assert sibling.manifest_profile_sha256 is not None
    assert selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
    selected_selector = ArtifactRefModel(
        artifact_id=selected.artifact_id,
        kind="scientist.skg_source_snapshot",
        media_type="application/json",
        manifest_profile_sha256=selected.manifest_profile_sha256,
    )
    sibling_selector = ArtifactRefModel(
        artifact_id=sibling.artifact_id,
        kind="other.snapshot",
        media_type="application/json",
        manifest_profile_sha256=sibling.manifest_profile_sha256,
    )
    assert ir_store.get_manifest(selected_selector).kind == "scientist.skg_source_snapshot"
    assert ir_store.get_manifest(sibling_selector).kind == "other.snapshot"
    assert ir_store.get_manifest(selected.artifact_id).kind == "other.snapshot"
    assert store.get_bytes(selected_source_ref) == b"{}"
    assert store.get_bytes(sibling_ref) == b"{}"

    ref = persist_context_adaptive_parameter_bundle_v1_1(
        ir_store,
        _bundle_v1_1(),
        inputs=[_graph_input(), selected],
    )

    assert ir_store.get_manifest(ref).inputs[1] == selected


def test_context_adaptive_parameter_bundle_v1_1_rejects_corrupt_selected_skg_bytes(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)

    def put_source_view(kind: str):
        ref = store.put_bytes(
            b"{}",
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=kind, version="1.0"),
                producer=ProducerInfo(component="tests.ir.parameters", version="1.0"),
            ),
            return_selected_profile=True,
        )
        return ref, input_ref_from_artifact_ref(ref, role="skg_source_snapshot")

    _sibling_ref, _sibling = put_source_view("other.snapshot")
    selected_ref, selected = put_source_view("scientist.skg_source_snapshot")
    assert selected.manifest_profile_sha256 is not None
    selected_selector = ArtifactRefModel(
        artifact_id=selected.artifact_id,
        kind="scientist.skg_source_snapshot",
        media_type="application/json",
        manifest_profile_sha256=selected.manifest_profile_sha256,
    )
    manifest_before_corruption = ir_store.get_manifest(selected_selector)
    assert manifest_before_corruption.kind == "scientist.skg_source_snapshot"
    assert manifest_before_corruption.media_type == "application/json"
    assert manifest_before_corruption.artifact_schema is not None
    assert manifest_before_corruption.artifact_schema.name == "scientist.skg_source_snapshot"
    assert manifest_before_corruption.artifact_schema.version == "1.0"
    assert artifact_manifest_profile_sha256(manifest_before_corruption) == (
        selected.manifest_profile_sha256
    )
    assert ir_store.get_manifest(selected.artifact_id).kind == "other.snapshot"

    blob_path, _manifest_path = store._paths(selected.artifact_id)
    blob_path.write_bytes(b'{"tampered":true}')
    assert ir_store.get_manifest(selected_selector) == manifest_before_corruption

    with pytest.raises(
        ValueError, match="Selected SKG source profile could not be resolved"
    ) as error:
        persist_context_adaptive_parameter_bundle_v1_1(
            ir_store,
            _bundle_v1_1(),
            inputs=[_graph_input(), selected],
        )
    assert isinstance(error.value.__cause__, ArtifactIntegrityError)
    assert selected_ref.manifest_profile_sha256 == selected.manifest_profile_sha256


def test_context_adaptive_parameter_bundle_v1_1_resolves_selected_skg_source_profile(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    source_input = _profiled_source_input(store)
    bundle = _bundle_v1_1()

    ref = persist_context_adaptive_parameter_bundle_v1_1(
        ir_store,
        bundle,
        inputs=[_graph_input(), source_input],
    )

    manifest = ir_store.get_manifest(ref)
    assert [item.role for item in manifest.inputs] == ["causal_graph", "skg_source_snapshot"]
    assert manifest.inputs[1] == source_input
    assert load_context_adaptive_parameter_bundle(ir_store, ref) == bundle


@pytest.mark.parametrize(
    ("source_input", "reason"),
    [
        ("missing_profile", "exact manifest profile"),
        ("stale_profile", "profile could not be resolved"),
        ("duplicate", "at most one selected SKG source"),
        ("extra_role", "unsupported input role"),
        ("wrong_kind", "incompatible manifest"),
        ("wrong_media", "incompatible manifest"),
        ("wrong_schema", "incompatible manifest"),
    ],
)
def test_context_adaptive_parameter_bundle_v1_1_rejects_unbound_skg_source(
    tmp_path, source_input: str, reason: str
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    selected = _profiled_source_input(store)
    if source_input == "missing_profile":
        selected = selected.model_copy(update={"manifest_profile_sha256": None})
    elif source_input == "stale_profile":
        selected = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    elif source_input == "extra_role":
        selected = selected.model_copy(update={"role": "source_chunk:0"})
    elif source_input == "wrong_kind":
        selected = _profiled_source_input(store, kind="other.snapshot")
    elif source_input == "wrong_media":
        selected = _profiled_source_input(store, media_type="application/octet-stream")
    elif source_input == "wrong_schema":
        selected = _profiled_source_input(store, schema_name="other.snapshot")

    inputs = [_graph_input(), selected]
    if source_input == "duplicate":
        inputs.append(selected)
    with pytest.raises((TypeError, ValueError), match=reason):
        persist_context_adaptive_parameter_bundle_v1_1(ir_store, _bundle_v1_1(), inputs=inputs)


def test_context_adaptive_parameter_bundle_v1_1_loader_rechecks_source_manifest(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    wrong_source = _profiled_source_input(store, kind="other.snapshot")
    ref = put_json_artifact(
        ir_store,
        _bundle_v1_1().model_dump(mode="json"),
        kind="ir.context_adaptive_parameter_bundle",
        schema_name="ir.context_adaptive_parameter_bundle",
        schema_version="1.1",
        inputs=[_graph_input(), wrong_source],
    )

    with pytest.raises(ValueError, match="incompatible manifest"):
        load_context_adaptive_parameter_bundle(
            ir_store, ContextAdaptiveParameterBundleRef.model_validate(ref)
        )


def test_context_adaptive_parameter_bundle_v1_1_records_verified_profile_absence(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    bundle = ContextAdaptiveParameterBundleV11(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
    )

    ref = persist_context_adaptive_parameter_bundle_v1_1(
        ir_store,
        bundle,
        inputs=[_graph_input()],
    )
    payload = get_json_artifact(ir_store, ref)
    loaded = load_context_adaptive_parameter_bundle(ir_store, ref)

    assert payload["schema_version"] == "1.1"
    assert "selected_cross_graph_profile_ref" in payload
    assert payload["selected_cross_graph_profile_ref"] is None
    assert ir_store.get_manifest(ref).artifact_schema.version == "1.1"
    assert loaded == bundle
    assert isinstance(loaded, ContextAdaptiveParameterBundleV11)


def test_context_adaptive_parameter_bundle_v1_1_missing_selection_field_is_rejected(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    bundle = ContextAdaptiveParameterBundleV11(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
    )
    payload = bundle.model_dump(mode="json")
    payload.pop("selected_cross_graph_profile_ref")
    ref = put_json_artifact(
        ir_store,
        payload,
        kind="ir.context_adaptive_parameter_bundle",
        schema_name="ir.context_adaptive_parameter_bundle",
        schema_version="1.1",
        inputs=[_graph_input()],
    )

    with pytest.raises(ValidationError) as exc_info:
        load_context_adaptive_parameter_bundle(ir_store, ref)
    assert any(
        error["loc"] == ("selected_cross_graph_profile_ref",) for error in exc_info.value.errors()
    )


def _persisted_skg_source_v11(store, *, source_digest=None, build_binding=True):
    """Create one selected source descriptor for bundle tests."""
    chunk_bytes = b"source bytes selected by one read"
    chunk_ref = store.put_bytes(
        chunk_bytes,
        ArtifactWriteOptions(
            kind="scientist.skg_source_chunk",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="scientist.skg_source_chunk", version="1.0"),
            producer=ProducerInfo(component="tests.ir.parameters", version="1.0"),
        ),
        return_selected_profile=True,
    )
    snapshot = RetainedSKGSnapshotV11(
        schema_version="1.1",
        source_reference="duckdb://captured/source#v7",
        source_sha256=source_digest or hashlib.sha256(chunk_bytes).hexdigest(),
        byte_size=len(chunk_bytes),
        source_binding_schema_version="academic.skg_source_binding.v2",
        query_version="skg-query-read.v3",
        source_version_id=7,
        version_identity_kind="content_digest",
        chunks=(RetainedSKGSnapshotChunk(ref=chunk_ref, byte_size=len(chunk_bytes)),),
    )
    source_payload = put_json_artifact(
        _ensure_ir_artifact_store(store),
        snapshot.model_dump(mode="json"),
        kind="scientist.skg_source_snapshot",
        schema_name="scientist.skg_source_snapshot",
        schema_version="1.1",
        inputs=[input_ref_from_artifact_ref(chunk_ref, role="source_chunk:0")],
        return_selected_profile=True,
    )
    source_ref = ArtifactRef.model_validate(source_payload)
    if not build_binding:
        return source_ref, None
    binding = retained_skg_source_binding(_ensure_ir_artifact_store(store), source_ref)
    return source_ref, binding


def test_context_adaptive_parameter_bundle_v1_2_roundtrips_exact_source_and_observed_version(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    source_ref, binding = _persisted_skg_source_v11(store)
    bundle = ContextAdaptiveParameterBundleV12(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
        skg_snapshot_ref=binding.source_reference,
        skg_version_id=binding.source_version_id,
        selected_skg_source=binding,
    )

    ref = persist_context_adaptive_parameter_bundle_v1_2(
        ir_store,
        bundle,
        inputs=[
            _graph_input(),
            input_ref_from_artifact_ref(source_ref, role="skg_source_snapshot"),
        ],
    )
    cold_bundle = load_context_adaptive_parameter_bundle(ir_store, ref)
    manifest = ir_store.get_manifest(ref)

    assert isinstance(cold_bundle, ContextAdaptiveParameterBundleV12)
    assert cold_bundle.selected_skg_source == binding
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "1.2"
    assert manifest.inputs[1] == input_ref_from_artifact_ref(source_ref, role="skg_source_snapshot")


def test_context_adaptive_parameter_bundle_v1_2_recomputes_retained_source_bytes(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    source_ref, _ = _persisted_skg_source_v11(
        store,
        source_digest="0" * 64,
        build_binding=False,
    )
    binding = RetainedSKGSourceBinding(
        descriptor_ref=source_ref,
        source_reference="duckdb://captured/source#v7",
        source_sha256="0" * 64,
        source_version_id=7,
        source_binding_schema_version="academic.skg_source_binding.v2",
        query_version="skg-query-read.v3",
        version_identity_kind="content_digest",
    )
    bundle = ContextAdaptiveParameterBundleV12(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
        skg_snapshot_ref=binding.source_reference,
        skg_version_id=binding.source_version_id,
        selected_skg_source=binding,
    )

    with pytest.raises(ValueError, match="descriptor could not be resolved"):
        persist_context_adaptive_parameter_bundle_v1_2(
            ir_store,
            bundle,
            inputs=[
                _graph_input(),
                input_ref_from_artifact_ref(source_ref, role="skg_source_snapshot"),
            ],
        )


def test_context_adaptive_parameter_bundle_v1_2_rejects_unjoined_or_changed_source(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ir_store = _ensure_ir_artifact_store(store)
    source_ref, binding = _persisted_skg_source_v11(store)
    source_input = input_ref_from_artifact_ref(source_ref, role="skg_source_snapshot")
    bundle = ContextAdaptiveParameterBundleV12(
        target_context=ContextProfile(context_id="UA"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
        skg_snapshot_ref=binding.source_reference,
        skg_version_id=binding.source_version_id,
        selected_skg_source=binding,
    )

    with pytest.raises(ValueError, match="exactly one selected SKG source input"):
        persist_context_adaptive_parameter_bundle_v1_2(ir_store, bundle, inputs=[_graph_input()])
    changed = binding.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(ValueError, match="content and observed version disagree"):
        persist_context_adaptive_parameter_bundle_v1_2(
            ir_store,
            bundle.model_copy(update={"selected_skg_source": changed}),
            inputs=[_graph_input(), source_input],
        )

    payload = bundle.model_dump(mode="json")
    payload.pop("selected_skg_source")
    unbound_ref = put_json_artifact(
        ir_store,
        payload,
        kind="ir.context_adaptive_parameter_bundle",
        schema_name="ir.context_adaptive_parameter_bundle",
        schema_version="1.2",
        inputs=[_graph_input(), source_input],
    )
    with pytest.raises(ValidationError):
        load_context_adaptive_parameter_bundle(
            ir_store, ContextAdaptiveParameterBundleRef.model_validate(unbound_ref)
        )
