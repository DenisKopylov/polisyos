"""Semantic HTTP tests for canonical capability discovery."""

from __future__ import annotations

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import SearchLedger
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control.capability_discovery import (
    CapabilityDiscoveryService,
)
from polisyos.runtime.quality.capability_discovery import CapabilityProviderSearchResult


def _search_body(*, resource_kinds: list[str] | None = None) -> dict[str, object]:
    return {
        "search": {
            "request_id": "search:http-test",
            "query_text": "generated capability",
            "construct_refs": ["construct:generated"],
            "intent": "capability_discovery",
            "required_layers": ["runtime_registry"],
            "authority_purpose": "review_capability_candidates",
            "allowed_modes": ["exact"],
            "budget": {"top_k": 5},
            "rule_version": "policyos.ds10.discovery.v1",
        },
        "resource_kinds": resource_kinds or ["method", "dataset", "case"],
        "audience": "REVIEWER",
    }


def test_capability_search_returns_typed_missing_owner_frontier(runtime_api_env) -> None:
    """Missing deployed owners must be visible, never an empty success."""
    with runtime_api_env["client"] as client:
        response = client.post(
            "/api/v1/control/capabilities/search",
            json=_search_body(),
        )

    assert response.status_code == 200
    packet = CapabilityDiscoveryResponse.model_validate(response.json())
    assert packet.results == ()
    assert packet.frontier.completeness_status == "producer_missing"
    assert packet.frontier.incompleteness_reasons == (
        "method:producer_missing",
        "dataset:producer_missing",
        "case:producer_missing",
    )


