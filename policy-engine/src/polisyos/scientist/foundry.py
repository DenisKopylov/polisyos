from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import CompileRequest, CompileResult, ExecuteRequest, ExecuteResult
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.scientist.engine.context import FoundryPort


class DefaultFoundryPort(FoundryPort):
    """Default Foundry adapter for Scientist engine (E1.7)."""

    def compile(self, store: FileSystemCAS, request: CompileRequest) -> CompileResult:
        return compile_foundry(store, request)

    def execute(self, store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
        return execute_foundry(store, request)


__all__ = ["DefaultFoundryPort"]
