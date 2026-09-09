"""Exercise C1's real SDK transport and credential-safe artifact boundary."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest


def _owner():
    from polisyos.data_forge.domains.academic.batch import reextraction_transport

    return reextraction_transport


@pytest.mark.asyncio
async def test_sdk_response_is_attributed_and_saved_without_credentials(tmp_path: Path) -> None:
    owner = _owner()
    observed = []

    def respond(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "response-1", "object": "chat.completion", "created": 1,
            "model": "MiniMaxAI/MiniMax-M2.7",
            "choices": [{"index": 0, "message": {"role": "assistant", "content":
                '{"relevant": false}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 7, "total_tokens": 28},
        })

    async with owner.SDKExtractionTransport(
        api_key="private-test-token", base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        prompt_estimator=lambda model, messages: len(messages[0]["content"]),
    ) as transport:
        parsed, usage = await transport.bind({
            "attempt_id": 1, "work_id": "work-a", "phase": "screening",
            "input_hash": "source-a", "campaign_id": "campaign-a",
        }).chat(model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON")
    assert parsed == {"relevant": False}
    assert usage["prompt_tokens"] == 21
    assert observed[0]["response_format"] == {"type": "json_object"}
    record = json.loads((tmp_path / "provider_attempts" / "1.json").read_text())
    assert record["context"]["work_id"] == "work-a"
    assert record["synthetic"] is True and record["authority_status"] == "candidate_only"
    assert record["status"] == "returned"
    assert record["local_prompt_token_estimate"] > 0
    assert "private-test-token" not in json.dumps(record)


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "kind", "retryable"), [
    (429, "upstream_rate_limit", True), (503, "upstream_error", True),
    (401, "authentication_error", False), (400, "request_rejected", False),
])
async def test_provider_error_body_cannot_escape_or_trigger_hidden_retries(
    tmp_path: Path, capsys, status: int, kind: str, retryable: bool,
) -> None:
    owner = _owner()
    attempts = []
    secret = "private-test-token"  # noqa: S105 - synthetic echo used only by MockTransport.

    def respond(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        return httpx.Response(status, json={"error": {"message": secret, "code": secret}})

    async with owner.SDKExtractionTransport(
        api_key=secret, base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as transport:
        with pytest.raises(owner.ExtractionRequestError) as caught:
            await transport.bind({"attempt_id": 1, "work_id": "work-a", "phase": "extraction"}).chat(
                model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON",
            )
    assert caught.value.kind == kind and caught.value.retryable is retryable
    assert attempts == ["/v1/chat/completions"]
    assert secret not in str(caught.value)
    assert secret not in capsys.readouterr().out
    assert all(secret not in p.read_text() for p in tmp_path.rglob("*.json"))


@pytest.mark.asyncio
async def test_malformed_output_is_retained_as_failure_without_contract_relaxation(
    tmp_path: Path,
) -> None:
    owner = _owner()

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "response-1", "object": "chat.completion", "created": 1,
            "model": "MiniMaxAI/MiniMax-M2.7",
            "choices": [{"index": 0, "message": {"role": "assistant", "content":
                "not JSON"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 7, "total_tokens": 28},
        })

    async with owner.SDKExtractionTransport(
        api_key="private-test-token", base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as transport:
        with pytest.raises(owner.ExtractionRequestError, match="malformed_output"):
            await transport.bind({"attempt_id": 1}).chat(
                model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON",
            )
    record = json.loads((tmp_path / "provider_attempts" / "1.json").read_text())
    assert record["status"] == "failed" and record["error_kind"] == "malformed_output"
    assert record["usage"]["completion_tokens"] == 7


def test_secret_echo_refuses_before_file_creation(tmp_path: Path) -> None:
    owner = _owner()
    writer = owner.SafeJsonWriter("private-test-token")
    with pytest.raises(ValueError, match="credential_echo_refused"):
        writer(tmp_path / "forbidden.json", {"nested": ["private-test-token"]})
    assert not (tmp_path / "forbidden.json").exists()


def test_model_and_endpoint_cannot_silently_change(tmp_path: Path) -> None:
    owner = _owner()
    with pytest.raises(ValueError, match="provider_endpoint_not_declared"):
        owner.SDKExtractionTransport(
            api_key="private-test-token", base_url="https://api.openai.com/v1",
            model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
            timeout_seconds=5, max_completion_tokens=8192,
        )


@pytest.mark.asyncio
async def test_decoded_provider_secret_never_reaches_the_owner(tmp_path: Path, capsys) -> None:
    owner = _owner()
    secret = "private-test-token"  # noqa: S105 - synthetic adversarial echo.
    escaped = "".join("\\u" + format(ord(character), "04x") for character in secret)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "synthetic-escaped-echo", "object": "chat.completion", "created": 1,
            "model": "MiniMaxAI/MiniMax-M2.7",
            "choices": [{"index": 0, "message": {"role": "assistant", "content":
                '{"sample_size":"' + escaped + '","causal_claims":[]}'},
                "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 7, "total_tokens": 28},
        })

    async with owner.SDKExtractionTransport(
        api_key=secret, base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as transport:
        with pytest.raises(owner.ExtractionRequestError, match="unsafe_response_refused"):
            await transport.bind({"attempt_id": "encoded-echo"}).chat(
                model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON",
            )
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert all(secret not in p.read_text() for p in tmp_path.rglob("*.json"))


@pytest.mark.asyncio
async def test_reported_model_mismatch_cannot_enter_model_comparison(tmp_path: Path) -> None:
    owner = _owner()
    reported_model = "deepseek-ai/DeepSeek-V4-Flash-0731"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "synthetic-model-mismatch", "object": "chat.completion", "created": 1,
            "model": reported_model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content":
                '{"relevant":false}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 7, "total_tokens": 28},
        })

    async with owner.SDKExtractionTransport(
        api_key="private-test-token", base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as transport:
        with pytest.raises(owner.ExtractionRequestError, match="reported_model_mismatch"):
            await transport.bind({"attempt_id": "model-mismatch"}).chat(
                model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON",
            )
    record = json.loads((tmp_path / "provider_attempts/model-mismatch.json").read_text())
    assert record["reported_model_id"] == reported_model
    assert record["model_id"] == "MiniMaxAI/MiniMax-M2.7"
    assert record["usage"]["total_tokens"] == 28


@pytest.mark.asyncio
async def test_existing_owner_codec_accepts_wrapped_json(tmp_path: Path) -> None:
    owner = _owner()

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "synthetic-wrapper", "object": "chat.completion", "created": 1,
            "model": "MiniMaxAI/MiniMax-M2.7",
            "choices": [{"index": 0, "message": {"role": "assistant", "content":
                '```json\n{"causal_claims": []}\n```'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 7, "total_tokens": 28},
        })

    async with owner.SDKExtractionTransport(
        api_key="private-test-token", base_url="https://api.proxy.gonka.gg/v1",
        model_id="MiniMaxAI/MiniMax-M2.7", output_root=tmp_path,
        timeout_seconds=5, max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as transport:
        parsed, _ = await transport.bind({"attempt_id": "wrapped"}).chat(
            model="MiniMaxAI/MiniMax-M2.7", temperature=0.0, prompt="Return JSON",
        )
    assert parsed == {"causal_claims": []}
