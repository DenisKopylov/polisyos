from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from types import FunctionType

import pytest

from polisyos.ir.migrations import (
    IR_CURRENT_VERSION,
    CompatibilityMode,
    can_read_schema,
    get_schema_rule,
    migrate_policy_ir,
    negotiate_schema_version,
)
from polisyos.ir.migrations.base import (
    IRCompatibilityKind,
    IRRepresentationKey,
    MigrationCompatibilityError,
    find_writable_representation,
    get_current_ir_representation,
    get_default_write_representation,
    get_ir_owner_registry_snapshot,
    register_ir_representation,
    register_migration,
    register_schema_version,
    resolve_owned_representation,
)
from polisyos.ir.migrations.schema_registry import register_default_schema_rules
from polisyos.ir.model_layer.canon import to_canonical_bytes

ZERO_REF = "sha256:" + "0" * 64


def _canonical_trinity_payload() -> dict:
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


def test_migrate_policy_ir_accepts_canonical_trinity_payload() -> None:
    payload = _canonical_trinity_payload()
    migrated = migrate_policy_ir(payload, IR_CURRENT_VERSION)
    assert migrated["schema_version"] == "1.0"
    assert migrated["policy_spec"]["policy_id"] == "ps_test"


def test_migrate_policy_ir_rejects_invalid_version() -> None:
    payload = {"schema_version": "v1"}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_non_trinity_schema_v2() -> None:
    payload = {
        "schema_version": "2.0",
        "semantic": {"context_snapshot_ref": ZERO_REF},
    }
    with pytest.raises(ValueError, match="Legacy non-Trinity payloads"):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_non_trinity_semantic_surface() -> None:
    payload = {
        "schema_version": "1.0",
        "semantic": {"context_snapshot_ref": ZERO_REF},
    }
    with pytest.raises(ValueError, match="Legacy non-Trinity payloads"):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_missing_schema_version() -> None:
    payload = {"policy_spec": {"schema_version": "1.0"}}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_schema_registry_answers_backward_compatibility_for_old_payloads() -> None:
    decision = negotiate_schema_version(
        "article_extraction_result",
        producer_version="1.0",
        consumer_version="1.5",
    )

    assert decision.can_read is True
    assert decision.mode is CompatibilityMode.BACKWARD
    assert decision.migration_required is False
    assert can_read_schema("transportability_result", "1.0", "2.0") is True


def test_schema_registry_rejects_unknown_or_cross_major_payloads() -> None:
    unknown = negotiate_schema_version(
        "article_extraction_result",
        producer_version="1.0",
        consumer_version="9.9",
    )
    cross_major = negotiate_schema_version(
        "article_extraction_result",
        producer_version="2.0",
        consumer_version="1.5",
    )

    assert unknown.can_read is False
    assert unknown.reason == "unknown_consumer_version"
    assert cross_major.can_read is False
    assert cross_major.reason == "not_compatible"


def test_schema_registry_records_field_evolution_policy() -> None:
    article_rule = get_schema_rule("article_extraction_result", "1.5")
    transport_rule = get_schema_rule("transportability_result", "2.0")

    assert article_rule is not None
    assert article_rule.mode is CompatibilityMode.BACKWARD
    assert ("publication_year", "year") in article_rule.renamed_fields
    assert "paper_kind" in article_rule.additive_optional_fields
    assert transport_rule is not None
    assert ("formula", "transport_formula") in transport_rule.renamed_fields
    assert ("schema_version", "2.0") in transport_rule.canonical_defaults


def test_old_canonical_fixture_bytes_do_not_silently_degrade() -> None:
    legacy_payload = {
        "schema_version": "1.0",
        "openalex_id": "W1",
        "title": "Legacy",
        "publication_year": 2020,
    }

    assert can_read_schema("article_extraction_result", "1.0", "1.5") is True
    assert to_canonical_bytes(legacy_payload) == (
        b'{"openalex_id":"W1","publication_year":2020,"schema_version":"1.0","title":"Legacy"}'
    )


