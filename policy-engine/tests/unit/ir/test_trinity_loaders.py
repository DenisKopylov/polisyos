from __future__ import annotations

import json

import pytest
import yaml

from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import (
    TrinityLoadError,
    load_model_spec,
    load_policy_spec,
    load_problem_frame,
    load_trinity_bundle,
    load_trinity_bundle_artifact,
)

ZERO_REF = "sha256:" + "0" * 64
TRINITY_OWNER_CANON_SPEC = CanonSpec(forbid_floats=False)


def _minimal_trinity_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_cas",
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
            "policy_id": "ps_cas",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_cas",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_load_problem_frame_from_json_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "problem_id": "pf_demo",
        "domain": "custom",
        "objectives": [],
        "kpis": [],
        "success_criteria": [],
        "hard_constraints": [],
        "soft_constraints": [],
        "stakeholders": [],
        "labels": [],
        "notes": [],
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_problem_frame(data)
    assert model.problem_id == "pf_demo"


def test_load_policy_spec_from_yaml_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "policy_id": "ps_demo",
        "interventions": [],
        "mechanism_bindings": [],
        "parameters": [],
        "labels": [],
        "notes": [],
    }
    data = yaml.safe_dump(payload).encode("utf-8")
    model = load_policy_spec(data)
    assert model.policy_id == "ps_demo"


def test_load_model_spec_from_json_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "model_id": "ms_demo",
        "data_snapshot_ref": ZERO_REF,
        "registry_bundle_ref": None,
        "assumptions": [],
        "labels": [],
        "notes": [],
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_model_spec(data)
    assert model.model_id == "ms_demo"


def test_load_trinity_bundle_from_mapping() -> None:
    payload = {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_demo",
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
            "policy_id": "ps_demo",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_demo",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }
    bundle = load_trinity_bundle(payload)
    assert isinstance(bundle, TrinityBundle)


def test_load_trinity_bundle_artifact_uses_selected_owner_manifest(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = _minimal_trinity_payload()
    put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name="polisyos.ir.OtherPayload",
        schema_version="9.0",
        canon_spec=TRINITY_OWNER_CANON_SPEC,
    )
    selected_ref = put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        canon_spec=TRINITY_OWNER_CANON_SPEC,
        return_selected_profile=True,
    )

    bundle = load_trinity_bundle_artifact(store, selected_ref)

    assert bundle.problem_frame.problem_id == "pf_cas"
    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(store, selected_ref["artifact_id"])


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "error_match"),
    [
        ("1.0", "1.0", None),
        ("1.0", "9.0", "Unsupported schema_version"),
        ("9.0", "1.0", "manifest"),
    ],
)
def test_load_trinity_bundle_artifact_requires_matching_payload_and_manifest_version(
    tmp_path,
    manifest_version: str,
    payload_version: str,
    error_match: str | None,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = _minimal_trinity_payload()
    payload["schema_version"] = payload_version
    selected_ref = put_json_artifact(
        store,
        payload,
        kind=TrinityBundle.ARTIFACT_KIND,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=manifest_version,
        canon_spec=TRINITY_OWNER_CANON_SPEC,
        return_selected_profile=True,
    )

    if error_match is None:
        bundle = load_trinity_bundle_artifact(store, selected_ref)
        assert bundle.schema_version == manifest_version
    else:
        with pytest.raises(TrinityLoadError, match=error_match):
            load_trinity_bundle_artifact(store, selected_ref)


@pytest.mark.parametrize(
    ("kind", "media_type", "schema_name", "schema_version"),
    [
        ("other.kind", "application/json", TrinityBundle.ARTIFACT_SCHEMA_NAME, "1.0"),
        (
            TrinityBundle.ARTIFACT_KIND,
            "application/yaml",
            TrinityBundle.ARTIFACT_SCHEMA_NAME,
            "1.0",
        ),
        (TrinityBundle.ARTIFACT_KIND, "application/json", "polisyos.ir.OtherPayload", "1.0"),
        (
            TrinityBundle.ARTIFACT_KIND,
            "application/json",
            TrinityBundle.ARTIFACT_SCHEMA_NAME,
            "9.0",
        ),
    ],
)
def test_load_trinity_bundle_artifact_refuses_wrong_owner_metadata(
    tmp_path, kind: str, media_type: str, schema_name: str, schema_version: str
) -> None:
    core_store = FileSystemCAS(tmp_path / "cas")
    store = ensure_ir_artifact_store(core_store)
    options = PutOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
        canon=CanonInfo.from_spec(TRINITY_OWNER_CANON_SPEC),
    )
    if media_type == "application/json":
        selected_ref = core_store.put_json(
            _minimal_trinity_payload(),
            options,
            canon_spec=TRINITY_OWNER_CANON_SPEC,
            return_selected_profile=True,
        )
    else:
        selected_ref = core_store.put_bytes(
            to_canonical_bytes(_minimal_trinity_payload(), TRINITY_OWNER_CANON_SPEC),
            options,
            return_selected_profile=True,
        )

    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(store, selected_ref)
