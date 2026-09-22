"""RED characterization for the UDF-01 D4 handoff relocation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import (
    StageId,
    build_default_pipeline_config,
)
from polisyos.data_forge.read_api.ukraine import (
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)
from polisyos.scientist.governance.blueprint_release import _load_d4_governance_request

D4_OUTPUT = "d4_governance_request.json"
EXPECTED_D4_PAYLOAD = {
    "authority_purpose": "producer_governance_handoff",
    "may_not_use_for": [
        "governance_admissibility",
        "release_acceptance",
        "legal_intervention_compilation",
        "method_validity",
    ],
    "required_stage_manifests": {
        "d0_p0": "build_run_d0_p0.json",
        "d2": "build_run_d2.json",
        "d3": "build_run_d3.json",
    },
    "schema_version": "policyos.data_forge.ukraine.d4_governance_request.v1",
}


def _load_d4_builder_surface():
    """Load canonical D4 modules during test execution, not collection."""

    try:
        from polisyos.data_forge.domains.ukraine import builders
        from polisyos.data_forge.domains.ukraine.builders import (
            calibration,
            contracts,
            governance_handoff,
        )
    except ImportError as exc:
        raise AssertionError(
            "UDF-01 canonical D4 owner/contracts must import during test execution"
        ) from exc
    return builders.build_d4_stage, calibration, contracts, governance_handoff


def _build_d4_fixture(root: Path):
    _, _, contracts, governance_handoff = _load_d4_builder_surface()
    config = build_default_pipeline_config(root=root / "ukraine")
    result = governance_handoff.build_d4_stage(config)
    output_path = config.build_root.calibration_dir / "d4" / D4_OUTPUT
    return config, result, output_path, contracts, governance_handoff


def test_canonical_d4_owner_preserves_exact_bytes_and_artifact_contract(tmp_path: Path) -> None:
    (
        config,
        result,
        output_path,
        contracts,
        governance_handoff,
    ) = _build_d4_fixture(tmp_path)

    actual_bytes = output_path.read_bytes()
    expected_bytes = json.dumps(
        EXPECTED_D4_PAYLOAD,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    record = result.outputs[D4_OUTPUT]

    assert governance_handoff.build_d4_stage.__module__ == (
        "polisyos.data_forge.domains.ukraine.builders.governance_handoff"
    )
    assert actual_bytes == expected_bytes
    assert json.loads(actual_bytes) == EXPECTED_D4_PAYLOAD
    assert isinstance(result, contracts.StageBuildResult)
    assert set(result.outputs) == {D4_OUTPUT}
    assert isinstance(record, ArtifactRecord)
    assert Path(record.path) == output_path
    assert record.sha256 == hashlib.sha256(actual_bytes).hexdigest()
    assert record.size_bytes == len(actual_bytes)
    assert result.findings == []
    assert result.metrics == {"producer_handoff_ready": True}
    assert result.manifest_paths == [output_path]
    assert config.build_root.calibration_dir == output_path.parent.parent


def test_calibration_alias_and_package_facade_share_the_canonical_owner() -> None:
    (
        facade_build_d4_stage,
        calibration,
        _,
        governance_handoff,
    ) = _load_d4_builder_surface()
    assert calibration.build_d4_stage is governance_handoff.build_d4_stage
    assert facade_build_d4_stage is governance_handoff.build_d4_stage
    assert calibration.build_d4_stage.__module__ == (
        "polisyos.data_forge.domains.ukraine.builders.governance_handoff"
    )
    assert calibration.__all__ == ("build_d4_stage",)
    assert {
        name for name in vars(calibration) if not name.startswith("_")
    } == {"build_d4_stage"}


def test_d4_contract_and_handoff_namespaces_do_not_leak_common_builders() -> None:
    _, _, contracts, governance_handoff = _load_d4_builder_surface()
    assert contracts.StageBuildResult.__module__ == (
        "polisyos.data_forge.domains.ukraine.builders.contracts"
    )
    assert contracts.__all__ == ("StageBuildResult",)

    assert governance_handoff.__all__ == ("build_d4_stage",)
    assert not hasattr(governance_handoff, "build_d0_p0_stage")
    assert not hasattr(governance_handoff, "MemoryAwareScheduler")
    assert not hasattr(governance_handoff, "FileSystemCAS")
    assert not hasattr(governance_handoff, "np")


def test_d4_handoff_reaches_existing_read_api_and_scientist_consumer(
    tmp_path: Path,
) -> None:
    config, result, output_path, _, _ = _build_d4_fixture(tmp_path)
    manifest_path = config.build_root.manifests_dir / "build_run_d4.json"
    write_manifest(
        manifest_path,
        BuildRunManifest(
            run_id="d4-udf-01-fixture",
            stage_id=StageId.D4,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=[result.outputs[D4_OUTPUT]],
        ),
    )

    store = FileSystemCAS(tmp_path / "cas")
    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=config.build_root.root,
        expected_stage=StageId.D4.value,
        required_outputs=(D4_OUTPUT,),
    )
    admitted_bytes = load_verified_stage_output_bytes(store, receipt, D4_OUTPUT)
    request = _load_d4_governance_request(admitted_bytes)

    assert admitted_bytes == output_path.read_bytes()
    assert receipt.outputs[D4_OUTPUT].sha256 == result.outputs[D4_OUTPUT].sha256
    assert request.model_dump(mode="json") == EXPECTED_D4_PAYLOAD
    assert "governance_admissibility" in request.may_not_use_for
