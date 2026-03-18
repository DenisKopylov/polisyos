"""Track 7 — Audit & Evidence: tests for all new IR models and integrations.

Covers:
    5.1  CompilationStep, EstimationStep, EvidenceBundle fingerprints
    5.2  CovariateBalanceReport, FalsificationReport, DiagnosticDashboardData
    5.3  CausalRunSnapshot (build + persist + lookup)
    5.4  QualityDimension, CausalQualityReport, QualityScoreAggregator
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ===========================================================================
# 5.1 — EvidenceBundle new types
# ===========================================================================


class TestCompilationStep:
    def test_basic(self):
        from polisyos.ir.analytics.evidence_bundle import CompilationStep

        step = CompilationStep(
            estimand_shape="backdoor",
            estimation_strategy="aipw",
            n_executor_nodes=3,
        )
        assert step.estimand_shape == "backdoor"
        assert step.n_executor_nodes == 3
        assert step.nuisance_components == ()
        assert step.compiler_warnings == ()

    def test_frozen(self):
        from polisyos.ir.analytics.evidence_bundle import CompilationStep

        step = CompilationStep(
            estimand_shape="frontdoor",
            estimation_strategy="mediation",
            n_executor_nodes=5,
        )
        with pytest.raises((TypeError, Exception)):
            step.n_executor_nodes = 99  # type: ignore[misc]

    def test_extra_forbidden(self):
        from polisyos.ir.analytics.evidence_bundle import CompilationStep
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CompilationStep(
                estimand_shape="backdoor",
                estimation_strategy="aipw",
                n_executor_nodes=1,
                bogus_field="oops",
            )


class TestEstimationStep:
    def test_basic(self):
        from polisyos.ir.analytics.evidence_bundle import EstimationStep

        step = EstimationStep(
            node_id="node_0",
            method_fqn="causal.treatment_effects.aipw",
            method_version="1.0.0",
        )
        assert step.node_id == "node_0"
        assert step.method_fqn == "causal.treatment_effects.aipw"
        assert step.method_version == "1.0.0"
        assert step.warnings == ()
        assert step.is_nuisance is False

    def test_frozen(self):
        from polisyos.ir.analytics.evidence_bundle import EstimationStep

        step = EstimationStep(node_id="n", method_fqn="a.b")
        with pytest.raises((TypeError, Exception)):
            step.node_id = "other"  # type: ignore[misc]


class TestEvidenceBundleNewFields:
    def test_fingerprint_utility(self):
        from polisyos.ir.analytics.evidence_bundle import _fingerprint

        h = _fingerprint({"x": 1, "y": [2, 3]})
        assert isinstance(h, str)
        assert len(h) == 16
        # Deterministic
        assert h == _fingerprint({"x": 1, "y": [2, 3]})
        # Different inputs → different hashes
        assert h != _fingerprint({"x": 2})

    def test_bundle_new_fields_defaults(self):
        from polisyos.ir.analytics.evidence_bundle import EvidenceBundle

        bundle = EvidenceBundle(run_id="r1", query_str="P(Y|do(X))")
        assert bundle.graph_fingerprint == ""
        assert bundle.estimand_fingerprint == ""
        assert bundle.compilation_steps == ()
        assert bundle.estimation_steps == ()
        assert bundle.diagnostic_dashboard is None
        assert bundle.quality_report is None

    def test_bundle_with_fingerprints(self):
        from polisyos.ir.analytics.evidence_bundle import (
            CompilationStep,
            EstimationStep,
            EvidenceBundle,
            _fingerprint,
        )

        cs = CompilationStep(estimand_shape="backdoor", estimation_strategy="aipw", n_executor_nodes=2)
        es = EstimationStep(node_id="n0", method_fqn="causal.treatment_effects.aipw")
        fp = _fingerprint({"nodes": ["X", "Y"]})
        bundle = EvidenceBundle(
            run_id="r2",
            query_str="P(Y|do(X))",
            graph_fingerprint=fp,
            estimand_fingerprint="deadbeef12345678",
            compilation_steps=(cs,),
            estimation_steps=(es,),
        )
        assert bundle.graph_fingerprint == fp
        assert len(bundle.compilation_steps) == 1
        assert len(bundle.estimation_steps) == 1

    def test_to_summary_includes_fingerprint(self):
        from polisyos.ir.analytics.evidence_bundle import EvidenceBundle

        bundle = EvidenceBundle(
            run_id="r3",
            query_str="P(Y|do(X))",
            graph_fingerprint="abc123",
            identification_status="identified",
        )
        summary = bundle.to_summary()
        assert "abc123" in summary


# ===========================================================================
# 5.2 — Diagnostic models
# ===========================================================================


class TestCovariateBalanceReport:
    def test_basic_defaults(self):
        from polisyos.ir.analytics.covariate_balance import CovariateBalanceReport

        report = CovariateBalanceReport(
            variable_smd={"age": 0.05, "income": 0.15},
            max_smd=0.15,
            mean_smd=0.10,
            n_imbalanced=1,
            passes_balance_check=False,
        )
        assert report.max_smd == 0.15
        assert report.n_imbalanced == 1
        assert report.imbalance_threshold == 0.1
        assert not report.passes_balance_check

    def test_compute_smd_balanced(self):
        import numpy as np
        from polisyos.ir.analytics.covariate_balance import compute_smd

        rng = np.random.default_rng(42)
        Xt = rng.normal(0, 1, (100, 3))
        Xc = rng.normal(0, 1, (100, 3))
        report = compute_smd(Xt, Xc, column_names=["a", "b", "c"])
        assert set(report.variable_smd.keys()) == {"a", "b", "c"}
        assert report.n_vars_total == 3
        # With same distribution, SMD should be small
        assert report.mean_smd < 0.5

    def test_compute_smd_imbalanced(self):
        import numpy as np
        from polisyos.ir.analytics.covariate_balance import compute_smd

        Xt = np.ones((50, 1)) * 2.0   # mean=2
        Xc = np.ones((50, 1)) * 0.0   # mean=0
        report = compute_smd(Xt, Xc)
        # SMD should be large
        assert report.max_smd > 0.5
        assert not report.passes_balance_check
        assert len(report.recommendations) > 0


class TestFalsificationReport:
    def test_from_tests_all_passed(self):
        from polisyos.ir.analytics.falsification_report import (
            FalsificationReport,
            FalsificationTest,
            FalsificationTestKind,
        )

        tests = [
            FalsificationTest(
                test_name="placebo",
                test_kind=FalsificationTestKind.PLACEBO_TREATMENT,
                passed=True,
                interpretation="ok",
                is_critical=True,
            ),
            FalsificationTest(
                test_name="data_subset",
                test_kind=FalsificationTestKind.DATA_SUBSET,
                passed=True,
                interpretation="ok",
            ),
        ]
        report = FalsificationReport.from_tests(tests)
        assert report.n_passed == 2
        assert report.n_failed == 0
        assert report.overall_passed is True
        assert report.critical_failures == ()

    def test_from_tests_critical_failure(self):
        from polisyos.ir.analytics.falsification_report import (
            FalsificationReport,
            FalsificationTest,
            FalsificationTestKind,
        )

        tests = [
            FalsificationTest(
                test_name="independence",
                test_kind=FalsificationTestKind.INDEPENDENCE_TEST,
                passed=False,
                interpretation="violated",
                is_critical=True,
            ),
        ]
        report = FalsificationReport.from_tests(tests)
        assert not report.overall_passed
        assert "independence" in report.critical_failures

    def test_from_parallel_trends(self):
        from polisyos.ir.analytics.falsification_report import FalsificationReport

        result = {"passed": False, "statistic": -2.1, "p_value": 0.03}
        report = FalsificationReport.from_parallel_trends(result)
        assert report.n_failed == 1
        assert not report.overall_passed


class TestDiagnosticDashboardData:
    def test_from_empty_outputs(self):
        from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData

        dashboard = DiagnosticDashboardData.from_node_outputs(
            run_id="r1",
            query_str="P(Y|do(X))",
            node_outputs={},
        )
        assert dashboard.run_id == "r1"
        assert dashboard.n_diagnostics_run == 0
        assert dashboard.overall_passed is True
        assert dashboard.positivity is None

    def test_from_positivity_output(self):
        from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData

        node_outputs = {
            "diag_positivity": {
                "result": {
                    "passes_positivity": True,
                    "ess_fraction": 0.75,
                    "overlap_score": 0.80,
                    "n_obs": 500,
                    "n_trimmed": 0,
                    "recommendations": [],
                }
            }
        }
        dashboard = DiagnosticDashboardData.from_node_outputs(
            run_id="r2",
            query_str="P(Y|do(X))",
            node_outputs=node_outputs,
        )
        assert dashboard.positivity is not None
        assert dashboard.positivity["passes_positivity"] is True
        assert dashboard.n_diagnostics_run >= 1
        assert not dashboard.has_overlap_issues

    def test_from_failing_positivity(self):
        from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData

        node_outputs = {
            "diag_positivity": {
                "result": {
                    "passes_positivity": False,
                    "ess_fraction": 0.1,
                    "overlap_score": 0.3,
                    "n_obs": 100,
                    "n_trimmed": 20,
                    "recommendations": ["Consider trimming."],
                }
            }
        }
        dashboard = DiagnosticDashboardData.from_node_outputs(
            run_id="r3",
            query_str="test",
            node_outputs=node_outputs,
        )
        assert dashboard.has_overlap_issues is True
        assert dashboard.overall_passed is False


# ===========================================================================
# 5.3 — CausalRunSnapshot
# ===========================================================================


class TestCausalRunSnapshot:
    def test_build_minimal(self):
        from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

        snap = CausalRunSnapshot.build(run_id="test-001")
        assert snap.run_id == "test-001"
        assert snap.schema_version == "1.0"
        assert snap.python_version != ""
        assert snap.created_at != ""

    def test_stable_hash_deterministic(self):
        from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

        snap = CausalRunSnapshot(
            run_id="abc",
            graph_fingerprint="deadbeef",
            estimand_fingerprint="cafebabe",
            dataset_fingerprints={"obs": "hash1"},
            algorithm_version="id_v1",
        )
        h1 = snap.stable_hash()
        h2 = snap.stable_hash()
        assert h1 == h2
        assert len(h1) == 32

    def test_stable_hash_varies_with_content(self):
        from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

        snap_a = CausalRunSnapshot(run_id="a", graph_fingerprint="fp1")
        snap_b = CausalRunSnapshot(run_id="b", graph_fingerprint="fp2")
        assert snap_a.stable_hash() != snap_b.stable_hash()

    def test_persist_and_lookup(self):
        from polisyos.ir.analytics.causal_run_snapshot import (
            CausalRunSnapshot,
            lookup_snapshot,
            persist_snapshot,
        )

        snap = CausalRunSnapshot(
            run_id="persist-test-001",
            graph_fingerprint="fp1",
            estimand_fingerprint="ep1",
            algorithm_version="id_v1",
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact_id = persist_snapshot(snap, tmp)
            assert isinstance(artifact_id, str)
            assert len(artifact_id) == 32

            # Index file was created
            index = Path(tmp) / "index" / "causal_run_snapshots.jsonl"
            assert index.exists()

            # Can look up by run_id
            loaded = lookup_snapshot("persist-test-001", tmp)
            assert loaded is not None
            assert loaded.run_id == snap.run_id
            assert loaded.graph_fingerprint == snap.graph_fingerprint

    def test_lookup_missing_returns_none(self):
        from polisyos.ir.analytics.causal_run_snapshot import lookup_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            result = lookup_snapshot("nonexistent-run", tmp)
            assert result is None

    def test_method_invocation_record(self):
        from polisyos.ir.analytics.causal_run_snapshot import MethodInvocationRecord

        rec = MethodInvocationRecord(
            method_fqn="causal.treatment_effects.aipw",
            method_version="1.0.0",
            backend="numpy",
            params_hash="abc123",
            determinism_tier="library_deterministic",
        )
        assert rec.method_fqn == "causal.treatment_effects.aipw"
        assert rec.is_nuisance is False


# ===========================================================================
# 5.4 — Quality models
# ===========================================================================


class TestQualityDimension:
    def test_basic(self):
        from polisyos.ir.analytics.quality_report import QualityDimension

        dim = QualityDimension(score=0.85, grade="A", components={"ess": 0.9})
        assert dim.score == 0.85
        assert dim.grade == "A"
        assert not dim.is_blocking

    def test_blocking_below_threshold(self):
        from polisyos.ir.analytics.quality_report import QualityDimension

        dim = QualityDimension(score=0.25, grade="F", components={}, is_blocking=True)
        assert dim.is_blocking is True


class TestCausalQualityReport:
    def test_score_to_grade(self):
        from polisyos.ir.analytics.quality_report import _score_to_grade

        assert _score_to_grade(0.90) == "A"
        assert _score_to_grade(0.75) == "B"
        assert _score_to_grade(0.60) == "C"
        assert _score_to_grade(0.45) == "D"
        assert _score_to_grade(0.30) == "F"

    def test_full_report(self):
        from polisyos.ir.analytics.quality_report import CausalQualityReport, QualityDimension

        dim = QualityDimension(score=0.8, grade="B", components={"a": 0.8})
        report = CausalQualityReport(
            run_id="r1",
            query_str="P(Y|do(X))",
            data_quality=dim,
            method_quality=dim,
            robustness=dim,
            composite_score=0.8,
            composite_grade="B",
            is_publication_ready=True,
        )
        assert report.composite_grade == "B"
        assert report.is_publication_ready is True
        assert "r1" in report.to_summary()


class TestQualityScoreAggregator:
    def test_no_data(self):
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator

        agg = QualityScoreAggregator()
        report = agg.score(run_id="test", query_str="P(Y|do(X))")
        assert 0.0 <= report.composite_score <= 1.0
        assert report.composite_grade in ("A", "B", "C", "D", "F")

    def test_good_diagnostics_high_score(self):
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator
        from polisyos.ir.analytics.evidence_bundle import DataProvenance, EstimationStep

        agg = QualityScoreAggregator()
        prov = (DataProvenance(dataset_ref="obs", quality_score=0.95),)
        steps = (EstimationStep(
            node_id="n0",
            method_fqn="causal.treatment_effects.aipw",
            determinism_tier="library_deterministic",
        ),)
        node_outputs = {
            "pos": {
                "result": {
                    "passes_positivity": True,
                    "ess_fraction": 0.85,
                    "overlap_score": 0.90,
                }
            }
        }
        report = agg.score(
            run_id="good",
            data_provenance=prov,
            estimation_steps=steps,
            node_outputs=node_outputs,
        )
        assert report.composite_score > 0.70
        assert report.composite_grade in ("A", "B")

    def test_poor_diagnostics_low_score(self):
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator
        from polisyos.ir.analytics.evidence_bundle import DataProvenance

        agg = QualityScoreAggregator()
        prov = (DataProvenance(dataset_ref="obs", quality_score=0.3),)
        node_outputs = {
            "pos": {
                "result": {
                    "passes_positivity": False,
                    "ess_fraction": 0.05,
                    "overlap_score": 0.10,
                }
            }
        }
        report = agg.score(
            run_id="poor",
            data_provenance=prov,
            node_outputs=node_outputs,
        )
        assert report.composite_score < 0.70

    def test_blocking_dimension_caps_composite(self):
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator
        from polisyos.ir.analytics.evidence_bundle import DataProvenance

        agg = QualityScoreAggregator()
        prov = (DataProvenance(dataset_ref="obs", quality_score=0.1),)
        node_outputs = {
            "pos": {
                "result": {
                    "passes_positivity": False,
                    "ess_fraction": 0.01,
                    "overlap_score": 0.01,
                }
            }
        }
        report = agg.score(run_id="block", data_provenance=prov, node_outputs=node_outputs)
        if report.data_quality.is_blocking:
            assert report.composite_score <= 0.39

    def test_aggregate_weights_stored(self):
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator

        # Custom weights are accepted and stored
        agg = QualityScoreAggregator(weights={"data": 0.5, "method": 0.3, "robustness": 0.2})
        assert agg._weights["data"] == 0.5
        assert agg._weights["method"] == 0.3
        assert agg._weights["robustness"] == 0.2

    def test_json_serializable(self):
        import json
        from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator

        agg = QualityScoreAggregator()
        report = agg.score(run_id="json-test")
        dumped = report.model_dump(mode="json")
        # Should be JSON-serializable
        json.dumps(dumped)
