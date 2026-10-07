"""Read exact HTTP cost evidence through the traced callback and a fresh Core reader.

The network boundary is a bounded local HTTP server; provider responses are the only
producer input. The Core readback case manually persists captured callback evidence in
an ``ExperimentState`` root artifact so it tests the existing CAS/RunDetails surface.
It does not claim the ordinary NL pipeline produced the fixture or that a public
RunDetails budget summary exists. The cost fields are operational telemetry, not
invoice or managed-settlement authority.
"""

from __future__ import annotations
import __future__

import ast
import inspect
import os
import textwrap
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web

pytestmark = pytest.mark.integration

TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CELL_ID = "cell-a"
MODEL_NAME = "gpt-4o"


@asynccontextmanager
async def _http_completions(
    payloads: list[bytes],
) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
    """Serve exact completion bytes over a local socket and retain actual requests."""
    requests: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        body = await request.read()
        ordinal = len(requests)
        requests.append(
            {
                "body": body,
                "idempotency_key": request.headers.get("x-idempotency-key"),
                "response_body": payloads[ordinal]
                if ordinal < len(payloads)
                else None,
            }
        )
        if ordinal >= len(payloads):
            return web.Response(status=500, text="unexpected extra provider request")
        return web.Response(
            body=payloads[ordinal],
            content_type="application/json",
            headers={"x-request-id": f"loopback-request-{ordinal + 1}"},
        )

    app = web.Application()
    app.router.add_post("/chat/completions", completion)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    address = runner.addresses[0]
    try:
        yield f"http://127.0.0.1:{address[1]}", requests
    finally:
        await runner.cleanup()


def _completion_payload(
    *,
    cost_lexeme: str | None = None,
    usage_known: bool = True,
) -> bytes:
    """Build raw JSON without parsing or rewriting provider numeric lexemes."""
    usage_fields: list[str] = []
    if usage_known:
        usage_fields.extend(('"prompt_tokens":1', '"completion_tokens":1'))
    if cost_lexeme is not None:
        usage_fields.append(f'"cost_usd":{cost_lexeme}')
    usage = "{" + ",".join(usage_fields) + "}"
    return (
        '{"choices":[{"message":{"content":"loopback answer"}}],'
        f'"model":"{MODEL_NAME}","provider":"loopback-provider","usage":{usage}'
        "}"
    ).encode()


