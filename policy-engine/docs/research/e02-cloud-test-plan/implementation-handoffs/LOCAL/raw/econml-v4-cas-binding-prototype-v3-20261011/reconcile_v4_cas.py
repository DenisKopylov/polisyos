"""Reconcile retained V4 CAS objects under a new, candidate-only envelope.

This local prototype is deliberately post-hoc. It does not rewrite V4 artifacts,
rerun EconML, claim that V4 originally emitted a profile/adapter binding, or
promote a candidate computation to causal authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

PRODUCT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file() and (parent / "src" / "polisyos").is_dir()
)
LOCAL = PRODUCT_ROOT / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL"
PROFILE_DIR = LOCAL / "raw/econml-worker-profile-prototype-macos-arm64-v4-20261010"
RECORD_PATH = LOCAL / "econml-macos-arm64-worker-prototype.json"
SOURCE_CHECKPOINT_PATH = LOCAL / "raw/econml-v4-prototype-source-checkpoint-20261010/readback.json"
REMOTE_CHECKPOINT_PATH = (
    LOCAL / "raw/econml-v4-prototype-source-checkpoint-20261010/remote-readback.json"
)
DEFAULT_CAS_ROOT = (
    LOCAL
    / "raw/batched-blocking-focused-20261010"
    / "econml-mac-real-methodjob-cas-fresh-reader-prototype-v4"
    / "cas"
)
DEFAULT_POINTER = Path(__file__).resolve().parent / "binding-ref.json"
DEFAULT_READBACK = Path(__file__).resolve().parent / "fresh-reader-output.json"
sys.path.insert(0, str(PRODUCT_ROOT / "src"))

from polisyos.core.artifacts.manifest import (  # noqa: E402
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions  # noqa: E402
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes  # noqa: E402
from polisyos.foundry.methods.catalog.causal.protocols import (  # noqa: E402
    HTEObservationalData,
)

RECORD_SHA256 = "b6482af1701ddb2d44defee4fc39d8ee682b0672a599c0397d31551337ea16ab"
SOURCE_CHECKPOINT_SHA256 = "54f5b03a181f2b443934d4ccf6693c9685de8561bed3aae27a1f07abed9dfee2"
REMOTE_CHECKPOINT_SHA256 = "7b6b827288354289a5b48eff480cfb3ac4d5de1ef576d557436324a0a3391fe7"
EXECUTION_HEAD = "297b0557511234bb4b1bd3b09991cef0bd050a3f"
EXECUTION_TREE = "ad9ecc1c4bf2acd57b187b5a2534aa9f3b2d3ffd"
PROFILE_CHECKPOINT_HEAD = "19b0486608f0c134fcbff174c88d32fef82edafe"
PROFILE_CHECKPOINT_TREE = "b193643df4dcc876b1ccb8202411db099610f79e"
METHOD_FQN = "causal.hte.double_ml_worker_prototype@0.2.0"
PROFILE_ID = "econml-0.16.0-py312-macos-arm64-v4-prototype"
PRODUCER_COMPONENT = "candidate.econml_v4_posthoc_cas_reconciler_v3"
PRODUCER_VERSION = "0.3.0"
ENVELOPE_KIND = "candidate.econml.historical_methodjob_binding.v3"
ENVELOPE_SCHEMA = "polisyos.candidate.EconMLHistoricalMethodJobBindingV3"
ENVELOPE_VERSION = "0.3.0"
PROFILE_KIND = "candidate.econml.worker_profile_reconciliation.v3"
PROFILE_SCHEMA = "polisyos.candidate.EconMLWorkerProfileReconciliationV3"
PROFILE_VERSION = "0.3.0"
JSON_MEDIA = "application/json"
OCTET_STREAM_MEDIA = "application/octet-stream"


class StrictModel(BaseModel):
    """Base for the prototype's strict, immutable wire values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceRevision(StrictModel):
    head: str
    tree: str


class ProfileCheckpoint(StrictModel):
    head: str
    tree: str
    parent: str
    readback_sha256: str
    remote_readback_sha256: str
    file_count: int


class ProfileAsset(StrictModel):
    path: str
    role: str
    sha256: str
    artifact_ref: ArtifactRef


class HostRuntime(StrictModel):
    implementation: str
    machine: str
    macos_version: str
    python_version: str
    sys_platform: str


class WorkerRuntime(HostRuntime):
    executable: str
    worker_estimator_fqn: str
    worker_distribution_count: int
    distributions: dict[str, str]


class BackendEvidenceRuntime(StrictModel):
    backend: str
    determinism_tier: str
    execution_device: str
    fingerprint: str
    library_versions: dict[str, str]
    observed_scope: Literal["method_runner_host"]


class RuntimeScopes(StrictModel):
    method_runner_host: HostRuntime
    isolated_estimator_worker: WorkerRuntime
    backend_evidence: BackendEvidenceRuntime


class ProfileDescriptor(StrictModel):
    identity: Literal["candidate.econml.v4.profile-reconciliation@0.3.0"]
    relationship: Literal["posthoc_reconciliation_of_historical_v4_execution"]
    authority: Literal["candidate_computation_only"]
    descriptor_selected_for_execution: Literal[False]
    method_fqn: str
    profile_id: str
    method_signature_sha256: str
    lock_sha256: str
    bridge_sha256: str
    harness_sha256: str
    worker_plus_protocol_sha256: str
    execution_source: SourceRevision
    profile_source_checkpoint: ProfileCheckpoint
    assets: list[ProfileAsset]
    runtime_scopes: RuntimeScopes


class EnvelopeRefs(StrictModel):
    v4_execution_record: ArtifactRef
    source_checkpoint_readback: ArtifactRef
    remote_checkpoint_readback: ArtifactRef
    worker_profile: ArtifactRef
    source: ArtifactRef
    adapter: ArtifactRef
    method_result: ArtifactRef
    method_evidence: ArtifactRef
    binding_producer_source: ArtifactRef


class HistoricalMethodJobBinding(StrictModel):
    identity: Literal["candidate.econml.v4.posthoc_cas_binding@0.3.0"]
    relationship: Literal["posthoc_reconciliation_of_historical_v4_execution"]
    authority: Literal["candidate_computation_only"]
    status: Literal["reconciled_candidate_artifacts"]
    record_sha256: str
    producer_source_sha256: str
    method_job_id: str
    method_fqn: str
    profile_id: str
    method_signature_sha256: str
    request_id: str
    request_sha256: str
    data_sha256: str
    row_order_sha256: str
    seed: int
    execution_source: SourceRevision
    profile_source_checkpoint: ProfileCheckpoint
    refs: EnvelopeRefs
    runtime_scopes: RuntimeScopes
    limitations: list[str]


class RefPointer(StrictModel):
    identity: Literal["candidate.econml.v4.posthoc_cas_binding_pointer@0.3.0"]
    envelope_ref: ArtifactRef


