"""Bounded existing B CAS source + existing D consumer experiment; no source files copied.

Not an integrated Git candidate or whole B adoption. The parent and fresh child
resolve the same exact Git source bytes, verified before execution.
"""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

_packet = json.loads(Path(__file__).with_name("B333-module-map.json").read_text())
class _ExactGitCAS(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _packet["modules"]:
            row = _packet["modules"][fullname]
            return importlib.util.spec_from_loader(fullname, self, origin="git:"+_packet["source"]+":"+row["path"])
        return None
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        row = _packet["modules"][module.__name__]
        source = subprocess.check_output(["git", "-C", _packet["repository"], "show", _packet["source"]+":"+row["path"]])
        digest = hashlib.sha256(source).hexdigest()
        if digest != row["B_sha256"] or len(source) != row["B_bytes"]:
            raise ImportError("Exact B CAS source identity changed")
        module.__file__ = module.__spec__.origin
        exec(compile(source, module.__spec__.origin, "exec"), module.__dict__)
        namespace = os.environ.get("E02_CAS_PAIR_ORIGINS")
        if namespace:
            with open(namespace+"."+str(os.getpid())+".jsonl", "a") as stream:
                stream.write(json.dumps({"pid":os.getpid(), "module":module.__name__, "source":_packet["source"], "path":row["path"], "blob":row["B_blob"], "sha256":digest, "bytes":len(source)})+"\n")

sys.meta_path.insert(0, _ExactGitCAS())
