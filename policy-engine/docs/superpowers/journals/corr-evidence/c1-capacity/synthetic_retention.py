"""Declared finite campaign memory diagnostic through the real SDK and HTTP mock.

No provider credentials are read and no socket transport is constructed. The
generated source and responses are synthetic candidates. This measures only the
finite existing campaign/SDK/estimator chain, excluding graph finalization.
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import hashlib
import importlib
import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    import httpx

    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
        CampaignCallContext,
        PhaseChatClient,
    )
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        SDKExtractionTransport,
    )

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
ROOT = Path(__file__).resolve().parents[5]
MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
TEST_KEY = "SYNTHETIC_RETENTION_NO_PROVIDER_CREDENTIAL"
SCHEMA = "corr.synthetic_campaign_retention.v1"


def digest(value: object) -> str:
    """Use the campaign's canonical JSON binding convention."""
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def seal(value: dict[str, Any]) -> dict[str, Any]:
    return {**value, "content_hash": digest(value)}


def write_json(path: Path, value: object) -> None:
    """Use the existing secret-aware immutable writer with only a synthetic key."""
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    SafeJsonWriter(TEST_KEY)(path, value)


def works(size: int) -> Iterator[dict[str, Any]]:
    """Yield one constructed source at a time, without retaining the corpus."""
    for ordinal in range(size):
        yield {
            "synthetic": True,
            "id": f"synthetic:retention:{ordinal:06d}",
            "title": f"Constructed policy study {ordinal:06d}",
            "abstract": f"Constructed study {ordinal:06d}: tax rate reduced employment.",
            "year": 2024,
            "cited_by_count": 20,
            "doi": "",
        }


def frame_descriptor(size: int) -> dict[str, Any]:
    """Enumerate the complete frame and independently reconcile SQL ordinal IDs."""
    if type(size) is not int or size < 1 or size > 1000:
        raise ValueError("retention_frame_outside_declared_bound")
    streamed = hashlib.sha256()
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE frame(ordinal INTEGER PRIMARY KEY,id TEXT UNIQUE,hash TEXT)")
        for ordinal, work in enumerate(works(size)):
            bound = digest(work)
            streamed.update((bound + "\n").encode())
            db.execute("INSERT INTO frame VALUES(?,?,?)", (ordinal, work["id"], bound))
        db.execute("CREATE TABLE expected(ordinal INTEGER PRIMARY KEY,id TEXT UNIQUE)")
        db.execute(
            """
            WITH RECURSIVE ordinal(value) AS (
                SELECT 0 UNION ALL SELECT value+1 FROM ordinal WHERE value+1 < ?
            ) INSERT INTO expected
              SELECT value,printf('synthetic:retention:%06d',value) FROM ordinal
        """,
            (size,),
        )
        mismatch = db.execute("""
            SELECT * FROM (SELECT ordinal,id FROM frame EXCEPT SELECT ordinal,id FROM expected)
            UNION ALL
            SELECT * FROM (SELECT ordinal,id FROM expected EXCEPT SELECT ordinal,id FROM frame)
        """).fetchall()
        count = db.execute("SELECT COUNT(*) FROM expected").fetchone()[0]
        actual_count = db.execute("SELECT COUNT(*) FROM frame").fetchone()[0]
        independent = hashlib.sha256()
        for (bound,) in db.execute("SELECT hash FROM frame ORDER BY ordinal"):
            independent.update((bound + "\n").encode())
    if (
        mismatch
        or actual_count != count
        or count != size
        or independent.digest() != streamed.digest()
    ):
        raise ValueError("retention_complete_frame_identity_mismatch")
    return {
        "synthetic": True,
        "input_count": size,
        "ordinal_start": 0,
        "ordinal_stop_exclusive": size,
        "input_digest": "sha256:" + streamed.hexdigest(),
        "independent_sql_count": count,
        "identity_sets_equal": True,
        "denominator": "every ordinal in the declared half-open interval, no selection by outcomes",
    }


def execution_projection() -> dict[str, Any]:
    """Extend the existing campaign projection with this diagnostic's finite owners."""
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
        campaign_owner_projection,
    )

    campaign = campaign_owner_projection()
    sources = dict(campaign["sources"])
    for path in (
        Path(__file__).resolve(),
        Path(__file__).with_name("process_telemetry.py").resolve(),
        Path(__file__).with_name("retention_analysis.py").resolve(),
        Path(__file__).with_name("throughput_trace_analysis.py").resolve(),
        Path(__file__).with_name("pilot_analysis.py").resolve(),
        ROOT / "src/polisyos/scientist/orchestration/llm/token_estimator.py",
    ):
        sources[path.relative_to(ROOT).as_posix()] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return seal(
        {
            "schema_version": "corr.synthetic_retention_execution_projection.v1",
            "campaign_owner_hash": campaign["content_hash"],
            "sources": sources,
            "scope": "finite owning source; installed/transitive dependencies not attested",
        }
    )


