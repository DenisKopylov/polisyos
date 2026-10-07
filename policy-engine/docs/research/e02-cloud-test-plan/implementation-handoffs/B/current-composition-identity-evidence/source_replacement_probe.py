import hashlib,json,pathlib,uuid
from typing import ClassVar,Any
from polisyos.foundry.methods.base import ComplexityClass,ComputeBackend,FidelityLevel,MethodMetadata,MethodSignature,ParameterSpec,SlotSpec,SlotType,Unit
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.selection.registry import MethodRegistry
import polisyos.foundry.methods.backends.checkpointing as module
slot=lambda n:SlotSpec(n,SlotType.SCALAR,Unit('count','1'),shape=())
producer=MethodSignature(name='source',namespace='tests.e02_identity',version='1.0.0',input_slots=frozenset(),output_slots=frozenset({slot('product')}),parameters=(ParameterSpec('factor',default=2,is_static=True),),backend=ComputeBackend.NUMPY,fidelity=FidelityLevel.LOW,complexity=ComplexityClass.O_1,supports_jit=False,supports_vmap=False,supports_grad=False)
consumer=MethodSignature(name='consumer',namespace='tests.e02_identity',version='1.0.0',input_slots=frozenset({slot('operand')}),output_slots=frozenset({slot('total')}),parameters=(ParameterSpec('increment',default=1),),requires=frozenset({producer.fqn}),backend=ComputeBackend.NUMPY,fidelity=FidelityLevel.LOW,complexity=ComplexityClass.O_1,supports_jit=False,supports_vmap=False,supports_grad=False)
metadata=MethodMetadata(description='Real source identity fixture',tags=frozenset({'test'}))
class Original:
 signature:ClassVar=producer
 metadata:ClassVar=metadata
 @staticmethod
 def pure_step(state,params):return {'product':state['x']*params['factor']}
class Replacement:
 signature:ClassVar=producer
 metadata:ClassVar=metadata
 @staticmethod
 def pure_step(state,params):return {'product':state['x']*(params['factor']+1)}
class Consumer:
 signature:ClassVar=consumer
 metadata:ClassVar=metadata
 @staticmethod
 def pure_step(state,params):return {'total':state+params['increment']}
MethodRegistry.reset_instance();registry=MethodRegistry.get_instance();registry.register(Original);registry.register(Consumer)
composer=MethodComposer(registry=registry);a=composer.add(producer.fqn);b=composer.add(consumer.fqn);composer.connect(a,b,{'product':'operand'});chain=composer.build(validate_semantics=False)
fixture=pathlib.Path('_build/e02-B-current-composition/raw')/('source-replacement-'+uuid.uuid4().hex);fixture.mkdir()
old=module.CheckpointingChainExecutor(registry=registry,checkpoint_dir=fixture).execute(chain,initial_state={'x':3},seed=7)
checkpoint=module.ChainCheckpoint.load(next(fixture.glob('*_0001_*.json')))
registry.register(Replacement,override=True)
cold=module.CheckpointingChainExecutor(registry=registry).execute(chain,initial_state={'x':3},seed=7)
warm=module.CheckpointingChainExecutor(registry=registry).execute(chain,initial_state={'x':3},checkpoint=checkpoint,seed=7)
assert old.final_state['total']==7 and cold.final_state['total']==10 and warm.final_state['total']==7
assert consumer.requires==frozenset({producer.fqn}) and a.id in chain.dag.predecessors[b.id]
print(json.dumps({'property':'Actual source replacement is NOT bound by existing request digest; cold10 versus accepted warm7 on same compiledsignature/config/input/seed','fixture':str(fixture.resolve()),'source_module':module.__file__,'source_module_sha256':hashlib.sha256(pathlib.Path(module.__file__).read_bytes()).hexdigest(),'inputs':{'x':3,'factor':2,'increment':1,'seed':7},'compiled_required_edge':[str(a.id),str(b.id)],'signature_digest_unchanged':Original.signature.stable_digest()==Replacement.signature.stable_digest(),'old_outputs':[r.output for _,r in old.node_results],'cold_outputs':[r.output for _,r in cold.node_results],'warm_outputs':[r.output for _,r in warm.node_results]},indent=2))
