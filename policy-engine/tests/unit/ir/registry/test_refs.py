from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import SchemaInfo as CoreSchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.contracts import ArtifactID, normalize_artifact_ref
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel, StrategicPayoffTableRef


def test_artifact_ref_model_preserves_selected_manifest_profile() -> None:
    profile = "sha256:" + "a" * 64

    ref = StrategicPayoffTableRef.model_validate(
        {
            "artifact_id": "sha256:" + "b" * 64,
            "kind": "ir.strategic_payoff_table",
            "media_type": "application/json",
            "manifest_profile_sha256": profile,
        }
    )

    assert ref.manifest_profile_sha256 == profile
    assert dict(ref) == {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "ir.strategic_payoff_table",
        "media_type": "application/json",
        "manifest_profile_sha256": profile,
    }
    assert len(ref) == 4


def test_artifact_ref_model_keeps_profileless_legacy_mapping() -> None:
    ref = StrategicPayoffTableRef(artifact_id="sha256:" + "c" * 64)

    assert ref.manifest_profile_sha256 is None
    assert dict(ref) == {
        "artifact_id": "sha256:" + "c" * 64,
        "kind": "ir.strategic_payoff_table",
        "media_type": "application/json",
    }
    assert len(ref) == 3


@pytest.mark.parametrize(
    "value",
    ["sha256:" + "A" * 64, "sha256:short", "not-a-profile", 42],
)
def test_artifact_ref_model_rejects_malformed_profile(value: object) -> None:
    with pytest.raises(ValidationError):
        ArtifactRefModel.model_validate(
            {
                "artifact_id": "sha256:" + "d" * 64,
                "kind": "ir.example",
                "media_type": "application/json",
                "manifest_profile_sha256": value,
            }
        )


def test_artifact_ref_model_refuses_unknown_selector_fields() -> None:
    with pytest.raises(ValidationError):
        ArtifactRefModel.model_validate(
            {
                "artifact_id": "sha256:" + "e" * 64,
                "kind": "ir.example",
                "media_type": "application/json",
                "manifest_profile_sha256": "sha256:" + "f" * 64,
                "selector_hint": "ignore me",
            }
        )


def test_normalize_artifact_ref_uses_the_strict_shared_ref_schema() -> None:
    legacy = ArtifactRefModel(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.example",
        media_type="application/json",
    )
    selected = {
        "artifact_id": "sha256:" + "2" * 64,
        "kind": "ir.example",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "3" * 64,
    }

    assert normalize_artifact_ref(legacy) == dict(legacy)
    assert normalize_artifact_ref(selected) == selected
    with pytest.raises(ValidationError):
        normalize_artifact_ref({**selected, "selection_hint": "unknown"})

    class PropertySelectorWithExtraField:
        def __init__(self) -> None:
            self.artifact_id = legacy.artifact_id
            self.kind = legacy.kind
            self.media_type = legacy.media_type

        @property
        def selection_hint(self) -> str:
            return "must not be dropped"

    class PropertyOnlySelector:
        @property
        def artifact_id(self) -> object:
            return legacy.artifact_id

        @property
        def kind(self) -> str:
            return legacy.kind

        @property
        def media_type(self) -> str:
            return legacy.media_type

    class MappingSelectorWithExtraField(dict[str, object]):
        @property
        def selection_hint(self) -> str:
            return "must not be dropped from a mapping"

    class ModelSelectorWithExcludedExtra(BaseModel):
        model_config = ConfigDict(extra="forbid")

        artifact_id: object
        kind: str
        media_type: str
        manifest_profile_sha256: str | None = None
        selection_hint: str = Field(exclude=True)

    class ExtendedArtifactRef(ArtifactRefModel):
        selection_hint: str

    @dataclass(frozen=True)
    class DataclassSelector:
        artifact_id: object
        kind: str
        media_type: str
        manifest_profile_sha256: str | None = None

    class SlotsSelector:
        __slots__ = ("artifact_id", "kind", "media_type")

        def __init__(self) -> None:
            self.artifact_id = legacy.artifact_id
            self.kind = legacy.kind
            self.media_type = legacy.media_type

    class SlotsSelectorWithExtra(SlotsSelector):
        __slots__ = ("selection_hint",)

        def __init__(self) -> None:
            super().__init__()
            self.selection_hint = "extra"

    class StringifyingSelector:
        def __str__(self) -> str:
            return "sha256:" + "f" * 64

    @dataclass(frozen=True)
    class DataclassSelectorWithExtra:
        artifact_id: object
        kind: str
        media_type: str
        selection_hint: str
        manifest_profile_sha256: str | None = None

    for selector in (
        PropertySelectorWithExtraField(),
        MappingSelectorWithExtraField(selected),
        ModelSelectorWithExcludedExtra(
            artifact_id=legacy.artifact_id,
            kind=legacy.kind,
            media_type=legacy.media_type,
            selection_hint="excluded from model_dump",
        ),
        ExtendedArtifactRef(
            **legacy.model_dump(mode="python"),
            selection_hint="extra mapping field",
        ),
    ):
        with pytest.raises(TypeError, match="unexpected field"):
            normalize_artifact_ref(selector)

    with pytest.raises(TypeError, match="unexpected field"):
        normalize_artifact_ref(
            DataclassSelectorWithExtra(
                **legacy.model_dump(mode="python"),
                selection_hint="extra",
            )
        )
    with pytest.raises(TypeError, match="unexpected field"):
        normalize_artifact_ref(SlotsSelectorWithExtra())
    with pytest.raises(TypeError, match="required fields"):
        normalize_artifact_ref(StringifyingSelector())
    assert normalize_artifact_ref(
        DataclassSelector(
            artifact_id=legacy.artifact_id,
            kind=legacy.kind,
            media_type=legacy.media_type,
        )
    ) == dict(legacy)
    assert normalize_artifact_ref(PropertyOnlySelector()) == dict(legacy)
    assert normalize_artifact_ref(SlotsSelector()) == dict(legacy)


