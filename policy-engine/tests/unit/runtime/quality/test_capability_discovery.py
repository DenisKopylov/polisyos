"""Behavioral tests for registry-backed capability discovery composition."""

from __future__ import annotations

import copy
import hashlib
import json
import shlex
import subprocess
from datetime import UTC, date, datetime, timedelta

import pytest

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
    CapabilityIndexOwnerReceipt,
    CapabilityProviderSearchResult,
    CapabilityProviderUnavailableError,
    LexOwnerReceipt,
    ScientistRegistryOwnerReceipt,
    SourceProfileOwnerReceipt,
    main,
)
from polisyos.runtime.quality.capability_index import (
    CapabilityIndexDiscoveryRow,
    LegalNormOwnerTruth,
    ScientistCapabilityOwnerTruth,
)
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
    assert item.execution_result.state == "not_established"
    assert item.authority_result.state == "bridge_missing"
    assert "not_established" in item.authority_result.reason_codes
    assert item.authoritative_for == ()


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("index_stale", "owner_snapshot_expired"),
        ("producer_unavailable", "owner_connector_unavailable"),
        ("recall_unmeasured", "owner_recall_not_measured"),
        ("budget_cutoff", "owner_budget_cutoff"),
    ],
)
def test_incomplete_selected_row_is_not_a_discovery_positive(
    status: str,
    reason: str,
) -> None:
    calls: list[str] = []
    capability_ref = f"capability:method:{status}"
    incomplete = _provider_result(
        "method",
        capability_ref,
        completeness_status=status,
        incompleteness_reasons=(reason,),
    )
    current = _provider_result("method", capability_ref)

    response = _composer(providers=(_Provider(incomplete, calls),)).search(
        _request(("method",)), meta=ApiMeta(request_id=f"http:{status}-selected")
    )
    current_response = _composer(providers=(_Provider(current, []),)).search(
        _request(("method",)), meta=ApiMeta(request_id=f"http:{status}-current")
    )

    item = response.results[0]
    current_item = current_response.results[0]
    assert item.discovery_result.state == status
    assert item.discovery_result.reason_codes == (reason,)
    assert item.execution_result == current_item.execution_result
    assert item.execution_result.state == "not_established"
    assert item.authority_result == current_item.authority_result
    assert item.authority_result.state == "bridge_missing"


def test_agent_result_requires_exact_scientist_registry_owner_evidence() -> None:
    with pytest.raises(ValueError, match="ScientistRegistryOwnerReceipt"):
        _provider_result(
            "agent",
            "capability:agent:world-model",
            receipt_kind="capability_index",
        )

    l4_row = _row("capability:agent:world-model", "agent")
    payload = l4_row.model_dump(mode="python")
    payload["owner_truth"] = None
    payload["provenance_refs"] = ("world-model:l4-agent-row",)
    with pytest.raises(ValueError, match="ScientistCapabilityOwnerTruth"):
        CapabilityIndexDiscoveryRow.model_validate(payload)

    valid_agent = _provider_result("agent", "capability:agent:scientist-node")
    mismatched = valid_agent.model_dump(mode="python")
    mismatched["rows"][0]["owner_truth"]["registry_snapshot_digest"] = "sha256:" + "9" * 64
    with pytest.raises(ValueError, match="typed registry snapshot"):
        CapabilityProviderSearchResult.model_validate(mismatched)


def test_current_scientist_registry_receipt_admits_candidate_discovery_only() -> None:
    calls: list[str] = []
    agent = _provider_result("agent", "capability:agent:scientist-node")

    response = _composer(providers=(_Provider(agent, calls),)).search(
        _request(("agent",)), meta=ApiMeta(request_id="http:scientist-agent")
    )

    item = response.results[0]
    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state == "not_established"
    assert item.authority_result.state == "bridge_missing"


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


