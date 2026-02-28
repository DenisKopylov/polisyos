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
    ci = [e for e in estimates if e.pattern_name == "confidence_interval"]
    assert len(ci) >= 1
    assert ci[0].ci_low == pytest.approx(0.15)
    assert ci[0].ci_high == pytest.approx(0.45)


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
