from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
)
from polisyos.core.artifacts.canonical_profile import read_core_json_artifact
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, CanonViolation


def _profiled_options(spec: CanonSpec) -> PutOptions:
    return PutOptions(
        kind="test.core-json-producer-conformance",
        media_type="application/json",
        canon=CanonInfo.from_spec(spec),
    )


def _stored_files(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"value": {"_type": "bytes_hex", "value": "00ff"}},
            id="recognized-bytes-alias",
        ),
        pytest.param(
            {"value": {"_type": "float_hex", "value": "0x1.4000000000000p+0"}},
            id="recognized-float-alias",
        ),
        pytest.param(
            {"value": {"_type": "float_hex", "value": "not-a-float"}},
            id="malformed-present-tag",
        ),
    ],
)
@pytest.mark.parametrize("return_selected_profile", [False, True])
def test_filesystem_json_writer_refuses_nonconformant_tags_before_persistence(
    tmp_path: Path,
    payload: dict[str, object],
    return_selected_profile: bool,
) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    before = _stored_files(root)

    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        store.put_json(
            payload,
            _profiled_options(spec),
            canon_spec=spec,
            return_selected_profile=return_selected_profile,
        )

    assert refusal.value.code == "canon_profile_payload_nonconformant"
    assert _stored_files(root) == before


def test_filesystem_json_writer_emits_roundtrippable_native_values(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    payload = {"binary": b"\x00\xff", "ratio": 1.25, "optional": None}

    ref = store.put_json(
        payload,
        _profiled_options(spec),
        canon_spec=spec,
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    admitted = read_core_json_artifact(store, ref)
    assert admitted.status == "declared_bytes_conformant"
    assert admitted.value == payload


def test_filesystem_json_writer_keeps_default_float_refusal(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    spec = CanonSpec()
    before = _stored_files(root)

    with pytest.raises(CanonViolation, match="float forbidden"):
        store.put_json(
            {"ratio": 1.25},
            _profiled_options(spec),
            canon_spec=spec,
        )

    assert _stored_files(root) == before


@pytest.mark.parametrize(
    "adapter_type",
    [AsyncArtifactStoreAdapter, AsyncFileSystemArtifactStore],
)
@pytest.mark.asyncio
async def test_async_json_facades_preserve_writer_conformance_preflight(
    tmp_path: Path,
    adapter_type: type[AsyncArtifactStoreAdapter] | type[AsyncFileSystemArtifactStore],
) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    adapter = adapter_type(store=store)
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    before = _stored_files(root)

    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        await adapter.put_json(
            {"value": {"_type": "bytes_hex", "value": "00ff"}},
            _profiled_options(spec),
            canon_spec=spec,
        )

    assert refusal.value.code == "canon_profile_payload_nonconformant"
    assert _stored_files(root) == before
