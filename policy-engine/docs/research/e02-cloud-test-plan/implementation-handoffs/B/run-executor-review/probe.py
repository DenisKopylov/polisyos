import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

from polisyos.common import async_tools

class ObservedLock:
    def __init__(self, lock, name, before=None, after=None):
        self.lock, self.name, self.before, self.after = lock,name,before,after
        self.guard=threading.Lock(); self.owner=None; self.waiting=set();self.depth=0
    def acquire(self, *args, **kwargs):
        who=threading.current_thread().name
        with self.guard:self.waiting.add(who)
        if self.before:self.before(who)
        acquired=self.lock.acquire(*args,**kwargs)
        with self.guard:
            self.waiting.discard(who)
            if acquired:self.owner=who;self.depth+=1
        if acquired and self.after:self.after(who)
        return acquired
    def release(self):
        with self.guard:
            self.depth-=1
            if self.depth==0:self.owner=None
        self.lock.release()
    def __enter__(self):self.acquire();return self
    def __exit__(self,*args):self.release()
    def snapshot(self):
        with self.guard:return {'owner':self.owner,'waiting':sorted(self.waiting),'depth':self.depth}

def identity():
    p=Path(async_tools.__file__)
    return {'module':str(p),'module_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'python':sys.version,'platform':platform.platform(),'pid':os.getpid()}

def shutdown_probe():
    executor=async_tools._SharedExecutor(max_workers=1,thread_name_prefix='review-blocker')
    release=threading.Event();started=threading.Event()
    def blocker():started.set();release.wait(3);return 'running'
    active=executor.submit(blocker);assert started.wait(1)
    queued=executor.submit(lambda:'queued-must-cancel')
    shutdown_owned=threading.Event();allow_shutdown=threading.Event()
    submit_waits_shutdown=threading.Event();callback_touches_admission=threading.Event()
    def shutdown_after(who):
        if who=='shutdown':shutdown_owned.set();assert allow_shutdown.wait(1)
    def shutdown_before(who):
        if who=='submitter':submit_waits_shutdown.set()
    def admission_before(who):
        if who=='shutdown':callback_touches_admission.set()
    executor._admission_lock=ObservedLock(executor._admission_lock,'admission',before=admission_before)
    executor._shutdown_lock=ObservedLock(executor._shutdown_lock,'shutdown',before=shutdown_before,after=shutdown_after)
    submitted=[];shutdown_finished=threading.Event();submit_finished=threading.Event()
    def shutdown():
        executor.shutdown(wait=False,cancel_futures=True);shutdown_finished.set()
    def submitter():
        try:executor.submit(lambda:'rejected-after-shutdown')
        except BaseException as exc:submitted.append(type(exc).__name__+': '+str(exc))
        finally:submit_finished.set()
    stopping=threading.Thread(target=shutdown,name='shutdown',daemon=True)
    submitting=threading.Thread(target=submitter,name='submitter',daemon=True)
    stopping.start();assert shutdown_owned.wait(1)
    submitting.start();assert submit_waits_shutdown.wait(1)
    admission_before_cancel=executor._admission_lock.snapshot()
    allow_shutdown.set();assert callback_touches_admission.wait(1)
    stopping.join(0.05);submitting.join(0.05)
    locks={'admission':executor._admission_lock.snapshot(),'shutdown':executor._shutdown_lock.snapshot()}
    cycle=(locks['admission']['owner']=='submitter' and 'shutdown' in locks['admission']['waiting']
           and locks['shutdown']['owner']=='shutdown' and 'submitter' in locks['shutdown']['waiting'])
    record={'case':'shutdown-submit','identity':identity(),'admission_before_cancel':admission_before_cancel,
            'locks':locks,'lock_cycle':cycle,'shutdown_finished':shutdown_finished.is_set(),
            'submit_finished':submit_finished.is_set(),'submit_result':submitted,'queued_future_cancelled':queued.cancelled(),
            'outstanding_before_worker_release':executor._outstanding_jobs}
    if cycle:
        record['outcome']='FAIL_LOCK_ORDER_CYCLE';print(json.dumps(record),flush=True);os._exit(73)
    assert shutdown_finished.is_set() and submit_finished.is_set()
    release.set();executor.shutdown(wait=True,cancel_futures=True)
    record['active_result']=active.result();record['final_outstanding']=executor._outstanding_jobs
    record['outcome']='PASS_NO_CYCLE';print(json.dumps(record),flush=True)

def callback_probe(count,output):
    executor=async_tools._SharedExecutor(max_workers=4,thread_name_prefix='review-callback')
    ready=threading.Barrier(count+1);body_release=threading.Event()
    callbacks_ready=threading.Barrier(count+1);submit_release=threading.Event()
    all_submitted=threading.Barrier(count+1);wait_release=threading.Event()
    all_waited=threading.Barrier(count+1);callback_release=threading.Event()
    records=[];guard=threading.Lock();inner_started=[]
    def outer(i):ready.wait(1);assert body_release.wait(1);return i
    def inner(i):
        with guard:
            inner_started.append(i)
            with output.open('a') as file:file.write(json.dumps({'inner':i,'worker':threading.get_ident()})+'\n')
        return 42
    def callback(i,future):
        row={'index':i,'worker_identity':getattr(executor._worker_identity,'active',False),
             'worker_id':threading.get_ident(),'outer_future_done':future.done()}
        callbacks_ready.wait(1);assert submit_release.wait(1)
        nested=None
        try:
            nested=executor.submit(inner,i);row['submit']='accepted'
        except RuntimeError as exc:row['submit']='rejected';row['error']=str(exc)
        all_submitted.wait(1);assert wait_release.wait(1)
        if nested is not None:
            try:row['result']=nested.result(timeout=0.1);row['wait']='completed'
            except concurrent.futures.TimeoutError:
                row['wait']='timed_out_with_callbacks_held';row['queued_cancelled']=nested.cancel()
        with guard:records.append(row)
        all_waited.wait(1);assert callback_release.wait(1)
    try:
        futures=[executor.submit(outer,i) for i in range(count)]
        for i,future in enumerate(futures):future.add_done_callback(lambda f,i=i:callback(i,f))
        ready.wait(1);body_release.set();callbacks_ready.wait(1)
        before=executor._outstanding_jobs
        assert all(f.done() for f in futures)
        submit_release.set();all_submitted.wait(1);wait_release.set();all_waited.wait(1)
        with guard:rows=sorted(records,key=lambda r:r['index']);started=list(inner_started)
        record={'case':'callback-saturated' if count==4 else 'callback-spare-worker','identity':identity(),
                'physical_callback_workers':count,'executor_workers':4,'outstanding_at_callback_barrier':before,
                'all_outer_futures_done':True,'rows':rows,'inner_started_while_callbacks_held':started,
                'actual_inner_file':str(output),'file_content':output.read_text() if output.exists() else ''}
        callback_release.set();executor.shutdown(wait=True)
        record['final_outstanding']=executor._outstanding_jobs
        if count==4:
            record['counterexample']=before==0 and len(rows)==4 and all(r.get('submit')=='accepted' and r.get('wait')=='timed_out_with_callbacks_held' for r in rows) and started==[]
            record['outcome']='FAIL_CALLBACK_CAPACITY_PROXY' if record['counterexample'] else 'OTHER'
        else:
            record['positive_control']=before==0 and len(rows)==3 and all(r.get('result')==42 for r in rows) and sorted(started)==[0,1,2]
            record['outcome']='PASS_SPARE_WORKER' if record['positive_control'] else 'FAIL'
        print(json.dumps(record),flush=True)
    finally:
        body_release.set();submit_release.set();wait_release.set();callback_release.set()
        executor.shutdown(wait=True,cancel_futures=True)

parser=argparse.ArgumentParser();parser.add_argument('--child');parser.add_argument('--output');parser.add_argument('--target');args=parser.parse_args()
if args.child:
    if args.child=='shutdown-submit':shutdown_probe()
    else:callback_probe(4 if args.child=='callback-saturated' else 3,Path(args.output))
else:
    folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    assert not (folder/'receipt.json').exists(),'fresh evidence directory required'
    results=[]
    for case in ['shutdown-submit','callback-saturated','callback-spare-worker']:
        command=[sys.executable,'-u',__file__,'--child',case,'--output',str(folder/(case+'.inner'))]
        start=time.monotonic();child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        try:stdout,_=child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,9);stdout,_=child.communicate();raise AssertionError(case+' external watchdog: '+stdout)
        record={'case':case,'argv':command,'exit_code':child.returncode,'wall_s':time.monotonic()-start,'stdout':stdout}
        results.append(record);print(json.dumps(record),flush=True)
    receipt={'schema':'policyos.e02.executor_independent_probe.v1','target_sha':args.target,'identity':identity(),
             'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cwd':os.getcwd(),'PYTHONPATH':os.environ.get('PYTHONPATH'),
             'cases':results,'limitations':'Shutdown gate wraps real lock objects without production function replacement; callback guard capability remains bounded when user done callbacks block all workers. Deliberate local fixture saturation is the tested property.'}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
