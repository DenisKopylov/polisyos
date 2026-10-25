from __future__ import annotations

from collections import UserDict
from collections.abc import Iterator, Mapping
from dataclasses import InitVar, dataclass
from dataclasses import field as dataclass_field
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import polisyos.ir.artifacts.contracts as _artifact_contracts
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import SchemaInfo as CoreSchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.contracts import (
    ArtifactID,
    normalize_artifact_ref,
    normalize_input_refs,
)
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


def test_artifact_ref_from_selected_write_requires_selected_profile() -> None:
    profileless = {
        "artifact_id": "sha256:" + "c" * 64,
        "kind": "ir.strategic_payoff_table",
        "media_type": "application/json",
    }

    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        StrategicPayoffTableRef.from_selected_write(profileless)


def test_artifact_ref_from_selected_write_refuses_a_different_typed_identity() -> None:
    selected = {
        "artifact_id": "sha256:" + "d" * 64,
        "kind": "ir.not_a_strategic_payoff_table",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "e" * 64,
    }

    with pytest.raises(ValidationError):
        StrategicPayoffTableRef.from_selected_write(selected)


def test_artifact_ref_from_selected_write_uses_one_mapping_snapshot() -> None:
    profile = "sha256:" + "f" * 64
    values: dict[str, object] = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": "ir.strategic_payoff_table",
        "media_type": "application/json",
        "manifest_profile_sha256": profile,
    }

    class InconsistentSelectedWriteMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            return values[key]

        def __iter__(self) -> Iterator[str]:
            for key in values:
                if key != "manifest_profile_sha256":
                    yield key

        def __len__(self) -> int:
            return len(values) - 1

    selected = InconsistentSelectedWriteMapping()
    assert selected.get("manifest_profile_sha256") == profile
    assert "manifest_profile_sha256" not in dict(selected)

    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        StrategicPayoffTableRef.from_selected_write(selected)


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


def test_normalize_artifact_ref_preserves_raw_mapping_error_class_before_projection() -> None:
    selected = {
        "artifact_id": "sha256:" + "2" * 64,
        "kind": "ir.example",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "3" * 64,
        "selection_hint": "unknown payload field",
    }

    class ProjectingMapping(Mapping[str, object]):
        __slots__ = ("_projection_calls", "_values")

        def __init__(self, values: Mapping[str, object]) -> None:
            self._values = dict(values)
            self._projection_calls = 0

        def __getitem__(self, key: str) -> object:
            return self._values[key]

        def __iter__(self) -> Iterator[str]:
            return iter(self._values)

        def __len__(self) -> int:
            return len(self._values)

        def model_dump(self, *, mode: str) -> object:
            self._projection_calls += 1
            return {key: value for key, value in self._values.items() if key != "selection_hint"}

    projecting = ProjectingMapping(selected)
    for raw_mapping in (selected, projecting):
        with pytest.raises(ValidationError):
            normalize_artifact_ref(raw_mapping)
    assert projecting._projection_calls == 0

    class MappingChangingShape(ProjectingMapping):
        def __getitem__(self, key: str) -> object:
            value = super().__getitem__(key)
            if key == "selection_hint":
                self._values["late_selector_field"] = "added during materialization"
            return value

    with pytest.raises(TypeError, match="mapping changed during materialization"):
        normalize_artifact_ref(MappingChangingShape(selected))

    class MappingWithDeclaredExtra(ProjectingMapping):
        @property
        def selection_hint(self) -> str:
            return "structural selector field"

    valid_selected = {key: value for key, value in selected.items() if key != "selection_hint"}
    with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
        normalize_artifact_ref(MappingWithDeclaredExtra(valid_selected))


