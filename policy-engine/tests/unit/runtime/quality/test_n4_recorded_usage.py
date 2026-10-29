"""Legacy ambiguity and new quantity evidence stay distinct through real consumers."""

from __future__ import annotations

import asyncio
import copy
import json
from contextlib import contextmanager
from decimal import Decimal
from itertools import product

import pytest

from polisyos.core.llm import parse_llm_usage_quantity, replay_llm_usage_payload
from polisyos.core.llm.response import _recorded_usage_payload, extract_llm_response_data
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality._n4_usage_capture import capture_call_usage
from polisyos.runtime.quality.design_generation import LLMGenerationCall, RecordingLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from tests._helpers.acquisition_chain import load_served_wdi_generation_recording
from tests._helpers.controlled_candidate_profile import (
    ControlledCandidateGateway,
    _current_compiler_problem,
)
from tools.quality.validation import check_layer3_gy_design_generation_contract as contract
from tools.quality.validation.generation_replay_input import (
    build_replay_capture,
    read_replay_capture,
    response_from_call_payload,
)

_LEGACY = [
    None,
    {},
    {"prompt_tokens": 0, "completion_tokens": 0},
    {"prompt_tokens": 2, "completion_tokens": 0},
    {"prompt_tokens": 2, "completion_tokens": 1},
    {"prompt_tokens": 0, "completion_tokens": 0, "usage_status": "known"},
]
_LIVE = [
    (None, "missing"),
    ({}, "missing"),
    ({"prompt_tokens": None, "completion_tokens": 1}, "invalid"),
    ({"prompt_tokens": 2}, "missing"),
    ({"prompt_tokens": "bad", "completion_tokens": 1}, "invalid"),
    ({"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": "bad"}, "invalid"),
    ({"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": None}, "invalid"),
    ({"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": True}, "invalid"),
    ({"input_tokens": 2, "output_tokens": 1}, "known"),
    ({"prompt_tokens": None, "input_tokens": 2, "completion_tokens": 1}, "invalid"),
    ({"prompt_tokens": 2, "completion_tokens": None, "output_tokens": 1}, "invalid"),
    ({"prompt_tokens": 0, "completion_tokens": 0}, "known"),
    ({"prompt_tokens": 2, "completion_tokens": 1}, "known"),
]


def _gateway_response(usage):
    payload = {"choices": [{"message": {"content": "{}"}}]}
    if usage is not None:
        payload["usage"] = usage
    return _gateway_payload(payload)


def _gateway_payload(payload):
    return GatewayLLMClient(
        base_url="http://127.0.0.1:1/v1", api_key="", model="moonshotai/Kimi-K2.6"
    )._parse_completion_payload(payload)


class _Span:
    def set_attribute(self, *args):
        pass

    def set_status(self, *args):
        pass

    def record_exception(self, *args):
        pass


class _Tracer:
    @contextmanager
    def start_as_current_span(self, *args, **kwargs):
        yield _Span()


class _Metrics:
    def record_llm_call(self, **kwargs):
        pass


def _capture(usage, tmp_path):
    payload = {"choices": [{"message": {"content": "{}"}}]}
    if usage is not None:
        payload["usage"] = usage
    return _capture_payload(payload, tmp_path)


