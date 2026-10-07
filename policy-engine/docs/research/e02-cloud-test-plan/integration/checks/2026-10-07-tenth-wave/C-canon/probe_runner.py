from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder
from pathlib import Path

BASE = Path(__file__).resolve().parent
GROOT = Path(os.environ["C_CANON_GROOT"]).resolve()
CANDIDATE_SHA = "55b45d9a5c95c3b773fc3b4d8679786b3993eb1e"
CANDIDATE_TREE = "70ed14e004063536ff3a12d30d14d9bdd79a4916"
CANDIDATE_ROOT = BASE / "candidate" / "policy-engine"
SOURCE_ROOT = CANDIDATE_ROOT / "src"
RESULTS = BASE / "results" / "attempt2"
RESULTS.mkdir(exist_ok=True)

preloaded = sorted(name for name in sys.modules if name == "polisyos" or name.startswith("polisyos."))
if preloaded:
    print(json.dumps({"runner_status": "ERROR_PRELOADED_POLISYOS", "preloaded": preloaded}))
    raise SystemExit(80)

class CandidateOnlyPolisyosFinder(MetaPathFinder):
    """Allow Polisyos imports only from the isolated exact-candidate source tree."""

    def find_spec(self, fullname, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname != "polisyos" and not fullname.startswith("polisyos."):
            return None
        search_path = [str(SOURCE_ROOT)] if fullname == "polisyos" else path
        spec = PathFinder.find_spec(fullname, search_path, target)
        if spec is None:
            raise ModuleNotFoundError(f"{fullname} absent from exact candidate source")
        roots = []
        if spec.origin and spec.origin not in {"built-in", "frozen"}:
            roots.append(Path(spec.origin).resolve())
        if spec.submodule_search_locations:
            roots.extend(Path(p).resolve() for p in spec.submodule_search_locations)
        if not roots or any(not p.is_relative_to(SOURCE_ROOT.resolve()) for p in roots):
            raise ModuleNotFoundError(f"{fullname} resolved outside exact candidate source: {roots}")
        return spec

sys.meta_path.insert(0, CandidateOnlyPolisyosFinder())
sys.path.insert(0, str(SOURCE_ROOT))
os.chdir(CANDIDATE_ROOT)

import pytest  # noqa: E402

selectors = [
    "tests/unit/core/artifacts/test_ir_adapter.py",
    "tests/unit/ir/analytics/test_ncm.py",
    "tests/unit/fabric/test_entity_resolution.py::test_probabilistic_entity_resolution_is_explainable_and_reversible",
]
pytest_junit = RESULTS / "pytest.junit.xml"
pytest_temp = RESULTS / "pytest-temp"
pytest_temp.mkdir(exist_ok=True)
pytest_argv = [
    "--noconftest",
    "-o", "addopts=",
    "-p", "no:cacheprovider",
    "-q",
    "--junitxml", str(pytest_junit),
    "--basetemp", str(pytest_temp),
    *selectors,
]
start = time.monotonic()
pytest_exit = int(pytest.main(pytest_argv))
pytest_seconds = time.monotonic() - start

probe = {
    "public_typed_manifest_roundtrip": "UNRUN",
    "json_mapping_profile_roundtrip": "UNRUN",
}
try:
    from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.artifacts.contracts import CanonInfo
    from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact

    cas_dir = RESULTS / "probe-cas"
    core_store = FileSystemCAS(cas_dir)
    typed_store = ensure_ir_artifact_store(core_store)
    payload = {"profile_probe": "canonical-ir-json-mapping", "value": 17}
    ref = put_json_artifact(
        typed_store,
        payload,
        kind="test.canon.mapping-probe",
        schema_name="test.canon.mapping-probe",
        schema_version="1.0",
    )
    artifact_id = ref["artifact_id"]
    typed_manifest = typed_store.get_manifest(artifact_id)
    typed_loaded = get_json_artifact(typed_store, artifact_id)
    probe["public_typed_manifest_roundtrip"] = "PASS" if typed_loaded == payload else "FAIL"
    probe["typed_manifest_type"] = f"{type(typed_manifest).__module__}.{type(typed_manifest).__qualname__}"

    canon_json = CanonInfo().model_dump(mode="json")
    separators = canon_json.get("separators")
    probe["CanonInfo_model_dump_mode_json_separators"] = separators
    probe["CanonInfo_json_separators_type"] = type(separators).__name__

    class JsonMappingManifestView:
        """Present the same real CAS manifest as its ordinary JSON Mapping view."""

        def get_bytes(self, key):  # type: ignore[no-untyped-def]
            return typed_store.get_bytes(key)

        def get_manifest(self, key):  # type: ignore[no-untyped-def]
            manifest = typed_store.get_manifest(key)
            mapping = manifest.model_dump(mode="json")
            # Use the actual IR CanonInfo JSON-mode representation, including its list tuple.
            mapping["canon"] = canon_json
            return mapping

    mapping_store = JsonMappingManifestView()
    try:
        mapping_loaded = get_json_artifact(mapping_store, artifact_id)
        probe["json_mapping_profile_roundtrip"] = "PASS" if mapping_loaded == payload else "FAIL"
        probe["json_mapping_readback"] = mapping_loaded
    except Exception as exc:  # The exception is the behavioral discriminator under test.
        probe["json_mapping_profile_roundtrip"] = "FAIL"
        probe["json_mapping_exception_type"] = f"{type(exc).__module__}.{type(exc).__qualname__}"
        probe["json_mapping_exception"] = str(exc)
    probe["cas_artifact_id"] = str(artifact_id)
    probe["real_cas_manifest_profile_type"] = type(typed_manifest.canon).__name__ if typed_manifest.canon is not None else None
    probe["actual_file_cas_bytes"] = typed_store.get_bytes(artifact_id).decode("utf-8")
except Exception as exc:
    probe["public_typed_manifest_roundtrip"] = "ERROR"
    probe["probe_setup_exception_type"] = f"{type(exc).__module__}.{type(exc).__qualname__}"
    probe["probe_setup_exception"] = str(exc)

# Hash every imported Polisyos module and bind it to the candidate Git blob.
listing = subprocess.check_output(
    ["git", "ls-tree", "-r", CANDIDATE_SHA, "--", "policy-engine/src/polisyos"],
    cwd=GROOT,
    text=True,
)
blob_by_path = {}
for line in listing.splitlines():
    left, git_path = line.split("\t", 1)
    fields = left.split()
    if len(fields) >= 3 and fields[1] == "blob":
        blob_by_path[git_path] = fields[2]
origins = []
origin_violations = []
for name, module in sorted(sys.modules.items()):
    if name != "polisyos" and not name.startswith("polisyos."):
        continue
    filename = getattr(module, "__file__", None)
    if not filename:
        origin_violations.append({"module": name, "reason": "missing___file__"})
        continue
    path = Path(filename).resolve()
    try:
        rel = path.relative_to(SOURCE_ROOT.resolve()).as_posix()
    except ValueError:
        origin_violations.append({"module": name, "path": str(path), "reason": "outside_candidate_source"})
        continue
    git_path = f"policy-engine/src/{rel}"
    data = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    expected_blob = blob_by_path.get(git_path)
    row = {
        "module": name,
        "origin": str(path),
        "git_path": git_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob": expected_blob,
        "candidate_blob_match": expected_blob == blob,
    }
    origins.append(row)
    if expected_blob != blob:
        origin_violations.append({"module": name, "path": str(path), "expected_blob": expected_blob, "actual_blob": blob})

summary = {
    "candidate_sha": CANDIDATE_SHA,
    "candidate_tree": CANDIDATE_TREE,
    "selectors": selectors,
    "pytest_argv": pytest_argv,
    "pytest_exit": pytest_exit,
    "pytest_wall_seconds": pytest_seconds,
    "pytest_junit_path": str(pytest_junit),
    "probe": probe,
    "loaded_polisyos_module_count": len(origins),
    "all_loaded_polisyos_modules_candidate_exact": not origin_violations,
    "origin_violation_count": len(origin_violations),
    "origin_violation_preview": origin_violations[:20],
}
(RESULTS / "module-origins.json").write_text(json.dumps(origins, ensure_ascii=False, indent=2) + "\n")
(RESULTS / "runner-result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print("C_CANON_RESULT=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
raise SystemExit(pytest_exit if pytest_exit else (82 if origin_violations else 0))