def _owned_registration(
    registry_key: str,
    *,
    owner_ref: str,
    schema_name: str,
    schema_version: str,
    payload_version: str | None,
    wire_policy_ref: str,
    wire_policy_revision: str,
    profile_ref: str | None = None,
    readable: bool = True,
    writable: bool = False,
    current: bool = False,
    default_write: bool = False,
    readable_from: tuple[IRRepresentationKey, ...] = (),
):
    return register_ir_representation(
        registry_key=registry_key,
        owner_ref=owner_ref,
        dto_abi="tests.ir.OwnerDTO",
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        schema_name=schema_name,
        schema_version=schema_version,
        payload_version=payload_version,
        profile_ref=profile_ref,
        readable=readable,
        writable=writable,
        current=current,
        default_write=default_write,
        readable_from=readable_from,
    )


def test_owner_registry_keeps_exact_payloadless_rows_and_allows_registered_same_law_extension() -> (
    None
):
    key = "test.ir.owner_registry.same_law_extension"
    owner = "tests.ir.owner.same_law_extension"
    schema = "tests.ir.same_law_extension"
    register_schema_version(key, "1.0", compatibility=CompatibilityMode.NONE)
    register_schema_version(key, "1.1", compatibility=CompatibilityMode.BACKWARD)
    register_schema_version(key, "1.2", compatibility=CompatibilityMode.BACKWARD)

    legacy = _owned_registration(
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version=None,
        wire_policy_ref="tests.wire.legacy",
        wire_policy_revision="1",
        profile_ref="tests.canon.legacy",
        readable=True,
        writable=False,
    )
    current = _owned_registration(
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.1",
        payload_version=None,
        wire_policy_ref="tests.wire.current",
        wire_policy_revision="2",
        profile_ref="tests.canon.current",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(legacy.key,),
    )
    frozen = get_ir_owner_registry_snapshot()
    extension_args = {
        "owner_ref": owner,
        "schema_name": schema,
        "schema_version": "1.2",
        "payload_version": None,
        "wire_policy_ref": "tests.wire.current",
        "wire_policy_revision": "2",
        "profile_ref": "tests.canon.nondefault",
        "readable": True,
        "writable": True,
        "current": False,
        "default_write": False,
    }
    extension = _owned_registration(key, **extension_args)
    assert _owned_registration(key, **extension_args) == extension
    snapshot = get_ir_owner_registry_snapshot()

    # A row explicitly registered by the owner can reuse the already trusted
    # current wire law without adding a central version dispatch or changing
    # current selection. Canonicalization profiles remain distinct identities.
    assert (
        get_current_ir_representation(snapshot, key, owner_ref=owner, schema_name=schema) == current
    )
    assert get_default_write_representation(snapshot, key, owner_ref=owner) == current
    assert extension.profile_ref != current.profile_ref
    admitted_extension = resolve_owned_representation(
        snapshot,
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.2",
        payload_version=None,
    )
    assert admitted_extension is not None
    assert admitted_extension.compatibility_kind is IRCompatibilityKind.DIRECT
    assert admitted_extension.source_registration == extension
    assert admitted_extension.source_registration.payload_version is None

    # Legacy remains admitted through its explicit owner relation even though
    # it has a distinct strict wire law.
    admitted_legacy = resolve_owned_representation(
        snapshot,
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version=None,
    )
    assert admitted_legacy is not None
    assert admitted_legacy.compatibility_kind is IRCompatibilityKind.DIRECT
    assert admitted_legacy.source_registration.payload_version is None

    # None is an exact absence of an embedded discriminator, never a wildcard
    # copied from the manifest version.
    assert (
        resolve_owned_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name=schema,
            schema_version="1.0",
            payload_version="1.0",
        )
        is None
    )
    assert (
        resolve_owned_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name=schema,
            schema_version="1.4",
            payload_version=None,
        )
        is None
    )
    assert (
        find_writable_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name=schema,
            schema_version="1.2",
            payload_version="1.0",
        )
        is None
    )

    # Old snapshots do not acquire later owner registrations.
    assert not any(
        record.registry_key == key and record.schema_version == "1.2"
        for record in frozen.representation_records
    )
    assert any(
        record.registry_key == key and record.schema_version == "1.2"
        for record in snapshot.representation_records
    )

    # Public equal-version FULL negotiation remains advisory and does not
    # authorize an unregistered tuple.
    assert negotiate_schema_version(key, "9.9", "9.9").can_read is True
    assert (
        resolve_owned_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name=schema,
            schema_version="9.9",
            payload_version="9.9",
        )
        is None
    )
    with pytest.raises(MigrationCompatibilityError, match="Conflicting IR representation"):
        _owned_registration(key, **{**extension_args, "wire_policy_revision": "3"})
    with pytest.raises(MigrationCompatibilityError, match="Conflicting schema registration"):
        register_schema_version(key, "1.2", compatibility=CompatibilityMode.NONE)


