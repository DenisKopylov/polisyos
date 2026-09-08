"""Bounded PR1 challenge using current fallback owners and already emitted real WMR."""
from dataclasses import asdict, fields
from pathlib import Path
import ast
import hashlib
import inspect
import json
from pydantic import ValidationError
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality import credal_reference as cr
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.runtime.quality.world_model_record import load_world_model_record
from tools.quality.validation import check_layer3_gy_design_generation_contract as recordings_owner

root=Path.cwd()
wmr_ref='sha256:8b96b3761b471ab0d05fb6f7ecd17ebeba9812abcc703b353bdbb70563f494b4'
store=FileSystemCAS(root/'.tmp/gy-s-composed-wmr-cas')
raw=store.get_bytes(wmr_ref)
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==wmr_ref
wmr=load_world_model_record(store,wmr_ref)
print(json.dumps({'measurement':'shared_real_WMR_readback','cas_ref':wmr_ref,'logical_content_hash':wmr.content_hash,'world_model_record_id':wmr.world_model_record_id,'authority_status':wmr.authority_status,'provenance':'existing canonical owner output supplied by S3; no WMR builder invoked'},indent=2),flush=True)
try:
    reference=cr.build_credal_reference(root,world_model_record=wmr)
except (OSError,ValueError,RuntimeError) as exc:
    print(json.dumps({'measurement':'full_current_K_ref_with_real_WMR','status':'owner_refused','exception':type(exc).__name__,'detail':str(exc)},indent=2),flush=True)
else:
    print(json.dumps({'measurement':'full_current_K_ref_with_real_WMR','status':'built','reference_hash':reference.reference_hash},indent=2),flush=True)
rows=recordings_owner._load_recordings(root)
raw_rows=json.loads((root/recordings_owner.RECORDING_FIXTURE_PATH).read_text())['recordings']
owned_ids=[row['recording_id'] for row in rows]
raw_ids=[row['recording_id'] for row in raw_rows]
assert set(owned_ids)==set(raw_ids) and len(owned_ids)==len(set(owned_ids))
print(json.dumps({'measurement':'recording_input_denominator','file':recordings_owner.RECORDING_FIXTURE_PATH,'owner_ids':owned_ids,'raw_ids':raw_ids,'note':'all canonical recording members; authentic historical LLM input controls, not a current canonical governed candidate population'},indent=2),flush=True)
for recording in rows:
    problem=recordings_owner._design_problem(recording)
    result=gc._grammar_fallback_result(problem,cycle_index=0,reason='generation_unavailable')
    generated_ids=[item.atom.intervention_id for item in result.candidates]
    source_ids=[item.lever_id for item in problem.candidate_lever_space.candidate_levers]
    assert set(generated_ids)==set(source_ids)
    attempts=[]
    for item in result.candidates:
        actual=asdict(item.atom)
        try:
            InterventionAtomBinding.model_validate(actual)
        except ValidationError as exc:
            disposition={'status':'not_InterventionAtomBinding','errors':exc.errors(include_url=False)}
        else:
            disposition={'status':'valid_InterventionAtomBinding'}
        attempts.append({'candidate':asdict(item),'canonical_atom_admission':disposition})
    model_fields={f.name for f in fields(gc._GrammarFallbackAtom)}
    module=ast.parse(inspect.getsource(gc._GrammarFallbackAtom))
    ast_fields={node.target.id for node in module.body[0].body if isinstance(node,ast.AnnAssign)}
    assert model_fields==ast_fields
    print(json.dumps({'measurement':'actual_N6_fallback_source','recording_id':recording['recording_id'],'source_lever_ids':source_ids,'emitted_atom_intervention_ids':generated_ids,'complete_atom_fields':sorted(model_fields),'independent_AST_fields':sorted(ast_fields),'result_status':result.status,'fallback_reason':result.fallback_reason,'attempts':attempts,'interpretation':'Fallback names are actual candidate search inputs; missing canonical atom fields may not be manufactured from lever defaults.'},indent=2),flush=True)
