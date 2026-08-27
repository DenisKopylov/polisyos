"""Compatibility access to authority-neutral legal benchmark fixtures.

The fixtures are Data Forge output. Lex owns semantic readiness and Scientist
owns the retrieval diagnostic that consumes them.
"""

from polisyos.data_forge.domains.legal.batch.benchmark_fixtures import (
    LegalSearchBenchmarkCase,
    legal_search_benchmark_cases,
)

__all__ = [
    "LegalSearchBenchmarkCase",
    "legal_search_benchmark_cases",
]
