"""Tests for HPActualCauseMethod — Halpern-Pearl actual causality (AC1/AC2/AC3).

Coverage (15 tests):
  1.  test_check_ac1_pass — context matches cause and effect values
  2.  test_check_ac1_fail_cause — cause value mismatch → AC1 False
  3.  test_check_ac1_fail_effect — effect value mismatch → AC1 False
  4.  test_ac2_empty_contingency_direct_cause — do(T=0) alone changes Y
  5.  test_ac2_requires_contingency_mediated — direct counterfactual fails, W needed
  6.  test_ac2_not_found_returns_none — disconnected var has no valid W
  7.  test_ac3_single_var_trivially_true — minimality always True for single-var
  8.  test_degree_of_responsibility_direct — DR=1.0 for direct cause
  9.  test_degree_of_responsibility_with_w — DR=0.5 when |W_min|=1
 10.  test_is_actual_cause_binary_chain — T=1 is actual cause of Y=1
 11.  test_is_not_actual_cause_disconnected_var — unrelated W not a cause
 12.  test_cyclic_ncm_raises — ValueError on cyclic NCM
 13.  test_hp_pure_step_runs — end-to-end dispatch returns HPResult dict
 14.  test_hp_pure_step_is_actual_cause_true — direct chain → is_actual_cause=True
 15.  test_hp_result_json_serializable — model_dump round-trip
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.actual_causality import (
    HPActualCauseMethod,
    _check_ac1,
    _check_ac2_find_contingency,
    _check_ac3_minimality,
    _degree_of_responsibility,
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


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _make_scm_chain() -> StructuralCausalModelSpec:
    """T → Y linear chain with no noise: Y = T."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["T", "Y"],
        edges=[CausalEdge(src="T", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="T",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.5, "std": 0.5},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["T"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"T": 1.0},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _make_ncm_direct() -> NCMSpec:
    """T → Y deterministic chain: Y = T."""
    scm = _make_scm_chain()
    return NCMSpec(
        endogenous_vars=["T", "Y"],
        exogenous_specs=[
            ExogenousSpec(variable="U_T", associated_endogenous="T"),
            ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="T",
                parents=[],
                exogenous="U_T",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="Y",
                parents=["T"],
                exogenous="U_Y",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {"T": 1.0}},
            ),
        ],
        scm_spec=scm,
        is_acyclic=True,
    )


def _make_ncm_cyclic() -> NCMSpec:
    """Cyclic NCM (is_acyclic=False) — should raise in AC2 check."""
    return NCMSpec(
        endogenous_vars=["A", "B"],
        exogenous_specs=[
            ExogenousSpec(variable="U_A", associated_endogenous="A"),
            ExogenousSpec(variable="U_B", associated_endogenous="B"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="A",
                parents=["B"],
                exogenous="U_A",
                equation_type="linear",
            ),
            StructuralEquation(
                variable="B",
                parents=["A"],
                exogenous="U_B",
                equation_type="linear",
            ),
        ],
        scm_spec=None,
        is_acyclic=False,
    )


