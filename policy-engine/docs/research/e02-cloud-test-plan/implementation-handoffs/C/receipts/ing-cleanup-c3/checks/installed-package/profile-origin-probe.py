from __future__ import annotations
import hashlib, importlib.metadata as metadata, json, os, sys, zipfile
from pathlib import Path
from packaging.requirements import Requirement
from jsonschema import Draft202012Validator, FormatChecker
import jsonschema
import polisyos
import polisyos.fabric.data_plane.streaming as streaming
import polisyos.fabric.data_plane.modes as modes
import polisyos.fabric.data_plane.schema_rows as schema_rows
wheel=Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C3/raw/installed-current/07bbb61/dist/policy_engine-0.1.0-py3-none-any.whl")
source_root=Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C3/raw/installed-current/07bbb61/source/policy-engine").resolve()
dist=metadata.distribution("policy-engine")
reqs=[Requirement(line) for line in (dist.metadata.get_all("Requires-Dist") or [])]
jsonschema_req=next(req for req in reqs if req.name.lower()=="jsonschema")
assert jsonschema_req.marker is None, f"jsonschema requirement is conditional: {jsonschema_req}"
assert "format-nongpl" in {item.lower() for item in jsonschema_req.extras}, jsonschema_req
site_packages=Path(dist.locate_file("")).resolve()
modules={
  "polisyos": Path(polisyos.__file__).resolve(),
  "streaming": Path(streaming.__file__).resolve(),
  "modes": Path(modes.__file__).resolve(),
  "schema_rows": Path(schema_rows.__file__).resolve(),
  "jsonschema": Path(jsonschema.__file__).resolve(),
}
for name,path in modules.items():
  assert "site-packages" in path.parts, (name,str(path))
  assert source_root not in path.parents, (name,str(path))
expected_members={
  "streaming":"polisyos/fabric/data_plane/streaming.py",
  "modes":"polisyos/fabric/data_plane/modes.py",
  "schema_rows":"polisyos/fabric/data_plane/schema_rows.py",
  "polisyos":"polisyos/__init__.py",
}
with zipfile.ZipFile(wheel) as z:
  for name,member in expected_members.items():
    installed=modules[name]
    expected=hashlib.sha256(z.read(member)).hexdigest()
    actual=hashlib.sha256(installed.read_bytes()).hexdigest()
    assert actual==expected, (name,actual,expected)
    modules[name+"_wheel_sha256"]=expected
schema={"type":"object","properties":{"created_at":{"type":"string","format":"date-time"}},"required":["created_at"],"additionalProperties":False}
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema,format_checker=FormatChecker())
valid_errors=list(validator.iter_errors({"created_at":"2026-10-07T00:00:00Z"}))
invalid_format_errors=list(validator.iter_errors({"created_at":"not-a-date"}))
invalid_extra_errors=list(validator.iter_errors({"created_at":"2026-10-07T00:00:00Z","forged":True}))
assert not valid_errors
assert invalid_format_errors and invalid_extra_errors
assert os.environ.get("PYTHONPATH") is None
result={
  "profile": {"python":sys.version,"executable":str(Path(sys.executable).resolve()),"isolated":bool(sys.flags.isolated),"safe_path":bool(sys.flags.safe_path),"pytest_present":any(d.metadata.get("Name","").lower()=="pytest" for d in metadata.distributions()),"hnswlib_present":any(d.metadata.get("Name","").lower()=="hnswlib" for d in metadata.distributions()),"PYTHONPATH":os.environ.get("PYTHONPATH")},
  "distribution": {"name":dist.metadata["Name"],"version":dist.version,"site_packages":str(site_packages),"jsonschema_requirement":str(jsonschema_req),"jsonschema_requirement_marker":jsonschema_req.marker},
  "jsonschema": {"version":metadata.version("jsonschema"),"module_origin":str(modules["jsonschema"]),"schema_dialect":Draft202012Validator.META_SCHEMA["$schema"],"valid_instance_errors":len(valid_errors),"bad_datetime_errors":len(invalid_format_errors),"extra_property_errors":len(invalid_extra_errors)},
  "modules": {name:str(path) for name,path in modules.items() if not name.endswith("_wheel_sha256")},
  "byte_hashes": {name+"_installed_sha256":hashlib.sha256(modules[name].read_bytes()).hexdigest() for name in expected_members},
  "wheel_hashes": {name+"_wheel_sha256":digest for name,digest in modules.items() if name.endswith("_wheel_sha256")},
  "import_path":sys.path,
}
print(json.dumps(result,sort_keys=True,separators=(",",":")))
