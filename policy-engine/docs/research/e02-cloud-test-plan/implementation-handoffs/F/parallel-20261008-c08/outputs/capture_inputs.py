import gzip,hashlib,importlib.metadata,json,pathlib,platform,subprocess,sys,tomllib
root=pathlib.Path('/dev/shm/e02-orch03-20261008/c08'); pe=root/'policy-engine'; out=pathlib.Path('/dev/shm/e02-orch03-20261008/c08-scratch')
sys.path.insert(0,str(pe/'src'))
from polisyos.runtime.quality.production_invocation import _read_tree
base='f00dd7661a8d3329fb1fa1b049decb0d1d2f277b';source='2dd8339c210caf973586f7ddec69b6b0a48f1df7'
current,entries=_read_tree(pe,None);old,old_entries=_read_tree(pe,base)
inputroster={'configured_scope':'all tracked src/**/*.py, tools/**/*.py, tests/**/*.py','suffix_exclusion':'non-.py paths only','deferrals':None,'base':base,'current':source,'base_entry_points':old_entries,'current_entry_points':entries,'current_files':len(current),'base_files':len(old),'source_files':sum(p.startswith('src/') for p in current),'current_sha256':hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),'base_sha256':hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest(),'current_inputs':[{'path':p,'utf8_sig_text_sha256':hashlib.sha256(s.encode()).hexdigest()} for p,s in sorted(current.items())],'base_inputs':[{'path':p,'utf8_sig_text_sha256':hashlib.sha256(s.encode()).hexdigest()} for p,s in sorted(old.items())],'measurement':'input byte census only; scanner semantic result incomplete after signal9'}
raw=json.dumps(inputroster,indent=2).encode()+b'\n';(out/'scanner-input-denominator.json.gz').write_bytes(gzip.compress(raw,mtime=0))
summary={key:inputroster[key] for key in ['configured_scope','suffix_exclusion','deferrals','base','current','current_files','base_files','source_files','current_sha256','base_sha256','measurement']};summary['full_roster']='scanner-input-denominator.json.gz';summary['uncompressed_sha256']=hashlib.sha256(raw).hexdigest();summary['uncompressed_bytes']=len(raw)
(out/'scanner-input-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
modules=['polisyos.foundry.methods.catalog.causal._partial_graph_queries','polisyos.foundry.methods.catalog.causal.causal_engine.identification','polisyos.foundry.methods.catalog.causal.id_engine.core','polisyos.ir.analytics.causal_graph','polisyos.ir.analytics.causal','polisyos.core.artifacts.store']
origins=[]
for name in modules:
 module=__import__(name,fromlist=['x']);p=pathlib.Path(module.__file__).resolve();assert p.is_relative_to(pe/'src'),p
 origins.append({'module':name,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'git_blob':subprocess.check_output(['git','rev-parse',f'{source}:{p.relative_to(root)}'],cwd=root,text=True).strip()})
identity={'source':source,'tree':'72c482aa7d731f1adfaf703dcd6708fcccff40cd','python':sys.version,'executable':sys.executable,'platform':platform.platform(),'module_origins':origins,'distributions':sorted([{'name':d.metadata.get('Name',''),'version':d.version} for d in importlib.metadata.distributions()],key=lambda x:x['name'].lower()),'production_payload_loaded':False,'scientific_fixture_inputs':'Tracked exact test blobs; deterministic all partial profiles and explicit binary finite joint laws; metadata authority_eligible=False is scope, not admission proof'}
(out/'environment-and-origins.json').write_text(json.dumps(identity,indent=2)+'\n')
coverage=json.loads((pe/'docs/research/e02-cloud-test-plan/closure-decisions/coverage.json').read_text());bindings=[]
for row in coverage['findings']:
 if row['id'] not in ['B214','B56']:continue
 item={'finding_id':row['id'],'original_unit':row['unit'],'bundle':row['primary_bundle'],'bindings':[]}
 for ref in row['criterion_refs']:
  doc=coverage['criterion_documents'][ref['document']];rawdoc=subprocess.check_output(['git','show',doc['blob']],cwd=root);a,b=ref['lines'];card=b''.join(rawdoc.splitlines(keepends=True)[a-1:b]);actual=hashlib.sha256(card).hexdigest();assert actual==ref['sha256'],(actual,ref['sha256'])
  item['bindings'].append({**ref,'path':doc['path'],'blob':doc['blob'],'original_text':card.decode()})
 bindings.append(item)
(out/'original-criteria.json').write_text(json.dumps(bindings,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary))
