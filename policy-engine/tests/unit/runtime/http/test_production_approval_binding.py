from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.production_approval_binding import (
    resolve_production_approval_scorecard,
)


def test_unavailable_explicit_scorecard_ref_does_not_fall_back_to_inline_cas_reference(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    persisted = store.put_json(
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "run_id": "run-current",
            "quality_status": "pass",
            "quality_gates": [],
            "evidence_refs": {},
        },
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    inline_ref = str(persisted.artifact_id)

    resolved = resolve_production_approval_scorecard(
        body={"quality_scorecard_ref": inline_ref},
        control_service=None,
        run_id="run-current",
        store=store,
    )
    assert resolved.reference == inline_ref
    assert resolved.run_id == "run-current"

    with pytest.raises(RuntimeHTTPError) as exc_info:
        resolve_production_approval_scorecard(
            body={
                "quality_scorecard_ref": "sha256:" + "f" * 64,
                "quality_scorecard": {"quality_scorecard_ref": inline_ref},
            },
            control_service=None,
            run_id="run-current",
            store=store,
        )

    assert exc_info.value.code == "quality_scorecard_ref_unavailable"
