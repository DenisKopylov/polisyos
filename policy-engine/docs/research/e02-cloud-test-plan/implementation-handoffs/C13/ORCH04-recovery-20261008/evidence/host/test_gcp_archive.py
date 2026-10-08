from pathlib import Path
import datetime, hashlib, json, os, subprocess, tarfile, time
ROOT=Path('/workspace/ORCH04-evidence/c13/gcp-archive');ROOT.mkdir(exist_ok=True)
PROJECT=Path('/workspace/ORCH04-C13/policy-engine')
ENV=os.environ.copy();ENV.update({'PATH':'/workspace/.polisyos-environment/bin:/workspace/.polisyos-environment/uv/bin:/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin:'+ENV['PATH'],'UV_CACHE_DIR':'/workspace/.polisyos-environment/cache/uv','TMPDIR':'/workspace/ORCH04-environments/tmp','OUT_DIR':str(ROOT/'archives'),'UPLOAD':'0','PYTHON_BIN':'/workspace/ORCH04-environments/app/bin/python'})
def run(label,argv,cwd):
    start=time.monotonic()
    with (ROOT/(label+'.log')).open('wb') as out:
        p=subprocess.Popen(argv,cwd=cwd,env=ENV,stdout=out,stderr=subprocess.STDOUT);pid=p.pid;_,status,usage=os.wait4(pid,0);p.returncode=os.waitstatus_to_exitcode(status)
    result={'source':'0321633c0e6d9a87bccfbbe889a4998934c52dd3','argv':argv,'cwd':str(cwd),'pid':pid,'exit_code':p.returncode,'wall_seconds':time.monotonic()-start,'max_rss_kib':usage.ru_maxrss,'UPLOAD':'0','output':str(ROOT/(label+'.log')),'output_sha256':hashlib.sha256((ROOT/(label+'.log')).read_bytes()).hexdigest()}
    (ROOT/(label+'.json')).write_text(json.dumps(result,indent=2)+'\n');return result
pack=run('package',['bash','ops/cloud/gcp/package_repo.sh'],PROJECT);assert pack['exit_code']==0
archive=next((ROOT/'archives').glob('*.tar.gz'));extract=Path('/workspace/ORCH04-environments/gcp-archive-source');extract.mkdir(exist_ok=True)
with tarfile.open(archive) as tar:
    members=tar.getnames();tar.extractall(extract,filter='data')
record={'archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'member_count':len(members),'members':members,'qualified_scope':'Actual source G archive no upload; build requirement assets tested, no deployment/production claim.'}
(ROOT/'archive-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
build=run('extracted-wheel-build',['uv','build','--wheel','--out-dir',str(ROOT/'wheel'),'--build-constraint','/workspace/ORCH04-evidence/host/packaging-tooling.lock'],extract/'policy-engine')
print(json.dumps({'package_exit':pack['exit_code'],'actual_archive_extracted_build_exit':build['exit_code'],'archive':str(archive)}))
