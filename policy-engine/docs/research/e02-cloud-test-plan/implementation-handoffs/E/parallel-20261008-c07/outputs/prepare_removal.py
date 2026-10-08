import ast, hashlib, io, json, subprocess, tarfile
from pathlib import Path
scratch=Path('/dev/shm/e02-orch03-20261008/c07-checks')
root=scratch/'retained-marker-source804'
root.mkdir(exist_ok=True)
paths=['policy-engine/src','policy-engine/tests/unit/ir/test_value_subject_relation.py','policy-engine/pyproject.toml']
archive=subprocess.run(['git','archive','804a6aba31125372b0b57a10041c6d6aad375ad5',*paths],cwd='/dev/shm/e02-orch03-20261008/c07',capture_output=True,check=True)
with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tf:
    tf.extractall(root,filter='data')
p=root/'policy-engine/src/polisyos/ir/analytics/uncertainty.py'
original=p.read_text()
body=original.replace('if len(actual) != len(inputs) or sorted(actual) != sorted(expected):','if False and (len(actual) != len(inputs) or sorted(actual) != sorted(expected)):')
start=body.index('def _value_subject_unit_factor(')
end=body.index('\ndef resolve_value_subject_relation(',start)
old=body[start:end]
module=ast.parse(old)
func=module.body[0]
lines=old.splitlines(keepends=True)
# Retain original docstring, models, enum values and every diagnostic; make the actual predicate unreachable.
first=func.body[1].lineno-1
mutated=''.join(lines[:first])+'    if False:\n'+''.join('    '+line for line in lines[first:])+'    return 1.0\n\n'
body=body[:start]+mutated+body[end:]
assert original != body
for marker in ['cas_bytes_manifest_lineage_recomputed.v1','resolved_content_join_only','value_subject_quantity_mismatch','value_subject_unit_mismatch','value_subject_complete_lineage_mismatch']:
    assert marker in body
ast.parse(body)
p.write_text(body)
record={'input_sha':'804a6aba31125372b0b57a10041c6d6aad375ad5','input_tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','scope':'scratch-only deletion of runtime complete subject/unit equality and complete role-set equality; all models/provenance/authority markers and diagnostics retained; missing/duplicate subject checks still active','original_file_sha256':hashlib.sha256(original.encode()).hexdigest(),'mutated_file_sha256':hashlib.sha256(body.encode()).hexdigest(),'source_root':str(root),'mutation':'value_subject_unit_factor predicate unreachable return1; expected role-set comparison unreachable'}
(scratch/'retained-marker-mutation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
(scratch/'retained-marker.patch').write_text(subprocess.run(['diff','-u','--label','source804/uncertainty.py','--label','removed-property/uncertainty.py','/dev/shm/e02-orch03-20261008/c07/policy-engine/src/polisyos/ir/analytics/uncertainty.py',str(p)],capture_output=True,text=True).stdout)
print(json.dumps(record))
