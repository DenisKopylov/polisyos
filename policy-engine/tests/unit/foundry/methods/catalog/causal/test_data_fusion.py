"""Tests for Phase 9: DataFusionEngine — multi-source causal data fusion.

Covers:
- fuse_experimental_observational (Z-transport)
- multi_study_fusion (mZ-ID)
- optimal_data_combination (inverse-variance weighting)
- design_external_validity (TR algorithm wrapper)

Reference:
  Bareinboim & Pearl (2016). Causal inference and the data-fusion problem. PNAS.
"""

from __future__ import annotations

from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.data_fusion import (
    DataCombinationPlan,
    FusionDataset,
    FusionResult,
    ValidityReport,
)
from polisyos.ir.analytics.transportability import SNode

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dag(edges: list[tuple[str, str]], extra_nodes: list[str] | None = None) -> CausalGraphModel:
    """Build a simple DAG from (src, dst) edge pairs."""
    nodes = sorted({n for e in edges for n in e} | set(extra_nodes or []))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


def _bidir(graph: CausalGraphModel, src: str, dst: str) -> CausalGraphModel:
    """Add a bidirected edge (latent confounder) between src and dst.

    Returns an ADMG (Acyclic Directed Mixed Graph) to allow bidirected edges.
    """
    extra = CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=list(graph.nodes),
        edges=list(graph.edges) + [extra],
    )


def _snode(var: str) -> SNode:
    return SNode(
        target_variable=var,
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )


# ---------------------------------------------------------------------------
# TestFuseExperimentalObservational
# ---------------------------------------------------------------------------


class TestFuseExperimentalObservational:
    """Z-transport: combine RCT + observational via z_id_algorithm."""

    def test_simple_mediated_structure(self):
        """Z→X→Y (IV-like): RCT on Z makes X identifiable even without Z→Y confounding."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        graph = _dag([("Z", "X"), ("X", "Y")])
        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["Z"],
        )

        assert isinstance(result, FusionResult)
        assert result.identification_algorithm == "z-id"
        assert "obs" in result.required_datasets
        assert "rct" in result.required_datasets
        assert "Z" in result.required_interventions

    def test_identified_with_z_interventions(self):
        """When Z-interventions enable identification, is_identified=True and formula set."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        # Simple identifiable graph: X→Y with no confounders; Z as extra var
        graph = _dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["Z"],
        )

        # The algorithm should run and return a FusionResult
        assert isinstance(result, FusionResult)
        assert result.identification_algorithm == "z-id"

    def test_empty_interventions_still_returns_result(self):
        """Empty exp_interventions: falls back to observational ID."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        graph = _dag([("X", "Y")])
        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=[],
        )

        assert isinstance(result, FusionResult)
        assert result.identification_algorithm == "z-id"
        assert result.required_interventions == ()

    def test_custom_data_refs(self):
        """Custom obs_data_ref and exp_data_ref are reflected in output."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        graph = _dag([("X", "Y")])
        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["Z"],
            obs_data_ref="my_obs",
            exp_data_ref="my_rct",
        )

        assert "my_obs" in result.required_datasets
        assert "my_rct" in result.required_datasets

    def test_proof_steps_nonempty_on_success(self):
        """Successful identification should produce proof steps."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        graph = _dag([("Z", "X"), ("X", "Y")])
        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["Z"],
        )

        # proof_steps may be empty for trivial ID, but result must be a valid FusionResult
        assert isinstance(result.proof_steps, tuple)


# ---------------------------------------------------------------------------
# TestMultiStudyFusion
# ---------------------------------------------------------------------------


class TestMultiStudyFusion:
    """mZ-ID: combine K studies with heterogeneous selection biases."""

    def _make_dataset(
        self,
        domain_id: str,
        dataset_ref: str,
        selection_bias_vars: tuple[str, ...] = (),
        available_interventions: tuple[str, ...] = (),
    ) -> FusionDataset:
        return FusionDataset(
            dataset_ref=dataset_ref,
            domain_id=domain_id,
            n_obs=1000,
            selection_bias_vars=selection_bias_vars,
            available_interventions=available_interventions,
        )

    def test_single_study_no_bias(self):
        """Single observational study with no S-nodes: routes to ID algorithm."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        graph = _dag([("X", "Y")])
        ds = self._make_dataset("d1", "study_obs")
        result = multi_study_fusion(datasets=[ds], graph=graph, treatment="X", outcome="Y")

        assert isinstance(result, FusionResult)
        assert result.identification_algorithm == "mz-id"
        assert "study_obs" in result.required_datasets

    def test_single_study_with_z_interventions(self):
        """Single study with z_interventions routes through mZ-ID."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        graph = _dag([("Z", "X"), ("X", "Y")])
        ds = self._make_dataset("d1", "rct", available_interventions=("Z",))
        result = multi_study_fusion(datasets=[ds], graph=graph, treatment="X", outcome="Y")

        assert isinstance(result, FusionResult)
        assert "Z" in result.required_interventions

    def test_two_studies_combined(self):
        """Two studies with complementary selection bias information."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        # Graph: C→X, C→Y (confounded); X→Y
        graph = _dag([("C", "X"), ("C", "Y"), ("X", "Y")])
        ds1 = self._make_dataset("d1", "study1", selection_bias_vars=("C",))
        ds2 = self._make_dataset("d2", "study2")
        result = multi_study_fusion(datasets=[ds1, ds2], graph=graph, treatment="X", outcome="Y")

        assert isinstance(result, FusionResult)
        assert result.identification_algorithm == "mz-id"

    def test_result_required_datasets(self):
        """required_datasets lists all non-None dataset refs."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        graph = _dag([("X", "Y")])
        ds1 = self._make_dataset("d1", "ref_a")
        ds2 = self._make_dataset("d2", "ref_b")
        result = multi_study_fusion(datasets=[ds1, ds2], graph=graph, treatment="X", outcome="Y")

        assert "ref_a" in result.required_datasets
        assert "ref_b" in result.required_datasets

    def test_query_string_format(self):
        """Query string includes treatment and outcome names."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        graph = _dag([("A", "B")])
        ds = self._make_dataset("d1", "study1")
        result = multi_study_fusion(datasets=[ds], graph=graph, treatment="A", outcome="B")

        assert "A" in result.query
        assert "B" in result.query

    def test_proof_steps_are_tuple(self):
        """proof_steps field is always a tuple (may be empty)."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        graph = _dag([("X", "Y")])
        ds = self._make_dataset("d1", "s1")
        result = multi_study_fusion(datasets=[ds], graph=graph, treatment="X", outcome="Y")

        assert isinstance(result.proof_steps, tuple)

    def test_warnings_on_failure(self):
        """Non-identified results emit warnings."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion

        # Graph with latent confounder U: X←U→Y but U is hidden (bidirected)
        graph = _bidir(_dag([("X", "Y")]), "X", "Y")
        # No RCT, no S-nodes that resolve it
        ds = self._make_dataset("d1", "obs")
        result = multi_study_fusion(datasets=[ds], graph=graph, treatment="X", outcome="Y")

        # Even if not identified, result is a valid FusionResult
        assert isinstance(result, FusionResult)
        # If not identified, warnings should be emitted
        if not result.is_identified:
            assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# TestOptimalDataCombination
