from pathlib import Path
from fractions import Fraction
import hashlib,json,subprocess,warnings
import numpy as np
import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty import sampling_admission as c
R=Path('/workspace/e02-E-continuation-20261006');O=Path(__file__).parent;REF='ec042402ec91fbdcb51006852e29fe67f38d9452';p='policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py';expected=subprocess.check_output(['git','show',REF+':'+p],cwd=R);assert Path(c.__file__).read_bytes()==expected
small=np.longdouble('1e-400');assert small>0 and np.isfinite(small);rows=[]
for label,name,args in [('longdouble-first-weight','admit_empirical_weights',(np.array([small,1],dtype=np.longdouble),2)),('longdouble-interior-weight','admit_empirical_weights',(np.array([.5,small,.5],dtype=np.longdouble),3)),('longdouble-first-CDF','empirical_cdf',(np.array([small,1],dtype=np.longdouble),)),('longdouble-range','admit_float32_range',(np.array([[small]],dtype=np.longdouble),)),('longdouble-uniform','admit_unit_uniform',(np.array([small],dtype=np.longdouble),)),('object-Fraction-weight','admit_empirical_weights',(np.array([Fraction(1,10**400),Fraction(1)],dtype=object),2))]:
 with warnings.catch_warnings(record=True) as observed:
  warnings.simplefilter('always')
  try:value=getattr(c,name)(*args)
  except Exception as e:row={'case':label,'outcome':'refused','exception':type(e).__name__,'reason':str(e)}
  else:row={'case':label,'outcome':'admitted','output':value.tolist(),'output_first_zero':bool(value.flat[0]==0)}
  row['warnings']=[str(w.message) for w in observed];rows.append(row)
assert Path(c.__file__).read_bytes()==expected
result={'source_sha':REF,'source_sha256':hashlib.sha256(expected).hexdigest(),'longdouble_bits':np.finfo(np.longdouble).bits,'raw_1e-400_nonzero':bool(small>0),'cases':rows,'scope':'nonzero positive category/range support lost during float128/object→float64 cast; no arbitrary-real exactness promised'}
(O/'longdouble-support-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
