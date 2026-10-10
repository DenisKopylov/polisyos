"""Local-only actual MethodJob→CAS→fresh-reader harness for the Mac worker prototype."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import runpy
import subprocess
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, from_canonical_obj
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import foundry_method
from polisyos.foundry.methods.catalog.causal._common import wrap_causal_output
from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.compute.runner import run_job

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

PROFILE_DIRECTORY = Path(__file__).resolve().parent
RAW_DIRECTORY = PROFILE_DIRECTORY.parent
PRODUCT_ROOT = next(
    parent
    for parent in PROFILE_DIRECTORY.parents
    if (parent / "pyproject.toml").is_file() and (parent / "src" / "polisyos").is_dir()
)
WORKER_PYTHON = RAW_DIRECTORY / "econml-macos-arm64-worker-env" / "bin" / "python"
LOCK_SHA256 = "5016a249a7dbe37ad22a3e0e15ab495b9e63a5a2d7c3f68cbcba04ad09fbfb0d"
CODE_SHA256 = "85f4ef138921b012f99a16a611da547e30a135f19a5c27d1fb6b417c010222a8"
BRIDGE_SHA256 = "3d2aa2c2997117dfeebd5d712017b5a243f733b3ba5acbe4318ea9adecb9c5e8"
METHOD_FQN = "causal.hte.double_ml_worker_prototype@0.2.0"
PROFILE_ID = "econml-0.16.0-py312-macos-arm64-v4-prototype"
PREVIOUS_METHOD_FQN = "causal.hte.double_ml_worker_prototype@0.1.0"
PREVIOUS_PROFILE_ID = "econml-0.16.0-py312-macos-arm64-prototype"
PREVIOUS_CODE_SHA256 = "fb3755badb40c33d08a4e5c75cc59217b04b68f03c0fa74bad080cb38b59804b"
PREVIOUS_HARNESS_SHA256 = "135ade741f0bb960e5307727ab7fdf1a05cef437019ad8aefe1017d093f55021"
PREVIOUS_PROFILE_DIRECTORY = RAW_DIRECTORY / (
    "econml-worker-profile-prototype-macos-arm64-v3-20261010"
)
SEED = 42

sys.path.insert(0, str(PROFILE_DIRECTORY))
import bridge  # noqa: E402 -- profile-local module is pinned beside this harness.
from protocol import (  # noqa: E402 -- profile-local module is pinned beside this harness.
    canonical_bytes,
    digest,
    validate_request,
    validate_response_shape,
)

_FRESH_READER = r"""
import hashlib, json, platform, sys
from pathlib import Path
profile_dir = Path(sys.argv[3]).resolve()
sys.path.insert(0, str(profile_dir))
from bridge import _data_payload, _locked_distributions
from protocol import METHOD_FQN, PROFILE_ID, canonical_bytes, digest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.hte import HTEResult
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from method_job_harness import _method_type

cas_root = Path(sys.argv[1])
result_ref = ArtifactRef.model_validate_json(sys.argv[2])
source_ref = ArtifactRef.model_validate_json(sys.argv[4])
spec = JobSpec.model_validate_json(sys.argv[5])
adapter_ref = ArtifactRef.model_validate_json(sys.argv[12])
evidence_ref = ArtifactRef.model_validate_json(sys.argv[13])
store = FileSystemCAS(cas_root)
for ref, kind, schema_name, schema_version in (
    (source_ref, "prototype.hte_observational_data", "prototype.HTEObservationalData", "1.0.0"),
    (adapter_ref, "scientist.unified_dag_adapter", "polisyos.scientist.UnifiedDagAdapter", "0.1.0"),
    (result_ref, "scientist.method_result.causal.hte", "polisyos.scientist.MethodResult", "0.1.0"),
    (
        evidence_ref,
        "scientist.method_evidence",
        "polisyos.scientist.MethodExecutionEvidence",
        "0.1.0",
    ),
):
    verification = store.verify(ref)
    manifest = store.get_manifest(ref)
    if (
        not verification.ok
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != schema_name
        or manifest.artifact_schema.version != schema_version
    ):
        raise RuntimeError(f"fresh reader artifact verification failed: {kind}")
