from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.academic.batch import cli

if TYPE_CHECKING:
    import argparse


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = cli._build_parser()
    return parser.parse_args(argv)


def test_build_config_accepts_track_b_and_track_c_flags(tmp_path) -> None:
    args = _parse_args(
        [
            "run",
            "--snapshot-root",
            str(tmp_path / "snap"),
            "--track-b-enabled",
            "--track-c-enabled",
            "--paper-classification-model",
            "classifier-model",
            "--track-b-extraction-model",
            "track-b-model",
            "--track-c-extraction-model",
            "track-c-model",
            "--fulltext-metadata-resolver-order",
            "crossref,semanticscholar",
            "--fulltext-shared-cache-dir",
            str(tmp_path / "shared-cache"),
            "--fulltext-cache-ttl-days",
            "14",
            "--fulltext-semantic-scholar-api-key",
            "s2-key",
            "--transport-target-context-id",
            "UA",
            "--transport-target-country-codes",
            "UA,PL",
            "--transport-target-time-period",
            "2020-2024",
        ]
    )

    config = cli._build_config(args, stages=frozenset({"resolve_extract"}))

    assert config.track_b_enabled is True
    assert config.track_c_enabled is True
    assert config.paper_classification_model == "classifier-model"
    assert config.track_b_extraction_model == "track-b-model"
    assert config.track_c_extraction_model == "track-c-model"
    assert config.fulltext_metadata_resolver_order == ("crossref", "semanticscholar")
    assert config.fulltext_shared_cache_dir == tmp_path / "shared-cache"
    assert config.fulltext_cache_ttl_days == 14
    assert config.fulltext_semantic_scholar_api_key == "s2-key"
    assert config.transport_target_context_id == "UA"
    assert config.transport_target_country_codes == ("UA", "PL")
    assert config.transport_target_time_period == "2020-2024"


def test_parse_stages_supports_transport_score_alias() -> None:
    stages = cli._parse_stages("graph-index,transport-score")

    assert stages == frozenset({"graph_index", "transport_score"})


def test_parse_stages_supports_sota_stage_aliases() -> None:
    stages = cli._parse_stages("doc-normalize,claim-extract,conflict-resolve,benchmark-run")

    assert stages == frozenset({"doc_normalize", "claim_extract", "conflict_resolve", "benchmark"})


def test_transport_score_command_dispatches(tmp_path, monkeypatch, capsys) -> None:
    args = _parse_args(
        [
            "transport-score",
            "--snapshot-root",
            str(tmp_path / "snap"),
        ]
    )

    def _fake_run_transport_score(config):  # type: ignore[no-untyped-def]
        assert config.snapshot_root == tmp_path / "snap"
        return {"edges_scored": 2, "moderators_applied": 1, "profiles_built": 3}

    monkeypatch.setattr(
        "polisyos.data_forge.domains.academic.batch.transport_score.run_transport_score",
        _fake_run_transport_score,
    )

    asyncio.run(cli._run_stage(args, "transport-score"))
    out = capsys.readouterr().out

    assert '"edges_scored": 2' in out
    assert '"profiles_built": 3' in out
