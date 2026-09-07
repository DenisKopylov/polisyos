"""Produce a tenant-scoped global inventory of persisted S2 case candidates.

The denominator is the canonical PDC binding vocabulary in the visible CAS,
not arbitrary objects containing a case_id. Inventory establishes neither
terminal-run completion nor policy authority. The authority slot stays empty.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts, canon
from polisyos.core.security import (
    TenantIsolationError,
    get_current_cell_id,
    get_current_tenant_id,
)
from polisyos.pdc import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    DesignRecordV0,
    RunBoundDesignRecordBinding,
    SearchLedger,
)

GLOBAL_CASE_INDEX_PRODUCER_REF = "runtime-quality:global-case-index-producer"
GLOBAL_CASE_INDEX_KIND = "runtime.global_case_index"
GLOBAL_CASE_INDEX_SCHEMA_VERSION = "policyos.global_case_index.v1"
_BINDING_KIND = "policyos.pdc.run_bound_design_record_binding"
_BINDING_VERSION = "policyos.pdc.run_bound_design_record_binding.v1"
_PDC_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.pdc.layer2_design_search",
    version="policyos.layer2.s2.design_search.v1",
)


class GlobalCaseIndexError(ValueError):
    """Refuse an unscoped, corrupt, or inconsistent canonical case inventory."""


class GlobalCaseIndexEntry(BaseModel):
    """Content-bound case identity and vocabulary emitted by the PDC producer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding_ref: str
    case_id: str
    run_id: str
    tenant_id: str
    cell_id: str | None
    design_record_ref: str
    search_ledger_ref: str
    candidate_ref: str
    instrument_families: tuple[str, ...]


