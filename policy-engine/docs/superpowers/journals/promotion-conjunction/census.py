"""Read-only task-zero census; research instrument, not a production capability."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SELECTORS = (
    "src/polisyos/runtime/quality/promotion_sequence.py",
    "src/polisyos/pdc/_impl/gy_waist.py",
)
HELPERS = {"_satisfied_obligation", "_failed_obligation", "_scope_insufficient_obligation"}


def main() -> None:
    """Print the complete selected denominator, read receipts and bounded findings."""
    report = {
        "predicate": {
            "primary": "Return expressions containing a call to one of the three obligation draft helpers, including model_copy chains; unit is a syntactic return site, not an obligation identity.",
            "function_name_control": "Every sync/async function whose identifier contains obligation; this is a lexical control, not a producer definition.",
            "producer_control": "Every function annotated with exactly PromotionObligationDraft, including the three constructor helpers.",
            "class_identity_control": "Every assigned enum member of PromotionObligationClass; instance identities additionally bind role, source and candidate/problem/invocation scope.",
        },
        "selectors": SELECTORS,
        "inputs_actually_read": [],
        "unresolved_by_construction": [
            "runtime_obligation_instances_require_a_selected_run",
            "static_helper_counts_do_not_decide_caller_reachability",
            "unselected_files_are_not_admitted_by_this_census",
        ],
    }
    sources = {}
    for relative in SELECTORS:
        try:
            body = (ROOT / relative).read_bytes()
            source = body.decode()
            tree = ast.parse(source)
        except (OSError, UnicodeError, SyntaxError) as exc:
            report["inputs_actually_read"].append({"path": relative, "status": "ambiguous", "error": str(exc)})
            report["unresolved_by_construction"].append("unreadable_or_unparsed_selected_member")
            print(json.dumps(report, indent=2))
            raise SystemExit(2) from exc
        report["inputs_actually_read"].append({"path": relative, "status": "parsed", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
        sources[relative] = (source, tree)
    source, tree = sources[SELECTORS[0]]
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    returns = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        calls = [call.func.id for call in ast.walk(node.value) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in HELPERS]
        if calls:
            returns.append({"line": node.lineno, "helpers": calls})
    names = [node for node in functions if "obligation" in node.name]
    producers = [node for node in functions if node.returns and ast.unparse(node.returns) == "PromotionObligationDraft"]
    enum_source, enum_tree = sources[SELECTORS[1]]
    enum = next(node for node in enum_tree.body if isinstance(node, ast.ClassDef) and node.name == "PromotionObligationClass")
    members = [node.value.value for node in enum.body if isinstance(node, ast.Assign)]
    enum_text = "\n".join(enum_source.splitlines()[enum.lineno - 1:enum.end_lineno])
    lexical_sites = re.findall(r"return (_satisfied_obligation|_failed_obligation|_scope_insufficient_obligation)\(", source)
    crosscheck = {
        "name_functions_token_lines": sum(bool(re.match(r"\s*(?:async )?def \w*obligation\w*\(", line)) for line in source.splitlines()),
        "helper_return_sites_token_lines": len(lexical_sites),
        "scope_helper_return_sites_token_lines": lexical_sites.count("_scope_insufficient_obligation"),
        "enum_assignment_token_lines": len(re.findall(r'^    [A-Z_]+ = "[a-z_]+"$', enum_text, re.M)),
        "single_draft_annotation_token_lines": len(re.findall(r"\) -> PromotionObligationDraft:", source)),
    }
    scope_sites = [row for row in returns if "_scope_insufficient_obligation" in row["helpers"]]
    report["result"] = {
        "unit": "syntactic helper-producing return site",
        "numerator": len(scope_sites),
        "denominator": len(returns),
        "return_sites": sorted(returns, key=lambda row: row["line"]),
        "name_only_functions": [{"name": n.name, "line": n.lineno} for n in sorted(names, key=lambda n: n.lineno)],
        "single_draft_producers": [{"name": n.name, "line": n.lineno} for n in sorted(producers, key=lambda n: n.lineno)],
        "class_identities": members,
        "direct_draft_constructor_returns": sum(isinstance(n, ast.Return) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "PromotionObligationDraft" for n in ast.walk(tree)),
        "independent_lexical_crosscheck": crosscheck,
    }
    expected = [len(names), len(returns), len(scope_sites), len(members), len(producers)]
    report["crosscheck_agrees"] = list(crosscheck.values()) == expected
    print(json.dumps(report, indent=2))
    if not report["crosscheck_agrees"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
