"""Selected TOML contract checks using existing canonical release functions.

This deliberately does not invoke all repository compatibility/architecture gates.
"""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import tomllib

ROOT=Path('/dev/shm/e02-D-oct07-continuation')
PRODUCT=ROOT/'policy-engine'
EXPECTED=sys.argv[1]
OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=False)
NAMES=['2026-10-07-state-read-binding-ambiguity.toml','2026-10-07-search-complete-history-resume.toml','2026-10-07-funnel-cost-input-origins.toml']
RELS=['policy-engine/release-fragments/unreleased/'+name for name in NAMES]
POLICIES=['policy-engine/architecture/gates/compatibility_release.toml','policy-engine/ops/release/release-fragment-policy.toml']
TOOLS=['policy-engine/tools/ops_runners/release/build_release_notes.py','policy-engine/tools/ops_runners/release/check_compatibility_release_gates.py']
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()
def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
head=git('rev-parse','HEAD').decode().strip();tree=git('rev-parse','HEAD^{tree}').decode().strip();status=git('status','--porcelain').decode();assert head==EXPECTED and not status
inputs={path:git('show',EXPECTED+':'+path) for path in RELS+POLICIES+TOOLS+['policy-engine/pyproject.toml']}
for path in RELS+TOOLS+['policy-engine/pyproject.toml']:assert (ROOT/path).read_bytes()==inputs[path]
write('before.json',{'head':head,'tree':tree,'status':status,'complete_selected_input_sha256':{p:sha(b) for p,b in inputs.items()},'policy_input_availability':{p:{'Git_object':True,'materialized':(ROOT/p).is_file()} for p in POLICIES}})
policy=tomllib.loads(inputs[POLICIES[0]].decode());fragment_policy=tomllib.loads(inputs[POLICIES[1]].decode())['release_fragments']
from tools.ops_runners.release.build_release_notes import render_release_notes, validate_required_curated_sections, structured_compatibility_changes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
fragments=[];errors=[];doc_inputs={}
for rel in RELS:
    fragment=tomllib.loads(inputs[rel].decode());fragment['__path__']=str(ROOT/rel);fragments.append(fragment)
    for field in fragment_policy['required_fields']:
        if not fragment.get(field):errors.append({'path':rel,'error':'missing required fragment field','field':field})
    if fragment.get('type') not in fragment_policy['allowed_types']:errors.append({'path':rel,'error':'unsupported type'})
    client=fragment.get('generated_client_compatibility')
    if client is not None and client not in fragment_policy['generated_client_compatibility_values']:errors.append({'path':rel,'error':'unsupported generated client compatibility'})
    for field in ('evidence','migration_docs','runbook_docs'):
        value=fragment.get(field,[]);value=[value] if isinstance(value,str) else value
        for linked in value:
            local=PRODUCT/linked
            if not local.is_file():errors.append({'path':rel,'error':'linked field path missing','field':field,'linked':linked});continue
            full='policy-engine/'+linked
            original=git('show',EXPECTED+':'+full);assert local.read_bytes()==original
            doc_inputs[full]=sha(original)
canonical_errors,canonical_findings=_validate_fragments(PRODUCT,policy,fragments,breaking_classes=('tooling','persisted-artifact-format','runtime-state-format'))
errors.extend(finding.as_dict() for finding in canonical_errors)
counts=validate_required_curated_sections(fragments,['compatibility','migration','api','limitations'])
version=tomllib.loads(inputs['policy-engine/pyproject.toml'].decode())['project']['version']
notes=render_release_notes(version,fragments,'2026-10-07');(OUT/'selected-release-notes.md').write_text(notes)
write('actual-canonical-selected-fragment-report.json',{'source':EXPECTED,'tree':tree,'fragment_count':len(fragments),'selected_paths':RELS,'errors':errors,'canonical_findings':[x.as_dict() for x in canonical_findings],'structured_compatibility_changes':structured_compatibility_changes(fragments),'curated_sections':counts,'linked_inputs_sha256':doc_inputs,'canonical_functions':['_validate_fragments','validate_required_curated_sections','render_release_notes'],'schema_policy':'exact Git '+EXPECTED+':'+POLICIES[1],'breaking_classes_explicit':['tooling','persisted-artifact-format','runtime-state-format'],'metadata_result':'PASS' if not errors else 'FAIL','global_release_gate':'UNRUN; fullCLI unconditionally validates unrelated public/extension/generated/runtime/migration/schema/template contracts; this selected-input result is not a whole gate or release publication'})
assert git('rev-parse','HEAD').decode().strip()==head and git('rev-parse','HEAD^{tree}').decode().strip()==tree and not git('status','--porcelain').decode()
assert all(git('show',EXPECTED+':'+p)==data for p,data in inputs.items())
write('after.json',{'head':head,'tree':tree,'status':'','selected_input_sha256':{p:sha(b) for p,b in inputs.items()},'linked_input_sha256':doc_inputs,'source_before_after_identical':True})
write('result.json',{'exitcode':1 if errors else 0,'check':'selected three release fragment metadata','actual_output_sha256':{p.name:sha(p.read_bytes()) for p in OUT.iterdir() if p.is_file()},'outer_streams':'Finalized by separate postcompletion manifest after wrapper END','global_gate':'UNRUN; not asserted'})
print(json.dumps({'metadata_result':'PASS' if not errors else 'FAIL','fragment_count':3,'output':str(OUT)}));sys.exit(1 if errors else 0)
