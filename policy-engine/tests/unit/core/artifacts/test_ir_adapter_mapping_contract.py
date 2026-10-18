"""Exercise generic Mapping carriers through canonical CAS persistence and fresh reads."""

from __future__ import annotations

import json
from collections import UserDict
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import (
    CanonInfo as IRCanonInfo,
)
from polisyos.ir.artifacts import (
    SchemaInfo as IRSchemaInfo,
)
from polisyos.ir.artifacts import (
    StorePutOptions,
    get_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec

_EXPECTED_DECIMAL_BYTES = b'{"amount":{"_type":"decimal","value":"12.30"}}'
_MAPPING_KINDS = ("dict", "userdict", "mapping-proxy", "custom-read-only")


class _ReadOnlyMapping(Mapping[str, object]):
    """Provide a non-dict Mapping backed by an immutable view."""

    def __init__(self, values: Mapping[str, object]) -> None:
        self._values: Mapping[str, object] = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _mapping_carrier(kind: str, values: Mapping[str, object]) -> Mapping[str, object]:
    """Wrap option values in a requested standard or custom Mapping carrier."""
    copied = dict(values)
    if kind == "dict":
        return copied
    if kind == "userdict":
        return cast("Mapping[str, object]", UserDict(copied))
    if kind == "mapping-proxy":
        return MappingProxyType(copied)
    if kind == "custom-read-only":
        return _ReadOnlyMapping(copied)
    raise AssertionError(f"Unexpected mapping carrier: {kind}")


@pytest.mark.parametrize("mapping_kind", _MAPPING_KINDS)
@pytest.mark.parametrize("profile_state", ["complete-mapping", "omitted", "none"])
def test_mapping_carriers_reopen_with_same_selected_profile_and_bytes(
    tmp_path: Path,
    mapping_kind: str,
    profile_state: str,
) -> None:
    """Map options retain profile identity and exact bytes through a fresh IR reader."""
    root = tmp_path / "mapping-cas"
    store = FileSystemCAS(root)
    adapter = ensure_ir_artifact_store(store)
    spec = IRCanonSpec()
    canon_info = IRCanonInfo.from_spec(spec)
    schema_values = {"name": "test.ir.mapping-carrier", "version": "1.0"}
    schema_mapping = _mapping_carrier(mapping_kind, schema_values)
    kind = "test.ir.mapping-carrier"
    payload = {"amount": Decimal("12.30")}
    typed_canon = canon_info if profile_state == "complete-mapping" else None
    typed_ref = adapter.put_json(
        payload,
        StorePutOptions(
            kind=kind,
            media_type="application/json",
            schema=IRSchemaInfo(**schema_values),
            canon=typed_canon,
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )

    mapping_values: dict[str, object] = {
        "kind": kind,
        "media_type": "application/json",
        "schema": schema_mapping,
    }
    if profile_state == "complete-mapping":
        mapping_values["canon"] = _mapping_carrier(
            mapping_kind,
            canon_info.model_dump(mode="python"),
        )
    elif profile_state == "none":
        mapping_values["canon"] = None
    elif profile_state != "omitted":
        raise AssertionError(f"Unexpected profile state: {profile_state}")
    mapped_ref = adapter.put_json(
        payload,
        _mapping_carrier(mapping_kind, mapping_values),
        canon_spec=spec,
        return_selected_profile=True,
    )

    assert mapped_ref.artifact_id == typed_ref.artifact_id
    assert mapped_ref.manifest_profile_sha256 == typed_ref.manifest_profile_sha256
    assert mapped_ref.manifest_profile_sha256 is not None
    assert adapter.get_bytes(mapped_ref) == _EXPECTED_DECIMAL_BYTES
    manifest_bytes = adapter.get_manifest_bytes(mapped_ref)
    raw_manifest = json.loads(manifest_bytes)
    assert raw_manifest["schema"] == schema_values
    assert raw_manifest["canon"] == canon_info.model_dump(mode="json")
    assert artifact_manifest_profile_sha256(store.get_manifest(mapped_ref)) == (
        mapped_ref.manifest_profile_sha256
    )

    fresh_store = FileSystemCAS(root)
    fresh_adapter = ensure_ir_artifact_store(fresh_store)
    assert fresh_adapter.get_manifest_bytes(mapped_ref) == manifest_bytes
    assert fresh_adapter.get_bytes(mapped_ref) == _EXPECTED_DECIMAL_BYTES
    assert get_json_artifact(fresh_adapter, mapped_ref) == payload
    assert artifact_manifest_profile_sha256(fresh_store.get_manifest(mapped_ref)) == (
        mapped_ref.manifest_profile_sha256
    )


@pytest.mark.parametrize("mapping_kind", _MAPPING_KINDS)
@pytest.mark.parametrize(
    ("invalid_case", "expected_error"),
    [
        ("incomplete-present-canon", "Invalid adapter option 'canon'"),
        ("extra-canon-field", "Invalid adapter option 'canon'"),
        ("unknown-write-option", "Unexpected adapter write option field"),
    ],
)
def test_mapping_carriers_refuse_malformed_present_options_before_cas_write(
    tmp_path: Path,
    mapping_kind: str,
    invalid_case: str,
    expected_error: str,
) -> None:
    """Malformed supplied mappings fail closed instead of falling through to defaults."""
    spec = IRCanonSpec()
    canon_values = IRCanonInfo.from_spec(spec).model_dump(mode="python")
    values: dict[str, object] = {
        "kind": f"test.ir.invalid-mapping-{mapping_kind}-{invalid_case}",
        "media_type": "application/json",
    }
    if invalid_case == "incomplete-present-canon":
        canon_values.pop("max_depth")
        values["canon"] = _mapping_carrier(mapping_kind, canon_values)
    elif invalid_case == "extra-canon-field":
        canon_values["unrecognized"] = "must be refused"
        values["canon"] = _mapping_carrier(mapping_kind, canon_values)
    elif invalid_case == "unknown-write-option":
        values["canon"] = _mapping_carrier(mapping_kind, canon_values)
        values["unrecognized"] = "must be refused"
    else:
        raise AssertionError(f"Unexpected invalid case: {invalid_case}")

    store = FileSystemCAS(tmp_path / "invalid-mapping-cas")
    adapter = ensure_ir_artifact_store(store)
    with pytest.raises(TypeError, match=expected_error):
        adapter.put_json(
            {"amount": Decimal("12.30")},
            _mapping_carrier(mapping_kind, values),
            canon_spec=spec,
        )

    assert store.iter_artifact_ids() == []
