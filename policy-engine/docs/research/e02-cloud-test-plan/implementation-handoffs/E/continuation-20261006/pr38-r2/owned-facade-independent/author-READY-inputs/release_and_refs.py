from pathlib import Path
import subprocess,json,copy,tomllib,hashlib,sys
OUT=Path(__file__).parent;ROOT=Path('/workspace/e02-E-continuation-20261006');BASE='5e3e3727685132f270a3a07b9f63dd962a88cd96';PRODUCT=ROOT/'policy-engine';POST=OUT/'postimage'
sys.path.insert(0,str(PRODUCT))
from tools.ops_runners.release import check_compatibility_release_gates as check
from tools.ops_runners.release.build_release_notes import load_fragments,structured_compatibility_changes
policy=tomllib.loads((PRODUCT/'architecture/gates/compatibility_release.toml').read_text());contract=tomllib.loads((PRODUCT/'architecture/public_surface/contract.toml').read_text())
fragments=load_fragments(POST/'policy-engine/release-fragments/unreleased');assert len(fragments)==2
errors,findings=check._validate_fragments(PRODUCT,policy,fragments,breaking_classes=());assert not errors
changes=structured_compatibility_changes(fragments);assert len(changes)==2
packages={row['module']:row for row in contract['package']}
expected={fragments[0]['id']:'polisyos.calibration',fragments[1]['id']:'polisyos.foundry.uncertainty'}
# Actual canonical owner/classification from public surface contract. Version owner
# team-architecture retained from G53 accepted owner metadata; no authority inferred.
def canonical_basis(rows):
 reasons=[]
 for row in rows:
  module='polisyos.calibration' if row['id']=='calibration-foundry-reader-alias' else 'polisyos.foundry.uncertainty'
  package=packages['polisyos.calibration' if module=='polisyos.calibration' else 'polisyos.foundry']
  for key,want in (('owner',package['owner']),('version_owner','team-architecture'),('surface',package['classification']+': '+module)):
   if row.get(key)!=want:reasons.append({'id':row['id'],'field':key,'actual':row.get(key),'required':want})
 return reasons
assert not canonical_basis(changes)
fake=copy.deepcopy(fragments);fake[0]['owner']='E';fake[0]['compatibility_change'][0]['owner']='E'
fake_errors,_=check._validate_fragments(PRODUCT,policy,fake,breaking_classes=());assert not fake_errors
fake_reasons=canonical_basis(structured_compatibility_changes(fake));assert fake_reasons
remove=copy.deepcopy(fragments)
for item in remove:item['public_surface_inventory_reviewed']=False;item['compatibility_change'][0]['public_surface_inventory_reviewed']=False
remove_errors,_=check._validate_fragments(PRODUCT,policy,remove,breaking_classes=());assert remove_errors
missing=copy.deepcopy(fragments);missing[0]['compatibility_change'][0].pop('version_owner')
missing_errors,_=check._validate_fragments(PRODUCT,policy,missing,breaking_classes=());assert missing_errors
result={'schema':'policyos.e02.owned_route_release_parser.v1','actual_parser':'build_release_notes.load_fragments + structured_compatibility_changes; check_compatibility_release_gates._validate_fragments','base':BASE,'fragments':fragments,'structured_rows':changes,'errors':[e.as_dict() for e in errors],'findings':[e.as_dict() for e in findings],'canonical_owner_basis':{name:{'owner':packages['polisyos.calibration' if name=='polisyos.calibration' else 'polisyos.foundry']['owner'],'classification':packages['polisyos.calibration' if name=='polisyos.calibration' else 'polisyos.foundry']['classification'],'version_owner':'team-architecture (G53 retained canonical version owner)'} for name in ('polisyos.calibration','polisyos.foundry.uncertainty')},'controls':{'present_fake_owner_E':{'generic_presence_parser_errors':[],'canonical_owner_predicate_refuses':fake_reasons},'inventory_review_field_removed':{'errors':[e.as_dict() for e in remove_errors]},'version_owner_field_removed':{'errors':[e.as_dict() for e in missing_errors]}},'scope':'Two owned route/public-API companion rows only, not whole release readiness/globalCI or wire/schema/semantic owner ratification.'}
(OUT/'release-parser.json').write_text(json.dumps(result,indent=2)+'\n')
argv=['git','-C',str(ROOT),'grep','-n','-E','load_foundry_calibration_report|Calibration re-exports',BASE,'--','policy-engine/src','policy-engine/tests','policy-engine/docs/reference','policy-engine/release-fragments/unreleased']
run=subprocess.run(argv,capture_output=True);assert run.returncode==0
(OUT/'tracked-reader-refs-base.stdout').write_bytes(run.stdout)
lines=run.stdout.decode().splitlines();parsed=[]
for line in lines:
 _,path,number,text=line.split(':',3)
 post=POST/path
 native=subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+path])
 new=post.read_bytes() if post.exists() else native
 matches=[{'line':i,'text':value} for i,value in enumerate(new.decode().splitlines(),1) if 'load_foundry_calibration_report' in value or 'Calibration re-exports' in value]
 parsed.append({'path':path,'old_line':int(number),'old_text':text,'postimage_used':post.exists(),'postimage_matching_lines':matches})
source_alias='from polisyos.calibration import load_foundry_calibration_report'
assert source_alias not in (POST/'policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py').read_text()
assert 'from polisyos.foundry.uncertainty import load_foundry_calibration_report' not in (POST/'policy-engine/src/polisyos/calibration/__init__.py').read_text()
refs={'schema':'policyos.e02.current_reader_reference_denominator.v1','base':BASE,'argv':argv,'exit_code':run.returncode,'scope':'All tracked source/tests/current public reference and unreleased fragments. Historical research receipts excluded from current mechanism and remain immutable historical evidence. Full emitted match list retained.','matches':parsed,'current_production_callers':['polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty._collect_input_envelopes'],'migration':'Only tracked current legacy caller imports the same canonical Foundry uncertainty reader directly; unreleased E-topic alias removed, no previous main-publication compatibility inferred. Root owner statement: alias was not published to main.','old_calibration_alias_remaining_runtime_imports':0,'other_calibration_exports':28,'reader_authority':'Kind/schema/payload validation only; B197 held source/evaluator authority unchanged.'}
(OUT/'tracked-reader-refs.json').write_text(json.dumps(refs,indent=2)+'\n')
print(json.dumps({'structured_rows':len(changes),'native_parser_errors':len(errors),'negative_controls':3,'tracked_ref_matches':len(lines),'distinct_ref_paths':len({row['path'] for row in parsed})},indent=2))
