from __future__ import annotations

# ruff: noqa: S101
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.rule_evolution import (
    RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
    RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION,
    RULE_EVOLUTION_REPLAY_SCHEMA_VERSION,
    build_rule_evolution_registry,
    build_rule_evolution_replay_context,
    logic_hash_for_rule,
    persist_rule_evolution_registry,
    public_rule_evolution_annotation,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _registry(*, threshold: float, requirement_id: str = "req.credit_support") -> dict[str, object]:
    return build_rule_evolution_registry(
        registry_id=f"rule-registry-{requirement_id}",
        version="2026.05",
        effective_at="2026-05-22T00:00:00+00:00",
        rule_refs=[
            {
                "requirement_id": requirement_id,
                "logic": {
                    "predicate": "msme_liquidity_gap_ratio_at_least",
                    "threshold": threshold,
                    "authority_level": "production",
                },
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
                "provenance_ref": _sha("a"),
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation",
                "version": "2026.05",
                "ref": _sha("b"),
                "logic_hash": logic_hash_for_rule({"terms": ["admissible", "limited"]}),
            }
        ],
        evidence_ref=_sha("c"),
        runtime_event_ref="event://rule-evolution/2026-05",
    )


def test_lossless_requirement_id_alias_is_compatible_but_still_annotated() -> None:
    old_registry = _registry(threshold=0.2)

    registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-06",
        version="2026.06",
        effective_at="2026-06-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic_hash": old_registry["rule_refs"][0]["logic_hash"],
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
                "provenance_ref": _sha("d"),
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
                "reason": "Canonical id namespace migration.",
            }
        ],
        evidence_ref=_sha("e"),
        runtime_event_ref="event://rule-evolution/2026-06",
    )

    assert registry["schema_version"] == RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION
    assert registry["status"] == "pass"
    assert registry["alias_remaps"][0]["decision"] == "lossless_alias_migration"
    assert registry["alias_remaps"][0]["compatible_migration"] is True
    assert registry["alias_remaps"][0]["semantic_change_detected"] is False
    assert registry["revalidation_state"]["state"] == "not_required"
    assert registry["public_annotation"]["schema_version"] == (
        RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION
    )
    assert registry["public_annotation"]["annotation_required"] is True
    assert registry["public_annotation"]["silent_upgrade_allowed"] is False


def test_requirement_id_alias_with_changed_logic_hash_requires_revalidation() -> None:
    old_registry = _registry(threshold=0.2)
    tightened_logic = {
        "predicate": "msme_liquidity_gap_ratio_at_least",
        "threshold": 0.35,
        "authority_level": "production",
    }

    registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-07",
        version="2026.07",
        effective_at="2026-07-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic": tightened_logic,
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
                "provenance_ref": _sha("f"),
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
                "reason": "Tightened production threshold.",
            }
        ],
        evidence_ref=_sha("1"),
        runtime_event_ref="event://rule-evolution/2026-07",
    )

    remap = registry["alias_remaps"][0]
    assert registry["status"] == "blocked"
    assert remap["decision"] == "semantic_rule_change"
    assert remap["compatible_migration"] is False
    assert remap["semantic_change_detected"] is True
    assert remap["source_logic_hash"] != remap["target_logic_hash"]
    assert registry["revalidation_state"]["state"] == "revalidation_required"
    assert registry["revalidation_state"]["affected_requirement_ids"] == [
        "req.credit_support.v2"
    ]
    assert "rule_alias_semantic_change_detected" in {
        issue["code"] for issue in registry["issues"]
    }
    assert registry["public_annotation"]["public_annotation_state"] == "semantic_change"


def test_closed_case_replay_uses_original_logic_when_current_registry_changes() -> None:
    old_registry = _registry(threshold=0.2)
    current_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-07",
        version="2026.07",
        effective_at="2026-07-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic": {
                    "predicate": "msme_liquidity_gap_ratio_at_least",
                    "threshold": 0.35,
                    "authority_level": "production",
                },
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
            }
        ],
        evidence_ref=_sha("2"),
        runtime_event_ref="event://rule-evolution/2026-07",
    )

    replay = build_rule_evolution_replay_context(
        case_id="pdc-closed-001",
        closed_case_rule_registry=old_registry,
        current_rule_registry=current_registry,
        closure_time="2026-05-22T00:00:00+00:00",
        replay_time="2026-07-02T00:00:00+00:00",
    )

    assert replay["schema_version"] == RULE_EVOLUTION_REPLAY_SCHEMA_VERSION
    assert replay["replay_mode"] == "original_logic"
    assert replay["semantic_change_detected"] is True
    assert replay["original_rule_registry_ref"] == old_registry["rule_registry_ref"]
    assert replay["current_rule_registry_ref"] == current_registry["rule_registry_ref"]
    assert replay["original_logic_hashes"]["req.credit_support"] == (
        old_registry["rule_refs"][0]["logic_hash"]
    )
    assert replay["revalidation_state"]["state"] == "legacy_replay_only"
    assert replay["public_annotation"]["legacy_case_annotation"] == (
        "replayed_under_original_logic"
    )


def test_rule_evolution_registry_persists_as_runtime_artifact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = _registry(threshold=0.2)

    ref = persist_rule_evolution_registry(registry, store=store)
    stored = from_canonical_bytes(store.get_bytes(ref.artifact_id))

    assert str(ref.artifact_id).startswith("sha256:")
    assert stored == registry
    assert stored["runtime_authority_envelope"]["authoritative_for"] == [
        "rule_evolution_replay"
    ]


def test_public_annotation_can_be_built_from_existing_registry() -> None:
    old_registry = _registry(threshold=0.2)
    registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-06",
        version="2026.06",
        effective_at="2026-06-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic_hash": old_registry["rule_refs"][0]["logic_hash"],
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
            }
        ],
        evidence_ref=_sha("3"),
        runtime_event_ref="event://rule-evolution/2026-06",
    )

    annotation = public_rule_evolution_annotation(registry)

    assert annotation["schema_version"] == RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION
    assert annotation["registry_id"] == "rule-registry-2026-06"
    assert annotation["annotation_required"] is True
    assert annotation["public_annotation_state"] == "compatible_alias"
    assert annotation["revalidation_state"] == "not_required"
