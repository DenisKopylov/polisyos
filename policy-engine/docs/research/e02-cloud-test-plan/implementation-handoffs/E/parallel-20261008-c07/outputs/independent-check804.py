import hashlib, importlib.util, json, os, time
from pathlib import Path
from fractions import Fraction
from polisyos.ir.analytics.uncertainty import (
 load_value_subject_relation, resolve_value_subject_relation, persist_value_subject_relation,
 load_uncertainty_envelope
)
from polisyos.ir.registry.refs import ValueSubjectRelationRef, ArtifactRefModel
from polisyos.ir.artifacts import InputRef, put_json_artifact, get_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
root=Path('/dev/shm/e02-orch03-20261008/oracle-ir')
spec=importlib.util.spec_from_file_location('fixture804',root/'source804/policy-engine/tests/unit/ir/test_value_subject_relation.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
results=[]
def check(name,fn):
 start=time.monotonic()
 try:
  detail=fn(); results.append({'name':name,'outcome':'PASS','detail':detail,'wall_s':time.monotonic()-start})
 except Exception as exc:
  results.append({'name':name,'outcome':'FAIL','type':type(exc).__name__,'detail':str(exc),'wall_s':time.monotonic()-start})
def positive():
 from polisyos.ir.kernel.units import RateUnit
 from polisyos.core.artifacts.store import FileSystemCAS
 store,subject,ir,nr=fixture._producer_pair(root/'cas804_positive',native_changes={'unit':RateUnit(base='ratio')})
 rr=persist_value_subject_relation(store,identification_ref=ir,native_uncertainty_ref=nr)
 relation=load_value_subject_relation(FileSystemCAS(store.root),rr)
 native=load_uncertainty_envelope(FileSystemCAS(store.root),nr)
 expected=[Fraction(1),Fraction(10)]
 got=[Fraction(str(v))*Fraction(str(relation.native_to_identification_factor)) for v in native.confidence_interval]
 assert got==expected
 assert Fraction(str(native.point_estimate))*Fraction(str(relation.native_to_identification_factor))==4
 assert relation.production_value_eligible is False
 assert get_json_artifact(store,ir.artifact_id)['lower']==[4.0]
 return {'factor':relation.native_to_identification_factor,'native_ci':native.confidence_interval,'identification_ref':str(ir.artifact_id),'native_ref':str(nr.artifact_id),'authority':relation.production_value_eligible}
check('independent_fraction_rate_conversion_and_reopen',positive)
for name,changes in [('foreign_time',{'time_horizon':'other-horizon'}),('foreign_contrast',{'control_value':9.0}),('foreign_population',{'population':'other-population'})]:
 def negative(n=name,c=changes):
  store,_,ir,nr=fixture._producer_pair(root/('cas804_'+n),native_changes=c)
  try: resolve_value_subject_relation(store,identification_ref=ir,native_uncertainty_ref=nr)
  except ValueError as exc:
   assert 'value_subject_quantity_mismatch' in str(exc);return {'refusal':str(exc)}
  raise AssertionError('foreign resolved subject accepted')
 check(name,negative)
for change in ('missing','extra','duplicate'):
 def negative(c=change):
  store,_,ir,nr=fixture._producer_pair(root/('cas804_roster_'+c),lineage_change=c)
  try: persist_value_subject_relation(store,identification_ref=ir,native_uncertainty_ref=nr)
  except ValueError as exc:
   assert 'value_subject_' in str(exc);return {'refusal':str(exc)}
  raise AssertionError('incomplete/overcomplete producer roster accepted')
 check('roster_'+change,negative)
print(json.dumps({'source':'804a6aba31125372b0b57a10041c6d6aad375ad5','tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','pid':os.getpid(),'scope':'non-author review probes; author fixture only producer setup, Fraction oracle independent; not actual C10 ValuePort or scientific authority','results':results},indent=2))
raise SystemExit(any(r['outcome']!='PASS' for r in results))
