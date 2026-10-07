"""Covariance consumers use the admitted facade and canonical numeric objects."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos.foundry import uncertainty
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    UncertaintyEnvelope,
    UncertaintySource,
)

_COVARIANCE_NAMES = (
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    "build_covariance_matrix",
    "calibration_covariance_blocks_agree_v1",
    "preserve_singular_covariance",
)


def _normal_env(std: float, row: list[float], order: list[str]) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-std, std),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL, parameters={"mean": 0.0, "std": std}
        ),
        metadata={"covariance_row": row, "covariance_params": order},
    )


def test_covariance_facade_preserves_owner_and_actual_welfare_object_identity() -> None:
    owner = importlib.import_module("polisyos.foundry.uncertainty.covariance")
    welfare = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_welfare"
    )
    for name in _COVARIANCE_NAMES:
        assert name in uncertainty.__all__
        assert getattr(uncertainty, name) is getattr(owner, name)
        assert getattr(welfare, name) is getattr(uncertainty, name)
    with pytest.raises(AttributeError):
        _ = uncertainty.nonexistent_covariance_authority


def test_covariance_facade_reconciles_owned_rows_and_declared_column_axes() -> None:
    envelopes = {
        "a": _normal_env(2.0, [1.0, 4.0], ["b", "a"]),
        "b": _normal_env(3.0, [9.0, 1.0], ["b", "a"]),
    }
    result = uncertainty.build_covariance_matrix(
        ["a", "b"], envelopes, use_full_covariance=True, jitter=0.0, preserve_singular=True
    )
    np.testing.assert_array_equal(result, [[4.0, 1.0], [1.0, 9.0]])
    forged = dict(envelopes)
    forged["b"] = _normal_env(3.0, [9.0, 1.0], ["a", "b"])
    with pytest.raises(ValueError, match="common column ordering"):
        uncertainty.build_covariance_matrix(
            ["a", "b"], forged, use_full_covariance=True, jitter=0.0, preserve_singular=True
        )


def test_covariance_facade_keeps_tied_nullspace_and_rejects_indefinite_law() -> None:
    matrix = uncertainty.preserve_singular_covariance([[0.0025, 0.0025], [0.0025, 0.0025]])
    np.testing.assert_array_equal(matrix @ [1.0, -1.0], [0.0, 0.0])
    assert float(np.array([1.0, -1.0]) @ matrix @ [1.0, -1.0]) == 0.0
    assert 0.0025 + 0.0025 == 0.005  # Independent marginals describe a different law.
    with pytest.raises(ValueError, match="positive semidefinite"):
        uncertainty.preserve_singular_covariance([[1.0, 1.1], [1.1, 1.0]])
    assert uncertainty.calibration_covariance_blocks_agree_v1(matrix, matrix)
    assert not uncertainty.calibration_covariance_blocks_agree_v1(
        matrix, [[0.0025, 0.00250001], [0.0025, 0.0025]]
    )


def test_actual_welfare_covariance_route_is_a_supported_entrypoint(monkeypatch) -> None:
    from tools.devx.architecture import guardrails

    welfare = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_welfare"
    )
    welfare_source = Path(welfare.__file__).resolve()
    product = welfare_source.parents[6]
    monkeypatch.setattr(guardrails, "REPO_ROOT", product)
    monkeypatch.setattr(guardrails, "SRC_ROOT", product / "src")
    monkeypatch.setattr(guardrails, "_iter_py_files", lambda: [welfare_source])
    policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
    edges = guardrails.collect_deep_import_edges(policies)
    assert not any(
        edge.target_module == "polisyos.foundry.uncertainty.covariance" for edge in edges
    )


def test_covariance_facade_preserves_missing_optional_jax_dependency() -> None:
    command = """
import importlib.abc, json, sys
class BlockJax(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'jax' or fullname.startswith('jax.'):
            raise ModuleNotFoundError('fixture blocks optional JAX', name=fullname)
sys.meta_path.insert(0, BlockJax())
from polisyos.foundry import uncertainty
assert uncertainty.PropagationDispatcher is None
try:
    uncertainty.preserve_singular_covariance
except ImportError as error:
    assert error.name == 'jax' or error.name.startswith('jax.')
    print(json.dumps({'facade_import': 'PASS', 'numeric_request': 'ImportError'}))
else:
    raise AssertionError('missing numeric dependency was hidden')
"""
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"facade_import": "PASS", "numeric_request": "ImportError"}
