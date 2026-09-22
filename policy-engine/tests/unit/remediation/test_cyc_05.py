"""CYC-05 witnesses for typed recursive limits and structural receipts."""

from __future__ import annotations

from pathlib import Path

from polisyos.runtime.quality.recursive_generation_cycle import (
    recompute_depth_n_strangle_receipt,
)


def _source_root(root: Path) -> Path:
    source = root / "src" / "polisyos"
    source.mkdir(parents=True)
    return source


def test_depth_n_strangle_receipt_fails_closed_when_source_is_missing(tmp_path: Path) -> None:
    """An absent controlled source slice cannot produce positive strangle evidence."""

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == ()
    assert receipt.production_default_routes == ()
    assert receipt.default_controller == "unresolved"


def test_depth_n_strangle_receipt_separates_parse_error_from_prohibited_caller(
    tmp_path: Path,
) -> None:
    """A syntax error is an unestablished denominator, not a caller finding."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert receipt.production_fixture_callers == ()
    assert any("src/polisyos/broken.py" in item for item in receipt.parse_errors)


def test_depth_n_strangle_receipt_binds_available_slice_and_invalidates_on_change(
    tmp_path: Path,
) -> None:
    """A real caller is drift, and any source-slice change yields a new receipt identity."""

    source = _source_root(tmp_path)
    (source / "route.py").write_text(
        "def route():\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    (source / "legacy.py").write_text(
        "def route():\n"
        "    return run_recursive_case()\n",
        encoding="utf-8",
    )

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "drift"
    assert receipt.source_state == "available"
    assert receipt.source_content_hash is not None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == (
        "src/polisyos/legacy.py:2:call:run_recursive_case",
    )
    assert receipt.production_default_routes == (
        "src/polisyos/route.py:2:call:build_default_recursive_generation_cycle_controller",
    )
    original_hash = receipt.source_content_hash

    (source / "route.py").write_text(
        "def route():\n"
        "    # meaningful source-slice change\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    changed = recompute_depth_n_strangle_receipt(tmp_path)

    assert changed.source_state == "available"
    assert changed.source_content_hash is not None
    assert changed.source_content_hash != original_hash
