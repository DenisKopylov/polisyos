"""Characterization witnesses for the CAN-01 strict-canon migration.

The finite corpus extends the vectors retained at the audited source commit
20d9009be21097bfbdc38a546a15cc60213b8ace. It is a software compatibility corpus,
not an inventory of production artifacts. Core and IR intentionally share
ordinary persisted bytes while keeping separate typed-tag profiles, exception
identities, and public facades. Raw alias readability is distinct from current
producer and selected-reader admission; production owners are unchanged here.
"""

from __future__ import annotations

# ruff: noqa: S101
# CAN-01 characterization uses direct pytest assertions as executable golden-corpus oracles.
import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

import polisyos.core.canon as core_canon
import polisyos.ir.model_layer.canon as ir_canon
from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    read_core_json_artifact,
)
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

_GOLDEN_VALUE = {
    "bool": True,
    "bytes": b"\x00\x01\xfe",
    "date": date(2024, 1, 2),
    "datetime": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
    "decimal": Decimal("12.30"),
    "integer": 7,
    "nested": [None, {"z": "café", "a": 0}],
}
_GOLDEN_BYTES = (
    '{"bool":true,"bytes":{"_type":"bytes","data":"AAH+","encoding":"base64"},'
    '"date":{"_type":"date","iso":"2024-01-02"},'
    '"datetime":{"_type":"datetime","iso_utc":"2024-01-02T03:04:05Z"},'
    '"decimal":{"_type":"decimal","value":"12.30"},"integer":7,'
    '"nested":[null,{"a":0,"z":"café"}]}'
).encode()

_CORE_EXTRA_TAGS = [
    (b'{"_type":"float_hex","value":"0x1.8p+1"}', 3.0),
    (b'{"_type":"bytes_hex","value":"00ff"}', b"\x00\xff"),
    (
        b'{"_type":"array_digest","digest":"sha256:abc","length":2}',
        {"_type": "array_digest", "digest": "sha256:abc", "length": 2},
    ),
]

_NON_STRING_TYPE_TAGS = [
    {"_type": [], "value": "list-tag"},
    {"_type": {}, "value": "object-tag"},
]

# Literal byte expectations are independent of the encoder being qualified.
# Provenance: the mixed golden and three raw Core aliases above are retained
# unchanged from the audited source; these four boundary vectors extend that
# finite corpus. They do not attest arbitrary historical objects or producers.
_SUPPORTED_V2_CORPUS = [
    pytest.param(_GOLDEN_VALUE, _GOLDEN_BYTES, id="retained-mixed-golden"),
    pytest.param(None, b"null", id="null-scalar"),
    pytest.param(
        {"empty": b"", "null": None},
        b'{"empty":{"_type":"bytes","data":"","encoding":"base64"},"null":null}',
        id="empty-bytes-and-mapping-null",
    ),
    pytest.param(
        {"float": 0.125, "minus_zero": -0.0},
        b'{"float":{"_type":"float","repr":"0.125"},"minus_zero":{"_type":"float","repr":"0"}}',
        id="finite-float-and-v2-zero-normalization",
    ),
    pytest.param(
        {"nested": [True, False, 10**30, "é"]},
        '{"nested":[true,false,1000000000000000000000000000000,"é"]}'.encode(),
        id="nested-unicode-and-integer",
    ),
]


@pytest.mark.parametrize(
    "module",
    [core_canon, ir_canon],
    ids=("core", "ir"),
)
def test_ordinary_golden_payload_preserves_bytes_and_round_trips(module: ModuleType) -> None:
    """The shared persisted corpus remains byte-identical in both facades."""

    assert module.to_canonical_bytes(_GOLDEN_VALUE) == _GOLDEN_BYTES
    assert module.from_canonical_bytes(_GOLDEN_BYTES) == _GOLDEN_VALUE


