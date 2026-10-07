from pathlib import Path
import hashlib,json,warnings
import numpy as np
import polisyos.foundry.uncertainty as f
R=Path('/workspace/e02-E-continuation-20261006');O=Path(__file__).parent;rows=[]
for label,name,args in [('complex-CDF','empirical_cdf',(np.array([.5+.1j,.5-.1j]),)),('complex-U','admit_unit_uniform',(np.array([.5+2j]),)),('complex-weights','admit_empirical_weights',(np.array([1.+2j,1.-2j]),2)),('finite-total-overflow','admit_empirical_weights',([1e308,1e308],2))]:
 with warnings.catch_warnings(record=True) as observed:
  warnings.simplefilter('always')
  try:value=getattr(f,name)(*args)
  except Exception as exc:row={'case':label,'result':'refused','exception':type(exc).__name__,'reason':str(exc)}
  else:row={'case':label,'result':'admitted','projection':value.tolist()}
  row['warnings']=[str(w.message) for w in observed];rows.append(row)
result={'source_sha':'1e0eb2f6c589b74c6adae850b27af6d720dfa5ea','input_description':'complex NumPy arrays; finite huge real weights; exact full inputs in this script','cases':rows,'potential_boundary':'public helper receives object; complex mass/coordinate has no probability-domain ordering, imaginary components must not silently select a real law; investigate actual typed consumer reachability separately'}
(O/'unsupported-dtype-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
