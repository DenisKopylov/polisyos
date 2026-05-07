from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / ".polisyos"


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_phase2_3_schema_and_contract_register_runtime_root_entries() -> None:
    local = _read_toml("architecture/local_runtime_state.toml")
    layout = _read_toml("architecture/runtime_state_layout.toml")
    schema = RUNTIME_ROOT / "SCHEMA.md"

    assert schema.exists()
    assert local["local_runtime_state"]["schema_document_status"] == "present"
    assert layout["runtime_state_layout"]["schema_document_status"] == "present"
    assert layout["runtime_state_layout"]["default_gate_mode"] == "fail_closed"

    local_registered = set(local["local_runtime_state"]["registered_first_level_entries"])
    layout_registered = set(layout["runtime_state_layout"]["registered_first_level_entries"])
    legacy = set(layout["runtime_state_layout"]["legacy_first_level_entries"])
    assert local_registered == layout_registered
    assert {
        "audits",
        "cas",
        "decision_validity",
        "evicted",
        "production_data",
        "provider_verification",
        "reports",
        "runtime",
        "runs",
        "search_registry",
        "security",
    } <= local_registered
    assert {"artifacts", "cas_cache", "cas-readme-check", "live_gonka_smoke.json"} <= legacy

    physical = {path.name for path in RUNTIME_ROOT.iterdir()} - {"SCHEMA.md"}
    assert physical <= local_registered, sorted(physical - local_registered)
    assert physical.isdisjoint(legacy), sorted(physical & legacy)

    schema_text = schema.read_text(encoding="utf-8")
    for entry in sorted(physical | {"facts", "idempotency", "keys", "scholar_cache", "state"}):
        assert f"`{entry}" in schema_text or f"`{entry}/`" in schema_text


def test_phase2_3_every_state_class_has_layout_slot_and_cleanup_policy() -> None:
    local = _read_toml("architecture/local_runtime_state.toml")
    layout = _read_toml("architecture/runtime_state_layout.toml")

    classes = {item["id"]: item for item in local["state_class"]}
    slots = {item["id"]: item for item in layout["state_slot"]}
    aliases = {item["path"]: item for item in layout["legacy_alias"]}

    for slot_id, state_class in classes.items():
        assert state_class["paths"], slot_id
        assert state_class["cleanup_command"], slot_id
        if slot_id != "artifact_cache":
            assert slot_id in slots, slot_id

    assert aliases[".polisyos/artifacts"]["canonical_path"] == ".polisyos/cas/_cache/artifacts"
    assert aliases[".polisyos/cas_cache"]["canonical_path"] == ".polisyos/cas/_cache"
    assert aliases[".polisyos/cas-readme-check"]["canonical_path"] == ".polisyos/cas/_readme_check"
    assert (
        aliases[".polisyos/live_gonka_smoke.json"]["canonical_path"]
        == ".polisyos/provider_verification/live_gonka_smoke.json"
    )

    protected = set(local["local_runtime_state"]["protected_cleanup_slots"])
    assert "production_data" in protected
    assert "cas" in protected
    assert "keys" in protected


def test_phase2_3_runtime_state_migration_slots_are_physical() -> None:
    layout = _read_toml("architecture/runtime_state_layout.toml")
    required = {
        "audit",
        "idempotency",
        "decision_validity",
        "search_registry",
        "provider_verification",
        "persisted_local_state",
    }
    migration_slots = {item["id"]: item for item in layout["migration_slot"]}

    assert required <= set(migration_slots)
    for slot_id in required:
        target = REPO_ROOT / migration_slots[slot_id]["target_path"]
        assert target.exists(), slot_id
        assert (target / "README.md").exists(), slot_id


def test_phase2_3_cas_paths_are_canonicalized_locally_when_present() -> None:
    cas = RUNTIME_ROOT / "cas"
    if not cas.exists():
        return

    assert (cas / "_cache").exists()
    assert (cas / "_readme_check").exists()
    assert not (RUNTIME_ROOT / "artifacts").exists()
    assert not (RUNTIME_ROOT / "cas_cache").exists()
    assert not (RUNTIME_ROOT / "cas-readme-check").exists()
    assert not (RUNTIME_ROOT / "live_gonka_smoke.json").exists()
