"""Predeclare one MiniMax codec-compatibility retry; perform no model call."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime

import httpx

from polisyos.data_forge.domains.academic.batch.reextraction_transport import MODELS

common = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
)


def main() -> int:
    """Read live unauthenticated metadata and append the unchanged-input retry."""
    writer = common.SafeJsonWriter(common.load_credential())
    observation_path = common.EVIDENCE / "provider-metadata-codec-v2.json"
    if sys.argv[1:] == ["--declare"]:
        metadata = json.loads(observation_path.read_text())
        models = metadata["endpoints"]["/v1/models"]["body"]["data"]
        prices = metadata["endpoints"]["/api/pricing"]["body"]["models"]
        identities = {row["id"] for row in models}
        rates = {row["model_id"]: row["usd_per_token"] for row in prices}
        if identities != MODELS or set(rates) != identities or len(prices) != len(identities):
            raise ValueError("live_model_price_identity_mismatch")
        original = common.read_sealed(
            common.EVIDENCE / "2026-09-09-minimax-contract-declaration.json"
        )
        updates = {
            "schema_version": "corr.model_measurement_declaration.v2",
            "declared_at": datetime.now(UTC).isoformat(),
            "metadata_observation": str(observation_path),
            "metadata_observation_hash": common.digest(metadata),
            "price_observed_at": metadata["observed_at"],
            "transport_observation_epoch": "policyos.academic.extraction_attempt.v2",
            "response_codec": "article_extractor._parse_json_object",
            "contract_change": "none; reuse existing owner text codec and typed DTO",
        }
        retry = common.seal({
            **{key: value for key, value in original.items() if key != "content_hash"},
            **updates, "measurement_id": "minimax-codec-v2",
            "supersedes_contract_declaration_hash": original["content_hash"],
            "retry_reason": "adapter codec compatibility; first malformed cause not established",
            "live_pricing_usd_per_token": {
                "input": rates[original["model_id"]], "output": rates[original["model_id"]],
            },
        })
        retry_path = common.EVIDENCE / "2026-09-09-minimax-contract-v2-declaration.json"
        writer(retry_path, retry)
        paths = [retry_path]
        for slug in ("deepseek", "minimax"):
            prior = common.read_sealed(
                common.EVIDENCE / f"2026-09-09-{slug}-pilot-declaration.json"
            )
            current = common.seal({
                **{key: value for key, value in prior.items() if key != "content_hash"},
                **updates, "supersedes_pilot_declaration_hash": prior["content_hash"],
                "contract_probe_required": retry["content_hash"] if slug == "minimax"
                else prior["contract_probe_required"],
                "live_pricing_usd_per_token": {
                    "input": rates[prior["model_id"]], "output": rates[prior["model_id"]],
                },
            })
            path = common.EVIDENCE / f"2026-09-09-{slug}-pilot-v2-declaration.json"
            writer(path, current)
            paths.append(path)
        sys.stdout.write(writer.encode({"declaration_paths": [str(path) for path in paths]}))
        return 0
    metadata = {"observed_at": datetime.now(UTC).isoformat(), "synthetic": False, "endpoints": {}}
    with httpx.Client(timeout=30) as client:
        for route in ("/v1/models", "/api/pricing"):
            response = client.get("https://api.proxy.gonka.gg" + route)
            if response.status_code != 200:
                raise ValueError("live_provider_metadata_unavailable")
            metadata["endpoints"][route] = {
                "url": str(response.url), "status_code": response.status_code,
                "body": response.json(),
            }
    writer.check_payload(metadata)
    writer(observation_path, metadata)
    original_path = common.EVIDENCE / "2026-09-09-minimax-contract-declaration.json"
    original = common.read_sealed(original_path)
    models = metadata["endpoints"]["/v1/models"]["body"]
    pricing = metadata["endpoints"]["/api/pricing"]["body"]
    # Schema-specific extraction is established from the retained live responses.
    sys.stdout.write(writer.encode({
        "metadata_path": str(observation_path), "models": models, "pricing": pricing,
        "original_declaration_hash": original["content_hash"],
        "next_action": "bind observed pricing schema before retry declaration; no model calls",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