adapter_payload = from_canonical_bytes(store.get_bytes(adapter_ref))
evidence_payload = from_canonical_bytes(store.get_bytes(evidence_ref))
payload = from_canonical_bytes(store.get_bytes(result_ref))
binding = payload["candidate_binding"]
raw_result = payload["worker_result"]
source_bytes = store.get_bytes(source_ref)
source_state = HTEObservationalData.model_validate(from_canonical_bytes(source_bytes))
expected_data = _data_payload(source_ref, source_state)
lock_bytes = (profile_dir / "uv.lock").read_bytes()
code_bytes = (profile_dir / "worker.py").read_bytes() + (profile_dir / "protocol.py").read_bytes()
if binding.get("method_fqn") != METHOD_FQN or binding.get("profile_id") != PROFILE_ID:
    raise RuntimeError("fresh_reader_selected_profile_mismatch")
assert spec.method_fqn == METHOD_FQN
assert spec.input_refs["hte_data"] == source_ref
assert spec.method_params == {}
actual_signature_sha256 = _method_type().signature.stable_digest()
assert actual_signature_sha256 == sys.argv[14]
assert binding["method_signature_sha256"] == actual_signature_sha256
assert adapter_payload["method_fqn"] == METHOD_FQN
assert adapter_payload["method_params"] == {}
assert adapter_payload["program_graph"]["nodes"] == [
    {"node_id": "method_node_1", "node_kind": "method", "method_fqn": METHOD_FQN}
]
assert evidence_payload["method_fqn"] == METHOD_FQN
assert evidence_payload["method_result_ref"] == result_ref.model_dump(mode="json")
declared_tier = DoubleMachineLearning.determinism_tier
if declared_tier is not DeterminismTier.STATISTICAL:
    raise RuntimeError("source method no longer declares statistical reproducibility")
if evidence_payload.get("reproducibility", {}).get("tier") != declared_tier.value:
    raise RuntimeError("persisted execution evidence lost the source determinism tier")
evidence_manifest = store.get_manifest(evidence_ref)
if (
    len(evidence_manifest.inputs) != 1
    or evidence_manifest.inputs[0].artifact_id != result_ref.artifact_id
    or evidence_manifest.inputs[0].role != "method_result"
    or evidence_manifest.inputs[0].manifest_profile_sha256 != result_ref.manifest_profile_sha256
):
    raise RuntimeError("fresh reader found unexpected MethodEvidence input lineage")
assert binding["authority"] == "candidate_computation_only"
assert binding["job_id"] == JobKey.from_spec(spec).value
assert binding["seed"] == spec.seed == 42
assert binding["source_ref"] == source_ref.model_dump(mode="json")
assert binding["source_content_sha256"] == hashlib.sha256(source_bytes).hexdigest()
assert binding["worker_lock_sha256"] == hashlib.sha256(lock_bytes).hexdigest()
assert binding["worker_code_sha256"] == hashlib.sha256(code_bytes).hexdigest()
assert binding["bridge_code_sha256"] == hashlib.sha256(
    (profile_dir / "bridge.py").read_bytes()
).hexdigest()
assert binding["worker_lock_sha256"] == sys.argv[6]
assert binding["worker_code_sha256"] == sys.argv[7]
assert binding["worker_environment"]["executable"] == str(Path(sys.argv[8]).resolve())
assert binding["bridge_code_sha256"] == sys.argv[9]
if (
    binding.get("harness_sha256") != sys.argv[10]
    or hashlib.sha256(Path(sys.argv[11]).resolve().read_bytes()).hexdigest() != sys.argv[10]
):
    raise RuntimeError("fresh_reader_harness_digest_mismatch")
