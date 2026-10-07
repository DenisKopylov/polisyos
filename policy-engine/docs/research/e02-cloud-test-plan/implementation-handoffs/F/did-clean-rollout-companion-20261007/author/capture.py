#!/usr/bin/env python3
"""Capture exact commands and complete streams for the bounded DiD companion."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

def digest(path):
    raw=pathlib.Path(path).read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cwd',required=True);p.add_argument('--repo',required=True);p.add_argument('--stem',required=True)
    p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    argv=a.command[1:] if a.command and a.command[0]=='--' else a.command
    def git(*args):return subprocess.check_output(['git',*args],cwd=a.repo,stderr=subprocess.PIPE).decode().strip()
    before={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'branch':git('symbolic-ref','--short','HEAD'),'status':git('status','--porcelain')}
    stem=pathlib.Path(a.stem);stem.parent.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    env={**os.environ,'PYTHONPATH':'src:.','PYTHONDONTWRITEBYTECODE':'1'}
    with pathlib.Path(str(stem)+'.stdout').open('wb') as out,pathlib.Path(str(stem)+'.stderr').open('wb') as err:
        child=subprocess.Popen(argv,cwd=a.cwd,env=env,stdout=out,stderr=err)
        _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
    after={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'branch':git('symbolic-ref','--short','HEAD'),'status':git('status','--porcelain')}
    doc={'command':argv,'cwd':a.cwd,'environment':{'PYTHONPATH':'src:.','PYTHONDONTWRITEBYTECODE':'1','command_executable':argv[0],'capture_python':platform.python_version(),'capture_executable':sys.executable},'source_begin':before,'source_end':after,'exit':child.returncode,'elapsed_s':time.monotonic()-start,'peak_rss_platform_units':usage.ru_maxrss,'source_identity_unchanged':before==after,'stdout':digest(str(stem)+'.stdout'),'stderr':digest(str(stem)+'.stderr'),'replayer':digest(__file__)}
    path=pathlib.Path(str(stem)+'.execution.json');path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'execution':str(path),'exit':child.returncode,'elapsed_s':doc['elapsed_s'],'stdout':doc['stdout'],'stderr':doc['stderr'],'source_identity_unchanged':doc['source_identity_unchanged']},indent=2))
    return child.returncode
if __name__=='__main__':raise SystemExit(main())
