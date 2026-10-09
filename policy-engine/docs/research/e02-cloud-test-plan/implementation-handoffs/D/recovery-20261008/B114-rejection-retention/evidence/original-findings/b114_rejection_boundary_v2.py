"""Existing-input original B114 rejection visibility boundary; no fit/oracle replay."""
import ast,pathlib,sys,json,hashlib,inspect,dataclasses,enum,argparse,textwrap,datetime
sys.path.insert(0,str(pathlib.Path.cwd()/'tests'))
from _helpers import search_strategies as fixture
from tests.unit.scientist.search.strategies import test_bayesian as supplied
from polisyos.scientist.methods.search.strategies import bayesian as owner
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(exist_ok=False)
source_path=pathlib.Path(supplied.__file__);source=source_path.read_text();root=ast.parse(source);test=next(n for n in root.body if isinstance(n,ast.FunctionDef) and n.name=='test_bayesian_warm_start_reaches_gp_training_before_initial_threshold');prefix=[]
for node in test.body:
 if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='warm_start':break
 prefix.append(node)
else:raise AssertionError('supplied input boundary not found')
module=ast.Module(body=prefix,type_ignores=[]);ns=dict(vars(supplied));ns['simple_space']=fixture.simple_space.__wrapped__();exec(compile(module,str(source_path),'exec'),ns)
strategy=ns['strategy'];warm=ns['warm'];assert strategy._botorch_ready is True,'native profile not ready'
def encode(x):
 if isinstance(x,datetime.datetime):return x.isoformat()
 if isinstance(x,enum.Enum):return x.value
 if dataclasses.is_dataclass(x):return dataclasses.asdict(x)
 if hasattr(x,'model_dump'):return x.model_dump(mode='json')
 raise TypeError(type(x).__name__)
logs=[];traced={}
class LogSpy:
 def __init__(self,actual):self.actual=actual
 def info(self,message,*args,**kwargs):logs.append(message.format(*args));return self.actual.info(message,*args,**kwargs)
 def __getattr__(self,name):return getattr(self.actual,name)
original_logger=owner.logger;owner.logger=LogSpy(original_logger)
def trace(frame,event,arg):
 if frame.f_code is owner.BayesianOptimizer.warm_start.__code__ and event=='return':traced['reasons']=list(frame.f_locals.get('rejected',[]))
 return trace
old_trace=sys.gettrace();sys.settrace(trace)
try:returned=strategy.warm_start(warm)
finally:sys.settrace(old_trace);owner.logger=original_logger
accepted=[e.candidate_id for e in strategy._warm_evals];rejected=[e.candidate_id for e in warm if e.candidate_id not in accepted];assert len(accepted)==8 and len(rejected)==3
state=strategy.get_state();observable=json.dumps({'returned':returned,'state':state,'logs':logs},default=encode,sort_keys=True)
inputs={'source':'c1bffbd531b9b2c4339f073416c95d42d90ee317','test_module':str(source_path),'test_module_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'input_prefix_ast_sha256':hashlib.sha256(ast.dump(module,include_attributes=False).encode()).hexdigest(),'test_helper':fixture.__file__,'test_helper_sha256':hashlib.sha256(pathlib.Path(fixture.__file__).read_bytes()).hexdigest(),'owner_module':owner.__file__,'owner_module_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'warm_rows':warm,'current_rows_unexecuted':ns['current'],'qualification':'Exact declared bounded warm-test fixtures only; no TRN original CAS/content admission, GP fit, statistical/issuer/production law or whole B114 closure claim.'}
(out/'inputs.json').write_text(json.dumps(inputs,default=encode,indent=2)+'\n');r={'backend_ready':strategy._botorch_ready,'accepted_positive':accepted,'rejected_inputs':rejected,'actual_local_rejection_reasons':traced['reasons'],'outward_return':returned,'actual_logs':logs,'public_checkpoint_state':state,'rejected_ids_visible':{x:x in observable for x in rejected},'reasons_visible':{x:x in observable for x in traced['reasons']},'fit_executed':False,'result':'FAIL original rejected-record reasons visibility; accepted positive control PASS','scope':'warm_start owned boundary only; no required report API/field format imposed'};(out/'observations.json').write_text(json.dumps(r,default=encode,indent=2)+'\n');print(json.dumps(r,default=encode,indent=2),flush=True)
# Independent control: remove only acceptance effect with metadata/logger/function markers preserved.
pre=inspect.getsource(owner.BayesianOptimizer.warm_start);old='self._warm_evals.extend(accepted)';new='pass  # self._warm_evals.extend(accepted) marker retained';assert pre.count(old)==1;post=pre.replace(old,new);(out/'acceptance-preimage.py').write_text(pre);(out/'acceptance-postimage.py').write_text(post)
control=owner.BayesianOptimizer(ns['simple_space'],strategy._config);namespace=dict(vars(owner));exec(compile(textwrap.dedent(post),str(out/'acceptance-postimage.py'),'exec'),namespace);namespace['warm_start'](control,warm);assert len(control._warm_evals)==0,'acceptance removal unexpectedly retained rows';(out/'acceptance-removal.json').write_text(json.dumps({'preimage_sha256':hashlib.sha256(pre.encode()).hexdigest(),'postimage_sha256':hashlib.sha256(post.encode()).hexdigest(),'actual_accepted':len(control._warm_evals),'positive_expected_accepted':8,'semantic_expected_failure':'original accepted-count assertion would fail0vs8','source_files_changed':False,'qualification':'Separate accepted-corpus effect discriminator; original reason visibility already fails and cannot have positive removal proof until owner repair.'},indent=2)+'\n')
assert all(rejected_id in observable for rejected_id in rejected) and all(reason in observable for reason in traced['reasons']),'B114 rejected records and reasons disappeared from result/state/logs; no particular public report API required'
