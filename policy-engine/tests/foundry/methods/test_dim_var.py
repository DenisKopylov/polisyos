"""
Tests for DimVar symbolic dimension algebra (T3.1).

Verifies:
- DimVar construction and equality
- SlotSpec accepts DimVar, str, int, None in shape
- check_slot_compatibility handles all DimVar combination rules:
  - DimVar × DimVar same name → compatible, no warning
  - DimVar × DimVar diff name → compatible, warning
  - DimVar × int → compatible, warning
  - int × DimVar → compatible, warning
  - None (wildcard) × anything → compatible, no warning
- stable_digest changes when DimVar name changes
"""
from __future__ import annotations

import pytest

from polisyos.foundry.methods.base import DimVar, DimExpr, Shape, SlotSpec, SlotType, Unit
from polisyos.foundry.methods.types.checker import check_slot_compatibility


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_UNIT = Unit("dimensionless", "-")
_VECTOR = SlotType.VECTOR
_MATRIX = SlotType.MATRIX


def _slot(name: str, shape: tuple, slot_type: SlotType = _VECTOR) -> SlotSpec:
    return SlotSpec(name=name, slot_type=slot_type, unit=_UNIT, shape=shape)


# ---------------------------------------------------------------------------
# DimVar basic
# ---------------------------------------------------------------------------

class TestDimVar:
    def test_construction(self):
        dv = DimVar("n_obs")
        assert dv.name == "n_obs"

    def test_repr(self):
        dv = DimVar("n_vars")
        assert repr(dv) == "DimVar('n_vars')"

    def test_str(self):
        dv = DimVar("k_treat")
        assert str(dv) == "k_treat"

    def test_equality_same_name(self):
        assert DimVar("n_obs") == DimVar("n_obs")

    def test_inequality_different_name(self):
        assert DimVar("n_obs") != DimVar("n_vars")

    def test_hashable(self):
        s = {DimVar("n_obs"), DimVar("n_obs"), DimVar("n_vars")}
        assert len(s) == 2

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            DimVar("")

    def test_whitespace_name_raises(self):
        with pytest.raises(ValueError):
            DimVar("   ")

    def test_frozen(self):
        dv = DimVar("n_obs")
        with pytest.raises((AttributeError, TypeError)):
            dv.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SlotSpec accepts DimVar
# ---------------------------------------------------------------------------

class TestSlotSpecWithDimVar:
    def test_accepts_dimvar_in_shape(self):
        n_obs = DimVar("n_obs")
        slot = _slot("outcome", (n_obs,))
        assert slot.shape == (n_obs,)

    def test_accepts_dimvar_and_int(self):
        n_obs = DimVar("n_obs")
        slot = _slot("covariates", (n_obs, 3), slot_type=_MATRIX)
        assert slot.shape == (n_obs, 3)

    def test_accepts_none_wildcard(self):
        slot = _slot("x", (None, 3), slot_type=_MATRIX)
        assert slot.shape[0] is None

    def test_accepts_mixed_dimvar_str_int(self):
        n_obs = DimVar("n_obs")
        slot = _slot("data", (n_obs, "k", 1), slot_type=_MATRIX)
        assert len(slot.shape) == 3

    def test_invalid_shape_entry_raises(self):
        with pytest.raises(TypeError, match="DimVar"):
            _slot("bad", (3.14,))  # float is not allowed

    def test_stable_digest_changes_with_dimvar_name(self):
        slot_a = _slot("x", (DimVar("n_obs"),))
        slot_b = _slot("x", (DimVar("n_vars"),))
        assert slot_a.stable_digest() != slot_b.stable_digest()

    def test_stable_digest_consistent_same_dimvar(self):
        slot = _slot("x", (DimVar("n_obs"),))
        assert slot.stable_digest() == slot.stable_digest()


# ---------------------------------------------------------------------------
# check_slot_compatibility with DimVar
# ---------------------------------------------------------------------------

class TestDimVarCompatibility:
    def test_same_dimvar_compatible_no_warning(self):
        n = DimVar("n_obs")
        src = _slot("out", (n,))
        tgt = _slot("inp", (n,))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible
        # No warning expected for same symbolic name
        assert not any("mismatch" in w.lower() for w in result.warnings)

    def test_different_dimvar_compatible_with_warning(self):
        src = _slot("out", (DimVar("n_obs"),))
        tgt = _slot("inp", (DimVar("n_rows"),))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible
        assert result.has_warnings

    def test_dimvar_vs_int_compatible_with_warning(self):
        src = _slot("out", (DimVar("n_obs"),))
        tgt = _slot("inp", (100,))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible
        # Should warn: symbolic vs fixed
        assert result.has_warnings

    def test_int_vs_dimvar_compatible_with_warning(self):
        src = _slot("out", (100,))
        tgt = _slot("inp", (DimVar("n_obs"),))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible
        assert result.has_warnings

    def test_none_wildcard_vs_anything_compatible(self):
        src = _slot("out", (None,))
        tgt = _slot("inp", (DimVar("n_obs"),))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible

    def test_none_vs_int_compatible(self):
        src = _slot("out", (None,))
        tgt = _slot("inp", (500,))
        result = check_slot_compatibility(src, tgt)
        assert result.compatible

    def test_concrete_mismatch_still_incompatible(self):
        """Two concrete ints that differ should still be incompatible."""
        src = _slot("out", (100,))
        tgt = _slot("inp", (200,))
        result = check_slot_compatibility(src, tgt)
        assert not result.compatible

    def test_dimvar_mixed_with_concrete_matrix(self):
        n = DimVar("n_obs")
        src = _slot("out", (n, 5), slot_type=_MATRIX)
        tgt = _slot("inp", (n, 5), slot_type=_MATRIX)
        result = check_slot_compatibility(src, tgt)
        assert result.compatible
