"""C49 current-observation and resource-stop discriminators (no authority claim)."""

from __future__ import annotations

import hashlib

import pytest

from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceObservation,
    ConvergenceStrategy,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _observation(number: int, *, version: str | None = "fixture-weights-1", **changes):
    source = f"actual-response-{number}"
    values = dict(
        subject_ref=_digest("selected-problem"),
        request_ref=_digest(f"request-{number}"),
        producer_request_ref=_digest(f"actual-core-request-{number}"),
        source_ref=_digest(source),
        producer_response_ref=_digest(source),
        producer_event_id=f"provider-event-{number}",
        model_ref="fixture-model",
        model_version=version,
        pass_number=number,
        value=0.2 + number * 0.001,
    )
    values.update(changes)
    return ConvergenceObservation(**values), source


def _consume(detector, observation, source, **changes):
    values = dict(
        subject_ref=_digest("selected-problem"),
        request_ref=observation.request_ref,
        source_text=source,
        value=observation.value,
        pass_number=observation.pass_number,
    )
    values.update(changes)
    return detector.check_candidate_observation(observation, **values)


def _detector(**changes):
    values = dict(threshold=0.01, min_iterations=2, max_iterations=10, window_size=2)
    values.update(changes)
    return ConvergenceDetector(ConvergenceConfig(**values))


def test_fresh_current_same_version_observations_bound_optional_iteration():
    detector = _detector()
    first, source1 = _observation(1)
    assert not _consume(detector, first, source1).should_stop
    second, source2 = _observation(2)
    state = _consume(detector, second, source2)
    assert state.should_stop and state.stop_kind == "heuristic_stability"
    assert not state.scientific_converged
    assert state.last_checked_observation == second
    assert state.profile == detector.config


@pytest.mark.parametrize("alteration", ["raw", "subject", "request", "value", "pass"])
def test_removal_control_current_binding_is_observable(alteration):
    detector = _detector()
    first, source1 = _observation(1)
    _consume(detector, first, source1)
    second, source2 = _observation(2)
    changes = {
        "raw": {"source_text": source2 + " altered"},
        "subject": {"subject_ref": _digest("foreign-problem")},
        "request": {"request_ref": _digest("foreign-request")},
        "value": {"value": 0.8},
        "pass": {"pass_number": 3},
    }[alteration]
    state = _consume(detector, second, source2, **changes)
    assert not state.should_stop
    assert state.observation_status == "current_observation_binding_mismatch"
    assert state.last_checked_observation == first


def test_event_replay_reuse_and_model_epoch_do_not_fill_a_current_window():
    for change in (
        {"producer_event_id": "provider-event-1"},
        {"producer_kind": "reuse"},
        {"model_version": "fixture-weights-2"},
    ):
        detector = _detector()
        first, source1 = _observation(1)
        _consume(detector, first, source1)
        second, source2 = _observation(2, **change)
        assert not _consume(detector, second, source2).should_stop


def test_missing_version_preserves_candidate_and_raw_similarity_without_stability():
    detector = _detector()
    for number in (1, 2, 3):
        view, source = _observation(number, version=None)
        state = _consume(detector, view, source)
        assert not state.should_stop
        assert state.observation_status == "model_version_not_established"
        assert state.last_checked_observation == view

    class UnversionedEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    embeddings = ConvergenceDetector(
        ConvergenceConfig(strategy=ConvergenceStrategy.EMBEDDING_COSINE, threshold=0.99),
        embedder=UnversionedEmbedder(),
    )
    embeddings.check_with_text(0.2, "first")
    state = embeddings.check_with_text(0.2, "second")
    assert state.raw_embedding_similarity == pytest.approx(1.0)
    assert state.embedding_identity_status == "not_established"
    assert not state.should_stop


def test_failed_or_skipped_pass_cannot_reuse_confidence_but_resource_cap_still_stops():
    detector = _detector(min_iterations=1, max_iterations=1)
    state = detector.check_candidate_observation(
        None,
        subject_ref=_digest("selected-problem"),
        request_ref=None,
        source_text=None,
        value=None,
        pass_number=1,
        unavailable_reason="pass_parse_failed",
    )
    assert state.should_stop and state.stop_kind == "resource_limit"
    assert state.reason == "max_iterations" and not state.scientific_converged
    assert state.observation_status == "pass_parse_failed"


def test_profile_is_detached_from_caller_mutations():
    profile = ConvergenceConfig(threshold=0.01)
    detector = ConvergenceDetector(profile)
    profile.threshold = 0.8
    detached = detector.config
    detached.threshold = 0.9
    assert detector.config.threshold == 0.01
