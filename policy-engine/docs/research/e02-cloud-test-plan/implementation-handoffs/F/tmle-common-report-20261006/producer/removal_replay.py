from pathlib import Path
import ast,hashlib,inspect,json,sys,textwrap
import pytest
from polisyos.foundry.methods.catalog.causal import treatment_effects as owner
from polisyos.ir.analytics.causal import EstimationStatus
mode=sys.argv[1];out=Path(__file__).parent;cls=owner.TMLEEstimator
markers={"class_fqn":cls.__module__+"."+cls.__qualname__,"method_fqn":cls.signature.fqn,"signature_digest":cls.signature.stable_digest(),"output_slots":sorted(s.name for s in cls.signature.output_slots)}
if mode=="adjustment_basis":
 original=cls.pure_step;tree=ast.parse(textwrap.dedent(inspect.getsource(original)));node=tree.body[0];node.decorator_list=[]
 branch=node.body[1] if isinstance(node.body[0],ast.Expr) else node.body[0]
 assert isinstance(branch,ast.If)
 count=sum(isinstance(item,ast.If) for item in branch.body);assert count==1
 branch.body=[item for item in branch.body if not isinstance(item,ast.If)]
 ns={};exec(compile(ast.fix_missing_locations(tree),"<removed-only-typed-confounder-basis>","exec"),original.__globals__,ns)
 removed=ns["pure_step"];removed.__qualname__=original.__qualname__;removed.__module__=original.__module__;cls.pure_step=staticmethod(removed)
 selector="test_typed_confounders_preserve_complete_native_adjustment_basis"
else:
 original=cls.report_from_result
 def removed(**kwargs):
  report=original(**kwargs)
  if mode=="native_interval" and report.confidence_interval is not None:
   l,u=report.confidence_interval;return report.model_copy(update={"confidence_interval":(l-0.5,u+0.5)})
  if mode=="limited_disposition" and report.status is not EstimationStatus.SUCCESS:
   return report.model_copy(update={"status":EstimationStatus.SUCCESS,"point_estimate":kwargs["result"]["ate"],"standard_error":kwargs["result"]["standard_error"],"confidence_interval":(-1.0,1.0),"confidence_level":0.95,"inference_method":"asymptotic"})
  return report
 removed.__qualname__=original.__qualname__;removed.__module__=original.__module__;cls.report_from_result=staticmethod(removed)
 selector="test_real_configured_method_job_projects_exact_native_eif_and_cas_reader" if mode=="native_interval" else "test_actual_limited_profiles_preserve_result_and_emit_point_free_report"
after={"class_fqn":cls.__module__+"."+cls.__qualname__,"method_fqn":cls.signature.fqn,"signature_digest":cls.signature.stable_digest(),"output_slots":sorted(s.name for s in cls.signature.output_slots)};assert markers==after
print(json.dumps({"control":mode,"markers_retained":markers,"source_owner_path":owner.__file__,"source_sha256":hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest(),"canonical_native_fit_unchanged":True}),flush=True)
args=["tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py::"+selector,"-o","addopts=","-o",f"cache_dir={out/'removal-cache'/mode}","-q","-ra","--basetemp="+str(out/"removal-tmp"/mode),"--junitxml="+str(out/("removal-"+mode+".junit.xml"))]
if mode=="limited_disposition":args.extend(["-k","unsupported_inference_profile"])
(out/"removal-tmp").mkdir(exist_ok=True)
raise SystemExit(pytest.main(args))
