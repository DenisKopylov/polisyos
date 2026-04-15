"""
Fetch-time schema contract validation middleware.
"""
from __future__ import annotations

import time
import threading
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, TypeVar

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.fabric.temporal import FutureTimestampError, ensure_aware_utc, utc_age
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)
from polisyos.fabric.connectors.types import SchemaError
from polisyos.ir.connectors import ConnectorCapability

from .contract import ConnectorSchemaContract
from .contract_registry import ContractRegistry
from .inference import validate_dataframe_against_schema

if TYPE_CHECKING:
    from polisyos.fabric.connectors.types import FreshnessResult
    from polisyos.ir.connectors import DataVersion

logger = get_logger(__name__)

DataT = TypeVar("DataT")
ValidationMode = Literal["strict", "warn", "disabled"]


class SchemaValidationMode:
    """Schema validation mode public type."""
    STRICT: ClassVar[ValidationMode] = "strict"
    WARN: ClassVar[ValidationMode] = "warn"
    DISABLED: ClassVar[ValidationMode] = "disabled"


class ContractValidatingProxy(Generic[DataT]):
    """Transparent wrapper that validates fetch() results against registered contracts."""

    def __init__(
        self,
        connector: SourceConnector[DataT],
        contract_registry: ContractRegistry,
        *,
        mode: ValidationMode = SchemaValidationMode.STRICT,
        resolution_cache_max_entries: int = 512,
        resolution_cache_ttl_seconds: float = 900.0,
    ) -> None:
        self._connector = connector
        self._registry = contract_registry
        self._mode = mode
        self._resolution_cache: OrderedDict[
            tuple[str, str, int],
            tuple[float, ConnectorSchemaContract | None],
        ] = OrderedDict()
        self._resolution_cache_max_entries = max(1, resolution_cache_max_entries)
        self._resolution_cache_ttl_seconds = max(0.001, resolution_cache_ttl_seconds)
        self._validation_errors_total = 0
        self._validation_warnings_total = 0
        self._lock = threading.RLock()

    @property
    def connector_id(self) -> str:
        return self._connector.connector_id

    @property
    def capabilities(self) -> ConnectorCapability:
        return self._connector.capabilities

    @property
    def metadata(self) -> Any:
        return self._connector.metadata

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return await self._connector.connect(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        await self._connector.disconnect(handle)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return await self._connector.health_check(handle)

    async def list_datasets(self, handle: ConnectionHandle):  # AsyncIterator[DatasetDescriptor]
        async for dataset in self._connector.list_datasets(handle):
            yield dataset

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ):  # AsyncIterator[DataChunk[DataT]]
        async for chunk in self._connector.fetch_stream(handle, request):
            yield chunk

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: "DataVersion",
    ) -> "FreshnessResult":
        return await self._connector.check_freshness(handle, dataset_id, cached_version)

    async def get_dataset_schema(self, handle: ConnectionHandle, dataset_id: str) -> dict[str, Any]:
        return await self._connector.get_dataset_schema(handle, dataset_id)

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[DataT]:
        result = await self._connector.fetch(handle, request)

        if self._mode == SchemaValidationMode.DISABLED:
            return result

        contract = self._resolve_contract(request.dataset_id)
        if contract is None:
            return result

        errors = self._validate_against_contract(result, contract)
        if not errors:
            return result

        with self._lock:
            self._validation_errors_total += len(errors)
        message = (
            f"Schema contract violation ({contract.contract_id}): "
            f"{len(errors)} error(s)"
        )
        if self._mode == SchemaValidationMode.STRICT:
            raise SchemaError(
                message=message,
                connector_id=self.connector_id,
                schema_id=contract.schema.schema_id,
                expected_version=str(contract.schema.version),
                actual_version=result.schema_version,
            )

        with self._lock:
            self._validation_warnings_total += len(errors)
        logger.warning(
            message,
            connector_id=self.connector_id,
            dataset_id=request.dataset_id,
            errors=errors[:10],
        )
        return result

    @property
    def validation_errors_total(self) -> int:
        with self._lock:
            return self._validation_errors_total

    @property
    def validation_warnings_total(self) -> int:
        with self._lock:
            return self._validation_warnings_total

    def _resolve_contract(self, dataset_id: str) -> ConnectorSchemaContract | None:
        key = (self.connector_id, dataset_id, self._registry.revision)
        now = time.monotonic()
        with self._lock:
            self._prune_resolution_cache_locked(now)
            cached = self._resolution_cache.pop(key, None)
            if cached is not None:
                expires_at, contract = cached
                if expires_at > now:
                    self._resolution_cache[key] = (expires_at, contract)
                    return contract

        contract = self._registry.resolve(self.connector_id, dataset_id)
        with self._lock:
            self._resolution_cache[key] = (now + self._resolution_cache_ttl_seconds, contract)
            self._prune_resolution_cache_locked(now)
        return contract

    def _prune_resolution_cache_locked(self, now: float) -> None:
        expired_keys = [
            key for key, (expires_at, _contract) in self._resolution_cache.items()
            if expires_at <= now
        ]
        for key in expired_keys:
            self._resolution_cache.pop(key, None)
        while len(self._resolution_cache) > self._resolution_cache_max_entries:
            self._resolution_cache.popitem(last=False)

    def _validate_against_contract(
        self,
        result: FetchResult[DataT],
        contract: ConnectorSchemaContract,
    ) -> list[str]:
        errors = self._validate_reported_schema(result, contract)
        frame, frame_error = self._coerce_frame(result.data)
        if frame_error:
            return errors + [frame_error]

        errors.extend(validate_dataframe_against_schema(frame, contract.schema, strict=False))
        errors.extend(self._validate_completeness(result, frame, contract))
        errors.extend(self._validate_row_counts(result, contract))
        errors.extend(self._validate_staleness(result, contract))
        return errors

    @staticmethod
    def _validate_reported_schema(
        result: FetchResult[DataT],
        contract: ConnectorSchemaContract,
    ) -> list[str]:
        errors: list[str] = []
        if result.schema_id != contract.schema.schema_id:
            errors.append(
                "reported schema_id "
                f"{result.schema_id!r} does not match contract schema_id "
                f"{contract.schema.schema_id!r}"
            )
        if result.schema_version != str(contract.schema.version):
            errors.append(
                "reported schema_version "
                f"{result.schema_version!r} does not match contract version "
                f"{contract.schema.version!s}"
            )
        return errors

    @staticmethod
    def _coerce_frame(data: DataT) -> tuple[pd.DataFrame, str | None]:
        if isinstance(data, pd.DataFrame):
            return data, None
        if isinstance(data, list):
            if not data:
                return pd.DataFrame(), None
            if all(isinstance(row, dict) for row in data):
                return pd.DataFrame(data), None
        return pd.DataFrame(), "Cannot validate: data is not DataFrame or list[dict]"

    def _validate_completeness(
        self,
        result: FetchResult[DataT],
        frame: pd.DataFrame,
        contract: ConnectorSchemaContract,
    ) -> list[str]:
        errors: list[str] = []

        if contract.min_completeness is not None and result.completeness < contract.min_completeness:
            errors.append(
                f"completeness {result.completeness:.3f} below minimum {contract.min_completeness:.3f}"
            )

        if not contract.field_completeness:
            return errors

        scoped = self._scope_completeness_frame(frame, contract)
        for field_name, min_ratio in sorted(contract.field_completeness.items()):
            if field_name not in scoped.columns:
                errors.append(f"field_completeness field '{field_name}' missing in fetched data")
                continue

            if len(scoped.index) == 0:
                completeness = 0.0
            else:
                completeness = 1.0 - float(scoped[field_name].isna().mean())
            if completeness < min_ratio:
                errors.append(
                    f"field '{field_name}' completeness {completeness:.3f} below {min_ratio:.3f}"
                )
        return errors

    @staticmethod
    def _scope_completeness_frame(
        frame: pd.DataFrame,
        contract: ConnectorSchemaContract,
    ) -> pd.DataFrame:
        if contract.completeness_scope != "latest_window":
            return frame
        if contract.completeness_window_rows is None:
            return frame
        if len(frame.index) <= contract.completeness_window_rows:
            return frame

        time_dimension = contract.schema.time_dimension
        if time_dimension and time_dimension in frame.columns:
            try:
                scoped = frame.sort_values(time_dimension, kind="stable")
                return scoped.tail(contract.completeness_window_rows)
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)
        return frame.tail(contract.completeness_window_rows)

    @staticmethod
    def _validate_row_counts(
        result: FetchResult[DataT],
        contract: ConnectorSchemaContract,
    ) -> list[str]:
        errors: list[str] = []
        min_rows, max_rows = contract.expected_row_count_range
        if min_rows is not None and result.row_count < min_rows:
            errors.append(f"row_count {result.row_count} below minimum {min_rows}")
        if max_rows is not None and result.row_count > max_rows:
            errors.append(f"row_count {result.row_count} above maximum {max_rows}")
        return errors

    @staticmethod
    def _validate_staleness(
        result: FetchResult[DataT],
        contract: ConnectorSchemaContract,
    ) -> list[str]:
        if contract.max_staleness_hours is None:
            return []

        baseline: datetime = ensure_aware_utc(
            result.source_updated_at or result.fetched_at,
            what="source timestamp",
        )
        try:
            age, _warning = utc_age(
                baseline,
                what="source timestamp",
                clamp_future=False,
            )
        except FutureTimestampError as exc:
            return [str(exc)]
        age_hours = age.total_seconds() / 3600.0
        if age_hours > contract.max_staleness_hours:
            return [
                f"source staleness {age_hours:.2f}h exceeds {contract.max_staleness_hours:.2f}h"
            ]
        return []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connector, name)
