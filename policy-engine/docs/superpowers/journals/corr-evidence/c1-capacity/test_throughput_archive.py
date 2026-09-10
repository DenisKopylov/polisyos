"""Marked run artifacts prove full throughput archive identity and secret refusal."""

from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
fixture = importlib.import_module(PREFIX + "test_pilot_analysis")


def _fixture(root: Path) -> tuple[Path, Path]:
    members = [
        {
            "work_id": f"synthetic:work:{n}",
            "abstract_content_hash": f"synthetic:input:{n}",
            "synthetic": True,
        }
        for n in range(2)
    ]
    plan = {
        "synthetic": True,
        "model_id": "synthetic:model",
        "selected_members": members,
        "levels": [{"concurrency": 1, "request_count": 2}],
        "full_pass_authorized": False,
    }
    declaration = root / "declaration.json"
    fixture.sealed(declaration, plan)
    plan_hash = fixture.digest(plan)
    level_root = root / "run" / "concurrency-1"
    level_root.mkdir(parents=True)
    con = sqlite3.connect(level_root / "checkpoint.sqlite")
    con.executescript("""CREATE TABLE work_items(work_id TEXT,ordinal INTEGER,status TEXT,
      error_kind TEXT,outcome_hash TEXT);
      CREATE TABLE artifact_provenance(synthetic INTEGER,authority_status TEXT);
      INSERT INTO artifact_provenance VALUES(1,'candidate_only');""")
    for n, member in enumerate(members):
        context = {
            "attempt_id": f"throughput-1-{n:03}",
            "work_id": member["work_id"],
            "phase": "extraction",
            "campaign_id": plan_hash,
            "input_hash": member["abstract_content_hash"],
            "synthetic": True,
        }
        observation = {
            "synthetic": True,
            "authority_status": "candidate_only",
            "context": context,
            "model_id": "synthetic:model",
            "reported_model_id": "synthetic:model",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        provider = level_root / "provider_attempts" / (context["attempt_id"] + ".json")
        fixture.write(provider, observation)
        outcome = {
            "synthetic": True,
            "authority_status": "candidate_only",
            "authority_granted": False,
            "declaration_hash": plan_hash,
            "work_id": member["work_id"],
            "input_hash": member["abstract_content_hash"],
            "attempt_id": context["attempt_id"],
            "status": "succeeded",
            "error_kind": None,
            "requested_model_id": "synthetic:model",
            "reported_model_id": "synthetic:model",
            "provider_observation_path": str(provider),
            "provider_observation_hash": fixture.digest(observation),
            "parsed_response": {"synthetic": True, "causal_claims": []},
        }
        fixture.write(level_root / "outcomes" / f"{n:03}.json", outcome)
        con.execute(
            "INSERT INTO work_items VALUES(?,?,?,?,?)",
            (member["work_id"], n, "succeeded", None, fixture.digest(outcome)),
        )
    con.commit()
    con.close()
    profile = root / "run" / "profile-1" / "samples.jsonl"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps({"synthetic": True, "elapsed_seconds": 1, "completed_work_count": 2}) + "\n"
    )
    level = {
        "synthetic": True,
        "concurrency": 1,
        "declaration_hash": plan_hash,
        "profile": {"synthetic": True, "sample_count": 1, "wall_seconds": 2},
    }
    level_path = root / "run" / "concurrency-1-report.json"
    fixture.write(level_path, level)
    report = {
        "schema_version": "corr.direct_extraction_throughput_report.v1",
        "synthetic": True,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "declaration_hash": plan_hash,
        "levels": [
            {"concurrency": 1, "report_path": str(level_path), "report_hash": fixture.digest(level)}
        ],
        "unrun_concurrencies": [],
        "full_pass_executed": False,
    }
    path = root / "run" / "throughput-report.json"
    fixture.write(path, report)
    return path, declaration


class ThroughputArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_archive")
        real = owner.runner.load_plan

        def resolve(path: Path) -> dict:
            value = owner.analysis._sealed(path)
            if value["synthetic"] is True:
                # Unit fixtures inject an already resolved plan; live integration below
                # executes the real committed declaration/frame owner without a bypass.
                return value
            return real(path)

        replacement = patch.object(owner.runner, "load_plan", side_effect=resolve)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_actual_committed_declaration_frame_reaches_archive_preflight(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_archive")
        source = Path(".tmp/corr-c1-capacity/throughput/deepseek/throughput-report.json")
        declaration = Path(
            "docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-deepseek-throughput-declaration.json"
        )

        class RefuseBeforeCopy:
            def check_payload(self, payload: object) -> None:
                del payload
                raise ValueError("archive_integration_preflight_reached")

        scratch = Path.cwd() / ".tmp"
        with tempfile.TemporaryDirectory(prefix="archive-live-integration-", dir=scratch) as name:
            destination = Path(name) / "never-written"
            with fixture._refuses("archive_integration_preflight_reached"):
                owner.archive_throughput(
                    source, declaration, destination, writer=RefuseBeforeCopy()
                )
            fixture._equal(destination.exists(), False)

    def test_complete_primary_byte_archive_and_trace_secret_refusal(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_archive")
        scratch = Path.cwd() / ".tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="throughput-archive-", dir=scratch) as name:
            root = Path(name)
            report, declaration = _fixture(root)
            destination = root / "archive"
            manifest = owner.archive_throughput(
                report, declaration, destination, writer=fixture._SyntheticWriter()
            )
            archived = {row["archive_path"] for row in manifest["primary_files"]}
            actual = {str(path) for path in destination.rglob("*") if path.is_file()}
            fixture._equal(archived, actual)
            fixture._equal(manifest["authority_granted"], False)
            fixture._equal(manifest["level_denominators"][0]["work_count"], 2)
            fixture._equal(any(path.endswith("samples.jsonl") for path in archived), True)
            fixture._equal(any(path.endswith("checkpoint.sqlite") for path in archived), True)
            for entry in manifest["primary_files"]:
                fixture._equal(
                    Path(entry["source_path"]).read_bytes(),
                    Path(entry["archive_path"]).read_bytes(),
                )
            trace = report.parent / "profile-1" / "samples.jsonl"
            trace.write_text(
                json.dumps(
                    {
                        "synthetic": True,
                        "elapsed_seconds": 1,
                        "completed_work_count": 2,
                        "synthetic_probe": "synthetic-sensitive-sentinel",
                    }
                )
                + "\n"
            )
            with fixture._refuses("synthetic_scan_refused"):
                owner.archive_throughput(
                    report, declaration, root / "refused", writer=fixture._SyntheticWriter()
                )
            fixture._equal((root / "refused").exists(), False)

    def test_missing_provider_or_novel_outcome_is_not_complete(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_archive")
        scratch = Path.cwd() / ".tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="throughput-archive-", dir=scratch) as name:
            root = Path(name)
            report, declaration = _fixture(root)
            extra = report.parent / "concurrency-1" / "provider_attempts" / "unbound.json"
            fixture.write(extra, {"synthetic": True})
            with fixture._refuses("throughput_archive_provider_identity_mismatch"):
                owner.archive_throughput(
                    report, declaration, root / "refused", writer=fixture._SyntheticWriter()
                )
            fixture._equal((root / "refused").exists(), False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
