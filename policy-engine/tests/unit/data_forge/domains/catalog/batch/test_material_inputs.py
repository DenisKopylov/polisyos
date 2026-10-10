from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.data_forge.domains.catalog.batch.material_inputs import (
    _material_file_snapshot,
    _material_yaml_snapshot,
)


def test_material_snapshot_binds_selection_presence_and_exact_cached_bytes(
    tmp_path: Path,
) -> None:
    selected_path = tmp_path / "supplier.yaml"
    selected_path.write_bytes(b"supplier: first\n")

    _material_yaml_snapshot.cache_clear()
    selected = _material_file_snapshot(selected_path)
    assert selected.raw == b"supplier: first\n"
    assert selected.generation_member("supplier_registry") == (
        f"supplier_registry:{selected_path.resolve()}:present",
        b"supplier: first\n",
    )
    parsed = _material_yaml_snapshot(selected)
    assert parsed == {"supplier": "first"}
    assert _material_yaml_snapshot(selected) is parsed
    assert _material_yaml_snapshot.cache_info().hits == 1

    unselected = _material_file_snapshot(selected_path, selected=False)
    assert unselected.raw is None
    assert unselected.generation_member("supplier_registry") == (
        f"supplier_registry:{selected_path.resolve()}:unselected",
        b"",
    )
    assert _material_yaml_snapshot(unselected) is None

    absent_path = tmp_path / "optional.yaml"
    absent = _material_file_snapshot(absent_path)
    assert absent.generation_member("supplier_registry") == (
        f"supplier_registry:{absent_path.resolve()}:absent",
        b"",
    )
    with pytest.raises(FileNotFoundError):
        _material_file_snapshot(absent_path, required=True)

    selected_path.write_bytes(b"supplier: second\n")
    replacement = _material_file_snapshot(selected_path)
    assert replacement.raw == b"supplier: second\n"
    assert replacement.generation_member("supplier_registry") != selected.generation_member(
        "supplier_registry"
    )
    assert _material_yaml_snapshot(replacement) == {"supplier": "second"}
    assert _material_yaml_snapshot.cache_info().misses == 3
