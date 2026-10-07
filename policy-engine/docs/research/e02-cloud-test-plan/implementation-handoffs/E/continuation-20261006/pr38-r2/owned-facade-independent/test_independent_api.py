"""Independent actual consumer identities and optional-stack boundary checks."""

import importlib
import json
import subprocess
import sys

import numpy as np
import pytest


NAMES = (
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    "build_covariance_matrix",
    "calibration_covariance_blocks_agree_v1",
    "preserve_singular_covariance",
)


def test_both_real_consumer_globals_are_owner_objects_and_count_metadata_matches():
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
    assert len(facade.__all__) == 25 and len(set(facade.__all__)) == 25
    assert len(calibration.__all__) == 28
    for name in NAMES:
        assert getattr(facade, name) is getattr(owner, name)
        assert getattr(welfare, name) is getattr(owner, name)
    assert (
        legacy.load_foundry_calibration_report is report_owner.load_calibration_report
    )
    assert (
        facade.load_foundry_calibration_report is report_owner.load_calibration_report
    )
    assert not hasattr(calibration, "load_foundry_calibration_report")
    assert facade.CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1 == 1e-7
    assert facade.CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1 == 1e-10
    np.testing.assert_array_equal(
        facade.preserve_singular_covariance([[0.25, -0.25], [-0.25, 0.25]]) @ [1, 1],
        [0, 0],
    )


def test_optional_jax_refuses_required_lookup_but_preserves_base_facade_import():
    source = """
import importlib.abc, json, sys
class RefuseJax(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'jax' or fullname.startswith('jax.'):
            raise ModuleNotFoundError('independent unavailable optional JAX', name=fullname)
sys.meta_path.insert(0, RefuseJax())
from polisyos.foundry import uncertainty
assert uncertainty.PropagationDispatcher is None
assert 'polisyos.foundry.uncertainty.covariance' not in sys.modules
for name in ('preserve_singular_covariance','build_covariance_matrix'):
    try:
        getattr(uncertainty,name)
    except ImportError as exc:
        assert exc.name == 'jax' or exc.name.startswith('jax.')
    else:
        raise AssertionError('unavailable numeric owner silently admitted')
assert 'polisyos.foundry.uncertainty.covariance' not in sys.modules
print(json.dumps({'base_import':'PASS','required_numeric_lookup':'ImportError','authority':'not_established'}))
"""
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["required_numeric_lookup"] == "ImportError"


def test_present_numeric_proxy_preserves_values_but_fails_owner_identity(monkeypatch):
    facade = importlib.import_module("polisyos.foundry.uncertainty")
    owner = importlib.import_module("polisyos.foundry.uncertainty.covariance")
    native = owner.preserve_singular_covariance

    def proxy(value):
        return native(value)

    monkeypatch.setattr(facade, "preserve_singular_covariance", proxy)
    np.testing.assert_array_equal(
        facade.preserve_singular_covariance([[0.25]]), [[0.25]]
    )
    assert "preserve_singular_covariance" in facade.__all__
    with pytest.raises(AssertionError):
        assert facade.preserve_singular_covariance is native
