from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactID as CoreArtifactID,
)
from polisyos.core.artifacts import (
    FileSystemCAS,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.artifacts.contracts import (
    ArtifactID as IRArtifactID,
)
from polisyos.ir.artifacts.contracts import (
    InputRef as IRInputRef,
)
from polisyos.ir.artifacts.contracts import (
    normalize_input_refs,
)


def test_ir_persistence_preserves_core_and_ir_lineage_profile_identity(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(core_store)
    source_payload = put_json_artifact(
        ir_store,
        {"source": "policy-evidence"},
        kind="test.source",
        schema_name="test.Source",
        schema_version="1.0",
        return_selected_profile=True,
    )
    source_ref = CoreArtifactRef.model_validate(source_payload)
    core_edge = input_ref_from_artifact_ref(source_ref, role="core-source")
    ir_edge = IRInputRef.model_validate(
        core_edge.model_copy(update={"role": "ir-source"}).model_dump(mode="json")
    )

    output_payload = put_json_artifact(
        ir_store,
        {"derived": "consumer-output"},
        kind="test.derived",
        schema_name="test.Derived",
        schema_version="1.0",
        inputs=[core_edge, ir_edge],
        return_selected_profile=True,
    )
    output_id = CoreArtifactID.model_validate(output_payload["artifact_id"])
    manifest = core_store.get_manifest(output_id)

    assert [
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256) for edge in manifest.inputs
    ] == [
        (
            str(CoreArtifactID.model_validate(source_payload["artifact_id"])),
            "core-source",
            source_payload["manifest_profile_sha256"],
        ),
        (
            str(CoreArtifactID.model_validate(source_payload["artifact_id"])),
            "ir-source",
            source_payload["manifest_profile_sha256"],
        ),
    ]
    with pytest.raises(ValidationError):
        normalize_input_refs(
            [
                {
                    "artifact_id": str(IRArtifactID.model_validate(source_payload["artifact_id"])),
                    "role": "untrusted-extra",
                    "authority": "issuer",
                }
            ]
        )
