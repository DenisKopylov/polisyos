"""
Registry for ConnectorSchemaContract versions and evolution enforcement.
"""
from __future__ import annotations

import threading
from typing import Callable, Iterable, Iterator

from polisyos.common.logger import get_logger
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.registry.generic import GenericRegistry

from .contract import ConnectorSchemaContract
from .evolution import EvolutionReport, SchemaEvolution
from .schema import SchemaVersion

logger = get_logger(__name__)


class ContractNotFoundError(PolicyOSError):
    """Raised when a connector contract is not found."""

    default_stage = "fabric.connectors.contract_registry"
    default_category = ErrorCategory.VALIDATION

    def __init__(self, contract_id: str, version: SchemaVersion | None = None) -> None:
        self.contract_id = contract_id
        self.version = version
        if version is None:
            super().__init__(f"Contract '{contract_id}' not found")
        else:
            super().__init__(f"Contract '{contract_id}' version '{version}' not found")


class ContractVersionError(PolicyOSError):
    """Raised when contract versioning rules are violated."""

    default_stage = "fabric.connectors.contract_registry"
    default_category = ErrorCategory.VALIDATION


class ContractViolationError(PolicyOSError):
    """Raised when breaking contract changes are registered without override."""

    default_stage = "fabric.connectors.contract_registry"
    default_category = ErrorCategory.VALIDATION

    def __init__(self, contract_id: str, report: EvolutionReport) -> None:
        self.contract_id = contract_id
        self.report = report
        breaking_count = len(report.breaking_changes)
        super().__init__(
            f"Contract '{contract_id}' has {breaking_count} breaking change(s); "
            "major schema version bump is required."
        )


ContractRegisteredCallback = Callable[[ConnectorSchemaContract, EvolutionReport | None], None]


class _ContractHistory:
    """Mutable contract history tracked per logical contract_id."""

    def __init__(self, contract_id: str, connector_id: str) -> None:
        self.contract_id = contract_id
        self.connector_id = connector_id
        self.versions: list[ConnectorSchemaContract] = []


