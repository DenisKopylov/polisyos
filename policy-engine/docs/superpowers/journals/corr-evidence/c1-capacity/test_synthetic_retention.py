"""Constructed retention diagnostics must use a bounded, marked real owner chain."""

from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from types import ModuleType

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
checks = importlib.import_module(PREFIX + "test_pilot_analysis")


class SyntheticRetentionTests(unittest.TestCase):
    def owner(self) -> ModuleType:
        spec = importlib.util.find_spec(PREFIX + "synthetic_retention")
        if spec is None:
            raise AssertionError("bounded_actual_campaign_retention_diagnostic_missing")
        return importlib.import_module(PREFIX + "synthetic_retention")

    def test_complete_ordinal_frame_and_source_intake(self) -> None:
        owner = self.owner()
        for size in (100, 1000):
            frame = owner.frame_descriptor(size)
            checks._equal(frame["input_count"], size)
            checks._equal(frame["independent_sql_count"], size)
            checks._equal(frame["identity_sets_equal"] is True, True)
            checks._equal(frame["synthetic"] is True, True)
        with tempfile.TemporaryDirectory(dir=".tmp") as directory:
            root = Path(directory)
            declaration = owner.make_declaration(sizes=(2,))
            path = root / "declaration.json"
            owner.write_json(path, declaration)
            checks._equal(owner.admit(path, 2)["content_hash"], declaration["content_hash"])
            with (
                patch.object(owner, "execution_projection", return_value={"changed": True}),
                checks._refuses("retention_execution_source_changed"),
            ):
                owner.admit(path, 2)
            changed = {**declaration, "synthetic": False}
            changed.pop("content_hash")
            changed = owner.seal(changed)
            bad = root / "unmarked.json"
            owner.write_json(bad, changed)
            with checks._refuses("retention_requires_marked_synthetic"):
                owner.admit(bad, 2)

    def test_real_campaign_sdk_estimator_and_bounded_mock(self) -> None:
        owner = self.owner()
        with tempfile.TemporaryDirectory(dir=".tmp") as directory:
            root = Path(directory)
            declaration = owner.make_declaration(sizes=(2,))
            path = root / "declaration.json"
            owner.write_json(path, declaration)
            result = asyncio.run(owner.run_worker(path, 2, root / "worker"))
            checks._equal(result["synthetic"] is True, True)
            checks._equal(result["authority_granted"] is False, True)
            checks._equal(result["completed_work_count"], 2)
            checks._equal(result["mock_http_attempt_count"], 6)
            checks._equal(
                result["mock_phase_counts"],
                {
                    "screening": 2,
                    "extraction": 2,
                    "self_verification": 2,
                },
            )
            checks._equal(result["mock_peak_active"], 1)
            checks._equal(result["retained_mock_payloads"], 0)
            checkpoint = root / "worker" / "campaign" / "checkpoint.sqlite3"
            with sqlite3.connect(checkpoint) as con:
                checks._equal(
                    con.execute("SELECT COUNT(*) FROM works WHERE state='complete'").fetchone()[0],
                    2,
                )
            observations = root / "worker" / "provider" / "provider_attempts"
            checked = 0
            for source in observations.glob("*.json"):
                observation = json.loads(source.read_text())
                checks._equal(observation["synthetic"] is True, True)
                checks._equal(observation["authority_status"], "candidate_only")
                checks._equal(observation["local_prompt_token_estimate"] > 0, True)
                checked += 1
            checks._equal(checked, 6)
            checks._equal(result["provider_observation_count"], 6)
            checks._equal(result["extracted_work_count"], 2)

    def test_warm_progress_bins_exclude_startup_and_replay_cleanup(self) -> None:
        name = PREFIX + "retention_analysis"
        if importlib.util.find_spec(name) is None:
            raise AssertionError("retention_complete_warm_trace_analysis_missing")
        analysis = importlib.import_module(name)
        rows = [
            (0, 0.0, 100, 0, 0.0),
            (1, 1.0, 120, 1, 0.1),
            (2, 2.0, 130, 1, 0.2),
            (3, 3.0, 140, 2, 0.3),
            (4, 4.0, 150, 2, 0.4),
            (5, 5.0, 160, 3, 0.5),
            (6, 6.0, 0, 3, 0.5),
        ]
        result = analysis.windows(rows, input_count=3, campaign_end=5.5, logical_cpus=8)
        checks._equal(result["work_progress_warm"]["sample_count"], 4)
        checks._equal(result["work_progress_warm"]["rss_slope_bytes_per_second"], 10.0)
        checks._equal(result["work_progress_warm"]["first_completion_bin"]["rss_mean_bytes"], 125)
        checks._equal(result["work_progress_warm"]["last_completion_bin"]["rss_mean_bytes"], 145)
        checks._equal(result["campaign_warm_including_replay"]["sample_count"], 5)
        checks._equal(result["warm_through_exit"]["sample_count"], 6)
        checks._equal(result["startup_sample_count"], 1)

    def test_source_drift_at_worker_finish_is_not_attributed(self) -> None:
        owner = self.owner()
        with tempfile.TemporaryDirectory(dir=".tmp") as directory:
            root = Path(directory)
            declaration = owner.make_declaration(sizes=(1,))
            path = root / "declaration.json"
            owner.write_json(path, declaration)
            with (
                patch.object(
                    owner,
                    "execution_projection",
                    side_effect=[
                        declaration["execution_projection"],
                        {"changed_during_execution": True},
                    ],
                ),
                checks._refuses("retention_execution_source_changed"),
            ):
                asyncio.run(owner.run_worker(path, 1, root / "worker"))

    def test_duplicate_observation_body_cannot_hide_missing_identity(self) -> None:
        owner = self.owner()
        transport = importlib.import_module(
            "polisyos.data_forge.domains.academic.batch.reextraction_transport"
        )
        original = transport.SDKExtractionTransport.__aexit__

        async def corrupt_after_close(instance: object, *exc: object) -> None:
            await original(instance, *exc)
            paths = sorted((instance.root / "provider_attempts").glob("*.json"))
            checks._equal(len(paths), 3)
            paths[0].write_bytes(paths[1].read_bytes())

        with tempfile.TemporaryDirectory(dir=".tmp") as directory:
            root = Path(directory)
            declaration = owner.make_declaration(sizes=(1,))
            path = root / "declaration.json"
            owner.write_json(path, declaration)
            with (
                patch.object(transport.SDKExtractionTransport, "__aexit__", corrupt_after_close),
                checks._refuses("retention_mock_observation_identity_mismatch"),
            ):
                asyncio.run(owner.run_worker(path, 1, root / "worker"))


if __name__ == "__main__":
    unittest.main()
