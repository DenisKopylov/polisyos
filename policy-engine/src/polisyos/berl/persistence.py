"""Versioned CAS persistence for BERL explanation bundles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    ExplanationBundle,
)
from polisyos.berl.contracts.schema import (
    explanation_bundle_schema_id,
    generated_explanation_bundle_schema,
)
from polisyos.core.artifacts import ArtifactStore as CoreArtifactStore
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.canon import CanonSpec
from polisyos.ir.artifacts import (
    ArtifactStore as IRArtifactStore,
)
from polisyos.ir.artifacts import (
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.registry.refs import ExplanationBundleRef

_EXPLANATION_BUNDLE_KIND = "scientist.explanation_bundle"
_EXPLANATION_BUNDLE_SCHEMA_NAME = explanation_bundle_schema_id()


def persist_explanation_bundle(
    store: CoreArtifactStore | IRArtifactStore,
    bundle: ExplanationBundle,
    *,
    inputs: Sequence[InputRef] | None = None,
) -> ExplanationBundleRef:
    """Persist a versioned explanation bundle and return its full selected-view ref.

    Args:
        store: Artifact store implementing the IR CAS protocol.
        bundle: Bundle produced by the BERL orchestration service.
        inputs: Optional typed upstream lineage refs recorded in the manifest.

    Returns:
        ExplanationBundleRef: Fixed-kind JSON ref including any selected profile.

    Raises:
        ValueError: If the bundle schema version is outside this writer's contract.
    """
    if bundle.schema_version != EXPLANATION_BUNDLE_SCHEMA_VERSION:
        raise ValueError("explanation_bundle_schema_version_unsupported")

    ir_store = ensure_ir_artifact_store(store)
    reference = put_json_artifact(
        ir_store,
        bundle.model_dump(mode="json", round_trip=True),
        kind=_EXPLANATION_BUNDLE_KIND,
        schema_name=_EXPLANATION_BUNDLE_SCHEMA_NAME,
        schema_version=EXPLANATION_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    try:
        return ExplanationBundleRef.model_validate(reference)
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_persisted_ref_invalid") from exc


def load_explanation_bundle(
    store: CoreArtifactStore | IRArtifactStore,
    reference: ExplanationBundleRef | Mapping[str, object],
) -> ExplanationBundle:
    """Load a bundle through its exact selected ref after checking manifest and wire contract.

    Args:
        store: Artifact store implementing the IR CAS protocol.
        reference: Typed fixed-kind ref, retaining any manifest-profile selector.

    Returns:
        ExplanationBundle: Validated bundle from the exact selected manifest view.

    Raises:
        ValueError: If the ref, selected manifest, or persisted bundle is invalid.
    """
    try:
        selected_ref = ExplanationBundleRef.model_validate(_reference_payload(reference))
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_ref_invalid") from exc

    ir_store = ensure_ir_artifact_store(store)
    try:
        manifest = ir_store.get_manifest(selected_ref)
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise ValueError("explanation_bundle_manifest_contract_mismatch") from exc

    schema = getattr(manifest, "artifact_schema", None)
    if (
        str(getattr(manifest, "artifact_id", "")) != str(selected_ref.artifact_id)
        or getattr(manifest, "kind", None) != _EXPLANATION_BUNDLE_KIND
        or getattr(manifest, "media_type", None) != "application/json"
        or getattr(schema, "name", None) != _EXPLANATION_BUNDLE_SCHEMA_NAME
        or getattr(schema, "version", None) != EXPLANATION_BUNDLE_SCHEMA_VERSION
    ):
        raise ValueError("explanation_bundle_manifest_contract_mismatch")

    try:
        payload = get_json_artifact(ir_store, selected_ref)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("explanation_bundle_persisted_payload_invalid") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("explanation_bundle_persisted_payload_invalid")

    schema_required = generated_explanation_bundle_schema().get("required")
    if not isinstance(schema_required, list) or any(
        not isinstance(field_name, str) for field_name in schema_required
    ):
        raise TypeError("generated ExplanationBundle schema has invalid required fields")
    if any(field_name not in payload for field_name in schema_required):
        raise ValueError("explanation_bundle_persisted_field_missing")
    if payload.get("schema_version") != EXPLANATION_BUNDLE_SCHEMA_VERSION:
        raise ValueError("explanation_bundle_manifest_contract_mismatch")

    try:
        return ExplanationBundle.model_validate(payload)
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_persisted_payload_invalid") from exc


def _reference_payload(
    reference: ExplanationBundleRef | Mapping[str, object],
) -> Mapping[str, object]:
    if isinstance(reference, ExplanationBundleRef):
        return reference.model_dump(mode="python")
    return reference


__all__ = ["load_explanation_bundle", "persist_explanation_bundle"]
