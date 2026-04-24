"""Curated source contracts that pin external provider schemas to internal connector expectations."""

from __future__ import annotations

from polisyos.fabric.connectors.contracts import ContractRegistry

from .eurostat_contracts import (
    EUROSTAT_CONTRACTS,
    EUROSTAT_GENERIC_CONTRACT,
    EUROSTAT_GENERIC_SCHEMA,
)
from .sdmx_contracts import SDMX_CONTRACTS, SDMX_GENERIC_CONTRACT, SDMX_GENERIC_SCHEMA
from .ukons_contracts import UKONS_CONTRACTS, UKONS_GENERIC_CONTRACT, UKONS_GENERIC_SCHEMA
from .world_bank_contracts import WDI_GENERIC_CONTRACT, WDI_GENERIC_SCHEMA, WORLD_BANK_CONTRACTS
from .wvs_contracts import WVS_CONTRACTS, WVS_GENERIC_CONTRACT, WVS_GENERIC_SCHEMA

ALL_SOURCE_CONTRACTS = (
    *WORLD_BANK_CONTRACTS,
    *WVS_CONTRACTS,
    *EUROSTAT_CONTRACTS,
    *UKONS_CONTRACTS,
    *SDMX_CONTRACTS,
)


def build_builtin_contract_registry() -> ContractRegistry:
    """Build the canonical Fabric contract registry used by runtime and CI."""

    registry = ContractRegistry()
    for contract in ALL_SOURCE_CONTRACTS:
        registry.register(contract, allow_breaking=True)
    return registry


__all__ = [
    "ALL_SOURCE_CONTRACTS",
    "EUROSTAT_CONTRACTS",
    "EUROSTAT_GENERIC_CONTRACT",
    "EUROSTAT_GENERIC_SCHEMA",
    "SDMX_CONTRACTS",
    "SDMX_GENERIC_CONTRACT",
    "SDMX_GENERIC_SCHEMA",
    "UKONS_CONTRACTS",
    "UKONS_GENERIC_CONTRACT",
    "UKONS_GENERIC_SCHEMA",
    "WDI_GENERIC_CONTRACT",
    "WDI_GENERIC_SCHEMA",
    "WORLD_BANK_CONTRACTS",
    "WVS_CONTRACTS",
    "WVS_GENERIC_CONTRACT",
    "WVS_GENERIC_SCHEMA",
    "build_builtin_contract_registry",
]
