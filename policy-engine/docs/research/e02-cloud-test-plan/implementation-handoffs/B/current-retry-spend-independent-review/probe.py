"""Read-only real providers: on-time exceptions vs ordinary failed state writes."""
import asyncio, hashlib, importlib.util, json, logging, os, pathlib, subprocess, sys, time
from decimal import Decimal
ROOT=pathlib.Path('/workspace/e02-B-current-execution-state')
SHA='f04e3b80e910ad3cbbbf8262ed58bec69e3d57e8'
PATH='policy-engine/src/polisyos/scientist/orchestration/engine/retry.py'
raw=subprocess.check_output(['git','show',SHA+':'+PATH],cwd=ROOT)
name='e02_review_retry_f04'
spec=importlib.util.spec_from_loader(name,loader=None)
retry=importlib.util.module_from_spec(spec)
sys.modules[name]=retry
exec(compile(raw,SHA+':'+PATH,'exec'),retry.__dict__)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome,NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
out=ROOT/'_build/current-execution-state/failed-spend-f04'
out.mkdir(parents=True,exist_ok=True)
class Provider:
    spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.known_spend@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='known spend',description='Known on-time failed spend',capabilities=Capability.SCIENTIST_NODE),state_reads=['budgets','params'],state_writes=['budgets','params'])
    def __init__(self,log):self.log=log
    def body(self,state):
        prior=self.log.read_text().splitlines() if self.log.exists() else []
        ordinal=len(prior)+1
        observed={'ordinal':ordinal,'pid':os.getpid(),'spend_before':str(state.budgets['llm_spent_usd']),'dirty_before':state.params.get('failed_dirty'),'monotonic':time.monotonic()}
        state.budgets['llm_spent_usd']+=Decimal(2 if ordinal==1 else 1)
        observed['spend_after']=str(state.budgets['llm_spent_usd'])
        with self.log.open('a') as f:f.write(json.dumps(observed)+'\n')
        if ordinal==1:
            state.params['failed_dirty']='must not publish'
            raise TimeoutError('provider completed on-time with known two-dollar state spend')
        state.params['success']=True
        return NodeOutcome(status='ok',state=state)
    def execute(self,ctx,state):return self.body(state)
class AsyncProvider(Provider):
    async def execute_async(self,ctx,state):
        await asyncio.sleep(0)
        return self.body(state)
results=[]
original=retry._can_use_forked_timeout_worker
for route,api,force_thread,finite,async_node in [('sync-direct','sync',False,False,False),('sync-fork','sync',False,True,False),('sync-thread','sync',True,True,False),('async-fork','async',False,True,False),('async-thread','async',True,True,False),('async-provider','async',False,True,True),('async-provider-unbounded','async',False,False,True)]:
    directory=out/route;directory.mkdir(exist_ok=True)
    store=FileSystemCAS(directory/'cas')
    bundle=build_default_registry_bundle(store)
    run_id='R_'+route.replace('-','_')
    run=RunContext.start(store=store,registry_bundle=bundle.bundle_ref,run_id=run_id)
    ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('failed-spend-review'))
    state=ExperimentState(run_id=run_id,budgets={'llm_spent_usd':Decimal(5)})
    node=(AsyncProvider if async_node else Provider)(directory/'attempts.jsonl')
    retry._can_use_forked_timeout_worker=(lambda:False) if force_thread else original
    kwargs=dict(retry_policy=retry.RetryPolicy(max_retries=1,backoff_base_s=.1,jitter='none'),timeout_s=2.0 if finite else None,deadline_monotonic=time.monotonic()+2 if finite else None,alias=route)
    t=time.monotonic()
    result=retry.execute_with_retry_sync(node,ctx,state,**kwargs) if api=='sync' else asyncio.run(retry.execute_with_retry_async(node,ctx,state,**kwargs))
    elapsed=time.monotonic()-t
    attempts=[json.loads(line) for line in node.log.read_text().splitlines()]
    results.append({'route':route,'actual_fork_capability':original(),'force_thread_platform_branch':force_thread,'physical_attempts':attempts,'result_status':result.status,'result_spend':str(result.state.budgets['llm_spent_usd']),'expected_known_spend':'8','known_failed_spend_preserved':result.state.budgets['llm_spent_usd']==Decimal(8),'ordinary_failed_write_absent':'failed_dirty' not in result.state.params,'result_params':result.state.params,'input_spend_after':str(state.budgets['llm_spent_usd']),'elapsed_seconds':elapsed,'on_time':elapsed<2})
retry._can_use_forked_timeout_worker=original
packet={'schema':'policyos.e02.independent_probe.v1','source_sha':SHA,'retry_path':PATH,'retry_sha256':hashlib.sha256(raw).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'source_mode':'Git object exec; retry-only immutable candidate, other imports own tracked source; no candidate checkout claim','environment':{'python':sys.executable,'version':sys.version,'PYTHONPATH':os.environ.get('PYTHONPATH'),'POLISYOS_METRICS_PORT':os.environ.get('POLISYOS_METRICS_PORT'),'clock_info':str(time.get_clock_info('monotonic'))},'input_contract':'Known state-budget llm_spent_usd 5 + failed2 + success1 =8, first provider raises retryable TimeoutError on time; ordinary failed params excluded','results':results,'vendor_financial_authority_claimed':False}
print(json.dumps(packet,indent=2))
(out/'review.json').write_text(json.dumps(packet,indent=2)+'\n')