def test_ordinary_golden_payload_has_content_hash_parity() -> None:
    """Structured fingerprints are hashes of the exact golden bytes."""

    expected = hashlib.sha256(_GOLDEN_BYTES).hexdigest()
    core_bytes = core_canon.to_canonical_bytes(_GOLDEN_VALUE)
    ir_bytes = ir_canon.to_canonical_bytes(_GOLDEN_VALUE)

    assert core_bytes == ir_bytes == _GOLDEN_BYTES
    assert core_canon.content_hash(core_bytes) == expected
    assert ir_canon.content_hash(ir_bytes) == expected
    assert core_canon.fingerprint(_GOLDEN_VALUE) == expected
    assert core_canon.content_hash(_GOLDEN_BYTES, prefix=True) == f"sha256:{expected}"


@pytest.mark.parametrize(
    "module",
    [core_canon, ir_canon],
    ids=("core", "ir"),
)
def test_malformed_unknown_tag_and_depth_errors_keep_canon_boundary(module: ModuleType) -> None:
    """Malformed JSON, unknown tags, and over-depth values fail explicitly."""

    with pytest.raises(json.JSONDecodeError):
        module.from_canonical_bytes(b'{"broken":')

    unknown_tag = {"_type": "future_tag", "value": "x"}
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type"):
        module.to_canonical_bytes(unknown_tag)
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type"):
        module.from_canonical_bytes(json.dumps(unknown_tag).encode("utf-8"))

    with pytest.raises(module.CanonViolation, match="max_depth=1"):
        module.to_canonical_bytes({"outer": {"inner": 1}}, module.CanonSpec(max_depth=1))
    with pytest.raises(module.CanonViolation, match="max_depth=1"):
        module.from_canonical_bytes(b'{"outer":{"inner":1}}', max_depth=1)


@pytest.mark.parametrize(
    ("module", "expected_fqn"),
    [
        pytest.param(
            core_canon,
            "polisyos.core.canon.canon_json.CanonViolation",
            id="core",
        ),
        pytest.param(
            ir_canon,
            "polisyos.ir.model_layer.canon.CanonViolation",
            id="ir",
        ),
    ],
)
@pytest.mark.parametrize(
    "payload",
    _NON_STRING_TYPE_TAGS,
    ids=("list-type", "object-type"),
)
def test_non_string_type_tags_keep_facade_exception_identity(
    module: ModuleType,
    expected_fqn: str,
    payload: dict[str, object],
) -> None:
    """Malformed tag kinds fail with the owning facade's exact exception."""

    with pytest.raises(module.CanonViolation, match="Unknown canonical _type") as encode_error:
        module.to_canonical_bytes(payload)
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type") as object_error:
        module.from_canonical_obj(payload)
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type") as bytes_error:
        module.from_canonical_bytes(json.dumps(payload).encode("utf-8"))

    for error in (encode_error, object_error, bytes_error):
        assert type(error.value) is module.CanonViolation
        observed_fqn = f"{type(error.value).__module__}.{type(error.value).__qualname__}"
        assert observed_fqn == expected_fqn


@pytest.mark.parametrize(("payload", "expected"), _CORE_EXTRA_TAGS)
def test_core_preserves_extended_typed_tag_profile(payload: bytes, expected: object) -> None:
    """The raw Core decoder keeps the historical alias interpretation."""

    assert core_canon.from_canonical_bytes(payload) == expected