def test_get_json_artifact_rejects_property_extension_before_manifest_or_payload_reads(
    tmp_path, monkeypatch
) -> None:
    core_store = FileSystemCAS(tmp_path / "strict-selector-cas")
    ir_store = ensure_ir_artifact_store(core_store)
    stored_ref = put_json_artifact(
        ir_store,
        {"accepted": True},
        kind="ir.strict-selector-test",
        schema_name="ir.strict-selector-test",
        schema_version="1",
    )
    assert get_json_artifact(ir_store, stored_ref["artifact_id"]) == {"accepted": True}
    assert get_json_artifact(
        ir_store,
        ArtifactID.model_validate(stored_ref["artifact_id"]),
    ) == {"accepted": True}
    assert get_json_artifact(
        ir_store,
        CoreArtifactID.model_validate(stored_ref["artifact_id"]),
    ) == {"accepted": True}

    class PropertySelectorWithExtraField:
        def __init__(self) -> None:
            self.artifact_id = stored_ref["artifact_id"]
            self.kind = stored_ref["kind"]
            self.media_type = stored_ref["media_type"]

        @property
        def selection_hint(self) -> str:
            return "not part of the selected view contract"

    class RootOnlyObject:
        root = stored_ref["artifact_id"]

    class StringDumpObject:
        def model_dump(self, *, mode: str) -> str:
            return stored_ref["artifact_id"]

    reads = {"manifest": 0, "payload": 0}
    get_manifest_bytes = core_store.get_manifest_bytes
    get_bytes = core_store.get_bytes

    def record_manifest_read(selector):
        reads["manifest"] += 1
        return get_manifest_bytes(selector)

    def record_payload_read(selector):
        reads["payload"] += 1
        return get_bytes(selector)

    monkeypatch.setattr(core_store, "get_manifest_bytes", record_manifest_read)
    monkeypatch.setattr(core_store, "get_bytes", record_payload_read)

    for invalid_selector in (
        PropertySelectorWithExtraField(),
        RootOnlyObject(),
        StringDumpObject(),
    ):
        with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
            get_json_artifact(ir_store, invalid_selector)

    assert reads == {"manifest": 0, "payload": 0}


def test_typed_artifact_ref_fresh_load_keeps_selected_manifest_view(tmp_path) -> None:
    root = tmp_path / "cas"
    producer = FileSystemCAS(root)
    raw = b'{"nested":{"value":1}}'
    kind = "ir.strategic_payoff_table"
    default_ref = producer.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=kind, version="1.0"),
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = producer.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=kind, version="2.0"),
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    typed_ref = StrategicPayoffTableRef.model_validate(selected_ref.model_dump(mode="json"))
    fresh_reader = FileSystemCAS(root)
    ir_reader = ensure_ir_artifact_store(fresh_reader)

    assert typed_ref.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert ir_reader.get_bytes(typed_ref) == raw
    assert ir_reader.get_manifest(typed_ref).artifact_schema.version == "2.0"
    assert get_json_artifact(_ensure_ir_artifact_store(ir_reader), typed_ref) == {
        "nested": {"value": 1}
    }

    wrong_view = StrategicPayoffTableRef.model_validate(
        {
            **dict(typed_ref),
            "manifest_profile_sha256": "sha256:" + "f" * 64,
        }
    )
    with pytest.raises(FileNotFoundError):
        ir_reader.get_manifest(wrong_view)
    with pytest.raises(FileNotFoundError):
        get_json_artifact(_ensure_ir_artifact_store(ir_reader), wrong_view)
