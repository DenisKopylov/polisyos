from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.backends.jax_runner import JaxRunner
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.compiler import MethodCompiler
from polisyos.foundry.methods.equivalence import (
    CalibrationBattery,
    CalibrationCase,
    ComparatorKind,
    CrossBackendEquivalenceCertificate,
    EquivalencePolicy,
    EquivalenceVerdict,
    FieldRequirement,
    FieldToleranceSpec,
    attach_equivalence_ref,
    calibrate_backend_pair_detailed,
    load_equivalence_certificate,
    persist_attested_equivalence_certificate,
    persist_equivalence_certificate,
    runtime_envelope_from_results,
    verify_backend_equivalence,
    verify_persisted_equivalence_certificate,
)


def _result(
    *,
    backend: ComputeBackend,
    output,
    runtime_fp: str,
    library_versions: dict[str, str],
) -> MethodResult:
    return MethodResult(
        output=output,
        timing=MethodTiming(wall_time_ms=1.0),
        reproducibility=ReproducibilityInfo(
            backend=backend,
            determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
            seed=7,
            library_versions=library_versions,
            fingerprint=f"repro-{runtime_fp}",
            observed_tolerance_budget={
                "budget_source": "seed_prior",
                "mode": "allclose",
                "scope": "cross_architecture",
                "route_key": {
                    "backend_route": backend.value,
                    "arch_family": "x86_64",
                    "device_family": "cpu",
                    "dtype_mode": "float64_capable",
                    "blas_vendor": "openblas",
                    "thread_policy": "default",
                },
                "expected_budget": {
                    "same_fingerprint_abs_tol": 0.0,
                    "same_fingerprint_rel_tol": 0.0,
                    "same_architecture_abs_tol": 1.0e-12,
                    "same_architecture_rel_tol": 1.0e-12,
                    "cross_architecture_abs_tol": 1.0e-6,
                    "cross_architecture_rel_tol": 1.0e-6,
                    "semantic_mode": "library_exact_cpu",
                },
                "validation_status": "compatible",
                "failure_reasons": [],
                "solver_residual_budget": {},
            },
        ),
        artifacts={
            "backend_runtime_fingerprint": {
                "backend": backend.value,
                "execution_device": "cpu:test",
                "fingerprint": runtime_fp,
            }
        },
    )


def test_verify_backend_equivalence_passes_strict_for_matching_results() -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={"metric": 1.0, "status": "ok"},
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={"metric": 1.0 + 1.0e-8, "status": "ok"},
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:strict",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.metric",
                comparator=ComparatorKind.ABS_REL,
                strict_atol=1.0e-6,
                strict_rtol=1.0e-6,
            ),
            FieldToleranceSpec(
                path="output.status",
                comparator=ComparatorKind.EXACT,
            ),
        ),
    )

    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
    )

    assert report.applicable is True
    assert report.verdict is EquivalenceVerdict.PASS_STRICT
    assert report.failed_required_paths == ()
    assert report.runtime_budget_validation["budget_source"] == "runtime_measured"
    assert report.runtime_budget_validation["validation_status"] == "compatible"


def test_verify_backend_equivalence_returns_relaxed_verdict_when_needed() -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={"metric": np.array([1.0, 2.0])},
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={"metric": np.array([1.0005, 2.0005])},
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:relaxed",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.metric",
                comparator=ComparatorKind.ABS_REL,
                strict_atol=1.0e-6,
                strict_rtol=1.0e-6,
                relaxed_atol=1.0e-2,
                relaxed_rtol=1.0e-2,
            ),
        ),
    )

    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
    )

    assert report.verdict is EquivalenceVerdict.PASS_RELAXED
    assert report.field_reports[0].strict_ok is False
    assert report.field_reports[0].relaxed_ok is True


def test_verify_backend_equivalence_returns_unknown_for_inapplicable_certificate() -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={"metric": 1.0},
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={"metric": 1.0},
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:expired",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.metric",
                comparator=ComparatorKind.ABS_REL,
                strict_atol=1.0e-6,
                strict_rtol=1.0e-6,
            ),
        ),
        expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )

    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
    )

    assert report.applicable is False
    assert report.verdict is EquivalenceVerdict.UNKNOWN
    assert "certificate expired" in report.notes


