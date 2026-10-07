import json,sys
from datetime import UTC,datetime,timedelta
from pathlib import Path
import polisyos.runtime.http.services.control
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
path=Path(sys.argv[1]).resolve();assert not path.exists()
a=ControlPlaneStore(backend='sqlite',sqlite_path=path)
a.create_job(job_id='actual-upsert-job',kind='workflow_run',run_id='actual-upsert-run',pipeline_id=None,requested_execution_profile='dev',effective_execution_profile='dev',policy_flags={},capability_manifest_ref=None,payload_ref=None,submitted_by='fixture')
observed={}
def handler(job):
 assert a.current_execution_job_record().attempt==1
 a._execute('UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?',((datetime.now(UTC)-timedelta(seconds=1)).isoformat(),job.job_id))
 b=ControlPlaneStore(backend='sqlite',sqlite_path=path)
 current=b.lease_next_job(worker_id='new-owner-B',lease_seconds=300);assert current.attempt==2
 before=b.get_job(job.job_id)
 try: a.upsert_progress(job_id=job.job_id,progress={'phase':'stale-handler-overwrite'})
 except RuntimeError as exc: observed['exception']=type(exc).__name__
 after=b.get_job(job.job_id)
 observed.update(before={'attempt':before.attempt,'owner':before.lease_owner,'progress':before.progress},after={'attempt':after.attempt,'owner':after.lease_owner,'progress':after.progress},protected_progress_preserved=after.progress==before.progress)
worker=ControlWorker(store=a,handler=handler,worker_id='old-owner-A',lease_seconds=300)
assert worker.dispatch_once()
print(json.dumps(observed,indent=2),flush=True)
assert observed['protected_progress_preserved'],'bound stale handler rewrote current attempt progress through public upsert_progress'
