"""Tests for Track G: CausalEngine Integration (G0–G6).

Tests cover:
  G0  – estimate() returns (report, node_outputs) tuple
  G1  – multi-domain source_domains routing to mz_id_algorithm
  G2  – _inject_diagnostic_nodes: PositivityDiagnostic always;
         SupportMismatchDiagnostic for TRANSPORT_REWEIGHT; idempotent
  G3  – sensitivity_result / diagnostic scores captured in EvidenceBundle
  G4  – CausalQueryValidator gate: ERROR → early NegativeCertificate
  G5  – skip_if_failed; nuisance-failure continuation; main-estimator break
  G6  – ProofStep enrichment; SuggestedExperiment fix in hedge cert
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimandShape,
    ExecutorGraph,
    ExecutorNode,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    SourceDomain,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    SuggestedExperiment,
)
from polisyos.ir.analytics.query_validation_report import (
    QueryValidationReport,
    ValidationError,
    ValidationWarning,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_dag(directed_edges: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = list({n for e in directed_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)


def _minimal_ir(
    status: IdentificationStatus = IdentificationStatus.IDENTIFIED,
    estimand_ast: Any = None,
    proof_steps: list | None = None,
) -> IdentificationResult:
    return IdentificationResult(
        status=status,
        estimand_ast=estimand_ast,
        hedge_certificate=None,
        trace=[],
        required_distributions=[],
        proof_steps=proof_steps or [],
    )


def _make_graph() -> ExecutorGraph:
    return ExecutorGraph(nodes=(), edges=(), nuisance_schedule=(), run_id="test")


def _make_node(
    node_id: str = "n1",
    fqn: str = "causal.estimator.aipw",
    is_nuisance: bool = False,
    skip_if_failed: tuple = (),
) -> ExecutorNode:
    return ExecutorNode(
        node_id=node_id,
        method_fqn=fqn,
        method_version="1.0.0",
        params={},
        depends_on=(),
        reads_slots=(),
        writes_slots=(),
        is_nuisance=is_nuisance,
        dataset_ref=None,
        skip_if_failed=skip_if_failed,
    )


def _make_executor_graph(
    nodes: tuple = (),
    nuisance_schedule: tuple = (),
    run_id: str = "run1",
) -> ExecutorGraph:
    return ExecutorGraph(
        nodes=nodes,
        edges=(),
        nuisance_schedule=nuisance_schedule,
        total_folds=1,
        run_id=run_id,
        warnings=(),
    )


def _make_registry(node_behaviors: dict[str, Any]) -> MagicMock:
    """Build a mock MethodRegistry.

    node_behaviors: {method_fqn (without version): output_dict | Exception instance}
    """
    registry = MagicMock()

    def _get(fqn_full: str) -> MagicMock:
        fqn = fqn_full.split("@")[0]
        behavior = node_behaviors.get(fqn, {})
        method = MagicMock()
        if isinstance(behavior, Exception):
            method.pure_step.side_effect = behavior
        else:
            method.pure_step.return_value = behavior
        return method

    registry.get.side_effect = _get
    return registry


def _error_val_report() -> QueryValidationReport:
    return QueryValidationReport(
        is_valid=False,
        errors=(ValidationError(code="TREATMENT_MISSING", message="Treatment X not in graph"),),
    )


def _warning_val_report() -> QueryValidationReport:
    return QueryValidationReport(
        is_valid=True,
        errors=(),
        warnings=(ValidationWarning(code="SMALL_SAMPLE", message="n<50"),),
    )


def _clean_val_report() -> QueryValidationReport:
    return QueryValidationReport(is_valid=True)


# ---------------------------------------------------------------------------
# G0: estimate() returns tuple
# ---------------------------------------------------------------------------


class TestG0EstimateReturnType:
    def test_estimate_returns_two_tuple(self):
        """G0: estimate() returns (last_report, node_outputs) tuple."""
        node = _make_node(node_id="n1", fqn="causal.estimator.aipw")
        graph = _make_executor_graph(nodes=(node,))
        mock_report = MagicMock()
        registry = _make_registry({"causal.estimator.aipw": {"report": mock_report}})

        engine = CausalEngine(registry=registry)
        result = engine.estimate(graph, {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        report, node_outputs = result
        assert report is mock_report
        assert "n1" in node_outputs

    def test_estimate_node_outputs_contain_raw_output(self):
        """G0: node_outputs maps node_id → pure_step output dict."""
        node = _make_node(node_id="my_node", fqn="causal.estimator.tmle")
        graph = _make_executor_graph(nodes=(node,))
        raw_output = {"report": MagicMock(), "extra_key": 42}
        registry = _make_registry({"causal.estimator.tmle": raw_output})

        engine = CausalEngine(registry=registry)
        _, node_outputs = engine.estimate(graph, {})

        assert "my_node" in node_outputs
        assert node_outputs["my_node"]["extra_key"] == 42


# ---------------------------------------------------------------------------
# G1: Multi-domain mz_id routing
# ---------------------------------------------------------------------------


class TestG1MultiDomainRouting:
    def test_source_domains_len_gt1_routes_to_mz_id(self):
        """G1: source_domains=[d1, d2] → mz_id_algorithm called with that list."""
        engine = CausalEngine()
        graph = _make_dag([("X", "Y")])
        d1, d2 = MagicMock(), MagicMock()
        identified = _minimal_ir()

        with patch(
            "polisyos.foundry.methods.catalog.causal.causal_engine.mz_id_algorithm",
            return_value=identified,
        ) as mock_mz:
            result = engine.identify("X", "Y", graph, source_domains=[d1, d2])

        mock_mz.assert_called_once()
        assert mock_mz.call_args.kwargs["source_domains"] == [d1, d2]
        assert isinstance(result, IdentificationResult)

    def test_source_domains_len1_falls_through_to_standard(self):
        """G1: source_domains with len==1 does not use the multi-domain branch."""
        engine = CausalEngine()
        graph = _make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        identified = _minimal_ir()

        with (
            patch(
                "polisyos.foundry.methods.catalog.causal.causal_engine.mz_id_algorithm",
            ) as mock_mz,
            patch(
                "polisyos.foundry.methods.catalog.causal.causal_engine.id_with_oracle_fallback",
                return_value=identified,
            ),
        ):
            engine.identify("X", "Y", graph, source_domains=[MagicMock()])

        mock_mz.assert_not_called()

    def test_s_nodes_z_int_still_calls_mz_id_single_domain(self):
        """G1: existing s_nodes+z_int path → mz_id_algorithm with single SourceDomain."""
        engine = CausalEngine()
        graph = _make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        identified = _minimal_ir()

        with patch(
            "polisyos.foundry.methods.catalog.causal.causal_engine.mz_id_algorithm",
            return_value=identified,
        ) as mock_mz:
            result = engine.identify(
                "X",
                "Y",
                graph,
                s_nodes=["S"],
                z_interventions=frozenset({"Z"}),
            )

        mock_mz.assert_called_once()
        assert len(mock_mz.call_args.kwargs["source_domains"]) == 1
        assert isinstance(result, IdentificationResult)

    def test_run_forwards_source_domains(self):
        """G1: run() accepts source_domains and forwards to identify()."""
        engine = CausalEngine()
        graph = _make_dag([("X", "Y")])
        d1, d2 = MagicMock(), MagicMock()
        identified = _minimal_ir()

        with (
            patch.object(engine, "identify", return_value=identified) as mock_id,
            patch(
                "polisyos.foundry.methods.catalog.causal.query_validator.CausalQueryValidator"
            ) as MockVal,
            patch.object(engine, "compile", side_effect=ValueError("no ast")),
        ):
            MockVal.return_value.validate.return_value = _clean_val_report()
            engine.run("X", "Y", graph, source_domains=[d1, d2])

        call_kwargs = mock_id.call_args.kwargs
        assert call_kwargs.get("source_domains") == [d1, d2]

    def test_counterfactual_with_s_nodes_routes_to_ctf_transport(self):
        """G1: counterfactual + s_nodes must route to ctf_transportability, not plain ID*."""
        engine = CausalEngine()
        graph = _make_dag([("X", "Y")])
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        identified = _minimal_ir()

        with (
            patch(
                "polisyos.foundry.methods.catalog.causal.ctf_transport.build_ctf_selection_diagram",
                return_value=MagicMock(),
            ) as mock_build,
            patch(
                "polisyos.foundry.methods.catalog.causal.ctf_transport.ctf_transportability",
                return_value=identified,
            ) as mock_ctf_transport,
            patch(
                "polisyos.foundry.methods.catalog.causal.causal_engine.id_star_algorithm",
            ) as mock_id_star,
        ):
            result = engine.identify(
                "X",
                "Y",
                graph,
                s_nodes=["Y"],
                counterfactual_query=query,
            )

        mock_build.assert_called_once()
        mock_ctf_transport.assert_called_once()
        mock_id_star.assert_not_called()
        assert isinstance(result, IdentificationResult)

    def test_counterfactual_with_source_domains_routes_to_ctf_transport(self):
        """G1: counterfactual + source_domains must route to counterfactual transport."""
        engine = CausalEngine()
        graph = _make_dag([("X", "Y")])
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        domains = [
            SourceDomain(domain_id="d1", s_nodes=frozenset({"Y"}), dataset_ref="study_obs"),
            SourceDomain(domain_id="d2", z_interventions=frozenset({"X"}), dataset_ref="study_rct"),
        ]
        identified = _minimal_ir()

        with (
            patch(
                "polisyos.foundry.methods.catalog.causal.ctf_transport.build_ctf_selection_diagram",
                return_value=MagicMock(),
            ) as mock_build,
            patch(
                "polisyos.foundry.methods.catalog.causal.ctf_transport.ctf_transportability",
                return_value=identified,
            ) as mock_ctf_transport,
            patch(
                "polisyos.foundry.methods.catalog.causal.causal_engine.idc_star_algorithm",
            ) as mock_idc_star,
        ):
            result = engine.identify(
                "X",
                "Y",
                graph,
                source_domains=domains,
                counterfactual_query=query,
            )

        mock_build.assert_called_once()
        assert mock_ctf_transport.call_args.kwargs["source_domains"] == domains
        mock_idc_star.assert_not_called()
        assert isinstance(result, IdentificationResult)


# ---------------------------------------------------------------------------
# G2: Auto-diagnostic node injection
# ---------------------------------------------------------------------------


class TestG2DiagnosticInjection:
    def test_positivity_injected_always(self):
        """G2: PositivityDiagnostic node always added to empty graph."""
        engine = CausalEngine()
        graph = _make_executor_graph(nodes=(), run_id="r1")
        ast = MagicMock()

        with patch(
            "polisyos.foundry.methods.catalog.causal.estimand_compiler.classify_estimand",
            return_value=EstimandShape.BACKDOOR,
        ):
            result = engine._inject_diagnostic_nodes(graph, ast)

        fqns = {n.method_fqn for n in result.nodes}
        assert "causal.diagnostics.positivity" in fqns
        assert "causal.diagnostics.support_mismatch" not in fqns

    def test_support_mismatch_injected_for_transport_shape(self):
        """G2: TRANSPORT_REWEIGHT → both PositivityDiagnostic and SupportMismatch injected."""
        engine = CausalEngine()
        graph = _make_executor_graph(nodes=(), run_id="r2")
        ast = MagicMock()

        with patch(
            "polisyos.foundry.methods.catalog.causal.estimand_compiler.classify_estimand",
            return_value=EstimandShape.TRANSPORT_REWEIGHT,
        ):
            result = engine._inject_diagnostic_nodes(graph, ast)

        fqns = {n.method_fqn for n in result.nodes}
        assert "causal.diagnostics.positivity" in fqns
        assert "causal.diagnostics.support_mismatch" in fqns

    def test_injection_idempotent(self):
        """G2: Calling inject twice doesn't create duplicate nodes."""
        engine = CausalEngine()
        ast = MagicMock()

        with patch(
            "polisyos.foundry.methods.catalog.causal.estimand_compiler.classify_estimand",
            return_value=EstimandShape.BACKDOOR,
        ):
            g1 = engine._inject_diagnostic_nodes(_make_executor_graph(nodes=(), run_id="r3"), ast)
            g2 = engine._inject_diagnostic_nodes(g1, ast)

        positivity_count = sum(
            1 for n in g2.nodes if n.method_fqn == "causal.diagnostics.positivity"
        )
        assert positivity_count == 1

    def test_no_injection_when_ast_none(self):
        """G2: ast=None → returns the same ExecutorGraph object unchanged."""
        engine = CausalEngine()
        graph = _make_executor_graph(nodes=(), run_id="r4")
        result = engine._inject_diagnostic_nodes(graph, None)
        assert result is graph

    def test_inject_preserves_existing_nodes(self):
        """G2: Injected graph still contains original nodes."""
        engine = CausalEngine()
        existing = _make_node(node_id="orig", fqn="causal.estimator.aipw")
        graph = _make_executor_graph(nodes=(existing,), run_id="r5")
        ast = MagicMock()

        with patch(
            "polisyos.foundry.methods.catalog.causal.estimand_compiler.classify_estimand",
            return_value=EstimandShape.BACKDOOR,
        ):
            result = engine._inject_diagnostic_nodes(graph, ast)

        node_ids = {n.node_id for n in result.nodes}
        assert "orig" in node_ids


