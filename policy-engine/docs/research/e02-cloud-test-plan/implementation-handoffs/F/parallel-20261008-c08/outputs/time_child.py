import json, resource, subprocess, sys, time
started=time.time()
p=subprocess.run(sys.argv[2:])
u=resource.getrusage(resource.RUSAGE_CHILDREN)
record={'wall_s':time.time()-started,'returncode':p.returncode,'peak_rss_kib':u.ru_maxrss,'user_s':u.ru_utime,'sys_s':u.ru_stime,'voluntary_context_switches':u.ru_nvcsw,'involuntary_context_switches':u.ru_nivcsw}
with open(sys.argv[1],'w') as f:json.dump(record,f,indent=2);f.write('\n')
sys.exit(p.returncode if p.returncode>=0 else 128-p.returncode)
