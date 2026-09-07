"""Semantic HTTP tests for canonical capability discovery."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import SearchLedger
from polisyos.core.security import tenant_scope
from polisyos.pdc import Layer2S2DesignSearchInput
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control.capability_discovery import (
    CapabilityDiscoveryService,
)
from polisyos.runtime.quality.capability_discovery import CapabilityProviderSearchResult
from polisyos.runtime.quality.workspace.s2_design_search_operation import (
    S2_DESIGN_SEARCH_OPERATION_ID,
    execute_s2_design_search_operation,
)
from tests.unit.runtime.http.test_runtime_api_authz import _AllowOPA, _build_secure_client, _claims


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
    """Missing owners and an unconfigured release must remain distinct negatives."""
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
        "dataset:producer_missing",
        "method:capability_index_release_path_unconfigured",
        "case:case_index_source_invalid_or_scope_missing",
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


def test_case_provider_is_backed_by_canonical_global_index(runtime_api_env) -> None:
    """A real production S2 emission reaches HTTP through a persisted case index."""
    secure_client, cell, identity = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    bearer = "case-index-test-token"
    identity.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"], cell_id=cell.cell_id, jti="case-index-request"
        ),
    )
    headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": runtime_api_env["tenant_a"]}
    context = secure_client.app.state.runtime_container.runtime_api_context
    with tenant_scope(None, tenant_id=runtime_api_env["tenant_a"], cell_id=cell.cell_id):
        produced = execute_s2_design_search_operation(
            operation_id=S2_DESIGN_SEARCH_OPERATION_ID,
            search_input=Layer2S2DesignSearchInput(
                case_id="case:missing-producers",
                intent_ref="intent:employment",
                grammar_ref="grammar:policy",
                instrument_families=("subsidy", "tax", "regulation"),
                parameter_space={"rate": ("low", "high")},
                actor_ref="actor:policy-designer",
                domain="employment",
                objective_refs=("objective:employment",),
                construct_refs=("construct:employment",),
                authority_profile_ref="authority:shadow",
                generated_at=datetime(2026, 9, 7, tzinfo=UTC),
            ),
            store=context.store,
            core_runs_root=context.core_runs_root,
            run_id="R_case_index_producer",
        )
    body = _search_body(resource_kinds=["case"])
    body["search"]["budget"]["match_all"] = True
    with secure_client as client:
        response = client.post("/api/v1/control/capabilities/search", json=body, headers=headers)
        body["search"]["budget"]["match_all"] = False
        body["search"]["construct_refs"] = ["subsidy"]
        body["search"]["allowed_modes"] = ["lexical"]
        body["search"]["query_text"] = "subsidy"
        vocabulary_hit = client.post("/api/v1/control/capabilities/search", json=body, headers=headers)
        body["search"]["query_text"] = "instrument_family_coverage"
        body["search"]["construct_refs"] = ["instrument_family_coverage"]
        field_name_miss = client.post("/api/v1/control/capabilities/search", json=body, headers=headers)
        assert response.status_code == 200
        assert vocabulary_hit.status_code == field_name_miss.status_code == 200
        assert len(vocabulary_hit.json()["results"]) == 1
        assert field_name_miss.json()["results"] == []
        packet = CapabilityDiscoveryResponse.model_validate(response.json())
        assert len(packet.results) == 1
        item = packet.results[0]
        assert item.label == "case:missing-producers"
        assert str(produced.binding_ref.artifact_id) in item.provenance_refs
        assert item.authoritative_for == ()
        assert item.authority_result.state != "admitted_authority"
        assert item.execution_result.state != "executable"
        assert packet.frontier.completeness_status == "recall_unmeasured"
        with tenant_scope(
            None, tenant_id=runtime_api_env["tenant_a"], cell_id=cell.cell_id
        ):
            index = from_canonical_bytes(context.store.get_bytes(item.discovery_result.snapshot_ref))
        assert index["source_artifact_refs"] == [str(produced.binding_ref.artifact_id)]
        assert index["entries"][0]["run_id"] == "R_case_index_producer"
        assert index["authority_owner_ref"] is None