def test_replay_rebuilds_complete_frontier_and_binds_every_owner_field(capsys) -> None:
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
        _request(("dataset",)), meta=ApiMeta(request_id="http:replay-complete")
    )
    payload_hex = shlex.split(response.frontier.replay_command)[-1]
    packet = json.loads(bytes.fromhex(payload_hex).decode("utf-8"))

    owner = packet["provider_results"][0]
    assert owner["ledger"]["candidates"][0]["candidate_ref"] == ("capability:dataset:selected")
    assert owner["ledger"]["rejected_candidates"][0]["candidate_ref"] == (
        "capability:dataset:rejected"
    )
    assert owner["actual_cutoff"] == 1
    assert owner["completeness_status"] == "budget_cutoff"

    assert main(["--replay-frontier", payload_hex]) == 0
    baseline = capsys.readouterr().out.strip()
    assert baseline == response.frontier.replay_expected_output_hash

    mutations = (
        ("request", ("request", "search", "query_text"), "mutated query"),
        ("row", ("provider_results", 0, "rows", 0, "label"), "mutated label"),
        (
            "selected",
            ("provider_results", 0, "ledger", "candidates", 0, "score"),
            0.7,
        ),
        (
            "rejected",
            ("provider_results", 0, "ledger", "rejected_candidates", 0, "score"),
            0.6,
        ),
        (
            "no-hit",
            ("provider_results", 0, "ledger", "no_hit_frontier"),
            ["dataset"],
        ),
        (
            "indexes",
            ("provider_results", 0, "ledger", "indexes_used", 0),
            "index:dataset:mutated",
        ),
        (
            "freshness",
            (
                "provider_results",
                0,
                "ledger",
                "index_freshness",
                "index:dataset:owner",
                "state",
            ),
            "stale",
        ),
        ("cutoff", ("provider_results", 0, "actual_cutoff"), 2),
        ("requested-count", ("provider_results", 0, "requested_count"), 6),
        ("evaluated-count", ("provider_results", 0, "evaluated_count"), 3),
        (
            "completeness",
            ("provider_results", 0, "completeness_status"),
            "index_stale",
        ),
        (
            "reasons",
            ("provider_results", 0, "incompleteness_reasons", 0),
            "mutated_reason",
        ),
    )
    for label, path, replacement in mutations:
        mutated = copy.deepcopy(packet)
        target = mutated
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        mutated_hex = json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode().hex()

        try:
            main(["--replay-frontier", mutated_hex])
        except (ValueError, TypeError):
            continue
        assert capsys.readouterr().out.strip() != baseline, label


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
        execution_resolver=CapabilityExecutionResolver(
            operation_registry=None,
            conformance_verifier=None,
            policy_resolver=policy,
        ),
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
    receipt_kind: str | None = None,
) -> CapabilityProviderSearchResult:
    selected = (_candidate(selected_ref, resource_kind),) if selected_ref else ()
    rejected = (_candidate(rejected_ref, resource_kind),) if rejected_ref else ()
    search_snapshot_ref = f"snapshot:{resource_kind}:owner"
    profile_snapshot_ref = "source-profile-registry:snapshot:test"
    connector_snapshot_ref = "connector-registry:snapshot:test"
    node_snapshot_ref = "scientist:node-registry:snapshot:test"
    tool_snapshot_ref = "scientist:tool-registry:snapshot:test"
    verifier_ref = "lex:grounding-verifier:test"
    if resource_kind == "source":
        search_snapshot_digest = "sha256:" + _test_digest(
            {
                "profile_registry_snapshot_ref": profile_snapshot_ref,
                "profile_registry_snapshot_digest": "sha256:" + "4" * 64,
                "connector_snapshot_ref": connector_snapshot_ref,
                "connector_snapshot_digest": "sha256:" + "5" * 64,
            }
        )
    elif resource_kind == "agent":
        search_snapshot_digest = "sha256:" + _test_digest(
            {
                "node_registry_snapshot_ref": node_snapshot_ref,
                "node_registry_snapshot_digest": "sha256:" + "7" * 64,
                "tool_registry_snapshot_ref": tool_snapshot_ref,
                "tool_registry_snapshot_digest": "sha256:" + "8" * 64,
            }
        )
    elif resource_kind == "legal_norm":
        search_snapshot_digest = "sha256:" + "6" * 64
    else:
        search_snapshot_digest = "sha256:" + "1" * 64
    ledger = SearchLedger(
        request_ref="search:generated",
        query_plan={"match": "owner_defined"},
        corpus_ref=f"corpus:{resource_kind}:owner",
        corpus_path=f"owner/{resource_kind}",
        corpus_snapshot_hash=search_snapshot_digest,
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
    payload = {
        "resource_kind": resource_kind,
        "producer_ref": f"producer:{resource_kind}:owner",
        "rows": rows,
        "ledger": ledger,
        "requested_count": 5,
        "evaluated_count": len(selected) + len(rejected),
        "actual_cutoff": actual_cutoff,
        "completeness_status": completeness_status,
        "incompleteness_reasons": incompleteness_reasons,
    }
    payload_json = {
        **payload,
        "rows": [row.model_dump(mode="json") for row in rows],
        "ledger": ledger.model_dump(mode="json"),
    }
    result_digest = "sha256:" + _test_digest(payload_json)
    owner_kind = receipt_kind or resource_kind
    provenance_refs = [
        f"provenance:{resource_kind}:owner",
        payload["producer_ref"],
        search_snapshot_ref,
    ]
    if owner_kind in {"method", "dataset", "capability_index"}:
        provenance_refs.append(f"release:{resource_kind}:owner")
    elif owner_kind == "source":
        provenance_refs.extend((profile_snapshot_ref, connector_snapshot_ref))
    elif owner_kind == "legal_norm":
        provenance_refs.append(verifier_ref)
    elif owner_kind == "agent":
        provenance_refs.extend((node_snapshot_ref, tool_snapshot_ref))
    common = {
        "owner_producer_ref": payload["producer_ref"],
        "search_snapshot_ref": search_snapshot_ref,
        "search_snapshot_digest": ledger.corpus_snapshot_hash,
        "result_digest": result_digest,
        "provenance_refs": tuple(provenance_refs),
    }
    if owner_kind in {"method", "dataset", "capability_index"}:
        receipt = CapabilityIndexOwnerReceipt(
            resource_kind=(resource_kind if resource_kind in {"method", "dataset"} else "method"),
            index_release_ref=f"release:{resource_kind}:owner",
            **common,
        )
    elif owner_kind == "source":
        receipt = SourceProfileOwnerReceipt(
            profile_registry_snapshot_ref=profile_snapshot_ref,
            profile_registry_snapshot_digest="sha256:" + "4" * 64,
            connector_snapshot_ref=connector_snapshot_ref,
            connector_snapshot_digest="sha256:" + "5" * 64,
            **common,
        )
    elif owner_kind == "legal_norm":
        receipt = LexOwnerReceipt(
            lex_snapshot_ref=search_snapshot_ref,
            lex_snapshot_digest=search_snapshot_digest,
            verifier_ref=verifier_ref,
            **common,
        )
    elif owner_kind == "agent":
        receipt = ScientistRegistryOwnerReceipt(
            node_registry_snapshot_ref=node_snapshot_ref,
            node_registry_snapshot_digest="sha256:" + "7" * 64,
            tool_registry_snapshot_ref=tool_snapshot_ref,
            tool_registry_snapshot_digest="sha256:" + "8" * 64,
            **common,
        )
    else:
        raise AssertionError(f"unsupported owner kind: {owner_kind}")
    return CapabilityProviderSearchResult(**payload, owner_receipt=receipt)


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
    owner_truth = None
    if resource_kind == "legal_norm":
        owner_truth = LegalNormOwnerTruth(
            legal_norm_ref=ref,
            normative_fact_ref="lex:fact:test",
            source_document_ref="lex:document:test",
            provision_citation="Art. 1",
            grounding_status="grounded",
            hallucination_status="verified_clear",
            jurisdiction="UA",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            temporal_state="effective",
            temporal_resolution_status="resolved",
            temporal_snapshot_at=NOW,
            temporal_audit_ref="lex:temporal-audit:test",
            provenance_refs=("provenance:legal_norm:owner",),
        )
    elif resource_kind == "agent":
        owner_truth = ScientistCapabilityOwnerTruth(
            capability_ref=ref,
            registry_kind="node_registry",
            registry_schema_ref="scientist.node_registry.v1",
            registry_entry_ref="scientist:node:test",
            registry_snapshot_ref="scientist:node-registry:snapshot:test",
            registry_snapshot_digest="sha256:" + "7" * 64,
            provenance_refs=("provenance:agent:owner",),
        )
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
        owner_truth=owner_truth,
        may_not_use_for=("publication_authority",),
        time=CapabilityTimeSemantics(
            observed_at=NOW,
            valid_from=NOW,
            valid_until=NOW + timedelta(hours=1),
            freshness="current",
        ),
    )


def _test_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
