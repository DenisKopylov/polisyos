from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.foundry.data_plane.bindings import InputBindingsBuildResult


class TestInputBindingsBuildResult:
    def test_result_fields(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1", "b2"),
        )
        assert result.applied_binding_ids == ("b1", "b2")
        assert result.input_bindings_ref is not None

    def test_result_empty_bindings(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=(),
        )
        assert len(result.applied_binding_ids) == 0

    def test_result_frozen(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1",),
        )
        with pytest.raises(AttributeError):
            result.applied_binding_ids = ("b2",)  # type: ignore[misc]

    def test_result_tuple_immutability(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1", "b2", "b3"),
        )
        assert isinstance(result.applied_binding_ids, tuple)
        assert len(result.applied_binding_ids) == 3
