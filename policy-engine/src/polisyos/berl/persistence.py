"""Versioned CAS persistence for BERL explanation bundles."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, TypeVar, cast

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
from polisyos.ir import (
    ArtifactStore as IRArtifactStore,
)
from polisyos.ir import (
    CanonSpec as IRCanonSpec,
)
from polisyos.ir import (
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.analytics import ExplanationBundleRef

if TYPE_CHECKING:
    from polisyos.ir import ArtifactSelector

from pydantic import ValidationError

_ReadResult = TypeVar("_ReadResult")

_EXPLANATION_BUNDLE_KIND = "scientist.explanation_bundle"
_EXPLANATION_BUNDLE_SCHEMA_NAME = explanation_bundle_schema_id()


class ExplanationBundleStoreReadError(RuntimeError):
    """A selected CAS read failed without establishing that its object is absent."""

    code = "explanation_bundle_store_read_unavailable"


class _SelectedViewReadAdapter:
    """Normalize unexpected exceptions from selected-view raw read operations."""

    def __init__(self, store: IRArtifactStore) -> None:
        self._store = store

    def get_bytes(self, selector: ArtifactSelector) -> bytes:
        return self._read(self._store.get_bytes, selector)

    def get_manifest_bytes(self, selector: ArtifactSelector) -> bytes:
        return self._read(self._store.get_manifest_bytes, selector)

    def get_manifest(self, selector: ArtifactSelector) -> object:
        return self._read(self._store.get_manifest, selector)

    @staticmethod
    def _read(
        reader: Callable[[ArtifactSelector], _ReadResult],
        selector: ArtifactSelector,
    ) -> _ReadResult:
        try:
            return reader(selector)
        except (FileNotFoundError, TypeError, ValueError, MemoryError):
            raise
        except Exception:
            raise ExplanationBundleStoreReadError(ExplanationBundleStoreReadError.code) from None


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
        canon_spec=IRCanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    try:
        selected_ref = ExplanationBundleRef.model_validate(reference)
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_persisted_ref_invalid") from exc
    if selected_ref.manifest_profile_sha256 is None:
        raise ValueError("explanation_bundle_persisted_profile_missing")
    return selected_ref


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
        ExplanationBundleStoreReadError: If a selected store read fails unexpectedly.
        ValueError: If the ref, selected manifest, or persisted bundle is invalid.
    """
    try:
        selected_ref = ExplanationBundleRef.model_validate(_reference_payload(reference))
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_ref_invalid") from exc

    ir_store = ensure_ir_artifact_store(store)
    if not all(
        callable(getattr(ir_store, method_name, None))
        for method_name in ("get_manifest", "get_manifest_bytes", "get_bytes")
    ):
        raise TypeError("artifact store does not support selected BERL reads")
    try:
        manifest = ir_store.get_manifest(selected_ref)
    except FileNotFoundError as exc:
        raise ValueError("explanation_bundle_manifest_contract_mismatch") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("explanation_bundle_manifest_contract_mismatch") from exc
    except MemoryError:
        raise
    except Exception:
        raise ExplanationBundleStoreReadError(ExplanationBundleStoreReadError.code) from None

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
        payload = get_json_artifact(
            cast("IRArtifactStore", _SelectedViewReadAdapter(ir_store)), selected_ref
        )
    except ExplanationBundleStoreReadError:
        raise
    except FileNotFoundError as exc:
        raise ValueError("explanation_bundle_persisted_payload_invalid") from exc
    except (TypeError, ValueError) as exc:
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
        # Validate with Pydantic's strict JSON path: unlike ``model_validate`` this
        # retains JSON-native datetime parsing while refusing Python coercions
        # (for example numeric strings and booleans in numeric wire slots).
        return ExplanationBundle.model_validate_json(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), strict=True
        )
    except (TypeError, ValidationError, ValueError) as exc:
        raise ValueError("explanation_bundle_persisted_payload_invalid") from exc


def _reference_payload(
    reference: ExplanationBundleRef | Mapping[str, object],
) -> Mapping[str, object]:
    if isinstance(reference, ExplanationBundleRef):
        return reference.model_dump(mode="python")
    return reference


__all__ = [
    "ExplanationBundleStoreReadError",
    "load_explanation_bundle",
    "persist_explanation_bundle",
]
