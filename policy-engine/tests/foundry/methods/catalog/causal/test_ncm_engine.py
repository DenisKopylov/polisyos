"""Tests for NCMEngineMethod — Abduction-Action-Prediction for NCMs.

Coverage (15 tests):
  1.  test_validate_markov_condition_acyclic_independent — True for standard DAG NCM
  2.  test_validate_markov_condition_cyclic — False for cyclic NCM
  3.  test_abduce_exogenous_linear_exact — analytic U = Y - f(Pa)
  4.  test_abduce_exogenous_empty_evidence — returns empty dict
  5.  test_abduce_exogenous_delegates_to_scm_spec — uses _abduce_noises_unified
  6.  test_predict_from_abducted_linear — deterministic for linear equation
  7.  test_counterfactual_world_do_x_linear_chain — Y_x = 0.5 + 2.0 * x
  8.  test_counterfactual_world_respects_evidence — abduction pins U from evidence
  9.  test_parallel_worlds_k3_share_same_u — K=3 worlds, shared noise
 10.  test_parallel_worlds_k1_observational — single world, no intervention
 11.  test_twin_network_from_ncm_doubles_variables — result has 2n variables
 12.  test_ncm_engine_pure_step_runs — end-to-end dispatch, output keys present
 13.  test_ncm_engine_output_is_serializable — model_dump round-trip via json
 14.  test_ncm_engine_registered — NCMEngineMethod in registry
 15.  test_ncm_spec_validation_missing_exo_raises — model_validator error
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.ncm_engine import (
    NCMEngineMethod,
    _abduce_exogenous,
    _counterfactual_world,
    _ncm_topological_order,
    _parallel_worlds,
    _predict_from_abducted,
    _twin_network_from_ncm,
    _validate_markov_condition,
)
from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _chain_scm(*, noise_std: float = 0.0) -> StructuralCausalModelSpec:
    """Simple linear chain X → Y: Y = 0.5 + 2.0 * X + U_Y."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.5,
                    "coefficients": {"X": 2.0},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _chain_ncm(*, noise_std: float = 0.0) -> NCMSpec:
    """NCMSpec wrapping _chain_scm."""
    scm = _chain_scm(noise_std=noise_std)
    return NCMSpec(
        endogenous_vars=["X", "Y"],
        exogenous_specs=[
            ExogenousSpec(variable="U_X", associated_endogenous="X"),
            ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="X",
                parents=[],
                exogenous="U_X",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="Y",
                parents=["X"],
                exogenous="U_Y",
                equation_type="linear",
                equation_params={"intercept": 0.5, "coefficients": {"X": 2.0}},
            ),
        ],
        scm_spec=scm,
        is_acyclic=True,
    )


def _symbolic_chain_ncm() -> NCMSpec:
    """Symbolic NCMSpec (no scm_spec) for testing fallback code paths."""
    return NCMSpec(
        endogenous_vars=["X", "Y"],
        exogenous_specs=[
            ExogenousSpec(variable="U_X", associated_endogenous="X"),
            ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="X",
                parents=[],
                exogenous="U_X",
                equation_type="linear",
                equation_params={"intercept": 1.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="Y",
                parents=["X"],
                exogenous="U_Y",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {"X": 3.0}},
            ),
        ],
        scm_spec=None,
        is_acyclic=True,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestValidateMarkovCondition:
    def test_validate_markov_condition_acyclic_independent(self):
        ncm = _chain_ncm()
        assert _validate_markov_condition(ncm) is True

    def test_validate_markov_condition_cyclic(self):
        ncm = NCMSpec(
            endogenous_vars=["X", "Y"],
            exogenous_specs=[
                ExogenousSpec(variable="U_X", associated_endogenous="X"),
                ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
            ],
            structural_equations=[
                StructuralEquation(variable="X", parents=["Y"], exogenous="U_X", equation_type="linear"),
                StructuralEquation(variable="Y", parents=["X"], exogenous="U_Y", equation_type="linear"),
            ],
            is_acyclic=False,
        )
        assert _validate_markov_condition(ncm) is False


