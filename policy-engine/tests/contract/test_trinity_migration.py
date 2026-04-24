"""Contract tests for Trinity-only migration helpers."""

from __future__ import annotations

import pytest

from polisyos.ir.loaders import PolicyLoadError, load_policy, load_trinity
from polisyos.ir.migrations.trinity_migration import is_trinity_migrated, split_to_bundle
from polisyos.ir.trinity import TrinityBundle

ZERO_REF = "sha256:" + "0" * 64


def _bundle_payload() -> dict:
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_test",
            "domain": "custom",
            "objectives": [],
            "kpis": [],
            "success_criteria": [],
            "hard_constraints": [],
            "soft_constraints": [],
            "stakeholders": [],
            "labels": [],
            "notes": [],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "ps_test",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_test",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_split_to_bundle_accepts_mapping() -> None:
    bundle = split_to_bundle(_bundle_payload())
    assert isinstance(bundle, TrinityBundle)
    assert bundle.policy_spec.policy_id == "ps_test"


def test_is_trinity_migrated_true_for_valid_bundle() -> None:
    assert is_trinity_migrated(_bundle_payload()) is True


def test_is_trinity_migrated_false_for_invalid_payload() -> None:
    assert is_trinity_migrated({"schema_version": "2.0", "semantic": {}}) is False


def test_load_policy_returns_trinity_bundle() -> None:
    bundle = load_policy(_bundle_payload())
    assert isinstance(bundle, TrinityBundle)


def test_load_trinity_returns_trinity_bundle() -> None:
    bundle = load_trinity(_bundle_payload())
    assert isinstance(bundle, TrinityBundle)


def test_load_policy_rejects_non_mapping_payload() -> None:
    with pytest.raises(PolicyLoadError):
        load_policy("not a valid bundle")
