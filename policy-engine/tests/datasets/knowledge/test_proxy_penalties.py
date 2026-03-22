from __future__ import annotations

from pathlib import Path

from polisyos.datasets.knowledge.proxy_penalties import (
    load_proxy_metric_alignments,
    metric_name_from_alignment_evidence,
    resolve_proxy_penalty,
)


def test_load_proxy_metric_alignments_reads_yaml() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "dataset_catalog" / "proxy_metric_alignments.yaml"
    mappings = load_proxy_metric_alignments(path)

    assert "health_spending" in mappings
    assert mappings["health_spending"][0].canonical_var == "health_outcomes"


def test_resolve_proxy_penalty_applies_country_and_year_overrides() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "dataset_catalog" / "proxy_metric_alignments.yaml"

    assert resolve_proxy_penalty(
        metric_name="health_spending",
        canonical_var="health_outcomes",
        base_penalty=0.15,
        country_code="UA",
        year=2020,
        path=path,
    ) == 0.12
    assert resolve_proxy_penalty(
        metric_name="health_spending",
        canonical_var="health_outcomes",
        base_penalty=0.15,
        country_code="PL",
        year=2024,
        path=path,
    ) == 0.18


def test_metric_name_from_alignment_evidence_extracts_proxy_metric() -> None:
    assert metric_name_from_alignment_evidence("metric_binding_proxy:health_spending") == "health_spending"
