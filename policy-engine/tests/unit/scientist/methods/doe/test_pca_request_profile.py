"""Independent large-profile PCA and whole-request DOE replay oracles.

DOE-02/03 qualification uses two distinct fixtures: an analytic DCT matrix and
a deterministic parameter-only Morris model. The NumPy full SVD below qualifies
the Morris fixture before the PCA under test; it is not a tested PCA result.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Literal

import numpy as np
import pytest

from polisyos.scientist.methods.doe.analysis import _array_digest
from polisyos.scientist.methods.doe.designs import (
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
    _derive_backend_seed,
)
from polisyos.scientist.methods.doe.multi_output import (
    MultiOutputAnalyzer,
    MultiOutputSensitivityResult,
)
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.doe.uncertainty import SensitivityUncertaintyConfig

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS


_FIXED_SEEDS = (13, 17, 19, 23)
_PCA_STREAM = "preprocess:pca:doe-pca-v1"
_REPLAY_RTOL = 1e-10
_REPLAY_ATOL = 1e-12
type _RngSnapshot = tuple[str, bytes, int, int, float]
type _SvdSolver = Literal["auto", "full", "randomized"]


@dataclass(frozen=True)
class _MorrisCase:
    """Frozen source inputs selected without observing a tested PCA result."""

    plan: SensitivityPlan
    samples: np.ndarray
    outputs: np.ndarray
    input_path: Path
    samples_sha256: str
    outputs_sha256: str


@dataclass(frozen=True)
class _MorrisPreflight:
    """Retain the whole fixed-seed denominator and the first two qualified cases."""

    pair: tuple[_MorrisCase, _MorrisCase]
    replica: _MorrisCase
    report_path: Path


@dataclass(frozen=True)
class _Execution:
    """Observe actual sampler, deterministic model, and PCA/Morris outputs."""

    samples: np.ndarray
    outputs: np.ndarray
    result: MultiOutputSensitivityResult


def _require_native_versions() -> None:
    """Keep another backend version explicitly outside this qualification."""
    for distribution, expected in (("SALib", "1.5.2"), ("scikit-learn", "1.8.0")):
        try:
            actual = version(distribution)
        except PackageNotFoundError:
            pytest.skip(f"NOT_RUN: required {distribution}@{expected} is unavailable")
        if actual != expected:
            pytest.skip(
                f"NOT_RUN: {distribution}@{actual} is outside the pinned {expected} profile"
            )
    pytest.importorskip("SALib", reason="NOT_RUN: native SALib is unavailable")
    pytest.importorskip("sklearn.decomposition", reason="NOT_RUN: native PCA is unavailable")


def _rng_snapshot() -> _RngSnapshot:
    state = np.random.get_state()
    return str(state[0]), state[1].tobytes(), int(state[2]), int(state[3]), float(state[4])


def _without_global_rng[T](operation: Callable[[], T]) -> T:
    before = _rng_snapshot()
    answer = operation()
    assert _rng_snapshot() == before, "the whole invocation changed external NumPy RNG state"
    return answer


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fixture_matrix_digest(values: np.ndarray) -> str:
    """Hash actual fixture bytes independently of the product identity helper."""
    return hashlib.sha256(
        _canonical_bytes({"dtype": "float64", "shape": list(values.shape)})
        + np.asarray(values, dtype="<f8", order="C").tobytes(order="C")
    ).hexdigest()


def _morris_plan(seed: int, *, replica_id: int = 0) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name=name, lower_bound=0.0, upper_bound=1.0, num_levels=8)
            for name in ("x1", "x2")
        ],
        n_trajectories=200,
        seed=seed,
        replica_id=replica_id,
        input_law="independent",
        uncertainty=SensitivityUncertaintyConfig(
            enabled=True,
            method="percentile",
            n_resamples=20,
            random_seed=29,
            interval_types=["marginal"],
            simulated_rank_draws=100,
        ),
    )


def _legendre_columns(coordinate: np.ndarray) -> np.ndarray:
    """Evaluate P0..P9 by the independent recurrence fixed in DOE-03."""
    polynomials = np.empty((coordinate.size, 10), dtype=np.float64)
    polynomials[:, 0] = 1.0
    polynomials[:, 1] = coordinate
    for degree in range(1, 9):
        polynomials[:, degree + 1] = (
            (2 * degree + 1) * coordinate * polynomials[:, degree]
            - degree * polynomials[:, degree - 1]
        ) / (degree + 1)
    return polynomials


def _legendre_outputs(samples: np.ndarray) -> np.ndarray:
    """Use only the actual parameter vector, with no row or replica randomness."""
    left = _legendre_columns(2.0 * samples[:, 0] - 1.0)
    right = _legendre_columns(2.0 * samples[:, 1] - 1.0)
    return np.column_stack(
        [
            2.0 ** (-(10 * a + b) / 8.0) * left[:, a] * right[:, b]
            for a in range(10)
            for b in range(10)
        ]
    )


def _assert_morris_model_and_geometry(samples: np.ndarray, outputs: np.ndarray) -> None:
    assert samples.shape == (600, 2)
    assert outputs.shape == (600, 100)
    assert samples.dtype == outputs.dtype == np.dtype("float64")
    assert np.all(np.isfinite(samples))
    assert np.all(np.isfinite(outputs))
    assert np.all((samples >= 0.0) & (samples <= 1.0))
    np.testing.assert_allclose(samples * 7.0, np.rint(samples * 7.0), rtol=0, atol=1e-12)
    steps = np.diff(samples.reshape(200, 3, 2), axis=1)
    changes = np.abs(steps) > 1e-12
    np.testing.assert_array_equal(changes.sum(axis=2), np.ones((200, 2), dtype=int))
    np.testing.assert_array_equal(changes.sum(axis=1), np.ones((200, 2), dtype=int))
    np.testing.assert_allclose(np.abs(steps[changes]), 4.0 / 7.0, rtol=0, atol=1e-12)
    _, inverse, counts = np.unique(samples, axis=0, return_inverse=True, return_counts=True)
    assert np.any(counts > 1), "the declared grid must expose repeated parameter vectors"
    for group in np.flatnonzero(counts > 1):
        rows = outputs[inverse == group]
        np.testing.assert_array_equal(rows, np.repeat(rows[:1], rows.shape[0], axis=0))


def _preflight_case(
    plan: SensitivityPlan, directory: Path
) -> tuple[_MorrisCase, dict[str, object]]:
    samples = _without_global_rng(lambda: generate_sensitivity_samples(plan))
    outputs = _legendre_outputs(samples)
    _assert_morris_model_and_geometry(samples, outputs)
    # Qualification is deliberately completed with NumPy full SVD before any
    # tested sklearn PCA sees this case. No fixture is selected by its PCA output.
    singular_values = np.linalg.svd(
        outputs - outputs.mean(axis=0), full_matrices=False, compute_uv=False
    )
    rank = int(np.count_nonzero(singular_values > 1e-10 * singular_values[0]))
    relative_gap = float((singular_values[4] - singular_values[5]) / singular_values[0])
    reasons = []
    if rank <= 15:
        reasons.append("centered_rank_not_above_15")
    if relative_gap < 1e-3:
        reasons.append("relative_s5_s6_gap_below_1e-3")
    samples_hash = _fixture_matrix_digest(samples)
    outputs_hash = _fixture_matrix_digest(outputs)
    input_path = directory / f"seed-{plan.seed}-replica-{plan.replica_id}.json"
    with input_path.open("xb") as stream:
        stream.write(
            _canonical_bytes(
                {
                    "plan": plan.model_dump(mode="json"),
                    "samples": samples.tolist(),
                    "outputs": outputs.tolist(),
                }
            )
        )
    samples.setflags(write=False)
    outputs.setflags(write=False)
    case = _MorrisCase(plan, samples, outputs, input_path, samples_hash, outputs_hash)
    return case, {
        "seed": plan.seed,
        "replica_id": plan.replica_id,
        "shape": list(outputs.shape),
        "finite": True,
        "centered_rank": rank,
        "singular_values": singular_values.tolist(),
        "relative_s5_s6_gap": relative_gap,
        "qualification_reasons": reasons,
        "qualifies": not reasons,
        "canonical_input_path": str(input_path),
        "canonical_input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "samples_sha256": samples_hash,
        "outputs_sha256": outputs_hash,
    }


@pytest.fixture(scope="module")
def morris_preflight(tmp_path_factory: pytest.TempPathFactory) -> _MorrisPreflight:
    """Freeze every fixed-seed observation before selecting A and B."""
    _require_native_versions()
    directory = tmp_path_factory.mktemp("doe-pca-morris-preflight")
    observations: list[dict[str, object]] = []
    accepted: list[_MorrisCase] = []
    for seed in _FIXED_SEEDS:
        case, observation = _preflight_case(_morris_plan(seed), directory)
        observations.append(observation)
        if observation["qualifies"]:
            accepted.append(case)
    report_path = directory / "preflight.json"
    report: dict[str, object] = {
        "fixed_seed_order": list(_FIXED_SEEDS),
        "rank_cutoff_relative_to_s1": 1e-10,
        "required_rank_exclusive": 15,
        "required_relative_s5_s6_gap": 1e-3,
        "observations": observations,
        "accepted_seeds": [case.plan.seed for case in accepted[:2]],
    }
    if len(accepted) < 2:
        with report_path.open("xb") as stream:
            stream.write(_canonical_bytes(report))
        pytest.skip(f"NOT_RUN: fixture-preflight-blocked; complete observations at {report_path}")
    # Replica1 is a new actual experiment, never a metadata-only rename. Its
    # rank/gap observations are retained but do not select the fixed A/B pair.
    first_seed = accepted[0].plan.seed
    assert first_seed is not None
    replica, replica_observation = _preflight_case(
        _morris_plan(first_seed, replica_id=1), directory
    )
    report["replica_observation"] = replica_observation
    with report_path.open("xb") as stream:
        stream.write(_canonical_bytes(report))
    return _MorrisPreflight((accepted[0], accepted[1]), replica, report_path)


def _analyzer(svd_solver: _SvdSolver = "randomized") -> MultiOutputAnalyzer:
    return MultiOutputAnalyzer(
        max_components=5,
        min_variance_explained=1.0,
        svd_solver=svd_solver,
        n_oversamples=10,
        iterated_power=7,
        power_iteration_normalizer="QR",
    )


def _assert_profile(
    profile: object,
    *,
    random_seed: int,
    requested_solver: str = "randomized",
) -> None:
    assert isinstance(profile, dict)
    assert profile["profile_version"] == "doe-pca-v1"
    assert profile["backend"] == "sklearn"
    assert profile["backend_version"] == "1.8.0"
    assert profile["requested_solver"] == requested_solver
    assert profile["resolved_solver"] == "randomized"
    assert profile["random_seed"] == random_seed
    assert profile["n_components_requested"] == 5
    assert profile["n_components_cap"] == 5
    assert profile["min_variance_explained"] == 1.0
    assert profile["centering"] == "column_mean"
    assert profile["n_oversamples"] == 10
    assert profile["iterated_power"] == 7
    assert profile["power_iteration_normalizer"] == "QR"


def _assert_same_values(actual: object, expected: object) -> None:
    """Compare replay numbers at the packet tolerance while retaining typed structure."""
    if isinstance(expected, float):
        assert isinstance(actual, int | float)
        assert np.isfinite(actual)
        assert np.isfinite(expected)
        np.testing.assert_allclose(actual, expected, rtol=_REPLAY_RTOL, atol=_REPLAY_ATOL)
    elif isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key, expected_value in expected.items():
            _assert_same_values(actual[key], expected_value)
    elif isinstance(expected, list | tuple):
        assert isinstance(actual, type(expected))
        assert len(actual) == len(expected)
        for actual_value, expected_value in zip(actual, expected, strict=True):
            _assert_same_values(actual_value, expected_value)
    else:
        assert actual == expected


def _run_request(case: _MorrisCase, *, use_solver_defaults: bool = False) -> _Execution:
    def execute() -> _Execution:
        plan = SensitivityPlan.model_validate(case.plan.model_dump(mode="python"))
        samples = generate_sensitivity_samples(plan)
        outputs = _legendre_outputs(samples)
        # These are source identities frozen before the first tested PCA, not
        # fixture values selected after seeing an algorithm result.
        assert _fixture_matrix_digest(samples) == case.samples_sha256
        assert _fixture_matrix_digest(outputs) == case.outputs_sha256
        np.testing.assert_array_equal(samples, case.samples)
        np.testing.assert_array_equal(outputs, case.outputs)
        analyzer = (
            MultiOutputAnalyzer(max_components=5, min_variance_explained=1.0)
            if use_solver_defaults
            else _analyzer()
        )
        result = analyzer.analyze(plan, samples, outputs)
        assert _fixture_matrix_digest(samples) == case.samples_sha256
        assert _fixture_matrix_digest(outputs) == case.outputs_sha256
        return _Execution(samples, outputs, result)

    return _without_global_rng(execute)


def _assert_request_identity(case: _MorrisCase, execution: _Execution) -> None:
    from sklearn.decomposition import PCA  # type: ignore[import-untyped]

    result = execution.result
    streams = result.metadata["rng_streams"]
    assert isinstance(streams, dict)
    effective_seed = case.plan.seed
    if case.plan.replica_id:
        effective_seed = _derive_backend_seed(effective_seed, f"replica:{case.plan.replica_id}")
    assert streams["request_seed"] == effective_seed
    assert streams["replica_id"] == case.plan.replica_id
    assert streams["sampling"] == _derive_backend_seed(effective_seed, "sampling:morris")
    assert streams["analysis"] == _derive_backend_seed(effective_seed, "analysis:morris")
    assert streams[_PCA_STREAM] == _derive_backend_seed(effective_seed, _PCA_STREAM)
    stages = [streams[key] for key in ("sampling", "analysis", _PCA_STREAM, "model", "uncertainty")]
    assert all(isinstance(seed, int) for seed in stages)
    assert len(set(stages)) == len(stages)
    local_seed = streams[_PCA_STREAM]
    assert isinstance(local_seed, int)
    _assert_profile(result.metadata["pca_profile"], random_seed=local_seed)
    assert result.metadata["ordered_samples_sha256"] == _array_digest(execution.samples)
    assert result.metadata["ordered_outputs_sha256"] == _array_digest(execution.outputs)
    assert result.n_components_used == 5
    assert result.pca_variance_threshold_status == "unmet_limited"
    assert result.metadata["pca_scientific_sufficiency"] == "not_established"
    profile = result.metadata["pca_profile"]
    assert isinstance(profile, dict)
    assert profile["active_output_columns"] == list(range(1, 100))
    assert np.all(np.isfinite(result.explained_variance_ratio))
    # This second real sklearn call checks consumed local-seed/profile identity,
    # not scientific accuracy. The DCT test supplies the independent numerical
    # oracle. No numerical collaborator is replaced or intercepted.
    active_outputs = execution.outputs[:, np.var(execution.outputs, axis=0) > 0.0]
    expected_scores = _without_global_rng(
        lambda: PCA(
            n_components=5,
            svd_solver="randomized",
            n_oversamples=10,
            iterated_power=7,
            power_iteration_normalizer="QR",
            random_state=local_seed,
        ).fit_transform(active_outputs)
    )
    for index, component in enumerate(result.per_component):
        assert component.metadata["pca_profile"] == result.metadata["pca_profile"]
        assert component.metadata["analyzer_seed"] == streams["analysis"]
        assert component.metadata["ordered_outputs_sha256"] == _array_digest(
            expected_scores[:, index]
        )
        assert component.total_runs == component.successful_runs == 600
        assert component.failed_runs == 0
        assert component.metadata["effective_trajectory_ids"] == list(range(200))
        assert component.metadata["uncertainty_status"] == "ok"
        assert component.uncertainty is not None
        assert np.all(np.isfinite(list(component.mu_star.values())))
        assert np.all(np.isfinite(list(component.sigma.values())))


def _assert_replay(actual: _Execution, expected: _Execution) -> None:
    np.testing.assert_array_equal(actual.samples, expected.samples)
    np.testing.assert_array_equal(actual.outputs, expected.outputs)
    assert actual.result.metadata == expected.result.metadata
    assert actual.result.aggregate_ranking == expected.result.aggregate_ranking
    np.testing.assert_allclose(
        actual.result.explained_variance_ratio,
        expected.result.explained_variance_ratio,
        rtol=_REPLAY_RTOL,
        atol=_REPLAY_ATOL,
    )
    for actual_component, expected_component in zip(
        actual.result.per_component, expected.result.per_component, strict=True
    ):
        # Each digest binds the actual score array consumed by Morris. Same
        # request/seed/backend score signs are therefore not discarded here.
        assert (
            actual_component.metadata["ordered_outputs_sha256"]
            == expected_component.metadata["ordered_outputs_sha256"]
        )
        _assert_same_values(
            actual_component.model_dump(mode="python"),
            expected_component.model_dump(mode="python"),
        )


def test_randomized_dct_profile_matches_analytic_oracles_without_global_rng() -> None:
    """Qualify the actual randomized solver against the packet's analytic spectrum."""
    _require_native_versions()
    rows = np.arange(600, dtype=np.float64)[:, None]
    frequencies = np.arange(1, 101, dtype=np.float64)[None, :]
    basis = np.sqrt(2.0 / 600.0) * np.cos(np.pi * (rows + 0.5) * frequencies / 600.0)
    singular_values = 2.0 ** (-frequencies[0] / 4.0)
    outputs = basis * singular_values
    seed = _derive_backend_seed(13, _PCA_STREAM)
    assert seed is not None
    components, ratios, profile = _without_global_rng(
        lambda: _analyzer()._fit_pca(outputs, random_seed=seed)
    )
    assert len(components) == len(ratios) == 5
    scores = np.column_stack(components)
    assert scores.shape == (600, 5)
    assert np.all(np.isfinite(scores))
    _assert_profile(profile, random_seed=seed)
    expected_ratios = singular_values[:5] ** 2 / np.sum(singular_values**2)
    np.testing.assert_allclose(ratios, expected_ratios, rtol=1e-5, atol=1e-8)
    q, _ = np.linalg.qr(scores, mode="reduced")
    overlap_squared = float(np.linalg.norm(q.T @ basis[:, :5], ord="fro") ** 2)
    subspace_distance = np.sqrt(max(0.0, 10.0 - 2.0 * overlap_squared))
    assert subspace_distance <= 1e-3
    residual = np.linalg.norm(outputs - q @ (q.T @ outputs), ord="fro")
    optimal_residual = np.sqrt(np.sum(singular_values[5:] ** 2))
    assert residual <= 1.01 * optimal_residual + 1e-12


