"""Behavioral tests for registry-backed capability discovery composition."""

from __future__ import annotations

import shlex
import subprocess
from datetime import UTC, datetime, timedelta

from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryRequest,
    CapabilityTimeSemantics,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import SearchCandidate, SearchLedger, SearchRequest
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.quality.capability_authority import CapabilityDiscoveryAuthorityResolver
from polisyos.runtime.quality.capability_discovery import (
    CapabilityDiscoveryComposer,
    CapabilityDiscoveryProvider,
    CapabilityProviderSearchResult,
    CapabilityProviderUnavailableError,
)
from polisyos.runtime.quality.capability_index import CapabilityIndexDiscoveryRow
from polisyos.runtime.quality.capability_resolver import CapabilityExecutionResolver

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)


class _Provider(CapabilityDiscoveryProvider):
    def __init__(self, result: CapabilityProviderSearchResult, calls: list[str]) -> None:
        self._result = result
        self._calls = calls

    @property
    def resource_kind(self) -> str:
        return self._result.resource_kind

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        self._calls.append(self.resource_kind)
        return self._result


class _UnavailableProvider(CapabilityDiscoveryProvider):
    @property
    def resource_kind(self) -> str:
        return "source"

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        raise CapabilityProviderUnavailableError("connector_registry_outage")


def test_capability_discovery_postures_use_three_independent_producers() -> None:
    """An index hit must not establish either execution or authority."""
    calls: list[str] = []
    method = _provider_result("method", "capability:method:generated")
    response = _composer(providers=(_Provider(method, calls),)).search(
        _request(("method",)), meta=ApiMeta(request_id="http:test")
    )

    assert calls == ["method"]
    item = response.results[0]
    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state == "operation_missing"
    assert item.authority_result.state == "bridge_missing"
    assert "not_established" in item.authority_result.reason_codes
    assert item.authoritative_for == ()


def test_provider_mapping_permutation_does_not_change_composed_packet() -> None:
    """Federation order is request-owned, not mapping-insertion-owned."""
    first_calls: list[str] = []
    second_calls: list[str] = []
    method = _provider_result("method", "capability:method:generated")
    dataset = _provider_result("dataset", "capability:dataset:generated")
    request = _request(("method", "dataset"))
    first = _composer(
        providers=(_Provider(method, first_calls), _Provider(dataset, first_calls))
    ).search(request, meta=ApiMeta(request_id="http:test"))
    second = _composer(
        providers=(_Provider(dataset, second_calls), _Provider(method, second_calls))
    ).search(request, meta=ApiMeta(request_id="http:test"))

    assert first_calls == second_calls == ["method", "dataset"]
    assert first.model_dump(mode="json", exclude={"meta": {"generated_at"}}) == (
        second.model_dump(mode="json", exclude={"meta": {"generated_at"}})
    )


def test_complete_federation_with_one_no_hit_and_one_hit_is_complete() -> None:
    calls: list[str] = []
    method = _provider_result("method", "capability:method:generated")
    dataset = _provider_result(
        "dataset",
        None,
        completeness_status="complete_no_match",
        incompleteness_reasons=(),
    )

    response = _composer(providers=(_Provider(method, calls), _Provider(dataset, calls))).search(
        _request(("method", "dataset")),
        meta=ApiMeta(request_id="http:mixed-complete"),
    )

    assert response.frontier.completeness_status == "complete"
    assert tuple(item.capability_ref for item in response.results) == (
        "capability:method:generated",
    )