def test_normalize_artifact_ref_uses_exact_registered_facade_extractor() -> None:
    artifact_id = "sha256:" + "1" * 64

    class RegisteredFacade:
        __slots__ = ("_projection_calls", "_target")

        def __init__(self, target: object) -> None:
            self._target = target
            self._projection_calls = 0

        @property
        def __class__(self) -> type[object]:
            return type(self._target)

        def model_dump(self, *, mode: str) -> object:
            assert mode == "python"
            self._projection_calls += 1
            return {}

    def extract_target(value: object) -> object:
        return object.__getattribute__(value, "_target")

    registry = _artifact_contracts._TRUSTED_ARTIFACT_REF_FACADE_EXTRACTORS
    previous = registry.get(RegisteredFacade)
    was_registered = RegisteredFacade in registry
    _artifact_contracts._register_trusted_artifact_ref_facade(RegisteredFacade, extract_target)
    try:
        target = ArtifactRefModel(
            artifact_id=artifact_id,
            kind="ir.example",
            media_type="application/json",
        )
        facade = RegisteredFacade(target)
        assert isinstance(facade, ArtifactRefModel)
        assert normalize_artifact_ref(facade) == normalize_artifact_ref(target)
        assert facade._projection_calls == 0

        class HiddenExtraModel(BaseModel):
            model_config = ConfigDict(extra="forbid")

            artifact_id: str
            kind: str
            media_type: str
            selection_hint: str = Field(exclude=True)

        hidden_target = HiddenExtraModel(
            artifact_id=artifact_id,
            kind="ir.example",
            media_type="application/json",
            selection_hint="must remain visible before projection",
        )
        hidden_facade = RegisteredFacade(hidden_target)
        with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
            normalize_artifact_ref(hidden_facade)
        assert hidden_facade._projection_calls == 0

        class UnregisteredSubclass(RegisteredFacade):
            __slots__ = ()

        unregistered = UnregisteredSubclass(target)
        with pytest.raises(TypeError):
            normalize_artifact_ref(unregistered)
        assert unregistered._projection_calls == 0
    finally:
        if was_registered:
            registry[RegisteredFacade] = previous
        else:
            registry.pop(RegisteredFacade, None)


def test_normalize_artifact_ref_rejects_unregistered_class_view_without_projection() -> None:
    target = ArtifactRefWithHiddenSelectorField(
        artifact_id="sha256:" + "2" * 64,
        kind="ir.example",
        media_type="application/json",
        selection_hint="must remain visible before projection",
    )

    class UnregisteredFacade:
        __slots__ = ("_projection_calls", "_target")

        def __init__(self, wrapped: BaseModel) -> None:
            self._target = wrapped
            self._projection_calls = 0

        @property
        def __class__(self) -> type[object]:
            return type(self._target)

        def __getattr__(self, name: str) -> object:
            if name in {"artifact_id", "kind", "media_type", "manifest_profile_sha256"}:
                return getattr(self._target, name)
            raise AttributeError(name)

        def model_dump(self, *, mode: str) -> object:
            assert mode == "python"
            self._projection_calls += 1
            return {
                "artifact_id": self._target.artifact_id,
                "kind": self._target.kind,
                "media_type": self._target.media_type,
            }

    facade = UnregisteredFacade(target)
    assert isinstance(facade, BaseModel)
    assert BaseModel not in type(facade).__mro__
    with pytest.raises(
        TypeError,
        match="claims Pydantic model without actual Pydantic storage",
    ):
        normalize_artifact_ref(facade)
    assert facade._projection_calls == 0


def test_normalize_artifact_ref_accepts_unclaimed_structural_selector() -> None:
    class StructuralSelector:
        def __init__(self) -> None:
            self.artifact_id = "sha256:" + "3" * 64
            self.kind = "ir.example"
            self.media_type = "application/json"

    selector = StructuralSelector()

    assert not isinstance(selector, BaseModel)
    assert normalize_artifact_ref(selector) == {
        "artifact_id": "sha256:" + "3" * 64,
        "kind": "ir.example",
        "media_type": "application/json",
    }


class ArtifactRefWithHiddenSelectorField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    media_type: str
    selection_hint: str = Field(exclude=True)


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


def test_normalize_artifact_ref_uses_dataclass_instances_not_field_markers() -> None:
    expected = {
        "artifact_id": "sha256:" + "d" * 64,
        "kind": "ir.structural_ref",
        "media_type": "application/json",
    }

    class StructuralSelector:
        __dataclass_fields__: ClassVar[dict[str, object]] = {}

        def __init__(self) -> None:
            self.artifact_id = expected["artifact_id"]
            self.kind = expected["kind"]
            self.media_type = expected["media_type"]

    assert normalize_artifact_ref(StructuralSelector()) == expected


def test_normalize_artifact_ref_refuses_malformed_dataclass_field_metadata() -> None:
    class MalformedSelector:
        __dataclass_fields__: ClassVar[dict[str, object]] = {"artifact_id": object()}

        def __init__(self) -> None:
            self.artifact_id = "sha256:" + "d" * 64
            self.kind = "ir.structural_ref"
            self.media_type = "application/json"

    with pytest.raises(TypeError, match="malformed field metadata"):
        normalize_artifact_ref(MalformedSelector())