# ---------------------------------------------------------------------------
# G3: Sensitivity capture in EvidenceBundle
# ---------------------------------------------------------------------------


class TestG3SensitivityCapture:
    def _ir(self) -> IdentificationResult:
        return _minimal_ir()

    def test_e_value_captured(self):
        """G3: sensitivity_result in node_outputs → e_value in diagnostic_scores."""
        engine = CausalEngine()
        sr = MagicMock()
        sr.e_value = 2.5
        sr.rosenbaum_gamma = 1.8

        bundle = engine.audit(
            self._ir(),
            None,
            run_id="r1",
            node_outputs={"sens": {"sensitivity_result": sr}},
        )

        assert bundle.diagnostic_scores.get("e_value") == pytest.approx(2.5)
        assert bundle.diagnostic_scores.get("rosenbaum_gamma") == pytest.approx(1.8)

    def test_empty_node_outputs_returns_valid_bundle(self):
        """G3: node_outputs={} → audit() returns valid EvidenceBundle."""
        bundle = CausalEngine().audit(self._ir(), None, run_id="r2", node_outputs={})
        assert isinstance(bundle, EvidenceBundle)

    def test_diagnostic_keys_captured(self):
        """G3: ess_fraction / overlap_score captured from diagnostic node output."""
        engine = CausalEngine()
        bundle = engine.audit(
            self._ir(),
            None,
            run_id="r3",
            node_outputs={"diag": {"ess_fraction": 0.72, "overlap_score": 0.88}},
        )
        assert bundle.diagnostic_scores.get("ess_fraction") == pytest.approx(0.72)
        assert bundle.diagnostic_scores.get("overlap_score") == pytest.approx(0.88)

    def test_none_node_outputs_default_works(self):
        """G3: default node_outputs=None → audit() still works (backward compat)."""
        bundle = CausalEngine().audit(self._ir(), None, run_id="r4")
        assert isinstance(bundle, EvidenceBundle)

    def test_non_dict_output_value_ignored(self):
        """G3: non-dict value in node_outputs doesn't crash audit()."""
        engine = CausalEngine()
        bundle = engine.audit(
            self._ir(),
            None,
            run_id="r5",
            node_outputs={"broken": "not-a-dict"},  # type: ignore[arg-type]
        )
        assert isinstance(bundle, EvidenceBundle)


