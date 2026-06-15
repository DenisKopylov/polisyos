from __future__ import annotations

import json
from pathlib import Path

from polisyos.runtime.quality.required_reference_resolver import resolve_required_ref


def _sha256(value: str) -> str:
    return f"sha256:{value}"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolved_ref_requires_pointer_to_existing_payload(tmp_path: Path) -> None:
    artifact = tmp_path / "architecture/policy_design_case/source.json"
    _write_json(
        artifact,
        {
            "bindings": {
                "present": {
                    "value": "grounded",
                    "producer_ref": "producer://g1/source-binding",
                    "producer_type": "source_binding",
                    "producer_root_refs": ["root://g1"],
                    "produced_at": "2026-06-12T00:00:00Z",
                    "schema_version": "schema.v1",
                    "rule_version": "rule.v1",
                    "authority_boundary": {"may_not_use_for": ["claim_authority"]},
                }
            }
        },
    )

    resolved = resolve_required_ref(
        tmp_path,
        "repo://architecture/policy_design_case/source.json#bindings/missing",
        authority_bearing=True,
    )

    assert resolved.exists is False
    assert "required_ref_pointer_missing" in resolved.issue_codes
    assert resolved.artifact_path == "architecture/policy_design_case/source.json"


def test_placeholder_digest_is_blocker_not_warning(tmp_path: Path) -> None:
    artifact = tmp_path / "architecture/policy_design_case/source.json"
    _write_json(
        artifact,
        {
            "bindings": {
                "present": {
                    "producer_ref": "producer://g1/source-binding",
                    "producer_type": "source_binding",
                    "producer_root_refs": ["root://g1"],
                }
            }
        },
    )

    resolved = resolve_required_ref(
        tmp_path,
        "repo://architecture/policy_design_case/source.json#bindings/present",
        expected_content_hash=_sha256("a" * 64),
    )

    assert resolved.exists is False
    assert "required_ref_placeholder_digest" in resolved.issue_codes


def test_authority_bearing_inline_shape_without_producer_ref_fails(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "architecture/policy_design_case/source.json"
    _write_json(
        artifact,
        {
            "bindings": {
                "shape_only": {
                    "schema_version": "schema.v1",
                    "rule_version": "rule.v1",
                    "authority_boundary": {"may_not_use_for": ["claim_authority"]},
                }
            }
        },
    )

    resolved = resolve_required_ref(
        tmp_path,
        "repo://architecture/policy_design_case/source.json#bindings/shape_only",
        authority_bearing=True,
    )

    assert resolved.exists is False
    assert "required_ref_producer_ref_missing" in resolved.issue_codes


def test_derivation_only_input_cannot_supply_positive_evidence(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "architecture/policy_design_case/source.json"
    _write_json(
        artifact,
        {
            "evidence": [
                {
                    "ref": "evidence://derived",
                    "producer_ref": "producer://derived-summary",
                    "producer_type": "derivation",
                    "producer_root_refs": ["root://summary"],
                }
            ]
        },
    )

    resolved = resolve_required_ref(
        tmp_path,
        "repo://architecture/policy_design_case/source.json#evidence/0",
        authority_bearing=True,
        allowed_producer_types=("source_binding", "observed_source"),
    )

    assert resolved.exists is False
    assert "required_ref_producer_type_invalid" in resolved.issue_codes
