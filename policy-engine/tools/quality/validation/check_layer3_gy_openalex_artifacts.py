#!/usr/bin/env python3
"""Validate or regenerate GY-K OpenAlex span-grounded L2 artifacts."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import asyncio
import json
import os
import sys
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb

from tools.lib.timing import run_timed_entrypoint

FAMILY_ID = "policy-design-case-layer3-gy-openalex-artifacts"
SOURCE_FAMILY_ID = "policy-design-case-layer3-gy-openalex-source-artifacts"
HISTORY_FAMILY_ID = "policy-design-case-layer3-gy-openalex-history-artifacts"
HISTORICAL_OUTPUTS_SHA256 = {
    "architecture/policy_design_case/layer3_gy_openalex_accuracy_report.json": "sha256:f0a638647aebc33e327c989b816529cc6b0f750f081dab533dc3611ad47f8c68",
    "architecture/policy_design_case/layer3_gy_openalex_skg_ingest_records.json": "sha256:c45e37e16c539787acaca9b44f0afed6fb3ed77b941f2ded78e40c3fa51239de",
}
CONFIG_PATH = "architecture/policy_design_case/layer3_gy_openalex_provider_config.json"
GOLD_PATH = "architecture/policy_design_case/layer3_gy_openalex_claim_span_gold.json"
ACCURACY_PATH = "architecture/policy_design_case/layer3_gy_openalex_accuracy_report_v2.json"
INGEST_PATH = "architecture/policy_design_case/layer3_gy_openalex_skg_ingest_records_v2.json"
OUTPUTS = [ACCURACY_PATH, INGEST_PATH]

REAL_AGENT_MODEL_ID = "MiniMaxAI/MiniMax-M2.7"
REAL_AGENT_MODEL_VARIANT_ID = "layer3-gy-span-support-judge-v1"
HELD_OUT_ACCURACY_CASES: tuple[dict[str, Any], ...] = (
    {
        "label_id": "openalex-heldout-credit-sme-contribution-positive",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W2169693233",
        "title": (
            "The Impact of Firm and Entrepreneurial Characteristics on Access to Debt "
            "Finance by SMEs in King Williams' Town, South Africa"
        ),
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "SMEs contribute to economic growth, employment, and poverty alleviation "
            "in South Africa."
        ),
        "treatment_or_cause": "SMEs",
        "effect": "economic growth, employment, and poverty alleviation",
        "claim_direction": "positive",
        "gold_span_text": (
            "SMEs contribute positively to economic growth, employment and poverty "
            "alleviation in South Africa."
        ),
        "expected_supported": True,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-credit-rct-negative",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W2169693233",
        "title": (
            "The Impact of Firm and Entrepreneurial Characteristics on Access to Debt "
            "Finance by SMEs in King Williams' Town, South Africa"
        ),
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": "The South Africa SME study was a randomized controlled trial.",
        "treatment_or_cause": "random assignment",
        "effect": "access to debt finance by SMEs",
        "claim_direction": "mixed",
        "gold_span_text": "Data was collected throughself-administered questionnaire in a survey.",
        "expected_supported": False,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-collateral-credit-positive",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W3123109680",
        "title": "Collateralization, Bank Loan Rates, and Monitoring",
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "A legal reform that reduced collateral values led the bank to raise "
            "interest rates, tighten credit limits, and reduce monitoring."
        ),
        "treatment_or_cause": "legal reform reducing collateral values",
        "effect": "bank loan rates, credit limits, and monitoring",
        "claim_direction": "mixed",
        "gold_span_text": (
            "Using a unique data set from a large bank containing timely assessments "
            "of collateral values, we find that the bank responded to a legal reform "
            "that exogenously reduced collateral values by increasing interest rates, "
            "tightening credit limits, and reducing the intensity of its monitoring "
            "of borrowers and collateral, spurring borrower delinquency on outstanding claims."
        ),
        "expected_supported": True,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-collateral-opposite-negative",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W3123109680",
        "title": "Collateralization, Bank Loan Rates, and Monitoring",
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "A legal reform that reduced collateral values led the bank to lower "
            "interest rates and loosen credit limits."
        ),
        "treatment_or_cause": "legal reform reducing collateral values",
        "effect": "bank loan rates and credit limits",
        "claim_direction": "negative",
        "gold_span_text": (
            "Using a unique data set from a large bank containing timely assessments "
            "of collateral values, we find that the bank responded to a legal reform "
            "that exogenously reduced collateral values by increasing interest rates, "
            "tightening credit limits, and reducing the intensity of its monitoring "
            "of borrowers and collateral, spurring borrower delinquency on outstanding claims."
        ),
        "expected_supported": False,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
)


class DeterministicSpanSupportClient:
    """Offline replay client for the GY-K validator; never production wiring."""

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        del tools, temperature, seed
        decision, confidence, rationale = _deterministic_span_support_judgment(messages)
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": decision,
                        "confidence": confidence,
                        "rationale": rationale,
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=5),
            raw={"deterministic_replay_key": "layer3-gy-openalex-validator"},
        )


def _deterministic_span_support_judgment(
    messages: list[dict[str, object]],
) -> tuple[str, float, str]:
    """Return the committed offline replay label for the validator gold set."""

    payload = _span_support_request_payload(messages)
    span = str(payload.get("span_text", "")).lower()
    claim = str(payload.get("claim_text", "")).lower()
    direction = str(payload.get("claim_direction", "")).lower()

    if "difference-in-differences approach" in span and "reduced" in claim:
        return "neutral", 0.94, "method-only span does not entail the effect claim"
    if "tradeable sectors" in span and (
        "all low-wage jobs" in claim or "overall low-wage" in claim
    ):
        return "neutral", 0.93, "sector-specific span does not support the broad claim"
    if "remained essentially unchanged" in span and (
        "reduced overall" in claim or ("reduced" in claim and direction in {"negative", "positive"})
    ):
        return "contradicts", 0.95, "stable-job span contradicts a reduction claim"

    return "entails", 0.91, "deterministic validator replay support"


def _span_support_request_payload(messages: list[dict[str, object]]) -> dict[str, object]:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def declared_outputs() -> list[str]:
    """Return generated OpenAlex GY-K artifacts written by --write mode."""

    return list(OUTPUTS)


def validate(
    repo_root: Path,
    *,
    write: bool = False,
    corrupt_field_drift_check: bool = False,
) -> dict[str, Any]:
    """Return a drift report for the OpenAlex generated proof family."""

    repo_root = repo_root.resolve()
    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_payloads(repo_root)

    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if relative_path == ACCURACY_PATH and committed is not None:
                validate_accuracy_report_payload(
                    committed,
                    expected=expected_payload,
                    issues=issues,
                    repo_root=repo_root,
                )
            if committed != expected_payload:
                issues.append({"code": "layer3_gy_openalex_artifact_drift", "path": relative_path})

    if corrupt_field_drift_check:
        corrupted = json.loads(json.dumps(expected[ACCURACY_PATH]))
        corrupted["accuracy"]["precision"] = 1.0
        corrupt_issues: list[dict[str, str]] = []
        validate_accuracy_report_payload(
            corrupted, expected[ACCURACY_PATH], corrupt_issues, repo_root=repo_root
        )
        if corrupt_issues:
            issues.append({"code": "layer3_gy_openalex_corrupt_field_drift_detected"})
        else:
            issues.append({"code": "layer3_gy_openalex_corrupt_field_drift_not_detected"})

    try:
        from tools.quality.validation import check_layer3_gy_generated_public_lifecycle_audit

        lifecycle_report = (
            check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
                repo_root
            )
        )
        issues.extend(lifecycle_report["issues"])
    except Exception as exc:
        issues.append({"code": "layer3_gy_openalex_lifecycle_check_failed", "error": str(exc)})

    return {
        "status": "pass" if not issues else "fail",
        "family_id": FAMILY_ID,
        "source_family_id": SOURCE_FAMILY_ID,
        "checked_artifacts": [CONFIG_PATH, GOLD_PATH, *OUTPUTS],
        "write": write,
        "issues": issues,
        "accuracy": expected[ACCURACY_PATH]["accuracy"],
        "ingest": expected[INGEST_PATH]["ingest"],
    }


def _recorded_provider_population(repo_root: Path) -> tuple[list[Any], list[dict[str, Any]]]:
    from polisyos.ir.analytics.literature import (
        OpenAlexExtractionCase,
        load_recorded_openalex_source,
    )

    config = _read_required_json(repo_root / CONFIG_PATH)
    paths = config["provenance"]["recorded_response_fixtures"]
    cases = []
    sources = []
    for relative in paths:
        source = load_recorded_openalex_source(repo_root / relative, allow_empty=True)
        payload, query = source.payload, source.query
        result = asyncio.run(_provider_works_from_fixture(payload, query=query))
        source_ref = f"{relative}@{source.content_sha256}"
        sources.append(
            {
                "source_ref": source_ref,
                "query": query,
                "recorded_at": source.captured_at,
                "response_sha256": result.response_sha256,
                "returned_work_ids": [str(row.get("id")) for row in result.raw_response["results"]],
                "selected_hit_ids": [str(hit.url) for hit in result.hits],
                "excluded_results": [list(row) for row in result.excluded_results],
                "response_meta": result.raw_response.get("meta"),
                "population_scope": "complete_recorded_response_not_global_OpenAlex",
            }
        )
        for index, row in enumerate(result.raw_response["results"]):
            work_id = str(row["id"])
            matched = [work for work in result.works if work.openalex_id == work_id]
            cases.append(
                OpenAlexExtractionCase(
                    case_id=_content_digest([source_ref, index, work_id, query]),
                    openalex_id=work_id,
                    query=query,
                    source_ref=source_ref,
                    recorded_at=source.captured_at,
                    work=matched[0] if len(matched) == 1 else None,
                )
            )
    return cases, sources


async def _provider_works_from_fixture(payload: dict[str, Any], *, query: str) -> Any:
    from unittest.mock import patch

    from polisyos.scholar.search import providers
    from polisyos.scholar.search.models import SearchConstraints

    async def recorded_response(url: str, *, headers: dict[str, str], timeout_s: float) -> str:
        del headers, timeout_s
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.openalex.org":
            raise ValueError("openalex_recorded_transport_target_mismatch")
        if parse_qs(parsed.query).get("search") != [query]:
            raise ValueError("openalex_recorded_transport_query_mismatch")
        return json.dumps({key: value for key, value in payload.items() if key != "_recording"})

    with patch.object(providers, "_read_url_text", recorded_response):
        return await providers.OpenAlexWorksProvider().search_with_works(
            query,
            constraints=SearchConstraints(source_types=["academic"]),
            max_results=max(1, len(payload["results"])),
            timeout_s=5,
        )


def _content_digest(value: object) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _build_current_accuracy_payload(repo_root: Path) -> dict[str, Any]:
    from polisyos.ir.analytics.literature import evaluate_openalex_claim_extractor_accuracy

    cases, sources = _recorded_provider_population(repo_root)
    report = evaluate_openalex_claim_extractor_accuracy(cases=cases)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v2",
        "gy_lifecycle_marker": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v2",
        "produced_by": "tools/quality/validation/check_layer3_gy_openalex_artifacts.py",
        "population_sources": sources,
        "accuracy": report.model_dump(mode="json"),
        "accuracy_provenance": {
            "predicate_basis": "recomputed",
            "adjudicator_appointment": "not_established",
            "standing_rule_ref": "correspondence-acceptance-standing-rule",
            "scope": "extractor_execution_and_constructed_negatives_only",
        },
    }


def recompute_openalex_accuracy_strangle(repo_root: Path) -> dict[str, Any]:
    """Reject production references to the fenced, extractor-free predecessor."""

    import ast
    import os

    roots = [repo_root / name for name in ("src", "tools")]
    paths = {path for root in roots for path in root.rglob("*.py")}
    independent = {
        Path(directory) / name
        for root in roots
        for directory, _, names in os.walk(root)
        for name in names
        if name.endswith(".py")
    }
    if not paths or paths != independent:
        raise ValueError("openalex_strangle_source_denominator_unresolved")
    predecessor = "_evaluate_gold_span_support_accuracy"
    references = []
    for path in sorted(paths):
        relative = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            target = (
                node.id
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                else node.attr
                if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                else node.name
                if isinstance(node, ast.alias)
                else None
            )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
            ):
                member = node.args[1]
                if isinstance(member, ast.Constant):
                    target = member.value
            if target == predecessor:
                references.append(
                    {"path": relative, "line": node.lineno, "column": node.col_offset}
                )
    if references:
        raise ValueError(
            "openalex_unfenced_predecessor_reference:" + json.dumps(references, sort_keys=True)
        )
    return {
        "source_denominator": {
            "roots": ["src", "tools"],
            "rglob_py": len(paths),
            "os_walk_py": len(independent),
        },
        "remaining_callers": references,
        "remaining_callers_disposition": "no_current_production_callers_of_fenced_predecessor",
        "caller_guard_ref": "recompute_openalex_accuracy_strangle",
    }


def build_live_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute complete provider→candidate SQL evidence and extractor instrumentation."""

    from unittest.mock import patch

    from polisyos.data_forge.domains.academic.batch.article_extractor import (
        serialize_rich_claim_occurrence_vocabulary,
    )
    from polisyos.data_forge.domains.academic.knowledge import skg_store
    from polisyos.ir.analytics import literature
    from polisyos.scholar.search.models import SearchQueryTrace

    cases, sources = _recorded_provider_population(repo_root)
    instrument = literature.evaluate_openalex_claim_extractor_accuracy(cases=cases)
    accuracy = {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v2",
        "gy_lifecycle_marker": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v2",
        "produced_by": "tools/quality/validation/check_layer3_gy_openalex_artifacts.py",
        "population_sources": sources,
        "accuracy": instrument.model_dump(mode="json"),
        "accuracy_provenance": {
            "predicate_basis": "recomputed",
            "adjudicator_appointment": "not_established",
            "standing_rule_ref": "correspondence-acceptance-standing-rule",
            "scope": "extractor_execution_and_constructed_negatives_only",
        },
    }
    observations = {row.case_id: row for row in instrument.observations}
    witnesses = []
    candidate_inputs = []
    expected_claim_ids = set()
    expected_native_rows = {}
    with tempfile.TemporaryDirectory(prefix="polisyos-openalex-candidate-") as tmpdir:
        con = duckdb.connect(str(Path(tmpdir) / "skg.duckdb"))
        try:
            skg_store.ensure_skg_schema(con)
            for case in cases:
                observation = observations[case.case_id]
                if observation.disposition != "extracted":
                    witnesses.append(
                        {
                            "case_id": case.case_id,
                            "disposition": observation.disposition,
                            "reason": observation.reason,
                        }
                    )
                    continue
                claims = [
                    literature.CausalClaim.model_validate(row["claim"])
                    for row in observation.predictions
                ]
                trace = SearchQueryTrace(
                    query_node_id=case.case_id,
                    query=case.query,
                    perspective="root",
                    provider="openalex",
                    hit_count=len(
                        next(
                            row["selected_hit_ids"]
                            for row in sources
                            if row["source_ref"] == case.source_ref
                        )
                    ),
                    searched_at=case.recorded_at,
                )
                report = skg_store.ingest_openalex_source_bound_candidates(
                    con,
                    work=case.work,
                    claims=claims,
                    query_trace=trace,
                )
                claim_ids = {claim.claim_id for claim in claims}
                expected_claim_ids.update(claim_ids)
                for candidate in claims:
                    binding = literature.validate_openalex_source_bound_candidate(
                        case.work, candidate, query=case.query
                    )
                    transport = skg_store.preflight_candidate_claim_vocabulary(
                        serialize_rich_claim_occurrence_vocabulary(
                            candidate, record_extraction_mode="openalex_span_grounded"
                        )
                    )
                    vocabulary = skg_store.candidate_claim_vocabulary_store_values(transport)
                    expected_native_rows[candidate.claim_id] = {
                        "claim_id": candidate.claim_id,
                        "openalex_id": case.openalex_id,
                        "cause": candidate.cause_variable,
                        "effect": candidate.effect_variable,
                        "direction": candidate.direction.value,
                        "claim_text": candidate.claim_text,
                        "span_text": candidate.supporting_spans[0].text,
                        "span_start": binding.span_start,
                        "span_end": binding.span_end,
                        "source_content_sha256": case.work.content_sha256,
                        "support_status": binding.status,
                        "authority_tier": "candidate_unverified",
                        "grounding_ref": binding.grounding_ref,
                        "query_trace_id": report.query_trace_id,
                        "design_family": None,
                        "design_quality_tier": candidate.design_quality_tier,
                        "evidence_strength": skg_store.encode_edge_evidence_strength(
                            vocabulary["evidence_strength"],
                            status=vocabulary["evidence_strength_status"],
                        ),
                        "confidence": float(candidate.claim_extraction_confidence or 0.5),
                        "skg_version": report.skg_version_id,
                    }
                candidate_inputs.extend((case, claim, trace) for claim in claims)
                witnesses.append(
                    {
                        "case_id": case.case_id,
                        "query": case.query,
                        "source_ref": case.source_ref,
                        "claim_ids": sorted(claim_ids),
                        "authority_tier": report.authority_tier,
                        "query_trace_id": report.query_trace_id,
                    }
                )
            for source in sources:
                if source["returned_work_ids"]:
                    continue
                trace = SearchQueryTrace(
                    query_node_id=_content_digest(source),
                    query=source["query"],
                    perspective="root",
                    provider="openalex",
                    hit_count=0,
                    searched_at=source["recorded_at"],
                )
                skg_store.ingest_openalex_no_hit_frontier(con, query_trace=trace)
            cursor = con.execute("SELECT * FROM ac_skg_span_grounded_claims ORDER BY claim_id")
            columns = [column[0] for column in cursor.description]
            persisted_claims = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            persisted_evidence_ids = {
                row[0]
                for row in con.execute("SELECT claim_id FROM ac_skg_edge_evidence").fetchall()
            }
            persisted_claim_ids = {row["claim_id"] for row in persisted_claims}
            if (
                expected_claim_ids != persisted_claim_ids
                or expected_claim_ids != persisted_evidence_ids
            ):
                raise ValueError("openalex_candidate_ingest_identity_loss")
            if {row["claim_id"]: row for row in persisted_claims} != expected_native_rows:
                raise ValueError("openalex_candidate_complete_native_content_mismatch")
            if any(
                row[0] != "candidate"
                for row in con.execute("SELECT candidate_layer FROM ac_skg_edges").fetchall()
            ):
                raise ValueError("openalex_candidate_layer_escape")
            sql_trace_ids = sorted(
                row[0] for row in con.execute("SELECT trace_id FROM ac_skg_query_traces").fetchall()
            )
            no_hit_rows = con.execute(
                "SELECT query, provider, reason FROM ac_skg_no_hit_frontier ORDER BY frontier_id"
            ).fetchall()
        finally:
            con.close()
    if not candidate_inputs:
        raise ValueError("openalex_candidate_population_produced_no_candidates")
    case, claim, trace = candidate_inputs[0]
    poisoned = claim.model_copy(
        update={"claim_text": "Constructed claim outside this extractor/source binding."}
    )

    def attempt(row: Any) -> bool:
        con = duckdb.connect(":memory:")
        try:
            try:
                skg_store.ingest_openalex_source_bound_candidates(
                    con, work=case.work, claims=[row], query_trace=trace
                )
            except ValueError:
                return False
            return bool(
                con.execute("SELECT COUNT(*) FROM ac_skg_span_grounded_claims").fetchone()[0]
            )
        finally:
            con.close()

    baseline_fake_admitted = attempt(poisoned)
    if baseline_fake_admitted:
        raise ValueError("openalex_fake_candidate_owner_validation_missing")
    actual_binding = skg_store.validate_openalex_source_bound_candidate
    with patch.object(
        skg_store,
        "validate_openalex_source_bound_candidate",
        lambda work, candidate, **kwargs: actual_binding(work, claim, **kwargs),
    ):
        removed_verifier_fake_admitted = attempt(poisoned)
    if not removed_verifier_fake_admitted:
        raise ValueError("openalex_owner_removal_control_not_decisive")
    with patch.object(
        literature, "extract_span_grounded_claims_from_openalex_work", lambda *args, **kwargs: []
    ):
        removed_extractor = literature.evaluate_openalex_claim_extractor_accuracy(cases=cases)
    if removed_extractor == instrument:
        raise ValueError("openalex_accuracy_default_did_not_consult_extractor")
    if any(
        negative["disposition"] != "refused"
        for observation in instrument.observations
        for negative in observation.constructed_negatives
    ):
        raise ValueError("openalex_constructed_negative_not_refused")
    baseline_spans = {
        (item.openalex_id, span.text)
        for item, candidate, _ in candidate_inputs
        for span in candidate.supporting_spans
    }
    novel = []
    for item in cases:
        if item.work is None:
            continue
        for query in literature._split_sentences(item.work.abstract_text):
            for candidate in literature.extract_span_grounded_claims_from_openalex_work(
                item.work, query=query
            ):
                if candidate.claim_id not in expected_claim_ids and any(
                    (item.openalex_id, span.text) not in baseline_spans
                    for span in candidate.supporting_spans
                ):
                    novel.append((item, query, candidate))
    if not novel:
        raise ValueError("openalex_data_only_novel_claim_witness_missing")
    novel.sort(key=lambda row: (row[0].case_id, row[1], row[2].claim_id))
    novel_case, novel_query, novel_claim = novel[0]
    novel_trace = SearchQueryTrace(
        query_node_id=_content_digest([novel_case.case_id, novel_query]),
        query=novel_query,
        perspective="root",
        provider="openalex",
        hit_count=1,
        searched_at=novel_case.recorded_at,
    )
    con = duckdb.connect(":memory:")
    try:
        novel_report = skg_store.ingest_openalex_source_bound_candidates(
            con,
            work=novel_case.work,
            claims=[novel_claim],
            query_trace=novel_trace,
        )
        novel_ids = [
            row[0]
            for row in con.execute("SELECT claim_id FROM ac_skg_span_grounded_claims").fetchall()
        ]
        if (
            novel_ids != [novel_claim.claim_id]
            or novel_report.authority_tier != "candidate_unverified"
        ):
            raise ValueError("openalex_data_only_candidate_growth_failed")
    finally:
        con.close()
    ingest = {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_skg_ingest_records.v2",
        "gy_lifecycle_marker": "policyos.policy_design_case.layer3_gy.openalex_skg_ingest_records.v2",
        "produced_by": "tools/quality/validation/check_layer3_gy_openalex_artifacts.py",
        "ingest": {
            "population_sources": sources,
            "witness_records": witnesses,
            "persisted_claims": persisted_claims,
            "query_trace_ids": sql_trace_ids,
            "no_hit_frontier": [list(row) for row in no_hit_rows],
            "identity_sets_reconciled": True,
            "owner_validation_control": {
                "baseline_fake_admitted": baseline_fake_admitted,
                "removed_verifier_fake_admitted": removed_verifier_fake_admitted,
            },
            "data_only_growth_control": {
                "source_ref": novel_case.source_ref,
                "source_content_sha256": novel_case.work.content_sha256,
                "source_capture_query": novel_case.query,
                "constructed_selection_query": novel_query,
                "new_claim_id": novel_claim.claim_id,
                "new_span_not_in_baseline": True,
                "authority_tier": novel_report.authority_tier,
                "population_disposition": "isolated_engineering_selection_not_accuracy_population",
                "external_query_occurrence": "not_established",
            },
            "strangle_receipt": {
                **recompute_openalex_accuracy_strangle(repo_root),
                "predecessor_ref": "literature._evaluate_gold_span_support_accuracy",
                "replacement_ref": "literature.evaluate_openalex_claim_extractor_accuracy",
                "disposition": "fenced_default_flipped",
                "default_before": "gold_claim_semantic_judgments_without_extractor",
                "default_after": "actual_extractor_with_constructed_negative_source_checks",
                "guard_ref": "test_extractor_instrument_observes_actual_default_extractor",
                "default_removal_changed_report": removed_extractor != instrument,
                "baseline_report_hash": _content_digest(instrument.model_dump(mode="json")),
                "removed_report_hash": _content_digest(removed_extractor.model_dump(mode="json")),
                "verified_by": "live_default_extractor_removal_and_real_candidate_owner_control",
            },
        },
    }
    return {ACCURACY_PATH: accuracy, INGEST_PATH: ingest}