assert binding["worker_environment"]["distributions"] == _locked_distributions(lock_bytes)
assert binding["worker_result_sha256"] == digest(raw_result)
assert binding["data_sha256"] == expected_data["data_sha256"]
assert binding["row_order_sha256"] == expected_data["row_order_sha256"]
assert raw_result["row_ids"] == expected_data["row_ids"]
assert len(raw_result["row_ids"]) == 400
lineage = store.get_manifest(result_ref).inputs
if (
    len(lineage) != 1
    or lineage[0].artifact_id != source_ref.artifact_id
    or lineage[0].role != "input:hte_data"
    or lineage[0].manifest_profile_sha256 != source_ref.manifest_profile_sha256
):
    raise RuntimeError("fresh reader found unexpected MethodResult input lineage")

report = CausalEffectReport.model_validate(payload["report"])
hte = HTEResult.model_validate(payload["hte_result"])
assert report.status.value == "success"
assert report.metadata["candidate_computation_only"] is True
assert report.metadata["worker_profile_id"] == PROFILE_ID
assert report.point_estimate == raw_result["ate"]
assert list(report.confidence_interval) == [raw_result["ate_ci_lower"], raw_result["ate_ci_upper"]]
assert list(hte.cate_values) == raw_result["cate_values"]
assert hte.ate == raw_result["ate"]
assert list(hte.feature_names) == raw_result["feature_names"]
assert hte.n_samples == 400

server = binding["server_environment"]
assert server["sys_platform"] == sys.platform == "darwin"
assert server["machine"] == platform.machine().lower() == "arm64"
assert server["macos_version"] == platform.mac_ver()[0] == "27.0.1"
assert server["python_version"] == platform.python_version()
assert server["implementation"] == platform.python_implementation()
assert sys.version_info[:2] == (3, 14)
print(
    json.dumps(
        {"fresh_reader": "passed", "result_id": str(result_ref.artifact_id), "rows": 400},
        sort_keys=True,
    )
)
"""


@dataclass(slots=True)
class _Invocation:
    store: FileSystemCAS
    profile: bridge.ServerSelectedProfile
    source_ref: ArtifactRef
    harness_sha256: str
    method_signature_sha256: str
    job_id: str
    seed: int
    candidate: bridge.CandidateHTEOutput | None = None
    captured_request: dict[str, Any] | None = None
    captured_response: dict[str, Any] | None = None


_INVOCATION: ContextVar[_Invocation | None] = ContextVar("mac_econml_invocation", default=None)


class _RecordingCAS(FileSystemCAS):
    """Record exact refs returned by the ordinary MethodJob CAS writes."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.refs_by_kind: dict[str, list[ArtifactRef]] = {}

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        ref = super().put_json(obj, opts, canon_spec)
        self.refs_by_kind.setdefault(opts.kind, []).append(ref)
        return ref


def _verify_artifact(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
) -> bytes:
    """Resolve the exact ref, verify CAS integrity, and require its declared schema."""
    verification = store.verify(ref)
    if not verification.ok:
        raise RuntimeError(f"artifact integrity verification failed: {kind}")
    manifest = store.get_manifest(ref)
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != schema_name
        or manifest.artifact_schema.version != schema_version
    ):
        raise RuntimeError(f"artifact manifest contract mismatch: {kind}")
    return store.get_bytes(ref)


