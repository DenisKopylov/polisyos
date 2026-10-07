"""Remove only current spec-binding admission by restoring exact code680 read-union.

The actual checker reader, current receipt markers, grammar helpers, main caller
and fixture inputs stay unchanged. This is a static-diagnostic counterfactual,
not a runtime node or scientific-authority experiment.
"""

from __future__ import annotations

from tools.quality.diagnostics import check_state_reads as checker

_LEGACY_EXTRACT_SPEC_READS = 'def _extract_spec_reads(tree: ast.Module) -> tuple[set[str], set[str]]:\n    exact: set[str] = set()\n    prefix: set[str] = set()\n    for parsed in ast.walk(tree):\n        if not isinstance(parsed, (ast.Assign, ast.AnnAssign)):\n            continue\n        targets = [parsed.target] if isinstance(parsed, ast.AnnAssign) else parsed.targets\n        if not any(isinstance(target, ast.Name) and target.id == "_SPEC" for target in targets):\n            continue\n        if not (\n            isinstance(parsed.value, ast.Call)\n            and isinstance(parsed.value.func, ast.Name)\n            and parsed.value.func.id in _NODE_SPEC_CONSTRUCTORS\n        ):\n            raise ValueError("unsupported_spec_constructor")\n        if parsed.value.args or any(kw.arg is None for kw in parsed.value.keywords):\n            raise ValueError("unsupported_spec_arguments")\n        for kw in parsed.value.keywords:\n            if kw.arg != "state_reads":\n                continue\n            if not isinstance(kw.value, (ast.List, ast.Tuple)):\n                raise ValueError("unsupported_state_reads_expression")\n            for entry in kw.value.elts:\n                path = _read_value_to_path(entry)\n                if not path:\n                    raise ValueError("unsupported_state_reads_entry")\n                exact.add(path)\n                prefix.add(path.split(".", 1)[0])\n    return exact, prefix'


def pytest_configure(config):
    namespace = {}
    exec(
        compile(_LEGACY_EXTRACT_SPEC_READS, "<exact680_spec_union_removal>", "exec"),
        checker.__dict__,
        namespace,
    )
    checker._extract_spec_reads = namespace["_extract_spec_reads"]
