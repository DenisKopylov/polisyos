"""Freeze new model measurements without reselecting the existing six inputs."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime

from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
    MODELS,
    PROVIDER_BASE_URL,
    SafeJsonWriter,
)

common = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
)


def main() -> None:
    """Write separate contract and exact-six pilot declarations before calls."""
    writer = SafeJsonWriter(common.load_credential())
    old = json.loads((common.OLD / "abstract-subset-manifest.json").read_text())
    original_profile = json.loads((common.OLD / "provider-configuration.json").read_text())
    metadata_path = common.EVIDENCE / "provider-metadata.json"
    metadata = json.loads(metadata_path.read_text())
    by_url = {row["url"]: row for row in metadata["endpoints"]}
    if any(row["status_code"] != 200 for row in by_url.values()):
        raise ValueError("provider_metadata_unavailable")
    models = json.loads(by_url[PROVIDER_BASE_URL + "/models"]["body"])["data"]
    pricing = json.loads(by_url["https://api.proxy.gonka.gg/api/pricing"]["body"])
    ids = {row["id"] for row in models}
    rate_ids = {row["model_id"] for row in pricing["models"]}
    if ids != MODELS or rate_ids != ids or len(models) != len(ids):
        raise ValueError("servable_model_or_price_identity_disagreement")
    rates = {row["model_id"]: row["usd_per_token"] for row in pricing["models"]}
    members = old["selected_members"]
    # Independently derive the exact identity/hash/tercile set from the frozen list.
    tuples = {(row["work_id"], row["abstract_content_hash"], row["stratum"]) for row in members}
    inverse = {(key, row["abstract_content_hash"], row["stratum"]) for key, row in
               {row["work_id"]: row for row in members}.items()}
    if tuples != inverse or len(tuples) != 6 or len(members) != 6:
        raise ValueError("frozen_pilot_identity_ambiguous")
    for model in sorted(ids):
        slug = "deepseek" if model.startswith("deepseek") else "minimax"
        basis = {
            "schema_version": "corr.model_measurement_declaration.v1",
            "declared_at": datetime.now(UTC).isoformat(), "synthetic": False,
            "authority_status": "candidate_only", "run_status": "not_started",
            "model_id": model, "base_url": PROVIDER_BASE_URL,
            "api": "chat_completions", "transport": "ordinary_openai_sdk",
            "response_format": {"type": "json_object"}, "temperature": 0.0,
            "max_completion_tokens": 8192, "timeout_seconds": 180,
            "sdk_automatic_retries": 0, "client_connection_limit": 64,
            "metadata_observation": str(metadata_path),
            "metadata_observation_hash": common.digest(metadata),
            "live_pricing_usd_per_token": {"input": rates[model], "output": rates[model]},
            "price_observed_at": metadata["observed_at"],
            "supersedes_model_configuration_digest": original_profile["configuration_digest"],
            "original_six_declaration_path": str(common.OLD / "abstract-subset-manifest.json"),
            "original_six_declaration_digest": old["declaration_digest"],
            "source_path": old["source_path"], "source_open_mode": "read_only",
            "selected_members": members, "selected_identity_hash": common.digest(sorted(tuples)),
            "selection_change": "none; exact frozen work/hash/tercile identities",
            "strata": old["strata"], "full_pass_authorized": False,
        }
        contract = common.seal({
            **basis, "purpose": "one_typed_extraction_contract_probe",
            "execution_members": [members[0]], "concurrency": 1,
            "max_http_attempts": 1, "phase": "extraction",
            "typed_owner": "PolicyArticleExtractor._extract -> ArticleExtractionResult",
        })
        pilot = common.seal({
            **basis, "purpose": "frozen_six_model_comparison_and_token_pilot",
            "execution_members": members, "concurrency": 1, "max_http_attempts": 18,
            "retry_limit": 0, "phases": ["screening", "extraction", "self_verification"],
            "contract_probe_required": contract["content_hash"],
            "agreement_rule": {
                "exclusive_judgment": "same document screening relevant boolean under same prompt",
                "disagreement_union_error_lower_bound": "D/N for complete paired judgments only",
                "pooled_model_document_lower_bound": "D/(2N); no individual model bound",
                "structural_output_difference": (
                    "not necessarily contradiction; separate observation"
                ),
                "gold_standard": None,
            },
            "extrapolation_assumption": (
                "exchangeability within original input-length terciles; no precision guarantee"
            ),
        })
        for suffix, declaration in (("contract", contract), ("pilot", pilot)):
            path = common.EVIDENCE / f"2026-09-09-{slug}-{suffix}-declaration.json"
            writer(path, declaration)
            sys.stdout.write(json.dumps({
                "path": str(path), "content_hash": declaration["content_hash"],
            }) + "\n")


if __name__ == "__main__":
    main()
