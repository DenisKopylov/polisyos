"""A stored parameter must distinguish a judgment from manufactured strength."""

import json
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.batch import (
    article_extractor,
    graph_builder,
    resolve_finalize,
)
from polisyos.data_forge.domains.academic.batch._resolve_extract_transformers import (
    _deterministic_numeric_rescue_parameters,
    _merge_numeric_parameter_lists,
)
from polisyos.data_forge.domains.academic.knowledge import skg_store
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    EvidenceParameter,
    EvidenceStrength,
    SourceBasis,
)


def _article(parameter: EvidenceParameter) -> ArticleExtractionResult:
    return ArticleExtractionResult(
        openalex_id="controlled:parameter-provenance",
        title="Stored parameter provenance fixture",
        extraction_model="controlled-no-model-call",
        extraction_timestamp="2026-09-06T00:00:00Z",
        extraction_confidence=0.5,
        empirical_parameters=[parameter],
    )


@pytest.mark.parametrize(
    ("supplied", "strength", "origin"),
    [
        ({}, "unknown", "not_supplied"),
        ({"evidence_strength": "unknown"}, "unknown", "declared_unknown"),
        ({"evidence_strength": "this-is-not-evidence"}, "unknown", "normalizer_fallback"),
        ({"evidence_strength": "rct"}, "rct", "supplied"),
        ({"evidence_strength": " RANDOMIZED "}, "rct", "supplied"),
        ({"evidence_strength": None}, "unknown", "normalizer_fallback"),
        ({"evidence_strength": ""}, "unknown", "normalizer_fallback"),
    ],
)
def test_origin_survives_normalizer_article_storage_and_skg_intake(
    tmp_path: Path, supplied: dict[str, object], strength: str, origin: str
) -> None:
    """Removing derivation must collapse these cases and fail at the real consumer."""
    parameter = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, **supplied}
    )
    assert parameter is not None
    stored = tmp_path / "article.json"
    stored.write_text(_article(parameter).model_dump_json())
    loaded = ArticleExtractionResult.model_validate_json(stored.read_text())
    payload = loaded.empirical_parameters[0].model_dump(mode="json")
    consumer = SKGQuery._to_evidence_parameter("controlled.effect", payload)
    assert consumer is not None
    observed = consumer.model_dump(mode="json")
    assert (observed["evidence_strength"], observed.get("evidence_strength_origin")) == (
        strength,
        origin,
    )


@pytest.mark.parametrize(
    ("supplied", "origin"),
    [
        ({}, "not_supplied"),
        ({"evidence_strength": "unknown"}, "declared_unknown"),
        ({"evidence_strength": "invalid"}, "normalizer_fallback"),
        ({"evidence_strength": "rct"}, "supplied"),
    ],
)
def test_origin_survives_work_record_and_actual_raw_skg_storage(
    tmp_path: Path, supplied: dict[str, object], origin: str
) -> None:
    """A DTO-only fix must fail if the WorkRecord bridge or SQL writer drops it."""
    parameter = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, **supplied}
    )
    assert parameter is not None
    record = article_extractor._to_work_record(
        result=_article(parameter),
        raw_work={},
        topic_ids=[],
        topic_display_names=[],
        run_id="controlled",
        pass_name="",
    )
    stored = tmp_path / "work.json"
    stored.write_text(record.model_dump_json())
    db = tmp_path / "skg.duckdb"
    graph_builder.load_graph(
        records=[WorkRecord.model_validate_json(stored.read_text())], db_path=db
    )
    with duckdb.connect(str(db), read_only=True) as connection:
        (payload,) = connection.execute("SELECT parameter_json FROM ac_skg_parameters").fetchone()
    consumer = SKGQuery._to_evidence_parameter("controlled.effect", json.loads(payload))
    assert consumer is not None
    assert consumer.model_dump(mode="json").get("evidence_strength_origin") == origin
    query = SKGQuery(db, tmp_path / "index")
    try:
        (candidate,) = query.query_parameters("controlled.effect", layer="raw")
    finally:
        query.close()
    assert candidate.parameter.model_dump(mode="json")["evidence_strength_origin"] == origin


@pytest.mark.parametrize("strength", ["unknown", "rct"])
def test_historically_unmarked_value_cannot_become_a_recorded_judgment(strength: str) -> None:
    parameter = SKGQuery._to_evidence_parameter(
        "controlled.effect", {"value": 1.0, "evidence_strength": strength}
    )
    assert parameter is not None
    stored = parameter.model_dump_json()
    restored = EvidenceParameter.model_validate_json(stored)
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "unresolved"


def test_omission_stays_unsupplied_after_default_materialization() -> None:
    parameter = EvidenceParameter(name="controlled.effect", value=1.0)
    restored = EvidenceParameter.model_validate_json(parameter.model_dump_json())
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "not_supplied"


def test_intake_manufactured_unknown_is_not_a_declared_unknown() -> None:
    diagnostics: list[str] = []
    parameter = SKGQuery._to_evidence_parameter(
        "controlled.effect",
        {"value": 1.0, "evidence_strength": "invalid"},
        diagnostics=diagnostics,
    )
    assert parameter is not None
    assert "fallback:manual_evidence_parameter" in diagnostics
    restored = EvidenceParameter.model_validate_json(parameter.model_dump_json())
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "intake_fallback"


