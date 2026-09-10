"""Recompute the SDK codec strangle through real requests on a synthetic transport."""

from __future__ import annotations

import argparse
import asyncio
import functools
import hashlib
import importlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx

from polisyos.data_forge.domains.academic.batch import article_extractor as owner
from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
    ExtractionRequestError,
    SDKExtractionTransport,
)

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
CASES = {
    "ordinary": '{"causal_claims":[]}',
    "wrapped": '```json\n{"causal_claims":[]}\n```',
    "malformed": "a deliberately invalid response",
}


async def recompute(*, remove_property: bool) -> dict:
    """Run the complete declared codec vocabulary and fail on behavioral drift."""
    common = importlib.import_module(PREFIX + "capacity_common")
    original = owner._parse_json_object
    calls = []

    @functools.wraps(original)
    def codec(text: str) -> dict | None:
        calls.append(text)
        if not remove_property:
            return original(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    scratch = Path(".tmp/corr-c1-capacity/codec-strangle")
    scratch.mkdir(parents=True, exist_ok=True)
    results = {}
    observed = {}
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        root = Path(directory)
        for identity, content in CASES.items():
            def respond(request: httpx.Request, text: str = content) -> httpx.Response:
                del request
                return httpx.Response(200, json={
                    "id": "synthetic-codec", "object": "chat.completion", "created": 1,
                    "model": "MiniMaxAI/MiniMax-M2.7",
                    "choices": [{"index": 0, "message": {
                        "role": "assistant", "content": text,
                    }, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                })

            async with SDKExtractionTransport(
                api_key="synthetic-codec-private-token", base_url="https://api.proxy.gonka.gg/v1",
                model_id="MiniMaxAI/MiniMax-M2.7", output_root=root,
                timeout_seconds=5, max_completion_tokens=8192,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
            ) as transport:
                with patch.object(owner, "_parse_json_object", codec):
                    try:
                        parsed, _ = await transport.bind({
                            "attempt_id": identity, "synthetic": True,
                        }).chat(model="MiniMaxAI/MiniMax-M2.7", temperature=0, prompt="synthetic")
                        results[identity] = (
                            "accepted" if parsed == {"causal_claims": []} else "drift"
                        )
                    except ExtractionRequestError as exc:
                        results[identity] = exc.kind
        for path in (root / "provider_attempts").glob("*.json"):
            record = json.loads(path.read_text())
            if record["synthetic"] is not True or record["authority_status"] != "candidate_only":
                raise ValueError("codec_provenance_mismatch")
            observed[path.stem] = record
        if set(observed) != set(CASES) or set(results) != set(CASES):
            raise ValueError("codec_complete_identity_denominator")
        if len(calls) != len(CASES) or set(calls) != set(CASES.values()):
            raise ValueError("codec_owner_dispatch")
        expected = {"ordinary": "accepted", "wrapped": "accepted", "malformed": "malformed_output"}
        print(json.dumps({"synthetic": True, "actual": results, "expected": expected}))  # noqa: T201
        if results != expected:
            raise ValueError("codec_default_property_removed")
    source_paths = [Path(__file__), Path(owner.__file__)]
    transport_module = importlib.import_module(
        "polisyos.data_forge.domains.academic.batch.reextraction_transport"
    )
    source_paths.append(Path(transport_module.__file__))
    return common.seal({
        "schema_version": "corr.sdk_codec_strangle_receipt.v1",
        "emitted_at": datetime.now(UTC).isoformat(), "synthetic": True,
        "authority_status": "candidate_measurement", "authority_granted": False,
        "legacy_path": "SDK adapter independent json.loads codec",
        "default_path": original.__module__ + "." + original.__qualname__,
        "default_flipped": results == expected and len(calls) == len(CASES),
        "complete_fixture_denominator": list(CASES),
        "fixture_hash": common.digest({"synthetic": True, "cases": CASES}),
        "results": results, "provider_observations": observed,
        "sources": {str(p.resolve().relative_to(Path.cwd())):
                    "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        "scope": "codec default only; no extraction correctness or authority claim",
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remove-property", action="store_true")
    args = parser.parse_args()
    receipt = asyncio.run(recompute(remove_property=args.remove_property))
    if args.output:
        common = importlib.import_module(PREFIX + "capacity_common")
        common.SafeJsonWriter(common.load_credential())(args.output, receipt)


if __name__ == "__main__":
    main()
