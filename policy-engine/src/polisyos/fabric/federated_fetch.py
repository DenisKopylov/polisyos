"""Bounded candidate acquisition, independently selected request and Core projection.

Captured rows are never a proof of EOF, fulfilled filtering, source authority or
currentness. The acquisition receipt binds the requested scope and captured
software basis; receipt-supplied capture origin remains consumer_asserted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import write_bytes_atomic
from polisyos.core.canon import (
    CanonicalResourceLimits,
    CanonSpec,
    from_canonical_bytes,
    to_bounded_canonical_bytes,
)
from polisyos.fabric.connectors.federation.artifact import (
    FederationArtifactRef,
    SelectedFederationInput,
    persist_federation_derivation,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.composer import DataComposer
from polisyos.fabric.connectors.federation.profile import (
    MAX_CELLS,
    MAX_FILE_BYTES,
    MAX_GRAPH_NODES,
    MAX_ROWS,
    MAX_SOURCES,
    bounded_encode,
    encode_scalar,
    frame_projection,
)
from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    CompositionRequest,
    FederationError,
    SourceMetadata,
)
from polisyos.ir.connectors import (
    ConnectorMetadataSpec,
    DataVersion,
    FetchProvenanceEnvelope,
    FetchQualityEnvelope,
    FetchResult,
    FetchTransferEnvelope,
    QualityTier,
    TrustLevel,
    VersionStrategy,
)

if TYPE_CHECKING:
    from polisyos.fabric.api import ConnectorRegistryLike, FederationFetchRequest
    from polisyos.fabric.connectors.federation.artifact import VerifiedFederationResult

_FORMAT = "policyos.fabric.federation-acquisition/2"
_CORE_SPEC = CanonSpec(forbid_floats=False, exclude_none=False)
_CORE_LIMITS = CanonicalResourceLimits(
    policy_id="fabric.federation.core-projection/1",
    max_wire_bytes=MAX_FILE_BYTES,
    max_wire_depth=32,
    max_elements=MAX_CELLS * 5 + MAX_ROWS * 4,
)


class FederationSnapshotProjectionError(FederationError):
    """Selected data cannot be delivered under this exact Core row profile."""

    profile_id: ClassVar[str] = "fabric.federation.core-projection/1"
    limitation: ClassVar[str] = "selected_value_not_losslessly_representable_in_CAN.2_rows"
    required_capability: ClassVar[str] = "agreed_lossless_snapshot_row_codec_and_reader"


class FederationFetchObservation(BaseModel):
    """A selected source member and consumer-asserted capture/provenance claims."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    position: int = Field(ge=0)
    selected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connector_id: str
    dataset_id: str
    request_key: str
    observed_at: datetime
    row_count: int = Field(ge=0)
    schema_id: str
    schema_version: str
    quality: FetchQualityEnvelope
    transfer: FetchTransferEnvelope
    provenance: FetchProvenanceEnvelope
    provenance_basis: Literal["consumer_asserted"] = "consumer_asserted"
    observation_basis: Literal["consumer_asserted"] = "consumer_asserted"
    captured_bytes_basis: Literal["consumer_asserted"] = "consumer_asserted"
    selected_member_bytes_basis: Literal["recomputed"] = "recomputed"
    selected_member_row_count_basis: Literal["recomputed"] = "recomputed"
    source_scope: Literal["captured_rows_only"] = "captured_rows_only"
    source_completeness: Literal["not_established"] = "not_established"
    pagination_reported: bool


class FederationParentObservation(BaseModel):
    """Kernel parents do not carry a separately bound acquisition/warning history."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    position: int = Field(ge=0)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_history: Literal["unavailable"] = "unavailable"
    warning_history: Literal["not_established"] = "not_established"


class FederationColumnProjection(BaseModel):
    """Fresh selected schema retained even when there are no rows."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    name: str
    pandas_dtype: str


