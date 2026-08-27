from __future__ import annotations

import argparse
import asyncio
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.legal.batch import cli
from polisyos.data_forge.domains.legal.batch.benchmark import (
    legal_search_benchmark_cases,
)
from polisyos.data_forge.domains.legal.batch.config import BatchConfig
from polisyos.data_forge.domains.legal.batch.pipeline import run_batch_pipeline
from polisyos.data_forge.read_api import legal as legal_read_api


def test_legal_benchmark_cases_are_published_as_authority_neutral_fixtures() -> None:
    direct = legal_search_benchmark_cases()
    published = legal_read_api.legal_search_benchmark_cases()

    assert direct == published
    assert len(direct) == 4
    assert {case.case_id for case in direct} == {
        "entry_force_amendment",
        "licensing_approvals",
        "reporting_compliance",
        "thresholds",
    }


def test_data_forge_cli_refuses_lex_semantic_authority(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="Lex-owned"):
        cli._cmd_benchmark(argparse.Namespace(output_dir=tmp_path))


def test_data_forge_pipeline_requires_and_consumes_injected_benchmark_runner(
    tmp_path,
) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"benchmark"}),
    )

    with pytest.raises(RuntimeError, match="injected Lex semantic benchmark runner"):
        asyncio.run(run_batch_pipeline(config))

    stats = asyncio.run(
        run_batch_pipeline(
            config,
            benchmark_runner=lambda _: SimpleNamespace(
                passed=False,
                metrics={"benchmark_normpack_ready_pct": 0.0},
                failed_checks=["benchmark_normpack_ready_pct"],
            ),
        )
    )

    assert stats.benchmark_passed is False
    assert stats.benchmark_failed_checks == ["benchmark_normpack_ready_pct"]