def test_migration_identity_covers_constants_defaults_closures_and_recreated_functions() -> None:
    from polisyos.ir.migrations.base import _migration_function_fingerprint

    literal_a = lambda value: "A"  # noqa: E731
    literal_b_code = literal_a.__code__.replace(
        co_consts=tuple("B" if item == "A" else item for item in literal_a.__code__.co_consts)
    )
    literal_b = FunctionType(
        literal_b_code,
        literal_a.__globals__,
        literal_a.__name__,
        literal_a.__defaults__,
    )
    assert literal_a.__code__.co_code == literal_b.__code__.co_code
    assert _migration_function_fingerprint(literal_a) != _migration_function_fingerprint(literal_b)

    default_a = lambda value, marker="A": marker  # noqa: E731
    default_b = FunctionType(
        default_a.__code__,
        default_a.__globals__,
        default_a.__name__,
        ("B",),
    )
    assert default_a.__code__.co_code == default_b.__code__.co_code
    assert _migration_function_fingerprint(default_a) != _migration_function_fingerprint(default_b)

    def capture(value: str):
        def migrate(payload: dict[str, object]) -> dict[str, object]:
            return {**payload, "captured": value}

        return migrate

    captured_a = capture("A")
    captured_b = capture("B")
    assert _migration_function_fingerprint(captured_a) != _migration_function_fingerprint(
        captured_b
    )

    key = "test.ir.owner_registry.migration_identity"
    duplicate = FunctionType(
        literal_a.__code__,
        literal_a.__globals__,
        literal_a.__name__,
        literal_a.__defaults__,
        literal_a.__closure__,
    )
    register_migration(key, "1.0", "1.1")(literal_a)
    register_migration(key, "1.0", "1.1")(duplicate)
    with pytest.raises(MigrationCompatibilityError, match="Conflicting migration edge"):
        register_migration(key, "1.0", "1.1")(literal_b)


def test_payloadless_migration_uses_manifest_graph_keys_without_rewriting_exact_tuple() -> None:
    key = "test.ir.owner_registry.payloadless_migration"
    owner = "tests.ir.owner.payloadless_migration"
    schema = "tests.ir.payloadless_migration"

    @register_migration(key, "1.0", "1.1")
    def migrate_10_to_11(value: dict[str, object]) -> dict[str, object]:
        return value

    @register_migration(key, "1.1", "1.2")
    def migrate_11_to_12(value: dict[str, object]) -> dict[str, object]:
        return value

    # Identical function registrations are idempotent; conflicting meaning
    # and cycles are refused without replacing a pre-existing schema rule.
    register_migration(key, "1.0", "1.1")(migrate_10_to_11)
    with pytest.raises(MigrationCompatibilityError, match="Conflicting migration edge"):
        register_migration(key, "1.0", "1.1")(lambda value: value)
    with pytest.raises(MigrationCompatibilityError, match="creates a cycle"):
        register_migration(key, "1.2", "1.0")(lambda value: value)

    _owned_registration(
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version=None,
        wire_policy_ref="tests.wire.old",
        wire_policy_revision="1",
        readable=True,
    )
    _owned_registration(
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.1",
        payload_version=None,
        wire_policy_ref="tests.wire.middle",
        wire_policy_revision="1",
        readable=True,
    )
    _owned_registration(
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.2",
        payload_version=None,
        wire_policy_ref="tests.wire.current",
        wire_policy_revision="1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    snapshot = get_ir_owner_registry_snapshot()
    admission = resolve_owned_representation(
        snapshot,
        key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version=None,
    )
    assert admission is not None
    assert admission.compatibility_kind is IRCompatibilityKind.MIGRATION
    assert admission.migration_path == ("1.0", "1.1", "1.2")
    assert admission.source_registration.payload_version is None
    assert admission.source_registration.key == IRRepresentationKey(schema, "1.0", None)
    assert (
        resolve_owned_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name=schema,
            schema_version="1.0",
            payload_version="1.0",
        )
        is None
    )


