from pathlib import Path
import json,hashlib,subprocess,gzip
D=Path('/tmp/e02-F-continuation-20261007/graph/root519-G855-review');R=Path('/workspace/e02-F-graph-20261006');d=json.loads((D/'source-input-comparison-v2.json').read_text());
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
for pair in d['pairs']:
 rows=[x for x in pair['all_selected_bindings'] if not x['path'].endswith('.md')]
 pair['runtime_code_data_config_denominator']=len(rows);pair['runtime_code_data_config_changed_paths']=[x['path'] for x in rows if x['before']!=x['after']];pair['documentation_changed_paths']=[p for p in pair['selected_changed_paths'] if p.endswith('.md')]
d['runtime_source_identity_check']='PASS' if all(not x['runtime_code_data_config_changed_paths'] for x in d['pairs'][:2]) else 'FAIL'
d['root_contains_complete_resource_handoff']='FAIL' if not d['components'][1]['material_all_valid'] or d['components'][1]['primary_root'] is None else 'PASS'
d['root_local_material_custody_check']='FAIL' if d['root_contains_complete_resource_handoff']=='FAIL' else 'PASS'
missing=[x['path'] for x in d['components'][1]['material_bindings'] if x['root'] is None];d['resource_material_missing_at_root']=missing;d['resource_material_missing_count']=len(missing)
rawbindings=[]
for c in d['components']:
 rp=c['primary_own']['path'];sha=c['primary_own']['git_ref'];receipt=json.loads(git('show',sha+':'+rp));mf=receipt['evidence_transfer']['full_output_manifest'];full=json.loads(git('show',sha+':'+mf['path']))
 for row in full['files']:
  p=row['path'];b=git('show',sha+':'+p);v={'path':p,'carrier':sha,'stored_bytes':len(b),'stored_sha256':hashlib.sha256(b).hexdigest(),'stored_declared_match':len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],'decode_check':'not_encoded'}
  if p.endswith('.gz'):
   x=gzip.decompress(b);v['decoded_bytes']=len(x);v['decoded_sha256']=hashlib.sha256(x).hexdigest();dc=row.get('decompressed_bytes',row.get('decoded_bytes'));dh=row.get('decompressed_sha256',row.get('decoded_sha256'))
   v['decoded_declaration']={'bytes':dc,'sha256':dh};v['decode_check']='PASS' if (dc is None or dc==len(x)) and (dh is None or dh==v['decoded_sha256']) else 'FAIL'
  rawbindings.append(v)
d['published_stored_decoded_material_bindings']=rawbindings;d['published_component_custody_check']='PASS' if all(x['stored_declared_match'] and x['decode_check']!='FAIL' for x in rawbindings) else 'FAIL';d['published_material_count']=len(rawbindings);d['published_gzip_count']=sum(x['decode_check']!='not_encoded' for x in rawbindings)
d['metadata_reconciliation']='v2 selected source-prefix README was intentionally included in broader path selection; final runtime/code/data/config classification excludes only documentation .md. Original v2 broad differences preserved; no scientific test failures relabelled.'
(D/'source-input-comparison-final.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
summary={'runtime_source_identity_check':d['runtime_source_identity_check'],'root_contains_complete_resource_handoff':d['root_contains_complete_resource_handoff'],'published_component_custody_check':d['published_component_custody_check'],'root_missing_resource_material':len(missing),'published_material':len(rawbindings),'gzip':d['published_gzip_count'],'pairs':[{k:x[k] for k in ['label','selected_path_denominator','runtime_code_data_config_denominator','runtime_code_data_config_changed_paths','documentation_changed_paths']} for x in d['pairs']]}
print(json.dumps(summary,ensure_ascii=False,indent=2))
