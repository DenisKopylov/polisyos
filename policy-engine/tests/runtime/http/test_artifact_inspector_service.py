from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService
from polisyos.runtime.http.services.lineage import LineageService


def test_redaction_hook_failure_fails_closed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b"super secret",
        PutOptions(kind="test.preview", media_type="text/plain"),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
        redaction_hooks={
            "test.preview": lambda preview, mode: (_ for _ in ()).throw(RuntimeError("boom"))
        },
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.preview == "[REDACTED]"