class FederationFetchAudit(BaseModel):
    """Request-bound selected candidate; no field is an EOF or authority proof."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    artifact_root: Path
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fetches: tuple[FederationFetchObservation, ...]
    parents: tuple[FederationParentObservation, ...]
    held_parents: dict[str, Path]
    columns: tuple[FederationColumnProjection, ...]
    merge_summary: dict[str, Any]
    verified_at: datetime
    assurance: Literal["software_derivation_candidate"] = "software_derivation_candidate"
    selected_bytes_basis: Literal["recomputed"] = "recomputed"
    leaf_history_basis: Literal["consumer_asserted"] = "consumer_asserted"
    capture_origin_basis: Literal["consumer_asserted"] = "consumer_asserted"
    observation_origin_basis: Literal["consumer_asserted"] = "consumer_asserted"
    capture_scope: Literal["captured_rows_only"] = "captured_rows_only"
    fetches_scope: Literal["fresh_connector_fetches_only"] = "fresh_connector_fetches_only"
    parent_history: Literal["not_applicable", "unavailable"]
    output_completeness: Literal["not_established"] = "not_established"
    data_shape_basis: Literal["not_established"] = "not_established"
    workflow_compatibility_basis: Literal["not_established"] = "not_established"
    limitation: str


class FederatedFetchResult(FetchResult[Any]):
    """FetchResult-compatible captured candidate with a selected receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
    federation_audit: FederationFetchAudit


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_selected_json(path: Path, digest: str) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            value = stream.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise FederationError("Independently selected acquisition bytes unavailable") from exc
    if len(value) > MAX_FILE_BYTES or _sha(value) != digest:
        raise FederationError("Selected acquisition/basis bytes unavailable or different")
    try:
        decoded = json.loads(value)
    except (ValueError, RecursionError) as exc:
        raise FederationError("Selected acquisition/basis JSON is unsupported") from exc
    if not isinstance(decoded, dict):
        raise FederationError("Selected acquisition/basis object is not a mapping")
    return decoded


def _metadata(metadata: SourceMetadata) -> dict[str, Any]:
    if metadata.quality_report is not None or metadata.coverage is not None:
        raise FederationError("Parent metadata is outside the selected wire profile")
    return {
        "connector_id": metadata.connector_id,
        "metadata": metadata.metadata.model_dump(mode="json"),
        "fetched_at": metadata.fetched_at.isoformat(),
        "row_count": metadata.row_count,
        "last_updated": metadata.last_updated.isoformat() if metadata.last_updated else None,
        "observed_latency_ms": metadata.observed_latency_ms,
    }


def freeze_federation_request(
    *,
    dataset_id: str,
    federation: FederationFetchRequest,
    constraints: dict[str, Any] | None,
    registry: ConnectorRegistryLike | None = None,
) -> str:
    """Freeze independent requested intent before invoking any fetch callback.

    Nonempty filter/date scope is unsupported in this first capture profile for
    every source kind. A requested page_size is a capture bound, never EOF.
    """
    from polisyos.fabric.api import (
        FederationFetchRequest,
        FederationFetchSource,
        resolve_connector_registry,
    )

    if type(federation) is not FederationFetchRequest:
        raise FederationError("An explicit FederationFetchRequest is required")
    request = federation.composition
    if type(request) is not CompositionRequest or request.schema is not None:
        raise FederationError("A supported schema-free CompositionRequest is required")
    if dataset_id != request.dataset_pattern or request.max_staleness is not None:
        raise FederationError("Dataset mismatch or unsupported currentness constraint")
    if type(federation.sources) is not tuple or not 1 <= len(federation.sources) <= MAX_SOURCES:
        raise FederationError("A bounded explicit source tuple is required")
    constraints = dict(constraints or {})
    if set(constraints) - {"page_size", "filters", "date_start", "date_end"}:
        raise FederationError("Unsupported capture constraints")
    filters = constraints.get("filters")
    if (
        (filters is not None and (type(filters) is not dict or bool(filters)))
        or constraints.get("date_start") is not None
        or constraints.get("date_end") is not None
    ):
        raise FederationError(
            "Filter/date scope is unsupported before capture for every source kind",
        )
    page_size = constraints.get("page_size")
    if page_size is not None and (type(page_size) is not int or not 1 <= page_size <= MAX_ROWS):
        raise FederationError("Capture page_size exceeds the supported engineering profile")
    if not isinstance(federation.output_root, Path):
        raise FederationError("Acquisition output_root must be a Path")
    resolved = resolve_connector_registry(registry)
    selected = []
    parents: dict[str, str] = {}
    for source in federation.sources:
        if isinstance(source, SelectedFederationInput):
            for index, (digest, path) in enumerate(source.parents.items()):
                if index >= MAX_GRAPH_NODES:
                    raise FederationError("Parent registry exceeds the graph profile")
                resolved_path = str(path.resolve())
                if digest in parents and parents[digest] != resolved_path:
                    raise FederationError("Ambiguous held parent")
                parents[digest] = resolved_path
            digest = source.ref.manifest_sha256
            root = str(source.root.resolve())
            if digest in parents and parents[digest] != root:
                raise FederationError("Ambiguous selected parent")
            parents[digest] = root
            selected.append(
                {"kind": "parent", "digest": digest, "metadata": _metadata(source.metadata)}
            )
        elif type(source) is FederationFetchSource:
            metadata = getattr(resolved.get_entry(source.connector_id), "metadata", None)
            if not isinstance(metadata, ConnectorMetadataSpec) or not source.dataset_id:
                raise FederationError("Selected source lacks typed registry metadata/dataset")
            if metadata.trust_level < request.min_trust_level:
                raise FederationError("Declared source is below the candidate trust preference")
            selected.append(
                {
                    "kind": "connector",
                    "connector_id": source.connector_id,
                    "dataset_id": source.dataset_id,
                    "metadata": metadata.model_dump(mode="json"),
                }
            )
        else:
            raise FederationError("Unsupported source selection")
        if len(parents) > MAX_GRAPH_NODES:
            raise FederationError("Held parent union exceeds the graph profile")
    # Enums are str/int subclasses; max_staleness and schema were pre-refused.
    composition = json.loads(bounded_encode(asdict(request)))
    context = {
        "dataset_id": dataset_id,
        "composition": composition,
        "sources": selected,
        "constraints": {"page_size": page_size},
        "held_parents": parents,
        "output_root": str(federation.output_root.resolve()),
        "capture_scope": "captured_rows_only",
    }
    _admit_context(context, federation.output_root)
    return bounded_encode(context).decode()


