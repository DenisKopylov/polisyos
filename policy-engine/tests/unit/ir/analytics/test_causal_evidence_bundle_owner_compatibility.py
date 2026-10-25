"""Behavioral compatibility tests for causal EvidenceBundle owner writes."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    ProofStep,
    load_causal_evidence_bundle,
    load_causal_evidence_bundle_with_admission,
    persist_causal_evidence_bundle,
)
from polisyos.ir.artifacts import get_json_artifact

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.ir.artifacts import ArtifactStore
from polisyos.ir.migrations import base as migrations_base
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.registry.refs import (
    BoundsBundleRef,
    DataReadinessReportRef,
    EvidenceBundleRef,
    KernelEstimatorSpecRef,
    NegativeCertificateRef,
    ProofBundleRef,
    TwinNetworkResultRef,
)

_SCHEMA = "ir.causal_evidence_bundle"
_REGISTRY_KEY = "ir.causal_evidence_bundle"
_OWNER_REF = "ir.analytics.causal_evidence_bundle"
_DTO_ABI = "polisyos.ir.analytics.evidence_bundle.EvidenceBundle"
_CURRENT_WIRE_POLICY = ("evidence-bundle-optional-twin-field", "1")


class _StrictEvidenceBundleV10(BaseModel):
    """Pinned strict reader for the EvidenceBundle wire shape before Twin linkage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    query_str: str
    estimand_ast: dict[str, Any] = Field(default_factory=dict)
    proof_steps: tuple[ProofStep, ...] = ()
    data_provenance: tuple[DataProvenance, ...] = ()
    diagnostic_scores: dict[str, float] = Field(default_factory=dict)
    method_config: dict[str, Any] = Field(default_factory=dict)
    identification_status: str = ""
    algorithm_version: str = ""
    created_at: str = ""
    graph_fingerprint: str = ""
    estimand_fingerprint: str = ""
    compilation_steps: tuple[CompilationStep, ...] = ()
    estimation_steps: tuple[EstimationStep, ...] = ()
    diagnostic_dashboard: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    proof_bundle_ref: ProofBundleRef | None = None
    bounds_bundle_ref: BoundsBundleRef | None = None
    negative_certificate_ref: NegativeCertificateRef | None = None
    data_readiness_report_ref: DataReadinessReportRef | None = None
    kernel_estimator_spec_ref: KernelEstimatorSpecRef | None = None


def _read_strict_v10(store: ArtifactStore, ref: EvidenceBundleRef) -> _StrictEvidenceBundleV10:
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if schema is None or schema.name != _SCHEMA or schema.version != "1.0":
        version = None if schema is None else schema.version
        raise ValueError(f"Unsupported schema version {version!r}; expected '1.0'")
    return _StrictEvidenceBundleV10.model_validate(get_json_artifact(store, ref))


def _isolated_schema_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        migrations_base,
        "_SCHEMA_REGISTRY",
        {
            artifact: dict(versions)
            for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
        },
    )


def test_default_no_twin_write_round_trips_through_strict_v10_reader(
    tmp_path: Path,
) -> None:
    """The no-Twin payload stays consumable by a fresh strict legacy reader."""
    bundle = EvidenceBundle(run_id="no-twin", query_str="P(Y|do(X))")
    write_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))

    ref = persist_causal_evidence_bundle(write_store, bundle)

    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    manifest = fresh_store.get_manifest(ref)
    payload = get_json_artifact(fresh_store, ref)
    strict_legacy_value = _read_strict_v10(fresh_store, ref)
    admitted = load_causal_evidence_bundle_with_admission(fresh_store, ref)

    assert manifest.artifact_schema.name == _SCHEMA
    assert manifest.artifact_schema.version == "1.0"
    assert "twin_network_result_ref" not in payload
    assert strict_legacy_value.run_id == bundle.run_id
    assert admitted.value == bundle
    assert admitted.admission.source_registration.schema_version == "1.0"
    assert admitted.admission.source_registration.writable is True
    assert admitted.admission.current_registration.schema_version == "1.1"


def test_twin_write_uses_v11_and_strict_v10_reader_refuses(tmp_path: Path) -> None:
    """Twin-linked output uses its registered newer wire law."""
    twin_ref = TwinNetworkResultRef(artifact_id="sha256:" + "a" * 64)
    bundle = EvidenceBundle(
        run_id="with-twin",
        query_str="P(Y|do(X))",
        twin_network_result_ref=twin_ref,
    )
    write_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))

    ref = persist_causal_evidence_bundle(write_store, bundle)

    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    manifest = fresh_store.get_manifest(ref)
    payload = get_json_artifact(fresh_store, ref)
    assert manifest.artifact_schema.version == "1.1"
    assert payload["twin_network_result_ref"] == twin_ref.model_dump(mode="json")
    assert load_causal_evidence_bundle(fresh_store, ref) == bundle
    with pytest.raises(ValueError, match=r"Unsupported schema version '1.1'"):
        _read_strict_v10(fresh_store, ref)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _StrictEvidenceBundleV10.model_validate(payload)


