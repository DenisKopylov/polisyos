import subprocess,json,hashlib
from pathlib import Path
p=Path('/tmp/e02-F-continuation-20261006/root-closeout-publication');cwd='/workspace/e02-F-closeout-20261006'
payload={'title':'fix(scientist): complete F causal consumers and source-bound 35-ID handoff','body':(p/'pr65-body.md').read_text().rstrip('\n')}
(p/'pr65-update.json').write_text(json.dumps(payload,ensure_ascii=False)+'\n')
cmd=['gh','api','--method','PATCH','repos/DenisKopylov/polisyos/pulls/65','--input',str(p/'pr65-update.json')]
r=subprocess.run(cmd,cwd=cwd,capture_output=True)
(p/'pr-rest-edit.json').write_bytes(r.stdout);(p/'pr-rest-edit.stderr').write_bytes(r.stderr)
(p/'pr-rest-edit.execution.json').write_text(json.dumps({'command':cmd,'cwd':cwd,'exit_code':r.returncode},indent=2)+'\n');assert r.returncode==0
cmd=['gh','api','repos/DenisKopylov/polisyos/pulls/65'];r=subprocess.run(cmd,cwd=cwd,capture_output=True)
(p/'pr-readback.json').write_bytes(r.stdout);(p/'pr-readback.stderr').write_bytes(r.stderr);assert r.returncode==0
d=json.loads(r.stdout);assert d['body']==payload['body'];assert d['title']==payload['title'];assert d['head']['sha']=='f17b9a52784d9484ef65563dc6695240629bdfc6';assert d['draft'] and d['state']=='open' and d['merged_at'] is None and d['base']['ref']=='main'
(p/'pr-readback-proof.json').write_text(json.dumps({'check':'PASS','url':d['html_url'],'head':d['head']['sha'],'body_sha256':hashlib.sha256(d['body'].encode()).hexdigest(),'scope':'Metadata only; draft/open/unmerged. Exact receipt publication follows, product source unchanged.','initial_gh_pr_edit':'ERROR: deprecated classic projectCards GraphQL read; preserved full stderr; REST correction no history or product mutation.'},indent=2)+'\n')
print('PR65 REST metadata edit/readback PASS')
