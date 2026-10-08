"""Independent hand HC1 diagnostic oracle; diagnostic nonrejection does not identify causality."""
import importlib,json,math,numpy as np
from polisyos.foundry.methods.causal import StaggeredDifferenceInDifferences
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
fixture=importlib.import_module("tests.unit.scientist.nodes.builtins.simulate.test_did_diagnostic_consumer")
data=fixture._panel(pre=3)
# Declared diagnostic compares untreated-period group means at t=0,1,2.
# Fixture's group difference is exactly [0,.5,-.3]. An intercept+slope fit
# has beta=-.15, residual=(-13/60,13/30,-13/60), Sxx=2 and HC1 factor3.
expected_slope=-3/20
residual=np.array([-13/60,13/30,-13/60])
expected_variance=3*float(np.sum(np.array([-1,0,1])**2*residual**2))/4
expected_se=math.sqrt(expected_variance)
expected_p=math.erfc(abs(expected_slope/expected_se)/math.sqrt(2))
output=StaggeredDifferenceInDifferences.pure_step(data,{"n_bootstrap":99,"__rng__":np.random.default_rng(13)})
report=CausalEffectReport.model_validate(output["report"]);diag=report.diagnostics[0]
assert math.isclose(diag.statistic,expected_slope,rel_tol=0,abs_tol=1e-12)
assert math.isclose(diag.details["slope_se"],expected_se,rel_tol=0,abs_tol=1e-12)
assert math.isclose(diag.p_value,expected_p,rel_tol=0,abs_tol=1e-12)
assert diag.passed is True and diag.details["identification_authority"] is False
owner._verify_selected_did_diagnostics(output,observational_data=data,staggered=True)
print(json.dumps({"source_sha":owner.__frozen_e02_source_sha__,"source_sha256":owner.__frozen_e02_source_sha256__,"independent_definition":"group-mean pretrend difference intercept+slope OLS; HC1 n/(n-k); Normal two-sided erfc","hand_expected":{"slope":expected_slope,"variance":expected_variance,"se":expected_se,"p":expected_p},"actual_typed_diagnostic":diag.model_dump(mode="json"),"consumer":"PASS","scope":"known finite synthetic diagnostic; no identification/evaluation authority"},indent=2),flush=True)
