from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path as PathType

from polisyos.runtime.quality.projection_semantics import (
    assert_policy_design_projection_not_authority,
)
from polisyos.runtime.quality.wave2_walking_skeleton import (
    build_wave2_policy_design_case_walking_skeleton,
    persist_wave2_policy_design_case_walking_skeleton,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
COMMITTED_I2_BUNDLE_DIR = (
    REPO_ROOT / "architecture/policy_design_case/wave2_i2_walking_skeleton"
)


def test_wave2_i2_walking_skeleton_traverses_runtime_seam(tmp_path: PathType) -> None:
    skeleton = build_wave2_policy_design_case_walking_skeleton()

    assert skeleton["schema_version"] == "policyos.runtime.policy_design_case.wave2_i2.v1"
    assert skeleton["status"] == "pass"
    assert skeleton["integration_slice"] == "I2"

    artifacts = skeleton["artifacts"]
    concept_spine = artifacts["concept_spine"]
    handshake_ledger = artifacts["producer_handshake_ledger"]
    claim_registry = artifacts["claim_registry"]
    closeout = artifacts["closeout_verdict"]
    projection = artifacts["typed_projection"]
    semantic_negative = skeleton["semantic_negative"]

    assert concept_spine["status"] == "pass"
    assert concept_spine["bridge_authority"]["authority_role"] == "closeout_input"
    assert handshake_ledger["status"] == "pass"
    assert claim_registry["status"] == "pass"
    assert closeout["status"] == "closed"
    assert closeout["can_closeout"] is True
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert_policy_design_projection_not_authority(projection)

    claim_row = claim_registry["claims"][0]
    assert claim_row["concept_spine_ref"] == concept_spine["concept_spine_ref"]
    assert claim_row["producer_handshake_ledger_ref"] == (
        handshake_ledger["producer_handshake_ledger_ref"]
    )
    assert claim_row["producer_handshake_refs"] == [
        handshake_ledger["records"][0]["handshake_id"]
    ]

    handoff_ledger = artifacts["evidence_spine_handoff_ledger"]
    assert handoff_ledger["status"] == "pass"
    assert {
        handoff["bridge_authority_ref"] for handoff in handoff_ledger["handoffs"]
    } >= {
        concept_spine["bridge_authority"]["bridge_ref"],
        handshake_ledger["records"][0]["bridge_authority"]["bridge_ref"],
    }

    assert semantic_negative["status"] == "fail"
    assert semantic_negative["negative_control"] == "historical_prior_claim_evidence_slot"
    assert "historical_prior_ref_not_admissible_as_claim_evidence" in {
        issue["code"] for issue in semantic_negative["issues"]
    }

    manifest = persist_wave2_policy_design_case_walking_skeleton(
        skeleton,
        output_dir=tmp_path / "wave2-i2",
    )

    assert manifest["status"] == "pass"
    assert manifest["artifact_count"] >= 8
    assert (tmp_path / "wave2-i2" / "manifest.json").is_file()
    persisted_manifest = json.loads(
        (tmp_path / "wave2-i2" / "manifest.json").read_text(encoding="utf-8")
    )
    assert persisted_manifest["integration_slice"] == "I2"
    assert persisted_manifest["refs"]["closeout_verdict"] == closeout["authority_envelope"][
        "reader_contract"
    ]


def test_wave2_i2_committed_bundle_matches_fresh_runtime_generation(
    tmp_path: PathType,
) -> None:
    skeleton = build_wave2_policy_design_case_walking_skeleton(
        include_projection_closeout_negative=True,
    )
    generated_dir = tmp_path / "wave2-i2"

    persist_wave2_policy_design_case_walking_skeleton(
        skeleton,
        output_dir=generated_dir,
    )

    generated_files = sorted(path.name for path in generated_dir.glob("*.json"))
    committed_files = sorted(path.name for path in COMMITTED_I2_BUNDLE_DIR.glob("*.json"))
    assert generated_files == committed_files
    for filename in generated_files:
        assert (generated_dir / filename).read_text(encoding="utf-8") == (
            COMMITTED_I2_BUNDLE_DIR / filename
        ).read_text(encoding="utf-8"), filename


def test_wave2_i2_negative_rejects_projection_as_closeout_substitute() -> None:
    skeleton = build_wave2_policy_design_case_walking_skeleton(
        include_projection_closeout_negative=True,
    )

    negative = skeleton["projection_closeout_negative"]

    assert negative["status"] == "blocked"
    assert negative["can_closeout"] is False
    assert "closeout_projection_only_not_authority" in {
        issue["code"] for issue in negative["issues"]
    }
