from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
cfg=json.loads(Path(sys.argv[1]).read_text());scratch=Path(cfg['scratch']);rows=[]
for kind,path in cfg['archives'].items():
 if kind=='sdist':continue
 with zipfile.ZipFile(path) as z:
  for name in z.namelist():
   if name.endswith('.dist-info/WHEEL'):
    raw=z.read(name);rows.append({'archive':kind,'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'complete_contents':raw.decode()})
proof={'source_sha':cfg['source_sha'],'source_tree':cfg['source_tree'],'wheel_backend_metadata':rows,'explicit_build_interpreter':cfg['app_python'],'worker_python_configured':cfg['worker_python'],'sites':{},'scope':'Distribution setup/startup profile only; selected numerical/native consumer assertions separately executed and recorded.'}
program="import importlib.metadata as m,importlib.util as u,json,platform,sys;print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'prefix':sys.prefix,'isolated':sys.flags.isolated,'sys_path':sys.path,'backend_presence':{n:{'find_spec_present':u.find_spec(n) is not None,'installed_version':m.version(n) if any(d.metadata['Name'].lower()==n for d in m.distributions()) else None} for n in ('dowhy','econml')}}))"
for kind,p in cfg['installed_pythons'].items():
 site=Path(cfg['sites'][kind]);cwd=scratch/(kind+'-consumer');argv=[p,'-I','-c',program]
 r=subprocess.run(argv,cwd=cwd,capture_output=True);record={'argv':argv,'cwd':str(cwd),'exit_code':r.returncode}
 for stream,data in [('stdout',r.stdout),('stderr',r.stderr)]:
  f=scratch/(kind+'-startup-profile.'+stream+'.txt');assert not f.exists();f.write_bytes(data);record[stream]={'path':str(f),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 assert r.returncode==0,r.stderr
 record['actual_startup']=json.loads(r.stdout);assert record['actual_startup']['isolated']==1
 assert not any(v and Path(v).is_relative_to(Path(cfg['source_root'])) for v in record['actual_startup']['sys_path'])
 record['pth_files']=[]
 for base,role in [(site,'own installed site'),(Path(cfg['dependency_site']),'readonly dependency directory, appended literally; its pth files are not recursively processed')]:
  for f in sorted(base.glob('*.pth')):
   raw=f.read_bytes();record['pth_files'].append({'role':role,'path':str(f),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'complete_contents':raw.decode()})
 proof['sites'][kind]=record
p=scratch/'setup-profile.json';assert not p.exists();p.write_text(json.dumps(proof,indent=2)+'\n');raw=p.read_bytes();print(json.dumps({'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'startup_profiles':{k:v['actual_startup']['backend_presence'] for k,v in proof['sites'].items()},'scientific_backend_assertion':'UNRUN in this startup-only receipt; DoWhy selected external worker proof follows native tests.'}))