def _ref(raw: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef.model_validate(raw)


def _dump_ref(ref: ArtifactRef) -> dict[str, Any]:
    return ref.model_dump(mode="json")


def _ref_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    """Return every selector field that determines the typed manifest view."""
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _expected_ref(raw: bytes, *, kind: str, media_type: str) -> ArtifactRef:
    """Derive a default-view reference from exact bytes and the declared artifact type."""
    return ArtifactRef(
        artifact_id=f"sha256:{_sha(raw)}",
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=None,
    )


def _require_ref_equal(actual: ArtifactRef, expected: ArtifactRef, code: str) -> None:
    """Compare the complete artifact reference, including selected manifest profile."""
    _require(_ref_identity(actual) == _ref_identity(expected), code)


def _require_ref_payload(raw: object, expected: ArtifactRef, code: str) -> None:
    """Validate and compare a nested reference without dropping typed selector fields."""
    _require(isinstance(raw, dict), code)
    _require(
        {"artifact_id", "kind", "media_type"} <= set(raw)
        and set(raw) <= {"artifact_id", "kind", "media_type", "manifest_profile_sha256"},
        code,
    )
    observed = ArtifactRef.model_validate(raw, strict=True)
    _require_ref_equal(observed, expected, code)
    _require(
        to_canonical_bytes(raw) == to_canonical_bytes(_dump_ref(expected)),
        code,
    )


def _require_model_equal(actual: BaseModel, expected: BaseModel, code: str) -> None:
    """Require the entire strict typed value to equal independently rebuilt expectations."""
    _require(type(actual) is type(expected) and actual == expected, code)


def _require_canonical_payload_equal(
    actual: object,
    expected: BaseModel,
    code: str,
) -> None:
    """Reject payload-shape/coercion differences after strict typed comparison."""
    observed = actual.model_dump(mode="json") if isinstance(actual, BaseModel) else actual
    _require(
        to_canonical_bytes(observed) == to_canonical_bytes(expected.model_dump(mode="json")),
        code,
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _record_from_pinned_local_file() -> tuple[dict[str, Any], bytes]:
    raw = RECORD_PATH.read_bytes()
    _require(_sha(raw) == RECORD_SHA256, "pinned_v4_execution_record_changed")
    return json.loads(raw), raw


def _read_checkpoint_files(
    record: dict[str, Any],
) -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    source_bytes = SOURCE_CHECKPOINT_PATH.read_bytes()
    remote_bytes = REMOTE_CHECKPOINT_PATH.read_bytes()
    _require(_sha(source_bytes) == SOURCE_CHECKPOINT_SHA256, "source_checkpoint_readback_changed")
    _require(_sha(remote_bytes) == REMOTE_CHECKPOINT_SHA256, "remote_checkpoint_readback_changed")
    source = json.loads(source_bytes)
    remote = json.loads(remote_bytes)
    checkpoint = record["profile_source_checkpoint"]
    _require(source["candidate"] == PROFILE_CHECKPOINT_HEAD, "profile_checkpoint_head_mismatch")
    _require(source["tree"] == PROFILE_CHECKPOINT_TREE, "profile_checkpoint_tree_mismatch")
    _require(source["parents"] == [EXECUTION_HEAD], "profile_checkpoint_parent_mismatch")
    _require(remote["remote_sha"] == PROFILE_CHECKPOINT_HEAD, "remote_checkpoint_head_mismatch")
    _require(remote["remote_tree"] == PROFILE_CHECKPOINT_TREE, "remote_checkpoint_tree_mismatch")
    _require(remote["verified_changed_files"] == 9, "remote_checkpoint_file_count_mismatch")
    _require(remote["exact_changed_files_and_bytes"] is True, "remote_checkpoint_bytes_unverified")
    _require(
        remote["source_readback_sha256"] == SOURCE_CHECKPOINT_SHA256,
        "remote_checkpoint_readback_mismatch",
    )
    _require(checkpoint["head"] == PROFILE_CHECKPOINT_HEAD, "record_checkpoint_head_mismatch")
    _require(checkpoint["tree"] == PROFILE_CHECKPOINT_TREE, "record_checkpoint_tree_mismatch")
    _require(checkpoint["parent"] == EXECUTION_HEAD, "record_checkpoint_parent_mismatch")
    _require(
        checkpoint["readback"] == str(SOURCE_CHECKPOINT_PATH.relative_to(PRODUCT_ROOT)),
        "record_checkpoint_readback_path_mismatch",
    )
    _require(
        checkpoint["readback_sha256"] == SOURCE_CHECKPOINT_SHA256,
        "record_checkpoint_readback_digest_mismatch",
    )
    _require(
        checkpoint["remote_readback"] == str(REMOTE_CHECKPOINT_PATH.relative_to(PRODUCT_ROOT)),
        "record_remote_checkpoint_readback_path_mismatch",
    )
    _require(
        checkpoint["remote_readback_sha256"] == REMOTE_CHECKPOINT_SHA256,
        "record_remote_checkpoint_readback_digest_mismatch",
    )
    _check_checkpoint_contents(record, source, remote)
    return source_bytes, remote_bytes, source, remote


def _check_checkpoint_contents(
    record: dict[str, Any], checkpoint: dict[str, Any], remote: dict[str, Any]
) -> None:
    expected_files = [
        {"path": f"{PRODUCT_ROOT.name}/{row['path']}", "sha256": row["sha256"]}
        for row in record["candidate"]["source_footprint"]
    ]
    _require(checkpoint["files"] == expected_files, "profile_checkpoint_file_set_mismatch")
    _require(
        len(checkpoint["files"])
        == record["profile_source_checkpoint"]["profile_source_count"]
        == 9,
        "profile_checkpoint_file_count_mismatch",
    )
    _require(
        remote["verified_changed_files"] == len(expected_files),
        "remote_checkpoint_file_count_mismatch",
    )
    _require(remote["exact_changed_files_and_bytes"] is True, "remote_checkpoint_bytes_unverified")
    _require(
        remote["source_readback_sha256"] == SOURCE_CHECKPOINT_SHA256,
        "remote_checkpoint_readback_mismatch",
    )
    _require(remote["remote_sha"] == checkpoint["candidate"], "remote_checkpoint_source_mismatch")
    _require(remote["remote_tree"] == checkpoint["tree"], "remote_checkpoint_tree_mismatch")


def _runtime_scopes(record: dict[str, Any], evidence: dict[str, Any]) -> RuntimeScopes:
    selected = record["candidate"]["selected_runtime"]
    backend = evidence["artifacts"]["backend_runtime_fingerprint"]
    worker = {
        **selected["worker"],
        "worker_estimator_fqn": selected["worker_estimator_fqn"],
        "worker_distribution_count": selected["worker_distribution_count"],
    }
    _require(
        worker["worker_distribution_count"] == len(worker["distributions"]),
        "selected_worker_distribution_inventory_mismatch",
    )
    return RuntimeScopes(
        method_runner_host=HostRuntime.model_validate(selected["server"]),
        isolated_estimator_worker=WorkerRuntime.model_validate(worker),
        backend_evidence=BackendEvidenceRuntime.model_validate(
            {
                "backend": backend["backend"],
                "determinism_tier": backend["determinism_tier"],
                "execution_device": backend["execution_device"],
                "fingerprint": backend["fingerprint"],
                "library_versions": backend["library_versions"],
                "observed_scope": "method_runner_host",
            }
        ),
    )


def _expected_profile_assets(record: dict[str, Any]) -> list[ProfileAsset]:
    """Rebuild profile assets from the pinned source footprint, not descriptor claims."""
    rows = record["candidate"]["source_footprint"]
    _require(len(rows) == 9, "pinned_profile_source_count_mismatch")
    assets: list[ProfileAsset] = []
    for row in rows:
        path = PRODUCT_ROOT / row["path"]
        _require(path.is_file(), f"pinned_profile_source_missing:{row['path']}")
        content = path.read_bytes()
        digest = _sha(content)
        _require(digest == row["sha256"], f"pinned_profile_source_changed:{row['path']}")
        assets.append(
            ProfileAsset(
                path=row["path"],
                role=row["role"],
                sha256=digest,
                artifact_ref=_expected_ref(
                    content,
                    kind="candidate.econml.worker_profile_source",
                    media_type=OCTET_STREAM_MEDIA,
                ),
            )
        )
    return assets


def _build_profile_descriptor(
    record: dict[str, Any],
    evidence: dict[str, Any],
    checkpoint_bytes: bytes,
    remote_bytes: bytes,
    assets: list[ProfileAsset],
) -> ProfileDescriptor:
    """Build every descriptor field from pinned record, readbacks, assets, and evidence."""
    candidate = record["candidate"]
    checkpoint = json.loads(checkpoint_bytes)
    return ProfileDescriptor(
        identity="candidate.econml.v4.profile-reconciliation@0.3.0",
        relationship="posthoc_reconciliation_of_historical_v4_execution",
        authority="candidate_computation_only",
        descriptor_selected_for_execution=False,
        method_fqn=candidate["method_fqn"],
        profile_id=candidate["profile_id"],
        method_signature_sha256=candidate["method_signature_sha256"],
        lock_sha256=candidate["lock_sha256"],
        bridge_sha256=candidate["bridge_sha256"],
        harness_sha256=candidate["harness_sha256"],
        worker_plus_protocol_sha256=candidate["worker_plus_protocol_sha256"],
        execution_source=SourceRevision(
            head=record["source_revision"]["head"],
            tree=record["source_revision"]["tree"],
        ),
        profile_source_checkpoint=ProfileCheckpoint(
            head=checkpoint["candidate"],
            tree=checkpoint["tree"],
            parent=checkpoint["parents"][0],
            readback_sha256=_sha(checkpoint_bytes),
            remote_readback_sha256=_sha(remote_bytes),
            file_count=len(assets),
        ),
        assets=assets,
        runtime_scopes=_runtime_scopes(record, evidence),
    )


def _check_manifest(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    expected_manifest_sha256: str | None = None,
    expected_inputs: list[tuple[str, str, str | None]] | None = None,
    expected_local_producer: bool = False,
    expected_media_type: str | None = None,
) -> ArtifactManifest:
    verification = store.verify(ref)
    _require(verification.ok, f"artifact_verification_failed:{kind}")
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    _require(str(manifest.artifact_id) == str(ref.artifact_id), f"artifact_id_mismatch:{kind}")
    _require(manifest.kind == kind and ref.kind == kind, f"artifact_kind_mismatch:{kind}")
    _require(manifest.media_type == ref.media_type, f"artifact_media_type_mismatch:{kind}")
    if expected_media_type is not None:
        _require(
            manifest.media_type == expected_media_type,
            f"artifact_media_type_mismatch:{kind}",
        )
    _require(schema is not None, f"artifact_schema_missing:{kind}")
    _require(
        schema.name == schema_name and schema.version == schema_version,
        f"artifact_schema_mismatch:{kind}",
    )
    if expected_local_producer:
        producer = manifest.producer
        _require(producer is not None, f"prototype_producer_missing:{kind}")
        _require(
            str(producer.component) == PRODUCER_COMPONENT,
            f"prototype_producer_component_mismatch:{kind}",
        )
        _require(
            producer.version == PRODUCER_VERSION, f"prototype_producer_version_mismatch:{kind}"
        )
    if expected_manifest_sha256 is not None:
        actual_manifest_sha = _sha(store.get_manifest_bytes(ref))
        _require(
            actual_manifest_sha == expected_manifest_sha256, f"historical_manifest_changed:{kind}"
        )
    if expected_inputs is not None:
        actual = [
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in manifest.inputs
        ]
        _require(actual == expected_inputs, f"artifact_lineage_mismatch:{kind}")
    return manifest


def _require_manifest_inputs(
    store: FileSystemCAS,
    ref: ArtifactRef,
    expected: list[InputRef],
    code: str,
) -> None:
    """Compare complete typed lineage edges, including selected manifest views."""
    actual = store.get_manifest(ref).inputs
    _require(actual == expected, code)


def _record_refs(record: dict[str, Any]) -> dict[str, ArtifactRef]:
    refs: dict[str, ArtifactRef] = {}
    for item in record["execution"]["artifact_refs"]:
        refs[item["role"]] = _ref(item["artifact_ref"])
    _require(
        set(refs) == {"source", "adapter", "method_result", "method_evidence"},
        "v4_ref_roles_incomplete",
    )
    _require(
        {role: str(ref.artifact_id) for role, ref in refs.items()}
        == {
            "source": ("sha256:b1d4e29a4dc5a77cb617572f087f497bfb50abae19f900f2b40e70e0f3c3b9dc"),
            "adapter": ("sha256:3c22f5e16e3d21ffe5ef7e9ccd405f8474b48db6ff117eed861c48cad1ff1241"),
            "method_result": (
                "sha256:436675a2a5440340ee9ef0c058fdfe01c4fb8282e778db880778ba9f9be45303"
            ),
            "method_evidence": (
                "sha256:43cacb0bbf2a68939165b9d537de6d79949846afa7a3642dbede829e2b28d241"
            ),
        },
        "unexpected_v4_artifact_identity",
    )
    return refs


def _load_pinned_profile_data_payload(
    record: dict[str, Any],
) -> Callable[[ArtifactRef, HTEObservationalData], dict[str, Any]]:
    """Load the historical data-digest routine only after verifying all nine files."""
    footprint = record["candidate"]["source_footprint"]
    _require(len(footprint) == 9, "pinned_profile_source_count_mismatch")
    for row in footprint:
        path = PRODUCT_ROOT / row["path"]
        _require(path.is_file(), f"pinned_profile_source_missing:{row['path']}")
        _require(
            _sha(path.read_bytes()) == row["sha256"], f"pinned_profile_source_changed:{row['path']}"
        )
    bridge_path = PROFILE_DIR / "bridge.py"
    spec = importlib.util.spec_from_file_location("_e02_pinned_v4_bridge", bridge_path)
    _require(spec is not None and spec.loader is not None, "pinned_profile_bridge_unloadable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module._data_payload


def _verify_historical_nested_references(
    result: dict[str, Any],
    evidence: dict[str, Any],
    refs: dict[str, ArtifactRef],
) -> None:
    """Check complete nested source/result refs at the consumer boundary."""
    binding = result["candidate_binding"]
    _require_ref_payload(
        binding["source_ref"], refs["source"], "result_source_ref_mismatch"
    )
    _require_ref_payload(
        evidence["method_result_ref"], refs["method_result"], "evidence_result_ref_mismatch"
    )


def _load_and_verify_historical_run(
    store: FileSystemCAS,
    record: dict[str, Any],
) -> tuple[dict[str, ArtifactRef], dict[str, Any], dict[str, Any], HTEObservationalData]:
    _require(
        record["record_status"] == "executed_candidate_computation_only",
        "v4_record_status_mismatch",
    )
    _require(record["authority"] == "candidate_computation_only", "v4_authority_mismatch")
    _require(record["source_revision"]["head"] == EXECUTION_HEAD, "v4_execution_head_mismatch")
    _require(record["source_revision"]["tree"] == EXECUTION_TREE, "v4_execution_tree_mismatch")
    _require(
        record["profile_source_checkpoint"]["head"] == PROFILE_CHECKPOINT_HEAD,
        "profile_checkpoint_not_pinned",
    )
    _require(record["candidate"]["method_fqn"] == METHOD_FQN, "v4_method_mismatch")
    _require(record["candidate"]["profile_id"] == PROFILE_ID, "v4_profile_mismatch")
    refs = _record_refs(record)
    _require(len(record["execution"]["artifact_refs"]) == 4, "v4_artifact_ref_count_mismatch")
    by_role = {item["role"]: item for item in record["execution"]["artifact_refs"]}
    _require(len(by_role) == 4, "v4_artifact_ref_role_collision")
    expected = {
        "source": (
            "prototype.hte_observational_data",
            "prototype.HTEObservationalData",
            "1.0.0",
            JSON_MEDIA,
            [],
        ),
        "adapter": (
            "scientist.unified_dag_adapter",
            "polisyos.scientist.UnifiedDagAdapter",
            "0.1.0",
            JSON_MEDIA,
            [],
        ),
        "method_result": (
            "scientist.method_result.causal.hte",
            "polisyos.scientist.MethodResult",
            "0.1.0",
            JSON_MEDIA,
            [(str(refs["source"].artifact_id), "input:hte_data", None)],
        ),
        "method_evidence": (
            "scientist.method_evidence",
            "polisyos.scientist.MethodExecutionEvidence",
            "0.1.0",
            JSON_MEDIA,
            [(str(refs["method_result"].artifact_id), "method_result", None)],
        ),
    }
    payloads: dict[str, Any] = {}
    for role, ref in refs.items():
        info = by_role[role]
        kind, schema_name, schema_version, media_type, inputs = expected[role]
        _require_ref_equal(
            ref,
            ArtifactRef(
                artifact_id=ref.artifact_id,
                kind=kind,
                media_type=media_type,
                manifest_profile_sha256=None,
            ),
            f"unexpected_v4_reference_shape:{role}",
        )
        _check_manifest(
            store,
            ref,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            expected_manifest_sha256=info["manifest_sha256"],
            expected_inputs=inputs,
            expected_media_type=media_type,
        )
        payloads[role] = from_canonical_bytes(store.get_bytes(ref))
    source_state = HTEObservationalData.model_validate(
        from_canonical_bytes(store.get_bytes(refs["source"]))
    )
    adapter = payloads["adapter"]
    binding = payloads["method_result"]["candidate_binding"]
    result_envelope = payloads["method_result"]["envelope"]
    evidence = payloads["method_evidence"]
    fixture = record["fixture"]
    candidate = record["candidate"]
    _require(adapter["method_fqn"] == METHOD_FQN, "adapter_method_mismatch")
    _require(binding["method_fqn"] == METHOD_FQN, "result_method_mismatch")
    _require(binding["profile_id"] == PROFILE_ID, "result_profile_mismatch")
    _require(binding["job_id"] == record["execution"]["method_job_id"], "result_job_mismatch")
    _verify_historical_nested_references(payloads["method_result"], evidence, refs)
    _require(
        binding["source_content_sha256"] == fixture["source_content_sha256"],
        "result_source_digest_mismatch",
    )
    _require(binding["data_sha256"] == fixture["data_sha256"], "result_data_digest_mismatch")
    _require(
        binding["row_order_sha256"] == fixture["row_order_sha256"], "result_row_order_mismatch"
    )
    _require(binding["request_id"] == fixture["request_id"], "result_request_id_mismatch")
    _require(
        binding["request_sha256"] == fixture["request_sha256"], "result_request_digest_mismatch"
    )
    _require(binding["seed"] == fixture["seed"], "result_seed_mismatch")
    _require(
        binding["method_signature_sha256"] == candidate["method_signature_sha256"],
        "result_signature_mismatch",
    )
    _require(binding["worker_lock_sha256"] == candidate["lock_sha256"], "result_lock_mismatch")
    _require(binding["bridge_code_sha256"] == candidate["bridge_sha256"], "result_bridge_mismatch")
    _require(binding["harness_sha256"] == candidate["harness_sha256"], "result_harness_mismatch")
    _require(
        binding["worker_code_sha256"] == candidate["worker_plus_protocol_sha256"],
        "result_worker_mismatch",
    )
    _require(
        binding["server_environment"] == candidate["selected_runtime"]["server"],
        "result_host_scope_mismatch",
    )
    _require(
        binding["worker_environment"] == candidate["selected_runtime"]["worker"],
        "result_worker_scope_mismatch",
    )
    _require(result_envelope["gate_eligible"] is False, "candidate_result_claims_gate_eligibility")
    _require(
        result_envelope["metadata"]["status"] == "success",
        "historical_candidate_computation_not_successful",
    )
    _require(evidence["method_fqn"] == METHOD_FQN, "evidence_method_mismatch")
    _require(
        evidence["result_ref"] == str(refs["method_result"].artifact_id),
        "evidence_result_id_mismatch",
    )
    data_payload = _load_pinned_profile_data_payload(record)
    recomputed_data = data_payload(refs["source"], source_state)
    _require(
        recomputed_data["data_sha256"] == fixture["data_sha256"],
        "source_data_digest_not_recomputed",
    )
    _require(
        recomputed_data["row_order_sha256"] == fixture["row_order_sha256"],
        "source_row_order_not_recomputed",
    )
    return refs, payloads["method_result"], evidence, source_state


def _profile_assets(
    store: FileSystemCAS,
    record: dict[str, Any],
) -> list[ProfileAsset]:
    assets: list[ProfileAsset] = []
    for expected in _expected_profile_assets(record):
        path = PRODUCT_ROOT / expected.path
        content = path.read_bytes()
        ref = store.put_bytes(
            content,
            PutOptions(
                kind="candidate.econml.worker_profile_source",
                media_type=OCTET_STREAM_MEDIA,
                schema=SchemaInfo(
                    name="polisyos.candidate.EconMLWorkerProfileSource", version="0.1.0"
                ),
                producer=ProducerInfo(component=PRODUCER_COMPONENT, version=PRODUCER_VERSION),
            ),
        )
        _require_ref_equal(
            ref,
            expected.artifact_ref,
            f"profile_source_ref_mismatch:{expected.path}",
        )
        assets.append(expected.model_copy(update={"artifact_ref": ref}))
    _require(len(assets) == 9, "profile_source_file_count_mismatch")
    return assets


def _put_bytes(
    store: FileSystemCAS,
    raw: bytes,
    *,
    kind: str,
    schema_info: SchemaInfo,
    media_type: str = JSON_MEDIA,
) -> ArtifactRef:
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind=kind,
            media_type=media_type,
            schema=schema_info,
            producer=ProducerInfo(component=PRODUCER_COMPONENT, version=PRODUCER_VERSION),
        ),
    )
    _require_ref_equal(
        ref,
        _expected_ref(raw, kind=kind, media_type=media_type),
        f"written_artifact_ref_mismatch:{kind}",
    )
    return ref


def _put_json(
    store: FileSystemCAS,
    payload: BaseModel,
    *,
    kind: str,
    schema_info: SchemaInfo,
    inputs: list[InputRef],
) -> ArtifactRef:
    dumped = payload.model_dump(mode="json")
    ref = store.put_json(
        dumped,
        PutOptions(
            kind=kind,
            media_type=JSON_MEDIA,
            schema=schema_info,
            producer=ProducerInfo(component=PRODUCER_COMPONENT, version=PRODUCER_VERSION),
            inputs=inputs,
        ),
    )
    _require_ref_equal(
        ref,
        _expected_ref(
            to_canonical_bytes(dumped),
            kind=kind,
            media_type=JSON_MEDIA,
        ),
        f"written_artifact_ref_mismatch:{kind}",
    )
    return ref


def _build_binding(
    record: dict[str, Any],
    refs_bundle: EnvelopeRefs,
    descriptor: ProfileDescriptor,
    producer_source_bytes: bytes,
) -> HistoricalMethodJobBinding:
    """Rebuild the complete envelope from independently verified source objects."""
    fixture = record["fixture"]
    candidate = record["candidate"]
    return HistoricalMethodJobBinding(
        identity="candidate.econml.v4.posthoc_cas_binding@0.3.0",
        relationship="posthoc_reconciliation_of_historical_v4_execution",
        authority="candidate_computation_only",
        status="reconciled_candidate_artifacts",
        record_sha256=RECORD_SHA256,
        producer_source_sha256=_sha(producer_source_bytes),
        method_job_id=record["execution"]["method_job_id"],
        method_fqn=candidate["method_fqn"],
        profile_id=candidate["profile_id"],
        method_signature_sha256=candidate["method_signature_sha256"],
        request_id=fixture["request_id"],
        request_sha256=fixture["request_sha256"],
        data_sha256=fixture["data_sha256"],
        row_order_sha256=fixture["row_order_sha256"],
        seed=fixture["seed"],
        execution_source=SourceRevision(
            head=record["source_revision"]["head"],
            tree=record["source_revision"]["tree"],
        ),
        profile_source_checkpoint=descriptor.profile_source_checkpoint,
        refs=refs_bundle,
        runtime_scopes=descriptor.runtime_scopes,
        limitations=[
            "posthoc_reconciliation_not_a_profile_ref_emitted_by_the_historical_method_job",
            "candidate_computation_only_not_causal_identification_or_calibration",
            "no_generic_structured_slot_abi_or_product_methodjob_lineage_extension",
            "unsigned_local_prototype_no_external_verifier_or_production_support",
        ],
    )


def write_binding(pointer_path: Path) -> dict[str, Any]:
    _require(
        not pointer_path.exists() and not pointer_path.is_symlink(),
        "binding_pointer_must_be_new",
    )
    record, record_bytes = _record_from_pinned_local_file()
    checkpoint_bytes, remote_bytes, _checkpoint, _remote = _read_checkpoint_files(record)
    store = FileSystemCAS(DEFAULT_CAS_ROOT)
    refs, _result, evidence, _source_state = _load_and_verify_historical_run(store, record)
    record_ref = _put_bytes(
        store,
        record_bytes,
        kind="candidate.econml.v4_execution_record",
        schema_info=SchemaInfo(
            name="polisyos.candidate.EconMLV4ExecutionRecord", version="0.1.0"
        ),
    )
    checkpoint_ref = _put_bytes(
        store,
        checkpoint_bytes,
        kind="candidate.econml.v4_profile_source_readback",
        schema_info=SchemaInfo(
            name="polisyos.candidate.EconMLV4ProfileSourceReadback", version="0.1.0"
        ),
    )
    remote_ref = _put_bytes(
        store,
        remote_bytes,
        kind="candidate.econml.v4_remote_profile_source_readback",
        schema_info=SchemaInfo(
            name="polisyos.candidate.EconMLV4RemoteProfileSourceReadback", version="0.1.0"
        ),
    )
    assets = _profile_assets(store, record)
    descriptor = _build_profile_descriptor(
        record, evidence, checkpoint_bytes, remote_bytes, assets
    )
    descriptor_inputs = [
        input_ref_from_artifact_ref(record_ref, role="v4_execution_record"),
        input_ref_from_artifact_ref(checkpoint_ref, role="v4_profile_source_checkpoint"),
        input_ref_from_artifact_ref(remote_ref, role="v4_profile_source_checkpoint_remote"),
        *[
            input_ref_from_artifact_ref(asset.artifact_ref, role=f"profile_source:{asset.path}")
            for asset in assets
        ],
    ]
    profile_ref = _put_json(
        store,
        descriptor,
        kind=PROFILE_KIND,
        schema_info=SchemaInfo(name=PROFILE_SCHEMA, version=PROFILE_VERSION),
        inputs=descriptor_inputs,
    )
    _require_ref_equal(
        profile_ref,
        _expected_ref(
            to_canonical_bytes(descriptor.model_dump(mode="json")),
            kind=PROFILE_KIND,
            media_type=JSON_MEDIA,
        ),
        "written_profile_descriptor_ref_mismatch",
    )
    producer_source_bytes = Path(__file__).read_bytes()
    refs_bundle = EnvelopeRefs(
        v4_execution_record=record_ref,
        source_checkpoint_readback=checkpoint_ref,
        remote_checkpoint_readback=remote_ref,
        worker_profile=profile_ref,
        source=refs["source"],
        adapter=refs["adapter"],
        method_result=refs["method_result"],
        method_evidence=refs["method_evidence"],
        binding_producer_source=_put_bytes(
            store,
            producer_source_bytes,
            kind="candidate.econml.posthoc_binding_producer_source",
            schema_info=SchemaInfo(
                name="polisyos.candidate.EconMLPosthocBindingProducerSource",
                version="0.1.0",
            ),
            media_type=OCTET_STREAM_MEDIA,
        ),
    )
    binding = _build_binding(record, refs_bundle, descriptor, producer_source_bytes)
    envelope_inputs = [
        input_ref_from_artifact_ref(record_ref, role="v4_execution_record"),
        input_ref_from_artifact_ref(checkpoint_ref, role="v4_profile_source_checkpoint"),
        input_ref_from_artifact_ref(remote_ref, role="v4_profile_source_checkpoint_remote"),
        input_ref_from_artifact_ref(profile_ref, role="reconciled_worker_profile"),
        input_ref_from_artifact_ref(refs["source"], role="v4_method_input:hte_data"),
        input_ref_from_artifact_ref(refs["adapter"], role="v4_method_adapter"),
        input_ref_from_artifact_ref(refs["method_result"], role="v4_method_result"),
        input_ref_from_artifact_ref(refs["method_evidence"], role="v4_method_evidence"),
        input_ref_from_artifact_ref(
            refs_bundle.binding_producer_source, role="reconciliation_producer_source"
        ),
    ]
    envelope_ref = _put_json(
        store,
        binding,
        kind=ENVELOPE_KIND,
        schema_info=SchemaInfo(name=ENVELOPE_SCHEMA, version=ENVELOPE_VERSION),
        inputs=envelope_inputs,
    )
    _require_ref_equal(
        envelope_ref,
        _expected_ref(
            to_canonical_bytes(binding.model_dump(mode="json")),
            kind=ENVELOPE_KIND,
            media_type=JSON_MEDIA,
        ),
        "written_binding_ref_mismatch",
    )
    pointer = RefPointer(
        identity="candidate.econml.v4.posthoc_cas_binding_pointer@0.3.0",
        envelope_ref=envelope_ref,
    )
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_bytes(to_canonical_bytes(pointer.model_dump(mode="json")))
    return {
        "status": "written_candidate_only_posthoc_binding",
        "authority": "candidate_computation_only",
        "envelope_ref": _dump_ref(envelope_ref),
        "pointer_path": str(pointer_path),
        "cas_root": str(DEFAULT_CAS_ROOT),
        "record_sha256": RECORD_SHA256,
        "profile_asset_count": len(assets),
        "cas_writes": 1 + 1 + 1 + len(assets) + 1 + 1 + 1,
    }


def _load_record_artifact(store: FileSystemCAS, ref: ArtifactRef) -> tuple[dict[str, Any], bytes]:
    _check_manifest(
        store,
        ref,
        kind="candidate.econml.v4_execution_record",
        schema_name="polisyos.candidate.EconMLV4ExecutionRecord",
        schema_version="0.1.0",
        expected_inputs=[],
        expected_local_producer=True,
        expected_media_type=JSON_MEDIA,
    )
    raw = store.get_bytes(ref)
    _require(_sha(raw) == RECORD_SHA256, "cas_record_bytes_do_not_match_pinned_record")
    _require_ref_equal(
        ref,
        _expected_ref(raw, kind="candidate.econml.v4_execution_record", media_type=JSON_MEDIA),
        "cas_record_reference_mismatch",
    )
    return json.loads(raw), raw


def _load_json_artifact(store: FileSystemCAS, ref: ArtifactRef) -> object:
    return from_canonical_bytes(store.get_bytes(ref))


def _verify_profile_descriptor(
    store: FileSystemCAS,
    descriptor_ref: ArtifactRef,
    record: dict[str, Any],
    record_ref: ArtifactRef,
    checkpoint_ref: ArtifactRef,
    remote_ref: ArtifactRef,
    evidence: dict[str, Any],
) -> ProfileDescriptor:
    payload = _load_json_artifact(store, descriptor_ref)
    return _validate_profile_descriptor_payload(
        store,
        descriptor_ref,
        payload,
        record,
        record_ref,
        checkpoint_ref,
        remote_ref,
        evidence,
    )


def _validate_profile_descriptor_payload(
    store: FileSystemCAS,
    descriptor_ref: ArtifactRef,
    payload: object,
    record: dict[str, Any],
    record_ref: ArtifactRef,
    checkpoint_ref: ArtifactRef,
    remote_ref: ArtifactRef,
    evidence: dict[str, Any],
) -> ProfileDescriptor:
    """Apply the reader's full descriptor check to stored or adversarial payloads."""
    _check_manifest(
        store,
        descriptor_ref,
        kind=PROFILE_KIND,
        schema_name=PROFILE_SCHEMA,
        schema_version=PROFILE_VERSION,
        expected_media_type=JSON_MEDIA,
        expected_local_producer=True,
    )
    descriptor = ProfileDescriptor.model_validate(payload)
    checkpoint_bytes = store.get_bytes(checkpoint_ref)
    remote_bytes = store.get_bytes(remote_ref)
    expected_assets = _expected_profile_assets(record)
    expected = _build_profile_descriptor(
        record, evidence, checkpoint_bytes, remote_bytes, expected_assets
    )
    _require_model_equal(descriptor, expected, "profile_descriptor_full_binding_mismatch")
    _require_canonical_payload_equal(
        payload, expected, "profile_descriptor_payload_shape_mismatch"
    )
    descriptor_bytes = to_canonical_bytes(expected.model_dump(mode="json"))
    _require_ref_equal(
        descriptor_ref,
        _expected_ref(descriptor_bytes, kind=PROFILE_KIND, media_type=JSON_MEDIA),
        "profile_descriptor_reference_mismatch",
    )
    expected_inputs = [
        input_ref_from_artifact_ref(record_ref, role="v4_execution_record"),
        input_ref_from_artifact_ref(checkpoint_ref, role="v4_profile_source_checkpoint"),
        input_ref_from_artifact_ref(remote_ref, role="v4_profile_source_checkpoint_remote"),
        *[
            input_ref_from_artifact_ref(asset.artifact_ref, role=f"profile_source:{asset.path}")
            for asset in expected_assets
        ],
    ]
    _require_manifest_inputs(
        store, descriptor_ref, expected_inputs, "profile_descriptor_lineage_mismatch"
    )
    for asset in expected_assets:
        _check_manifest(
            store,
            asset.artifact_ref,
            kind="candidate.econml.worker_profile_source",
            schema_name="polisyos.candidate.EconMLWorkerProfileSource",
            schema_version="0.1.0",
            expected_inputs=[],
            expected_local_producer=True,
            expected_media_type=OCTET_STREAM_MEDIA,
        )
        _require(
            _sha(store.get_bytes(asset.artifact_ref)) == asset.sha256,
            "profile_asset_bytes_mismatch",
        )
    return descriptor


def _verify_readback_artifact(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    kind: str,
    schema: str,
    expected_sha256: str,
) -> dict[str, Any]:
    _check_manifest(
        store,
        ref,
        kind=kind,
        schema_name=schema,
        schema_version="0.1.0",
        expected_inputs=[],
        expected_local_producer=True,
        expected_media_type=JSON_MEDIA,
    )
    raw = store.get_bytes(ref)
    _require(_sha(raw) == expected_sha256, f"readback_bytes_changed:{kind}")
    _require_ref_equal(
        ref,
        _expected_ref(raw, kind=kind, media_type=JSON_MEDIA),
        f"readback_reference_mismatch:{kind}",
    )
    return json.loads(raw)


def _validate_envelope_payload(
    store: FileSystemCAS,
    payload: object,
    *,
    expected_envelope_ref: ArtifactRef,
    include_negative_controls: bool = True,
) -> dict[str, Any]:
    envelope = HistoricalMethodJobBinding.model_validate(payload)
    _check_manifest(
        store,
        expected_envelope_ref,
        kind=ENVELOPE_KIND,
        schema_name=ENVELOPE_SCHEMA,
        schema_version=ENVELOPE_VERSION,
        expected_local_producer=True,
        expected_media_type=JSON_MEDIA,
    )
    refs = envelope.refs
    _check_manifest(
        store,
        refs.binding_producer_source,
        kind="candidate.econml.posthoc_binding_producer_source",
        schema_name="polisyos.candidate.EconMLPosthocBindingProducerSource",
        schema_version="0.1.0",
        expected_local_producer=True,
        expected_inputs=[],
        expected_media_type=OCTET_STREAM_MEDIA,
    )
    producer_source_bytes = store.get_bytes(refs.binding_producer_source)
    current_source_bytes = Path(__file__).read_bytes()
    _require(
        producer_source_bytes == current_source_bytes,
        "reconciliation_source_artifact_mismatch",
    )
    _require_ref_equal(
        refs.binding_producer_source,
        _expected_ref(
            producer_source_bytes,
            kind="candidate.econml.posthoc_binding_producer_source",
            media_type=OCTET_STREAM_MEDIA,
        ),
        "reconciliation_source_reference_mismatch",
    )
    record, _record_bytes = _load_record_artifact(store, refs.v4_execution_record)
    checkpoint = _verify_readback_artifact(
        store,
        refs.source_checkpoint_readback,
        kind="candidate.econml.v4_profile_source_readback",
        schema="polisyos.candidate.EconMLV4ProfileSourceReadback",
        expected_sha256=SOURCE_CHECKPOINT_SHA256,
    )
    remote = _verify_readback_artifact(
        store,
        refs.remote_checkpoint_readback,
        kind="candidate.econml.v4_remote_profile_source_readback",
        schema="polisyos.candidate.EconMLV4RemoteProfileSourceReadback",
        expected_sha256=REMOTE_CHECKPOINT_SHA256,
    )
    _check_checkpoint_contents(record, checkpoint, remote)
    original_refs, result, evidence, _source_state = _load_and_verify_historical_run(store, record)
    descriptor = _verify_profile_descriptor(
        store,
        refs.worker_profile,
        record,
        refs.v4_execution_record,
        refs.source_checkpoint_readback,
        refs.remote_checkpoint_readback,
        evidence,
    )
    expected_profile_ref = _expected_ref(
        to_canonical_bytes(descriptor.model_dump(mode="json")),
        kind=PROFILE_KIND,
        media_type=JSON_MEDIA,
    )
    expected_refs = EnvelopeRefs(
        v4_execution_record=refs.v4_execution_record,
        source_checkpoint_readback=refs.source_checkpoint_readback,
        remote_checkpoint_readback=refs.remote_checkpoint_readback,
        worker_profile=expected_profile_ref,
        source=original_refs["source"],
        adapter=original_refs["adapter"],
        method_result=original_refs["method_result"],
        method_evidence=original_refs["method_evidence"],
        binding_producer_source=refs.binding_producer_source,
    )
    expected_envelope = _build_binding(record, expected_refs, descriptor, current_source_bytes)
    _require_model_equal(envelope, expected_envelope, "envelope_full_binding_mismatch")
    _require_canonical_payload_equal(
        payload, expected_envelope, "envelope_payload_shape_mismatch"
    )
    _require_ref_equal(
        expected_envelope_ref,
        _expected_ref(
            to_canonical_bytes(expected_envelope.model_dump(mode="json")),
            kind=ENVELOPE_KIND,
            media_type=JSON_MEDIA,
        ),
        "envelope_reference_mismatch",
    )
    _require(result["envelope"]["gate_eligible"] is False, "historical_result_gate_eligible")
    expected_envelope_inputs = [
        input_ref_from_artifact_ref(expected_refs.v4_execution_record, role="v4_execution_record"),
        input_ref_from_artifact_ref(
            expected_refs.source_checkpoint_readback, role="v4_profile_source_checkpoint"
        ),
        input_ref_from_artifact_ref(
            expected_refs.remote_checkpoint_readback,
            role="v4_profile_source_checkpoint_remote",
        ),
        input_ref_from_artifact_ref(expected_refs.worker_profile, role="reconciled_worker_profile"),
        input_ref_from_artifact_ref(expected_refs.source, role="v4_method_input:hte_data"),
        input_ref_from_artifact_ref(expected_refs.adapter, role="v4_method_adapter"),
        input_ref_from_artifact_ref(expected_refs.method_result, role="v4_method_result"),
        input_ref_from_artifact_ref(expected_refs.method_evidence, role="v4_method_evidence"),
        input_ref_from_artifact_ref(
            expected_refs.binding_producer_source, role="reconciliation_producer_source"
        ),
    ]
    _require_manifest_inputs(
        store,
        expected_envelope_ref,
        expected_envelope_inputs,
        "envelope_manifest_lineage_mismatch",
    )
    return {
        "identity": envelope.identity,
        "authority": envelope.authority,
        "producer_source_sha256": expected_envelope.producer_source_sha256,
        "method_job_id": envelope.method_job_id,
        "method_fqn": envelope.method_fqn,
        "profile_id": envelope.profile_id,
        "refs": {name: _dump_ref(getattr(refs, name)) for name in EnvelopeRefs.model_fields},
        "source_observations": {
            "source_rows": record["fixture"]["rows"],
            "source_schema": "prototype.HTEObservationalData@1.0.0",
            "input_manifest_edge": "input:hte_data",
        },
        "runtime_scope_names": [
            "method_runner_host",
            "isolated_estimator_worker",
            "backend_evidence",
        ],
        "result_gate_eligible": False,
        "limitations": list(envelope.limitations),
        "negative_controls": (
            _negative_controls(store, envelope, expected_envelope_ref)
            if include_negative_controls
            else []
        ),
    }


def _negative_controls(
    store: FileSystemCAS,
    envelope: HistoricalMethodJobBinding,
    envelope_ref: ArtifactRef,
) -> list[dict[str, str]]:
    baseline = envelope.model_dump(mode="json")
    cases: list[tuple[str, Any]] = []

    substituted = json.loads(json.dumps(baseline))
    substituted["refs"]["adapter"] = substituted["refs"]["method_result"]
    cases.append(("generic_reference_substitution", substituted))

    stale = json.loads(json.dumps(baseline))
    stale["profile_id"] = "econml-0.16.0-py312-macos-arm64-v3-prototype"
    cases.append(("stale_sibling_profile", stale))

    forged = json.loads(json.dumps(baseline))
    forged["causal_validity"] = "identified"
    cases.append(("forged_self_authority_field", forged))

    foreign_execution = json.loads(json.dumps(baseline))
    foreign_execution["execution_source"]["head"] = "f" * 40
    cases.append(("envelope_mirrored_foreign_execution_source", foreign_execution))

    false_checkpoint = json.loads(json.dumps(baseline))
    false_checkpoint["profile_source_checkpoint"]["readback_sha256"] = "0" * 64
    cases.append(("envelope_mirrored_false_local_checkpoint_digest", false_checkpoint))

    false_remote_checkpoint = json.loads(json.dumps(baseline))
    false_remote_checkpoint["profile_source_checkpoint"]["remote_readback_sha256"] = "f" * 64
    cases.append(("envelope_mirrored_false_remote_checkpoint_digest", false_remote_checkpoint))

    for field, value, label in (
        ("kind", "candidate.econml.unrelated", "kind"),
        ("media_type", "application/octet-stream", "media_type"),
        ("manifest_profile_sha256", f"sha256:{'0' * 64}", "profile"),
    ):
        mutated_ref = json.loads(json.dumps(baseline))
        mutated_ref["refs"]["source"][field] = value
        cases.append((f"envelope_source_ref_wrong_{label}", mutated_ref))

    swapped = json.loads(json.dumps(baseline))
    swapped_runtime = swapped["runtime_scopes"]["method_runner_host"]
    swapped["runtime_scopes"]["method_runner_host"] = swapped["runtime_scopes"][
        "isolated_estimator_worker"
    ]
    swapped["runtime_scopes"]["isolated_estimator_worker"] = swapped_runtime
    cases.append(("host_worker_scope_swap", swapped))

    outcomes: list[dict[str, str]] = []

    def _expect_refusal(name: str, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (ValidationError, ValueError) as exc:
            outcomes.append(
                {
                    "case": name,
                    "outcome": "refused",
                    "reason_type": type(exc).__name__,
                    "reason": str(exc),
                }
            )
        else:
            raise RuntimeError(f"negative_control_unexpectedly_accepted:{name}")

    for name, mutated in cases:
        _expect_refusal(
            name,
            lambda mutated=mutated: _validate_envelope_payload(
                store,
                mutated,
                expected_envelope_ref=envelope_ref,
                include_negative_controls=False,
            ),
        )

    refs = envelope.refs
    record, _record_bytes = _load_record_artifact(store, refs.v4_execution_record)
    _checkpoint = _verify_readback_artifact(
        store,
        refs.source_checkpoint_readback,
        kind="candidate.econml.v4_profile_source_readback",
        schema="polisyos.candidate.EconMLV4ProfileSourceReadback",
        expected_sha256=SOURCE_CHECKPOINT_SHA256,
    )
    _remote = _verify_readback_artifact(
        store,
        refs.remote_checkpoint_readback,
        kind="candidate.econml.v4_remote_profile_source_readback",
        schema="polisyos.candidate.EconMLV4RemoteProfileSourceReadback",
        expected_sha256=REMOTE_CHECKPOINT_SHA256,
    )
    original_refs, result, evidence, _source_state = _load_and_verify_historical_run(store, record)
    descriptor = _verify_profile_descriptor(
        store,
        refs.worker_profile,
        record,
        refs.v4_execution_record,
        refs.source_checkpoint_readback,
        refs.remote_checkpoint_readback,
        evidence,
    )
    descriptor_baseline = descriptor.model_dump(mode="json")
    descriptor_mutations: list[tuple[str, Any]] = []

    foreign_descriptor = json.loads(json.dumps(descriptor_baseline))
    foreign_descriptor["execution_source"]["head"] = "f" * 40
    descriptor_mutations.append(("descriptor_foreign_execution_source", foreign_descriptor))

    for field, label in (
        ("readback_sha256", "local"),
        ("remote_readback_sha256", "remote"),
    ):
        bad_checkpoint = json.loads(json.dumps(descriptor_baseline))
        bad_checkpoint["profile_source_checkpoint"][field] = "0" * 64
        descriptor_mutations.append((f"descriptor_false_{label}_checkpoint_digest", bad_checkpoint))

    for field, value, label in (
        ("kind", "candidate.econml.unrelated", "kind"),
        ("media_type", JSON_MEDIA, "media_type"),
        ("manifest_profile_sha256", f"sha256:{'0' * 64}", "profile"),
    ):
        bad_asset_ref = json.loads(json.dumps(descriptor_baseline))
        bad_asset_ref["assets"][0]["artifact_ref"][field] = value
        descriptor_mutations.append((f"descriptor_asset_ref_wrong_{label}", bad_asset_ref))

    for name, mutated in descriptor_mutations:
        _expect_refusal(
            name,
            lambda mutated=mutated: _validate_profile_descriptor_payload(
                store,
                refs.worker_profile,
                mutated,
                record,
                refs.v4_execution_record,
                refs.source_checkpoint_readback,
                refs.remote_checkpoint_readback,
                evidence,
            ),
        )

    for field, value, label in (
        ("kind", "candidate.econml.unrelated", "kind"),
        ("media_type", "application/octet-stream", "media_type"),
        ("manifest_profile_sha256", f"sha256:{'0' * 64}", "profile"),
    ):
        result_mutation = json.loads(json.dumps(result))
        result_mutation["candidate_binding"]["source_ref"][field] = value
        _expect_refusal(
            f"nested_result_source_ref_wrong_{label}",
            lambda result_mutation=result_mutation: _verify_historical_nested_references(
                result_mutation, evidence, original_refs
            ),
        )
        evidence_mutation = json.loads(json.dumps(evidence))
        evidence_mutation["method_result_ref"][field] = value
        _expect_refusal(
            f"nested_evidence_result_ref_wrong_{label}",
            lambda evidence_mutation=evidence_mutation: _verify_historical_nested_references(
                result, evidence_mutation, original_refs
            ),
        )
    return outcomes


def read_binding(pointer_path: Path, output_path: Path) -> dict[str, Any]:
    _require(
        not output_path.exists() and not output_path.is_symlink(),
        "readback_output_must_be_new",
    )
    pointer = RefPointer.model_validate_json(pointer_path.read_bytes())
    expected_id = f"sha256:{RECORD_SHA256}"
    store = FileSystemCAS(DEFAULT_CAS_ROOT)
    _check_manifest(
        store,
        pointer.envelope_ref,
        kind=ENVELOPE_KIND,
        schema_name=ENVELOPE_SCHEMA,
        schema_version=ENVELOPE_VERSION,
        expected_local_producer=True,
        expected_media_type=JSON_MEDIA,
    )
    payload = _load_json_artifact(store, pointer.envelope_ref)
    result = _validate_envelope_payload(store, payload, expected_envelope_ref=pointer.envelope_ref)
    output = {
        "status": "fresh_process_candidate_binding_read_succeeded",
        "authority": "candidate_computation_only",
        "envelope_ref": _dump_ref(pointer.envelope_ref),
        "producer_source_sha256": result["producer_source_sha256"],
        "producer_source_artifact_ref": result["refs"]["binding_producer_source"],
        "cas_root": str(DEFAULT_CAS_ROOT),
        "record_pin": expected_id,
        "binding": result,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(to_canonical_bytes(output))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("write", "read"))
    parser.add_argument("--pointer", type=Path, default=DEFAULT_POINTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_READBACK)
    args = parser.parse_args()
    try:
        output = (
            write_binding(args.pointer)
            if args.mode == "write"
            else read_binding(args.pointer, args.output)
        )
    except (OSError, ValueError, ValidationError, KeyError, TypeError) as exc:
        sys.stderr.write(
            json.dumps(
                {"status": "refused", "error_type": type(exc).__name__, "error": str(exc)},
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    sys.stdout.write(json.dumps(output, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
