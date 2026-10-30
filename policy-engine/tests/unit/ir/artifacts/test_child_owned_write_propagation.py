"""Owner write boundaries preserve unresolved child effects without laundering them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import (
    ArtifactTenantContextInfo,
    FileSystemCAS,
    ensure_ir_artifact_store,
)
from polisyos.core.run.child_custody import ChildGuardedStageWriteUnknown
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from tests.unit.ir.test_trinity_owner_admission import _bundle

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "stage", ["prepare", "selected_write", "selected_manifest", "selected_read", "standard_write"]
)
def test_owned_trinity_writer_preserves_exact_unknown_outcome(tmp_path: Path, stage: str) -> None:
    """An uncertain entered effect stays the same object through each IR owner boundary."""
    inner = ensure_ir_artifact_store(FileSystemCAS(tmp_path / stage, ownership_enforced=False))
    unknown = ChildGuardedStageWriteUnknown(
        release_id="release-one",
        root_run_id="root-one",
        parent_attempt_id="attempt-one",
        parent_basis_json=b"{}",
        job_intent_locator=None,
    )

    class FaultingStore:
        manifest_reads = 0

        def __getattr__(self, name: str) -> Any:
            return getattr(inner, name)

        def prepare_owned_write_options(self, options: object) -> object:
            if stage == "prepare":
                raise unknown
            return inner.prepare_owned_write_options(options)

        def put_bytes(
            self, data: bytes, opts: object, *, return_selected_profile: bool = False
        ) -> object:
            if stage == "selected_write":
                raise unknown
            return inner.put_bytes(data, opts, return_selected_profile=return_selected_profile)

        def put_json(
            self,
            payload: object,
            opts: object,
            *,
            canon_spec: object = None,
            return_selected_profile: bool = False,
        ) -> object:
            if stage == "standard_write":
                raise unknown
            return inner.put_json(
                payload, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
            )

        def get_manifest_bytes(self, ref: object) -> bytes:
            self.manifest_reads += 1
            if (stage == "selected_manifest" and self.manifest_reads == 1) or (
                stage == "selected_read" and self.manifest_reads == 2
            ):
                raise unknown
            return inner.get_manifest_bytes(ref)

    selected = stage != "standard_write"
    with pytest.raises(ChildGuardedStageWriteUnknown) as caught:
        persist_trinity_bundle_artifact(
            FaultingStore(),
            _bundle(),
            tenant_context=(
                ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
                if selected
                else None
            ),
        )
    assert caught.value is unknown
