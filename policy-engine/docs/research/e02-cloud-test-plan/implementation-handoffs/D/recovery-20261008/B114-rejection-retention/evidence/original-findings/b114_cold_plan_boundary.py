"""Original B114 below-threshold whole-vs-split actual Sobol consumer."""
import ast,pathlib,sys,json,hashlib,dataclasses,enum,argparse,datetime
sys.path.insert(0,str(pathlib.Path.cwd()/'tests'))
from _helpers import search_strategies as fixture
from tests.unit.scientist.search.strategies import test_bayesian as supplied
from polisyos.scientist.methods.search.strategies import bayesian as owner
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--source',default='c1bffbd531b9b2c4339f073416c95d42d90ee317');a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(exist_ok=False)
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
warm=ns['warm'][:2];current=ns['current'];config=ns['strategy']._config;assert config.n_initial==6 and len(warm)+len(current)==3
observed={}
def run(label,accepted,new,batch):
 strategy=owner.BayesianOptimizer(ns['simple_space'],config);assert strategy._botorch_ready
 if accepted:strategy.warm_start(accepted)
 corpus=strategy._effective_training_corpus(new);subset=strategy._select_training_subset(new)
 candidates=strategy.suggest_batch(new,2) if batch else [strategy.suggest(new)]
 observed[label]={'corpus_ids':[e.candidate_id for e in corpus],'selected_ids':[e.candidate_id for e in subset],'below_initial_threshold':len(corpus)<config.n_initial,'candidates':[{'params':c.params,'params_normalized':c.params_normalized,'source':c.source_strategy} for c in candidates],'cold_request_count':len(new),'fit_executed':False}
run('single_whole',[],[*warm,*current],False);run('single_warm_plus_new',warm,current,False);run('batch_whole',[],[*warm,*current],True);run('batch_warm_plus_new',warm,current,True)
result={'observations':observed,'same_single_corpus':observed['single_whole']['corpus_ids']==observed['single_warm_plus_new']['corpus_ids'],'same_batch_corpus':observed['batch_whole']['corpus_ids']==observed['batch_warm_plus_new']['corpus_ids'],'same_single_plan':observed['single_whole']['candidates']==observed['single_warm_plus_new']['candidates'],'same_batch_plan':observed['batch_whole']['candidates']==observed['batch_warm_plus_new']['candidates'],'scope':'Original B114 same below-threshold eligible corpus whole-vs-warm+new; actual supported Sobol candidates without fit/acquisition stubs or GP training; no request/refit counter equality imposed.'}
inputs={'source':a.source,'owner_module':owner.__file__,'owner_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'test_module':str(test_path),'test_sha256':hashlib.sha256(test_path.read_bytes()).hexdigest(),'helper_module':fixture.__file__,'helper_sha256':hashlib.sha256(pathlib.Path(fixture.__file__).read_bytes()).hexdigest(),'input_prefix_ast_sha256':hashlib.sha256(ast.dump(module,include_attributes=False).encode()).hexdigest(),'config':config,'eligible_warm':warm,'current':current,'batch_size':2}
(out/'inputs.json').write_text(json.dumps(inputs,default=encode,indent=2)+'\n');(out/'observations.json').write_text(json.dumps(result,default=encode,indent=2)+'\n');print(json.dumps(result,default=encode,indent=2),flush=True)
assert result['same_single_corpus'] and result['same_batch_corpus']
assert result['same_single_plan'] and result['same_batch_plan'],'B114 below-threshold same eligible corpus produces different actual Sobol plan whole versus warm+new'
