from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import pytest

import polisyos.berl as berl
import polisyos.berl.perturbations as perturbations
import polisyos.berl.service as service
import polisyos.berl.service.cache_identity as cache_identity
import polisyos.berl.service.results as results
from polisyos.berl import ExplanationOrchestrator, ExplanationRequest
from polisyos.berl.perturbations import (
    FeatureConstraint,
    PerturbedPoint,
    build_heldout_records,
    perturbation_support_rates,
    sample_local_perturbations,
)

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "berl" / "legacy_pre_move_fqns.pkl"
_FIXTURE_SHA256 = "2e332064b5218faad0aed2e9ee79422990e8cd4012fd711209ce3c278935e1e6"


def _trusted_fixture_bytes() -> bytes:
    payload = _FIXTURE.read_bytes()
    if hashlib.sha256(payload).hexdigest() != _FIXTURE_SHA256:
        pytest.fail("BERL historical pickle fixture does not match its frozen SHA-256")
    return payload


_EXPECTED_ROOT_EXPORTS = (
    "EmpiricalBoundResult",
    "ExplanationBundle",
    "ExplanationBundleStoreReadError",
    "ExplanationOrchestrator",
    "ExplanationRequest",
    "ExplanationValidationResult",
    "ValidationThresholds",
    "empirical_bernstein_upper_bound",
    "estimate_local_infidelity",
    "hoeffding_upper_bound",
    "load_explanation_bundle",
    "persist_explanation_bundle",
    "summarize_explanation_response",
    "validate_explanation_bundle",
    "validate_persisted_explanation_bundle_payload",
)


def test_berl_root_exports_and_old_module_objects_keep_identity() -> None:
    assert tuple(berl.__all__) == _EXPECTED_ROOT_EXPORTS
    assert berl.ExplanationRequest is service.ExplanationRequest is ExplanationRequest
    assert (
        berl.ExplanationOrchestrator is service.ExplanationOrchestrator is ExplanationOrchestrator
    )
    assert ExplanationRequest.__module__ == "polisyos.berl.service"
    assert ExplanationOrchestrator.__module__ == "polisyos.berl.service"
    assert FeatureConstraint.__module__ == "polisyos.berl.perturbations"
    assert PerturbedPoint.__module__ == "polisyos.berl.perturbations"
    assert service.default_adapters.__module__ == "polisyos.berl.service"
    assert service.detect_redundancy_clusters_from_bundle.__module__ == "polisyos.berl.service"


def test_historical_service_module_names_remain_package_attributes() -> None:
    cache_names = (
        "_adapter_cache_identity",
        "_effective_method_id",
        "_effective_request_key",
        "_freeze",
        "_freeze_immutable_configuration",
        "_freeze_scalar",
        "_is_builtin_adapter",
        "_string_param",
    )
    result_names = (
        "_diagnostic_method",
        "_feature_in_redundancy_cluster",
        "_reidentify_method",
        "_scope_from_raw",
        "_top_feature_from_vectors",
    )
    for name in cache_names:
        candidate = getattr(cache_identity, name)
        assert getattr(service, name) is candidate
        assert candidate.__module__ == "polisyos.berl.service.cache_identity"
    for name in result_names:
        candidate = getattr(results, name)
        assert getattr(service, name) is candidate
        assert candidate.__module__ == "polisyos.berl.service.results"


def test_historical_pickle_loads_through_canonical_package_fqns() -> None:
    request, constraint = pickle.loads(  # noqa: S301 -- fixed repo-owned pre-move fixture; hash-checked above
        _trusted_fixture_bytes()
    )

    assert type(request) is ExplanationRequest
    assert type(constraint) is FeatureConstraint
    assert request.prediction_id == "pre-move-fixture-prediction"
    assert constraint.lower == 0.25
    assert constraint.upper == 7.5
    assert type(request).__module__ == "polisyos.berl.service"
    assert type(constraint).__module__ == "polisyos.berl.perturbations"
    round_trip = pickle.loads(  # noqa: S301 -- locally produced from hash-pinned fixture types
        pickle.dumps((request, constraint))
    )
    assert round_trip == (request, constraint)


def test_old_pickle_module_binding_is_behavioral_not_a_marker() -> None:
    original = _trusted_fixture_bytes()
    mutated = original.replace(b"polisyos.berl.service", b"polisyos.berl._ervice", 1)
    assert mutated != original
    with pytest.raises(ModuleNotFoundError):
        pickle.loads(mutated)  # noqa: S301 -- one-name mutation of hash-pinned repo fixture


def test_package_import_paths_export_the_real_perturbation_owners() -> None:
    assert perturbations.FeatureConstraint is FeatureConstraint
    assert perturbations.PerturbedPoint is PerturbedPoint
    assert perturbations.sample_local_perturbations is sample_local_perturbations
    assert perturbations.build_heldout_records is build_heldout_records
    assert perturbations.perturbation_support_rates is perturbation_support_rates
