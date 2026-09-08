"""Verify exact-request/source replay and the publication/relation boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic
from polisyos.runtime.quality.production_grounding_calibration import (
    ProductionCG2CalibrationSource,
    SourceGroundingRequest,
)


@pytest.fixture(name="source_request")
def request() -> SourceGroundingRequest:
    return SourceGroundingRequest(
        requirement_ref="requirement:avg-income",
        claim_ref="claim:avg-income",
        compiled_requirement={"required_data_families": ["household_panel"]},
        design_problem={
            "outcome_of_interest": {
                "target_variable": "avg_income",
                "estimand": "average_treatment_effect",
            },
            "jurisdiction_time": {"jurisdiction": "UA"},
        },
        world_snapshot={"world_ref": "world:current"},
    )


@pytest.fixture
def owner(tmp_path: Path):
    path = tmp_path / "source.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_skg_simulation_parameters AS "
            "SELECT 'n' || i numeric_id, 'W1' openalex_id, 'avg_income' canonical_name, "
            "'[\"c1\"]' linked_claim_ids_json, '[\"e1\"]' linked_edges_json "
            "FROM range(30) t(i)"
        )
    source = academic.SourceSnapshot(
        path=path,
        reference="fixture://source",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    return ProductionCG2CalibrationSource(
        source=source, store=store, scratch=tmp_path / "spill"
    ), store


def test_source_matches_persist_and_replay_without_becoming_relation_calibration(
    owner, source_request
):
    request = source_request
    producer, store = owner
    ref = producer.produce(request)
    result = producer.replay(ref=ref, request=request)
    assert store.get_bytes(ref.artifact_id)
    assert result.source_population.row_count == 30
    assert len(result.source_population.literal_target_row_indices) == 30
    assert result.target_variable == "avg_income"
    assert result.estimand == "average_treatment_effect"
    assert result.cg2_status == "cold_start"
    assert result.cg2_owner_ledger_id == "cg2_production_calibration_empty"
    assert result.relation_acceptance.status == "not_established"
    assert result.admitted_relation_observation_count == 0
    assert result.n7_disposition == "no_acquired_grounding"
    assert result.n8_admission == "blocked"


@pytest.mark.parametrize(
    "field", ["claim_ref", "compiled_requirement", "design_problem", "world_snapshot"]
)
def test_replay_requires_complete_current_request(owner, source_request, field):
    request = source_request
    producer, _ = owner
    ref = producer.produce(request)
    changed = request.model_dump(mode="json")
    changed[field] = "claim:other" if field == "claim_ref" else {"swapped": True}
    other = SourceGroundingRequest.model_validate_json(json.dumps(changed))
    with pytest.raises(ValueError, match="replay_mismatch"):
        producer.replay(ref=ref, request=other)


@pytest.mark.parametrize(
    "mutation", ["source_row", "source_count", "match", "refusal", "publication", "grade"]
)
def test_valid_new_cas_cannot_launder_candidate_or_publication_data(
    owner, source_request, mutation
):
    request = source_request
    producer, store = owner
    ref = producer.produce(request)
    payload = json.loads(store.get_bytes(ref.artifact_id))
    if mutation == "source_row":
        payload["source_population"]["rows"][0]["canonical_name"] = "unrelated"
    elif mutation == "source_count":
        payload["source_population"]["row_count"] += 1
    elif mutation == "match":
        payload["source_population"]["literal_target_row_indices"] = []
    elif mutation == "refusal":
        payload["refusal_reasons"] = []
    elif mutation == "publication":
        payload["relation_acceptance"]["relation_gold_context"] = {
            "publish_to_graph": "yes",
            "accepted": True,
            "sample_count": 30,
        }
    else:
        payload["n8_admission"] = "certified"
    forged = store.put_bytes(
        json.dumps(payload).encode(),
        artifacts.ArtifactWriteOptions(
            kind="runtime.production_grounding_source_resolution",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="runtime.production_grounding_source_resolution", version="1.0"
            ),
            producer=artifacts.ProducerInfo(component="candidate", version="1.0"),
        ),
    )
    with pytest.raises(ValueError):
        producer.replay(ref=forged, request=request)


def test_missing_source_and_exact_context_are_persisted_refusals(tmp_path, source_request):
    request = source_request
    producer = ProductionCG2CalibrationSource(
        source=None, store=artifacts.FileSystemCAS(tmp_path / "cas"), scratch=tmp_path / "spill"
    )
    request = request.model_copy(update={"design_problem": None, "world_snapshot": None})
    result = producer.replay(ref=producer.produce(request), request=request)
    assert result.source_population is None
    assert result.target_variable is None
    assert "source_snapshot_unavailable" in result.refusal_reasons
    assert "exact_outcome_request_not_established" in result.refusal_reasons
    assert result.production_value_eligible is False
