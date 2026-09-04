"""Tests for OpenAlex span-grounded claim ingestion into the academic SKG."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.academic.knowledge import skg_store
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    ingest_openalex_no_hit_frontier,
    ingest_openalex_span_grounded_claims,
)
from polisyos.data_forge.domains.academic.knowledge.types import ClaimOccurrenceVocabularyTransport
from polisyos.ir.analytics.literature import (
    CausalClaim,
    EvidenceSpan,
    OpenAlexWorkText,
    VersionedClaimVocabularyEnvelope,
    extract_span_grounded_claims_from_openalex_work,
)
from polisyos.scholar.search.models import SearchQueryTrace

REPO_ROOT = Path(__file__).resolve().parents[6]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "scholar" / "openalex"


def test_span_writer_inactive_preflight_reuses_the_graph_vocabulary_boundary() -> None:
    """Catch a direct writer seam that admits a duplicate vocabulary key."""

    transport = ClaimOccurrenceVocabularyTransport(
        occurrence={
            "cause": "tax rate",
            "effect": "employment",
            "direction": "negative",
            "mechanism": "labour cost",
            "supporting_span_ids": ["span-1"],
        },
        vocabulary=VersionedClaimVocabularyEnvelope(
            cause="tax rate",
            effect="employment",
            direction="negative",
            mechanism="labour cost",
        ),
    )

    assert skg_store.preflight_candidate_claim_vocabulary(transport) == transport
    bad = transport.model_copy(
        update={"occurrence": {**transport.occurrence, "evidence_strength": "rct"}}
    )
    with pytest.raises(ValidationError, match="evidence_strength"):
        skg_store.preflight_candidate_claim_vocabulary(bad)


def test_span_writer_admits_every_claim_before_first_database_write() -> None:
    """A forged vocabulary candidate cannot leave a partial writer footprint."""

    con = duckdb.connect(":memory:")
    forged = CausalClaim(
        claim_id="claim-forged",
        cause_variable="tax rate",
        effect_variable="employment",
    ).model_copy(update={"evidence_strength": "moderate"})

    with (
        pytest.warns(UserWarning, match="Pydantic serializer warnings"),
        pytest.raises(ValidationError, match="evidence_strength"),
    ):
        ingest_openalex_span_grounded_claims(
            con,
            work=_work(),
            claims=[forged],
            query_trace=SearchQueryTrace(
                query_node_id="q-forged",
                query="tax rate employment",
                perspective="root",
                provider="openalex",
                hit_count=1,
            ),
        )

    assert con.execute(
        "SELECT table_name FROM information_schema.tables ORDER BY table_name"
    ).fetchall() == []
    con.close()


class _DeterministicSpanSupportClient:
    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        del messages, tools, temperature, seed
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": "entails",
                        "confidence": 0.91,
                        "rationale": "deterministic test support",
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=5),
            raw={"deterministic_replay_key": "test-only"},
        )


def _work() -> OpenAlexWorkText:
    payload = json.loads((FIXTURE_DIR / "credit_guarantee_firm_survival.json").read_text())
    work_payload = payload["results"][0]
    return OpenAlexWorkText.from_openalex_work(work_payload)


def test_ingest_accepts_validated_spans_and_rejects_non_supporting_spans(tmp_path: Path) -> None:
    db_path = tmp_path / "skg.duckdb"
    con = duckdb.connect(str(db_path))
    ensure_skg_schema(con)
    work = _work()
    client = _DeterministicSpanSupportClient()
    claims = extract_span_grounded_claims_from_openalex_work(
        work,
        query="loan guarantees SMEs firm survival impact evaluation",
        span_support_client=client,
    )
    assert claims
    poisoned_claim = claims[0].model_copy(
        update={
            "claim_id": f"{claims[0].claim_id}.poisoned",
            "supporting_spans": [
                EvidenceSpan(
                    span_id="fake-span",
                    text="This asserted span is not present in the OpenAlex abstract.",
                    source_ref=work.openalex_id,
                )
            ],
            "supporting_span_ids": ["fake-span"],
        }
    )
    non_supporting_claim = claims[0].model_copy(
        update={
            "claim_id": f"{claims[0].claim_id}.non_supporting_title",
            "claim_text": "Debt finance substantially improves SME survival.",
            "cause_variable": "debt finance",
            "effect_variable": "SME survival",
            "supporting_spans": [
                EvidenceSpan(
                    span_id="title-present",
                    text=work.title,
                    source_ref=work.openalex_id,
                    start_char=0,
                    end_char=len(work.title),
                    content_sha256=work.content_sha256,
                )
            ],
            "supporting_span_ids": ["title-present"],
        }
    )

    report = ingest_openalex_span_grounded_claims(
        con,
        work=work,
        claims=[*claims, poisoned_claim, non_supporting_claim],
        query_trace=SearchQueryTrace(
            query_node_id="q-credit",
            query="loan guarantees SMEs firm survival impact evaluation",
            perspective="root",
            provider="openalex",
            hit_count=5,
        ),
        span_support_client=client,
    )

    assert report.ingested_claim_count >= 1
    assert report.rejected_claim_count == 2
    assert report.rejected_claim_ids == (
        poisoned_claim.claim_id,
        non_supporting_claim.claim_id,
    )
    assert report.query_trace.provider == "openalex"
    assert report.authority_tier == "design_tier_l2"

    edge_count = con.execute("SELECT COUNT(*) FROM ac_skg_edge_evidence").fetchone()[0]
    edge_rows = con.execute(
        "SELECT src, dst, quality_signals_json FROM ac_skg_edges ORDER BY edge_id"
    ).fetchall()
    trace_count = con.execute("SELECT COUNT(*) FROM ac_skg_query_traces").fetchone()[0]
    authority_count = con.execute(
        "SELECT COUNT(*) FROM ac_skg_span_grounded_claims "
        "WHERE authority_tier = 'design_tier_l2' AND support_status = 'validated_supporting'"
    ).fetchone()[0]
    extraction_json = con.execute(
        "SELECT extraction_json FROM ac_skg_articles WHERE openalex_id = ?",
        [work.openalex_id],
    ).fetchone()[0]
    con.close()

    assert edge_count >= 1
    assert edge_rows
    for src, dst, quality_json in edge_rows:
        assert src and src == src.lower()
        assert dst and dst == dst.lower()
        quality = json.loads(quality_json)
        assert quality["source_cause_variable"]
        assert quality["source_effect_variable"]
    assert trace_count == 1
    assert authority_count >= 1
    persisted_claims = json.loads(extraction_json)["claims"]
    assert persisted_claims
    assert all(set(item) == {"occurrence", "vocabulary"} for item in persisted_claims)
    assert all("strength" not in item["occurrence"] for item in persisted_claims)
    assert all(item["vocabulary"]["schema_version"] == "2.0" for item in persisted_claims)


def test_no_hit_query_trace_persists_queryable_skg_frontier(tmp_path: Path) -> None:
    db_path = tmp_path / "skg.duckdb"
    con = duckdb.connect(str(db_path))
    ensure_skg_schema(con)

    report = ingest_openalex_no_hit_frontier(
        con,
        query_trace=SearchQueryTrace(
            query_node_id="q-nohit",
            query="zzzxxy policyos nonexistent phrase qwertyuiopasdfgh 123456789",
            perspective="root",
            provider="openalex",
            hit_count=0,
        ),
    )

    rows = con.execute(
        "SELECT trace_id, query, provider, reason FROM ac_skg_no_hit_frontier"
    ).fetchall()
    trace_rows = con.execute(
        "SELECT trace_id, hit_count FROM ac_skg_query_traces"
    ).fetchall()
    con.close()

    assert report.authority_tier == "candidate_unverified"
    assert report.ingested_claim_count == 0
    assert rows == [
        (
            report.query_trace_id,
            "zzzxxy policyos nonexistent phrase qwertyuiopasdfgh 123456789",
            "openalex",
            "provider_returned_no_hits",
        )
    ]
    assert trace_rows == [(report.query_trace_id, 0)]
