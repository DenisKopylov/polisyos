"""Run predeclared direct-extraction levels with bounded workers and observations.

Only the explicit CLI can dispatch real calls, after committed plan/frame and
successful model-contract checks. Synthetic tests use the same worker/SDK/owner
path with an explicitly marked mock transport. No result grants authority.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        SDKExtractionTransport,
    )

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
PROVIDER_BASE_URL = "https://api.proxy.gonka.gg/v1"
LEVELS = ((1, 12, 2400), (4, 24, 1500), (16, 48, 900), (32, 96, 900))


def _committed(path: Path) -> dict[str, Any]:
    common = importlib.import_module(PREFIX + "capacity_common")
    if path.is_absolute() or path.parent != common.EVIDENCE:
        raise ValueError("throughput_declaration_path_outside_lane")
    data = common.read_sealed(path)
    committed = subprocess.check_output(  # noqa: S603 - fixed read-only git invocation.
        [
            "/usr/bin/git",
            "show",
            "HEAD:policy-engine/" + path.as_posix(),
        ]
    )
    if path.read_bytes() != committed:
        raise ValueError("throughput_declaration_not_committed_before_call")
    if datetime.fromisoformat(data["declared_at"]) >= datetime.now(UTC):
        raise ValueError("throughput_declaration_not_before_call")
    return data


def load_plan(path: Path) -> dict[str, Any]:
    """Resolve the exact committed experiment and its admitted typed contract."""
    plan = _committed(path)
    admission = importlib.import_module(PREFIX + "throughput_admission")
    admission.require_admitted_execution(plan, Path.cwd())
    frame = _committed(Path(plan["frame_path"]))
    contract = _committed(Path(plan["contract_declaration_path"]))
    configuration = _committed(Path(plan["configuration_path"]))
    verdict = json.loads(Path(plan["contract_verdict_path"]).read_text())
    if (
        plan["schema_version"] != "corr.direct_extraction_throughput_declaration.v1"
        or plan["synthetic"] is not False
        or frame["synthetic"] is not False
        or plan["full_pass_authorized"] is not False
        or plan["frame_hash"] != frame["content_hash"]
        or plan["contract_declaration_hash"] != contract["content_hash"]
        or plan["configuration_hash"] != configuration["content_hash"]
        or any(
            plan[key] != configuration[key]
            for key in (
                "model_id",
                "base_url",
                "max_completion_tokens",
                "timeout_seconds",
                "metadata_observation",
                "metadata_observation_hash",
                "live_pricing_usd_per_token",
                "price_observed_at",
                "response_format",
                "temperature",
                "transport",
            )
        )
        or verdict.get("declaration_hash") != contract["content_hash"]
        or verdict.get("contract_satisfied") is not True
        or verdict.get("synthetic") is not False
        or verdict.get("model_id") != plan["model_id"]
        or contract["model_id"] != plan["model_id"]
        or plan["base_url"] != PROVIDER_BASE_URL
        or plan["response_codec"]
        != ("polisyos.data_forge.domains.academic.batch.article_extractor._parse_json_object")
        or plan["transport_observation_epoch"] != "policyos.academic.extraction_attempt.v3"
        or [(r["concurrency"], r["request_count"], r["max_wall_seconds"]) for r in plan["levels"]]
        != list(LEVELS)
        or plan["max_total_http_attempts"] != 180
        or plan["retry_limit"] != 0
        or plan["sdk_automatic_retries"] != 0
        or plan["transport_attempts_per_request"] != 1
        or plan["max_completion_tokens"] != 8192
        or plan["timeout_seconds"] != 180
    ):
        raise ValueError("throughput_declared_execution_contract_mismatch")
    members = frame["selected_members"]
    ids = {r["work_id"] for r in members}
    if (
        len(members) != 180
        or len(ids) != 180
        or ids & set(frame["excluded_frozen_pilot_ids"])
        or any(r["synthetic"] is not False for r in members)
    ):
        raise ValueError("throughput_declared_selection_mismatch")
    offset = 0
    for _, count, _ in LEVELS:
        if [
            sum(r["stratum"] == tier for r in members[offset : offset + count]) for tier in range(3)
        ] != [count // 3] * 3:
            raise ValueError("throughput_declared_block_mismatch")
        offset += count
    return {
        **plan,
        "selected_members": members,
        "source_path": frame["source_path"],
        "resolved_frame_hash": frame["content_hash"],
    }


def level_members(plan: dict[str, Any], index: int) -> list[dict[str, Any]]:
    """Resolve the declared disjoint block without reusing lower-level inputs."""
    start = sum(level["request_count"] for level in plan["levels"][:index])
    count = plan["levels"][index]["request_count"]
    return plan["selected_members"][start : start + count]


def completed_count(path: Path) -> int:
    """Reconcile the full scalar checkpoint denominator for telemetry."""
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1) as con:
        count = con.execute(
            "SELECT count(*) FROM work_items WHERE status IN ('succeeded','failed')"
        ).fetchone()[0]
        rows = con.execute("SELECT work_id,status FROM work_items").fetchall()
    if len(rows) != len({row[0] for row in rows}):
        raise ValueError("throughput_checkpoint_identity_ambiguous")
    independent = len({key for key, status in rows if status in {"succeeded", "failed"}})
    if count != independent:
        raise ValueError("throughput_completion_count_mismatch")
    return count


def initialize_checkpoint(
    path: Path,
    members: list[dict[str, Any]],
    *,
    synthetic: bool,
) -> sqlite3.Connection:
    """Create the single complete scalar checkpoint with its own provenance."""
    if path.exists() or type(synthetic) is not bool:
        raise ValueError("throughput_checkpoint_creation_not_admitted")
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("""CREATE TABLE artifact_provenance(
        synthetic BOOLEAN NOT NULL CHECK(synthetic IN (0,1)),authority_status TEXT NOT NULL)
    """)
    con.execute("INSERT INTO artifact_provenance VALUES(?,'candidate_only')", (synthetic,))
    con.execute("""CREATE TABLE work_items(
        work_id TEXT PRIMARY KEY, ordinal INTEGER UNIQUE, status TEXT, started_at REAL,
        finished_at REAL, latency_seconds REAL, error_kind TEXT, retryable INTEGER,
        prompt_tokens INTEGER, completion_tokens INTEGER, outcome_hash TEXT)
    """)
    con.executemany(
        "INSERT INTO work_items(work_id,ordinal,status) VALUES(?,?,'pending')",
        [(m["work_id"], i) for i, m in enumerate(members)],
    )
    con.commit()
    return con


def read_level_rows(output: Path, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconcile all terminal outcome files against the complete SQL identity set."""
    with sqlite3.connect(
        (output / "checkpoint.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    ) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(row) for row in con.execute("SELECT * FROM work_items ORDER BY ordinal")]
    if {row["work_id"] for row in rows} != {row["work_id"] for row in members} or len(rows) != len(
        members
    ):
        raise ValueError("throughput_checkpoint_declared_identity_mismatch")
    sql = {
        (row["work_id"], row["status"], row["error_kind"], row["outcome_hash"])
        for row in rows
        if row["status"] in {"succeeded", "failed"}
    }
    files = set()
    count = 0
    declaration = importlib.import_module(PREFIX + "throughput_declaration")
    for path in (output / "outcomes").glob("*.json"):
        packet = json.loads(path.read_text())
        files.add(
            (packet["work_id"], packet["status"], packet["error_kind"], declaration.digest(packet))
        )
        count += 1
    if sql != files or len(files) != count:
        raise ValueError("throughput_outcome_checkpoint_reconciliation_failed")
    return rows


async def _run_level(
    plan: dict[str, Any],
    index: int,
    output: Path,
    transport: SDKExtractionTransport,
) -> None:
    """Keep at most concurrency source/parsed/typed owner objects alive at once."""
    declaration = importlib.import_module(PREFIX + "throughput_declaration")
    probe = importlib.import_module(PREFIX + "contract_probe")
    from polisyos.data_forge.domains.academic.batch.article_extractor import (
        ExtractorStats,
        PolicyArticleExtractor,
    )
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        ExtractionRequestError,
    )
    from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer
    from polisyos.ir import ArticleExtractionResult

    if bool(plan["synthetic"]) != bool(transport.synthetic):
        raise ValueError("throughput_synthetic_transport_scope_mismatch")
    transport.check_payload(plan)
    level = plan["levels"][index]
    members = level_members(plan, index)
    output.mkdir(parents=True, exist_ok=False)
    con = initialize_checkpoint(output / "checkpoint.sqlite", members, synthetic=plan["synthetic"])
    cursor = iter(enumerate(members))
    deadline = time.monotonic() + level["max_wall_seconds"]

    async def worker() -> None:
        for ordinal, member in cursor:
            if time.monotonic() >= deadline:
                return
            work = declaration.read_selected_work(Path(plan["source_path"]), member)
            attempt_id = f"throughput-{level['concurrency']}-{ordinal:03}"
            started = time.monotonic()
            with con:
                con.execute(
                    "UPDATE work_items SET status='running',started_at=? WHERE work_id=?",
                    (started, member["work_id"]),
                )
            client = probe._ObservedClient(
                transport.bind(
                    {
                        "attempt_id": attempt_id,
                        "work_id": member["work_id"],
                        "phase": "extraction",
                        "campaign_id": plan["content_hash"],
                        "input_hash": member["abstract_content_hash"],
                        "synthetic": plan["synthetic"],
                    }
                )
            )
            owner = PolicyArticleExtractor(
                screening_model=plan["model_id"],
                extraction_model=plan["model_id"],
                max_concurrent=1,
                canonizer=VariableCanonizer(),
                gonka_client=client,
                fulltext_timeout_seconds=3,
                cache_path=output / "unused-cache.jsonl",
                preserve_source_presence=True,
            )
            result = None
            error_kind = None
            retryable = False
            try:
                result = await owner._extract(
                    work, work["abstract"], "abstract_fallback", ExtractorStats()
                )
                if not isinstance(result, ArticleExtractionResult):
                    error_kind = "contract_violation"
            except ExtractionRequestError as exc:
                error_kind, retryable = exc.kind, exc.retryable
            finished = time.monotonic()
            # Provider usage on failed/truncated replies still contributes to cost.
            observation_path = output / "provider_attempts" / (attempt_id + ".json")
            observation = json.loads(observation_path.read_text())
            usage = observation.get("usage") or {}
            status = "succeeded" if error_kind is None else "failed"
            packet = {
                "schema_version": "corr.direct_extraction_outcome.v1",
                "synthetic": plan["synthetic"],
                "authority_status": "candidate_only",
                "authority_granted": False,
                "declaration_hash": plan["content_hash"],
                "work_id": member["work_id"],
                "input_hash": member["abstract_content_hash"],
                "attempt_id": attempt_id,
                "status": status,
                "error_kind": error_kind,
                "retryable": retryable,
                "actual_http_attempts": client.count,
                "requested_model_id": plan["model_id"],
                "reported_model_id": observation.get("reported_model_id"),
                "provider_observation_path": str(observation_path),
                "provider_observation_hash": declaration.digest(observation),
                "typed_result_hash": declaration.digest(result.model_dump(mode="json"))
                if result
                else None,
                "parsed_response": client.response,
            }
            transport.safe_write_json(output / "outcomes" / f"{ordinal:03}.json", packet)
            values = (
                status,
                finished,
                finished - started,
                error_kind,
                int(retryable),
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                declaration.digest(packet),
                member["work_id"],
            )
            transport.check_payload(values)
            with con:
                con.execute(
                    """UPDATE work_items SET status=?,finished_at=?,latency_seconds=?,
                    error_kind=?,retryable=?,prompt_tokens=?,completion_tokens=?,outcome_hash=?
                    WHERE work_id=?""",
                    values,
                )
            # The next iteration replaces these objects; no corpus-sized result list.
            del owner, result, client, work, packet, observation

    try:
        async with asyncio.timeout(level["max_wall_seconds"]):
            async with asyncio.TaskGroup() as group:
                for _ in range(min(level["concurrency"], len(members))):
                    group.create_task(worker())
    finally:
        con.close()


async def run_synthetic_level(
    plan: dict[str, Any],
    index: int,
    output: Path,
    transport: SDKExtractionTransport,
) -> None:
    """Expose the actual path only for explicitly marked synthetic SDK fixtures."""
    if plan.get("synthetic") is not True or transport.synthetic is not True:
        raise ValueError("throughput_synthetic_entrypoint_refuses_live_transport")
    await _run_level(plan, index, output, transport)


async def _live_worker(path: Path, index: int, output: Path) -> None:
    plan = load_plan(path)  # Recheck immediately before any real dispatch.
    common = importlib.import_module(PREFIX + "capacity_common")
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        SDKExtractionTransport,
    )

    async with SDKExtractionTransport(
        api_key=common.load_credential(),
        base_url=plan["base_url"],
        model_id=plan["model_id"],
        output_root=output,
        timeout_seconds=plan["timeout_seconds"],
        max_completion_tokens=plan["max_completion_tokens"],
        prompt_estimator=common.local_estimator,
    ) as transport:
        await _run_level(plan, index, output, transport)


