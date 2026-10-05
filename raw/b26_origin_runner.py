from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


def _resolved(entry: str) -> Path | None:
    if not entry:
        entry = os.getcwd()
    try:
        return Path(entry).resolve()
    except OSError:
        return None


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def main() -> int:
    candidate = Path(os.environ["B26_CANDIDATE_ROOT"]).resolve()
    product_root = candidate / "policy-engine"
    legacy_root = Path(os.environ["B26_EXCLUDE_PATH"]).resolve()
    legacy_import_roots = (
        legacy_root,
        legacy_root / "src",
        legacy_root / "tests",
    )
    output = Path(os.environ["B26_ORIGIN_CENSUS_PATH"])

    paths = []
    for entry in sys.path:
        resolved = _resolved(entry)
        if resolved is not None and any(
            resolved == import_root or _within(resolved, import_root)
            for import_root in legacy_import_roots
        ):
            continue
        paths.append(entry)
    sys.path[:] = paths
    sys.path.insert(0, str(candidate))
    sys.path.insert(0, str(product_root / "src"))

    import pytest

    test_exit = int(pytest.main(sys.argv[1:]))
    modules: list[dict[str, object]] = []
    violations: list[dict[str, str]] = []
    for name, module in sorted(sys.modules.items()):
        if name != "polisyos" and not name.startswith("polisyos.") and name != "tests" and not name.startswith("tests."):
            continue
        module_file = getattr(module, "__file__", None)
        spec = getattr(module, "__spec__", None)
        origin = module_file or getattr(spec, "origin", None)
        locations = tuple(getattr(spec, "submodule_search_locations", ()) or ())
        resolved_origins: list[str] = []
        source_hashes: dict[str, str] = {}
        if origin and origin not in {"built-in", "frozen"}:
            origin_path = Path(origin).resolve()
            resolved_origins.append(str(origin_path))
            source_path = origin_path
            if origin_path.suffix == ".pyc":
                try:
                    import importlib.util

                    source_path = Path(importlib.util.source_from_cache(str(origin_path)))
                except (ValueError, NotImplementedError):
                    source_path = origin_path
            if source_path.is_file():
                source_hashes[str(source_path)] = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if not _within(origin_path, product_root):
                violations.append({"module": name, "path": str(origin_path)})
        for location in locations:
            resolved = Path(location).resolve()
            resolved_origins.append(str(resolved))
            if not _within(resolved, product_root):
                violations.append({"module": name, "path": str(resolved)})
        modules.append(
            {
                "module": name,
                "origins": sorted(set(resolved_origins)),
                "source_sha256": source_hashes,
            }
        )

    payload = {
        "candidate_root": str(candidate),
        "legacy_import_root_excluded": str(legacy_root),
        "pythonpath": os.environ.get("PYTHONPATH"),
        "pytest_exit": test_exit,
        "loaded_module_count": len(modules),
        "origin_violation_count": len(violations),
        "origin_violations": violations,
        "modules": modules,
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"origin census: modules={len(modules)} violations={len(violations)} "
        f"pytest_exit={test_exit} output={output}"
    )
    if violations:
        print(json.dumps(violations, indent=2))
        return 1
    return test_exit


if __name__ == "__main__":
    raise SystemExit(main())
