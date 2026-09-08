"""Re-extract a declared held-abstract subset through the existing rich owner.

This candidate pipeline never supplies an adjudication or publishes a snapshot.
Graph ingestion and exact/family/contested reassembly retain their existing owners.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import duckdb

from polisyos.data_forge.domains.academic.batch.article_extractor import (
    ExtractorStats,
    GonkaChatClient,
    PolicyArticleExtractor,
    _to_work_record,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph
from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.ir.analytics.literature import ArticleExtractionResult

SUBSET_STAGE = "declared_abstract_subset"
SUBSET_SELECTION_RULE = (
    "nonblank-held-abstract; length-terciles; two lowest fixed salted ID hashes "
    "per tercile; no outcome-based replacement"
)


class ArticleChatClient(Protocol):
    """Existing rich-extractor transport, with explicit synthetic provenance."""

    synthetic: bool

    async def chat(
        self, *, model: str, temperature: float, prompt: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return the provider's parsed content and unchanged usage."""
        ...


def _digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _reconcile_strata(
    con: duckdb.DuckDBPyConnection,
    basis: list[tuple[str, str | None]],
    manifest: Mapping[str, Any],
) -> None:
    """Recompute the complete input frame and both independent stratum partitions."""
    if manifest.get("selection_rule") != SUBSET_SELECTION_RULE:
        raise ValueError("subset_stratum_rule_unknown")
    lengths = {
        key: len(value.strip()) for key, value in basis if isinstance(value, str) and value.strip()
    }
    ordered = sorted(lengths, key=lambda key: (lengths[key], key))
    groups = [
        ordered[len(ordered) * index // 3 : len(ordered) * (index + 1) // 3] for index in range(3)
    ]
    sql_partition = con.execute(r"""
        WITH eligible AS (
            SELECT id, length(regexp_replace(abstract, '^\s+|\s+$', '', 'g')) AS size
            FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract, '\S')
        ), ranked AS (
            SELECT id, row_number() OVER (ORDER BY size,id) AS position,
                   count(*) OVER () AS denominator FROM eligible
        )
        SELECT id, band FROM ranked CROSS JOIN range(3) bands(band)
        WHERE position > floor(denominator * band / 3)
          AND position <= floor(denominator * (band+1) / 3)
    """).fetchall()
    python_partition = {(key, index) for index, group in enumerate(groups) for key in group}
    if python_partition != set(sql_partition) or len(sql_partition) != len(ordered):
        raise ValueError("subset_stratum_independent_partition_mismatch")
    expected_strata = [
        {
            "stratum": index,
            "member_count": len(group),
            "member_identity_digest": _digest(sorted(group)),
        }
        for index, group in enumerate(groups)
    ]
    if manifest["strata"] != expected_strata or sum(
        row["member_count"] for row in manifest["strata"]
    ) != len(ordered):
        raise ValueError("subset_stratum_denominator_mismatch")
    expected = [
        (key, index)
        for index, group in enumerate(groups)
        for key in sorted(
            group,
            key=lambda key: hashlib.sha256(
                f"corr-held-abstract-pilot.v1|{key}".encode()
            ).hexdigest(),
        )[:2]
    ]
    if any(len(group) < 2 for group in groups) or expected != [
        (member["work_id"], member["stratum"]) for member in manifest["selected_members"]
    ]:
        raise ValueError("subset_stratum_selected_identity_mismatch")
    if any(
        member["abstract_length"] != lengths[member["work_id"]]
        for member in manifest["selected_members"]
    ):
        raise ValueError("subset_stratum_input_length_mismatch")


def _load_declared_works(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    unsigned = {key: value for key, value in manifest.items() if key != "declaration_digest"}
    if _digest(unsigned) != manifest.get("declaration_digest"):
        raise ValueError("subset_declaration_digest_mismatch")
    if (
        manifest.get("schema_version") != "corr.abstract_subset_declaration.v1"
        or manifest.get("scope") != "subset"
        or not isinstance(manifest.get("synthetic"), bool)
        or manifest.get("source_open_mode") != "read_only"
        or manifest.get("source_table") != "ac_works"
        or manifest.get("provider_run_status") != "not_started"
    ):
        raise ValueError("subset_declaration_invalid")
    declared_at = datetime.fromisoformat(manifest["declared_at"])
    if declared_at.tzinfo is None or declared_at > datetime.now(UTC):
        raise ValueError("subset_declaration_not_before_execution")
    members = manifest["selected_members"]
    ids = [member["work_id"] for member in members]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("subset_identity_denominator_invalid")
    if len(ids) >= manifest["eligible_count"]:
        raise ValueError("full_reextraction_not_authorized")
    limits = manifest["execution_limits"]
    if (
        limits["concurrency"] != 1
        or limits["transport_attempts_per_call"] != 1
        or not 0 < limits["max_phase_calls"] <= 18
        or not 0 < limits["per_call_timeout_seconds"] <= 120
    ):
        raise ValueError("subset_execution_limits_invalid")
    with duckdb.connect(str(manifest["source_path"]), read_only=True) as con:
        basis = con.execute("SELECT id,abstract FROM ac_works ORDER BY id").fetchall()
        if _digest(basis) != manifest["source_row_basis_digest"]:
            raise ValueError("subset_source_basis_mismatch")
        if len(basis) != manifest["complete_work_count"]:
            raise ValueError("subset_source_denominator_mismatch")
        if len({row[0] for row in basis}) != len(basis) or any(
            not isinstance(row[0], str) or (row[1] is not None and not isinstance(row[1], str))
            for row in basis
        ):
            raise ValueError("subset_source_identity_or_type_ambiguous")
        eligible = {key for key, text in basis if isinstance(text, str) and text.strip()}
        independent = {
            row[0]
            for row in con.execute(
                "SELECT id FROM ac_works WHERE abstract IS NOT NULL "
                "AND regexp_matches(abstract, '\\S')"
            ).fetchall()
        }
        if eligible != independent or len(eligible) != manifest["eligible_count"]:
            raise ValueError("subset_eligible_denominator_mismatch")
        _reconcile_strata(con, basis, manifest)
        columns = [row[0] for row in con.execute("DESCRIBE ac_works").fetchall()]
        works = []
        for member in members:
            if member.get("scope") != "subset" or member.get("synthetic") != manifest["synthetic"]:
                raise ValueError("subset_member_provenance_mismatch")
            matches = con.execute(
                "SELECT * FROM ac_works WHERE id=?", [member["work_id"]]
            ).fetchall()
            if len(matches) != 1 or member["work_id"] not in eligible:
                raise ValueError("subset_source_identity_mismatch")
            work = dict(zip(columns, matches[0], strict=True))
            text = work["abstract"]
            if (
                "sha256:" + hashlib.sha256(text.encode()).hexdigest()
                != member["abstract_content_hash"]
            ):
                raise ValueError("subset_source_abstract_mismatch")
            works.append(work)
    return works


class _MeasuredClient:
    def __init__(
        self, client: ArticleChatClient, *, root: Path, synthetic: bool, limits: Mapping[str, int]
    ) -> None:
        self.client = client
        self.root = root
        self.synthetic = synthetic
        self.limits = limits
        self.phase = "unassigned"
        self.work_id = ""
        self.calls: list[dict[str, Any]] = []
        self.failed = False

    async def chat(
        self, *, model: str, temperature: float, prompt: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if len(self.calls) >= self.limits["max_phase_calls"]:
            self.failed = True
            raise RuntimeError("subset_phase_call_budget_exhausted")
        started = time.monotonic()
        event = {
            "synthetic": self.synthetic,
            "scope": "subset",
            "authority_status": "candidate_only",
            "work_id": self.work_id,
            "phase": self.phase,
            "model_id": model,
            "prompt_hash": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
            "provider_cost_usd": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "cached_prompt_tokens": None,
            "status": "failed",
            "error_class": None,
        }
        parsed: dict[str, Any] | None = None
        usage: dict[str, Any] = {}
        try:
            async with asyncio.timeout(self.limits["per_call_timeout_seconds"]):
                parsed, usage = await self.client.chat(
                    model=model, temperature=temperature, prompt=prompt
                )
            event.update(
                {
                    "status": "returned",
                    "provider_cost_usd": usage.get("total_cost_usd"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cached_prompt_tokens": (
                        usage["prompt_tokens_details"].get("cached_tokens")
                        if isinstance(usage.get("prompt_tokens_details"), dict)
                        else None
                    ),
                }
            )
            return parsed, usage
        except Exception as exc:
            # Provider messages can contain credentials. Persist the type, never that message.
            self.failed = True
            event["error_class"] = type(exc).__name__
            raise
        finally:
            event["elapsed_seconds"] = time.monotonic() - started
            artifact = self.root / "provider_calls" / f"{len(self.calls):04d}.json"
            _write_new(artifact, {**event, "response": parsed, "usage": usage})
            event["artifact_path"] = str(artifact)
            event["artifact_hash"] = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.calls.append(event)


class _SubsetExtractor(PolicyArticleExtractor):
    """Observe real owner phases without recognizing prompt text as a phase proxy."""

    async def _screen(self, abstract: str, stats: ExtractorStats) -> bool:
        self._gonka.phase = "screening"
        return await super()._screen(abstract, stats)

    async def _extract(
        self, work: dict[str, Any], text: str, source_kind: str, stats: ExtractorStats
    ) -> ArticleExtractionResult | None:
        self._gonka.phase = "extraction"
        return await super()._extract(work, text, source_kind, stats)

    async def _self_verify(
        self,
        result: ArticleExtractionResult,
        evidence_bundle: dict[str, Any],
        stats: ExtractorStats,
    ) -> ArticleExtractionResult:
        self._gonka.phase = "self_verification"
        return await super()._self_verify(result, evidence_bundle, stats)


def _estimate(
    manifest: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    *,
    synthetic: bool,
) -> dict[str, Any]:
    completed = all(
        row["status"] in {"extracted", "screening_rejected", "no_claim_artifact"}
        for row in outcomes
    )
    measured = not synthetic and completed and all(row["status"] == "returned" for row in calls)
    projection = {"elapsed_seconds_serial": 0.0, "prompt_tokens": 0.0, "completion_tokens": 0.0}
    projected_phase_calls: dict[str, float] = {}
    observed_phase_calls: dict[str, int] = {}
    for call in calls:
        observed_phase_calls[call["phase"]] = observed_phase_calls.get(call["phase"], 0) + 1
    for stratum in manifest["strata"]:
        member_ids = {
            member["work_id"]
            for member in manifest["selected_members"]
            if member["stratum"] == stratum["stratum"]
        }
        if not member_ids:
            measured = False
            continue
        weight = stratum["member_count"] / len(member_ids)
        selected_calls = [call for call in calls if call["work_id"] in member_ids]
        for call in selected_calls:
            projected_phase_calls[call["phase"]] = (
                projected_phase_calls.get(call["phase"], 0.0) + weight
            )
        projection["elapsed_seconds_serial"] += weight * sum(
            call["elapsed_seconds"] for call in selected_calls
        )
        for key in ("prompt_tokens", "completion_tokens"):
            if any(call[key] is None for call in selected_calls):
                measured = False
            projection[key] += weight * sum(call[key] or 0 for call in selected_calls)
    return {
        "provider_time_status": "measured"
        if measured
        else ("not_established_synthetic" if synthetic else "not_established_incomplete"),
        "projection": projection if measured else None,
        "observed_phase_calls": observed_phase_calls,
        "projected_phase_calls": projected_phase_calls if measured else None,
        "uncertainty": (
            "Small outcome-blind pilot; no precision guarantee; serial provider time "
            "excludes full-pass overhead and parallel throughput."
        ),
        "provider_invoice_cost_usd": None,
        "self_verification_authority": "not_independent_entailment",
    }


async def run_abstract_reextraction(
    *,
    manifest_path: Path,
    output_root: Path,
    client: ArticleChatClient,
    model_id: str,
    provider_configuration_path: Path | None = None,
) -> dict[str, Any]:
    """Persist one predeclared subset, phase accounting, and current-rule graph refusal.

    Args:
        manifest_path: Dated declaration bound to the held source bytes and exact subset.
        output_root: New output directory; never the held snapshot or an existing run.
        client: Existing compatible transport, or explicitly synthetic test transport.
        model_id: Explicit provider model, unchanged across all phases.

    Returns:
        Persisted candidate-only run report; no publication or promotion receipt.
    """
    manifest = json.loads(manifest_path.read_text())
    source = Path(manifest["source_path"]).resolve()
    root = output_root.resolve()
    owner_root = Path(__file__).resolve().parents[6]
    held_root = (owner_root / "production_data").resolve()
    synthetic = bool(manifest["synthetic"] or type(client) is not GonkaChatClient)
    if (
        source.is_relative_to(root)
        or root.exists()
        or root.is_relative_to(held_root)
        or (not synthetic and not root.is_relative_to((owner_root / ".tmp").resolve()))
    ):
        raise ValueError("subset_output_must_be_new_lane_owned_and_separate")
    works = _load_declared_works(manifest)
    configuration = None
    if provider_configuration_path is not None:
        configuration = _provider_configuration(provider_configuration_path, manifest, model_id)
    elif not manifest["synthetic"] and getattr(client, "synthetic", True) is False:
        raise ValueError("live_provider_configuration_required")
    if not synthetic:
        expected_transport = {
            "_url": configuration["base_url"].rstrip("/") + "/chat/completions",
            "_max_retries": configuration["transport_attempts_per_call"],
            "_max_completion_tokens": configuration["max_completion_tokens"],
            "_disable_json_mode": False,
        }
        if any(getattr(client, key) != value for key, value in expected_transport.items()) or (
            client._timeout.total != configuration["per_call_timeout_seconds"]
        ):
            raise ValueError("provider_transport_configuration_mismatch")
    root.mkdir(parents=True)
    run_id = manifest["declaration_digest"].removeprefix("sha256:")
    provenance = {
        "synthetic": synthetic,
        "scope": "subset",
        "authority_status": "candidate_only",
        "subset_declaration_digest": manifest["declaration_digest"],
        "provider_configuration_digest": configuration["configuration_digest"]
        if configuration
        else None,
    }
    measured = _MeasuredClient(
        client, root=root, synthetic=synthetic, limits=manifest["execution_limits"]
    )
    extractor = _SubsetExtractor(
        screening_model=model_id,
        extraction_model=model_id,
        max_concurrent=1,
        canonizer=VariableCanonizer(),
        gonka_client=measured,
        fulltext_timeout_seconds=3,
        cache_path=root / "processed.jsonl",
        preserve_source_presence=True,
        cache_provenance=provenance,
        resolved_texts={
            work["id"]: {"text": work["abstract"], "source_kind": "abstract_fallback"}
            for work in works
        },
    )
    records = []
    outcomes = []
    for index, work in enumerate(works):
        outcome = {
            "work_id": work["id"],
            "synthetic": synthetic,
            "scope": "subset",
            "authority_status": "candidate_only",
        }
        if measured.failed:
            outcome["status"] = "not_attempted_provider_failed"
            outcomes.append(outcome)
            continue
        measured.work_id = work["id"]
        stats = ExtractorStats()
        try:
            result = await extractor._process_one(work, stats)
        except Exception as exc:
            outcome.update({"status": "provider_failed", "error_class": type(exc).__name__})
            outcomes.append(outcome)
            continue
        if result is None:
            outcome["status"] = (
                "screening_rejected" if stats.screening_rejected else "no_claim_artifact"
            )
        else:
            outcome["status"] = "extracted"
            record = _to_work_record(
                result=result,
                raw_work=work,
                topic_ids=[],
                topic_display_names=[],
                run_id=run_id,
                pass_name=SUBSET_STAGE,
            )
            record.metadata.update(
                {
                    "synthetic": synthetic,
                    "scope": "subset",
                    "authority_status": "candidate_only",
                    "subset_declaration_digest": manifest["declaration_digest"],
                    "source_abstract_content_hash": manifest["selected_members"][index][
                        "abstract_content_hash"
                    ],
                    "model_id": model_id,
                    "self_verification_authority": "not_independent_entailment",
                    "legacy_extractor_cost_fields_status": (
                        "not_established_provider_usd_not_supplied"
                    ),
                }
            )
            record.causal_claims = [
                transport.model_copy(
                    update={
                        "occurrence": {
                            **transport.occurrence,
                            **provenance,
                            "source_provenance": provenance,
                        }
                    }
                )
                for transport in record.causal_claims
            ]
            records.append(record)
            path = root / "works" / f"{index:04d}.json"
            _write_new(path, {**outcome, "record": record.model_dump(mode="json")})
            outcome["artifact_path"] = str(path)
        outcomes.append(outcome)
    config = AcademicBatchConfig(snapshot_root=root, run_id=run_id, pass_name=SUBSET_STAGE)
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    load_graph(
        records=records,
        db_path=config.db_path,
        run_id=run_id,
        pass_name=SUBSET_STAGE,
        config_json=json.dumps(provenance),
    )
    run_edge_synthesize(config, source_provenance=provenance)
    report = {
        "schema_version": "policyos.academic.abstract_reextraction.v1",
        **provenance,
        "model_id": model_id,
        "graph_path": str(config.db_path),
        "work_outcomes": outcomes,
        "phase_calls": measured.calls,
        "full_pass_estimate": _estimate(manifest, outcomes, measured.calls, synthetic=synthetic),
    }
    report["price_from_observed_usage"] = _price(configuration, measured.calls, synthetic=synthetic)
    if report["full_pass_estimate"]["projection"] is not None:
        projection = report["full_pass_estimate"]["projection"]
        rates = configuration["pricing"]["per_million_tokens"]
        projection["uncached_upper_price_usd"] = (
            projection["prompt_tokens"] * rates["input"]
            + projection["completion_tokens"] * rates["output"]
        ) / 1_000_000
    report["source_pins"] = {
        str(path.relative_to(Path(__file__).resolve().parents[6])): "sha256:"
        + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            Path(__file__).resolve(),
            Path(__file__).with_name("article_extractor.py"),
            *Path(__file__).with_name("prompts").rglob("*.py"),
            Path(__file__).with_name("graph_builder.py"),
            Path(__file__).with_name("edge_synthesize.py"),
        )
    }
    _write_new(root / "run.json", report)
    return report


def _provider_configuration(
    path: Path, manifest: Mapping[str, Any], model_id: str
) -> dict[str, Any]:
    configuration = json.loads(path.read_text())
    unsigned = {key: value for key, value in configuration.items() if key != "configuration_digest"}
    if _digest(unsigned) != configuration.get("configuration_digest"):
        raise ValueError("provider_configuration_digest_mismatch")
    if (
        configuration["schema_version"] != "corr.abstract_provider_configuration.v1"
        or configuration["subset_declaration_digest"] != manifest["declaration_digest"]
        or configuration["model_id"] != model_id
        or configuration["scope"] != "subset"
        or configuration["provider_run_status"] != "not_started"
        or configuration["api"] != "chat_completions"
        or configuration["json_mode"] is not True
        or type(configuration["max_completion_tokens"]) is not int
        or not 0 < configuration["max_completion_tokens"] <= 4096
    ):
        raise ValueError("provider_configuration_scope_mismatch")
    if any(configuration[key] != value for key, value in manifest["execution_limits"].items()):
        raise ValueError("provider_configuration_limits_mismatch")
    date = datetime.fromisoformat(configuration["declared_at"])
    if date.tzinfo is None or date > datetime.now(UTC):
        raise ValueError("provider_configuration_not_before_execution")
    return configuration


def _price(
    configuration: Mapping[str, Any] | None, calls: list[dict[str, Any]], *, synthetic: bool
) -> dict[str, Any]:
    result = {"status": "not_established", "usd": None, "provider_invoice": False}
    if (
        synthetic
        or configuration is None
        or any(
            row["status"] != "returned"
            or row["prompt_tokens"] is None
            or row["completion_tokens"] is None
            for row in calls
        )
    ):
        return result
    rates = configuration["pricing"]["per_million_tokens"]
    missing_cache = any(row.get("cached_prompt_tokens") is None for row in calls)
    result.update(
        status="uncached_upper_estimate" if missing_cache else "calculated_from_usage",
        usd=sum(
            (row["prompt_tokens"] - (row.get("cached_prompt_tokens") or 0)) * rates["input"]
            + (row.get("cached_prompt_tokens") or 0) * rates["cached_input"]
            + row["completion_tokens"] * rates["output"]
            for row in calls
        )
        / 1_000_000,
    )
    return result


async def _run_cli(args: argparse.Namespace) -> dict[str, Any]:
    # The environment is the credential surface; no credential enters an artifact.
    configuration = _provider_configuration(
        args.provider_configuration,
        json.loads(args.manifest.read_text()),
        json.loads(args.provider_configuration.read_text())["model_id"],
    )
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("provider_credential_absent")
    async with GonkaChatClient(
        api_key=key,
        base_url=configuration["base_url"],
        max_concurrent=configuration["concurrency"],
        rate_limit_rps=1,
        max_retries=configuration["transport_attempts_per_call"],
        timeout_seconds=configuration["per_call_timeout_seconds"],
        max_completion_tokens=configuration["max_completion_tokens"],
    ) as client:
        return await run_abstract_reextraction(
            manifest_path=args.manifest,
            output_root=args.output_root,
            client=client,
            model_id=configuration["model_id"],
            provider_configuration_path=args.provider_configuration,
        )


def main() -> int:
    """Run a predeclared subset with credentials supplied only by the environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--provider-configuration", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.write(json.dumps(asyncio.run(_run_cli(args)), ensure_ascii=False) + "\n")
    return 0


__all__ = ["ArticleChatClient", "run_abstract_reextraction"]

if __name__ == "__main__":
    raise SystemExit(main())
