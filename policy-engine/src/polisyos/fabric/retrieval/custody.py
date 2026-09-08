"""Persist complete connector results with replayable catalog-selection custody.

This receipt proves the catalog binding and custody of the returned result. It
does not upgrade connector assertions into independently measured source truth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core import canon, scan_secret_and_pii
from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
)
from polisyos.core.contracts.control import FetchPlan
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.ir.connectors import FetchRequest, FetchResult

from .providers import RetrievalProviders

_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_PRODUCER = ProducerInfo(
    component="polisyos.fabric.retrieval.executor.FetchExecutor", version="1.0.0"
)
_SCHEMA_VERSION = "1.0.0"
_FETCH_KIND = "fabric.fetch_receipt"
_BINDING_KIND = "fabric.catalog_fetch_binding"
_PAYLOAD_KIND = "fabric.fetch_payload"
_JSON = "application/json"
_ARROW = "application/vnd.apache.arrow.stream"


class FabricFetchCustodyError(ValueError):
    """Refuse a missing, detached, stale, or malformed fetch custody chain."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FabricFetchReceipt(BaseModel):
    """Carry the actual request and every FetchResult field with full data in CAS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.fabric.fetch_receipt.v1"] = "polisyos.fabric.fetch_receipt.v1"
    used_plan: FetchPlan
    request: FetchRequest
    result: FetchResult[ArtifactRef]
    payload_encoding: Literal["canonical_json", "pandas_arrow_ipc", "arrow_ipc"]
    catalog_binding_ref: ArtifactRef
    authority_scope: Literal["catalog_selection_and_returned_result_custody"] = (
        "catalog_selection_and_returned_result_custody"
    )


@dataclass(frozen=True)
class ResolvedFabricFetch:
    """Expose verified full data and the concrete catalog target to downstream owners."""

    result: FetchResult[Any]
    used_plan: FetchPlan
    catalog_binding: catalog_api.CatalogFetchBinding
    payload_ref: ArtifactRef
    fetch_receipt_ref: ArtifactRef
    catalog_binding_ref: ArtifactRef
    checked_at: datetime
    replayed_result: FetchResult[Any]
    source_agreement: Literal["recomputed"] = "recomputed"


def _require_catalog(catalog: object) -> catalog_api.DatasetCatalogGraph:
    if not isinstance(catalog, catalog_api.DatasetCatalogGraph):
        raise FabricFetchCustodyError("catalog_fetch_owner_missing")
    return catalog


def _bind_plan(catalog: object, plan: FetchPlan) -> catalog_api.CatalogFetchBinding:
    graph = _require_catalog(catalog)
    try:
        return catalog_api.DatasetCatalogGraph.bind_fetch_target(
            graph,
            metric_id=plan.metric_id,
            connector_id=plan.connector_id,
            request_dataset_id=plan.dataset_id,
            profile_id=plan.profile_id,
            filters=plan.filters,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise FabricFetchCustodyError("catalog_fetch_target_not_admitted") from exc


def _encode_payload(data: Any) -> tuple[bytes, str, str]:
    import pandas as pd
    import pyarrow as pa

    if isinstance(data, (pd.DataFrame, pa.Table)):
        pandas_frame = isinstance(data, pd.DataFrame)
        table = pa.Table.from_pandas(data, preserve_index=True) if pandas_frame else data
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return (
            sink.getvalue().to_pybytes(),
            _ARROW,
            "pandas_arrow_ipc" if pandas_frame else "arrow_ipc",
        )
    return canon.to_canonical_bytes(data, spec=_CANON), _JSON, "canonical_json"


def _decode_payload(data: bytes, encoding: str) -> Any:
    if encoding == "canonical_json":
        return canon.from_canonical_bytes(data)
    import pyarrow as pa

    table = pa.ipc.open_stream(data).read_all()
    return table.to_pandas() if encoding == "pandas_arrow_ipc" else table


def _validate_payload(result: FetchResult[Any]) -> None:
    import pandas as pd
    import pyarrow as pa

    data = result.data
    count = None
    if isinstance(data, pd.DataFrame):
        count = len(data)
        scan_data = {
            "columns": list(data.columns),
            "index": list(data.index),
            "records": data.to_dict(orient="records"),
            "attrs": data.attrs,
        }
    elif isinstance(data, pa.Table):
        count = data.num_rows
        scan_data = data.to_pylist()
    else:
        scan_data = data
        if isinstance(data, list):
            count = len(data)
    if count is not None and result.row_count != count:
        raise FabricFetchCustodyError("fabric_fetch_row_count_mismatch")
    scan = scan_secret_and_pii(
        {"data": scan_data, "result": result.model_dump(mode="json", exclude={"data"})},
        scope="connector request/response payloads",
        artifact_ref_or_route="fabric-fetch://payload",
        redact=False,
        block_on_findings=True,
    )
    if scan.has_findings:
        raise FabricFetchCustodyError("fabric_fetch_secret_or_pii_blocked")


def _result_semantics(result: FetchResult[Any]) -> dict[str, Any]:
    """Compare all result fields except explicitly non-authoritative capture timing.

    Current content agreement does not prove the original transport occurred at
    its recorded time. Version timestamp is omitted only when a separate source
    content hash establishes the identical version; source_updated_at, version
    value, paging, schema, quality, provenance and all other fields remain exact.
    """
    if not math.isfinite(result.fetch_duration_ms) or result.fetch_duration_ms < 0:
        raise FabricFetchCustodyError("fabric_fetch_timing_invalid")
    metadata = result.model_dump(mode="json", exclude={"data", "fetched_at", "fetch_duration_ms"})
    if result.version.content_hash is not None:
        metadata["version"].pop("timestamp")
    return metadata


def _require_source_agreement(
    *,
    result: FetchResult[Any],
    raw: bytes,
    encoding: str,
    replayed: FetchResult[Any],
) -> None:
    _validate_payload(replayed)
    replayed_raw, _, replayed_encoding = _encode_payload(replayed.data)
    if (
        raw != replayed_raw
        or encoding != replayed_encoding
        or _result_semantics(result) != _result_semantics(replayed)
    ):
        raise FabricFetchCustodyError("fabric_fetch_source_changed")


def _put_json(
    store: FileSystemCAS, payload: BaseModel, *, kind: str, schema: str, inputs: list[InputRef]
) -> ArtifactRef:
    return store.put_bytes(
        canon.to_canonical_bytes(payload.model_dump(mode="json"), spec=_CANON),
        PutOptions(
            kind=kind,
            media_type=_JSON,
            schema=SchemaInfo(name=schema, version=_SCHEMA_VERSION),
            producer=_PRODUCER,
            inputs=inputs,
        ),
    )


def _persist_fetched_result(
    *,
    store: FileSystemCAS,
    plan: FetchPlan,
    request: FetchRequest,
    result: FetchResult[Any],
    catalog: object,
    binding: catalog_api.CatalogFetchBinding,
) -> tuple[ArtifactRef, ArtifactRef]:
    """Persist only from the executor's actual full-fetch continuation."""
    graph = _require_catalog(catalog)
    try:
        rebound = catalog_api.DatasetCatalogGraph.verify_fetch_binding(graph, binding)
        if rebound != _bind_plan(graph, plan):
            raise FabricFetchCustodyError("catalog_fetch_plan_changed")
        _validate_payload(result)
        payload, media_type, encoding = _encode_payload(result.data)
        # Rebuilding validates concrete metadata even if a connector used model_copy.
        metadata = result.model_dump(mode="json", exclude={"data"})
        payload_ref = store.put_bytes(
            payload,
            PutOptions(
                kind=_PAYLOAD_KIND,
                media_type=media_type,
                schema=SchemaInfo(name="polisyos.fabric.fetch_payload.v1", version=_SCHEMA_VERSION),
                producer=_PRODUCER,
                inputs=[],
            ),
        )
        binding_ref = _put_json(
            store,
            rebound,
            kind=_BINDING_KIND,
            schema="polisyos.data_forge.catalog_fetch_binding.v1",
            inputs=[],
        )
        receipt = FabricFetchReceipt(
            used_plan=plan,
            request=request,
            result=FetchResult[ArtifactRef].model_validate({**metadata, "data": payload_ref}),
            payload_encoding=encoding,
            catalog_binding_ref=binding_ref,
        )
        receipt_ref = _put_json(
            store,
            receipt,
            kind=_FETCH_KIND,
            schema="polisyos.fabric.fetch_receipt.v1",
            inputs=[
                InputRef(artifact_id=payload_ref.artifact_id, role="fetched_payload"),
                InputRef(artifact_id=binding_ref.artifact_id, role="catalog_binding"),
            ],
        )
        return payload_ref, receipt_ref
    except FabricFetchCustodyError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise FabricFetchCustodyError("fabric_fetch_persistence_refused") from exc


