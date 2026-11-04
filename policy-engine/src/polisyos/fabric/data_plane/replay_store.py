"""ReplayStore — CAS-backed persistence for record/replay sessions.

Bridges the APISimulator (test-level HTTP record/replay) with the CAS
storage layer for ingestion-level record/replay.

Record mode: APISimulator captures HTTP responses as SimulatorFixture
objects on disk → ReplayStore collects them into a RecordSession and
persists the session to CAS.

Replay mode: ReplayStore loads a RecordSession from CAS → writes
SimulatorFixture files to a temp directory → APISimulator serves them
in REPLAY mode (no network).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.canon import CanonSpec

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordSession:
    """All captured HTTP fixtures from a single ingestion run."""

    session_id: str
    fixtures: list[dict[str, Any]] = field(default_factory=list)
    connector_datasets: list[dict[str, str]] = field(default_factory=list)
    recorded_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordSession:
        return cls(
            session_id=data["session_id"],
            fixtures=data.get("fixtures", []),
            connector_datasets=data.get("connector_datasets", []),
            recorded_at=data.get("recorded_at", ""),
        )


# ---------------------------------------------------------------------------
# ReplayStore
# ---------------------------------------------------------------------------


class ReplayStore:
    """Persistence layer for record/replay sessions in CAS."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def save_record_session(
        self, session: RecordSession, *, evidence_ref: ArtifactRef | None = None
    ) -> ArtifactRef:
        """Persist a RecordSession to CAS as a JSON artifact."""
        from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
        from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
        from polisyos.core.contracts import EvidenceBundle

        if evidence_ref is not None:
            if (
                evidence_ref.kind != "fabric.evidence_bundle"
                or evidence_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("record_session_requires_selected_evidence")
            evidence = EvidenceBundle.model_validate(
                load_core_json_artifact(self._store, evidence_ref)
            )
            if (
                evidence.execution_context is None
                or evidence.execution_context.mode != "record"
                or evidence.execution_context.capture_session_id != session.session_id
            ):
                raise ValueError("record_session_capture_evidence_mismatch")

        return self._store.put_json(
            session.to_dict(),
            ArtifactWriteOptions(
                kind="fabric.record_session",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.fabric.RecordSession",
                    version="2.0",
                ),
                inputs=(
                    [input_ref_from_artifact_ref(evidence_ref, role="fabric.ingestion.evidence")]
                    if evidence_ref is not None
                    else None
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    def resolve_record_session_ref(self, selector: ArtifactID | str | ArtifactRef) -> ArtifactRef:
        """Resolve an explicit selected view or a legacy default-only identifier."""
        from polisyos.core.artifacts import artifact_ref_for_manifest

        selector = (
            selector if isinstance(selector, ArtifactRef) else ArtifactID.model_validate(selector)
        )
        manifest = self._store.get_manifest(selector)
        if (
            manifest.kind != "fabric.record_session"
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != "polisyos.fabric.RecordSession"
            or manifest.artifact_schema.version not in {"1.0", "2.0"}
        ):
            raise ValueError("record_session_schema_unsupported")
        return artifact_ref_for_manifest(manifest)

    def load_record_session(self, artifact_id: ArtifactID | str | ArtifactRef) -> RecordSession:
        """Load the declared v1 legacy or v2 request-bound session without rewriting it."""
        from polisyos.core.artifacts import load_core_json_artifact

        selected = self.resolve_record_session_ref(artifact_id)
        data = load_core_json_artifact(self._store, selected)
        if not isinstance(data, dict):
            raise ValueError("record_session_payload_invalid")
        return RecordSession.from_dict(data)

    def build_replay_fixture_dir(
        self,
        session: RecordSession,
        target: Path,
    ) -> Path:
        """Write SimulatorFixture files to target dir in APISimulator layout.

        Layout: target/<connector_id>/<dataset_id>/<request_hash>.json
        """
        from polisyos.fabric.connectors.testing.simulator import (
            SimulatorFixture,
            _fixture_path_for_namespace,
        )

        planned: list[tuple[SimulatorFixture, Path]] = []
        for fixture_dict in session.fixtures:
            fixture = SimulatorFixture.from_dict(fixture_dict)
            connector_id = fixture.connector_id or "unknown"
            dataset_id = fixture.dataset_id or "unknown"
            req_hash = fixture.request_hash

            fixture_path = _fixture_path_for_namespace(target, connector_id, dataset_id, req_hash)
            planned.append((fixture, fixture_path))
        for fixture, fixture_path in planned:
            fixture.write(fixture_path)

        return target


def collect_fixtures_from_dir(fixture_root: Path) -> list[dict[str, Any]]:
    """Collect all SimulatorFixture JSON files from a fixture directory tree.

    Scans the APISimulator layout: fixture_root/<connector_id>/<dataset_id>/<hash>.json
    Returns a list of fixture dicts suitable for RecordSession.fixtures.
    """
    from polisyos.fabric.connectors.testing.simulator import SimulatorFixture

    fixtures: list[dict[str, Any]] = []
    if not fixture_root.exists():
        return fixtures

    for json_file in sorted(fixture_root.rglob("*.json")):
        try:
            fixture = SimulatorFixture.read(json_file)
            fixtures.append(fixture.to_dict())
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Skipping invalid fixture %s: %s", json_file, exc)

    return fixtures


def make_record_session(
    *,
    session_id: str,
    fixture_root: Path,
    connector_datasets: list[dict[str, str]] | None = None,
) -> RecordSession:
    """Build a RecordSession from collected fixtures on disk."""
    fixtures = collect_fixtures_from_dir(fixture_root)
    return RecordSession(
        session_id=session_id,
        fixtures=fixtures,
        connector_datasets=connector_datasets or [],
        recorded_at=datetime.now(UTC).isoformat(),
    )


__all__ = [
    "RecordSession",
    "ReplayStore",
    "collect_fixtures_from_dir",
    "make_record_session",
]