def _capture_payload(payload, tmp_path):
    class Provider:
        async def generate(self, **kwargs):
            return _gateway_payload(payload)

    model = "moonshotai/Kimi-K2.6"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(tmp_path / "actual-capture-ledger.json"),
    )
    traced = TracedLLMClient(
        Provider(),
        model_name=model,
        provider_name="declared-fixture",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    recorder = RecordingLLMClient(traced, model_id=model)
    with capture_call_usage() as captured:
        asyncio.run(recorder.generate(user="new declared provider fixture input"))
    return recorder.calls, build_replay_capture(
        metadata={
            "model_id": model,
            "recorded_at": "fixture",
            "design_problem_id": "fixture",
            "domain": "fixture",
        },
        calls=captured.calls,
        evidence=captured.evidence,
    )


def _settle_gateway_payload(payload, tmp_path):
    """Run a parsed Gateway response through Core and the normal settlement path."""

    class Provider:
        async def generate(self, **kwargs):
            return _gateway_payload(payload)

    model = "moonshotai/Kimi-K2.6"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(tmp_path / "gateway-selection-ledger.json"),
    )
    traced = TracedLLMClient(
        Provider(),
        model_name=model,
        provider_name="declared-fixture",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    return asyncio.run(traced.generate(user="usage container selection fixture"))


@pytest.mark.parametrize("usage", _LEGACY)
def test_every_unqualified_legacy_counter_quantity_stays_unknown(usage):
    before = copy.deepcopy(usage)
    normalized = _recorded_usage_payload(usage)
    assert extract_llm_response_data({"usage": normalized}).usage_status == "missing"
    assert usage == before
    recording = copy.deepcopy(load_served_wdi_generation_recording())
    recording["responses"][0]["usage"] = usage
    response = asyncio.run(contract.RecordedGenerationReplayClient(recording).generate())
    assert extract_llm_response_data(response).usage_status == "missing"


@pytest.mark.parametrize(("usage", "status"), _LIVE)
def test_one_quantity_interpretation_across_live_gateway_and_versioned_replay(
    usage, status, tmp_path
):
    live = _gateway_response(usage)
    assert extract_llm_response_data(live).usage_status == status
    calls, captured = _capture(usage, tmp_path)
    assert captured.call_usage[0].observation.provider_usage_status == status
    replayed = asyncio.run(contract.RecordedGenerationReplayClient(captured).generate())
    assert extract_llm_response_data(replayed).usage_status == status
    # The product call DTO stays unchanged; availability is an exact sidecar fact.
    assert "usage_status" not in calls[0].model_dump(mode="json")


@pytest.mark.parametrize("usage", _LEGACY)
def test_default_legacy_http_fixture_cannot_upgrade_counter_magnitudes(usage):
    recording = copy.deepcopy(load_served_wdi_generation_recording())
    recording["responses"][0]["usage"] = usage
    recording["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in recording.items() if key != "recording_content_hash"}
    )
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=_current_compiler_problem(recording))

        async def run():
            client = GatewayLLMClient(
                base_url=gateway.base_url, api_key="", model=recording["model_id"], max_retries=0
            )
            try:
                return await client.generate(user="legacy fixture")
            finally:
                await client.aclose()

        response = asyncio.run(run())
    assert extract_llm_response_data(response).usage_status == "missing"


@pytest.mark.parametrize(
    ("known", "unknown", "pair"),
    [
        ({"prompt_tokens": 2, "completion_tokens": 0}, {"prompt_tokens": 2}, (2, 0)),
        (
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 0},
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": "bad"},
            (2, 1),
        ),
    ],
)
def test_actual_recorder_has_indistinguishable_counter_preimages_but_new_evidence_distinguishes(
    known, unknown, pair, tmp_path
):
    first_calls, first = _capture(known, tmp_path)
    second_calls, second = _capture(unknown, tmp_path)
    assert (first_calls[0].prompt_tokens, first_calls[0].completion_tokens) == pair
    assert (second_calls[0].prompt_tokens, second_calls[0].completion_tokens) == pair
    assert first.call_usage[0].observation.provider_usage_status == "known"
    assert second.call_usage[0].observation.provider_usage_status in {"missing", "invalid"}
    for call in (first_calls[0], second_calls[0]):
        legacy = {
            "model_id": "fixture-model",
            "responses": [response_from_call_payload(call.model_dump(mode="json"))],
        }
        assert (
            extract_llm_response_data(
                asyncio.run(contract.RecordedGenerationReplayClient(legacy).generate())
            ).usage_status
            == "missing"
        )


def test_versioned_capture_roundtrip_binds_every_call_and_old_loader_refuses_its_root(tmp_path):
    _calls, captured = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    path = tmp_path / "capture-v2.json"
    path.write_text(captured.model_dump_json())
    assert read_replay_capture(path) == captured
    old_path = tmp_path / contract.RECORDING_FIXTURE_PATH
    old_path.parent.mkdir(parents=True)
    old_path.write_bytes(path.read_bytes())
    with pytest.raises(RuntimeError, match="gy_n4_recordings_missing"):
        contract._load_recordings(tmp_path)
    with pytest.raises(ValueError, match="unknown_format"):
        contract.RecordedGenerationReplayClient(json.loads(path.read_bytes()))


@pytest.mark.parametrize("mutation", ["prompt", "response", "evidence_missing", "future_version"])
def test_rehashed_outer_envelope_cannot_hide_a_wrong_call_or_unknown_version(mutation, tmp_path):
    _calls, captured = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    payload = captured.model_dump(mode="json")
    if mutation == "prompt":
        payload["source_calls"][0]["prompt_hash"] = "sha256:" + "f" * 64
    elif mutation == "response":
        payload["source_calls"][0]["raw_llm_response"] = "different body"
    elif mutation == "evidence_missing":
        payload["call_usage"] = []
    else:
        payload["schema_version"] = "policyos.testing.design_generation_replay_input.future"
    payload["content_hash"] = gy_content_hash(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )
    with pytest.raises(ValueError):
        type(captured).model_validate(payload)


