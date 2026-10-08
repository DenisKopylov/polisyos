import json,os,pathlib,subprocess,sys,time
label=sys.argv[1];cmd=sys.argv[2:];root=pathlib.Path('/dev/shm/e02-orch03-20261008/c09-sensitivity-checks');start=time.monotonic()
p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
(root/(label+'.stdout')).write_bytes(p.stdout);(root/(label+'.stderr')).write_bytes(p.stderr)
d={'command':cmd,'cwd':os.getcwd(),'returncode':p.returncode,'wall_s':time.monotonic()-start,'stdout':str(root/(label+'.stdout')),'stderr':str(root/(label+'.stderr'))};(root/(label+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d));print(p.stdout.decode(errors='replace'));print(p.stderr.decode(errors='replace'))