def _sample_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def profile_experiment(path: Path, output: Path) -> dict[str, Any]:
    """Run levels serially, preserving current denominators before applying stops."""
    plan = load_plan(path)
    common = importlib.import_module(PREFIX + "capacity_common")
    analysis = importlib.import_module(PREFIX + "throughput_analysis")
    telemetry = importlib.import_module(PREFIX + "process_telemetry")
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    writer = SafeJsonWriter(common.load_credential())
    output.mkdir(parents=True, exist_ok=False)
    previous = None
    results = []  # Bounded scalar summaries only, never extracted records.
    for index, level in enumerate(plan["levels"]):
        level_root = output / f"concurrency-{level['concurrency']}"
        profile_root = output / f"profile-{level['concurrency']}"
        profile = telemetry.profile_module(
            PREFIX + "throughput_runner",
            [str(path), "--output", str(level_root), "--worker-level", str(index)],
            cwd=Path.cwd(),
            output_root=profile_root,
            limits=telemetry.ProfileLimits(
                max_wall_seconds=level["max_wall_seconds"], **plan["resource_caps"]
            ),
            completion_reader=lambda root=level_root: completed_count(root / "checkpoint.sqlite"),
            synthetic=False,
        )
        metadata_error = None
        try:
            rows = read_level_rows(level_root, level_members(plan, index))
        except (OSError, ValueError, sqlite3.Error, KeyError):
            rows = []
            metadata_error = "ambiguous_checkpoint_or_outcome_reconciliation"
        origin = profile["monotonic_started_seconds"]
        for row in rows:
            for key in ("started_at", "finished_at"):
                if row[key] is not None:
                    row[key] -= origin
        result = analysis.analyse_level(
            rows,
            _sample_rows(profile_root / "samples.jsonl"),
            declared_count=level["request_count"],
            synthetic=False,
            profile=profile,
        )
        result.update(
            concurrency=level["concurrency"],
            declaration_hash=plan["content_hash"],
            metadata_error=metadata_error,
        )
        if metadata_error is not None:
            # Unreadable is not an observed zero, even when no metadata can be admitted.
            for key in (
                "observed_identity_count",
                "terminal_count",
                "typed_success_count",
                "error_count",
                "missing_terminal_count",
                "complete_rate",
                "typed_success_rate",
                "error_rate",
                "error_kinds",
                "latency_seconds_all_terminal",
                "latency_seconds_typed_success",
                "known_usage_count",
                "unknown_usage_count",
                "observed_prompt_tokens",
                "observed_completion_tokens",
            ):
                result[key] = None
        rates = plan["live_pricing_usd_per_token"]
        result["observed_token_cost_usd_lower_bound"] = (
            (
                result["observed_prompt_tokens"] * rates["input"]
                + result["observed_completion_tokens"] * rates["output"]
            )
            if metadata_error is None
            else None
        )
        result["cost_complete"] = (
            result["unknown_usage_count"] == 0 and result["status"] == "measured"
        )
        decision = analysis.stop_decision(result, previous)
        result["stop_decision"] = decision
        summary_path = output / f"concurrency-{level['concurrency']}-report.json"
        writer(summary_path, result)
        results.append(
            {
                "concurrency": level["concurrency"],
                "status": result["status"],
                "report_path": str(summary_path),
                "report_hash": common.digest(result),
                "stop_decision": decision,
            }
        )
        if decision["stop_higher_levels"]:
            break
        previous = result
    report = {
        "schema_version": "corr.direct_extraction_throughput_report.v1",
        "synthetic": False,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "declaration_hash": plan["content_hash"],
        "levels": results,
        "unrun_concurrencies": [level["concurrency"] for level in plan["levels"][len(results) :]],
        "full_pass_executed": False,
        "scope_limitation": plan["scope_limitation"],
        "comparison_limitation": plan["comparison_limitation"],
        "correctness_claim": None,
    }
    writer(output / "throughput-report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("declaration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-level", type=int)
    args = parser.parse_args()
    if args.worker_level is None:
        profile_experiment(args.declaration, args.output)
    else:
        if args.worker_level not in range(4):
            raise ValueError("throughput_level_outside_declaration")
        asyncio.run(_live_worker(args.declaration, args.worker_level, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
