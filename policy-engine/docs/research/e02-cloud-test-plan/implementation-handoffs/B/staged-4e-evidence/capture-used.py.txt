import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--tag',required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();argv=a.command[1:] if a.command[:1]==['--'] else a.command
repo=Path(a.repo);out=repo/'.polisyos/e02-B-current/raw/review';out.mkdir(parents=True,exist_ok=True)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}');started=time.monotonic();log=out/(a.tag+'.txt')
pid=os.fork()
if pid==0:
 fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644);os.dup2(fd,1);os.dup2(fd,2);os.close(fd);os.chdir(repo/'policy-engine');os.execvpe(argv[0],argv,dict(os.environ));os._exit(127)
_,status,rusage=os.wait4(pid,0);code=os.waitstatus_to_exitcode(status)
d={'command':argv,'cwd':str(repo/'policy-engine'),'head':head,'tree':tree,'head_after':git('rev-parse','HEAD'),'wall_s':time.monotonic()-started,'process_rusage_maxrss_kib':rusage.ru_maxrss,'exit_code':code,'output_path':str(log),'output_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'source_environment':{k:os.environ.get(k) for k in ('PYTHONPATH','PATH','LANG','POLISYOS_METRICS_PORT','TIKTOKEN_CACHE_DIR','E02_B_PROPERTY_REMOVAL')}}
assert d['head_after']==head,'candidate changed during deciding check'
(out/(a.tag+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2));raise SystemExit(code)
