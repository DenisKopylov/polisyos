"""Tests for KnowledgeToolkit (scientist/agent/knowledge_tools.py)."""

from __future__ import annotations

from polisyos.academic.knowledge.types import (
    ParameterPrior,
    WorkSearchResult,
)
from polisyos.datasets.knowledge.types import DatasetSearchResult
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit


class _MockDatasetCatalog:
    """Minimal mock for DatasetCatalogGraph."""

    def search_datasets(self, query, *, domain_filter=None, top_k=10):
        return [
            DatasetSearchResult(
                id="ds-1",
                title=f"Mock dataset for {query}",
                publisher="mock",
                similarity=0.9,
            ),
        ]

    def find_by_polisyos_metric(self, metric_name, *, top_k=20):
        if metric_name == "gdp":
            return [
                DatasetSearchResult(
                    id="ds-gdp-1",
                    title="GDP Dataset",
                    publisher="worldbank",
                    polisyos_metrics=["gdp"],
                    similarity=1.0,
                ),
            ]
        return []

    def get_connector_params(self, dataset_id):
        if dataset_id == "ds-gdp-1":
            return {"type": "worldbank", "params": {"indicator_id": "NY.GDP.MKTP.CD"}}
        return None


class _MockScholarGraph:
    """Minimal mock for ScholarKnowledgeGraph."""

    def find_relevant_works(self, query, *, domain=None, top_k=20):
        return [
            WorkSearchResult(
                id="w-1",
                title=f"Study about {query}",
                year=2023,
                trust_score=0.8,
                similarity=0.9,
            ),
        ]

    def get_parameter_prior(self, variable, domain=None, country=None):
        if variable == "min_wage_elasticity":
            return ParameterPrior(
                variable=variable,
                prior_mean=-0.1,
                prior_std=0.05,
                prior_low=-0.2,
                prior_high=0.0,
                n_studies=10,
                best_design="rct",
                as_calibration_prior={"distribution": "normal", "mean": -0.1, "std": 0.05},
            )
        return None

    def find_causal_evidence(self, cause, effect, *, min_trust=0.5):
        return []

    def get_mechanism_evidence(self, mechanism_name, *, top_k=20):
        return []


def test_toolkit_no_graphs() -> None:
    toolkit = KnowledgeToolkit()
    assert not toolkit.has_dataset_catalog
    assert not toolkit.has_scholar_graph
    assert toolkit.search_datasets("GDP") == []
    assert toolkit.get_parameter_prior("test") is None
    assert toolkit.find_causal_evidence("X", "Y") == []


def test_toolkit_search_datasets() -> None:
    toolkit = KnowledgeToolkit(dataset_catalog=_MockDatasetCatalog())
    assert toolkit.has_dataset_catalog
    results = toolkit.search_datasets("GDP per capita")
    assert len(results) == 1
    assert "Mock dataset" in results[0].title


def test_toolkit_find_datasets_for_metric() -> None:
    toolkit = KnowledgeToolkit(dataset_catalog=_MockDatasetCatalog())
    results = toolkit.find_datasets_for_metric("gdp")
    assert len(results) == 1
    assert results[0].id == "ds-gdp-1"


def test_toolkit_get_dataset_connector() -> None:
    toolkit = KnowledgeToolkit(dataset_catalog=_MockDatasetCatalog())
    connector = toolkit.get_dataset_connector("ds-gdp-1")
    assert connector is not None
    assert connector["type"] == "worldbank"


def test_toolkit_search_evidence() -> None:
    toolkit = KnowledgeToolkit(scholar_graph=_MockScholarGraph())
    assert toolkit.has_scholar_graph
    results = toolkit.search_evidence("minimum wage")
    assert len(results) == 1
    assert "minimum wage" in results[0].title


def test_toolkit_get_parameter_prior() -> None:
    toolkit = KnowledgeToolkit(scholar_graph=_MockScholarGraph())
    prior = toolkit.get_parameter_prior("min_wage_elasticity")
    assert prior is not None
    assert prior.prior_mean == -0.1
    assert prior.n_studies == 10
    assert prior.as_calibration_prior["distribution"] == "normal"


def test_toolkit_get_parameter_prior_missing() -> None:
    toolkit = KnowledgeToolkit(scholar_graph=_MockScholarGraph())
    prior = toolkit.get_parameter_prior("nonexistent_variable")
    assert prior is None


def test_toolkit_format_dataset_context() -> None:
    toolkit = KnowledgeToolkit(dataset_catalog=_MockDatasetCatalog())
    results = toolkit.search_datasets("GDP")
    text = toolkit.format_dataset_context(results)
    assert "AVAILABLE DATASETS" in text
    assert "Mock dataset" in text


def test_toolkit_format_evidence_context() -> None:
    toolkit = KnowledgeToolkit(scholar_graph=_MockScholarGraph())
    results = toolkit.search_evidence("minimum wage")
    text = toolkit.format_evidence_context(results)
    assert "ACADEMIC EVIDENCE" in text


def test_toolkit_format_prior_context() -> None:
    toolkit = KnowledgeToolkit(scholar_graph=_MockScholarGraph())
    prior = toolkit.get_parameter_prior("min_wage_elasticity")
    text = toolkit.format_prior_context(prior)
    assert "LITERATURE PRIOR" in text
    assert "-0.1" in text
