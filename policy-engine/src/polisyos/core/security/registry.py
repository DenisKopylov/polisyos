"""Tenant-to-cell in-memory registry."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from polisyos.core.security.cell import CellAssignment, CellSpec, CellTier, TenantSpec
from polisyos.core.security.exceptions import CellCapacityError, TenantNotFoundError


class CellResolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    tenant_name: str
    cell_id: str
    cell_slug: str
    cell_tier: str
    cell_region: str
    namespace: str


class CellRegistry:
    """Thread-safe tenant/cell registry with O(1) tenant resolution."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cells: dict[str, CellSpec] = {}
        self._tenants: dict[str, TenantSpec] = {}
        self._assignments: dict[str, CellAssignment] = {}
        self._tenant_to_cell: dict[str, str] = {}
        self._cell_tenant_counts: dict[str, int] = {}

    def register_cell(self, spec: CellSpec) -> None:
        with self._lock:
            self._cells[spec.cell_id] = spec
            self._cell_tenant_counts.setdefault(spec.cell_id, 0)

    def register_tenant(self, spec: TenantSpec, cell_id: str) -> CellAssignment:
        with self._lock:
            cell = self._cells.get(cell_id)
            if cell is None:
                raise TenantNotFoundError(f"Cell {cell_id} not found")

            if spec.region != cell.region:
                raise ValueError(
                    f"Tenant region {spec.region!r} does not match cell region {cell.region!r}"
                )

            if spec.tier == CellTier.DEDICATED and cell.tier != CellTier.DEDICATED:
                raise ValueError("Dedicated tenant must be assigned to dedicated cell")

            previous_cell = self._tenant_to_cell.get(spec.tenant_id)
            current_count = self._cell_tenant_counts.get(cell_id, 0)
            if previous_cell == cell_id:
                current_count = max(0, current_count - 1)
            if current_count >= cell.max_tenants:
                raise CellCapacityError(f"Cell {cell_id} at capacity ({cell.max_tenants})")

            if previous_cell is not None and previous_cell != cell_id:
                self._cell_tenant_counts[previous_cell] = max(
                    0,
                    self._cell_tenant_counts.get(previous_cell, 0) - 1,
                )

            assignment = CellAssignment(tenant_id=spec.tenant_id, cell_id=cell_id)
            self._tenants[spec.tenant_id] = spec
            self._assignments[spec.tenant_id] = assignment
            self._tenant_to_cell[spec.tenant_id] = cell_id
            self._cell_tenant_counts[cell_id] = current_count + 1
            return assignment

    def resolve(self, tenant_id: str) -> CellResolution:
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")

            cell_id = self._tenant_to_cell.get(tenant_id)
            if cell_id is None:
                raise TenantNotFoundError(f"Tenant {tenant_id} is not assigned")

            cell = self._cells.get(cell_id)
            if cell is None:
                raise TenantNotFoundError(f"Cell {cell_id} not found")

            return CellResolution(
                tenant_id=tenant.tenant_id,
                tenant_name=tenant.name,
                cell_id=cell.cell_id,
                cell_slug=cell.cell_slug,
                cell_tier=cell.tier.value,
                cell_region=cell.region,
                namespace=cell.namespace,
            )

    def resolve_cell(self, tenant_id: str) -> CellSpec:
        resolution = self.resolve(tenant_id)
        with self._lock:
            cell = self._cells.get(resolution.cell_id)
            if cell is None:
                raise TenantNotFoundError(f"Cell {resolution.cell_id} not found")
            return cell

    def get_cell(self, cell_id: str) -> CellSpec | None:
        with self._lock:
            return self._cells.get(cell_id)

    def list_tenants_in_cell(self, cell_id: str) -> list[str]:
        with self._lock:
            return [
                tenant_id
                for tenant_id, assigned_cell in self._tenant_to_cell.items()
                if assigned_cell == cell_id
            ]

    def replace_snapshot(self, *, cells: list[CellSpec], tenants: list[tuple[TenantSpec, str]]) -> None:
        with self._lock:
            self._cells = {}
            self._tenants = {}
            self._assignments = {}
            self._tenant_to_cell = {}
            self._cell_tenant_counts = {}
            for cell in cells:
                self.register_cell(cell)
            for tenant, cell_id in tenants:
                self.register_tenant(tenant, cell_id)

    @property
    def cell_count(self) -> int:
        with self._lock:
            return len(self._cells)

    @property
    def tenant_count(self) -> int:
        with self._lock:
            return len(self._tenants)

    def load_from_json(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cells = [CellSpec.model_validate(item) for item in payload.get("cells", [])]
        tenants: list[tuple[TenantSpec, str]] = []
        for raw in payload.get("tenants", []):
            if not isinstance(raw, dict):
                continue
            tenant_payload = dict(raw)
            cell_id = str(tenant_payload.pop("cell_id"))
            tenants.append((TenantSpec.model_validate(tenant_payload), cell_id))
        self.replace_snapshot(cells=cells, tenants=tenants)

    def to_json(self) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            return {
                "cells": [cell.model_dump(mode="json") for cell in self._cells.values()],
                "tenants": [
                    {
                        **tenant.model_dump(mode="json"),
                        "cell_id": self._tenant_to_cell[tenant.tenant_id],
                    }
                    for tenant in self._tenants.values()
                ],
            }


__all__ = ["CellRegistry", "CellResolution"]