def test_morris_full_request_abba_replay_preserves_sources_streams_and_rng(
    morris_preflight: _MorrisPreflight,
) -> None:
    """AB followed by BA exercises the actual sampler→model→PCA→Morris/UQ path."""
    first_case, second_case = morris_preflight.pair
    first, second, second_replay, first_replay = [
        _run_request(case) for case in (first_case, second_case, second_case, first_case)
    ]
    for case, execution in ((first_case, first), (second_case, second)):
        _assert_request_identity(case, execution)
    _assert_replay(first_replay, first)
    _assert_replay(second_replay, second)
    assert not np.array_equal(first.samples, second.samples)
    assert first.result.metadata["rng_streams"] != second.result.metadata["rng_streams"]


def test_default_auto_solver_on_seeded_large_request_resolves_a_local_stream(
    morris_preflight: _MorrisPreflight,
) -> None:
    """The large auto-policy boundary must not fall back to ambient NumPy state."""
    case = morris_preflight.pair[0]
    first = _run_request(case, use_solver_defaults=True)
    repeated = _run_request(case, use_solver_defaults=True)
    local_seed = _derive_backend_seed(case.plan.seed, _PCA_STREAM)
    assert local_seed is not None
    _assert_profile(
        first.result.metadata["pca_profile"], random_seed=local_seed, requested_solver="auto"
    )
    _assert_replay(repeated, first)


