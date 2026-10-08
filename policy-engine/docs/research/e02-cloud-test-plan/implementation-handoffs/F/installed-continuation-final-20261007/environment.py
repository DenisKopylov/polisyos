"""Record the real installed profile, dependencies and literal path environment."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import sys
import sysconfig
versions={dist.metadata['Name']:dist.version for dist in metadata.distributions() if dist.metadata.get('Name')}
keys=['PYTHONPATH','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','XLA_FLAGS','XLA_PYTHON_CLIENT_PREALLOCATE','JAX_PLATFORM_NAME','JAX_PLATFORMS']
print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'prefix':sys.prefix,'isolated':sys.flags.isolated,'sys_path':sys.path,'purelib':sysconfig.get_paths()['purelib'],'dependencies':versions,'environment':{key:os.environ.get(key,'absent') for key in keys},'new_quota':False,'platform':platform.platform(),'cpu_count_observed':os.cpu_count(),'DoWhy_status':'External locked3.12 reference/backend profile unchanged; version/resource observation is not a native backend positive in this162case wave.'},indent=2,sort_keys=True))
