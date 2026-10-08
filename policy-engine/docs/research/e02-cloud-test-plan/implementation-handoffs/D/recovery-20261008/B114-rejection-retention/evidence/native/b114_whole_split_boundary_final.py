"""Original B114 corpus/plan discriminator; bounded route spy, no numerical claim."""
import ast,pathlib,sys,json,hashlib,dataclasses,enum,argparse,datetime,inspect
sys.path.insert(0,str(pathlib.Path.cwd()/'tests'))
from _helpers import search_strategies as fixture
from tests.unit.scientist.search.strategies import test_bayesian as supplied
from polisyos.scientist.methods.search.strategies import bayesian as owner
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--reverse-warm',action='store_true');p.add_argument('--source',required=True);a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(exist_ok=False)
test_path=pathlib.Path(supplied.__file__);tree=ast.parse(test_path.read_text());test=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='test_bayesian_warm_start_reaches_gp_training_before_initial_threshold');prefix=[]
for node in test.body:
 if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='warm_start':break
 prefix.append(node)
else:raise AssertionError('committed fixture boundary not found')
module=ast.Module(body=prefix,type_ignores=[]);ns=dict(vars(supplied));ns['simple_space']=fixture.simple_space.__wrapped__();exec(compile(module,str(test_path),'exec'),ns)
def encode(x):
 if isinstance(x,datetime.datetime):return x.isoformat()
 if isinstance(x,enum.Enum):return x.value
 if dataclasses.is_dataclass(x):return dataclasses.asdict(x)
 if hasattr(x,'model_dump'):return x.model_dump(mode='json')
 raise TypeError(type(x).__name__)
eligible=ns['warm'][:8];eligible=list(reversed(eligible)) if a.reverse_warm else eligible;current=ns['current'];assert len(eligible)==8 and len(current)==1
config=dataclasses.replace(ns['strategy']._config,adaptive_acquisition=True,fallback_on_failure=False)
records={}
def run(label,warm,new):
 strategy=owner.BayesianOptimizer(ns['simple_space'],config);assert strategy._botorch_ready
 if warm:strategy.warm_start(warm)
 r={'native_ready':strategy._botorch_ready,'effective_ids':[e.candidate_id for e in strategy._effective_training_corpus(new)],'selected_ids':[e.candidate_id for e in strategy._select_training_subset(new)]}
 def observe_fit(X,y):
  r['training_X']=X.detach().cpu().tolist();r['training_y_bo']=y.detach().cpu().tolist();r['fit_executed']=False
 def observe_acquisition(y_bo,soft_limit,evaluations=None):
  r['actual_acquisition_caller_ids']=[e.candidate_id for e in evaluations or []]
  r['actual_plan']=strategy._select_acquisition(evaluations or [],y_bo).value
  r['actual_best_f']=float(y_bo.max().item());r['soft_limit']=soft_limit
  # Numerical optimize is outside this local plan/corpus boundary.
  return strategy._torch.tensor([[.11]],dtype=strategy._torch.double),strategy._torch.tensor([0.],dtype=strategy._torch.double)
 strategy._fit_gp=observe_fit;strategy._optimize_acquisition=observe_acquisition
 candidate=strategy.suggest(new);r['candidate_route']=candidate.source_strategy;r['iteration']=strategy._iteration;records[label]=r
run('whole',[],[*eligible,*current]);run('warm_plus_new',eligible,current)
inputs={'source':a.source,'owner_module':owner.__file__,'owner_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'test_module':str(test_path),'test_sha256':hashlib.sha256(test_path.read_bytes()).hexdigest(),'helper_module':fixture.__file__,'helper_sha256':hashlib.sha256(pathlib.Path(fixture.__file__).read_bytes()).hexdigest(),'input_prefix_ast_sha256':hashlib.sha256(ast.dump(module,include_attributes=False).encode()).hexdigest(),'config':config,'warm_order':'reversed exact declared fixture rows' if a.reverse_warm else 'original declared fixture order','eligible_warm':eligible,'current':current,'scope':'Original B114 same eligible corpus whole-vs-warm+new, adaptive planning option; actual suggest route and native tensor preparation, local fit/acquisition spies; NO numerical fit/optimization or full-chain claim.'}
(out/'inputs.json').write_text(json.dumps(inputs,default=encode,indent=2)+'\n')
result={'observations':records,'same_effective_ids':records['whole']['effective_ids']==records['warm_plus_new']['effective_ids'],'same_selected_ids':records['whole']['selected_ids']==records['warm_plus_new']['selected_ids'],'same_training_X':records['whole']['training_X']==records['warm_plus_new']['training_X'],'same_training_y_bo':records['whole']['training_y_bo']==records['warm_plus_new']['training_y_bo'],'same_plan':records['whole']['actual_plan']==records['warm_plus_new']['actual_plan'],'qualification':inputs['scope']}
(out/'observations.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
assert all(result[k] for k in ['same_effective_ids','same_selected_ids','same_training_X','same_training_y_bo']),'Original B114 compatible corpus differs between whole and warm+new'
assert result['same_plan'],'Original B114 adaptive planning differs for the same eligible corpus'
