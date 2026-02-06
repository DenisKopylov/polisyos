from __future__ import annotations

import pytest

from polisyos.ir.loaders import PolicyLoadError, load_policy
from polisyos.ir.trinity import TrinityBundle

ZERO_REF = "sha256:" + "0" * 64


def _bundle_payload() -> dict:
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_demo",
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
            "policy_id": "ps_demo",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_demo",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_load_policy_from_mapping_bundle() -> None:
    loaded = load_policy(_bundle_payload())
    assert isinstance(loaded, TrinityBundle)
    assert loaded.problem_frame.problem_id == "pf_demo"


def test_load_policy_passthrough_bundle() -> None:
    bundle = TrinityBundle.model_validate(_bundle_payload())
    loaded = load_policy(bundle)
    assert loaded is bundle


def test_load_policy_invalid_payload_raises() -> None:
    with pytest.raises(PolicyLoadError):
        load_policy({"schema_version": "2.0", "semantic": {}})
