"""Focused invalid/not-testable diagnostic dispositions at the genuine native consumer."""
import importlib,json,numpy as np
from polisyos.foundry.methods.causal import StandardDifferenceInDifferences,StaggeredDifferenceInDifferences
from polisyos.ir.analytics.causal import CausalEffectReport,EstimationStatus
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
fixture=importlib.import_module("tests.unit.scientist.nodes.builtins.simulate.test_did_diagnostic_consumer")
records=[]
for method,pre in [(StandardDifferenceInDifferences,0),(StandardDifferenceInDifferences,2),(StaggeredDifferenceInDifferences,2),(StaggeredDifferenceInDifferences,3)]:
    data=fixture._panel(pre=pre)
    params={"n_bootstrap":99,"__rng__":np.random.default_rng(13)} if method is StaggeredDifferenceInDifferences else {}
    output=method.pure_step(data,params);report=CausalEffectReport.model_validate(output["report"])
    owner._verify_selected_did_diagnostics(output,observational_data=data,staggered=method is StaggeredDifferenceInDifferences)
    if pre==0:
        assert report.status is EstimationStatus.INPUT_INVALID and not report.diagnostics
    elif pre==2:
        assert report.diagnostics[0].details["status"]=="not_testable"
        assert report.diagnostics[0].passed is False
    else:
        assert report.method_params["diagnostic_contract"]["identification_authority"] is False
    records.append({"method":method.signature.fqn,"time_treatment":pre,"status":report.status.value,"diagnostics":[d.model_dump(mode="json") for d in report.diagnostics],"consumer":"PASS","identification_authority":"not established"})
print(json.dumps({"source_sha":owner.__frozen_e02_source_sha__,"source_sha256":owner.__frozen_e02_source_sha256__,"cases":records},indent=2),flush=True)
