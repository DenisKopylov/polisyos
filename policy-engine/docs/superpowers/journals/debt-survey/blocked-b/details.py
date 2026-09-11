"""Exact supplemental evidence not implied by AST symbol searches."""
import ast
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('survey_tree', HERE.parent/'open/inspect_tree.py')
own=importlib.util.module_from_spec(spec);spec.loader.exec_module(own)
mode=sys.argv[1]
paths=own.tracked()
if mode=='growth':
 p='architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json'
 obj=json.loads((own.ROOT/p).read_text())
 found=[]
 def walk(value, pointer=''):
  if isinstance(value,dict):
   if 'voi_owner_fit' in value: found.append((pointer,value))
   for k,v in value.items():walk(v,pointer+'/'+k)
  elif isinstance(value,list):
   for i,v in enumerate(value):walk(v,pointer+'/'+str(i))
 walk(obj)
 # Independent textual decoder walk using object_pairs_hook, preserves each object identity.
 pairs=json.loads((own.ROOT/p).read_text(),object_pairs_hook=lambda pairs: ('OBJECT',pairs))
 second=[]
 def pairs_walk(v):
  if isinstance(v,tuple) and len(v)==2 and v[0]=='OBJECT':
   d=dict(v[1])
   if 'voi_owner_fit' in d:second.append((d['variable_id'],d['voi_owner_fit']))
   for _,child in v[1]:pairs_walk(child)
  elif isinstance(v,list):
   for child in v:pairs_walk(child)
 pairs_walk(pairs)
 assert sorted((r['variable_id'],r['voi_owner_fit']) for _,r in found)==sorted(second)
 print(json.dumps({'evidence':p+'@'+own.BASE,'denominator':'every object in complete one JSON artifact with voi_owner_fit, independently decoded object-pairs identity equal','count':len(found),'distribution':dict(Counter(r['voi_owner_fit'] for _,r in found)),'rows':found},indent=2))
elif mode=='lineage':
 inv=own.ast_inventory();ps=[p for p in inv['paths'] if p.startswith('src/polisyos/scientist/')]
 keys=['subject_ref','gate_evidence_ref','epoch_validity_projection','decision_packet_lineage_key_ref']
 print(json.dumps({'base':own.BASE,'denominator':ps,'file_type':'.py','count':len(ps),'matches':{k:[{'path':p,'line':n,'text':line} for p in ps for n,line in enumerate((own.ROOT/p).read_text().splitlines(),1) if k in line] for k in keys}},indent=2))
elif mode=='source-details':
 names=['src/polisyos/runtime/http/services/cycle_board_projection.py','src/polisyos/runtime/quality/acquisition_epoch_admission.py','src/polisyos/runtime/quality/acquisition_epoch_activation.py','src/polisyos/runtime/quality/semantic_epoch_production.py','src/polisyos/lex/normpack/legal_authority.py','src/polisyos/runtime/quality/compression_loss.py','tools/quality/validation/layer3_gy_n13a_acquisition_census.py']
 print(json.dumps({'base':own.BASE,'files':[{'path':p,'exists':(own.ROOT/p).exists(),'body':(own.ROOT/p).read_text() if (own.ROOT/p).exists() else None} for p in names]},indent=2))