def _capture_bound(context: dict[str, Any]) -> int | None:
    constraints = context.get("constraints")
    if type(constraints) is not dict or set(constraints) != {"page_size"}:
        raise FederationError("Unsupported frozen capture constraint profile")
    bound = constraints["page_size"]
    if bound is not None and (type(bound) is not int or not 1 <= bound <= MAX_ROWS):
        raise FederationError("Invalid frozen source/output row bound")
    return bound


def _admit_rows(rows: int, bound: int | None, subject: str) -> None:
    if bound is not None and rows > bound:
        raise FederationError(f"{subject} exceeds the independently requested row bound")


def _admit_context(context: dict[str, Any], root: Path) -> None:
    expected = {
        "dataset_id",
        "composition",
        "sources",
        "constraints",
        "held_parents",
        "output_root",
        "capture_scope",
    }
    if set(context) != expected or context["capture_scope"] != "captured_rows_only":
        raise FederationError("Unsupported frozen acquisition profile")
    composition = context["composition"]
    if type(composition) is not dict or set(composition) != {
        field.name for field in fields(CompositionRequest)
    }:
        raise FederationError("Frozen composition does not match the owner contract")
    if (
        composition["schema"] is not None
        or composition["max_staleness"] is not None
        or type(composition["min_trust_level"]) is not int
        or type(context["dataset_id"]) is not str
        or not context["dataset_id"].strip()
        or context["dataset_id"] != composition["dataset_pattern"]
        or str(root.resolve()) != context["output_root"]
    ):
        raise FederationError("Unsupported or mismatched frozen request scope")
    TrustLevel(composition["min_trust_level"])
    sources = context["sources"]
    if type(sources) is not list or not 1 <= len(sources) <= MAX_SOURCES:
        raise FederationError("Frozen source selection exceeds its supported profile")
    if type(context["held_parents"]) is not dict or len(context["held_parents"]) > MAX_GRAPH_NODES:
        raise FederationError("Frozen parent registry exceeds its supported profile")
    _capture_bound(context)
    for source in sources:
        if type(source) is not dict:
            raise FederationError("Frozen source is not a typed selection mapping")
        if source.get("kind") == "connector":
            if set(source) != {"kind", "connector_id", "dataset_id", "metadata"} or (
                type(source["connector_id"]) is not str
                or type(source["dataset_id"]) is not str
                or not source["connector_id"]
                or not source["dataset_id"]
            ):
                raise FederationError("Unsupported frozen connector selection")
        elif source.get("kind") == "parent":
            if set(source) != {"kind", "digest", "metadata"}:
                raise FederationError("Unsupported frozen parent selection")
        else:
            raise FederationError("Unsupported frozen source kind")


