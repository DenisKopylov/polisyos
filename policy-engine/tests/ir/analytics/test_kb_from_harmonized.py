"""Tests for DataKnowledgeBase.from_harmonized() (Track E, task E4)."""

from __future__ import annotations

import pandas as pd
import pytest

from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
)
from polisyos.ir.analytics.knowledge_base import (
    DataKnowledgeBase,
    DistributionAvailability,
)
from polisyos.ir.data.harmonizer import DomainHarmonizer, MissingVariableStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clean_report(
    *,
    source_dataset_ref: str = "src",
    target_dataset_ref: str = "tgt",
):
    """Return a compatible HarmonizationReport with no mismatches."""
    src = pd.DataFrame({"X": [1.0, 2.0], "Y": [0.1, 0.2]})
    tgt = pd.DataFrame({"treatment": [1.0, 0.0], "outcome": [0.1, 0.3]})
    return DomainHarmonizer.align(
        src,
        tgt,
        {"X": "treatment", "Y": "outcome"},
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
        source_dataset_ref=source_dataset_ref,
        target_dataset_ref=target_dataset_ref,
    )


def _make_coercion_report():
    """Return a compatible report with numeric coercions (int64→float64)."""
    src = pd.DataFrame({"X": [1, 2, 3]})  # int64
    tgt = pd.DataFrame({"X_f": [1.0, 2.0, 3.0]})  # float64
    return DomainHarmonizer.align(
        src,
        tgt,
        {"X": "X_f"},
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
    )


def _make_imputed_report():
    """Return a compatible report with an imputed missing variable."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"X_mapped": [1.0, 2.0], "extra": [0.0, 1.0]})
    return DomainHarmonizer.align(
        src,
        tgt,
        {"X": "X_mapped"},
        missing_strategy=MissingVariableStrategy.IMPUTE_MEAN,
    )


def _make_error_report():
    """Return an incompatible HarmonizationReport (RAISE_ERROR triggered)."""
    src = pd.DataFrame({"X": [1.0]})
    tgt = pd.DataFrame({"Y": [1.0], "missing": [0.0]})
    return DomainHarmonizer.align(
        src,
        tgt,
        {"X": "Y"},
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_from_harmonized_available() -> None:
    """Clean report → source entry with AVAILABLE availability."""
    report = _make_clean_report()
    kb = DataKnowledgeBase.from_harmonized(report)

    assert len(kb.datasets) == 2  # source + target
    src_entry = next(e for e in kb.datasets if e.domain is DistributionDomain.SOURCE)
    assert src_entry.availability is DistributionAvailability.AVAILABLE
    assert set(src_entry.variables) == {"treatment", "outcome"}
    assert src_entry.dataset_ref == "src"


def test_from_harmonized_partial_on_coercion() -> None:
    """Report with type mismatches → source entry with PARTIAL availability."""
    report = _make_coercion_report()
    kb = DataKnowledgeBase.from_harmonized(report)

    src_entry = next(e for e in kb.datasets if e.domain is DistributionDomain.SOURCE)
    assert src_entry.availability is DistributionAvailability.PARTIAL


def test_from_harmonized_partial_on_imputed() -> None:
    """Report with imputed missing vars → source entry with PARTIAL availability."""
    report = _make_imputed_report()
    kb = DataKnowledgeBase.from_harmonized(report)

    src_entry = next(e for e in kb.datasets if e.domain is DistributionDomain.SOURCE)
    assert src_entry.availability is DistributionAvailability.PARTIAL


def test_from_harmonized_raises_on_errors() -> None:
    """Incompatible report (errors present) → ValueError."""
    report = _make_error_report()
    assert not report.is_compatible
    with pytest.raises(ValueError, match="incompatible"):
        DataKnowledgeBase.from_harmonized(report)


def test_from_harmonized_two_entries() -> None:
    """When target_dataset_ref is set, KB has entries for both source and target domains."""
    report = _make_clean_report(source_dataset_ref="rct", target_dataset_ref="census")
    kb = DataKnowledgeBase.from_harmonized(report)

    assert len(kb.datasets) == 2
    domains = {e.domain for e in kb.datasets}
    assert DistributionDomain.SOURCE in domains
    assert DistributionDomain.TARGET in domains

    tgt_entry = next(e for e in kb.datasets if e.domain is DistributionDomain.TARGET)
    assert tgt_entry.dataset_ref == "census"
    assert tgt_entry.availability is DistributionAvailability.AVAILABLE


def test_from_harmonized_source_n_obs() -> None:
    """n_obs from the report is stored in the DatasetEntry."""
    report = _make_clean_report()
    kb = DataKnowledgeBase.from_harmonized(report)
    src_entry = next(e for e in kb.datasets if e.domain is DistributionDomain.SOURCE)
    assert src_entry.n_obs == report.n_source_obs


def test_from_harmonized_custom_domains() -> None:
    """Custom source_domain and target_domain kwargs are respected."""
    report = _make_clean_report()
    kb = DataKnowledgeBase.from_harmonized(
        report,
        source_domain=DistributionDomain.EXPERIMENTAL,
        target_domain=DistributionDomain.TARGET,
    )
    exp_entry = next((e for e in kb.datasets if e.domain is DistributionDomain.EXPERIMENTAL), None)
    assert exp_entry is not None


def test_kb_score_estimand_from_harmonized() -> None:
    """End-to-end: harmonize → KB → score_estimand feasibility check."""
    src = pd.DataFrame({"income": [1.0, 2.0, 3.0], "employed": [1.0, 0.0, 1.0]})
    tgt = pd.DataFrame({"Y": [1.0, 2.0, 3.0], "T": [1.0, 0.0, 1.0]})
    report = DomainHarmonizer.align(
        src,
        tgt,
        {"income": "Y", "employed": "T"},
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
        source_dataset_ref="study_data",
        target_dataset_ref="target_pop",
    )

    kb = DataKnowledgeBase.from_harmonized(report)

    # Build a simple estimand AST: P(Y | T, domain=source)
    dist_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T",),
        dataset_ref="study_data",
    )
    ast = EstimandAST(
        query_str="P(Y|T)",
        root=dist_ref,
        treatment="T",
        outcome="Y",
        all_variables=("Y", "T"),
    )

    score, missing = kb.score_estimand(ast)
    assert score > 0.0
    # "study_data" is registered → should be found
    assert "study_data" not in missing