def build_real_agent_accuracy_payload(repo_root: Path) -> dict[str, Any]:
    """Refuse a current positive accuracy reissue without the ruled appointment."""

    del repo_root
    raise ValueError("correspondence-acceptance-standing-rule:adjudicator_appointment_missing")


def _claim_payload_from_accuracy_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(case.get("label_id") or ""),
        "claim_text": str(case.get("claim_text") or ""),
        "claim_family": "causal",
        "cause_variable": str(case.get("treatment_or_cause") or ""),
        "effect_variable": str(case.get("effect") or ""),
        "direction": str(case.get("claim_direction") or ""),
        "data_refs": [str(case.get("openalex_id") or "")],
        "source_attribution": str(case.get("openalex_id") or ""),
        "method_refs": ["source_bound_claim_span"],
        "identification_strategy": "source_bound_claim_span",
    }


def _evidence_payload_from_accuracy_case(repo_root: Path, case: dict[str, Any]) -> dict[str, Any]:
    span_text = str(case.get("gold_span_text") or "")
    work = _work_from_fixture(
        _recorded_fixture_payload(
            repo_root,
            str(case.get("source_fixture") or ""),
            query=str(case.get("query") or ""),
        ),
        str(case.get("openalex_id") or ""),
    )
    span_start = work.source_text.find(span_text)
    return {
        "ref_id": f"{case.get('openalex_id')}#{case.get('label_id')}",
        "source_ref": str(case.get("openalex_id") or ""),
        "text": span_text,
        "section": "abstract",
        "start_char": span_start if span_start >= 0 else None,
        "end_char": span_start + len(span_text) if span_start >= 0 else None,
        "source_content_sha256": work.content_sha256,
    }


