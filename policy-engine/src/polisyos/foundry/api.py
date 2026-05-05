"""Stable Foundry public facade for compile and execute entrypoints."""

from __future__ import annotations

from polisyos.foundry.compile.api import compile
from polisyos.foundry.execute.api import execute

compile_program = compile

__all__ = ["compile", "compile_program", "execute"]