class ContractRegistry:
    """
    Thread-safe registry for connector schema contracts.

    - Stores full version history per contract_id
    - Enforces schema evolution semantics using SchemaEvolution
    - Supports connector+dataset contract resolution
    - Exposes revision counter for cheap memoization in callers
    """

    def __init__(self) -> None:
        self._contracts = GenericRegistry[str, _ContractHistory](
            key_fn=lambda history: history.contract_id,
            indexers={"connector_id": lambda history: history.connector_id},
        )
        self._callbacks: list[ContractRegisteredCallback] = []
        self._evolution = SchemaEvolution()
        self._lock = threading.RLock()
        self._revision = 0

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def register_callback(self, callback: ContractRegisteredCallback) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def register(
        self,
        contract: ConnectorSchemaContract,
        *,
        allow_breaking: bool = False,
    ) -> EvolutionReport | None:
        """
        Register a contract version.

        Returns:
            EvolutionReport when previous version exists, else None.
        """
        callbacks: tuple[ContractRegisteredCallback, ...]
        report: EvolutionReport | None = None

        with self._lock:
            history = self._contracts.get(contract.contract_id)
            if history is None:
                history = _ContractHistory(
                    contract_id=contract.contract_id,
                    connector_id=contract.connector_id,
                )
                self._contracts.register(history)
            elif history.connector_id != contract.connector_id:
                raise ContractVersionError(
                    f"{contract.contract_id}: connector_id changed "
                    f"({history.connector_id} -> {contract.connector_id})"
                )

            if history.versions:
                previous = history.versions[-1]
                report = self._evolution.compare(previous.schema, contract.schema)
                self._validate_version_bump(previous, contract, report)

                if report.breaking_changes and not allow_breaking:
                    raise ContractViolationError(contract.contract_id, report)

            history.versions.append(contract)
            self._revision += 1
            callbacks = tuple(self._callbacks)

        for callback in callbacks:
            try:
                callback(contract, report)
            except Exception as exc:  # pragma: no cover - defensive callback isolation
                logger.warning(
                    "Contract registry callback failed",
                    contract_id=contract.contract_id,
                    callback=getattr(callback, "__name__", repr(callback)),
                    error=str(exc),
                )

        logger.info(
            "Contract registered",
            contract_id=contract.contract_id,
            connector_id=contract.connector_id,
            dataset_id=contract.dataset_id,
            schema_version=str(contract.schema_version),
            has_previous=report is not None,
            has_breaking=bool(report.breaking_changes) if report else False,
        )
        return report

    def get(
        self,
        contract_id: str,
        version: str | SchemaVersion | None = None,
    ) -> ConnectorSchemaContract:
        with self._lock:
            history = self._contracts.get(contract_id)
            if history is None or not history.versions:
                raise ContractNotFoundError(contract_id, None if version is None else self._parse(version))

            if version is None:
                return history.versions[-1]

            target = self._parse(version)
            for contract in history.versions:
                if contract.schema_version == target:
                    return contract
            raise ContractNotFoundError(contract_id, target)

    def history(self, contract_id: str) -> tuple[ConnectorSchemaContract, ...]:
        with self._lock:
            history = self._contracts.get(contract_id)
            if history is None or not history.versions:
                raise ContractNotFoundError(contract_id)
            return tuple(history.versions)

    def get_for_connector(self, connector_id: str) -> list[ConnectorSchemaContract]:
        with self._lock:
            rows = self._contracts.find("connector_id", connector_id)
            rows.sort(key=lambda row: row.contract_id)
            return [row.versions[-1] for row in rows if row.versions]

    def resolve(self, connector_id: str, dataset_id: str) -> ConnectorSchemaContract | None:
        """
        Resolve best matching latest contract for connector_id + dataset_id.

        Exact dataset_id match wins over wildcard matches.
        """
        contracts = self.get_for_connector(connector_id)
        if not contracts:
            return None

        matches = [contract for contract in contracts if contract.matches_dataset(dataset_id)]
        if not matches:
            return None

        matches.sort(
            key=lambda contract: (
                contract.dataset_id != dataset_id,
                -len(contract.dataset_id),
                contract.contract_id,
            )
        )
        return matches[0]

    def list_all(self) -> Iterator[ConnectorSchemaContract]:
        with self._lock:
            latest = [history.versions[-1] for history in self._contracts.values() if history.versions]
        for contract in sorted(latest, key=lambda item: item.contract_id):
            yield contract

    def __len__(self) -> int:
        with self._lock:
            return sum(len(history.versions) for history in self._contracts.values())

    def _validate_version_bump(
        self,
        previous: ConnectorSchemaContract,
        current: ConnectorSchemaContract,
        report: EvolutionReport,
    ) -> None:
        previous_version = previous.schema_version
        current_version = current.schema_version

        if current_version <= previous_version and current.content_hash != previous.content_hash:
            raise ContractVersionError(
                f"{current.contract_id}: schema version must increase "
                f"({previous_version} -> {current_version}) when contract changes"
            )

        if not report.changes:
            return

        required = report.recommended_version_bump
        actual = self._actual_bump(previous_version, current_version)

        if required == "major" and actual != "major":
            raise ContractVersionError(
                f"{current.contract_id}: breaking schema changes require major bump "
                f"({previous_version} -> {current_version})"
            )
        if required == "minor" and actual not in {"minor", "major"}:
            raise ContractVersionError(
                f"{current.contract_id}: non-breaking schema changes require at least minor bump "
                f"({previous_version} -> {current_version})"
            )
        if required == "patch" and actual == "none":
            raise ContractVersionError(
                f"{current.contract_id}: contract change requires version bump "
                f"({previous_version} -> {current_version})"
            )

    @staticmethod
    def _actual_bump(previous: SchemaVersion, current: SchemaVersion) -> str:
        if current.major > previous.major:
            return "major"
        if current.minor > previous.minor:
            return "minor"
        if current.patch > previous.patch:
            return "patch"
        return "none"

    @staticmethod
    def _parse(value: str | SchemaVersion) -> SchemaVersion:
        if isinstance(value, SchemaVersion):
            return value
        return SchemaVersion.parse(value)


def build_contract_registry(
    contracts: Iterable[ConnectorSchemaContract],
    *,
    allow_breaking: bool = False,
) -> ContractRegistry:
    """Convenience constructor for a pre-populated contract registry."""
    registry = ContractRegistry()
    for contract in contracts:
        registry.register(contract, allow_breaking=allow_breaking)
    return registry
