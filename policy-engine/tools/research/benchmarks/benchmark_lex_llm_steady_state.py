"""Compatibility wrapper for the Lex steady-state benchmark entry point."""

from __future__ import annotations

from collections.abc import Sequence

from tools.lib.compat import expose_module, run_module_entrypoint

_TARGET = "tools.research.benchmarks.lex.benchmark_lex_llm_steady_state"

expose_module(globals(), _TARGET)


def main(argv: Sequence[str] | None = None) -> int:
    return run_module_entrypoint(_TARGET, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