def test_normalize_artifact_ref_does_not_use_dataclass_class_defaults() -> None:
    @dataclass(frozen=True, slots=True)
    class DefaultedSelector:
        artifact_id: str = "sha256:" + "e" * 64
        kind: str = "ir.structural_ref"
        media_type: str = "application/json"

    with pytest.raises(TypeError, match="dataclass selector must be an instance"):
        normalize_artifact_ref(DefaultedSelector)


def test_normalize_artifact_ref_keeps_slotted_dataclass_extension_refusal() -> None:
    @dataclass(frozen=True, slots=True)
    class ExtendedSelector:
        artifact_id: str = "sha256:" + "f" * 64
        kind: str = "ir.structural_ref"
        media_type: str = "application/json"
        selection_hint: str = "extra field"

    with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
        normalize_artifact_ref(ExtendedSelector())


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
        {
            "artifact_id": stored_ref["artifact_id"],
            "kind": stored_ref["kind"],
            "media_type": stored_ref["media_type"],
            "selection_hint": "unknown payload field",
        },
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

    typed_ref = StrategicPayoffTableRef.from_selected_write(selected_ref.model_dump(mode="json"))
    fresh_reader = FileSystemCAS(root)
    ir_reader = ensure_ir_artifact_store(fresh_reader)

    assert typed_ref.model_dump(mode="json") == selected_ref.model_dump(mode="json")
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


def test_normalize_artifact_ref_rejects_incoherent_dataclass_metadata() -> None:
    @dataclass(frozen=True)
    class FieldSource:
        artifact_id: str
        kind: str
        media_type: str

    fields_by_name = FieldSource.__dataclass_fields__
    valid_metadata = {
        "artifact_id": fields_by_name["artifact_id"],
        "kind": fields_by_name["kind"],
        "media_type": fields_by_name["media_type"],
    }

    class DuplicateKeyMapping(Mapping[str, object]):
        def __init__(self, values: Mapping[str, object]) -> None:
            self._values = values

        def __getitem__(self, key: str) -> object:
            return self._values[key]

        def __iter__(self) -> Iterator[str]:
            return iter(("artifact_id", "artifact_id", "kind", "media_type"))

        def __len__(self) -> int:
            return 4

    class DuplicateItemsMapping(DuplicateKeyMapping):
        def __iter__(self) -> Iterator[str]:
            return iter(("artifact_id", "kind", "media_type"))

        def __len__(self) -> int:
            return 3

        def items(self) -> Iterator[tuple[str, object]]:
            return iter(
                (
                    ("artifact_id", self._values["artifact_id"]),
                    ("artifact_id", self._values["artifact_id"]),
                    ("kind", self._values["kind"]),
                    ("media_type", self._values["media_type"]),
                )
            )

    malformed_metadata: dict[str, object] = {
        "key_name_mismatch": {
            "selection_hint": fields_by_name["artifact_id"],
            "kind": fields_by_name["kind"],
            "media_type": fields_by_name["media_type"],
        },
        "duplicate_field_identity": {
            "artifact_id": fields_by_name["artifact_id"],
            "kind": fields_by_name["artifact_id"],
            "media_type": fields_by_name["media_type"],
        },
        "non_field_value": {
            "artifact_id": fields_by_name["artifact_id"],
            "kind": object(),
            "media_type": fields_by_name["media_type"],
        },
        "invalid_field_name": {
            "artifact_id": dataclass_field(),
            "kind": fields_by_name["kind"],
            "media_type": fields_by_name["media_type"],
        },
        "non_string_key": {
            1: fields_by_name["artifact_id"],
            "kind": fields_by_name["kind"],
            "media_type": fields_by_name["media_type"],
        },
        "non_mapping_marker": object(),
        "duplicate_mapping_key": DuplicateKeyMapping(valid_metadata),
        "duplicate_mapping_item": DuplicateItemsMapping(valid_metadata),
    }

    for name, metadata in malformed_metadata.items():
        selector_type = type("MetadataSelector", (), {"__dataclass_fields__": metadata})
        selector = selector_type()
        selector.artifact_id = "sha256:" + "d" * 64
        selector.kind = "ir.example"
        selector.media_type = "application/json"

        try:
            normalize_artifact_ref(selector)
        except TypeError:
            continue
        pytest.fail(f"{name} dataclass metadata was accepted")


