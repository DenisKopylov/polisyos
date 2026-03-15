"""Tests for academic abstract parser + regex extraction."""

from __future__ import annotations

from polisyos.academic.batch.parser import (
    classify_study_design,
    extract_numerical_estimates,
    reconstruct_abstract,
)


# ---------------------------------------------------------------------------
# Abstract reconstruction
# ---------------------------------------------------------------------------


def test_reconstruct_abstract_basic() -> None:
    inverted = {"We": [0], "find": [1], "a": [2], "positive": [3], "effect": [4]}
    text = reconstruct_abstract(inverted)
    assert text == "We find a positive effect"


def test_reconstruct_abstract_out_of_order() -> None:
    inverted = {"effect": [4], "positive": [3], "a": [2], "find": [1], "We": [0]}
    text = reconstruct_abstract(inverted)
    assert text == "We find a positive effect"


def test_reconstruct_abstract_repeated_word() -> None:
    inverted = {"the": [0, 3], "cat": [1], "sat": [2], "mat": [4]}
    text = reconstruct_abstract(inverted)
    assert text == "the cat sat the mat"


def test_reconstruct_abstract_empty() -> None:
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""


# ---------------------------------------------------------------------------
# Numerical extraction
# ---------------------------------------------------------------------------


def test_extract_elasticity_of() -> None:
    abstract = "We find an elasticity of 0.35 for minimum wage on employment."
    estimates = extract_numerical_estimates(abstract, ["minimum wage"])
    assert len(estimates) >= 1
    est = estimates[0]
    assert est.value == pytest.approx(0.35)
    assert est.pattern_name == "elasticity_of"


def test_extract_change_by_percent() -> None:
    abstract = "The policy increased by 2.3 percent relative to the control group."
    estimates = extract_numerical_estimates(abstract)
    assert len(estimates) >= 1
    assert any(e.value == pytest.approx(2.3) for e in estimates)


def test_extract_beta_se() -> None:
    abstract = "The coefficient was (β = -0.12, SE = 0.04) in our main specification."
    estimates = extract_numerical_estimates(abstract)
    assert len(estimates) >= 1
    est = [e for e in estimates if e.pattern_name == "beta_se"]
    assert len(est) >= 1
    assert est[0].value == pytest.approx(-0.12)
    assert est[0].std_error == pytest.approx(0.04)


def test_extract_confidence_interval() -> None:
    abstract = "The effect was 0.25 (95% CI [0.15, 0.45])."
    estimates = extract_numerical_estimates(abstract)
    with_value = [e for e in estimates if e.pattern_name == "value_with_confidence_interval"]
    assert len(with_value) >= 1
    assert with_value[0].value == pytest.approx(0.25)
    assert with_value[0].ci_low == pytest.approx(0.15)
    assert with_value[0].ci_high == pytest.approx(0.45)
    ci = [e for e in estimates if e.pattern_name == "confidence_interval"]
    assert len(ci) >= 1
    assert ci[0].ci_low == pytest.approx(0.15)
    assert ci[0].ci_high == pytest.approx(0.45)


def test_extract_generic_coefficient_se() -> None:
    abstract = "The coefficient is 0.18 (SE = 0.04) for employment."
    estimates = extract_numerical_estimates(abstract)
    rows = [e for e in estimates if e.pattern_name == "coefficient_se"]
    assert len(rows) >= 1
    assert rows[0].value == pytest.approx(0.18)
    assert rows[0].std_error == pytest.approx(0.04)


def test_extract_change_by_with_confidence_interval() -> None:
    abstract = "The reform increased employment by 4 percentage points (95% CI 2.1 to 5.9)."
    estimates = extract_numerical_estimates(abstract)
    rows = [e for e in estimates if e.pattern_name == "change_by_with_confidence_interval"]
    assert len(rows) >= 1
    assert rows[0].value == pytest.approx(4.0)
    assert rows[0].ci_low == pytest.approx(2.1)
    assert rows[0].ci_high == pytest.approx(5.9)
    assert rows[0].unit == "pp"


def test_extract_change_by_with_standard_error() -> None:
    abstract = "The shock increased the probability of democratization by 1.3 percentage points (standard error=0.45)."
    estimates = extract_numerical_estimates(abstract)
    rows = [e for e in estimates if e.pattern_name == "change_by_with_standard_error"]
    assert len(rows) >= 1
    assert rows[0].value == pytest.approx(1.3)
    assert rows[0].std_error == pytest.approx(0.45)
    assert rows[0].unit == "pp"


def test_extract_table_estimate_std_error_rows() -> None:
    abstract = (
        "TABLE D.I MODEL RESULTS ESTIMATING WITH GAUSSIAN MIXTURE NOISE. "
        "Panel A: Estimated Parameters Symbol Estimate (Std. Error) "
        "R&D elasticity of innovation γ 0.1980 (0.0183) "
        "Manager private R&D benefits φe 0.1718 (0.0094)"
    )
    estimates = extract_numerical_estimates(abstract)
    rows = [e for e in estimates if e.pattern_name == "table_estimate_std_error"]
    assert len(rows) >= 2
    assert rows[0].value == pytest.approx(0.1980)
    assert rows[0].std_error == pytest.approx(0.0183)
    assert "elasticity of innovation" in rows[0].variable_hint.lower()


def test_extract_odds_ratio_preserves_ratio_unit() -> None:
    abstract = "OR = 1.25 (95% CI: 1.10-1.42)"
    estimates = extract_numerical_estimates(abstract)
    rows = [e for e in estimates if e.pattern_name == "odds_ratio"]
    assert len(rows) >= 1
    assert rows[0].unit == "odds_ratio"


def test_extract_range_from_to() -> None:
    abstract = "Effect sizes were ranging from 0.1 to 0.5 across studies."
    estimates = extract_numerical_estimates(abstract)
    rng = [e for e in estimates if e.pattern_name == "range_from_to"]
    assert len(rng) >= 1
    assert rng[0].ci_low == pytest.approx(0.1)
    assert rng[0].ci_high == pytest.approx(0.5)
    # Midpoint used as value
    assert rng[0].value == pytest.approx(0.3)


def test_extract_no_matches() -> None:
    abstract = "This paper discusses the history of economic thought."
    estimates = extract_numerical_estimates(abstract)
    assert estimates == []


def test_extract_empty_abstract() -> None:
    assert extract_numerical_estimates("") == []


# ---------------------------------------------------------------------------
# Study design classification
# ---------------------------------------------------------------------------


def test_classify_meta_analysis() -> None:
    assert classify_study_design("We conduct a meta-analysis of 50 studies.") == "meta-analysis"


def test_classify_rct() -> None:
    assert classify_study_design("A randomized controlled trial was conducted.") == "rct"


def test_classify_did() -> None:
    assert classify_study_design("Using difference-in-differences we estimate...") == "did"


def test_classify_iv() -> None:
    assert classify_study_design("Using instrumental variable estimation (2SLS)...") == "iv"


def test_classify_ols() -> None:
    assert classify_study_design("We use OLS regression with controls.") == "ols"


def test_classify_fixed_effects() -> None:
    assert classify_study_design("Panel data with fixed effects model.") == "fe"


def test_classify_empty() -> None:
    assert classify_study_design("") == ""


def test_classify_no_match() -> None:
    assert classify_study_design("We discuss the topic.") == ""


# Need pytest for approx
import pytest  # noqa: E402
