#!/usr/bin/env python3
"""Independent read-only canonical collectors over immutable proposed source."""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).parent
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
POST = OUT / "immutable-inputs/postimage"
sys.path.insert(0, str(ROOT / "policy-engine"))


def git(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", BASE + ":" + path])


def load(name, path):
    assert (ROOT / path).read_bytes() == git(path)
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    manifest = json.loads(
        (OUT / "immutable-inputs/postimage-manifest.json").read_text()
    )
    for record in manifest["paths"]:
        value = (POST / record["path"]).read_bytes()
        assert len(value) == record["bytes"]
        assert hashlib.sha256(value).hexdigest() == record["after_sha256"]
    modules = {
        "polisyos.calibration": "policy-engine/src/polisyos/calibration/__init__.py",
        "polisyos.foundry.uncertainty": "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
        "polisyos.scientist.nodes.builtins.simulate.propagate_welfare": "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py",
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty": "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py",
    }
    values = {ROOT / path: (POST / path).read_text() for path in modules.values()}
    guard = load(
        "independent_guard_facade",
        "policy-engine/tools/devx/architecture/guardrails.py",
    )
    lint = load(
        "independent_lint_facade", "policy-engine/tools/quality/lint/lint_imports.py"
    )
    contract_path = "policy-engine/architecture/public_surface/contract.toml"
    assert (ROOT / contract_path).read_bytes() == git(contract_path)
    policies = guard._parse_public_surface(ROOT / contract_path)
    families = guard._parse_public_generated_artifact_families(ROOT / contract_path)
    reader = Path.read_text
    observed_source_reads = set()

    def source_reader(overrides):
        def read(path, *args, **kwargs):
            if path in overrides:
                return overrides[path]
            if path.is_relative_to(ROOT / "policy-engine/src"):
                relative = path.relative_to(ROOT).as_posix()
                original = git(relative)
                assert path.read_bytes() == original
                observed_source_reads.add(relative)
                return original.decode()
            return reader(path, *args, **kwargs)

        return read

    def collect(overrides):
        with (
            patch.object(Path, "read_text", source_reader(overrides)),
            patch.object(
                guard, "_iter_py_files", lambda: [ROOT / p for p in modules.values()]
            ),
        ):
            return {edge.key for edge in guard.collect_deep_import_edges(policies)}

    old_edges = collect({})
    new_edges = collect(values)
    wanted = "polisyos.scientist.nodes.builtins.simulate.propagate_welfare->polisyos.foundry.uncertainty.covariance"
    assert old_edges - new_edges == {wanted}
    assert not new_edges - old_edges
    old_route = dict(values)
    welfare_path = modules[
        "polisyos.scientist.nodes.builtins.simulate.propagate_welfare"
    ]
    old_route[ROOT / welfare_path] = git(welfare_path).decode()
    assert wanted in collect(old_route)
    native_parse = lint.parse_imports
    policy = "policy-engine/architecture/imports/policy.toml"
    exceptions = "policy-engine/architecture/imports/exceptions.toml"
    for path in [
        policy,
        exceptions,
        "policy-engine/architecture/packages/boundaries.toml",
    ]:
        assert (ROOT / path).read_bytes() == git(path)

    def scan(overrides, label):
        stdout = io.StringIO()
        argv = [
            "--policy",
            str(ROOT / policy),
            "--exceptions",
            str(ROOT / exceptions),
            "--output-format",
            "json",
            "--cache-dir",
            str(OUT / (label + "-cache")),
        ]
        with (
            patch.object(Path, "read_text", source_reader(overrides)),
            patch.object(
                lint,
                "iter_py_files",
                lambda src_root: [ROOT / p for p in modules.values()],
            ),
            patch.object(
                lint,
                "parse_imports",
                lambda config, cache_root=None: native_parse(config, cache_root=None),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = lint.main(argv)
        return {
            "argv": argv,
            "exit_code": code,
            "stdout": json.loads(stdout.getvalue()),
        }

    scans = {"old_exact5e": scan({}, "old"), "immutable_proposed": scan(values, "new")}
    old_alias = dict(values)
    cal = modules["polisyos.calibration"]
    old_alias[ROOT / cal] = (
        git(cal).decode().replace('    "load_foundry_calibration_report",\n', "")
    )
    scans["restored_old_import_with28export_metadata"] = scan(
        old_alias, "old-alias-negative"
    )
    assert scans["old_exact5e"]["exit_code"] == 1
    assert scans["immutable_proposed"]["exit_code"] == 0
    assert scans["restored_old_import_with28export_metadata"]["exit_code"] == 1
    assert scans["old_exact5e"]["stdout"]["data"]["violation_count"] == 1
    assert scans["immutable_proposed"]["stdout"]["data"]["violation_count"] == 0
    assert "calibration -> foundry" in json.dumps(
        scans["restored_old_import_with28export_metadata"]
    )
    with patch.object(Path, "read_text", source_reader({})):
        before = guard.build_public_surface_inventory(policies)
    with patch.object(Path, "read_text", source_reader(values)):
        after = guard.build_public_surface_inventory(policies)
    rendered = guard.render_public_surface_json(
        after, generated_artifact_families=families
    ).encode()
    md = guard.render_public_surface_markdown(after).encode()
    assert (
        rendered
        == (
            POST / "policy-engine/architecture/public_surface/inventory.json"
        ).read_bytes()
    )
    assert md == (POST / "policy-engine/docs/reference/public-surface.md").read_bytes()
    prior = json.loads(
        guard.render_public_surface_json(before, generated_artifact_families=families)
    )
    current = json.loads(rendered)
    allowed = copy.deepcopy(prior)
    counts = {}
    for package in current["packages"]:
        for entry in package["entrypoints"]:
            if entry["module"] in [
                "polisyos.calibration",
                "polisyos.foundry.uncertainty",
                "polisyos.ddm",
            ]:
                counts[entry["module"]] = entry["export_count"]
    for pkg in allowed["packages"]:
        if pkg["module"] == "polisyos.calibration":
            now = next(x for x in current["packages"] if x["module"] == pkg["module"])
            pkg["exports"], pkg["export_count"] = now["exports"], now["export_count"]
        for entry in pkg["entrypoints"]:
            if entry["module"] in [
                "polisyos.calibration",
                "polisyos.foundry.uncertainty",
            ]:
                now = next(
                    e
                    for p in current["packages"]
                    for e in p["entrypoints"]
                    if e["module"] == entry["module"]
                )
                entry.update(now)
    assert allowed == current
    assert counts == {
        "polisyos.calibration": 28,
        "polisyos.foundry.uncertainty": 25,
        "polisyos.ddm": 17,
    }
    for name in ["propagate_welfare", "propagate_uncertainty"]:
        path = modules["polisyos.scientist.nodes.builtins.simulate." + name]

        def body(payload):
            return [
                ast.dump(n, include_attributes=False)
                for n in ast.parse(payload).body
                if not isinstance(n, (ast.Import, ast.ImportFrom))
            ]

        assert body(git(path)) == body((POST / path).read_bytes())
    result = {
        "schema": "policyos.e02.independent-selected-facade-routes.v1",
        "base_sha": BASE,
        "patch_sha256": manifest["patch_sha256"],
        "state": "PASS_bounded_selected_routes_and_generator",
        "selected_complete_module_denominator": modules,
        "source_reads_exact_base": sorted(observed_source_reads),
        "source_read_denominator": len(observed_source_reads),
        "old_edges": sorted(old_edges),
        "new_edges": sorted(new_edges),
        "only_removed_edge": wanted,
        "new_private_edges": [],
        "actual_policy_scans": scans,
        "negative_controls": [
            "all25exports_present_oldprivateWelfare_route_detected",
            "28Calexports_present_oldforbiddenimport_detected",
        ],
        "generator_exact_postimage_bytes": True,
        "inventory_counts": counts,
        "only_owned_facade_inventory_values_changed": True,
        "both_actual_Node_nonimport_AST_unchanged": True,
        "full_global_guard_PASS_inferred": False,
        "unadjudicated_other21_current_lint_rows": "Unchanged selected slice doesnot attribute or waive global rows",
    }
    (OUT / "selected-routes-review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "state",
                    "source_read_denominator",
                    "inventory_counts",
                    "negative_controls",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
