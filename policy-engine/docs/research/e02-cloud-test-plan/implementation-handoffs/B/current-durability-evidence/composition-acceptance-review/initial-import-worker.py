"""Fresh process performs selected import order before actual registry fixture import."""
import asyncio,importlib.util,json,pathlib,sys
if sys.argv[1]=='chain-first':
 from polisyos.foundry.methods.backends import chain_executor
 from polisyos.foundry.methods.backends import async_chain_executor
else:
 from polisyos.foundry.methods.backends import async_chain_executor
 from polisyos.foundry.methods.backends import chain_executor
p=pathlib.Path(__file__).with_name('test_acceptance.py');spec=importlib.util.spec_from_file_location('independent_actual_composition',p);fixture=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fixture;spec.loader.exec_module(fixture)
r,c,na,nb,_=fixture.scalar_chain();chain=c.build(validate_semantics=fixture.Level.STRICT);result=asyncio.run(chain_executor.execute_heterogeneous_chain_async(chain,state={'value':100},registry=r));assert result.final_state['result']==21
print('RESULT:'+json.dumps({'order':sys.argv[1],'value':result.final_state['result'],'node_count':len(result.node_results),'actual_edges':len(chain.bindings)}))
