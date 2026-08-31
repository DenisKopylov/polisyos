"""Registry-backed capability discovery federation.

The federation composes owner-returned search ledgers without inventing search
matches, independently reconciles execution, and keeps authority fail closed
until the separately signed capability-purpose binding producer exists.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    CapabilityDiscoveryItem,
    CapabilityDiscoveryPostureResult,
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
    CapabilityResourceKind,
    CapabilityTimeSemantics,
    SearchCandidate,
    SearchCompletenessStatus,
    SearchFrontier,
    SearchLedger,
)
from polisyos.runtime.quality.capability_index import (
    CapabilityIndex,
    CapabilityIndexDiscoveryRow,
    LegalNormOwnerTruth,
    ScientistCapabilityOwnerTruth,
)
from polisyos.runtime.quality.capability_index_compiler import build_capability_discovery_snapshot

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from polisyos.core import contracts as core_contracts
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.quality.capability_authority import (
        CapabilityAuthorityContext,
        CapabilityDiscoveryAuthorityResolver,
    )
    from polisyos.runtime.quality.capability_resolver import CapabilityExecutionResolver

CAPABILITY_DISCOVERY_RULE_VERSION = "policyos.ds10.discovery.v1"
CAPABILITY_PROVIDER_REGISTRY_INDEX_REF = "runtime-quality:capability-provider-registry"
LEX_CAPABILITY_DISCOVERY_PROVIDER_REF = "runtime-quality:lex-capability-discovery-provider"
SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF = (
    "runtime-quality:scientist-registry-capability-discovery-provider"
)
LEX_LEGAL_NORM_ADMISSION_VERIFIER_REF = (
    "runtime-quality:capability-index-compiler:legal-norm-owner-truth"
)

_COMPLETENESS_PRIORITY: dict[SearchCompletenessStatus, int] = {
    "producer_missing": 0,
    "producer_unavailable": 1,
    "index_stale": 2,
    "budget_cutoff": 3,
    "recall_unmeasured": 4,
    "complete_no_match": 5,
    "complete": 6,
}


class CapabilityProviderUnavailableError(RuntimeError):
    """Signal that an installed owner could not complete its registry search."""

    def __init__(self, reason_code: str) -> None:
        if not reason_code:
            raise ValueError("provider unavailability requires a reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


class _CapabilityOwnerReceipt(BaseModel):
    """Content-bound owner search receipt shared by finite provider kinds."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    owner_producer_ref: str = Field(min_length=1)
    search_snapshot_ref: str = Field(min_length=1)
    search_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    result_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provenance_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _owner_and_snapshot_are_in_provenance(self) -> _CapabilityOwnerReceipt:
        required = {self.owner_producer_ref, self.search_snapshot_ref}
        if not required <= set(self.provenance_refs):
            raise ValueError("owner receipt provenance must include producer and search snapshot")
        return self


class CapabilityIndexOwnerReceipt(_CapabilityOwnerReceipt):
    """CapabilityIndex receipt for method or L1 dataset discovery."""

    schema_version: Literal["policyos.capability_index_owner_receipt.v1"] = (
        "policyos.capability_index_owner_receipt.v1"
    )
    owner_type: Literal["capability_index"] = "capability_index"
    resource_kind: Literal["method", "dataset"]
    index_release_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _index_release_is_in_provenance(self) -> CapabilityIndexOwnerReceipt:
        if self.index_release_ref not in self.provenance_refs:
            raise ValueError("CapabilityIndex release must be carried in provenance")
        return self


class SourceProfileOwnerReceipt(_CapabilityOwnerReceipt):
    """SourceProfileRegistry plus connector-registry snapshot receipt."""

    schema_version: Literal["policyos.source_profile_owner_receipt.v1"] = (
        "policyos.source_profile_owner_receipt.v1"
    )
    owner_type: Literal["source_profile_registry"] = "source_profile_registry"
    resource_kind: Literal["source"] = "source"
    profile_registry_snapshot_ref: str = Field(min_length=1)
    profile_registry_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    connector_snapshot_ref: str = Field(min_length=1)
    connector_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _source_snapshots_bind_search_snapshot(self) -> SourceProfileOwnerReceipt:
        required = {self.profile_registry_snapshot_ref, self.connector_snapshot_ref}
        if not required <= set(self.provenance_refs):
            raise ValueError("source owner snapshots must be carried in provenance")
        expected = "sha256:" + _digest(
            {
                "profile_registry_snapshot_ref": self.profile_registry_snapshot_ref,
                "profile_registry_snapshot_digest": self.profile_registry_snapshot_digest,
                "connector_snapshot_ref": self.connector_snapshot_ref,
                "connector_snapshot_digest": self.connector_snapshot_digest,
            }
        )
        if self.search_snapshot_digest != expected:
            raise ValueError("source search snapshot must bind profile and connector snapshots")
        return self


class LexOwnerReceipt(_CapabilityOwnerReceipt):
    """Rich Lex owner snapshot and verifier receipt."""

    schema_version: Literal["policyos.lex_owner_receipt.v1"] = "policyos.lex_owner_receipt.v1"
    owner_type: Literal["lex_knowledge_graph"] = "lex_knowledge_graph"
    resource_kind: Literal["legal_norm"] = "legal_norm"
    lex_snapshot_ref: str = Field(min_length=1)
    lex_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _lex_snapshot_and_verifier_are_bound(self) -> LexOwnerReceipt:
        if (
            self.lex_snapshot_ref != self.search_snapshot_ref
            or self.lex_snapshot_digest != self.search_snapshot_digest
        ):
            raise ValueError("Lex receipt must bind the searched snapshot")
        if not {self.lex_snapshot_ref, self.verifier_ref} <= set(self.provenance_refs):
            raise ValueError("Lex snapshot and verifier must be carried in provenance")
        return self


class ScientistRegistryOwnerReceipt(_CapabilityOwnerReceipt):
    """Scientist NodeRegistry and ToolRegistry owner receipt."""

    schema_version: Literal["policyos.scientist_registry_owner_receipt.v1"] = (
        "policyos.scientist_registry_owner_receipt.v1"
    )
    owner_type: Literal["scientist_node_tool_registries"] = "scientist_node_tool_registries"
    resource_kind: Literal["agent"] = "agent"
    node_registry_snapshot_ref: str = Field(min_length=1)
    node_registry_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tool_registry_snapshot_ref: str = Field(min_length=1)
    tool_registry_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _scientist_snapshots_bind_search_snapshot(self) -> ScientistRegistryOwnerReceipt:
        required = {self.node_registry_snapshot_ref, self.tool_registry_snapshot_ref}
        if not required <= set(self.provenance_refs):
            raise ValueError("Scientist registry snapshots must be carried in provenance")
        expected = "sha256:" + _digest(
            {
                "node_registry_snapshot_ref": self.node_registry_snapshot_ref,
                "node_registry_snapshot_digest": self.node_registry_snapshot_digest,
                "tool_registry_snapshot_ref": self.tool_registry_snapshot_ref,
                "tool_registry_snapshot_digest": self.tool_registry_snapshot_digest,
            }
        )
        if self.search_snapshot_digest != expected:
            raise ValueError("Scientist search snapshot must bind NodeRegistry and ToolRegistry")
        return self


