"""Owner for recorded OpenAlex span evidence and candidate SKG proof production."""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class OpenAlexEvidenceDependencies:
    """Bind evidence production to the active validator facade inputs."""

    config_path: str
    accuracy_path: str
    ingest_path: str
    read_required_json: Callable[[Path], dict[str, Any]]
    provider_works_from_fixture: Callable[..., Coroutine[Any, Any, Any]]
    run_async: Callable[[Coroutine[Any, Any, Any]], Any]
    content_digest: Callable[[object], str]
    recorded_provider_population: Callable[[Path], tuple[list[Any], list[dict[str, Any]]]]
    recompute_openalex_accuracy_strangle: Callable[[Path], dict[str, Any]]
    duckdb_connect: Callable[[str], Any]
    temporary_directory: Callable[..., AbstractContextManager[str]]


def _recorded_provider_population(
    repo_root: Path, *, dependencies: OpenAlexEvidenceDependencies
) -> tuple[list[Any], list[dict[str, Any]]]:
    from polisyos.ir.analytics.literature import (
        OpenAlexExtractionCase,
        load_recorded_openalex_source,
    )

    config = dependencies.read_required_json(repo_root / dependencies.config_path)
    paths = config["provenance"]["recorded_response_fixtures"]
    cases = []
    sources = []
    for relative in paths:
        source = load_recorded_openalex_source(repo_root / relative, allow_empty=True)
        payload, query = source.payload, source.query
        result = dependencies.run_async(
            dependencies.provider_works_from_fixture(payload, query=query)
        )
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
                    case_id=dependencies.content_digest([source_ref, index, work_id, query]),
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


def _build_current_accuracy_payload(
    repo_root: Path, *, dependencies: OpenAlexEvidenceDependencies
) -> dict[str, Any]:
    from polisyos.ir.analytics.literature import evaluate_openalex_claim_extractor_accuracy

    cases, sources = dependencies.recorded_provider_population(repo_root)
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


def build_live_payloads(
    repo_root: Path, *, dependencies: OpenAlexEvidenceDependencies
) -> dict[str, dict[str, Any]]:
    """Recompute complete provider→candidate SQL evidence and extractor instrumentation."""

    from unittest.mock import patch

    from polisyos.data_forge.domains.academic.batch.article_extractor import (
        serialize_rich_claim_occurrence_vocabulary,
    )
    from polisyos.data_forge.domains.academic.knowledge import skg_store
    from polisyos.ir.analytics import literature
    from polisyos.scholar.search.models import SearchQueryTrace

    cases, sources = dependencies.recorded_provider_population(repo_root)
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
    with dependencies.temporary_directory(prefix="polisyos-openalex-candidate-") as tmpdir:
        con = dependencies.duckdb_connect(str(Path(tmpdir) / "skg.duckdb"))
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
                    query_node_id=dependencies.content_digest(source),
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
        con = dependencies.duckdb_connect(":memory:")
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
        query_node_id=dependencies.content_digest([novel_case.case_id, novel_query]),
        query=novel_query,
        perspective="root",
        provider="openalex",
        hit_count=1,
        searched_at=novel_case.recorded_at,
    )
    con = dependencies.duckdb_connect(":memory:")
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
                **dependencies.recompute_openalex_accuracy_strangle(repo_root),
                "predecessor_ref": "literature._evaluate_gold_span_support_accuracy",
                "replacement_ref": "literature.evaluate_openalex_claim_extractor_accuracy",
                "disposition": "fenced_default_flipped",
                "default_before": "gold_claim_semantic_judgments_without_extractor",
                "default_after": "actual_extractor_with_constructed_negative_source_checks",
                "guard_ref": "test_extractor_instrument_observes_actual_default_extractor",
                "default_removal_changed_report": removed_extractor != instrument,
                "baseline_report_hash": dependencies.content_digest(
                    instrument.model_dump(mode="json")
                ),
                "removed_report_hash": dependencies.content_digest(
                    removed_extractor.model_dump(mode="json")
                ),
                "verified_by": "live_default_extractor_removal_and_real_candidate_owner_control",
            },
        },
    }
    return {dependencies.accuracy_path: accuracy, dependencies.ingest_path: ingest}
