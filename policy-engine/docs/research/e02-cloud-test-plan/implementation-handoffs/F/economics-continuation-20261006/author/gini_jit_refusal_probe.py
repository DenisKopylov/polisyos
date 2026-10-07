from pathlib import Path
import hashlib,json,os
import jax
import jax.numpy as jnp
import polisyos.foundry.agent_sim.distributions as d
for values in ([-2.,1.],[-1.,2.]):
    try:
        out=jax.jit(d.compute_gini_hard)(jnp.asarray(values),jnp.ones(2,dtype=bool))
        jax.block_until_ready(out)
    except (RuntimeError,ValueError) as exc:
        assert 'classical Gini requires finite nonnegative active values' in str(exc)
        print(json.dumps(dict(input=values,exception_type=type(exc).__name__,canonical_refusal=True,configured_error_mode=os.environ.get('EQX_ON_ERROR'),origin=d.__file__,source_sha256=hashlib.sha256(Path(d.__file__).read_bytes()).hexdigest())),flush=True)
    else:
        raise AssertionError('invalid classical Gini published: '+str(out))
