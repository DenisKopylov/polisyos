"""Bounded extraction campaigns with durable, content-bound candidate checkpoints.

The journal owns progress, not scientific authority. A dispatch with no durable
response is an unknown outcome and still spends an attempt after restart.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from polisyos.ir import ArticleExtractionResult

    from .article_extractor import ExtractorStats

Phase = Literal["screening", "extraction", "self_verification"]
SafeJSONWriter = Callable[[Path, object], None]
_PHASES = frozenset({"screening", "extraction", "self_verification"})
_SCHEMA = "policyos.academic.extraction_campaign.v1"
_STAGE = "abstract_campaign"
_WORK_OUTCOMES = frozenset({
    "extracted", "screening_rejected", "no_claim_artifact",
    "verification_unavailable", "provider_failed", "contract_violation",
})
_OWNER_PATHS = (
    "src/polisyos/data_forge/domains/academic/batch/reextraction_campaign.py",
    "src/polisyos/data_forge/domains/academic/batch/reextraction_transport.py",
    "src/polisyos/data_forge/domains/academic/batch/article_extractor.py",
    "src/polisyos/data_forge/domains/academic/batch/prompts",
    "src/polisyos/data_forge/domains/academic/batch/claim_ids.py",
    "src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py",
    "src/polisyos/data_forge/domains/academic/batch/context_classifier.py",
    "src/polisyos/data_forge/domains/academic/batch/fulltext_resolver.py",
    "src/polisyos/data_forge/domains/academic/knowledge/variable_canonizer.py",
    "src/polisyos/data_forge/domains/academic/knowledge/canonical_seed.py",
    "src/polisyos/data_forge/domains/academic/knowledge/canonical_resolver.py",
    "src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py",
    "src/polisyos/data_forge/domains/academic/knowledge/skg_store.py",
    "src/polisyos/data_forge/domains/academic/knowledge/types.py",
    "src/polisyos/data_forge/domains/academic/trust.py",
    "src/polisyos/ir/analytics/literature.py",
    "src/polisyos/core/canon/hashing.py",
    "uv.lock",
)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def campaign_owner_projection() -> dict[str, Any]:
    """Recompute the finite execution-owner source binding from current bytes.

    This projection names its complete finite denominator. It is not a claim of
    process attestation or coverage of every transitive installed dependency.
    """
    root = Path(__file__).resolve().parents[6]
    sources = {}
    for relative in _OWNER_PATHS:
        target = root / relative
        paths = sorted(target.rglob("*.py")) if target.is_dir() else (target,)
        for path in paths:
            sources[path.relative_to(root).as_posix()] = _bytes_digest(path.read_bytes())
    projection = {"schema_version": "policyos.academic.campaign_execution_sources.v1",
                  "sources": sources}
    return {**projection, "content_hash": _digest(projection)}


@dataclass(frozen=True)
class CampaignPlan:
    """Bind a bounded execution to its input frame and provider configuration."""

    campaign_id: str
    synthetic: bool
    input_count: int
    input_digest: str
    provider_profile_hash: str
    screening_model: str
    extraction_model: str
    concurrency: int
    queue_capacity: int
    max_attempts: int
    max_attempts_per_phase: int
    retry_unknown: bool = False
    retry_delay_seconds: float = 0.0
    max_artifact_bytes: int = 8_388_608
    owner_source_hash: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "input_count", "concurrency", "queue_capacity", "max_attempts",
            "max_attempts_per_phase", "max_artifact_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"campaign_invalid_{name}")
        if type(self.synthetic) is not bool or type(self.retry_unknown) is not bool:
            raise ValueError("campaign_invalid_boolean")
        if self.concurrency > 32 or self.queue_capacity > 2 * self.concurrency:
            raise ValueError("campaign_queue_or_concurrency_limit")
        if self.max_attempts_per_phase > 8:
            raise ValueError("campaign_phase_attempt_limit")
        if not 0 <= self.retry_delay_seconds <= 120:
            raise ValueError("campaign_invalid_retry_delay")
        for value in (self.input_digest, self.provider_profile_hash):
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
                raise ValueError("campaign_invalid_binding_hash")
        if not all(isinstance(value, str) and value for value in (
            self.campaign_id, self.screening_model, self.extraction_model,
        )):
            raise ValueError("campaign_missing_identity")


@dataclass(frozen=True)
class CampaignCallContext:
    """Attribute one actual dispatch without shared mutable worker context."""

    campaign_id: str
    work_id: str
    work_key: str
    phase: Phase
    phase_key: str
    attempt_id: str
    attempt_ordinal: int
    model_id: str
    prompt_hash: str
    synthetic: bool
    scope: Literal["candidate_only"] = "candidate_only"


class PhaseChatClient(Protocol):
    """One immutable-attribution dispatch through the selected transport."""

    synthetic: bool

    async def chat(
        self, *, model: str, temperature: float, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return the actual JSON object and usage, or a sanitized error."""
        ...


