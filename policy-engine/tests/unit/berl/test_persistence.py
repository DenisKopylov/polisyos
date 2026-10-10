from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.berl import load_explanation_bundle, persist_explanation_bundle
from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    AuditReport,
    ExplanationAssumptions,
    ExplanationBundle,
    FeatureContext,
    FeatureDependencePolicy,
    ModelContext,
    PerturbationDistribution,
    PredictionContext,
)
from polisyos.berl.contracts.schema import explanation_bundle_schema_id
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import ExplanationBundleRef

_SCHEMA_NAME = explanation_bundle_schema_id()
_SCHEMA_VERSION = EXPLANATION_BUNDLE_SCHEMA_VERSION
_KIND = "scientist.explanation_bundle"


def _bundle() -> ExplanationBundle:
    return ExplanationBundle(
        bundle_id="bundle-cas-test",
        created_at=datetime(2026, 10, 10, tzinfo=UTC),
        model=ModelContext(
            model_id="model",
            model_hash="sha256:model",
            model_class="linear",
        ),
        prediction=PredictionContext(
            prediction_id="prediction",
            row_id="row",
            output_name="score",
            output_scale="score",
            raw_score=1.0,
        ),
        feature_context=FeatureContext(
            feature_values_ref="inline://features",
            feature_schema_version="features-v1",
        ),
        assumptions=ExplanationAssumptions(
            perturbation_distribution=PerturbationDistribution(name="empirical"),
            feature_dependence_policy=FeatureDependencePolicy(primary="marginal"),
        ),
        audit=AuditReport(code_version="test"),
    )


def test_persistence_returns_selected_typed_ref_and_reads_its_manifest_view(
    tmp_path,
) -> None:
    store_root = tmp_path / "cas"
    store = FileSystemCAS(store_root)
    bundle = _bundle()
    payload = bundle.model_dump(mode="json", round_trip=True)

    first_view = store.put_json(
        payload,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA_NAME, version="0.9.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = persist_explanation_bundle(store, bundle)

    assert isinstance(ref, ExplanationBundleRef)
    assert str(ref.artifact_id) == str(first_view.artifact_id)
    assert ref.kind == _KIND
    assert ref.media_type == "application/json"
    assert ref.manifest_profile_sha256 is not None
    assert store.get_manifest(ref.artifact_id).artifact_schema == SchemaInfo(
        name=_SCHEMA_NAME,
        version="0.9.0",
    )
    assert ensure_ir_artifact_store(store).get_manifest(ref).artifact_schema == SchemaInfo(
        name=_SCHEMA_NAME,
        version=_SCHEMA_VERSION,
    )

    fresh_store = FileSystemCAS(store_root)
    loaded = load_explanation_bundle(fresh_store, ref)

    assert loaded == bundle
    wrong_profile = ref.model_copy(update={"manifest_profile_sha256": f"sha256:{'0' * 64}"})
    with pytest.raises(ValueError, match="explanation_bundle_manifest_contract_mismatch"):
        load_explanation_bundle(fresh_store, wrong_profile)


@pytest.mark.parametrize(
    ("kind", "media_type", "schema_name", "schema_version"),
    [
        ("scientist.other_bundle", "application/json", _SCHEMA_NAME, _SCHEMA_VERSION),
        (_KIND, "text/plain", _SCHEMA_NAME, _SCHEMA_VERSION),
        (_KIND, "application/json", f"{_SCHEMA_NAME}.other", _SCHEMA_VERSION),
        (_KIND, "application/json", _SCHEMA_NAME, "0.9.0"),
    ],
)
def test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract(
    tmp_path,
    kind: str,
    media_type: str,
    schema_name: str,
    schema_version: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle()
    options = PutOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
    )
    payload = bundle.model_dump(mode="json", round_trip=True)
    canon_spec = CanonSpec(forbid_floats=False)
    stored = (
        store.put_json(payload, options, canon_spec=canon_spec)
        if media_type == "application/json"
        else store.put_bytes(to_canonical_bytes(payload, canon_spec), options)
    )
    claimed_bundle_ref = ExplanationBundleRef(
        artifact_id=stored.artifact_id,
        manifest_profile_sha256=stored.manifest_profile_sha256,
    )

    with pytest.raises(ValueError, match="explanation_bundle_manifest_contract_mismatch"):
        load_explanation_bundle(store, claimed_bundle_ref)


def test_loader_refuses_persisted_payloads_missing_required_wire_fields(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = _bundle().model_dump(mode="json", round_trip=True)
    del payload["methods"]
    stored = store.put_json(
        payload,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA_NAME, version=_SCHEMA_VERSION),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = ExplanationBundleRef(
        artifact_id=stored.artifact_id,
        manifest_profile_sha256=stored.manifest_profile_sha256,
    )

    with pytest.raises(ValueError, match="explanation_bundle_persisted_field_missing"):
        load_explanation_bundle(store, ref)


def test_public_loader_rejects_reference_claims_with_wrong_kind_or_media(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    stored = store.put_json(
        _bundle().model_dump(mode="json", round_trip=True),
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA_NAME, version=_SCHEMA_VERSION),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    wrong_kind = {
        "artifact_id": str(stored.artifact_id),
        "kind": "scientist.other_bundle",
        "media_type": "application/json",
    }
    wrong_media_type = {
        "artifact_id": str(stored.artifact_id),
        "kind": _KIND,
        "media_type": "text/plain",
    }
    with pytest.raises(ValidationError):
        ExplanationBundleRef.model_validate(wrong_kind)
    with pytest.raises(ValidationError):
        ExplanationBundleRef.model_validate(wrong_media_type)
    with pytest.raises(ValueError, match="explanation_bundle_ref_invalid"):
        load_explanation_bundle(store, wrong_kind)
    with pytest.raises(ValueError, match="explanation_bundle_ref_invalid"):
        load_explanation_bundle(store, wrong_media_type)


def test_loader_refuses_payload_version_that_disagrees_with_manifest(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = _bundle().model_dump(mode="json", round_trip=True)
    payload["schema_version"] = "0.9.0"
    stored = store.put_json(
        payload,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA_NAME, version=_SCHEMA_VERSION),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = ExplanationBundleRef(
        artifact_id=stored.artifact_id,
        manifest_profile_sha256=stored.manifest_profile_sha256,
    )

    with pytest.raises(ValueError, match="explanation_bundle_manifest_contract_mismatch"):
        load_explanation_bundle(store, ref)


def test_writer_refuses_bundle_schema_version_outside_current_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    unsupported = _bundle().model_copy(update={"schema_version": "0.9.0"})

    with pytest.raises(ValueError, match="explanation_bundle_schema_version_unsupported"):
        persist_explanation_bundle(store, unsupported)

    assert store.iter_artifact_ids() == []
