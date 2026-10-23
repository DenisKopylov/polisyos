from __future__ import annotations

import json
from typing import ClassVar, cast

import jsonschema
import pytest
from pydantic import ValidationError

from polisyos.ir.artifacts.contracts import ArtifactID

DIGEST = "a" * 64


def test_prefix_subclass_cannot_change_normalized_artifact_text() -> None:
    callbacks: list[str] = []

    class Prefix(str):
        def __len__(self) -> int:
            callbacks.append("__len__")
            return str.__len__(self)

        def __format__(self, spec: str) -> str:
            callbacks.append("__format__")
            return "evil:sha256:"

        def __str__(self) -> str:
            callbacks.append("__str__")
            return "evil:sha256:"

    class DerivedArtifactID(ArtifactID):
        prefix: ClassVar[str] = Prefix("sha256:")

    validated = DerivedArtifactID.model_validate("sha256:" + DIGEST)
    constructed = DerivedArtifactID.from_sha256_hex(DIGEST)

    assert validated.root == "sha256:" + DIGEST
    assert constructed.root == "sha256:" + DIGEST
    schema = DerivedArtifactID.model_json_schema(mode="validation")
    assert schema["pattern"] == r"^sha256:[0-9A-Fa-f]{64}$"
    assert schema["minLength"] == schema["maxLength"] == 71
    assert callbacks == []


def test_plain_derived_prefix_and_base_rejections_remain_supported() -> None:
    class AlternateArtifactID(ArtifactID):
        prefix: ClassVar[str] = "artifact:"

    validated = AlternateArtifactID.model_validate("artifact:" + DIGEST)
    constructed = AlternateArtifactID.from_sha256_hex(DIGEST)

    assert validated.root == "artifact:" + DIGEST
    assert constructed.root == "artifact:" + DIGEST

    with pytest.raises(ValidationError, match="ArtifactID must start with sha256"):
        ArtifactID.model_validate("other:" + DIGEST)
    with pytest.raises(ValidationError, match="64 lowercase characters"):
        ArtifactID.model_validate("sha256:" + ("g" * 64))
    with pytest.raises(ValueError, match="64 characters"):
        ArtifactID.from_sha256_hex("g" * 64)


def test_string_subclass_payload_uses_its_text_without_overridden_dispatch() -> None:
    callbacks: list[str] = []

    class Input(str):
        def startswith(self, *args: object, **kwargs: object) -> bool:
            callbacks.append("startswith")
            return True

        def __getitem__(self, key: int | slice) -> str:
            callbacks.append("__getitem__")
            return "c" * 64

        def lower(self) -> str:
            callbacks.append("lower")
            return "c" * 64

    validated = ArtifactID.model_validate(Input("sha256:" + ("A" * 64)))
    constructed = ArtifactID.from_sha256_hex(Input("A" * 64))

    assert validated.root == "sha256:" + DIGEST
    assert constructed.root == "sha256:" + DIGEST
    assert callbacks == []


def test_nonstring_callbacks_and_their_errors_remain_observable() -> None:
    callbacks: list[str] = []

    class TextSubclass(str):
        def __str__(self) -> str:
            callbacks.append("text.__str__")
            return "wrong"

    class Stringable:
        def __str__(self) -> str:
            callbacks.append("stringable.__str__")
            return TextSubclass("sha256:" + DIGEST)

    class Lowerable:
        def lower(self) -> str:
            callbacks.append("lowerable.lower")
            return TextSubclass(DIGEST)

    class InvalidStringable:
        def __str__(self) -> str:
            callbacks.append("invalid.__str__")
            return cast("str", 1)

    class InvalidLowerable:
        def lower(self) -> str:
            callbacks.append("invalid.lower")
            return cast("str", object())

    assert ArtifactID.model_validate(Stringable()).root == "sha256:" + DIGEST
    assert callbacks == ["stringable.__str__"]
    callbacks.clear()
    assert ArtifactID.from_sha256_hex(Lowerable()).root == "sha256:" + DIGEST
    assert callbacks == ["lowerable.lower"]

    with pytest.raises(TypeError):
        ArtifactID.model_validate(InvalidStringable())
    assert callbacks[-1] == "invalid.__str__"
    with pytest.raises(TypeError):
        ArtifactID.from_sha256_hex(InvalidLowerable())
    assert callbacks[-1] == "invalid.lower"


def test_native_json_schema_enforces_validation_and_serialization_grammar() -> None:
    validation_schema = ArtifactID.model_json_schema(mode="validation")
    serialization_schema = ArtifactID.model_json_schema(mode="serialization")
    assert validation_schema["pattern"] == r"^sha256:[0-9A-Fa-f]{64}$"
    assert serialization_schema["pattern"] == r"^sha256:[0-9a-f]{64}$"
    assert validation_schema["minLength"] == validation_schema["maxLength"] == 71
    assert serialization_schema["minLength"] == serialization_schema["maxLength"] == 71

    validation = jsonschema.validators.validator_for(validation_schema)(validation_schema)
    serialization = jsonschema.validators.validator_for(serialization_schema)(serialization_schema)
    canonical = "sha256:" + DIGEST
    uppercase = "sha256:" + ("A" * 64)
    terminal_newline = chr(10)
    assert validation.is_valid(canonical)
    assert validation.is_valid(uppercase)
    assert not validation.is_valid("sha256:" + DIGEST + terminal_newline)
    pattern_only_schema = dict(validation_schema)
    pattern_only_schema.pop("minLength")
    pattern_only_schema.pop("maxLength")
    pattern_only = jsonschema.validators.validator_for(pattern_only_schema)(pattern_only_schema)
    assert pattern_only.is_valid("sha256:" + DIGEST + terminal_newline)
    assert not validation.is_valid("sha256:" + ("a" * 63))
    assert not validation.is_valid("sha384:" + DIGEST)
    assert not validation.is_valid("sha256:" + DIGEST + "0")

    normalized = ArtifactID.model_validate(uppercase)
    assert normalized.root == canonical
    serialized = json.loads(normalized.model_dump_json())
    assert serialization.is_valid(serialized)
    assert not serialization.is_valid(uppercase)

    with pytest.raises(ValidationError):
        ArtifactID.model_validate(uppercase + terminal_newline)
    with pytest.raises(ValueError):
        ArtifactID.from_sha256_hex(DIGEST + terminal_newline)
    bypassed = ArtifactID.model_construct(root=canonical + terminal_newline)
    with pytest.raises(ValueError, match="Invalid sha256 hex"):
        _ = bypassed.hex


def test_native_json_schema_preserves_derived_prefix_behavior() -> None:
    class AlternateArtifactID(ArtifactID):
        prefix: ClassVar[str] = "artifact:"

    validation_schema = AlternateArtifactID.model_json_schema(mode="validation")
    serialization_schema = AlternateArtifactID.model_json_schema(mode="serialization")
    assert validation_schema["pattern"] == r"^artifact:[0-9A-Fa-f]{64}$"
    assert validation_schema["minLength"] == validation_schema["maxLength"] == 73
    assert serialization_schema["pattern"] == r"^artifact:[0-9a-f]{64}$"
    validator = jsonschema.validators.validator_for(validation_schema)(validation_schema)
    serializer = jsonschema.validators.validator_for(serialization_schema)(serialization_schema)
    uppercase = "artifact:" + ("A" * 64)
    assert validator.is_valid(uppercase)
    assert not validator.is_valid("sha256:" + DIGEST)
    normalized = AlternateArtifactID.model_validate(uppercase)
    assert normalized.root == "artifact:" + DIGEST
    assert serializer.is_valid(json.loads(normalized.model_dump_json()))
