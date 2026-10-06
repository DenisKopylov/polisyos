import collections,concurrent.futures,csv,datetime,gzip,hashlib,io,json,pathlib,re,subprocess
REPO='/workspace/e02-F-graph-20261006';OUT=pathlib.Path('/workspace/e02-F-20261006-receipts/protocol-audit');BASE='198076863e143dea9f89f02734b13d50dae3eed5';PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
PINS={'cau':('4c5a11ff8050c6108f6753177b96e6714cef401f','did-selected-cohort-20261006.json'),'fit':('f460bd81b8124be58f890f59a53e2aba9e7ceb76','tmle-20261006.json'),'rdd':('15a04c4400497374416e167a5f61ebc12f61b8e4','rdd-sharp-rbc-20261006.json'),'eco':('fb51511fef60c5123875e99ab2f19a9a0bd5d16f','economic-science-profiles-20261006.json'),'lex':('77166daa0ff8b9659e3978447f9016c691694266','lex-pass-plan-20261006.json'),'api':('449d32909928caf39382f4ff02ac74b0adf277eb','api-20261006.json'),'dowhy':('c8c2319d6c48f23f90103322da8cd63bc959da6f','dowhy-worker-20261006.json'),'fry':('f4fa51e6dd247cfd967450263579d67233a743d6','treasury-execution-20261006.json'),'graph':('bf335dd687c313fda9001fa3bb1365df6bc5ae1f','scm-source-bound-20261006.json'),'b220':('bf335dd687c313fda9001fa3bb1365df6bc5ae1f','graph-cache-immutability-20261006.json')}
GZIP_CACHE={}
for cached_name in ['cau','fit','rdd','eco','lex','api','dowhy','fry','graph','b220','graph_native','root_consumer','installed','intake','installed_latest']:
 cached_path=OUT/(cached_name+'.json')
 if not cached_path.exists():continue
 try:cached_result=json.loads(cached_path.read_text())
 except ValueError:continue
 for record in cached_result.get('hash_records',[]):
  if record.get('path','').endswith('.gz') and record.get('decoded_hash_match') and record.get('decoded_size_match'):
   GZIP_CACHE.setdefault((record['sha256'],record['bytes']),[]).append(record)