def test_owner_registry_snapshot_is_immutable_and_builtin_registration_is_idempotent() -> None:
    key = "test.ir.owner_registry.snapshot_immutability"
    owner = "tests.ir.owner.snapshot_immutability"
    register_schema_version(key, "1.0", compatibility=CompatibilityMode.FULL)
    row = _owned_registration(
        key,
        owner_ref=owner,
        schema_name="tests.ir.snapshot_immutability",
        schema_version="1.0",
        payload_version=None,
        wire_policy_ref="tests.wire.snapshot_immutability",
        wire_policy_revision="1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    first = get_ir_owner_registry_snapshot()
    register_default_schema_rules()
    second = get_ir_owner_registry_snapshot()

    assert first.revision == second.revision
    with pytest.raises(TypeError):
        first.schema_rules[("new", "1.0")] = first.schema_rules[(key, "1.0")]
    with pytest.raises(FrozenInstanceError):
        row.writable = False


def test_owner_registry_registers_one_exact_extension_idempotently_and_refuses_conflicts() -> None:
    key = "test.ir.owner_registry.extension.single"
    owner = "test.contract.owner.single"
    abi = "test.package.dto:OwnerV1"
    register_schema_version(key, "1.0", compatibility=CompatibilityMode.FULL)
    args = {
        "owner_ref": owner,
        "dto_abi": abi,
        "wire_policy_ref": "tests.wire.owner_registry.single",
        "wire_policy_revision": "1",
        "schema_name": "test.owner.v1",
        "schema_version": "1.0",
        "payload_version": None,
        "readable": True,
        "writable": True,
        "current": True,
        "default_write": True,
    }

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = tuple(
            pool.map(lambda _: register_ir_representation(registry_key=key, **args), range(2))
        )
    assert rows[0] == rows[1]
    snapshot = get_ir_owner_registry_snapshot()
    assert (
        resolve_owned_representation(
            snapshot,
            key,
            owner_ref=owner,
            schema_name="test.owner.v1",
            schema_version="1.0",
            payload_version=None,
        )
        is not None
    )

    with pytest.raises(MigrationCompatibilityError, match="Conflicting IR representation"):
        register_ir_representation(
            registry_key=key, **{**args, "dto_abi": "test.package.dto:Changed"}
        )
    with pytest.raises(MigrationCompatibilityError, match="Conflicting schema registration"):
        register_schema_version(key, "1.0", compatibility=CompatibilityMode.NONE)


def test_owner_direct_read_compatibility_is_explicitly_directional() -> None:
    forward_key = "test.ir.owner_registry.directed.forward"
    owner = "tests.ir.owner.directed"
    schema = "tests.ir.directed"
    register_schema_version(forward_key, "1.0", compatibility=CompatibilityMode.FULL)
    register_schema_version(forward_key, "1.1", compatibility=CompatibilityMode.FULL)
    old = _owned_registration(
        forward_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version="2.0",
        wire_policy_ref="tests.wire.directed.old",
        wire_policy_revision="1",
        readable=True,
    )
    _owned_registration(
        forward_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.1",
        payload_version="2.1",
        wire_policy_ref="tests.wire.directed.new",
        wire_policy_revision="2",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(old.key,),
    )
    forward = resolve_owned_representation(
        get_ir_owner_registry_snapshot(),
        forward_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version="2.0",
    )
    assert forward is not None
    assert forward.compatibility_kind is IRCompatibilityKind.DIRECT
    assert forward.source_registration.key == old.key

    reverse_key = "test.ir.owner_registry.directed.reverse"
    register_schema_version(reverse_key, "1.0", compatibility=CompatibilityMode.FULL)
    register_schema_version(reverse_key, "1.1", compatibility=CompatibilityMode.FULL)
    newer = _owned_registration(
        reverse_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.1",
        payload_version="2.1",
        wire_policy_ref="tests.wire.directed.new",
        wire_policy_revision="2",
        readable=True,
    )
    _owned_registration(
        reverse_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.0",
        payload_version="2.0",
        wire_policy_ref="tests.wire.directed.old",
        wire_policy_revision="1",
        readable=True,
        writable=True,
        current=True,
        default_write=True,
    )
    reverse = resolve_owned_representation(
        get_ir_owner_registry_snapshot(),
        reverse_key,
        owner_ref=owner,
        schema_name=schema,
        schema_version="1.1",
        payload_version="2.1",
    )
    assert reverse is None
    assert newer.key == IRRepresentationKey(schema, "1.1", "2.1")
