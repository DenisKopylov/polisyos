"""Read-only native removal probes for the frozen economic dtype slice."""

import inspect
import sys
import textwrap

import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim import distributions
from polisyos.foundry.plugins.economics import state


probe = sys.argv[1]
if probe == "gini-zero-dtype":
    source = inspect.getsource(distributions.compute_gini_hard)
    source = source.replace("dtype=output_dtype", "dtype=jnp.float32")
    exec(compile(source, "<gini-zero-dtype-removal>", "exec"), distributions.__dict__)
    state.compute_gini_hard = distributions.compute_gini_hard
    selector = "gini and (float32-default or float64-x64)"
elif probe == "median-zero-dtype":
    source = textwrap.dedent(inspect.getsource(state.EconomicState._median_active))
    source = source.replace("@staticmethod\n", "", 1)
    source = source.replace("dtype=output_dtype", "dtype=jnp.float32")
    scope = {}
    exec(compile(source, "<median-zero-dtype-removal>", "exec"), state.__dict__, scope)
    state.EconomicState._median_active = staticmethod(scope["_median_active"])
    selector = "median and (float32-default or float64-x64)"
elif probe == "median-downcast":
    original = state.EconomicState._median_active

    def narrow_then_restore(values, active):
        return original(values.astype(jnp.float32), active).astype(jnp.result_type(values, jnp.inf))

    state.EconomicState._median_active = staticmethod(narrow_then_restore)
    selector = "float64_lower_median"
else:
    raise ValueError(probe)

print(f"Probe={probe}; unchanged module/class/export names; real native JAX branches.")
raise SystemExit(
    pytest.main(
        [
            "-o",
            "addopts=",
            "tests/unit/foundry/plugins/test_economics_dtype.py",
            "-v",
            "-ra",
            "--tb=short",
            "-k",
            selector,
        ]
    )
)