class TestAbduceExogenous:
    def test_abduce_exogenous_empty_evidence(self):
        ncm = _chain_ncm()
        warnings: list[str] = []
        result = _abduce_exogenous(ncm, {}, "exact", warnings=warnings)
        assert result == {}

    def test_abduce_exogenous_delegates_to_scm_spec(self):
        """When scm_spec is present, delegation returns noise via _abduce_noises_unified."""
        ncm = _chain_ncm(noise_std=0.0)
        # With Y = 0.5 + 2.0 * X and no noise, abducted U_Y = Y - (0.5 + 2.0 * X)
        evidence = {"X": 1.0, "Y": 3.0}  # Y = 0.5 + 2*1 = 2.5, so U_Y = 0.5
        warnings: list[str] = []
        noise = _abduce_exogenous(ncm, evidence, "exact", warnings=warnings)
        assert "Y" in noise
        assert abs(noise["Y"] - 0.5) < 1e-9

    def test_abduce_exogenous_symbolic_linear_exact(self):
        """Symbolic NCM (no scm_spec): closed-form U = Y - f(Pa)."""
        ncm = _symbolic_chain_ncm()
        # Y = 3.0 * X, X = 1.0 (from equation_params intercept)
        # evidence: X=2.0 → X = 1.0 (intercept) + U_X → U_X = 1.0
        # Y = 3*2 + U_Y = 6 → U_Y = 0.0 for Y=6
        evidence = {"X": 2.0, "Y": 6.0}
        warnings: list[str] = []
        noise = _abduce_exogenous(ncm, evidence, "exact", warnings=warnings)
        assert "X" in noise
        assert abs(noise["X"] - 1.0) < 1e-9  # U_X = 2.0 - 1.0(intercept)
        assert "Y" in noise
        assert abs(noise["Y"]) < 1e-9  # U_Y = 6.0 - 3*2.0 = 0.0

    def test_abduce_mcmc_falls_back_to_exact_with_warning(self):
        ncm = _chain_ncm()
        evidence = {"X": 1.0, "Y": 2.5}
        warnings: list[str] = []
        _abduce_exogenous(ncm, evidence, "mcmc", warnings=warnings)
        assert any("mcmc" in w for w in warnings)


class TestPredictFromAbducted:
    def test_predict_from_abducted_linear(self):
        ncm = _chain_ncm()
        order = _ncm_topological_order(ncm)
        from polisyos.foundry.methods.catalog.causal.gcm_query import _parents_by_node
        parents_map = _parents_by_node(ncm.scm_spec)
        warnings: list[str] = []
        # With U_Y = 0, Y = 0.5 + 2.0 * 1.0 = 2.5
        result = _predict_from_abducted(ncm, {"X": 0.0, "Y": 0.0}, {"X": 1.0}, order, parents_map, warnings)
        assert abs(result["Y"] - 2.5) < 1e-9

    def test_predict_intervention_overrides_equation(self):
        ncm = _chain_ncm()
        order = _ncm_topological_order(ncm)
        from polisyos.foundry.methods.catalog.causal.gcm_query import _parents_by_node
        parents_map = _parents_by_node(ncm.scm_spec)
        warnings: list[str] = []
        # do(Y=99.0) overrides structural equation
        result = _predict_from_abducted(ncm, {}, {"X": 1.0, "Y": 99.0}, order, parents_map, warnings)
        assert result["Y"] == 99.0


class TestCounterfactualWorld:
    def test_counterfactual_world_do_x_linear_chain(self):
        """Y_{do(X=x)} = 0.5 + 2.0 * x for deterministic chain."""
        ncm = _chain_ncm(noise_std=0.0)
        for x_val in [0.0, 1.0, 2.5, -1.0]:
            warnings: list[str] = []
            result = _counterfactual_world(ncm, {"X": x_val}, {}, "exact", warnings=warnings)
            expected_y = 0.5 + 2.0 * x_val
            assert abs(result["Y"] - expected_y) < 1e-9, f"Failed for X={x_val}"

    def test_counterfactual_world_respects_evidence(self):
        """Evidence pins factual world; counterfactual uses abducted U."""
        ncm = _chain_ncm(noise_std=0.0)
        # Factual: X=1.0, Y=5.0 → U_Y = 5.0 - (0.5 + 2.0*1.0) = 2.5
        # Counterfactual do(X=2.0): Y = 0.5 + 2.0*2.0 + 2.5 = 7.0
        evidence = {"X": 1.0, "Y": 5.0}
        warnings: list[str] = []
        result = _counterfactual_world(ncm, {"X": 2.0}, evidence, "exact", warnings=warnings)
        assert abs(result["Y"] - 7.0) < 1e-9


