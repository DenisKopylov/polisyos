from __future__ import annotations

import json

import yaml

from polisyos.ir.legacy.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.legacy.trinity_v0 import (
    ModelSpec as LegacyModelSpec,
    PolicySpec as LegacyPolicySpec,
    ProblemFrame as LegacyProblemFrame,
    TrinityBundle as LegacyTrinityBundle,
)
from polisyos.ir.loaders import load_trinity_bundle
from polisyos.ir.trinity.loaders import (
    load_model_spec,
    load_policy_spec,
    load_problem_frame,
)
from polisyos.ir.trinity import TrinityBundle

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


def test_load_trinity_bundle_from_legacy_surface() -> None:
    legacy = PolicySurfaceIR(
        schema_version="2.0",
        semantic=PolicySemantic(
            context_snapshot_ref=ZERO_REF,
            registry_bundle_ref=None,
        ),
    )
    bundle, report = load_trinity_bundle(legacy.model_dump())
    assert isinstance(bundle, TrinityBundle)
    assert report is not None
    assert report.source_format == "policy_surface_ir"


def test_load_trinity_bundle_from_legacy_bundle() -> None:
    legacy_bundle = LegacyTrinityBundle(
        problem_frame=LegacyProblemFrame(),
        policy_spec=LegacyPolicySpec(),
        model_spec=LegacyModelSpec(data_snapshot_ref=ZERO_REF),
    )
    bundle, report = load_trinity_bundle(legacy_bundle.model_dump())
    assert isinstance(bundle, TrinityBundle)
    assert report is not None
    assert report.source_format == "legacy_trinity_bundle_v0"