def test_merge_inherited_strength_is_not_a_judgment_about_the_kept_parameter() -> None:
    kept = article_extractor._normalize_empirical_parameter(
        {
            "name": "controlled.effect",
            "value": 1.0,
            "confidence_interval": [0.5, 1.5],
            "std_error": 0.1,
        }
    )
    donor = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, "evidence_strength": "rct"}
    )
    assert kept is not None and donor is not None
    (merged,) = _merge_numeric_parameter_lists([kept], [donor])
    restored = EvidenceParameter.model_validate_json(merged.model_dump_json())
    assert restored.evidence_strength.value == "rct"
    assert restored.std_error == 0.1
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "inherited"


def test_finalize_merge_retains_inheritance_through_storage() -> None:
    kept = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0}
    )
    donor = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, "evidence_strength": "rct"}
    )
    assert kept is not None and donor is not None
    (merged,) = resolve_finalize._merge_parameters([_article(kept), _article(donor)])
    restored = EvidenceParameter.model_validate_json(merged.model_dump_json())
    assert restored.evidence_strength.value == "rct"
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "inherited"


@pytest.mark.parametrize("supplied", [{}, {"evidence_strength": "unknown"}])
def test_methodology_inheritance_survives_simulation_sql_and_public_query(
    tmp_path: Path, supplied: dict[str, object]
) -> None:
    parameter = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, "unit": "ratio", **supplied}
    )
    assert parameter is not None
    article = _article(parameter).model_copy(update={"methodology_enum": EvidenceStrength.RCT})
    numeric = resolve_finalize._curated_numeric_rows(article, source_context={}, mode="balanced")
    assert len(numeric) == 1
    numeric_file = tmp_path / "numeric.jsonl"
    numeric_file.write_text(json.dumps(numeric[0]) + "\n")
    record = article_extractor._to_work_record(
        result=article,
        raw_work={},
        topic_ids=[],
        topic_display_names=[],
        run_id="controlled",
        pass_name="",
    )
    db = tmp_path / "simulation.duckdb"
    graph_builder.load_graph(
        records=[record], db_path=db, simulation_ready_numeric_path=numeric_file
    )
    query = SKGQuery(db, tmp_path / "index")
    try:
        (candidate,) = query.query_parameters("controlled.effect", layer="simulation")
    finally:
        query.close()
    restored = EvidenceParameter.model_validate_json(candidate.parameter.model_dump_json())
    assert restored.evidence_strength.value == "rct"
    assert restored.model_dump(mode="json").get("evidence_strength_origin") == "inherited"


def test_deterministic_rescue_marks_inherited_methodology() -> None:
    parameter = EvidenceParameter(name="controlled.effect", value=0.25)
    article = _article(parameter).model_copy(
        update={"source_basis": SourceBasis.FULLTEXT, "methodology_enum": EvidenceStrength.RCT}
    )
    rescued = _deterministic_numeric_rescue_parameters(
        bundle={
            "numeric_result_snippets": [{"text": "The effect was 0.25 (95% CI [0.15, 0.45])."}]
        },
        result=article,
    )
    assert rescued
    for parameter in rescued:
        restored = EvidenceParameter.model_validate_json(parameter.model_dump_json())
        assert restored.evidence_strength == EvidenceStrength.RCT
        assert restored.model_dump(mode="json")["evidence_strength_origin"] == "inherited"


@pytest.mark.parametrize("origin", ["supplied", "declared_unknown", "inherited"])
def test_an_origin_marker_without_a_strength_cannot_create_a_judgment(origin: str) -> None:
    with pytest.raises(ValueError):
        EvidenceParameter.model_validate(
            {"name": "controlled.effect", "value": 1.0, "evidence_strength_origin": origin}
        )


def test_intake_retains_a_recorded_unknown_when_an_unrelated_field_needs_fallback() -> None:
    parameter = article_extractor._normalize_empirical_parameter(
        {"name": "controlled.effect", "value": 1.0, "evidence_strength": "unknown"}
    )
    assert parameter is not None
    stored = json.loads(parameter.model_dump_json())
    diagnostics: list[str] = []
    consumer = SKGQuery._to_evidence_parameter(
        parameter.name, {**stored, "parameter_type": "invalid"}, diagnostics=diagnostics
    )
    assert consumer is not None
    assert "fallback:manual_evidence_parameter" in diagnostics
    assert consumer.model_dump(mode="json")["evidence_strength_origin"] == "declared_unknown"


def test_legacy_simulation_schema_upgrade_does_not_invent_an_origin(tmp_path: Path) -> None:
    db = tmp_path / "legacy.duckdb"
    with duckdb.connect(str(db)) as connection:
        connection.execute(skg_store.SKG_DDL)
        connection.execute("DROP INDEX idx_ac_skg_sim_params_name")
        connection.execute("DROP INDEX idx_ac_skg_sim_params_article")
        connection.execute(
            "ALTER TABLE ac_skg_simulation_parameters DROP COLUMN evidence_strength_origin"
        )
        connection.execute(
            "INSERT INTO ac_skg_simulation_parameters "
            "(numeric_id, openalex_id, canonical_name, estimate_type, point_estimate, evidence_strength) "
            "VALUES ('legacy', 'legacy', 'controlled.effect', 'point', 1.0, 'unknown')"
        )
    for upgrade in (False, True):
        if upgrade:
            with duckdb.connect(str(db)) as connection:
                skg_store.ensure_skg_schema(connection)
                assert connection.execute(
                    "SELECT evidence_strength_origin FROM ac_skg_simulation_parameters"
                ).fetchone() == (None,)
        query = SKGQuery(db, tmp_path / "index")
        try:
            (candidate,) = query.query_parameters("controlled.effect", layer="simulation")
        finally:
            query.close()
        assert (
            candidate.parameter.model_dump(mode="json")["evidence_strength_origin"] == "unresolved"
        )
