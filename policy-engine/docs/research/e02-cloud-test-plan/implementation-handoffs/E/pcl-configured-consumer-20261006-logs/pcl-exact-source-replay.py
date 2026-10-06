"""Replay focused assertions with exact historical module bytes, no checkout mutation."""
import hashlib
import importlib.abc
import importlib.util
import json
import subprocess
import sys

SOURCE = "58e2d97965c0826c44843a78dcb2f8698d9950a3"
PATHS = {
    "polisyos.foundry.methods.backends.numpy_runner": "policy-engine/src/polisyos/foundry/methods/backends/numpy_runner.py",
    "polisyos.foundry.methods.catalog.econometrics.advanced": "policy-engine/src/polisyos/foundry/methods/catalog/econometrics/advanced.py",
    "polisyos.foundry.execute._internal.graph": "policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py",
}
SOURCES = {module: subprocess.check_output(["git", "show", f"{SOURCE}:{path}"]) for module,path in PATHS.items()}
print(json.dumps({"source": SOURCE,"mode": "exact_git_blob_import_overlay", "modules": {module:{"path": PATHS[module],"sha256": hashlib.sha256(data).hexdigest(),"bytes":len(data)} for module,data in SOURCES.items()}}),flush=True)
class BlobLoader(importlib.abc.Loader):
    def create_module(self,spec):
        return None
    def exec_module(self,module):
        module.__file__ = f"git:{SOURCE}:{PATHS[module.__name__]}"
        if module.__name__.endswith(".graph"):
            module.__path__ = []
        exec(compile(SOURCES[module.__name__],module.__file__,"exec"),module.__dict__)
class BlobFinder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in SOURCES:
            return importlib.util.spec_from_loader(fullname,BlobLoader(),is_package=fullname.endswith(".graph"))
        return None
sys.meta_path.insert(0,BlobFinder())
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
