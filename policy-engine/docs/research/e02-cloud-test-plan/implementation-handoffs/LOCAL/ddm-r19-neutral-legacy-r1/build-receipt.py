import base64, hashlib, json, os, pathlib, tarfile
BASE=pathlib.Path(os.environ['DDM_BASE']); E=BASE/'evidence'; phases=['n-baseline','n-mutant','n-restored','l-baseline','l-mutant','l-restored']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def wrappers(p): return [json.loads(x.split('DDM_COMPLETE_CHILD ',1)[1]) for x in p.read_text().splitlines() if 'DDM_COMPLETE_CHILD ' in x]
def inner(w):
 raw=base64.b64decode(w['stdout_base64'],validate=True); assert raw.endswith(b'\n') and raw.count(b'\n')==1
 return json.loads(raw)
summary={}
for phase in phases:
 d=E/'runs'/phase; proc=json.loads((d/'process.json').read_text()); ws=wrappers(d/'stdout.txt'); records=[inner(w) for w in ws]
 expected_exit=1 if phase.endswith('mutant') else 0; assert proc['exit_status']==expected_exit
 assert len(proc['pytest_pid_from_observer_dirs'])==1; pid=str(proc['pytest_pid_from_observer_dirs'][0]); obs=d/'observer'/pid
 for name in ('process.json','collection.json','events.jsonl','origins.json','session.json'): assert (obs/name).is_file()
 origins=json.loads((obs/'origins.json').read_text()); root=str(BASE/phase[0]/'policy-engine')
 # Observer records every first-party origin; all must be in this detached worktree.
 origin_items=origins if isinstance(origins,list) else origins.get('origins',origins)
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ('origin','file') and isinstance(v,str) and ('polisyos' in v or '/tests/' in v or '/tools/' in v): assert v.startswith(root),(phase,v)
    walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(origin_items)
 for w,r in zip(ws,records):
  assert r['before_first_party_modules']==[] and r['dont_write_bytecode']==1 and r['pycache_prefix']
  assert w['cache_initial_entries']==[] and w['cache_final_entries']==[] and r['pid']==w['pid_from_parent'] and r['ppid']==w['parent_pid']
  assert not r['foreign_first_party_origins']
  for name,v in r['first_party_modules'].items():
   for q in ([v.get('origin')] if v.get('origin') else [])+v.get('locations',[]): assert q.startswith(root),(phase,name,q)
 summary[phase]={'classification':'SEMANTIC_RED' if expected_exit else 'PASS','exit_status':expected_exit,'duration_ns':proc['duration_ns'],'pytest_pid':int(pid),'wrapper_labels':[w['label'] for w in ws],'child_pids':[r['pid'] for r in records],'snapshot_errors':[{'label':w['label'],'errors':r['first_party_origin_snapshot_errors']} for w,r in zip(ws,records)],'files':{n:{'bytes':(d/n).stat().st_size,'sha256':sha(d/n)} for n in ('stdout.txt','stderr.txt','junit.xml')},'observer_dir':f'runs/{phase}/observer/{pid}'}
