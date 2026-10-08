from __future__ import annotations
import hashlib, importlib.metadata, json, os, pathlib, platform, subprocess, sys
from decimal import Decimal
import jax
import jax.numpy as jnp
import numpy as np
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import apply_patch_map, load_state_snapshot, put_state_snapshot
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax, TaxSubsidy, compute_tax
from polisyos.foundry._registry import _coerce_params, create_mechanism_from_spec, get_mechanism_descriptor
from polisyos.foundry.methods.catalog.mechanism.runtime import IncomeTaxMechanismMethod
from polisyos.ir.kernel.values import RateValue
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
ROOT=pathlib.Path('/workspace/e02-F-economics-20261006')
SHA='e84acb04fbe1fbebdfa5a54f87ff0fc72640a4ef'
OUT=pathlib.Path('/tmp/e02-F-continuation-20261006/economics/fiscal-precision')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA

def tensor(value):
    a=np.asarray(value)
    return {'dtype':str(a.dtype),'shape':list(a.shape),'value':a.tolist(),'weak_type':bool(getattr(value,'weak_type',False))}
def state_profile(state):
    return {k:tensor(v) for k,v in {'income':state.agents.income,'reported_income':state.agents.reported_income,'active':state.agents.active,'government_balance':state.government_balance}.items()}
def patches(patch):
    return {slot:[{field:tensor(value) for field,value in record.items()} for record in records] for slot,records in patch.items()}
def apply(state,patch):
    return apply_patch_map(state,patch,slot_registry=DEFAULT_SLOT_REGISTRY,merge_registry=DEFAULT_MERGE_RULE_REGISTRY,default_node_id='fiscal-precision-probe')
def fixture(dtype=None):
    s=GlobalState.empty(n_agents=10,n_firms=2)
    return s.replace(agents=s.agents.replace(income=jnp.ones(10,dtype=dtype)*1000.0,reported_income=jnp.ones(10,dtype=dtype)*1000.0),government_balance=jnp.asarray(0.0,dtype=dtype))