def _install_r1_float_json_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove only the Decimal decoder from the actual gateway response path."""
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

    original = GatewayLLMClient._post_json
    source = textwrap.dedent(inspect.getsource(original))
    tree = ast.parse(source)
    matching_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "loads"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and any(keyword.arg == "parse_float" for keyword in node.keywords)
    ]
    assert len(matching_calls) == 1, "expected one json.loads parse_float call"
    target_call = matching_calls[0]
    target_call.keywords = [
        keyword for keyword in target_call.keywords if keyword.arg != "parse_float"
    ]

    filename = inspect.getsourcefile(original) or "<gateway-client-r1-probe>"
    code = compile(
        ast.fix_missing_locations(tree),
        filename,
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    namespace = dict(original.__globals__)
    exec(code, namespace)  # noqa: S102 - execute the inspected, single-method AST probe
    monkeypatch.setattr(GatewayLLMClient, "_post_json", namespace[original.__name__])


def _traced_client(
    *,
    base_url: str,
    events: list[dict[str, Any]],
    cache_size: int = 0,
) -> Any:
    """Use the registered gateway factory and its real producer callback."""
    from polisyos.scientist.orchestration.llm.factory import (
        GatewayLLMConfig,
        create_traced_gateway_client,
    )

    config = GatewayLLMConfig(
        base_url=base_url,
        api_key="sk-e02-local-monetary-producer",
        timeout_s=5.0,
        max_retries=0,
        default_provider="loopback-provider",
        cache_ttl_s=60.0 if cache_size else 0.0,
        cache_maxsize=cache_size,
        enable_prompt_sanitizer=False,
    )
    client = create_traced_gateway_client(
        model_name=MODEL_NAME,
        provider_hint="loopback-provider",
        run_id="e02-monetary-readback",
        model_variant_id="loopback-variant",
        call_observer=events.append,
        config=config,
    )
    assert client is not None
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "case_name",
        "payloads",
        "prompts",
        "event_statuses",
        "event_origins",
        "summary_status",
        "summary_origin",
    ),
    [
        (
            "reported-zero",
            [_completion_payload(cost_lexeme="0")],
            ["report an actual zero"],
            ["known"],
            ["reported"],
            "known",
            "reported",
        ),
        (
            "positive-underflow",
            [_completion_payload(cost_lexeme="1e-1000")],
            ["retain exact tiny positive cost"],
            ["invalid"],
            ["unknown"],
            "invalid",
            "unknown",
        ),
        (
            "negative-underflow",
            [_completion_payload(cost_lexeme="-1e-1000")],
            ["retain exact tiny negative cost"],
            ["invalid"],
            ["unknown"],
            "invalid",
            "unknown",
        ),
        (
            "negative-cost",
            [_completion_payload(cost_lexeme="-0.02")],
            ["reject a negative provider cost"],
            ["invalid"],
            ["unknown"],
            "invalid",
            "unknown",
        ),
        (
            "missing-unknown",
            [_completion_payload(usage_known=False)],
            ["leave cost and usable token evidence missing"],
            ["missing"],
            ["unknown"],
            "missing",
            "unknown",
        ),
        (
            "reported-and-estimated",
            [
                _completion_payload(cost_lexeme="0.02"),
                _completion_payload(),
            ],
            ["report a cost", "omit reported cost but include usage"],
            ["known", "missing"],
            ["reported", "estimated"],
            "known",
            "mixed",
        ),
    ],
    ids=(
        "reported-zero",
        "positive-underflow",
        "negative-underflow",
        "negative-cost",
        "missing-unknown",
        "reported-and-estimated",
    ),
)
async def test_actual_http_cost_events_keep_typed_meaning(
    case_name: str,
    payloads: list[bytes],
    prompts: list[str],
    event_statuses: list[str],
    event_origins: list[str],
    summary_status: str,
    summary_origin: str,
) -> None:
    """The real HTTP decoder, trace callback, and A budget gate preserve source meaning."""
    from polisyos.runtime.http.services.control.nl_pipeline import _budget_cost_amount
    from polisyos.runtime.http.services.control.response_shapes import (
        _cost_event_evidence,
        _sum_call_events,
    )

    async with _http_completions(payloads) as (base_url, requests):
        events: list[dict[str, Any]] = []
        client = _traced_client(base_url=base_url, events=events)
        responses: list[Any] = []
        try:
            for prompt in prompts:
                responses.append(await client.generate(user=prompt, max_tokens=1))
        finally:
            await client.aclose()

    assert len(requests) == len(payloads), case_name
    assert all(item["idempotency_key"] for item in requests), case_name
    assert len(events) == len(prompts), case_name
    assert len(responses) == len(prompts), case_name

    for event, status, origin in zip(events, event_statuses, event_origins, strict=True):
        # This is deliberately the first semantic assertion: on the pre-adoption
        # f029 source the callback exists but has no typed producer cost status.
        assert event.get("cost_status") == status, (case_name, event)
        assert event.get("cost_origin") == origin, (case_name, event)
        assert event.get("settlement_status") == "unmanaged", (case_name, event)
        assert event.get("provider_call") is True, (case_name, event)
        assert event.get("cache_hit") is False, (case_name, event)
        assert event.get("event_identity"), (case_name, event)
        evidence = _cost_event_evidence(event)
        assert evidence["cost_status"] == status, (case_name, evidence)
        assert evidence["cost_origin"] == origin, (case_name, evidence)

    if case_name in {"positive-underflow", "negative-underflow"}:
        raw_cost = responses[0].raw["usage"]["cost_usd"]
        lexeme = "1e-1000" if case_name == "positive-underflow" else "-1e-1000"
        assert isinstance(raw_cost, Decimal)
        assert raw_cost == Decimal(lexeme)

    summary = _sum_call_events(events)
    assert summary["cost_status"] == summary_status, case_name
    assert summary["cost_origin"] == summary_origin, case_name

    if case_name == "reported-zero":
        assert events[0]["cost_usd"] == 0.0
        assert summary["cost_usd"] == 0.0
        assert _budget_cost_amount(summary) == 0.0
    elif case_name == "reported-and-estimated":
        estimated_event = events[1]
        assert estimated_event["origin_cost_usd"] is None
        assert estimated_event["estimated_cost_usd"] > 0
        assert events[0]["cost_usd"] == 0.02
        assert summary["cost_usd"] == pytest.approx(
            events[0]["cost_usd"] + estimated_event["cost_usd"]
        )
        assert _budget_cost_amount(summary) == summary["cost_usd"]
    else:
        assert summary["cost_usd"] is None
        assert _budget_cost_amount(summary) is None


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("POLISYOS_E02_RAW_COST_DECIMAL_REMOVAL") != "1",
    reason="R1 removal probe runs only with its explicit environment selector",
)
async def test_r1_raw_float_decoder_removal_exposes_underflow_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing Decimal decoding makes the unchanged positive underflow look valid."""
    from polisyos.runtime.http.services.control.response_shapes import _cost_event_evidence

    _install_r1_float_json_decoder(monkeypatch)
    raw_payload = _completion_payload(cost_lexeme="1e-1000")
    async with _http_completions([raw_payload]) as (base_url, requests):
        events: list[dict[str, Any]] = []
        client = _traced_client(base_url=base_url, events=events)
        try:
            response = await client.generate(
                user="retain exact tiny positive cost",
                max_tokens=1,
            )
        finally:
            await client.aclose()

    assert len(requests) == 1
    assert requests[0]["response_body"] == raw_payload
    assert len(events) == 1
    event = events[0]
    assert event.get("provider_call") is True
    assert event.get("cache_hit") is False
    assert event.get("event_identity")
    assert response.raw["usage"]["cost_usd"] == 0.0
    # The invariant expects invalid. With ordinary float decoding the same raw
    # positive lexeme underflows to zero, so this assertion naturally fails.
    assert event.get("cost_status") == "invalid", _cost_event_evidence(event)


