import gzip
import hashlib
import io
import json
import lzma
import pathlib
import subprocess
import time

ROOT = pathlib.Path('/workspace/e02-F-closeout-20261006')
E02 = ROOT / 'policy-engine/docs/research/e02-cloud-test-plan'
OUT = pathlib.Path('/tmp/e02-F-continuation-20261007/intake')
PIN = '072d45a56d1119fe3e7665cec2cbbdca015d2934'
START = time.monotonic()

def git_bytes(spec):
    return subprocess.check_output(['git', 'show', spec], cwd=ROOT)

def digest(data):
    return hashlib.sha256(data).hexdigest()

docs = []
for p in sorted((E02 / 'implementation-handoffs/F/continuation-transfer-20261006').rglob('*')):
    if p.is_file():
        data = p.read_bytes()
        if p.suffix == '.json':
            json.loads(data)
        docs.append({'path': str(p.relative_to(ROOT)), 'bytes': len(data), 'sha256': digest(data)})
for rel in ['implementation-handoffs/F/continuation-closeout-20261006.json',
            'implementation-handoffs/F/continuation-closeout-20261006/transport.json',
            'implementation-handoffs/F/continuation-publication-readback-20261006.json',
            'closure-decisions/coverage.json']:
    p = E02 / rel
    data = p.read_bytes()
    json.loads(data)
    docs.append({'path': str(p.relative_to(ROOT)), 'bytes': len(data), 'sha256': digest(data)})

audit = json.loads((E02/'implementation-handoffs/F/continuation-transfer-20261006/full-audit.json').read_bytes())
coverage = json.loads((E02/'closure-decisions/coverage.json').read_bytes())
expected = {r['id'] for r in coverage['findings'] if r['unit'] == 'F'}
assert len(audit['rows']) == 35 and {r['finding_id'] for r in audit['rows']} == expected
bindings = []
for r in audit['rows']:
    for c in r['original_source_criterion_refs']:
        doc = git_bytes(c['source_sha'] + ':' + c['source_path'])
        selected = b''.join(doc.splitlines(keepends=True)[c['lines'][0]-1:c['lines'][1]])
        assert len(selected) == c['bytes'] and digest(selected) == c['sha256'], (r['finding_id'], c)
        assert selected.decode() == c['complete_original_block']
        bindings.append({'finding_id': r['finding_id'], **{k:v for k,v in c.items() if k != 'complete_original_block'}, 'check':'PASS'})
assert len(bindings) == 36

transport = json.loads((E02/'implementation-handoffs/F/continuation-transfer-20261006/artifact-transports.json').read_bytes())
checks = []
for n, rec in enumerate(transport['files']):
    path = rec['path']
    ref = rec.get('git_ref') or rec.get('head') or PIN
    proc = subprocess.run(['git','show',ref+':'+path],cwd=ROOT,capture_output=True)
    if proc.returncode:
        checks.append({'ordinal': n, 'ref':ref,'path':path,'check':'UNRUN','exit_code':proc.returncode,'stderr':proc.stderr.decode(errors='replace'),'declared_check':rec.get('check')})
        continue
    data = proc.stdout
    assert len(data) == rec['bytes'] and digest(data) == rec['sha256'], (n,ref,path,len(data),digest(data))
    item = {'ordinal':n,'ref':ref,'path':path,'bytes':len(data),'sha256':digest(data),'check':'PASS'}
    if rec.get('decoded_sha256'):
        dec = (rec.get('decoding') or rec.get('encoding') or ('gzip' if path.endswith('.gz') else 'xz' if path.endswith('.xz') else '')).lower()
        if dec == 'gzip':
            stream = gzip.GzipFile(fileobj=io.BytesIO(data))
        elif dec in ('xz','lzma'):
            stream = lzma.LZMAFile(io.BytesIO(data))
        elif digest(data) == rec['decoded_sha256']:
            stream = io.BytesIO(data)
        elif data.lstrip().startswith((b'{', b'"')):
            wrapped = json.loads(data)
            values = [wrapped] if isinstance(wrapped,str) else [wrapped.get(k) for k in ['raw_utf8','raw_text','text','stdout','stderr','content','output','data','raw_output','utf8_text','original_utf8','utf8','verbatim_utf8','raw']]
            candidates = [v.encode('utf8') for v in values if isinstance(v,str) and digest(v.encode('utf8')) == rec['decoded_sha256']]
            if len(candidates) != 1:
                raise ValueError((n,'nonunique lossless wrapper',dec))
            stream = io.BytesIO(candidates[0])
        else:
            stream = None
        if stream is None:
            raise ValueError((n,'unknown decoding',dec))
        h = hashlib.sha256(); size = 0
        while chunk := stream.read(1024*1024):
            size += len(chunk); h.update(chunk)
        assert size == rec['decoded_bytes'] and h.hexdigest() == rec['decoded_sha256'], (n,'decoded drift',path)
        item.update(decoded_bytes=size,decoded_sha256=h.hexdigest(),decoding=dec)
    checks.append(item)
    if n and n % 500 == 0:
        print(json.dumps({'read_transport_records':n,'elapsed_seconds':time.monotonic()-START}),flush=True)

report={'schema':'e02.F.current-pack-read.v1','source_sha':PIN,'source_tree':subprocess.check_output(['git','rev-parse',PIN+'^{tree}'],cwd=ROOT,text=True).strip(),
        'documents':docs,'finding_count':35,'bundle_count':len({r['primary_bundle'] for r in audit['rows']}),'original_bindings':bindings,
        'transport_checks':checks,'transport_count':len(checks),'scientific_checks_run':False,
        'missing_historical_refs_do_not_become_deciding_inputs':True,'elapsed_seconds':time.monotonic()-START}
(OUT/'current-pack-read.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'documents':len(docs),'IDs':35,'bindings':len(bindings),'stored_records':len(checks),'states':{s:sum(x['check']==s for x in checks) for s in ['PASS','UNRUN']},'elapsed_seconds':report['elapsed_seconds']}))