def _method_type() -> type:
    @foundry_method(
        namespace="causal.hte",
        version="0.2.0",
        tags={"causal", "hte", "double-ml", "candidate-worker-prototype"},
    )
    class MacWorkerDoubleMachineLearning:
        """Local candidate wrapper used only to exercise actual MethodJob persistence."""

        signature = replace(
            DoubleMachineLearning.signature,
            name="double_ml_worker_prototype",
            namespace="",
            version="0.0.0",
            parameters=(),
        )
        metadata = DoubleMachineLearning.metadata
        materialize_input = staticmethod(DoubleMachineLearning.materialize_input)

        @staticmethod
        def pure_step(
            state: Mapping[str, object],
            params: Mapping[str, object],
        ) -> dict[str, Any]:
            invocation = _INVOCATION.get()
            if invocation is None:
                raise RuntimeError("server-selected candidate invocation is missing")
            if not isinstance(state, Mapping) or set(state) != {"hte_data"}:
                raise bridge.WorkerProtocolError("method_job_hte_input_shape_mismatch")
            if type(params.get("__seed__")) is not int or params["__seed__"] != invocation.seed:
                raise bridge.WorkerProtocolError("method_job_seed_binding_mismatch")
            canonical_payload = from_canonical_obj(state["hte_data"])
            typed_state = DoubleMachineLearning.materialize_input(
                {"hte_data": canonical_payload}, fallback_state=None
            )
            candidate = bridge.run_candidate(
                profile=invocation.profile,
                store=invocation.store,
                source_ref=invocation.source_ref,
                state=typed_state,
                job_id=invocation.job_id,
                seed=invocation.seed,
            )
            invocation.candidate = candidate
            binding = candidate.model_dump(
                mode="json",
                exclude={"report", "hte_result", "worker_result"},
            )
            binding["harness_sha256"] = invocation.harness_sha256
            binding["method_signature_sha256"] = invocation.method_signature_sha256
            return wrap_causal_output(
                candidate.report,
                extras={
                    "hte_result": candidate.hte_result,
                    "candidate_binding": binding,
                    "worker_result": candidate.worker_result,
                },
            )

    return MacWorkerDoubleMachineLearning


