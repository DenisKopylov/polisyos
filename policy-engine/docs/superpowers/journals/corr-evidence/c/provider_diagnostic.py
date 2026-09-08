"""Diagnose one exact failed screening request without emitting provider message text."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import aiohttp

from polisyos.data_forge.domains.academic.batch.abstract_reextraction import (
    _load_declared_works,
    _provider_configuration,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    SCREENING_PROMPT,
    GonkaChatClient,
)

ROOT = Path("docs/superpowers/journals/corr-evidence/c")
ALLOWED = {
    "insufficient_quota", "invalid_api_key", "rate_limit_exceeded", "model_not_found",
    "invalid_request_error", "context_length_exceeded", "unsupported_parameter",
    "unsupported_value", "tokens", "requests", "server_error", "authentication_error",
    "response_format", "max_tokens", "max_completion_tokens", "temperature", "model",
}


def safe(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and value in ALLOWED else "unrecognized_redacted"


async def main() -> None:
    declaration = json.loads((ROOT / "provider-diagnostic-declaration.json").read_text())
    unsigned = {k: v for k, v in declaration.items() if k != "content_hash"}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if expected != declaration["content_hash"] or datetime.fromisoformat(
        declaration["declared_at"]
    ) >= datetime.now(UTC):
        raise ValueError("diagnostic_declaration_invalid")
    manifest = json.loads((ROOT / "abstract-subset-manifest.json").read_text())
    work = _load_declared_works(manifest)[0]
    config_path = ROOT / "provider-configuration.json"
    configuration = json.loads(config_path.read_text())
    config = _provider_configuration(config_path, manifest, configuration["model_id"])
    if config["configuration_digest"] != declaration["same_model_configuration"]:
        raise ValueError("diagnostic_provider_configuration_changed")
    prompt = SCREENING_PROMPT.format(abstract=work["abstract"][:6000])
    digest = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
    if digest != declaration["same_first_input_prompt_hash"]:
        raise ValueError("diagnostic_prompt_changed")
    attempts = []
    original = aiohttp.ClientSession._request

    async def observe(
        self: aiohttp.ClientSession, method: str, url: object,
        *args: object, **kwargs: object,
    ) -> aiohttp.ClientResponse:
        if attempts or method != "POST" or str(url) != config["base_url"] + "/chat/completions":
            raise ValueError("diagnostic_http_scope_exceeded")
        attempt = {"status": None, "provider_error_code": None, "provider_error_type": None,
                   "provider_error_param": None, "usage": None}
        attempts.append(attempt)
        response = await original(self, method, url, *args, **kwargs)
        attempt["status"] = response.status
        try:
            data = await response.json(content_type=None)
        except (ValueError, aiohttp.ClientError):
            attempt["json_status"] = "ambiguous"
        else:
            error = data.get("error", {}) if isinstance(data, dict) else {}
            if isinstance(error, dict):
                for key in ("code", "type", "param"):
                    attempt["provider_error_" + key] = safe(error.get(key))
            usage = data.get("usage") if isinstance(data, dict) else None
            if isinstance(usage, dict):
                attempt["usage"] = {
                    key: value for key, value in usage.items()
                    if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                    and type(value) is int and value >= 0
                }
        return response

    started = time.monotonic()
    error_class = None
    with patch.object(aiohttp.ClientSession, "_request", observe):
        async with GonkaChatClient(
            api_key=os.environ["OPENAI_API_KEY"], base_url=config["base_url"],
            max_concurrent=1, rate_limit_rps=1, max_retries=1,
            timeout_seconds=120, max_completion_tokens=config["max_completion_tokens"],
        ) as client:
            try:
                await client.chat(model=config["model_id"], temperature=0.0, prompt=prompt)
            except Exception as exc:
                error_class = type(exc).__name__
    sys.stdout.write(json.dumps({
        "synthetic": False, "purpose": declaration["purpose"],
        "declaration_hash": declaration["content_hash"], "prompt_hash": digest,
        "http_attempts": attempts, "transport_error_class": error_class,
        "elapsed_seconds": time.monotonic() - started,
        "cumulative_actual_attempts": 1 + len(attempts),
        "prior_pilot_unchanged": True,
    }, sort_keys=True) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
