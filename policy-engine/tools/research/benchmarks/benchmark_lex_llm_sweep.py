"""Compatibility wrapper for the Lex sweep benchmark entry point."""

from __future__ import annotations

from collections.abc import Sequence

from tools._lib.compat import expose_module, run_module_entrypoint

_TARGET = "tools.research.benchmarks.lex.benchmark_lex_llm_sweep"

expose_module(globals(), _TARGET)


def main(argv: Sequence[str] | None = None) -> int:
    return run_module_entrypoint(_TARGET, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
