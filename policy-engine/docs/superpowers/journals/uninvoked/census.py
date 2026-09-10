"""Research instrument: complete tracked Python AST census, independently token-checked.

Run from policy-engine. Raw records are deliberately gitignored. This instrument
reports syntax, never asserts that a static call is reached by a real run.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import keyword
import subprocess
import tokenize
from collections import Counter
from pathlib import Path


TARGETS = {
    "AcquisitionAuthorityGateway", "HumanDecisionProductionGateway",
    "AgentActionAuthorityGateway", "RealAcquisitionOwnerGateway",
    "RecordedAcquisitionOwnerGateway", "CurrentMandateOwnerEvidence",
    "produce_agent_action_authority_decision",
    "admit_acquisition_with_production_semantic_epoch", "SemanticEpochQualificationAdapter",
    "compose_production_semantic_epoch_admission", "qualify_chronology_query",
    "for_unallocated_policy_query", "EpochAnchorCustodyService",
    "build_production_epoch_anchor_custody_provider", "NoEpochAnchorAppointmentResolver",
    "EmptyEpochAnchorAuthorityRegistry", "EpochAnchorCustodyProvider",
    "evaluate_acceptance_and_custody", "evaluate_retained_challenge",
    "validate_adapter_semantic_preservation", "admit_playbook_step",
    "consume_foundry_method_result", "validate_outcome_run",
    "evaluate_openalex_claim_extractor_accuracy", "select_method_for_input_contract",
    "extract_span_grounded_claims_from_openalex_work", "run_non_data_acquisition",
    "run_assurance", "run_source_content", "run_comprehension_trial",
    "run_instrument", "read_locale_catalogues",
}
MODULES = {
    "operator_comprehension", "multilingual_assurance", "locale_census",
    "non_data_acquisition", "ceiling_relations", "adaptation_transition",
    "semantic_epoch", "chronology_custody", "agent_action_authority",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def tokens_for(source: str) -> list[tokenize.TokenInfo]:
    return [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
            if t.type not in {tokenize.COMMENT, tokenize.NL,
                              tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
                              tokenize.ENCODING}]


def independent_calls(source: str) -> set[tuple[int, int, str]]:
    """Token grammar: NAME immediately followed by '('; exclude definitions/keywords.

    This deliberately over-approximates class patterns; disagreement is recorded,
    never erased using the first parser. Parenthesized/subscript callees are outside
    this cross-check's declared intersection, and remain in the full AST census.
    """
    ts = tokens_for(source)
    return {(t.start[0], t.start[1], t.string) for i, t in enumerate(ts[:-1])
            if t.type == tokenize.NAME and not keyword.iskeyword(t.string)
            and ts[i + 1].string == "("
            and (i == 0 or ts[i - 1].string not in {"def", "class"})}


def measure(root: Path, ref: str) -> tuple[dict, dict]:
    """Walk ALL tracked src Python files; reconcile index with independent tree listing."""
    prefix = "policy-engine/src/"
    indexed = {x.decode() for x in git("ls-files", "-z", "--full-name").split(b"\0")
               if x.decode().startswith(prefix) and x.endswith(b".py")}
    tree = {x.decode() for x in git("ls-tree", "-rz", "--full-tree", "--name-only", ref, "--", "policy-engine/src").split(b"\0")
            if x.endswith(b".py")}
    # ls-tree paths are repository-root-relative even from a subdirectory.
    if indexed != tree:
        raise ValueError(f"denominator_disagreement: index={len(indexed)} tree={len(tree)}; first={sorted(indexed ^ tree)[:3]}")
    records: list[dict] = []
    differences: list[dict] = []
    hashes = {}
    count = Counter()
    for path in sorted(indexed):
        raw = (root / path).read_bytes()
        hashes[path] = hashlib.sha256(raw).hexdigest()
        source = raw.decode("utf-8-sig")
        parsed = ast.parse(source, filename=path)
        ts = tokens_for(source)
        token_index = {t.start: i for i, t in enumerate(ts)}
        lines = source.splitlines()
        aliases: dict[str, str] = {}
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{node.module or ''}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split('.')[0]] = alias.name
        def name(expr: ast.AST) -> str:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return f"{name(expr.value)}.{expr.attr}"
            return "<dynamic>"
        primary_simple = set()
        scope: list[str] = []
        def visit(node: ast.AST) -> None:
            item = None
            is_scope = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            if is_scope:
                item = {"kind": "class_definition" if isinstance(node, ast.ClassDef)
                        else "function_definition", "symbol": node.name}
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                item = {"kind": "import", "symbol": ast.unparse(node),
                        "aliases": [a.asname or a.name for a in node.names]}
            elif isinstance(node, ast.Call):
                callee = name(node.func)
                head, *tail = callee.split(".")
                resolved = ".".join([aliases.get(head, head), *tail])
                item = {"kind": "call", "symbol": callee, "resolved_hint": resolved}
                if isinstance(node.func, (ast.Name, ast.Attribute)):
                    leaf = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                    line = node.func.end_lineno
                    end = len(lines[line - 1].encode()[:node.func.end_col_offset].decode())
                    col = end - len(leaf)
                    index = token_index.get((line, col))
                    if index is not None and index + 1 < len(ts) and ts[index + 1].string == "(":
                        primary_simple.add((line, col, leaf))
            if item:
                count[item["kind"]] += 1
                records.append({"path": path, "line": node.lineno, "scope": ".".join(scope), **item})
            if is_scope:
                scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                visit(child)
            if is_scope:
                scope.pop()
        visit(parsed)
        secondary = independent_calls(source)
        for kind, values in (("ast_only", primary_simple - secondary),
                             ("token_only", secondary - primary_simple)):
            for line, column, symbol in sorted(values):
                differences.append({"path": path, "line": line, "column": column,
                                    "symbol": symbol, "kind": kind})
        count["ast_simple_call_sites"] += len(primary_simple)
        count["token_simple_call_sites"] += len(secondary)
    target_rows = {target: [r for r in records
                           if r["symbol"].split(".")[-1] == target
                           or (r["kind"] == "call" and r["resolved_hint"].split(".")[-1] == target)
                           or (r["kind"] == "import" and target in r["symbol"].replace(",", " ").split())]
                   for target in sorted(TARGETS)}
    module_rows = {module: [r for r in records if r["kind"] == "import"
                           and module in r["symbol"].replace(".", " ").replace(",", " ").split()]
                   for module in sorted(MODULES)}
    summary = {
        "ref": ref, "head": git("rev-parse", ref).decode().strip(),
        "path_denominator": "complete tracked policy-engine/src/**/*.py",
        "file_type_denominator": "Python .py only; tests and tools excluded",
        "file_count": len(indexed), "path_set_sha256": digest(sorted(indexed)),
        "source_set_sha256": digest(hashes), "parse_failures": 0,
        "independent_denominator": "git ls-files vs git ls-tree exact path-set equality",
        "counts": dict(count), "crosscheck_differences": differences,
        "targets": target_rows, "module_imports": module_rows,
        "limits": ["Static syntax is not runtime reachability or load-bearing invocation.",
                   "resolved_hint is module import alias expansion, not type or scope proof.",
                   "Token cross-check covers unparenthesized NAME/attribute call syntax only.",
                   "Calls through callbacks, registries, getattr and factories require tracing.",
                   "Import statements, definitions and construction calls are distinct records."],
    }
    return summary, {"source_hashes": hashes, "records": records}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    summary, raw = measure(root, args.ref)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "complete.json").write_text(json.dumps(raw, separators=(",", ":")) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"targets", "module_imports", "crosscheck_differences"}}, indent=2))


if __name__ == "__main__":
    main()
