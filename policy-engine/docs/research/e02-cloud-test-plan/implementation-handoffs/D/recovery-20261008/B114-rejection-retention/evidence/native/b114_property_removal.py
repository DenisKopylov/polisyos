"""Source-qualified, process-only effect removal; ordinary committed pytest/conftest."""
import argparse,pathlib,inspect,textwrap,hashlib,json,sys,ast
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--kind',required=True,choices=['ledger_append','ledger_restore','adaptive_corpus','cold_index','corpus_union']);p.add_argument('--source',required=True);p.add_argument('tests',nargs=argparse.REMAINDER);a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(exist_ok=False)
from polisyos.scientist.methods.search.strategies import bayesian as owner
from polisyos.scientist.methods.search.strategies import base as base_owner
changes=[]
def patch(name,before,after):
 actual=getattr(owner.BayesianOptimizer,name);pre=inspect.getsource(actual);assert pre.count(before)==1,(name,before,pre);post=pre.replace(before,after);post=('    # '+repr(before)+' marker retained\n'+post) if before not in post else post;pre_path=out/(name+'.preimage.py');post_path=out/(name+'.postimage.py');pre_path.write_text(pre);post_path.write_text(post)
 namespace=dict(vars(owner));exec(compile(textwrap.dedent(post),str(post_path),'exec'),namespace);setattr(owner.BayesianOptimizer,name,namespace[name]);changes.append({'method':name,'actual_original_code_filename':actual.__code__.co_filename,'preimage':str(pre_path),'preimage_sha256':hashlib.sha256(pre.encode()).hexdigest(),'postimage':str(post_path),'postimage_sha256':hashlib.sha256(post.encode()).hexdigest(),'removed_effect':before,'effect_identifier_marker_preserved':before.split('(',1)[0].strip() in post or 'len(training_corpus)' in post,'runtime_function_code_filename':str(post_path)})
if a.kind=='ledger_append':
 patch('_record_warm_start_rejection','self._warm_start_rejections.append(\n            {"reason": reason, "evaluation": asdict(evaluation)}\n        )','pass  # self._warm_start_rejections.append marker retained')
elif a.kind=='ledger_restore':
 patch('set_state','self._warm_start_rejections = rejection_records','pass  # self._warm_start_rejections = rejection_records marker retained')
elif a.kind=='adaptive_corpus':
 patch('suggest','evaluations=training_corpus,','evaluations=evaluations,  # evaluations=training_corpus marker retained')
elif a.kind=='cold_index':
 for name in ['suggest','suggest_batch']:
  patch(name,'self._sobol_candidate(len(training_corpus)','self._sobol_candidate(len(evaluations)')
elif a.kind=='corpus_union':
 patch('_effective_training_corpus','for evaluation in [*self._warm_evals, *evaluations]:','for evaluation in evaluations:  # [*self._warm_evals, *evaluations] marker retained')
packet={'schema':'ORCH04-B114-matched-property-removal-v1','source':a.source,'kind':a.kind,'source_files_modified':False,'original_owner_module':owner.__file__,'original_owner_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'actual_base_module':base_owner.__file__,'actual_base_sha256':hashlib.sha256(pathlib.Path(base_owner.__file__).read_bytes()).hexdigest(),'changes':changes,'pytest_argv':a.tests[1:] if a.tests[:1]==['--'] else a.tests,'qualification':'Only the named effect is removed in this process. Version/complete/count/per-record log/class/enum/reference/input markers remain. Original committed tests and ordinary conftest run; no product/test file edit, native numerical positive inferred from removal, or hook bypass.'}
(out/'removal-manifest.json').write_text(json.dumps(packet,indent=2)+'\n');print(json.dumps(packet,indent=2),flush=True)
import pytest
raise SystemExit(pytest.main(packet['pytest_argv']))
