"Independent actual consumer identities and optional-stack boundary checks."

import importlib
import json
import subprocess
import sys

import numpy as np
import pytest


def _require_same_object(value: object, expected: object) -> None:
    "Reject a numeric-compatible proxy that changes the canonical owner object."
    if value is not expected:
        raise AssertionError("consumer callable is not the canonical owner")


NAMES = (
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    "build_covariance_matrix",
    "calibration_covariance_blocks_agree_v1",
    "preserve_singular_covariance",
)


def test_both_real_consumer_globals_are_owner_objects_and_count_metadata_matches() -> None:
    facade = importlib.import_module("polisyos.foundry.uncertainty")
    owner = importlib.import_module("polisyos.foundry.uncertainty.covariance")
    welfare = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_welfare"
    )
    legacy = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty"
    )
    report_owner = importlib.import_module("polisyos.foundry.calibration.report")
    calibration = importlib.import_module("polisyos.calibration")
    if not (len(facade.__all__) == 25 and len(set(facade.__all__)) == 25):
        raise AssertionError
    if not (len(calibration.__all__) == 28):
        raise AssertionError
    for name in NAMES:
        if getattr(facade, name) is not getattr(owner, name):
            raise AssertionError
        if getattr(welfare, name) is not getattr(owner, name):
            raise AssertionError
    if legacy.load_foundry_calibration_report is not report_owner.load_calibration_report:
        raise AssertionError
    if facade.load_foundry_calibration_report is not report_owner.load_calibration_report:
        raise AssertionError
    if hasattr(calibration, "load_foundry_calibration_report"):
        raise AssertionError
    if not (facade.CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1 == 1e-7):
        raise AssertionError
    if not (facade.CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1 == 1e-10):
        raise AssertionError
    np.testing.assert_array_equal(
        facade.preserve_singular_covariance([[0.25, -0.25], [-0.25, 0.25]]) @ [1, 1],
        [0, 0],
    )


def test_optional_jax_refuses_required_lookup_but_preserves_base_facade_import() -> None:
    source = (
        "\nimport importlib.abc, json, sys\nclass RefuseJax(importlib.a"
        "bc.MetaPathFinder):\n    def find_spec(self, fullname, path=N"
        "one, target=None):\n        if fullname == 'jax' or fullname."
        "startswith('jax.'):\n            raise ModuleNotFoundError('i"
        "ndependent unavailable optional JAX', name=fullname)\nsys.met"
        "a_path.insert(0, RefuseJax())\nfrom polisyos.foundry import u"
        "ncertainty\nassert uncertainty.PropagationDispatcher is None\n"
        "assert 'polisyos.foundry.uncertainty.covariance' not in sys."
        "modules\nfor name in ('preserve_singular_covariance','build_c"
        "ovariance_matrix'):\n    try:\n        getattr(uncertainty,nam"
        "e)\n    except ImportError as exc:\n        assert exc.name =="
        " 'jax' or exc.name.startswith('jax.')\n    else:\n        rais"
        "e AssertionError('unavailable numeric owner silently admitte"
        "d')\nassert 'polisyos.foundry.uncertainty.covariance' not in "
        "sys.modules\nprint(json.dumps({'base_import':'PASS','required"
        "_numeric_lookup':'ImportError','authority':'not_established'"
        "}))\n"
    )
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not (result.returncode == 0):
        raise AssertionError(result.stderr)
    if not (json.loads(result.stdout)["required_numeric_lookup"] == "ImportError"):
        raise AssertionError


def test_present_numeric_proxy_preserves_values_but_fails_owner_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = importlib.import_module("polisyos.foundry.uncertainty")
    owner = importlib.import_module("polisyos.foundry.uncertainty.covariance")
    native = owner.preserve_singular_covariance

    def proxy(value: object) -> object:
        return native(value)

    monkeypatch.setattr(facade, "preserve_singular_covariance", proxy)
    np.testing.assert_array_equal(facade.preserve_singular_covariance([[0.25]]), [[0.25]])
    if "preserve_singular_covariance" not in facade.__all__:
        raise AssertionError
    with pytest.raises(AssertionError):
        _require_same_object(facade.preserve_singular_covariance, native)
