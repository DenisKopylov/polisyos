"""Selected layout identity for model-owned scalar GLOBAL state slots."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_SLOT_ID = re.compile(r"^[a-z][a-z0-9_.]{0,199}$")


class ModelScalarStateLayoutRef(ArtifactRef):
    """Require the exact CAS view of one selected scalar-state layout."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["foundry.model_scalar_state_layout"] = "foundry.model_scalar_state_layout"
    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=_SHA256.pattern, strict=True)


class ModelScalarStateSlot(BaseModel):
    """One scalar GLOBAL stock's identity and physical position in a selected layout."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    slot_id: str = Field(min_length=1, max_length=200, strict=True)
    index: int = Field(ge=0, strict=True)
    slot_spec_sha256: str = Field(pattern=_SHA256.pattern, strict=True)
    scope: Literal["global"] = "global"
    kind: Literal["stock"] = "stock"
    value_type: Literal["decimal"] = "decimal"
    dtype: Literal["float32"] = "float32"
    shape: tuple[int, ...] = ()

    @model_validator(mode="after")
    def validate_slot_descriptor(self) -> ModelScalarStateSlot:
        """Keep the first carrier limited to named scalar GLOBAL stocks."""

        if _SLOT_ID.fullmatch(self.slot_id) is None:
            raise ValueError("model_scalar_state_slot_id_invalid")
        if self.shape != ():
            raise ValueError("model_scalar_state_slot_must_be_scalar")
        return self


class ModelScalarStateLayout(BaseModel):
    """Exact selected registry and slot-index mapping for a model scalar state vector.

    The array index is only a physical address. The registry bundle reference,
    slot ID, slot-spec digest, and this complete layout digest bind its meaning.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    registry_bundle_ref: ArtifactRef
    slots: tuple[ModelScalarStateSlot, ...] = Field(min_length=1, max_length=256)
    layout_sha256: str = Field(pattern=_SHA256.pattern, strict=True)

    @model_validator(mode="after")
    def validate_selected_layout(self) -> ModelScalarStateLayout:
        """Require exact selected identity, canonical ordering, and a complete digest."""

        if self.registry_bundle_ref.manifest_profile_sha256 is None:
            raise ValueError("model_scalar_state_registry_bundle_profile_required")
        if (
            self.registry_bundle_ref.kind != "core.registry_bundle"
            or self.registry_bundle_ref.media_type != "application/json"
        ):
            raise ValueError("model_scalar_state_registry_bundle_ref_invalid")
        slot_ids = tuple(slot.slot_id for slot in self.slots)
        indices = tuple(slot.index for slot in self.slots)
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("model_scalar_state_slot_ids_must_be_unique")
        if indices != tuple(range(len(self.slots))):
            raise ValueError("model_scalar_state_indices_must_be_contiguous_and_ordered")
        if slot_ids != tuple(sorted(slot_ids)):
            raise ValueError("model_scalar_state_slots_must_be_canonically_ordered")
        expected = model_scalar_state_layout_digest(
            registry_bundle_ref=self.registry_bundle_ref,
            slots=self.slots,
        )
        if self.layout_sha256 != expected:
            raise ValueError("model_scalar_state_layout_digest_mismatch")
        return self

    def slot(self, slot_id: str) -> ModelScalarStateSlot:
        """Resolve one semantic slot ID without treating its index as identity."""

        for descriptor in self.slots:
            if descriptor.slot_id == slot_id:
                return descriptor
        raise KeyError("model_scalar_state_slot_not_in_selected_layout")


def model_scalar_state_layout_digest(
    *,
    registry_bundle_ref: ArtifactRef,
    slots: tuple[ModelScalarStateSlot, ...],
) -> str:
    """Hash the complete selected registry reference and slot-to-index mapping."""

    payload = {
        "schema_version": "1.0",
        "registry_bundle_ref": {
            "artifact_id": str(registry_bundle_ref.artifact_id),
            "kind": registry_bundle_ref.kind,
            "media_type": registry_bundle_ref.media_type,
            "manifest_profile_sha256": registry_bundle_ref.manifest_profile_sha256,
        },
        "registry_bundle_identity": list(artifact_ref_identity_key(registry_bundle_ref)),
        "slots": [slot.model_dump(mode="json") for slot in slots],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
