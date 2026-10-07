"""Preserve late completed helper captures as a separate additive byte carrier.
Default validates only. ROOT alone may pass --materialize and explicit destination.
Frozen main selection, main transport manifest and primary template are unchanged.
"""
from pathlib import Path
import argparse,json
from publish_transport_v5 import file_binding,verify_original,write_exact,write_json_additive,safe_target,PREFIX

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selection',type=Path,required=True);p.add_argument('--materialize',action='store_true');p.add_argument('--destination',type=Path);a=p.parse_args()
 if a.materialize and a.destination is None:p.error('--materialize requires explicit ROOT destination')
 o=json.loads(a.selection.read_bytes());rows=o['files']
 for r in rows:verify_original(r)
 frozen=o['frozen_main_selection'];assert file_binding(Path(frozen['original_path']))=={k:frozen[k] for k in ['bytes','sha256']}
 if not a.materialize:print(json.dumps({'outcome':'PASS','mode':'validation_only','complete_late_captures':len(rows),'main_selection_unchanged':True,'science_tests_run':False,'root_or_Git_writes':False},indent=2));return
 d=a.destination.resolve();mainpath=safe_target(d,PREFIX+'/artifact-transports.json');mainbinding=file_binding(mainpath);m=json.loads(mainpath.read_bytes());expected=m['frozen_publisher_input']
 assert {k:expected[k] for k in ['bytes','sha256']}=={k:frozen[k] for k in ['bytes','sha256']}
 byoriginal={r['original_path']:r for r in m['files']};byoriginal.update({r['original_path']:r for r in m['aliases']})
 existing=[]
 for e in o['already_main_transported_context']:
  assert e['original_path'] in byoriginal
  actual=byoriginal[e['original_path']];assert actual['decoded_bytes']==e['bytes'] and actual['decoded_sha256']==e['sha256']
  existing.append({'original_path':e['original_path'],'decoded_bytes':e['bytes'],'decoded_sha256':e['sha256'],'main_manifest_path':PREFIX+'/artifact-transports.json','stored_path':actual.get('path',actual.get('stored_path')),'scope':e['scope']})
 actual=[write_exact(r,d) for r in rows]
 recipe={'original_path':str(a.selection.resolve()),**file_binding(a.selection),'target_path':PREFIX+'/late-transport-validation/recipe/selection.json','encoding':'identity','role':'Exact frozen late-capture plan; output manifest binds it without recursive self-hash.'}
 actual.append(write_exact(recipe,d))
 manifest={'schema':'policyos.e02.complete_late_transport_validation.v1','files':actual,'already_main_transported_context':existing,'main_artifact_transports':{'path':PREFIX+'/artifact-transports.json',**mainbinding},'frozen_main_selection':{'path':expected['path'],'bytes':expected['bytes'],'sha256':expected['sha256']},'scope':'Completed exact final byte-custody refresh and validation captures; original ERROR preserved. No scientific PASS, source changes, new admissions or finding closure. Main selection/manifest and input primary template untouched.','sanitation':'none; complete byte-exact identity or lossless gzip; original files remain unchanged.','science_tests_run':False,'Git_writes':False,'counts':{'complete_late_capture_files':len(actual),'stored_bytes':sum(r['bytes'] for r in actual),'decoded_bytes':sum(r['decoded_bytes'] for r in actual)}}
 target=safe_target(d,PREFIX+'/late-transport-validation/outputs.json');b=write_json_additive(target,manifest)
 print(json.dumps({'mode':'materialized_exact_bytes','outputs':{'path':str(target),'committed_relative_path':PREFIX+'/late-transport-validation/outputs.json',**b},'counts':manifest['counts'],'ROOT_primary_additive_field':{'late_transport_validation':{'path':PREFIX+'/late-transport-validation/outputs.json',**b}},'main_selection_manifest_primary_template_unchanged':True,'Git_writes':False,'science_tests_run':False},indent=2))
if __name__=='__main__':main()
