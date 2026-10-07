"""Independent check-output quantities; does not invoke checks or producer collector."""
from __future__ import annotations
import copy,hashlib,json
from pathlib import Path
from defusedxml import ElementTree

def content_digest(path:Path):
 h=hashlib.sha256();size=0
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block);size+=len(block)
 return {'bytes':size,'sha256':h.hexdigest()}

def junit_quantities(path:Path):
 root=ElementTree.parse(path,forbid_dtd=True).getroot()
 counts=dict(cases=0,passed=0,failed=0,errors=0,skipped=0);bad=[];case_ids=[]
 for case in root.iter('testcase'):
  counts['cases']+=1;identity=dict(classname=case.get('classname'),name=case.get('name'),file=case.get('file'),line=case.get('line'))
  failures=case.findall('failure');errors=case.findall('error');skips=case.findall('skipped')
  outcome='failed' if failures else 'errors' if errors else 'skipped' if skips else 'passed'
  counts[outcome]+=1;case_ids.append(identity|{'outcome':outcome})
  if failures or errors or skips:bad.append(identity|{'outcome':outcome,'details':[{'tag':n.tag,'attributes':dict(n.attrib),'text':n.text} for n in failures+errors+skips]})
 assert sum(counts[k] for k in ['passed','failed','errors','skipped'])==counts['cases']
 return {'counts':counts,'case_ids':case_ids,'non_pass_cases':bad,'xml_digest':content_digest(path)}

def receipt_outcome(receipt,counts):
 immutable=(receipt.get('source_identity_before')==receipt.get('source_identity_after') and receipt.get('head_at_end')==receipt.get('candidate_sha') and receipt.get('git_input_config',{}).get('stable') is True and receipt.get('git_input_config',{}).get('sha256')==receipt.get('git_input_config',{}).get('after_sha256') and receipt.get('source_immutable') is True)
 if not immutable:return 'FAIL'
 if receipt.get('backend_error') is not None:return 'UNRUN'
 if counts and counts['cases'] and counts['skipped']==counts['cases']:return 'SKIP'
 return 'PASS' if receipt.get('exit_code')==0 else 'FAIL'

def validate_receipt(receipt,freeze,tree,observed):
 assert receipt['candidate_sha']==freeze and receipt['candidate_tree_sha']==tree
 assert type(receipt['exit_code']) is int and type(receipt['source_immutable']) is bool
 assert receipt['stdout_bytes']==observed['stdout']['bytes'] and receipt['stdout_sha256']==observed['stdout']['sha256']
 counts=None if observed.get('junit') is None else observed['junit']['counts']
 if counts is not None:
  assert all(type(x) is int for x in receipt['counts'].values())
 assert receipt.get('counts')==counts
 if observed.get('tracked_source') is not None:
  assert receipt['source_identity_before']==receipt['source_identity_after']==observed['tracked_source']
 if observed.get('private_config') is not None:
  config=receipt['git_input_config'];assert config['bytes']==observed['private_config']['bytes'] and config['sha256']==config['after_sha256']==observed['private_config']['sha256']
 expected=receipt_outcome(receipt,counts);assert receipt['outcome']==expected
 if expected=='PASS' and counts:assert counts['failed']==counts['errors']==0
 if expected=='PASS':
  assert receipt['exit_code']==0
  if observed.get('kind')=='numerical':assert counts is not None and counts['cases']>0
 return expected

def validate_stage_scope(scope):
 failed=False;seen=[]
 for row in scope['steps']:
  outcome=row['outcome'];assert outcome in ['PASS','FAIL','UNRUN']
  if failed:assert outcome=='UNRUN'
  if outcome=='PASS':assert row.get('exit_code')==0 and 'started_unix' in row
  if outcome=='FAIL':assert 'started_unix' in row;failed=True
  if outcome=='UNRUN':assert 'started_unix' not in row and 'reason' in row
  seen.append({'label':row['label'],'outcome':outcome,'command':row['command'],'cwd':row['cwd']})
 return seen