def test_malformed_injected_provider_is_a_typed_unavailable_frontier() -> None:
    """Malformed owner output must fail closed without becoming an empty success."""

    class _MalformedProvider:
        resource_kind = "method"

        def search(self, request):
            del request
            return object()

    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    )
    service = CapabilityDiscoveryService(
        providers=(_MalformedProvider(),),
        operation_registry=None,
        conformance_verifier=None,
        policy_resolver=policy,
        production_approval_resolver=None,
    )

    response = service.search(
        CapabilityDiscoveryRequest.model_validate(_search_body(resource_kinds=["method"])),
        meta=ApiMeta(request_id="http:malformed-provider"),
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_unavailable"
    assert response.frontier.incompleteness_reasons == ("method:provider_result_invalid",)


def test_model_constructed_provider_result_is_revalidated_into_typed_unavailable() -> None:
    """A forged model instance must not bypass the owner-result validators."""
    ledger = SearchLedger(
        request_ref="search:http-test",
        query_plan={},
        corpus_ref="corpus:forged",
        corpus_path="owner/forged",
        corpus_snapshot_hash="sha256:" + "1" * 64,
        corpus_kind="fixture",
        indexes_used=("index:forged",),
        candidates=(),
        rejected_candidates=(),
        no_hit_frontier=("method",),
        replay_key="replay:forged",
        replay_command="python -m forged",
        replay_expected_output_hash="sha256:" + "2" * 64,
    )
    malformed = CapabilityProviderSearchResult.model_construct(
        resource_kind="method",
        producer_ref="provider:forged",
        owner_receipt=object(),
        rows=(),
        ledger=ledger,
        requested_count=1,
        evaluated_count=0,
        actual_cutoff=None,
        completeness_status="complete_no_match",
        incompleteness_reasons=(),
    )

    class _ConstructedProvider:
        resource_kind = "method"

        def search(self, request):
            del request
            return malformed

    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    )
    service = CapabilityDiscoveryService(
        providers=(_ConstructedProvider(),),
        operation_registry=None,
        conformance_verifier=None,
        policy_resolver=policy,
        production_approval_resolver=None,
    )

    response = service.search(
        CapabilityDiscoveryRequest.model_validate(_search_body(resource_kinds=["method"])),
        meta=ApiMeta(request_id="http:constructed-provider"),
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_unavailable"
    assert response.frontier.incompleteness_reasons == ("method:provider_result_invalid",)


def test_capability_search_persists_exact_returned_packet(
    runtime_api_env,
    monkeypatch,
) -> None:
    """The control boundary must persist the exact packet returned to HTTP."""
    control = runtime_api_env["app"].state._control_service
    persisted: list[tuple[object, str, str, str]] = []
    original_put = control._put_json_artifact

    def _capture(payload: object, *, kind: str, schema_name: str) -> str:
        ref = original_put(payload, kind=kind, schema_name=schema_name)
        persisted.append((payload, kind, schema_name, ref))
        return ref

    monkeypatch.setattr(control, "_put_json_artifact", _capture)

    with runtime_api_env["client"] as client:
        response = client.post(
            "/api/v1/control/capabilities/search",
            json=_search_body(resource_kinds=["case"]),
        )
        assert len(persisted) == 1
        persisted_packet = from_canonical_bytes(control._artifact_store.get_bytes(persisted[0][3]))

    assert response.status_code == 200
    payload, kind, schema_name, ref = persisted[0]
    assert payload == response.json()
    assert kind == "runtime.capability_discovery_response"
    assert schema_name == "polisyos.core.contracts.CapabilityDiscoveryResponse"
    assert ref.startswith("sha256:")
    assert persisted_packet == response.json()


def test_dataset_compatibility_route_delegates_to_canonical_search_once(
    runtime_api_env,
    monkeypatch,
) -> None:
    """Legacy dataset search must not retain a sibling retrieval searcher."""
    control = runtime_api_env["app"].state._control_service
    calls: list[object] = []
    original = control.search_capabilities

    def _canonical(request, *, request_id=None):
        calls.append(request)
        return original(request, request_id=request_id)

    monkeypatch.setattr(control, "search_capabilities", _canonical)
    monkeypatch.setattr(
        control._retrieval,
        "search_catalog",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy retrieval search must be strangled")
        ),
    )

    with runtime_api_env["client"] as client:
        response = client.get("/api/v1/control/data/catalog/search?metric=us.macro&geo=US&limit=5")

    assert response.status_code == 200
    packet = CapabilityDiscoveryResponse.model_validate(response.json())
    assert packet.request.resource_kinds == ("dataset",)
    assert packet.request.search.query_text == "us.macro"
    assert packet.request.search.construct_refs == ("us.macro",)
    assert packet.request.search.required_layers == ("L1",)
    assert packet.request.search.budget == {"geography": "US", "top_k": 5}
    assert len(calls) == 1


def test_post_and_dataset_get_return_the_same_injected_owner_packet(
    runtime_api_env,
    monkeypatch,
) -> None:
    """Both addresses must preserve one owner's complete canonical packet."""
    with runtime_api_env["client"] as client:
        control = runtime_api_env["app"].state._control_service
        canonical = control.search_capabilities(
            CapabilityDiscoveryRequest.model_validate(_search_body(resource_kinds=["case"])),
            request_id="http:canonical-owner",
        )
        calls: list[CapabilityDiscoveryRequest] = []

        def _same_owner(request, *, request_id=None):
            del request_id
            calls.append(request)
            return canonical

        monkeypatch.setattr(control, "search_capabilities", _same_owner)
        post = client.post(
            "/api/v1/control/capabilities/search",
            json=_search_body(resource_kinds=["case"]),
        )
        get = client.get("/api/v1/control/data/catalog/search?metric=gdp&limit=5")

    assert post.status_code == get.status_code == 200
    assert post.json() == get.json() == canonical.model_dump(mode="json")
    assert [request.resource_kinds for request in calls] == [("case",), ("dataset",)]


def test_capability_search_rejects_audience_drift_as_422(runtime_api_env) -> None:
    body = _search_body(resource_kinds=["case"])
    body["audience"] = "PUBLIC"

    with runtime_api_env["client"] as client:
        response = client.post("/api/v1/control/capabilities/search", json=body)

    assert response.status_code == 422
