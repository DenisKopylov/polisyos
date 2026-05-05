from __future__ import annotations

import json

import yaml
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import (
    load_model_spec,
    load_policy_spec,
    load_problem_frame,
    load_trinity_bundle,
)

ZERO_REF = "sha256:" + "0" * 64


def test_load_problem_frame_from_json_bytes() -> None:
    payload = {
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
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_problem_frame(data)
    assert model.problem_id == "pf_demo"


def test_load_policy_spec_from_yaml_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "policy_id": "ps_demo",
        "interventions": [],
        "mechanism_bindings": [],
        "parameters": [],
        "labels": [],
        "notes": [],
    }
    data = yaml.safe_dump(payload).encode("utf-8")
    model = load_policy_spec(data)
    assert model.policy_id == "ps_demo"


def test_load_model_spec_from_json_bytes() -> None:
    payload = {
        "schema_version": "1.0",
        "model_id": "ms_demo",
        "data_snapshot_ref": ZERO_REF,
        "registry_bundle_ref": None,
        "assumptions": [],
        "labels": [],
        "notes": [],
    }
    data = json.dumps(payload).encode("utf-8")
    model = load_model_spec(data)
    assert model.model_id == "ms_demo"


def test_load_trinity_bundle_from_mapping() -> None:
    payload = {
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
    bundle = load_trinity_bundle(payload)
    assert isinstance(bundle, TrinityBundle)
