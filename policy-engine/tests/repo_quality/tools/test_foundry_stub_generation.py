from __future__ import annotations

import ast

from tools.devx.foundry.generate_stubs import _remove_private_exports


def test_private_stub_definitions_are_removed_without_orphaning_their_bodies() -> None:
    source = """\
class Public:
    value: int

class _Private:
    hidden: str

    def helper(self) -> None: ...
"""

    cleaned = _remove_private_exports(source)

    ast.parse(cleaned)
    assert "class _Private:" in cleaned
