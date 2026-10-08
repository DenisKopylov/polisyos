import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
prefix=Path(sys.argv[1]);argv=sys.argv[2:];start=datetime.datetime.now(datetime.UTC).isoformat();ts=time.monotonic()
metadata={'argv':argv,'cwd':os.getcwd(),'started_utc':start,'python_executable':sys.executable,'profile_env':{k:os.environ.get(k) for k in ['PYTHONPATH','NODE_USE_ENV_PROXY','COREPACK_HOME','npm_config_store_dir']}}
with prefix.with_suffix('.stdout').open('wb') as out,prefix.with_suffix('.stderr').open('wb') as err:
 p=subprocess.Popen(argv,stdout=out,stderr=err);metadata['pid']=p.pid;prefix.with_suffix('.execution.json').write_text(json.dumps(metadata,indent=2)+'\n');rc=p.wait()
metadata.update({'finished_utc':datetime.datetime.now(datetime.UTC).isoformat(),'elapsed_seconds':time.monotonic()-ts,'returncode':rc,'outputs':{suffix:{'bytes':prefix.with_suffix(suffix).stat().st_size,'sha256':hashlib.sha256(prefix.with_suffix(suffix).read_bytes()).hexdigest()} for suffix in ['.stdout','.stderr']}});prefix.with_suffix('.execution.json').write_text(json.dumps(metadata,indent=2)+'\n');sys.exit(rc)
