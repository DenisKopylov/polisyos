"""Characterization corpus for the Common and IR migration profiles.

These tests intentionally keep the two public runners side by side.  The
future shared engine may remove duplicated traversal code, but it must not
erase the observable copy, stamping, identity, or error differences recorded
here. IR registration is stricter than Common: conflicting replacement and
cycle edges refuse at registration. Data Forge graph migration is outside
this corpus (LK25).
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


class _OpaqueMigrationConfiguration:
    """Unsupported semantic configuration, not an empty closure cell."""

    def __init__(self, factor: int) -> None:
        self.factor = factor


def _capture_configuration(configuration: object) -> Callback:
    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        result = _return_without_schema_version(data)
        result["configuration"] = configuration
        return result

    return migrate


@pytest.mark.parametrize("boundary", ["fingerprint", "registration"])
def test_unsupported_closure_configuration_is_not_an_empty_cell(boundary: str) -> None:
    """Distinct opaque captures refuse without changing any registry state."""
    first = _capture_configuration(_OpaqueMigrationConfiguration(2))
    second = _capture_configuration(_OpaqueMigrationConfiguration(7))
    assert first.__code__ is second.__code__
    before = ir_migrations.get_ir_owner_registry_snapshot()
    for callback in (first, second):
        operation = (
            ir_migrations._migration_function_fingerprint
            if boundary == "fingerprint"
            else lambda fn: _register_ir("mig05.ir.opaque_capture", "0.1", "0.2", fn)
        )
        with pytest.raises(
            ir_migrations.MigrationCompatibilityError,
            match="deterministic supported identities",
        ):
            operation(callback)
        assert ir_migrations.get_ir_owner_registry_snapshot() == before


def _empty_capture_callback() -> Callback:
    configuration = "deliberately removed"

    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        if data.get("read_empty_capture"):
            # The deleted free variable deliberately leaves an actual empty cell.
            return {"configuration": configuration}  # noqa: F821
        return _return_without_schema_version(data)

    del configuration
    return migrate


def test_genuinely_empty_closure_keeps_stable_registration_and_actual_execution() -> None:
    """Empty-cell handling stays separate from unsupported-value encoding."""
    first, second = _empty_capture_callback(), _empty_capture_callback()
    assert first.__closure__ is not None and len(first.__closure__) == 1
    with pytest.raises(ValueError, match="Cell is empty"):
        _ = first.__closure__[0].cell_contents
    assert ir_migrations._migration_function_fingerprint(first) == (
        ir_migrations._migration_function_fingerprint(second)
    )
    _register_ir("mig05.ir.empty_capture", "0.1", "0.2", first)
    _register_ir("mig05.ir.empty_capture", "0.1", "0.2", second)
    result = ir_migrations.migrate_artifact(
        _payload(), artifact="mig05.ir.empty_capture", target_version="0.2"
    )
    assert result["schema_version"] == "0.2"
    assert result["marker"] == "unchanged"


@pytest.mark.parametrize(
    ("first_value", "identical_value", "conflicting_value"),
    [(2, 2, 7), ({"factor": 2}, {"factor": 2}, {"factor": 7})],
    ids=["scalar", "mapping"],
)
def test_supported_closure_repeat_and_conflict_keep_the_registered_callback(
    first_value: object,
    identical_value: object,
    conflicting_value: object,
) -> None:
    """Equal supported descriptors reuse; a different capture cannot replace it."""
    artifact = "mig05.ir.supported_capture." + type(first_value).__name__
    first = _capture_configuration(first_value)
    identical = _capture_configuration(identical_value)
    conflicting = _capture_configuration(conflicting_value)
    _register_ir(artifact, "0.1", "0.2", first)
    before = ir_migrations.get_ir_owner_registry_snapshot()
    _register_ir(artifact, "0.1", "0.2", identical)
    assert ir_migrations.get_ir_owner_registry_snapshot() == before
    with pytest.raises(ir_migrations.MigrationCompatibilityError, match="Conflicting migration"):
        _register_ir(artifact, "0.1", "0.2", conflicting)
    after = ir_migrations.get_ir_owner_registry_snapshot()
    assert after == before
    assert after.migration_edges[(artifact, "0.1")].fn is first
    result = ir_migrations.migrate_artifact(_payload(), artifact=artifact, target_version="0.2")
    assert result["configuration"] == first_value
    assert result["schema_version"] == "0.2"


def test_registration_descriptor_does_not_claim_live_semantic_configuration_is_frozen() -> None:
    """Mutable semantic capture remains explicitly outside reproducible identity."""
    configuration = {"factor": 2}

    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        return {"result": data["value"] * configuration["factor"]}

    artifact = "mig05.ir.mutable_semantic_capture"
    _register_ir(artifact, "0.1", "0.2", migrate)
    before = ir_migrations.get_ir_owner_registry_snapshot()
    registration = before.migration_edges[(artifact, "0.1")]
    configuration["factor"] = 7
    assert ir_migrations.get_ir_owner_registry_snapshot() == before
    result = ir_migrations.migrate_artifact(
        {"schema_version": "0.1", "value": 3}, artifact=artifact, target_version="0.2"
    )
    assert result == {"result": 21, "schema_version": "0.2"}
    assert ir_migrations._migration_function_fingerprint(migrate) != registration.fingerprint


def test_immutable_semantic_capture_and_mutable_observer_keep_actual_profile_behavior() -> None:
    """An observer list stays live without rehashing or freezing the callback."""
    stable_configuration = (2,)
    observations: list[int] = []

    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        observations.append(data["value"])
        return {"result": data["value"] * stable_configuration[0]}

    artifact = "mig05.ir.observed_immutable_capture"
    _register_ir(artifact, "0.1", "0.2", migrate)
    before = ir_migrations.get_ir_owner_registry_snapshot()
    for value in (3, 4):
        result = ir_migrations.migrate_artifact(
            {"schema_version": "0.1", "value": value}, artifact=artifact, target_version="0.2"
        )
        assert result == {"result": value * 2, "schema_version": "0.2"}
        assert ir_migrations.get_ir_owner_registry_snapshot() == before
    assert observations == [3, 4]


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
    with pytest.raises(ir_migrations.MigrationCompatibilityError, match="creates a cycle"):
        _register_ir("mig05.ir.cycle", "0.2", "0.1", _return_without_schema_version)


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


def test_ir_duplicate_registration_refuses_conflicting_callback_and_preserves_original() -> None:
    called: list[str] = []

    def old_callback(data: dict[str, Any]) -> dict[str, Any]:
        called.append("old")
        return _return_without_schema_version(data)

    def new_callback(data: dict[str, Any]) -> dict[str, Any]:
        called.append("new")
        return _return_without_schema_version(data)

    _register_ir("mig05.ir.duplicate", "0.1", "0.2", old_callback)
    with pytest.raises(
        ir_migrations.MigrationCompatibilityError, match="Conflicting migration edge"
    ):
        _register_ir("mig05.ir.duplicate", "0.1", "0.2", new_callback)

    ir_migrations.migrate_artifact(
        _payload(),
        artifact="mig05.ir.duplicate",
        target_version="0.2",
    )

    assert called == ["old"]


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


def test_legacy_ir_identity_helper_remains_callable_with_its_owner() -> None:
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


@pytest.mark.parametrize("reverse_registration", [False, True])
def test_data_forge_keeps_deterministic_shortest_path_and_its_distinct_profile(
    reverse_registration: bool,
) -> None:
    """The branching owner preserves ordering, instance scope and shallow copy."""
    from pydantic import ValidationError

    from polisyos.data_forge.kernel import DataForgeValidationError
    from polisyos.data_forge.kernel.schemas.migrations import (
        SchemaMigrationPlan,
        SchemaMigrationRegistry,
    )

    registry = SchemaMigrationRegistry()
    edges = [
        ("0.1.0", "0.3.0", "high"),
        ("0.1.0", "0.2.0", "low"),
        ("0.3.0", "1.0.0", "viahigh"),
        ("0.2.0", "1.0.0", "vialow"),
    ]

    def converter(label: str):
        def migrate(data):
            data["nested"]["last_step"] = label
            return {**data, "route": [*data["route"], label]}

        return migrate

    for from_version, to_version, name in reversed(edges) if reverse_registration else edges:
        registry.register(
            SchemaMigrationPlan(
                schema_id="mig05.graph",
                from_version=from_version,
                to_version=to_version,
                migration_id=name,
            ),
            converter(name),
        )
    path = registry.plan_path(schema_id="mig05.graph", from_version="0.1.0", to_version="1.0.0")
    assert [edge.migration_id for edge in path] == ["low", "vialow"]
    original = {"schema_version": "0.1.0", "nested": {}, "route": []}
    migrated = registry.apply(
        original, schema_id="mig05.graph", from_version="0.1.0", to_version="1.0.0"
    )
    assert migrated["route"] == ["low", "vialow"]
    assert original["route"] == []
    assert migrated is not original
    assert migrated["nested"] is original["nested"]
    assert original["nested"] == {"last_step": "vialow"}
    assert migrated["schema_version"] == "0.1.0"  # Graph owner does not auto-stamp.

    with pytest.raises(DataForgeValidationError, match="already registered"):
        registry.register(path[0], converter("duplicate"))
    with pytest.raises(ValidationError):
        SchemaMigrationPlan(
            schema_id="mig05.graph", from_version="0.1", to_version="1.0.0", migration_id="bad"
        )
    with pytest.raises(DataForgeValidationError, match="no schema migration path"):
        SchemaMigrationRegistry().plan_path(
            schema_id="mig05.graph", from_version="0.1.0", to_version="1.0.0"
        )
    registry.register(
        SchemaMigrationPlan(
            schema_id="mig05.graph", from_version="0.1.0", to_version="1.0.0", migration_id="direct"
        ),
        converter("direct"),
    )
    assert [
        edge.migration_id
        for edge in registry.plan_path(
            schema_id="mig05.graph", from_version="0.1.0", to_version="1.0.0"
        )
    ] == ["direct"]


def test_migration_required_is_not_direct_read_or_actual_dto_admission() -> None:
    """A successful version conversion still needs the actual Trinity validator."""
    from pydantic import ValidationError

    from polisyos.ir.trinity import TrinityBundle

    artifact = "mig05.ir.conversion_not_admission"
    for version in ("0.9", "1.0"):
        ir_migrations.register_schema_version(
            artifact, version, compatibility=ir_migrations.CompatibilityMode.NONE
        )

    def convert(data: dict[str, Any]) -> dict[str, Any]:
        return {**data, "schema_version": "1.0"}

    _register_ir(artifact, "0.9", "1.0", convert)
    decision = ir_migrations.negotiate_schema_version(artifact, "0.9", "1.0")
    assert decision.can_read is True
    assert decision.migration_required is True
    assert decision.reason == "migration_available"
    valid_source = {**_canonical_trinity_payload(), "schema_version": "0.9"}
    converted = ir_migrations.migrate_artifact(
        valid_source, artifact=artifact, target_version="1.0"
    )
    bundle = TrinityBundle.model_validate(converted)
    assert bundle.policy_spec.policy_id == "ps_mig05"
    invalid_source = {"schema_version": "0.9", "policy_spec": {"policy_id": "missing_dependencies"}}
    converted_invalid = ir_migrations.migrate_artifact(
        invalid_source, artifact=artifact, target_version="1.0"
    )
    assert converted_invalid["schema_version"] == "1.0"
    with pytest.raises(ValidationError):
        TrinityBundle.model_validate(converted_invalid)
