"""Observe actual owned semantic fixtures independently, without changing files.

For C05 member removal the observation run continues beyond signature assertions
and stops after the fresh benchmark, before the core producer can repair evidence.
Only contribution bytes are frozen; names, markers, actual policy and consumers stay.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

EVENTS = []


def value(x):
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, bytes):
        return {"bytes": len(x), "sha256": hashlib.sha256(x).hexdigest()}
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, dict):
        return {str(k): value(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [value(v) for v in x]
    if hasattr(x, "tolist"):
        return x.tolist()
    return repr(x)


def observe(line, expression, result, left=None, right=None, state=None):
    event = {"line": line, "expression": expression, "holds": bool(result)}
    if left is not None or right is not None:
        event.update({"actual_left": value(left), "expected_right": value(right)})
    if state:
        for key in ["knn_calls", "fetch_urls", "branches", "rows", "evidence", "held_evidence", "reads"]:
            if key in state:
                event[key] = value(state[key])
        for key in ["encoder", "query_encoder"]:
            if key in state and hasattr(state[key], "encoded_texts"):
                event[key + "_encoded_texts"] = value(state[key].encoded_texts)
    EVENTS.append(event)
    return bool(result)


class ObservedAssertions(ast.NodeTransformer):
    def __init__(self, stop_at_repair=False, enforce=True):
        self.stop_at_repair = stop_at_repair
        self.enforce = enforce

    def visit_FunctionDef(self, node):
        if self.stop_at_repair:
            for i, statement in enumerate(node.body):
                if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "repaired" for target in statement.targets
                ):
                    node.body = node.body[:i]
                    break
        return self.generic_visit(node)

    def visit_Assert(self, node):
        expression = ast.unparse(node.test)
        left = ast.Constant(None)
        right = ast.Constant(None)
        assignments = []
        condition = node.test
        if isinstance(node.test, ast.Compare) and len(node.test.comparators) == 1:
            left_name = "__orch02_left_" + str(node.lineno)
            right_name = "__orch02_right_" + str(node.lineno)
            assignments = [ast.Assign([ast.Name(left_name, ast.Store())], node.test.left),
                           ast.Assign([ast.Name(right_name, ast.Store())], node.test.comparators[0])]
            left, right = ast.Name(left_name, ast.Load()), ast.Name(right_name, ast.Load())
            condition = ast.Compare(left, node.test.ops, [right])
        call = ast.Call(ast.Name("__orch02_observe", ast.Load()),
                        [ast.Constant(node.lineno), ast.Constant(expression), condition, left, right,
                         ast.Call(ast.Name("locals", ast.Load()), [], [])], [])
        final = ast.Assert(call, node.msg) if self.enforce else ast.Expr(call)
        return [ast.copy_location(x, node) for x in [*assignments, final]]


def module_from_path(path):
    spec = importlib.util.spec_from_file_location("orch02_owned_semantic", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--kind", choices=["c05-profile", "c05-seed", "c05-proxy", "c05-wvs", "c05-fallback",
                                   "c05-legacy", "c05-bulk", "c12-intent"], required=True)
    p.add_argument("--remove", choices=["none", "member", "cache", "cache-core", "forwarding"], default="none")
    args = p.parse_args()
    names = {
        "c05-profile": "test_material_input_change_recomputes_real_producer_and_benchmark",
        "c05-seed": "test_material_input_change_recomputes_real_producer_and_benchmark",
        "c05-proxy": "test_warm_proxy_policy_change_updates_actual_catalog_alignment",
        "c05-wvs": "test_warm_wvs_policy_change_updates_selected_bulk_rows_and_harvest_catalog",
        "c05-fallback": "test_wvs_metadata_fallback_tracks_actual_branch_and_optional_asset",
        "c05-legacy": "test_resolved_legacy_mode_binds_signature_and_actual_dispatch",
        "c05-bulk": "test_wvs_bulk_resolves_current_policy_once_per_operation",
        "c12-intent": "test_same_assets_new_generation_requires_fresh_request_intent_and_fresh_reader",
    }
    path = args.repo / "policy-engine/tests/unit/remediation" / (
        "test_emb_03.py" if args.kind.startswith("c12") else "test_dfi_03.py")
    module = module_from_path(path)
    tree = ast.parse(path.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == names[args.kind])
    function.decorator_list = []
    function = ObservedAssertions(
        stop_at_repair=args.kind in {"c05-profile", "c05-seed"},
        enforce=args.remove == "none").visit(function)
    root = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    module.__dict__["__orch02_observe"] = observe
    exec(compile(root, str(path), "exec"), module.__dict__)
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    tmp = Path(tempfile.mkdtemp(prefix="semantic-", dir=out))
    removal = {"kind": args.remove, "quantity": None, "held_markers": True, "source_files_changed": False}
    with pytest.MonkeyPatch.context() as monkeypatch:
        if args.remove == "member":
            from polisyos.data_forge.domains.catalog.batch import config
            original = config.build_generation_basis
            role = {"c05-profile": "resolved_profile_registry", "c05-seed": "seed_variable_alignments",
                    "c05-proxy": "proxy_metric_alignments", "c05-legacy": "resolved_producer_runtime_policy"}[args.kind]
            frozen = {}
            def frozen_contribution(*, members, **kwargs):
                captured = []
                for name, payload in members:
                    if name == role or name.startswith(role + ":"):
                        frozen.setdefault(name, payload)
                        payload = frozen[name]
                    captured.append((name, payload))
                return original(members=captured, **kwargs)
            monkeypatch.setattr(config, "build_generation_basis", frozen_contribution)
            removal["quantity"] = "freeze only " + role + " contribution bytes before first producer"
        elif args.remove in {"cache", "cache-core"}:
            if args.kind == "c05-proxy":
                from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties as owner
            elif args.remove == "cache-core":
                from polisyos.data_forge.domains.catalog.batch.core_sources import loaders as owner
            else:
                from polisyos.data_forge.domains.catalog.batch import harvester as owner
            original = owner._material_file_snapshot
            frozen = {}
            def stale_snapshot(path, **kwargs):
                key = (str(path), tuple(sorted(kwargs.items())))
                if key not in frozen:
                    frozen[key] = original(path, **kwargs)
                return frozen[key]
            monkeypatch.setattr(owner, "_material_file_snapshot", stale_snapshot)
            removal["quantity"] = "restore obsolete path-only warm snapshot in actual owner reader; current basis remains"
        elif args.remove == "forwarding":
            from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
            original = loaders._normalize_wvs_response_value_typed
            def reintroduce_per_cell_policy(indicator, raw_value, **kwargs):
                return original(indicator, raw_value)
            monkeypatch.setattr(loaders, "_normalize_wvs_response_value_typed", reintroduce_per_cell_policy)
            removal["quantity"] = "omit only operation-bound response_type forwarding; real DuckDB normalization remains"
        call_kwargs = {"monkeypatch": monkeypatch, "tmp_path": tmp}
        if args.kind in {"c05-profile", "c05-seed"}:
            call_kwargs["material_change"] = "profile_url" if args.kind == "c05-profile" else "seed_evidence"
        error = None
        try:
            getattr(module, names[args.kind])(**call_kwargs)
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        if args.remove == "none":
            verdict = "PASS" if error is None and all(e["holds"] for e in EVENTS) else "FAIL"
        else:
            divergent = [e for e in EVENTS if not e["holds"]]
            meaningful = [e for e in divergent if any(s in e["expression"] for s in (
                "evaluation_mode", "core_output_receipt_current", "persisted_alignment", "aggregation_method",
                "title", "name_en", "reads", "value", "branches", "changed =="))]
            legacy_discriminator = args.kind == "c05-legacy" and divergent and any(
                e.get("branches") == ["parallel", "legacy"] for e in EVENTS)
            verdict = "DISCRIMINATING" if meaningful or legacy_discriminator else "INCONCLUSIVE"
    report = {"kind": args.kind, "removal": removal, "owned_fixture_source": str(path),
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "oracle": "literal actual SQL/benchmark/native outputs; assertion observations continue beyond digest failures",
              "verdict": verdict, "error": error, "events": EVENTS,
              "marker_and_fixture_outputs": str(tmp)}
    (out / "semantic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if verdict not in {"PASS", "DISCRIMINATING"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