MINIMUM=['schema','unit','slice','closure_ids','bundle_ids','slice_base_sha','implementation_commits','candidate_tree_sha','branch','pull_request','changed_paths','baseline_cells','checks','property','predicate_basis','capability_state_or_finding_state','limitations_and_next_owner']
CHECK_MINIMUM=['command','target_sha','environment','input_closure','outcome','output'];ENUM={'PASS','FAIL','ERROR','SKIP','UNRUN'}
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.DEVNULL)
def walk(x,loc=''):
 if isinstance(x,dict):
  yield loc,x
  for k,v in x.items():yield from walk(v,loc+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from walk(v,loc+'/'+str(i))
def strings(x,loc=''):
 if isinstance(x,str):yield loc,x
 elif isinstance(x,dict):
  for k,v in x.items():yield from strings(v,loc+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from strings(v,loc+'/'+str(i))
def exists(sha,path):return subprocess.run(['git','cat-file','-e',sha+':'+path],cwd=REPO,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
def ancestor(a,b):return subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=REPO,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
remotes={ref:sha for sha,ref in (line.split() for line in git('ls-remote','--heads','origin','codex/e02-F-*20261006*').decode().splitlines())}
(OUT/'remote-heads.json').write_text(json.dumps(remotes,indent=2)+'\n')
def component(item):
 name,(head,file)=item;primary=PREFIX+file;raw=git('show',head+':'+primary);d=json.loads(raw);issues=[];caveats=[];hash_records=[];documents=[];normalized_records=[];recordsseen=set();jsonseen=set();byte_cache={};referenced=[];blob_records=[]
 cached_gzip_reuses=0
 def issue(kind,loc,detail):issues.append({'kind':kind,'location':loc,'detail':detail})
 for k in MINIMUM:
  if k not in d:issue('minimum_field',k,'missing canonical primary field')
 for i,c in enumerate(d['checks']):
  for k in CHECK_MINIMUM:
   if k not in c:issue('check_minimum',f'checks/{i}/{k}','missing')
  if c.get('outcome') not in ENUM:issue('outcome_enum',f'checks/{i}/outcome',c.get('outcome'))
  if not isinstance(c.get('output'),str):issue('output_string',f'checks/{i}/output',{'actual_type':type(c.get('output')).__name__,'preserve_ref_and_supply_string':True})
  if isinstance(c.get('output'),str) and c['output'].startswith('policy-engine/') and not exists(head,c['output']):issue('output_missing',f'checks/{i}/output',c['output'])
 base=d['slice_base_sha'];candidate=d.get('candidate_sha') or d.get('implementation_sha') or d['implementation_commits'][-1];tree=git('rev-parse',candidate+'^{tree}').decode().strip()
 if tree!=d['candidate_tree_sha']:issue('candidate_tree','candidate_tree_sha',{'declared':d['candidate_tree_sha'],'actual':tree,'candidate':candidate})
 if not ancestor(base,candidate):issue('ancestry','slice_base_sha','base is not ancestor of candidate')
 if not ancestor(candidate,head):issue('ancestry','candidate','candidate is not ancestor of published head')
 for c in d['implementation_commits']:
  if not ancestor(base,c) or not ancestor(c,head):issue('implementation_ancestry','implementation_commits',c)
 remote=remotes.get('refs/heads/'+d['branch'])
 if remote!=head:issue('remote_head','branch',{'read':remote,'pin':head})
 changed=git('diff','--name-only',base,candidate).decode().splitlines();actual=[p for p in changed if '/implementation-handoffs/' not in p]
 declared=[p if p.startswith('policy-engine/') else 'policy-engine/'+p for p in d['changed_paths']]
 footprint={'actual_nonreceipt_changes':actual,'declared_changed_paths':declared,'actual_minus_declared':sorted(set(actual)-set(declared)),'declared_minus_actual':sorted(set(declared)-set(actual)),'receipt_paths_excluded':[p for p in changed if '/implementation-handoffs/' in p]}
 if footprint['actual_minus_declared'] or footprint['declared_minus_actual']:caveats.append({'kind':'footprint_scope_difference','detail':footprint})
 def fetch(sha,path):
  key=(sha,path)
  if key not in byte_cache:byte_cache[key]=git('show',sha+':'+path)
  return byte_cache[key]
 def parse_ref(sha,path,depth=0):
  if (sha,path) in jsonseen:return
  jsonseen.add((sha,path));r=fetch(sha,path)
  try:v=json.loads(r)
  except (ValueError,UnicodeError):return
  if isinstance(v,(dict,list)):scan(v,sha,path,depth+1)
 def scan(v,sha,doc,depth):
  nonlocal cached_gzip_reuses
  doc_source=None
  if isinstance(v,dict):
   candidates=[v.get(k) for k in ['source_sha','target_sha','candidate_sha','implementation_sha']]
   if isinstance(v.get('implementation_commits'),list) and v['implementation_commits']:candidates.append(v['implementation_commits'][-1])
   for candidate_source in candidates:
    if isinstance(candidate_source,str) and re.fullmatch('[0-9a-f]{40}',candidate_source):
     try:
      if git('cat-file','-t',candidate_source).strip()==b'commit':doc_source=candidate_source;break
     except subprocess.CalledProcessError:pass
  explicit_path_locations=set()
  for loc,original in walk(v):
   if isinstance(original.get('source_path'),str) and any(k in original for k in ['sha256','bytes','git_blob']):explicit_path_locations.add(loc+'/source_path')
   if isinstance(original.get('path'),str) and any(k in original for k in ['sha256','bytes','git_blob','artifact_git_ref','git_commit','sha','commit','stored_sha256','original_sha256','decoded_sha256','decompressed_sha256','raw_sha256','classification']):explicit_path_locations.add(loc+'/path')
   if isinstance(original.get('committed_path'),str) and any(k in original for k in ['sha256','bytes','git_blob','stored_sha256']):explicit_path_locations.add(loc+'/committed_path')
   rec=dict(original)
   path=rec.get('path',rec.get('committed_path',rec.get('source_path')))
   if 'decoded_utf8_sha256' in rec:rec['decoded_sha256']=rec['decoded_utf8_sha256']
   if 'decoded_utf8_bytes' in rec:rec['decoded_bytes']=rec['decoded_utf8_bytes']
   if 'stored_sha256' in rec:rec['sha256']=rec['stored_sha256']
   if 'stored_bytes' in rec:rec['bytes']=rec['stored_bytes']
   if isinstance(rec.get('compressed'),dict) and 'decompressed_sha256' in rec:
    rec={**rec['compressed'],'encoding':'gzip','decompressed_sha256':rec['decompressed_sha256'],'decompressed_bytes':rec['decompressed_bytes']};path=rec['path']
   if not isinstance(path,str) or not path.startswith('policy-engine/'):continue
   recsha=next((rec[k] for k in ['artifact_git_ref','git_commit','sha','commit','head','implementation_doc_commit'] if isinstance(rec.get(k),str) and re.fullmatch('[0-9a-f]{40}',rec[k])),sha)
   if '/implementation-handoffs/' not in path and isinstance(rec.get('source_sha'),str) and re.fullmatch('[0-9a-f]{40}',rec['source_sha']):recsha=rec['source_sha']
   elif doc_source and '/implementation-handoffs/' not in path and not any(isinstance(rec.get(k),str) and re.fullmatch('[0-9a-f]{40}',rec[k]) for k in ['artifact_git_ref','git_commit','sha','commit','head','implementation_doc_commit']):recsha=doc_source
   # Source bindings retain requested candidate context if final append introduced extra receipt-only fields.
   if not exists(recsha,path):
    if rec.get('source_path')==path and re.fullmatch('[0-9a-f]{40}',str(rec.get('git_blob',''))) and not any(k in rec for k in ['sha256','bytes','stored_sha256','stored_bytes','original_sha256','decoded_sha256','decompressed_sha256','raw_sha256']):
     declared_blob=rec['git_blob']
     try:
      blob_bytes=git('cat-file','blob',declared_blob);actual_blob=subprocess.check_output(['git','hash-object','--stdin'],cwd=REPO,input=blob_bytes)
     except subprocess.CalledProcessError:
      historical_scope=rec.get('scope')
      detail={'git_blob':declared_blob,'source_path':path,'referencing_document_sha':sha,'resolved_source_context_sha':recsha,'declared_scope':historical_scope}
      if declared_blob=='175c1ed4db37589e8adaf14af6700ad639edb2c8' and doc=='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json' and loc=='/citation_catalog/reviewed_no_record_audit/historical_held_review_source' and historical_scope=='Historical source blob retained only as provenance for the N-card audit; the blob object exists, but this path is not tracked at the ledger head. It is not current finding-status or behavior evidence.':
       detail.update(classification='unavailable_historical_non_deciding',check='UNRUN',current_deciding=False)
      issue('blob_source_missing',doc+loc,detail);continue
     actual_blob=actual_blob.decode().strip()
     if actual_blob!=declared_blob:issue('blob_source_identity',doc+loc,{'declared':declared_blob,'actual':actual_blob})
     blob_records.append({'git_blob':declared_blob,'source_path':path,'bytes':len(blob_bytes),'sha256':hashlib.sha256(blob_bytes).hexdigest(),'record_location':doc+loc,'declared_scope':rec.get('scope'),'actual_current_path_exists':False,'binding_kind':'explicit immutable blob-only historical source locator; no current provider/path claim'})
     continue
    if any(k in rec for k in ['sha256','bytes','git_blob','original_sha256','decoded_sha256','decompressed_sha256','raw_sha256']):issue('hash_ref_missing',doc+loc,{'sha':recsha,'path':path})
    continue
   key=(recsha,path,rec.get('sha256'),rec.get('bytes'),rec.get('decoded_sha256'),rec.get('original_sha256'),rec.get('decompressed_sha256'),rec.get('uncompressed_sha256'),rec.get('raw_sha256'))
   if key in recordsseen:continue
   recordsseen.add(key);b=fetch(recsha,path);digest=hashlib.sha256(b).hexdigest();record={'sha':recsha,'path':path,'bytes':len(b),'sha256':digest,'record_location':doc+loc}
   if rec.get('classification')=='historical_non_deciding':record['historical_non_deciding']=True
   if isinstance(rec.get('lines'),list) and len(rec['lines'])==2 and all(isinstance(x,int) and x>=1 for x in rec['lines']) and (isinstance(rec.get('verified_block_bytes'),int) or (isinstance(rec.get('bytes'),int) and re.fullmatch('[0-9a-f]{64}',str(rec.get('sha256',''))))):
    lo,hi=rec['lines'];block=b''.join(b.splitlines(keepends=True)[lo-1:hi]);record['file_bytes']=len(b);record['file_sha256']=digest;record['hash_scope']={'source_lines_inclusive':rec['lines']};digest=hashlib.sha256(block).hexdigest();record['sha256']=digest;record['bytes']=len(block);rec['bytes']=rec.get('verified_block_bytes',rec['bytes'])
   expected=rec.get('sha256')
   if expected is not None and isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected):
    record['declared_sha256']=expected;record['hash_match']=digest==expected
    if digest!=expected:issue('sha256_mismatch',doc+loc,record)
   size=rec.get('bytes')
   if isinstance(size,int) and not isinstance(size,bool):
    record['declared_bytes']=size;record['size_match']=size==record['bytes']
    if size!=record['bytes']:issue('size_mismatch',doc+loc,record)
   blob=rec.get('git_blob')
   if blob and isinstance(blob,str) and re.fullmatch('[0-9a-f]{40}',blob):
    actualblob=git('rev-parse',recsha+':'+path).decode().strip();record['git_blob_match']=actualblob==blob
    if actualblob!=blob:issue('blob_mismatch',doc+loc,{'declared':blob,'actual':actualblob,'sha':recsha,'path':path})
   raw_expected=rec.get('original_sha256',rec.get('decoded_sha256',rec.get('decompressed_sha256',rec.get('uncompressed_sha256',rec.get('raw_sha256')))))
   raw_size=rec.get('original_bytes',rec.get('decoded_bytes',rec.get('decompressed_bytes',rec.get('uncompressed_bytes',rec.get('raw_bytes')))))
   if str(rec.get('normalization','none')).lower().startswith('strip trailing whitespace'):
    normalized_records.append({'record_location':doc+loc,'stored_path':path,'normalization':rec['normalization'],'raw_sha256':raw_expected,'raw_bytes':raw_size});raw_expected=None;raw_size=None
   if raw_expected is not None or raw_size is not None:
    encoding=str(rec.get('encoding','identity')).lower();h=hashlib.sha256();count=0
    if 'gzip' in encoding or path.endswith('.gz'):
     cached=next((x for x in GZIP_CACHE.get((hashlib.sha256(b).hexdigest(),len(b)),[]) if raw_expected==x['decoded_sha256'] and (raw_size is None or raw_size==x['decoded_bytes'])),None)
     if cached is not None:
      cached_gzip_reuses+=1;count=cached['decoded_bytes'];decoded_digest=cached['decoded_sha256']
     else:
      stream=gzip.GzipFile(fileobj=io.BytesIO(b))
      while chunk:=stream.read(1024*1024):h.update(chunk);count+=len(chunk)
      decoded_digest=h.hexdigest()
    elif 'json' in encoding or path.endswith('.text.json') or path.endswith('.txt.json'):
     obj=json.loads(b)
     if isinstance(obj,str):decoded=obj.encode()
     elif isinstance(obj,dict):
      field=rec.get('decoded_field') or next((k for k in ['text','raw_stdout_or_stderr','raw_utf8','stdout','stderr','content','raw'] if isinstance(obj.get(k),str)),None)
      if field is None:
       issue('unknown_decoding',doc+loc,{'path':path,'encoding':encoding,'keys':list(obj)});continue
      decoded=obj[field].encode()
     else:issue('unknown_decoding',doc+loc,{'path':path,'encoding':encoding});continue
     h.update(decoded);count=len(decoded)
    else:h.update(b);count=len(b)
    decoded_digest=decoded_digest if ('gzip' in encoding or path.endswith('.gz')) else h.hexdigest()
    record['decoded_bytes']=count;record['decoded_sha256']=decoded_digest;record['decoded_hash_match']=raw_expected is None or decoded_digest==raw_expected;record['decoded_size_match']=raw_size is None or count==raw_size
    if not record['decoded_hash_match'] or not record['decoded_size_match']:issue('decoded_mismatch',doc+loc,record)
   decoded_manifest_original=next((rec.get(k) for k in ['raw_original_path','original_scratch_path','original_path'] if isinstance(rec.get(k),str) and rec[k].endswith('.json')),None)
   if (path.endswith('.json.gz') or decoded_manifest_original) and 'decoded_sha256' in record and not record.get('historical_non_deciding'):
    decoded_key=(recsha,path+'#decoded_json')
    if decoded_key not in jsonseen:
     jsonseen.add(decoded_key)
     try:
      raw_manifest=gzip.decompress(b) if path.endswith('.gz') or 'gzip' in str(rec.get('encoding','')).lower() else decoded
      decoded_object=json.loads(raw_manifest)
     except (ValueError,UnicodeError,NameError):decoded_object=None
     if isinstance(decoded_object,(dict,list)):scan(decoded_object,recsha,path+'#decoded_json',depth+1)
   if expected is not None or size is not None or blob is not None:hash_records.append(record)
   if path.endswith('.json') and len(b)<5_000_000 and not record.get('historical_non_deciding'):parse_ref(recsha,path,depth)
  # Canonical string companion refs (API/FIT manifest pointers are ordinary strings) are opened recursively.
  for loc,path in strings(v):
   if loc in explicit_path_locations:continue
   if not path.startswith('policy-engine/') or '#' in path or '*' in path or '\n' in path:continue
   if exists(sha,path):
    referenced.append({'sha':sha,'path':path,'location':doc+loc})
    if path.endswith('.json') and len(fetch(sha,path))<5_000_000:parse_ref(sha,path,depth)
 scan(d,head,primary,0)
 for n in normalized_records:
  witnesses=[r for r in hash_records if r.get('decoded_sha256',r['sha256'])==n['raw_sha256'] and r.get('decoded_bytes',r['bytes'])==n['raw_bytes']]
  n['raw_lossless_witness_refs']=[{'sha':r['sha'],'path':r['path']} for r in witnesses]
  if not witnesses:issue('original_normalized_bytes_not_transferred',n['record_location'],n)
 caveats.extend(normalized_records)
 ids=[];decisions=[]
 for k in ['per_finding','per_id','finding_decisions','finding_outcomes','criterion_decisions','decisions']:
  c=d.get(k)
  if isinstance(c,dict):rows=[(id,x) for id,x in c.items()]
  elif isinstance(c,list):rows=[(x.get('finding_id',x.get('id',x.get('criterion_id'))),x) for x in c if isinstance(x,dict)]
  else:continue
  for id,x in rows:
   if id is None:issue('finding_id','/'+k,'row lacks recognized finding identifier');continue
   ids.append(id);decisions.append({'finding_id':id,'location':k,'check':x.get('check',x.get('native_outcome',x.get('check_outcome',x.get('outcome') if x.get('outcome') in ENUM else None))),'outcome':x.get('finding_state',x.get('state',x.get('outcome'))),'bundle_id':x.get('bundle_id')})
 current_issues=[x for x in issues if x.get('detail',{}).get('classification')!='unavailable_historical_non_deciding']
 historical_missing=[x for x in issues if x.get('detail',{}).get('classification')=='unavailable_historical_non_deciding']
 result={'component':name,'head':head,'remote_verified':remote==head,'primary':{'path':primary,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'candidate_sha':candidate,'candidate_tree_sha':tree,'base_sha':base,'ancestry':'PASS' if ancestor(base,candidate) and ancestor(candidate,head) else 'FAIL','required_primary_keys':MINIMUM,'checks_count':len(d['checks']),'check_outcome_counts':dict(collections.Counter(x.get('outcome') for x in d['checks'])),'issues':issues,'caveats':caveats,'diff_footprint':footprint,'hash_records':hash_records,'blob_source_records':blob_records,'referenced_files':referenced,'decoded_records_count':sum('decoded_sha256' in r for r in hash_records),'cached_gzip_decode_reuses':cached_gzip_reuses,'unique_git_bytes_verified':len({(r['sha'],r['path']) for r in hash_records}),'recursive_json_refs_opened':len(jsonseen),'oversized_json_refs_not_recursed':[{'sha':k[0],'path':k[1],'bytes':len(v)} for k,v in byte_cache.items() if k[1].endswith('.json') and len(v)>=5_000_000],'finding_ids':sorted(set(ids)),'finding_decisions':decisions,'bundle_ids':d['bundle_ids'],'closure_ids':d['closure_ids'],'audit_scope':'protocol/bytes/ancestry/diff/canonical mapping only; no scientific test rerun or finding closure','current_deciding_reference_check':'FAIL' if current_issues else 'PASS','all_reference_custody_check':'FAIL' if current_issues else ('UNRUN' if historical_missing else 'PASS'),'historical_unavailable_non_deciding_records':historical_missing,'check':'FAIL' if current_issues else ('UNRUN' if historical_missing else 'PASS')}
 (OUT/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'component':name,'check':result['check'],'issues':len(issues),'hash_records':len(hash_records),'decoded':result['decoded_records_count'],'finding_ids':result['finding_ids']}),flush=True)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=len(PINS)) as pool:results=list(pool.map(component,PINS.items()))
