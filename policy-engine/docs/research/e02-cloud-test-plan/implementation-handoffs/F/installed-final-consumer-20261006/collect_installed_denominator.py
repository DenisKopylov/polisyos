"""Cheap exact selected/deselected census; executes no test body or estimator."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import pytest

config = json.loads(Path(sys.argv[1]).read_text())
kind = sys.argv[2]
assert kind in ("wheel", "sdist") and sys.flags.isolated == 1
scratch = Path(config["scratch"])
carrier = scratch / (kind + "-consumer")
assert Path.cwd() == carrier
os.environ.update({"E02_TEST_DOWHY_WORKER_PYTHON": config["worker_python"],
                   "E02_DOWHY_FIXTURE_PATH": str(carrier / "test_dowhy_worker.py"),
                   "E02_GCM_FIXTURE_PATH": str(carrier / "test_gcm_backend_contract.py"),
                   "E02_PROFILE_EXPECTED_JSON": str(scratch / "profile-expected.json"),
                   "E02_TMLE_FIXTURE_PATH": str(carrier / "test_tmle_common_report.py")})
selected, deselected = [], []
class Observer:
    def pytest_collection_finish(self, session):
        selected.extend(item.nodeid for item in session.items)
    def pytest_deselected(self, items):
        deselected.extend(item.nodeid for item in items)

selectors = []
for selector in config["selectors"]:
    if selector.endswith("::test_real_configured_method_job_projects_exact_native_eif_and_cas_reader"):
        selector = "test_installed_native_boundaries.py::test_installed_native_tmle_configured_job_and_actual_boundaries"
    parts = selector.split("::", 1)
    selectors.append(str(carrier / parts[0]) + ("::" + parts[1] if len(parts) == 2 else ""))
status = pytest.main(["--collect-only", "-q", "-o", "addopts=", "--import-mode=importlib",
                     "-p", "no:cacheprovider", *selectors, "-k", config["selection_expression"]],
                    plugins=[Observer()])
native = json.loads((Path(config["review_scratch"]) / (kind + "-independent-consumer-proof.json")).read_text())
assert selected == native["collection"]
assert status == 0 and len(selected) == 199 and len(deselected) == 5
record = {"source_sha": config["source_sha"], "source_tree": config["source_tree"], "profile": kind,
          "check": "PASS", "pytest_exit": int(status), "selected": selected, "deselected": deselected,
          "selection_expression": config["selection_expression"],
          "scope": "Actual collection only; test bodies/worker/estimator were not executed. Full selected node sequence equals previous actual native wave."}
(Path(config["review_scratch"]) / (kind + "-collection-denominator.json")).write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"check": "PASS", "selected": len(selected), "deselected": deselected}))
raise SystemExit(status)
