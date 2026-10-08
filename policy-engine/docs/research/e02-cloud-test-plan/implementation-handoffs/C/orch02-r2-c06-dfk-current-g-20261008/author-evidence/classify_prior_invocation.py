"""Stream the original complete static receipt; retain exact DFK-related records."""
from __future__ import annotations
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path('/workspace/orch02-c06-dfk/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/orch02-c06-dfk-recovery-20261008')
SOURCE=ROOT/'required-gates/invocation-initial/receipt.json.gz'
OUT=Path('/workspace/orch02-r2/c06-dfk')
prefixes=('src/polisyos/data_forge/kernel/schemas/', 'src/polisyos/data_forge/kernel/pipeline/',
          'src/polisyos/foundry/domain/', 'src/polisyos/foundry/agent_sim/')
counts=Counter(); selected={}; pieces=[]; name=None; in_mechanisms=False
raw_digest=hashlib.sha256(); raw_bytes=0
with gzip.open(SOURCE,'rb') as stream:
 for raw_line in stream:
  raw_digest.update(raw_line);raw_bytes+=len(raw_line);line=raw_line.decode()
  if line=='  "mechanisms": {\n':
   in_mechanisms=True;continue
  if in_mechanisms and line.startswith('    "') and line.rstrip().endswith(': {'):
   name=json.loads(line.split(': {',1)[0].strip());pieces=['{\n'];continue
  if in_mechanisms and name is not None:
   if line.startswith('    }'):
    pieces.append('}\n');entry=json.loads(''.join(pieces));counts[entry['status']]+=1
    if entry['path'].startswith(prefixes):selected[name]=entry
    name=None;pieces=[]
   else:pieces.append(line)
  elif in_mechanisms and line=='  },\n':in_mechanisms=False
assert not in_mechanisms and name is None
result={'schema':'policyos.orch02.r2.c06.dfk.prior-invocation-classification.v1',
 'counterexample':'A dynamically registered or test-only caller can have no resolved direct production path while still being executable; static status is not runtime absence.',
 'original_commit':'cbbfffd367fe283813a8177575d26c0ede8d20c4','original_receipt_path':str(SOURCE),
 'compressed_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'decoded_sha256':raw_digest.hexdigest(),'decoded_bytes':raw_bytes,
 'complete_mechanism_status_denominator':dict(counts),'complete_mechanism_count':sum(counts.values()),
 'selected_path_prefixes':prefixes,'exact_DFK_related_mechanisms':selected,
 'classification':'Existing static unresolved records preserve their original caller and indirect-boundary evidence. No source defect, absence or current-G status inferred.',
 'current_G_new_src_paths':[],'current_G_pyproject_changed':False,
 'new_tool_call_chain':['tools.cli._run_registered_tool','tools.lib.runner.invoke_tool_main','tools.quality.validation.schema_fqn_census.main','tools.quality.validation.schema_fqn_census.collect_census'],
 'dynamic_seam':'invoke_tool_main imports ToolSpec.module then calls getattr(module, callable_name)(args); actual canonical CLI positive exercises this finite seam.',
 'full_current_G_diagnostic':'Separate newly changed-input run; never substituted by this historical classification.',
 'source_acceptance':'not_admitted_by_G','formal_closure_ids':[]}
(OUT/'prior-invocation-classification.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
print(json.dumps({'complete_mechanisms':sum(counts.values()),'DFK_related':len(selected),'statuses':dict(counts)}))
