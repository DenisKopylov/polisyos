"""Call the unchanged intake owner against the complete required local stage set."""

import ast
import hashlib
import inspect
import json
import tempfile
from pathlib import Path


def main():
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.data_plane import load_ukraine_foundry_intake

    root = Path.cwd()
    source_root = root / "production_data/ukraine_agent_simulation_baseline_20260410/production_bundle"
    source = inspect.getsource(load_ukraine_foundry_intake)
    tree = ast.parse(source)
    declarations = [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "required_outputs" for t in node.targets)]
    assert len(declarations) == 1
    required = ast.literal_eval(declarations[0])
    paths = sorted((source_root / "manifests").glob("build_run_*.json"))
    independently_walked = sorted(p for p in (source_root / "manifests").iterdir()
                                   if p.is_file() and p.name.startswith("build_run_") and p.suffix == ".json")
    assert paths == independently_walked
    rows = []
    supplied = {}
    hashes = {}
    for path in paths:
        raw = path.read_bytes()
        payload = json.loads(raw)
        stage = payload["stage_id"]
        assert path.stem == "build_run_" + stage
        assert stage not in supplied
        supplied[stage] = path
        hashes[path] = hashlib.sha256(raw).hexdigest()
        rows.append({"path": str(path.relative_to(root)), "sha256": hashes[path],
                     "stage_id": stage, "status": payload["status"],
                     "required_by_intake": stage in required})
    assert set(required).issubset(supplied)
    selected = {stage: supplied[stage] for stage in required}
    assert {p.stem.removeprefix("build_run_") for p in selected.values()} == set(required)
    print(json.dumps({"stage_manifest_json_denominator": len(paths),
                      "required_stage_denominator": len(required),
                      "identity_delta": [], "manifests": rows}, sort_keys=True), flush=True)
    try:
        with tempfile.TemporaryDirectory(dir=root / "_build/gy-gaps/c3", prefix="actual-intake-") as temporary:
            load_ukraine_foundry_intake(FileSystemCAS(Path(temporary)),
                                       stage_manifests=selected, allowed_root=source_root)
    except Exception as exc:
        print(json.dumps({"actual_owner_refusal": {"type": type(exc).__name__, "message": str(exc)},
                          "canonical_stage_authority": "not_admitted"}, sort_keys=True), flush=True)
        raise
    finally:
        assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in hashes.items())
    raise AssertionError("Previously failed canonical stage unexpectedly admitted; inspect changed source")


if __name__ == "__main__":
    main()
