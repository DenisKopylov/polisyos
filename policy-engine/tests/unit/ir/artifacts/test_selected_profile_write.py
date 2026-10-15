from __future__ import annotations

import json
from hashlib import sha256

import pytest

from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactID, CanonInfo
from polisyos.ir.model_layer.canon import CanonViolation


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
