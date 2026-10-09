from __future__ import annotations

from dataclasses import replace
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.calibration.uncertainty_adapter import (
    load_persisted_posterior_summary,
    persist_posterior_summary_from_method_evidence,
)
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import canonical_draws_artifact
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryRef,
)
from polisyos.scientist.compute.job_spec import JobResult, JobSpec
from polisyos.scientist.compute.runner import run_job


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


class _PosteriorMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="posterior_fixture",
        namespace="tests.posterior",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="posterior producer fixture")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        del state, params
        return {}


def _native_method_result(*, corrupt_hash: bool = False) -> MethodResult:
    draws_ref, draws_payload, draws_hash, _layout = canonical_draws_artifact(
        {"beta": np.asarray([[1.0, 2.0, 3.0, 10.0]], dtype=np.float64)},
        method_name="posterior_fixture",
        sampler_kernel="hmc",
        stage="posterior",
    )
    posterior_result = {
        "method_name": "posterior_fixture",
        "sampler_family": "mcmc",
        "sampler_kernel": "hmc",
        "draws_ref": draws_ref,
        "posterior_means": {"beta": 2.5},
        "credible_intervals": {"beta": [1.0, 4.0]},
        "diagnostics": {"credible_mass": 0.8},
    }
    return MethodResult(
        output={"result": posterior_result},
        timing=MethodTiming(wall_time_ms=0.0),
        reproducibility=ReproducibilityInfo(
            backend=ComputeBackend.BAYESIAN,
            determinism_tier=DeterminismTier.STATISTICAL,
            seed=13,
        ),
        artifacts={
            "posterior_draws": {
                "artifact_ref": draws_ref,
                "artifact_hash": "sha256:" + ("0" * 64) if corrupt_hash else draws_hash,
                "payload": draws_payload,
            }
        },
    )


class _FixedDispatcher:
    def __init__(self, result: MethodResult) -> None:
        self._result = result

    def dispatch(self, **kwargs: Any) -> MethodResult:
        assert kwargs["method_class"] is _PosteriorMethod
        return self._result


class _ProfiledResultStore:
    """Return an explicitly selected result view from the real CAS writer."""

    def __init__(self, root) -> None:
        self._store = FileSystemCAS(root)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def put_json(self, obj: object, opts, canon_spec=None):
        ref = self._store.put_json(obj, opts, canon_spec)
        if opts.kind != "scientist.method_result.tests.posterior":
            return ref
        selected_opts = replace(
            opts,
            schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.2.0"),
        )
        return self._store.put_json(obj, selected_opts, canon_spec)


def _run_native_fixture(tmp_path, *, corrupt_hash: bool = False) -> JobResult:
    registry = MethodRegistry.get_instance()
    registry.register(_PosteriorMethod, override=True)
    return run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_PosteriorMethod.signature.fqn,
            method_params={"credible_mass": 0.95},
            seed=13,
        ),
        cas_root=tmp_path,
        store_factory=lambda root: _ProfiledResultStore(root),
        method_registry_provider=lambda: registry,
        method_dispatcher_provider=lambda: _FixedDispatcher(
            _native_method_result(corrupt_hash=corrupt_hash)
        ),
    )


def test_method_job_returns_fresh_readable_summary_refs_for_both_point_roles(tmp_path) -> None:
    result = _run_native_fixture(tmp_path)

    assert result.issues == []
    assert result.method_result_ref is not None
    assert result.method_result_ref.manifest_profile_sha256 is not None
    assert result.method_evidence_ref is not None
    assert set(result.posterior_summary_refs) == {
        PosteriorPointRole.POSTERIOR_MEAN,
        PosteriorPointRole.POSTERIOR_MEDIAN,
    }

    fresh_store = FileSystemCAS(tmp_path)
    evidence_manifest = fresh_store.get_manifest(result.method_evidence_ref)
    assert len(evidence_manifest.inputs) == 1
    assert evidence_manifest.inputs[0].role == "method_result"
    assert str(evidence_manifest.inputs[0].artifact_id) == str(result.method_result_ref.artifact_id)
    assert (
        evidence_manifest.inputs[0].manifest_profile_sha256
        == result.method_result_ref.manifest_profile_sha256
    )

    for role, summary_ref in result.posterior_summary_refs.items():
        assert isinstance(summary_ref, PosteriorSummaryRef)
        summary = load_persisted_posterior_summary(fresh_store, summary_ref)
        assert summary.point_role is role
        assert summary.credible_mass == 0.8
        assert summary.parameters["beta"].draws == (1.0, 2.0, 3.0, 10.0)
        assert summary.parameters["beta"].posterior_mean == 4.0
        assert summary.parameters["beta"].posterior_median == 2.0
        assert summary.parameters["beta"].selected_point == (
            4.0 if role is PosteriorPointRole.POSTERIOR_MEAN else 2.0
        )
        assert summary.gate_eligible is False
        assert summary.unit_binding_status == "not_established"
        assert summary.source_method_evidence_ref is not None
        assert (
            summary.source_method_evidence_ref.manifest_profile_sha256
            == result.method_evidence_ref.manifest_profile_sha256
        )


def test_method_job_refuses_corrupt_native_draw_digest(tmp_path) -> None:
    result = _run_native_fixture(tmp_path, corrupt_hash=True)

    assert result.posterior_summary_refs == {}
    assert result.issues
    assert "does not content-bind" in result.issues[0]["message"]


def test_method_job_refuses_declared_native_draws_without_persisted_payload(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_PosteriorMethod, override=True)
    dispatcher = _FixedDispatcher(
        MethodResult(
            output={
                "result": {
                    "method_name": "posterior_fixture",
                    "sampler_family": "mcmc",
                    "sampler_kernel": "hmc",
                    "draws_ref": "artifact://foundry/bayesian/posterior/declared-only",
                    "diagnostics": {"credible_mass": 0.8},
                }
            },
            timing=MethodTiming(wall_time_ms=0.0),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.BAYESIAN,
                determinism_tier=DeterminismTier.STATISTICAL,
            ),
        )
    )

    result = run_job(
        JobSpec(job_kind="method", method_fqn=_PosteriorMethod.signature.fqn),
        cas_root=tmp_path,
        method_registry_provider=lambda: registry,
        method_dispatcher_provider=lambda: dispatcher,
    )

    assert result.posterior_summary_refs == {}
    assert result.issues
    assert "without their evidence" in result.issues[0]["message"]


def test_summary_refuses_result_profile_not_bound_by_method_evidence(tmp_path) -> None:
    result = _run_native_fixture(tmp_path)
    assert result.method_evidence_ref is not None
    store = FileSystemCAS(tmp_path)
    evidence = from_canonical_bytes(store.get_bytes(result.method_evidence_ref))
    evidence["method_result_ref"]["manifest_profile_sha256"] = "sha256:" + ("0" * 64)
    evidence_manifest = store.get_manifest(result.method_evidence_ref)
    unbound_view_ref = store.put_json(
        evidence,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.MethodExecutionEvidence",
                version="0.1.0",
            ),
            inputs=evidence_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    with pytest.raises(ValueError, match="does not bind the producer-issued method-result view"):
        persist_posterior_summary_from_method_evidence(
            store,
            unbound_view_ref,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


def test_job_result_keeps_legacy_methods_without_summary_refs_compatible() -> None:
    legacy_result = JobResult(job_key={"value": "job:test"})

    assert legacy_result.posterior_summary_refs == {}
