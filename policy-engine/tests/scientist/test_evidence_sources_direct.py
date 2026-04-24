from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.scientist.evidence_sources import (
    EvidenceSourcesConfig,
    merge_evidence_sources_payload,
    normalize_evidence_sources_config,
)

_FIELD_NAMES = [
    "academic_db_path",
    "academic_index_dir",
    "datasets_db_path",
    "legal_db_path",
    "benchmark_suite_path",
    "benchmark_report_path",
    "academic_demand_backlog_path",
]

_PATH_TEXT = st.text(
    alphabet="abc/_-.",
    min_size=1,
    max_size=12,
)


def test_nested_evidence_sources_override_flat_fields() -> None:
    config = normalize_evidence_sources_config(
        {"legal_db_path": "/tmp/flat.duckdb"},
        {"evidence_sources": {"legal_db_path": "/tmp/nested.duckdb"}},
    )

    assert config.legal_db_path == "/tmp/nested.duckdb"


@given(st.fixed_dictionaries({field: st.one_of(st.none(), _PATH_TEXT) for field in _FIELD_NAMES}))
@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_merge_roundtrip_preserves_normalized_values(payload: dict[str, str | None]) -> None:
    normalized = normalize_evidence_sources_config(payload)
    merged = merge_evidence_sources_payload({"evidence_sources": {"ignored": True}}, normalized)
    reloaded = EvidenceSourcesConfig.model_validate(
        {key: merged.get(key) for key in _FIELD_NAMES if merged.get(key) is not None}
    )

    assert reloaded == EvidenceSourcesConfig.model_validate(
        {key: value for key, value in payload.items() if value is not None}
    )
    assert "evidence_sources" not in merged