def test_normalize_artifact_ref_rejects_unknown_dataclass_raw_classvar_and_initvar() -> None:
    @dataclass(frozen=True)
    class ClassVarExtension:
        artifact_id: str
        kind: str
        media_type: str
        selection_hint: ClassVar[str] = "unknown"

    @dataclass(frozen=True)
    class InitVarExtension:
        artifact_id: str
        kind: str
        media_type: str
        selection_hint: InitVar[str]

    with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
        normalize_artifact_ref(
            ClassVarExtension("sha256:" + "d" * 64, "ir.example", "application/json")
        )
    with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
        normalize_artifact_ref(
            InitVarExtension("sha256:" + "d" * 64, "ir.example", "application/json", "extra")
        )


def test_normalize_artifact_ref_accepts_inherited_dataclass_metadata_and_rejects_slots() -> None:
    @dataclass(frozen=True)
    class BaseSelector:
        artifact_id: str
        kind: str
        media_type: str

    @dataclass(frozen=True)
    class ExtendedSelector(BaseSelector):
        manifest_profile_sha256: str | None = None

    class UndecoratedInheritedSelector(BaseSelector):
        pass

    class SlotExtension:
        __slots__ = ("selection_hint",)

    @dataclass
    class SlottedDataclassSelector(SlotExtension):
        artifact_id: str
        kind: str
        media_type: str

    base_args = ("sha256:" + "d" * 64, "ir.example", "application/json")
    assert normalize_artifact_ref(ExtendedSelector(*base_args)) == {
        "artifact_id": base_args[0],
        "kind": base_args[1],
        "media_type": base_args[2],
    }
    assert normalize_artifact_ref(UndecoratedInheritedSelector(*base_args)) == {
        "artifact_id": base_args[0],
        "kind": base_args[1],
        "media_type": base_args[2],
    }

    slotted = SlottedDataclassSelector(*base_args)
    slotted.selection_hint = "extra"
    with pytest.raises(TypeError, match="unexpected field.*selection_hint"):
        normalize_artifact_ref(slotted)


def test_normalize_artifact_ref_empty_dataclass_uses_only_structural_contract() -> None:
    @dataclass(frozen=True)
    class EmptyDataclass:
        pass

    with pytest.raises(TypeError, match="required fields"):
        normalize_artifact_ref(EmptyDataclass())


def test_normalize_artifact_ref_refuses_schema_members_without_values() -> None:
    profile = "sha256:" + "9" * 64
    artifact_id = "sha256:" + "8" * 64

    @dataclass(frozen=True)
    class InitVarProfileSelector:
        artifact_id: str
        kind: str
        media_type: str
        manifest_profile_sha256: InitVar[str | None]

    @dataclass(frozen=True)
    class ClassVarProfileSelector:
        artifact_id: str
        kind: str
        media_type: str
        manifest_profile_sha256: ClassVar[str | None] = profile

    @dataclass(frozen=True)
    class InitVarKindSelector:
        artifact_id: str
        kind: InitVar[str]
        media_type: str

    with pytest.raises(TypeError, match="must be value-bearing"):
        normalize_artifact_ref(
            InitVarProfileSelector(artifact_id, "ir.example", "application/json", profile)
        )
    with pytest.raises(TypeError, match="must be value-bearing"):
        normalize_artifact_ref(
            ClassVarProfileSelector(artifact_id, "ir.example", "application/json")
        )
    with pytest.raises(TypeError, match="must be value-bearing"):
        normalize_artifact_ref(InitVarKindSelector(artifact_id, "ir.example", "application/json"))

    @dataclass(frozen=True)
    class StoredProfileSelector:
        artifact_id: str
        kind: str
        media_type: str
        manifest_profile_sha256: str | None = None

    stored = StoredProfileSelector(artifact_id, "ir.example", "application/json", profile)
    assert normalize_artifact_ref(stored) == {
        "artifact_id": artifact_id,
        "kind": "ir.example",
        "media_type": "application/json",
        "manifest_profile_sha256": profile,
    }

    @dataclass(frozen=True)
    class LegacyProfilelessSelector:
        artifact_id: str
        kind: str
        media_type: str

    legacy = LegacyProfilelessSelector(artifact_id, "ir.example", "application/json")
    assert normalize_artifact_ref(legacy) == {
        "artifact_id": artifact_id,
        "kind": "ir.example",
        "media_type": "application/json",
    }


