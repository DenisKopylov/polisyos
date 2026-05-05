from __future__ import annotations

import pytest
from polisyos.core.security.cell import CellSpec, CellTier, DatabaseBackendKind


class TestCellSpec:
    def test_create_shared_cell(self) -> None:
        cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1")
        assert cell.tier == CellTier.SHARED
        assert cell.max_tenants == 50
        assert cell.requires_rls is True
        assert cell.namespace.startswith("polisyos-cell-")

    def test_create_dedicated_cell(self) -> None:
        cell = CellSpec(
            tier=CellTier.DEDICATED,
            max_tenants=1,
            region="us-gov-west-1",
            db_backend=DatabaseBackendKind.DUCKDB,
        )
        assert cell.requires_rls is False

    def test_dedicated_cell_rejects_multiple_tenants(self) -> None:
        with pytest.raises(ValueError, match="max_tenants=1"):
            CellSpec(tier=CellTier.DEDICATED, max_tenants=5, region="us-gov-west-1")

    def test_cell_id_is_uuid7(self) -> None:
        cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1")
        assert cell.cell_id[14] == "7"

    def test_uuid7_monotonic_ordering(self) -> None:
        cells = [CellSpec(tier=CellTier.SHARED, region="us-gov-west-1") for _ in range(5)]
        ids = [cell.cell_id for cell in cells]
        assert ids == sorted(ids)
