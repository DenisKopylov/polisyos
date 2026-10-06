"""Independent packet validator recomputes edge denominators and file identity."""
from pathlib import Path
import copy,hashlib,json,subprocess
O=Path(__file__).parent;R=Path('/workspace/e02-E-continuation-20261006')
def validate(d):
 assert d['schema']=='e02.E.public_surface_import_owner_packet.v1'
 actual=subprocess.check_output(['git','rev-parse',d['source_scope']['publication_companion_sha']+'^{tree}'],cwd=R,text=True).strip();assert actual==d['source_scope']['publication_companion_tree'],'candidate tree'
 rows=d['edge_symbol_owner_matrix'];original=[r for r in rows if r['scope']=='original audit12'];bkt=[r for r in rows if r['scope']=='BKT separate family delta'];frc=[r for r in rows if r['scope']=='FRC separate family delta']
 assert len(original)==12 and len(bkt)==7 and len(frc)==1
 pending=[r for r in rows if r['status']=='pending_owner_admission'];assert d['denominators']['targeted_current_pending_owner_edges']==len(pending)==14,'pending denominator'
 assert sum(r['status']=='pending_owner_admission' for r in original)==d['denominators']['original12_remaining_owner_edges']==9
 assert sum(r['status']=='resolved_existing_E_facade' for r in original)==d['denominators']['original12_resolved_edges']==3
 assert sum(r['status']=='pending_owner_admission' for r in bkt)==d['denominators']['BKT_separate_pending_owner_edges']==5
 assert d['owner_preview_native']['owner_admission']=='not_ratified','owner admission cannot be minted by library preview'
 assert d['denominators']['new_unadmitted_cross_root_module_edges']==12 and d['denominators']['E_changed_path_report_rows']==35 and d['denominators']['all_report_rows']==163
 seen=set()
 for ref in d['artifact_refs']:
  assert ref['path'] not in seen;seen.add(ref['path']);p=O/ref['path'];b=p.read_bytes();assert len(b)==ref['bytes'],('size',ref['path']);assert hashlib.sha256(b).hexdigest()==ref['sha256'],('hash',ref['path'])
 assert d['publication_companion']['candidate_sha']==d['source_scope']['publication_companion_sha'] and d['publication_companion']['verdict']=='GO'
 assert d['publication_companion']['unrelated_inventory_delta'] is False
 assert d['publication_companion']['public_surface']['polisyos.calibration']['count']==28
 assert d['publication_companion']['public_surface']['polisyos.foundry.uncertainty']['count']==16
packet=json.loads((O/'packet.json').read_text());validate(packet);controls=[]
for label,mutation in [('corrupt-hash-marker-retained',lambda d:d['artifact_refs'][0].update(sha256='0'*64)),('corrupt-size-marker-retained',lambda d:d['artifact_refs'][0].update(bytes=d['artifact_refs'][0]['bytes']+1)),('denominator-zero-marker-retained',lambda d:d['denominators'].update(targeted_current_pending_owner_edges=0)),('minted-owner-admission',lambda d:d['owner_preview_native'].update(owner_admission='ratified'))]:
 d=copy.deepcopy(packet);mutation(d)
 try:validate(d)
 except AssertionError as exc:controls.append({'name':label,'outcome':'REJECTED','reason':str(exc)})
 else:raise AssertionError('corrupt packet passed '+label)
result={'outcome':'PASS','artifact_refs_validated':len(packet['artifact_refs']),'matrix_rows_validated':len(packet['edge_symbol_owner_matrix']),'negative_controls':controls,'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(O/'packet-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