ClientFactory = Callable[[CampaignCallContext], PhaseChatClient]


class CampaignCheckpoint:
    """Keep a single-writer disk journal and immutable candidate artifacts.

    Args:
        root: Isolated output directory. Live outputs stay under lane scratch.
        plan: Immutable pre-execution source and budget binding.
        safe_write_json: Credential-checking writer supplied by the transport.
    """

    def __init__(self, root: Path, plan: CampaignPlan, safe_write_json: SafeJSONWriter) -> None:
        self.root = root.resolve()
        self.plan = plan
        self._safe_write = safe_write_json
        self._binding = _digest(asdict(plan))
        if plan.owner_source_hash != campaign_owner_projection()["content_hash"]:
            raise ValueError("campaign_owner_source_mismatch")
        product_root = Path(__file__).resolve().parents[6]
        held = (product_root / "production_data").resolve()
        if self.root == held or held in self.root.parents or self.root in held.parents:
            raise ValueError("campaign_output_crosses_held_source")
        if not plan.synthetic and (product_root / ".tmp").resolve() not in self.root.parents:
            raise ValueError("campaign_live_output_outside_lane_scratch")
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = (self.root / "writer.lock").open("a+b")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock.close()
            raise ValueError("campaign_already_running") from exc
        self._db: sqlite3.Connection | None = None
        try:
            packet = self._packet("plan", plan=asdict(plan))
            path = self.root / "plan.json"
            if path.exists() and json.loads(self._bounded_bytes(path)) != packet:
                raise ValueError("campaign_binding_mismatch")
            self._write_packet(path, packet)
            self._db = sqlite3.connect(self.root / "checkpoint.sqlite3")
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS works (
                    work_key TEXT PRIMARY KEY, ordinal INTEGER UNIQUE NOT NULL,
                    source_hash TEXT NOT NULL, state TEXT NOT NULL,
                    output_hash TEXT, output_status TEXT, intended_output_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY, work_key TEXT NOT NULL,
                    phase TEXT NOT NULL, phase_key TEXT NOT NULL,
                    ordinal INTEGER NOT NULL, state TEXT NOT NULL,
                    intent_hash TEXT NOT NULL, output_hash TEXT,
                    usage_known INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(phase_key, ordinal)
                );
                CREATE INDEX IF NOT EXISTS attempts_phase ON attempts(phase_key, ordinal);
                CREATE TABLE IF NOT EXISTS work_identities (
                    identity_hash TEXT PRIMARY KEY, work_key TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            self._recover_attempts()
            self._recover_work_outputs()
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> CampaignCheckpoint:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the local database and process lock."""
        if self._db is not None:
            self._db.close()
            self._db = None
        if not self._lock.closed:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            self._lock.close()

    @property
    def db(self) -> sqlite3.Connection:
        """Return this instance's open single-writer checkpoint connection."""
        if self._db is None:
            raise ValueError("campaign_checkpoint_closed")
        return self._db

    def _packet(self, kind: str, **payload: object) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA, "artifact_kind": kind,
            "campaign_binding": self._binding, "synthetic": self.plan.synthetic,
            "scope": "candidate_only", **payload,
        }

    def _bounded_bytes(self, path: Path) -> bytes:
        with path.open("rb") as stream:
            data = stream.read(self.plan.max_artifact_bytes + 1)
        if len(data) > self.plan.max_artifact_bytes:
            raise ValueError("campaign_artifact_exceeds_bound")
        return data

    def _write_packet(self, path: Path, packet: dict[str, Any]) -> str:
        # The supplied writer checks secrets before any bytes reach the filesystem.
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".pending-{uuid.uuid4().hex}.json"
        try:
            self._safe_write(temporary, packet)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
                data = stream.read(self.plan.max_artifact_bytes + 1)
            if len(data) > self.plan.max_artifact_bytes:
                raise ValueError("campaign_artifact_exceeds_bound")
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._bounded_bytes(path) != data:
                    raise ValueError("campaign_immutable_artifact_conflict") from None
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return _bytes_digest(data)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_packet(self, path: Path, expected_hash: str) -> dict[str, Any]:
        data = self._bounded_bytes(path)
        if _bytes_digest(data) != expected_hash:
            raise ValueError("campaign_artifact_hash_mismatch")
        packet = json.loads(data)
        if (
            not isinstance(packet, dict) or packet.get("schema_version") != _SCHEMA
            or packet.get("campaign_binding") != self._binding
            or packet.get("synthetic") is not self.plan.synthetic
            or packet.get("scope") != "candidate_only"
        ):
            raise ValueError("campaign_artifact_binding_mismatch")
        return packet

    def register_work(self, work: dict[str, Any]) -> str:
        """Persist one complete input without collecting the frame in memory."""
        if not isinstance(work.get("id"), str) or not work["id"]:
            raise ValueError("campaign_work_identity_missing")
        if not isinstance(work.get("abstract"), str) or not work["abstract"].strip():
            raise ValueError("campaign_held_abstract_missing")
        if not self.plan.synthetic and _contains_synthetic(work):
            raise ValueError("campaign_synthetic_source_requires_marked_plan")
        key = _digest(work)
        identity_hash = _digest(work["id"])
        existing_identity = self.db.execute(
            "SELECT work_key FROM work_identities WHERE identity_hash=?", (identity_hash,),
        ).fetchone()
        if existing_identity is not None and existing_identity[0] != key:
            raise ValueError("campaign_work_identity_rebound")
        if existing_identity is None and self.db.execute(
            "SELECT value FROM metadata WHERE key='frame_admitted'",
        ).fetchone() is not None:
            raise ValueError("campaign_input_frame_already_admitted")
        packet = self._packet("input", work_key=key, work=work)
        source_hash = self._write_packet(self.root / "inputs" / f"{key[7:]}.json", packet)
        row = self.db.execute("SELECT source_hash FROM works WHERE work_key=?", (key,)).fetchone()
        if row is not None:
            if row[0] != source_hash:
                raise ValueError("campaign_source_binding_mismatch")
            return key
        ordinal = self.db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        with self.db:
            self.db.execute("INSERT INTO work_identities VALUES(?,?)", (identity_hash, key))
            self.db.execute(
                "INSERT INTO works VALUES(?,?,?,'pending',NULL,NULL,NULL)",
                (key, ordinal, source_hash),
            )
        return key

    def source_work(self, work_key: str) -> dict[str, Any]:
        """Replay the complete source artifact behind a registered work key."""
        row = self.db.execute(
            "SELECT source_hash FROM works WHERE work_key=?", (work_key,),
        ).fetchone()
        if row is None:
            raise ValueError("campaign_work_unregistered")
        packet = self._read_packet(self.root / "inputs" / f"{work_key[7:]}.json", row[0])
        if packet.get("work_key") != work_key or _digest(packet.get("work")) != work_key:
            raise ValueError("campaign_source_binding_mismatch")
        return packet["work"]

    def _phase_key(self, work_key: str, phase: str, model: str, prompt: str) -> str:
        if phase not in _PHASES:
            raise ValueError("campaign_unknown_phase")
        return _digest((self._binding, work_key, phase, model, _bytes_digest(prompt.encode())))

    def begin_attempt(
        self, work_key: str, *, phase: Phase, model: str, prompt: str,
    ) -> CampaignCallContext:
        """Durably spend an attempt before allowing the external dispatch."""
        admitted = self.db.execute(
            "SELECT value FROM metadata WHERE key='frame_admitted'",
        ).fetchone()
        if admitted is None or admitted[0] != self.plan.input_digest:
            raise ValueError("campaign_input_frame_not_admitted")
        phase_key = self._phase_key(work_key, phase, model, prompt)
        source = self.source_work(work_key)
        total = self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        if total >= self.plan.max_attempts:
            raise ValueError("campaign_attempt_budget_exhausted")
        previous = self.db.execute(
            "SELECT ordinal,state FROM attempts WHERE phase_key=? ORDER BY ordinal DESC LIMIT 1",
            (phase_key,),
        ).fetchone()
        ordinal = previous[0] + 1 if previous else 1
        if previous and previous[1] == "returned":
            raise ValueError("campaign_phase_already_completed")
        if previous and previous[1] == "outcome_unknown" and not self.plan.retry_unknown:
            raise ValueError("campaign_unknown_outcome_requires_declared_retry")
        if ordinal > self.plan.max_attempts_per_phase:
            raise ValueError("campaign_phase_attempt_budget_exhausted")
        context = CampaignCallContext(
            self.plan.campaign_id, source["id"], work_key, phase, phase_key,
            _digest((phase_key, ordinal))[7:], ordinal, model,
            _bytes_digest(prompt.encode()), self.plan.synthetic,
        )
        intent_hash = self._write_packet(
            self.root / "intents" / f"{context.attempt_id}.json",
            self._packet("attempt_intent", context=asdict(context)),
        )
        with self.db:
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,'dispatched',?,NULL,0)", (
                context.attempt_id, work_key, phase, phase_key, ordinal, intent_hash,
            ))
        return context

    def finish_attempt(
        self, context: CampaignCallContext, parsed: dict[str, Any], usage: dict[str, Any],
    ) -> None:
        """Commit a complete response before the extractor consumes it."""
        if not isinstance(parsed, dict) or not isinstance(usage, dict):
            raise ValueError("campaign_response_requires_objects")
        packet = self._packet("attempt_result", context=asdict(context),
                              status="returned", parsed=parsed, usage=usage)
        output_hash = self._write_packet(
            self.root / "attempts" / f"{context.attempt_id}.json", packet,
        )
        self._finish_row(context, output_hash, "returned", all(
            type(usage.get(name)) is int and usage[name] >= 0
            for name in ("prompt_tokens", "completion_tokens")
        ))

    def fail_attempt(
        self, context: CampaignCallContext, *, kind: str, retryable: bool,
        status_code: int | None = None,
    ) -> None:
        """Persist only allowlisted scalar error information, never error bodies."""
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,80}", kind):
            kind = "unclassified_error"
        if type(retryable) is not bool or (
            status_code is not None
            and (type(status_code) is not int or not 100 <= status_code < 600)
        ):
            raise ValueError("campaign_invalid_safe_error")
        output_hash = self._write_packet(
            self.root / "attempts" / f"{context.attempt_id}.json",
            self._packet("attempt_result", context=asdict(context), status="failed",
                         error_kind=kind, retryable=retryable, status_code=status_code,
                         usage=None),
        )
        self._finish_row(context, output_hash, "failed", False)

    def _finish_row(
        self, context: CampaignCallContext, output_hash: str, state: str, usage_known: bool,
    ) -> None:
        row = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (
            context.attempt_id,
        )).fetchone()
        if row is None or row["state"] != "dispatched":
            raise ValueError("campaign_attempt_not_dispatched")
        intent = self._read_packet(
            self.root / "intents" / f"{context.attempt_id}.json", row["intent_hash"],
        )
        if intent.get("context") != asdict(context):
            raise ValueError("campaign_attempt_binding_mismatch")
        with self.db:
            self.db.execute(
                "UPDATE attempts SET state=?,output_hash=?,usage_known=? WHERE attempt_id=?",
                (state, output_hash, int(usage_known), context.attempt_id),
            )

    def _recover_attempts(self) -> None:
        # A final response file can precede the SQLite commit by one atomic step.
        for row in self.db.execute("SELECT * FROM attempts WHERE state='dispatched'"):
            intent = self._read_packet(
                self.root / "intents" / f"{row['attempt_id']}.json", row["intent_hash"],
            )
            path = self.root / "attempts" / f"{row['attempt_id']}.json"
            if path.exists():
                data = self._bounded_bytes(path)
                packet = self._read_packet(path, _bytes_digest(data))
                if packet.get("context") != intent["context"]:
                    raise ValueError("campaign_attempt_binding_mismatch")
                context = CampaignCallContext(**intent["context"])
                if packet.get("status") == "returned":
                    self.finish_attempt(context, packet["parsed"], packet["usage"])
                elif packet.get("status") == "failed":
                    self.fail_attempt(
                        context, kind=packet["error_kind"], retryable=packet["retryable"],
                        status_code=packet["status_code"],
                    )
                else:
                    raise ValueError("campaign_attempt_result_invalid")
            else:
                with self.db:
                    self.db.execute(
                        "UPDATE attempts SET state='outcome_unknown' WHERE attempt_id=?",
                        (row["attempt_id"],),
                    )

    def cached_response(
        self, work_key: str, *, phase: Phase, model: str, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Replay only an intact response bound to this exact phase request."""
        self.source_work(work_key)
        phase_key = self._phase_key(work_key, phase, model, prompt)
        row = self.db.execute(
            "SELECT * FROM attempts WHERE phase_key=? AND state='returned' "
            "ORDER BY ordinal LIMIT 1",
            (phase_key,),
        ).fetchone()
        if row is None:
            return None
        packet = self._read_packet(
            self.root / "attempts" / f"{row['attempt_id']}.json", row["output_hash"],
        )
        if packet["context"]["phase_key"] != phase_key or packet.get("status") != "returned":
            raise ValueError("campaign_attempt_binding_mismatch")
        return packet["parsed"], packet["usage"]

    def commit_work(self, work_key: str, *, status: str, record: dict[str, Any] | None) -> None:
        """Publish a complete candidate work outcome, including honest non-emission."""
        self.source_work(work_key)
        if status not in _WORK_OUTCOMES:
            raise ValueError("campaign_unknown_work_outcome")
        phases = [dict(row) for row in self.db.execute(
            "SELECT attempt_id,intent_hash,output_hash,state FROM attempts "
            "WHERE work_key=? ORDER BY phase,ordinal", (work_key,),
        )]
        packet = self._packet("work_outcome", work_key=work_key, status=status,
                              record=record, phase_artifacts=phases)
        # Pin the complete intended value before atomic publication. Recovery
        # can then adopt exactly those bytes without restamping extraction time.
        with self.db:
            self.db.execute("UPDATE works SET intended_output_hash=? WHERE work_key=?",
                            (_digest(packet), work_key))
        output_hash = self._write_packet(self.root / "works" / f"{work_key[7:]}.json", packet)
        with self.db:
            self.db.execute("UPDATE works SET state='complete',output_hash=?,output_status=? "
                            "WHERE work_key=?", (output_hash, status, work_key))

    def _validate_work_packet(self, work_key: str, packet: dict[str, Any]) -> None:
        if packet.get("work_key") != work_key or packet.get("status") not in _WORK_OUTCOMES:
            raise ValueError("campaign_work_outcome_binding_mismatch")
        phases = packet.get("phase_artifacts")
        actual = [dict(row) for row in self.db.execute(
            "SELECT attempt_id,intent_hash,output_hash,state FROM attempts "
            "WHERE work_key=? ORDER BY phase,ordinal", (work_key,),
        )]
        if phases != actual:
            raise ValueError("campaign_work_phase_binding_mismatch")
        for phase in phases:
            intent = self._read_packet(
                self.root / "intents" / f"{phase['attempt_id']}.json", phase["intent_hash"],
            )
            if intent["context"]["work_key"] != work_key:
                raise ValueError("campaign_work_phase_binding_mismatch")
            if phase["output_hash"] is not None:
                result = self._read_packet(
                    self.root / "attempts" / f"{phase['attempt_id']}.json", phase["output_hash"],
                )
                if result["context"] != intent["context"]:
                    raise ValueError("campaign_work_phase_binding_mismatch")

    def _recover_work_outputs(self) -> None:
        for row in self.db.execute("SELECT * FROM works WHERE state='pending'"):
            key = row["work_key"]
            path = self.root / "works" / f"{key[7:]}.json"
            if not path.exists():
                continue
            self.source_work(key)
            with path.open("rb") as stream:
                data = stream.read(self.plan.max_artifact_bytes + 1)
            packet = self._read_packet(path, _bytes_digest(data))
            if row["intended_output_hash"] != _digest(packet):
                raise ValueError("campaign_work_publication_binding_mismatch")
            self._validate_work_packet(key, packet)
            with self.db:
                self.db.execute("UPDATE works SET state='complete',output_hash=?,output_status=? "
                                "WHERE work_key=?", (_bytes_digest(data), packet["status"], key))

    def completed_work(self, work_key: str) -> dict[str, Any] | None:
        """Resolve a completed checkpoint through its source and result bytes."""
        self.source_work(work_key)
        row = self.db.execute("SELECT * FROM works WHERE work_key=?", (work_key,)).fetchone()
        if row["state"] != "complete":
            return None
        packet = self._read_packet(self.root / "works" / f"{work_key[7:]}.json", row["output_hash"])
        self._validate_work_packet(work_key, packet)
        if packet.get("status") != row["output_status"]:
            raise ValueError("campaign_work_outcome_binding_mismatch")
        return packet

    def iter_work_keys(self) -> Iterator[str]:
        """Stream source-order identities from disk rather than a corpus list."""
        for row in self.db.execute("SELECT work_key FROM works ORDER BY ordinal"):
            yield row[0]

    def prepare_inputs(self, works: Iterable[dict[str, Any]]) -> None:
        """Reconcile the complete declared frame before permitting any calls."""
        digest = hashlib.sha256()
        count = 0
        for work in works:
            key = self.register_work(work)
            digest.update((key + "\n").encode())
            count += 1
        persisted = self.db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        if (
            count != self.plan.input_count or count != persisted
            or "sha256:" + digest.hexdigest() != self.plan.input_digest
        ):
            raise ValueError("campaign_input_frame_mismatch")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('frame_admitted',?)",
                            (self.plan.input_digest,))

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """Yield intact candidate records individually for the existing graph owner."""
        for key in self.iter_work_keys():
            output = self.completed_work(key)
            if output is not None and output["record"] is not None:
                yield output["record"]

    def summary(self) -> dict[str, Any]:
        """Return bounded aggregates while retaining unknown usage distinctly."""
        return self._packet(
            "summary", works=dict(self.db.execute(
                "SELECT state,COUNT(*) FROM works GROUP BY state",
            )), attempts=dict(self.db.execute(
                "SELECT state,COUNT(*) FROM attempts GROUP BY state",
            )), outcomes=dict(self.db.execute(
                "SELECT output_status,COUNT(*) FROM works WHERE state='complete' "
                "GROUP BY output_status",
            )), unknown_usage_attempts=self.db.execute(
                "SELECT COUNT(*) FROM attempts WHERE usage_known=0",
            ).fetchone()[0],
        )


def _contains_synthetic(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("synthetic") is True or any(
            _contains_synthetic(item) for item in value.values()
        )
    return isinstance(value, (list, tuple)) and any(_contains_synthetic(item) for item in value)


class _PhaseFailedError(RuntimeError):
    """A sanitized phase failed within its declared execution budget."""


class _CheckpointChat:
    def __init__(
        self, checkpoint: CampaignCheckpoint, work_key: str, factory: ClientFactory,
    ) -> None:
        self.checkpoint = checkpoint
        self.work_key = work_key
        self.factory = factory
        self.phase: Phase = "screening"
        self.failure_kind: str | None = None
        self.contract_failed = False
        self.verification_received = False
        self.synthetic = checkpoint.plan.synthetic

    def _admit_response(self, parsed: dict[str, Any]) -> None:
        from .article_extractor import _validate_extraction_response

        if self.phase == "screening":
            valid = type(parsed.get("relevant")) is bool
        elif self.phase == "extraction":
            # Reuse the real owner's admission; do not invent a stricter
            # extraction spec or count normalization of an empty object.
            valid = _validate_extraction_response(parsed, context="extraction") is not None
        else:
            rows = parsed.get("verifications")
            valid = isinstance(rows, list) and all(
                isinstance(row, dict)
                and type(row.get("claim_index")) is int and row["claim_index"] > 0
                and type(row.get("supported")) is bool
                and type(row.get("confidence_adjustment")) in (int, float)
                and math.isfinite(row["confidence_adjustment"])
                and -0.3 <= row["confidence_adjustment"] <= 0
                and (row.get("issue") is None or isinstance(row["issue"], str))
                for row in rows
            )
            self.verification_received = valid
        if not valid:
            self.failure_kind = f"{self.phase}_contract_violation"
            self.contract_failed = True
            raise _PhaseFailedError(self.failure_kind)

    async def chat(
        self, *, model: str, temperature: float, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from .reextraction_transport import ExtractionRequestError

        cached = self.checkpoint.cached_response(
            self.work_key, phase=self.phase, model=model, prompt=prompt,
        )
        if cached is not None:
            self._admit_response(cached[0])
            return cached
        while True:
            try:
                context = self.checkpoint.begin_attempt(
                    self.work_key, phase=self.phase, model=model, prompt=prompt,
                )
            except ValueError as exc:
                if str(exc) not in {
                    "campaign_attempt_budget_exhausted", "campaign_phase_attempt_budget_exhausted",
                    "campaign_unknown_outcome_requires_declared_retry",
                }:
                    raise
                self.failure_kind = str(exc)
                raise _PhaseFailedError(str(exc)) from None
            client = self.factory(context)
            if not self.synthetic and client.synthetic is not False:
                raise ValueError("campaign_synthetic_transport_requires_marked_plan")
            try:
                parsed, usage = await client.chat(
                    model=model, temperature=temperature, prompt=prompt,
                )
            except ExtractionRequestError as exc:
                self.checkpoint.fail_attempt(
                    context, kind=exc.kind, retryable=exc.retryable, status_code=exc.status_code,
                )
                if exc.retryable and context.attempt_ordinal < (
                    self.checkpoint.plan.max_attempts_per_phase
                ):
                    await asyncio.sleep(self.checkpoint.plan.retry_delay_seconds)
                    continue
                self.failure_kind = exc.kind
                raise _PhaseFailedError(exc.kind) from None
            # Only the transport's sanitized exception is an expected provider failure.
            # Other exceptions preserve a dispatched/unknown attempt, not a fake response.
            self.checkpoint.finish_attempt(context, parsed, usage)
            self._admit_response(parsed)
            return parsed, usage


def _extractor_for_work(
    checkpoint: CampaignCheckpoint, work_key: str, work: dict[str, Any], chat: _CheckpointChat,
) -> object:
    from ..knowledge.variable_canonizer import VariableCanonizer
    from .article_extractor import PolicyArticleExtractor

    class CampaignExtractor(PolicyArticleExtractor):
        # Existing extraction/postprocessing remains the owner. This entrypoint
        # subordinates the lossy processed-key cache to complete work checkpoints.
        @staticmethod
        def _load_processed_cache(cache_path: Path) -> set[str]:
            del cache_path
            return set()

        def _append_cache_key(self, cache_key: str, openalex_id: str) -> None:
            del cache_key, openalex_id

        async def _screen(self, abstract: str, stats: ExtractorStats) -> bool:
            chat.phase = "screening"
            return await super()._screen(abstract, stats)

        async def _extract(
            self, work: dict[str, Any], text: str, source_kind: str, stats: ExtractorStats,
        ) -> ArticleExtractionResult | None:
            chat.phase = "extraction"
            return await super()._extract(work, text, source_kind, stats)

        async def _self_verify(
            self, result: ArticleExtractionResult, evidence_bundle: dict[str, Any],
            stats: ExtractorStats,
        ) -> ArticleExtractionResult:
            chat.phase = "self_verification"
            return await super()._self_verify(result, evidence_bundle, stats)

    return CampaignExtractor(
        screening_model=checkpoint.plan.screening_model,
        extraction_model=checkpoint.plan.extraction_model,
        max_concurrent=1,
        # Per-work lifetime prevents the canonizer's cache/pending-review list
        # growing with the corpus; its deterministic existing owner is unchanged.
        canonizer=VariableCanonizer(), gonka_client=chat,
        fulltext_timeout_seconds=3,
        cache_path=checkpoint.root / "unused_legacy_cache.jsonl",
        resolved_texts={work["id"]: {"text": work["abstract"], "source_kind": "abstract_fallback"}},
        preserve_source_presence=True,
    )


async def _process_work(
    checkpoint: CampaignCheckpoint, work_key: str, factory: ClientFactory,
) -> None:
    from .article_extractor import ExtractorStats, _to_work_record

    if checkpoint.completed_work(work_key) is not None:
        return
    work = checkpoint.source_work(work_key)
    if not isinstance(work.get("abstract"), str) or not work["abstract"].strip():
        raise ValueError("campaign_held_abstract_missing")
    chat = _CheckpointChat(checkpoint, work_key, factory)
    extractor = _extractor_for_work(checkpoint, work_key, work, chat)
    stats = ExtractorStats()
    try:
        result = await extractor._process_one(work, stats)
    except _PhaseFailedError:
        checkpoint.commit_work(
            work_key, status="contract_violation" if chat.contract_failed else "provider_failed",
            record=None,
        )
        return
    if result is None:
        checkpoint.commit_work(
            work_key,
            status="screening_rejected" if stats.screening_rejected else "no_claim_artifact",
            record=None,
        )
        return
    provenance = {
        "synthetic": checkpoint.plan.synthetic, "scope": "candidate_only",
        "campaign_binding": checkpoint._binding, "work_key": work_key,
        "authority_status": "candidate_only",
        "self_verification_authority": "not_independent_entailment",
    }
    record = _to_work_record(
        result=result, raw_work=work, topic_ids=[], topic_display_names=[],
        run_id=checkpoint.plan.campaign_id, pass_name=_STAGE,
    )
    record.metadata.update({
        **provenance, "source_provenance": provenance,
        "self_verification_status": (
            "unavailable" if chat.failure_kind else
            "typed_response_received" if chat.verification_received else "not_required_no_claims"
        ),
        "self_verification_claim_coverage": "not_established",
        "self_verification_error_kind": chat.failure_kind,
        "legacy_extractor_cost_fields_status": "not_established_provider_usd_not_supplied",
    })
    record.causal_claims = [transport.model_copy(update={"occurrence": {
        **transport.occurrence, **provenance, "source_provenance": provenance,
    }}) for transport in record.causal_claims]
    checkpoint.commit_work(
        work_key, status="verification_unavailable" if chat.failure_kind else "extracted",
        record=record.model_dump(mode="json"),
    )


def _completed_projection(checkpoint: CampaignCheckpoint) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in checkpoint.db.execute(
        "SELECT work_key,output_hash FROM works WHERE state='complete' ORDER BY work_key",
    ):
        key, output_hash = row
        checkpoint.source_work(key)
        packet = checkpoint._read_packet(
            checkpoint.root / "works" / f"{key[7:]}.json", output_hash,
        )
        checkpoint._validate_work_packet(key, packet)
        digest.update(json.dumps((key, output_hash), separators=(",", ":")).encode() + b"\n")
        count += 1
    sql_count = checkpoint.db.execute(
        "SELECT COUNT(*) FROM works WHERE state='complete'",
    ).fetchone()[0]
    if count != sql_count:
        raise ValueError("campaign_completed_identity_reconciliation_failed")
    return count, "sha256:" + digest.hexdigest()


async def recompute_campaign_strangle(checkpoint: CampaignCheckpoint) -> dict[str, Any]:
    """Replay the real default over every completed identity before emitting proof.

    The replay uses a fail-fast transport boundary: a provider request on already
    completed work is a failed proof, never an extra live call hidden in validation.
    """
    before = _completed_projection(checkpoint)
    attempts_before = checkpoint.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    provider_replay_attempts = 0

    def forbid_provider_replay(context: CampaignCallContext) -> PhaseChatClient:
        nonlocal provider_replay_attempts
        del context
        provider_replay_attempts += 1
        raise ValueError("campaign_completed_work_requested_provider")

    try:
        for row in checkpoint.db.execute("SELECT work_key FROM works WHERE state='complete'"):
            await _process_work(checkpoint, row[0], forbid_provider_replay)
        after = _completed_projection(checkpoint)
        attempts_after = checkpoint.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        if before != after or attempts_before != attempts_after or provider_replay_attempts:
            raise ValueError("campaign_completed_replay_changed_evidence")
    except Exception:
        raise ValueError("campaign_checkpoint_replay_strangle_failed") from None
    return checkpoint._packet(
        "strangle", strangle_schema_version="policyos.academic.campaign_checkpoint_strangle.v1",
        legacy_path="PolicyArticleExtractor.processed_key_cache",
        default_path="CampaignCheckpoint.complete_artifact_replay",
        default_flipped=before[0] > 0, completed_work_count=before[0],
        completed_identity_projection=before[1], provider_replay_attempts=provider_replay_attempts,
        actual_owner_replay="recomputed",
    )


async def run_campaign(
    plan: CampaignPlan, *, works: Iterable[dict[str, Any]], output_root: Path,
    client_factory: ClientFactory, safe_write_json: SafeJSONWriter,
) -> dict[str, Any]:
    """Run bounded candidate extraction, resuming intact phase/work artifacts.

    Graph finalization is a separate existing-owner stage. This function never
    claims that its bounded extraction queue makes a whole graph rebuild bounded.
    """
    with CampaignCheckpoint(output_root, plan, safe_write_json) as checkpoint:
        checkpoint.prepare_inputs(works)
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=plan.queue_capacity)
        queue_peak = 0

        async def producer() -> None:
            nonlocal queue_peak
            for key in checkpoint.iter_work_keys():
                await queue.put(key)
                queue_peak = max(queue_peak, queue.qsize())
            for _ in range(plan.concurrency):
                await queue.put(None)

        async def worker() -> None:
            while True:
                key = await queue.get()
                try:
                    if key is None:
                        return
                    await _process_work(checkpoint, key, client_factory)
                finally:
                    queue.task_done()

        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(producer())
            for _ in range(plan.concurrency):
                tasks.create_task(worker())
        report = checkpoint.summary()
        report["queue_peak"] = queue_peak
        report["graph_finalization"] = "not_started_separate_owner_stage"
        strangle = await recompute_campaign_strangle(checkpoint)
        strangle_path = Path("strangles") / f"{_digest(strangle)[7:]}.json"
        strangle_hash = checkpoint._write_packet(checkpoint.root / strangle_path, strangle)
        report["strangle_ref"] = {"path": strangle_path.as_posix(), "sha256": strangle_hash}
        # An append-only observation can differ on restart (e.g. queue scheduling).
        checkpoint._write_packet(output_root / "observations" / f"{uuid.uuid4().hex}.json", report)
        return report


__all__ = [
    "CampaignCallContext", "CampaignCheckpoint", "CampaignPlan", "PhaseChatClient",
    "campaign_owner_projection", "recompute_campaign_strangle", "run_campaign",
]
