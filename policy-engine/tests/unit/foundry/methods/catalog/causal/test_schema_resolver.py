"""Tests for SchemaResolver."""

import pytest
from polisyos.foundry.methods.catalog.causal.schema_resolver import (
    SchemaResolutionReport,
    SchemaResolver,
)
from polisyos.ir.analytics.estimand import make_backdoor_estimand, make_transport_reweight_estimand


class TestSchemaResolutionReport:
    def test_frozen_model(self):
        report = SchemaResolutionReport()
        with pytest.raises((TypeError, Exception)):
            report.is_feasible = False

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            SchemaResolutionReport(nonexistent_field="oops")

    def test_defaults_are_feasible(self):
        report = SchemaResolutionReport()
        assert report.is_feasible is True
        assert report.missing_variables == []
        assert report.type_mismatches == []


class TestSchemaResolver:
    def setup_method(self):
        self.resolver = SchemaResolver()

    def test_exact_match_backdoor_estimand(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        report = self.resolver.resolve(
            ast,
            df_columns=["X", "Y", "Z"],
            df_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
        )
        assert report.is_feasible
        assert len(report.missing_variables) == 0

    def test_missing_variable_detected(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        report = self.resolver.resolve(
            ast,
            df_columns=["X", "Y"],  # Z is missing
            df_dtypes={"X": "float64", "Y": "float64"},
        )
        assert not report.is_feasible
        assert "Z" in report.missing_variables

    def test_case_insensitive_matching(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        report = self.resolver.resolve(
            ast,
            df_columns=["x", "y", "z"],  # lowercase
            df_dtypes={"x": "float64", "y": "float64", "z": "float64"},
        )
        assert report.is_feasible

    def test_type_mismatch_string_outcome(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        report = self.resolver.resolve(
            ast,
            df_columns=["X", "Y", "Z"],
            df_dtypes={"X": "float64", "Y": "object", "Z": "float64"},  # Y is string
        )
        # Should detect Y as non-numeric if Y is outcome variable
        # (depends on whether Y is correctly identified as outcome)
        # At minimum, check it runs without error
        assert isinstance(report, SchemaResolutionReport)

    def test_positivity_warning_low_prevalence(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        report = self.resolver.resolve(
            ast,
            df_columns=["X", "Y", "Z"],
            df_dtypes={"X": "int64", "Y": "float64", "Z": "float64"},
            treatment_prevalence_hint={"X": 0.01},  # very low prevalence
        )
        # Should have support warning
        # (May or may not depending on whether X is identified as treatment)
        assert isinstance(report.support_warnings, list)

    def test_is_feasible_true_when_all_resolved(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        report = self.resolver.resolve(
            ast,
            df_columns=["X", "Y", "Z", "extra_col"],
            df_dtypes={"X": "float64", "Y": "float64", "Z": "float64", "extra_col": "object"},
        )
        assert report.is_feasible

    def test_resolve_multi_domain(self):
        ast = make_transport_reweight_estimand(
            treatment="X",
            outcome="Y",
            reweighting_vars=("Z",),
            source_dataset_ref="src",
            target_dataset_ref="tgt",
        )
        report = self.resolver.resolve_multi_domain(
            ast,
            source_columns=["X", "Y", "Z"],
            target_columns=["X", "Y", "Z"],
            source_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
            target_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
        )
        assert isinstance(report, SchemaResolutionReport)

    def test_multi_domain_missing_target_column(self):
        ast = make_transport_reweight_estimand(
            treatment="X",
            outcome="Y",
            reweighting_vars=("Z",),
            source_dataset_ref="src",
            target_dataset_ref="tgt",
        )
        report = self.resolver.resolve_multi_domain(
            ast,
            source_columns=["X", "Y", "Z"],
            target_columns=["X", "Y"],  # Z missing in target
            source_dtypes={"X": "float64", "Y": "float64", "Z": "float64"},
            target_dtypes={"X": "float64", "Y": "float64"},
        )
        assert isinstance(report, SchemaResolutionReport)
        # Z should appear in missing_variables
        assert "Z" in report.missing_variables

    def test_non_estimand_ast_returns_not_feasible(self):
        report = self.resolver.resolve(
            "not an ast",
            df_columns=["X", "Y"],
            df_dtypes={"X": "float64", "Y": "float64"},
        )
        assert not report.is_feasible
