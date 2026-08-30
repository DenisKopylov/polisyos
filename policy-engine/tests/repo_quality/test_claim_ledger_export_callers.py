from __future__ import annotations

import ast
import io
import subprocess
import tokenize
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

_ROOT = Path(__file__).resolve().parents[2]
_IGNORED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
_LEGACY_CLAIM_API_NAMES = {
    "append_and_persist_claim_event",
    "append_only_audit_summary",
    "blocked_claim_summary",
    "claim_ledger_inputs",
    "claim_ledger_summary",
    "claim_ledger_v2_inputs",
    "export_claim_ledger",
    "legacy_claim_ledger_export_status",
    "load_append_only_claim_ledger",
    "load_claim_ledger",
    "load_claim_ledger_as_append_only",
    "persist_append_only_claim_ledger",
    "persist_claim_ledger",
    "retention_window_for_export",
}
_PRIVATE_RAW_CLAIM_NAMES = {
    "_format_resolved_claim_ledger",
    "_persist_append_only_claim_ledger",
    "_persist_claim_bridge_pending",
    "_persist_claim_ledger",
}
_CLAIM_AUTHORITY_MODULE = "src/polisyos/scientist/evidence/claims/head_index.py"
_DENOMINATOR_TEST = "tests/repo_quality/test_claim_ledger_export_callers.py"
_EXPECTED_CONTEXT_CONSTRUCTORS = {
    "src/polisyos/runtime/quality/workspace/loop.py",
    "src/polisyos/scientist/methods/backtesting/composition_bridge.py",
    "src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py",
    "src/polisyos/scientist/orchestration/workflows/builder.py",
}
_EXPECTED_TEST_CLAIM_CONTEXT_CONSTRUCTORS = {
    "tests/unit/scientist/methods/backtesting/test_composition_bridge.py",
    "tests/unit/scientist/nodes/test_build_policy_output_bundle.py",
}
_EXPECTED_INITIAL_ROOT_CALLERS = {
    "src/polisyos/scientist/nodes/builtins/decide/decision_packet/builder.py",
    "src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py",
}


class _CallSite(NamedTuple):
    path: str
    line: int
    column: int


@lru_cache(maxsize=1)
def _filesystem_candidate_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            candidate
            for suffix in ("*.py", "*.pyi")
            for candidate in _ROOT.rglob(suffix)
            if not (_IGNORED_PARTS & set(candidate.parts))
        )
    )