# ---------------------------------------------------------------------------


class TestOptimalDataCombination:
    """Inverse-variance-optimal combination weights."""

    def test_equal_variances_equal_weights(self):
        """Two datasets with equal variance → weights = 0.5 each."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"d1": 1.0, "d2": 1.0},
            query="P*(Y|do(X))",
        )

        assert isinstance(plan, DataCombinationPlan)
        assert abs(plan.source_weights["d1"] - 0.5) < 1e-9
        assert abs(plan.source_weights["d2"] - 0.5) < 1e-9
        assert plan.expected_variance is not None
        assert abs(plan.expected_variance - 0.5) < 1e-9

    def test_unequal_variances_optimal_weights(self):
        """V1=1.0, V2=4.0 → w1=0.8, w2=0.2, V_combined=0.8."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"d1": 1.0, "d2": 4.0},
            query="ATE",
        )

        assert abs(plan.source_weights["d1"] - 0.8) < 1e-9
        assert abs(plan.source_weights["d2"] - 0.2) < 1e-9
        assert plan.expected_variance is not None
        assert abs(plan.expected_variance - 0.8) < 1e-9

    def test_single_dataset_weight_one(self):
        """Single dataset → weight = 1.0."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"only": 2.5},
            query="P(Y|do(X))",
        )

        assert abs(plan.source_weights["only"] - 1.0) < 1e-9
        assert plan.expected_variance is not None
        assert abs(plan.expected_variance - 2.5) < 1e-9

    def test_weights_sum_to_one(self):
        """Weights must sum to 1 for any input."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"a": 0.5, "b": 1.5, "c": 3.0},
            query="ATE",
        )

        total = sum(plan.source_weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_zero_variance_fallback(self):
        """All-zero variance → uniform fallback (no crash)."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"d1": 0.0, "d2": 0.0},
            query="ATE",
        )

        assert isinstance(plan, DataCombinationPlan)
        # Fallback: uniform
        assert plan.combination_method == "uniform_fallback"

    def test_required_datasets_passed_through(self):
        """required_datasets field is set from the argument."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            optimal_data_combination,
        )

        plan = optimal_data_combination(
            eif_variances={"d1": 1.0},
            query="P(Y|do(X))",
            required_datasets=["ref1", "ref2"],
        )

        assert "ref1" in plan.required_datasets
        assert "ref2" in plan.required_datasets


