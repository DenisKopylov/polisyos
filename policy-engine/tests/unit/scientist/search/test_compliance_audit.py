from __future__ import annotations

from polisyos.scientist.methods.search.compliance_audit import (
    scientist_blueprint_compliance_audit,
    validate_scientist_blueprint_artifact_minimality,
    validate_scientist_blueprint_compliance_targets,
)


def test_compliance_audit_covers_cutover_invariants() -> None:
    entries = scientist_blueprint_compliance_audit()
    ids = {entry.invariant_id for entry in entries}

    assert "promotion.hidden_holdout_required" in ids
    assert "promotion.replay_bundle_required" in ids
    assert "policy_runtime.blueprint_only" in ids
    assert "discovery.workflow.first_class" in ids
    assert "cross_layer_refs.cas_pinned" in ids
    assert "benchmarks.registry_authoritative" in ids
    assert "registry.legacy_policy_shortcuts_not_registered" in ids
    assert "public_surface.no_legacy_shortcuts" in ids
    assert "artifacts.minimality_tag_required" in ids
    assert "degraded.synthetic_runtime_caps_readiness" in ids
    assert "discovery.strict_seed_reproducibility_measured" in ids
    assert all(entry.status in {"active", "partial"} for entry in entries)


def test_compliance_audit_targets_resolve() -> None:
    assert validate_scientist_blueprint_compliance_targets() == []


def test_blueprint_artifact_minimality_audit_passes() -> None:
    assert validate_scientist_blueprint_artifact_minimality() == []