def _admit_source(
    store: FileSystemCAS, data: HTEObservationalData
) -> ArtifactRef:
    return store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="prototype.hte_observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="prototype.HTEObservationalData", version="1.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _fresh_reader(
    *,
    cas_root: Path,
    result_ref: ArtifactRef,
    source_ref: ArtifactRef,
    adapter_ref: ArtifactRef,
    evidence_ref: ArtifactRef,
    spec: JobSpec,
    harness_sha256: str,
    method_signature_sha256: str,
    profile_directory: Path = PROFILE_DIRECTORY,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PRODUCT_ROOT / "src")
    process = subprocess.run(  # noqa: S603 -- fixed app interpreter and inline read-only reader.
        [
            sys.executable,
            "-c",
            _FRESH_READER,
            str(cas_root),
            result_ref.model_dump_json(),
            str(profile_directory),
            source_ref.model_dump_json(),
            spec.model_dump_json(),
            LOCK_SHA256,
            CODE_SHA256,
            str(WORKER_PYTHON),
            BRIDGE_SHA256,
            harness_sha256,
            str(Path(__file__).resolve()),
            adapter_ref.model_dump_json(),
            evidence_ref.model_dump_json(),
            method_signature_sha256,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"fresh reader failed: {process.stdout}{process.stderr}")
    return json.loads(process.stdout)


def _assert_direct_reference(request: dict[str, Any], result: dict[str, Any]) -> None:
    """Compare the worker output with a separate direct LinearDML fit, same input/seed."""
    reference_code = r"""
import json, sys
import numpy as np
from econml.dml import LinearDML
request = json.load(sys.stdin)
data, config = request["data"], request["configuration"]
model = LinearDML(
    model_y=config["model_y"], model_t=config["model_t"], cv=config["cv_folds"],
    discrete_treatment=config["discrete_treatment"], random_state=request["seed"],
)
y = np.asarray(data["y"], dtype=float)
t = np.asarray(data["t"], dtype=int)
x = np.asarray(data["x"], dtype=float)
w = None if data["w"] is None else np.asarray(data["w"], dtype=float)
model.fit(y, t, X=x, W=w, inference="auto")
cate = np.asarray(model.effect(x, T0=0, T1=1), dtype=float).reshape(-1)
interval = model.ate_interval(
    X=x, T0=0, T1=1, alpha=1.0-config["confidence_level"]
)
print(
    json.dumps(
        {
            "ate": float(np.mean(cate)),
            "cate": cate.tolist(),
            "ate_interval": [float(interval[0]), float(interval[1])],
        },
        allow_nan=False,
        sort_keys=True,
    )
)
"""
    process = subprocess.run(  # noqa: S603 -- exact frozen profile interpreter and inline code.
        [str(WORKER_PYTHON), "-I", "-c", reference_code],
        input=canonical_bytes(request),
        capture_output=True,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith("POLISYOS_")
        },
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("direct LinearDML reference failed")
    reference = json.loads(process.stdout)
    if (
        reference["ate"] != result["ate"]
        or reference["cate"] != result["cate_values"]
        or reference["ate_interval"] != [result["ate_ci_lower"], result["ate_ci_upper"]]
    ):
        raise AssertionError("worker output differs from same-input direct LinearDML reference")


def _expect_refusal(
    name: str, operation: Callable[[], object], expected: str
) -> None:
    try:
        operation()
    except Exception as exc:
        if expected not in str(exc):
            raise AssertionError(f"{name} refused for the wrong reason: {exc}") from exc
    else:
        raise AssertionError(f"{name} was unexpectedly accepted")


def _rebind_request(request: dict[str, Any]) -> None:
    request["request_id"] = digest(
        {
            key: value
            for key, value in request.items()
            if key not in {"request_id", "request_sha256"}
        }
    )
    request["request_sha256"] = digest(
        {key: value for key, value in request.items() if key != "request_sha256"}
    )


def _negative_controls(invocation: _Invocation, profile: bridge.ServerSelectedProfile) -> list[str]:
    if invocation.captured_request is None or invocation.captured_response is None:
        raise RuntimeError("worker response capture missing from MethodJob execution")
    request = invocation.captured_request
    response = invocation.captured_response
    _, protocol_bytes, lock_bytes = bridge._profile_assets(profile)
    del protocol_bytes
    outcomes: list[str] = []

    bad_profile_request = copy.deepcopy(request)
    bad_profile_request["profile"] = "unselected-worker-profile"
    _rebind_request(bad_profile_request)
    _expect_refusal(
        "unselected request profile",
        lambda: validate_request(bad_profile_request),
        "unsupported profile",
    )
    outcomes.append("unselected_profile_refused")

    previous_profile_request = copy.deepcopy(request)
    previous_profile_request["profile"] = PREVIOUS_PROFILE_ID
    previous_profile_request["method_fqn"] = PREVIOUS_METHOD_FQN
    _rebind_request(previous_profile_request)
    _expect_refusal(
        "previous profile request",
        lambda: validate_request(previous_profile_request),
        "unsupported profile",
    )
    outcomes.append("previous_profile_refused")

    previous_code_profile = replace(
        profile,
        expected_code_sha256=PREVIOUS_CODE_SHA256,
    )
    _expect_refusal(
        "previous worker code digest",
        lambda: bridge._profile_assets(previous_code_profile),
        "selected_profile_asset_digest_mismatch",
    )
    outcomes.append("previous_code_digest_refused")

    bad_lock_response = copy.deepcopy(response)
    bad_lock_response["lock_sha256"] = "0" * 64
    _expect_refusal(
        "worker lock substitution",
        lambda: bridge._validate_response(bad_lock_response, request, lock_bytes, profile),
        "worker_response_binding_mismatch",
    )
    outcomes.append("lock_substitution_refused")

    wrong_bridge_profile = replace(profile, expected_bridge_sha256="0" * 64)
    _expect_refusal(
        "bridge code substitution",
        lambda: bridge._profile_assets(wrong_bridge_profile),
        "selected_profile_asset_digest_mismatch",
    )
    outcomes.append("bridge_substitution_refused")

    malformed_response = copy.deepcopy(response)
    del malformed_response["job_id"]
    _expect_refusal(
        "malformed worker response",
        lambda: validate_response_shape(malformed_response),
        "unexpected protocol object shape",
    )
    outcomes.append("malformed_response_refused")

    substituted = copy.deepcopy(response)
    substituted["outcome"]["result"]["cate_values"][0] += 0.25
    _expect_refusal(
        "substituted result with stale result digest",
        lambda: bridge._validate_response(substituted, request, lock_bytes, profile),
        "worker_result_digest_mismatch",
    )
    substituted["outcome"]["result_sha256"] = digest(substituted["outcome"]["result"])
    _expect_refusal(
        "substituted result with recomputed digest",
        lambda: bridge._validate_response(substituted, request, lock_bytes, profile),
        "worker_ate_not_mean_of_returned_cates",
    )
    outcomes.append("substituted_result_refused")

    reordered = copy.deepcopy(request)
    reordered_rows = reordered["data"]["row_ids"]
    reordered_rows[0], reordered_rows[1] = reordered_rows[1], reordered_rows[0]
    reordered["data"]["row_order_sha256"] = digest(reordered_rows)
    data_without_digest = {
        key: value for key, value in reordered["data"].items() if key != "data_sha256"
    }
    reordered["data"]["data_sha256"] = digest(data_without_digest)
    _rebind_request(reordered)
    _expect_refusal(
        "reordered source rows",
        lambda: validate_request(reordered),
        "source row order binding mismatch",
    )
    outcomes.append("row_permutation_refused")
    return outcomes


def run(cas_root: Path, expected_harness_sha256: str) -> dict[str, Any]:
    actual_harness_sha256 = hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()
    if (
        not bridge._digest_string(expected_harness_sha256)
        or actual_harness_sha256 != expected_harness_sha256
    ):
        raise RuntimeError("selected MethodJob harness digest mismatch")
    if not WORKER_PYTHON.is_file():
        raise FileNotFoundError(f"frozen worker interpreter missing: {WORKER_PYTHON}")
    profile = bridge.ServerSelectedProfile(
        profile_id=PROFILE_ID,
        # Preserve the venv entrypoint symlink when launching; resolving it
        # first runs the base interpreter and drops the selected venv packages.
        python_executable=WORKER_PYTHON.absolute(),
        worker_directory=PROFILE_DIRECTORY.resolve(),
        expected_lock_sha256=LOCK_SHA256,
        expected_code_sha256=CODE_SHA256,
        expected_bridge_sha256=BRIDGE_SHA256,
    )
    store = FileSystemCAS(cas_root)
    dgp_namespace = runpy.run_path(
        str(PRODUCT_ROOT / "tests/unit/foundry/methods/catalog/causal/test_hte_methods.py")
    )
    data = dgp_namespace["_synthetic_hte_data"](n=400, seed=SEED)
    source_ref = _admit_source(store, data)
    spec = JobSpec(
        job_kind="method",
        method_fqn=METHOD_FQN,
        seed=SEED,
        method_params={
            # Estimator configuration is fixed and content-bound in protocol.py.
            # Keep the MethodJob adapter's parameter object float-free under the
            # default Core canonical profile; the top-level JobSpec seed remains
            # the one runtime-controlled estimator input.
        },
        input_refs={"hte_data": source_ref},
    )
    method_class = _method_type()
    method_signature_sha256 = method_class.signature.stable_digest()
    recording_store = _RecordingCAS(cas_root)

    def store_factory(root: Path) -> FileSystemCAS:
        if Path(root).resolve() != cas_root.resolve():
            raise RuntimeError("MethodJob requested an unexpected CAS root")
        return recording_store

    invocation = _Invocation(
        store=store,
        profile=profile,
        source_ref=source_ref,
        harness_sha256=expected_harness_sha256,
        method_signature_sha256=method_signature_sha256,
        job_id=JobKey.from_spec(spec).value,
        seed=SEED,
    )
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    registry = MethodRegistry.get_instance()
    registry.register(method_class)

    original_validator = bridge._validate_response

    def capture_response(
        response: dict[str, Any],
        request: dict[str, Any],
        lock_bytes: bytes,
        selected_profile: bridge.ServerSelectedProfile,
    ) -> dict[str, Any]:
        invocation.captured_request = copy.deepcopy(request)
        invocation.captured_response = copy.deepcopy(response)
        return original_validator(response, request, lock_bytes, selected_profile)

    bridge._validate_response = capture_response
    token = _INVOCATION.set(invocation)
    try:
        result = run_job(
            spec,
            cas_root=cas_root,
            store_factory=store_factory,
        )
    finally:
        _INVOCATION.reset(token)
        bridge._validate_response = original_validator
    if result.issues or result.method_result_ref is None:
        raise RuntimeError(f"actual MethodJob failed: {result.issues}")
    if result.method_evidence_ref is None:
        raise RuntimeError("actual MethodJob did not persist execution evidence")
    adapter_refs = recording_store.refs_by_kind.get("scientist.unified_dag_adapter", [])
    method_result_refs = recording_store.refs_by_kind.get(
        "scientist.method_result.causal.hte", []
    )
    evidence_refs = recording_store.refs_by_kind.get("scientist.method_evidence", [])
    if len(adapter_refs) != 1:
        raise RuntimeError("actual MethodJob did not persist exactly one adapter artifact")
    adapter_ref = adapter_refs[0]
    if (
        len(method_result_refs) != 1
        or method_result_refs[0] != result.method_result_ref
        or len(evidence_refs) != 1
        or evidence_refs[0] != result.method_evidence_ref
    ):
        raise RuntimeError("JobResult refs differ from the exact CAS writer receipts")
    if f"legacy_method_adapter_ref:{adapter_ref.artifact_id}" not in result.warnings:
        raise RuntimeError("JobResult does not preserve the adapter writer receipt")
    adapter_payload = from_canonical_bytes(
        _verify_artifact(
            recording_store,
            adapter_ref,
            kind="scientist.unified_dag_adapter",
            schema_name="polisyos.scientist.UnifiedDagAdapter",
            schema_version="0.1.0",
        )
    )
    if (
        adapter_payload.get("method_fqn") != METHOD_FQN
        or adapter_payload.get("method_params") != {}
        or adapter_payload.get("program_graph", {}).get("nodes") != [
            {"node_id": "method_node_1", "node_kind": "method", "method_fqn": METHOD_FQN}
        ]
    ):
        raise RuntimeError("persisted adapter does not match the selected MethodJob")
    evidence_payload = from_canonical_bytes(
        _verify_artifact(
            recording_store,
            result.method_evidence_ref,
            kind="scientist.method_evidence",
            schema_name="polisyos.scientist.MethodExecutionEvidence",
            schema_version="0.1.0",
        )
    )
    if (
        evidence_payload.get("method_result_ref")
        != result.method_result_ref.model_dump(mode="json")
        or evidence_payload.get("method_fqn") != METHOD_FQN
    ):
        raise RuntimeError("persisted execution evidence is not bound to its MethodResult")
    payload = from_canonical_bytes(
        _verify_artifact(
            recording_store,
            result.method_result_ref,
            kind="scientist.method_result.causal.hte",
            schema_name="polisyos.scientist.MethodResult",
            schema_version="0.1.0",
        )
    )
    if invocation.candidate is None:
        raise RuntimeError("MethodJob completed without a captured candidate computation")
    if payload["candidate_binding"]["job_id"] != invocation.job_id:
        raise AssertionError("persisted candidate is not bound to the server-owned MethodJob")
    if payload["candidate_binding"].get("method_signature_sha256") != method_signature_sha256:
        raise AssertionError("persisted candidate is not bound to the selected MethodSignature")
    fresh_reader = _fresh_reader(
        cas_root=cas_root,
        result_ref=result.method_result_ref,
        source_ref=source_ref,
        adapter_ref=adapter_ref,
        evidence_ref=result.method_evidence_ref,
        spec=spec,
        harness_sha256=expected_harness_sha256,
        method_signature_sha256=method_signature_sha256,
    )
    fresh_reader_negative_controls: list[str] = []
    for label, reader_profile, reader_harness, expected_error in (
        (
            "previous profile",
            PREVIOUS_PROFILE_DIRECTORY,
            expected_harness_sha256,
            "fresh_reader_selected_profile_mismatch",
        ),
        (
            "previous harness digest",
            PROFILE_DIRECTORY,
            PREVIOUS_HARNESS_SHA256,
            "fresh_reader_harness_digest_mismatch",
        ),
    ):
        try:
            _fresh_reader(
                cas_root=cas_root,
                result_ref=result.method_result_ref,
                source_ref=source_ref,
                adapter_ref=adapter_ref,
                evidence_ref=result.method_evidence_ref,
                spec=spec,
                harness_sha256=reader_harness,
                method_signature_sha256=method_signature_sha256,
                profile_directory=reader_profile,
            )
        except RuntimeError as exc:
            if expected_error not in str(exc):
                raise RuntimeError(
                    f"unexpected fresh-reader negative-control result: {label}"
                ) from exc
        else:
            raise RuntimeError(f"fresh reader accepted {label}")
        fresh_reader_negative_controls.append(f"{label.replace(' ', '_')}_refused")
    if invocation.captured_request is None:
        raise RuntimeError("worker request capture missing from MethodJob execution")
    raw_worker_result = payload["worker_result"]
    _assert_direct_reference(invocation.captured_request, raw_worker_result)
    negative_controls = _negative_controls(invocation, profile)
    negative_controls.extend(fresh_reader_negative_controls)
    true_cate = 0.5 * data.covariates[:, 0] - 0.2 * data.covariates[:, 1]
    return {
        "status": "candidate_computation_only",
        "method_fqn": METHOD_FQN,
        "profile_id": PROFILE_ID,
        "lock_sha256": LOCK_SHA256,
        "code_sha256": CODE_SHA256,
        "bridge_sha256": BRIDGE_SHA256,
        "harness_sha256": expected_harness_sha256,
        "source_ref": source_ref.model_dump(mode="json"),
        "adapter_ref": adapter_ref.model_dump(mode="json"),
        "method_result_ref": result.method_result_ref.model_dump(mode="json"),
        "method_evidence_ref": result.method_evidence_ref.model_dump(mode="json"),
        "method_signature_sha256": method_signature_sha256,
        "job_id": invocation.job_id,
        "seed": SEED,
        "rows": data.n_obs,
        "direct_linear_dml_reference": "exact_same_data_config_seed_match",
        "fresh_reader": fresh_reader,
        "negative_controls": negative_controls,
        "diagnostic_only": {
            "known_sample_ate": float(true_cate.mean()),
            "cate_rmse_against_dgp": float(
                np.sqrt(np.mean((np.asarray(raw_worker_result["cate_values"]) - true_cate) ** 2))
            ),
        },
        "authority": "candidate_computation_only",
    }


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write(
            "usage: method_job_harness.py ABSOLUTE_CAS_ROOT EXPECTED_HARNESS_SHA256\n"
        )
        return 2
    cas_root = Path(sys.argv[1])
    if not cas_root.is_absolute():
        sys.stderr.write("CAS root must be absolute\n")
        return 2
    sys.stdout.write(json.dumps(run(cas_root, sys.argv[2]), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
