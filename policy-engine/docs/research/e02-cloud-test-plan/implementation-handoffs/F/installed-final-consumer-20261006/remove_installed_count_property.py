"""Remove generic selected-source/count properties only in installed memory."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pytest
from polisyos.foundry.methods.backends import dispatch

config = json.loads(Path(sys.argv[1]).read_text())
kind, mode = sys.argv[2:]
assert kind in ("wheel", "sdist") and mode in ("no_consumption", "broad_identity_skip")
assert sys.flags.isolated == 1
site = Path(sys.prefix) / "lib/python3.14/site-packages"
module = Path(dispatch.__file__)
assert module.is_relative_to(site)
disk = module.read_bytes()
target = dispatch._consumed_raw_output_keys
if mode == "no_consumption":
    def replacement(*, method_class, signature, raw_output, slot_outputs):
        return frozenset()
    selection = "nan_inf_vector and consumed_source"
else:
    def replacement(*, method_class, signature, raw_output, slot_outputs):
        if not isinstance(raw_output, Mapping):
            return frozenset({"output"})
        return frozenset(key for key, value in raw_output.items()
                         if any(value is canonical for canonical in slot_outputs.values()))
    selection = "unused_alias_retains_anomalies"

def markers():
    return {"name": target.__name__, "qualname": target.__qualname__, "module": target.__module__,
            "doc": target.__doc__, "signature": str(inspect.signature(target)),
            "annotations": repr(target.__annotations__), "id": id(target)}

original = target.__code__
before = markers()
target.__code__ = replacement.__code__
assert markers() == before
carrier = Path(config["scratch"]) / (kind + "-consumer")
assert Path.cwd() == carrier
print(json.dumps({"source_sha": config["source_sha"], "profile": kind, "property_removal": mode,
                  "markers_retained": before, "actual_installed_module": str(module),
                  "disk_sha256": hashlib.sha256(disk).hexdigest(), "source_files_modified": False}))
try:
    status = pytest.main([str(carrier / "test_output_anomaly_count.py"), "-k", selection,
                         "-o", "addopts=", "-p", "no:cacheprovider", "-q", "-s", "--tb=short",
                         "--basetemp=" + str(Path(config["review_scratch"]) / (kind + "-removed-" + mode))])
finally:
    target.__code__ = original
assert module.read_bytes() == disk
raise SystemExit(status)