report={'source_sha':SHA,'tree_sha':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'scope':'readonly numerical trace, no code changes, no finding closure or P41 claim','environment':{'python':platform.python_version(),'jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'numpy':np.__version__,'equinox':importlib.metadata.version('equinox'),'jax_enable_x64_initial':jax.config.jax_enable_x64,'backend':jax.default_backend(),'JAX_ENABLE_X64':os.getenv('JAX_ENABLE_X64')},'profiles':[]}
for x64 in [False,True]:
    with jax.enable_x64(x64):
        s=fixture();m=IncomeTax(n_agents=10,rate=0.10)
        patch,key=m.emit_patches(s,jax.random.PRNGKey(0));next_state=apply(s,patch)
        jit_patch,jit_key=jax.jit(lambda st, k: m.emit_patches(st, k))(s,jax.random.PRNGKey(0))
        subsidy=TaxSubsidy(n_agents=10,rate=.50);subpatch,_=subsidy.emit_patches(next_state,jax.random.PRNGKey(1));last_state=apply(next_state,subpatch)
        expected_rate32=float(np.float32(.1));expected_balance=expected_rate32*10000.0
        report['profiles'].append({'jax_enable_x64':x64,'producer':{'type':'builtins.float','value':.1,'float_hex':float(.1).hex()},'materialized_rate':tensor(m.rate),'input_state':state_profile(s),'native_compute_tax':tensor(compute_tax(s,m.rate)),'patches':patches(patch),'jit_patches':patches(jit_patch),'next_state':state_profile(next_state),'subsidy_patches':patches(subpatch),'subsidy_next_state':state_profile(last_state),'key_unchanged':bool(np.array_equal(key,jax.random.PRNGKey(0))),'jit_key_unchanged':bool(np.array_equal(jit_key,jax.random.PRNGKey(0))),'exact_assertion_expected':1000.0,'exact_assertion_passes':float(next_state.government_balance)==1000.0,'rate32_promoted_mathematical_balance':expected_balance})
with jax.enable_x64(True):
    state=fixture()
    producers=[('python-float',.1),('decimal',Decimal('.10')),('ratio-ratevalue',RateValue(value=Decimal('.10'))),('percent-ratevalue',RateValue(value=Decimal('10'),base='percent')),('canonical-string','0.1'),('explicit-float64',jnp.asarray(.1,dtype=jnp.float64)),('explicit-float32',jnp.asarray(.1,dtype=jnp.float32))]
    report['registered_parameter_producers']=[]
    for name,value in producers:
        coerced=_coerce_params({'rate':value})['rate']
        row={'name':name,'input_type':type(value).__module__+'.'+type(value).__qualname__,'input_repr':str(value),'coerced_type':type(coerced).__module__+'.'+type(coerced).__qualname__,'coerced':tensor(coerced)}
        try:
            mech=create_mechanism_from_spec('income_tax',{'rate':value},10,2)
        except ValueError as exc:
            row['registry_refusal']={'type':type(exc).__qualname__,'message':str(exc)}
            mech=IncomeTax(rate=value,n_agents=10)
            row['direct_constructor_profile_only']=True
        patch,_=mech.emit_patches(state,jax.random.PRNGKey(0))
        row.update({'materialized_rate':tensor(mech.rate),'patches':patches(patch),'next_state':state_profile(apply(state,patch))})
        report['registered_parameter_producers'].append(row)
    catalog=IncomeTaxMechanismMethod.pure_step(state,{'rate':Decimal('.10'),'__seed__':0})
    report['actual_registered_catalog_result']=catalog
    report['registered_descriptor']={'class_path':get_mechanism_descriptor('income_tax').mechanism_class_path,'method_fqn':get_mechanism_descriptor('income_tax').method_fqn}
    # Numerical alternatives only. They are falsifiers, not ratified implementations.
    rate32=jnp.asarray(.1,dtype=jnp.float32)
    rate64_from32=rate32.astype(jnp.float64)
    direct64=jnp.asarray(.1,dtype=jnp.float64)
    state32=fixture(jnp.float32)
    precision_income64=jnp.asarray([2**24+1.],dtype=jnp.float64)
    report['nonfix_falsifiers']={
        'late_rate_upcast_preserves_error':tensor(jnp.sum(state.agents.reported_income*rate64_from32)),
        'native_float64_producer_without_early_quantization':tensor(jnp.sum(state.agents.reported_income*direct64)),
        'always64_rate_changes_float32_state_output_dtype':tensor(state32.agents.reported_income*direct64),
        'downcasting_tax_changes_valid_float64_values':{'full64':tensor(precision_income64*jnp.asarray(.5,dtype=jnp.float64)),'narrowed32':tensor((precision_income64*jnp.asarray(.5,dtype=jnp.float64)).astype(jnp.float32))},
        'explicit64_rate_below_quantization_boundary':{'input':tensor(jnp.asarray(.1000000001,dtype=jnp.float64)),'current_materialized':tensor(IncomeTax(rate=jnp.asarray(.1000000001,dtype=jnp.float64),n_agents=1).rate),'direct64_tax':tensor(jnp.asarray(1000.,dtype=jnp.float64)*jnp.asarray(.1000000001,dtype=jnp.float64))}}
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import CompileRequest, ExecuteRequest, FoundryExecConfig, FoundryInputBindings, FoundryInputBindingsRef, SimulationResult, StateSnapshotRef
    from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.execute.api import execute as execute_foundry
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.core.contracts.foundry import ProgramGraph
    store=FileSystemCAS(OUT/'cas-trace');bundle=build_default_registry_bundle(store)
    policy=TrinityBundle(problem_frame=ProblemFrame(problem_id='fiscal_precision',domain=ProblemDomain.FISCAL),policy_spec=PolicySpec(policy_id='fiscal_precision',interventions=[{'intervention_id':'tax','kind':'income_tax','target':{'kind':'predicate','field':'id','operator':'==','value':'all'},'schedule':{'start_step':0,'duration_steps':1},'params':{'rate':Decimal('.10')}}]),model_spec=ModelSpec(model_id='fiscal_precision',data_snapshot_ref='sha256:'+'0'*64,registry_bundle_ref=str(bundle.bundle_ref.artifact_id)))
    policy_ref=store.put_json(policy,PutOptions(kind='ir.trinity_bundle',media_type='application/json',schema=SchemaInfo(name='polisyos.ir.TrinityBundle',version=policy.schema_version)))
    compiled=compile_foundry(store,CompileRequest(input_kind='trinity',policy_ref=policy_ref,registry_bundle_ref=bundle.bundle_ref));assert compiled.ok
    graph=ProgramGraph.model_validate(from_canonical_bytes(store.get_bytes(compiled.program_graph_ref)))
    param_payloads=[{'node_id':node.node_id,'params_ref':str(node.params_ref.artifact_id),'payload':from_canonical_bytes(store.get_bytes(node.params_ref))} for node in graph.nodes if node.params_ref is not None]
    snapshot=put_state_snapshot(store,state=state,step=0);snapshot_ref=StateSnapshotRef(artifact_id=snapshot.artifact_id)
    data=store.put_json(DataSnapshot(data_ref=snapshot_ref),PutOptions(kind='fabric.data_snapshot',media_type='application/json'))
    binding=store.put_json(FoundryInputBindings(data_snapshot_ref=data,registry_bundle_ref=bundle.bundle_ref,rules=[],bound_state_snapshot_ref=snapshot_ref),PutOptions(kind='foundry.input_bindings',media_type='application/json'))
    request=ExecuteRequest(exec_plan_ref=compiled.exec_plan_ref,input_bindings_ref=FoundryInputBindingsRef(artifact_id=binding.artifact_id),registry_bundle_ref=bundle.bundle_ref,exec_config=FoundryExecConfig(seed=0))
    executed=execute_foundry(store,request);assert executed.ok
    reopened=FileSystemCAS(OUT/'cas-trace')
    result=SimulationResult.model_validate(from_canonical_bytes(reopened.get_bytes(executed.simulation_result_ref)))
    readback=load_state_snapshot(reopened,snapshot_ref=result.state_snapshot_ref)
    report['actual_spec_compile_cas_execute_fresh_reader']={'policy_ref':str(policy_ref.artifact_id),'source_policy_rate':str(policy.policy_spec.interventions[0].params['rate']),'compile_ok':compiled.ok,'lowered_parameter_payloads':param_payloads,'execute_ok':executed.ok,'simulation_result_ref':str(executed.simulation_result_ref.artifact_id),'fresh_state_snapshot_ref':str(result.state_snapshot_ref.artifact_id),'fresh_state':state_profile(readback),'exact1000_assertion_passes':float(readback.government_balance)==1000.0}
# Complete actual imported source denominator bound to exact Git.
source_rows=[]
for name,module in sorted(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if not name.startswith('polisyos') or not path:continue
    p=pathlib.Path(path).resolve()
    if p.suffix!='.py':continue
    rel=str(p.relative_to(ROOT));data=p.read_bytes();git_bytes=subprocess.check_output(['git','show',SHA+':'+rel],cwd=ROOT)
    assert data==git_bytes,rel
    source_rows.append({'module':name,'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
report['actual_imported_source_denominator']={'count':len(source_rows),'all_git_bytes_match':True,'rows':source_rows}
report['source_status_after']=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
assert not report['source_status_after']
report['all_trace_assertions_passed']=True
(OUT/'fiscal-precision-trace.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
