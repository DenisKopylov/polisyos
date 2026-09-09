"""Marked synthetic witnesses for the bounded direct-extraction experiment."""

from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _fixture(root: Path) -> tuple[Path, dict]:
    import duckdb

    source = root / "synthetic.duckdb"
    with duckdb.connect(str(source)) as con:
        con.execute("CREATE TABLE ac_works(id VARCHAR, abstract VARCHAR, title VARCHAR)")
        con.execute("CREATE TABLE artifact_provenance(synthetic BOOLEAN CHECK(synthetic))")
        con.execute("INSERT INTO artifact_provenance VALUES(TRUE)")
        con.executemany(
            "INSERT INTO ac_works VALUES (?,?,?)",
            [
                (f"synthetic:{i:03}", "synthetic input " + "x" * (i + 1), "synthetic title")
                for i in range(240)
            ],
        )
    old = {
        "selected_members": [{"work_id": f"synthetic:{i:03}"} for i in (0, 1, 80, 81, 160, 161)],
        "synthetic": True,
    }
    return source, old


class ThroughputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path.cwd() / ".tmp"
        self.scratch.mkdir(exist_ok=True)

    def test_checkpoint_artifact_has_own_synthetic_provenance(self) -> None:
        runner = importlib.import_module(PREFIX + "throughput_runner")
        with tempfile.TemporaryDirectory(
            prefix="throughput-provenance-", dir=self.scratch
        ) as temporary:
            output = Path(temporary) / "checkpoint.sqlite"
            con = runner.initialize_checkpoint(
                output, [{"work_id": "synthetic:one"}], synthetic=True
            )
            try:
                provenance = con.execute(
                    "SELECT synthetic,authority_status FROM artifact_provenance"
                ).fetchall()
                _check(
                    provenance == [(1, "candidate_only")], "checkpoint lacks own synthetic marker"
                )
            finally:
                con.close()

    def test_actual_marked_process_memory_growth_and_origin(self) -> None:
        telemetry = importlib.import_module(PREFIX + "process_telemetry")
        runner = importlib.import_module(PREFIX + "throughput_runner")
        analysis = importlib.import_module(PREFIX + "throughput_analysis")
        with tempfile.TemporaryDirectory(
            prefix="throughput-memory-", dir=self.scratch
        ) as temporary:
            root = Path(temporary)
            checkpoint = root / "checkpoint.sqlite"
            profile = telemetry.profile_module(
                PREFIX + "throughput_memory_fixture",
                [str(checkpoint)],
                cwd=Path.cwd(),
                output_root=root / "profile",
                synthetic=True,
                completion_reader=lambda: runner.completed_count(checkpoint),
                limits=telemetry.ProfileLimits(max_wall_seconds=12),
            )
            _check(profile["status"] == "completed", "synthetic memory worker failed")
            _check(profile["monotonic_started_seconds"] > 0, "clock origin unavailable")
            _check(
                profile["hardware_observation"]["logical_cpu_count"] > 0,
                "CPU capacity denominator not measured",
            )
            _check(
                profile["hardware_observation"]["physical_memory_bytes"] > 0,
                "physical memory denominator not measured",
            )
            with sqlite3.connect(checkpoint) as con:
                con.row_factory = sqlite3.Row
                rows = [dict(row) for row in con.execute("SELECT * FROM work_items")]
                _check(
                    con.execute("SELECT synthetic FROM provenance").fetchall()[0][0] == 1,
                    "synthetic checkpoint missing own provenance",
                )
            for row in rows:
                for key in ("started_at", "finished_at"):
                    row[key] -= profile["monotonic_started_seconds"]
            samples = [
                json.loads(line)
                for line in (root / "profile/samples.jsonl").read_text().splitlines()
            ]
            result = analysis.analyse_level(
                rows, samples, declared_count=12, synthetic=True, profile=profile
            )
            _check(result["status"] == "measured", "actual memory denominator not complete")
            slope = result["memory"]["rss_slope_bytes_per_completed"]
            _check(
                slope is not None and slope > 3 * 1024**2,
                "deliberate retained-memory growth disappeared from actual analysis",
            )
            _check(
                result["memory"]["rss_slope_bytes_per_second"] > 0,
                "actual memory/time growth disappeared",
            )
            print(  # noqa: T201 - retained actual process measurement witness.
                json.dumps(
                    {
                        "synthetic": True,
                        "actual_memory_witness": result["memory"],
                        "hardware_observation": profile["hardware_observation"],
                        "warm_observed_cpu_per_wall": result["warm_observed_cpu_per_wall"],
                    }
                )
            )

    def test_complete_input_only_frame_disjoint_interleaved_and_fake_identity(self) -> None:
        declaration = importlib.import_module(PREFIX + "throughput_declaration")
        runner = importlib.import_module(PREFIX + "throughput_runner")
        with tempfile.TemporaryDirectory(
            prefix="throughput-synthetic-", dir=self.scratch
        ) as temporary:
            root = Path(temporary)
            source, old = _fixture(root)
            frame = declaration.enumerate_frame(source, old, synthetic=True)
            selected = frame["selected_members"]
            _check(frame["synthetic"] is True, "synthetic frame lost own provenance")
            _check(frame["eligible_count"] == 240, "complete frame denominator was narrowed")
            _check(frame["independent_sql_eligible_count"] == 240, "independent count missing")
            _check(
                len(selected) == len({r["work_id"] for r in selected}) == 180,
                "selection is not complete and unique",
            )
            _check(
                not (
                    {r["work_id"] for r in selected}
                    & {r["work_id"] for r in old["selected_members"]}
                ),
                "throughput selection overlaps frozen pilot",
            )
            offset = 0
            blocks = []
            block_plan = {
                "selected_members": selected,
                "levels": [{"request_count": n} for n in (12, 24, 48, 96)],
            }
            for index, count in enumerate((12, 24, 48, 96)):
                block = runner.level_members(block_plan, index)
                _check(block == selected[offset : offset + count], "runtime block offset changed")
                _check(
                    [sum(r["stratum"] == tier for r in block) for tier in range(3)]
                    == [count // 3] * 3,
                    "declared block is not interleaved across complete strata",
                )
                blocks.append({row["work_id"] for row in block})
                offset += count
            _check(
                sum(map(len, blocks)) == len(set.union(*blocks)) == 180,
                "level blocks repeat inputs and can confound caching with throughput",
            )
            _check(
                frame == declaration.enumerate_frame(source, old, synthetic=True),
                "input-only selection changed without input changes",
            )
            bad = [{**selected[0], "abstract_content_hash": "sha256:" + "0" * 64}]
            try:
                declaration.read_selected_work(source, bad[0])
            except ValueError as exc:
                _check(str(exc) == "throughput_selected_input_binding_mismatch", "wrong refusal")
            else:
                raise AssertionError("fake source binding admitted")

    def test_memory_trend_real_analysis_and_full_failed_denominator(self) -> None:
        analysis = importlib.import_module(PREFIX + "throughput_analysis")
        rows = [
            {
                "work_id": f"synthetic:{i}",
                "status": "succeeded" if i < 9 else "failed",
                "latency_seconds": float(i + 1),
                "error_kind": None if i < 9 else "malformed_output",
                "started_at": float(i),
                "finished_at": float(i + 1),
                "prompt_tokens": 10,
                "completion_tokens": 20,
            }
            for i in range(12)
        ]
        samples = [
            {
                "synthetic": True,
                "elapsed_seconds": float(i),
                "summed_rss_bytes": 1_000_000 + i * 65_536,
                "completed_work_count": i,
                "measurement_status": "measured",
            }
            for i in range(13)
        ]
        result = analysis.analyse_level(rows, samples, declared_count=12, synthetic=True)
        _check(result["declared_count"] == result["terminal_count"] == 12, "failed cases lost")
        _check(
            result["typed_success_count"] == 9 and result["error_rate"] == 0.25,
            "errors were removed from decisive denominator",
        )
        _check(
            result["memory"]["rss_slope_bytes_per_completed"] == 65_536,
            "actual RSS/completion growth was not measured",
        )
        _check(
            result["memory"]["rss_slope_bytes_per_second"] == 65_536,
            "actual RSS/time growth was not measured",
        )
        _check(
            analysis.stop_decision(result, None)["stop_higher_levels"] is True,
            "high error fraction did not stop higher levels",
        )
        partial = analysis.analyse_level(rows[:9], samples, declared_count=12, synthetic=True)
        _check(partial["status"] == "not_established", "partial level was credited as knee")
        _check(
            analysis.stop_decision(partial, None)["reason"] == "incomplete_level",
            "partial denominator did not stop progression",
        )
        previous = {**result, "error_rate": 0.0, "typed_success_per_second": 1.0}
        current = {**previous, "typed_success_per_second": 1.19}
        _check(
            analysis.stop_decision(current, previous)["reason"] == "throughput_plateau",
            "predeclared plateau threshold not enforced",
        )

    def test_marked_sdk_real_owner_bounded_queue_errors_and_candidate_only(self) -> None:
        runner = importlib.import_module(PREFIX + "throughput_runner")
        declaration = importlib.import_module(PREFIX + "throughput_declaration")
        import httpx

        from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
            SDKExtractionTransport,
        )

        async def witness(root: Path) -> None:
            source, old = _fixture(root)
            frame = declaration.enumerate_frame(source, old, synthetic=True)
            plan = {
                **frame,
                "content_hash": "sha256:" + "a" * 64,
                "model_id": "MiniMaxAI/MiniMax-M2.7",
                "source_path": str(source),
                "levels": [{"concurrency": 4, "request_count": 12, "max_wall_seconds": 120}],
                "max_completion_tokens": 8192,
                "timeout_seconds": 180,
                "full_pass_authorized": False,
                "authority_status": "candidate_only",
            }
            calls = active = peak = 0

            async def reply(request: httpx.Request) -> httpx.Response:
                nonlocal calls, active, peak
                calls += 1
                ordinal = calls
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.01)
                active -= 1
                body = {} if ordinal == 1 else {"causal_claims": []}
                return httpx.Response(
                    200,
                    json={
                        "id": "synthetic",
                        "object": "chat.completion",
                        "created": 0,
                        "model": plan["model_id"],
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": json.dumps(body)},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                    },
                )

            output = root / "level"
            async with SDKExtractionTransport(
                api_key="synthetic-credential-not-a-real-key",
                base_url=runner.PROVIDER_BASE_URL,
                model_id=plan["model_id"],
                output_root=output,
                timeout_seconds=180,
                max_completion_tokens=8192,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(reply)),
            ) as transport:
                await runner.run_synthetic_level(plan, 0, output, transport)
            rows = runner.read_level_rows(output, plan["selected_members"][:12])
            _check(calls == 12 and 1 < peak <= 4, "bounded worker count or request cap violated")
            _check(
                len(rows) == 12 and sum(r["status"] == "succeeded" for r in rows) == 11,
                "actual typed owner did not preserve valid/invalid distinction",
            )
            _check(
                sum(r["error_kind"] == "contract_violation" for r in rows) == 1,
                "malformed shape was normalized into a vacuous typed success",
            )
            for path in sorted((output / "outcomes").glob("*.json")):
                packet = json.loads(path.read_text())
                _check(packet["synthetic"] is True, "synthetic result lost own marker")
                _check(
                    packet["authority_status"] == "candidate_only"
                    and packet["authority_granted"] is False,
                    "synthetic model output was granted authority",
                )
            _check(
                runner.completed_count(output / "checkpoint.sqlite") == 12,
                "profiler completed count differs from complete checkpoint",
            )
            changed_path = next((output / "outcomes").glob("*.json"))
            corrupted = json.loads(changed_path.read_text())
            corrupted["typed_result_hash"] = "sha256:" + "0" * 64
            changed_path.write_text(json.dumps(corrupted))
            try:
                runner.read_level_rows(output, plan["selected_members"][:12])
            except ValueError as exc:
                _check(
                    str(exc) == "throughput_outcome_checkpoint_reconciliation_failed",
                    "persisted corruption failed for a different reason",
                )
            else:
                raise AssertionError("changed persisted outcome retained green result")

        with tempfile.TemporaryDirectory(
            prefix="throughput-synthetic-", dir=self.scratch
        ) as temporary:
            asyncio.run(witness(Path(temporary)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