def _validate_kernel_binding(
    root: Path,
    ref: FederationArtifactRef,
    context: dict[str, Any],
    observations: tuple[FederationFetchObservation, ...],
) -> dict[str, Any]:
    """Reconcile exact selected kernel members after its actual graph replay."""
    manifest = _read_selected_json(root / "manifest.json", ref.manifest_sha256)
    if _fingerprint(manifest["request"]) != _fingerprint(context["composition"]):
        raise FederationError(
            "Selected derivation differs from the independent composition request",
        )
    records = manifest["sources"]
    if len(records) != len(context["sources"]):
        raise FederationError("Selected source count differs from the independent request")
    by_position = {observation.position: observation for observation in observations}
    expected_positions = {
        i for i, source in enumerate(context["sources"]) if source["kind"] == "connector"
    }
    if set(by_position) != expected_positions or len(by_position) != len(observations):
        raise FederationError(
            "Acquisition observations do not cover the selected connector positions",
        )
    from polisyos.ir.connectors import FetchRequest

    bound = _capture_bound(context)
    held = {digest: Path(path) for digest, path in context["held_parents"].items()}
    for position, (record, source) in enumerate(zip(records, context["sources"], strict=True)):
        value = _read_selected_json(root / record["path"], record["sha256"])
        if source["kind"] == "parent":
            expected = {"parent": source["digest"], "metadata": source["metadata"]}
            if _fingerprint(value) != _fingerprint(expected):
                raise FederationError("Selected parent differs from the independently held basis")
            parent = read_verified_federation_derivation(
                held[source["digest"]], FederationArtifactRef(source["digest"]), held_parents=held
            )
            actual_rows = len(parent.data)
            if type(source["metadata"]["row_count"]) is not int or (
                source["metadata"]["row_count"] != actual_rows
            ):
                raise FederationError("Declared parent row count differs from its selected rows")
            _admit_rows(actual_rows, bound, f"Selected parent {position}")
            continue
        if source["kind"] != "connector" or set(value) != {"frame", "metadata"}:
            raise FederationError("Unsupported selected source kind")
        observation = by_position[position]
        # This is compatibility of the supplied claim, not proof that no
        # unreported fallback/304 occurred. Capture origin stays consumer_asserted.
        if observation.transfer.not_modified or (
            observation.transfer.resilience is not None
            and observation.transfer.resilience.fallback_used
        ):
            raise FederationError("Receipt declares an unsupported transfer scenario")
        request = FetchRequest(
            dataset_id=source["dataset_id"], page_size=context["constraints"]["page_size"]
        )
        actual_rows = len(value["frame"]["rows"])
        expected_metadata = {
            "connector_id": observation.connector_id,
            "metadata": source["metadata"],
            "row_count": actual_rows,
            "fetched_at": observation.provenance.fetched_at.isoformat(),
            "last_updated": observation.provenance.source_updated_at.isoformat()
            if observation.provenance.source_updated_at
            else None,
            "observed_latency_ms": None,
        }
        if (
            _fingerprint(value["metadata"]) != _fingerprint(expected_metadata)
            or observation.connector_id
            != (ConnectorMetadataSpec.model_validate(source["metadata"]).fully_qualified_id)
            or observation.dataset_id != source["dataset_id"]
            or observation.request_key != request.request_key
            or observation.selected_source_sha256 != record["sha256"]
            or observation.row_count != actual_rows
        ):
            raise FederationError("Selected member/receipt differs from the requested source basis")
        # Matching bytes/request is not proof of who supplied the capture.
        # All receipt-origin observations remain consumer_asserted.
        _admit_rows(actual_rows, bound, f"Declared connector capture {position}")
    return manifest


def _admit_declared_preference(
    verified: VerifiedFederationResult,
    context: dict[str, Any],
) -> None:
    if not verified.source_declarations:
        raise FederationError("Fresh graph does not expose its declared whole-leaf basis")
    threshold = TrustLevel(context["composition"]["min_trust_level"])
    for _token, declaration in verified.source_declarations:
        leaf = ConnectorMetadataSpec.model_validate(json.loads(declaration)["metadata"])
        if leaf.trust_level < threshold:
            raise FederationError("Fresh selected graph contains a declared leaf below the filter")