# ---------------------------------------------------------------------------
# G4: Query validation gate
# ---------------------------------------------------------------------------


class TestG4ValidationGate:
    _VALIDATOR_PATH = "polisyos.foundry.methods.catalog.causal.query_validator.CausalQueryValidator"

    def test_error_report_returns_negative_cert_before_compile(self):
        """G4: Validator ERROR → (None, bundle, NegativeCertificate) without compile."""
        engine = CausalEngine()
        identified = _minimal_ir()

        with (
            patch.object(engine, "identify", return_value=identified),
            patch(self._VALIDATOR_PATH) as MockVal,
            patch.object(engine, "compile") as mock_compile,
        ):
            MockVal.return_value.validate.return_value = _error_val_report()
            report, bundle, cert = engine.run("X", "Y", MagicMock())

        assert report is None
        assert isinstance(bundle, EvidenceBundle)
        assert isinstance(cert, NegativeCertificate)
        assert cert.blocking_type == BlockingType.MISSING_DISTRIBUTION
        assert "Treatment X not in graph" in cert.blocking_description
        mock_compile.assert_not_called()

    def test_warning_only_does_not_block(self):
        """G4: WARNING-only report → validation passes, execution continues to compile."""
        engine = CausalEngine()
        identified = _minimal_ir()

        with (
            patch.object(engine, "identify", return_value=identified),
            patch(self._VALIDATOR_PATH) as MockVal,
            patch.object(engine, "compile", side_effect=ValueError("compile fail")),
        ):
            MockVal.return_value.validate.return_value = _warning_val_report()
            report, bundle, cert = engine.run("X", "Y", MagicMock())

        # Reached compile → cert is from compile failure, not validation
        assert cert is not None
        assert "Compilation failed" in cert.blocking_description

    def test_clean_report_continues_to_compilation(self):
        """G4: No errors → validation gate passes, compile step reached."""
        engine = CausalEngine()
        identified = _minimal_ir()

        with (
            patch.object(engine, "identify", return_value=identified),
            patch(self._VALIDATOR_PATH) as MockVal,
            patch.object(engine, "compile", side_effect=ValueError("compile fail")),
        ):
            MockVal.return_value.validate.return_value = _clean_val_report()
            _, _, cert = engine.run("X", "Y", MagicMock())

        assert cert is not None
        assert "Compilation failed" in cert.blocking_description


