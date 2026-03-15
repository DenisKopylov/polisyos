"""Tests for KnowledgeToolkit (scientist/agent/knowledge_tools.py)."""

from __future__ import annotations

from polisyos.academic.knowledge.types import (
    ParameterPrior,
    WorkSearchResult,
)
from polisyos.datasets.knowledge.types import DatasetSearchResult
from polisyos.lex.knowledge.types import LegalFactResult, LegalProvisionResult
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
            return {"type": "worldbank.wdi", "params": {"indicator_id": "NY.GDP.MKTP.CD"}}
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

    def get_parameter_prior(self, variable, domain=None, country=None, *, prefer_simulation_ready=True):
        del prefer_simulation_ready
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

    def find_causal_evidence(self, cause, effect, *, min_trust=0.5, support_mode="exact"):
        del cause, effect, min_trust, support_mode
        return []

    def get_mechanism_evidence(self, mechanism_name, *, top_k=20):
        return []


class _MockLegalGraph:
    """Minimal mock for LegalKnowledgeGraph."""

    def hybrid_search(
        self,
        query,
        *,
        top_k=20,
        trust_tier="grounded_fact",
        jurisdiction="UA",
        domain=None,
        as_of=None,
        include_candidates=False,
    ):
        return [
            LegalFactResult(
                fact_id="lf-1",
                subject_name="state",
                predicate="requires",
                object_name="license",
                fact_text=f"Mock legal fact for {query}",
                confidence=0.9,
                norm_type="obligation",
                trust_tier=trust_tier,
                jurisdiction=jurisdiction or "UA",
                top_domain=domain or "",
                doc_name="Mock law",
                doc_reestr_code="123",
                provision_citation="стаття 1",
                similarity=0.95,
            )
        ]

    def search_provisions(self, query, *, top_k=10, min_similarity=0.3):
        return [
            LegalProvisionResult(
                provision_id="prov-1",
                doc_name="Mock law",
                doc_reestr_code="123",
                citation_label="стаття 1",
                kind="article",
                provision_text_preview=f"Provision for {query}",
                struct_kind="article",
                section_role="normative_unit",
                fallback_allowed_for_reasoning=True,
                similarity=0.8,
            )
        ]

    def find_legal_constraints(self, *, query=None, top_k=50, jurisdiction="UA", domain=None, as_of=None):
        return self.hybrid_search(
            query or "constraints",
            top_k=top_k,
            trust_tier="normative_fact",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )

    def search_facts_with_threshold(self, metric, *, top_k=50, jurisdiction="UA", domain=None, as_of=None):
        return self.hybrid_search(
            metric,
            top_k=top_k,
            trust_tier="normative_fact",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )

    def get_applicable_norms(self, *, domain=None, jurisdiction="UA", as_of=None, top_k=100):
        return self.hybrid_search(
            domain or "norms",
            top_k=top_k,
            trust_tier="normative_fact",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )


def test_toolkit_no_graphs() -> None:
    toolkit = KnowledgeToolkit()
    assert not toolkit.has_dataset_catalog
    assert not toolkit.has_scholar_graph
    assert not toolkit.has_legal_graph
    assert toolkit.search_datasets("GDP") == []
    assert toolkit.get_parameter_prior("test") is None
    assert toolkit.find_causal_evidence("X", "Y") == []
    assert toolkit.search_legal_facts("ліцензія") == []


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
    assert connector["type"] == "worldbank.wdi"


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


def test_toolkit_legal_methods() -> None:
    toolkit = KnowledgeToolkit(legal_graph=_MockLegalGraph())
    assert toolkit.has_legal_graph

    facts = toolkit.search_legal_facts("ліцензія", domain="transport")
    assert len(facts) == 1
    assert facts[0].trust_tier == "grounded_fact"
    assert facts[0].top_domain == "transport"

    provisions = toolkit.search_legal_provisions("дозвіл")
    assert len(provisions) == 1
    assert provisions[0].struct_kind == "article"

    constraints = toolkit.find_legal_constraints(domain="transport")
    assert len(constraints) == 1
    assert constraints[0].trust_tier == "normative_fact"

    thresholds = toolkit.search_legal_thresholds("vat_rate")
    assert len(thresholds) == 1
    assert thresholds[0].trust_tier == "normative_fact"

    norms = toolkit.get_applicable_norms(domain="transport")
    assert len(norms) == 1
    assert norms[0].jurisdiction == "UA"

    formatted = toolkit.format_legal_context(constraints)
    assert "LEGAL CONTEXT" in formatted
    assert "normative_fact" in formatted