def _read(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    kind: str,
    media_type: str,
    schema: str,
    inputs: list[InputRef] | None = None,
) -> bytes:
    checked = ArtifactRef.model_validate(ref.model_dump(mode="python"))
    manifest = store.get_manifest(checked.artifact_id)
    data = store.get_bytes(checked.artifact_id)
    if (
        checked.kind != kind
        or checked.media_type != media_type
        or manifest.kind != kind
        or manifest.media_type != media_type
        or manifest.artifact_schema != SchemaInfo(name=schema, version=_SCHEMA_VERSION)
        or manifest.producer != _PRODUCER
        or manifest.byte_size != len(data)
        or (inputs is not None and manifest.inputs != inputs)
    ):
        raise FabricFetchCustodyError("fabric_fetch_manifest_mismatch")
    return data


def resolve_persisted_fetch(
    *,
    store: FileSystemCAS,
    fetch_receipt_ref: ArtifactRef,
    catalog: catalog_api.DatasetCatalogGraph,
    providers: RetrievalProviders | None = None,
) -> ResolvedFabricFetch:
    """Resolve full result bytes and recompute the exact selected catalog binding.

    Args:
        store: The CAS holding this fetch and its direct inputs.
        fetch_receipt_ref: The executor-emitted receipt reference.
        catalog: The real selected catalog owner, including its optional overlay.
        providers: The selected real connector/profile providers; defaults to
            the ordinary runtime provider owner.

    Returns:
        The complete historical result and a fresh, full connector result that
        agrees with it now. Historical transport occurrence and scientific truth
        are not established by this current-source comparison.

    Raises:
        FabricFetchCustodyError: The source, selected tuple, or CAS chain differs.
    """
    graph = _require_catalog(catalog)
    try:
        receipt = FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(
                _read(
                    store,
                    fetch_receipt_ref,
                    kind=_FETCH_KIND,
                    media_type=_JSON,
                    schema="polisyos.fabric.fetch_receipt.v1",
                )
            )
        )
        binding = catalog_api.CatalogFetchBinding.model_validate(
            canon.from_canonical_bytes(
                _read(
                    store,
                    receipt.catalog_binding_ref,
                    kind=_BINDING_KIND,
                    media_type=_JSON,
                    schema="polisyos.data_forge.catalog_fetch_binding.v1",
                    inputs=[],
                )
            )
        )
        rebound = catalog_api.DatasetCatalogGraph.verify_fetch_binding(graph, binding)
        if rebound != _bind_plan(graph, receipt.used_plan):
            raise FabricFetchCustodyError("catalog_fetch_plan_changed")
        from .executor import FetchExecutor, _fetch_request

        if receipt.request != _fetch_request(receipt.used_plan, page_size=None):
            raise FabricFetchCustodyError("fabric_fetch_request_mismatch")
        expected_inputs = [
            InputRef(artifact_id=receipt.result.data.artifact_id, role="fetched_payload"),
            InputRef(artifact_id=receipt.catalog_binding_ref.artifact_id, role="catalog_binding"),
        ]
        _read(
            store,
            fetch_receipt_ref,
            kind=_FETCH_KIND,
            media_type=_JSON,
            schema="polisyos.fabric.fetch_receipt.v1",
            inputs=expected_inputs,
        )
        raw = _read(
            store,
            receipt.result.data,
            kind=_PAYLOAD_KIND,
            media_type=_JSON if receipt.payload_encoding == "canonical_json" else _ARROW,
            schema="polisyos.fabric.fetch_payload.v1",
            inputs=[],
        )
        result = FetchResult[Any].model_validate(
            {
                **receipt.result.model_dump(mode="python", exclude={"data"}),
                "data": _decode_payload(raw, receipt.payload_encoding),
            }
        )
        _validate_payload(result)
        try:
            replayed = FetchExecutor(providers=providers).replay_fetch(
                plan=receipt.used_plan, request=receipt.request
            )
        except Exception as exc:
            raise FabricFetchCustodyError("fabric_fetch_source_unverifiable") from exc
        _require_source_agreement(
            result=result, raw=raw, encoding=receipt.payload_encoding, replayed=replayed
        )
        catalog_api.DatasetCatalogGraph.verify_fetch_binding(graph, binding)
        return ResolvedFabricFetch(
            result=result,
            used_plan=receipt.used_plan,
            catalog_binding=rebound,
            payload_ref=receipt.result.data,
            fetch_receipt_ref=fetch_receipt_ref,
            catalog_binding_ref=receipt.catalog_binding_ref,
            checked_at=datetime.now(UTC),
            replayed_result=replayed,
        )
    except FabricFetchCustodyError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise FabricFetchCustodyError("fabric_fetch_custody_invalid") from exc