def test_fresh_legacy_reader_keeps_exact_call_shape_and_content_hash(tmp_path):
    calls, _captured = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    legacy = calls[0].model_dump(mode="json")
    assert "usage_status" not in legacy
    path = tmp_path / "legacy-call.json"
    path.write_text(json.dumps(legacy))
    fresh = LLMGenerationCall.model_validate_json(path.read_bytes())
    assert fresh.model_dump(mode="json") == legacy
    assert gy_content_hash(fresh.model_dump(mode="json")) == gy_content_hash(legacy)


@pytest.mark.parametrize(
    "change", ["missing_component", "invalid_total", "missing_status", "different_known_quantity"]
)
def test_availability_marker_cannot_survive_falsifying_its_actual_usage_basis(change, tmp_path):
    _calls, captured = _capture(
        {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}, tmp_path
    )
    payload = captured.model_dump(mode="json")
    observation = payload["call_usage"][0]["observation"]
    if change == "missing_component":
        observation["provider_usage"].pop("completion_tokens")
    elif change == "invalid_total":
        observation["provider_usage"]["total_tokens"] = "bad"
    elif change == "different_known_quantity":
        observation["provider_usage"]["prompt_tokens"] = 200
    else:
        observation.pop("provider_usage_status")
    payload["content_hash"] = gy_content_hash(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )
    with pytest.raises(ValueError):
        type(captured).model_validate(payload)


def test_replay_admission_freezes_all_input_quantities_against_caller_aliases(tmp_path):
    _calls, envelope = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    admitted = contract.RecordedGenerationReplayClient(envelope)
    envelope.call_usage[0].observation.provider_usage["completion_tokens"] = 900
    response = asyncio.run(admitted.generate())
    assert extract_llm_response_data(response).completion_tokens == 1
    # The same mutation before a second admission is a content mismatch, not new evidence.
    with pytest.raises(ValueError, match=r"content_mismatch|observation_mismatch"):
        contract.RecordedGenerationReplayClient(envelope)
    legacy = copy.deepcopy(load_served_wdi_generation_recording())
    raw = legacy["responses"][0]["raw_response"]
    reader = contract.RecordedGenerationReplayClient(legacy)
    legacy["responses"][0]["raw_response"] = "different after admission"
    assert asyncio.run(reader.generate()).content == raw


def test_new_replay_estimates_current_tariff_and_does_not_reuse_a_historical_reported_amount(
    tmp_path,
):
    from polisyos.core.observability.pricing import estimate_llm_cost_usd

    configured = Decimal(
        str(
            estimate_llm_cost_usd(
                model="moonshotai/Kimi-K2.6", prompt_tokens=2, completion_tokens=1
            )
        )
    )
    reported = configured + Decimal("1")
    _calls, envelope = _capture(
        {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": float(reported)}, tmp_path
    )
    assert envelope.call_usage[0].observation.settlement.cost_origin == "reported"
    replay = contract.RecordedGenerationReplayClient(envelope)
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(tmp_path / "current-replay-ledger.json"),
    )
    current = TracedLLMClient(
        replay,
        model_name="moonshotai/Kimi-K2.6",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    response = asyncio.run(current.generate(user="new software replay"))
    expected = Decimal(
        str(
            estimate_llm_cost_usd(
                model="moonshotai/Kimi-K2.6", prompt_tokens=2, completion_tokens=1
            )
        )
    )
    assert response.settlement.event.cost_origin == "estimated"
    assert response.settlement.event.amount == expected
    assert response.settlement.event.amount != Decimal(str(float(reported)))


def test_legacy_historical_price_cannot_become_a_current_reported_provider_event(tmp_path):
    recording = copy.deepcopy(load_served_wdi_generation_recording())
    recording["responses"][0]["usage"] = {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "cost_usd": 0.25,
    }
    replay = contract.RecordedGenerationReplayClient(recording)
    model = recording["model_id"]
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(tmp_path / "legacy-price.json"),
    )
    current = TracedLLMClient(
        replay,
        model_name=model,
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    response = asyncio.run(current.generate(user="historical amount is not a new provider report"))
    assert response.settlement.event.cost_origin == "unknown"
    assert response.settlement.event.amount is None


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_pair"),
    [
        (
            {"choices": [{"message": {"content": "{}"}}]},
            "missing",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
            "missing",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
            "invalid",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": None,
                "prompt_tokens": 2,
                "completion_tokens": 1,
            },
            "missing",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2},
                "completion_tokens": 0,
            },
            "missing",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {
                    "input_tokens": 2,
                    "output_tokens": 1,
                },
                "prompt_tokens": 900,
                "completion_tokens": 900,
            },
            "known",
            (2, 1),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "prompt_tokens": 2,
                "completion_tokens": 1,
            },
            "known",
            (2, 1),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            },
            "known",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {
                    "prompt_tokens": None,
                    "input_tokens": 2,
                    "completion_tokens": 1,
                },
                "prompt_tokens": 900,
            },
            "invalid",
            (0, 0),
        ),
        (
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": None,
                    "output_tokens": 1,
                },
                "completion_tokens": 900,
            },
            "invalid",
            (0, 0),
        ),
    ],
)
def test_gateway_uses_one_selected_usage_container_through_core_and_settlement(
    payload, expected_status, expected_pair, tmp_path
):
    settled = _settle_gateway_payload(payload, tmp_path)
    data = extract_llm_response_data(settled)

    assert data.usage_status == expected_status
    assert (data.prompt_tokens, data.completion_tokens) == expected_pair
    if expected_status in {"missing", "invalid"}:
        assert settled.settlement.event.cost_origin == "unknown"
        assert settled.settlement.event.amount is None


