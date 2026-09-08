"""Read-only PA1 source/behavior stations; synthetic evidence is a control only."""

from __future__ import annotations

import ast
import copy
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import tokenize


EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[4]


def census() -> None:
    """Reconcile the complete Python source path and symbol-file identity sets."""
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "src/**/*.py"], text=True, cwd=ROOT
    ).splitlines())
    walked = {str(path.relative_to(ROOT)) for path in (ROOT / "src").rglob("*.py")}
    symbols = {
        "NormativeDecisionRequest", "NormativeAuthorizationRecord",
        "NormativeValueScheduleOwner", "NormativeAuthorityTrust",
        "ValueGateReceipt", "build_authorized_value_schedule",
        "build_pareto_archive", "ParetoArchive", "emit_welfare_frontier",
        "NormativeRankingResult", "CandidateFront", "GenerationCycleFronts",
    }
    parsed, ambiguous = {}, []
    ast_files = {key: set() for key in symbols}
    token_files = {key: set() for key in symbols}
    definitions, calls = [], []
    for rel in sorted(tracked | walked):
        try:
            source = (ROOT / rel).read_text()
            tree = ast.parse(source, filename=rel)
            parsed[rel] = tree
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.NAME and token.string in symbols:
                    token_files[token.string].add(rel)
            for node in ast.walk(tree):
                name = None
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                    if name in symbols:
                        definitions.append({"path": rel, "line": node.lineno, "symbol": name})
                elif isinstance(node, ast.Name):
                    name = node.id
                elif isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, ast.alias):
                    name = node.name
                elif isinstance(node, ast.arg):
                    name = node.arg
                if name in symbols:
                    ast_files[name].add(rel)
                if isinstance(node, ast.Call):
                    target = ast.unparse(node.func)
                    if any(part in symbols for part in target.split(".")):
                        calls.append({"path": rel, "line": node.lineno, "target": target})
        except (OSError, SyntaxError, UnicodeError, tokenize.TokenError) as exc:
            ambiguous.append({"path": rel, "error": str(exc)})
    token_differences = {
        symbol: {"ast_only": sorted(ast_files[symbol] - token_files[symbol]),
                 "token_only": sorted(token_files[symbol] - ast_files[symbol])}
        for symbol in sorted(symbols)
    }
    result = {
        "denominator": "all src/**/*.py, git tracked vs filesystem walk; no sampling",
        "tracked_count": len(tracked), "walked_count": len(walked),
        "tracked_only": sorted(tracked - walked), "walked_only": sorted(walked - tracked),
        "ambiguous": ambiguous, "complete_source_identity_set": sorted(tracked | walked),
        "symbol_file_identity_sets": {key: sorted(value) for key, value in sorted(ast_files.items())},
        "independent_token_identity_differences": token_differences,
        "definitions": definitions, "calls_in_complete_source": calls,
    }
    print(json.dumps(result, indent=2))
    assert not tracked ^ walked
    assert not ambiguous
    assert all(not values["ast_only"] and not values["token_only"]
               for values in token_differences.values())


