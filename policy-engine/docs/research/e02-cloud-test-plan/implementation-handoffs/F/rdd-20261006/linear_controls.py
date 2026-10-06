"""Actual-method linear DGP control independent of quadratic correction fixtures."""
import json
import sys

import numpy as np

from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.ir.analytics.causal import EstimationStatus

x = np.linspace(-1, 1, 800)
y = 1 + .4*x + 3*(x >= 0)
cases = []
for kernel in ["triangular", "uniform", "epanechnikov"]:
    for order in [1, 2]:
        params = dict(bandwidth=.45, bias_bandwidth=.65, polynomial_order=order,
                      kernel=kernel, bias_correction=True, manipulation_test=False)
        data = dict(running_variable=x, outcome=y, cutoff=0.)
        corrected = RegressionDiscontinuity.pure_step(data, params)["report"]
        ordinary = RegressionDiscontinuity.pure_step(data, {**params, "bias_correction":False})["report"]
        assert corrected.status is ordinary.status is EstimationStatus.SUCCESS
        assert abs(corrected.point_estimate - 3) < 1e-10
        assert abs(ordinary.point_estimate - 3) < 1e-10
        cases.append(dict(params=params, corrected_point=corrected.point_estimate,
                          corrected_se=corrected.standard_error,
                          conventional_point=ordinary.point_estimate,
                          conventional_se=ordinary.standard_error, outcome="PASS"))
print(json.dumps(dict(outcome="PASS", source_sha="cdede69e8c0713aac4fd6c8b393ae34837c3a594",
                     python=sys.version, executable=sys.executable,
                     scope="Native linear sharp control tau3, no leading curvature bias",
                     input_rows=800, cases=cases,
                     prior_harness_errors=["first inline harness omitted required cutoff; Pydantic rejected before estimator",
                                           "second inline harness treated decorated pure_step dict as report; corrected by reading actual report slot"]), indent=2))
