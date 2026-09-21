#!/usr/bin/env python3
"""Finite mutation checks of the launch-kit verifier; never modifies repository data."""
from pathlib import Path
import importlib.util
import json
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kit_verifier',ROOT/'verify_plan.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

def json_change(root,name,change):
    p=root/name; obj=json.loads(p.read_text());change(obj)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def run():
    report=[]
    # Checksums intentionally disabled: failures must come from structural checks, not just stale hashes.
    v.verify(ROOT,check_hashes=False)
    with tempfile.TemporaryDirectory(prefix='policyos-e02-verifier-') as tmp:
        target=Path(tmp)/'kit';shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        cases=[
          ('missing_B','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:x['bundles'][0]['findings'].pop()),'B coverage'),
          ('missing_LA','legacy_to_bundles.json',lambda r:json_change(r,'legacy_to_bundles.json',lambda x:x.pop('LA-057')),'LA coverage'),
          ('missing_late_amendment','source/amendment_index.json',lambda r:json_change(r,'source/amendment_index.json',lambda x:x.pop(2)),'Late amendments'),
          ('dependency_cycle','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:next(b for b in x['bundles'] if b['id']=='CYC-01')['depends_on'].append('CYC-02')),'cycle'),
          ('source_changed','source/LA_r09_original.md',lambda r:(r/'source/LA_r09_original.md').write_bytes((r/'source/LA_r09_original.md').read_bytes()+b'\nCHANGED\n'),'source integrity'),
          ('first_dispatch_promoted','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:x.__setitem__('first_dispatch_status','active_queue')),'historical seed'),
          ('excess_parallel_tests','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:x['local_execution'].__setitem__('max_resource_processes',8)),'Mac resource'),
          ('excess_weighted_budget','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:x['local_execution'].__setitem__('light_equivalent_budget',8)),'Mac resource'),
          ('DDM_schema_protection_removed','bundle_manifest.json',lambda r:json_change(r,'bundle_manifest.json',lambda x:[b['protected_controls'].remove('LK35') for b in x['bundles'] if 'LK35' in b['protected_controls']]),'Protected LK'),
          ('move_target_not_leased','relocation_map.json',lambda r:json_change(r,'relocation_map.json',lambda x:x['moves'][0]['proposed_target_paths'].append('policy-engine/src/polisyos/unleased_target.py')),'lease both'),
        ]
        for name,file,mutate,expected in cases:
            path=target/file;original=path.read_bytes()
            try:
                mutate(target)
                try:v.verify(target,check_hashes=False)
                except ValueError as exc:
                    message=str(exc)
                    if expected.lower() not in message.lower():raise RuntimeError(f'{name} failed for unexpected reason: {message}') from exc
                    report.append({'case':name,'detected':True,'error':message})
                else:raise RuntimeError(f'Mutation was not detected: {name}')
            finally:path.write_bytes(original)
        v.verify(target,check_hashes=False)
    result={'status':'PASS','scope':'verifier negative controls only','cases':report,'count':len(report),'PolicyOS_execution':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

def test_verifier_controls():
    run()

if __name__=='__main__':run()
