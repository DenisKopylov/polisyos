from __future__ import annotations

import json
from hashlib import sha256

import pytest

from polisyos.core.artifacts import (
    CanonInfo as CoreCanonInfo,
)
from polisyos.core.artifacts import (
    FileSystemCAS,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts import (
    PutOptions as CorePutOptions,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactID, CanonInfo
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation, to_canonical_bytes


def test_ir_fresh_reader_selects_v3_policy_for_raw_mapping(tmp_path) -> None:
    root = tmp_path / "cas"
    wire = to_canonical_bytes({"_type": "future"}, CanonSpec(version="0.3.0"))
    assert wire == b'{"_type":"mapping","entries":[["_type","future"]]}'
    core = FileSystemCAS(root)
    ref = core.put_bytes(
        wire,
        CorePutOptions(
            kind="test.ir.v3",
            media_type="application/json",
            canon=CoreCanonInfo(version="0.3.0"),
        ),
        return_selected_profile=True,
    )
    value = get_json_artifact(
        ensure_ir_artifact_store(FileSystemCAS(root)),
        {
            "artifact_id": str(ref.artifact_id),
            "kind": ref.kind,
            "media_type": ref.media_type,
            "manifest_profile_sha256": ref.manifest_profile_sha256,
        },
    )
    assert value == {"_type": "future"}
    assert type(value) is dict


def test_ir_json_write_returns_exact_profile_from_core_write(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected_store = ensure_ir_artifact_store(store)

    ref = put_json_artifact(
        selected_store,
        {"value": "payload"},
        kind="test.ir_selected_profile",
        schema_name="test.SelectedProfile",
        schema_version="1.0",
        return_selected_profile=True,
    )

    profile = ref["manifest_profile_sha256"]
    assert profile.startswith("sha256:")
    manifest = selected_store.get_manifest(ref)
    assert manifest.kind == "test.ir_selected_profile"
    assert artifact_manifest_profile_sha256(manifest) == profile


def test_ir_json_write_accepts_explicit_positional_or_keyword_profile_parameter() -> None:
    class PositionalOrKeywordStore:
        called = False

        def put_json(self, obj, opts, canon_spec=None, return_selected_profile=False):
            self.called = True
            assert return_selected_profile is True
            return {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": opts.kind,
                "media_type": opts.media_type,
                "manifest_profile_sha256": "sha256:" + "1" * 64,
            }

    store = PositionalOrKeywordStore()
    ref = put_json_artifact(
        store,
        {"value": "payload"},
        kind="test.ir_pos_or_kw",
        schema_name="test.SelectedProfile",
        schema_version="1.0",
        return_selected_profile=True,
    )

    assert store.called is True
    assert ref["manifest_profile_sha256"] == "sha256:" + "1" * 64


def test_ir_json_write_refuses_non_bool_before_store_call() -> None:
    class Store:
        called = False

        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            self.called = True
            raise AssertionError("invalid request must be refused before writer call")

    store = Store()
    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        put_json_artifact(
            store,
            {"value": "payload"},
            kind="test.invalid_profile_option",
            schema_name="test.SelectedProfile",
            schema_version="1.0",
            return_selected_profile=1,  # type: ignore[arg-type]
        )
    assert store.called is False


def test_ir_json_write_reports_unsupported_writer_without_calling_it() -> None:
    class LegacyStore:
        called = False

        def put_json(self, obj, opts, canon_spec=None):
            self.called = True
            return {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "test",
                "media_type": "application/json",
            }

    store = LegacyStore()
    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        put_json_artifact(
            store,
            {"value": "payload"},
            kind="test.profile_unsupported",
            schema_name="test.SelectedProfile",
            schema_version="1.0",
            return_selected_profile=True,
        )
    assert store.called is False


@pytest.mark.parametrize(
    "signature_kind",
    ["positional_only", "variadic_positional", "variadic_keyword"],
)
def test_ir_json_write_refuses_non_keyword_profile_parameters_before_writer_call(
    signature_kind: str,
) -> None:
    class PositionalOnlyStore:
        called = False

        def put_json(self, obj, opts, canon_spec=None, return_selected_profile=False, /):
            self.called = True

    class VariadicPositionalStore:
        called = False

        def put_json(self, obj, opts, canon_spec=None, *return_selected_profile):
            self.called = True

    class VariadicKeywordStore:
        called = False

        def put_json(self, obj, opts, canon_spec=None, **return_selected_profile):
            self.called = True

    store_type = {
        "positional_only": PositionalOnlyStore,
        "variadic_positional": VariadicPositionalStore,
        "variadic_keyword": VariadicKeywordStore,
    }[signature_kind]
    store = store_type()

    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        put_json_artifact(
            store,
            {"value": "payload"},
            kind="test.ir_unsupported_signature",
            schema_name="test.SelectedProfile",
            schema_version="1.0",
            return_selected_profile=True,
        )

    assert store.called is False


def test_ir_json_write_does_not_relabel_writer_type_error_as_unsupported() -> None:
    class BrokenStore:
        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            assert return_selected_profile is True
            raise TypeError("writer serialization defect")

    with pytest.raises(TypeError, match="writer serialization defect"):
        put_json_artifact(
            BrokenStore(),
            {"value": "payload"},
            kind="test.profile_writer_error",
            schema_name="test.SelectedProfile",
            schema_version="1.0",
            return_selected_profile=True,
        )


def test_ir_json_read_refuses_bytes_that_violate_the_selected_profile() -> None:
    raw_payload = b'{"value":1.0}'
    artifact_id = "sha256:" + sha256(raw_payload).hexdigest()
    manifest = {
        "artifact_id": artifact_id,
        "kind": "test.ir_selected_profile_read",
        "media_type": "application/json",
        "schema": {"name": "test.SelectedProfileRead", "version": "1.0"},
        "canon": CanonInfo().model_dump(mode="json"),
    }

    class RawProfiledReader:
        def get_bytes(self, selected_id):
            assert str(selected_id) == artifact_id
            return raw_payload

        def get_manifest_bytes(self, selected_id):
            assert str(selected_id) == artifact_id
            return json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()

    with pytest.raises(
        CanonViolation,
        match="ir_artifact_bytes_do_not_conform_to_persisted_canon_profile",
    ):
        get_json_artifact(RawProfiledReader(), ArtifactID.model_validate(artifact_id))


def test_ir_json_read_reconciles_selected_profile_with_typed_manifest(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(cas)
    payload = {"value": 1}
    first_ref = put_json_artifact(
        ir_store,
        payload,
        kind="test.ir_profile_identity",
        schema_name="test.ProfileA",
        schema_version="1.0",
        return_selected_profile=True,
    )
    selected_ref = put_json_artifact(
        ir_store,
        payload,
        kind="test.ir_profile_identity",
        schema_name="test.ProfileB",
        schema_version="1.0",
        return_selected_profile=True,
    )

    assert first_ref["artifact_id"] == selected_ref["artifact_id"]
    assert first_ref["manifest_profile_sha256"] != selected_ref["manifest_profile_sha256"]
    assert get_json_artifact(ir_store, selected_ref) == payload

    class DefaultViewIgnoringSelector:
        """Expose real CAS bytes while deliberately discarding view selectors."""

        def __init__(self):
            self.payload_reads = 0

        @staticmethod
        def _artifact_id(selector):
            return selector["artifact_id"] if isinstance(selector, dict) else selector

        def get_manifest_bytes(self, selector):
            return cas.get_manifest_bytes(self._artifact_id(selector))

        def get_manifest(self, selector):
            return cas.get_manifest(self._artifact_id(selector))

        def get_bytes(self, selector):
            self.payload_reads += 1
            return cas.get_bytes(self._artifact_id(selector))

    reader = DefaultViewIgnoringSelector()
    with pytest.raises(CanonViolation, match="ir_artifact_selected_profile_mismatch"):
        get_json_artifact(reader, selected_ref)
    assert reader.payload_reads == 0


@pytest.mark.parametrize("escaped", [False, True])
def test_ir_selected_v3_keeps_core_only_descriptor_policy(tmp_path, escaped) -> None:
    root = tmp_path / "descriptor-cas"
    wire = (
        b'{"_type":"mapping","entries":[["_type","bytes_hex"],["value","00ff"]]}'
        if escaped
        else b'{"_type":"bytes_hex","value":"00ff"}'
    )
    ref = FileSystemCAS(root).put_bytes(
        wire,
        CorePutOptions(
            kind="test.ir.v3.descriptor",
            media_type="application/json",
            canon=CoreCanonInfo(version="0.3.0"),
        ),
        return_selected_profile=True,
    )
    selector = {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
        "manifest_profile_sha256": ref.manifest_profile_sha256,
    }
    store = ensure_ir_artifact_store(FileSystemCAS(root))
    if escaped:
        assert get_json_artifact(store, selector) == {"_type": "bytes_hex", "value": "00ff"}
    else:
        with pytest.raises(CanonViolation):
            get_json_artifact(store, selector)


def test_ir_owned_v3_refuses_before_payload_and_profile_callbacks(tmp_path) -> None:
    from uuid import uuid4

    from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration
    from polisyos.ir.artifacts.io import _get_owned_json_artifact_with_bytes
    from polisyos.ir.migrations.base import (
        CompatibilityMode,
        register_ir_representation,
        register_schema_version,
    )

    token = uuid4().hex
    registry, contract = f"test.reader.callback.{token}", f"test.reader.owner.{token}"
    register_schema_version(registry, "1", compatibility=CompatibilityMode.NONE)
    register_ir_representation(
        registry_key=registry,
        owner_ref=contract,
        dto_abi="test.callback.Payload",
        wire_policy_ref="test.callback-wire",
        wire_policy_revision="1",
        schema_name="test.callback.Payload",
        schema_version="1",
        payload_version=None,
        readable=True,
    )
    events = []

    def unqualified_callback(*args):
        events.append("callback")
        return True

    owner = ArtifactOwnerDeclaration(
        contract_id=contract,
        dto_fqn="test.callback.Payload",
        abi_key="test.callback@1",
        registry_key=registry,
        kind="test.callback",
        media_type="application/json",
        purpose="negative unqualified callback cohort",
        policy_revision="1",
        accepted_wire_policies=(("test.callback-wire", "1"),),
        payload_version_of=unqualified_callback,
        validate_source=unqualified_callback,
        project_for_consumer=unqualified_callback,
        validate_profile=unqualified_callback,
    )
    from polisyos.core.artifacts import SchemaInfo

    core = FileSystemCAS(tmp_path / "owned-cas")
    ref = core.put_bytes(
        b'{"value":1}',
        CorePutOptions(
            kind="test.callback",
            media_type="application/json",
            schema=SchemaInfo(name="test.callback.Payload", version="1"),
            canon=CoreCanonInfo(version="0.3.0"),
        ),
        return_selected_profile=True,
    )
    inner = ensure_ir_artifact_store(core)

    class ObservedReader:
        def __getattr__(self, name):
            return getattr(inner, name)

        def get_bytes(self, selector):
            events.append("payload")
            return inner.get_bytes(selector)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_callback_codec_unavailable"):
        _get_owned_json_artifact_with_bytes(
            ObservedReader(),
            {
                "artifact_id": str(ref.artifact_id),
                "kind": ref.kind,
                "media_type": ref.media_type,
                "manifest_profile_sha256": ref.manifest_profile_sha256,
            },
            owner=owner,
        )
    assert events == []


def test_owned_callback_keeps_named_legacy_hash_domain_mechanics() -> None:
    from polisyos.ir.artifacts.io import _decode_owner_callback_payload

    # Noncanonical named domains retain the existing .2 grammar even when
    # their own identity version differs; no canonical .3 cohort is implied.
    value = _decode_owner_callback_payload(
        b'{"value":1}',
        CanonSpec(name="polisyos.idempotency.canon", version="2.0"),
        refusal_code="test.callback.refused",
    )
    assert value == {"value": 1}
