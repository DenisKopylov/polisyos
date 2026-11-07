"""Bounded build-input bridge and native census failure distinctions for CYC-05.

These tests use an explicit technical test principal. They do not supply the
final LANE-12 distribution/issuer or establish production reachability.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.runtime.quality import generation_cycle as cycle

_OWNER = "cyc05-test-build-owner"


def _configured_evidence(
    tmp_path: Path,
    *,
    change=None,
    signer_identity=_OWNER,
    census_content=b"VALUE = 1\n",
    public_trust_files=False,
):
    root = ledger._loaded_policy_engine_root()
    registry = ledger.load_confidence_ledger_registry(root / ledger.DEFAULT_REGISTRY_RELATIVE_PATH)
    policy = registry.source_payload()
    policy["certificate_class_routes"].append(
        {
            "certificate_class": "n6_build_identity",
            "instrument_id": "constant_unit_e_process",
            "obligation_class": "implementation",
            "certificate_role": "promotion_conformance",
            "claim_polarity": "conformance_only",
            "owner_ref": _OWNER,
            "verifier_kernel_id": "n6_build_identity_reconcile_v1",
            "verifier_ref": "polisyos.runtime.quality.confidence_ledger",
        }
    )
    source = tmp_path / "declared-census" / "src" / "polisyos"
    source.mkdir(parents=True)
    (source / "plain.py").write_bytes(census_content)
    census = cycle.inspect_n6_source_census(source.parents[1])
    loaded = ledger.capture_loaded_deployment_identity()
    assert loaded.status == "established", (loaded, ledger._IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE)
    payload = {
        "schema_version": "policyos.runtime.confidence_ledger.build_identity.v1",
        "profile": "source_checkout_import_snapshot_v1",
        "authority_purpose": "n6_technical_build_readiness",
        "issuer_ref": _OWNER,
        "deployment_identity": loaded.deployment_identity,
        "deployment_baseline_sha256": ledger._bytes_hash(
            ledger._IMPORT_TIME_DEPLOYMENT_BASELINE.encode("utf-8")
        ),
        "loaded_code_manifest_sha256": ledger._bytes_hash(
            ledger._IMPORT_TIME_LOADED_CODE_MANIFEST.encode("utf-8")
        ),
        "import_binding_sha256": ledger._bytes_hash(
            ledger._IMPORT_TIME_FACADE_RUNTIME_PROJECTION.encode("utf-8")
        ),
        "census": census.model_dump(mode="json"),
    }
    if change is not None:
        change(payload)
    store = artifacts.FileSystemCAS(tmp_path / "cas", tenant_id="cyc05", cell_id="test")
    key = artifacts.KeyPair.generate()
    signer = artifacts.Ed25519Signer.from_pem(key.private_pem())
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(key.public_key, key_id=key.key_id, identity=_OWNER)
    if public_trust_files:
        trust_dir = tmp_path / "trusted"
        trust_dir.mkdir()
        (tmp_path / "revoked").mkdir()
        (trust_dir / "issuer.pub").write_bytes(key.public_pem())
        (tmp_path / "identities.json").write_text(json.dumps({key.key_id: _OWNER}))
    reference = store.put_json(
        payload,
        artifacts.PutOptions(
            kind="runtime.quality.confidence_ledger.build_identity",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="runtime.quality.confidence_ledger.build_identity", version="1"
            ),
            producer=artifacts.ProducerInfo(component=_OWNER, version="test.v1"),
        ),
        return_selected_profile=True,
    )
    store.sign_artifact(reference, signer, signer_identity=signer_identity)
    return {
        "build_evidence_ref": reference,
        "evidence_store": store,
        "signature_verifier": verifier,
        "registry_source": policy,
    }


def _observe(kwargs):
    loaded = ledger.capture_loaded_deployment_identity()
    return ledger.observe_n6_deployment_currentness(
        recorded_identity_status=loaded.status,
        recorded_deployment_identity=loaded.deployment_identity,
        **kwargs,
    )


def test_signed_build_input_is_verified_without_promoting_source_census(tmp_path):
    """Actual CAS/signature/route consumer accepts only its finite technical scope."""

    kwargs = _configured_evidence(tmp_path)
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "UNRUN", ready
    assert ready.inputs["build_evidence_status"] == "verified"
    assert ready.inputs["readiness_scope"] == "technical_build_artifact_only"
    assert ready.inputs["issuer_route_provenance"] == "verification"
    assert ready.inputs["census_predicate_provenance"] == "institutionally_supplied"
    assert ready.inputs["n6_census_verdict"] == "UNRUN"
    assert "n6_source_census_production_binding_not_established" in ready.unresolved_by_construction
    currentness = _observe(kwargs)
    assert currentness.status == "not_established"
    assert currentness.census_verdict == "UNRUN"
    assert currentness.reason_code == "n6_census_not_established"


def test_existing_n6_consumer_selects_declared_route_and_public_trust_profile(
    tmp_path, monkeypatch
):
    kwargs = _configured_evidence(tmp_path, public_trust_files=True)
    policy = copy.deepcopy(kwargs["registry_source"])
    route = next(
        item
        for item in policy["certificate_class_routes"]
        if item["certificate_class"] == "n6_build_identity"
    )
    route["build_evidence_ref"] = kwargs["build_evidence_ref"].model_dump(mode="json")
    monkeypatch.setenv("POLISYOS_CAS_BACKEND", "filesystem")
    monkeypatch.setenv("POLISYOS_CAS_ROOT", str(kwargs["evidence_store"].root))
    monkeypatch.setenv("POLISYOS_SIGN_TRUST_DIR", str(tmp_path / "trusted"))
    monkeypatch.setenv("POLISYOS_SIGN_REVOKED_DIR", str(tmp_path / "revoked"))
    monkeypatch.setenv("POLISYOS_SIGN_IDENTITIES", str(tmp_path / "identities.json"))
    # No direct build-ref, store, verifier, or ready verdict is injected into
    # the reader. The existing registry and Core public trust config select it.
    ready = ledger.inspect_packaged_deployment_identity(registry_source=policy)
    assert ready.verdict == "UNRUN", ready
    assert ready.inputs["build_evidence_status"] == "verified", ready
    assert ready.inputs["census_loaded_binding"] == "not_established"
    observed = _observe({"registry_source": policy})
    assert observed.status == "not_established"
    assert observed.census_verdict == "UNRUN"
    # The next ordinary observation rereads revocation policy, not a cached
    # previous positive input or a caller's original verifier object.
    public_key = (tmp_path / "trusted" / "issuer.pub").read_bytes()
    (tmp_path / "revoked" / "issuer.pub").write_bytes(public_key)
    revoked = ledger.inspect_packaged_deployment_identity(registry_source=policy)
    assert revoked.inputs["build_evidence_status"] == "not_established"
    assert revoked.inputs["signature_status"] == "revoked"
    assert _observe({"registry_source": policy}).status == "not_established"
    # Selection removal cannot silently keep the previous authenticated input.
    route.pop("build_evidence_ref")
    removed = ledger.inspect_packaged_deployment_identity(registry_source=policy)
    assert removed.inputs.get("build_evidence_status") != "verified"


def test_absent_build_reference_preserves_historical_registry_serialization():
    registry = ledger.load_confidence_ledger_registry(
        ledger._loaded_policy_engine_root() / ledger.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    assert all(
        "build_evidence_ref" not in route.model_dump(mode="json")
        for route in registry.certificate_class_routes
    )


@pytest.mark.parametrize(
    "field",
    ["deployment_baseline_sha256", "loaded_code_manifest_sha256", "import_binding_sha256"],
)
def test_valid_signature_cannot_launder_wrong_loaded_basis(tmp_path, field):
    kwargs = _configured_evidence(
        tmp_path, change=lambda payload: payload.update({field: "sha256:" + "0" * 64})
    )
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.inputs["evidence_error_detail"] == "build_evidence_loaded_baseline_mismatch"
    assert _observe(kwargs).status == "not_established"
    assert _observe(kwargs).census_verdict == "UNRUN"


def test_valid_trusted_signature_without_issuer_identity_does_not_appoint_owner(tmp_path):
    kwargs = _configured_evidence(tmp_path, signer_identity=None)
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.inputs["evidence_error_detail"] == "build_evidence_issuer_signature_mismatch"
    assert _observe(kwargs).status == "not_established"


def test_technical_route_removal_and_incomplete_census_stay_unestablished(tmp_path):
    kwargs = _configured_evidence(tmp_path)
    policy = copy.deepcopy(kwargs["registry_source"])
    policy["certificate_class_routes"] = [
        item
        for item in policy["certificate_class_routes"]
        if item["certificate_class"] != "n6_build_identity"
    ]
    removed = {**kwargs, "registry_source": policy}
    ready = ledger.inspect_packaged_deployment_identity(**removed)
    assert ready.verdict == "UNRUN"
    assert ready.unresolved_by_construction == ("packaged_build_identity_issuer_not_appointed",)
    assert _observe(removed).status == "not_established"

    malformed = _configured_evidence(
        tmp_path / "incomplete",
        change=lambda payload: payload["census"].update(source_path_enumeration_complete=False),
    )
    ready = ledger.inspect_packaged_deployment_identity(**malformed)
    assert ready.verdict == "FAIL"
    assert "n6_source_census_content_binding_mismatch" in ready.inputs["evidence_error_detail"]
    assert _observe(malformed).census_verdict == "UNRUN"


@pytest.mark.parametrize("census_content", [b"def broken(:\n", b"\xff"])
def test_signed_actual_parse_failure_is_not_complete_build_input(tmp_path, census_content):
    kwargs = _configured_evidence(tmp_path, census_content=census_content)
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.inputs["evidence_error_detail"] == "build_evidence_census_incomplete"
    assert _observe(kwargs).census_verdict == "UNRUN"


def test_signed_census_digest_removal_is_not_complete_build_input(tmp_path):
    kwargs = _configured_evidence(
        tmp_path, change=lambda payload: payload["census"]["inputs"].pop("source_bytes_sha256")
    )
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.inputs["evidence_error_detail"] == "build_evidence_census_incomplete"
    assert _observe(kwargs).status == "not_established"


def test_signed_census_semantic_digest_tamper_fails_the_existing_owner_verifier(tmp_path):
    kwargs = _configured_evidence(
        tmp_path,
        change=lambda payload: payload["census"].update(semantic_census_sha256="0" * 64),
    )
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert "n6_source_census_content_binding_mismatch" in ready.inputs["evidence_error_detail"]
    assert _observe(kwargs).status == "not_established"


def test_evidence_requires_an_exact_selected_manifest_profile(tmp_path):
    kwargs = _configured_evidence(tmp_path)
    kwargs["build_evidence_ref"] = kwargs["build_evidence_ref"].model_copy(
        update={"manifest_profile_sha256": None}
    )
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.inputs["evidence_error_detail"] == "build_evidence_selected_profile_missing"


def test_runtime_fence_drift_does_not_rewrite_frozen_loaded_identity(tmp_path, monkeypatch):
    kwargs = _configured_evidence(tmp_path)
    original = ledger.capture_loaded_deployment_identity()
    assert (
        ledger.inspect_packaged_deployment_identity(**kwargs).inputs["build_evidence_status"]
        == "verified"
    )
    monkeypatch.setattr(sys, "abiflags", getattr(sys, "abiflags", "") + "-changed")
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict == "FAIL"
    assert ready.unresolved_by_construction == ("deployment_disk_drift",)
    assert ledger.capture_loaded_deployment_identity() == original
    assert _observe(kwargs).status == "not_established"


def test_unchanged_readiness_does_not_read_or_parse_source_again(tmp_path, monkeypatch):
    kwargs = _configured_evidence(tmp_path)
    reads = []
    parses = []
    original = Path.read_bytes
    original_parse = ast.parse

    def observe_read(path):
        if path.suffix == ".py" and "src/polisyos" in path.as_posix():
            reads.append(path)
        return original(path)

    def observe_parse(source, filename="<unknown>", *args, **kwargs):
        if "src/polisyos" in str(filename):
            parses.append(filename)
        return original_parse(source, filename, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", observe_read)
    monkeypatch.setattr(ast, "parse", observe_parse)
    assert (
        ledger.inspect_packaged_deployment_identity(**kwargs).inputs["build_evidence_status"]
        == "verified"
    )
    assert (
        ledger.inspect_packaged_deployment_identity(**kwargs).inputs["build_evidence_status"]
        == "verified"
    )
    assert ledger.capture_loaded_deployment_identity().status == "established"
    assert reads == []
    assert parses == []


@pytest.mark.parametrize(
    ("case", "content", "relative", "state", "status"),
    [
        ("missing", None, "plain.py", "missing", "not_established"),
        ("empty", None, "plain.py", "not_established", "not_established"),
        ("invalid_utf8", b"\xff", "plain.py", "parse_error", "not_established"),
        ("parse_error", b"def broken(:\n", "plain.py", "parse_error", "not_established"),
        ("forbidden", b"run_fixture()\n", "plain.py", "available", "drift"),
        (
            "allowed",
            b"run_fixture()\n",
            "runtime/quality/workspace/loop.py",
            "available",
            "strangled",
        ),
    ],
)
def test_native_census_distinguishes_failure_classes(
    tmp_path, case, content, relative, state, status
):
    source = tmp_path / "src" / "polisyos"
    if case != "missing":
        source.mkdir(parents=True)
    if content is not None:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    receipt = cycle.StrangleReceipt.recompute(tmp_path)
    inspected = cycle.inspect_n6_source_census(tmp_path)
    assert receipt.source_state == state
    assert receipt.status == status
    assert inspected.source_verdict == inspected.production_path_verdict == "UNRUN"
    if status == "not_established":
        assert receipt.source_content_hash is None
    if case in {"invalid_utf8", "parse_error"}:
        assert "source_read_or_parse_incomplete" in inspected.unresolved_by_construction
    if case == "forbidden":
        assert receipt.production_single_pass_callers == ("src/polisyos/plain.py:1",)


def test_denied_nested_census_cannot_hide_forbidden_caller_behind_readable_sibling(
    tmp_path, monkeypatch
):
    source = tmp_path / "src" / "polisyos"
    denied = source / "hidden"
    denied.mkdir(parents=True)
    (source / "plain.py").write_text("VALUE = 1\n")
    (denied / "caller.py").write_text("run_fixture()\n")
    real_scandir = os.scandir

    def deny_selected(path):
        if Path(path) == denied:
            raise PermissionError("controlled unreadable directory")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", deny_selected)
    receipt = cycle.StrangleReceipt.recompute(tmp_path)
    inspected = cycle.inspect_n6_source_census(tmp_path)
    assert receipt.status == "not_established"
    assert receipt.source_state == "read_error"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 1
    assert receipt.parse_errors
    assert inspected.source_path_count == 1
    assert not inspected.source_path_enumeration_complete
    assert "source_denominator_enumeration_failed" in inspected.unresolved_by_construction
    assert inspected.production_path_verdict == "UNRUN"


@pytest.mark.parametrize("failed_operation", ["root_stat", "file_read"])
def test_native_unreadable_census_is_distinct_from_parse_or_empty(
    tmp_path, monkeypatch, failed_operation
):
    source = tmp_path / "src" / "polisyos"
    source.mkdir(parents=True)
    target = source / "plain.py"
    target.write_text("VALUE = 1\n")
    if failed_operation == "root_stat":
        real_stat = Path.stat

        def deny_stat(path, *args, **kwargs):
            if path == source:
                raise PermissionError("controlled unreadable source root")
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", deny_stat)
    else:
        real_read = Path.read_bytes

        def deny_read(path):
            if path == target:
                raise PermissionError("controlled unreadable source file")
            return real_read(path)

        monkeypatch.setattr(Path, "read_bytes", deny_read)
    receipt = cycle.StrangleReceipt.recompute(tmp_path)
    inspected = cycle.inspect_n6_source_census(tmp_path)
    assert receipt.status == "not_established"
    assert receipt.source_state == "read_error"
    assert receipt.source_content_hash is None
    assert any("read_error" in item for item in receipt.parse_errors)
    assert inspected.production_path_verdict == "UNRUN"
    expected = (
        "source_denominator_root_inspection_failed"
        if failed_operation == "root_stat"
        else "source_read_or_parse_incomplete"
    )
    assert expected in inspected.unresolved_by_construction


def test_source_owned_imported_constant_defaults_are_reconciled_not_self_attested(
    tmp_path, monkeypatch
):
    provider_path = tmp_path / "constant_provider.py"
    provider_path.write_text("COUNT = 8\nBYTES = 1024**3\n")
    owner_path = tmp_path / "constant_owner.py"
    owner_path.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from cyc05_constant_provider import COUNT, BYTES\n"
        "@dataclass(frozen=True)\n"
        "class Quota:\n"
        "    count: int = COUNT\n"
        "    byte_limit: int = BYTES\n"
    )

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    provider = load(provider_path, "cyc05_constant_provider")
    owner = load(owner_path, "cyc05_constant_owner")
    tree = ast.parse(owner_path.read_bytes(), filename=str(owner_path))
    statement = next(node for node in tree.body if isinstance(node, ast.ClassDef))

    def supported():
        return ledger._source_python_dataclass_binding_supported(
            tmp_path, owner.__name__, "Quota", owner_path.relative_to(tmp_path), tree, statement
        )

    assert owner.Quota().byte_limit == 1024**3
    assert supported()
    # Rebinding both import ends does not rewrite the actual source premise.
    monkeypatch.setattr(provider, "COUNT", 9)
    monkeypatch.setattr(owner, "COUNT", 9)
    assert not supported()
    monkeypatch.setattr(provider, "COUNT", 8)
    monkeypatch.setattr(owner, "COUNT", 8)
    assert supported()
    # A source change with the old loaded value is also distinct and rejected.
    provider_path.write_text("COUNT = 9\nBYTES = 1024**3\n")
    assert not supported()


def test_dataclass_constant_reader_does_not_execute_nonconstant_expression(monkeypatch):
    calls = []

    def dangerous():
        calls.append("executed")
        return 8

    monkeypatch.setattr(ledger, "dangerous", dangerous, raising=False)
    node = ast.parse("dangerous()", mode="eval").body
    assert ledger._source_immutable_constant_expression(node) is ledger._SOURCE_DERIVATION_FAILED
    assert calls == []


def test_finite_capture_reads_real_source_and_lock_bytes_without_an_empty_denominator(tmp_path):
    """Qualify the reused snapshot primitive; final loaded-profile replay is DA-06."""

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "cyc05-finite-profile"\n')
    lock = tmp_path / "uv.lock"
    lock.write_text("version = 1\n")
    source = tmp_path / "src" / "polisyos" / "owner.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n")
    closure = (("polisyos.owner", "src/polisyos/owner.py"),)
    initial, fence = ledger._stable_deployment_snapshot(tmp_path, capture_closure=closure)
    assert set(json.loads(initial)["files"]) == {
        "pyproject.toml",
        "uv.lock",
        "src/polisyos/owner.py",
    }
    same, same_fence = ledger._stable_deployment_snapshot(tmp_path, capture_closure=closure)
    assert same == initial and same_fence == fence
    source.write_text("VALUE = 2\n")
    changed_source, _ = ledger._stable_deployment_snapshot(tmp_path, capture_closure=closure)
    assert changed_source != initial
    source.write_text("VALUE = 1\n")
    lock.write_text("version = 2\n")
    changed_lock, _ = ledger._stable_deployment_snapshot(tmp_path, capture_closure=closure)
    assert changed_lock != initial
    # The original basis stays an immutable value; an empty/missing declared
    # path set is not a replacement positive snapshot.
    assert json.loads(initial)["files"]["uv.lock"] != json.loads(changed_lock)["files"]["uv.lock"]
    with pytest.raises(ledger.ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        ledger._stable_deployment_snapshot(tmp_path, capture_closure=())


def test_changed_cas_bytes_cannot_reuse_authenticated_build_input(tmp_path):
    kwargs = _configured_evidence(tmp_path)
    reference = kwargs["build_evidence_ref"]
    digest = reference.artifact_id.hex
    blob = (
        kwargs["evidence_store"].root
        / "artifacts"
        / "sha256"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.blob"
    )
    blob.write_bytes(blob.read_bytes() + b" ")
    ready = ledger.inspect_packaged_deployment_identity(**kwargs)
    assert ready.verdict != "PASS"
    assert ready.inputs["build_evidence_status"] == "not_established"
    assert _observe(kwargs).status == "not_established"


def _protocol_probe(tmp_path, monkeypatch):
    path = tmp_path / "protocol_owner.py"
    path.write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol, runtime_checkable\n"
        "@runtime_checkable\n"
        "class Reader(Protocol):\n"
        "    title: str\n"
        "    def read(self, size: int = -1) -> bytes: ...\n"
        "@runtime_checkable\n"
        "class RootedReader(Reader, Protocol):\n"
        "    @property\n"
        "    def root(self) -> str: ...\n"
    )
    spec = importlib.util.spec_from_file_location("cyc05_protocol_owner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    tree = ast.parse(path.read_bytes(), filename=str(path))

    def supports(name="RootedReader"):
        node = next(
            item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name
        )
        return ledger._source_python_protocol_binding_supported(
            tmp_path, module.__name__, name, path.relative_to(tmp_path), tree, node
        )

    return module, supports


def _declared_core_runtime_protocol_names():
    path = Path(artifacts.__file__).resolve().with_name("protocol.py")
    tree = ast.parse(path.read_bytes(), filename=str(path))
    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(item, ast.Name) and item.id == "runtime_checkable"
            for item in node.decorator_list
        )
    )


@pytest.mark.parametrize("name", _declared_core_runtime_protocol_names())
def test_actual_core_protocols_match_finite_source_replay(name):
    from polisyos.core.artifacts import protocol

    root = ledger._loaded_policy_engine_root()
    path = Path(protocol.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    assert ledger._source_python_protocol_binding_supported(
        root, protocol.__name__, name, path.relative_to(root), tree, node
    )


def test_protocol_replay_preserves_real_property_and_refuses_flag_or_method_tamper(
    tmp_path, monkeypatch
):
    module, supports = _protocol_probe(tmp_path, monkeypatch)
    assert supports("Reader")
    assert supports("RootedReader")
    with monkeypatch.context() as patcher:
        patcher.setattr(module.RootedReader, "_is_runtime_protocol", False)
        assert not supports()
    assert supports()
    with monkeypatch.context() as patcher:
        patcher.setattr(module.Reader, "read", lambda self, size=-1: b"forged")
        assert not supports()
    assert supports()
    calls = []

    def forbidden_annotations(format):
        calls.append(format)
        raise AssertionError("a rebound annotation callback must never execute")

    with monkeypatch.context() as patcher:
        patcher.setattr(module.Reader.read, "__annotate__", forbidden_annotations)
        assert not supports()
    assert calls == []
    assert supports()


def test_protocol_replay_refuses_decorator_rebind(tmp_path, monkeypatch):
    module, supports = _protocol_probe(tmp_path, monkeypatch)
    assert supports()
    monkeypatch.setattr(module, "runtime_checkable", lambda cls: cls)
    assert not supports()


def test_typing_provider_source_and_runtime_rebind_are_distinguished(tmp_path, monkeypatch):
    import typing

    module, supports = _protocol_probe(tmp_path, monkeypatch)
    del module
    assert supports()
    provider = Path(typing.__file__).resolve()
    original_read = Path.read_bytes
    original_source = original_read(provider)
    changed = original_source.replace(
        b"    cls._is_runtime_protocol = True", b"    cls._is_runtime_protocol = False", 1
    )
    assert changed != original_source
    with monkeypatch.context() as patcher:
        patcher.setattr(
            Path, "read_bytes", lambda path: changed if path == provider else original_read(path)
        )
        with pytest.raises(ledger.ConfidenceLedgerError, match="typing provider source"):
            ledger._typing_protocol_provider_projection()
        assert not supports()
    assert supports()
    with monkeypatch.context() as patcher:
        patcher.setattr(typing, "runtime_checkable", lambda cls: cls)
        with pytest.raises(ledger.ConfidenceLedgerError, match="typing provider binding"):
            ledger._typing_protocol_provider_projection()
        assert not supports()
    assert supports()


def test_typing_provider_profile_is_stable_under_normal_lazy_resolution():
    import typing

    initial = ledger._typing_protocol_provider_projection()
    # The typing backend's ordinary lazy module cache is an implementation
    # representation change, not a change to the selected backend identity.
    assert typing._lazy_annotationlib.Format is not None
    assert ledger._typing_protocol_provider_projection() == initial
    assert initial["independent_transform_verification"] is False


@pytest.mark.parametrize(
    "member",
    [
        "    observed.append('class-body')\n",
        "    def read(self, size: int = observed.append('default')) -> bytes: ...\n",
    ],
)
def test_protocol_replay_refuses_executable_class_or_default_without_replaying_it(
    tmp_path, monkeypatch, member
):
    path = tmp_path / "unsafe_protocol.py"
    path.write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol, runtime_checkable\n"
        "observed = []\n"
        "@runtime_checkable\n"
        "class Reader(Protocol):\n" + member
    )
    spec = importlib.util.spec_from_file_location("cyc05_unsafe_protocol", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    before = list(module.observed)
    assert len(before) == 1
    tree = ast.parse(path.read_bytes(), filename=str(path))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef))
    assert not ledger._source_python_protocol_binding_supported(
        tmp_path, module.__name__, "Reader", path.relative_to(tmp_path), tree, node
    )
    assert module.observed == before


@pytest.mark.parametrize("rebind_provider_too", [False, True])
def test_protocol_imported_base_cannot_be_coherently_rebound_to_another_valid_protocol(
    tmp_path, monkeypatch, rebind_provider_too
):
    source = tmp_path / "src" / "polisyos"
    source.mkdir(parents=True)
    provider_path = source / "_cyc05_protocol_provider.py"
    provider_path.write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol, runtime_checkable\n"
        "@runtime_checkable\n"
        "class Good(Protocol):\n"
        "    def good(self) -> bytes: ...\n"
        "@runtime_checkable\n"
        "class Bad(Protocol):\n"
        "    def bad(self) -> bytes: ...\n"
    )
    owner_path = source / "_cyc05_protocol_child.py"
    owner_path.write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol, runtime_checkable\n"
        "from polisyos._cyc05_protocol_provider import Good as Selected\n"
        "@runtime_checkable\n"
        "class Child(Selected, Protocol):\n"
        '    """The declared source selects Good."""\n'
    )

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    provider = load(provider_path, "polisyos._cyc05_protocol_provider")
    owner = load(owner_path, "polisyos._cyc05_protocol_child")
    tree = ast.parse(owner_path.read_bytes(), filename=str(owner_path))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef))

    def supported():
        return ledger._source_python_protocol_binding_supported(
            tmp_path, owner.__name__, "Child", owner_path.relative_to(tmp_path), tree, node
        )

    assert supported()
    monkeypatch.setattr(owner, "Selected", provider.Bad)
    if rebind_provider_too:
        monkeypatch.setattr(provider, "Good", provider.Bad)
    # Reconstructing a child from its same AST under the wrong live import
    # would fool a replay that trusted the live base as its own oracle.
    future = [
        item
        for item in tree.body
        if isinstance(item, ast.ImportFrom) and item.module == "__future__"
    ]
    exec(  # noqa: S102 - reconstruct this controlled adversarial test class
        compile(ast.Module(body=[*future, node], type_ignores=[]), str(owner_path), "exec"),
        vars(owner),
    )
    assert owner.Child.__bases__[0] is provider.Bad
    assert not supported()


def _context_protocol_probe(tmp_path, monkeypatch):
    # Surface the exact provider refusal separately from the Protocol bridge.
    # Each adversarial mutation happens only after this authentic positive.
    assert ledger._context_manager_provider_projection()["profile"] == (
        "python314_context_manager_generic_alias_v1"
    )
    path = tmp_path / "context_protocol.py"
    path.write_text(
        "from __future__ import annotations\n"
        "from contextlib import AbstractContextManager as Context\n"
        "from typing import Protocol, runtime_checkable\n"
        "@runtime_checkable\n"
        "class Stream(Protocol):\n"
        "    def read(self) -> bytes: ...\n"
        "@runtime_checkable\n"
        "class Attempt(Context[Stream], Protocol):\n"
        '    """A declared stream context."""\n'
    )
    spec = importlib.util.spec_from_file_location("cyc05_context_protocol", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    tree = ast.parse(path.read_bytes(), filename=str(path))
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "Attempt"
    )

    def supported():
        return ledger._source_python_protocol_binding_supported(
            tmp_path, module.__name__, "Attempt", path.relative_to(tmp_path), tree, node
        )

    return module, supported, tree, node, path


def test_context_manager_protocol_alias_is_source_bound_without_calling_arbitrary_getitem(
    tmp_path, monkeypatch
):
    import contextlib
    import types
    import typing

    module, supported, _tree, _node, _path = _context_protocol_probe(tmp_path, monkeypatch)
    assert supported()
    with monkeypatch.context() as patcher:
        patcher.setattr(
            module.Attempt,
            "__orig_bases__",
            (
                types.GenericAlias(contextlib.AbstractContextManager, typing.Protocol),
                typing.Protocol,
            ),
        )
        assert not supported()
    assert supported()
    calls = []

    def forbidden_getitem(cls, argument):
        calls.append(argument)
        raise AssertionError("verifier must not invoke changed subscription")

    with monkeypatch.context() as patcher:
        patcher.setattr(
            contextlib.AbstractContextManager, "__class_getitem__", classmethod(forbidden_getitem)
        )
        assert not supported()
    assert calls == []
    assert supported()


def test_context_manager_alias_rejects_coherent_origin_with_inherited_construction_hook(
    tmp_path, monkeypatch
):
    import abc
    import contextlib

    module, supported, tree, node, path = _context_protocol_probe(tmp_path, monkeypatch)
    assert supported()
    calls = []

    class UnexpectedBase(abc.ABC):
        @abc.abstractmethod
        def unexpected(self) -> None: ...

        def __init_subclass__(cls, **kwargs):
            calls.append(cls.__name__)
            super().__init_subclass__(**kwargs)

    origin_namespace = dict(vars(contextlib.AbstractContextManager))
    for name in ("__dict__", "__weakref__", "_abc_impl", "__abstractmethods__"):
        origin_namespace.pop(name, None)
    forged_origin = abc.ABCMeta("AbstractContextManager", (UnexpectedBase,), origin_namespace)
    monkeypatch.setattr(contextlib, "AbstractContextManager", forged_origin)
    monkeypatch.setattr(module, "Context", forged_origin)
    future = [
        item
        for item in tree.body
        if isinstance(item, ast.ImportFrom) and item.module == "__future__"
    ]
    exec(  # noqa: S102 - construct the controlled, coherently rebound adversarial fixture
        compile(ast.Module(body=[*future, node], type_ignores=[]), str(path), "exec"), vars(module)
    )
    assert module.Attempt.__orig_bases__[0].__origin__ is forged_origin
    calls.clear()
    assert not supported()
    assert calls == []


def test_context_manager_provider_refuses_executable_source_body_without_replaying_it(
    tmp_path, monkeypatch
):
    import contextlib

    _module, supported, _tree, _node, _path = _context_protocol_probe(tmp_path, monkeypatch)
    assert supported()
    provider_path = Path(contextlib.__file__).resolve()
    original_read = Path.read_bytes
    source = original_read(provider_path)
    changed = source.replace(
        b"    __slots__ = ()",
        b"    __slots__ = (); _cyc05_provider_observed.append('unsafe')",
        1,
    )
    assert changed != source
    observed = []
    monkeypatch.setattr(contextlib, "_cyc05_provider_observed", observed, raising=False)
    monkeypatch.setattr(
        Path, "read_bytes", lambda path: changed if path == provider_path else original_read(path)
    )
    assert not supported()
    assert observed == []


def test_context_manager_annotation_free_provider_accepts_only_genuine_empty_lazy_stores(
    tmp_path, monkeypatch
):
    import abc

    _module, supported, _tree, _node, _path = _context_protocol_probe(tmp_path, monkeypatch)
    initial = ledger._context_manager_provider_projection()
    assert abc.ABC.__annotations__ == {}
    assert ledger._context_manager_provider_projection() == initial
    assert supported()
    with monkeypatch.context() as patcher:
        patcher.setattr(abc.ABC, "__annotations__", {"forged": int})
        assert not supported()
    assert supported()
    calls = []

    def forbidden_annotations(format):
        calls.append(format)
        raise AssertionError("source-free annotations must never be evaluated")

    original_callback = abc.ABC.__annotate__
    try:
        # This C-level type property cannot be deleted by monkeypatch.undo().
        abc.ABC.__annotate__ = forbidden_annotations
        assert not supported()
    finally:
        abc.ABC.__annotate__ = original_callback
    assert calls == []
    assert supported()