def _admit_selected_capture(
    root: Path,
    ref: FederationArtifactRef,
    context: dict[str, Any],
    observations: tuple[FederationFetchObservation, ...],
) -> VerifiedFederationResult:
    """The sole successful-result admission, shared by producer and consumer.

    Every load-bearing predicate is recomputed from independent frozen intent
    and actual fresh selected graph bytes. Capture origin is not authenticated.
    """
    _admit_context(context, root)
    held = {digest: Path(path) for digest, path in context["held_parents"].items()}
    verified = read_verified_federation_derivation(root, ref, held_parents=held)
    _validate_kernel_binding(root, ref, context, observations)
    _admit_declared_preference(verified, context)
    _admit_rows(len(verified.data), _capture_bound(context), "Composed output")
    return verified


def _result(
    verified: VerifiedFederationResult,
    root: Path,
    ref: FederationArtifactRef,
    receipt_sha256: str,
    context: dict[str, Any],
    observations: tuple[FederationFetchObservation, ...],
    observed_at: datetime,
    elapsed_ms: float,
) -> FederatedFetchResult:
    if verified.basis_status.selected_bytes != "recomputed":
        raise FederationError("Selected software basis was not recomputed")
    parents = tuple(
        FederationParentObservation(position=i, manifest_sha256=source["digest"])
        for i, source in enumerate(context["sources"])
        if source["kind"] == "parent"
    )
    audit = FederationFetchAudit(
        artifact_root=root,
        manifest_sha256=ref.manifest_sha256,
        acquisition_sha256=receipt_sha256,
        request_binding_sha256=_sha(bounded_encode(context)),
        fetches=observations,
        parents=parents,
        held_parents={digest: Path(path) for digest, path in context["held_parents"].items()},
        columns=tuple(
            FederationColumnProjection(name=name, pandas_dtype=str(dtype))
            for name, dtype in verified.data.dtypes.items()
        ),
        merge_summary=verified.merge_summary,
        verified_at=observed_at,
        parent_history="unavailable" if parents else "not_applicable",
        limitation=verified.limitation,
    )
    flags = set().union(*(observation.quality.quality_flags for observation in observations))
    flags.update(
        {
            "federation.software_derivation_candidate",
            "federation.captured_rows_only",
            "federation.source_completeness_not_established",
            "federation.currentness_not_established",
            "federation.output_completeness_not_established",
            "federation.capture_origin_consumer_asserted",
        }
    )
    if parents:
        flags.update(
            {
                "federation.parent_observations_unavailable",
                "federation.parent_quality_history_unavailable",
            }
        )
    digest = f"sha256:{ref.manifest_sha256}"
    return FederatedFetchResult(
        data=verified.data,
        row_count=len(verified.data),
        schema_id="polisyos.fabric.federation",
        schema_version="1.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=digest,
            content_hash=digest,
            timestamp=observed_at,
        ),
        fetched_at=observed_at,
        source_updated_at=None,
        completeness=0.0,
        quality_tier=QualityTier.UNVERIFIED,
        quality_flags=frozenset(flags),
        fetch_duration_ms=elapsed_ms,
        federation_audit=audit,
    )


