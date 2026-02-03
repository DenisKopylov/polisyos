from polisyos.ir.loaders import load_policy
from polisyos.ir.legacy.surface import PolicySurfaceIR

ZERO_REF = "sha256:" + "0" * 64


def _surface_payload():
    return {
        "schema_version": "2.0",
        "semantic": {
            "context_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "time_semantics": None,
            "objectives": [],
            "interventions": [],
            "constraints": [],
            "notes": [],
        },
    }


def test_load_policy_passthrough_surface():
    policy = PolicySurfaceIR.model_validate(_surface_payload())
    loaded = load_policy(policy)
    assert loaded is policy


def test_load_policy_from_mapping_surface():
    payload = _surface_payload()
    loaded = load_policy(payload)
    assert isinstance(loaded, PolicySurfaceIR)
    assert loaded.semantic.context_snapshot_ref == ZERO_REF