def test_rng_oracle_detects_removed_local_seed_with_profile_declaration_retained(
    morris_preflight: _MorrisPreflight,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing actual seed consumption fails despite keeping the profile marker."""
    case = morris_preflight.pair[0]
    baseline = _run_request(case, use_solver_defaults=True)
    local_seed = _derive_backend_seed(case.plan.seed, _PCA_STREAM)
    assert local_seed is not None
    _assert_profile(
        baseline.result.metadata["pca_profile"], random_seed=local_seed, requested_solver="auto"
    )
    original_fit = MultiOutputAnalyzer._fit_pca
    declared_profiles: list[dict[str, object]] = []

    def fit_without_local_seed(
        analyzer: MultiOutputAnalyzer,
        outputs: np.ndarray,
        *,
        random_seed: int | None = None,
    ) -> tuple[list[np.ndarray], list[float], dict[str, object]]:
        components, ratios, profile = original_fit(analyzer, outputs, random_seed=None)
        profile["random_seed"] = random_seed
        declared_profiles.append(copy.deepcopy(profile))
        return components, ratios, profile

    before = _rng_snapshot()
    saved_state = copy.deepcopy(np.random.get_state())
    with monkeypatch.context() as removal:
        removal.setattr(MultiOutputAnalyzer, "_fit_pca", fit_without_local_seed)
        try:
            with pytest.raises(
                AssertionError, match="whole invocation changed external NumPy RNG state"
            ):
                _run_request(case, use_solver_defaults=True)
        finally:
            # This restoration belongs only to the destructive negative control;
            # no ordinary qualification invocation resets process-global RNG.
            np.random.set_state(saved_state)
    assert _rng_snapshot() == before
    assert len(declared_profiles) == 1
    _assert_profile(declared_profiles[0], random_seed=local_seed, requested_solver="auto")


def test_new_replica_has_actual_new_sampling_record_and_replay_identity(
    morris_preflight: _MorrisPreflight,
) -> None:
    """A replica changes real source rows and local streams rather than only metadata."""
    original_case = morris_preflight.pair[0]
    replica_case = morris_preflight.replica
    original = _run_request(original_case)
    replica = _run_request(replica_case)
    replay = _run_request(replica_case)
    _assert_request_identity(replica_case, replica)
    _assert_replay(replay, replica)
    assert original_case.plan.seed == replica_case.plan.seed
    assert original_case.plan.replica_id == 0
    assert replica_case.plan.replica_id == 1
    assert original_case.samples_sha256 != replica_case.samples_sha256
    assert original_case.outputs_sha256 != replica_case.outputs_sha256
    assert not np.array_equal(original.samples, replica.samples)
    assert original.result.metadata["rng_streams"] != replica.result.metadata["rng_streams"]


def _put_multi_output_receipt(store: FileSystemCAS, payload: object) -> ArtifactRef:
    from polisyos.core.artifacts import ArtifactWriteOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec

    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="doe_multi_output_analysis",
            media_type="application/json",
            schema=SchemaInfo(name="doe_multi_output_analysis", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def test_persisted_morris_profile_replays_from_record_after_constructor_defaults_change(
    store: FileSystemCAS,
    morris_preflight: _MorrisPreflight,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh replay consumes the recorded profile even when current defaults differ."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.methods.doe._receipt import (
        _load_multi_output_analysis,
        _persist_multi_output_analysis,
    )

    case = morris_preflight.pair[0]
    execution = _run_request(case)
    ref = _without_global_rng(
        lambda: _persist_multi_output_analysis(
            store, case.plan, execution.samples, execution.outputs, execution.result
        )
    )
    defaults = dict(MultiOutputAnalyzer.__init__.__kwdefaults__ or {})
    defaults.update(
        max_components=1,
        min_variance_explained=0.5,
        svd_solver="full",
        n_oversamples=17,
        iterated_power=1,
        power_iteration_normalizer="none",
    )
    monkeypatch.setattr(MultiOutputAnalyzer.__init__, "__kwdefaults__", defaults)
    fresh_store = FileSystemCAS(store.root)
    reopened = _without_global_rng(lambda: _load_multi_output_analysis(fresh_store, ref))
    _assert_replay(_Execution(execution.samples, execution.outputs, reopened), execution)
    assert reopened.metadata["pca_profile"] == execution.result.metadata["pca_profile"]


@pytest.mark.parametrize("mutation", ["solver", "seed", "profile", "missing_profile"])
def test_fresh_reader_refuses_changed_pca_provenance_with_original_matrix(
    store: FileSystemCAS,
    morris_preflight: _MorrisPreflight,
    mutation: str,
) -> None:
    """Hash-valid bytes and unchanged raw rows cannot authenticate a forged PCA profile."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
    from polisyos.scientist.methods.doe._receipt import (
        _load_multi_output_analysis,
        _persist_multi_output_analysis,
    )

    case = morris_preflight.pair[0]
    execution = _run_request(case)
    ref = _without_global_rng(
        lambda: _persist_multi_output_analysis(
            store, case.plan, execution.samples, execution.outputs, execution.result
        )
    )
    fresh_store = FileSystemCAS(store.root)
    # Establish the genuine positive at the same reader before any mutation.
    positive = _without_global_rng(lambda: _load_multi_output_analysis(fresh_store, ref))
    _assert_replay(_Execution(execution.samples, execution.outputs, positive), execution)
    payload = from_canonical_bytes(store.get_bytes(ref))
    result = payload["result"]
    original_samples = copy.deepcopy(payload["samples"])
    original_outputs = copy.deepcopy(payload["outputs"])
    metadata_containers = [result["metadata"]] + [
        component["metadata"] for component in result["per_component"]
    ]
    # Change every carried copy coherently, so a duplicated marker is not the
    # only reason for refusal. The raw source matrix and its hashes stay fixed.
    for metadata in metadata_containers:
        profile = metadata["pca_profile"]
        if mutation == "solver":
            profile["requested_solver"] = profile["resolved_solver"] = "full"
        elif mutation == "seed":
            profile["random_seed"] += 1
            streams = metadata.get("rng_streams")
            if isinstance(streams, dict):
                streams[_PCA_STREAM] = profile["random_seed"]
        elif mutation == "profile":
            profile["profile_version"] = "doe-pca-unqualified"
        else:
            del metadata["pca_profile"]
    if mutation != "missing_profile":
        # Rehash the changed profile too: a checksum-only consumer must not
        # distinguish this forgery merely because its old digest was retained.
        metadata = result["metadata"]
        metadata["analysis_id"] = hashlib.sha256(
            to_canonical_bytes(
                {
                    "design_id": metadata["design_id"],
                    "outputs_sha256": metadata["ordered_outputs_sha256"],
                    "backend": metadata["backend_identity"],
                    "pca_profile": metadata["pca_profile"],
                },
                CanonSpec(forbid_floats=False, exclude_none=False),
            )
        ).hexdigest()
    assert payload["samples"] == original_samples
    assert payload["outputs"] == original_outputs
    altered_ref = _put_multi_output_receipt(store, payload)
    assert fresh_store.verify(altered_ref).ok
    before = _rng_snapshot()
    with pytest.raises(ValueError, match=r"PCA|pca|profile|reproduc|bind"):
        _load_multi_output_analysis(fresh_store, altered_ref)
    assert _rng_snapshot() == before