def test_case_provider_missing_is_typed_and_frontier_is_incomplete() -> None:
    """The absent global case index is not converted into an empty success."""
    response = _composer(providers=()).search(
        _request(("case",)), meta=ApiMeta(request_id="http:case")
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_missing"
    assert response.frontier.incompleteness_reasons == ("case:producer_missing",)
    assert response.frontier.no_hit_frontier == ("case",)
    replay = subprocess.run(  # noqa: S603
        shlex.split(response.frontier.replay_command),
        check=True,
        capture_output=True,
        text=True,
    )
    assert replay.stdout.strip() == response.frontier.replay_expected_output_hash


def test_distinct_no_hit_recall_stale_cutoff_and_outage_results_survive() -> None:
    """Federation must preserve distinct owner frontier failures."""
    cases = (
        ("complete_no_match", (), "complete_no_match"),
        ("recall_unmeasured", ("recall_not_measured",), "recall_unmeasured"),
        ("index_stale", ("snapshot_expired",), "index_stale"),
        ("budget_cutoff", ("row_budget_exhausted",), "budget_cutoff"),
        ("producer_unavailable", ("provider_outage",), "producer_unavailable"),
    )
    for source_status, reasons, expected in cases:
        calls: list[str] = []
        result = _provider_result(
            "method",
            None,
            completeness_status=source_status,
            incompleteness_reasons=reasons,
        )
        response = _composer(providers=(_Provider(result, calls),)).search(
            _request(("method",)), meta=ApiMeta(request_id=f"http:{source_status}")
        )
        assert response.frontier.completeness_status == expected
        assert response.frontier.incompleteness_reasons == reasons
        assert response.results == ()


def test_provider_outage_is_typed_instead_of_an_empty_success() -> None:
    response = _composer(providers=(_UnavailableProvider(),)).search(
        _request(("source",)), meta=ApiMeta(request_id="http:outage")
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_unavailable"
    assert response.frontier.incompleteness_reasons == ("source:connector_registry_outage",)


def test_selected_rejected_cutoff_index_freshness_and_incompleteness_are_owner_values() -> None:
    """The federation projects the actual owner ledger rather than rebuilding it."""
    calls: list[str] = []
    result = _provider_result(
        "dataset",
        "capability:dataset:selected",
        rejected_ref="capability:dataset:rejected",
        completeness_status="budget_cutoff",
        incompleteness_reasons=("owner_budget_cutoff",),
        actual_cutoff=1,
    )
    response = _composer(providers=(_Provider(result, calls),)).search(
        _request(("dataset",)), meta=ApiMeta(request_id="http:frontier")
    )

    assert tuple(row.candidate_ref for row in response.frontier.candidates) == (
        "capability:dataset:selected",
    )
    assert tuple(row.candidate_ref for row in response.frontier.rejected_candidates) == (
        "capability:dataset:rejected",
    )
    assert response.frontier.actual_cutoff == 1
    assert response.frontier.indexes_used == ("index:dataset:owner",)
    assert response.frontier.index_freshness == {
        "index:dataset:owner": {"state": "current", "observed_at": NOW.isoformat()}
    }
    assert response.frontier.incompleteness_reasons == ("owner_budget_cutoff",)


def _composer(*, providers: tuple[CapabilityDiscoveryProvider, ...]) -> CapabilityDiscoveryComposer:
    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    )
    return CapabilityDiscoveryComposer(
        providers=providers,
        execution_resolver=CapabilityExecutionResolver(registrations=(), policy_resolver=policy),
        authority_resolver=CapabilityDiscoveryAuthorityResolver(production_approval_resolver=None),
        observed_at=lambda: NOW,
    )


def _request(resource_kinds: tuple[str, ...]) -> CapabilityDiscoveryRequest:
    return CapabilityDiscoveryRequest(
        search=SearchRequest(
            request_id="search:generated",
            query_text="generated capability",
            construct_refs=("construct:generated",),
            intent="capability_discovery",
            required_layers=("runtime_registry",),
            authority_purpose="review_capability_candidates",
            allowed_modes=("exact",),
            budget={"top_k": 5},
            rule_version="policyos.ds10.discovery.v1",
        ),
        resource_kinds=resource_kinds,
        audience="REVIEWER",
    )


def _provider_result(
    resource_kind: str,
    selected_ref: str | None,
    *,
    rejected_ref: str | None = None,
    completeness_status: str = "complete",
    incompleteness_reasons: tuple[str, ...] = (),
    actual_cutoff: int | None = None,
) -> CapabilityProviderSearchResult:
    selected = (_candidate(selected_ref, resource_kind),) if selected_ref else ()
    rejected = (_candidate(rejected_ref, resource_kind),) if rejected_ref else ()
    ledger = SearchLedger(
        request_ref="search:generated",
        query_plan={"match": "owner_defined"},
        corpus_ref=f"corpus:{resource_kind}:owner",
        corpus_path=f"owner/{resource_kind}",
        corpus_snapshot_hash="sha256:" + "1" * 64,
        corpus_kind="canonical",
        indexes_used=(f"index:{resource_kind}:owner",),
        index_version_refs=(f"snapshot:{resource_kind}:owner",),
        index_freshness={
            f"index:{resource_kind}:owner": {
                "state": "current",
                "observed_at": NOW.isoformat(),
            }
        },
        candidates=selected,
        rejected_candidates=rejected,
        no_hit_frontier=(() if selected else (resource_kind,)),
        incompleteness={"status": completeness_status},
        replay_key=f"replay:{resource_kind}:owner",
        replay_command=f"owner-search --kind {resource_kind}",
        replay_expected_output_hash="sha256:" + "2" * 64,
    )
    rows = (_row(selected_ref, resource_kind),) if selected_ref else ()
    return CapabilityProviderSearchResult(
        resource_kind=resource_kind,
        producer_ref=f"producer:{resource_kind}:owner",
        rows=rows,
        ledger=ledger,
        requested_count=5,
        evaluated_count=len(selected) + len(rejected),
        actual_cutoff=actual_cutoff,
        completeness_status=completeness_status,
        incompleteness_reasons=incompleteness_reasons,
    )


def _candidate(ref: str, resource_kind: str) -> SearchCandidate:
    return SearchCandidate(
        candidate_ref=ref,
        source_layer="owner",
        match_mode="exact",
        score=0.8,
        evidence_refs=(f"evidence:{resource_kind}:owner",),
        authority_boundary={"authoritative_for": []},
        may_not_use_for=("publication_authority",),
    )


def _row(ref: str, resource_kind: str) -> CapabilityIndexDiscoveryRow:
    return CapabilityIndexDiscoveryRow(
        capability_ref=ref,
        content_digest="sha256:" + "3" * 64,
        resource_kind=resource_kind,
        construct_refs=("construct:generated",),
        label="Generated owner row",
        description="Owner-projected row for federation tests.",
        producer_ref=f"producer:{resource_kind}:owner",
        snapshot_ref=f"snapshot:{resource_kind}:owner",
        freshness_ref=f"freshness:{resource_kind}:owner",
        provenance_refs=(f"provenance:{resource_kind}:owner",),
        may_not_use_for=("publication_authority",),
        time=CapabilityTimeSemantics(
            observed_at=NOW,
            valid_from=NOW,
            valid_until=NOW + timedelta(hours=1),
            freshness="current",
        ),
    )