class ScientistRegistryCapabilityRecord(BaseModel):
    """Strict handler-free projection of one public NodeSpec or ToolDefinition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability_ref: str = Field(min_length=1)
    registry_kind: Literal["node_registry", "tool_registry"]
    registry_entry_ref: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    construct_refs: tuple[str, ...] = Field(min_length=1)
    definition: dict[str, object]


class ScientistRegistrySnapshot(BaseModel):
    """Canonical finite projection persisted separately for each Scientist registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["scientist.node_registry.v1", "scientist.tool_registry.v1"]
    registry_kind: Literal["node_registry", "tool_registry"]
    producer_ref: Literal[
        "runtime-quality:scientist-registry-capability-discovery-provider"
    ] = SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF
    entries: tuple[ScientistRegistryCapabilityRecord, ...]

    @model_validator(mode="after")
    def _schema_and_entries_match_registry(self) -> ScientistRegistrySnapshot:
        expected = {
            "node_registry": "scientist.node_registry.v1",
            "tool_registry": "scientist.tool_registry.v1",
        }[self.registry_kind]
        if self.schema_version != expected:
            raise ValueError("Scientist registry snapshot schema does not match registry_kind")
        if any(entry.registry_kind != self.registry_kind for entry in self.entries):
            raise ValueError("Scientist registry snapshot entries do not match registry_kind")
        return self


@dataclass(frozen=True, slots=True)
class _ScientistDiscoverySnapshot:
    """Immutable cached join over the two separately persisted registry snapshots."""

    node_registry_snapshot_ref: str
    node_registry_snapshot_digest: str
    tool_registry_snapshot_ref: str
    tool_registry_snapshot_digest: str
    search_snapshot_ref: str
    search_snapshot_digest: str
    rows: tuple[CapabilityIndexDiscoveryRow, ...]
    incompleteness_reasons: tuple[str, ...]


type CapabilityOwnerReceipt = (
    CapabilityIndexOwnerReceipt
    | SourceProfileOwnerReceipt
    | LexOwnerReceipt
    | ScientistRegistryOwnerReceipt
)


