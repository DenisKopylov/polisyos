"""Resolve all assigned baseline cell identities; navigation, never new proof."""
import argparse,hashlib,importlib.util,json,pathlib
root=pathlib.Path('/workspace/e02-B-current-execution-state')
directory=root/'policy-engine/docs/research/e02-cloud-test-plan/results'
s=importlib.util.spec_from_file_location('baseline_query',directory/'query.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
ids=['B51','B52','B55','B77','B63','B70','B71','B72','B73','B57','B58','B59','B60','B61','B62']
queries={i:m.select(directory,argparse.Namespace(unit='B',finding=i,cell=None,path=None,failures_only=False,limit=1000,block_limit=1000,details=True,job_context=True)) for i in ids}
cells={c['id']:c for q in queries.values() for c in q['cells']}
jobs=[]
for job in sorted({c['job'] for c in cells.values()}):
 p=directory/'received'/f'{job}.txt';raw=p.read_text();start=raw.find('{');metadata,end=json.JSONDecoder().raw_decode(raw[start:])
 jobs.append({'job':job,'source_path':str(p.relative_to(root)),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'metadata_line_start':raw[:start].count('\n')+1,'metadata_line_end':raw[:start+end].count('\n')+1,'metadata_source_reported_only':metadata})
blocks={}
for q in queries.values():
 for b in q['source_blocks']:
  blocks[(b['job'],b['line_start'],b['line_end'])]=b
result={'schema':'policyos.e02.baseline_navigation.v1','source_ref':'198076863e143dea9f89f02734b13d50dae3eed5','grade':'source_reported_compact_text_only; candidate_routes; no new proof','raw_archives_received':0,'assigned_finding_count':len(ids),'unique_cell_count':len(cells),'finding_cell_routes':{i:[c['id'] for c in q['cells']] for i,q in queries.items()},'cells':list(cells.values()),'resolved_source_blocks':list(blocks.values()),'source_job_metadata':jobs,'criterion_basis':{i:q['finding_basis'] for i,q in queries.items()},'limitations':'PASS does not establish semantic adequacy or finding closure. Environments, source SHA/ref and closure metadata below are historical source-reported; full raw input archives were not transferred.'}
print(json.dumps(result,ensure_ascii=False,indent=2))
