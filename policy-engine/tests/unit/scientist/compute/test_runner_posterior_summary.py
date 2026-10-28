from __future__ import annotations

import base64
import math
from dataclasses import replace
from fractions import Fraction
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import (
    CanonSpec,
    content_hash,
    from_canonical_bytes,
    to_canonical_bytes,
)
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
from polisyos.foundry.uncertainty import MonteCarloPropagator
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryRef,
    PosteriorSummaryV11,
    persist_posterior_summary,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel
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


def _native_method_result(
    *,
    corrupt_hash: bool = False,
    samples: dict[str, np.ndarray] | None = None,
    credible_mass: float = 0.8,
    source_extension: dict[str, Any] | None = None,
) -> MethodResult:
    draws_ref, draws_payload, draws_hash, _layout = canonical_draws_artifact(
        {"beta": np.asarray([[1.0, 2.0, 3.0, 10.0]], dtype=np.float64)}
        if samples is None
        else samples,
        method_name="posterior_fixture",
        sampler_kernel="hmc",
        stage="posterior",
    )
    if source_extension is not None:
        # A deliberately foreign source-format negative still travels through
        # the real MethodResult/evidence bridge with correctly bound bytes.
        draws_payload = {**draws_payload, **source_extension}
        draws_hash = content_hash(
            to_canonical_bytes(draws_payload, CanonSpec(forbid_floats=False)), prefix=True
        )
        draws_ref = f"artifact://foundry/bayesian/posterior/{draws_hash}"
    posterior_result = {
        "method_name": "posterior_fixture",
        "sampler_family": "mcmc",
        "sampler_kernel": "hmc",
        "draws_ref": draws_ref,
        # New controlled tensor corpora do not declare legacy moments. The
        # tested owner must derive its functionals from actual draw bytes.
        "posterior_means": {"beta": 2.5} if samples is None else {},
        "credible_intervals": {"beta": [1.0, 4.0]} if samples is None else {},
        "diagnostics": {"credible_mass": credible_mass},
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

    def __init__(self, root, *, evidence_refs: list[ArtifactRef] | None = None) -> None:
        self._store = FileSystemCAS(root)
        self._evidence_refs = evidence_refs

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def put_json(
        self,
        obj: object,
        opts,
        canon_spec=None,
        *,
        return_selected_profile: bool = False,
    ):
        if opts.kind != "scientist.method_result.tests.posterior":
            ref = self._store.put_json(
                obj,
                opts,
                canon_spec,
                return_selected_profile=return_selected_profile,
            )
            if opts.kind == "scientist.method_evidence" and self._evidence_refs is not None:
                self._evidence_refs.append(ref)
            return ref
        self._store.put_json(obj, opts, canon_spec)
        selected_opts = replace(
            opts,
            schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.2.0"),
        )
        return self._store.put_json(
            obj,
            selected_opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _run_native_fixture(
    tmp_path,
    *,
    corrupt_hash: bool = False,
    samples: dict[str, np.ndarray] | None = None,
    credible_mass: float = 0.8,
    evidence_refs: list[ArtifactRef] | None = None,
    source_extension: dict[str, Any] | None = None,
) -> JobResult:
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
        store_factory=lambda root: _ProfiledResultStore(root, evidence_refs=evidence_refs),
        method_registry_provider=lambda: registry,
        method_dispatcher_provider=lambda: _FixedDispatcher(
            _native_method_result(
                corrupt_hash=corrupt_hash,
                samples=samples,
                credible_mass=credible_mass,
                source_extension=source_extension,
            )
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


def test_posterior_summary_bridge_preserves_selected_evidence_manifest_profile(tmp_path) -> None:
    result = _run_native_fixture(tmp_path)
    assert result.method_evidence_ref is not None
    store = FileSystemCAS(tmp_path)
    original_manifest = store.get_manifest(result.method_evidence_ref)
    evidence_bytes = store.get_bytes(result.method_evidence_ref)
    selected_evidence_ref = store.put_bytes(
        evidence_bytes,
        PutOptions(
            kind=original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=SchemaInfo(name="tests.SelectedMethodEvidence", version="1"),
            canon=original_manifest.canon,
            inputs=original_manifest.inputs,
            producer=original_manifest.producer,
            env=original_manifest.env,
            governance=original_manifest.governance,
            tenant_context=original_manifest.tenant_context,
            same_input_closure=original_manifest.same_input_closure,
            authority=original_manifest.authority,
            warnings=original_manifest.warnings,
        ),
    )
    assert selected_evidence_ref.manifest_profile_sha256 is not None

    summary_ref = persist_posterior_summary_from_method_evidence(
        store,
        selected_evidence_ref,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    summary = load_persisted_posterior_summary(store, summary_ref)
    summary_manifest = store.get_manifest(
        ArtifactRef.model_validate(summary_ref.model_dump(mode="python"))
    )

    assert summary.source_method_evidence_ref is not None
    assert (
        summary.source_method_evidence_ref.manifest_profile_sha256
        == selected_evidence_ref.manifest_profile_sha256
    )
    method_evidence_inputs = [
        item for item in summary_manifest.inputs if item.role == "method_evidence"
    ]
    assert len(method_evidence_inputs) == 1
    assert (
        method_evidence_inputs[0].manifest_profile_sha256
        == selected_evidence_ref.manifest_profile_sha256
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


class _EmissionCountingCAS(FileSystemCAS):
    """Observe the real Core writer without replacing admission or emission."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.put_byte_calls = 0

    def put_bytes(
        self, data: bytes, opts: PutOptions, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        self.put_byte_calls += 1
        return super().put_bytes(data, opts, return_selected_profile=return_selected_profile)


def _fresh_controlled_summary(
    cas_root: Path,
    samples: dict[str, np.ndarray],
    *,
    point_role: PosteriorPointRole = PosteriorPointRole.POSTERIOR_MEAN,
    credible_mass: float = 0.9,
) -> tuple[PosteriorSummaryV11, PosteriorSummaryRef, ArtifactRef]:
    """Use the real MethodJob/evidence writer and a fresh selected-view reader.

    The dispatcher supplies controlled finite software draws. This fixture
    does not attest a posterior fit, source validity, mixing or ESS.
    """
    result = _run_native_fixture(cas_root, samples=samples, credible_mass=credible_mass)
    assert result.issues == []
    assert result.method_result_ref is not None
    assert result.method_result_ref.manifest_profile_sha256 is not None
    assert result.method_evidence_ref is not None
    producer = FileSystemCAS(cas_root)
    evidence = from_canonical_bytes(producer.get_bytes(result.method_evidence_ref))
    manifest = producer.get_manifest(result.method_evidence_ref)
    assert len(manifest.inputs) == 1
    assert str(manifest.inputs[0].artifact_id) == str(result.method_result_ref.artifact_id)
    assert (
        manifest.inputs[0].manifest_profile_sha256
        == result.method_result_ref.manifest_profile_sha256
    )
    selected_evidence = producer.put_json(
        evidence,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=139),
        return_selected_profile=True,
    )
    assert selected_evidence.artifact_id == result.method_evidence_ref.artifact_id
    assert selected_evidence.manifest_profile_sha256 is not None
    assert (
        selected_evidence.manifest_profile_sha256
        != result.method_evidence_ref.manifest_profile_sha256
    )
    summary_ref = persist_posterior_summary_from_method_evidence(
        producer, selected_evidence, credible_mass=credible_mass, point_role=point_role
    )
    del result, producer, evidence, manifest
    fresh = FileSystemCAS(cas_root)
    summary = load_persisted_posterior_summary(fresh, summary_ref)
    assert summary.source_method_evidence_ref is not None
    assert (
        summary.source_method_evidence_ref.manifest_profile_sha256
        == selected_evidence.manifest_profile_sha256
    )
    selected_manifest = fresh.get_manifest(
        ArtifactRef.model_validate(summary_ref.model_dump(mode="python"))
    )
    assert len(selected_manifest.inputs) == 1
    assert selected_manifest.inputs[0].role == "method_evidence"
    assert str(selected_manifest.inputs[0].artifact_id) == str(selected_evidence.artifact_id)
    assert (
        selected_manifest.inputs[0].manifest_profile_sha256
        == selected_evidence.manifest_profile_sha256
    )
    return summary, summary_ref, selected_evidence


def _consume_selected_reference(
    cas_root: Path,
    ref: PosteriorSummaryRef,
    simulation_fn: Callable[..., Mapping[str, float]],
    *,
    parameter_names: tuple[str, ...] = ("x",),
) -> object:
    """Run the actual fresh reader then consumer without replacing guards."""
    selected = load_persisted_posterior_summary(FileSystemCAS(cas_root), ref)
    return MonteCarloPropagator().propagate_posterior_summary(
        selected,
        simulation_fn=simulation_fn,
        nominal_params={},
        parameter_names=parameter_names,
        output_metric_ids=("value",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )


@pytest.mark.parametrize("point_role", list(PosteriorPointRole))
def test_selected_method_law_preserves_asymmetric_point_and_every_draw(
    tmp_path: Path, point_role: PosteriorPointRole
) -> None:
    source_rows = (0.0,) * 99 + (100.0,)
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path,
        {"theta": np.asarray(source_rows).reshape(2, 50)},
        point_role=point_role,
    )
    theta = summary.parameters["theta"]
    assert theta.draws == source_rows
    assert theta.posterior_mean == 1.0
    assert theta.posterior_median == 0.0
    assert theta.equal_tail_interval == (0.0, 0.0)
    expected_point = 1.0 if point_role is PosteriorPointRole.POSTERIOR_MEAN else 0.0
    calls: list[float] = []

    def identity(*, theta: float) -> dict[str, float]:
        calls.append(theta)
        return {"value": theta}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=identity,
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("value",),
        point_role=point_role,
    )
    output = result.output_summaries["value"]
    assert tuple(calls) == (expected_point, *source_rows)
    assert result.joint_input_matrix.rows == tuple((value,) for value in source_rows)
    assert output.draw_values == source_rows
    assert output.selected_point_value == expected_point
    assert output.successful_draw_count == 100
    assert output.failure_records == ()
    assert result.simulation_attempt_count == 101
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


@pytest.mark.parametrize(
    ("source_rows", "expected_probability"),
    [
        ((-2.0,) * 10 + (-1.0,) * 20 + (0.0,) * 40 + (1.0,) * 20 + (2.0,) * 10, Fraction(2, 5)),
        ((-2.0,) * 15 + (0.0,) * 70 + (2.0,) * 15, Fraction(7, 10)),
    ],
    ids=["forty-zero-atoms", "seventy-zero-atoms"],
)
def test_selected_method_law_distinguishes_atoms_after_fresh_read(
    tmp_path: Path, source_rows: tuple[float, ...], expected_probability: Fraction
) -> None:
    # Independent fixture arithmetic, not the production summary/row selector.
    assert len(source_rows) == 100
    assert sum(Fraction(value) for value in source_rows) / 100 == 0
    assert sum(Fraction(value) ** 2 for value in source_rows) / 100 == Fraction(6, 5)
    assert Fraction(source_rows.count(0.0), 100) == expected_probability
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray(source_rows).reshape(2, 50)}
    )
    assert summary.parameters["x"].draws == source_rows
    assert summary.parameters["x"].posterior_mean == 0.0
    assert summary.parameters["x"].posterior_median == 0.0
    assert summary.parameters["x"].equal_tail_interval == (-2.0, 2.0)
    calls: list[float] = []

    def indicator(*, x: float) -> dict[str, float]:
        calls.append(x)
        return {"zero": float(x == 0.0)}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=indicator,
        nominal_params={},
        parameter_names=("x",),
        output_metric_ids=("zero",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    output = result.output_summaries["zero"]
    assert tuple(calls) == (0.0, *source_rows)
    assert output.draw_values == tuple(float(value == 0.0) for value in source_rows)
    assert output.selected_point_value == 1.0
    assert output.successful_draw_count == 100
    assert output.failure_records == ()
    assert output.posterior_mean is not None
    # This bound covers this fixture's actual divide-then-fsum, not a new law.
    expected = float(expected_probability)
    positive_count = source_rows.count(0.0)
    error_bound = positive_count * abs(Fraction.from_float(1.0 / 100) - Fraction(1, 100))
    error_bound += Fraction.from_float(math.ulp(expected))
    assert error_bound < Fraction.from_float(2 * math.ulp(expected))
    assert abs(output.posterior_mean - expected) <= 2 * math.ulp(expected)
    other = Fraction(7, 10) if expected_probability == Fraction(2, 5) else Fraction(2, 5)
    assert abs(output.posterior_mean - float(other)) >= 0.3 - 4 * math.ulp(0.7)
    assert result.simulation_attempt_count == 101
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


@pytest.mark.parametrize("sign", [1.0, -1.0], ids=["same-pairing", "opposite-pairing"])
@pytest.mark.parametrize(
    "permutation", [(0, 1, 2, 3), (2, 0, 3, 1)], ids=["source-order", "whole-row-permutation"]
)
def test_selected_method_law_preserves_joint_products_and_difference_variance(
    tmp_path: Path, sign: float, permutation: tuple[int, ...]
) -> None:
    original_x = (-1.0, 1.0, -1.0, 1.0)
    x_rows = tuple(original_x[index] for index in permutation)
    y_rows = tuple(sign * original_x[index] for index in permutation)
    expected_rows = tuple(zip(y_rows, x_rows, strict=True))
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path,
        {"x": np.asarray(x_rows).reshape(2, 2), "y": np.asarray(y_rows).reshape(2, 2)},
    )
    calls: list[tuple[float, float]] = []

    def joint(*, x: float, y: float) -> dict[str, float]:
        calls.append((y, x))
        return {"product": x * y, "difference": x - y, "squared_difference": (x - y) ** 2}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=joint,
        nominal_params={},
        parameter_names=("y", "x"),
        output_metric_ids=("product", "difference", "squared_difference"),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    assert result.joint_input_matrix.rows == expected_rows
    assert tuple(calls) == ((0.0, 0.0), *expected_rows)
    expected_values = {
        "product": tuple(x * y for x, y in zip(x_rows, y_rows, strict=True)),
        "difference": tuple(x - y for x, y in zip(x_rows, y_rows, strict=True)),
        "squared_difference": tuple((x - y) ** 2 for x, y in zip(x_rows, y_rows, strict=True)),
    }
    for name, values in expected_values.items():
        output = result.output_summaries[name]
        assert output.draw_values == values
        assert output.selected_point_value == 0.0
        assert output.successful_draw_count == 4
        assert output.failure_records == ()
        assert output.posterior_mean == float(sum(Fraction(value) for value in values) / 4)
    assert result.output_summaries["product"].posterior_mean == sign
    expected_variance = 0.0 if sign == 1.0 else 4.0
    assert result.output_summaries["difference"].posterior_mean == 0.0
    assert result.output_summaries["squared_difference"].posterior_mean == expected_variance
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


def test_selected_method_law_retains_honest_partial_output_slots(tmp_path: Path) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[0.0, 1.0], [2.0, 3.0]])}
    )
    calls: list[float] = []

    def incomplete(*, x: float) -> dict[str, float]:
        calls.append(x)
        return {} if x == 1.0 else {"value": x}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=incomplete,
        nominal_params={},
        parameter_names=("x",),
        output_metric_ids=("value",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    output = result.output_summaries["value"]
    assert tuple(calls) == (1.5, 0.0, 1.0, 2.0, 3.0)
    assert output.selected_point_value == 1.5
    assert output.selected_point_failure is None
    assert output.draw_values == (0.0, None, 2.0, 3.0)
    assert output.successful_draw_count == 3
    assert len(output.failure_records) == 1
    assert output.failure_records[0].draw_index == 1
    assert output.failure_records[0].outcome_code.value == "missing_output"
    assert output.distribution_sample_semantics == "successful_draws_only_conditional_on_execution"
    assert output.posterior_mean is not None
    expected = float(Fraction(5, 3))
    assert abs(output.posterior_mean - expected) <= 2 * math.ulp(expected)
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


@pytest.mark.parametrize(
    "mutation",
    ["omitted_coordinate", "extra_coordinate", "draws", "point", "interval", "identity", "units"],
)
def test_actual_owner_writer_recomputes_complete_source_before_emission(
    tmp_path: Path, mutation: str
) -> None:
    summary, _ref, evidence_ref = _fresh_controlled_summary(
        tmp_path,
        {
            "x": np.asarray([[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]]),
            "z": np.asarray([[10.0, 20.0], [30.0, 40.0]]),
        },
    )
    parameters = dict(summary.parameters)
    first = parameters["x[0]"]
    changes: dict[str, Any] = {}
    if mutation == "omitted_coordinate":
        del parameters["x[0]"]
    elif mutation == "extra_coordinate":
        parameters["invented"] = first.model_copy(update={"source_parameter": "invented"})
    elif mutation == "draws":
        parameters["x[0]"] = first.model_copy(update={"draws": (99.0, *first.draws[1:])})
    elif mutation == "point":
        parameters["x[0]"] = first.model_copy(update={"selected_point": 99.0})
    elif mutation == "interval":
        parameters["x[0]"] = first.model_copy(update={"equal_tail_interval": (0.0, 100.0)})
    elif mutation == "identity":
        parameters["x[0]"] = first.model_copy(update={"source_coordinate": (1,)})
    else:
        changes["unit_bindings"] = {"x[0]": "invented-unit"}
    changes.update({"parameters": parameters, "parameter_order": tuple(parameters)})
    forged = summary.model_copy(update=changes)
    observed = _EmissionCountingCAS(tmp_path)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        persist_posterior_summary(
            ensure_ir_artifact_store(observed),
            forged,
            source_method_evidence_ref=ArtifactRefModel.model_validate(
                evidence_ref.model_dump(mode="python")
            ),
        )
    assert observed.put_byte_calls == 0
    # A valid write must reach this same real Core path: the observer cannot
    # certify a permanently silent fake writer as a prepublication refusal.
    persist_posterior_summary(
        ensure_ir_artifact_store(observed),
        summary,
        source_method_evidence_ref=ArtifactRefModel.model_validate(
            evidence_ref.model_dump(mode="python")
        ),
    )
    assert observed.put_byte_calls == 1


def _historical_ambiguous_summary(
    cas_root: Path,
) -> tuple[PosteriorSummaryV11, ArtifactRef]:
    """Recreate an old lossy DTO from actual controlled producer/evidence bytes."""
    scalar = np.asarray([[10.0, 20.0], [30.0, 40.0]])
    samples = {"x": np.asarray([[[1.0], [2.0]], [[3.0], [4.0]]]), "x[0]": scalar}
    actual_evidence: list[ArtifactRef] = []
    job = _run_native_fixture(
        cas_root, samples=samples, credible_mass=0.9, evidence_refs=actual_evidence
    )
    assert job.posterior_summary_refs == {}
    assert job.issues
    assert "scalar coordinate projection is ambiguous" in job.issues[0]["message"]
    assert len(actual_evidence) == 1
    evidence_ref = actual_evidence[0]
    store = FileSystemCAS(cas_root)
    evidence = from_canonical_bytes(store.get_bytes(evidence_ref))
    assert evidence["method_result_ref"]["manifest_profile_sha256"] is not None
    source = evidence["artifacts"]["posterior_draws"]
    scalar_ref, scalar_payload, scalar_hash, _ = canonical_draws_artifact(
        {"x[0]": scalar}, method_name="posterior_fixture", sampler_kernel="hmc", stage="posterior"
    )
    surviving_scalar = summarize_posterior_draw_artifact(
        artifact_ref=scalar_ref,
        artifact_payload=scalar_payload,
        artifact_hash=scalar_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    old_lossy = surviving_scalar.model_copy(
        update={
            "source_draws_ref": source["artifact_ref"],
            "source_draws_hash": source["artifact_hash"],
            "source_draws_payload": source["payload"],
            "source_method_evidence_ref": ArtifactRefModel.model_validate(
                evidence_ref.model_dump(mode="python")
            ),
        }
    )
    assert old_lossy.parameter_order == ("x[0]",)
    assert old_lossy.parameters["x[0]"].source_parameter == "x[0]"
    assert set(source["payload"]["parameters"]) == {"x", "x[0]"}
    return old_lossy, evidence_ref


def test_actual_owner_refuses_old_ambiguous_dto_before_emission(tmp_path: Path) -> None:
    old_lossy, evidence_ref = _historical_ambiguous_summary(tmp_path)
    store = _EmissionCountingCAS(tmp_path)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        persist_posterior_summary(
            ensure_ir_artifact_store(store),
            old_lossy,
            source_method_evidence_ref=ArtifactRefModel.model_validate(
                evidence_ref.model_dump(mode="python")
            ),
        )
    assert store.put_byte_calls == 0


def test_fresh_selected_reader_refuses_historical_ambiguous_payload_before_evaluator(
    tmp_path: Path,
) -> None:
    old_lossy, evidence_ref = _historical_ambiguous_summary(tmp_path)
    store = FileSystemCAS(tmp_path)
    # Deliberate historical/corrupt-wire injection through generic Core I/O,
    # never positive owner admission or fabricated method evidence.
    historical_ref = store.put_json(
        old_lossy.model_dump(mode="python", round_trip=True),
        PutOptions(
            kind="ir.posterior_summary",
            media_type="application/json",
            schema=SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1"),
            inputs=[
                InputRef(
                    artifact_id=evidence_ref.artifact_id,
                    role="method_evidence",
                    manifest_profile_sha256=evidence_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected = PosteriorSummaryRef.model_validate(historical_ref.model_dump(mode="python"))
    calls: list[float] = []

    def must_not_run(**_values: float) -> dict[str, float]:
        calls.append(1.0)
        return {"value": 1.0}

    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        _consume_selected_reference(tmp_path, selected, must_not_run, parameter_names=("x[0]",))
    assert calls == []


def test_selected_summary_reader_reconciles_sibling_evidence_profile_before_evaluator(
    tmp_path: Path,
) -> None:
    summary, summary_ref, evidence_ref = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[0.0, 1.0], [2.0, 3.0]])}
    )
    store = FileSystemCAS(tmp_path)
    evidence_payload = from_canonical_bytes(store.get_bytes(evidence_ref))
    evidence_manifest = store.get_manifest(evidence_ref)
    sibling = store.put_json(
        evidence_payload,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=evidence_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=140),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == evidence_ref.artifact_id
    assert sibling.manifest_profile_sha256 != evidence_ref.manifest_profile_sha256
    alternate = store.put_json(
        summary.model_dump(mode="python", round_trip=True),
        PutOptions(
            kind="ir.posterior_summary",
            media_type="application/json",
            schema=SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1"),
            inputs=[
                InputRef(
                    artifact_id=sibling.artifact_id,
                    role="method_evidence",
                    manifest_profile_sha256=sibling.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    alternate_ref = PosteriorSummaryRef.model_validate(alternate.model_dump(mode="python"))
    assert alternate_ref.artifact_id == summary_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != summary_ref.manifest_profile_sha256
    assert load_persisted_posterior_summary(FileSystemCAS(tmp_path), summary_ref) == summary
    calls: list[float] = []

    def must_not_run(**_values: float) -> dict[str, float]:
        calls.append(1.0)
        return {"value": 1.0}

    with pytest.raises(ValueError, match="does not bind the selected method-evidence view"):
        _consume_selected_reference(tmp_path, alternate_ref, must_not_run)
    assert calls == []
    assert load_persisted_posterior_summary(FileSystemCAS(tmp_path), summary_ref) == summary


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_source",
        "missing_profile",
        "wrong_kind",
        "wrong_schema",
        "changed_draws",
        "wrong_kernel",
        "credible_mass",
    ],
)
def test_selected_source_refusals_precede_actual_law_evaluator(
    tmp_path: Path, mutation: str
) -> None:
    summary, summary_ref, evidence_ref = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[0.0, 1.0], [2.0, 3.0]])}
    )
    store = FileSystemCAS(tmp_path)
    payload = summary.model_dump(mode="python", round_trip=True)
    source_ref = evidence_ref
    schema = SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1")
    expected_type: type[ValueError] = ValueError
    if mutation == "missing_source":
        payload["source_method_evidence_ref"] = None
        expected_match = "Field required"
    elif mutation == "missing_profile":
        summary_ref = summary_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        expected_type = CanonViolation
        expected_match = "manifest_unavailable|read_refused"
    elif mutation == "wrong_kind":
        summary_ref = summary_ref.model_copy(update={"kind": "tests.wrong_posterior_kind"})
        expected_type = CanonViolation
        expected_match = "selected_manifest_mismatch|read_refused"
    elif mutation == "wrong_schema":
        schema = SchemaInfo(name="ir.PosteriorSummaryV11", version="9.9")
        expected_type = CanonViolation
        expected_match = "representation_unregistered"
    elif mutation == "credible_mass":
        payload["credible_mass"] = 0.8
        expected_match = "does not match its persisted method-evidence source"
    else:
        evidence_payload = from_canonical_bytes(store.get_bytes(evidence_ref))
        source = evidence_payload["artifacts"]["posterior_draws"]["payload"]
        if mutation == "changed_draws":
            # Actual source bytes change while the declared ref/hash stay put.
            source["parameters"]["x"]["data_base64"] = base64.b64encode(
                np.asarray([[99.0, 1.0], [2.0, 3.0]], dtype="<f8").tobytes(order="C")
            ).decode("ascii")
            expected_match = "does not content-bind"
        else:
            source["sampler_kernel"] = "nuts"
            expected_match = "method result and posterior draw source do not match"
        source_ref = store.put_json(
            evidence_payload,
            PutOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"
                ),
                inputs=store.get_manifest(evidence_ref).inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, max_depth=139),
            return_selected_profile=True,
        )
        payload["source_method_evidence_ref"] = source_ref.model_dump(mode="python")
    if mutation not in {"missing_profile", "wrong_kind"}:
        # Deliberate malformed historical wire used solely for a real fresh
        # reader negative, never as positive producer/owner evidence.
        raw_ref = store.put_json(
            payload,
            PutOptions(
                kind="ir.posterior_summary",
                media_type="application/json",
                schema=schema,
                inputs=[]
                if mutation == "missing_source"
                else [
                    InputRef(
                        artifact_id=source_ref.artifact_id,
                        role="method_evidence",
                        manifest_profile_sha256=source_ref.manifest_profile_sha256,
                    )
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        summary_ref = PosteriorSummaryRef.model_validate(raw_ref.model_dump(mode="python"))
    calls: list[float] = []

    def must_not_run(**_values: float) -> dict[str, float]:
        calls.append(1.0)
        return {"value": 1.0}

    with pytest.raises(expected_type, match=expected_match):
        _consume_selected_reference(tmp_path, summary_ref, must_not_run)
    assert calls == []


@pytest.mark.parametrize("mutation", ["wrong_role", "point", "draws", "coordinate", "hash"])
def test_actual_law_consumer_reconciles_forged_summary_before_evaluator(
    tmp_path: Path, mutation: str
) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[0.0, 1.0], [2.0, 3.0]])}
    )
    parameters = dict(summary.parameters)
    if mutation == "point":
        parameters["x"] = parameters["x"].model_copy(update={"selected_point": 99.0})
    elif mutation == "draws":
        parameters["x"] = parameters["x"].model_copy(update={"draws": (99.0, 1.0, 2.0, 3.0)})
    elif mutation == "coordinate":
        parameters["x"] = parameters["x"].model_copy(update={"source_coordinate": (0,)})
    updates: dict[str, Any] = {"parameters": parameters}
    if mutation == "hash":
        updates["source_draws_hash"] = "sha256:" + "0" * 64
    forged = summary.model_copy(update=updates)
    calls: list[float] = []

    def must_not_run(**_values: float) -> dict[str, float]:
        calls.append(1.0)
        return {"value": 1.0}

    with pytest.raises(ValueError, match="point_role|does not match|does not content-bind"):
        MonteCarloPropagator().propagate_posterior_summary(
            forged,
            simulation_fn=must_not_run,
            nominal_params={},
            parameter_names=("x",),
            output_metric_ids=("value",),
            point_role=PosteriorPointRole.POSTERIOR_MEDIAN
            if mutation == "wrong_role"
            else PosteriorPointRole.POSTERIOR_MEAN,
        )
    assert calls == []


def test_selected_method_law_reconstructs_source_signed_zero_after_canonical_read(
    tmp_path: Path,
) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[-0.0, 0.0], [-0.0, 0.0]], dtype="<f8")}
    )
    expected_signs = (-1.0, 1.0, -1.0, 1.0)
    assert (
        tuple(math.copysign(1.0, value) for value in summary.parameters["x"].draws)
        == expected_signs
    )
    calls: list[float] = []

    def sign_of_source(*, x: float) -> dict[str, float]:
        value = math.copysign(1.0, x)
        calls.append(value)
        return {"sign": value}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=sign_of_source,
        nominal_params={},
        parameter_names=("x",),
        output_metric_ids=("sign",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    output = result.output_summaries["sign"]
    assert tuple(calls) == (1.0, *expected_signs)
    assert output.draw_values == expected_signs
    assert output.selected_point_value == 1.0
    assert output.posterior_mean == 0.0
    assert output.successful_draw_count == 4
    assert output.failure_records == ()
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


def test_selected_method_source_order_survives_canonical_mapping_key_order(
    tmp_path: Path,
) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"vector": np.arange(48, dtype=np.float64).reshape(2, 2, 12)}
    )
    # JSON object key order is lexical, while source tensor order is numeric.
    # Every coordinate and the declared source order must survive, including
    # [2] versus [10]; no parameter-count or name-vocabulary exception applies.
    expected_order = tuple(f"vector[{index}]" for index in range(12))
    assert summary.parameter_order == expected_order
    assert tuple(summary.parameters) == expected_order
    expected_rows = ((10.0, 2.0), (22.0, 14.0), (34.0, 26.0), (46.0, 38.0))
    calls: list[tuple[float, float]] = []

    def selected_sum(**values: float) -> dict[str, float]:
        row = (values["vector[10]"], values["vector[2]"])
        calls.append(row)
        return {"sum": row[0] + row[1]}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=selected_sum,
        nominal_params={},
        parameter_names=("vector[10]", "vector[2]"),
        output_metric_ids=("sum",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    assert result.joint_input_matrix.rows == expected_rows
    assert tuple(calls) == ((28.0, 20.0), *expected_rows)
    output = result.output_summaries["sum"]
    assert output.draw_values == (12.0, 36.0, 60.0, 84.0)
    assert output.selected_point_value == 48.0
    assert output.posterior_mean == 48.0
    assert output.successful_draw_count == 4
    assert output.failure_records == ()
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


@pytest.mark.parametrize("mutation", ["signed_zero_rows", "point_type_alias", "row_type_alias"])
def test_actual_consumer_uses_source_snapshot_after_equal_valued_nested_mutation(
    tmp_path: Path, mutation: str
) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[-0.0, 0.0], [-0.0, 0.0]], dtype="<f8")}
    )
    values = summary.parameters["x"]
    if mutation == "signed_zero_rows":
        changed = values.model_copy(update={"draws": (0.0, 0.0, 0.0, 0.0)})
    elif mutation == "point_type_alias":
        changed = values.model_copy(update={"selected_point": False})
    else:
        changed = values.model_copy(update={"draws": (False, 0.0, -0.0, 0.0)})
    # The actual fresh object, not a reconstructed DTO, is changed after read.
    summary.parameters["x"] = changed
    calls: list[tuple[type, str]] = []

    def distinguish_actual_values(*, x: float) -> dict[str, float]:
        calls.append((type(x), float(x).hex()))
        return {"sign": math.copysign(1.0, x), "typed": float(type(x) is float)}

    result = MonteCarloPropagator().propagate_posterior_summary(
        summary,
        simulation_fn=distinguish_actual_values,
        nominal_params={},
        parameter_names=("x",),
        output_metric_ids=("sign", "typed"),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    expected_inputs = (0.0, -0.0, 0.0, -0.0, 0.0)
    assert tuple(calls) == tuple((float, value.hex()) for value in expected_inputs)
    assert result.output_summaries["sign"].draw_values == (-1.0, 1.0, -1.0, 1.0)
    assert result.output_summaries["sign"].selected_point_value == 1.0
    assert result.output_summaries["typed"].draw_values == (1.0, 1.0, 1.0, 1.0)
    assert result.output_summaries["typed"].selected_point_value == 1.0
    for output in result.output_summaries.values():
        assert output.successful_draw_count == 4
        assert output.failure_records == ()
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 0
    assert result.gate_eligible is False


@pytest.mark.parametrize("mutation", ["signed_zero", "type_alias", "unequal_value"])
def test_public_joint_rows_reconcile_mutable_fresh_mapping(tmp_path: Path, mutation: str) -> None:
    summary, _ref, _evidence = _fresh_controlled_summary(
        tmp_path, {"x": np.asarray([[-0.0, 0.0], [-0.0, 0.0]], dtype="<f8")}
    )
    original = summary.parameters["x"]
    if mutation == "signed_zero":
        draws = (0.0, 0.0, 0.0, 0.0)
    elif mutation == "type_alias":
        draws = (False, 0.0, -0.0, 0.0)
    else:
        draws = (99.0, 0.0, -0.0, 0.0)
    summary.parameters["x"] = original.model_copy(update={"draws": draws})
    if mutation == "unequal_value":
        with pytest.raises(ValueError, match="does not match its source draw payload"):
            summary.joint_row_values(("x",))
    else:
        rows = summary.joint_row_values(("x",))
        expected = (-0.0, 0.0, -0.0, 0.0)
        assert len(rows) == 4
        assert all(type(row[0]) is float for row in rows)
        assert tuple(row[0].hex() for row in rows) == tuple(value.hex() for value in expected)


@pytest.mark.parametrize("bypass", ["model_construct", "post_validation_nested_map"])
def test_real_owner_revalidates_explicit_construction_and_nested_mutation(
    tmp_path: Path, bypass: str
) -> None:
    summary, _ref, evidence_ref = _fresh_controlled_summary(
        tmp_path,
        {"x": np.asarray([[1.0, 2.0], [3.0, 4.0]]), "y": np.asarray([[5.0, 6.0], [7.0, 8.0]])},
    )
    original = summary.parameters["x"]
    if bypass == "model_construct":
        all_fields = {name: getattr(summary, name) for name in type(summary).model_fields}
        all_fields["parameters"] = {"y": summary.parameters["y"]}
        all_fields["parameter_order"] = ("y",)
        forged = PosteriorSummaryV11.model_construct(**all_fields)
    else:
        # No outer model_copy: mutate the actual already validated mapping.
        summary.parameters["x"] = original.model_copy(update={"draws": (99.0, 2.0, 3.0, 4.0)})
        forged = summary
    observed = _EmissionCountingCAS(tmp_path)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        persist_posterior_summary(
            ensure_ir_artifact_store(observed),
            forged,
            source_method_evidence_ref=ArtifactRefModel.model_validate(
                evidence_ref.model_dump(mode="python")
            ),
        )
    assert observed.put_byte_calls == 0
    summary.parameters["x"] = original
    persist_posterior_summary(
        ensure_ir_artifact_store(observed),
        summary,
        source_method_evidence_ref=ArtifactRefModel.model_validate(
            evidence_ref.model_dump(mode="python")
        ),
    )
    assert observed.put_byte_calls == 1


@pytest.mark.parametrize(
    "extension",
    [{"sample_weight": [0.7, 0.1, 0.1, 0.1]}, {"metadata": {"note": "otherwise benign extra"}}],
    ids=["purported-weight-extension", "unknown-benign-extension"],
)
def test_real_method_source_format_refuses_unknown_extensions_without_losing_inspection(
    tmp_path: Path, extension: dict[str, Any]
) -> None:
    actual_evidence: list[ArtifactRef] = []
    result = _run_native_fixture(
        tmp_path,
        samples={"x": np.asarray([[0.0, 1.0], [2.0, 3.0]])},
        credible_mass=0.9,
        source_extension=extension,
        evidence_refs=actual_evidence,
    )
    assert result.posterior_summary_refs == {}
    assert result.issues
    assert "posterior draw source format is undeclared or malformed" in result.issues[0]["message"]
    assert len(actual_evidence) == 1
    store = FileSystemCAS(tmp_path)
    # The whole real producer evidence is retained and generic-readable; only
    # this typed unweighted law profile refuses an unadmitted source format.
    evidence = from_canonical_bytes(store.get_bytes(actual_evidence[0]))
    source = evidence["artifacts"]["posterior_draws"]
    for name, value in extension.items():
        assert source["payload"][name] == value
    assert source["artifact_hash"] == content_hash(
        to_canonical_bytes(source["payload"], CanonSpec(forbid_floats=False)), prefix=True
    )
    assert source["artifact_ref"].endswith(source["artifact_hash"])
    assert evidence["method_result_ref"]["manifest_profile_sha256"] is not None
