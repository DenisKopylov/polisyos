#!/usr/bin/env python3
"""Read-only, stdlib document integrity check. Does not import or run PolicyOS."""
from pathlib import Path
import json, hashlib, collections
P=Path(__file__).resolve().parent
errors=[]
def check(condition, message):
    if not condition: errors.append(message)
def read(path): return json.loads((P/path).read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
m=read('MANIFEST.json')
for x in m['files']:
    f=P/x['path'];check(f.is_file(), 'missing '+x['path'])
    if f.is_file():check(digest(f)==x['sha256'], 'hash '+x['path'])
for line in (P/'SHA256SUMS.txt').read_text().splitlines():
    sha,relative=line.split('  ',1);f=P/relative
    check(f.is_file() and digest(f)==sha, 'checksum '+relative)
idx=read('04_Трассировка/Индекс.json');ids={x['packet_id']for x in idx['packets']}
check(len(ids)==len(idx['packets'])==127,'127 unique packets')
reqs=[];tests=[]
for row in idx['packets']:
    for key,hkey in [('spec_path','spec_sha256'),('trace_path','trace_sha256')]:check(digest(P/row[key])==row[hkey], 'index hash '+row[key])
    s=read(row['trace_path']);reqs.extend(x['id']for x in s['requirements']);tests.extend(x['id']for x in s['tests'])
check(len(reqs)==len(set(reqs))==606,'606 unique REQ');check(len(tests)==len(set(tests))==613,'613 unique TEST')
p=read('09_Исполнение/План_исполнения.json');state=read('09_Исполнение/Состояние_исполнения.json')
check(len(p['lane_order'])==len(set(p['lane_order']))==12,'12 unique lanes')
check([x['lane_id']for x in p['lanes']]==p['lane_order'],'lane order parity')
assigned=[]
for lane in p['lanes']:
    local=[i for t in lane['tracks']for i in t['packets']];assigned.extend(local)
    ready=[i for batch in lane['topological_ready_batches']for i in batch]
    check(collections.Counter(ready)==collections.Counter(local),'readiness partition '+lane['lane_id'])
    levels={i:n for n,batch in enumerate(lane['topological_ready_batches'])for i in batch}
    for t in lane['tracks']:
        for a,b in zip(t['packets'],t['packets'][1:]):check(levels[a]<levels[b], 'serial order '+a+' '+b)
    for g in lane['cross_track_gates']:
        for a in g['before']:
            for b in g['after']:check(levels[a]<levels[b], 'gate '+a+' '+b)
check(set(assigned)==ids and len(assigned)==127,'127 packet schedule partition')
check({x['packet_id']for x in state['packets']}==ids and len(state['packets'])==127,'state packet partition')
mapping=read('04_Трассировка/Связь_требований_с_интеграцией.json')['scenario_mappings'];bindings=[x['binding_id']for s in mapping for x in s['bindings']]
check(len(mapping)==42 and len(bindings)==len(set(bindings))==159,'42 scenarios / 159 bindings')
check({s['scenario_id']for s in state['integration_scenarios']}=={s['scenario_id']for s in mapping},'state scenarios')
print(json.dumps({'status':'FAIL'if errors else'PASS_DOCUMENT_INTEGRITY','errors':errors,'product_tests':'NOT_RUN','meaning':'Checks document bytes, IDs and schedule structure; not scientific correctness or implementation acceptance'},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