def make_declaration(*, sizes: tuple[int, ...] = (100, 1000)) -> dict[str, Any]:
    """Declare both complete sizes before a measured run is allowed."""
    if len(set(sizes)) != len(sizes):
        raise ValueError("retention_duplicate_frame_size")
    return seal(
        {
            "schema_version": SCHEMA + ".declaration",
            "synthetic": True,
            "declared_at": datetime.now(UTC).isoformat(),
            "authority_granted": False,
            "frames": [frame_descriptor(size) for size in sizes],
            "execution_projection": execution_projection(),
            "mock_contract_model_id": MODEL,
            "model_identity_purpose": "SDK contract identifier only; no live model was called",
            "campaign_execution_epoch": "v2",
            "campaign_fatal_policy": "stop_systemic",
            "concurrency": 1,
            "queue_capacity": 2,
            "attempts_per_input": 3,
            "max_attempts_per_phase": 1,
            "retry_unknown": False,
            "mock_phase_shapes": "screening true, one constructed claim, empty verification list",
            "mock_transport": "httpx.MockTransport through unchanged SDKExtractionTransport",
            "harness_state": "one ContextVar, fixed three phase counters, rolling digest",
            "scope": "actual extraction campaign, SDK and local token estimator; graph excluded",
            "frame_reconciliation_memory": (
                "in-memory SQLite is bounded to at most 1000 declared ordinals; "
                "before first work completion, not a full-campaign memory bound"
            ),
            "metrics": "complete trace, after-first-completion bins and OLS; finite runs only",
            "long_run_memory_bound_established": False,
            "interpretation": (
                "Positive finite RSS slopes may reflect retained state or allocator warm-up; "
                "no provider throughput, quality, calibration, or week-long memory safety claim"
            ),
            "resource_limits": {
                "max_wall_seconds": 1800,
                "max_rss_bytes": 3 * 1024**3,
                "max_disk_write_bytes": 2 * 1024**3,
                "sample_interval_seconds": 0.25,
                "shutdown_grace_seconds": 2,
            },
            "cap_semantics": "sampled operational stops; a capped partial frame is not established",
        }
    )


def _same_source(actual: object, expected: object) -> None:
    if actual != expected:
        raise ValueError("retention_execution_source_changed")


def admit(path: Path, size: int) -> dict[str, Any]:
    """Recompute the declared source/frame before launching any work."""
    value = json.loads(path.read_text())
    unsigned = {key: item for key, item in value.items() if key != "content_hash"}
    if digest(unsigned) != value.get("content_hash"):
        raise ValueError("retention_declaration_hash_mismatch")
    if value.get("synthetic") is not True or value.get("authority_granted") is not False:
        raise ValueError("retention_requires_marked_synthetic")
    _same_source(execution_projection(), value["execution_projection"])
    selected = [frame for frame in value["frames"] if frame["input_count"] == size]
    if len(selected) != 1 or selected[0] != frame_descriptor(size):
        raise ValueError("retention_declared_frame_mismatch")
    return value


def local_estimator(model: str, messages: list[dict[str, str]]) -> int:
    """Call the same repository estimator used by the actual live pilot adapter."""
    from polisyos.scientist.orchestration.llm.token_estimator import estimate_request_tokens

    return estimate_request_tokens(messages=messages, model=model, provider_hint="gonka")


