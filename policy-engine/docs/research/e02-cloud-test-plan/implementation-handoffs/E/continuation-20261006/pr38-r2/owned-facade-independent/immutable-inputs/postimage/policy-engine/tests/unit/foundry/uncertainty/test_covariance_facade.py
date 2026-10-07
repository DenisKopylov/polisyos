"Covariance consumers use the admitted facade and canonical numeric objects."

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
        if name not in uncertainty.__all__:
            raise AssertionError
        if getattr(uncertainty, name) is not getattr(owner, name):
            raise AssertionError
        if getattr(welfare, name) is not getattr(uncertainty, name):
            raise AssertionError
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
    if not (float(np.array([1.0, -1.0]) @ matrix @ [1.0, -1.0]) == 0.0):
        raise AssertionError
    if not (0.0025 + 0.0025 == 0.005):
        raise AssertionError  # Independent marginals describe a different law.
    with pytest.raises(ValueError, match="positive semidefinite"):
        uncertainty.preserve_singular_covariance([[1.0, 1.1], [1.1, 1.0]])
    if not (uncertainty.calibration_covariance_blocks_agree_v1(matrix, matrix)):
        raise AssertionError
    if uncertainty.calibration_covariance_blocks_agree_v1(
        matrix, [[0.0025, 0.00250001], [0.0025, 0.0025]]
    ):
        raise AssertionError


def test_actual_welfare_covariance_route_is_a_supported_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    if any(edge.target_module == "polisyos.foundry.uncertainty.covariance" for edge in edges):
        raise AssertionError


def test_covariance_facade_preserves_missing_optional_jax_dependency() -> None:
    command = (
        "\nimport importlib.abc, json, sys\nclass B"
        "lockJax(importlib.abc.MetaPathFinder):\n "
        "   def find_spec(self, fullname, path=No"
        "ne, target=None):\n        if fullname =="
        " 'jax' or fullname.startswith('jax.'):\n "
        "           raise ModuleNotFoundError('fi"
        "xture blocks optional JAX', name=fullnam"
        "e)\nsys.meta_path.insert(0, BlockJax())\nf"
        "rom polisyos.foundry import uncertainty\n"
        "assert uncertainty.PropagationDispatcher"
        " is None\ntry:\n    uncertainty.preserve_s"
        "ingular_covariance\nexcept ImportError as"
        " error:\n    assert error.name == 'jax' o"
        "r error.name.startswith('jax.')\n    prin"
        "t(json.dumps({'facade_import': 'PASS', '"
        "numeric_request': 'ImportError'}))\nelse:"
        "\n    raise AssertionError('missing numer"
        "ic dependency was hidden')\n"
    )
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not (result.returncode == 0):
        raise AssertionError(result.stderr)
    if not (
        json.loads(result.stdout) == {"facade_import": "PASS", "numeric_request": "ImportError"}
    ):
        raise AssertionError
