"""Tests for dataset knowledge types."""

from __future__ import annotations

import pytest

from polisyos.datasets.knowledge.types import DatasetRecord, DatasetSearchResult, DistributionRecord


def test_dataset_search_result_embedding_text() -> None:
    result = DatasetSearchResult(
        id="ds-1",
        title="GDP per capita",
        description="Annual GDP per capita by country",
        keywords=["GDP", "economics"],
        variables=["NY.GDP.PCAP.CD"],
    )
    text = result.embedding_text()
    assert "GDP per capita" in text
    assert "Annual GDP" in text
    assert "economics" in text
    assert "NY.GDP.PCAP.CD" in text


def test_dataset_search_result_frozen() -> None:
    result = DatasetSearchResult(id="ds-1", title="Test")
    with pytest.raises(Exception):
        result.title = "Changed"


def test_dataset_record_extra_forbid() -> None:
    with pytest.raises(Exception):
        DatasetRecord(id="ds-1", title="Test", unknown_field="value")


def test_distribution_record_defaults() -> None:
    dist = DistributionRecord()
    assert dist.id == ""
    assert dist.url == ""
    assert dist.quality_score == 0.0
