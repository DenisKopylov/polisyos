"""Read exact native dependency and candidate provider origins without fitting."""
import importlib
import importlib.metadata
import json
import platform
from pathlib import Path
import sys

packages = {}
for name in ("numpy", "scipy", "scikit-learn", "pytest", "pydantic"):
    module_name = "sklearn" if name == "scikit-learn" else name
    module = importlib.import_module(module_name)
    packages[name] = {"version": importlib.metadata.version(name), "module_origin": str(Path(module.__file__).resolve())}
origins = {}
for name in ("polisyos.foundry.methods.catalog.causal.tmle_core", "polisyos.foundry.methods.catalog.causal.nuisance_layer", "polisyos.foundry.methods.catalog.causal.treatment_effects", "polisyos.ir.analytics.causal", "polisyos.scientist.governance.passes.confidence_pass", "polisyos.foundry.methods.components.value_evidence"):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(Path("/workspace/e02-F-tmle-20261006/policy-engine/src")), path
    origins[name] = str(path)
print(json.dumps({"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "native_dependencies": packages, "candidate_module_origins": origins, "backend_scope": "Native NumPy/scikit-learn; no DoWhy/EconML worker run or exclusion-as-witness", "environment_mutations": False}, indent=2))
