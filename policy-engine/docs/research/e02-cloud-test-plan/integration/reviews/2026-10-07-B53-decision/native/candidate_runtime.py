from __future__ import annotations

import importlib.machinery
import json
import os
import sys
import traceback
from hashlib import sha1, sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, ClassVar

GROOT = Path("/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos").resolve()
CANDIDATE = GROOT / "policy-engine/_build/e02-g-continuation-20261006/R/B-stop-53b-20261007/native/candidate/policy-engine"
SOURCE_ROOT = CANDIDATE / "src"
RESULTS = GROOT / "policy-engine/_build/e02-g-continuation-20261006/R/B-stop-53b-20261007/native/results"
MANIFEST_PATH = GROOT / "policy-engine/_build/e02-g-continuation-20261006/R/B-stop-53b-20261007/native/source-manifest-final.json"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _candidate_only_imports() -> None:
    live_product = (GROOT / "policy-engine").resolve()
    live_src = (live_product / "src").resolve()
    kept = []
    removed = []
    for item in sys.path:
        if not item:
            kept.append(item)
            continue
        try:
            resolved = Path(item).resolve()
        except OSError:
            kept.append(item)
            continue
        if resolved in (live_product, live_src):
            removed.append(str(resolved))
        else:
            kept.append(item)
    sys.path[:] = kept
    sys.path.insert(0, str(SOURCE_ROOT.resolve()))

    class CandidatePolisyosOnly:
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
            if fullname != "polisyos" and not fullname.startswith("polisyos."):
                return None
            search_path = list(path) if path is not None else [str(SOURCE_ROOT)]
            spec = importlib.machinery.PathFinder.find_spec(fullname, search_path)
            if spec is None:
                raise ModuleNotFoundError(
                    f"{fullname} is absent from pinned candidate source {SOURCE_ROOT}"
                )
            origin = spec.origin
            if origin not in (None, "namespace"):
                if not _inside(Path(origin), SOURCE_ROOT):
                    raise ImportError(f"non-candidate Polisyos origin rejected: {origin}")
            locations = list(spec.submodule_search_locations or ())
            if any(not _inside(Path(location), SOURCE_ROOT) for location in locations):
                raise ImportError(f"non-candidate Polisyos package path rejected: {locations}")
            return spec

    sys.meta_path.insert(0, CandidatePolisyosOnly())
    os.environ["POLISYOS_CANDIDATE_REMOVED_LIVE_PATHS"] = json.dumps(removed)


def _manifest() -> dict[str, dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text("utf-8"))
    return {entry["path"]: entry for entry in payload["files"]}


def _audit_import_origins(action: str) -> dict[str, Any]:
    expected = _manifest()
    modules: list[dict[str, Any]] = []
    errors: list[str] = []
    for name, module in sorted(sys.modules.items()):
        if name != "polisyos" and not name.startswith("polisyos."):
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None) if spec is not None else None
        if origin in (None, "namespace"):
            origin = getattr(module, "__file__", None)
        locations = list(getattr(spec, "submodule_search_locations", None) or ()) if spec else []
        if origin and origin not in ("built-in", "namespace"):
            path = Path(origin)
            if not _inside(path, SOURCE_ROOT):
                errors.append(f"{name}: origin outside pinned source: {origin}")
            elif path.suffix == ".py":
                rel = path.resolve().relative_to(SOURCE_ROOT.resolve()).as_posix()
                git_path = f"policy-engine/src/{rel}"
                entry = expected.get(git_path)
                raw = path.read_bytes()
                actual_git = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                if entry is None:
                    errors.append(f"{name}: source not in pinned manifest: {git_path}")
                elif actual_git != entry["git_blob"]:
                    errors.append(
                        f"{name}: source blob mismatch {git_path}: {actual_git} != {entry['git_blob']}"
                    )
                modules.append(
                    {
                        "name": name,
                        "origin": str(path),
                        "git_path": git_path,
                        "git_blob": actual_git,
                        "sha256": sha256(raw).hexdigest(),
                    }
                )
            else:
                modules.append({"name": name, "origin": str(path), "kind": path.suffix or "other"})
        for location in locations:
            if not _inside(Path(location), SOURCE_ROOT):
                errors.append(f"{name}: package search path outside pinned source: {location}")
    result = {
        "action": action,
        "candidate_source_root": str(SOURCE_ROOT),
        "removed_live_product_paths": json.loads(os.environ.get("POLISYOS_CANDIDATE_REMOVED_LIVE_PATHS", "[]")),
        "module_count": len(modules),
        "modules": modules,
        "errors": errors,
        "sys_path": sys.path,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"import-origins-{action}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"import_origin_receipt={path}")
    print(f"polisyos_modules={len(modules)} origin_errors={len(errors)}")
    if errors:
        print(json.dumps(errors, indent=2))
    return result


def _journal(journal: Any) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in journal.operations]


