"""Tests for NegativeCertificate IR model."""
import pytest
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate, SuggestedExperiment
from polisyos.ir.analytics.partial_identification import BoundMethod, PartialIdentificationResult


def _make_bounds(lower: float = -0.3, upper: float = 0.7) -> PartialIdentificationResult:
    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lower,
        upper_bound=upper,
        confidence=0.9,
    )


class TestBlockingType:
    def test_all_values_are_str(self):
        for bt in BlockingType:
            assert isinstance(bt.value, str)

    def test_all_expected_values_exist(self):
        expected = {
            "hedge_structure", "s_node_unresolved", "positivity_violation",
            "support_mismatch", "missing_distribution",
        }
        actual = {bt.value for bt in BlockingType}
        assert expected == actual


class TestNegativeCertificate:
    def _minimal(self):
        return NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="Non-identifiable: hedge F={X,Y,Z}, F'={X,Y}",
        )

    def test_minimal_creation(self):
        cert = self._minimal()
        assert cert.blocking_type == BlockingType.HEDGE_STRUCTURE

    def test_full_creation(self):
        cert = NegativeCertificate(
            blocking_type=BlockingType.MISSING_DISTRIBUTION,
            blocking_description="P(Y|do(X)) not available in any dataset",
            technical_detail="id_algorithm returned HEDGE_FOUND at step 4a",
            required_distributions=({"domain": "experimental", "variables": ["Y"]},),
            missing_dataset_refs=("experimental_ds",),
            suggested_experiments=(
                SuggestedExperiment(
                    required_variables=("X", "Y"),
                    domain="experimental",
                    design_type="RCT",
                    description="Randomize X and measure Y",
                ),
            ),
            partial_bounds=_make_bounds(-0.3, 0.7),
            constructive_message="Collect experimental data with X randomized",
        )
        assert cert.has_partial_bounds()
        assert cert.partial_bounds.lower_bound == -0.3

    def test_has_partial_bounds_true(self):
        cert = NegativeCertificate(
            blocking_type=BlockingType.S_NODE_UNRESOLVED,
            blocking_description="S-node unresolved",
            partial_bounds=_make_bounds(0.1, 0.5),
        )
        assert cert.has_partial_bounds() is True

    def test_has_partial_bounds_false(self):
        cert = self._minimal()
        assert cert.has_partial_bounds() is False

    def test_to_summary_contains_blocking_type(self):
        cert = self._minimal()
        summary = cert.to_summary()
        assert "hedge_structure" in summary

    def test_to_summary_includes_bounds(self):
        cert = NegativeCertificate(
            blocking_type=BlockingType.POSITIVITY_VIOLATION,
            blocking_description="Overlap failure",
            partial_bounds=_make_bounds(-0.1, 0.4),
        )
        summary = cert.to_summary()
        assert "bounds" in summary

    def test_round_trip_json(self):
        cert = NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="Test hedge",
            required_distributions=({"domain": "source", "variables": ["Y"]},),
        )
        data = cert.model_dump(mode="json")
        restored = NegativeCertificate.model_validate(data)
        assert restored.blocking_type == BlockingType.HEDGE_STRUCTURE
        assert len(restored.required_distributions) == 1

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            NegativeCertificate(
                blocking_type=BlockingType.HEDGE_STRUCTURE,
                blocking_description="d",
                unknown_field="oops",
            )

    def test_frozen_rejects_mutation(self):
        cert = self._minimal()
        with pytest.raises((TypeError, Exception)):
            cert.blocking_description = "changed"

    def test_defaults_are_empty(self):
        cert = self._minimal()
        assert cert.required_distributions == ()
        assert cert.missing_dataset_refs == ()
        assert cert.suggested_experiments == ()
        assert cert.partial_bounds is None
        assert cert.constructive_message == ""


