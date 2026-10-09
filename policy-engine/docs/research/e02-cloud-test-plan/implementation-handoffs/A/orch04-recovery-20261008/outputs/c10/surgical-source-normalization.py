import subprocess
from pathlib import Path
root=Path('/workspace/ORCH04-C10');product=root/'policy-engine'
def gitbytes(ref,path):return subprocess.check_output(['git','show',ref+':policy-engine/'+path],cwd=root).decode()
path='tests/unit/runtime/quality/test_generation_cycle.py';p=product/path;s=p.read_text();tail=s[s.index('\ndef _controlled_declared_n4_child_inputs():'):]
tail=tail.replace('    one = result.model_copy(update={"candidates": (result.candidates[0],)})\n','').replace('    payload = one.model_dump(mode="python")','    payload = result.model_dump(mode="python")')
a=tail.index('    payload["grounding_dispositions"] = [');b=tail.index('    duplicate =',a)
tail=tail[:a]+'''    payload["grounding_dispositions"] = [
        (dispositions[0].model_copy(update={"candidate_id": alternate.candidate_id})
         if row.candidate_id == result.candidates[1].candidate_id else row).model_dump(mode="python")
        for row in result.grounding_dispositions
    ]
'''+tail[b:]
tail=tail.replace('from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems','from polisyos.runtime.quality.design_generation import (\n        DesignGenerationError, derive_n4_candidate_child_problems,\n    )',1).replace('pytest.raises(Exception, match="n4_recursive_child_source_untyped")','pytest.raises(DesignGenerationError, match="n4_recursive_child_source_untyped")')
p.write_text(subprocess.check_output(['git','show',':policy-engine/'+path],cwd=root).decode()+tail)
path='src/polisyos/runtime/quality/design_generation.py';p=product/path;s=p.read_text();a=s.index('@dataclass(frozen=True)\nclass N4CandidateChildProblem:');b=s.index('class RecordingLLMClient:',a);block=s[a:b];s=gitbytes('HEAD',path);s=s.replace('class RecordingLLMClient:',block+'class RecordingLLMClient:');s=s.replace('    "N4CandidateProposalSource",','    "N4CandidateChildProblem",\n    "N4CandidateProposalSource",').replace('    "default_firewall_evidence",','    "default_firewall_evidence",\n    "derive_n4_candidate_child_problems",');p.write_text(s)
path='src/polisyos/runtime/http/services/control/run_lifecycle.py';p=product/path;s=gitbytes('HEAD',path)
s=s.replace('        candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,\n        root_evaluation_context:', '        candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,\n        n4_recursive_source: GenerationUnderAResult | None = None,\n        recursive_leaf_context_owner: RecursiveLeafContextOwner | None = None,\n        root_evaluation_context:')
s=s.replace('            root_evaluation_context=root_evaluation_context,\n            eval_safety_verifier=', '            n4_recursive_source=n4_recursive_source,\n            recursive_leaf_context_owner=recursive_leaf_context_owner,\n            root_evaluation_context=root_evaluation_context,\n            eval_safety_verifier=')
# Existing TYPE_CHECKING source imports are audited before adding exact aliases below.
p.write_text(s)