# ---------------------------------------------------------------------------
# G5: Conditional execution (skip_if_failed)
# ---------------------------------------------------------------------------


class TestG5ConditionalExecution:
    def test_nuisance_failure_does_not_break_loop(self):
        """G5: Failed nuisance node → loop continues, subsequent main node executes."""
        nuisance_id, main_id = "nuisance1", "main1"
        mock_report = MagicMock()
        graph = _make_executor_graph(
            nodes=(
                _make_node(node_id=nuisance_id, fqn="causal.nuisance.prop", is_nuisance=True),
                _make_node(node_id=main_id, fqn="causal.estimator.aipw"),
            ),
            nuisance_schedule=(nuisance_id,),
        )
        registry = _make_registry(
            {
                "causal.nuisance.prop": RuntimeError("nuisance failed"),
                "causal.estimator.aipw": {"report": mock_report},
            }
        )
        engine = CausalEngine(registry=registry)
        last_report, node_outputs = engine.estimate(graph, {})

        assert last_report is mock_report
        assert main_id in node_outputs

    def test_skip_if_failed_skips_dependent_node(self):
        """G5: Node with skip_if_failed=(A,) → not executed when A (nuisance) failed."""
        nuisance_id, dependent_id, independent_id = "nuisance1", "dep1", "indep1"
        mock_report = MagicMock()
        graph = _make_executor_graph(
            nodes=(
                _make_node(node_id=nuisance_id, fqn="causal.nuisance.prop", is_nuisance=True),
                _make_node(
                    node_id=dependent_id,
                    fqn="causal.estimator.aipw",
                    skip_if_failed=(nuisance_id,),
                ),
                _make_node(node_id=independent_id, fqn="causal.estimator.tmle"),
            ),
            nuisance_schedule=(nuisance_id,),
        )
        registry = _make_registry(
            {
                "causal.nuisance.prop": RuntimeError("nuisance failed"),
                "causal.estimator.aipw": {"report": MagicMock()},
                "causal.estimator.tmle": {"report": mock_report},
            }
        )
        engine = CausalEngine(registry=registry)
        last_report, node_outputs = engine.estimate(graph, {})

        assert dependent_id not in node_outputs  # skipped via skip_if_failed
        assert independent_id in node_outputs  # ran normally

    def test_main_estimator_failure_breaks_and_does_not_execute_subsequent(self):
        """G5: Main estimator failure → loop breaks; subsequent node not executed.

        Note: failure-report building is best-effort (CausalEffectReport validation
        may fail for 'unknown' method values), so we assert only the G5 invariant —
        that the loop broke and the subsequent node was never invoked.
        """
        main_id, subsequent_id = "main1", "sub1"
        graph = _make_executor_graph(
            nodes=(
                _make_node(node_id=main_id, fqn="causal.estimator.aipw"),
                _make_node(node_id=subsequent_id, fqn="causal.estimator.dr"),
            ),
        )
        registry = _make_registry(
            {
                "causal.estimator.aipw": RuntimeError("exploded"),
                "causal.estimator.dr": {"report": MagicMock()},
            }
        )
        engine = CausalEngine(registry=registry)
        _, node_outputs = engine.estimate(graph, {})

        # G5 invariant: loop broke after main failure → subsequent never ran
        assert subsequent_id not in node_outputs
        # main node itself also not in outputs (exception before assignment)
        assert main_id not in node_outputs