class BoundedMock:
    """Construct a single response at a time; retain counters and a rolling hash only."""

    __slots__ = ("active", "counts", "current", "peak", "rolling")

    def __init__(self) -> None:
        self.current: contextvars.ContextVar[CampaignCallContext] = contextvars.ContextVar(
            "retention_active_phase"
        )
        self.counts = {"screening": 0, "extraction": 0, "self_verification": 0}
        self.rolling = hashlib.sha256()
        self.active = 0
        self.peak = 0

    def bind(
        self, transport: SDKExtractionTransport, context: CampaignCallContext
    ) -> PhaseChatClient:
        bound = transport.bind(context)
        mock = self

        class Client:
            synthetic = True

            async def chat(
                self, *, model: str, temperature: float, prompt: str
            ) -> tuple[dict[str, Any], dict[str, Any]]:
                token = mock.current.set(context)
                try:
                    return await bound.chat(model=model, temperature=temperature, prompt=prompt)
                finally:
                    mock.current.reset(token)

        return Client()

    def handle(self, request: httpx.Request) -> httpx.Response:
        import httpx

        context = self.current.get()
        if context.phase not in self.counts:
            raise ValueError("retention_unknown_mock_phase")
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if context.phase == "screening":
                parsed = {"relevant": True}
            elif context.phase == "self_verification":
                parsed = {"verifications": []}
            else:
                ordinal = int(context.work_id.rsplit(":", 1)[1])
                text = f"Constructed study {ordinal:06d}: tax rate reduced employment."
                parsed = {
                    "causal_claims": [
                        {
                            "cause_variable": "tax rate",
                            "effect_variable": "employment",
                            "direction": "negative",
                            "evidence_strength": "structural",
                            "claim_extraction_confidence": 0.7,
                            "design_family_hint": "ols",
                            "claim_text": text,
                            "supporting_spans": [{"section": "abstract", "text": text}],
                        }
                    ],
                    "extraction_confidence": 0.8,
                }
            self.counts[context.phase] += 1
            self.rolling.update((context.attempt_id + ":" + digest(parsed) + "\n").encode())
            return httpx.Response(
                200,
                request=request,
                json={
                    "synthetic": True,
                    "id": "synthetic-retention",
                    "created": 1,
                    "object": "chat.completion",
                    "model": MODEL,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(parsed),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                },
            )
        finally:
            self.active -= 1


def completion_count(checkpoint: Path) -> int:
    """Use a constant-size SQL counter, without retaining work identities in Python."""
    with closing(
        sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1)
    ) as db:
        count, independent = db.execute(
            "SELECT COUNT(*),SUM(CASE WHEN state='complete' THEN 1 ELSE 0 END) "
            "FROM works WHERE state='complete'"
        ).fetchone()
    if count != (independent or 0):
        raise ValueError("retention_checkpoint_count_mismatch")
    return count


def _observation_identity(path: Path, identifier: str) -> None:
    if path.name != identifier.removeprefix("sha256:") + ".json":
        raise ValueError("retention_mock_observation_identity_mismatch")


