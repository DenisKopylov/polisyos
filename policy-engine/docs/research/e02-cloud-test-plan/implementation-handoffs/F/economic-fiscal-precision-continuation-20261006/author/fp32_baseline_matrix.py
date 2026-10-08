from __future__ import annotations
import json,pathlib,sys
import jax,jax.numpy as jnp,numpy as np
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax,TaxSubsidy
from polisyos.foundry.execute.executor import apply_patch_map
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
p=pathlib.Path('/tmp/e02-F-continuation-20261006/economics/fiscal-precision')
def arr(v):
 a=np.asarray(v);return {'dtype':str(a.dtype),'shape':list(a.shape),'bytes_hex':a.tobytes().hex(),'values':a.tolist()}
rows=[]
with jax.enable_x64(False):
 for kind,cls in [('income_tax',IncomeTax),('tax_subsidy',TaxSubsidy)]:
  for rate in [0.,.1,.2,.3333333,.5,1.]:
   for compiled in [False,True]:
    state=GlobalState.empty(n_agents=4,n_firms=1);income=jnp.asarray([80.25,19.75,100.125,1000.5],dtype=jnp.float32)
    state=state.replace(agents=state.agents.replace(income=income,reported_income=income,active=jnp.asarray([True,False,True,True])),government_balance=jnp.asarray(17.,dtype=jnp.float32))
    mech=cls(rate=rate,n_agents=4);target=jnp.asarray([True,True,False,True])
    emit=jax.jit(lambda s,k:mech.emit_patches(s,k,target_mask=target)) if compiled else lambda s,k:mech.emit_patches(s,k,target_mask=target)
    patches,key=emit(state,jax.random.PRNGKey(29))
    after=apply_patch_map(state,patches,slot_registry=DEFAULT_SLOT_REGISTRY,merge_registry=DEFAULT_MERGE_RULE_REGISTRY,default_node_id='same')
    leaves,tree=jax.tree_util.tree_flatten(after)
    rows.append({'kind':kind,'rate':rate,'compiled':compiled,'rate_attribute':arr(mech.rate),'patches':{slot:[{k:arr(v) for k,v in record.items()} for record in records] for slot,records in patches.items()},'state_tree':str(tree),'all_state_leaves':[arr(v) for v in leaves],'key':arr(key)})
result={'jax_enable_x64':False,'dtype':'float32','cases':len(rows),'rows':rows}
output=p/(sys.argv[-1]+'.json');output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':str(output),'cases':len(rows),'all_complete_state_patch_key_bytes_recorded':True}))