owner_text=git('show',BASE+':policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv').decode();owners=list(csv.DictReader(io.StringIO(owner_text),delimiter='\t'));frows=[r for r in owners if r.get('unit')=='F'];print('OWNER_KEYS',list(owners[0]),flush=True)
byid=collections.defaultdict(list)
for r in results:
 for id in r['finding_ids']:byid[id].append(r['component'])
expected={r.get('finding_id',r.get('id')) for r in frows};mapping={'expected_count':len(expected),'actual_count':len(byid),'expected_ids':sorted(expected),'actual_ids':sorted(byid),'missing_ids':sorted(expected-set(byid)),'extra_ids':sorted(set(byid)-expected),'duplicates':{id:names for id,names in byid.items() if len(names)!=1},'primary_owner_map':dict(byid),'finding_owners_sha':BASE,'finding_owners_path':'policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv'}
oldsha='c5cdcdf831bd9b56fb1a183c10a6417b0a8de0ff';old=json.loads(git('show',oldsha+':'+PREFIX+'graph-native-20261006.json'));old_missing=[i for i,c in enumerate(old['checks']) if not isinstance(c.get('output'),str)]
oldgraph={'sha':oldsha,'path':PREFIX+'graph-native-20261006.json','historical_check':'FAIL','missing_output_indices':old_missing,'scope':'historical exact receipt gap retained; new primarySCM9be has complete strings; local096fix is not used to make oldc5 green'}
final={'schema':'policyos.e02.protocol_byte_audit.v1','reviewer':'F/graph_scm','observed_utc':datetime.datetime.now(datetime.UTC).isoformat(),'remote_head_refs':remotes,'components':results,'mapping35':mapping,'historical_graph_receipt':oldgraph,'check':'FAIL' if any(r['issues'] for r in results) or mapping['missing_ids'] or mapping['extra_ids'] or mapping['duplicates'] else 'PASS','method':'All inputs opened as exact gitshowhead:path; every manifest-record digest/size andgzip/text wrapper decode checked; no ownerchat/ignoredscratch used as source evidence. Source equality footprints described, never P41 attributed.'}
(OUT/'F-published-protocol-audit.json').write_text(json.dumps(final,indent=2)+'\n')
lines=[f"Protocol/byte audit {final['check']}",f"9 exact heads; {sum(r['unique_git_bytes_verified'] for r in results)} per-component unique Git byte records, {sum(r['decoded_records_count'] for r in results)} decoded bodies",f"Primary mapping {mapping['actual_count']}/{mapping['expected_count']}; missing={mapping['missing_ids']} extra={mapping['extra_ids']} duplicate={mapping['duplicates']}"]
for r in results:
 lines.append(f"{r['component']} {r['head']}: {r['check']}; issues={len(r['issues'])}; ancestry={r['ancestry']}; hashes={len(r['hash_records'])}; decoded={r['decoded_records_count']}")
 for x in r['issues']:lines.append('  '+json.dumps(x))
lines.append('Historical graphc5 missingoutput: '+str(old_missing)+'; not masked by newer source.')
(OUT/'F-published-protocol-audit.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[:3]),flush=True)
