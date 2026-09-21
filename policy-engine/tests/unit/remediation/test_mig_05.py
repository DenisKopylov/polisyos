"""Characterization corpus for the Common and IR migration profiles.

These tests intentionally keep the two public runners side by side.  The
future shared engine may remove duplicated traversal code, but it must not
erase the observable copy, stamping, identity, or error differences recorded
here.  Data Forge graph migration is deliberately outside this corpus (LK25).
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, cast

import pytest

from polisyos.common.migrations import base as common_migrations
from polisyos.ir.migrations import base as ir_migrations

pytestmark = pytest.mark.unit

Callback = Callable[[dict[str, Any]], Any]


def _payload(version: object = "0.1") -> dict[str, Any]:
    return {
        "schema_version": version,
        "nested": {"x": 0},
        "marker": "unchanged",
    }


def _register_common(
    artifact: str,
    from_version: str,
    to_version: str,
    callback: Callback,
) -> None:
    common_migrations.register_migration(artifact, from_version, to_version)(
        cast("common_migrations.MigrationFn", callback)
    )


def _register_ir(
    artifact: str,
    from_version: str,
    to_version: str,
    callback: Callback,
) -> None:
    ir_migrations.register_migration(
        artifact,
        from_version,
        to_version,
        compatibility=ir_migrations.CompatibilityMode.FULL,
    )(cast("ir_migrations.MigrationFn", callback))


def _two_step_corpus(
    observed: list[tuple[str, object]],
) -> tuple[Callback, Callback]:
    def first(data: dict[str, Any]) -> dict[str, Any]:
        observed.append(("first", data["schema_version"]))
        data["nested"]["x"] = 7
        return _return_without_schema_version(data)

    def second(data: dict[str, Any]) -> dict[str, Any]:
        observed.append(("second", data["schema_version"]))
        data["nested"]["step2"] = True
        return _return_without_schema_version(data)

    return first, second


def _mutate_then_fail(data: dict[str, Any]) -> dict[str, Any]:
    data["nested"]["x"] = 99
    raise RuntimeError("intentional callback failure")


def _return_conflicting_version(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = "9.9"
    return data


def _return_without_schema_version(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key != "schema_version"}


def _return_bad_result(data: dict[str, Any]) -> Any:
    del data
    return ["not", "a", "mapping"]


def test_common_profile_isolates_nested_mutation_and_stamps_each_step() -> None:
    observed: list[tuple[str, object]] = []
    first, second = _two_step_corpus(observed)
    _register_common("mig05.common.two_step", "0.1", "0.2", first)
    _register_common("mig05.common.two_step", "0.2", "0.3", second)

    original = _payload()
    before = deepcopy(original)
    migrated = common_migrations.migrate_artifact(
        original,
        artifact="mig05.common.two_step",
        target_version="0.3",
    )

    assert observed == [("first", "0.1"), ("second", "0.2")]
    assert original == before
    assert migrated["schema_version"] == "0.3"
    assert migrated["nested"] == {"x": 7, "step2": True}


def test_ir_profile_preserves_live_nested_mutation_across_two_steps() -> None:
    observed: list[tuple[str, object]] = []
    first, second = _two_step_corpus(observed)
    _register_ir("mig05.ir.two_step", "0.1", "0.2", first)
    _register_ir("mig05.ir.two_step", "0.2", "0.3", second)

    original = _payload()
    migrated = ir_migrations.migrate_artifact(
        original,
        artifact="mig05.ir.two_step",
        target_version="0.3",
    )

    assert observed == [("first", "0.1"), ("second", "0.2")]
    assert original["schema_version"] == "0.1"
    assert original["nested"] == {"x": 7, "step2": True}
    assert migrated["schema_version"] == "0.3"
    assert migrated["nested"] is original["nested"]


def test_common_profile_isolates_nested_mutation_before_callback_failure() -> None:
    _register_common("mig05.common.failure", "0.1", "0.2", _mutate_then_fail)
    original = _payload()
    before = deepcopy(original)

    with pytest.raises(RuntimeError, match="intentional callback failure"):
        common_migrations.migrate_artifact(
            original,
            artifact="mig05.common.failure",
            target_version="0.2",
        )

    assert original == before


def test_ir_profile_exposes_nested_mutation_before_callback_failure() -> None:
    _register_ir("mig05.ir.failure", "0.1", "0.2", _mutate_then_fail)
    original = _payload()

    with pytest.raises(RuntimeError, match="intentional callback failure"):
        ir_migrations.migrate_artifact(
            original,
            artifact="mig05.ir.failure",
            target_version="0.2",
        )

    assert original["nested"]["x"] == 99


def test_common_noop_returns_deep_copy() -> None:
    original = _payload("0.3")

    migrated = common_migrations.migrate_artifact(
        original,
        artifact="mig05.common.noop",
        target_version="0.3",
    )

    assert migrated == original
    assert migrated is not original
    assert migrated["nested"] is not original["nested"]


def test_ir_noop_returns_same_object() -> None:
    original = _payload("0.3")

    migrated = ir_migrations.migrate_artifact(
        original,
        artifact="mig05.ir.noop",
        target_version="0.3",
    )

    assert migrated is original


def test_common_stamps_registered_target_over_callback_version() -> None:
    _register_common(
        "mig05.common.stamp",
        "0.1",
        "0.2",
        _return_conflicting_version,
    )

    migrated = common_migrations.migrate_artifact(
        _payload(),
        artifact="mig05.common.stamp",
        target_version="0.2",
    )

    assert migrated["schema_version"] == "0.2"


def test_ir_rejects_conflicting_callback_version_with_public_exception() -> None:
    _register_ir("mig05.ir.stamp", "0.1", "0.2", _return_conflicting_version)

    with pytest.raises(ir_migrations.MigrationSchemaVersionError) as raised:
        ir_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.ir.stamp",
            target_version="0.2",
        )

    assert type(raised.value) is ir_migrations.MigrationSchemaVersionError


def test_common_requires_string_source_version() -> None:
    with pytest.raises(TypeError, match="must be a string") as raised:
        common_migrations.migrate_artifact(
            _payload(1),
            artifact="mig05.common.source_type",
            target_version="0.2",
        )

    assert type(raised.value) is TypeError


def test_ir_coerces_source_version_to_string_for_routing() -> None:
    _register_ir(
        "mig05.ir.source_type",
        "1",
        "2",
        _return_without_schema_version,
    )

    migrated = ir_migrations.migrate_artifact(
        _payload(1),
        artifact="mig05.ir.source_type",
        target_version="2",
    )

    assert migrated["schema_version"] == "2"


def test_common_rejects_bad_callback_result_type() -> None:
    _register_common("mig05.common.bad_result", "0.1", "0.2", _return_bad_result)

    with pytest.raises(TypeError, match="expected dict") as raised:
        common_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.common.bad_result",
            target_version="0.2",
        )

    assert type(raised.value) is TypeError


def test_ir_rejects_bad_callback_result_with_public_exception() -> None:
    _register_ir("mig05.ir.bad_result", "0.1", "0.2", _return_bad_result)

    with pytest.raises(ir_migrations.MigrationError, match="must return a dict") as raised:
        ir_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.ir.bad_result",
            target_version="0.2",
        )

    assert type(raised.value) is ir_migrations.MigrationError


def test_common_missing_edge_and_cycle_remain_distinguishable() -> None:
    with pytest.raises(ValueError, match="No migrator"):
        common_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.common.missing",
            target_version="0.2",
        )

    _register_common("mig05.common.cycle", "0.1", "0.2", lambda data: data)
    _register_common("mig05.common.cycle", "0.2", "0.1", lambda data: data)
    with pytest.raises(ValueError, match="Migration loop detected"):
        common_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.common.cycle",
            target_version="0.3",
        )


def test_ir_missing_edge_and_cycle_remain_distinguishable() -> None:
    with pytest.raises(ValueError, match="No migrator"):
        ir_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.ir.missing",
            target_version="0.2",
        )

    _register_ir("mig05.ir.cycle", "0.1", "0.2", _return_without_schema_version)
    _register_ir("mig05.ir.cycle", "0.2", "0.1", _return_without_schema_version)
    with pytest.raises(ValueError, match="Migration loop detected"):
        ir_migrations.migrate_artifact(
            _payload(),
            artifact="mig05.ir.cycle",
            target_version="0.3",
        )


def test_common_duplicate_registration_replaces_previous_callback() -> None:
    called: list[str] = []

    def old_callback(data: dict[str, Any]) -> dict[str, Any]:
        del data
        raise AssertionError("replaced callback was called")

    def new_callback(data: dict[str, Any]) -> dict[str, Any]:
        called.append("new")
        return _return_without_schema_version(data)

    _register_common("mig05.common.duplicate", "0.1", "0.2", old_callback)
    _register_common("mig05.common.duplicate", "0.1", "0.2", new_callback)

    common_migrations.migrate_artifact(
        _payload(),
        artifact="mig05.common.duplicate",
        target_version="0.2",
    )

    assert called == ["new"]


def test_ir_duplicate_registration_replaces_previous_callback() -> None:
    called: list[str] = []

    def old_callback(data: dict[str, Any]) -> dict[str, Any]:
        del data
        raise AssertionError("replaced callback was called")

    def new_callback(data: dict[str, Any]) -> dict[str, Any]:
        called.append("new")
        return _return_without_schema_version(data)

    _register_ir("mig05.ir.duplicate", "0.1", "0.2", old_callback)
    _register_ir("mig05.ir.duplicate", "0.1", "0.2", new_callback)

    ir_migrations.migrate_artifact(
        _payload(),
        artifact="mig05.ir.duplicate",
        target_version="0.2",
    )

    assert called == ["new"]


def test_real_common_manifest_callback_remains_registered_and_isolated() -> None:
    from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION

    original = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
    }
    before = deepcopy(original)

    migrated = common_migrations.migrate_artifact(
        original,
        artifact="dataset_manifest",
        target_version=MANIFEST_CURRENT_VERSION,
    )

    assert original == before
    assert migrated["schema_version"] == MANIFEST_CURRENT_VERSION
    assert migrated["dataset_name"] == "baseline"
    assert migrated["raw_hash"] == "sha256:abc"


def _canonical_trinity_payload() -> dict[str, Any]:
    zero_ref = "sha256:" + "0" * 64
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_mig05",
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
            "policy_id": "ps_mig05",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_mig05",
            "data_snapshot_ref": zero_ref,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_real_ir_callback_remains_registered_with_its_ir_owner() -> None:
    from polisyos.ir.migrations.policy_ir import migrate_policy_ir_identity

    migrated = migrate_policy_ir_identity(_canonical_trinity_payload())

    assert migrated["schema_version"] == "1.0"
    assert migrated["policy_spec"]["policy_id"] == "ps_mig05"


def test_shared_engine_annotations_resolve_for_runtime_introspection() -> None:
    from typing import get_origin, get_type_hints

    from polisyos.common.migrations._engine import (
        LinearMigrationProfile,
        run_linear_migration,
    )

    profile_hints = get_type_hints(LinearMigrationProfile)
    runner_hints = get_type_hints(run_linear_migration)

    callable_fields = ("prepare", "no_op", "edge_target", "apply_step")
    assert set(callable_fields) <= profile_hints.keys()
    assert all(get_origin(profile_hints[field]) is Callable for field in callable_fields)
    assert get_origin(runner_hints["edge_lookup"]) is Callable
    assert "profile" in runner_hints