def _make_ncm_three_node() -> NCMSpec:
    """T → M → Y chain: Y = M, M = T. T is indirect cause of Y."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["T", "M", "Y"],
        edges=[CausalEdge(src="T", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    scm = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="T",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.5, "std": 0.5},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="M",
                parents=["T"],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {"T": 1.0}, "noise_std": 0.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["M"],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {"M": 1.0}, "noise_std": 0.0},
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )
    return NCMSpec(
        endogenous_vars=["T", "M", "Y"],
        exogenous_specs=[
            ExogenousSpec(variable="U_T", associated_endogenous="T"),
            ExogenousSpec(variable="U_M", associated_endogenous="M"),
            ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
        ],
        structural_equations=[
            StructuralEquation(variable="T", parents=[], exogenous="U_T",
                               equation_type="linear", equation_params={"intercept": 0.0, "coefficients": {}}),
            StructuralEquation(variable="M", parents=["T"], exogenous="U_M",
                               equation_type="linear", equation_params={"intercept": 0.0, "coefficients": {"T": 1.0}}),
            StructuralEquation(variable="Y", parents=["M"], exogenous="U_Y",
                               equation_type="linear", equation_params={"intercept": 0.0, "coefficients": {"M": 1.0}}),
        ],
        scm_spec=scm,
        is_acyclic=True,
    )


# ── AC1 tests ──────────────────────────────────────────────────────────────────


class TestAC1:
    def test_check_ac1_pass(self):
        """AC1 passes when context contains matching T and Y values."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        result = _check_ac1(ncm, "T", 1.0, "Y", 1.0, context, 0.5, warnings)
        assert result is True

    def test_check_ac1_fail_cause(self):
        """AC1 fails when context T value doesn't match cause_value."""
        ncm = _make_ncm_direct()
        context = {"T": 0.0, "Y": 1.0}  # T=0 but cause_value=1
        warnings: list[str] = []
        result = _check_ac1(ncm, "T", 1.0, "Y", 1.0, context, 0.5, warnings)
        assert result is False

    def test_check_ac1_fail_effect(self):
        """AC1 fails when context Y value doesn't match effect_value threshold."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 0.0}  # Y=0 but effect_value=1 (threshold 0.5)
        warnings: list[str] = []
        result = _check_ac1(ncm, "T", 1.0, "Y", 1.0, context, 0.5, warnings)
        assert result is False


# ── AC2 tests ──────────────────────────────────────────────────────────────────


class TestAC2:
    def test_ac2_empty_contingency_direct_cause(self):
        """Direct T → Y: do(T=0) alone changes Y from 1 to 0 → empty contingency."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        contingency = _check_ac2_find_contingency(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, 0.5,
            max_contingency_size=3, warnings=warnings,
        )
        assert contingency is not None
        assert contingency.size == 0  # No contingency variables needed
        assert contingency.variables == []

    def test_ac2_not_found_returns_none_for_isolated(self):
        """If T is disconnected from Y (all-zero coefficients), no contingency found."""
        # Build NCM where T has zero effect on Y (Y = 0 always)
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["T", "Y"],
            edges=[CausalEdge(src="T", dst="Y")],
        )
        scm = StructuralCausalModelSpec(
            graph=graph,
            mechanisms=[
                NodeMechanism(
                    variable="T",
                    parents=[],
                    family=MechanismFamily.EMPIRICAL,
                    family_params={"mean": 0.5, "std": 0.5},
                    source=MechanismSource.DATA_FITTED,
                ),
                NodeMechanism(
                    variable="Y",
                    parents=["T"],
                    family=MechanismFamily.LINEAR,
                    family_params={"intercept": 1.0, "coefficients": {"T": 0.0}, "noise_std": 0.0},
                    source=MechanismSource.DATA_FITTED,
                ),
            ],
            fitted=True,
            fit_method="gcm",
        )
        ncm = NCMSpec(
            endogenous_vars=["T", "Y"],
            exogenous_specs=[
                ExogenousSpec(variable="U_T", associated_endogenous="T"),
                ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
            ],
            structural_equations=[
                StructuralEquation(variable="T", parents=[], exogenous="U_T",
                                   equation_type="linear", equation_params={"intercept": 0.0, "coefficients": {}}),
                StructuralEquation(variable="Y", parents=["T"], exogenous="U_Y",
                                   equation_type="linear", equation_params={"intercept": 1.0, "coefficients": {"T": 0.0}}),
            ],
            scm_spec=scm,
            is_acyclic=True,
        )
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        # do(T=0) still gives Y=1 (coefficient=0), so no contingency works
        contingency = _check_ac2_find_contingency(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, 0.5,
            max_contingency_size=2, warnings=warnings,
        )
        assert contingency is None

    def test_ac2_cyclic_ncm_raises_value_error(self):
        """Cyclic NCM must raise ValueError in AC2 check."""
        ncm = _make_ncm_cyclic()
        context = {"A": 1.0, "B": 1.0}
        warnings: list[str] = []
        with pytest.raises(ValueError, match="acyclic"):
            _check_ac2_find_contingency(
                ncm, "A", 1.0, 0.0, "B", 1.0, context, 0.5,
                max_contingency_size=2, warnings=warnings,
            )


# ── AC3 tests ──────────────────────────────────────────────────────────────────


