"Replay the bounded R5 source census; output is a read receipt, not a capability proof."

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys

SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".rego",
        ".sql",
        ".cypher",
        ".tf",
        ".sh",
        ".html",
        ".css",
        ".tmpl",
        ".tpl",
        "",
    }
)
CONTEXT = re.compile(
    (
        "admi|accept|approv|authori|allow|publish|promot|release|valid|govern"
        "|sign|claim|custod|record|eligible|ready|success|grant|capab|receipt"
        "|recommend|ground|deploy|binding"
    ),
    re.I,
)
NEGATIVE_ROLE = re.compile(
    (
        "(?:^|[_./-])(not|no|missing|absent|unavailable|unestablished|unsuppo"
        "rted|refused|rejected|blocked|failed|cold_start|candidate)(?:$|[_./-"
        "])"
    ),
    re.I,
)
REFUSAL = re.compile(
    (
        "refus|block|reject|deni|fail|unavail|not_admi|not_approv|not_author|"
        "not_promot|ineligible|unsupported"
    ),
    re.I,
)
LEXICAL = re.compile(
    r"literal\s*\[|promoted_record|public.?record|governed.?record|admission|refusal", re.I
)
UNRESOLVED = [
    {
        "class": "semantic_route_and_runtime_dispatch",
        "property": (
            "AST/lexical singleton inventory does not execute a producer, persist"
            "ence, consumer, or public projection; semantic routes require separa"
            "tely cited manual review."
        ),
    },
    {
        "class": "alias_and_dynamic_literal_semantics",
        "property": (
            "AST resolves direct Literal and aliases imported from typing/typing_"
            "extensions, but not arbitrary assignment aliases, imported user alia"
            "ses, metaclass mutation, runtime-generated types, or dynamic dispatc"
            "h."
        ),
    },
    {
        "class": "non_python_static_semantics",
        "property": (
            "Other selected source types are read case-insensitively, but no Type"
            "Script or other language type checker runs; imported, computed or di"
            "fferently spelled positive/refusal types can remain unresolved."
        ),
    },
    {
        "class": "outside_source_selector",
        "property": (
            "Tracked JSON/JSONL/TOML/YAML/Markdown and binary data, untracked/ign"
            "ored files, remote services, and external authority documents are ou"
            "tside this source census; content there cannot be ruled absent."
        ),
    },
    {
        "class": "keyword_candidate_boundary",
        "property": (
            "All direct singleton Literal sites are enumerated, but the shortened"
            " review set uses named English admission/refusal terms; synonyms or "
            "opaque names may require review outside that subset."
        ),
    },
]


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def command(root: pathlib.Path, args: list[str], receipts: list[dict]) -> bytes:
    result = subprocess.run(args, cwd=root, capture_output=True, check=False)  # noqa: S603 - fixed read-only Git/rg argv; no shell
    receipts.append(
        {
            "operation": "subprocess",
            "cwd": str(root),
            "argv": args,
            "returncode": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stdout_sha256": digest(result.stdout),
            "stderr": result.stderr.decode(errors="replace"),
            "inputs": (
                "Git index/tree/object metadata or explicitly passed source paths; su"
                "bprocess implementation dependencies are not content-bound."
            ),
        }
    )
    if result.returncode:
        raise RuntimeError(f"Command failed: {args!r}")
    return result.stdout


