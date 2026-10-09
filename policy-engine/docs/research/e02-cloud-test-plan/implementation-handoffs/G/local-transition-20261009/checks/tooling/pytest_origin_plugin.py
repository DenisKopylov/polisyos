"""Capture import provenance for exact-candidate focused test runs."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def pytest_sessionfinish(session, exitstatus):
    candidate = Path(os.environ["E02_CANDIDATE_ROOT"]).resolve()
    product = candidate / "policy-engine"
    imports = []
    for name, module in sorted(sys.modules.items()):
        if not (name == "polisyos" or name.startswith("polisyos.") or name == "tools" or name.startswith("tools.") or name == "tests" or name.startswith("tests.")):
            continue
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        try:
            rel = path.relative_to(product).as_posix()
        except ValueError:
            rel = None
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        imports.append({"module": name, "origin": str(path), "candidate_relative_path": rel, "sha256": digest})
    destination = Path(os.environ["E02_IMPORT_ORIGINS_OUT"])
    destination.write_text(json.dumps({"exitstatus": int(exitstatus), "candidate_root": str(candidate), "candidate_product_root": str(product), "modules": imports}, indent=2, sort_keys=True) + "\n")