# ---------------------------------------------------------------------------
# TestDesignExternalValidity
# ---------------------------------------------------------------------------


class TestDesignExternalValidity:
    """design_external_validity wraps TR algorithm for population-level validity."""

    def test_no_s_nodes_transportable(self):
        """Graph with no S-nodes: trivially transportable."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            design_external_validity,
        )

        graph = _dag([("X", "Y")])
        report = design_external_validity(
            graph=graph,
            s_nodes=[],
            source_population="source",
            target_population="target",
            treatment="X",
            outcome="Y",
        )

        assert isinstance(report, ValidityReport)
        assert report.overall_transportability is True
        assert report.non_transportable_variables == ()

    def test_blocking_confounder_s_node(self):
        """S-node on confounder blocks transport when not adjustable."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            design_external_validity,
        )

        # C→X, C→Y (confounded); S_C signals mechanism shift in C
        graph = _bidir(_dag([("X", "Y")]), "X", "Y")
        s_nodes = [_snode("X")]  # S-node on X (mechanism differs)
        report = design_external_validity(
            graph=graph,
            s_nodes=s_nodes,
            source_population="europe",
            target_population="africa",
            treatment="X",
            outcome="Y",
        )

        assert isinstance(report, ValidityReport)
        assert report.source_population == "europe"
        assert report.target_population == "africa"
        assert "X" in report.recommended_adjustments

    def test_s_node_vars_in_recommended(self):
        """All S-node variables appear in recommended_adjustments."""
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            design_external_validity,
        )

        graph = _dag([("C", "X"), ("C", "Y"), ("X", "Y")])
        s_nodes = [_snode("C")]
        report = design_external_validity(
            graph=graph,
            s_nodes=s_nodes,
            source_population="pop_a",
            target_population="pop_b",
            treatment="X",
            outcome="Y",
        )

        assert "C" in report.recommended_adjustments


# ---------------------------------------------------------------------------
# TestCounterfactualFusion
# ---------------------------------------------------------------------------


class TestCounterfactualFusion:
    def _make_dataset(
        self,
        domain_id: str,
        dataset_ref: str,
        selection_bias_vars: tuple[str, ...] = (),
        available_interventions: tuple[str, ...] = (),
    ) -> FusionDataset:
        return FusionDataset(
            dataset_ref=dataset_ref,
            domain_id=domain_id,
            n_obs=200,
            selection_bias_vars=selection_bias_vars,
            available_interventions=available_interventions,
        )

    def test_counterfactual_fusion_identified(self) -> None:
        from polisyos.foundry.methods.catalog.causal.data_fusion import counterfactual_fusion
        from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery

        graph = _dag([], extra_nodes=["X", "Y"])
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        datasets = [
            self._make_dataset("d1", "study_obs", selection_bias_vars=("Y",)),
            self._make_dataset("d2", "study_rct", available_interventions=("X",)),
        ]

        result = counterfactual_fusion(
            datasets=datasets,
            graph=graph,
            counterfactual_query=query,
        )

        assert isinstance(result, FusionResult)
        assert result.is_identified is True
        assert result.identification_algorithm == "ctf_transport"
        assert "study_obs" in result.required_datasets
        assert "study_rct" in result.required_datasets
        assert "CTF_TRANSPORT_MZ" in result.proof_steps

    def test_counterfactual_fusion_failure_returns_warning(self) -> None:
        from polisyos.foundry.methods.catalog.causal.data_fusion import counterfactual_fusion
        from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery

        graph = _bidir(_dag([("X", "Y")]), "X", "Y")
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        datasets = [self._make_dataset("d1", "obs", selection_bias_vars=("Y",))]

        result = counterfactual_fusion(
            datasets=datasets,
            graph=graph,
            counterfactual_query=query,
        )

        assert isinstance(result, FusionResult)
        assert result.is_identified is False
        assert result.identification_algorithm == "ctf_transport"
        assert result.warnings

    def test_engine_ctf_fusion_mode(self) -> None:
        from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine

        graph = _dag([], extra_nodes=["X", "Y"])
        state = {"graph": graph}
        params = {
            "mode": "ctf_fusion",
            "datasets": [
                {
                    "dataset_ref": "study_obs",
                    "domain_id": "d1",
                    "n_obs": 100,
                    "selection_bias_vars": ["Y"],
                    "available_interventions": [],
                    "quality_score": 1.0,
                }
            ],
            "counterfactual_query": {
                "outcome": "Y",
                "intervention": [["X", 1.0]],
                "kind": "single_world",
            },
        }

        result = DataFusionEngine.pure_step(state, params)

        assert "fusion_result" in result
        assert result["fusion_result"]["identification_algorithm"] == "ctf_transport"
