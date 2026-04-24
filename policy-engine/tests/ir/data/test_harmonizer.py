"""Tests for DomainHarmonizer and HarmonizationReport (Track E, tasks E1 & E2)."""

from __future__ import annotations

import pandas as pd
import pytest

from polisyos.ir.data.harmonizer import (
    DomainHarmonizer,
    MissingVariableStrategy,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "income": [30_000, 50_000, 80_000],
            "age": [25, 35, 45],
            "employed": [1, 1, 0],
        }
    )


@pytest.fixture
def target_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "income_level": [1.0, 2.0, 3.0],
            "age_years": [25.0, 35.0, 45.0],
            "employment_status": [1.0, 1.0, 0.0],
        }
    )


# ---------------------------------------------------------------------------
# E1 — basic alignment tests
# ---------------------------------------------------------------------------


def test_align_perfect_match() -> None:
    """Identical dtypes across the mapping → no mismatches, all variables harmonized."""
    src = pd.DataFrame({"X": [1.0, 2.0], "Y": [0.1, 0.2]})
    tgt = pd.DataFrame({"treatment": [1.0, 0.0], "outcome": [0.1, 0.3]})
    mapping = {"X": "treatment", "Y": "outcome"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
        source_dataset_ref="src",
        target_dataset_ref="tgt",
    )

    assert report.is_compatible
    assert set(report.harmonized_variables) == {"treatment", "outcome"}
    assert len(report.type_mismatches) == 0
    assert len(report.errors) == 0
    assert len(report.missing_variables) == 0
    assert report.n_source_obs == 2
    assert report.n_target_obs == 2


def test_align_numeric_coercion(source_df: pd.DataFrame, target_df: pd.DataFrame) -> None:
    """int64 → float64 is coercible: recorded in type_mismatches but still harmonized."""
    mapping = {
        "income": "income_level",
        "age": "age_years",
        "employed": "employment_status",
    }
    report = DomainHarmonizer.align(
        source_df,
        target_df,
        mapping,
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
    )

    assert report.is_compatible
    assert set(report.harmonized_variables) == {"income_level", "age_years", "employment_status"}
    # All three map int64 → float64
    assert len(report.type_mismatches) == 3
    for m in report.type_mismatches:
        assert m.is_coercible
        assert m.coercion_applied is not None
    assert len(report.resolved_mappings) == 3


def test_align_non_coercible_excluded() -> None:
    """object ↔ float64 is not coercible: variable excluded from harmonized_variables."""
    src = pd.DataFrame({"label": ["low", "high", "medium"]})
    tgt = pd.DataFrame({"income_level": [1.0, 2.0, 3.0]})
    mapping = {"label": "income_level"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.EXCLUDE_UNIT,
    )

    assert "income_level" not in report.harmonized_variables
    assert "income_level" in report.excluded_variables
    assert len(report.type_mismatches) == 1
    assert not report.type_mismatches[0].is_coercible
    # warnings should mention the exclusion
    assert any("income_level" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# E2 — missing variable strategy tests
# ---------------------------------------------------------------------------


def test_align_missing_impute_mean() -> None:
    """IMPUTE_MEAN: missing target var is added to harmonized_variables with imputed_value."""
    src = pd.DataFrame({"X": [1.0, 2.0, 3.0]})
    tgt = pd.DataFrame({"X_mapped": [1.0, 2.0, 3.0], "missing_var": [10.0, 20.0, 30.0]})
    mapping = {"X": "X_mapped"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.IMPUTE_MEAN,
    )

    assert report.is_compatible
    assert "missing_var" in report.harmonized_variables
    assert len(report.missing_variables) == 1
    rec = report.missing_variables[0]
    assert rec.target_variable == "missing_var"
    assert rec.strategy_applied == MissingVariableStrategy.IMPUTE_MEAN
    assert rec.imputed_value is not None
    assert isinstance(rec.imputed_value, float)


def test_align_missing_exclude_unit() -> None:
    """EXCLUDE_UNIT: missing target var goes to excluded_variables, not harmonized."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"X_mapped": [1.0, 2.0], "extra": [0.0, 1.0]})
    mapping = {"X": "X_mapped"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.EXCLUDE_UNIT,
    )

    assert report.is_compatible
    assert "extra" not in report.harmonized_variables
    assert "extra" in report.excluded_variables
    assert len(report.missing_variables) == 1
    assert report.missing_variables[0].strategy_applied == MissingVariableStrategy.EXCLUDE_UNIT


def test_align_missing_raise_error() -> None:
    """RAISE_ERROR (default): missing target var makes is_compatible=False."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"X_mapped": [1.0, 2.0], "required_var": [0.0, 1.0]})
    mapping = {"X": "X_mapped"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.RAISE_ERROR,
    )

    assert not report.is_compatible
    assert len(report.errors) == 1
    assert "required_var" in report.errors[0]


def test_align_missing_impute_model_raises() -> None:
    """IMPUTE_MODEL raises NotImplementedError immediately."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"X_mapped": [1.0, 2.0], "missing": [0.0, 1.0]})
    mapping = {"X": "X_mapped"}

    with pytest.raises(NotImplementedError):
        DomainHarmonizer.align(
            src,
            tgt,
            mapping,
            missing_strategy=MissingVariableStrategy.IMPUTE_MODEL,
        )


def test_align_unknown_source_column_is_warning() -> None:
    """A source column that doesn't exist → warning, not an error."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"Y": [1.0, 2.0]})
    mapping = {"nonexistent_col": "Y"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.EXCLUDE_UNIT,
    )

    assert any("nonexistent_col" in w for w in report.warnings)
    # "Y" ends up as a missing variable (no mapping resolved), handled by strategy
    assert "Y" not in report.harmonized_variables


def test_align_unknown_target_variable_is_warning() -> None:
    """A target variable that doesn't exist in target_df → warning, mapping skipped."""
    src = pd.DataFrame({"X": [1.0, 2.0]})
    tgt = pd.DataFrame({"Y": [1.0, 2.0]})
    mapping = {"X": "ghost_variable"}

    report = DomainHarmonizer.align(
        src,
        tgt,
        mapping,
        missing_strategy=MissingVariableStrategy.EXCLUDE_UNIT,
    )

    assert any("ghost_variable" in w for w in report.warnings)


def test_align_result_is_frozen() -> None:
    """HarmonizationReport is a frozen Pydantic model."""
    src = pd.DataFrame({"X": [1.0]})
    tgt = pd.DataFrame({"Y": [1.0]})
    report = DomainHarmonizer.align(src, tgt, {"X": "Y"})
    with pytest.raises(Exception):  # ValidationError or TypeError from frozen=True
        report.source_dataset_ref = "modified"  # type: ignore[misc]


def test_align_dataset_refs_propagated() -> None:
    """source_dataset_ref and target_dataset_ref are stored in the report."""
    src = pd.DataFrame({"X": [1.0]})
    tgt = pd.DataFrame({"Y": [1.0]})
    report = DomainHarmonizer.align(
        src,
        tgt,
        {"X": "Y"},
        source_dataset_ref="rct_2024",
        target_dataset_ref="policy_region",
    )
    assert report.source_dataset_ref == "rct_2024"
    assert report.target_dataset_ref == "policy_region"
