from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, cast

import pytest
from pydantic import BaseModel, ConfigDict, RootModel, WithJsonSchema

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts.contracts import ArtifactStore
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation


class _ForeignStringRoot(RootModel[Annotated[str, WithJsonSchema({"type": "string"})]]):
    @property
    def hex(self) -> str:
        return self.root.split(":", 1)[1]


class _CountingReader:
    def __init__(self, store: object) -> None:
        self.store = store
        self.raw_manifest_reads = 0
        self.typed_manifest_reads = 0
        self.payload_reads = 0

    def get_manifest_bytes(self, selector: object) -> bytes:
        self.raw_manifest_reads += 1
        reader = getattr(self.store, "get_manifest_bytes", None)
        if not callable(reader):
            raise TypeError("reader does not expose get_manifest_bytes")
        result = reader(selector)
        if not isinstance(result, bytes):
            raise TypeError("get_manifest_bytes must return bytes")
        return result

    def get_manifest(self, selector: object) -> object:
        self.typed_manifest_reads += 1
        reader = getattr(self.store, "get_manifest", None)
        if not callable(reader):
            raise TypeError("reader does not expose get_manifest")
        return reader(selector)

    def get_bytes(self, selector: object) -> bytes:
        self.payload_reads += 1
        reader = getattr(self.store, "get_bytes", None)
        if not callable(reader):
            raise TypeError("reader does not expose get_bytes")
        result = reader(selector)
        if not isinstance(result, bytes):
            raise TypeError("get_bytes must return bytes")
        return result


def _persist_ref(tmp_path: Path) -> tuple[ArtifactStore, dict[str, str]]:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    ref = put_json_artifact(
        store,
        {"value": "payload"},
        kind="test.selector-field-inventory",
        schema_name="test.SelectorFieldInventory",
        schema_version="1.0",
        return_selected_profile=True,
    )
    return store, ref


@pytest.mark.parametrize("selector_shape", ["ordinary", "model_dump"])
def test_ir_reader_rejects_rogue_instance_field_before_manifest_or_payload_reads(
    tmp_path: Path, selector_shape: str
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)

    class Selector:
        class_marker: ClassVar[str] = "class metadata"

        def __init__(self) -> None:
            self.artifact_id = ref["artifact_id"]
            self.kind = ref["kind"]
            self.media_type = ref["media_type"]
            self.manifest_profile_sha256 = ref["manifest_profile_sha256"]
            self.rogue = "unexpected"

    class MutatingModelDumpSelector(Selector):
        def model_dump(self, *, mode: str) -> dict[str, object]:
            del self.rogue
            return {
                "artifact_id": self.artifact_id,
                "kind": self.kind,
                "media_type": self.media_type,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    selector = MutatingModelDumpSelector() if selector_shape == "model_dump" else Selector()
    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), selector)

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    if selector_shape == "model_dump":
        assert selector.rogue == "unexpected"


@pytest.mark.parametrize("selector_shape", ["ordinary", "model_dump"])
def test_ir_reader_accepts_genuine_classvar_only_selector(
    tmp_path: Path, selector_shape: str
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)

    class Selector:
        class_marker: ClassVar[str] = "class metadata"

        def __init__(self) -> None:
            self.artifact_id = ref["artifact_id"]
            self.kind = ref["kind"]
            self.media_type = ref["media_type"]
            self.manifest_profile_sha256 = ref["manifest_profile_sha256"]

    class ModelDumpSelector(Selector):
        def model_dump(self, *, mode: str) -> dict[str, object]:
            return {
                "artifact_id": self.artifact_id,
                "kind": self.kind,
                "media_type": self.media_type,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    selector = ModelDumpSelector() if selector_shape == "model_dump" else Selector()
    assert get_json_artifact(cast("ArtifactStore", reader), selector) == {"value": "payload"}
    assert reader.raw_manifest_reads == 1
    assert reader.typed_manifest_reads == 1
    assert reader.payload_reads == 1


def test_ir_reader_rejects_pydantic_extra_hidden_by_model_dump_before_reads(
    tmp_path: Path,
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)
    projection_calls: list[str] = []

    class MutatingExtraSelector(BaseModel):
        model_config = ConfigDict(extra="allow")

        artifact_id: str
        kind: str
        media_type: str
        manifest_profile_sha256: str | None

        def model_dump(self, *, mode: str = "python") -> dict[str, object]:
            projection_calls.append(mode)
            extras = object.__getattribute__(self, "__pydantic_extra__")
            if extras is not None:
                extras.pop("rogue", None)
            return {
                "artifact_id": self.artifact_id,
                "kind": self.kind,
                "media_type": self.media_type,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    selector = MutatingExtraSelector(**ref, rogue="unexpected")
    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), selector)

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    assert projection_calls == []
    assert object.__getattribute__(selector, "__pydantic_extra__")["rogue"] == "unexpected"