class GlobalCaseIndexSnapshot(BaseModel):
    """Immutable inventory of all visible bindings at one enumeration instant."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.global_case_index.v1"] = GLOBAL_CASE_INDEX_SCHEMA_VERSION
    producer_ref: Literal["runtime-quality:global-case-index-producer"] = (
        GLOBAL_CASE_INDEX_PRODUCER_REF
    )
    authority_owner_ref: None = None
    tenant_id: str
    cell_id: str | None
    observed_at: datetime
    scanned_artifact_count: int
    source_artifact_refs: tuple[str, ...]
    entries: tuple[GlobalCaseIndexEntry, ...]
    limitation_codes: tuple[Literal["s2_bindings_only"], Literal["terminality_not_established"]] = (
        "s2_bindings_only",
        "terminality_not_established",
    )


class GlobalCaseIndexProducer:
    """Recompute the canonical case index through native CAS ownership enforcement."""

    def __init__(self, store: artifacts.ArtifactStore) -> None:
        self._store = store

    def produce(self) -> tuple[artifacts.ArtifactRef, GlobalCaseIndexSnapshot]:
        """Verify the complete visible binding set and persist its candidate snapshot."""
        try:
            tenant_id = get_current_tenant_id()
            cell_id = get_current_cell_id()
            scope_store = getattr(self._store, "for_tenant", None)
            if not callable(scope_store):
                raise GlobalCaseIndexError("case_index_scoped_backend_unavailable")
            store = scope_store(tenant_id, cell_id=cell_id)
            if not isinstance(store, artifacts.FileSystemCAS):
                raise GlobalCaseIndexError("case_index_scoped_backend_unavailable")
            observed_at = datetime.now(UTC)
            ids = sorted(store.iter_artifact_ids(), key=str)
            bindings = tuple(
                artifact_id
                for artifact_id in ids
                if store.get_manifest(artifact_id).kind == _BINDING_KIND
            )
            entries = tuple(
                _resolve_entry(store, artifact_id, tenant_id=tenant_id, cell_id=cell_id)
                for artifact_id in bindings
            )
            snapshot = GlobalCaseIndexSnapshot(
                tenant_id=tenant_id,
                cell_id=cell_id,
                observed_at=observed_at,
                scanned_artifact_count=len(ids),
                source_artifact_refs=tuple(map(str, bindings)),
                entries=entries,
            )
            ref = store.put_json(
                snapshot.model_dump(mode="json"),
                artifacts.PutOptions(
                    kind=GLOBAL_CASE_INDEX_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name=GLOBAL_CASE_INDEX_KIND, version=GLOBAL_CASE_INDEX_SCHEMA_VERSION
                    ),
                    producer=artifacts.ProducerInfo(
                        component=GLOBAL_CASE_INDEX_PRODUCER_REF,
                        version=GLOBAL_CASE_INDEX_SCHEMA_VERSION,
                    ),
                    inputs=[
                        artifacts.InputRef(artifact_id=artifact_id, role="case_binding")
                        for artifact_id in bindings
                    ],
                ),
            )
            payload = store.get_bytes(ref.artifact_id)
            if not store.verify(ref.artifact_id).ok or canon.content_hash(
                payload, prefix=True
            ) != str(ref.artifact_id):
                raise GlobalCaseIndexError("case_index_snapshot_integrity_failed")
            reloaded = GlobalCaseIndexSnapshot.model_validate_json(payload)
            if reloaded != snapshot:
                raise GlobalCaseIndexError("case_index_snapshot_readback_mismatch")
            return ref, reloaded
        except GlobalCaseIndexError:
            raise
        except (
            OSError, KeyError, RuntimeError, TypeError, ValueError, TenantIsolationError
        ) as exc:
            raise GlobalCaseIndexError("case_index_source_invalid_or_scope_missing") from exc


def _verified_payload(
    store: artifacts.ArtifactStore,
    artifact_id: artifacts.ArtifactID,
    *,
    kind: str,
    version: str,
) -> object:
    """Resolve bytes, exact schema and producer provenance at one intake."""
    manifest = store.get_manifest(artifact_id)
    if (
        manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema != artifacts.SchemaInfo(name=kind, version=version)
        or manifest.producer != _PDC_PRODUCER
        or not store.verify(artifact_id).ok
    ):
        raise GlobalCaseIndexError("case_index_source_contract_mismatch")
    payload = store.get_bytes(artifact_id)
    if canon.content_hash(payload, prefix=True) != str(artifact_id):
        raise GlobalCaseIndexError("case_index_source_content_mismatch")
    return canon.from_canonical_bytes(payload)


def _resolve_entry(
    store: artifacts.ArtifactStore,
    artifact_id: artifacts.ArtifactID,
    *,
    tenant_id: str,
    cell_id: str | None,
) -> GlobalCaseIndexEntry:
    binding = RunBoundDesignRecordBinding.model_validate(
        _verified_payload(store, artifact_id, kind=_BINDING_KIND, version=_BINDING_VERSION)
    )
    if (
        binding.tenant_id != tenant_id
        or binding.cell_id != cell_id
        or binding.producer != _PDC_PRODUCER
    ):
        raise GlobalCaseIndexError("case_index_binding_owner_mismatch")
    record = DesignRecordV0.model_validate(
        _verified_payload(
            store,
            binding.design_record_ref.artifact_id,
            kind=binding.design_record_schema_name,
            version=binding.design_record_schema_version,
        )
    )
    ledger = SearchLedger.model_validate(
        _verified_payload(
            store,
            binding.search_ledger_ref.artifact_id,
            kind="policyos.layer2_s2.search_ledger",
            version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
        )
    )
    if (
        record.record_id != binding.design_record_record_id
        or record.schema_version != binding.design_record_schema_version
        or ledger.case_id != binding.case_id
        or ledger.ledger_id != binding.search_ledger_id
        or record.candidate_ref not in ledger.candidate_refs
        or not ledger.instrument_family_coverage
        or any(not family.strip() for family in ledger.instrument_family_coverage)
    ):
        raise GlobalCaseIndexError("case_index_binding_content_mismatch")
    return GlobalCaseIndexEntry(
        binding_ref=str(artifact_id),
        case_id=binding.case_id,
        run_id=binding.run_id,
        tenant_id=binding.tenant_id,
        cell_id=binding.cell_id,
        design_record_ref=str(binding.design_record_ref.artifact_id),
        search_ledger_ref=str(binding.search_ledger_ref.artifact_id),
        candidate_ref=record.candidate_ref,
        instrument_families=tuple(ledger.instrument_family_coverage),
    )