class TestParallelWorlds:
    def test_parallel_worlds_k3_share_same_u(self):
        """K=3 worlds with different X values — should share noise."""
        ncm = _chain_ncm(noise_std=0.5)
        rng = np.random.default_rng(42)
        warnings: list[str] = []
        n_samples = 1000
        interventions = [{"X": 0.0}, {"X": 1.0}, {"X": 2.0}]
        worlds = _parallel_worlds(ncm, interventions, {}, "exact", n_samples=n_samples, rng=rng, warnings=warnings)

        assert len(worlds) == 3
        for w in worlds:
            assert "Y" in w
            assert len(w["Y"]) == n_samples
            assert np.all(np.isfinite(w["Y"]))

        # E[Y_{do(X=1)}] - E[Y_{do(X=0)}] ≈ 2.0 (the coefficient)
        diff = np.mean(worlds[1]["Y"]) - np.mean(worlds[0]["Y"])
        assert abs(diff - 2.0) < 0.15  # loose tolerance for MC

    def test_parallel_worlds_k1_observational(self):
        """Single world with empty intervention = observational."""
        ncm = _chain_ncm(noise_std=1.0)
        rng = np.random.default_rng(0)
        warnings: list[str] = []
        worlds = _parallel_worlds(ncm, [{}], {}, "exact", n_samples=500, rng=rng, warnings=warnings)
        assert len(worlds) == 1
        assert "Y" in worlds[0]
        assert len(worlds[0]["Y"]) == 500


class TestTwinNetworkFromNCM:
    def test_twin_network_doubles_variables(self):
        ncm = _chain_ncm()
        twin = _twin_network_from_ncm(ncm)
        assert len(twin.endogenous_vars) == 2 * len(ncm.endogenous_vars)
        assert "X__0" in twin.endogenous_vars
        assert "X__1" in twin.endogenous_vars
        assert "Y__0" in twin.endogenous_vars
        assert "Y__1" in twin.endogenous_vars

    def test_twin_network_scm_spec_is_none(self):
        ncm = _chain_ncm()
        twin = _twin_network_from_ncm(ncm)
        assert twin.scm_spec is None


class TestNCMEnginePureStep:
    def test_ncm_engine_pure_step_runs(self):
        ncm = _chain_ncm(noise_std=0.3)
        query_data = NCMQueryData(
            ncm_spec=ncm,
            evidence={"X": 1.0},
            interventions=[{"X": 0.0}, {"X": 1.0}],
            query_vars=["Y"],
            n_samples=200,
        )
        result = NCMEngineMethod.pure_step(
            {"ncm_query_data": query_data},
            {"__seed__": 7},
        )
        assert "counterfactual_result" in result
        cr = result["counterfactual_result"]
        assert cr["n_worlds"] == 2
        assert cr["n_samples"] == 200
        assert len(cr["world_summaries"]) == 2
        # Each world summary should have Y statistics
        for ws in cr["world_summaries"]:
            assert "Y" in ws
            assert math.isfinite(ws["Y"]["mean"])

    def test_ncm_engine_output_is_serializable(self):
        ncm = _chain_ncm()
        query_data = NCMQueryData(
            ncm_spec=ncm,
            interventions=[{"X": 1.0}],
            n_samples=100,
        )
        result = NCMEngineMethod.pure_step({"ncm_query_data": query_data}, {"__seed__": 1})
        # Should be JSON-serializable
        dumped = json.dumps(result["counterfactual_result"])
        reloaded = json.loads(dumped)
        assert reloaded["n_worlds"] == 1

    def test_ncm_engine_registered(self):
        from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
        from polisyos.foundry.methods.registry import MethodRegistry
        MethodRegistry.reset_instance()
        ensure_causal_methods_registered()
        reg = MethodRegistry.get_instance()
        # NCMEngineMethod should be findable
        all_sigs = reg.list_all()
        names = [s.fqn for s in all_sigs]
        matches = [name for name in names if "ncm_engine" in name]
        assert len(matches) >= 1, f"NCMEngineMethod not found in registry; found: {names}"
        MethodRegistry.reset_instance()


class TestNCMSpecValidation:
    def test_ncm_spec_validation_missing_exo_raises(self):
        """model_validator should raise when equation has no matching ExogenousSpec."""
        with pytest.raises(ValueError, match="no ExogenousSpec"):
            NCMSpec(
                endogenous_vars=["X", "Y"],
                exogenous_specs=[
                    ExogenousSpec(variable="U_X", associated_endogenous="X"),
                    # Missing U_Y for Y!
                ],
                structural_equations=[
                    StructuralEquation(variable="X", parents=[], exogenous="U_X", equation_type="linear"),
                    StructuralEquation(variable="Y", parents=["X"], exogenous="U_Y", equation_type="linear"),
                ],
            )

    def test_ncm_spec_schema_round_trip(self):
        ncm = _chain_ncm()
        dumped = ncm.model_dump(mode="json")
        restored = NCMSpec.model_validate(dumped)
        assert restored.endogenous_vars == ncm.endogenous_vars
        assert len(restored.structural_equations) == len(ncm.structural_equations)