def test_ir_reader_accepts_scalar_root_computed_property_and_counts_both_manifests(
    tmp_path: Path,
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)
    selector = _ForeignStringRoot(ref["artifact_id"])

    assert selector.hex == ref["artifact_id"].split(":", 1)[1]
    assert get_json_artifact(cast("ArtifactStore", reader), selector) == {"value": "payload"}
    assert reader.raw_manifest_reads == 1
    assert reader.typed_manifest_reads == 1
    assert reader.payload_reads == 1


def test_ir_reader_rejects_scalar_root_unknown_value_before_projection_or_reads(
    tmp_path: Path,
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)
    projection_calls: list[str] = []

    class MutatingForeignRoot(_ForeignStringRoot):
        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            object.__getattribute__(self, "__dict__").pop("rogue", None)
            return self.root

    selector = MutatingForeignRoot(ref["artifact_id"])
    object.__setattr__(selector, "rogue", "unexpected")
    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), selector)

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    assert projection_calls == []
    assert object.__getattribute__(selector, "__dict__")["rogue"] == "unexpected"


def test_ir_reader_rejects_scalar_root_declared_slot_before_manifest_reads(
    tmp_path: Path,
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)

    class SlottedForeignRoot(_ForeignStringRoot):
        __slots__ = ("rogue",)

    selector = SlottedForeignRoot(ref["artifact_id"])
    object.__setattr__(selector, "rogue", "unexpected")
    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), selector)

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    assert object.__getattribute__(selector, "rogue") == "unexpected"


@pytest.mark.parametrize("stored_root_is_valid", [True, False])
def test_ir_reader_rejects_scalar_root_projection_substitution_before_reads(
    tmp_path: Path, stored_root_is_valid: bool
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)
    valid_id = ref["artifact_id"]
    alternate_hex = "0" * 64 if valid_id != "sha256:" + "0" * 64 else "1" * 64
    alternate_id = "sha256:" + alternate_hex
    stored_root = valid_id if stored_root_is_valid else "not-an-artifact-id"
    projection_calls: list[str] = []

    class SubstitutingRoot(_ForeignStringRoot):
        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            return alternate_id

    selector = SubstitutingRoot(stored_root)
    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), selector)

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    assert projection_calls == (["python"] if stored_root_is_valid else [])
    assert object.__getattribute__(selector, "__dict__")["root"] == stored_root


def test_ir_reader_rejects_fake_scalar_root_markers_with_rogue_property_before_reads(
    tmp_path: Path,
) -> None:
    store, ref = _persist_ref(tmp_path)
    reader = _CountingReader(store)
    projection_calls: list[str] = []

    class FakeRootField:
        annotation = str

    class FakeRootSelector:
        __pydantic_root_model__ = True
        model_fields: ClassVar[dict[str, object]] = {"root": FakeRootField()}

        @property
        def root(self) -> str:
            return ref["artifact_id"]

        @property
        def rogue(self) -> str:
            return "unexpected"

        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            return ref["artifact_id"]

    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(cast("ArtifactStore", reader), FakeRootSelector())

    assert reader.raw_manifest_reads == 0
    assert reader.typed_manifest_reads == 0
    assert reader.payload_reads == 0
    assert projection_calls == []
