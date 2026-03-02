from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.core_sources_ingest import run_core_sources_ingest
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector


def test_core_sources_ingest_populates_registry_tables(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "year": 2020,
                    "value": 0.5 if request.dataset_id.startswith("R") else 12345.0,
                }
            ]
        )
        return type("WBResult", (), {"data": df})()

    async def _fake_wvs_fetch(self, _handle, _request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "survey_year": 2020,
                    "wave": 7,
                    "value": 0.6,
                }
            ]
        )
        return type("WVSResult", (), {"data": df})()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(WVSConnector, "fetch", _fake_wvs_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
        stats = run_core_sources_ingest(config)
        assert stats.registry_datasets >= 4
        assert stats.variable_alignments > 0
        assert stats.observations > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            reg_count = con.execute("SELECT count(*) FROM ds_registry_datasets").fetchone()[0]
            align_count = con.execute("SELECT count(*) FROM ds_variable_alignments").fetchone()[0]
            obs_count = con.execute("SELECT count(*) FROM ds_observations").fetchone()[0]
        finally:
            con.close()

        assert reg_count >= 4
        assert align_count > 0
        assert obs_count > 0
