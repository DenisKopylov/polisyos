from pathlib import Path
import subprocess,json,hashlib,gzip
R=Path('/workspace/e02-F-graph-20261006');O=Path('/tmp/e02-F-continuation-20261007/graph/root519-G855-review')
ROOT='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'; G='855cb26a7a2c9fea60356663cf81e7d01e20c738'; OWN='ffae9fa4b45c23c3d2dca5c1bbf78d18418a7634'; V='9ac56f67695e9244a55c2c8a63c77263808a0588'; B='363e7ae0cb2929a92d9667334fdc0ac3087daf5e';P='policy-engine/'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def blob(s,p):return git('show',s+':'+p)
def tree(s):
 rows={}
 for b in git('ls-tree','-r','-z',s).split(b'\0'):
  if b:
   meta,p=b.split(b'\t',1);m,t,h=meta.decode().split();rows[p.decode()]={'mode':m,'type':t,'blob':h}
 return rows
def ref(s,p):
 b=blob(s,p);return {'git_ref':s,'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':git('rev-parse',s+':'+p).decode().strip()}
T={s:tree(s) for s in [ROOT,G,OWN,V,B]}
source_prefixes=[P+'src/',P+'tools/',P+'workers/',P+'architecture/',P+'schemas/',P+'data/dataset_catalog/']
source_singletons={P+x for x in ['hatch.toml','pyproject.toml','uv.lock','.python-version']}
def selected(p):return p in source_singletons or any(p.startswith(z) for z in source_prefixes)
audit={'schema':'policyos.e02.readonly.source_comparison.v1','refs':{s:git('rev-parse',s+'^{tree}').decode().strip() for s in [ROOT,G,OWN,V,B]},'pairs':[],'components':[],'ancestry':[],'scope':'Git source/material-byte identity review only; no numerical test replay, no G acceptance'}
for a,b,label in [(OWN,ROOT,'own published→root519'),(ROOT,V,'root519→virtualmerge'),(B,G,'mergebase→G855')]:
 paths=sorted(set(T[a])|set(T[b]));den=[p for p in paths if selected(p)];changed=[p for p in den if T[a].get(p)!=T[b].get(p)]
 rows=[{'path':p,'before':T[a].get(p),'after':T[b].get(p)} for p in den]
 fullchanged=[p for p in paths if T[a].get(p)!=T[b].get(p)]
 audit['pairs'].append({'label':label,'a':a,'b':b,'selection':source_prefixes+sorted(source_singletons),'selected_path_denominator':len(den),'selected_changed_paths':changed,'all_changed_path_denominator':len(fullchanged),'all_changed_paths':fullchanged,'all_selected_bindings':rows})
for impl in ['647f5d35362c2a5d7ad32283b804a5b03ea56e83','81f482e04bd8a2c85f894d425847c6e8657b6ea6',OWN,G]:
 r=subprocess.run(['git','merge-base','--is-ancestor',impl,ROOT],cwd=R)
 audit['ancestry'].append({'ancestor':impl,'descendant':ROOT,'returncode':r.returncode,'ancestor_established':r.returncode==0})
for name in ['graph-intake-current-content-20261007','catalog-default-resources-20261007']:
 rp=P+'docs/research/e02-cloud-test-plan/implementation-handoffs/F/'+name+'.json'
 d=json.loads(blob(OWN,rp)); m=d['evidence_transfer']['full_output_manifest'];mf=json.loads(blob(OWN,m['path']))
 current_source=d['candidate_sha'];paths=d['changed_paths'][:]
 if name.startswith('catalog'):
  paths+= [P+'data/dataset_catalog/'+n for n in ['seed_variable_alignments.yaml','proxy_metric_alignments.yaml','wvs_indicator_registry.yaml','metrics_map.yaml']]
 source_rows=[]
 for p in paths:
  x=ref(current_source,p); y=ref(ROOT,p); source_rows.append({'path':p,'source':x,'root':y,'byte_identical':x['sha256']==y['sha256'] and x['bytes']==y['bytes']})
 material=[]
 for f in mf['files']:
  p=f['path']; x=blob(OWN,p); y=blob(ROOT,p)
  row={'path':p,'expected_bytes':f['bytes'],'expected_sha256':f['sha256'],'own':ref(OWN,p),'root':ref(ROOT,p),'valid_expected_bytes':len(y)==f['bytes'] and hashlib.sha256(y).hexdigest()==f['sha256'],'byte_identical':x==y}
  if p.endswith('.gz'):
   decoded=gzip.decompress(y);row['decoded_bytes']=len(decoded);row['decoded_sha256']=hashlib.sha256(decoded).hexdigest();row['decoded_byte_identical']=decoded==gzip.decompress(x)
   for k in ['decoded_bytes','decoded_sha256','decompressed_bytes','decompressed_sha256','original_bytes','original_sha256']:
    if k in f:row['manifest_'+k]=f[k]
  material.append(row)
 cr={'name':name,'primary_own':ref(OWN,rp),'primary_root':ref(ROOT,rp),'primary_byte_identical':blob(OWN,rp)==blob(ROOT,rp),'candidate_sha':current_source,'candidate_tree':git('rev-parse',current_source+'^{tree}').decode().strip(),'manifest_binding':m,'manifest_own':ref(OWN,m['path']),'manifest_root':ref(ROOT,m['path']),'source_bindings':source_rows,'material_bindings':material,'material_count':len(material),'material_all_valid':all(z['valid_expected_bytes'] and z['byte_identical'] for z in material),'source_all_identical':all(z['byte_identical'] for z in source_rows)}
 audit['components'].append(cr)
audit['check']='PASS' if all(x['material_all_valid'] and x['source_all_identical'] and x['primary_byte_identical'] for x in audit['components']) and not audit['pairs'][0]['selected_changed_paths'] and not audit['pairs'][1]['selected_changed_paths'] else 'FAIL'
(O/'source-input-comparison.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'check':audit['check'],'pairs':[{k:v for k,v in x.items() if k not in ['all_selected_bindings','all_changed_paths']} for x in audit['pairs']],'components':[{k:v for k,v in x.items() if k not in ['source_bindings','material_bindings']} for x in audit['components']],'ancestry':audit['ancestry']},ensure_ascii=False,indent=2))