# Property-specific semantic adjudication.
nb=inner(wrappers(E/'runs/n-baseline/stdout.txt')[0]); nm=inner(wrappers(E/'runs/n-mutant/stdout.txt')[0]); nr=inner(wrappers(E/'runs/n-restored/stdout.txt')[0])
assert nb['error'] is None and nb['attempts']==[] and nb['forbidden_loaded']==[] and nb['outcome']=='neutral-child-used-real-value'
assert nm['attempts']==['polisyos.ddm.integration.monitor'] and nm['error']['type']=='RuntimeError' and nm['error']['message'].startswith('LIVE_DDM_IMPORT_TRAP:')
assert nr['error'] is None and nr['attempts']==[] and nr['forbidden_loaded']==[]
lbw=wrappers(E/'runs/l-baseline/stdout.txt'); assert [x['label'] for x in lbw]==['synthetic-event-legacy-writer','synthetic-event-cold-legacy-reader']
writer=inner(lbw[0]); baseline_reader=inner(lbw[1]); lm=wrappers(E/'runs/l-mutant/stdout.txt'); lr=wrappers(E/'runs/l-restored/stdout.txt')
assert [x['label'] for x in lm]==['synthetic-event-cold-legacy-reader'] and [x['label'] for x in lr]==['synthetic-event-cold-legacy-reader']
mut_reader=inner(lm[0]); restored_reader=inner(lr[0]); expected_global='polisyos.ddm.integration.events.ShiftDetectedEvent'
for r in (baseline_reader,mut_reader,restored_reader): assert r['input_pickle_bytes']==writer['pickle_bytes']==1345 and r['input_pickle_sha256']==writer['pickle_sha256']=='66083e3804228ba12bda0e5d41a32ffdf993311b5a18b846feebada9b6bf0306' and expected_global in r['seen_globals']
assert baseline_reader['error'] is None and restored_reader['error'] is None
assert mut_reader['error']['type']=='AttributeError' and "has no attribute 'ShiftDetectedEvent'" in mut_reader['error']['message']
status_n=os.popen(f"git -C {BASE/'n'} status --porcelain=v1").read(); status_l=os.popen(f"git -C {BASE/'l'} status --porcelain=v1").read(); assert status_n==status_l==''
receipt={'source':{'topic':'codex/e02-composed-progress-20261028-r19','commit':'aa8571cba044ebe04d4db4f99432cb49abdde59a','tree':'0ff45c87431af2a4139519ff31d123ff465ed862','parent':'0c2169fd0d17dc59b49733fe6a001ec4114d2d1c'},'selectors':{'N':'tests/unit/ddm/test_contract_fresh_consumers.py::test_neutral_contract_entrypoints_are_independent_cold_processes[polisyos.ddm.contracts.events]','L':'tests/unit/ddm/test_contract_fresh_consumers.py::test_synthetic_legacy_pickle_resolves_in_distinct_cold_reader[event]'},'pins':{'count':25,'all_ok':True,'file_type_denominator':{'.py':16,'.md':4,'.toml':2,'.python-version':1,'.lock':1,'.ini':1}},'mutations':{'N':{'target':'policy-engine/src/polisyos/ddm/__init__.py','preimage_sha256':'adbf26cc868a931b8ad4b2951558a065a52169a5d55acb3993e137d6657322fc','patch_sha256':'68165522704b19748078bcaf8c5a653b07fdc226ad502bdae663ad1e8b0b2278','mutated_sha256':'a9d1f05bcc614ecb29350480ef9f52d796aa9e7aac39348cc2813443f6b08383','git_diff_sha256':'dc3267f8f35b760104b497e10ca6675e31bbbeb62d5e0c1ab9aa30327a8b9188'},'L':{'target':'policy-engine/src/polisyos/ddm/integration/events.py','preimage_sha256':'894151bedc3046b2b41c469f15b42565818162dbd8d7a3d2d587a36ebcc9eb50','patch_sha256':'557cc9a2326db9723b3c7d66850c70a3397d9ad1424e577b0c061d42e4a64d48','mutated_sha256':'c67c1b65365f7b91aa506b0f461d340e761b7a2d3985f02f4a26e45b51fbef4e','git_diff_sha256':'db747a4af79136b5fa0a013dd628a369c695d87cb69571ee92beb1d652b5d1a6'}},'phases':summary,'semantic_causes':{'N':'Exact eager monitor mutation caused the neutral cold child live-import trap; complete report captured RuntimeError and the sole attempt polisyos.ddm.integration.monitor.','L':'Exact facade export removal caused the real cold reader to see the old global and raise AttributeError resolving ShiftDetectedEvent; mutant and restore reused the exact baseline writer record and ran no writer.'},'writer_reuse':json.loads((E/'writer-validation.json').read_text()),'final_controls':{'n_status_porcelain_v1':status_n,'l_status_porcelain_v1':status_l,'targets_restored':True},'classification_basis':{'P29':'Both selectors execute real cold import/unpickle behavior, not authorial markers.','P33':'Each exact source-property mutation is the witness; test/oracle bytes were unchanged.','P38':'Measured properties are forbidden live-import avoidance and old-FQN resolution, not exit codes; complete child semantics adjudicate each red.','P41':'Each unmodified baseline passed before attribution; each byte-exact restoration passed.'},'boundary':'Synthetic diagnostic values only. No historical writer-byte availability, calibration, authority, promotion, production-model evidence, whole-LA-056 acceptance, G closure, or broad-suite result is claimed. verification_missing remains pending independent review and broader criterion adjudication.','readset_location':'Lossless bundle: each run stdout contains complete cold-child snapshots and each observer/<pytest-pid>/origins.json contains the pytest-process first-party readset.'}
(E/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
# Lossless bundle contains all deciding streams/JUnit/observer files plus run records and admission.
with tarfile.open(E/'evidence.tar.gz','w:gz',compresslevel=9) as t:
 for rel in ['admission','runs','run-phase.sh','writer-validation.json']:
  t.add(E/rel,arcname=rel,recursive=True)
with tarfile.open(E/'evidence.tar.gz','r:gz') as t:
 members=[]; total=0
 for m in t.getmembers():
  if not m.isfile(): continue
  b=t.extractfile(m).read(); assert len(b)==m.size; total+=len(b); members.append({'path':m.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
manifest={'archive':'evidence.tar.gz','archive_bytes':(E/'evidence.tar.gz').stat().st_size,'archive_sha256':sha(E/'evidence.tar.gz'),'member_count':len(members),'uncompressed_file_bytes':total,'members':members,'verification':'gzip/tar stream opened; every regular member fully read and hashed'}
(E/'archive-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps({'phases':{k:v['classification'] for k,v in summary.items()},'archive':manifest|{'members':'omitted'}},indent=2))
