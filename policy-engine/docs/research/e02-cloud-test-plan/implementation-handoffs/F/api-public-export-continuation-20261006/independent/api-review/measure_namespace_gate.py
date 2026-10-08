"""Read the complete supported entrypoint selector and retain its incomplete gate."""
from dataclasses import asdict
import hashlib,json,sys
from tools.devx.architecture import guardrails
from polisyos.ir import analytics
from polisyos.fabric import world

policies=guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
inventory=guardrails.build_public_surface_inventory(policies)
rows=[entry for package in inventory for entry in package.entrypoints]
expected={entry for policy in policies for entry in policy.supported_entrypoints}
assert {entry.module for entry in rows}==expected
unknown={entry.module for entry in rows if entry.export_count is None}
violations=guardrails._check_public_surface_contracts(inventory)
incomplete=[item for item in violations if item.detail=='incomplete_exports']
assert {item.subject for item in incomplete}==unknown
analytics_row=next(row for row in rows if row.module=='polisyos.ir.analytics')
assert analytics_row.exports==tuple(analytics.__all__)
world_row=next(row for row in rows if row.module=='polisyos.fabric.world')
assert tuple(world.__all__[:world_row.known_export_count])==world_row.exports
read_refs=[]
for row in rows:
 for item in row.export_resolution['inputs']:
  if item['operation']=='read_bytes' and item['status']=='read':
   body=(guardrails.REPO_ROOT/item['path']).read_bytes()
   assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256']
   read_refs.append(item)
policy=guardrails.DEFAULT_PUBLIC_MANIFEST;body=policy.read_bytes()
report={'check':'FAIL' if violations else 'PASS','selector':'Every supported_entrypoints value in the canonical public surface contract; no full architecture or generated snapshot gate',
        'policy_ref':{'source_path':str(policy.relative_to(guardrails.REPO_ROOT)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()},
        'entrypoint_count':len(rows),'unknown_count':len(unknown),'entrypoints':[
         {'module':row.module,'export_count':row.export_count,'known_export_count':row.known_export_count,
          'complete':row.export_resolution['complete'],'facade_mode':row.facade_mode_observed,
          'source_file':row.source_file,'resolution':row.export_resolution} for row in rows],
        'canonical_contract_violations':[asdict(item) for item in violations],
        'actual_analytics_runtime_count':len(analytics.__all__),
        'actual_world_runtime_count':len(world.__all__),'world_known_static_prefix':world_row.known_export_count,
        'world_runtime_materialize_available':world._MATERIALIZE_AVAILABLE,
        'explicit_successful_read_count':len(read_refs),'all_explicit_successful_read_bytes_hashes_reconciled':True,
        'scope':'Actual static total metadata and real current profile namespace comparison. Source-reader imports/Git/subprocess execution outside explicit collector remain named unresolved boundaries; no real-data/backend causal claim.'}
print(json.dumps(report,indent=2))
sys.exit(1 if violations else 0)