def test_persist_load_and_attach_equivalence_certificate(tmp_path: Path) -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={"metric": 1.0, "status": "ok"},
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={"metric": 1.0, "status": "ok"},
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:persist",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.metric",
                comparator=ComparatorKind.ABS_REL,
                strict_atol=1.0e-6,
                strict_rtol=1.0e-6,
            ),
            FieldToleranceSpec(
                path="output.status",
                comparator=ComparatorKind.EXACT,
                requirement=FieldRequirement.ADVISORY,
            ),
        ),
    )
    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
    )

    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_equivalence_certificate(store=store, certificate=certificate)
    loaded = load_equivalence_certificate(store=store, ref=str(ref.artifact_id))
    attached = attach_equivalence_ref(
        source,
        str(ref.artifact_id),
        report.verdict,
        report=report,
    )

    assert loaded.certificate_id == certificate.certificate_id
    assert attached.cross_backend_equivalence_ref == str(ref.artifact_id)
    assert attached.artifacts["cross_backend_equivalence"]["verdict"] == "pass_strict"
    assert (
        attached.artifacts["cross_backend_equivalence"]["certificate_id"] == report.certificate_id
    )


def test_calibrate_backend_pair_builds_certificate_from_real_runner_pair(isolated_registry) -> None:
    pytest.importorskip("jax")
    pytest.importorskip("jaxlib")

    class _PolyglotMeanMethod:
        signature: ClassVar[MethodSignature] = MethodSignature(
            name="polyglot_mean",
            namespace="tests.equivalence",
            version="1.0.0",
            input_slots=frozenset(),
            output_slots=frozenset(
                {
                    SlotSpec("mean", SlotType.SCALAR, Unit("mean", "value")),
                    SlotSpec("shifted", SlotType.VECTOR, Unit("value", "amount")),
                }
            ),
            parameters=(ParameterSpec(name="delta", default=0.0),),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_N,
            backend=ComputeBackend.JAX,
        )
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description="backend-agnostic calibration fixture",
        )

        @staticmethod
        def pure_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            values = state["values"]
            shifted = values + params["delta"]
            return {
                "mean": shifted.sum() / shifted.size,
                "shifted": shifted,
            }

    isolated_registry.register(_PolyglotMeanMethod, override=True)
    fqn = _PolyglotMeanMethod.signature.fqn
    battery = CalibrationBattery(
        cases=(
            CalibrationCase(
                label="small",
                state={"values": np.linspace(1.0, 5.0, 5, dtype=np.float64)},
                params={"delta": 0.25},
                seed=7,
            ),
            CalibrationCase(
                label="medium",
                state={"values": np.linspace(10.0, 30.0, 9, dtype=np.float64)},
                params={"delta": -0.5},
                seed=9,
            ),
        ),
        battery_id="xbeq.synthetic.v1",
    )

    calibration = calibrate_backend_pair_detailed(
        method_fqn=fqn,
        source_backend=ComputeBackend.NUMPY,
        target_backend=ComputeBackend.JAX,
        battery=battery,
        policy=EquivalencePolicy(),
        registry=isolated_registry,
    )

    certificate = calibration.certificate
    assert certificate.method_fqn == fqn
    assert certificate.global_verdict in {
        EquivalenceVerdict.PASS_STRICT,
        EquivalenceVerdict.PASS_RELAXED,
    }
    assert certificate.test_vectors["n_cases"] == 2
    assert any(spec.path == "output.mean" for spec in certificate.field_specs)
    assert any(spec.path == "output.shifted" for spec in certificate.field_specs)
    assert certificate.provenance["ci_measured_tolerance_budget"]["budget_source"] == "ci_measured"
    assert (
        certificate.provenance["ci_measured_tolerance_budget"]["canary_suite_id"]
        == "xbeq.synthetic.v1"
    )

    numpy_result = NumpyRunner().execute(
        method_class=_PolyglotMeanMethod,
        signature=_PolyglotMeanMethod.signature,
        state={"values": np.linspace(3.0, 9.0, 7, dtype=np.float64)},
        params={"delta": 0.1},
        seed=5,
    )
    jax_result = JaxRunner(MethodCompiler(registry=isolated_registry)).execute(
        method_class=_PolyglotMeanMethod,
        signature=_PolyglotMeanMethod.signature,
        state={"values": np.linspace(3.0, 9.0, 7, dtype=np.float64)},
        params={"delta": 0.1},
        seed=5,
    )
    report = verify_backend_equivalence(
        result=numpy_result,
        counterpart=jax_result,
        certificate=certificate,
        method_fqn=fqn,
    )

    assert report.applicable is True
    assert report.verdict in {
        EquivalenceVerdict.PASS_STRICT,
        EquivalenceVerdict.PASS_RELAXED,
    }
    assert report.runtime_budget_validation["budget_source"] == "runtime_measured"


