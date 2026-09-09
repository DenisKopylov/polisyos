"""Bound C1 calls through the ordinary OpenAI SDK without leaking credentials.

The campaign owns durable admission, retry and extraction semantics. This adapter
owns one immutable attempt, safe transport observations, and candidate response
bytes. It does not change the rich extractor's typed contract.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

if TYPE_CHECKING:
    from pathlib import Path

PROVIDER_BASE_URL = "https://api.proxy.gonka.gg/v1"
MODELS = frozenset({"deepseek-ai/DeepSeek-V4-Flash-0731", "MiniMaxAI/MiniMax-M2.7"})


class ExtractionRequestError(RuntimeError):
    """Sanitized failure class; original provider messages are never retained."""

    def __init__(self, kind: str, retryable: bool, status_code: int | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.retryable = retryable
        self.status_code = status_code


class SafeJsonWriter:
    """Reject credential echoes before creating any output file."""

    def __init__(self, credential: str) -> None:
        if not credential:
            raise ValueError("provider_credential_absent")
        self._credential = credential

    def encode(self, payload: object) -> str:
        """Serialize once and scan complete bytes before any output side effect."""
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        # Scan the decoded JSON too: escaped provider strings cannot hide a key.
        if self._credential in text or self._credential in repr(payload):
            raise ValueError("credential_echo_refused")
        if re.search(r"sk-[A-Za-z0-9_-]{12,}", text):
            raise ValueError("credential_pattern_refused")
        return text + "\n"

    def check_payload(self, payload: object) -> None:
        """Apply the same guard to metadata about to enter SQLite or stdout."""
        self.encode(payload)

    def __call__(self, path: Path, payload: object) -> None:
        """Write one complete immutable JSON artifact with durable bytes."""
        text = self.encode(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic publication prevents interruption from exposing partial JSON.
        temporary = path.with_name(path.name + ".pending")
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_provider_json_key")
        result[key] = value
    return result


class _BoundClient:
    def __init__(self, transport: SDKExtractionTransport, context: dict[str, Any]) -> None:
        self.transport = transport
        self.context = context
        self.synthetic = transport.synthetic or context.get("synthetic") is True

    async def chat(
        self, *, model: str, temperature: float, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return await self.transport._attempt(self.context, model, temperature, prompt)


class SDKExtractionTransport:
    """Make one SDK request per reserved campaign attempt, with no hidden retries."""

    def __init__(
        self, *, api_key: str, base_url: str, model_id: str, output_root: Path,
        timeout_seconds: float, max_completion_tokens: int,
        http_client: httpx.AsyncClient | None = None,
        prompt_estimator: Callable[[str, list[dict[str, str]]], int] | None = None,
    ) -> None:
        if base_url.rstrip("/") != PROVIDER_BASE_URL:
            raise ValueError("provider_endpoint_not_declared")
        if model_id not in MODELS:
            raise ValueError("provider_model_not_declared")
        if not 0 < timeout_seconds <= 300 or not 0 < max_completion_tokens <= 16384:
            raise ValueError("provider_request_limits_invalid")
        self.model_id = model_id
        self.root = output_root
        self.max_completion_tokens = max_completion_tokens
        self.prompt_estimator = prompt_estimator
        self.safe_write_json = SafeJsonWriter(api_key)
        self.check_payload = self.safe_write_json.check_payload
        self.synthetic = http_client is not None
        for name in ("openai", "httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds,
            max_retries=0, http_client=http_client or httpx.AsyncClient(
                limits=httpx.Limits(max_connections=64, max_keepalive_connections=64),
            ),
        )

    async def __aenter__(self) -> SDKExtractionTransport:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.close()

    def bind(self, context: object) -> _BoundClient:
        """Freeze the caller's reserved work/phase/attempt attribution."""
        if is_dataclass(context) and not isinstance(context, type):
            value = asdict(context)
        elif isinstance(context, Mapping):
            value = dict(context)
        else:
            raise ValueError("provider_context_must_be_immutable_projection")
        self.check_payload(value)
        attempt_id = str(value.get("attempt_id", "")).removeprefix("sha256:")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", attempt_id):
            raise ValueError("provider_attempt_identity_invalid")
        return _BoundClient(self, value)

    async def _attempt(
        self, context: dict[str, Any], model: str, temperature: float, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if model != self.model_id or temperature != 0.0:
            raise ValueError("provider_model_or_temperature_changed")
        self.check_payload(prompt)
        messages = [{"role": "user", "content": prompt}]
        estimator_started = time.monotonic()
        estimated = self.prompt_estimator(model, messages) if self.prompt_estimator else None
        observation: dict[str, Any] = {
            "schema_version": "policyos.academic.extraction_attempt.v1",
            "synthetic": self.synthetic or context.get("synthetic") is True,
            "authority_status": "candidate_only", "context": context,
            "model_id": model, "base_url": PROVIDER_BASE_URL,
            "prompt_hash": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
            "local_prompt_token_estimate": estimated,
            "local_estimator": "injected_repository_estimator" if self.prompt_estimator else None,
            "estimator_elapsed_seconds": time.monotonic() - estimator_started,
            "status": "failed", "error_kind": None, "retryable": False,
            "status_code": None, "usage": None, "response_content_hash": None,
        }
        parsed: dict[str, Any] | None = None
        failure: ExtractionRequestError | None = None
        started = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=model, messages=messages, temperature=temperature,
                response_format={"type": "json_object"}, max_tokens=self.max_completion_tokens,
            )
            # Check the complete returned envelope before any parser or owner log.
            self.check_payload(response.model_dump(mode="json"))
            observation["status_code"] = 200
            usage = response.usage.model_dump(mode="json") if response.usage else {}
            observation["usage"] = {
                key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if type(usage.get(key)) is int and usage[key] >= 0
            }
            if not response.choices:
                raise ExtractionRequestError("malformed_output", True, 200)
            choice = response.choices[0]
            observation["finish_reason"] = choice.finish_reason
            content = choice.message.content
            observation["response_content_hash"] = (
                "sha256:" + hashlib.sha256(content.encode()).hexdigest()
                if isinstance(content, str) else None
            )
            if choice.finish_reason == "length":
                raise ExtractionRequestError("output_truncated", False, 200)
            try:
                value = json.loads(content or "", object_pairs_hook=_unique_object)
                if not isinstance(value, dict):
                    raise ValueError("provider_json_object_required")
                parsed = value
            except (ValueError, TypeError):
                raise ExtractionRequestError("malformed_output", True, 200) from None
            observation["status"] = "returned"
            observation["parsed_response_hash"] = "sha256:" + hashlib.sha256(
                json.dumps(
                    parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode()
            ).hexdigest()
        except ExtractionRequestError as exc:
            failure = exc
        except APITimeoutError:
            failure = ExtractionRequestError("timeout", True)
        except APIConnectionError:
            failure = ExtractionRequestError("connection_error", True)
        except APIStatusError as exc:
            status = exc.status_code
            kind = (
                "upstream_rate_limit" if status == 429 else
                "upstream_error" if status >= 500 else
                "authentication_error" if status in {401, 403} else "request_rejected"
            )
            failure = ExtractionRequestError(kind, status == 429 or status >= 500, status)
        except ValueError:
            # A credential echo cannot be recorded, even as raw model output.
            observation["response_content_hash"] = None
            failure = ExtractionRequestError("unsafe_response_refused", False)
        finally:
            observation["transport_elapsed_seconds"] = time.monotonic() - started
            if failure is not None:
                observation.update(
                    error_kind=failure.kind, retryable=failure.retryable,
                    status_code=failure.status_code,
                )
            name = str(context["attempt_id"]).removeprefix("sha256:") + ".json"
            self.safe_write_json(self.root / "provider_attempts" / name, observation)
        if failure is not None:
            raise failure from None
        if parsed is None:
            raise ExtractionRequestError("malformed_output", True, 200)
        return parsed, observation["usage"] or {}


__all__ = ["ExtractionRequestError", "SDKExtractionTransport", "SafeJsonWriter"]
