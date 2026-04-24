"""Tenant-to-cell in-memory registry."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from polisyos.core.registry.generic import GenericRegistry
from polisyos.core.security.cell import CellAssignment, CellSpec, CellTier, TenantSpec
from polisyos.core.security.exceptions import CellCapacityError, TenantNotFoundError


class CellResolution(BaseModel):
    """Return the tenant-to-cell placement and routing namespace for one tenant."""

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
        self._cells = GenericRegistry[str, CellSpec](key_fn=lambda spec: spec.cell_id)
        self._tenants = GenericRegistry[str, TenantSpec](key_fn=lambda spec: spec.tenant_id)
        self._assignments = GenericRegistry[str, CellAssignment](
            key_fn=lambda assignment: assignment.tenant_id,
            indexers={"cell_id": lambda assignment: assignment.cell_id},
        )
        self._cell_tenant_counts: dict[str, int] = {}

    def register_cell(self, spec: CellSpec) -> None:
        """Register or replace a cell definition and initialize its capacity counter."""
        with self._lock:
            self._cells.register(spec, override=True)
            self._cell_tenant_counts.setdefault(spec.cell_id, 0)

    def register_tenant(self, spec: TenantSpec, cell_id: str) -> CellAssignment:
        """Assign a tenant to a cell after validating region/tier/capacity invariants."""
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

            previous_assignment = self._assignments.get(spec.tenant_id)
            previous_cell = previous_assignment.cell_id if previous_assignment is not None else None
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
            self._tenants.register(spec, override=True)
            self._assignments.register(assignment, override=True)
            self._cell_tenant_counts[cell_id] = current_count + 1
            return assignment

    def resolve(self, tenant_id: str) -> CellResolution:
        """Resolve a tenant into its assigned cell and routing namespace.

        Raises:
            TenantNotFoundError: If the tenant, assignment, or target cell is missing.
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")

            assignment = self._assignments.get(tenant_id)
            if assignment is None:
                raise TenantNotFoundError(f"Tenant {tenant_id} is not assigned")

            cell_id = assignment.cell_id
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
        """Return the `CellSpec` assigned to a tenant.

        Raises:
            TenantNotFoundError: If resolution fails or the cell snapshot is stale.
        """
        resolution = self.resolve(tenant_id)
        with self._lock:
            cell = self._cells.get(resolution.cell_id)
            if cell is None:
                raise TenantNotFoundError(f"Cell {resolution.cell_id} not found")
            return cell

    def get_cell(self, cell_id: str) -> CellSpec | None:
        """Return a cell definition by id, or `None` when unknown."""
        with self._lock:
            return self._cells.get(cell_id)

    def list_tenants_in_cell(self, cell_id: str) -> list[str]:
        """List tenant ids currently assigned to one cell."""
        with self._lock:
            return sorted(
                assignment.tenant_id for assignment in self._assignments.find("cell_id", cell_id)
            )

    def replace_snapshot(
        self, *, cells: list[CellSpec], tenants: list[tuple[TenantSpec, str]]
    ) -> None:
        """Atomically replace the in-memory registry from a validated snapshot."""
        with self._lock:
            self._cells.clear()
            self._tenants.clear()
            self._assignments.clear()
            self._cell_tenant_counts = {}
            for cell in cells:
                self.register_cell(cell)
            for tenant, cell_id in tenants:
                self.register_tenant(tenant, cell_id)

    @property
    def cell_count(self) -> int:
        """Return the number of registered cells."""
        with self._lock:
            return self._cells.count

    @property
    def tenant_count(self) -> int:
        """Return the number of registered tenants."""
        with self._lock:
            return self._tenants.count

    def load_from_json(self, path: Path) -> None:
        """Load a registry snapshot from JSON and replace current state.

        Raises:
            ValueError: If a tenant references a missing cell or violates
                placement invariants during snapshot registration.
        """
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
        """Export the current registry snapshot as a JSON-serializable mapping."""
        with self._lock:
            return {
                "cells": [cell.model_dump(mode="json") for cell in self._cells.values()],
                "tenants": [
                    {
                        **tenant.model_dump(mode="json"),
                        "cell_id": self._assignments.require(tenant.tenant_id).cell_id,
                    }
                    for tenant in self._tenants.values()
                ],
            }


__all__ = ["CellRegistry", "CellResolution"]