@lru_cache(maxsize=1)
def _git_candidate_files() -> tuple[Path, ...]:
    """Derive the tracked/untracked candidate denominator from Git itself."""

    prefix = subprocess.run(
        ["git", "-C", str(_ROOT), "rev-parse", "--show-prefix"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = subprocess.run(
        ["git", "-C", str(_ROOT), "ls-files", "-co", "--exclude-standard", "-z", "--", "."],
        check=True,
        capture_output=True,
    )
    root_prefix = prefix.rstrip("/") + "/" if prefix else ""
    candidates: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative_to_repo = raw.decode("utf-8")
        relative = (
            relative_to_repo[len(root_prefix) :]
            if root_prefix and relative_to_repo.startswith(root_prefix)
            else relative_to_repo
        )
        candidate = _ROOT / relative
        if candidate.suffix in {".py", ".pyi"} and candidate.is_file():
            candidates.append(candidate)
    return tuple(sorted(set(candidates)))


def _attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_column(node: ast.Call) -> int:
    if isinstance(node.func, ast.Attribute) and node.func.end_col_offset is not None:
        return node.func.end_col_offset - len(node.func.attr)
    return node.col_offset


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    observed: set[str] = set()
    while name in aliases and name not in observed:
        observed.add(name)
        name = aliases[name]
    return name


def _scan_ast_source(source: str, *, relative: str) -> dict[str, set[_CallSite]]:
    tree = ast.parse(source, filename=relative)
    calls: dict[str, set[_CallSite]] = {}

    class Scanner(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scopes: list[dict[str, str]] = [{}]

        def _aliases(self) -> dict[str, str]:
            merged: dict[str, str] = {}
            for scope in self.scopes:
                merged.update(scope)
            return merged

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                if alias.name != "*":
                    self.scopes[-1][alias.asname or alias.name] = alias.name

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            value = _attribute_name(node.value)
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    self.visit(target)
                    continue
                if value is None:
                    self.scopes[-1].pop(target.id, None)
                else:
                    self.scopes[-1][target.id] = _resolve_alias(value, self._aliases())

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self.visit(node.value)
            if isinstance(node.target, ast.Name):
                value = _attribute_name(node.value) if node.value is not None else None
                if value is None:
                    self.scopes[-1].pop(node.target.id, None)
                else:
                    self.scopes[-1][node.target.id] = _resolve_alias(value, self._aliases())

        def _visit_nested_scope(self, body: list[ast.stmt]) -> None:
            self.scopes.append({})
            for statement in body:
                self.visit(statement)
            self.scopes.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            for decorator in node.decorator_list:
                self.visit(decorator)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            self._visit_nested_scope(node.body)

        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            for decorator in node.decorator_list:
                self.visit(decorator)
            for base in node.bases:
                self.visit(base)
            self._visit_nested_scope(node.body)

        def visit_Call(self, node: ast.Call) -> None:
            name = _attribute_name(node.func)
            if name is not None:
                canonical = _resolve_alias(name, self._aliases())
                calls.setdefault(canonical, set()).add(
                    _CallSite(relative, node.lineno, _call_column(node))
                )
            self.generic_visit(node)

    Scanner().visit(tree)
    return calls


def _token_statements(source: str) -> tuple[tuple[tokenize.TokenInfo, ...], ...]:
    statements: list[tuple[tokenize.TokenInfo, ...]] = []
    current: list[tokenize.TokenInfo] = []
    ignored = {
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NL,
        tokenize.COMMENT,
    }
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in ignored:
            continue
        if token.type == tokenize.NEWLINE:
            if current:
                statements.append(tuple(current))
                current = []
            continue
        current.append(token)
    if current:
        statements.append(tuple(current))
    return tuple(statements)


def _token_aliases(
    statements: tuple[tuple[tokenize.TokenInfo, ...], ...],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for statement in statements:
        strings = [token.string for token in statement]
        if strings[:1] == ["from"] and "import" in strings:
            position = strings.index("import") + 1
            while position < len(strings):
                imported = strings[position]
                if not imported.isidentifier():
                    position += 1
                    continue
                local = imported
                if position + 2 < len(strings) and strings[position + 1] == "as":
                    local = strings[position + 2]
                    position += 3
                else:
                    position += 1
                aliases[local] = imported
        if len(strings) >= 3 and strings[0].isidentifier() and strings[1] == "=":
            value_names = [value for value in strings[2:] if value.isidentifier()]
            if value_names:
                aliases[strings[0]] = value_names[-1]
    return aliases


def _scan_tokens_source(source: str, *, relative: str) -> dict[str, set[_CallSite]]:
    statements = _token_statements(source)
    aliases: dict[str, str] = {}
    calls: dict[str, set[_CallSite]] = {}
    for statement in statements:
        strings = [token.string for token in statement]
        for index, token in enumerate(statement[:-1]):
            if token.type != tokenize.NAME or statement[index + 1].string != "(":
                continue
            previous = statement[index - 1].string if index else None
            if previous in {"class", "def"}:
                continue
            canonical = _resolve_alias(token.string, aliases)
            calls.setdefault(canonical, set()).add(
                _CallSite(relative, token.start[0], token.start[1])
            )
        statement_aliases = _token_aliases((statement,))
        assigned = strings[0] if len(strings) >= 2 and strings[1] == "=" else None
        if isinstance(assigned, str) and assigned.isidentifier() and not statement_aliases:
            aliases.pop(assigned, None)
        else:
            for name, target in statement_aliases.items():
                aliases[name] = _resolve_alias(target, aliases)
    return calls


@lru_cache(maxsize=1)
def _walk_denominator() -> tuple[
    dict[str, set[_CallSite]],
    dict[str, set[_CallSite]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    ast_calls: dict[str, set[_CallSite]] = {}
    token_calls: dict[str, set[_CallSite]] = {}
    imports: dict[str, set[str]] = {}
    exports: dict[str, set[str]] = {}
    for source in _filesystem_candidate_files():
        relative = source.relative_to(_ROOT).as_posix()
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source))
        for name, rows in _scan_ast_source(text, relative=relative).items():
            ast_calls.setdefault(name, set()).update(rows)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.setdefault(alias.name, set()).add(relative)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(
                    isinstance(target, ast.Name) and target.id == "__all__" for target in targets
                ):
                    continue
                value = node.value
                if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                    for item in value.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            exports.setdefault(item.value, set()).add(relative)
    for source in _git_candidate_files():
        relative = source.relative_to(_ROOT).as_posix()
        text = source.read_text(encoding="utf-8")
        for name, rows in _scan_tokens_source(text, relative=relative).items():
            token_calls.setdefault(name, set()).update(rows)
    return ast_calls, token_calls, imports, exports


def test_raw_claim_persistence_has_zero_production_callers_outside_authority() -> None:
    ast_calls, token_calls, _, _ = _walk_denominator()
    watched = _LEGACY_CLAIM_API_NAMES | _PRIVATE_RAW_CLAIM_NAMES
    external = {
        name: sorted(
            row
            for row in ast_calls.get(name, set()) | token_calls.get(name, set())
            if row.path.startswith("src/") and row.path != _CLAIM_AUTHORITY_MODULE
        )
        for name in sorted(watched)
    }

    assert not {name: rows for name, rows in external.items() if rows}


def test_complete_old_export_caller_denominator_is_zero() -> None:
    ast_calls, token_calls, imports, exports = _walk_denominator()
    external = {
        name: {
            "ast_calls": sorted(ast_calls.get(name, set())),
            "token_calls": sorted(token_calls.get(name, set())),
            "imports": sorted(imports.get(name, set()) - {_CLAIM_AUTHORITY_MODULE}),
            "exports": sorted(exports.get(name, set()) - {_CLAIM_AUTHORITY_MODULE}),
        }
        for name in sorted(_LEGACY_CLAIM_API_NAMES)
    }

    assert all(
        not row["ast_calls"]
        and not row["token_calls"]
        and not row["imports"]
        and not row["exports"]
        for row in external.values()
    ), external


def test_all_execution_context_constructors_require_same_claim_owner_port() -> None:
    ast_calls, token_calls, _, _ = _walk_denominator()
    ast_base = ast_calls.get("ExecutionContext", set())
    token_base = token_calls.get("ExecutionContext", set())
    ast_claim = ast_calls.get("ClaimCapableExecutionContext", set())
    token_claim = token_calls.get("ClaimCapableExecutionContext", set())

    assert ast_base == token_base
    assert ast_claim == token_claim
    test_base = {row for row in ast_base if row.path.startswith("tests/")}
    assert ast_base == test_base
    assert {row.path for row in ast_claim if row.path.startswith("src/")} == (
        _EXPECTED_CONTEXT_CONSTRUCTORS
    )
    test_claim_contexts = {row for row in ast_claim if row.path.startswith("tests/")}
    assert {row.path for row in test_claim_contexts} == (_EXPECTED_TEST_CLAIM_CONTEXT_CONSTRUCTORS)
    assert len(test_claim_contexts) == len(_EXPECTED_TEST_CLAIM_CONTEXT_CONSTRUCTORS)
    assert not {row for row in ast_claim if not row.path.startswith(("src/", "tests/"))}


def test_new_initial_producer_or_unenumerated_legacy_root_fails_denominator() -> None:
    ast_calls, token_calls, _, _ = _walk_denominator()
    observed = ast_calls.get("prepare_initial_ledger", set()) | ast_calls.get(
        "finalize_initial_root", set()
    )
    token_observed = token_calls.get("prepare_initial_ledger", set()) | token_calls.get(
        "finalize_initial_root", set()
    )
    observed = {
        row
        for row in observed
        if row.path.startswith("src/") and row.path != _CLAIM_AUTHORITY_MODULE
    }
    token_observed = {
        row
        for row in token_observed
        if row.path.startswith("src/") and row.path != _CLAIM_AUTHORITY_MODULE
    }

    assert observed == token_observed
    assert {row.path for row in observed} == _EXPECTED_INITIAL_ROOT_CALLERS


def test_complete_denominator_follows_import_and_assignment_aliases() -> None:
    source = """
from owner import persist_claim_ledger as save
from context import ExecutionContext as EC
save()
Alias = EC
Alias()
"""

    ast_calls = _scan_ast_source(source, relative="candidate.py")
    token_calls = _scan_tokens_source(source, relative="candidate.py")

    assert ast_calls == token_calls
    assert set(ast_calls) == {"ExecutionContext", "persist_claim_ledger"}


def test_complete_denominator_uses_reaching_alias_not_later_reassignment() -> None:
    source = """
from context import ExecutionContext as EC
EC()
EC = OtherContext
EC()
"""

    ast_calls = _scan_ast_source(source, relative="candidate.py")
    token_calls = _scan_tokens_source(source, relative="candidate.py")

    assert ast_calls == token_calls
    assert ast_calls["ExecutionContext"] == {_CallSite("candidate.py", 3, 0)}
    assert ast_calls["OtherContext"] == {_CallSite("candidate.py", 5, 0)}


def test_candidate_file_denominators_reconcile_independently() -> None:
    assert _filesystem_candidate_files() == _git_candidate_files()


def test_public_export_api_accepts_owner_key_not_ledger_bytes_or_ref() -> None:
    from polisyos.scientist.evidence.claims.head_index import ClaimLedgerExportService

    tree = ast.parse((_ROOT / _CLAIM_AUTHORITY_MODULE).read_text(encoding="utf-8"))
    service = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == ClaimLedgerExportService.__name__
    )
    export = next(
        node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == "export"
    )
    parameters = {argument.arg for argument in (*export.args.args, *export.args.kwonlyargs)}

    assert parameters == {"self", "owner_key", "audience"}


def test_fake_head_or_artifact_store_cannot_enter_export_method() -> None:
    from polisyos.scientist.evidence.claims.head_index import ClaimLedgerExportService

    annotations = ClaimLedgerExportService.export.__annotations__

    assert "store" not in annotations
    assert "ledger" not in annotations
    assert "head" not in annotations
    assert "ledger_ref" not in annotations
