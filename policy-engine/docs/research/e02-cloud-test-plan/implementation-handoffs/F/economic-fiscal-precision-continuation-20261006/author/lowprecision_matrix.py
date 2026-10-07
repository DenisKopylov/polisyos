from __future__ import annotations
import json,pathlib,sys
import jax,jax.numpy as jnp,numpy as np
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax,TaxSubsidy
p=pathlib.Path('/tmp/e02-F-continuation-20261006/economics/fiscal-precision')
def arr(v):
 a=np.asarray(v);return {'dtype':str(a.dtype),'shape':list(a.shape),'bytes_hex':a.tobytes().hex(),'values':np.asarray(v,dtype=np.float64).tolist()}
rows=[]
for x64 in [False,True]:
 with jax.enable_x64(x64):
  for dtype in [jnp.int32,jnp.int64,jnp.bool_,jnp.float16,jnp.bfloat16]:
   for kind,cls in [('income_tax',IncomeTax),('tax_subsidy',TaxSubsidy)]:
    for compiled in [False,True]:
     income=jnp.asarray([1.125,3.25,9.5,17.75],dtype=dtype)
     state=GlobalState.empty(n_agents=4,n_firms=1).replace(agents=GlobalState.empty(n_agents=4,n_firms=1).agents.replace(income=income,reported_income=income))
     mech=cls(rate=.1,n_agents=4)
     emit=jax.jit(lambda s,k:mech.emit_patches(s,k)) if compiled else mech.emit_patches
     patch,key=emit(state,jax.random.PRNGKey(0))
     rows.append({'x64':x64,'requested_input_dtype':str(np.dtype(dtype)),'actual_income':arr(income),'kind':kind,'compiled':compiled,'rate_attribute':arr(mech.rate),'sector_weights':arr(mech.target_sector_mask) if kind=='tax_subsidy' else None,'delta':arr(patch['agents.income'][0]['delta']),'government':arr(patch['government.balance'][0]['delta']),'key':arr(key)})
result={'cases':len(rows),'scope':'only native existing lowerfloat/integer input behavior comparison; no new integer-income semantics','rows':rows}
output=p/(sys.argv[-1]+'.json');output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':str(output),'cases':len(rows)}))
