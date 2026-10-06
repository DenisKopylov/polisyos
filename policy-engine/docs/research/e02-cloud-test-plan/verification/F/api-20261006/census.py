"""Enumerate immutable tracked inputs to the two LA-020 package facades.

This is a bounded research instrument, not an arbitrary-Python call graph.
It reads every tracked blob at the chosen ref, parses every Python member,
and separately reports literal imports, address strings and lexical mentions.
Computed import calls remain an explicit unresolved set.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tokenize
from collections import Counter
from pathlib import Path

PREFIX = "polisyos.foundry.methods.catalog.causal"
TARGETS = (f"{PREFIX}.causal_engine", f"{PREFIX}.interference", f"{PREFIX}.id_engine")
TOKEN = re.compile(r"causal_engine|interference", re.IGNORECASE)
GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("The immutable input census requires Git")


def _git(root: Path, *args: str) -> bytes:
    # Controlled argv, resolved executable, no shell; the ref is a separate argument.
    return subprocess.check_output([GIT, *args], cwd=root)  # noqa: S603


def _package(path: str) -> str:
    if "/src/" not in path:
        return ""
    address = path.split("/src/", 1)[1].removesuffix(".py").replace("/", ".")
    return (
        address.removesuffix(".__init__")
        if address.endswith(".__init__")
        else address.rsplit(".", 1)[0]
    )


def _related(address: str) -> bool:
    return any(address == target or address.startswith(target + ".") for target in TARGETS)


def _literal(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal(node.left, constants), _literal(node.right, constants)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        pieces = []
        for part in node.values:
            piece = _literal(
                part.value if isinstance(part, ast.FormattedValue) else part, constants
            )
            if piece is None:
                return None
            pieces.append(piece)
        return "".join(pieces)
    return None


def _candidate_basis(
    path: str, tree: ast.Module, call: ast.Call, constants: dict[str, str]
) -> dict:
    """Classify source/configuration evidence without asserting runtime clients.

    All rows remain syntactic candidates. Finite local maps and fixed namespace
    prefixes narrow the declared source quantity; arbitrary alias flow, global
    mutation, caller arguments and external plugins remain undecided.
    """
    scopes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= call.lineno <= (node.end_lineno or node.lineno)
    ]
    scope = (
        min(scopes, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
        if scopes
        else tree
    )
    role = (
        "runtime_source"
        if "/src/" in path
        else "test_source"
        if "/tests/" in path
        else "tool_source"
        if "/tools/" in path
        else "historical_research_source"
        if "/docs/" in path
        else "other_tracked_source"
    )
    result = {
        "source_role": role,
        "enclosing_callable": getattr(scope, "name", "<module>"),
        "classification": "computed_argument_unresolved",
        "runtime_client_established": False,
        "basis": "complete selected immutable source AST only; not executed dispatch",
    }
    argument = call.args[0] if call.args else None
    literal = _literal(argument, constants)
    if literal is not None:
        return {
            **result,
            "classification": "literal_target_candidate",
            "declared_addresses": [literal],
        }
    if isinstance(argument, ast.JoinedStr):
        prefix = ""
        for part in argument.values:
            value = _literal(
                part.value if isinstance(part, ast.FormattedValue) else part, constants
            )
            if value is None:
                break
            prefix += value
        if prefix and all(
            not (prefix.startswith(target) or target.startswith(prefix)) for target in TARGETS
        ):
            return {**result, "classification": "fixed_other_namespace", "declared_prefix": prefix}
    if not isinstance(argument, ast.Name):
        return result
    maps = {}
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        if not targets:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            maps.update({target.id: value for target in targets if isinstance(target, ast.Name)})
    addresses = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Subscript):
            continue
        if not isinstance(node.value.value, ast.Name) or node.value.value.id not in maps:
            continue
        for target in node.targets:
            index = None
            if isinstance(target, (ast.Tuple, ast.List)):
                indexes = [
                    index
                    for index, name in enumerate(target.elts)
                    if isinstance(name, ast.Name) and name.id == argument.id
                ]
                if len(indexes) != 1:
                    continue
                index = indexes[0]
            elif not isinstance(target, ast.Name) or target.id != argument.id:
                continue
            for value in maps[node.value.value.id].values():
                if index is not None:
                    if not isinstance(value, (list, tuple)) or len(value) <= index:
                        return result
                    value = value[index]
                if not isinstance(value, str):
                    return result
                addresses.append(value)
    if addresses:
        return {
            **result,
            "classification": "finite_source_configuration",
            "declared_addresses": sorted(set(addresses)),
            "unresolved_by_construction": (
                "Runtime mutation and alternate argument assignments are not executed or resolved."
            ),
        }
    return result


def python_rows(path: str, data: bytes) -> tuple[list[dict], list[dict], list[dict]]:
    """Return all literal imports, addressed strings and dynamic import candidates."""
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    tree = ast.parse(data.decode(encoding), filename=path)
    package = _package(path)
    constants: dict[str, str] = {}
    if "/src/" in path:
        constants["__name__"] = (
            path.split("/src/", 1)[1]
            .removesuffix(".py")
            .replace("/", ".")
            .removesuffix(".__init__")
        )
        constants["__package__"] = package
    # Resolve only file-level constants, never overwrite them with function-local aliases.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = _literal(node.value, constants)
            names = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value is not None:
                constants.update({name.id: value for name in names if isinstance(name, ast.Name)})
    imports, strings, dynamic = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            address = node.module or ""
            if node.level:
                if not package:
                    continue
                address = importlib.util.resolve_name("." * node.level + address, package)
            names = [alias.name for alias in node.names]
            if address == PREFIX:
                names = [name for name in names if _related(address + "." + name)]
            elif not _related(address):
                continue
            if names:
                imports.append(
                    {"line": node.lineno, "kind": "from", "module": address, "names": names}
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _related(alias.name):
                    imports.append(
                        {"line": node.lineno, "kind": "import", "module": alias.name, "names": []}
                    )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(target in node.value for target in TARGETS):
                strings.append({"line": node.lineno, "kind": "address_string", "value": node.value})
        elif isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name.split(".")[-1] not in {"import_module", "__import__"}:
                continue
            address = _literal(node.args[0], constants) if node.args else None
            if address is None or _related(address):
                dynamic.append(
                    {
                        "line": node.lineno,
                        "function": name,
                        "address": address,
                        "expression": ast.unparse(node.args[0])
                        if node.args
                        else "<no positional address>",
                        "resolution": "literal_related" if address else "computed_unresolved",
                        "source_configuration_basis": _candidate_basis(path, tree, node, constants),
                    }
                )
    return imports, strings, dynamic


def addressed_uses(path: str, data: bytes) -> list[dict]:
    """Enumerate syntactic alias/patch/docs/serialization uses, without flow claims."""
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    tree = ast.parse(data.decode(encoding), filename=path)
    package = _package(path)
    aliases: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases.setdefault(alias.asname or alias.name.split(".")[0], set()).add(
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            address = node.module or ""
            if node.level:
                if not package:
                    continue
                address = importlib.util.resolve_name("." * node.level + address, package)
            for alias in node.names:
                if alias.name != "*":
                    aliases.setdefault(alias.asname or alias.name, set()).add(
                        address + "." + alias.name
                    )

    def addresses(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, set())
        if isinstance(node, ast.Attribute):
            return {address + "." + node.attr for address in addresses(node.value)}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        return set()

    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            related = sorted(address for address in addresses(node) if _related(address))
            if related:
                rows.append(
                    {"line": node.lineno, "kind": "syntactic_symbol_use", "addresses": related}
                )
        elif isinstance(node, ast.Call):
            function = ast.unparse(node.func)
            category = function.split(".")[-1]
            if category not in {"patch", "object", "setattr", "render_doc", "dumps", "loads"}:
                continue
            related = sorted(
                {address for arg in node.args for address in addresses(arg) if _related(address)}
            )
            if related:
                symbol = _literal(node.args[1], {}) if len(node.args) > 1 else None
                rows.append(
                    {
                        "line": node.lineno,
                        "kind": "addressed_call",
                        "function": function,
                        "addresses": related,
                        "literal_second_argument": symbol,
                    }
                )
    return rows


def census(root: Path, ref: str) -> dict:
    """Read the complete chosen Git tree and disclose all excluded/unresolved classes."""
    sha = _git(root, "rev-parse", ref + "^{commit}").decode().strip()
    entries = []
    for record in _git(root, "ls-tree", "-rz", "--full-tree", sha).split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        entries.append((path.decode(), mode, kind, oid))
    independent = _git(root, "ls-tree", "-r", "--name-only", "-z", sha).split(b"\0")[:-1]
    if sorted(path for path, *_ in entries) != sorted(p.decode() for p in independent):
        raise RuntimeError("Complete input-tree enumerations disagree")
    manifest = hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()
    members, imports, strings, dynamic, mentions, errors, uses = [], [], [], [], [], [], []
    counts: Counter[str] = Counter()
    # Fixed read-only Git command; blob ids come from the chosen immutable tree.
    with subprocess.Popen(  # noqa: S603
        [GIT, "cat-file", "--batch"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as reader:
        if reader.stdin is None or reader.stdout is None:
            raise RuntimeError("Git input pipes were not established")
        for path, mode, kind, oid in entries:
            counts["tracked_entries"] += 1
            counts["extension:" + (Path(path).suffix or "<none>")] += 1
            if path.endswith(".py"):
                counts["python_tracked"] += 1
            if kind != "blob":
                members.append({"path": path, "oid": oid, "classification": kind})
                counts["non_blob"] += 1
                continue
            reader.stdin.write((oid + "\n").encode())
            reader.stdin.flush()
            header = reader.stdout.readline().decode().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError(f"Unresolvable tracked blob: {path}@{oid}")
            size = int(header[2])
            data = reader.stdout.read(size)
            if len(data) != size or reader.stdout.read(1) != b"\n":
                raise RuntimeError(f"Incomplete tracked blob: {path}@{oid}")
            identity = {
                "path": path,
                "oid": oid,
                "bytes": size,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            if mode == "120000":
                identity["classification"] = "symlink_blob; target not traversed"
                counts["symlink"] += 1
                members.append(identity)
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                identity["classification"] = "non_utf8"
                counts["non_utf8"] += 1
                members.append(identity)
                continue
            if b"\0" in data:
                identity["classification"] = "binary_nul"
                counts["binary_nul"] += 1
                members.append(identity)
                continue
            identity["classification"] = "utf8_text"
            counts["utf8_text"] += 1
            members.append(identity)
            for line, value in enumerate(text.splitlines(), 1):
                if TOKEN.search(value):
                    mentions.append(
                        {
                            "path": path,
                            "oid": oid,
                            "line": line,
                            "full_address": any(target in value for target in TARGETS),
                        }
                    )
            if not path.endswith(".py"):
                continue
            counts["python"] += 1
            try:
                grouped = python_rows(path, data)
            except (SyntaxError, ValueError, UnicodeError) as exc:
                errors.append(
                    {
                        "path": path,
                        "oid": oid,
                        "error": str(exc),
                        "related_lexical_bytes": bool(TOKEN.search(text)),
                    }
                )
                continue
            counts["python_parsed"] += 1
            for destination, rows in zip((imports, strings, dynamic), grouped, strict=True):
                destination.extend({"path": path, "oid": oid, **row} for row in rows)
            uses.extend({"path": path, "oid": oid, **row} for row in addressed_uses(path, data))
        reader.stdin.close()
        if reader.wait() != 0:
            raise RuntimeError("Git blob reader failed")
    return {
        "schema": "policyos.e02.facade_census.v2",
        "executing_party": "F/fit_tmle API writer",
        "source_sha": sha,
        "source_tree": _git(root, "rev-parse", sha + "^{tree}").decode().strip(),
        "target_facades": TARGETS,
        "tracked_manifest_sha256": manifest,
        "denominator": dict(sorted(counts.items())),
        "literal_imports": imports,
        "address_strings": strings,
        "dynamic_import_candidates": dynamic,
        "dynamic_candidate_classification_counts": dict(
            sorted(
                Counter(
                    row["source_configuration_basis"]["classification"] for row in dynamic
                ).items()
            )
        ),
        "addressed_syntactic_uses": uses,
        "lexical_mentions": mentions,
        "unparsed_python": errors,
        "excluded_members": [row for row in members if row["classification"] != "utf8_text"],
        "limits": [
            "Full immutable tracked Git blob set only; "
            "ignored/untracked/third-party callers excluded.",
            "Lexical mentions include unrelated uses and historical receipts; "
            "they are not execution evidence.",
            "Literal addresses and file-level constants are resolved; arbitrary computed "
            "import/alias/exec/plugin configuration remains unresolved.",
            "Address strings enumerate FQN/docs/patch/config references; "
            "they are not a general serialization or docs-build guarantee.",
            "Imported alias references are syntactic candidates; "
            "scoped reassignment and runtime alias/data flow are not resolved.",
            "Computed import candidate counts are not actual facade client counts. "
            "Source-role, fixed-prefix and finite-map classifications disclose declared "
            "configuration only; no external/private/plugin compatibility is inferred.",
            "Symlink targets and non-UTF8/binary content are named excluded classes; "
            "this is not a repository-wide absence proof.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = census(args.root, args.ref)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "source_sha": result["source_sha"],
                "denominator": result["denominator"],
                "literal_imports": len(result["literal_imports"]),
                "literal_import_files": len({r["path"] for r in result["literal_imports"]}),
                "address_strings": len(result["address_strings"]),
                "computed_import_candidates": sum(
                    r["address"] is None for r in result["dynamic_import_candidates"]
                ),
                "unparsed_python": len(result["unparsed_python"]),
            }
        )
        + "\n"
    )
    if any(error["related_lexical_bytes"] for error in result["unparsed_python"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