class CapabilityProviderSearchResult(BaseModel):
    """Typed owner search rows plus the exact ledger that selected them."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_kind: CapabilityResourceKind
    producer_ref: str = Field(min_length=1)
    owner_receipt: CapabilityOwnerReceipt
    rows: tuple[CapabilityIndexDiscoveryRow, ...] = ()
    ledger: SearchLedger
    requested_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    actual_cutoff: int | None = Field(default=None, ge=0)
    completeness_status: SearchCompletenessStatus
    incompleteness_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def _rows_are_the_ordered_owner_selection(self) -> CapabilityProviderSearchResult:
        selected = tuple(candidate.candidate_ref for candidate in self.ledger.candidates)
        row_refs = tuple(row.capability_ref for row in self.rows)
        if selected != row_refs:
            raise ValueError("provider rows must preserve owner SearchLedger candidate order")
        if any(row.resource_kind != self.resource_kind for row in self.rows):
            raise ValueError("provider rows must match the provider resource kind")
        if any(row.producer_ref != self.producer_ref for row in self.rows):
            raise ValueError("provider row producer_ref must match the owner result")
        receipt_type = {
            "method": CapabilityIndexOwnerReceipt,
            "dataset": CapabilityIndexOwnerReceipt,
            "source": SourceProfileOwnerReceipt,
            "legal_norm": LexOwnerReceipt,
            "agent": ScientistRegistryOwnerReceipt,
        }.get(self.resource_kind)
        if receipt_type is None or type(self.owner_receipt) is not receipt_type:
            expected = receipt_type.__name__ if receipt_type is not None else "no owner receipt"
            raise ValueError(f"{self.resource_kind} results require {expected}")
        if self.owner_receipt.owner_producer_ref != self.producer_ref:
            raise ValueError("owner receipt must bind producer_ref")
        if self.owner_receipt.resource_kind != self.resource_kind:
            raise ValueError("owner receipt must bind resource_kind")
        if self.owner_receipt.search_snapshot_digest != self.ledger.corpus_snapshot_hash:
            raise ValueError("owner receipt must bind the searched corpus snapshot")
        if any(row.snapshot_ref != self.owner_receipt.search_snapshot_ref for row in self.rows):
            raise ValueError("owner receipt must bind every selected row snapshot")
        receipt_provenance = set(self.owner_receipt.provenance_refs)
        if any(not set(row.provenance_refs) <= receipt_provenance for row in self.rows):
            raise ValueError("selected row provenance must be covered by its owner receipt")
        if type(self.owner_receipt) is ScientistRegistryOwnerReceipt:
            for row in self.rows:
                truth = row.owner_truth
                if type(truth) is not ScientistCapabilityOwnerTruth:
                    raise ValueError("agent rows require ScientistCapabilityOwnerTruth")
                if not set(truth.provenance_refs) <= receipt_provenance:
                    raise ValueError("Scientist entry provenance must be covered by owner receipt")
                expected_snapshot = {
                    "node_registry": (
                        self.owner_receipt.node_registry_snapshot_ref,
                        self.owner_receipt.node_registry_snapshot_digest,
                    ),
                    "tool_registry": (
                        self.owner_receipt.tool_registry_snapshot_ref,
                        self.owner_receipt.tool_registry_snapshot_digest,
                    ),
                }[truth.registry_kind]
                if (
                    truth.registry_snapshot_ref,
                    truth.registry_snapshot_digest,
                ) != expected_snapshot:
                    raise ValueError("Scientist entry must bind its typed registry snapshot")
        if self.evaluated_count < len(self.ledger.candidates) + len(
            self.ledger.rejected_candidates
        ):
            raise ValueError("evaluated_count must cover selected and rejected owner rows")
        complete = self.completeness_status in {"complete", "complete_no_match"}
        if complete and self.incompleteness_reasons:
            raise ValueError("complete provider results cannot carry incompleteness reasons")
        if not complete and not self.incompleteness_reasons:
            raise ValueError("incomplete provider results require typed reasons")
        expected_digest = "sha256:" + _digest(
            self.model_dump(mode="json", exclude={"owner_receipt"})
        )
        if self.owner_receipt.result_digest != expected_digest:
            raise ValueError("owner receipt result_digest does not bind provider result content")
        return self


class CapabilityDiscoveryProvider(Protocol):
    """Injected owner boundary for one finite capability resource kind."""

    @property
    def resource_kind(self) -> CapabilityResourceKind:
        """Return the one kind this provider owns."""
        ...

    def search(
        self,
        request: CapabilityDiscoveryRequest,
    ) -> CapabilityProviderSearchResult:
        """Return owner-selected rows and the real owner ledger."""
        ...


class ScientistRegistryCapabilityDiscoveryProvider:
    """Lazily persist and search public Scientist NodeRegistry/ToolRegistry projections.

    Registry factories are never invoked during provider construction or store
    binding. The first agent query emits two separate immutable CAS artifacts,
    joins them into typed owner rows, and caches that snapshot for every later
    request. Custom, dynamic, and ordinary bootstrap registries all preserve
    unmeasured recall because request-scoped Scientist tools remain outside it.
    """

    def __init__(
        self,
        *,
        node_registry_factory: Callable[[], object],
        tool_registry_factory: Callable[[], object],
        recall_measured: bool = False,
        observed_at: Callable[[], datetime] | None = None,
    ) -> None:
        if not callable(node_registry_factory) or not callable(tool_registry_factory):
            raise TypeError("Scientist registry factories must be callable")
        self._node_registry_factory = node_registry_factory
        self._tool_registry_factory = tool_registry_factory
        self._recall_measured = recall_measured
        self._observed_at = observed_at or (lambda: datetime.now(UTC))
        self._artifact_store: ArtifactStore | None = None
        self._snapshot: _ScientistDiscoverySnapshot | None = None
        self._snapshot_lock = threading.Lock()

    @property
    def resource_kind(self) -> Literal["agent"]:
        """Return the single candidate-grade kind backed by Scientist registries."""
        return "agent"

    def bind_artifact_store(self, store: ArtifactStore) -> None:
        """Bind the runtime-owned store exactly once without executing discovery."""
        required = ("put_json", "get_bytes", "get_manifest", "has")
        if any(not callable(getattr(store, method, None)) for method in required):
            raise TypeError("Scientist discovery requires an ArtifactStore")
        if self._artifact_store is not None and self._artifact_store is not store:
            raise RuntimeError("Scientist discovery artifact store is already bound")
        self._artifact_store = store

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        """Return a content-bound owner ledger over the cached registry snapshot."""
        snapshot = self._resolve_snapshot()
        terms = _scientist_search_terms(request)
        matches = (
            list(snapshot.rows)
            if not terms
            else [row for row in snapshot.rows if _row_match_count(row, terms)]
        )
        limit = _owner_search_limit(request, fallback=len(matches))
        selected_rows = tuple(
            sorted(
                matches,
                key=lambda row: (-_row_match_count(row, terms), row.capability_ref),
            )[:limit]
        )
        selected_refs = {row.capability_ref for row in selected_rows}
        matching_refs = {row.capability_ref for row in matches}
        selected = tuple(_scientist_search_candidate(row, terms) for row in selected_rows)
        rejected = tuple(
            _scientist_search_candidate(
                row,
                terms,
                limitation=(
                    "scientist_registry_budget_cutoff"
                    if row.capability_ref in matching_refs
                    else "scientist_registry_query_mismatch"
                ),
            )
            for row in snapshot.rows
            if row.capability_ref not in selected_refs
        )
        budget_cutoff = len(matches) > limit
        completeness_status, incompleteness_reasons = _scientist_completeness(
            has_selected=bool(selected_rows),
            recall_measured=self._recall_measured,
            snapshot_reasons=snapshot.incompleteness_reasons,
            budget_cutoff=budget_cutoff,
        )
        ledger = SearchLedger(
            request_ref=request.search.request_id,
            query_plan={
                "match": "all_terms_over_scientist_registry_projection",
                "resource_kind": self.resource_kind,
                "handler_projection": "forbidden",
            },
            corpus_ref=snapshot.search_snapshot_ref,
            corpus_path="runtime/quality/capability_discovery.py",
            corpus_snapshot_hash=snapshot.search_snapshot_digest,
            corpus_kind="canonical" if self._recall_measured else "bounded_surrogate",
            indexes_used=("scientist_node_registry", "scientist_tool_registry"),
            index_version_refs=(
                snapshot.node_registry_snapshot_ref,
                snapshot.tool_registry_snapshot_ref,
            ),
            index_freshness={
                "scientist_node_registry": {
                    "state": "current",
                    "snapshot_ref": snapshot.node_registry_snapshot_ref,
                },
                "scientist_tool_registry": {
                    "state": "current",
                    "snapshot_ref": snapshot.tool_registry_snapshot_ref,
                },
            },
            candidates=selected,
            rejected_candidates=rejected,
            no_hit_frontier=() if selected_rows else (self.resource_kind,),
            incompleteness={
                "status": completeness_status,
                "reason_codes": list(incompleteness_reasons),
            },
            replay_key=(
                "scientist-registry-capability-discovery:"
                + snapshot.search_snapshot_digest.removeprefix("sha256:")
            ),
            replay_command="capability-discovery:scientist-registry-snapshot",
            replay_expected_output_hash=snapshot.search_snapshot_digest,
        )
        payload = {
            "resource_kind": self.resource_kind,
            "producer_ref": SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF,
            "rows": selected_rows,
            "ledger": ledger,
            "requested_count": limit,
            "evaluated_count": len(snapshot.rows),
            "actual_cutoff": limit if budget_cutoff else None,
            "completeness_status": completeness_status,
            "incompleteness_reasons": incompleteness_reasons,
        }
        result_digest = "sha256:" + _digest(
            {
                **payload,
                "rows": [row.model_dump(mode="json") for row in selected_rows],
                "ledger": ledger.model_dump(mode="json"),
            }
        )
        provenance_refs = tuple(
            dict.fromkeys(
                (
                    SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF,
                    snapshot.search_snapshot_ref,
                    snapshot.node_registry_snapshot_ref,
                    snapshot.tool_registry_snapshot_ref,
                    *(ref for row in snapshot.rows for ref in row.provenance_refs),
                )
            )
        )
        receipt = ScientistRegistryOwnerReceipt(
            owner_producer_ref=SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF,
            search_snapshot_ref=snapshot.search_snapshot_ref,
            search_snapshot_digest=snapshot.search_snapshot_digest,
            result_digest=result_digest,
            provenance_refs=provenance_refs,
            node_registry_snapshot_ref=snapshot.node_registry_snapshot_ref,
            node_registry_snapshot_digest=snapshot.node_registry_snapshot_digest,
            tool_registry_snapshot_ref=snapshot.tool_registry_snapshot_ref,
            tool_registry_snapshot_digest=snapshot.tool_registry_snapshot_digest,
        )
        result = CapabilityProviderSearchResult(**payload, owner_receipt=receipt)
        store = self._artifact_store
        if store is None:  # pragma: no cover - guarded by _resolve_snapshot
            raise CapabilityProviderUnavailableError("scientist_artifact_store_unbound")
        try:
            store.put_json(
                receipt.model_dump(mode="json"),
                artifacts.PutOptions(
                    kind="scientist.registry_owner_receipt",
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name="polisyos.runtime.quality.ScientistRegistryOwnerReceipt",
                        version=receipt.schema_version,
                    ),
                ),
            )
        except (OSError, TypeError, ValueError) as exc:
            raise CapabilityProviderUnavailableError(
                "scientist_owner_receipt_persistence_failed"
            ) from exc
        return result

    def _resolve_snapshot(self) -> _ScientistDiscoverySnapshot:
        cached = self._snapshot
        if cached is not None:
            return cached
        with self._snapshot_lock:
            cached = self._snapshot
            if cached is not None:
                return cached
            store = self._artifact_store
            if store is None:
                raise CapabilityProviderUnavailableError("scientist_artifact_store_unbound")
            try:
                cached = _build_scientist_discovery_snapshot(
                    store,
                    node_registry_source=self._node_registry_factory(),
                    tool_registry_source=self._tool_registry_factory(),
                    observed_at=self._observed_at(),
                )
            except CapabilityProviderUnavailableError:
                raise
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                raise CapabilityProviderUnavailableError(
                    "scientist_registry_snapshot_invalid"
                ) from exc
            self._snapshot = cached
            return cached


class LexCapabilityDiscoveryProvider:
    """Search admitted legal-norm rows from the existing CapabilityIndex projection.

    The provider does not create Lex capabilities.  It consumes the compiler's
    owner-admitted L3 rows, retaining their grounded and temporally resolved
    truth, then records an owner receipt over the exact queried snapshot.
    """

    def __init__(self, *, capability_index: CapabilityIndex) -> None:
        self._capability_index = capability_index

    @property
    def resource_kind(self) -> Literal["legal_norm"]:
        """Return the single owner kind served by this provider."""
        return "legal_norm"

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        """Return a content-bound Lex ledger for the requested legal-norm query."""
        rows = self._owner_rows()
        snapshot_ref = _lex_snapshot_ref(rows)
        snapshot_digest = "sha256:" + _digest(
            {
                "snapshot_ref": snapshot_ref,
                "legal_norm_rows": [row.model_dump(mode="json") for row in rows],
            }
        )
        terms = _owner_search_terms(request)
        matches = list(rows) if not terms else [row for row in rows if _row_match_count(row, terms)]
        limit = _owner_search_limit(request, fallback=len(matches))
        selected_rows = tuple(
            sorted(
                matches,
                key=lambda row: (-_row_match_count(row, terms), row.capability_ref),
            )[:limit]
        )
        selected_refs = {row.capability_ref for row in selected_rows}
        matching_refs = {row.capability_ref for row in matches}
        selected = tuple(_lex_search_candidate(row, terms) for row in selected_rows)
        rejected = tuple(
            _lex_search_candidate(
                row,
                terms,
                limitation="lex_owner_budget_cutoff"
                if row.capability_ref in matching_refs
                else "lex_owner_query_mismatch",
            )
            for row in rows
            if row.capability_ref not in selected_refs
        )
        budget_cutoff = len(matches) > limit
        stale = any(row.time.freshness == "stale" for row in rows)
        completeness_status, incompleteness_reasons = _lex_completeness(
            has_selected=bool(selected_rows),
            stale=stale,
            budget_cutoff=budget_cutoff,
        )
        ledger = SearchLedger(
            request_ref=request.search.request_id,
            query_plan={
                "match": "all_terms_over_capability_ref_construct_label_description",
                "resource_kind": self.resource_kind,
            },
            corpus_ref=self._capability_index.release_ref,
            corpus_path="runtime/quality/capability_index_compiler.py",
            corpus_snapshot_hash=snapshot_digest,
            corpus_kind="canonical",
            indexes_used=("lex_knowledge_graph",),
            index_version_refs=(snapshot_ref,),
            index_freshness={
                "lex_knowledge_graph": {
                    "state": "stale" if stale else "current",
                    "snapshot_ref": snapshot_ref,
                }
            },
            candidates=selected,
            rejected_candidates=rejected,
            no_hit_frontier=() if selected_rows else (self.resource_kind,),
            incompleteness={"status": completeness_status},
            replay_key="lex-capability-discovery:" + snapshot_digest.removeprefix("sha256:"),
            replay_command="capability-discovery:lex-owner-snapshot",
            replay_expected_output_hash=snapshot_digest,
        )
        payload = {
            "resource_kind": self.resource_kind,
            "producer_ref": self._capability_index.release_ref,
            "rows": selected_rows,
            "ledger": ledger,
            "requested_count": limit,
            "evaluated_count": len(rows),
            "actual_cutoff": limit if budget_cutoff else None,
            "completeness_status": completeness_status,
            "incompleteness_reasons": incompleteness_reasons,
        }
        result_digest = "sha256:" + _digest(
            {
                **payload,
                "rows": [row.model_dump(mode="json") for row in selected_rows],
                "ledger": ledger.model_dump(mode="json"),
            }
        )
        provenance_refs = tuple(
            dict.fromkeys(
                (
                    self._capability_index.release_ref,
                    LEX_CAPABILITY_DISCOVERY_PROVIDER_REF,
                    snapshot_ref,
                    LEX_LEGAL_NORM_ADMISSION_VERIFIER_REF,
                    *(ref for row in rows for ref in row.provenance_refs),
                )
            )
        )
        receipt = LexOwnerReceipt(
            owner_producer_ref=self._capability_index.release_ref,
            search_snapshot_ref=snapshot_ref,
            search_snapshot_digest=snapshot_digest,
            result_digest=result_digest,
            provenance_refs=provenance_refs,
            lex_snapshot_ref=snapshot_ref,
            lex_snapshot_digest=snapshot_digest,
            verifier_ref=LEX_LEGAL_NORM_ADMISSION_VERIFIER_REF,
        )
        return CapabilityProviderSearchResult(**payload, owner_receipt=receipt)

    def _owner_rows(self) -> tuple[CapabilityIndexDiscoveryRow, ...]:
        """Return only legal rows whose strict Lex owner truth survived projection."""
        if type(self._capability_index) is not CapabilityIndex:
            raise CapabilityProviderUnavailableError("lex_owner_index_invalid")
        try:
            rows = tuple(
                row
                for row in build_capability_discovery_snapshot(self._capability_index)
                if row.resource_kind == self.resource_kind
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise CapabilityProviderUnavailableError("lex_owner_index_invalid") from exc
        if any(type(row.owner_truth) is not LegalNormOwnerTruth for row in rows):
            raise CapabilityProviderUnavailableError("lex_owner_truth_invalid")
        return rows


def _lex_snapshot_ref(rows: tuple[CapabilityIndexDiscoveryRow, ...]) -> str:
    """Return the sole Lex snapshot reference represented by owner rows."""
    snapshot_refs = {row.snapshot_ref for row in rows}
    if len(snapshot_refs) == 1:
        return next(iter(snapshot_refs))
    if not snapshot_refs:
        return "lex:empty-owner-snapshot"
    raise CapabilityProviderUnavailableError("lex_owner_snapshot_ambiguous")


def _owner_search_terms(request: CapabilityDiscoveryRequest) -> tuple[str, ...]:
    """Normalize the request-owned query and construct terms without ID rules."""
    match_all = request.search.budget.get("match_all", False)
    if not isinstance(match_all, bool):
        raise CapabilityProviderUnavailableError("lex_owner_match_all_invalid")
    if match_all:
        return ()
    terms = re.findall(
        r"[\w]+",
        " ".join((request.search.query_text, *request.search.construct_refs)).casefold(),
    )
    normalized = tuple(dict.fromkeys(term for term in terms if term))
    if not normalized:
        raise CapabilityProviderUnavailableError("lex_owner_query_terms_missing")
    return normalized


def _owner_search_limit(request: CapabilityDiscoveryRequest, *, fallback: int) -> int:
    """Read the request budget while failing malformed owner queries closed."""
    raw_limit = request.search.budget.get("top_k", fallback)
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit < 0:
        raise CapabilityProviderUnavailableError("lex_owner_query_budget_invalid")
    return raw_limit


def _row_match_count(row: CapabilityIndexDiscoveryRow, terms: tuple[str, ...]) -> int:
    """Return the number of request terms present in one owner-projected row."""
    searchable = " ".join(
        (row.capability_ref, *row.construct_refs, row.label, row.description)
    ).casefold()
    return len(terms) if all(term in searchable for term in terms) else 0


def _lex_search_candidate(
    row: CapabilityIndexDiscoveryRow,
    terms: tuple[str, ...],
    *,
    limitation: str | None = None,
) -> SearchCandidate:
    """Project one retained Lex row into a scored owner ledger candidate."""
    match_count = _row_match_count(row, terms)
    query_text = " ".join(terms)
    searchable = " ".join(
        (row.capability_ref, *row.construct_refs, row.label, row.description)
    ).casefold()
    return SearchCandidate(
        candidate_ref=row.capability_ref,
        source_layer="L3",
        match_mode="exact" if query_text and query_text in searchable else "lexical",
        score=match_count / len(terms) if terms else 0.0,
        evidence_refs=row.provenance_refs,
        limitation_refs=(limitation,) if limitation is not None else (),
        authority_boundary={"authoritative_for": []},
        may_not_use_for=row.may_not_use_for,
    )


def _lex_completeness(
    *,
    has_selected: bool,
    stale: bool,
    budget_cutoff: bool,
) -> tuple[SearchCompletenessStatus, tuple[str, ...]]:
    """Preserve stale and bounded owner-index negatives in priority order."""
    if stale:
        reasons = ("lex_owner_snapshot_stale",)
        if budget_cutoff:
            reasons += ("lex_owner_budget_cutoff",)
        return "index_stale", reasons
    if budget_cutoff:
        return "budget_cutoff", ("lex_owner_budget_cutoff",)
    if not has_selected:
        return "complete_no_match", ()
    return "complete", ()


def _build_scientist_discovery_snapshot(
    store: ArtifactStore,
    *,
    node_registry_source: object,
    tool_registry_source: object,
    observed_at: datetime,
) -> _ScientistDiscoverySnapshot:
    """Project public registry contracts, persist them separately, and join owner rows."""
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry

    node_registry, node_reasons = _unpack_scientist_registry_source(node_registry_source)
    tool_registry, tool_reasons = _unpack_scientist_registry_source(tool_registry_source)
    if not isinstance(node_registry, NodeRegistry):
        raise CapabilityProviderUnavailableError("scientist_node_registry_invalid")
    if not isinstance(tool_registry, ToolRegistry):
        raise CapabilityProviderUnavailableError("scientist_tool_registry_invalid")
    if observed_at.tzinfo is None:
        raise CapabilityProviderUnavailableError("scientist_registry_observed_at_naive")
    entries_by_kind = {
        "node_registry": _scientist_node_records(node_registry),
        "tool_registry": _scientist_tool_records(tool_registry),
    }
    schema_by_kind = {
        "node_registry": "scientist.node_registry.v1",
        "tool_registry": "scientist.tool_registry.v1",
    }
    persisted: dict[str, tuple[str, str]] = {}
    for registry_kind in ("node_registry", "tool_registry"):
        schema_version = schema_by_kind[registry_kind]
        snapshot = ScientistRegistrySnapshot(
            schema_version=schema_version,
            registry_kind=registry_kind,
            entries=entries_by_kind[registry_kind],
        )
        ref = store.put_json(
            snapshot.model_dump(mode="json"),
            artifacts.PutOptions(
                kind=f"scientist.{registry_kind}_snapshot",
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name="polisyos.runtime.quality.ScientistRegistrySnapshot",
                    version=schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        persisted[registry_kind] = (str(ref.artifact_id), str(ref.artifact_id))
    node_snapshot_ref, node_snapshot_digest = persisted["node_registry"]
    tool_snapshot_ref, tool_snapshot_digest = persisted["tool_registry"]
    combined = {
        "node_registry_snapshot_ref": node_snapshot_ref,
        "node_registry_snapshot_digest": node_snapshot_digest,
        "tool_registry_snapshot_ref": tool_snapshot_ref,
        "tool_registry_snapshot_digest": tool_snapshot_digest,
    }
    search_snapshot_digest = "sha256:" + _digest(combined)
    search_snapshot_ref = (
        "scientist-registry-snapshot:"
        + search_snapshot_digest.removeprefix("sha256:")
    )
    time = CapabilityTimeSemantics(
        observed_at=observed_at,
        valid_from=observed_at,
        valid_until=None,
        freshness="current",
    )
    rows = tuple(
        _scientist_registry_row(
            entry,
            registry_snapshot_ref=persisted[entry.registry_kind][0],
            registry_snapshot_digest=persisted[entry.registry_kind][1],
            search_snapshot_ref=search_snapshot_ref,
            time=time,
        )
        for entry in sorted(
            (*entries_by_kind["node_registry"], *entries_by_kind["tool_registry"]),
            key=lambda item: item.capability_ref,
        )
    )
    return _ScientistDiscoverySnapshot(
        node_registry_snapshot_ref=node_snapshot_ref,
        node_registry_snapshot_digest=node_snapshot_digest,
        tool_registry_snapshot_ref=tool_snapshot_ref,
        tool_registry_snapshot_digest=tool_snapshot_digest,
        search_snapshot_ref=search_snapshot_ref,
        search_snapshot_digest=search_snapshot_digest,
        rows=rows,
        incompleteness_reasons=tuple(
            dict.fromkeys((*node_reasons, *tool_reasons))
        ),
    )


def _unpack_scientist_registry_source(source: object) -> tuple[object, tuple[str, ...]]:
    """Accept a registry or a registry plus typed discovery limitations."""
    if not isinstance(source, tuple):
        return source, ()
    if len(source) != 2:
        raise CapabilityProviderUnavailableError("scientist_registry_source_invalid")
    registry, raw_reasons = source
    if not isinstance(raw_reasons, (tuple, list)) or any(
        not isinstance(reason, str) or not reason for reason in raw_reasons
    ):
        raise CapabilityProviderUnavailableError("scientist_registry_source_invalid")
    return registry, tuple(raw_reasons)


def _scientist_node_records(registry: object) -> tuple[ScientistRegistryCapabilityRecord, ...]:
    """Canonical-sort public NodeSpec projections without retaining executable Nodes."""
    records = []
    for spec in registry.list():
        entry_ref = str(spec.metadata.component_id)
        records.append(
            ScientistRegistryCapabilityRecord(
                capability_ref=f"scientist-node:{entry_ref}",
                registry_kind="node_registry",
                registry_entry_ref=entry_ref,
                display_name=spec.metadata.display_name or entry_ref,
                description=spec.metadata.description or f"Scientist node {entry_ref}",
                construct_refs=_sorted_text(
                    (
                        f"scientist-node:{entry_ref}",
                        *spec.metadata.domains,
                        *spec.metadata.tags,
                        *spec.metadata.provides,
                        *spec.state_reads,
                        *spec.state_writes,
                        *spec.produces,
                    )
                ),
                definition=spec.model_dump(mode="json"),
            )
        )
    return tuple(sorted(records, key=lambda entry: entry.capability_ref))


def _scientist_tool_records(registry: object) -> tuple[ScientistRegistryCapabilityRecord, ...]:
    """Canonical-sort public ToolDefinitions without reading registry handlers."""
    records = []
    for definition in registry.list_definitions():
        parameters = definition.parameters.get("properties", {})
        records.append(
            ScientistRegistryCapabilityRecord(
                capability_ref=f"scientist-tool:{definition.name}",
                registry_kind="tool_registry",
                registry_entry_ref=definition.name,
                display_name=definition.name.replace("_", " "),
                description=definition.description or f"Scientist tool {definition.name}",
                construct_refs=_sorted_text(
                    (
                        f"scientist-tool:{definition.name}",
                        definition.domain,
                        *(parameters if isinstance(parameters, dict) else ()),
                    )
                ),
                definition=definition.model_dump(mode="json"),
            )
        )
    return tuple(sorted(records, key=lambda entry: entry.capability_ref))


def _scientist_registry_row(
    entry: ScientistRegistryCapabilityRecord,
    *,
    registry_snapshot_ref: str,
    registry_snapshot_digest: str,
    search_snapshot_ref: str,
    time: CapabilityTimeSemantics,
) -> CapabilityIndexDiscoveryRow:
    """Construct the shared typed row and owner truth for one registry entry."""
    truth_provenance = (
        SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF,
        registry_snapshot_ref,
    )
    owner_truth = ScientistCapabilityOwnerTruth(
        capability_ref=entry.capability_ref,
        registry_kind=entry.registry_kind,
        registry_schema_ref={
            "node_registry": "scientist.node_registry.v1",
            "tool_registry": "scientist.tool_registry.v1",
        }[entry.registry_kind],
        registry_entry_ref=entry.registry_entry_ref,
        registry_snapshot_ref=registry_snapshot_ref,
        registry_snapshot_digest=registry_snapshot_digest,
        provenance_refs=truth_provenance,
    )
    return CapabilityIndexDiscoveryRow(
        capability_ref=entry.capability_ref,
        content_digest="sha256:" + _digest(entry.model_dump(mode="json")),
        resource_kind="agent",
        construct_refs=entry.construct_refs,
        label=entry.display_name,
        description=entry.description,
        producer_ref=SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF,
        snapshot_ref=search_snapshot_ref,
        freshness_ref=f"{registry_snapshot_ref}#current",
        provenance_refs=(*truth_provenance, search_snapshot_ref),
        owner_truth=owner_truth,
        may_not_use_for=(
            "authority_without_signed_capability_purpose_binding",
            "execution_without_live_operation_registration",
            "world_entity_or_data_lookup",
        ),
        time=time,
    )


def _scientist_search_terms(request: CapabilityDiscoveryRequest) -> tuple[str, ...]:
    """Normalize a Scientist query while preserving a typed match-all control."""
    match_all = request.search.budget.get("match_all", False)
    if not isinstance(match_all, bool):
        raise CapabilityProviderUnavailableError("scientist_registry_match_all_invalid")
    if match_all:
        return ()
    terms = re.findall(
        r"[\w]+",
        " ".join((request.search.query_text, *request.search.construct_refs)).casefold(),
    )
    normalized = tuple(dict.fromkeys(term for term in terms if term))
    if not normalized:
        raise CapabilityProviderUnavailableError("scientist_registry_query_terms_missing")
    return normalized


def _scientist_search_candidate(
    row: CapabilityIndexDiscoveryRow,
    terms: tuple[str, ...],
    *,
    limitation: str | None = None,
) -> SearchCandidate:
    """Project one registry row into a scored, candidate-only ledger entry."""
    match_count = _row_match_count(row, terms)
    query_text = " ".join(terms)
    searchable = " ".join(
        (row.capability_ref, *row.construct_refs, row.label, row.description)
    ).casefold()
    return SearchCandidate(
        candidate_ref=row.capability_ref,
        source_layer="Scientist",
        match_mode="exact" if query_text and query_text in searchable else "lexical",
        score=match_count / len(terms) if terms else 1.0,
        evidence_refs=row.provenance_refs,
        limitation_refs=(limitation,) if limitation is not None else (),
        authority_boundary={"authoritative_for": []},
        may_not_use_for=row.may_not_use_for,
    )


def _scientist_completeness(
    *,
    has_selected: bool,
    recall_measured: bool,
    snapshot_reasons: tuple[str, ...],
    budget_cutoff: bool,
) -> tuple[SearchCompletenessStatus, tuple[str, ...]]:
    """Keep non-default/dynamic registry recall explicitly unmeasured."""
    reasons = list(snapshot_reasons)
    if not recall_measured:
        reasons.append("scientist_registry_recall_unmeasured")
    if reasons:
        if budget_cutoff:
            reasons.append("scientist_registry_budget_cutoff")
        return "recall_unmeasured", tuple(dict.fromkeys(reasons))
    if budget_cutoff:
        return "budget_cutoff", ("scientist_registry_budget_cutoff",)
    if not has_selected:
        return "complete_no_match", ()
    return "complete", ()


def _sorted_text(values: Sequence[object]) -> tuple[str, ...]:
    """Return a canonical non-empty-aware text projection without inventing meaning."""
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class CapabilityDiscoveryComposer:
    """Compose provider ledgers and independent posture resolvers into one packet."""

    def __init__(
        self,
        *,
        providers: Sequence[CapabilityDiscoveryProvider],
        execution_resolver: CapabilityExecutionResolver,
        authority_resolver: CapabilityDiscoveryAuthorityResolver,
        observed_at: Callable[[], datetime] | None = None,
    ) -> None:
        provider_map = {provider.resource_kind: provider for provider in providers}
        if len(provider_map) != len(providers):
            raise ValueError("capability discovery providers must be unique by resource kind")
        if "case" in provider_map:
            raise ValueError("case capability provider is absent/unallocated at this base")
        self._providers = provider_map
        self._execution_resolver = execution_resolver
        self._authority_resolver = authority_resolver
        self._observed_at = observed_at or (lambda: datetime.now(UTC))

    def search(
        self,
        request: CapabilityDiscoveryRequest,
        *,
        meta: core_contracts.ApiMeta,
        authority_contexts: Mapping[str, CapabilityAuthorityContext] | None = None,
    ) -> CapabilityDiscoveryResponse:
        """Emit one replayable candidate packet without claiming persistence."""

        contexts = authority_contexts or {}
        provider_results: list[CapabilityProviderSearchResult] = []
        missing_reasons: list[str] = []
        unavailable_reasons: list[str] = []
        for resource_kind in request.resource_kinds:
            provider = self._providers.get(resource_kind)
            if provider is None:
                missing_reasons.append(f"{resource_kind}:producer_missing")
                continue
            try:
                result = provider.search(request)
            except CapabilityProviderUnavailableError as exc:
                unavailable_reasons.append(f"{resource_kind}:{exc.reason_code}")
                continue
            if result.resource_kind != resource_kind:
                raise ValueError("provider returned a different resource kind")
            if result.ledger.request_ref != request.search.request_id:
                raise ValueError("provider ledger request_ref does not bind the request")
            provider_results.append(result)

        frontier = _compose_frontier(
            request=request,
            provider_results=provider_results,
            missing_reasons=tuple(missing_reasons),
            unavailable_reasons=tuple(unavailable_reasons),
        )
        observed_at = self._observed_at()
        items = tuple(
            self._compose_item(
                row,
                provider_result=result,
                request=request,
                authority_context=contexts.get(row.capability_ref),
                observed_at=observed_at,
            )
            for result in provider_results
            for row in result.rows
        )
        rows = tuple(row for result in provider_results for row in result.rows)
        request_digest = "sha256:" + _digest(request.model_dump(mode="json"))
        time = _response_time(observed_at, rows)
        provenance_refs = tuple(
            dict.fromkeys(
                (
                    CAPABILITY_PROVIDER_REGISTRY_INDEX_REF,
                    *(result.producer_ref for result in provider_results),
                    *(result.ledger.replay_key for result in provider_results),
                )
            )
        )
        return CapabilityDiscoveryResponse(
            meta=meta,
            request=request,
            request_digest=request_digest,
            authority_purpose=request.search.authority_purpose,
            audience=request.audience,
            results=items,
            frontier=frontier,
            rule_version=CAPABILITY_DISCOVERY_RULE_VERSION,
            provenance_refs=provenance_refs,
            time=time,
        )

    def _compose_item(
        self,
        row: CapabilityIndexDiscoveryRow,
        *,
        provider_result: CapabilityProviderSearchResult,
        request: CapabilityDiscoveryRequest,
        authority_context: CapabilityAuthorityContext | None,
        observed_at: datetime,
    ) -> CapabilityDiscoveryItem:
        if row.time.freshness == "stale":
            discovery_state = "index_stale"
            discovery_reasons = tuple(
                dict.fromkeys((*provider_result.incompleteness_reasons, "index_snapshot_stale"))
            )
        elif provider_result.completeness_status in {"complete", "complete_no_match"}:
            discovery_state = "discoverable"
            discovery_reasons = ()
        else:
            discovery_state = provider_result.completeness_status
            discovery_reasons = provider_result.incompleteness_reasons
        discovery = CapabilityDiscoveryPostureResult(
            state=discovery_state,
            producer_ref=row.producer_ref,
            snapshot_ref=row.snapshot_ref,
            freshness_ref=row.freshness_ref,
            reason_codes=discovery_reasons,
            provenance_refs=row.provenance_refs,
            time=row.time,
        )
        execution = self._execution_resolver.resolve(
            capability_ref=row.capability_ref,
            producer_ref="runtime-quality:capability-execution-reconciler",
            provenance_refs=row.provenance_refs,
            observed_at=observed_at,
        )
        authority = self._authority_resolver.resolve(
            capability_ref=row.capability_ref,
            content_digest=row.content_digest,
            authority_purpose=request.search.authority_purpose,
            audience=request.audience,
            context=authority_context,
            observed_at=observed_at,
        )
        return CapabilityDiscoveryItem(
            capability_ref=row.capability_ref,
            content_digest=row.content_digest,
            resource_kind=row.resource_kind,
            label=row.label,
            description=row.description,
            discovery_result=discovery,
            execution_result=execution,
            authority_result=authority,
            authoritative_for=(),
            may_not_use_for=tuple(
                dict.fromkeys(
                    (
                        *row.may_not_use_for,
                        "discovery_as_execution_authority",
                        "discovery_as_publication_authority",
                    )
                )
            ),
            authority_purpose=request.search.authority_purpose,
            provenance_refs=tuple(
                dict.fromkeys(
                    (
                        *row.provenance_refs,
                        *execution.provenance_refs,
                        *authority.provenance_refs,
                    )
                )
            ),
            rule_version=CAPABILITY_DISCOVERY_RULE_VERSION,
            time=row.time,
        )


def _compose_frontier(
    *,
    request: CapabilityDiscoveryRequest,
    provider_results: Sequence[CapabilityProviderSearchResult],
    missing_reasons: tuple[str, ...],
    unavailable_reasons: tuple[str, ...],
) -> SearchFrontier:
    replay_packet = {
        "request": request.model_dump(mode="json"),
        "provider_results": [result.model_dump(mode="json") for result in provider_results],
        "missing_reasons": list(missing_reasons),
        "unavailable_reasons": list(unavailable_reasons),
    }
    replay_payload = (
        json.dumps(
            replay_packet,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        .encode("utf-8")
        .hex()
    )
    fields, expected_hash = _replay_frontier(replay_payload)
    return SearchFrontier(
        **fields,
        replay_command=(
            "python -m polisyos.runtime.quality.capability_discovery "
            f"--replay-frontier {replay_payload}"
        ),
        replay_expected_output_hash=expected_hash,
    )


def _project_frontier(
    *,
    request: CapabilityDiscoveryRequest,
    provider_results: Sequence[CapabilityProviderSearchResult],
    missing_reasons: tuple[str, ...],
    unavailable_reasons: tuple[str, ...],
    replay_packet: dict[str, object],
) -> dict[str, object]:
    _validate_federation_inputs(
        request=request,
        provider_results=provider_results,
        missing_reasons=missing_reasons,
        unavailable_reasons=unavailable_reasons,
    )
    ledgers = tuple(result.ledger for result in provider_results)
    candidates = tuple(candidate for ledger in ledgers for candidate in ledger.candidates)
    rejected = tuple(candidate for ledger in ledgers for candidate in ledger.rejected_candidates)
    if len({candidate.candidate_ref for candidate in candidates}) != len(candidates):
        raise ValueError("provider candidate refs must be unique across the federation")
    indexes = tuple(
        dict.fromkeys(index for ledger in ledgers for index in ledger.indexes_used)
    ) or (CAPABILITY_PROVIDER_REGISTRY_INDEX_REF,)
    index_versions = tuple(
        dict.fromkeys(ref for ledger in ledgers for ref in ledger.index_version_refs)
    )
    index_freshness = {
        key: value for ledger in ledgers for key, value in ledger.index_freshness.items()
    }
    provider_failure_reasons = (*missing_reasons, *unavailable_reasons)
    if provider_failure_reasons and indexes == (CAPABILITY_PROVIDER_REGISTRY_INDEX_REF,):
        index_freshness[CAPABILITY_PROVIDER_REGISTRY_INDEX_REF] = {
            "state": "incomplete",
            "reason_codes": list(provider_failure_reasons),
        }
    statuses = [
        "complete"
        if result.completeness_status == "complete_no_match"
        else result.completeness_status
        for result in provider_results
    ]
    if missing_reasons:
        statuses.append("producer_missing")
    if unavailable_reasons:
        statuses.append("producer_unavailable")
    if not statuses:
        statuses.append("complete")
    completeness = min(statuses, key=_COMPLETENESS_PRIORITY.__getitem__)
    if completeness == "complete" and not candidates:
        completeness = "complete_no_match"
    incompleteness_reasons = tuple(
        dict.fromkeys(
            (
                *missing_reasons,
                *unavailable_reasons,
                *(
                    reason
                    for result in provider_results
                    for reason in result.incompleteness_reasons
                ),
            )
        )
    )
    no_hit_frontier = tuple(
        dict.fromkeys(
            (
                *(reason.partition(":")[0] for reason in missing_reasons),
                *(reason.partition(":")[0] for reason in unavailable_reasons),
                *(value for ledger in ledgers for value in ledger.no_hit_frontier),
            )
        )
    )
    snapshot_hash = "sha256:" + _digest(replay_packet)
    cutoffs = tuple(
        result.actual_cutoff for result in provider_results if result.actual_cutoff is not None
    )
    return {
        "request_ref": request.search.request_id,
        "query_plan": {
            "intent": request.search.intent,
            "resource_kinds": list(request.resource_kinds),
            "provider_query_plans": [ledger.query_plan for ledger in ledgers],
        },
        "corpus_ref": CAPABILITY_PROVIDER_REGISTRY_INDEX_REF,
        "corpus_path": "runtime/quality/capability_discovery.py",
        "corpus_snapshot_hash": snapshot_hash,
        "corpus_kind": "canonical",
        "indexes_used": indexes,
        "index_version_refs": index_versions,
        "index_freshness": index_freshness,
        "query_expansion_traces": tuple(
            trace for ledger in ledgers for trace in ledger.query_expansion_traces
        ),
        "candidates": candidates,
        "rejected_candidates": rejected,
        "no_hit_frontier": no_hit_frontier,
        "incompleteness": {
            "provider_count": len(provider_results),
            "missing_provider_count": len(missing_reasons),
            "unavailable_provider_count": len(unavailable_reasons),
        },
        "replay_key": "capability-discovery:" + _digest(replay_packet),
        "requested_count": sum(result.requested_count for result in provider_results),
        "evaluated_count": sum(result.evaluated_count for result in provider_results),
        "returned_count": len(candidates),
        "actual_cutoff": sum(cutoffs) if cutoffs else None,
        "completeness_status": completeness,
        "incompleteness_reasons": incompleteness_reasons,
    }


def _validate_federation_inputs(
    *,
    request: CapabilityDiscoveryRequest,
    provider_results: Sequence[CapabilityProviderSearchResult],
    missing_reasons: tuple[str, ...],
    unavailable_reasons: tuple[str, ...],
) -> None:
    result_kinds = tuple(result.resource_kind for result in provider_results)
    if len(set(result_kinds)) != len(result_kinds):
        raise ValueError("replayed provider results must be unique by resource kind")
    requested_order = tuple(kind for kind in request.resource_kinds if kind in result_kinds)
    if result_kinds != requested_order:
        raise ValueError("provider results must preserve requested resource-kind order")
    if any(result.ledger.request_ref != request.search.request_id for result in provider_results):
        raise ValueError("provider ledger request_ref does not bind the request")
    missing_kinds = tuple(reason.partition(":")[0] for reason in missing_reasons)
    unavailable_kinds = tuple(reason.partition(":")[0] for reason in unavailable_reasons)
    all_kinds = (*result_kinds, *missing_kinds, *unavailable_kinds)
    if len(set(all_kinds)) != len(all_kinds):
        raise ValueError("each requested resource kind requires exactly one producer disposition")
    if set(all_kinds) != set(request.resource_kinds):
        raise ValueError("replay packet must account for every requested resource kind")


def _response_time(
    observed_at: datetime,
    rows: Sequence[CapabilityIndexDiscoveryRow],
) -> dict[str, object]:
    freshness = "unknown"
    if rows:
        freshness = "stale" if any(row.time.freshness == "stale" for row in rows) else "current"
    return {
        "observed_at": observed_at,
        "valid_from": observed_at,
        "valid_until": None,
        "freshness": freshness,
    }


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _replay_frontier(payload_hex: str) -> tuple[dict[str, object], str]:
    packet = json.loads(bytes.fromhex(payload_hex).decode("utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("capability discovery replay packet must be an object")
    expected_keys = {
        "request",
        "provider_results",
        "missing_reasons",
        "unavailable_reasons",
    }
    if set(packet) != expected_keys:
        raise ValueError("capability discovery replay packet has unexpected fields")
    request = CapabilityDiscoveryRequest.model_validate_json(
        json.dumps(packet["request"], ensure_ascii=False)
    )
    raw_results = packet["provider_results"]
    if not isinstance(raw_results, list):
        raise ValueError("provider_results must be a list")
    provider_results = tuple(
        CapabilityProviderSearchResult.model_validate_json(json.dumps(item, ensure_ascii=False))
        for item in raw_results
    )
    missing_reasons = _replay_reason_tuple(packet["missing_reasons"])
    unavailable_reasons = _replay_reason_tuple(packet["unavailable_reasons"])
    canonical_packet = {
        "request": request.model_dump(mode="json"),
        "provider_results": [result.model_dump(mode="json") for result in provider_results],
        "missing_reasons": list(missing_reasons),
        "unavailable_reasons": list(unavailable_reasons),
    }
    fields = _project_frontier(
        request=request,
        provider_results=provider_results,
        missing_reasons=missing_reasons,
        unavailable_reasons=unavailable_reasons,
        replay_packet=canonical_packet,
    )
    validated = SearchFrontier(
        **fields,
        replay_command="capability-discovery:replay-packet",
        replay_expected_output_hash="sha256:" + "0" * 64,
    )
    output = validated.model_dump(
        mode="json",
        exclude={"replay_command", "replay_expected_output_hash"},
    )
    return fields, "sha256:" + _digest(output)


def _replay_reason_tuple(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
        raise ValueError("replay reason fields must be lists of non-empty strings")
    return tuple(raw)


def main(argv: list[str] | None = None) -> int:
    """Replay one emitted federation packet without claiming persistence."""

    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2 or arguments[0] != "--replay-frontier":
        raise SystemExit("usage: capability_discovery --replay-frontier PAYLOAD_HEX")
    _, expected_hash = _replay_frontier(arguments[1])
    sys.stdout.write(f"{expected_hash}\n")
    return 0


__all__ = [
    "CAPABILITY_DISCOVERY_RULE_VERSION",
    "CAPABILITY_PROVIDER_REGISTRY_INDEX_REF",
    "SCIENTIST_CAPABILITY_DISCOVERY_PROVIDER_REF",
    "CapabilityDiscoveryComposer",
    "CapabilityDiscoveryProvider",
    "CapabilityIndexOwnerReceipt",
    "CapabilityProviderSearchResult",
    "CapabilityProviderUnavailableError",
    "LexCapabilityDiscoveryProvider",
    "LexOwnerReceipt",
    "ScientistRegistryCapabilityDiscoveryProvider",
    "ScientistRegistryCapabilityRecord",
    "ScientistRegistryOwnerReceipt",
    "ScientistRegistrySnapshot",
    "SourceProfileOwnerReceipt",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