@pytest.mark.parametrize(
    ("usage", "expected_basis", "raw_total"),
    [
        (
            {"prompt_tokens": 2, "completion_tokens": 1},
            "derived",
            3,
        ),
        (
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 0},
            "reported",
            0,
        ),
    ],
)
def test_recorder_keeps_historical_total_fallback_separate_from_raw_usage(
    usage, expected_basis, raw_total, tmp_path
):
    calls, capture = _capture(usage, tmp_path)
    call = calls[0]
    observation = capture.call_usage[0].observation

    assert (call.prompt_tokens, call.completion_tokens, call.total_tokens) == (2, 1, 3)
    assert observation.provider_usage_status == "known"
    assert observation.provider_total_basis == expected_basis
    if expected_basis == "reported":
        assert observation.provider_usage["total_tokens"] == raw_total
    else:
        assert "total_tokens" not in observation.provider_usage
        assert raw_total == 3


def test_joint_call_and_usage_rehash_is_candidate_consistency_not_original_provider_attestation(
    tmp_path,
):
    _calls, capture = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    payload = capture.model_dump(mode="json")
    call = payload["source_calls"][0]
    evidence = payload["call_usage"][0]
    observation = evidence["observation"]

    # The envelope's internal joins can be re-established after coordinated
    # edits. This candidate-only reader intentionally cannot prove the original
    # provider exchange or turn these supplied bytes into historical authority.
    call["prompt_tokens"] = 200
    call["total_tokens"] = 201
    observation["provider_usage"]["prompt_tokens"] = 200
    evidence["call_content_hash"] = gy_content_hash(call)
    payload["content_hash"] = gy_content_hash(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )

    admitted = type(capture).model_validate(payload)
    assert admitted.usage_for(0)["prompt_tokens"] == 200
    assert admitted.call_usage[0].capture_execution_provenance == "not_established_by_this_artifact"
    assert (
        admitted.call_usage[0].observation.settlement.payload_digest
        == capture.call_usage[0].observation.settlement.payload_digest
    )


_ABSENT_COMPONENT = object()
_COMPONENT_VALUES = (_ABSENT_COMPONENT, None, 0, 2, "3", "bad", True, -1, [], {})


def test_canonical_replay_projection_preserves_quantity_and_component_presence_for_complete_matrix():
    # Cartesian component values plus availability markers cover the whole
    # declared three-component representation; aliases are exercised in both
    # spellings. This is an algebraic identity, not a copied expected parser.
    names = (("prompt_tokens", "completion_tokens"), ("input_tokens", "output_tokens"))
    statuses = (_ABSENT_COMPONENT, "known", "missing", "invalid", "bad")
    for (prompt_name, completion_name), values, status in product(
        names, product(_COMPONENT_VALUES, repeat=3), statuses
    ):
        source = {
            name: value
            for name, value in zip(
                (prompt_name, completion_name, "total_tokens"), values, strict=True
            )
            if value is not _ABSENT_COMPONENT
        }
        if status is not _ABSENT_COMPONENT:
            source["usage_status"] = status
        expected_presence = {
            name
            for name, value in zip(
                ("prompt_tokens", "completion_tokens", "total_tokens"), values, strict=True
            )
            if value is not _ABSENT_COMPONENT
        }
        original = parse_llm_usage_quantity(source)
        wire = replay_llm_usage_payload(source)
        actual_presence = set(wire) - {"usage_status"}
        assert actual_presence == expected_presence, source
        assert parse_llm_usage_quantity(wire) == original, source
        unknown_wire = replay_llm_usage_payload(source, unknown_provenance=True)
        unknown = parse_llm_usage_quantity(unknown_wire)
        assert set(unknown_wire) - {"usage_status"} == expected_presence
        assert unknown.status == ("invalid" if original.status == "invalid" else "missing")
        assert (unknown.prompt_tokens, unknown.completion_tokens) == (
            original.prompt_tokens,
            original.completion_tokens,
        )
        if original.total_basis == "reported":
            assert (unknown.total_tokens, unknown.total_basis) == (
                original.total_tokens,
                original.total_basis,
            )
        else:
            assert unknown.total_tokens is None and unknown.total_basis == "unavailable"


