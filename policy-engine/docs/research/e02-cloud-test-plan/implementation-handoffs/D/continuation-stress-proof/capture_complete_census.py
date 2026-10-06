"""Read every received byte and row; output compact D ownership/source locators."""
import collections, csv, hashlib, importlib.util, json, pathlib, subprocess
repo=pathlib.Path('/workspace/e02-D-published-stress')
base=repo/'policy-engine/docs/research/e02-cloud-test-plan'; pack=base/'results'
sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
def digest(data): return hashlib.sha256(data).hexdigest()
def table(path):
 data=path.read_bytes(); return list(csv.DictReader(data.decode().splitlines(),delimiter='\t'))
def binding(path):
 data=path.read_bytes();return {'path':str(path.relative_to(repo)),'source_sha':sha,'sha256':digest(data),'bytes':len(data)}
def locator(path,start,end):
 lines=path.read_bytes().splitlines(keepends=True);offsets=[0]
 for line in lines:offsets.append(offsets[-1]+len(line))
 return {'path':str(path.relative_to(repo)),'lines':[start,end],'bytes':[offsets[start-1],offsets[end]],'source_sha256':digest(path.read_bytes())}
spec=importlib.util.spec_from_file_location('e02_import',pack/'import_results.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
# Rebuild checks walk every full received text, primary row, property, gate and event.
rebuilt=reader.generate(pack)
assert all((pack/name).read_text()==data for name,data in rebuilt.items())
owners=table(base/'execution-organization/finding-owners.tsv'); all_bundles=table(base/'execution-organization/bundle-owners.tsv')
d_owners=[x for x in owners if x['unit']=='D']; d_bundles=[x for x in all_bundles if x['unit']=='D']; ids={x['finding_id'] for x in d_owners}
cells=table(pack/'cells.tsv'); properties=table(pack/'properties.tsv'); all_routes=table(pack/'routes.tsv'); routes=[x for x in all_routes if x['finding_id'] in ids]
assert all(x['unit']=='D' for x in routes)
cellmap={x['id']:x for x in cells}; selected_ids={x['cell_id'] for x in routes}; selected=[cellmap[x] for x in sorted(selected_ids)]
events=[json.loads(line) for line in (pack/'events.jsonl').read_text().splitlines()]; seeds=json.loads((pack/'sources.json').read_text())['sources']
verification=json.loads((pack/'verification.json').read_text());coverage=json.loads((base/'closure-decisions/coverage.json').read_text());criteria={x['id']:x for x in coverage['findings']}
old=json.loads((base/'implementation-handoffs/D/baseline-map.json').read_text())
assert set(old['cells'])==selected_ids and set(old['findings'])==ids
jobs={};all_source_blocks=0
for seed in seeds:
 path=pack/seed['path'];data=path.read_bytes();assert len(data)==seed['bytes'] and digest(data)==seed['sha256']
 blocks=reader.json_blocks(data.decode());all_source_blocks+=len(blocks)
 metadata=[(a,b,x) for a,b,x,_ in blocks if isinstance(x,dict) and str(x.get('job','')).endswith(seed['job'])]
 first=metadata[0][2];env=first.get('environment') or {};files=first.get('text_file_sha256') or {}
 job=seed['job'];source=first.get('source',first.get('source_sha'));assert source==old['jobs'][job]['source_sha']
 jobs[job]={'source_sha':source,'source_tree':first['tree'],'received_source':binding(path),'metadata_locators':[locator(path,a,b) for a,b,_ in metadata],'environment_basis':'consumer_asserted','reported_environment':{key:env.get(key,'not_established') for key in ['python','platform','arch','JAX_PLATFORMS']},'selected_extras':first.get('selected_extras','not_established'),'backend_versions_and_actual_GP_exercise':'not_established','environment_archive_ref':{'reported_sha256':files.get('environment.json'),'received':False},'input_archive_ref':{'reported_sha256':files.get('source-inputs.json'),'received':False},'complete_fixture_input_identity':'not_established','raw_archive_received':False}
rows=[]
for cell in selected:
 previous=old['cells'][cell['id']]
 assert all(cell[k]==previous[v] for k,v in [('source_sha','source_sha'),('job','job'),('path','path'),('state','reported_state'),('receipt_status','reported_receipt_status')])
 path=pack/cell['source_file'];line=int(cell['source_line']);loc=locator(path,line,line)
 assert loc['bytes']==previous['source_row']['bytes']
 rows.append({'id':cell['id'],'job':cell['job'],'source_sha':cell['source_sha'],'path':cell['path'],'reported_state':cell['state'],'reported_receipt_status':cell['receipt_status'],'source_row':loc,'environment_backend_input_identity_ref':'#/jobs/'+cell['job'],'full_event_locator_ref':{'path':str((base/'implementation-handoffs/D/baseline-map.json').relative_to(repo)),'source_sha':sha,'json_pointer':'/cells/'+cell['id']+'/event_locators'}})
findings=[];occurrences=0
for owner in d_owners:
 fid=owner['finding_id'];canonical=criteria[fid];assert owner['source_closure_owner']==canonical['source_closure_owner_literal'];refs=[]
 for ref in canonical['criterion_refs']:
  doc=coverage['criterion_documents'][ref['document']];path=repo/doc['path'];start,end=ref['lines'];text=b''.join(path.read_bytes().splitlines(keepends=True)[start-1:end]);assert digest(text)==ref['sha256'];assert subprocess.check_output(['git','-C',str(repo),'rev-parse',coverage['runtime_source']+':'+doc['path']],text=True).strip()==doc['blob']
  refs.append({'bundle':ref['card'],'document_source_sha':coverage['runtime_source'],'document_blob':doc['blob'],'criterion_sha256':ref['sha256'],'source_locator':locator(path,start,end)});occurrences+=1
 related=[x for x in routes if x['finding_id']==fid]
 findings.append({'finding_id':fid,'canonical_closure_owner':owner['source_closure_owner'],'bundle_ids':canonical['companion_bundles'],'task_anchors':canonical['task_refs'],'criterion_occurrences':refs,'candidate_cell_ids':sorted({x['cell_id'] for x in related}),'route_rows':len(related),'canonical_selected_route_ref':{'path':str((base/'closure-decisions/coverage.json').relative_to(repo)),'source_sha':sha,'json_pointer':'/findings/'+str(coverage['findings'].index(canonical))+'/selected_plan_not_executed'},'historical_ledger_status':owner['source_status'],'route_grade':'candidate_unverified','product_closure':'not_established'})
relevant_events=[x for x in events if selected_ids.intersection(x.get('cell_ids',[]))]
assert (len(d_owners),len(d_bundles),len(routes),len(selected),occurrences)==(45,17,456,115,46)
report={'schema':'policyos.e02.D.continuation.complete_result_pack_census.v1','source_sha':sha,'predicate_basis':'independently_reconciled','predicate_scope':'Complete received-byte/hash/index/ownership/criterion-locator join; historical behavior is source-reported, not new runtime or closure.','original_acceptance_binding':{'path':str((pack/'verification.json').relative_to(repo)),'source_sha':sha,'sha256':digest((pack/'verification.json').read_bytes()),'index_acceptance':verification['index_acceptance'],'product_closure':verification['product_closure']},'denominator':{'all_received_sources':len(seeds),'all_received_bytes':sum(x['bytes'] for x in seeds),'all_parsed_json_blocks':all_source_blocks,'all_primary_cells':len(cells),'all_property_states':len(properties),'all_event_locators':len(events),'all_routes':len(all_routes),'all_finding_owner_rows':len(owners),'all_bundle_owner_rows':len(all_bundles),'D_findings':len(ids),'D_bundles':len(d_bundles),'D_criterion_occurrences':occurrences,'D_routes':len(routes),'D_distinct_primary_cells':len(selected),'D_reported_states':dict(collections.Counter(x['state'] for x in selected)),'D_relevant_event_locators':len(relevant_events),'D_routed_property_states':len({x['id'] for x in properties}.intersection(selected_ids))},'inputs':[binding(base/'execution-organization'/n) for n in ['finding-owners.tsv','bundle-owners.tsv']]+[binding(pack/n) for n in ['README.md','sources.json','cells.tsv','properties.tsv','events.jsonl','routes.tsv','verification.json','gates.json']]+[binding(base/'closure-decisions/coverage.json'),binding(base/'implementation-handoffs/D/baseline-map.json')],'D_bundles':d_bundles,'jobs':jobs,'cells':rows,'findings':findings,'preserved_ownership_exception':{'finding_id':'LA-015','occurrences':['CTL-01','SRV-03'],'canonical_closure_owner':'SRV-03','CTL-01_role':'supplier companion only'},'complete_deciding_source_locator_ref':{'path':str((base/'implementation-handoffs/D/baseline-map.json').relative_to(repo)),'source_sha':sha,'json_pointer':'/deciding_blocks'},'limitations':['No raw VM archives received; metadata environment/source-input hashes do not supply those bytes.','Routed PASS/FAIL and receipt_status remain source assertions; semantic adequacy, production acceptance and finding closure not established.','No inherited-red attribution: exact base/environment/command/full-input disjointness is not established by this inventory.','Historical source cuts are not independent witnesses. Current authored stress mechanism receives independent review separately.']}
# Reuse existing exact, verified cell/event inventory; do not duplicate raw tables.
report['reference_documents']={name:binding(path) for name,path in [('baseline_map',base/'implementation-handoffs/D/baseline-map.json'),('canonical_coverage',base/'closure-decisions/coverage.json')]}
report['criterion_documents']={key:{'path':obj['path'],'source_sha':coverage['runtime_source'],'blob':obj['blob'],'sha256':digest((repo/obj['path']).read_bytes())} for key,obj in coverage['criterion_documents'].items()}
report['locator_convention']='UTF-8 bytes zero-based [start,end); lines one-based inclusive. Cell path/receipt/event refs resolve in reference_documents.baseline_map; canonical route pointers resolve in reference_documents.canonical_coverage, never this document.'
report['cells']=[{'id':x['id'],'reported_state':x['reported_state'],'source_sha':x['source_sha'],'job_profile':x['job'],'source_line':x['source_row']['lines'][0],'source_byte_range':x['source_row']['bytes'],'baseline_map_pointer':'/cells/'+x['id']} for x in rows]
for item in report['findings']:
 fid=item['finding_id'];canonical=criteria[fid]
 item['criterion_occurrences']=[{'bundle':ref['card'],'document':ref['document'],'lines':ref['lines'],'bytes':locator(repo/coverage['criterion_documents'][ref['document']]['path'],*ref['lines'])['bytes'],'criterion_sha256':ref['sha256']} for ref in canonical['criterion_refs']]
 item['canonical_selected_route_pointer']=item.pop('canonical_selected_route_ref')['json_pointer']
report['complete_deciding_source_locator_ref']={'document':'baseline_map','json_pointer':'/deciding_blocks'}
out=base/'implementation-handoffs/D/continuation/complete-result-pack-census.json';out.write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'output':str(out.relative_to(repo)),'sha256':digest(out.read_bytes()),'bytes':out.stat().st_size,'denominator':report['denominator']}))
