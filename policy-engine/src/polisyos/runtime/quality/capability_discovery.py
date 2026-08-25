"""Registry-backed capability discovery federation.

The federation composes owner-returned search ledgers without inventing search
matches, independently reconciles execution, and keeps authority fail closed
until the separately signed capability-purpose binding producer exists.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryItem,
    CapabilityDiscoveryPostureResult,
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
    CapabilityResourceKind,
)
from polisyos.core.contracts.search import (
    SearchCompletenessStatus,
    SearchFrontier,
    SearchLedger,
)
from polisyos.runtime.quality.capability_index import (  # noqa: TC001
    CapabilityIndexDiscoveryRow,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from polisyos.core.contracts.runtime import ApiMeta
    from polisyos.runtime.quality.capability_authority import (
        CapabilityAuthorityContext,
        CapabilityDiscoveryAuthorityResolver,
    )
    from polisyos.runtime.quality.capability_resolver import CapabilityExecutionResolver

CAPABILITY_DISCOVERY_RULE_VERSION = "policyos.ds10.discovery.v1"
CAPABILITY_PROVIDER_REGISTRY_INDEX_REF = "runtime-quality:capability-provider-registry"

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


class CapabilityProviderSearchResult(BaseModel):
    """Typed owner search rows plus the exact ledger that selected them."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_kind: CapabilityResourceKind
    producer_ref: str = Field(min_length=1)
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
        if self.evaluated_count < len(self.ledger.candidates) + len(
            self.ledger.rejected_candidates
        ):
            raise ValueError("evaluated_count must cover selected and rejected owner rows")
        complete = self.completeness_status in {"complete", "complete_no_match"}
        if complete and self.incompleteness_reasons:
            raise ValueError("complete provider results cannot carry incompleteness reasons")
        if not complete and not self.incompleteness_reasons:
            raise ValueError("incomplete provider results require typed reasons")
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
        meta: ApiMeta,
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
        rows = tuple(row for result in provider_results for row in result.rows)
        items = tuple(
            self._compose_item(
                row,
                request=request,
                authority_context=contexts.get(row.capability_ref),
                observed_at=observed_at,
            )
            for row in rows
        )
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
        request: CapabilityDiscoveryRequest,
        authority_context: CapabilityAuthorityContext | None,
        observed_at: datetime,
    ) -> CapabilityDiscoveryItem:
        discovery_state = "index_stale" if row.time.freshness == "stale" else "discoverable"
        discovery_reasons = ("index_snapshot_stale",) if discovery_state == "index_stale" else ()
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
    provider_hashes = tuple(ledger.corpus_snapshot_hash for ledger in ledgers)
    registry_snapshot = {
        "requested_resource_kinds": request.resource_kinds,
        "bound_provider_kinds": tuple(result.resource_kind for result in provider_results),
        "missing_reasons": missing_reasons,
        "unavailable_reasons": unavailable_reasons,
        "provider_replays": tuple(
            {
                "replay_key": ledger.replay_key,
                "replay_command": ledger.replay_command,
                "replay_expected_output_hash": ledger.replay_expected_output_hash,
            }
            for ledger in ledgers
        ),
    }
    replay_packet = {
        "provider_corpus_snapshot_hashes": provider_hashes,
        "provider_expected_output_hashes": tuple(
            ledger.replay_expected_output_hash for ledger in ledgers
        ),
        "registry_snapshot": registry_snapshot,
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
    snapshot_hash, expected_hash = _replay_frontier(replay_payload)
    replay_command = (
        "python -m polisyos.runtime.quality.capability_discovery "
        f"--replay-frontier {replay_payload}"
    )
    cutoffs = tuple(
        result.actual_cutoff for result in provider_results if result.actual_cutoff is not None
    )
    return SearchFrontier(
        request_ref=request.search.request_id,
        query_plan={
            "intent": request.search.intent,
            "resource_kinds": list(request.resource_kinds),
            "provider_query_plans": [ledger.query_plan for ledger in ledgers],
        },
        corpus_ref=CAPABILITY_PROVIDER_REGISTRY_INDEX_REF,
        corpus_path="runtime/quality/capability_discovery.py",
        corpus_snapshot_hash=snapshot_hash,
        corpus_kind="canonical",
        indexes_used=indexes,
        index_version_refs=index_versions,
        index_freshness=index_freshness,
        query_expansion_traces=tuple(
            trace for ledger in ledgers for trace in ledger.query_expansion_traces
        ),
        candidates=candidates,
        rejected_candidates=rejected,
        no_hit_frontier=no_hit_frontier,
        incompleteness={
            "provider_count": len(provider_results),
            "missing_provider_count": len(missing_reasons),
            "unavailable_provider_count": len(unavailable_reasons),
        },
        replay_key="capability-discovery:" + _digest(registry_snapshot),
        replay_command=replay_command,
        replay_expected_output_hash=expected_hash,
        requested_count=sum(result.requested_count for result in provider_results),
        evaluated_count=sum(result.evaluated_count for result in provider_results),
        returned_count=len(candidates),
        actual_cutoff=sum(cutoffs) if cutoffs else None,
        completeness_status=completeness,
        incompleteness_reasons=incompleteness_reasons,
    )


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


def _replay_frontier(payload_hex: str) -> tuple[str, str]:
    packet = json.loads(bytes.fromhex(payload_hex).decode("utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("capability discovery replay packet must be an object")
    provider_hashes = tuple(packet["provider_corpus_snapshot_hashes"])
    provider_expected_hashes = tuple(packet["provider_expected_output_hashes"])
    registry_snapshot = packet["registry_snapshot"]
    snapshot_hash = "sha256:" + _digest((provider_hashes, registry_snapshot))
    expected_hash = "sha256:" + _digest((*provider_expected_hashes, snapshot_hash))
    return snapshot_hash, expected_hash


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
    "CapabilityDiscoveryComposer",
    "CapabilityDiscoveryProvider",
    "CapabilityProviderSearchResult",
    "CapabilityProviderUnavailableError",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
