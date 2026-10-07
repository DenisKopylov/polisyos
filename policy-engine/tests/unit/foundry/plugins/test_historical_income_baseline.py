"""Original LA035 relocation preserves the native normalized-income baseline."""

from __future__ import annotations

import os
import subprocess
import sys
from fractions import Fraction

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods._internal.loss import policy_loss_fn as internal_alias
from polisyos.foundry.methods.loss import policy_loss_fn as public_alias
from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss
from polisyos.foundry.runtime.numeric import finite_loss_or_inf


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "income,balance,minimum,expected",
    [
        ([0], 0, -1000, Fraction(0)),
        ([2], 0, -1000, Fraction(-1)),
        ([-2], 0, -1000, Fraction(1)),
        ([1, -3, 0, 2, -1, 4, 0], 0, -1000, Fraction(-3, 11)),
        ([1, 2, 3, 4, 5, 6, 7], 0, -1000, Fraction(-1)),
        ([100, 200, 300, 400, 500, 600, 700], 0, -1000, Fraction(-1)),
        ([1, 2, 3], -2000, -1000, Fraction(9)),
        ([0, 0], -2, 0, Fraction(40)),
        ([0, 0], 10, 20, Fraction(5, 2)),
    ],
)
def test_original_sign_scale_population_and_budget_oracles(
    compiled, income, balance, minimum, expected
):
    state = GlobalState.empty(n_agents=len(income), n_firms=1)
    state = state.replace(
        agents=state.agents.replace(income=jnp.asarray(income, dtype=jnp.float32)),
        government_balance=jnp.asarray(balance, dtype=jnp.float32),
    )
    evaluate = jax.jit(normalized_income_budget_loss) if compiled else normalized_income_budget_loss
    actual = evaluate(state, min_balance=minimum)
    assert actual.dtype == jnp.float32
    np.testing.assert_allclose(actual, float(expected), rtol=0, atol=1e-6)


def test_historical_population_includes_supplied_inactive_entries():
    # The original baseline has no active-mask selection; relocation must not
    # introduce a different target population under the same public identity.
    state = GlobalState.empty(n_agents=3, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, False, True]),
            income=jnp.asarray([1.0, -6.0, 2.0], dtype=jnp.float32),
        ),
        government_balance=jnp.asarray(0.0, dtype=jnp.float32),
    )
    assert float(jax.jit(normalized_income_budget_loss)(state)) == pytest.approx(1 / 3)


def test_aliases_and_real_public_numeric_guard_keep_their_identity():
    from polisyos.foundry.execute._internal.numeric import finite_loss_or_inf as actual_guard

    assert internal_alias is public_alias is normalized_income_budget_loss
    assert finite_loss_or_inf is actual_guard
    np.testing.assert_array_equal(
        jax.jit(finite_loss_or_inf)(jnp.asarray([2.0, jnp.nan], dtype=jnp.float32)),
        [jnp.inf, jnp.inf],
    )
    # Overflow in the computed budget penalty reaches the real guard even
    # though all three source inputs are finite.
    state = GlobalState.empty(n_agents=1, n_firms=1)
    state = state.replace(government_balance=jnp.asarray(-3e38, dtype=jnp.float32))
    assert np.isposinf(jax.jit(public_alias)(state, min_balance=0.0))
    state = GlobalState.empty(n_agents=3, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(income=jnp.full((3,), 3e38, dtype=jnp.float32)),
        government_balance=jnp.asarray(0.0, dtype=jnp.float32),
    )
    assert np.isposinf(jax.jit(public_alias)(state))


def test_fresh_economic_owner_import_has_no_registration_io_or_execution_side_effects():
    code = """
import builtins, pathlib, socket, subprocess, threading
def denied(*args, **kwargs):
    raise AssertionError('economic baseline import performed runtime side effect')
original_open = builtins.open
def guarded_open(file, mode='r', *args, **kwargs):
    if any(flag in mode for flag in 'wax+'):
        denied(file, mode)
    return original_open(file, mode, *args, **kwargs)
builtins.open = guarded_open
pathlib.Path.write_text = denied
pathlib.Path.write_bytes = denied
socket.create_connection = denied
subprocess.Popen = denied
threading.Thread.start = denied
from polisyos.foundry.plugins.core import PluginRegistry
before = tuple(PluginRegistry().list_plugins())
from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss
from polisyos.foundry.methods.loss import policy_loss_fn
assert policy_loss_fn is normalized_income_budget_loss
assert tuple(PluginRegistry().list_plugins()) == before
print('fresh import: identity, no registration, no guarded IO/process/thread start')
"""
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-c", code], env=environment, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fresh import: identity" in result.stdout
