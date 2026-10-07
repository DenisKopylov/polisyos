"""Fresh default-codec and evaluator-pair provenance boundaries, no source writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.methods.autotune.models import MutationArtifact
from polisyos.scientist.methods.autotune.runtime import PydanticMutationCodec, SequenceCandidateGenerator
from polisyos.scientist.methods.doe._receipt import _load_analysis, _persist_analysis
from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import SensitivityPlan
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator

ROOT=Path('/workspace/e02-E-doe-20261006')
OUT=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer')
def snapshot():
 names=subprocess.check_output(['git','ls-files','-z','policy-engine/src'],cwd=ROOT).decode().split('\0')
 hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names if p}
 return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
before=snapshot()
store=FileSystemCAS(OUT/'doe-native-cas')
refs=json.loads((OUT/'doe_refs.json').read_text())
ref=ArtifactRef.model_validate(refs['canonical'])
base=MutationArtifact(loop_id='independent_sensitivity_review')
codec=PydanticMutationCodec(MutationArtifact)
assert codec.decode(base.model_dump(mode='json'))==base
wrapped=SensitivityAwareCandidateGenerator.from_artifact(SequenceCandidateGenerator([base]),store,ref)
candidate=wrapped.generate([],None,{})
assert candidate['_sensitivity']['analysis_ref']==ref.model_dump(mode='json')
try:
 codec.decode(candidate)
except ValueError as exc:
 codec_error={'type':type(exc).__name__,'message':str(exc)}
else:
 raise AssertionError('Expected default PydanticMutationCodec to refuse unadmitted metadata field')
print(json.dumps({'case':'default_codec_admits_base_refuses_decorator_metadata','outcome':'OBSERVED_OWNER_RESIDUAL','detail':codec_error}),flush=True)

# A numerical reader can bind supplied X/Y but cannot authenticate the evaluator
# that paired them. Recompute a mismatched finite outcome series and read it back;
# the declared evaluator-provenance limitation must remain explicit.
payload=from_canonical_bytes(store.get_bytes(ref))
plan=SensitivityPlan.model_validate(payload['plan'])
samples=np.asarray(payload['samples'],dtype=float)
outputs=np.roll(np.asarray(payload['outputs'],dtype=float),1)
fixture_truth=samples[:,0]+samples[:,1]+2*samples[:,0]*samples[:,1]
assert not np.array_equal(outputs,fixture_truth)
result=analyze_sensitivity(plan,samples,outputs)
newref=_persist_analysis(store,plan,samples,outputs,result)
reopened=FileSystemCAS(store.root)
assert _load_analysis(reopened,newref)==result
newpayload=json.loads(reopened.get_bytes(newref))
assert newpayload['evaluator_provenance']=='not_established'
assert newpayload['population_law_status']=='not_established'
assert newpayload['authority_purpose']=='exploratory_parameter_experiment'
origins={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(ROOT/'policy-engine/src') for p in origins.values())
assert snapshot()==before
receipt={'source_sha':'f07b7d485531b96a206ae9b2aad7acf5f2755324','source_before_after_identical':True,'source_snapshot_sha256':before,'all_polisyos_origins_pinned':True,'polisyos_module_count':len(origins),'default_codec_boundary':codec_error,'coherently_recomputed_misaligned_pairs':{'numerical_readback':'accepted supplied X/Y','evaluator_provenance':newpayload['evaluator_provenance'],'population_law_status':newpayload['population_law_status'],'authority_purpose':newpayload['authority_purpose'],'analysis_ref':newref.model_dump(mode='json')},'owner':'D Scientist default Search/autotune and source-evaluator owner','required_next_result':'admit existing generator/codec metadata carrier and actual proposal consumer; persist/reopen exact ref and test ranking-dependent behavior. Numeric CAS reproduction alone cannot authenticate source evaluator pairing.'}
(OUT/'doe-consumer-boundary-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'case':'coherent_XY_evaluator_provenance_boundary','outcome':'DECLARED_BOUNDARY_CONFIRMED','detail':receipt['coherently_recomputed_misaligned_pairs']}),flush=True)