@pytest.mark.parametrize(("payload", "expected"), _CORE_EXTRA_TAGS[:2])
def test_raw_alias_readability_does_not_admit_current_producer_or_selected_reader(
    tmp_path: Path,
    payload: bytes,
    expected: object,
) -> None:
    """Retain raw bytes while refusing the non-roundtrippable selected value."""
    assert core_canon.from_canonical_bytes(payload) == expected
    root = tmp_path / "alias-cas"
    store = FileSystemCAS(root)
    with pytest.raises(core_canon.CanonViolation) as producer_refusal:
        store.put_json(
            json.loads(payload),
            PutOptions(kind="test.can.alias", media_type="application/json"),
            return_selected_profile=True,
        )
    assert isinstance(producer_refusal.value, CanonicalProfileRefusalError)
    assert producer_refusal.value.code == "canon_profile_payload_nonconformant"
    assert list(store.iter_artifact_ids()) == []

    # Explicit raw import preserves old bytes/IDs; it does not promote them to
    # a currently conformant JSON value or prove a historical production origin.
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind="test.can.raw-alias",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    fresh = FileSystemCAS(root)
    assert fresh.get_bytes(ref) == payload
    assert str(ref.artifact_id) == "sha256:" + hashlib.sha256(payload).hexdigest()
    with pytest.raises(CanonicalProfileRefusalError) as selected_refusal:
        read_core_json_artifact(fresh, ref)
    assert selected_refusal.value.code == "canon_profile_payload_nonconformant"
    assert fresh.get_bytes(ref) == payload


def test_core_array_digest_remains_a_conformant_selected_value(tmp_path: Path) -> None:
    """The opaque array descriptor remains a positive beside refused aliases."""
    payload, expected = _CORE_EXTRA_TAGS[2]
    assert core_canon.to_canonical_bytes(expected) == payload
    root = tmp_path / "array-cas"
    ref = FileSystemCAS(root).put_json(
        expected,
        PutOptions(kind="test.can.array", media_type="application/json"),
        return_selected_profile=True,
    )
    read = read_core_json_artifact(FileSystemCAS(root), ref)
    assert read.raw_payload_bytes == payload
    assert read.value == expected
    assert read.reader_policy_id == "core-tag-policy@1"


@pytest.mark.parametrize("module", [core_canon, ir_canon], ids=["core", "ir"])
@pytest.mark.parametrize(("value", "expected_bytes"), _SUPPORTED_V2_CORPUS)
def test_finite_v2_corpus_reaches_real_selected_fresh_consumer(
    tmp_path: Path,
    module: ModuleType,
    value: object,
    expected_bytes: bytes,
) -> None:
    """Real writers preserve literal bytes, profile and hashes on fresh reads."""
    spec = module.CanonSpec(forbid_floats=False, exclude_none=False)
    assert spec.version == "0.2.0"
    assert module.to_canonical_bytes(value, spec) == expected_bytes
    assert module.content_hash(expected_bytes) == hashlib.sha256(expected_bytes).hexdigest()
    root = tmp_path / "corpus-cas"
    if module is core_canon:
        ref = FileSystemCAS(root).put_json(
            value,
            PutOptions(kind="test.can.corpus", media_type="application/json"),
            spec,
            return_selected_profile=True,
        )
        fresh = FileSystemCAS(root)
        read = read_core_json_artifact(fresh, ref)
        assert read.selected_artifact_id == str(ref.artifact_id)
        assert read.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
        assert read.reader_policy_id == "core-tag-policy@1"
        restored = read.value
        assert read.raw_payload_bytes == expected_bytes
    else:
        ref = put_json_artifact(
            ensure_ir_artifact_store(FileSystemCAS(root)),
            value,
            kind="test.can.ir-corpus",
            schema_name="test.CanonCorpus",
            schema_version="1.0",
            canon_spec=spec,
            return_selected_profile=True,
        )
        fresh = ensure_ir_artifact_store(FileSystemCAS(root))
        restored = get_json_artifact(fresh, ref)
        assert fresh.get_bytes(ref) == expected_bytes
    manifest = fresh.get_manifest(ref)
    canon = manifest.canon
    assert canon.version == spec.version
    assert canon.forbid_floats is False
    assert canon.exclude_none is False
    assert restored == value
    assert module.to_canonical_bytes(restored, spec) == expected_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", [AsyncArtifactStoreAdapter, AsyncFileSystemArtifactStore])
