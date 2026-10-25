from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import (
    TrinityLoadError,
    load_trinity_bundle,
    load_trinity_bundle_artifact,
    persist_trinity_bundle_artifact,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    _persist_trinity_bundle,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

ZERO_REF = "sha256:" + "0" * 64
TRINITY_OWNER_SPEC = CanonSpec(forbid_floats=False)


def _bundle(*, schema_version: str = "1.0") -> TrinityBundle:
    return TrinityBundle.model_validate(
        {
            "schema_version": schema_version,
            "problem_frame": {
                "schema_version": "1.0",
                "problem_id": "pf_owner",
                "domain": "custom",
                "objectives": [],
                "kpis": [],
                "success_criteria": [],
                "hard_constraints": [],
                "soft_constraints": [],
                "stakeholders": [],
                "labels": [],
                "notes": [],
            },
            "policy_spec": {
                "schema_version": "1.0",
                "policy_id": "ps_owner",
                "interventions": [],
                "mechanism_bindings": [],
                "parameters": [],
                "labels": [],
                "notes": [],
            },
            "model_spec": {
                "schema_version": "1.0",
                "model_id": "ms_owner",
                "data_snapshot_ref": ZERO_REF,
                "registry_bundle_ref": None,
                "assumptions": [],
                "labels": [],
                "notes": [],
            },
        }
    )


def _unowned_write(store: FileSystemCAS, payload: object, *, spec: CanonSpec):
    return store.put_json(
        payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version="1.0",
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def test_shared_trinity_writer_binds_selected_owner_profile_and_lineage_for_fresh_readers(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    ir_store = ensure_ir_artifact_store(store)
    bundle = _bundle()

    default_view = persist_trinity_bundle_artifact(ir_store, bundle)
    assert default_view.manifest_profile_sha256 is not None
    default_manifest = store.get_manifest(default_view)
    assert default_manifest.canon == CanonInfo.from_spec(TRINITY_OWNER_SPEC)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    assert load_trinity_bundle_artifact(fresh_store, default_view) == bundle

    # Profileless historical selectors remain usable for inspection when unambiguous.
    history_selector = ArtifactRefModel.model_validate(
        default_view.model_dump(exclude={"manifest_profile_sha256"})
    )
    assert load_trinity_bundle_artifact(fresh_store, history_selector) == bundle

    anchor = store.put_json(
        {"source": "lineage-anchor"},
        PutOptions(
            kind="ir.test_source_anchor",
            media_type="application/json",
            schema=SchemaInfo(name="ir.test_source_anchor", version="1.0"),
        ),
        return_selected_profile=True,
    )
    source_a = InputRef(
        artifact_id=anchor.artifact_id,
        role="source-view-a",
        manifest_profile_sha256=anchor.manifest_profile_sha256,
    )
    source_b = InputRef(
        artifact_id=anchor.artifact_id,
        role="source-view-b",
        manifest_profile_sha256=anchor.manifest_profile_sha256,
    )
    view_a = persist_trinity_bundle_artifact(ir_store, bundle, inputs=[source_a])
    view_b = persist_trinity_bundle_artifact(ir_store, bundle, inputs=[source_b])
    assert view_a.artifact_id == view_b.artifact_id == default_view.artifact_id
    assert view_a.manifest_profile_sha256 != view_b.manifest_profile_sha256
    assert store.get_manifest(view_a).inputs[0].role == "source-view-a"
    assert store.get_manifest(view_b).inputs[0].role == "source-view-b"
    assert load_trinity_bundle_artifact(fresh_store, view_a) == bundle
    assert load_trinity_bundle_artifact(fresh_store, view_b) == bundle

    profileless_payload = dict(view_a)
    profileless_payload.pop("manifest_profile_sha256")
    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        ArtifactRefModel.from_selected_write(profileless_payload)


def test_shared_trinity_writer_refuses_profile_dropped_at_selected_write_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.ir.trinity.loaders as loaders

    profileless = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": TrinityBundle.ARTIFACT_KIND,
        "media_type": TrinityBundle.ARTIFACT_MEDIA_TYPE,
    }
    monkeypatch.setattr(loaders, "_put_owned_json_artifact", lambda *_args, **_kwargs: profileless)
    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")),
            _bundle(),
        )


def test_hierarchical_trinity_producer_binds_its_cas_profile_for_a_fresh_reader(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    lineage_anchor = store.put_json(
        {"source": "lineage-anchor"},
        PutOptions(
            kind="ir.test_source_anchor",
            media_type="application/json",
            schema=SchemaInfo(name="ir.test_source_anchor", version="1.0"),
        ),
        return_selected_profile=True,
    )
    source_payload = {"source": "experiment-input"}
    first_source_view = store.put_json(
        source_payload,
        PutOptions(
            kind="ir.test_source",
            media_type="application/json",
            schema=SchemaInfo(name="ir.test_source", version="1.0"),
            inputs=[InputRef(artifact_id=lineage_anchor.artifact_id, role="source-lineage-a")],
        ),
        return_selected_profile=True,
    )
    source_ref = store.put_json(
        source_payload,
        PutOptions(
            kind="ir.test_source",
            media_type="application/json",
            schema=SchemaInfo(name="ir.test_source", version="1.0"),
            inputs=[InputRef(artifact_id=lineage_anchor.artifact_id, role="source-lineage-b")],
        ),
        return_selected_profile=True,
    )
    assert source_ref.artifact_id == first_source_view.artifact_id
    assert source_ref.manifest_profile_sha256 != first_source_view.manifest_profile_sha256
    state = ExperimentState(
        run_id="trinity-owner-run",
        inputs={
            "source_case_a": first_source_view,
            "source_case_b": source_ref,
        },
    )

    ref = _persist_trinity_bundle(
        SimpleNamespace(store=store),
        _bundle(),
        state=state,
    )

    assert isinstance(ref, TrinityBundleRef)
    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(ref)
    assert manifest.canon.forbid_floats is False
    assert [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    ] == [
        (
            str(first_source_view.artifact_id),
            "source_case_a",
            first_source_view.manifest_profile_sha256,
        ),
        (
            str(source_ref.artifact_id),
            "source_case_b",
            source_ref.manifest_profile_sha256,
        ),
    ]

    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    assert load_trinity_bundle_artifact(fresh_reader, ref) == _bundle()


def test_trinity_owner_refuses_same_kind_wrong_manifest_and_payload_versions(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    wrong_manifest_payload = _bundle().model_dump(mode="json")
    wrong_manifest = FileSystemCAS(tmp_path / "wrong-manifest")
    wrong_manifest_ref = wrong_manifest.put_json(
        wrong_manifest_payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version="9.0",
            ),
            canon=CanonInfo.from_spec(TRINITY_OWNER_SPEC),
        ),
        canon_spec=TRINITY_OWNER_SPEC,
        return_selected_profile=True,
    )
    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(wrong_manifest), wrong_manifest_ref)

    wrong_payload = _bundle().model_dump(mode="json")
    wrong_payload["schema_version"] = "9.0"
    payload_store = FileSystemCAS(tmp_path / "wrong-payload")
    wrong_payload_ref = _unowned_write(payload_store, wrong_payload, spec=TRINITY_OWNER_SPEC)
    with pytest.raises(TrinityLoadError, match="Unsupported schema_version"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(payload_store), wrong_payload_ref)


def test_trinity_owner_refuses_wrong_profile_even_when_markers_and_payload_validate(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    wrong_profile = CanonSpec(forbid_floats=True)
    ref = _unowned_write(
        store,
        _bundle().model_dump(mode="json"),
        spec=wrong_profile,
    )

    # Generic byte decoding plus the public DTO parser still succeeds. The CAS
    # consumer must separately enforce the registered owner profile.
    generic_payload = get_json_artifact(ensure_ir_artifact_store(store), ref)
    assert load_trinity_bundle(generic_payload) == _bundle()

    with pytest.raises(TrinityLoadError, match="profile"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(FileSystemCAS(cas_root)), ref)