def fetch_federated(
    *,
    dataset_id: str,
    federation: FederationFetchRequest,
    constraints: dict[str, Any] | None,
    registry: ConnectorRegistryLike,
) -> FederatedFetchResult:
    """Capture explicitly unknown source scope; never infer EOF from markers."""
    from polisyos.fabric.api import _sync_fetch
    from polisyos.ir.connectors import FetchRequest

    frozen = freeze_federation_request(
        dataset_id=dataset_id, federation=federation, constraints=constraints, registry=registry
    )
    context = json.loads(frozen)
    root = Path(context["output_root"])
    if root.exists() or root.is_symlink():
        raise FederationError("Acquisition output root already exists")
    held = {digest: Path(path) for digest, path in context["held_parents"].items()}
    inputs: list[tuple[pd.DataFrame, SourceMetadata] | SelectedFederationInput] = []
    observations = []
    started = perf_counter()
    for position, source in enumerate(context["sources"]):
        if source["kind"] == "parent":
            selected = federation.sources[position]
            if not isinstance(selected, SelectedFederationInput):
                raise FederationError("Frozen parent selection changed")
            # Early refusal uses the same predicates and frozen intent as the
            # canonical fresh-result intake; it is not a consumer substitute.
            parent = read_verified_federation_derivation(
                held[source["digest"]], FederationArtifactRef(source["digest"]), held_parents=held
            )
            _admit_rows(len(parent.data), _capture_bound(context), "Selected parent")
            _admit_declared_preference(parent, context)
            inputs.append(selected)
            continue
        request = FetchRequest(
            dataset_id=source["dataset_id"], page_size=context["constraints"]["page_size"]
        )
        fetched = _sync_fetch(
            registry, source["connector_id"], registry.get(source["connector_id"]), request
        )
        if fetched.not_modified or (
            fetched.resilience is not None and fetched.resilience.fallback_used
        ):
            raise FederationError(
                "Unmaterialized/fallback source requires a separate explicit basis",
            )
        if not isinstance(fetched.data, pd.DataFrame) or fetched.row_count != len(fetched.data):
            raise FederationError(
                "A materialized dataframe with its exact captured row count is required",
            )
        _admit_rows(len(fetched.data), _capture_bound(context), "Returned connector capture")
        metadata = ConnectorMetadataSpec.model_validate(source["metadata"])
        inputs.append(
            (
                fetched.data,
                SourceMetadata(
                    connector_id=metadata.fully_qualified_id,
                    metadata=metadata,
                    fetched_at=fetched.fetched_at,
                    row_count=len(fetched.data),
                    last_updated=fetched.source_updated_at,
                ),
            )
        )
        observations.append(
            {
                "position": position,
                "connector_id": metadata.fully_qualified_id,
                "dataset_id": source["dataset_id"],
                "request_key": request.request_key,
                "observed_at": datetime.now(UTC),
                "row_count": len(fetched.data),
                "schema_id": fetched.schema_id,
                "schema_version": fetched.schema_version,
                "quality": FetchQualityEnvelope(
                    completeness=fetched.completeness,
                    quality_tier=fetched.quality_tier,
                    quality_flags=fetched.quality_flags,
                ),
                "transfer": FetchTransferEnvelope(
                    fetch_duration_ms=fetched.fetch_duration_ms,
                    bytes_transferred=fetched.bytes_transferred,
                    not_modified=fetched.not_modified,
                    resilience=fetched.resilience,
                    pii_scan=fetched.pii_scan,
                ),
                "provenance": FetchProvenanceEnvelope(
                    version=fetched.version,
                    fetched_at=fetched.fetched_at,
                    source_updated_at=fetched.source_updated_at,
                    evidence_ref=fetched.evidence_ref,
                ),
                "pagination_reported": bool(
                    fetched.has_more or fetched.next_page_token is not None
                ),
            }
        )
    composer = DataComposer(
        ConflictResolver(
            federation.composition.conflict_policy,
            tie_breaker_seed=federation.composition.tie_breaker_seed,
        )
    )
    ref = persist_federation_derivation(root, composer, inputs, federation.composition)
    manifest = _read_selected_json(root / "manifest.json", ref.manifest_sha256)
    observed = tuple(
        FederationFetchObservation(
            selected_source_sha256=manifest["sources"][row["position"]]["sha256"], **row
        )
        for row in observations
    )
    verified = _admit_selected_capture(root, ref, context, observed)
    serialized_observations = [row.model_dump(mode="json") for row in observed]
    try:
        restored_observations = tuple(
            FederationFetchObservation.model_validate_json(json.dumps(row))
            for row in serialized_observations
        )
        if any(
            _fingerprint(before.model_dump(mode="python"))
            != _fingerprint(after.model_dump(mode="python"))
            for before, after in zip(observed, restored_observations, strict=True)
        ):
            raise ValueError("reported observation serialization changed its typed meaning")
    except (ValueError, TypeError, FederationError) as exc:
        raise FederationError(
            "Reported observations are outside the exact acquisition profile"
        ) from exc
    receipt = {
        "format": _FORMAT,
        "context": context,
        "kernel_ref": ref.manifest_sha256,
        "fetches": serialized_observations,
        "observed_at": datetime.now(UTC).isoformat(),
        "elapsed_ms": (perf_counter() - started) * 1000,
    }
    receipt_bytes = bounded_encode(receipt)
    write_bytes_atomic(root / "acquisition.json", receipt_bytes)
    return _result(
        verified,
        root,
        ref,
        _sha(receipt_bytes),
        context,
        observed,
        datetime.fromisoformat(receipt["observed_at"]),
        receipt["elapsed_ms"],
    )