# ---------------------------------------------------------------------------
# G6: ProofStep enrichment + SuggestedExperiment fix
# ---------------------------------------------------------------------------


class TestG6AuditEnrichment:
    def test_proof_step_rule_formal_name_populated(self):
        """G6: IRProofStep.rule_formal_name == IDProofStep.rule_name."""
        id_step = MagicMock()
        id_step.rule_name = "backdoor_criterion"
        id_step.applied_to_graph_state = "G[do(X)]"
        id_step.consequent_vars = ["Y"]
        id_step.depth = 2

        bundle = CausalEngine().audit(_minimal_ir(proof_steps=[id_step]), None, run_id="r1")

        assert len(bundle.proof_steps) == 1
        step = bundle.proof_steps[0]
        assert step.rule_formal_name == "backdoor_criterion"
        assert step.applicable_theorem == "do-calculus depth=2"
        assert step.graph_state_after == "G[do(X)]"
        assert step.graph_state_before == ""

    def test_applicable_theorem_empty_when_depth_is_none(self):
        """G6: proof step with depth=None → applicable_theorem == ''."""
        id_step = MagicMock()
        id_step.rule_name = "frontdoor"
        id_step.applied_to_graph_state = ""
        id_step.consequent_vars = []
        id_step.depth = None

        bundle = CausalEngine().audit(_minimal_ir(proof_steps=[id_step]), None, run_id="r2")
        assert bundle.proof_steps[0].applicable_theorem == ""

    def test_hedge_cert_wraps_string_into_suggested_experiment(self):
        """G6: _hedge_to_negative_cert wraps string hint → SuggestedExperiment."""
        required_data = MagicMock()
        required_data.missing_distributions = []
        required_data.suggested_experiment = "Run RCT on X in target domain"
        required_data.alternative_identification = None

        cert = MagicMock()
        cert.hedge_forest = frozenset({"X"})
        cert.hedge_root = frozenset({"Y"})
        cert.required_data = required_data
        cert.description = "hedge found"

        ir = IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[],
            required_distributions=[],
        )
        neg_cert = CausalEngine()._hedge_to_negative_cert(ir)

        assert len(neg_cert.suggested_experiments) == 1
        se = neg_cert.suggested_experiments[0]
        assert isinstance(se, SuggestedExperiment)
        assert se.description == "Run RCT on X in target domain"

    def test_hedge_cert_empty_suggested_experiment_gets_auto_suggestion(self):
        """G6 (Track 6 update): suggested_experiment=None → auto_suggest_experiments() populates RCT."""
        required_data = MagicMock()
        required_data.missing_distributions = []
        required_data.suggested_experiment = None
        required_data.alternative_identification = None

        cert = MagicMock()
        cert.hedge_forest = frozenset()
        cert.hedge_root = frozenset()
        cert.required_data = required_data
        cert.description = ""

        ir = IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[],
            required_distributions=[],
        )
        neg_cert = CausalEngine()._hedge_to_negative_cert(ir)

        # Track 6: auto_suggest_experiments always fills in at least one RCT suggestion
        assert len(neg_cert.suggested_experiments) >= 1
        assert neg_cert.suggested_experiments[0].design_type == "RCT"