def python_sites(path: str, source: str) -> tuple[list[dict], list[dict]]:
    if "literal" not in source.casefold():
        return [], []
    tree = ast.parse(source, filename=path)
    lines = source.splitlines()
    aliases = {"Literal", "literal"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"typing", "typing_extensions"}:
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name.casefold() == "literal"
            )
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    singleton = []
    anchors = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        name = (
            node.value.id
            if isinstance(node.value, ast.Name)
            else node.value.attr
            if isinstance(node.value, ast.Attribute)
            else ""
        )
        if name.casefold() not in {alias.casefold() for alias in aliases}:
            continue
        arguments = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if len(arguments) != 1:
            continue
        parent = parents.get(node)
        field = ""
        if isinstance(parent, ast.AnnAssign):
            field = ast.unparse(parent.target)
        elif isinstance(parent, (ast.Assign, ast.TypeAlias)):
            field = ast.unparse(
                parent.targets[0] if isinstance(parent, ast.Assign) else parent.name
            )
        elif isinstance(parent, ast.arg):
            field = parent.arg
        elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            field = "<return>"
        owner = parent
        while owner is not None and not isinstance(
            owner, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            owner = parents.get(owner)
        owner_name = owner.name if owner is not None else "<module>"
        extent = owner if owner is not None else parent or node
        owner_text = "\n".join(lines[extent.lineno - 1 : extent.end_lineno])
        value = ast.unparse(arguments[0])
        row = {
            "path": path,
            "line": node.lineno,
            "owner": owner_name,
            "field": field,
            "value": value,
            "annotation": ast.unparse(node),
            "owner_end_line": getattr(owner, "end_lineno", node.end_lineno),
            "admission_context": bool(CONTEXT.search(owner_name + " " + field)),
            "refusal_context": bool(REFUSAL.search(owner_text or "")),
        }
        singleton.append(row)
        if (
            field.casefold() == "promoted_record"
            and isinstance(arguments[0], ast.Constant)
            and arguments[0].value is None
        ):
            anchors.append(row)
    return singleton, anchors


def scan(
    root: pathlib.Path,
    expected: int | None,
    fixture_manifest: pathlib.Path | None = None,
    revision_ref: str = "HEAD",
) -> dict:
    operations: list[dict] = []
    report = {
        "status": "UNRUN",
        "counterexample_before_search": (
            "A fourth admission DTO under a different spelling, or a positive Pub"
            "licRecord sibling outside the named anchors, defeats an anchor-only "
            "or keyword-only census."
        ),
        "root": str(root),
        "actual_inputs_read": operations,
        "selector": {
            "paths": "all Git tracked paths at repository root",
            "suffixes_case_insensitive": sorted(SOURCE_SUFFIXES),
            "extensionless": "included, even when configuration rather than executable source",
            "exclusions": "all other suffixes, untracked and ignored content",
        },
        "unresolved_by_construction": list(UNRESOLVED),
    }
    try:
        if fixture_manifest is None:
            revision = (
                command(root, ["git", "rev-parse", revision_ref], operations).decode().strip()
            )
            tracked = command(root, ["git", "ls-files", "-z"], operations).decode().split("\0")[:-1]
            raw_tree = command(root, ["git", "ls-tree", "-rz", "--full-tree", revision], operations)
            tree = {}
            for item in raw_tree.split(b"\0"):
                if item:
                    header, path = item.split(b"\t", 1)
                    mode, kind, blob = header.decode().split()
                    tree[path.decode()] = {"mode": mode, "kind": kind, "blob": blob}
        else:
            try:
                raw_manifest = fixture_manifest.read_bytes()
            except OSError as exc:
                operations.append(
                    {
                        "operation": "failed_fixture_manifest_read",
                        "path": str(fixture_manifest),
                        "error": str(exc),
                    }
                )
                raise
            operations.append(
                {
                    "operation": "read_fixture_manifest",
                    "path": str(fixture_manifest),
                    "bytes": len(raw_manifest),
                    "sha256": digest(raw_manifest),
                }
            )
            manifest = json.loads(raw_manifest)
            revision = "fixture-only-not-a-repository-verdict"
            tracked = sorted(manifest)
            tree = {path: {"blob": oid} for path, oid in manifest.items()}
            report["unresolved_by_construction"].append(
                {
                    "class": "fixture_denominator_is_supplied",
                    "property": (
                        "Fixture mode tests file selection and failure behavior; supplied man"
                        "ifest is never repository completeness evidence."
                    ),
                }
            )
        index_paths = list(tracked)
        pinned_additions = []
        pinned_missing = []
        if fixture_manifest is None and revision_ref != "HEAD":
            pinned_additions = sorted(
                path
                for path in set(index_paths) - set(tree)
                if pathlib.PurePosixPath(path).suffix.casefold() in SOURCE_SUFFIXES
            )
            pinned_missing = sorted(
                path
                for path in set(tree) - set(index_paths)
                if pathlib.PurePosixPath(path).suffix.casefold() in SOURCE_SUFFIXES
            )
            tracked = sorted(tree)
            report["unresolved_by_construction"].append(
                {
                    "class": "tracked_source_added_after_pinned_revision",
                    "property": (
                        "Listed current-index additions are outside the pinned source denomin"
                        "ator; their content and semantic effects are not judged by this hist"
                        "orical census."
                    ),
                }
            )
        selected = sorted(
            path
            for path in tracked
            if pathlib.PurePosixPath(path).suffix.casefold() in SOURCE_SUFFIXES
        )
        independent = sorted(
            path
            for path in tree
            if pathlib.PurePosixPath(path).suffix.casefold() in SOURCE_SUFFIXES
        )
        report.update(
            {
                "revision": revision,
                "revision_selector": revision_ref,
                "current_index_path_count": len(index_paths),
                "source_added_after_pinned_revision": pinned_additions,
                "pinned_source_missing_from_current_index": pinned_missing,
                "tracked_path_count": len(tracked),
                "selected_source_count": len(selected),
                "extension_distribution": dict(
                    sorted(
                        collections.Counter(
                            pathlib.PurePosixPath(path).suffix.casefold() or "<extensionless>"
                            for path in selected
                        ).items()
                    )
                ),
                "independent_tree_reconciliation": {
                    "tree_source_count": len(independent),
                    "index_only": sorted(set(selected) - set(independent)),
                    "tree_only": sorted(set(independent) - set(selected)),
                    "method": (
                        "git ls-files index selector compared with git ls-tree recursive comm"
                        "itted tree selector; each disk read also compared to its selected-re"
                        "vision tree blob OID"
                    ),
                },
            }
        )
        singleton, anchors, lexical, failures, drifts, python_count = [], [], [], [], [], 0
        for path in selected:
            try:
                raw = (root / path).read_bytes()
                blob = hashlib.sha1(
                    b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False
                ).hexdigest()
                operations.append(
                    {
                        "operation": "read_bytes",
                        "path": path,
                        "bytes": len(raw),
                        "sha256": digest(raw),
                        "git_blob_oid": blob,
                        "matches_selected_revision_blob": blob == tree.get(path, {}).get("blob"),
                    }
                )
                if blob != tree.get(path, {}).get("blob"):
                    drifts.append(path)
                source = raw.decode("utf-8")
                for number, line in enumerate(source.splitlines(), 1):
                    if LEXICAL.search(line):
                        lexical.append({"path": path, "line": number, "text": line.strip()})
                if pathlib.PurePosixPath(path).suffix.casefold() in {".py", ".pyi"}:
                    python_count += 1
                    sites, records = python_sites(path, source)
                    singleton.extend(sites)
                    anchors.extend(records)
            except (OSError, UnicodeError, SyntaxError) as exc:
                operations.append(
                    {
                        "operation": "failed_read_or_parse",
                        "path": path,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                failures.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
        relevant = [
            site for site in singleton if site["admission_context"] and site["refusal_context"]
        ]
        negative_roles = [
            site
            for site in singleton
            if site["field"]
            and (
                site["value"] in {"False", "None", "0"}
                or NEGATIVE_ROLE.search(site["value"].strip("'"))
            )
        ]
        # Independent lexical engine receives the complete enumerated file set, in bounded chunks.
        rg_matches, rg_failures = [], []
        for offset in range(0, len(selected), 100):
            chunk = selected[offset : offset + 100]
            args = [
                "rg",
                "--no-config",
                "--no-ignore",
                "--with-filename",
                "--line-number",
                "--ignore-case",
                r"promoted_record\s*:\s*(?:typing\.)?Literal\s*\[\s*None\s*\]",
                "--",
                *chunk,
            ]
            result = subprocess.run(args, cwd=root, capture_output=True, check=False)  # noqa: S603 - fixed read-only Git/rg argv; no shell
            operations.append(
                {
                    "operation": "independent_rg_source_read",
                    "argv_prefix": args[:8],
                    "actual_input_paths": chunk,
                    "returncode": result.returncode,
                    "stdout_sha256": digest(result.stdout),
                    "stdout_bytes": len(result.stdout),
                    "stderr": result.stderr.decode(errors="replace"),
                }
            )
            if result.returncode not in {0, 1}:
                rg_failures.append(result.stderr.decode(errors="replace"))
            rg_matches.extend(result.stdout.decode().splitlines())
        anchor_keys = {(row["path"], row["line"]) for row in anchors}
        rg_keys = {(line.split(":", 2)[0], int(line.split(":", 2)[1])) for line in rg_matches}
        report.update(
            {
                "python_files_examined": python_count,
                "python_parse_selector": (
                    "case-insensitive Literal token; files without it cannot contain a di"
                    "rect or typing-import alias Literal site"
                ),
                "unreadable_or_unsupported": failures,
                "source_drift": drifts,
                "singleton_literal_sites": singleton,
                "singleton_literal_site_count": len(singleton),
                "negative_role_selector": (
                    "Direct annotated field/parameter/return or module alias; False, None"
                    ", 0, or case-insensitive negative/candidate token bounded by start/e"
                    "nd/underscore/dot/slash/hyphen. No admission/refusal class-name filt"
                    "er."
                ),
                "negative_role_candidates": negative_roles,
                "negative_role_candidate_count": len(negative_roles),
                "negative_role_owner_group_count": len(
                    {(row["path"], row["owner"]) for row in negative_roles}
                ),
                "review_candidates": relevant,
                "review_candidate_count": len(relevant),
                "direct_none_literal_sites": [row for row in singleton if row["value"] == "None"],
                "direct_none_literal_count": sum(row["value"] == "None" for row in singleton),
                "promoted_record_none_sites": anchors,
                "promoted_record_none_count": len(anchors),
                "case_insensitive_lexical_matches": lexical,
                "independent_anchor_crosscheck": {
                    "rg_matches": rg_matches,
                    "ast_only": sorted(anchor_keys - rg_keys),
                    "rg_only": sorted(rg_keys - anchor_keys),
                    "rg_failures": rg_failures,
                },
                "expected_anchor_count": expected,
            }
        )
        incomplete = bool(
            failures
            or drifts
            or rg_failures
            or pinned_missing
            or selected != independent
            or anchor_keys != rg_keys
        )
        mismatch = expected is not None and len(anchors) != expected
        report["status"] = (
            "UNRUN" if incomplete else "FAIL" if mismatch else "PASS_BOUNDED_SOURCE_CENSUS"
        )
        if failures:
            report["unresolved_by_construction"].append(
                {
                    "class": "unreadable_or_unsupported_member",
                    "property": "Listed members remain undecided, never counted as empty.",
                }
            )
    except (RuntimeError, OSError, UnicodeError, ValueError) as exc:
        report["error"] = str(exc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revision",
        default="HEAD",
        help=(
            "Pinned tree to replay without checkout; current disk bytes must stil"
            "l match its source blobs"
        ),
    )
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--expect-promoted-none", type=int)
    parser.add_argument(
        "--fixture-manifest",
        type=pathlib.Path,
        help="Test-only supplied denominator; never a repository verdict",
    )
    args = parser.parse_args()
    report = scan(
        args.root.resolve(), args.expect_promoted_none, args.fixture_manifest, args.revision
    )
    instrument_bytes = pathlib.Path(__file__).read_bytes()
    report["actual_inputs_read"].append(
        {
            "operation": "read_instrument",
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": digest(instrument_bytes),
            "bytes": len(instrument_bytes),
        }
    )
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "PASS_BOUNDED_SOURCE_CENSUS" else 1


if __name__ == "__main__":
    sys.exit(main())