class TestSuggestedExperiment:
    def test_minimal_creation(self):
        exp = SuggestedExperiment(required_variables=("X", "Y"))
        assert exp.required_variables == ("X", "Y")
        assert exp.domain == "target"
        assert exp.design_type == "observational"
        assert exp.description == ""

    def test_full_creation(self):
        exp = SuggestedExperiment(
            required_variables=("T", "Y", "Z"),
            domain="experimental",
            design_type="RCT",
            description="Randomize T, measure Y and Z in experimental setting",
        )
        assert exp.domain == "experimental"
        assert exp.design_type == "RCT"
        assert "Randomize" in exp.description

    def test_frozen_rejects_mutation(self):
        exp = SuggestedExperiment(required_variables=("X",))
        with pytest.raises((TypeError, Exception)):
            exp.domain = "source"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            SuggestedExperiment(required_variables=("X",), unexpected="oops")

    def test_round_trip_json(self):
        exp = SuggestedExperiment(
            required_variables=("A", "B"),
            domain="target",
            design_type="IV",
            description="Use Z as instrument for A",
        )
        data = exp.model_dump(mode="json")
        restored = SuggestedExperiment.model_validate(data)
        assert restored.required_variables == ("A", "B")
        assert restored.design_type == "IV"

    def test_used_in_negative_certificate(self):
        exp = SuggestedExperiment(
            required_variables=("T", "Y"),
            domain="experimental",
            design_type="RCT",
        )
        cert = NegativeCertificate(
            blocking_type=BlockingType.MISSING_DISTRIBUTION,
            blocking_description="P(Y|do(T)) not available",
            suggested_experiments=(exp,),
        )
        assert len(cert.suggested_experiments) == 1
        assert cert.suggested_experiments[0].design_type == "RCT"


class TestTrack6Additions:
    """Tests for Track 6 — Partial Identification & DataKB additions."""

    def test_partial_bounds_is_typed_partial_id_result(self):
        bounds = _make_bounds(-0.2, 0.5)
        cert = NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="hedge test",
            partial_bounds=bounds,
        )
        assert isinstance(cert.partial_bounds, PartialIdentificationResult)
        assert cert.partial_bounds.lower_bound == -0.2
        assert cert.partial_bounds.upper_bound == 0.5

    def test_partial_bounds_to_ui_dict(self):
        bounds = PartialIdentificationResult(
            method=BoundMethod.LP_BALKE_PEARL,
            lower_bound=-0.1,
            upper_bound=0.6,
            confidence=0.95,
            display_label="Balke-Pearl Sharp IV Bounds",
            chart_type="interval",
        )
        ui = bounds.to_ui_dict()
        assert ui["lower"] == -0.1
        assert ui["upper"] == 0.6
        assert ui["method"] == "lp_balke_pearl"
        assert ui["chart_type"] == "interval"
        assert ui["display_label"] == "Balke-Pearl Sharp IV Bounds"

    def test_auto_suggest_hedge_structure(self):
        suggestions = NegativeCertificate.auto_suggest_experiments(
            BlockingType.HEDGE_STRUCTURE, missing_vars=("X",)
        )
        assert len(suggestions) == 1
        assert suggestions[0].design_type == "RCT"
        assert suggestions[0].required_variables == ("X",)

    def test_auto_suggest_missing_distribution(self):
        suggestions = NegativeCertificate.auto_suggest_experiments(
            BlockingType.MISSING_DISTRIBUTION,
            missing_vars=("Z",),
            missing_dataset_refs=("experimental_ds",),
        )
        assert len(suggestions) == 1
        assert suggestions[0].design_type == "observational"
        assert "experimental_ds" in suggestions[0].description

    def test_auto_suggest_positivity_violation(self):
        suggestions = NegativeCertificate.auto_suggest_experiments(
            BlockingType.POSITIVITY_VIOLATION, missing_vars=("W",)
        )
        assert len(suggestions) == 1
        assert suggestions[0].design_type == "RCT"

    def test_auto_suggest_s_node_unresolved(self):
        suggestions = NegativeCertificate.auto_suggest_experiments(
            BlockingType.S_NODE_UNRESOLVED
        )
        assert len(suggestions) == 1
        assert suggestions[0].domain == "experimental"

    def test_auto_suggest_support_mismatch_returns_empty(self):
        suggestions = NegativeCertificate.auto_suggest_experiments(
            BlockingType.SUPPORT_MISMATCH
        )
        assert suggestions == ()

    def test_quantitative_diagnostics_field(self):
        cert = NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="test",
            quantitative_diagnostics={
                "hedge_forest_size": 3,
                "overlap_score": 0.45,
            },
        )
        assert cert.quantitative_diagnostics["hedge_forest_size"] == 3
        assert cert.quantitative_diagnostics["overlap_score"] == 0.45

    def test_round_trip_json_with_partial_bounds(self):
        bounds = PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=-0.5,
            upper_bound=0.5,
            confidence=0.8,
        )
        cert = NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="round-trip test",
            partial_bounds=bounds,
        )
        data = cert.model_dump(mode="json")
        restored = NegativeCertificate.model_validate(data)
        assert restored.partial_bounds is not None
        assert restored.partial_bounds.lower_bound == -0.5
        assert restored.partial_bounds.method == BoundMethod.MANSKI

    def test_bound_method_new_values(self):
        assert BoundMethod.LP_BALKE_PEARL.value == "lp_balke_pearl"
        assert BoundMethod.IMBENS_MANSKI_CI.value == "imbens_manski_ci"