def test_registered_nondefault_current_wire_row_remains_explicitly_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newly registered same-owner row remains usable without a default-path change."""
    _isolated_schema_registry(monkeypatch)
    migrations_base.register_schema_version(
        _SCHEMA,
        "1.2",
        compatibility=CompatibilityMode.BACKWARD,
        readable_versions=("1.0", "1.1"),
        additive_optional_fields=("twin_network_result_ref",),
        notes=("Exercise explicit EvidenceBundle owner extensions.",),
    )
    registered = migrations_base.register_ir_representation(
        registry_key=_REGISTRY_KEY,
        owner_ref=_OWNER_REF,
        dto_abi=_DTO_ABI,
        wire_policy_ref=_CURRENT_WIRE_POLICY[0],
        wire_policy_revision=_CURRENT_WIRE_POLICY[1],
        schema_name=_SCHEMA,
        schema_version="1.2",
        payload_version=None,
        profile_ref=None,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
    )
    bundle = EvidenceBundle(run_id="registered-extension", query_str="P(Y|do(X))")
    write_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))

    ref = persist_causal_evidence_bundle(write_store, bundle, schema_version="1.2")

    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    admitted = load_causal_evidence_bundle_with_admission(fresh_store, ref)
    assert admitted.value == bundle
    assert admitted.admission.source_registration == registered
    assert admitted.admission.source_registration.schema_version == "1.2"
    assert admitted.admission.current_registration.schema_version == "1.1"


def test_removing_v10_owner_row_refuses_even_while_schema_version_remains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matching version text does not replace exact owner-row admission."""
    _isolated_schema_registry(monkeypatch)
    rules = migrations_base._SCHEMA_REGISTRY
    legacy_rule = rules[_REGISTRY_KEY]["1.0"]
    assert legacy_rule.version == "1.0"
    rules[_REGISTRY_KEY]["1.0"] = replace(legacy_rule, representations=())

    current_rule = rules[_REGISTRY_KEY]["1.1"]
    rules[_REGISTRY_KEY]["1.1"] = replace(
        current_rule,
        representations=tuple(
            replace(
                row,
                readable_from=tuple(
                    key for key in row.readable_from if key.schema_version != "1.0"
                ),
            )
            for row in current_rule.representations
        ),
    )
    writes: list[object] = []

    def forbidden_put_json(*args: object, **kwargs: object) -> None:
        writes.append(args)
        raise AssertionError("missing v1.0 owner row reached CAS")

    monkeypatch.setattr(FileSystemCAS, "put_json", forbidden_put_json)
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match=r"write_override_unregistered|registry_invalid"):
        persist_causal_evidence_bundle(
            store,
            EvidenceBundle(run_id="removed-row", query_str="P(Y|do(X))"),
        )
    assert rules[_REGISTRY_KEY]["1.0"].version == "1.0"
    assert writes == []


@pytest.mark.parametrize("bad_version", ["", "   ", 7])
def test_malformed_explicit_schema_version_refuses_before_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_version: object
) -> None:
    writes: list[object] = []

    def forbidden_put_json(*args: object, **kwargs: object) -> None:
        writes.append(args)
        raise AssertionError("malformed version reached CAS")

    monkeypatch.setattr(FileSystemCAS, "put_json", forbidden_put_json)
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="write_override_invalid"):
        persist_causal_evidence_bundle(
            store,
            EvidenceBundle(run_id="bad-version", query_str="P(Y|do(X))"),
            schema_version=bad_version,  # type: ignore[arg-type]
        )
    assert writes == []


def test_twin_payload_cannot_be_written_under_no_twin_v10_law_before_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[object] = []

    def forbidden_put_json(*args: object, **kwargs: object) -> None:
        writes.append(args)
        raise AssertionError("mismatched Twin/v1.0 tuple reached CAS")

    monkeypatch.setattr(FileSystemCAS, "put_json", forbidden_put_json)
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    bundle = EvidenceBundle(
        run_id="twin-v10-mismatch",
        query_str="P(Y|do(X))",
        twin_network_result_ref=TwinNetworkResultRef(artifact_id="sha256:" + "b" * 64),
    )
    with pytest.raises(ValueError, match="source_invalid"):
        persist_causal_evidence_bundle(store, bundle, schema_version="1.0")
    assert writes == []