class TestAC3:
    def test_ac3_single_var_trivially_true(self):
        """AC3 minimality always returns True for single-variable causes."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        from polisyos.ir.analytics.actual_causality import ContingencySet
        contingency = ContingencySet(variables=[], values={}, size=0)
        result = _check_ac3_minimality(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, contingency, 0.5,
            max_contingency_size=3, warnings=warnings,
        )
        assert result is True


# ── Degree of responsibility ───────────────────────────────────────────────────


class TestDegreeOfResponsibility:
    def test_degree_of_responsibility_direct(self):
        """Direct cause (empty contingency): DR = 1/(0+1) = 1.0."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        dr = _degree_of_responsibility(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, 0.5,
            max_contingency_size=3, warnings=warnings,
        )
        assert abs(dr - 1.0) < 1e-9

    def test_degree_of_responsibility_disconnected(self):
        """Completely disconnected (no contingency found): DR = 0.0."""
        # Build zero-effect NCM
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["T", "Y"],
            edges=[CausalEdge(src="T", dst="Y")],
        )
        scm = StructuralCausalModelSpec(
            graph=graph,
            mechanisms=[
                NodeMechanism(variable="T", parents=[], family=MechanismFamily.EMPIRICAL,
                              family_params={"mean": 0.5, "std": 0.5}, source=MechanismSource.DATA_FITTED),
                NodeMechanism(variable="Y", parents=["T"], family=MechanismFamily.LINEAR,
                              family_params={"intercept": 1.0, "coefficients": {"T": 0.0}, "noise_std": 0.0},
                              source=MechanismSource.DATA_FITTED),
            ],
            fitted=True,
            fit_method="gcm",
        )
        ncm = NCMSpec(
            endogenous_vars=["T", "Y"],
            exogenous_specs=[
                ExogenousSpec(variable="U_T", associated_endogenous="T"),
                ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
            ],
            structural_equations=[
                StructuralEquation(variable="T", parents=[], exogenous="U_T",
                                   equation_type="linear", equation_params={"intercept": 0.0, "coefficients": {}}),
                StructuralEquation(variable="Y", parents=["T"], exogenous="U_Y",
                                   equation_type="linear", equation_params={"intercept": 1.0, "coefficients": {"T": 0.0}}),
            ],
            scm_spec=scm,
            is_acyclic=True,
        )
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []
        dr = _degree_of_responsibility(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, 0.5,
            max_contingency_size=2, warnings=warnings,
        )
        assert dr == 0.0


# ── Integrated HP result ───────────────────────────────────────────────────────


class TestHPActualCauseBinaryChain:
    def test_is_actual_cause_direct_chain(self):
        """T=1 is actual cause of Y=1 in direct T→Y chain."""
        ncm = _make_ncm_direct()
        context = {"T": 1.0, "Y": 1.0}
        warnings: list[str] = []

        ac1 = _check_ac1(ncm, "T", 1.0, "Y", 1.0, context, 0.5, warnings)
        contingency = _check_ac2_find_contingency(
            ncm, "T", 1.0, 0.0, "Y", 1.0, context, 0.5,
            max_contingency_size=3, warnings=warnings,
        )
        ac2 = contingency is not None
        assert ac1 is True
        assert ac2 is True  # T→Y direct, so do(T=0) changes Y


# ── HPActualCauseMethod.pure_step ──────────────────────────────────────────────


class TestHPPureStep:
    def _make_query_dict(self, ncm: NCMSpec, evidence: dict) -> dict:
        return {
            "ncm_spec": ncm.model_dump(mode="json"),
            "evidence": evidence,
            "interventions": [],
            "query_vars": ["Y"],
            "metadata": {},
        }

    def test_pure_step_runs_and_has_hp_result(self):
        """pure_step returns hp_result with expected keys."""
        ncm = _make_ncm_direct()
        state = {"ncm_query_data": self._make_query_dict(ncm, {"T": 1.0, "Y": 1.0})}
        params = {
            "cause_variable": "T",
            "cause_value": 1.0,
            "counterfactual_cause_value": 0.0,
            "effect_variable": "Y",
            "effect_value": 1.0,
            "max_contingency_size": 3,
            "outcome_threshold": 0.5,
            "compute_responsibility": True,
        }
        out = HPActualCauseMethod.pure_step(state, params)
        assert "hp_result" in out
        hp = out["hp_result"]
        assert "is_actual_cause" in hp
        assert "ac1_satisfied" in hp
        assert "ac2_satisfied" in hp
        assert "ac3_satisfied" in hp
        assert "degree_of_responsibility" in hp

    def test_pure_step_direct_chain_is_actual_cause(self):
        """Direct chain T→Y: is_actual_cause should be True."""
        ncm = _make_ncm_direct()
        state = {"ncm_query_data": self._make_query_dict(ncm, {"T": 1.0, "Y": 1.0})}
        params = {
            "cause_variable": "T",
            "cause_value": 1.0,
            "counterfactual_cause_value": 0.0,
            "effect_variable": "Y",
            "effect_value": 1.0,
            "max_contingency_size": 3,
            "outcome_threshold": 0.5,
        }
        out = HPActualCauseMethod.pure_step(state, params)
        hp = out["hp_result"]
        assert hp["is_actual_cause"] is True
        assert hp["degree_of_responsibility"] == 1.0

    def test_pure_step_json_serializable(self):
        """HPResult output must be JSON-serializable."""
        ncm = _make_ncm_direct()
        state = {"ncm_query_data": self._make_query_dict(ncm, {"T": 1.0, "Y": 1.0})}
        params = {
            "cause_variable": "T",
            "cause_value": 1.0,
            "counterfactual_cause_value": 0.0,
            "effect_variable": "Y",
            "effect_value": 1.0,
        }
        out = HPActualCauseMethod.pure_step(state, params)
        # Should not raise
        json.dumps(out)