def _probe() -> tuple[int, dict[str, Any]]:
    from pydantic import BaseModel, ConfigDict, RootModel, model_validator

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.state_branching import branch_state

    result: dict[str, Any] = {"candidate": "0bf788ac2e57533b08be9172d64c19705a3af30d"}

    # Authorized root field deletion must be refused before changing state or journal.
    report = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="probe.report",
        media_type="application/json",
    )
    root_base = ExperimentState(run_id="B-model-root-delete", reports_index={"report": report})
    root_branch = branch_state(
        root_base, write_paths=("reports_index",), enforce_write_scope=True
    )
    root_before = root_branch.state.model_dump(mode="json")
    root_base_before = root_base.model_dump(mode="json")
    root_journal_before = _journal(root_branch.journal)
    root_error = None
    try:
        del root_branch.state.reports_index
    except Exception as exc:
        root_error = {"type": type(exc).__name__, "message": str(exc)}
    root_case = {
        "error": root_error,
        "branch_unchanged": root_branch.state.model_dump(mode="json") == root_before,
        "base_unchanged": root_base.model_dump(mode="json") == root_base_before,
        "journal_unchanged": _journal(root_branch.journal) == root_journal_before,
        "journal_after": _journal(root_branch.journal),
    }
    root_case["pass"] = (
        root_error is not None
        and root_error["type"] == "TypeError"
        and root_case["branch_unchanged"]
        and root_case["base_unchanged"]
        and root_case["journal_unchanged"]
    )
    result["authorized_root_delete"] = root_case

    # Authorized nested ordinary-model field deletion must also refuse before mutation.
    class Nested(BaseModel):
        count: int = 1
        tag: str = "stable"

    nested_base = ExperimentState.model_construct(
        run_id="B-model-nested-delete", params={"holder": Nested()}
    )
    nested_branch = branch_state(
        nested_base,
        write_paths=("params.holder.count",),
        enforce_write_scope=True,
    )
    nested_before = nested_branch.state.model_dump(mode="json")
    nested_base_before = nested_base.model_dump(mode="json")
    nested_journal_before = _journal(nested_branch.journal)
    nested_error = None
    try:
        del nested_branch.state.params["holder"].count
    except Exception as exc:
        nested_error = {"type": type(exc).__name__, "message": str(exc)}
    nested_case = {
        "error": nested_error,
        "branch_unchanged": nested_branch.state.model_dump(mode="json") == nested_before,
        "base_unchanged": nested_base.model_dump(mode="json") == nested_base_before,
        "journal_unchanged": _journal(nested_branch.journal) == nested_journal_before,
        "journal_after": _journal(nested_branch.journal),
    }
    nested_case["pass"] = (
        nested_error is not None
        and nested_error["type"] == "TypeError"
        and nested_case["branch_unchanged"]
        and nested_case["base_unchanged"]
        and nested_case["journal_unchanged"]
    )
    result["authorized_nested_model_delete"] = nested_case

    # Pydantic assignment validation attempts to mutate an ungranted sibling.
    class ValidatorModel(BaseModel):
        model_config = ConfigDict(validate_assignment=True)
        calls: ClassVar[int] = 0
        count: int = 1
        tag: str = "stable"

        @model_validator(mode="after")
        def change_sibling(self) -> ValidatorModel:
            type(self).calls += 1
            if self.count == 2:
                object.__setattr__(self, "tag", "changed-by-validator")
            return self

    validator_base = ExperimentState.model_construct(
        run_id="B-model-validator-sibling", params={"holder": ValidatorModel()}
    )
    validator_branch = branch_state(
        validator_base,
        write_paths=("params.holder.count",),
        enforce_write_scope=True,
    )
    validator_before = validator_branch.state.model_dump(mode="json")
    validator_base_before = validator_base.model_dump(mode="json")
    validator_journal_before = _journal(validator_branch.journal)
    calls_before = ValidatorModel.calls
    validator_error = None
    try:
        validator_branch.state.params["holder"].count = 2
    except Exception as exc:
        validator_error = {"type": type(exc).__name__, "message": str(exc)}
    validator_after = validator_branch.state.model_dump(mode="json")
    validator_journal_after = _journal(validator_branch.journal)
    before_holder = validator_before["params"]["holder"]
    after_holder = validator_after["params"]["holder"]
    sibling_changed = after_holder.get("tag") != before_holder.get("tag")
    sibling_journaled = any(
        operation["path"].endswith(".tag") for operation in validator_journal_after
    )
    no_change = (
        validator_after == validator_before
        and validator_journal_after == validator_journal_before
    )
    validator_case = {
        "validator_calls_before": calls_before,
        "validator_calls_after": ValidatorModel.calls,
        "error": validator_error,
        "before": validator_before,
        "after": validator_after,
        "base_after": validator_base.model_dump(mode="json"),
        "journal_before": validator_journal_before,
        "journal_after": validator_journal_after,
        "sibling_changed": sibling_changed,
        "sibling_journaled": sibling_journaled,
        "base_unchanged": validator_base.model_dump(mode="json") == validator_base_before,
        "pass": (
            (validator_error is not None and no_change)
            or (not sibling_changed and not sibling_journaled)
        ),
    }
    validator_case["counterexample"] = sibling_changed and not sibling_journaled
    result["validator_ungranted_sibling"] = validator_case

    # RootModel support is explicitly documented by the exact candidate README.
    class RootPayload(RootModel[dict[str, int]]):
        pass

    rootmodel_base = ExperimentState.model_construct(
        run_id="B-model-root-model",
        params={"holder": RootPayload({"count": 1, "sibling": 9})},
    )
    rootmodel_case: dict[str, Any] = {}
    try:
        rootmodel_branch = branch_state(
            rootmodel_base,
            write_paths=("params.holder.root.count",),
            enforce_write_scope=True,
        )
        model_before = rootmodel_branch.state.model_dump(mode="json")
        base_before = rootmodel_base.model_dump(mode="json")
        rootmodel_branch.state.params["holder"].root["count"] = 2
        after_positive = rootmodel_branch.state.model_dump(mode="json")
        journal_after_positive = _journal(rootmodel_branch.journal)
        before_negative = rootmodel_branch.state.model_dump(mode="json")
        journal_before_negative = _journal(rootmodel_branch.journal)
        negative_error = None
        try:
            rootmodel_branch.state.params["holder"].root["sibling"] = 10
        except Exception as exc:
            negative_error = {"type": type(exc).__name__, "message": str(exc)}
        after_negative = rootmodel_branch.state.model_dump(mode="json")
        journal_after_negative = _journal(rootmodel_branch.journal)
        rootmodel_case = {
            "admitted": True,
            "base_before": base_before,
            "base_after": rootmodel_base.model_dump(mode="json"),
            "branch_before": model_before,
            "after_positive": after_positive,
            "journal_after_positive": journal_after_positive,
            "negative_error": negative_error,
            "after_negative": after_negative,
            "journal_after_negative": journal_after_negative,
            "root_after_positive": rootmodel_branch.state.params["holder"].root,
            "positive_changed_count": (
                rootmodel_branch.state.params["holder"].root["count"] == 2
            ),
            "negative_refused_before_change": (
                negative_error is not None
                and after_negative == after_positive
                and journal_after_negative == journal_before_negative
            ),
            "base_unchanged": rootmodel_base.model_dump(mode="json") == base_before,
        }
        rootmodel_case["pass"] = all(
            rootmodel_case[key]
            for key in (
                "positive_changed_count",
                "negative_refused_before_change",
                "base_unchanged",
            )
        ) and any(
            item["path"] == "params.holder.root.count" for item in journal_after_positive
        )
    except Exception as exc:
        rootmodel_case = {
            "admitted": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "pass": False,
        }
    result["root_model_supported_profile"] = rootmodel_case

    checks_pass = all(
        result[key].get("pass", False)
        for key in (
            "authorized_root_delete",
            "authorized_nested_model_delete",
            "validator_ungranted_sibling",
            "root_model_supported_profile",
        )
    )
    result["overall_probe"] = "PASS" if checks_pass else "COUNTEREXAMPLE_OR_LIMITATION"
    return (0 if checks_pass else 5), result


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: candidate_runtime.py pytest-native", file=sys.stderr)
        return 64
    action = sys.argv[1]
    _candidate_only_imports()
    exit_code = 0
    payload: dict[str, Any]
    try:
        if action.startswith("pytest"):
            import pytest

            junit = RESULTS / f"selected-tests-{action}.junit.xml"
            args = [
                "-o",
                "addopts=",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit}",
                "tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py",
                "tests/unit/scientist/orchestration/engine/test_producer_model_scope_oracle.py",
            ]
            print(json.dumps({"action": "pytest", "argv": args, "cwd": os.getcwd()}))
            exit_code = int(pytest.main(args))
            payload = {"pytest_exit_code": exit_code}
        elif action == "probe":
            exit_code, payload = _probe()
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"unknown action: {action}", file=sys.stderr)
            return 64
    except BaseException:
        traceback.print_exc()
        exit_code = 3
        payload = {"harness_exception": traceback.format_exc()}
    audit = _audit_import_origins(action)
    payload["origin_audit_errors"] = audit["errors"]
    payload["runtime"] = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "cwd": os.getcwd(),
        "maxrss_native_units": __import__("resource").getrusage(
            __import__("resource").RUSAGE_SELF
        ).ru_maxrss,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS / f"runtime-result-{action}.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"runtime_result={result_path}")
    if audit["errors"] and exit_code == 0:
        exit_code = 7
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