def _span_exists_in_source(repo_root: Path, case: dict[str, Any]) -> bool:
    try:
        work = _work_from_fixture(
            _recorded_fixture_payload(
                repo_root,
                str(case.get("source_fixture") or ""),
                query=str(case.get("query") or ""),
            ),
            str(case.get("openalex_id") or ""),
        )
    except Exception:
        return False
    return str(case.get("gold_span_text") or "") in work.source_text


def _agent_decision(result: dict[str, Any]) -> str:
    judgment = result.get("agent_judgment")
    if isinstance(judgment, dict):
        return str(judgment.get("decision") or "")
    return ""


def _agent_confidence(result: dict[str, Any]) -> float:
    judgment = result.get("agent_judgment")
    if isinstance(judgment, dict):
        try:
            return float(judgment.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(result.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _degraded_accuracy_from_case_judgments(case_judgments: list[dict[str, Any]]) -> dict[str, Any]:
    degraded_cases = [{**case, "predicted_supported": False} for case in case_judgments]
    degraded = _accuracy_from_case_judgments(degraded_cases)
    if degraded is None:
        raise RuntimeError("failed to build degraded accuracy report")
    return degraded


def _real_agent_model_id() -> str:
    return (
        os.getenv("POLISYOS_LLM_GATEWAY_SPAN_SUPPORT_MODEL", "").strip()
        or os.getenv("POLISYOS_LLM_GATEWAY_MODEL", "").strip()
        or REAL_AGENT_MODEL_ID
    )


async def _provider_hits_from_fixture(
    fixture_payload: dict[str, Any],
    *,
    query: str,
    max_results: int,
) -> list[Any]:
    from polisyos.scholar.search import providers as provider_module
    from polisyos.scholar.search.models import SearchConstraints
    from polisyos.scholar.search.providers import OpenAlexWorksProvider

    async def _fake_read_url_text(url: str, *, headers: dict[str, str], timeout_s: float) -> str:
        del url, headers, timeout_s
        return json.dumps(fixture_payload)

    original = provider_module._read_url_text
    provider_module._read_url_text = _fake_read_url_text
    try:
        provider = OpenAlexWorksProvider(endpoint="https://openalex.test/works")
        return await provider.search(
            query,
            constraints=SearchConstraints(source_types=["academic"]),
            max_results=max_results,
            timeout_s=5,
        )
    finally:
        provider_module._read_url_text = original


def _work_from_fixture(payload: dict[str, Any], openalex_id: str) -> Any:
    from polisyos.ir.analytics.literature import OpenAlexWorkText

    for item in payload.get("results", []):
        if isinstance(item, dict) and str(item.get("id") or "") == openalex_id:
            return OpenAlexWorkText.from_openalex_work(item)
    raise ValueError(f"OpenAlex work not found in fixture: {openalex_id}")


def _recorded_fixture_payload(repo_root: Path, relative_path: str, *, query: str) -> dict[str, Any]:
    from polisyos.ir.analytics.literature import load_recorded_openalex_source

    return load_recorded_openalex_source(repo_root / relative_path, query=query).payload


def _assert_recorded_openalex_fixture(
    payload: dict[str, Any],
    *,
    path: str,
    query: str,
    allow_empty: bool = False,
) -> None:
    from polisyos.ir.analytics.literature import validate_recorded_openalex_response

    try:
        validate_recorded_openalex_response(payload, query=query, allow_empty=allow_empty)
    except ValueError as exc:
        raise ValueError(f"{exc}: {path}") from exc


def _recorded_at(payload: dict[str, Any]) -> str:
    from polisyos.ir.analytics.literature import recorded_openalex_capture_time

    return recorded_openalex_capture_time(payload)


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        issues.append({"code": "layer3_gy_openalex_generated_artifacts_missing"})
        return
    generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not isinstance(family, dict):
        issues.append({"code": "layer3_gy_openalex_family_missing"})
    else:
        if family.get("outputs") != OUTPUTS:
            issues.append({"code": "layer3_gy_openalex_output_scope_drift"})
        if family.get("lifecycle") != "generated_committed":
            issues.append({"code": "layer3_gy_openalex_lifecycle_drift"})
        if "--check" not in list(family.get("check_command") or []):
            issues.append({"code": "layer3_gy_openalex_check_command_missing"})
        if "--write" not in " ".join(family.get("regenerate_commands") or []):
            issues.append({"code": "layer3_gy_openalex_regenerate_command_missing"})
    history = families.get(HISTORY_FAMILY_ID)
    if (
        not isinstance(history, dict)
        or history.get("lifecycle") != "source_committed"
        or history.get("outputs") != list(HISTORICAL_OUTPUTS_SHA256)
        or history.get("source_integrity_sha256") != HISTORICAL_OUTPUTS_SHA256
    ):
        issues.append({"code": "layer3_gy_openalex_history_partition_invalid"})
    for output, expected_hash in HISTORICAL_OUTPUTS_SHA256.items():
        path = repo_root / output
        if not path.is_file():
            issues.append({"code": "layer3_gy_openalex_history_output_missing", "path": output})
        elif _sha256(path) != expected_hash:
            issues.append({"code": "layer3_gy_openalex_history_integrity_drift", "path": output})
    source_family = families.get(SOURCE_FAMILY_ID)
    if not isinstance(source_family, dict):
        issues.append({"code": "layer3_gy_openalex_source_family_missing"})
    else:
        if set(source_family.get("outputs") or []) != {CONFIG_PATH, GOLD_PATH}:
            issues.append({"code": "layer3_gy_openalex_source_output_scope_drift"})
        _validate_source_integrity(repo_root, source_family, issues)


def _validate_source_integrity(
    repo_root: Path,
    family: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    integrity = family.get("source_integrity_sha256")
    if not isinstance(integrity, dict):
        issues.append({"code": "layer3_gy_openalex_source_integrity_missing"})
        return
    for output in (CONFIG_PATH, GOLD_PATH):
        path = repo_root / output
        expected = str(integrity.get(output) or "")
        if not path.is_file():
            issues.append({"code": "layer3_gy_openalex_source_output_missing", "path": output})
            continue
        actual = _sha256(path)
        if expected != actual:
            issues.append({"code": "layer3_gy_openalex_source_integrity_drift", "path": output})


def validate_accuracy_report_payload(
    payload: dict[str, Any],
    expected: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    repo_root: Path | None = None,
) -> None:
    """Recompute substantive current extractor evidence, never supplied arithmetic."""

    del expected
    from polisyos.ir.analytics.literature import ExtractorAccuracyReport

    try:
        ExtractorAccuracyReport.model_validate(payload["accuracy"])
    except (KeyError, ValueError, TypeError):
        issues.append({"code": "layer3_gy_openalex_accuracy_current_epoch_invalid"})
        return
    repo_root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    current = _build_current_accuracy_payload(repo_root)
    if payload != current:
        issues.append({"code": "layer3_gy_openalex_accuracy_substantive_recompute_drift"})


def _accuracy_from_case_judgments(value: object) -> dict[str, Any] | None:
    if not isinstance(value, list) or not value:
        return None
    true_positive_count = 0
    true_negative_count = 0
    false_positive_count = 0
    false_negative_count = 0
    predicted_claim_count = 0
    matched_label_ids: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        expected_supported = bool(item.get("expected_supported"))
        predicted_supported = bool(item.get("predicted_supported"))
        if predicted_supported:
            predicted_claim_count += 1
        label_id = str(item.get("label_id") or "")
        if expected_supported and predicted_supported:
            true_positive_count += 1
            if label_id:
                matched_label_ids.append(label_id)
        elif expected_supported and not predicted_supported:
            false_negative_count += 1
        elif not expected_supported and predicted_supported:
            false_positive_count += 1
        else:
            true_negative_count += 1
    precision_denominator = true_positive_count + false_positive_count
    recall_denominator = true_positive_count + false_negative_count
    precision = true_positive_count / precision_denominator if precision_denominator else 0.0
    recall = true_positive_count / recall_denominator if recall_denominator else 0.0
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_accuracy.v1",
        "measurement_basis": "human_labeled_gold_set",
        "gold_record_count": len(value),
        "predicted_claim_count": predicted_claim_count,
        "true_positive_count": true_positive_count,
        "false_positive_count": false_positive_count,
        "false_negative_count": false_negative_count,
        "true_negative_count": true_negative_count,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "matched_label_ids": sorted(matched_label_ids),
    }


def _case_looks_deterministic(case: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(case.get(key) or "")
        for key in ("judge_client", "rationale", "replay_key", "methodology")
    ).casefold()
    raw = case.get("agent_judgment")
    if isinstance(raw, dict):
        haystack = f"{haystack} {json.dumps(raw, sort_keys=True)}".casefold()
    return any(token in haystack for token in ("deterministic", "recorded", "replay"))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any] | None:
    if not path.is_file():
        issues.append({"code": "layer3_gy_openalex_artifact_missing", "path": str(path)})
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "layer3_gy_openalex_artifact_invalid_json",
                "path": str(path),
                "error": str(exc),
            }
        )
        return None
    except (OSError, UnicodeError) as exc:
        issues.append(
            {"code": "layer3_gy_openalex_artifact_unreadable", "path": str(path), "error": str(exc)}
        )
        return None
    if not isinstance(payload, dict):
        issues.append({"code": "layer3_gy_openalex_artifact_object_required", "path": str(path)})
        return None
    return payload


def _read_required_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_src_path(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "src"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-real-accuracy", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if args.write_real_accuracy:
        _ensure_src_path(repo_root)
        payload = build_real_agent_accuracy_payload(repo_root)
        path = repo_root / ACCURACY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = {
            "status": "pass",
            "family_id": FAMILY_ID,
            "checked_artifacts": [ACCURACY_PATH],
            "accuracy": payload["accuracy"],
            "accuracy_provenance": payload["accuracy_provenance"],
            "case_judgment_count": len(payload["case_judgments"]),
        }
        if args.output_format == "json":
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("PASS layer3_gy_openalex_real_accuracy")
        return 0

    report = validate(
        repo_root,
        write=bool(args.write),
        corrupt_field_drift_check=bool(args.corrupt_field_drift_check),
    )
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print("PASS layer3_gy_openalex_artifacts")
    else:
        print("FAIL layer3_gy_openalex_artifacts")
        for issue in report["issues"]:
            print(issue)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