async def test_async_writer_preserves_exact_profile_for_fresh_selected_consumer(
    tmp_path: Path,
    adapter: type[AsyncArtifactStoreAdapter] | type[AsyncFileSystemArtifactStore],
) -> None:
    """Both actual async facades reach a real CAS and a newly opened reader."""
    root = tmp_path / "async-cas"
    spec = core_canon.CanonSpec(exclude_none=False)
    writer = adapter(FileSystemCAS(root), timeout_seconds=5.0)
    ref = await writer.put_json(
        _GOLDEN_VALUE,
        PutOptions(kind="test.can.async", media_type="application/json"),
        spec,
        return_selected_profile=True,
    )
    read = read_core_json_artifact(FileSystemCAS(root), ref)
    assert read.raw_payload_bytes == _GOLDEN_BYTES
    assert read.value == _GOLDEN_VALUE
    assert read.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    assert read.reader_policy_id == "core-tag-policy@1"


def test_fresh_ir_artifact_import_does_not_activate_core() -> None:
    """A fresh ordinary IR package import preserves the neutral-owner boundary."""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import json, sys; import polisyos.ir.artifacts.io; "
            "print(json.dumps(sorted(name for name in sys.modules "
            "if name == 'polisyos.core' or name.startswith('polisyos.core.'))))",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("payload", [payload for payload, _ in _CORE_EXTRA_TAGS])
def test_ir_rejects_core_only_typed_tags(payload: bytes) -> None:
    """IR remains strict and does not silently widen its 0.2.0 decoder."""

    with pytest.raises(ir_canon.CanonViolation, match="Unknown canonical _type"):
        ir_canon.to_canonical_bytes(json.loads(payload))
    with pytest.raises(ir_canon.CanonViolation, match="Unknown canonical _type"):
        ir_canon.from_canonical_bytes(payload)


def test_core_and_ir_keep_exception_identity_and_fully_qualified_names() -> None:
    """The two public profiles retain distinct exception classes."""

    assert core_canon.CanonViolation is not ir_canon.CanonViolation
    assert core_canon.CanonViolation.__module__ == "polisyos.core.canon.canon_json"
    assert ir_canon.CanonViolation.__module__ == "polisyos.ir.model_layer.canon"
    assert issubclass(core_canon.CanonViolation, ValueError)
    assert issubclass(ir_canon.CanonViolation, ValueError)


def test_core_and_ir_public_facades_remain_separate() -> None:
    """Core-only hashing helpers are not accidentally exposed through IR."""

    core_public = set(core_canon.__all__)
    ir_public = set(ir_canon.__all__)
    shared = {
        "CanonSpec",
        "CanonViolation",
        "DeprecatedHashAlgorithm",
        "content_hash",
        "from_canonical_bytes",
        "from_canonical_obj",
        "to_canonical_bytes",
    }
    core_only = {"fingerprint", "streaming_hash", "truncated_hash"}

    assert shared <= core_public
    assert shared <= ir_public
    assert core_only <= core_public
    assert core_only.isdisjoint(ir_public)
    assert "HashAlgorithm" not in core_public
    assert "HashAlgorithm" in ir_public
    assert not any(hasattr(ir_canon, name) for name in core_only)


@pytest.mark.parametrize(
    "module",
    [core_canon, ir_canon],
    ids=("core", "ir"),
)
def test_explicit_sha1_keeps_deprecated_legacy_hash_identity(module: ModuleType) -> None:
    """Explicit SHA-1 remains readable with a deprecation warning only."""

    payload = b"legacy-canon-payload"
    expected = hashlib.sha1(payload).hexdigest()  # noqa: S324 - legacy SHA-1 witness.

    with pytest.warns(DeprecationWarning, match="sha1 content hashing is deprecated"):
        observed = module.content_hash(payload, algorithm="sha1", prefix=True)

    assert observed == f"sha1:{expected}"
