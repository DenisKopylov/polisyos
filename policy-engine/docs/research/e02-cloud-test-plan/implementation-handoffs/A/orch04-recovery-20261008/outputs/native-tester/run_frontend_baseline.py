import subprocess,pathlib,json,hashlib,datetime,time,os
repo=pathlib.Path('/workspace/ORCH04-C13');cwd=repo/'policy-engine';out=pathlib.Path('/workspace/ORCH04-evidence/native-tester/C13-G032-frontend-ui-parity-baseline-v2');out.mkdir(exist_ok=False)
g='0321633c0e6d9a87bccfbbe889a4998934c52dd3'
def git(*args):return subprocess.check_output(['git',*args],cwd=repo).decode().strip()
head=git('rev-parse','HEAD')
def tree(ref):
 rows={}
 for row in subprocess.check_output(['git','ls-tree','-r','-z',ref],cwd=repo).split(b'\0'):
  if row:
   meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split();rows[name.decode()]={'mode':mode,'kind':kind,'blob':blob}
 return rows
before=tree(head);base=tree(g)
changed=[p for p in sorted(base.keys()|before.keys()) if before.get(p)!=base.get(p)]
inputs=[p for p in sorted(before) if (p.startswith('policy-engine/') and '/implementation-handoffs/' not in p) or p.startswith('.githooks/') or p.startswith('.github/') or p in {'AGENTS.md','CONTRIBUTING.md','.gitattributes','.gitignore'}]
input_changed=[p for p in inputs if before[p]!=base.get(p)]
assert not input_changed,input_changed
m={'baseline':g,'actual_head':head,'actual_tree':git('rev-parse','HEAD^{tree}'),'parents':git('rev-list','--parents','-n','1','HEAD').split()[1:],'remote':git('remote','get-url','origin'),'branch':git('branch','--show-current'),'path':str(repo),'status_before':git('status','--porcelain'),'complete_head_delta_paths':changed,'input_selection':'all policy-engine tracked paths except any implementation-handoffs receipt subtree, plus root CI/hooks/AGENTS/CONTRIBUTING/Git configs','actual_frontend_runtime_lock_config_source_input_paths':inputs,'actual_input_changed_paths':input_changed,'actual_input_blobs':{p:before[p] for p in inputs}}
assert not m['status_before'],m['status_before']
(out/'input-equality.json').write_text(json.dumps(m,indent=2)+'\n')
origins={'node':subprocess.check_output(['which','node'],cwd=cwd).decode().strip(),'corepack':subprocess.check_output(['which','corepack'],cwd=cwd).decode().strip(),'node_version':subprocess.check_output(['node','--version'],cwd=cwd).decode().strip(),'pnpm_version':subprocess.check_output(['corepack','pnpm','--version'],cwd=cwd).decode().strip(),'dashboard_workspace_modules':{p.name:str(p.resolve()) for p in (cwd/'apps/runtime-dashboard/node_modules/@polisyos').iterdir()},'lock_sha256':hashlib.sha256((cwd/'pnpm-lock.yaml').read_bytes()).hexdigest(),'pnpm_metadata_sha256':hashlib.sha256((cwd/'node_modules/.modules.yaml').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
(out/'runner-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
cmd=json.loads(pathlib.Path('/workspace/ORCH04-evidence/c10/frontend-ui-parity.execution.json').read_text())['argv']
def snap():
 r={p:(pathlib.Path('/sys/fs/cgroup')/p).read_text() for p in ('memory.current','memory.max','memory.events','memory.stat','cpu.max','pids.current')};v=os.statvfs(cwd);r['filesystem']={'available_bytes':v.f_bavail*v.f_frsize,'available_inodes':v.f_favail};return r
r={'argv':cmd,'cwd':str(cwd),'source_head':head,'source_tree':m['actual_tree'],'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parent_pid':os.getpid(),'environment':{k:os.environ.get(k) for k in ('PATH','TMPDIR','NODE_USE_ENV_PROXY','COREPACK_HOME','npm_config_store_dir','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')},'cgroup_before':snap(),'origins':origins}
with (out/'stdout.txt').open('wb') as so,(out/'stderr.txt').open('wb') as se:
 t=time.monotonic();p=subprocess.Popen(cmd,cwd=cwd,stdout=so,stderr=se);r['pid']=p.pid;(out/'execution.json').write_text(json.dumps(r,indent=2)+'\n');_,status,usage=os.wait4(p.pid,0);r['exit_code']=os.waitstatus_to_exitcode(status);p.returncode=r['exit_code']
r.update(finish_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-t,max_rss_kib=usage.ru_maxrss,user_seconds=usage.ru_utime,system_seconds=usage.ru_stime,cgroup_after=snap(),git_head_after=git('rev-parse','HEAD'),git_status_after=git('status','--porcelain'))
(out/'execution.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ('pid','exit_code','wall_seconds','max_rss_kib','git_head_after','git_status_after')}));raise SystemExit(r['exit_code'])
