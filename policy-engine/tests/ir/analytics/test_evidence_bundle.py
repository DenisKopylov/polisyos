"""Tests for EvidenceBundle IR models."""
import pytest
from polisyos.ir.analytics.evidence_bundle import ProofStep, DataProvenance, EvidenceBundle


class TestProofStep:
    def test_frozen_model(self):
        step = ProofStep(rule_name="RULE1", description="backdoor criterion applied")
        with pytest.raises((TypeError, Exception)):
            step.rule_name = "RULE2"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ProofStep(rule_name="R", description="d", nonexistent_field="oops")

    def test_defaults(self):
        step = ProofStep(rule_name="C_COMPONENT", description="c-component factorization")
        assert step.variables_affected == ()
        assert step.graph_subset == ""

    def test_all_fields(self):
        step = ProofStep(
            rule_name="RULE3",
            description="do-calculus rule 3",
            variables_affected=("X", "Y"),
            graph_subset="G[X,Y,Z]",
        )
        assert step.rule_name == "RULE3"
        assert step.variables_affected == ("X", "Y")

    def test_new_fields_default_to_empty_string(self):
        step = ProofStep(rule_name="RULE1", description="backdoor criterion applied")
        assert step.rule_formal_name == ""
        assert step.applicable_theorem == ""
        assert step.graph_state_before == ""
        assert step.graph_state_after == ""

    def test_new_fields_can_be_set(self):
        step = ProofStep(
            rule_name="RULE3",
            description="Removing do-operator via rule 3",
            rule_formal_name="do-calculus rule 3",
            applicable_theorem="do-calculus-R3",
            graph_state_before="G_X_intervened",
            graph_state_after="G_X_observed",
        )
        assert step.rule_formal_name == "do-calculus rule 3"
        assert step.applicable_theorem == "do-calculus-R3"
        assert step.graph_state_before == "G_X_intervened"
        assert step.graph_state_after == "G_X_observed"

    def test_new_fields_round_trip_json(self):
        step = ProofStep(
            rule_name="HEDGE",
            description="Hedge found",
            rule_formal_name="hedge-certificate",
            applicable_theorem="ID-algorithm-step-4a",
            graph_state_before="G_full",
            graph_state_after="G_blocked",
        )
        data = step.model_dump(mode="json")
        restored = ProofStep.model_validate(data)
        assert restored.rule_formal_name == "hedge-certificate"
        assert restored.graph_state_after == "G_blocked"


class TestDataProvenance:
    def test_frozen_model(self):
        dp = DataProvenance(dataset_ref="ds1")
        with pytest.raises((TypeError, Exception)):
            dp.dataset_ref = "ds2"

    def test_quality_score_bounded(self):
        with pytest.raises(Exception):
            DataProvenance(dataset_ref="ds1", quality_score=1.5)
        with pytest.raises(Exception):
            DataProvenance(dataset_ref="ds1", quality_score=-0.1)

    def test_valid_quality_score(self):
        dp = DataProvenance(dataset_ref="ds1", quality_score=0.8)
        assert dp.quality_score == 0.8

    def test_defaults(self):
        dp = DataProvenance(dataset_ref="ds1")
        assert dp.n_obs is None
        assert dp.domain == "source"
        assert dp.availability_status == "available"


class TestEvidenceBundle:
    def _minimal(self):
        return EvidenceBundle(run_id="run-001", query_str="P(Y|do(X))")

    def test_minimal_creation(self):
        bundle = self._minimal()
        assert bundle.run_id == "run-001"
        assert bundle.query_str == "P(Y|do(X))"

    def test_full_creation(self):
        step = ProofStep(rule_name="RULE1", description="backdoor")
        dp = DataProvenance(dataset_ref="ds1", n_obs=500)
        bundle = EvidenceBundle(
            run_id="run-002",
            query_str="P(Y|do(X),Z)",
            estimand_ast={"root": {}, "treatment": ["X"]},
            proof_steps=(step,),
            data_provenance=(dp,),
            diagnostic_scores={"overlap": 0.95},
            method_config={"method": "AIPW"},
            identification_status="IDENTIFIED",
            algorithm_version="id_v1",
            created_at="2026-03-15T10:00:00Z",
        )
        assert len(bundle.proof_steps) == 1
        assert bundle.identification_status == "IDENTIFIED"

    def test_to_summary_format(self):
        bundle = self._minimal()
        summary = bundle.to_summary()
        assert "run-001" in summary
        assert "P(Y|do(X))" in summary

    def test_to_summary_with_diagnostics(self):
        bundle = EvidenceBundle(
            run_id="r1",
            query_str="Q",
            diagnostic_scores={"overlap": 0.8, "positivity": 0.9},
        )
        summary = bundle.to_summary()
        assert "overlap" in summary

    def test_round_trip_json(self):
        step = ProofStep(rule_name="RULE2", description="d")
        bundle = EvidenceBundle(
            run_id="r3",
            query_str="P(Y|do(X))",
            proof_steps=(step,),
            identification_status="IDENTIFIED",
        )
        data = bundle.model_dump(mode="json")
        restored = EvidenceBundle.model_validate(data)
        assert restored.run_id == "r3"
        assert len(restored.proof_steps) == 1
        assert restored.proof_steps[0].rule_name == "RULE2"

    def test_estimand_ast_stored_as_dict(self):
        bundle = EvidenceBundle(
            run_id="r4",
            query_str="Q",
            estimand_ast={"schema_version": "1.0", "root": {}},
        )
        assert isinstance(bundle.estimand_ast, dict)

    def test_frozen_rejects_mutation(self):
        bundle = self._minimal()
        with pytest.raises((TypeError, Exception)):
            bundle.run_id = "mutated"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            EvidenceBundle(run_id="r", query_str="q", secret_field="oops")