def reopen_federated_fetch_result(
    result: FetchResult[Any],
    *,
    expected_context: str,
    expected_root: Path,
) -> FederatedFetchResult:
    """Use independent pre-callback intent/root, not returned locator/observations."""
    started = perf_counter()
    if not isinstance(result, FederatedFetchResult):
        raise FederationError("Opt-in acquisition did not return a selected typed receipt")
    context = json.loads(expected_context)
    root = expected_root.resolve()
    if str(root) != context["output_root"]:
        raise FederationError("Independent output root differs from the frozen request")
    # Only the receipt selector comes from the callback. Root and all expected
    # source/request/parent selections were frozen independently beforehand.
    receipt = _read_selected_json(
        root / "acquisition.json", result.federation_audit.acquisition_sha256
    )
    if (
        set(receipt) != {"format", "context", "kernel_ref", "fetches", "observed_at", "elapsed_ms"}
        or receipt.get("format") != _FORMAT
        or _fingerprint(receipt.get("context")) != _fingerprint(context)
    ):
        raise FederationError("Acquisition differs from the independent consumer request")
    ref = FederationArtifactRef(receipt["kernel_ref"])
    observed = tuple(
        FederationFetchObservation.model_validate_json(json.dumps(row))
        for row in receipt["fetches"]
    )
    verified = _admit_selected_capture(root, ref, context, observed)
    # Base fetched_at/version time and duration describe this actual software
    # acquisition/readback. Earlier capture times remain consumer assertions.
    return _result(
        verified,
        root,
        ref,
        result.federation_audit.acquisition_sha256,
        context,
        observed,
        datetime.now(UTC),
        (perf_counter() - started) * 1000,
    )


def _fingerprint(value: Any) -> object:  # noqa: ANN401
    if isinstance(value, dict):
        return (
            "mapping",
            tuple(sorted((key, _fingerprint(member)) for key, member in value.items())),
        )
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_fingerprint(member) for member in value), key=repr)))
    if isinstance(value, (list, tuple)):
        return ("sequence", tuple(_fingerprint(member) for member in value))
    return encode_scalar(value)


def prepare_federation_core_payload(value: object, *, frame: pd.DataFrame | None = None) -> object:
    """Preflight actual CAN.2 decoding against full source semantics, not bytes.

    Kernel-declared null equivalence permits null->None. Other scalar/name/type
    collisions are unsupported before Core publication; no column blacklist or
    automatic CAN.3 dependency is introduced.
    """
    if frame is not None:
        projection = frame_projection(frame)  # Complete bounded admission first.
        records = []
        for values in frame.itertuples(False, None):
            row = {}
            for column, member in zip(frame.columns, values, strict=True):
                if encode_scalar(member) == {"t": "null"}:
                    member = None
                elif isinstance(member, np.generic):
                    member = member.item()
                row[column] = member
            records.append(row)
        value = records
    else:
        projection = None
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
    try:
        raw = to_bounded_canonical_bytes(value, _CORE_SPEC, _CORE_LIMITS)
        decoded = from_canonical_bytes(raw)
        verify_federation_core_payload(decoded, value, frame=frame, projection=projection)
    except (FederationError, ValueError, TypeError, OverflowError, KeyError) as exc:
        raise FederationSnapshotProjectionError(
            "Snapshot projection is unsupported by the exact CAN.2 row profile"
        ) from exc
    return value


def verify_federation_core_payload(
    actual: object,
    expected: object,
    *,
    frame: pd.DataFrame | None = None,
    projection: dict[str, Any] | None = None,
) -> None:
    """Compare every actual decoded row/scalar/schema; a hash is not the oracle."""
    if frame is None:
        if _fingerprint(actual) != _fingerprint(expected):
            raise FederationError("Core snapshot projection changed source semantics")
        return
    projection = projection if projection is not None else frame_projection(frame)
    if not isinstance(actual, list) or len(actual) != len(projection["rows"]):
        raise FederationError("Core snapshot row relation changed")
    columns = projection["columns"]
    for row, cells in zip(actual, projection["rows"], strict=True):
        if not isinstance(row, dict) or set(row) != set(columns):
            raise FederationError("Core snapshot column relation changed")
        if [encode_scalar(row[column]) for column in columns] != cells:
            raise FederationError("Core snapshot scalar relation changed")
