import argparse,datetime,hashlib,importlib.metadata,json,os,pathlib,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cwd',required=True);p.add_argument('--manifest',required=True);p.add_argument('cmd',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.cmd[1:] if a.cmd[:1]==['--'] else a.cmd
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False);cwd=pathlib.Path(a.cwd);manifest=json.loads(pathlib.Path(a.manifest).read_text());root=cwd.parent

def snap():
 d={}
 for n in ('memory.current','memory.peak','memory.max','memory.events','memory.stat','pids.current','pids.max','cpu.max'):
  q=pathlib.Path('/sys/fs/cgroup')/n
  if q.exists():d[n]=q.read_text()
 fs=os.statvfs(cwd);d['filesystem']={'available_bytes':fs.f_bavail*fs.f_frsize,'available_inodes':fs.f_favail};return d

def source_delta():
 d=[]
 for x in manifest['tracked_files']:
  q=root/x['path'];payload=str(q.readlink()).encode() if x['mode']=='120000' else q.read_bytes()
  sha=hashlib.sha256(payload).hexdigest()
  if sha!=x['sha256']:d.append({'path':x['path'],'before':x['sha256'],'after':sha})
 return d

env=dict(os.environ);env['PYTHONPATH']=str(cwd/'src')+os.pathsep+str(cwd)+os.pathsep+env.get('PYTHONPATH','');env['TMPDIR']=str(out/'tmp');pathlib.Path(env['TMPDIR']).mkdir()
r={'schema':'orch04.native_execution.v1','argv':cmd,'cwd':str(cwd),'source_commit':manifest['commit'],'source_tree':manifest['tree'],'source_manifest_path':a.manifest,'source_manifest_sha256':hashlib.sha256(pathlib.Path(a.manifest).read_bytes()).hexdigest(),'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parent_pid':os.getpid(),'cgroup_before':snap(),'source_delta_before':source_delta(),'selected_environment':{k:env.get(k) for k in ('PYTHONPATH','TMPDIR','JAX_PLATFORMS','JAX_PLATFORM_NAME','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','XLA_FLAGS')}}
r['external_file_inputs']=[{'path':x,'sha256':hashlib.sha256(pathlib.Path(x).read_bytes()).hexdigest()} for x in [__file__,*cmd[1:]] if pathlib.Path(x).is_file()];origin_cmd=[cmd[0],'-c',"import importlib.util,importlib.metadata,json,sys;print(json.dumps({'executable':sys.executable,'version':sys.version,'origins':{n:(None if (s:=importlib.util.find_spec(n)) is None else s.origin) for n in ['polisyos','pytest','numpy','scipy','torch','gpytorch','botorch']},'distributions':sorted([(d.metadata['Name'],d.version) for d in importlib.metadata.distributions()])},indent=2))"]
origin=subprocess.run(origin_cmd,cwd=cwd,env=env,capture_output=True);(out/'environment-origins.stdout.txt').write_bytes(origin.stdout);(out/'environment-origins.stderr.txt').write_bytes(origin.stderr);r['origins_exit_code']=origin.returncode
with (out/'stdout.txt').open('wb') as so,(out/'stderr.txt').open('wb') as se:
 t=time.monotonic();proc=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=so,stderr=se);r['pid']=proc.pid;(out/'execution.json').write_text(json.dumps(r,indent=2)+'\n');_,status,usage=os.wait4(proc.pid,0);r['exit_code']=os.waitstatus_to_exitcode(status);proc.returncode=r['exit_code']
r.update(wall_seconds=time.monotonic()-t,finish_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),max_rss_kib=usage.ru_maxrss,user_seconds=usage.ru_utime,system_seconds=usage.ru_stime,cgroup_after=snap(),source_delta_after=source_delta())
(out/'execution.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ('argv','pid','exit_code','wall_seconds','max_rss_kib','source_delta_before','source_delta_after')}));raise SystemExit(r['exit_code'] if r['exit_code']>=0 else 128-r['exit_code'])
