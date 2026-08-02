"""Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

The package exports the supported entry points for connector-backed acquisition and materialized
world reads while keeping heavy dependencies lazy. ``__all__`` defines the stable facade; catalog
contracts are still available through lazy attribute loading, and ``world`` is exposed as a lazy
subpackage for lower-level materialization utilities.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
import warnings
from types import ModuleType

__all__ = [
    "AccessRef",
    "AuthoredText",
    "ConnectorRegistryLike",
    "ConnectorSchemaContract",
    "DataSchema",
    "FabricDecisionData",
    "FabricDecisionDataCoverage",
    "FabricDecisionDataResponse",
    "FieldSpec",
    "LineageRef",
    "ProcessingGuarantee",
    "ProcessingGuaranteeContract",
    "QualityRef",
    "ReplayRef",
    "SchemaType",
    "SimulationDB",
    "SourceContract",
    "SourceContractRef",
    "TemporalRef",
    "TypedGap",
    "UnitRef",
    "WorldQueryError",
    "WorldQueryRequest",
    "atomic_write_json",
    "batch_processing_contract",
    "build_source_contract_requirement_bindings",
    "execute_world_query",
    "fabric_claim_to_authored_text",
    "fabric_event_to_authored_text",
    "fabric_fact_to_quantity_value",
    "fabric_get_data",
    "query_claims",
    "query_events",
    "query_world_table",
    "resolve_connector_registry",
    "resolve_world_snapshot",
    "run_connectors_ingestion",
    "stream_processing_contract",
    "world",
]


class _LazyReexportModule(ModuleType):
    """Lazy compatibility module that forwards reads and monkeypatch writes."""

    def __init__(self, alias_fqn: str, target_fqn: str, *, is_package: bool = False) -> None:
        super().__init__(alias_fqn)
        super().__setattr__("_alias_fqn", alias_fqn)
        super().__setattr__("_target_fqn", target_fqn)
        super().__setattr__("_target_module", None)
        super().__setattr__("_warned", False)
        super().__setattr__("__doc__", f"Compatibility re-export for ``{target_fqn}``.")
        super().__setattr__("__package__", alias_fqn.rpartition(".")[0])
        if is_package:
            super().__setattr__("__path__", [])

    def _warn_deprecated(self, *, stacklevel: int = 3) -> None:
        if self.__dict__.get("_warned"):
            return
        warnings.warn(
            (
                f"{self.__dict__['_alias_fqn']} is a deprecated Fabric compatibility import; "
                f"use {self.__dict__['_target_fqn']} instead. This shim is scheduled for "
                "removal after 2026-12-31; see "
                "docs/archive/reports/REPOSITORY_BEST_IN_CLASS_LAST_MILE_IMPORT_MAP.md"
                "#fabric-shell-packages."
            ),
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        super().__setattr__("_warned", True)

    def _target(self) -> ModuleType:
        self._warn_deprecated()
        target = self.__dict__.get("_target_module")
        if target is None:
            target = importlib.import_module(self.__dict__["_target_fqn"])
            super().__setattr__("_target_module", target)
        return target

    def __getattr__(self, name: str) -> object:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._target(), name)

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("__") or name in {"_target_fqn", "_target_module"}:
            super().__setattr__(name, value)
            return
        setattr(self._target(), name, value)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self._target())))


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "atomic_write_json": ("polisyos.fabric.io.atomic", "atomic_write_json"),
    "AccessRef": ("polisyos.fabric.evidence.decision_data", "AccessRef"),
    "AuthoredText": ("polisyos.fabric.evidence.decision_data", "AuthoredText"),
    "FabricDecisionData": ("polisyos.fabric.evidence.decision_data", "FabricDecisionData"),
    "FabricDecisionDataCoverage": (
        "polisyos.fabric.evidence.decision_data",
        "FabricDecisionDataCoverage",
    ),
    "FabricDecisionDataResponse": (
        "polisyos.fabric.evidence.decision_data",
        "FabricDecisionDataResponse",
    ),
    "fabric_claim_to_authored_text": (
        "polisyos.fabric.evidence.decision_data",
        "fabric_claim_to_authored_text",
    ),
    "fabric_event_to_authored_text": (
        "polisyos.fabric.evidence.decision_data",
        "fabric_event_to_authored_text",
    ),
    "fabric_fact_to_quantity_value": (
        "polisyos.fabric.evidence.decision_data",
        "fabric_fact_to_quantity_value",
    ),
    "LineageRef": ("polisyos.fabric.evidence.decision_data", "LineageRef"),
    "QualityRef": ("polisyos.fabric.evidence.decision_data", "QualityRef"),
    "ReplayRef": ("polisyos.fabric.evidence.decision_data", "ReplayRef"),
    "SourceContractRef": ("polisyos.fabric.evidence.decision_data", "SourceContractRef"),
    "TemporalRef": ("polisyos.fabric.evidence.decision_data", "TemporalRef"),
    "TypedGap": ("polisyos.fabric.evidence.decision_data", "TypedGap"),
    "UnitRef": ("polisyos.fabric.evidence.decision_data", "UnitRef"),
    "ProcessingGuarantee": (
        "polisyos.fabric.quality.processing_guarantees",
        "ProcessingGuarantee",
    ),
    "ProcessingGuaranteeContract": (
        "polisyos.fabric.quality.processing_guarantees",
        "ProcessingGuaranteeContract",
    ),
    "batch_processing_contract": (
        "polisyos.fabric.quality.processing_guarantees",
        "batch_processing_contract",
    ),
    "stream_processing_contract": (
        "polisyos.fabric.quality.processing_guarantees",
        "stream_processing_contract",
    ),
    "ConnectorRegistryLike": ("polisyos.fabric.api", "ConnectorRegistryLike"),
    "ConnectorSchemaContract": (
        "polisyos.fabric.connectors.contracts",
        "ConnectorSchemaContract",
    ),
    "DataSchema": ("polisyos.fabric.connectors.contracts", "DataSchema"),
    "FieldSpec": ("polisyos.fabric.connectors.contracts", "FieldSpec"),
    "SchemaType": ("polisyos.fabric.connectors.contracts", "SchemaType"),
    "SourceContract": ("polisyos.fabric.connectors.contracts", "SourceContract"),
    "fabric_get_data": ("polisyos.fabric.api", "fabric_get_data"),
    "SimulationDB": ("polisyos.fabric.io.db", "SimulationDB"),
    "resolve_connector_registry": (
        "polisyos.fabric.api",
        "resolve_connector_registry",
    ),
    "execute_world_query": ("polisyos.fabric.world.query", "execute_world_query"),
    "run_connectors_ingestion": (
        "polisyos.fabric.ingestion.ingestion",
        "run_connectors_ingestion",
    ),
    "query_claims": ("polisyos.fabric.world.query", "query_claims"),
    "query_events": ("polisyos.fabric.world.query", "query_events"),
    "query_world_table": ("polisyos.fabric.world.query", "query_world_table"),
    "resolve_world_snapshot": ("polisyos.fabric.world.store", "resolve_world_snapshot"),
    "WorldQueryError": ("polisyos.fabric.world.query", "WorldQueryError"),
    "WorldQueryRequest": ("polisyos.fabric.world.query", "WorldQueryRequest"),
    "ContractHashMismatchError": ("polisyos.fabric.catalog", "ContractHashMismatchError"),
    "ContractNotFoundError": ("polisyos.fabric.catalog", "ContractNotFoundError"),
    "ContractValidationError": ("polisyos.fabric.catalog", "ContractValidationError"),
    "DataContract": ("polisyos.fabric.catalog", "DataContract"),
    "DataContractCollection": ("polisyos.fabric.catalog", "DataContractCollection"),
    "DataContractRegistry": ("polisyos.fabric.catalog", "DataContractRegistry"),
    "DataContractSchemaBinding": ("polisyos.fabric.catalog", "DataContractSchemaBinding"),
    "DataType": ("polisyos.fabric.catalog", "DataType"),
    "Granularity": ("polisyos.fabric.catalog", "Granularity"),
    "MetricBinding": ("polisyos.fabric.catalog", "MetricBinding"),
    "MetricSearcher": ("polisyos.fabric.catalog", "MetricSearcher"),
    "PIITier": ("polisyos.fabric.catalog", "PIITier"),
    "SearchResponse": ("polisyos.fabric.catalog", "SearchResponse"),
    "SearchResult": ("polisyos.fabric.catalog", "SearchResult"),
    "load_contract_collection": ("polisyos.fabric.catalog", "load_contract_collection"),
    "build_source_contract_requirement_bindings": (
        "polisyos.fabric.catalog",
        "build_source_contract_requirement_bindings",
    ),
}

_COMPAT_MODULE_ALIASES: dict[str, str] = {}
_PACKAGE_COMPAT_ALIASES: set[str] = set()


class _FabricCompatAliasLoader(importlib.abc.Loader):
    def __init__(self, target_fqn: str, *, is_package: bool = False) -> None:
        self._target_fqn = target_fqn
        self._is_package = is_package

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = _LazyReexportModule(spec.name, self._target_fqn, is_package=self._is_package)
        module._warn_deprecated(stacklevel=4)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _FabricCompatAliasFinder(importlib.abc.MetaPathFinder):
    _polisyos_fabric_alias_finder = True

    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: object | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        target_fqn = _COMPAT_MODULE_ALIASES.get(fullname)
        if target_fqn is None:
            return None
        is_package = fullname in _PACKAGE_COMPAT_ALIASES
        loader = _FabricCompatAliasLoader(target_fqn, is_package=is_package)
        spec = importlib.machinery.ModuleSpec(fullname, loader, is_package=is_package)
        if is_package:
            spec.submodule_search_locations = []
        return spec


def _install_compat_alias_finder() -> None:
    if any(getattr(finder, "_polisyos_fabric_alias_finder", False) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _FabricCompatAliasFinder())


def _install_compat_module_aliases() -> None:
    _install_compat_alias_finder()
    alias_modules: dict[str, ModuleType] = {}
    for alias_fqn, target_fqn in _COMPAT_MODULE_ALIASES.items():
        module = sys.modules.get(alias_fqn)
        if module is None:
            module = _LazyReexportModule(
                alias_fqn,
                target_fqn,
                is_package=alias_fqn in _PACKAGE_COMPAT_ALIASES,
            )
            sys.modules[alias_fqn] = module
        alias_modules[alias_fqn] = module

        parent_fqn, _, leaf = alias_fqn.rpartition(".")
        if parent_fqn == __name__:
            globals()[leaf] = module

    for alias_fqn, module in alias_modules.items():
        parent_fqn, _, leaf = alias_fqn.rpartition(".")
        parent = alias_modules.get(parent_fqn)
        if parent is not None:
            ModuleType.__setattr__(parent, leaf, module)


_install_compat_module_aliases()


def __getattr__(name: str) -> object:
    """Load Fabric exports or the ``world`` subpackage lazily.

    Raises:
        AttributeError: If ``name`` is not a supported Fabric facade symbol.
    """
    if name == "world":
        module = importlib.import_module("polisyos.fabric.world")
        globals()[name] = module
        return module
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.fabric' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Return eager globals plus lazily exported Fabric symbols."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