async def run_worker(declaration: Path, size: int, output: Path) -> dict[str, Any]:
    """Execute the unchanged campaign/SDK on marked mocks in one long-lived process."""
    value = admit(declaration, size)
    if output.exists():
        raise ValueError("retention_output_must_be_new")
    import httpx

    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
        CampaignPlan,
        run_campaign,
    )
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        PROVIDER_BASE_URL,
        SDKExtractionTransport,
    )

    frame = next(frame for frame in value["frames"] if frame["input_count"] == size)
    plan = CampaignPlan(
        campaign_id=f"synthetic:retention:{size}:{value['content_hash'][7:23]}",
        synthetic=True,
        input_count=size,
        input_digest=frame["input_digest"],
        provider_profile_hash=digest(
            {"synthetic": True, "declaration_hash": value["content_hash"]}
        ),
        screening_model=MODEL,
        extraction_model=MODEL,
        concurrency=value["concurrency"],
        queue_capacity=value["queue_capacity"],
        max_attempts=size * value["attempts_per_input"],
        max_attempts_per_phase=value["max_attempts_per_phase"],
        retry_unknown=False,
        owner_source_hash=value["execution_projection"]["campaign_owner_hash"],
        execution_epoch=value["campaign_execution_epoch"],
        fatal_policy=value["campaign_fatal_policy"],
    )
    mock = BoundedMock()
    async with SDKExtractionTransport(
        api_key=TEST_KEY,
        base_url=PROVIDER_BASE_URL,
        model_id=MODEL,
        output_root=output / "provider",
        timeout_seconds=180,
        max_completion_tokens=8192,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(mock.handle)),
        prompt_estimator=local_estimator,
    ) as transport:
        summary = await run_campaign(
            plan,
            works=works(size),
            output_root=output / "campaign",
            client_factory=lambda context: mock.bind(transport, context),
            safe_write_json=transport.safe_write_json,
        )
    finished = time.monotonic()
    if mock.current.get(None) is not None or mock.active != 0:
        raise ValueError("retention_mock_kept_finished_context")
    checkpoint = output / "campaign" / "checkpoint.sqlite3"
    complete = completion_count(checkpoint)
    provider_root = output / "provider" / "provider_attempts"
    observed = 0
    with closing(sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for identifier, output_status in db.execute(
            "SELECT work_key,output_status FROM works ORDER BY work_key"
        ):
            packet = json.loads(
                (output / "campaign" / "works" / (identifier[7:] + ".json")).read_text()
            )
            if packet["synthetic"] is not True or output_status != "extracted":
                raise ValueError("retention_constructed_work_not_extracted")
        expected = db.execute("SELECT COUNT(*) FROM attempts WHERE state='returned'").fetchone()[0]
        for path in provider_root.glob("*.json"):
            observation = json.loads(path.read_text())
            identifier = observation["context"]["attempt_id"]
            _observation_identity(path, identifier)
            exists = db.execute(
                "SELECT state FROM attempts WHERE attempt_id=?", (identifier,)
            ).fetchone()
            if (
                exists != ("returned",)
                or observation["synthetic"] is not True
                or observation["authority_status"] != "candidate_only"
                or observation["local_prompt_token_estimate"] <= 0
            ):
                raise ValueError("retention_mock_observation_mismatch")
            observed += 1
        # Both memberships, with unique filesystem names and database PKs,
        # decide identity equality without retaining a corpus-sized Python set.
        for (identifier,) in db.execute("SELECT attempt_id FROM attempts WHERE state='returned'"):
            path = provider_root / (identifier.removeprefix("sha256:") + ".json")
            if not path.is_file():
                raise ValueError("retention_mock_observation_identity_mismatch")
            packet = json.loads(path.read_text())
            if packet["context"]["attempt_id"] != identifier:
                raise ValueError("retention_mock_observation_identity_mismatch")
        independent = sum(
            1
            for entry in os.scandir(provider_root)
            if entry.is_file() and entry.name.endswith(".json")
        )
    if observed != independent or observed != expected or expected != 3 * size or complete != size:
        raise ValueError("retention_complete_attempt_identity_mismatch")
    _same_source(execution_projection(), value["execution_projection"])
    result = {
        "schema_version": SCHEMA + ".worker",
        "synthetic": True,
        "authority_granted": False,
        "authority_status": "candidate_measurement",
        "declaration_hash": value["content_hash"],
        "completed_work_count": complete,
        "extracted_work_count": complete,
        "mock_http_attempt_count": sum(mock.counts.values()),
        "mock_phase_counts": mock.counts,
        "mock_peak_active": mock.peak,
        "retained_mock_payloads": 0,
        "mock_response_stream_hash": "sha256:" + mock.rolling.hexdigest(),
        "provider_observation_count": observed,
        "provider_usage": "constructed_not_billable",
        "campaign_finished_monotonic_seconds": finished,
        "end_reconciliation_seconds": time.monotonic() - finished,
        "execution_source_finish_comparison": "recomputed_equal",
        "campaign_summary": summary,
        "mock_schema_validity": "actual_typed_owner",
    }
    write_json(output / "worker-summary.json", result)
    return result


def profile(declaration: Path, size: int, output: Path) -> dict[str, Any]:
    """Monitor only the spawned campaign and its descendants under declared caps."""
    value = admit(declaration, size)
    if output.exists():
        raise ValueError("retention_profile_output_must_be_new")
    telemetry = importlib.import_module(PREFIX + "process_telemetry")
    worker = output / "worker"
    checkpoint = worker / "campaign" / "checkpoint.sqlite3"
    result = telemetry.profile_module(
        PREFIX + "synthetic_retention",
        ["worker", str(declaration), str(size), str(worker)],
        cwd=ROOT,
        output_root=output / "profile",
        limits=telemetry.ProfileLimits(**value["resource_limits"]),
        completion_reader=lambda: completion_count(checkpoint),
        synthetic=True,
    )
    packet = {
        "schema_version": SCHEMA + ".profile",
        "synthetic": True,
        "authority_granted": False,
        "declaration_hash": value["content_hash"],
        "declared_input_count": size,
        "profile": result,
        "worker_summary_path": str(worker / "worker-summary.json"),
        "long_run_memory_bound_established": False,
    }
    write_json(output / "profile-summary.json", packet)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    declare = commands.add_parser("declare")
    declare.add_argument("output", type=Path)
    for name in ("worker", "profile"):
        child = commands.add_parser(name)
        child.add_argument("declaration", type=Path)
        child.add_argument("size", type=int, choices=(100, 1000))
        child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "declare":
        value = make_declaration()
        write_json(args.output, value)
        result = {"synthetic": True, "declaration_hash": value["content_hash"]}
    elif args.command == "worker":
        result = asyncio.run(run_worker(args.declaration, args.size, args.output))
    else:
        result = profile(args.declaration, args.size, args.output)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if args.command != "profile" or result["profile"]["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
