"""Run frozen test carriers in a neutral Python -I installation and bind origins."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import pytest

config = json.loads(Path(sys.argv[1]).read_text())
kind = sys.argv[2]
assert kind in ("wheel", "sdist")
scratch = Path(config["scratch"])
site = Path(sys.prefix) / "lib/python3.14/site-packages"
carrier = scratch / (kind + "-consumer")
assert sys.flags.isolated == 1
assert Path.cwd() == carrier
assert not any(Path(entry).is_relative_to(Path(config["source_root"])) for entry in sys.path if entry)
os.environ["E02_TEST_DOWHY_WORKER_PYTHON"] = config["worker_python"]
os.environ["E02_DOWHY_FIXTURE_PATH"] = str(carrier / "test_dowhy_worker.py")
os.environ["E02_GCM_FIXTURE_PATH"] = str(carrier / "test_gcm_backend_contract.py")
os.environ["E02_PROFILE_EXPECTED_JSON"] = str(scratch / "profile-expected.json")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
selectors = [str(carrier / item.split("::")[0]) + ("::" + item.split("::", 1)[1] if "::" in item else "")
             for item in config["selectors"]]
argv = ["-q", "-s", "-o", "addopts=", "--import-mode=importlib", "-p", "no:cacheprovider", *selectors]
if config.get("selection_expression"):
    argv += ["-k", config["selection_expression"]]
status = pytest.main(argv)
origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.copy().items()
           if name.startswith(("polisyos", "tools")) and getattr(module, "__file__", None)}
violations = {name: path for name, path in origins.items() if not Path(path).is_relative_to(site)}
assets = json.loads((scratch / "profile-expected.json").read_text())["assets"]
profile = site / "polisyos/foundry/methods/catalog/causal/_dowhy_profile"
for name, binding in assets.items():
    raw = (profile / name).read_bytes()
    assert len(raw) == binding["bytes"] and hashlib.sha256(raw).hexdigest() == binding["sha256"]
proof = {"source_sha": config["source_sha"], "source_tree": config["source_tree"],
         "python": platform.python_version(), "executable": sys.executable,
         "isolated": sys.flags.isolated, "cwd": str(Path.cwd()), "sys_path": sys.path,
         "pytest_argv": argv, "pytest_exit": int(status), "product_origins": origins,
         "origin_violations": violations, "six_assets_restored": assets,
         "authority": "known synthetic candidate computation; no production admission witness"}
(scratch / (kind + "-installed-proof.json")).write_text(json.dumps(proof, indent=2) + "\n")
assert not violations, violations
print(json.dumps({"source_sha": config["source_sha"], "owned_origins": len(origins),
                  "origin_violations": len(violations), "pytest_exit": int(status)}))
raise SystemExit(status)
