import csv,json,hashlib,subprocess
from pathlib import Path
root=Path('/workspace/e02-F-closeout-20261006');e=root/'policy-engine/docs/research/e02-cloud-test-plan';out=Path('/tmp/e02-F-continuation-20261007/intake');r=e/'results'
files=[];objects={}
for p in sorted(r.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts:continue
 b=p.read_bytes();s=b.decode('utf-8');files.append({'path':str(p.relative_to(root)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 if p.suffix=='.json':objects[p.name]=json.loads(s)
 elif p.suffix=='.jsonl':objects[p.name]=[json.loads(x) for x in s.splitlines() if x]
 elif p.suffix=='.tsv':objects[p.name]=list(csv.DictReader(s.splitlines(),delimiter='\t'))
verification=objects['verification.json'];assert verification['primary_cells']==2074 and verification['finding_ids']==282 and verification['raw_archives_received']==0
owners={}
for n in ['bundle-owners.tsv','finding-owners.tsv']:
 p=e/'execution-organization'/n; rows=list(csv.DictReader(p.read_text().splitlines(),delimiter='\t'));owners[n]=rows
assert len(owners['bundle-owners.tsv'])==127 and len(owners['finding-owners.tsv'])==282
frows=[x for x in owners['finding-owners.tsv'] if x['unit']=='F'];assert len(frows)==35
bs=[x for x in owners['bundle-owners.tsv'] if x['unit']=='F'];assert len(bs)==17
out.joinpath('result-pack-and-owner-read.json').write_text(json.dumps({'full_files_read':files,'counts':{'sources':len(verification['sources']),'cells':len(objects['cells.tsv']),'routes':len(objects['routes.tsv']),'events_locators':len(objects['events.jsonl']),'owners':{'bundles':127,'findings':282,'F_bundles':17,'F_findings':35}},'F_bundle_owner_rows':bs,'F_finding_owner_rows':frows,'baseline_grade':verification['index_acceptance'],'raw_archives_received':0},ensure_ascii=False,indent=2)+'\n')
queries=[('finding-'+x['finding_id'],['--finding',x['finding_id'],'--limit','1000','--details']) for x in frows]+[(c,['--cell',c,'--details','--job-context','--block-limit','1000']) for c in ['F01-P025','F08-P048','F13-P030']]
ps=[]
qdir=out/'queries';qdir.mkdir(exist_ok=True)
for name,args in queries:
 cmd=['python3','policy-engine/docs/research/e02-cloud-test-plan/results/query.py']+args;a=(qdir/(name+'.json')).open('wb');b=(qdir/(name+'.stderr')).open('wb');p=subprocess.Popen(cmd,cwd=root,stdout=a,stderr=b);ps.append((name,cmd,p,a,b))
qr=[]
for name,cmd,p,a,b in ps:
 rc=p.wait();a.close();b.close();raw=(qdir/(name+'.json')).read_bytes();assert rc==0;d=json.loads(raw);qr.append({'name':name,'command':cmd,'returncode':rc,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'matching_cells':d['matching_cells'],'displayed_cells':d['displayed_cells'],'states':d['states'],'source_blocks':d['matching_source_blocks'],'raw_archives_received':d['raw_archives_received']})
(qdir/'index.json').write_text(json.dumps(qr,indent=2)+'\n');print(json.dumps({'full_result_files':len(files),'cells':2074,'owners':{'bundles':127,'findings':282,'F_bundles':17,'F_ids':35},'queries':len(qr),'grade':verification['index_acceptance'],'raw_archives':0}))
