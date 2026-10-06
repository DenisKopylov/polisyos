"""Bounded A/B/empty caller context through one reused actual worker and CAS."""
import asyncio
import contextvars
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading

from polisyos.common import async_tools
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine import retry
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState

root=Path(__file__).resolve().parents[7]
out=Path(sys.argv[1]).resolve()
out.mkdir(parents=True,exist_ok=True)
sha='e1871506fcebc47d6572891b323ddf1f2083a3c9'
paths=['policy-engine/src/polisyos/common/async_tools.py','policy-engine/src/polisyos/scientist/orchestration/engine/retry.py']
identity={}
for path in paths:
    raw=subprocess.check_output(['git','show',sha+':'+path],cwd=root)
    assert (root/path).read_bytes()==raw
    identity[path]=hashlib.sha256(raw).hexdigest()
scope=contextvars.ContextVar('runtime_context_consumer',default=None)
executor=async_tools._SharedExecutor(max_workers=1)
original_common,original_retry,original_fork=async_tools._get_shared_executor,retry.get_shared_executor,retry._can_use_forked_timeout_worker
async_tools._get_shared_executor=lambda:executor
retry.get_shared_executor=lambda:executor
retry._can_use_forked_timeout_worker=lambda:False
store=FileSystemCAS(out/'cas')
bundle=build_default_registry_bundle(store)
run=RunContext.start(store=store,registry_bundle=bundle.bundle_ref,run_id='R_context_consumer')
ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('runtime-context-consumer'))
rows=[]
class Node:
    spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.context_consumer@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='context consumer',description='Actual caller context artifact',capabilities=Capability.SCIENTIST_NODE),state_reads=[],state_writes=[])
    def execute(self,ctx,state):
        value=scope.get()
        payload={'scope':value,'thread_id':threading.get_ident()}
        ref=ctx.store.put_json(payload,PutOptions(kind='scientist.context_consumer',media_type='application/json'))
        scope.set('body-mutated')
        return NodeOutcome(status='ok',state=state,artifacts=[ref])
try:
    for route in ['sync-thread','async-thread','async-sync-unbounded']:
        for requested in ['A','B',None]:
            token=scope.set(requested)
            try:
                state=ExperimentState(run_id='R_context_consumer')
                kwargs=dict(retry_policy=retry.RetryPolicy(),timeout_s=None if route.endswith('unbounded') else 1.0,alias=route)
                outcome=retry.execute_with_retry_sync(Node(),ctx,state,**kwargs) if route=='sync-thread' else asyncio.run(retry.execute_with_retry_async(Node(),ctx,state,**kwargs))
                consumed=json.loads(store.get_bytes(outcome.artifacts[0]))
                row={'route':route,'requested':requested,'artifact_id':str(outcome.artifacts[0].artifact_id),'consumed':consumed,'caller_after':scope.get()}
                row['pass']=consumed['scope']==requested and scope.get()==requested
                rows.append(row)
            finally:scope.reset(token)
    worker_scope=executor.submit(scope.get).result(timeout=1)
    assert len({row['consumed']['thread_id'] for row in rows})==1
    assert worker_scope is None
    assert all(row['pass'] for row in rows)
finally:
    async_tools._get_shared_executor, retry.get_shared_executor, retry._can_use_forked_timeout_worker=original_common,original_retry,original_fork
    executor.shutdown(wait=True,cancel_futures=True)
packet={'schema':'policyos.e02.consumer_probe.v1','target_sha':sha,'producer_identity':identity,'command':sys.argv,'cwd':os.getcwd(),'environment':{'python':sys.executable,'version':sys.version,'PYTHONPATH':os.environ.get('PYTHONPATH'),'POLISYOS_METRICS_PORT':os.environ.get('POLISYOS_METRICS_PORT')},'input_closure':'Canonical Git source identity checked; actual reused one-worker fixture is deliberate reuse oracle, no process-wide quota; actual FileSystemCAS/RunContext/NodeSpec; admitted source tree e187 and installed environment receipt','rows':rows,'worker_scope_after':worker_scope,'outcome':'9PASS; exact caller scope persisted and consumed; no old body-mutated worker context','limitations':['Caller ContextVar propagation and typed artifact values, not a tenant authorization or grant proof.','Thread capability deliberately selected, no native macOS/fork distribution claim.']}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n')
print(json.dumps(packet,indent=2))
