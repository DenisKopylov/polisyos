"""Fresh process performs selected import order before actual registry fixture import."""
import asyncio,importlib.abc,importlib.util,json,pathlib,sys
if sys.argv[1]=='missing':
 from polisyos.foundry.methods.backends import chain_executor
 class MissingModule(importlib.abc.MetaPathFinder):
  def find_spec(self,fullname,path=None,target=None):
   if fullname=='polisyos.foundry.methods.backends.async_chain_executor':raise ModuleNotFoundError('Injected required async module absence',name=fullname)
 sys.modules.pop('polisyos.foundry.methods.backends.async_chain_executor',None);sys.meta_path.insert(0,MissingModule())
elif sys.argv[1]=='chain-first':
 from polisyos.foundry.methods.backends import chain_executor
 from polisyos.foundry.methods.backends import async_chain_executor
else:
 from polisyos.foundry.methods.backends import async_chain_executor
 from polisyos.foundry.methods.backends import chain_executor
p=pathlib.Path(__file__).with_name('test_acceptance.py');spec=importlib.util.spec_from_file_location('independent_actual_composition',p);fixture=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fixture;spec.loader.exec_module(fixture)
r,c,na,nb,_=fixture.scalar_chain();chain=c.build(validate_semantics=fixture.Level.STRICT)
if sys.argv[1]=='missing':
 try:asyncio.run(chain_executor.execute_heterogeneous_chain_async(chain,state={'value':100},registry=r))
 except ModuleNotFoundError as exc:print('RESULT:'+json.dumps({'type':type(exc).__name__,'name':exc.name,'message':str(exc),'injection':'meta-path controlled required-module absence, not physical installation removal'}));sys.exit(0)
 else:raise AssertionError('required missing dependency hidden')
result=asyncio.run(chain_executor.execute_heterogeneous_chain_async(chain,state={'value':100},registry=r));assert result.final_state['result']==21
print('RESULT:'+json.dumps({'order':sys.argv[1],'value':result.final_state['result'],'node_count':len(result.node_results),'actual_edges':len(chain.bindings)}))
