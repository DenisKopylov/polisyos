"""CAS-backed cursor persistence for incremental ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import CursorState

logger = get_logger(__name__)


class CursorStore:
    """Read/write CursorState artifacts to CAS with a lightweight index."""

    _INDEX_FILE = "cursor_index.json"

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store
        self._index_path = Path(store.root) / self._INDEX_FILE
        self._index: dict[str, str] = self._load_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_cursor(self, cursor: CursorState) -> ArtifactRef:
        """Persist cursor state to CAS and update index."""
        ref = self._store.put_json(
            cursor.model_dump(mode="json"),
            PutOptions(
                kind="fabric.cursor_state",
                media_type="application/json",
                schema=SchemaInfo(name="cursor_state", version="1.0"),
            ),
        )
        self._index[cursor.cursor_id] = str(ref.artifact_id)
        self._save_index()
        return ref

    def load_cursor(self, artifact_id: ArtifactID) -> CursorState:
        """Load cursor state from CAS by artifact ID."""
        raw = self._store.get_bytes(artifact_id)
        data = from_canonical_bytes(raw)
        return CursorState.model_validate(data)

    def find_latest_cursor(
        self, connector_id: str, dataset_id: str,
    ) -> CursorState | None:
        """Find the most recent cursor for a connector:dataset pair."""
        cursor_id = f"{connector_id}:{dataset_id}"
        artifact_id_str = self._index.get(cursor_id)
        if not artifact_id_str:
            return None
        try:
            aid = ArtifactID.model_validate(artifact_id_str)
            return self.load_cursor(aid)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            logger.debug(
                "Failed to load cursor for %s:%s (artifact=%s)",
                connector_id, dataset_id, artifact_id_str, exc_info=True,
            )
            return None

    def list_cursors(self) -> list[CursorState]:
        """List all known cursors from the index."""
        result: list[CursorState] = []
        for cursor_id, artifact_id_str in self._index.items():
            try:
                aid = ArtifactID.model_validate(artifact_id_str)
                result.append(self.load_cursor(aid))
            except (FileNotFoundError, OSError, TypeError, ValueError):
                logger.debug(
                    "Failed to load cursor %s (artifact=%s)",
                    cursor_id, artifact_id_str, exc_info=True,
                )
                continue
        return result

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, str]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._index, sort_keys=True, indent=2))
        tmp.rename(self._index_path)


__all__ = ["CursorStore"]
