"""Exercise actual immutable missing-reference admission AST with controlled metadata."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"


def require(condition: bool) -> None:
    """Keep discriminator predicates active with optimized Python too."""
    if not condition:
        raise AssertionError("Independent metadata discriminator failed")


def main() -> None:
    """Review the root-owned generic mapping and namespace delta without pytest."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("Git executable unavailable")

    def git(*argv: str) -> bytes:
        return subprocess.check_output([git_executable, "-C", str(args.repo), *argv])  # noqa: S603 - immutable argv-only Git reads

    def source(sha: str, path: str) -> bytes:
        return git("show", f"{sha}:{path}")

    selector_path = PREFIX + "final-cohort-selector.py"
    before = source(args.base, selector_path)
    after = source(args.target, selector_path)
    module = ast.parse(after, filename=selector_path)
    main_node = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    start = next(
        index
        for index, node in enumerate(main_node.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "existing" for t in node.targets)
    )
    end = next(
        index
        for index, node in enumerate(main_node.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "result" for t in node.targets)
    )
    admission_ast = ast.Module(body=copy.deepcopy(main_node.body[start:end]), type_ignores=[])
    ast.fix_missing_locations(admission_ast)
    filename = selector_path + "#actual-absent-admission"
    code = compile(admission_ast, filename, "exec")
    canonical = "tests/arbitrary/test_canonical_absent.py"
    incidental = "tests/arbitrary/test_incidental_absent.py"
    present = "tests/arbitrary/test_present.py"
    body = "def test_real_discriminator():\n    pass\n"
    cases = []
    for mask in range(4):
        mapping = {
            path: {
                "candidates": [{"selector": present + "::test_real_discriminator"}],
                "residuals": ["bounded controlled metadata equivalence, no execution"],
            }
            for bit, path in enumerate((canonical, incidental))
            if mask & (1 << bit)
        }
        namespace = {
            "ast": ast,
            "hashlib": hashlib,
            "sources": {
                path: {
                    ("kind", path): {
                        "kind": "canonical_card_plan"
                        if path == canonical
                        else "metadata_reference",
                        "locator": path,
                    }
                }
                for path in (canonical, incidental, present)
            },
            "planned": {canonical: {"EXE-01"}},
            "tracked": {"policy-engine/" + present},
            "mapping": mapping,
            "text": lambda path: body,
            "identity": lambda path: {"path": path, "source": "controlled immutable AST input"},
            "normalize": lambda selector: selector.split("::")[0].removeprefix("policy-engine/"),
        }
        exec(code, namespace)  # noqa: S102 - actual hash-bound root admission AST, controlled metadata only
        rows = {row["named_selector"]: row for row in namespace["missing"]}
        require(set(rows) == {canonical, incidental})
        require([row["test_path"] for row in namespace["existing"]] == [present])
        for path, row in rows.items():
            require(row["state"] == "UNRUN_named_selector_absent")
            require(row["required_by_canonical_plan"] == (path == canonical))
            require(row["has_reviewed_equivalence_map"] == (path in mapping))
            require(bool(row["equivalent_candidate_selectors"]) == (path in mapping))
            if path in mapping:
                require(
                    row["equivalent_candidate_selectors"][0]["execution_state"].startswith("UNRUN")
                )
            else:
                require(row["equivalence_grade"].startswith("UNRUN"))
        cases.append(
            {"map_subset": sorted(mapping), "outcome": "PASS", "missing": list(rows.values())}
        )
    invalid = copy.copy(namespace)
    invalid["mapping"] = {
        canonical: {"candidates": [{"selector": present + "::test_absent_body"}], "residuals": []}
    }
    try:
        exec(code, invalid)  # noqa: S102 - same actual admission AST, invalid metadata discriminator
    except ValueError as exc:
        invalid_result = {"outcome": "PASS", "typed_refusal": str(exc)}
    else:
        raise AssertionError("Invalid mapped body escaped exact-one-source-definition guard")

    def helper_ast(blob: bytes) -> str:
        tree = ast.parse(blob)
        return ast.dump(
            next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "native_pytest_positionals"
            ),
            include_attributes=False,
        )

    helper_equal = helper_ast(before) == helper_ast(after)
    require(helper_equal)
    launcher_path = PREFIX + "final-root-evidence/run_frozen.py"
    old_launcher = source(args.base, launcher_path)
    new_launcher = source(args.target, launcher_path)
    require(new_launcher == old_launcher.replace(b"repaired-final", b"terminal-final"))
    namespace_equal = ast.dump(
        ast.parse(new_launcher.replace(b"terminal-final", b"repaired-final")),
        include_attributes=False,
    ) == ast.dump(ast.parse(old_launcher), include_attributes=False)
    require(namespace_equal)
    profile_path = PREFIX + "final-root-evidence/pytest-cli-option-profile.json"
    profile_equal = source(args.base, profile_path) == source(args.target, profile_path)
    require(profile_equal)
    changed = git("diff", "--name-only", args.base, args.target).decode().splitlines()
    require(changed == [selector_path, launcher_path])
    result = {
        "schema": "policyos.e02.independent_selector_lineage_fix_review.v1",
        "base_sha": args.base,
        "target_sha": args.target,
        "target_tree": git("rev-parse", args.target + "^{tree}").decode().strip(),
        "command": sys.argv,
        "changed_paths": changed,
        "source_identities": [
            {
                "path": path,
                "sha256": hashlib.sha256(source(args.target, path)).hexdigest(),
                "bytes": len(source(args.target, path)),
            }
            for path in (selector_path, launcher_path, profile_path)
        ],
        "actual_admission_ast_sha256": hashlib.sha256(
            ast.dump(admission_ast, include_attributes=False).encode()
        ).hexdigest(),
        "controls": cases,
        "invalid_exact_body_control": invalid_result,
        "option_helper_ast_unchanged": helper_equal,
        "pinned_option_profile_unchanged": profile_equal,
        "namespace_only_launcher_bytes": True,
        "namespace_normalized_launcher_ast_unchanged": namespace_equal,
        "outcome": "PASS",
        "qualification": (
            "Four mapping-subset controls execute the actual root classification/resolution AST; "
            "one invalid body retains exact-source refusal. Namespace normalization matches both "
            "complete launcher bytes and AST. No pytest, collection, live registry, gate, product "
            "code, or root edit. Historical 19 grammar controls remain bound to d3; unchanged "
            "helper/profile is a delta comparison, not a new 19-case runtime claim."
        ),
    }
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