def controls(mode: str) -> None:
    """Exercise existing owner through test-only cryptographic principals."""
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    checks = runpy.run_path(str(ROOT / "tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py"))
    with tempfile.TemporaryDirectory(prefix="cas-", dir=EVIDENCE) as scratch:
        scratch_root = Path(scratch)
        if mode == "signature_removal":
            s8.NormativeValueScheduleOwner._require_signature = staticmethod(lambda signature: None)
            checks["test_invalid_authority_keeps_frontier_and_persists_typed_request"](
                scratch_root, "signature", "p20_normative_signature_unverified"
            )
            return
        positive = checks["_normative_harness"](scratch_root / "positive")
        actual, bundle = positive["owner"].recommend(**positive["kwargs"])
        assert actual.authorization_status == "authorized"
        assert actual.ranked_recommendations == ("targeted_credit",)
        assert positive["owner"].project(bundle, evaluated_at=checks["NOW"]) == actual.model_dump(mode="json")
        print(json.dumps({"control": "positive_signed_fixture_not_production_denominator",
                          "bundle_ref": bundle, "result": actual.model_dump(mode="json")}, indent=2))
        if mode == "refusals":
            test = checks["test_invalid_authority_keeps_frontier_and_persists_typed_request"]
            params = next(mark.args[1] for mark in test.pytestmark if mark.name == "parametrize")
            print(json.dumps({"refusal_identity_set": sorted(fault for fault, _ in params)}))
            for fault, reason in params:
                harness = checks["_normative_harness"](scratch_root / fault, fault=fault)
                result, bundle = harness["owner"].recommend(**harness["kwargs"])
                assert result.ranked_recommendations == ()
                assert result.authorization_status == "blocked"
                assert result.decision_request.reason_codes == (reason,)
                assert reason != "p20_value_schedule_resolver_absent"
                assert result.archive.nondominated_alternative_ids == harness["frontier"].nondominated_alternative_ids
                assert harness["owner"].project(bundle, evaluated_at=checks["NOW"]) == result.model_dump(mode="json")
                print(json.dumps({"fault": fault, "bundle_ref": bundle, "result": result.model_dump(mode="json")}, indent=2))
            return
        # These defaults are interventions on the same real output boundary: a selector
        # supplies its preferred alternative without an authorized schedule. They are
        # controls for the user's three named defaults, never a canonical population.
        defaults = {
            "silent_equal_weight": "targeted_credit",
            "historical_prior": "cash_transfer",
            "proxy_as_priority": "targeted_credit",
        }
        if mode == "emission_removal":
            s8._admit_normative_emission = lambda value, **kwargs: dict(value)
        escaped = []
        for label, selected in defaults.items():
            harness = checks["_normative_harness"](scratch_root / label, fault="missing")
            result, _ = harness["owner"].recommend(**harness["kwargs"])
            injected = copy.deepcopy(result.model_dump(mode="json"))
            injected["ranked_recommendations"] = [selected]
            try:
                s8.persist_value_choice_provenance_bundle(
                    injected, store=harness["store"], owner=harness["owner"],
                    evaluated_at=checks["NOW"],
                )
            except s8.P20NormativeChoiceError as exc:
                print(json.dumps({"default": label, "selected": selected,
                                  "refusal": str(exc)}, indent=2))
                assert str(exc) == "p20_candidate_result_authority_mismatch"
            else:
                escaped.append(label)
                print(json.dumps({"default": label, "selected": selected,
                                  "escaped_to_cas": True}, indent=2))
        assert not escaped, f"unauthorized defaults reached CAS persistence: {escaped}"


def deployed_store() -> None:
    """Measure the configured HTTP store wrapper against the S8 constructor."""
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality.design_axes.value_choice_provenance import NormativeValueScheduleOwner

    with tempfile.TemporaryDirectory(prefix="deployed-store-", dir=EVIDENCE) as scratch:
        root = Path(scratch)
        context = build_runtime_api_context(cas_root=root / "cas", core_runs_root=root / "runs")
        store = context.store
        target = store._target
        record = {
            "deployed_store_type": f"{type(store).__module__}.{type(store).__name__}",
            "canonical_target_type": f"{type(target).__module__}.{type(target).__name__}",
        }
        try:
            NormativeValueScheduleOwner(store=store)
        except TypeError as exc:
            record["guarded_constructor_refusal"] = str(exc)
        else:
            raise AssertionError("expected exact concrete-store constraint changed")
        owner = NormativeValueScheduleOwner(store=target)
        record["same_backend_object_reused"] = owner._store is target
        print(json.dumps(record, indent=2))
        store.close()


if __name__ == "__main__":
    print(json.dumps({"python": sys.executable, "cwd": str(Path.cwd()),
                      "PATH": os.environ.get("PATH"), "mode": sys.argv[1]}, indent=2))
    if sys.argv[1] == "census":
        census()
    elif sys.argv[1] == "deployed_store":
        deployed_store()
    else:
        controls(sys.argv[1])