def test_normalize_input_refs_preserves_mapping_and_model_dump_payloads() -> None:
    artifact_id = "sha256:" + "a" * 64
    profile = "sha256:" + "b" * 64
    payload = {
        "artifact_id": artifact_id,
        "role": "input",
        "manifest_profile_sha256": profile,
    }

    class DumpedReference:
        def model_dump(self, *, mode: str) -> object:
            assert mode == "python"
            return UserDict(payload)

    references = normalize_input_refs([UserDict(payload), DumpedReference()])

    assert len(references) == 2
    for reference in references:
        assert str(reference.artifact_id) == artifact_id
        assert reference.role == "input"
        assert reference.manifest_profile_sha256 == profile


def test_normalize_input_refs_rejects_non_string_payload_keys() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        normalize_input_refs(
            [{"artifact_id": "sha256:" + "c" * 64, "role": "input", 17: "unexpected"}]
        )


def test_normalize_input_refs_rejects_non_mapping_model_dump() -> None:
    class PairSequenceDump:
        def model_dump(self, *, mode: str) -> object:
            assert mode == "python"
            return [
                ("artifact_id", "sha256:" + "d" * 64),
                ("role", "input"),
            ]

    with pytest.raises(TypeError, match="must be a mapping"):
        normalize_input_refs([PairSequenceDump()])


def test_normalize_input_refs_rejects_duplicate_mapping_keys() -> None:
    class DuplicateKeyMapping(UserDict[str, object]):
        def __iter__(self):
            return iter(("artifact_id", "role", "role"))

        def __len__(self) -> int:
            return 3

    with pytest.raises(TypeError, match="duplicate key"):
        normalize_input_refs(
            [DuplicateKeyMapping({"artifact_id": "sha256:" + "e" * 64, "role": "input"})]
        )


def test_normalize_input_refs_keeps_unknown_fields_fail_closed() -> None:
    with pytest.raises(ValidationError):
        normalize_input_refs(
            [
                {
                    "artifact_id": "sha256:" + "f" * 64,
                    "role": "input",
                    "selection_hint": "must not be dropped",
                }
            ]
        )


def test_normalize_input_refs_preserves_attribute_fallback() -> None:
    artifact_id = "sha256:" + "1" * 64
    profile = "sha256:" + "2" * 64

    class AttributeReference:
        def __init__(self) -> None:
            self.artifact_id = artifact_id
            self.role = "input"
            self.manifest_profile_sha256 = profile

    reference = normalize_input_refs([AttributeReference()])[0]

    assert str(reference.artifact_id) == artifact_id
    assert reference.role == "input"
    assert reference.manifest_profile_sha256 == profile


@pytest.mark.parametrize("via_model_dump", [False, True], ids=["mapping", "model_dump"])
def test_normalize_input_refs_keeps_mapping_keys_when_items_omits_them(
    via_model_dump: bool,
) -> None:
    artifact_id = "sha256:" + "a" * 64
    payload = {
        "artifact_id": artifact_id,
        "role": "input",
        "selection_hint": "must remain visible to strict validation",
    }

    class ItemsOmissionMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            return payload[key]

        def __iter__(self) -> Iterator[str]:
            return iter(payload)

        def __len__(self) -> int:
            return len(payload)

        def items(self) -> Iterator[tuple[str, object]]:
            return iter(
                (
                    ("artifact_id", payload["artifact_id"]),
                    ("role", payload["role"]),
                )
            )

    class DumpedItemsOmission:
        def model_dump(self, *, mode: str) -> object:
            assert mode == "python"
            return ItemsOmissionMapping()

    supplied: object = ItemsOmissionMapping()
    if via_model_dump:
        supplied = DumpedItemsOmission()
    with pytest.raises(ValidationError):
        normalize_input_refs([supplied])


def test_normalize_input_refs_refuses_mapping_key_without_value() -> None:
    class MissingValueMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            if key == "artifact_id":
                return "sha256:" + "b" * 64
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            return iter(("artifact_id", "role"))

        def __len__(self) -> int:
            return 2

        def items(self) -> Iterator[tuple[str, object]]:
            return iter((("artifact_id", self["artifact_id"]),))

    with pytest.raises(TypeError, match="no corresponding value: role"):
        normalize_input_refs([MissingValueMapping()])
