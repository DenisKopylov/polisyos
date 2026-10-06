from __future__ import annotations
import hashlib,importlib.metadata as md,json,sys,zipfile
from pathlib import Path
root=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source-extract/source/policy-engine').resolve();wheel=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/dist-wheel/policy_engine-0.1.0-py3-none-any.whl');before=list(sys.path);d=md.distribution("policy-engine");site=Path(d.locate_file("")).resolve()
import tools.devx.workspace.doctor as doctor
o=Path(doctor.__file__).resolve();member="tools/devx/workspace/doctor.py"
with zipfile.ZipFile(wheel) as z:b=z.read(member)
actual=o.read_bytes()
assert o.is_relative_to(site) and actual==b
added=[x for x in sys.path if x not in before]
assert added==[str(root)],(before,sys.path,added)
print(json.dumps({"module_origin":str(o),"module_sha256":hashlib.sha256(actual).hexdigest(),"site_packages":str(site),"wheel_member":member,"wheel_byte_identity":True,"intended_checkout_root_insertion":added,"source_root_not_inserted":True},sort_keys=True))
