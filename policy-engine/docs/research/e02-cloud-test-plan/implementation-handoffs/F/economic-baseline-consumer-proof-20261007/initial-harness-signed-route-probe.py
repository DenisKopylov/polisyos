import jax
import jax.numpy as jnp
import numpy as np
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.composite import CompositeState, CompositeStateConfig, CompositeExecutor
from polisyos.foundry.plugins.economics import EconomicsPlugin
from polisyos.foundry.plugins.training_adapter import EconomicsTrainingAdapter, _native_to_composite
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.agent_sim.training import TrainingConfig, collect_trajectory
from polisyos.foundry.contracts.fidelity import FidelityLevel
with jax.enable_x64(False):
 registry=PluginRegistry(); registry.register(EconomicsPlugin())
 cfg=DomainConfig(n_agents=10, max_agents=10, time_horizon=4)
 config=CompositeStateConfig(domains={'economics':cfg}, global_seed=31)
 composite=CompositeState.create(config,registry)
 es=composite.get_domain('economics')
 es=es.replace(agents=es.agents.replace(wealth=jnp.zeros(10),income=jnp.zeros(10),wage=jnp.full((10,),30.),skill_level=jnp.full((10,),2.),employed=jnp.ones(10,dtype=bool)),policy=es.policy.replace(transfer_rate=jnp.asarray(0.),unemployment_benefit=jnp.asarray(0.),minimum_wage=jnp.asarray(0.),interest_rate=jnp.asarray(0.)))
 composite=composite.update_domain('economics',es.update_aggregates())
 executor=CompositeExecutor(['economics'],registry)
 adapter=EconomicsTrainingAdapter.from_composite(composite,executor); assert adapter is not None
 traincfg=TrainingConfig(n_episodes=1,steps_per_episode=1,ppo_epochs=1,horizon=4,include_expectations=False)
 actor=ActorCritic(jax.random.PRNGKey(4), adapter.observation_dim(traincfg),hidden_dims=(8,4))
 native=adapter.to_native_state(seed=19)
 bridged=adapter.make_executor(actor,traincfg)
 seam=bridged.mechanisms[0]
 key=jax.random.PRNGKey(7)
 after,_=TemporalConsumptionMechanism.apply(seam,native,key,FidelityLevel.HARD)
 domain=_native_to_composite(after,config=seam._bridge_config,n_agents=10,max_agents=10,wage_growth_rate=adapter.wage_growth_rate).get_domain('economics')
 _,bridgekey=jax.random.split(key); _,dk=jax.random.split(bridgekey)
 enabled=set(seam._bridge_config.domains['economics'].enabled_mechanisms)
 for m in registry.get('economics').get_mechanisms():
  if m.name not in enabled: continue
  dk,mk=jax.random.split(dk)
  domain=m.apply(domain,rng_key=mk)
  print(m.name,'wealth',np.asarray(domain.agents.wealth).tolist(),'income',np.asarray(domain.agents.income).tolist(),flush=True)
 assert np.all(np.asarray(domain.agents.wealth)<0)
 for label,invoke in [('seam',lambda: seam.apply(native,key,FidelityLevel.HARD)),('PPO_trajectory',lambda: collect_trajectory(bridged,native,actor,traincfg))]:
  try:
   result=invoke(); jax.block_until_ready(result); print(label,'ERROR accepted signed population')
  except Exception as e: print(label,type(e).__module__+'.'+type(e).__name__,str(e),flush=True)