def test_verify_backend_equivalence_supports_extended_comparators() -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={
            "scalar": np.float64(1.0),
            "vector": np.array([1.0, 2.0, 3.0], dtype=np.float64),
            "draws": np.array([0.1, 0.2, 0.4, 0.8], dtype=np.float64),
        },
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={
            "scalar": np.nextafter(np.float64(1.0), np.float64(2.0)),
            "vector": np.array([1.0, 2.0, 3.000001], dtype=np.float64),
            "draws": np.array([0.1, 0.21, 0.39, 0.79], dtype=np.float64),
        },
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:extended-comparators",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.scalar",
                comparator=ComparatorKind.ULP,
                ulp_tol=8,
            ),
            FieldToleranceSpec(
                path="output.vector",
                comparator=ComparatorKind.NORM,
                norm_order="fro",
                strict_norm_tol=1e-5,
                relaxed_norm_tol=1e-4,
                scale_floor=1e-12,
            ),
            FieldToleranceSpec(
                path="output.draws",
                comparator=ComparatorKind.DISTRIBUTIONAL,
                distribution_metric="ks",
                strict_distribution_tol=0.3,
                relaxed_distribution_tol=0.4,
            ),
        ),
    )

    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
    )

    assert report.applicable is True
    assert report.verdict is EquivalenceVerdict.PASS_STRICT
    assert report.field_reports[0].max_ulp_error is not None
    assert report.field_reports[1].norm_error is not None
    assert report.field_reports[2].distribution_error is not None


def test_verify_backend_equivalence_checks_route_key_and_signed_artifact(tmp_path: Path) -> None:
    source = _result(
        backend=ComputeBackend.NUMPY,
        output={"metric": 1.0},
        runtime_fp="src-fp",
        library_versions={"numpy": "2.1.0"},
    )
    target = _result(
        backend=ComputeBackend.JAX,
        output={"metric": 1.0},
        runtime_fp="tgt-fp",
        library_versions={"jax": "0.4.35"},
    )
    certificate = CrossBackendEquivalenceCertificate(
        certificate_id="xbeq:test:signed",
        method_fqn="demo.metric@1.0.0",
        runtime_envelope=runtime_envelope_from_results(
            source_result=source,
            target_result=target,
        ),
        field_specs=(
            FieldToleranceSpec(
                path="output.metric",
                comparator=ComparatorKind.ULP,
                ulp_tol=0,
            ),
        ),
    )

    pair = KeyPair.generate()
    signer = Ed25519Signer(pair.private_key)
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(
        pair.public_key,
        identity="ci/policyos/backend-equivalence",
    )
    store = FileSystemCAS(tmp_path / "cas")
    persisted = persist_attested_equivalence_certificate(
        store=store,
        certificate=certificate,
        signer=signer,
        signer_identity="ci/policyos/backend-equivalence",
    )

    signature_report = verify_persisted_equivalence_certificate(
        store=store,
        ref=persisted.certificate_ref,
        verifier=verifier,
        strict_identity=True,
    )
    assert signature_report.status is SignatureVerificationStatus.VALID

    report = verify_backend_equivalence(
        result=source,
        counterpart=target,
        certificate=certificate,
        method_fqn="demo.metric@1.0.0",
        certificate_ref=persisted.certificate_ref,
        artifact_store=store,
        signature_verifier=verifier,
        strict_identity=True,
        require_signed_certificate=True,
    )

    assert report.applicable is True
    assert report.verdict is EquivalenceVerdict.PASS_STRICT
    assert persisted.attestation_ref is not None