_ROUNDTRIP_WIRE_CASES = [
    ({}, set()),
    ({"usage": None}, set()),
    ({"usage": None, "prompt_tokens": 9, "completion_tokens": 9}, set()),
    ({"usage": []}, set()),
    ({"usage": {}}, set()),
    ({"usage": {"prompt_tokens": 2}}, {"prompt_tokens"}),
    ({"usage": {"completion_tokens": 1}}, {"completion_tokens"}),
    ({"usage": {"total_tokens": 3}}, {"total_tokens"}),
    (
        {"usage": {"prompt_tokens": None, "completion_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": None, "input_tokens": 2, "completion_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": None, "output_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": "bad", "completion_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 0, "completion_tokens": 0}},
        {"prompt_tokens", "completion_tokens"},
    ),
    ({"usage": {"input_tokens": "2", "output_tokens": 1}}, {"prompt_tokens", "completion_tokens"}),
    (
        {"usage": {"prompt_tokens": 0, "input_tokens": 9, "completion_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": 1}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 0}},
        {"prompt_tokens", "completion_tokens", "total_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": "bad"}},
        {"prompt_tokens", "completion_tokens", "total_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": 1, "usage_status": "missing"}},
        {"prompt_tokens", "completion_tokens"},
    ),
    (
        {"usage": {"prompt_tokens": 2, "completion_tokens": 1, "usage_status": "invalid"}},
        {"prompt_tokens", "completion_tokens"},
    ),
    ({"prompt_tokens": 2, "completion_tokens": 1}, {"prompt_tokens", "completion_tokens"}),
]


@pytest.mark.parametrize(
    ("body", "expected_presence"),
    _ROUNDTRIP_WIRE_CASES,
    ids=[f"wire-{index:02}" for index in range(len(_ROUNDTRIP_WIRE_CASES))],
)
def test_capture_to_both_replay_wire_stages_preserves_canonical_quantity_and_presence(
    body, expected_presence, tmp_path
):
    payload = {"choices": [{"message": {"content": "{}"}}], **body}
    original = parse_llm_usage_quantity(payload)
    _calls, capture = _capture_payload(payload, tmp_path)
    first_wire = capture.usage_for(0)
    assert set(first_wire) - {"usage_status"} == expected_presence
    assert parse_llm_usage_quantity(first_wire) == original
    replayed = asyncio.run(contract.RecordedGenerationReplayClient(capture).generate())
    assert set(replayed.raw["usage"]) - {"usage_status"} == expected_presence
    assert parse_llm_usage_quantity(replayed.raw) == original
    assert extract_llm_response_data(replayed).usage_status == original.status
    live = _gateway_payload(payload)
    assert (
        replayed.usage.prompt_tokens,
        replayed.usage.completion_tokens,
        replayed.usage.total_tokens,
    ) == (live.usage.prompt_tokens, live.usage.completion_tokens, live.usage.total_tokens)


def test_unqualified_complete_capture_keeps_presence_without_reifying_a_derived_total(tmp_path):
    _calls, capture = _capture({"prompt_tokens": 2, "completion_tokens": 1}, tmp_path)
    body = capture.model_dump(mode="json")
    body["call_usage"][0]["observation"]["settlement"]["ack_status"] = "unmanaged"
    body["content_hash"] = gy_content_hash(
        {key: value for key, value in body.items() if key != "content_hash"}
    )
    unqualified = type(capture).model_validate(body)
    first = unqualified.usage_for(0)
    assert first == {"prompt_tokens": 2, "completion_tokens": 1, "usage_status": "missing"}
    replayed = asyncio.run(contract.RecordedGenerationReplayClient(unqualified).generate())
    assert replayed.raw["usage"] == first
    assert parse_llm_usage_quantity(replayed.raw).status == "missing"
    assert extract_llm_response_data(replayed).usage_status == "missing"
