"""Bind complete unique scratch outputs; do not copy tracked source snapshots."""
from pathlib import Path
import hashlib
import json
import subprocess

here=Path(__file__).parent
author=Path('/tmp/e02-F-continuation-20261006/tmle-generated')
root=Path('/workspace/e02-F-tmle-20261006')
pin='27f28925d8ecaa674ae7b553faa262b1cb624903'
base='ae9f30204c84cb3f9d1bd418752145eec2a5429d'
audit=json.loads((here/'source-audit.stdout.txt').read_text())

def ref(path):
    data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

for source in audit['source_refs']:
    raw=subprocess.check_output(['git','-C',str(root),'show',f"{source['git_sha']}:{source['path']}"])
    assert len(raw)==source['bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256']
names=['native-harness-first','native-corrected','removal-enum-causal_effect_report',
    'removal-enum-hte_result','removal-hash-causal_effect_report','removal-hash-hte_result']
runs=[]
for name in names:
    row=json.loads((here/(name+'.json')).read_text())
    row['retained_original_command_receipt']=ref(here/(name+'.json'))
    row['actual_output_refs']={kind:ref(here/(name+'.'+kind+'.txt')) for kind in ('stdout','stderr')}
    for kind in ('stdout','stderr'):
        assert row['actual_output_refs'][kind]['sha256']==row['outputs'][kind]['sha256']
        assert row['actual_output_refs'][kind]['bytes']==row['outputs'][kind]['bytes']
    stdout=(here/(name+'.stdout.txt')).read_text()
    if name=='native-harness-first':
        assert row['exit_code']==1 and '4 failed, 13 passed' in stdout and 'ArtifactID is not JSON serializable' in stdout
        row.update(outcome='FAIL',interpretation='Reviewer stdout logging TypeError after native CAS/fresh-reader/schema assertions; no product defect. Original output refs retained verbatim and raw files renamed with historical suffix.')
    elif name=='native-corrected':
        assert row['exit_code']==0 and '17 passed' in stdout and 'failed' not in stdout and 'warning' not in stdout
        row.update(outcome='PASS',pytest_census=dict(passed=17,failed=0,skipped=0,errors=0,warnings=0),
            interpretation='Actual native TMLE report and explicitly synthetic HTE typed-wire fixtures through real CAS and fresh process readers; old1.0 readers and generated schema checks.')
    else:
        assert row['exit_code']==1 and '1 failed' in stdout and 'ERROR at setup' not in stdout and 'ERROR collecting' not in stdout
        reason="'tmle' is not one of" if '-enum-' in name else "assert '000000000000"
        assert reason in stdout, name
        row.update(outcome='FAIL',expected_negative=True,property_detected=True,
            interpretation='Actual criterion assertion failed for removed companion property with native provider/markers retained; not counted as PASS.')
    runs.append(row)
observed_author=[]
for name in ('positive','enum','hash','full','selected-first-debug'):
    receipt=json.loads((author/(name+'.json')).read_text())
    outputs=[ref(author/(name+'.'+kind+'.txt')) for kind in ('stdout','stderr')]
    observed_author.append(dict(name=name,receipt=ref(author/(name+'.json')),outputs=outputs,
        actual_exit_code=receipt['exit_code'],execution='Author actual execution independently read; no reviewer duplicate full generator run.'))
assert observed_author[3]['actual_exit_code']==1
full=(author/'full.stdout.txt').read_text()+(author/'full.stderr.txt').read_text()
assert 'feedback_solve_result.schema.json' in full and '_manifest.json' in full
local_names=['test_tmle_generated_consumer.py','remove_enum_or_hash.py','run_review.py',
    'audit_companion.py','finish_review.py','source-paths.json','harness-correction.json',
    'source-audit.stdout.txt','source-audit.stderr.txt', 'finish-first.stdout.txt', 'finish-first.stderr.txt']
for name in names:
    local_names.extend(name+'.'+suffix for suffix in ('json','stdout.txt','stderr.txt'))
unique_refs=[ref(here/name) for name in local_names]
review=dict(review_type='Independent read-only generated TMLE enum companion',decision='GO',
    source_sha=pin,source_tree=audit['tree'],slice_base_sha=base,slice_base_tree=audit['base_tree'],
    implementation_changed_paths=audit['changed_paths'],full_diff_sha256=audit['full_diff_sha256'],
    source_refs=audit['source_refs'],related_finding_ids=['B54','B56'],closure_ids=[],
    independent_checks=runs,
    source_audit=dict(outcome='PASS',output=ref(here/'source-audit.stdout.txt'),stderr=ref(here/'source-audit.stderr.txt'),
        environment_ref=ref(here/'source-audit.stdout.txt'),
        criterion='Exact5path scope; native two complete snapshots; CausalMethod37; existing description only; exact99-entry digest with97unowned rows/provenance unchanged; full canonical catalogue; old SCM1.1 retained; public stable release classification.'),
    observed_author_checks=observed_author,
    scientific_scope='One independently seeded bounded360-row synthetic DGP native TMLE call verifies real report serialization and regular-IID interval preservation, not population coverage. HTEResult is a supported typed wire fixture, not a new native heterogeneous TMLE producer.',
    retained_negative_history='Initial reviewer4FAIL13PASS logging harness retained verbatim; corrected17PASS. Initial packaging harness ERROR mistakenly matched expected ValidationError text, corrected to reject only pytest setup/collection ERROR. Author initial selected tools-origin ERROR/FAIL retained. All four reviewer removal tests remain actual FAIL, correctly detecting removed enum/hash properties.',
    limitations=['Full canonical generator is actual FAIL at FeedbackSolveResult snapshot and dependent manifest; five Core ArtifactRef nested additions outside owner scope are not autofixed.',
        'No inherited P41/global generation/architecture/docs PASS claim.',
        'Reports retain1.0; SCM retained1.1. Old non-TMLE existing labels and explicit/omitted1.0 actual CAS readers verified, not old non-TMLE backends.',
        'Native report numerical SUCCESS+CI remains non-gating; accepted production TMLE Node authority/intake/identification and actual common budget admission remain UNRUN/limited.',
        'No DoWhy/EconML backend witness inferred from absence in baseline Python3.14; actual used native NumPy profile identified in environment.'],
    source_mutations=False,grandchildren=False,resource_quota_added=False,
    transfer_file_policy='Unique measured scratch outputs and replayers only; tracked snapshots/source/full generated99-model views referenced by exact Git path@SHA without copied bodies.',
    retained_unique_artifacts=unique_refs)
(here/'review.json').write_text(json.dumps(review,indent=2)+'\n')
selection=dict(source_sha=pin,source_tree=audit['tree'],files=[ref(here/'review.json'),*unique_refs],
    author_existing_refs=observed_author,
    omitted_redundant_views=['runs.json','whole generated99snapshot tree','tracked source/snapshot/catalog bodies'])
(here/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps(dict(decision='GO',source_sha=pin,review=ref(here/'review.json'),selection=ref(here/'transfer-selection.json'),
    unique_files=len(selection['files']),unique_bytes=sum(x['bytes'] for x in selection['files']))))