@pytest.mark.asyncio
async def test_partial_http_cost_events_survive_owned_core_cas_and_fresh_details_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real partial producer summary survives the existing Core/CAS readback path.

    This is a manual ExperimentState producer for the surface check. The traced
    callback events are real loopback HTTP observations, but this test does not
    claim an ordinary NL request or worker created the state artifact.
    """
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _aggregate_variant_costs,
        _budget_cost_amount,
    )
    from polisyos.runtime.http.services.control.response_shapes import _sum_call_events
    from polisyos.runtime.quality import substrate_registry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import _valid_intake_for_mode

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())

    catalog_root = tmp_path / "monetary-readback-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    curated_root = tmp_path / "monetary-readback-curated"
    curated_root.mkdir()
    monkeypatch.setenv("POLISYOS_CURATED_DIR", curated_root.as_posix())
    monkeypatch.setattr(
        catalog_api,
        "default_acquisition_overlay_path",
        lambda _root: tmp_path / "absent-acquisition-overlay.duckdb",
    )
    default_catalog_paths = substrate_registry.default_substrate_catalog_paths
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(
                default_catalog_paths(root),
                l1_dcat_path=catalog_root / "catalog.duckdb",
            )
            if Path(root).resolve() == repo_root
            else default_catalog_paths(root)
        ),
    )

    async with _http_completions(
        [
            _completion_payload(cost_lexeme="0.02"),
            _completion_payload(usage_known=False),
        ]
    ) as (base_url, requests):
        events: list[dict[str, Any]] = []
        client = _traced_client(base_url=base_url, events=events)
        try:
            await client.generate(user="actual paid HTTP response", max_tokens=1)
            await client.generate(user="actual unknown HTTP response", max_tokens=1)
        finally:
            await client.aclose()

    assert len(requests) == 2
    assert len(events) == 2
    assert [event.get("cost_status") for event in events] == ["known", "missing"]
    assert [event.get("cost_origin") for event in events] == ["reported", "unknown"]
    summary = _sum_call_events(events)
    assert summary["cost_status"] == "missing"
    assert summary["cost_origin"] == "mixed"
    assert summary["cost_usd"] is None

    variant = {
        "cost_usd": summary["cost_usd"],
        "cost_status": summary["cost_status"],
        "cost_origin": summary["cost_origin"],
        "estimated_cost_usd": summary["estimated_cost_usd"],
        "cost_delta_usd": summary["cost_delta_usd"],
        "cost_events": list(summary["cost_events"]),
    }
    assert _budget_cost_amount(variant) is None
    run_cost = _aggregate_variant_costs([variant])
    assert run_cost["cost_usd"] is None
    assert run_cost["cost_status"] == "missing"
    budget_status = "unknown" if run_cost["cost_usd"] is None else "within_budget"

    cas_root = tmp_path / ".polisyos"
    first_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    first_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=first_context),
        allow_fixture_identity=True,
    )
    with TestClient(first_app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Persist a bounded cost summary for fresh inspection.",
                "llm_model": MODEL_NAME,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode(
                        "simulate_only"
                    ).model_dump(mode="json")
                },
            },
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        service = first_app.state._control_service
        state_refs: dict[str, ArtifactRef] = {}
        core_run_ids: dict[str, str] = {}

        def persist_manual_experiment_state(owner_service: Any) -> None:
            admission = owner_service._control_store.current_execution_job_admission()
            job = admission.job
            scope = admission.scope
            assert job.job_id == accepted["job_id"]
            assert scope.status == "established"
            assert scope.tenant_id == TENANT_ID
            assert scope.cell_id == CELL_ID
            with owner_service._install_execution_scope(scope):
                core_run_id, core_context = owner_service._start_generation_run_context(
                    job=job,
                    execution_scope=scope,
                )
                params = {
                    "llm_model_variants": [variant],
                    "llm_cost_events": list(summary["cost_events"]),
                    "llm_cost_usd": summary["cost_usd"],
                    "llm_cost_status": summary["cost_status"],
                    "llm_cost_origin": summary["cost_origin"],
                    "run_cost_usd": run_cost["cost_usd"],
                    "run_cost_status": run_cost["cost_status"],
                    "run_cost_origin": run_cost["cost_origin"],
                    "run_estimated_cost_usd": run_cost["estimated_cost_usd"],
                    "run_budget_usd": 1.0,
                    "run_budget_status": budget_status,
                }
                state = ExperimentState(
                    run_id=str(job.run_id),
                    control_job_id=job.job_id,
                    execution_profile="dev",
                    params=params,
                )
                state_ref = owner_service._put_json_artifact_ref(
                    state.model_dump(mode="json"),
                    kind="scientist.experiment_state",
                    schema_name="polisyos.scientist.orchestration.engine.ExperimentState",
                    schema_version=state.schema_version,
                )
                manifest_ref = owner_service._finish_generation_run_context(
                    job=job,
                    execution_scope=scope,
                    core_run_id=core_run_id,
                    context=core_context,
                    outputs=[state_ref],
                    status="ok",
                )
                progress = {
                    "state": "completed",
                    "phase": "natural_language_run",
                    "status": "monetary_budget_readback_fixture",
                    "execution_band": "candidate",
                    "candidate_computation_status": "completed",
                    "execution_intent_band": "simulate_only",
                    "run_id": job.run_id,
                    "run_budget_status": budget_status,
                    **owner_service._core_run_progress_fields(
                        job=job,
                        core_run_id=core_run_id,
                        manifest_ref=manifest_ref,
                    ),
                }
                owner_service._control_store.complete_job(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    capability_manifest_ref=job.capability_manifest_ref,
                    progress=progress,
                )
                state_refs[job.job_id] = state_ref
                core_run_ids[job.job_id] = core_run_id

        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=lambda _snapshot: persist_manual_experiment_state(service),
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        core_run_id = core_run_ids[accepted["job_id"]]
        expected_state_ref = state_refs[accepted["job_id"]]

    fresh_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    fresh_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=fresh_context),
        allow_fixture_identity=True,
    )
    with TestClient(fresh_app) as fresh_client:
        response = fresh_client.get(f"/api/v1/runs/{core_run_id}")
        assert response.status_code == 200, response.text
        run = response.json()["run"]
        refs = [ArtifactRef.model_validate(item) for item in run["root_artifacts"]]
        state_ref = next(ref for ref in refs if ref.kind == "scientist.experiment_state")
        assert artifact_ref_identity_key(state_ref) == artifact_ref_identity_key(
            expected_state_ref
        )
        assert run["control_job_id"] == completed.job_id
        # Keep the independently bootstrapped RuntimeApiContext open while using
        # its guarded CAS. TestClient shutdown closes the owned runtime guard.
        with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
            assert fresh_context.store.verify(state_ref).ok
            raw = fresh_context.store.get_bytes(state_ref)
    persisted = ExperimentState.model_validate(canon.from_canonical_bytes(raw))
    persisted_params = persisted.params
    assert persisted_params["llm_cost_events"] == list(summary["cost_events"])
    recomputed = _sum_call_events(persisted_params["llm_cost_events"])
    assert recomputed["cost_status"] == persisted_params["llm_cost_status"]
    assert recomputed["cost_origin"] == persisted_params["llm_cost_origin"]
    assert recomputed["cost_usd"] is None
    assert persisted_params["llm_cost_usd"] is None

    persisted_variant = persisted_params["llm_model_variants"][0]
    assert _budget_cost_amount(persisted_variant) is None
    persisted_run_cost = _aggregate_variant_costs(persisted_params["llm_model_variants"])
    assert persisted_run_cost["cost_usd"] is None
    assert persisted_params["run_cost_usd"] is None
    assert persisted_params["run_budget_status"] == "unknown"


@pytest.mark.asyncio
async def test_default_factory_cache_hit_is_one_provider_call_and_a_reuse_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ordinary default-cache hit is visible as a zero-cost reuse callback."""
    from polisyos.runtime.http.services.control.nl_pipeline import _budget_cost_amount
    from polisyos.runtime.http.services.control.response_shapes import (
        _cost_event_evidence,
        _sum_call_events,
    )
    from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "false")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-e02-local-monetary-producer")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PROVIDER", "loopback-provider")
    monkeypatch.delenv("POLISYOS_LLM_FALLBACK_URLS", raising=False)
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRIVACY_SANITIZATION", "false")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "128")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "60")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")

    async with _http_completions([_completion_payload(cost_lexeme="0.02")]) as (
        base_url,
        requests,
    ):
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", base_url)
        events: list[dict[str, Any]] = []
        client = create_traced_gateway_client(
            model_name=MODEL_NAME,
            provider_hint="loopback-provider",
            run_id="e02-default-cache-readback",
            model_variant_id="loopback-variant",
            call_observer=events.append,
        )
        assert client is not None
        try:
            first = await client.generate(user="same deterministic cache prompt", max_tokens=1)
            second = await client.generate(user="same deterministic cache prompt", max_tokens=1)
        finally:
            await client.aclose()

    assert first.content == second.content
    assert len(requests) == 1
    assert len(events) == 2
    reported, reused = events
    assert reported.get("cost_status") == "known"
    assert reported.get("cost_origin") == "reported"
    assert reported.get("provider_call") is True
    assert reported.get("producer_event_id")
    assert reported.get("event_identity") == reported.get("producer_event_id")
    assert reported.get("settlement_status") == "unmanaged"
    assert reused.get("cost_origin") == "reuse"
    assert reused.get("cost_usd") == 0.0
    assert reused.get("cache_hit") is True
    assert reused.get("provider_call") is False
    assert reused.get("reuse_event_id")
    assert reused.get("cache_key")
    assert reused.get("event_identity") == reused.get("reuse_event_id")
    assert reused.get("settlement_status") == "unmanaged"
    reused_evidence = _cost_event_evidence(reused)
    assert reused_evidence["cost_status"] == "known"
    assert reused_evidence["cost_origin"] == "reuse"
    summary = _sum_call_events(events)
    assert summary["cost_status"] == "known"
    assert summary["cost_origin"] == "mixed"
    assert summary["cost_usd"] == 0.02
    assert _budget_cost_amount(summary) == 0.02
